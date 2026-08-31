"""Feature-selection dialog + publish-dialog pre-check — PI-444 (REQ-546).

Covers the new per-instance feature-selection dialog (list, pre-check,
save/clear PATCH bodies, the nothing-checked guard path) and the publish
dialog's scope list pre-checking from the validate result's reported
selection resolution.
"""

from __future__ import annotations

from crmbuilder_v2.ui.dialogs.feature_selection_dialog import (
    FeatureSelectionDialog,
)
from crmbuilder_v2.ui.dialogs.publish_dialog import PublishDialog
from PySide6.QtCore import Qt


class _FakeClient:
    def __init__(self, entities=None, validate_result=None):
        self._entities = entities or []
        self._v = validate_result
        self.patches: list[tuple[str, dict]] = []

    def list_entities(self, *, include_deleted=False):
        return self._entities

    def patch_instance(self, identifier, body):
        self.patches.append((identifier, body))
        record = {"instance_identifier": identifier}
        record.update(body)
        return record

    def publish_validate_instance(self, identifier, scope=None):
        return self._v


_ENTITIES = [
    {"entity_identifier": "ENT-001", "entity_name": "Contact"},
    {"entity_identifier": "ENT-002", "entity_name": "Account"},
]


def _record(selection=None):
    return {
        "instance_identifier": "INST-001",
        "instance_name": "Chapter target",
        "instance_feature_selection": selection,
    }


def _checked(dlg):
    return [
        dlg._list.item(i).data(Qt.ItemDataRole.UserRole)
        for i in range(dlg._list.count())
        if dlg._list.item(i).checkState() == Qt.CheckState.Checked
    ]


# --- FeatureSelectionDialog -------------------------------------------------


def test_dialog_lists_entities_prechecked_from_stored(qtbot):
    client = _FakeClient(entities=_ENTITIES)
    dlg = FeatureSelectionDialog(client, _record(["ENT-002"]))
    qtbot.addWidget(dlg)
    assert dlg._list.count() == 2
    assert _checked(dlg) == ["ENT-002"]


def test_dialog_unresolved_stored_id_listed_and_flagged(qtbot):
    client = _FakeClient(entities=_ENTITIES)
    dlg = FeatureSelectionDialog(client, _record(["ENT-001", "ENT-099"]))
    qtbot.addWidget(dlg)
    assert dlg._list.count() == 3
    labels = [dlg._list.item(i).text() for i in range(dlg._list.count())]
    assert any("no longer in the design" in text for text in labels)
    assert set(_checked(dlg)) == {"ENT-001", "ENT-099"}


def test_save_patches_checked_identifiers(qtbot):
    client = _FakeClient(entities=_ENTITIES)
    dlg = FeatureSelectionDialog(client, _record(None))
    qtbot.addWidget(dlg)
    dlg._list.item(0).setCheckState(Qt.CheckState.Checked)
    dlg._on_save_clicked()
    assert client.patches == [
        ("INST-001", {"instance_feature_selection": ["ENT-001"]})
    ]
    assert dlg.result() == 1  # accepted


def test_clear_patches_null(qtbot):
    client = _FakeClient(entities=_ENTITIES)
    dlg = FeatureSelectionDialog(client, _record(["ENT-001"]))
    qtbot.addWidget(dlg)
    dlg._on_clear_clicked()
    assert client.patches == [
        ("INST-001", {"instance_feature_selection": None})
    ]
    assert dlg.result() == 1


def test_save_with_nothing_checked_does_not_patch(qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from crmbuilder_v2.ui.widgets.selectable_text import CopyableMessageBox

    monkeypatch.setattr(
        CopyableMessageBox,
        "information",
        lambda *a, **k: QMessageBox.StandardButton.Ok,
    )
    client = _FakeClient(entities=_ENTITIES)
    dlg = FeatureSelectionDialog(client, _record(None))
    qtbot.addWidget(dlg)
    dlg._on_save_clicked()
    assert client.patches == []
    assert dlg.result() == 0  # still open / not accepted


# --- PublishDialog pre-check (REQ-546) --------------------------------------


def _validate_result_with_selection(filenames, unresolved=()):
    return {
        "engine": "espocrm",
        "target_instance": "INST-001",
        "validate_only": True,
        "validation_failed": False,
        "programs": [
            {"filename": "Contact.yaml", "validation_errors": []},
            {"filename": "Account.yaml", "validation_errors": []},
        ],
        "deferrals": [],
        "manual_config": None,
        "scope_source": "full_design",
        "feature_selection": {
            "filenames": list(filenames),
            "resolved": [],
            "unresolved": list(unresolved),
        },
    }


def test_publish_dialog_prechecks_stored_selection(qtbot):
    client = _FakeClient(
        validate_result=_validate_result_with_selection(["Account.yaml"])
    )
    dlg = PublishDialog(client, _record(["ENT-002"]))
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: dlg._revalidate_btn.isEnabled(), timeout=3000)
    # Only the stored selection's program is checked → subset scope.
    assert dlg._selected_scope() == ["Account.yaml"]
    assert "stored" in dlg._scope_label.text().lower()


def test_publish_dialog_notes_unresolved_entries(qtbot):
    client = _FakeClient(
        validate_result=_validate_result_with_selection(
            ["Account.yaml"], unresolved=["ENT-099"]
        )
    )
    dlg = PublishDialog(client, _record(["ENT-002", "ENT-099"]))
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: dlg._revalidate_btn.isEnabled(), timeout=3000)
    assert "no longer in the design" in dlg._scope_label.text()

"""Tests for the AuditEntry sidebar widget.

Covers the audit-v1.2 Prompt J additions (DEC-180, DEC-181):

* Entity picker populated by pre-flight ``get_all_scopes()`` discovery,
  including Select All / Select None buttons and the
  ``_get_selected_entities`` semantic (``None`` for "all checked" /
  "empty picker", a set for a partial selection)
* Two new scope checkboxes — Security and Filtered tabs — default-True
* Overwrite-confirmation dialog when the output directory already
  contains audit YAML output
* No-entities-selected warning before launching the progress dialog
* Pre-flight discovery failure leaves the rest of the UI usable

The tests boot an offscreen ``QApplication`` and instantiate the
``AuditEntry`` widget directly. Network seams (``load_instance_detail``,
``EspoAdminClient``) and the audit progress dialog are patched so no
real network or worker thread is started.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from automation.ui.deployment.deployment_logic import (
    InstanceDetail,
    InstanceRow,
)


@pytest.fixture(scope="module", autouse=True)
def _qapplication():
    """Boot an offscreen QApplication for the widget tests."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_instance() -> InstanceRow:
    return InstanceRow(
        id=42,
        name="Audit Test",
        code="AUDITTEST",
        environment="test",
        url="https://audit.example.com",
        is_default=False,
    )


def _make_instance_detail() -> InstanceDetail:
    return InstanceDetail(
        id=42,
        name="Audit Test",
        code="AUDITTEST",
        environment="test",
        url="https://audit.example.com",
        username="admin",
        password="adminpw",
        description=None,
        is_default=False,
        created_at=None,
        updated_at=None,
    )


def _three_entity_scopes() -> dict[str, dict]:
    """Three entity-bearing scopes plus one tab-only scope to confirm
    the picker filters out non-entity scopes."""
    return {
        "Contact": {"entity": True, "isCustom": False},
        "Account": {"entity": True, "isCustom": False},
        "CEngagement": {"entity": True, "isCustom": True},
        "MyEngagements": {"entity": False, "tab": True, "isCustom": True},
    }


def _patch_picker_population(
    monkeypatch: pytest.MonkeyPatch,
    scopes_response: tuple[int, dict | None],
    *,
    detail: InstanceDetail | None = None,
) -> MagicMock:
    """Patch ``load_instance_detail`` and ``EspoAdminClient`` so the
    entity-picker pre-flight runs without touching the network.

    Returns the mocked client instance so tests can assert on its
    method calls.
    """
    from automation.ui.deployment import audit_entry as audit_entry_module
    from espo_impl.core import api_client as api_client_module

    monkeypatch.setattr(
        audit_entry_module, "load_instance_detail",
        lambda _conn, _id: detail or _make_instance_detail(),
    )
    mock_client = MagicMock()
    mock_client.get_all_scopes.return_value = scopes_response
    monkeypatch.setattr(
        api_client_module, "EspoAdminClient",
        MagicMock(return_value=mock_client),
    )
    return mock_client


def _fake_conn() -> MagicMock:
    """A MagicMock standing in for a sqlite3 connection. Both the
    PRAGMA call in ``_on_start_audit`` and the audit-history query in
    ``_update_last_audit_info`` work without raising.
    """
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    conn.execute.return_value.fetchall.return_value = []
    return conn


def _build_entry(
    monkeypatch: pytest.MonkeyPatch,
    scopes_response: tuple[int, dict | None] = (200, None),
    *,
    populate: bool = True,
    project_folder: str | None = "/tmp/audit-project",
):
    """Construct an ``AuditEntry`` widget, optionally invoking
    ``refresh()`` to populate the picker. ``scopes_response`` controls
    what the mocked ``get_all_scopes`` returns; default is an empty
    success that leaves the picker empty.
    """
    from automation.ui.deployment import audit_entry as audit_entry_module

    if populate:
        _patch_picker_population(monkeypatch, scopes_response)

    widget = audit_entry_module.AuditEntry()
    widget.show()
    if populate:
        widget.refresh(
            conn=_fake_conn(),
            instance=_make_instance(),
            project_folder=project_folder,
            has_instances=True,
        )
    return widget


# ---------------------------------------------------------------------------
# Picker population
# ---------------------------------------------------------------------------


def test_audit_entry_picker_populates_on_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful ``get_all_scopes`` response populates the picker
    with one checkable item per entity scope, skipping tab-only
    scopes, and every item is checked by default."""
    widget = _build_entry(
        monkeypatch,
        scopes_response=(200, _three_entity_scopes()),
    )
    try:
        names = [
            widget._entity_picker.item(i).text()
            for i in range(widget._entity_picker.count())
        ]
        # Sorted alphabetically; MyEngagements is a tab scope, excluded.
        assert names == ["Account", "CEngagement", "Contact"]
        from PySide6.QtCore import Qt
        for i in range(widget._entity_picker.count()):
            assert (
                widget._entity_picker.item(i).checkState()
                == Qt.CheckState.Checked
            )
    finally:
        widget.close()
        widget.deleteLater()


def test_audit_entry_picker_select_all_button(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Click Select All on a partially-unchecked picker → every item
    is checked."""
    from PySide6.QtCore import Qt

    widget = _build_entry(
        monkeypatch,
        scopes_response=(200, _three_entity_scopes()),
    )
    try:
        widget._entity_picker.item(0).setCheckState(Qt.CheckState.Unchecked)
        widget._on_select_all_entities()
        for i in range(widget._entity_picker.count()):
            assert (
                widget._entity_picker.item(i).checkState()
                == Qt.CheckState.Checked
            )
    finally:
        widget.close()
        widget.deleteLater()


def test_audit_entry_picker_select_none_button(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Click Select None → every item is unchecked."""
    from PySide6.QtCore import Qt

    widget = _build_entry(
        monkeypatch,
        scopes_response=(200, _three_entity_scopes()),
    )
    try:
        widget._on_select_none_entities()
        for i in range(widget._entity_picker.count()):
            assert (
                widget._entity_picker.item(i).checkState()
                == Qt.CheckState.Unchecked
            )
    finally:
        widget.close()
        widget.deleteLater()


def test_audit_entry_picker_failure_keeps_ui_usable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An HTTP failure on the scope pre-flight leaves the picker empty,
    surfaces an error message in the loading label, and does not
    tear down the rest of the audit-entry UI."""
    widget = _build_entry(monkeypatch, scopes_response=(500, None))
    try:
        assert widget._entity_picker.count() == 0
        assert widget._picker_loading_label.isVisible()
        assert "HTTP 500" in widget._picker_loading_label.text()
        # The scope checkboxes were still built and remain interactive.
        assert widget._cb_security.isEnabled()
        assert widget._cb_filtered_tabs.isEnabled()
        assert widget._start_btn.isEnabled()
    finally:
        widget.close()
        widget.deleteLater()


# ---------------------------------------------------------------------------
# Default checkbox state (DEC-180)
# ---------------------------------------------------------------------------


def test_audit_entry_security_checkbox_default_checked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from automation.ui.deployment import audit_entry as audit_entry_module

    widget = audit_entry_module.AuditEntry()
    try:
        assert widget._cb_security.isChecked() is True
    finally:
        widget.close()
        widget.deleteLater()


def test_audit_entry_filtered_tabs_checkbox_default_checked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from automation.ui.deployment import audit_entry as audit_entry_module

    widget = audit_entry_module.AuditEntry()
    try:
        assert widget._cb_filtered_tabs.isChecked() is True
    finally:
        widget.close()
        widget.deleteLater()


# ---------------------------------------------------------------------------
# _on_start_audit — AuditOptions construction
# ---------------------------------------------------------------------------


def _patch_progress_dialog(
    monkeypatch: pytest.MonkeyPatch,
) -> MagicMock:
    """Replace AuditProgressDialog with a MagicMock so _on_start_audit
    can be exercised without launching a worker thread. Returns the
    class mock so tests can read constructor kwargs."""
    from automation.ui.deployment import audit_entry as audit_entry_module

    dialog_class = MagicMock()
    # The instance returned by the class must have an exec() that
    # returns immediately so _on_start_audit completes synchronously.
    dialog_instance = MagicMock()
    dialog_instance.exec.return_value = 0
    dialog_class.return_value = dialog_instance
    monkeypatch.setattr(
        audit_entry_module, "AuditProgressDialog", dialog_class,
    )
    return dialog_class


def test_audit_entry_start_audit_passes_selected_entities(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """With a partial selection (one entity unchecked), the AuditOptions
    handed to the progress dialog contains the expected subset."""
    from PySide6.QtCore import Qt

    widget = _build_entry(
        monkeypatch,
        scopes_response=(200, _three_entity_scopes()),
        project_folder=str(tmp_path),
    )
    try:
        # Uncheck Account; expect Contact + CEngagement to flow through.
        for i in range(widget._entity_picker.count()):
            if widget._entity_picker.item(i).text() == "Account":
                widget._entity_picker.item(i).setCheckState(
                    Qt.CheckState.Unchecked
                )

        dialog_class = _patch_progress_dialog(monkeypatch)
        widget._on_start_audit()

        dialog_class.assert_called_once()
        options = dialog_class.call_args.kwargs["options"]
        assert options.selected_entities == {"Contact", "CEngagement"}
        # And the two new checkbox values propagate.
        assert options.include_security is True
        assert options.include_filtered_tabs is True
    finally:
        widget.close()
        widget.deleteLater()


def test_audit_entry_start_audit_all_checked_passes_none(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When every picker item is checked, ``selected_entities=None``
    is passed (preserves the audit-everything semantic)."""
    widget = _build_entry(
        monkeypatch,
        scopes_response=(200, _three_entity_scopes()),
        project_folder=str(tmp_path),
    )
    try:
        dialog_class = _patch_progress_dialog(monkeypatch)
        widget._on_start_audit()

        dialog_class.assert_called_once()
        options = dialog_class.call_args.kwargs["options"]
        assert options.selected_entities is None
    finally:
        widget.close()
        widget.deleteLater()


def test_audit_entry_no_entities_selected_shows_warning(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Select None → Start Audit → information dialog fires and the
    progress dialog is NOT launched."""
    from automation.ui.deployment import audit_entry as audit_entry_module

    widget = _build_entry(
        monkeypatch,
        scopes_response=(200, _three_entity_scopes()),
        project_folder=str(tmp_path),
    )
    try:
        widget._on_select_none_entities()

        info_mock = MagicMock()
        monkeypatch.setattr(
            audit_entry_module.QMessageBox, "information", info_mock,
        )
        dialog_class = _patch_progress_dialog(monkeypatch)

        widget._on_start_audit()

        info_mock.assert_called_once()
        # Title is the second positional argument to QMessageBox.information
        assert info_mock.call_args.args[1] == "No Entities Selected"
        dialog_class.assert_not_called()
    finally:
        widget.close()
        widget.deleteLater()


# ---------------------------------------------------------------------------
# Overwrite-confirmation dialog (DEC-181)
# ---------------------------------------------------------------------------


def _stub_widget_for_start(
    project_folder: Path,
    selected: set[str] | None = None,
) -> SimpleNamespace:
    """Build a minimal SimpleNamespace usable as ``self`` when invoking
    ``AuditEntry._on_start_audit`` directly. Avoids the cost of building
    a real Qt widget for tests that only care about the overwrite-
    confirmation branch.
    """
    stub = SimpleNamespace(
        _instance=_make_instance(),
        _conn=_fake_conn(),
        _project_folder=str(project_folder),
        _output_entry=None,
        _get_selected_entities=lambda: selected,
    )
    # All the checkbox attributes must respond to isChecked()
    for cb_name in (
        "_cb_custom_fields", "_cb_native_fields", "_cb_detail_layouts",
        "_cb_list_layouts", "_cb_relationships", "_cb_include_native",
        "_cb_security", "_cb_filtered_tabs", "_cb_email_templates",
    ):
        setattr(stub, cb_name, MagicMock(isChecked=MagicMock(return_value=True)))
    stub._update_last_audit_info = lambda: None
    return stub


def test_audit_entry_overwrite_confirmation_fires_on_existing_yaml(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The output directory already contains a stub ``.yaml`` file;
    Start Audit fires a QMessageBox.warning. When Cancel is chosen the
    progress dialog is NOT launched."""
    from automation.ui.deployment import audit_entry as audit_entry_module

    # Force the timestamp into a deterministic value so we can pre-
    # populate the matching output directory.
    fake_now = MagicMock()
    fake_now.strftime.return_value = "20260524-080000"
    fake_dt_class = MagicMock()
    fake_dt_class.now.return_value = fake_now
    monkeypatch.setattr(audit_entry_module, "datetime", fake_dt_class)

    output_dir = tmp_path / "programs" / "audit-20260524-080000"
    output_dir.mkdir(parents=True)
    (output_dir / "Engagement.yaml").write_text("stub")

    monkeypatch.setattr(
        audit_entry_module, "load_instance_detail",
        lambda _conn, _id: _make_instance_detail(),
    )

    from PySide6.QtWidgets import QMessageBox
    warning_mock = MagicMock(return_value=QMessageBox.StandardButton.Cancel)
    monkeypatch.setattr(
        audit_entry_module.QMessageBox, "warning", warning_mock,
    )
    dialog_class = _patch_progress_dialog(monkeypatch)

    stub = _stub_widget_for_start(tmp_path, selected=None)
    audit_entry_module.AuditEntry._on_start_audit(stub)

    warning_mock.assert_called_once()
    assert warning_mock.call_args.args[1] == "Overwrite Existing Audit Output?"
    dialog_class.assert_not_called()


def test_audit_entry_overwrite_confirmation_skipped_when_empty(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Empty output directory → no confirmation dialog fires; the
    progress dialog is launched normally."""
    from automation.ui.deployment import audit_entry as audit_entry_module

    fake_now = MagicMock()
    fake_now.strftime.return_value = "20260524-090000"
    fake_dt_class = MagicMock()
    fake_dt_class.now.return_value = fake_now
    monkeypatch.setattr(audit_entry_module, "datetime", fake_dt_class)

    monkeypatch.setattr(
        audit_entry_module, "load_instance_detail",
        lambda _conn, _id: _make_instance_detail(),
    )

    warning_mock = MagicMock()
    monkeypatch.setattr(
        audit_entry_module.QMessageBox, "warning", warning_mock,
    )
    dialog_class = _patch_progress_dialog(monkeypatch)

    stub = _stub_widget_for_start(tmp_path, selected=None)
    audit_entry_module.AuditEntry._on_start_audit(stub)

    warning_mock.assert_not_called()
    dialog_class.assert_called_once()

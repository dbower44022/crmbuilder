"""Publish dialog + client tests — PRJ-042 / PI-251 (REQ-287 + REQ-288).

Covers the pure rich-text renderers, the StorageClient publish request paths,
and the dialog's core behavior: it validates on open and only enables the
Publish button when every program is valid.
"""

from __future__ import annotations

from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.publish_dialog import (
    PublishDialog,
    render_manual_config_html,
    render_preview_html,
    render_publish_html,
    render_validate_html,
    render_verification_html,
)


def _validate_result(*, failed, programs, deferrals=None, manual_config=None):
    return {
        "engine": "espocrm",
        "target_instance": "INST-001",
        "validate_only": True,
        "validation_failed": failed,
        "programs": programs,
        "deferrals": deferrals or [],
        "manual_config": manual_config,
    }


# -- renderers ---------------------------------------------------------------


def test_render_validate_clean():
    out = render_validate_html(
        _validate_result(
            failed=False,
            programs=[{"filename": "Contact.yaml", "validation_errors": []}],
        )
    )
    assert "Contact.yaml" in out
    assert "&#10003;" in out  # check mark
    assert "ready to publish" in out


def test_render_validate_errors_and_deferrals():
    out = render_validate_html(
        _validate_result(
            failed=True,
            programs=[
                {
                    "filename": "Account.yaml",
                    "validation_errors": ["accountType not found"],
                }
            ],
            deferrals=[{"kind": "workflow"}],
        )
    )
    assert "&#10007;" in out  # cross mark
    assert "accountType not found" in out
    assert "Fix the errors" in out
    assert "manual" in out.lower()


def test_render_validate_escapes_html():
    out = render_validate_html(
        _validate_result(
            failed=True,
            programs=[
                {"filename": "X.yaml", "validation_errors": ["<script>oops"]}
            ],
        )
    )
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_render_publish_deployed_with_counts():
    out = render_publish_html(
        {
            "engine": "espocrm",
            "target_instance": "INST-001",
            "programs": [
                {
                    "filename": "Contact.yaml",
                    "deployed": True,
                    "summary": {"created": 3, "updated": 1},
                }
            ],
        }
    )
    assert "deployed" in out
    assert "3 created" in out
    assert "1 updated" in out


def test_render_publish_not_deployed():
    out = render_publish_html(
        {
            "engine": "espocrm",
            "target_instance": "INST-001",
            "programs": [
                {
                    "filename": "Account.yaml",
                    "deployed": False,
                    "validation_errors": ["bad"],
                }
            ],
        }
    )
    assert "&#10007;" in out
    assert "validation error" in out


# -- manual-config checklist (REQ-294) ---------------------------------------


_DEFERRALS = [
    {
        "kind": "view",
        "identifier": "VIW-1",
        "name": "Active Mentors",
        "parent": "Contact",
        "detail": "saved-view filter is not expressible over REST",
    },
    {
        "kind": "workflow_action",
        "identifier": "AUT-1",
        "name": "Send welcome email",
        "parent": "Contact",
        "detail": "workflows need the Advanced Pack + admin UI",
    },
    {
        "kind": "dedup_rule",
        "identifier": "DUP-1",
        "name": "email match",
        "parent": "Contact",
        "detail": "duplicate-check rules have no public write path",
    },
]


def test_render_manual_config_groups_and_labels():
    out = render_manual_config_html({"deferrals": _DEFERRALS})
    # Header names the count.
    assert "Manual configuration required (3 item(s))" in out
    # Friendly group labels, not raw kind tokens.
    assert "Saved views" in out
    assert "Workflows" in out
    assert "Duplicate-check rules" in out
    assert "workflow_action" not in out
    # Each item is a checklist row with its name + reason.
    assert "&#9744;" in out  # ballot box (checkbox)
    assert "Active Mentors" in out
    assert "saved-view filter is not expressible over REST" in out
    # Parent context surfaces.
    assert "Contact" in out


def test_render_manual_config_empty_is_blank():
    assert render_manual_config_html({"deferrals": []}) == ""
    assert render_manual_config_html({}) == ""


def test_render_manual_config_companion_only():
    out = render_manual_config_html(
        {"deferrals": [], "manual_config": "# MANUAL-CONFIG\n..."}
    )
    assert "MANUAL-CONFIG.md" in out


def test_render_manual_config_unknown_kind_falls_back():
    out = render_manual_config_html(
        {"deferrals": [{"kind": "some_new_thing", "name": "X"}]}
    )
    assert "Some new thing" in out


def test_render_manual_config_escapes_html():
    out = render_manual_config_html(
        {"deferrals": [{"kind": "view", "name": "<script>x", "detail": "<b>"}]}
    )
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_render_publish_includes_checklist():
    out = render_publish_html(
        {
            "engine": "espocrm",
            "target_instance": "INST-001",
            "programs": [{"filename": "Contact.yaml", "deployed": True}],
            "deferrals": _DEFERRALS,
        }
    )
    assert "Manual configuration required" in out
    assert "Send welcome email" in out


def test_render_preview_includes_checklist():
    out = render_preview_html(
        {
            "engine": "espocrm",
            "target_instance": "INST-001",
            "programs": [
                {"filename": "Contact.yaml", "summary": {}, "validation_errors": []}
            ],
            "deferrals": _DEFERRALS,
        }
    )
    assert "Manual configuration required" in out
    assert "email match" in out


# -- post-publish verification (REQ-291) -------------------------------------


def test_render_verification_all_present():
    out = render_verification_html(
        {
            "verification": {
                "ran": True,
                "conclusive": True,
                "all_present": True,
                "entities": [
                    {
                        "entity": "Contact",
                        "present": True,
                        "fields_present": ["nickName"],
                        "fields_missing": [],
                        "status": "matching",
                    }
                ],
                "warnings": [],
            }
        }
    )
    assert "Verified on target" in out
    assert "Contact" in out
    assert "&#10003;" in out


def test_render_verification_with_gaps():
    out = render_verification_html(
        {
            "verification": {
                "ran": True,
                "conclusive": True,
                "all_present": False,
                "entities": [
                    {
                        "entity": "CEngagement",
                        "present": False,
                        "fields_missing": ["stage"],
                        "status": "missing",
                    },
                    {
                        "entity": "Contact",
                        "present": True,
                        "fields_present": ["a"],
                        "fields_missing": ["nickName"],
                        "status": "partial",
                    },
                ],
                "warnings": ["CEngagement: not present"],
            }
        }
    )
    assert "found gaps" in out
    assert "entity not found on target" in out
    assert "missing field(s): nickName" in out
    assert "CEngagement: not present" in out


def test_render_verification_inconclusive():
    out = render_verification_html(
        {
            "verification": {
                "ran": True,
                "conclusive": False,
                "all_present": False,
                "entities": [
                    {"entity": "Contact", "present": None, "status": "unverified"}
                ],
                "warnings": ["Could not read live instance scopes"],
            }
        }
    )
    assert "inconclusive" in out


def test_render_verification_absent_when_not_run():
    assert render_verification_html({}) == ""
    assert render_verification_html({"verification": {"ran": False}}) == ""


def test_render_publish_includes_verification():
    out = render_publish_html(
        {
            "engine": "espocrm",
            "target_instance": "INST-001",
            "programs": [{"filename": "Contact.yaml", "deployed": True}],
            "verification": {
                "ran": True,
                "conclusive": True,
                "all_present": True,
                "entities": [{"entity": "Contact", "status": "matching"}],
                "warnings": [],
            },
        }
    )
    assert "Verified on target" in out


# -- backup / abort (REQ-292) ------------------------------------------------


def test_render_publish_backup_captured_note():
    out = render_publish_html(
        {
            "engine": "espocrm",
            "target_instance": "INST-001",
            "programs": [{"filename": "Contact.yaml", "deployed": True}],
            "backup_captured": True,
            "publish_run": "PUB-007",
        }
    )
    assert "backed up" in out.lower()
    assert "PUB-007" in out


def test_render_publish_aborted_note():
    out = render_publish_html(
        {
            "engine": "espocrm",
            "target_instance": "INST-001",
            "programs": [],
            "aborted": True,
            "abort_reason": "could not read the target's scopes (HTTP 500)",
        }
    )
    assert "aborted" in out.lower()
    assert "could not read the target&#x27;s scopes (HTTP 500)" in out or (
        "could not read the target" in out
    )
    # Nothing was deployed — no program list rendered.
    assert "deployed" not in out.lower()


def test_dialog_has_backup_override_unchecked_by_default(qtbot):
    client = _FakeClient(
        _validate_result(
            failed=False,
            programs=[{"filename": "Contact.yaml", "validation_errors": []}],
        )
    )
    dlg = PublishDialog(client, _RECORD)
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: dlg._revalidate_btn.isEnabled(), timeout=3000)
    # The backup gate is on by default (override unchecked).
    assert not dlg._allow_no_backup.isChecked()


def test_dialog_publish_forwards_scope_and_override(qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    client = _FakeClient(
        _validate_result(
            failed=False,
            programs=[{"filename": "Contact.yaml", "validation_errors": []}],
        ),
        publish_result={
            "engine": "espocrm",
            "target_instance": "INST-001",
            "programs": [{"filename": "Contact.yaml", "deployed": True}],
            "backup_captured": False,
        },
    )
    dlg = PublishDialog(client, _RECORD)
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: dlg._revalidate_btn.isEnabled(), timeout=3000)
    dlg._allow_no_backup.setChecked(True)
    # Auto-accept the confirm dialog, then trigger the publish handler.
    monkeypatch.setattr(
        "crmbuilder_v2.ui.dialogs.publish_dialog.CopyableMessageBox.exec",
        lambda self: QMessageBox.StandardButton.Ok,
    )
    dlg._on_publish_clicked()
    qtbot.waitUntil(
        lambda: any(c[0] == "publish" for c in client.calls), timeout=3000
    )
    pub = next(c for c in client.calls if c[0] == "publish")
    # ("publish", identifier, scope, allow_no_backup)
    assert pub[1] == "INST-001"
    assert pub[2] is None  # all programs selected → full scope
    assert pub[3] is True  # override forwarded


# -- client request paths ----------------------------------------------------


def test_client_publish_request_paths():
    sc = StorageClient.__new__(StorageClient)
    calls: list[tuple[str, str, object]] = []

    def _req(method, path, *, json_body=None):
        calls.append((method, path, json_body))
        return {"validation_failed": False}

    sc._request = _req
    assert sc.publish_validate_instance("INST-001") == {
        "validation_failed": False
    }
    assert sc.publish_instance("INST-002") == {"validation_failed": False}
    assert sc.publish_preview_instance("INST-003") == {
        "validation_failed": False
    }
    # A scoped publish sends the selected filenames in the body.
    sc.publish_instance("INST-004", ["Contact.yaml"])
    # The backup-gate override is sent when set.
    sc.publish_instance("INST-005", None, allow_no_backup=True)
    assert ("POST", "/instances/INST-001/publish-validate", None) in calls
    assert ("POST", "/instances/INST-002/publish", None) in calls
    assert ("POST", "/instances/INST-003/publish-preview", None) in calls
    assert (
        "POST",
        "/instances/INST-004/publish",
        {"scope": ["Contact.yaml"]},
    ) in calls
    assert (
        "POST",
        "/instances/INST-005/publish",
        {"allow_no_backup": True},
    ) in calls


def test_render_preview_html():
    out = render_preview_html(
        {
            "engine": "espocrm",
            "target_instance": "INST-001",
            "programs": [
                {
                    "filename": "Contact.yaml",
                    "summary": {"created": 3, "skipped": 34},
                    "validation_errors": [],
                }
            ],
            "deferrals": [],
        }
    )
    assert "Non-destructive" in out
    assert "would: 3 create" in out
    assert "34 unchanged" in out
    assert "&#9656;" in out  # ▸ planned marker


# -- dialog behavior ---------------------------------------------------------


class _FakeClient:
    def __init__(self, validate_result, publish_result=None):
        self._v = validate_result
        self._p = publish_result if publish_result is not None else validate_result
        self.calls: list[tuple] = []

    def publish_validate_instance(self, identifier, scope=None):
        self.calls.append(("validate", identifier, scope))
        return self._v

    def publish_instance(self, identifier, scope=None, allow_no_backup=False):
        self.calls.append(("publish", identifier, scope, allow_no_backup))
        return self._p

    def publish_preview_instance(self, identifier, scope=None):
        self.calls.append(("preview", identifier, scope))
        return self._p


_RECORD = {"instance_identifier": "INST-001", "instance_name": "CBM sandbox"}


def test_dialog_enables_publish_when_valid(qtbot):
    client = _FakeClient(
        _validate_result(
            failed=False,
            programs=[{"filename": "Contact.yaml", "validation_errors": []}],
        )
    )
    dlg = PublishDialog(client, _RECORD)
    qtbot.addWidget(dlg)
    # The dialog validates on open; wait for that to settle (busy clears).
    qtbot.waitUntil(lambda: dlg._revalidate_btn.isEnabled(), timeout=3000)
    assert ("validate", "INST-001", None) in client.calls
    assert dlg._publish_btn.isEnabled()
    assert "ready to publish" in dlg._status.text().lower()


def test_dialog_keeps_publish_disabled_when_invalid(qtbot):
    client = _FakeClient(
        _validate_result(
            failed=True,
            programs=[
                {"filename": "A.yaml", "validation_errors": ["accountType"]}
            ],
        )
    )
    dlg = PublishDialog(client, _RECORD)
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: dlg._revalidate_btn.isEnabled(), timeout=3000)
    assert not dlg._publish_btn.isEnabled()
    assert "failed" in dlg._status.text().lower()


# -- scope selection (REQ-290) -----------------------------------------------


def _two_program_validate():
    return _validate_result(
        failed=False,
        programs=[
            {"filename": "Contact.yaml", "validation_errors": []},
            {"filename": "Account.yaml", "validation_errors": []},
        ],
    )


def test_dialog_populates_scope_list(qtbot):
    client = _FakeClient(_two_program_validate())
    dlg = PublishDialog(client, _RECORD)
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: dlg._revalidate_btn.isEnabled(), timeout=3000)
    # Every generated program is a checked, selectable row.
    assert dlg._scope_list.count() == 2
    # All checked → publish everything → scope is None (no body sent).
    assert dlg._selected_scope() is None
    assert dlg._publish_btn.isEnabled()


def test_dialog_scope_subset_when_unchecked(qtbot):
    from PySide6.QtCore import Qt

    client = _FakeClient(_two_program_validate())
    dlg = PublishDialog(client, _RECORD)
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: dlg._revalidate_btn.isEnabled(), timeout=3000)
    # Uncheck Contact.yaml → scope narrows to the remaining selection.
    dlg._scope_list.item(0).setCheckState(Qt.CheckState.Unchecked)
    assert dlg._selected_scope() == ["Account.yaml"]
    assert dlg._publish_btn.isEnabled()


def test_dialog_publish_disabled_when_nothing_selected(qtbot):
    from PySide6.QtCore import Qt

    client = _FakeClient(_two_program_validate())
    dlg = PublishDialog(client, _RECORD)
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: dlg._revalidate_btn.isEnabled(), timeout=3000)
    for i in range(dlg._scope_list.count()):
        dlg._scope_list.item(i).setCheckState(Qt.CheckState.Unchecked)
    assert not dlg._publish_btn.isEnabled()

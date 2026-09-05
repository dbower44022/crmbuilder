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
    """A stubbed StorageClient. ``publish_result`` may be a dict or a callable
    taking the publish kwargs (``expected_plan_fingerprint``,
    ``confirm_access_removal``) so a test can behave as the API's fence does;
    ``preview_result`` defaults to ``publish_result``."""

    def __init__(self, validate_result, publish_result=None, preview_result=None):
        self._v = validate_result
        self._p = publish_result if publish_result is not None else validate_result
        self._pv = preview_result if preview_result is not None else self._p
        self.calls: list[tuple] = []
        self.publish_kwargs: list[dict] = []

    def publish_validate_instance(self, identifier, scope=None):
        self.calls.append(("validate", identifier, scope))
        return self._v

    def publish_instance(
        self, identifier, scope=None, allow_no_backup=False, *,
        expected_plan_fingerprint=None, confirm_access_removal=False,
    ):
        self.calls.append(("publish", identifier, scope, allow_no_backup))
        kwargs = {
            "expected_plan_fingerprint": expected_plan_fingerprint,
            "confirm_access_removal": confirm_access_removal,
        }
        self.publish_kwargs.append(kwargs)
        return self._p(**kwargs) if callable(self._p) else self._p

    def publish_preview_instance(self, identifier, scope=None):
        self.calls.append(("preview", identifier, scope))
        return self._pv


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


# -- the access gate in the dialog (REQ-521 / PI-468) -----------------------
#
# The API contract (PI-466): the preview carries ``plan_fingerprint`` and an
# ``access`` section; a run without the fingerprint is automatic and a
# removal comes back declined by name (200, ``declined_changes``); a run with
# the fingerprint and a removal is 409 unless ``confirm_access_removal`` is
# sent. The client is stubbed to behave exactly as that fence does.

_REMOVAL = {
    "attribute": "role_scope_access", "scope": "Contact", "action": "delete",
    "before": "all", "after": "no", "removes_access": True,
    "member_name": "Mentor", "description": "Mentor: Contact.delete all → no",
}
_WIDENING = {
    "attribute": "role_scope_access", "scope": "Account", "action": "read",
    "before": "own", "after": "all", "removes_access": False,
    "member_name": "Mentor", "description": "Mentor: Account.read own → all",
}


def _role_entry(changes, *, live_state="present", summary=None):
    removals = [c for c in changes if c["removes_access"]]
    return {
        "target": {
            "instance": "INST-001", "member_type": "role",
            "member_identifier": "ROL-001", "member_name": "Mentor",
        },
        "changes": changes, "removals": removals,
        "removes_access": bool(removals), "requires_confirmation": True,
        "summary": summary or (
            f"Publishing role Mentor to INST-001 changes {len(changes)} access "
            f"setting(s), {len(removals)} of which take access away."
        ),
        "live_state": live_state,
    }


def _access_section(changes, *, known=True):
    removals = [c for c in changes if c["removes_access"]]
    if not known:
        role = _role_entry(
            [], live_state="unknown",
            summary="Publishing role Mentor to INST-001 has an effect on "
            "access that could not be determined: could not read the "
            "target's roles (HTTP 500)",
        )
        return {
            "target": "INST-001", "assessed": True, "known": False,
            "reason": "could not read the target's roles (HTTP 500)",
            "roles": [role], "teams": [], "changes": [], "removals": [],
            "removes_access": False, "requires_confirmation": True,
            "summary": "The effect of this publish on access at INST-001 could "
            "not be determined: could not read the target's roles (HTTP 500)",
        }
    return {
        "target": "INST-001", "assessed": True, "known": True, "reason": None,
        "roles": [_role_entry(changes)],
        "teams": [{
            "target": {
                "instance": "INST-001", "member_type": "team",
                "member_identifier": "Mentors", "member_name": "Mentors",
            },
            "changes": [], "removals": [], "removes_access": False,
            "requires_confirmation": True, "live_state": "absent",
            "summary": "Publishing team Mentors to INST-001 changes who is "
            "grouped for sharing on that instance. The target holds no such "
            "team; it is created.",
        }],
        "changes": changes, "removals": removals,
        "removes_access": bool(removals), "requires_confirmation": True,
        "summary": "Publishing the security program to INST-001 changes "
        f"{len(changes)} access setting(s) across 1 role(s), {len(removals)} "
        "of which take access away. 1 team(s) change who is grouped for "
        "sharing on that instance.",
    }


def _preview_result(access, fingerprint="fp-1"):
    return {
        "engine": "espocrm", "target_instance": "INST-001", "preview": True,
        "validation_failed": False,
        "programs": [
            {"filename": "Contact.yaml", "summary": {"created": 1},
             "validation_errors": []},
        ],
        "deferrals": [], "plan_fingerprint": fingerprint, "access": access,
    }


def _fenced_publish(access):
    """Behave as ``POST /instances/{id}/publish`` does on the two words."""
    from crmbuilder_v2.ui.exceptions import ConflictError

    base = {
        "engine": "espocrm", "target_instance": "INST-001",
        "programs": [{"filename": "Contact.yaml", "deployed": True}],
        "backup_captured": True, "publish_run": "PUB-009",
        "plan_fingerprint": "fp-1", "access": access, "declined_changes": [],
        "aborted": False,
    }

    def _publish(*, expected_plan_fingerprint, confirm_access_removal):
        if not access.get("removes_access"):
            return base
        if expected_plan_fingerprint is None:
            return {
                **base, "aborted": True, "backup_captured": False,
                "publish_run": "PUB-008",
                "programs": [{"filename": "Contact.yaml", "deployed": False}],
                "declined_changes": [{
                    "construct": "role Mentor (security.yaml)",
                    "attribute": "role_scope_access", "design": "no",
                    "instance": "all", "kind": "removal",
                    "reason": "takes away access the instance currently "
                    "grants: Mentor: Contact.delete all → no",
                }],
                "abort_reason": "an automatic apply may only add or widen "
                "(REQ-497); declined 1 change(s): role Mentor (security.yaml): "
                "removal — takes away access the instance currently grants: "
                "Mentor: Contact.delete all → no. Nothing was applied. Run a "
                "publish preview, review these changes, and resubmit with the "
                "approved plan fingerprint.",
            }
        if not confirm_access_removal:
            raise ConflictError(
                errors=[{"code": "conflict"}],
                message=access["summary"] + " This publish removes access "
                "the instance currently grants and is never applied "
                "automatically; confirm the removal separately "
                "(confirm_access_removal): Mentor: Contact.delete all → no",
            )
        return base

    return _publish


def _accept_publish(monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    seen: list[str] = []

    def _exec(self):
        seen.append(self.text())
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(
        "crmbuilder_v2.ui.dialogs.publish_dialog.CopyableMessageBox.exec", _exec
    )
    return seen


def _answer_removal(monkeypatch, reply):
    """Answer the separate removal question, recording the text shown."""
    from crmbuilder_v2.ui.dialogs import publish_dialog as pd

    seen: list[str] = []

    def _warning(parent, title, text, *args, **kwargs):
        seen.append(f"{title}\n{text}")
        return reply

    monkeypatch.setattr(pd.CopyableMessageBox, "warning", staticmethod(_warning))
    return seen


def _open(qtbot, client):
    dlg = PublishDialog(client, _RECORD)
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: dlg._revalidate_btn.isEnabled(), timeout=3000)
    return dlg


def _preview(qtbot, dlg, client):
    dlg._start_preview()
    qtbot.waitUntil(
        lambda: any(c[0] == "preview" for c in client.calls)
        and dlg._revalidate_btn.isEnabled(),
        timeout=3000,
    )


def _wait_published(qtbot, dlg, client):
    qtbot.waitUntil(
        lambda: any(c[0] == "publish" for c in client.calls)
        and dlg._revalidate_btn.isEnabled(),
        timeout=3000,
    )


# renderers


def test_render_access_additive_states_each_change_in_the_apis_words():
    from crmbuilder_v2.ui.dialogs.publish_dialog import render_access_html

    out = render_access_html(_access_section([_WIDENING]))
    assert "changes 1 access setting(s)" in out
    assert "Role Mentor" in out
    assert "Mentor: Account.read own → all" in out
    assert "removes access" not in out
    assert "Team Mentors" in out
    assert "it is created" in out
    assert "&#10003;" in out


def test_render_access_flags_each_removal():
    from crmbuilder_v2.ui.dialogs.publish_dialog import render_access_html

    out = render_access_html(_access_section([_WIDENING, _REMOVAL]))
    assert "1 of which take access away" in out
    assert "Mentor: Contact.delete all → no" in out
    assert "removes access" in out
    assert "confirm each removal separately" in out
    # the additive line is not flagged
    assert out.index("Account.read own → all") < out.index("Contact.delete")
    assert "&#10007;" in out


def test_render_access_unknown_says_the_target_could_not_be_read():
    from crmbuilder_v2.ui.dialogs.publish_dialog import render_access_html

    out = render_access_html(_access_section([], known=False))
    assert "Access effect unknown" in out
    assert "the target could not be read" in out
    assert "could not read the target&#x27;s roles (HTTP 500)" in out
    assert "effect unknown" in out  # the role line, not "no changes"
    assert "no access setting changes" not in out


def test_render_access_absent_on_a_validate_result():
    from crmbuilder_v2.ui.dialogs.publish_dialog import render_access_html

    assert render_access_html(None) == ""
    assert "no role or team" in render_access_html(
        {"assessed": False, "summary": "The published programs declare no "
         "role or team; access on INST-001 is left as it is."}
    )


def test_render_preview_includes_access_and_plan():
    out = render_preview_html(_preview_result(_access_section([_REMOVAL])))
    assert "Mentor: Contact.delete all → no" in out
    assert "fp-1" in out


def test_render_publish_declined_lists_reasons_and_the_reviewed_path():
    from crmbuilder_v2.ui.dialogs.publish_dialog import render_declined_html

    result = _fenced_publish(_access_section([_REMOVAL]))(
        expected_plan_fingerprint=None, confirm_access_removal=False
    )
    out = render_publish_html(result)
    assert "an automatic publish may only add or widen" in out
    assert "role Mentor (security.yaml)" in out
    assert "Mentor: Contact.delete all → no" in out
    assert "Preview" in out and "Publish" in out
    # not the backup-gate wording
    assert "override the backup gate" not in out
    assert render_declined_html({"declined_changes": []}) == ""


# the dialog


def test_dialog_preview_renders_access_and_holds_the_fingerprint(qtbot):
    client = _FakeClient(
        _two_program_validate(),
        preview_result=_preview_result(_access_section([_WIDENING])),
    )
    dlg = _open(qtbot, client)
    assert not dlg.is_reviewed()
    _preview(qtbot, dlg, client)
    assert dlg.is_reviewed()
    assert "Mentor: Account.read own → all" in dlg._results.toPlainText()
    assert "reviewed plan" in dlg._status.text()


def test_dialog_additive_reviewed_run_sends_the_fingerprint_only(
    qtbot, monkeypatch
):
    access = _access_section([_WIDENING])
    client = _FakeClient(
        _two_program_validate(),
        publish_result=_fenced_publish(access),
        preview_result=_preview_result(access),
    )
    dlg = _open(qtbot, client)
    _preview(qtbot, dlg, client)
    shown = _accept_publish(monkeypatch)
    asked = _answer_removal(monkeypatch, None)
    dlg._on_publish_clicked()
    _wait_published(qtbot, dlg, client)
    # one question, stating the target and the effect; no removal question
    assert len(shown) == 1
    assert "CBM sandbox" in shown[0]
    assert "Mentor: Account.read own → all" in shown[0]
    assert "Reviewed run — plan fp-1" in shown[0]
    assert asked == []
    assert client.publish_kwargs == [
        {"expected_plan_fingerprint": "fp-1", "confirm_access_removal": False}
    ]
    assert dlg._status.text() == "Publish complete."


def test_dialog_automatic_run_sends_no_fingerprint_and_shows_the_decline(
    qtbot, monkeypatch
):
    access = _access_section([_REMOVAL])
    client = _FakeClient(
        _two_program_validate(), publish_result=_fenced_publish(access)
    )
    dlg = _open(qtbot, client)
    shown = _accept_publish(monkeypatch)
    asked = _answer_removal(monkeypatch, None)
    dlg._on_publish_clicked()  # no preview: automatic
    _wait_published(qtbot, dlg, client)
    assert "Automatic run" in shown[0]
    assert asked == []  # the dialog never asks for a word it cannot send
    assert client.publish_kwargs == [
        {"expected_plan_fingerprint": None, "confirm_access_removal": False}
    ]
    text = dlg._results.toPlainText()
    assert "Mentor: Contact.delete all → no" in text
    assert "an automatic publish may only add or widen" in text
    assert "declined" in dlg._status.text()
    assert "Preview" in dlg._status.text()
    # the reviewed path is open: Preview is enabled
    assert dlg._preview_btn.isEnabled()


def test_dialog_removal_is_refused_until_confirmed_then_proceeds(
    qtbot, monkeypatch
):
    from PySide6.QtWidgets import QMessageBox

    access = _access_section([_WIDENING, _REMOVAL])
    client = _FakeClient(
        _two_program_validate(),
        publish_result=_fenced_publish(access),
        preview_result=_preview_result(access),
    )
    dlg = _open(qtbot, client)
    _preview(qtbot, dlg, client)
    assert "confirm each removal" in dlg._status.text()
    shown = _accept_publish(monkeypatch)
    # Agreeing to the publish and declining the removal sends nothing.
    asked = _answer_removal(monkeypatch, QMessageBox.StandardButton.Cancel)
    dlg._on_publish_clicked()
    assert len(asked) == 1
    assert "This removes access" in asked[0]
    assert "Mentor: Contact.delete all → no" in asked[0]
    assert "Account.read own → all" not in asked[0]  # only the removals
    assert "Remove this access on CBM sandbox?" in asked[0]
    assert client.publish_kwargs == []
    assert "not confirmed" in dlg._status.text()
    assert dlg.is_reviewed()  # the plan still stands; nothing was spent
    # Confirming the removal sends the fingerprint and the word together.
    asked = _answer_removal(monkeypatch, QMessageBox.StandardButton.Yes)
    dlg._on_publish_clicked()
    _wait_published(qtbot, dlg, client)
    assert len(shown) == 2
    assert "(removes access)" in shown[1]
    assert client.publish_kwargs == [
        {"expected_plan_fingerprint": "fp-1", "confirm_access_removal": True}
    ]
    assert dlg._status.text() == "Publish complete."
    assert not dlg.is_reviewed()  # spent


def test_dialog_unknown_effect_reviewed_run_proceeds_without_the_word(
    qtbot, monkeypatch
):
    access = _access_section([], known=False)
    client = _FakeClient(
        _two_program_validate(),
        publish_result=_fenced_publish(access),
        preview_result=_preview_result(access),
    )
    dlg = _open(qtbot, client)
    _preview(qtbot, dlg, client)
    assert "unknown because the target could not be read" in dlg._status.text()
    assert "Access effect unknown" in dlg._results.toPlainText()
    shown = _accept_publish(monkeypatch)
    asked = _answer_removal(monkeypatch, None)
    dlg._on_publish_clicked()
    _wait_published(qtbot, dlg, client)
    assert "could not be determined" in shown[0]
    assert asked == []
    assert client.publish_kwargs == [
        {"expected_plan_fingerprint": "fp-1", "confirm_access_removal": False}
    ]


def test_dialog_shows_the_apis_refusal_and_the_way_through(qtbot, monkeypatch):
    """The target changed after the preview: a removal the preview did not
    show. The API's 409 is rendered in its words, not as an error dialog."""
    access = _access_section([_REMOVAL])
    client = _FakeClient(
        _two_program_validate(),
        publish_result=_fenced_publish(access),
        preview_result=_preview_result(_access_section([_WIDENING])),
    )
    dlg = _open(qtbot, client)
    _preview(qtbot, dlg, client)
    _accept_publish(monkeypatch)
    monkeypatch.setattr(
        "crmbuilder_v2.ui.dialogs.publish_dialog.ErrorDialog.exec",
        lambda self: (_ for _ in ()).throw(AssertionError("error dialog shown")),
    )
    dlg._on_publish_clicked()
    _wait_published(qtbot, dlg, client)
    assert client.publish_kwargs[0]["confirm_access_removal"] is False
    text = dlg._results.toPlainText()
    assert "Publish refused" in text
    assert "confirm_access_removal" in text
    assert "Mentor: Contact.delete all → no" in text
    assert "refused" in dlg._status.text()
    assert dlg._preview_btn.isEnabled()


def test_dialog_scope_change_and_revalidate_drop_the_reviewed_plan(qtbot):
    from PySide6.QtCore import Qt

    client = _FakeClient(
        _two_program_validate(),
        preview_result=_preview_result(_access_section([_WIDENING])),
    )
    dlg = _open(qtbot, client)
    _preview(qtbot, dlg, client)
    assert dlg.is_reviewed()
    dlg._scope_list.item(0).setCheckState(Qt.CheckState.Unchecked)
    assert not dlg.is_reviewed()  # a different scope is a different plan
    _preview(qtbot, dlg, client)
    assert dlg.is_reviewed()
    dlg._start_validate()
    qtbot.waitUntil(lambda: dlg._revalidate_btn.isEnabled(), timeout=3000)
    assert not dlg.is_reviewed()


def test_client_publish_sends_the_fingerprint_and_the_word():
    sc = StorageClient.__new__(StorageClient)
    calls: list[tuple[str, str, object]] = []

    def _req(method, path, *, json_body=None):
        calls.append((method, path, json_body))
        return {}

    sc._request = _req
    sc.publish_instance(
        "INST-006", None, expected_plan_fingerprint="fp-1",
        confirm_access_removal=True,
    )
    assert calls == [(
        "POST", "/instances/INST-006/publish",
        {"expected_plan_fingerprint": "fp-1", "confirm_access_removal": True},
    )]

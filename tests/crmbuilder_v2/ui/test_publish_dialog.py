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


# -- client request paths ----------------------------------------------------


def test_client_publish_request_paths():
    sc = StorageClient.__new__(StorageClient)
    calls: list[tuple[str, str]] = []
    sc._request = lambda method, path: (
        calls.append((method, path)) or {"validation_failed": False}
    )
    assert sc.publish_validate_instance("INST-001") == {
        "validation_failed": False
    }
    assert sc.publish_instance("INST-002") == {"validation_failed": False}
    assert sc.publish_preview_instance("INST-003") == {
        "validation_failed": False
    }
    assert ("POST", "/instances/INST-001/publish-validate") in calls
    assert ("POST", "/instances/INST-002/publish") in calls
    assert ("POST", "/instances/INST-003/publish-preview") in calls


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
    def __init__(self, validate_result):
        self._v = validate_result
        self.calls: list[tuple[str, str]] = []

    def publish_validate_instance(self, identifier):
        self.calls.append(("validate", identifier))
        return self._v

    def publish_instance(self, identifier):  # pragma: no cover - not hit here
        self.calls.append(("publish", identifier))
        return self._v


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
    assert ("validate", "INST-001") in client.calls
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

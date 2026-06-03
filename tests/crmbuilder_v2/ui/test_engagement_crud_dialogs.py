"""Engagement CRUD + delete dialog tests — UI v0.5 slice C.

Covers PRD §5.1 / §5.6 acceptance criteria for the three dialogs:

* ``EngagementCreateDialog`` — opens empty; submits with valid input;
  surfaces inline validation errors for each rule (lowercase code,
  too-short code, missing required fields).
* ``EngagementEditDialog`` — pre-fills from selected row; ``code`` and
  ``identifier`` are read-only; PATCH submits only the changed fields.
* ``EngagementDeleteDialog`` — three branches:
  - Case A (non-active target): standard edge-text confirmation.
  - Case B (active target, multi-engagement install): "Switch
    engagement" button; slice-C inert handler.
  - Case B sub-case (active target, only engagement): "Create
    engagement" button; opens the slice-C Create dialog.
"""

from __future__ import annotations

from datetime import UTC, datetime
import pytest
from crmbuilder_v2.access.engagement_models import (
    Engagement,
    EngagementStatus,
)
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.active_engagement_context import ActiveEngagementContext
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.engagement_crud import (
    EngagementCreateDialog,
    EngagementEditDialog,
)
from crmbuilder_v2.ui.dialogs.engagement_delete import (
    _SLICE_D_TODO_CREATE,
    _SLICE_D_TODO_SWITCH,
    EngagementDeleteDialog,
)
from fastapi.testclient import TestClient
from PySide6.QtWidgets import QDialog, QLineEdit


@pytest.fixture
def engagement_client(v2_env) -> StorageClient:
    """A StorageClient over a TestClient bound to the unified DB (PI-β).

    The engagement registry is the unified ``engagements`` table; ``v2_env``
    seeds ``ENG-001`` for scoping, so clear it to an empty registry for these
    dialog tests, which seed their own engagements.

    These tests drive a *headerless* client against the **unscoped**
    engagements table. ``v2_env`` turns scope-enforcement on (to catch
    un-stamped scoped writes); with no ``X-Engagement`` header the per-request
    active engagement is ``None``, so the writable-session export snapshot's
    scoped reads would trip enforcement. Production runs scoping on but
    enforcement *off*, so disable enforcement here to match.
    """
    from crmbuilder_v2.access import engagement_scope
    from crmbuilder_v2.access.db import session_scope
    from crmbuilder_v2.access.models import EngagementRow

    with session_scope() as s:
        s.query(EngagementRow).delete()
    prev = engagement_scope.set_enforcement(False)
    try:
        yield StorageClient(
            base_url="http://testserver", client=TestClient(create_app())
        )
    finally:
        engagement_scope.set_enforcement(prev)


def _make_active(identifier: str = "ENG-001", code: str = "ALPHA") -> ActiveEngagementContext:
    ctx = ActiveEngagementContext()
    now = datetime.now(UTC)
    ctx.set_engagement(
        Engagement(
            engagement_identifier=identifier,
            engagement_code=code,
            engagement_name=code,
            engagement_purpose="",
            engagement_status=EngagementStatus.ACTIVE,
            engagement_last_opened_at=None,
            engagement_export_dir=None,
            engagement_created_at=now,
            engagement_updated_at=now,
            engagement_deleted_at=None,
        )
    )
    return ctx


# ---------------------------------------------------------------------------
# EngagementCreateDialog
# ---------------------------------------------------------------------------


def test_create_dialog_persists_and_assigns_identifier(qtbot, engagement_client):
    dialog = EngagementCreateDialog(engagement_client)
    qtbot.addWidget(dialog)
    # Identifier is server-assigned; not part of the create schema.
    assert "engagement_identifier" not in dialog._widgets
    dialog._widgets["engagement_code"].setText("ALPHA")
    dialog._widgets["engagement_name"].setText("Alpha Engagement")
    dialog._widgets["engagement_purpose"].setPlainText("Verification only")
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    assert dialog.created_identifier() == "ENG-001"
    stored = engagement_client.get_engagement("ENG-001")
    assert stored["engagement_code"] == "ALPHA"
    assert stored["engagement_status"] == "active"


def test_create_dialog_rejects_lowercase_code_inline(qtbot, engagement_client):
    dialog = EngagementCreateDialog(engagement_client)
    qtbot.addWidget(dialog)
    dialog._widgets["engagement_code"].setText("alpha")
    dialog._widgets["engagement_name"].setText("Alpha")
    dialog._widgets["engagement_purpose"].setPlainText("test")
    dialog._on_save_clicked()
    qtbot.waitUntil(
        lambda: dialog._error_labels["engagement_code"].text() != "",
        timeout=3000,
    )
    assert dialog.result() != QDialog.DialogCode.Accepted


def test_create_dialog_rejects_short_code_inline(qtbot, engagement_client):
    dialog = EngagementCreateDialog(engagement_client)
    qtbot.addWidget(dialog)
    dialog._widgets["engagement_code"].setText("A")
    dialog._widgets["engagement_name"].setText("Alpha")
    dialog._widgets["engagement_purpose"].setPlainText("test")
    dialog._on_save_clicked()
    qtbot.waitUntil(
        lambda: dialog._error_labels["engagement_code"].text() != "",
        timeout=3000,
    )
    assert dialog.result() != QDialog.DialogCode.Accepted


def test_create_dialog_rejects_missing_name(qtbot, engagement_client):
    dialog = EngagementCreateDialog(engagement_client)
    qtbot.addWidget(dialog)
    dialog._widgets["engagement_code"].setText("ALPHA")
    dialog._widgets["engagement_purpose"].setPlainText("test")
    dialog._on_save_clicked()
    qtbot.waitUntil(
        lambda: dialog._error_labels["engagement_name"].text() != "",
        timeout=3000,
    )


def test_create_dialog_has_export_dir_browse_button(qtbot, engagement_client):
    dialog = EngagementCreateDialog(engagement_client)
    qtbot.addWidget(dialog)
    browse = dialog.findChild(object, "engagement_export_dir_browse")
    assert browse is not None


# ---------------------------------------------------------------------------
# EngagementEditDialog
# ---------------------------------------------------------------------------


def _seed(client: StorageClient, code: str, name: str) -> dict:
    return client.create_engagement(
        {
            "engagement_code": code,
            "engagement_name": name,
            "engagement_purpose": f"Test {code}",
        }
    )


def test_edit_dialog_prefill_and_readonly_code(qtbot, engagement_client):
    _seed(engagement_client, "ALPHA", "Alpha")
    record = engagement_client.get_engagement("ENG-001")
    dialog = EngagementEditDialog(engagement_client, record)
    qtbot.addWidget(dialog)
    code = dialog._widgets["engagement_code"]
    identifier = dialog._widgets["engagement_identifier"]
    assert code.isReadOnly()
    assert identifier.isReadOnly()
    assert code.text() == "ALPHA"
    assert identifier.text() == "ENG-001"
    # Tooltip mentions the post-creation restriction.
    assert "cannot be changed" in code.toolTip().lower()


def test_edit_dialog_patches_only_changed_fields(qtbot, engagement_client):
    _seed(engagement_client, "ALPHA", "Alpha")
    record = engagement_client.get_engagement("ENG-001")
    dialog = EngagementEditDialog(engagement_client, record)
    qtbot.addWidget(dialog)
    dialog._widgets["engagement_purpose"].setPlainText("Updated purpose")
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    refreshed = engagement_client.get_engagement("ENG-001")
    assert refreshed["engagement_purpose"] == "Updated purpose"
    # Other fields untouched.
    assert refreshed["engagement_code"] == "ALPHA"
    assert refreshed["engagement_name"] == "Alpha"


# ---------------------------------------------------------------------------
# EngagementDeleteDialog — Case A
# ---------------------------------------------------------------------------


def test_delete_dialog_case_a_edge_text_then_soft_deletes(
    qtbot, engagement_client
):
    _seed(engagement_client, "ALPHA", "Alpha")
    _seed(engagement_client, "BRAVO", "Bravo")
    active = _make_active("ENG-001", "ALPHA")  # ALPHA active; deleting BRAVO
    dialog = EngagementDeleteDialog(
        engagement_client, "ENG-002", "Bravo", active_context=active
    )
    qtbot.addWidget(dialog)
    # Edge-text confirmation field is present; Delete disabled until typed.
    assert dialog._confirm_edit is not None
    # Use isHidden() — isVisible() requires the dialog itself to be shown.
    assert dialog._delete_btn.isHidden() is False
    assert dialog._delete_btn.isEnabled() is False
    dialog._confirm_edit.setText("ENG-00")
    assert dialog._delete_btn.isEnabled() is False
    dialog._confirm_edit.setText("ENG-002")
    assert dialog._delete_btn.isEnabled() is True
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._delete_btn.click()
    # ENG-002 soft-deleted; ENG-001 still in default list.
    live = [e["engagement_identifier"] for e in engagement_client.list_engagements()]
    assert "ENG-001" in live
    assert "ENG-002" not in live


# ---------------------------------------------------------------------------
# EngagementDeleteDialog — Case B (active target, multi-engagement)
# ---------------------------------------------------------------------------


def test_delete_dialog_case_b_switch_button(qtbot, engagement_client, capsys):
    _seed(engagement_client, "ALPHA", "Alpha")
    _seed(engagement_client, "BRAVO", "Bravo")
    active = _make_active("ENG-001", "ALPHA")
    dialog = EngagementDeleteDialog(
        engagement_client, "ENG-001", "Alpha", active_context=active
    )
    qtbot.addWidget(dialog)
    # Standard confirmation field NOT rendered.
    assert dialog._confirm_edit is None
    # Switch-engagement button replaces Delete.
    assert dialog._switch_btn is not None
    assert dialog._switch_btn.text() == "Switch engagement"
    assert dialog._delete_btn.isHidden() is True
    # Body message names the switch-first guidance.
    assert "switch" in dialog._body_label.text().lower()
    # Inert handler prints the TODO marker; slice D rewires.
    dialog._switch_btn.click()
    captured = capsys.readouterr().out
    assert _SLICE_D_TODO_SWITCH in captured


# ---------------------------------------------------------------------------
# EngagementDeleteDialog — Case B sub-case (only engagement)
# ---------------------------------------------------------------------------


def test_delete_dialog_case_b_only_engagement_create_button(
    qtbot, engagement_client, monkeypatch
):
    _seed(engagement_client, "ALPHA", "Alpha")
    active = _make_active("ENG-001", "ALPHA")
    dialog = EngagementDeleteDialog(
        engagement_client, "ENG-001", "Alpha", active_context=active
    )
    qtbot.addWidget(dialog)
    assert dialog._create_btn is not None
    assert dialog._create_btn.text() == "Create engagement"
    assert "only engagement" in dialog._body_label.text().lower()

    # Clicking opens the slice-C EngagementCreateDialog (stubbed here so
    # the test doesn't depend on async event-loop interactions).
    opened: dict = {"count": 0}

    class _StubCreate:
        def __init__(self, client, parent=None):
            opened["count"] += 1

        def exec(self):  # noqa: A003 — Qt naming
            return QDialog.DialogCode.Rejected

        def created_identifier(self):
            return None

    monkeypatch.setattr(
        "crmbuilder_v2.ui.dialogs.engagement_crud.EngagementCreateDialog",
        _StubCreate,
    )
    dialog._create_btn.click()
    assert opened["count"] == 1


def test_delete_dialog_slice_d_hooks_present(qtbot, engagement_client):
    """Slice D will call set_switch_handler / set_create_handler to rewire."""
    _seed(engagement_client, "ALPHA", "Alpha")
    active = _make_active("ENG-001", "ALPHA")
    dialog = EngagementDeleteDialog(
        engagement_client, "ENG-001", "Alpha", active_context=active
    )
    qtbot.addWidget(dialog)

    called = {"switch": 0, "create": 0}

    def new_switch():
        called["switch"] += 1

    def new_create():
        called["create"] += 1

    dialog.set_switch_handler(new_switch)
    dialog.set_create_handler(new_create)
    dialog._invoke_switch_handler()
    dialog._invoke_create_handler()
    assert called == {"switch": 1, "create": 1}


def test_delete_slice_d_create_todo_marker_string_present():
    # Bare sanity check that the slice-D TODO markers are still
    # importable as module-level constants. Slice D's prompt locates
    # these via the constant names and rewires the handlers.
    assert _SLICE_D_TODO_CREATE.startswith("[TODO slice D]")
    assert _SLICE_D_TODO_SWITCH.startswith("[TODO slice D]")


# ---------------------------------------------------------------------------
# Misc — Edit dialog also has the directory browser
# ---------------------------------------------------------------------------


def test_edit_dialog_has_export_dir_browse_button(qtbot, engagement_client):
    _seed(engagement_client, "ALPHA", "Alpha")
    record = engagement_client.get_engagement("ENG-001")
    dialog = EngagementEditDialog(engagement_client, record)
    qtbot.addWidget(dialog)
    browse = dialog.findChild(object, "engagement_export_dir_browse")
    assert browse is not None


def test_edit_dialog_export_dir_value_widget_is_line_edit(
    qtbot, engagement_client
):
    _seed(engagement_client, "ALPHA", "Alpha")
    record = engagement_client.get_engagement("ENG-001")
    dialog = EngagementEditDialog(engagement_client, record)
    qtbot.addWidget(dialog)
    line = dialog._widgets["engagement_export_dir"]
    assert isinstance(line, QLineEdit)


def test_edit_dialog_emphasises_empty_export_dir(qtbot, engagement_client):
    """Slice B (B6): the export-dir field is emphasised while empty."""
    _seed(engagement_client, "ALPHA", "Alpha")
    record = engagement_client.get_engagement("ENG-001")
    dialog = EngagementEditDialog(engagement_client, record)
    qtbot.addWidget(dialog)
    line = dialog._widgets["engagement_export_dir"]
    # Empty on open → amber border emphasis.
    assert line.text() == ""
    assert "border" in line.styleSheet()
    # Typing a value clears the emphasis.
    line.setText("/some/path")
    assert line.styleSheet() == ""


def test_edit_dialog_focus_export_dir_field(qtbot, engagement_client):
    """Slice B (B6): focus_export_dir_field() targets the export-dir field.

    Asserted via a setFocus spy rather than ``hasFocus()`` because the
    offscreen Qt platform used in CI has no active window, so real focus
    state is unreliable.
    """
    _seed(engagement_client, "ALPHA", "Alpha")
    record = engagement_client.get_engagement("ENG-001")
    dialog = EngagementEditDialog(engagement_client, record)
    qtbot.addWidget(dialog)
    line = dialog._widgets["engagement_export_dir"]
    calls: dict = {"n": 0}
    line.setFocus = lambda *a, **k: calls.__setitem__("n", calls["n"] + 1)
    dialog.focus_export_dir_field()
    assert calls["n"] == 1

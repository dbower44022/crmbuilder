"""CRM Candidates panel / dialog tests — UI v0.4 slice E.

Covers ``crm_candidate.md`` section 3.7 acceptance criteria 9–12: the
"CRM Candidates" sidebar entry at Methodology position #4, the
master-pane columns and context menu, the detail-pane field layout,
the CRUD dialogs end to end (including the singleton-``selected``
inline error and the delete-dialog clarifying note per PRD section
4.6), the foundation slice's ``ENTITY_TYPES`` registration and
cascading ``ReferenceCreateDialog`` admitting universal kinds for
``(decision, crm_candidate)`` and ``(session, crm_candidate)``, the
inbound-reference rendering on the detail pane, and the sample
CBM-redo Phase 1 → Phase 5 selection round-trip.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.vocab import (
    ENTITY_TYPES,
    RELATIONSHIP_RULES,
    _kinds_for_pair,
)
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.crm_candidate_crud import (
    CrmCandidateCreateDialog,
    CrmCandidateDeleteDialog,
    CrmCandidateEditDialog,
)
from crmbuilder_v2.ui.dialogs.reference_create import ReferenceCreateDialog
from crmbuilder_v2.ui.main_window import (
    ENTITY_TYPE_TO_SIDEBAR_LABEL,
    MainWindow,
)
from crmbuilder_v2.ui.panels.crm_candidates import CrmCandidatesPanel
from crmbuilder_v2.ui.refresh import _FILENAME_TO_ENTITY_TYPE
from crmbuilder_v2.ui.sidebar import SIDEBAR_GROUPS, Sidebar
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection
from fastapi.testclient import TestClient
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QWidget,
)


@pytest.fixture
def candidate_client(v2_env) -> StorageClient:
    """A StorageClient over a real TestClient bound to the per-test DB."""
    return StorageClient(
        base_url="http://testserver", client=TestClient(create_app())
    )


def _seed(client: StorageClient, name: str, **overrides) -> dict:
    body = {
        "crm_candidate_name": name,
        "crm_candidate_fit_reason": overrides.pop(
            "crm_candidate_fit_reason",
            "Open source self-hostable platform with strong customization.",
        ),
    }
    body.update(overrides)
    return client.create_crm_candidate(body)


def _seed_decision(client: StorageClient, identifier: str, **overrides) -> dict:
    body = {
        "identifier": identifier,
        "title": overrides.pop("title", "A decision"),
        "decision_date": overrides.pop("decision_date", "2026-05-14"),
        "status": overrides.pop("status", "Active"),
        "executive_summary": overrides.pop(
            "executive_summary",
            "PI-102 test executive summary. " * 7,
        ),
        "context": overrides.pop("context", ""),
        "decision": overrides.pop("decision", ""),
        "rationale": overrides.pop("rationale", ""),
        "alternatives_considered": overrides.pop(
            "alternatives_considered", ""
        ),
        "consequences": overrides.pop("consequences", ""),
    }
    return client.create_decision(body)


def _wait_rows(qtbot, panel: CrmCandidatesPanel, count: int) -> None:
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == count, timeout=3000)


# ---------------------------------------------------------------------------
# Criterion 10 — sidebar entry under the Methodology group
# ---------------------------------------------------------------------------


def test_crm_candidates_is_present_in_methodology_group():
    methodology = dict(SIDEBAR_GROUPS)["Methodology"]
    # v0.5+ PI-003 added "Personas"; PI-004 first slice added "Fields";
    # PI-004 cohort added "Requirements" at position #4 (1-indexed),
    # pushing CRM Candidates to position #5. Domains/Entities/Processes
    # remain the foundational three.
    assert methodology[:3] == ("Domains", "Entities", "Processes")
    assert "CRM Candidates" in methodology
    # Requirements now precedes CRM Candidates in the cohort ordering
    # per PI-004 cohort build prompt.
    assert methodology.index("Requirements") < methodology.index(
        "CRM Candidates"
    )


def test_sidebar_renders_crm_candidates_under_methodology(qtbot):
    # v0.6 slice B retired uppercased header text per design pass §2.1;
    # see test_domains_panel.py for the pattern.
    from crmbuilder_v2.ui.sidebar import _HEADER_ROLE  # noqa: PLC0415

    sidebar = Sidebar()
    qtbot.addWidget(sidebar)
    items = [sidebar.item(r) for r in range(sidebar.count())]
    rendered = [item.text() for item in items]
    headers = {item.text(): i for i, item in enumerate(items) if item.data(_HEADER_ROLE)}
    assert "Methodology" in headers
    assert "CRM Candidates" in rendered
    # CRM Candidates appears somewhere under the Methodology header
    # (exact offset shifts as cohort siblings land).
    methodology_idx = headers["Methodology"]
    cc_idx = rendered.index("CRM Candidates")
    assert cc_idx > methodology_idx


def test_main_window_crm_candidates_page_is_panel(
    qtbot, lifecycle_stub, candidate_client
):
    window = MainWindow(lifecycle=lifecycle_stub, client=candidate_client)
    qtbot.addWidget(window)
    page = window._stack.widget(
        window._pages_by_entry["CRM Candidates"]
    )
    assert isinstance(page, CrmCandidatesPanel)


# ---------------------------------------------------------------------------
# Criterion 11 — master-pane columns, sort, context menu, and detail layout
# ---------------------------------------------------------------------------


def test_master_pane_columns_and_order(qtbot, candidate_client):
    panel = CrmCandidatesPanel(candidate_client)
    qtbot.addWidget(panel)
    columns = panel.list_columns()
    assert [c.title for c in columns] == [
        "Identifier",
        "Name",
        "Status",
        "Created",
    ]
    assert [c.field for c in columns] == [
        "crm_candidate_identifier",
        "crm_candidate_name",
        "crm_candidate_status",
        "created_at_display",
    ]


def test_master_pane_sorted_by_identifier_ascending(qtbot, candidate_client):
    _seed(candidate_client, "Bravo")
    _seed(candidate_client, "Alpha")
    _seed(candidate_client, "Charlie")
    panel = CrmCandidatesPanel(candidate_client)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 3)
    ids = [
        panel._model.record_at(r)["crm_candidate_identifier"]
        for r in range(panel._model.rowCount())
    ]
    assert ids == ["CRM-001", "CRM-002", "CRM-003"]


def test_context_menu_actions_live_row(qtbot, candidate_client):
    _seed(candidate_client, "EspoCRM")
    panel = CrmCandidatesPanel(candidate_client)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 1)
    menu = panel._build_context_menu(panel._model.index(0, 0))
    labels = [a.text() for a in menu.actions()]
    assert "New CRM candidate" in labels
    assert "Edit" in labels
    assert "Delete" in labels
    assert "Restore" not in labels


def test_context_menu_offers_restore_on_soft_deleted_row(
    qtbot, candidate_client
):
    _seed(candidate_client, "EspoCRM")
    candidate_client.delete_crm_candidate("CRM-001")
    panel = CrmCandidatesPanel(candidate_client)
    qtbot.addWidget(panel)
    panel._show_deleted_check.setChecked(True)
    qtbot.waitUntil(lambda: panel._model.rowCount() == 1, timeout=3000)
    menu = panel._build_context_menu(panel._model.index(0, 0))
    labels = [a.text() for a in menu.actions()]
    assert "Restore" in labels
    assert "Delete" not in labels


def test_detail_pane_renders_fields_in_order(qtbot, candidate_client):
    panel = CrmCandidatesPanel(candidate_client)
    qtbot.addWidget(panel)
    record = {
        "crm_candidate_identifier": "CRM-001",
        "crm_candidate_name": "EspoCRM",
        "crm_candidate_status": "active",
        "crm_candidate_fit_reason": "Open source self-hostable platform.",
        "crm_candidate_notes": "consultant scratchpad",
        "crm_candidate_created_at": "2026-05-14T00:00:00+00:00",
        "crm_candidate_updated_at": "2026-05-14T00:00:00+00:00",
        "crm_candidate_deleted_at": None,
    }
    detail = panel.render_detail(
        record, {"references": {"as_source": [], "as_target": []}}
    )

    # Construction order of the prefixed value widgets equals the
    # section-3.6.3 field order.
    ordered = [
        w.objectName()
        for w in detail.findChildren(QWidget)
        if w.objectName().startswith("crm_candidate_") and w.objectName().endswith(
            ("_value", "_toggle")
        )
    ]
    assert ordered == [
        "crm_candidate_identifier_value",
        "crm_candidate_name_value",
        "crm_candidate_fit_reason_value",
        "crm_candidate_notes_toggle",
        "crm_candidate_notes_value",
        "crm_candidate_status_value",
    ]

    # Identifier is a read-only label; name a read-only line editor;
    # fit reason a read-only multi-line; status a combo box.
    assert isinstance(
        detail.findChild(QLabel, "crm_candidate_identifier_value"), QLabel
    )
    name = detail.findChild(QLineEdit, "crm_candidate_name_value")
    assert name.isReadOnly() and name.text() == "EspoCRM"
    assert detail.findChild(
        QPlainTextEdit, "crm_candidate_fit_reason_value"
    ).isReadOnly()
    assert isinstance(
        detail.findChild(QComboBox, "crm_candidate_status_value"), QComboBox
    )

    # crm_candidate_notes is collapsed by default under "Internal notes".
    notes_value = detail.findChild(QPlainTextEdit, "crm_candidate_notes_value")
    assert notes_value.isHidden() is True
    # ReferencesSection is always present (inbound side only in v0.4).
    assert detail.findChildren(ReferencesSection)


def test_terminal_state_record_status_combo_shows_only_current(
    qtbot, candidate_client
):
    """A record in a terminal state shows only its current value in the combo."""
    panel = CrmCandidatesPanel(candidate_client)
    qtbot.addWidget(panel)
    record = {
        "crm_candidate_identifier": "CRM-001",
        "crm_candidate_name": "EspoCRM",
        "crm_candidate_status": "removed",
        "crm_candidate_fit_reason": "Open source.",
        "crm_candidate_notes": None,
        "crm_candidate_created_at": "2026-05-14T00:00:00+00:00",
        "crm_candidate_updated_at": "2026-05-14T00:00:00+00:00",
        "crm_candidate_deleted_at": None,
    }
    detail = panel.render_detail(
        record, {"references": {"as_source": [], "as_target": []}}
    )
    status = detail.findChild(QComboBox, "crm_candidate_status_value")
    items = [status.itemText(i) for i in range(status.count())]
    assert items == ["removed"]


# ---------------------------------------------------------------------------
# Criterion 9 — vocab registration + cascading dialog admits universal kinds
# ---------------------------------------------------------------------------


def test_crm_candidate_in_entity_types():
    assert "crm_candidate" in ENTITY_TYPES


def test_kinds_for_pair_decision_crm_candidate_universal_kinds():
    """Universal ``is_about`` and ``references`` are valid for any pair."""
    kinds = _kinds_for_pair("decision", "crm_candidate")
    assert "is_about" in kinds
    assert "references" in kinds
    # supersedes requires source_type == target_type; not the case here.
    assert "supersedes" not in kinds
    assert (
        "is_about"
        in RELATIONSHIP_RULES[("decision", "crm_candidate")]
    )


def test_kinds_for_pair_session_crm_candidate_includes_decided_in():
    """``decided_in`` is keyed on target=session, so (crm_candidate,
    session) admits it; (session, crm_candidate) gets only universals."""
    cand_to_session = _kinds_for_pair("crm_candidate", "session")
    assert "decided_in" in cand_to_session
    session_to_cand = _kinds_for_pair("session", "crm_candidate")
    assert "is_about" in session_to_cand
    assert "references" in session_to_cand


def test_post_reference_decision_is_about_crm_candidate_succeeds(
    candidate_client,
):
    _seed(candidate_client, "EspoCRM")
    _seed_decision(candidate_client, "DEC-001", title="Selection decision")
    created = candidate_client.create_reference(
        {
            "source_type": "decision",
            "source_id": "DEC-001",
            "target_type": "crm_candidate",
            "target_id": "CRM-001",
            "relationship": "is_about",
        }
    )
    assert created["source_type"] == "decision"
    assert created["target_type"] == "crm_candidate"
    assert created["relationship"] == "is_about"
    assert len(candidate_client.list_references()) == 1


def test_reference_create_dialog_offers_universal_kinds_for_decision_to_candidate(
    qtbot, candidate_client
):
    """The cascading dialog opened from a Decisions context with a
    decision source offers universal kinds for a crm_candidate target.
    """
    _seed(candidate_client, "EspoCRM")
    _seed_decision(candidate_client, "DEC-001")
    dialog = ReferenceCreateDialog(
        candidate_client, pre_populated_source=("decision", "DEC-001")
    )
    qtbot.addWidget(dialog)
    rel = dialog._field_widgets["relationship"]
    kinds = [rel.itemText(i) for i in range(rel.count())]
    assert "is_about" in kinds
    assert "references" in kinds
    rel.setCurrentText("is_about")
    target_type = dialog._field_widgets["target_type"]
    target_types = [
        target_type.itemText(i) for i in range(target_type.count())
    ]
    assert "crm_candidate" in target_types


def test_inbound_reference_renders_on_crm_candidate_detail_pane(
    qtbot, candidate_client
):
    _seed(candidate_client, "EspoCRM")
    _seed_decision(candidate_client, "DEC-001", title="Phase 5 selection")
    candidate_client.create_reference(
        {
            "source_type": "decision",
            "source_id": "DEC-001",
            "target_type": "crm_candidate",
            "target_id": "CRM-001",
            "relationship": "is_about",
        }
    )
    panel = CrmCandidatesPanel(candidate_client)
    qtbot.addWidget(panel)
    record = candidate_client.get_crm_candidate("CRM-001")
    extras = panel.fetch_detail_extras(record)
    detail = panel.render_detail(record, extras)
    # PRJ-015: inbound references render in a grid; the far-side identifier
    # is a cell value rather than a QLabel link.
    from crmbuilder_v2.ui.widgets.references_section import ReferencesSection

    section = detail.findChild(ReferencesSection)
    assert section is not None
    proxy = section._proxy
    cells = [
        str(proxy.data(proxy.index(r, c)) or "")
        for r in range(proxy.rowCount())
        for c in range(proxy.columnCount())
    ]
    assert any("DEC-001" in c for c in cells), (
        "decision citation should render in inbound references grid"
    )


def test_crm_candidates_snapshot_filename_is_mapped():
    assert _FILENAME_TO_ENTITY_TYPE["crm_candidates.json"] == "crm_candidate"
    assert ENTITY_TYPE_TO_SIDEBAR_LABEL["crm_candidate"] == "CRM Candidates"


# ---------------------------------------------------------------------------
# CRUD dialog smoke tests
# ---------------------------------------------------------------------------


def test_create_dialog_persists_and_assigns_identifier(
    qtbot, candidate_client
):
    dialog = CrmCandidateCreateDialog(candidate_client)
    qtbot.addWidget(dialog)
    assert "crm_candidate_identifier" not in dialog._widgets  # server-assigned
    dialog._widgets["crm_candidate_name"].setText("EspoCRM")
    dialog._widgets["crm_candidate_fit_reason"].setPlainText(
        "Open source, self-hostable platform with strong customization."
    )
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    assert dialog.created_identifier() == "CRM-001"
    stored = candidate_client.get_crm_candidate("CRM-001")
    assert stored["crm_candidate_name"] == "EspoCRM"
    assert stored["crm_candidate_status"] == "active"


def test_create_dialog_surfaces_duplicate_name_inline(
    qtbot, candidate_client
):
    _seed(candidate_client, "EspoCRM")
    dialog = CrmCandidateCreateDialog(candidate_client)
    qtbot.addWidget(dialog)
    dialog._widgets["crm_candidate_name"].setText("espocrm")
    dialog._widgets["crm_candidate_fit_reason"].setPlainText("fr")
    dialog._on_save_clicked()
    qtbot.waitUntil(
        lambda: dialog._error_labels["crm_candidate_name"].text() != "",
        timeout=3000,
    )
    assert dialog.result() != QDialog.DialogCode.Accepted


def test_edit_dialog_persists_status_change(qtbot, candidate_client):
    _seed(candidate_client, "EspoCRM")
    record = candidate_client.get_crm_candidate("CRM-001")
    dialog = CrmCandidateEditDialog(candidate_client, record)
    qtbot.addWidget(dialog)
    assert dialog._widgets["crm_candidate_identifier"].isReadOnly()
    status = dialog._widgets["crm_candidate_status"]
    status.setCurrentIndex(status.findText("declined"))
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    assert (
        candidate_client.get_crm_candidate("CRM-001")["crm_candidate_status"]
        == "declined"
    )


def test_delete_dialog_edge_text_then_soft_deletes_and_shows_clarifying_note(
    qtbot, candidate_client
):
    _seed(candidate_client, "EspoCRM")
    dialog = CrmCandidateDeleteDialog(
        candidate_client, "CRM-001", "EspoCRM"
    )
    qtbot.addWidget(dialog)
    body = dialog._body_label.text()
    # Per PRD section 4.6 the dialog clarifies soft-delete (authoring
    # error) vs status=removed (legitimate mid-engagement drop).
    assert "Removed" in body
    assert "authoring-error" in body or "authoring error" in body

    # Delete is disabled until the identifier is typed exactly.
    assert dialog._delete_btn.isEnabled() is False
    dialog._confirm_edit.setText("CRM-00")
    assert dialog._delete_btn.isEnabled() is False
    dialog._confirm_edit.setText("CRM-001")
    assert dialog._delete_btn.isEnabled() is True
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._delete_btn.click()
    assert candidate_client.list_crm_candidates() == []
    assert len(candidate_client.list_crm_candidates(include_deleted=True)) == 1


def test_edit_dialog_singleton_selected_conflict_surfaces_inline(
    qtbot, candidate_client
):
    """Transitioning a second record to ``selected`` surfaces inline on
    the status field with the prescribed "CRM-NNN is already selected"
    text per PRD section 4.6."""
    _seed(candidate_client, "EspoCRM", crm_candidate_status="selected")
    _seed(candidate_client, "SuiteCRM")
    record = candidate_client.get_crm_candidate("CRM-002")
    dialog = CrmCandidateEditDialog(candidate_client, record)
    qtbot.addWidget(dialog)
    status = dialog._widgets["crm_candidate_status"]
    status.setCurrentIndex(status.findText("selected"))
    dialog._on_save_clicked()
    qtbot.waitUntil(
        lambda: dialog._error_labels["crm_candidate_status"].text() != "",
        timeout=3000,
    )
    message = dialog._error_labels["crm_candidate_status"].text()
    assert "CRM-001" in message
    assert "already selected" in message
    # The dialog stayed open (the conflict prevented save).
    assert dialog.result() != QDialog.DialogCode.Accepted


# ---------------------------------------------------------------------------
# Criterion 12 — sample CBM-redo Phase 1 → Phase 5 selection round-trip
# ---------------------------------------------------------------------------


def test_phase_5_selection_round_trip_with_singleton_block_and_restart(
    qtbot, candidate_client
):
    # Phase 1: author three active candidates.
    _seed(candidate_client, "CRM A")
    _seed(candidate_client, "CRM B")
    _seed(candidate_client, "CRM C")

    # Mid-engagement: CRM A is pulled from further iterations.
    candidate_client.patch_crm_candidate(
        "CRM-001", {"crm_candidate_status": "removed"}
    )

    # Phase 5: CRM B is selected.
    candidate_client.patch_crm_candidate(
        "CRM-002", {"crm_candidate_status": "selected"}
    )

    # Attempting to transition CRM C to selected is rejected; the edit
    # dialog surfaces the prescribed inline message.
    record_c = candidate_client.get_crm_candidate("CRM-003")
    dialog = CrmCandidateEditDialog(candidate_client, record_c)
    qtbot.addWidget(dialog)
    status = dialog._widgets["crm_candidate_status"]
    status.setCurrentIndex(status.findText("selected"))
    dialog._on_save_clicked()
    qtbot.waitUntil(
        lambda: dialog._error_labels["crm_candidate_status"].text() != "",
        timeout=3000,
    )
    assert "CRM-002" in dialog._error_labels["crm_candidate_status"].text()
    dialog.reject()

    # Transition CRM C to declined instead.
    candidate_client.patch_crm_candidate(
        "CRM-003", {"crm_candidate_status": "declined"}
    )

    # Simulated app restart over the same on-disk DB.
    restarted = StorageClient(
        base_url="http://testserver", client=TestClient(create_app())
    )
    records = {
        r["crm_candidate_identifier"]: r["crm_candidate_status"]
        for r in restarted.list_crm_candidates()
    }
    assert records == {
        "CRM-001": "removed",
        "CRM-002": "selected",
        "CRM-003": "declined",
    }

    # Soft-deleting CRM-002 frees the singleton pool.
    restarted.delete_crm_candidate("CRM-002")
    live_selected = [
        r
        for r in restarted.list_crm_candidates()
        if r["crm_candidate_status"] == "selected"
    ]
    assert live_selected == []

    # Restoring CRM-002 puts selected back when no other live selected
    # exists.
    restored = restarted.restore_crm_candidate("CRM-002")
    assert restored["crm_candidate_status"] == "selected"
    assert restored["crm_candidate_deleted_at"] is None

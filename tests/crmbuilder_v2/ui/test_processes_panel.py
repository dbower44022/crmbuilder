"""Processes panel / dialog tests — UI v0.4 slice D.

Covers ``process.md`` section 3.7 acceptance criteria 10–15: the
"Processes" sidebar entry at Methodology position #3, the master-pane
columns and context menu, the detail-pane field layout (including the
domain re-affiliation warning), the CRUD dialogs end to end, the
``process_hands_off_to_process`` vocab registration and bidirectional
round-trip with directional rendering, and authoring a sample
CBM-redo Phase 1 Prioritized Backbone that survives an app "restart".

The ``process_client`` fixture wires a ``StorageClient`` over a real
FastAPI ``TestClient`` bound to the per-test SQLite database, so the
panel, dialogs, and handoff flow exercise the genuine
access → REST → DB path.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.models import Reference
from crmbuilder_v2.access.vocab import (
    RELATIONSHIP_RULES,
    _kinds_for_pair,
)
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.process_crud import (
    ProcessCreateDialog,
    ProcessDeleteDialog,
    ProcessEditDialog,
)
from crmbuilder_v2.ui.dialogs.reference_create import ReferenceCreateDialog
from crmbuilder_v2.ui.main_window import (
    ENTITY_TYPE_TO_SIDEBAR_LABEL,
    MainWindow,
)
from crmbuilder_v2.ui.panels.processes import ProcessesPanel
from crmbuilder_v2.ui.sidebar import SIDEBAR_GROUPS, Sidebar
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection
from crmbuilder_v2.ui.widgets.warning_callout import WarningCallout
from fastapi.testclient import TestClient
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QWidget,
)
from sqlalchemy.exc import IntegrityError


def _refs_grid_texts(detail) -> list[str]:
    """All display-cell strings from a detail pane's ReferencesSection grid."""
    section = detail.findChild(ReferencesSection)
    assert section is not None, "expected a ReferencesSection in the detail pane"
    model = section._proxy
    return [
        str(model.data(model.index(r, c)) or "")
        for r in range(model.rowCount())
        for c in range(model.columnCount())
    ]


@pytest.fixture
def process_client(v2_env) -> StorageClient:
    """A StorageClient over a real TestClient bound to the per-test DB."""
    sc = StorageClient(
        base_url="http://testserver", client=TestClient(create_app())
    )
    # PI-β: mirror the desktop, which sends the active engagement as the
    # X-Engagement header on every request, so scoped reads/writes resolve
    # v2_env's seeded ENG-001 through the per-request scope middleware
    # (the TestClient runs the app in a portal thread that does not inherit
    # the test thread's active-engagement ContextVar).
    sc.set_active_engagement("ENG-001")
    return sc


def _seed_domain(client: StorageClient, name: str = "Mentoring") -> str:
    row = client.create_domain(
        {
            "domain_name": name,
            "domain_purpose": "Why it exists",
            "domain_description": "What it covers",
        }
    )
    return row["domain_identifier"]


def _seed_process(
    client: StorageClient,
    name: str,
    *,
    domain_identifier: str,
    **overrides,
) -> dict:
    body = {
        "process_name": name,
        "process_domain_identifier": domain_identifier,
        "process_purpose": overrides.pop(
            "process_purpose", "What this process does"
        ),
    }
    body.update(overrides)
    return client.create_process(body)


def _attach_handoff(
    client: StorageClient, source_id: str, target_id: str
) -> dict:
    return client.create_reference(
        {
            "source_type": "process",
            "source_id": source_id,
            "target_type": "process",
            "target_id": target_id,
            "relationship": "process_hands_off_to_process",
        }
    )


def _wait_rows(qtbot, panel: ProcessesPanel, count: int) -> None:
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == count, timeout=3000)


# ---------------------------------------------------------------------------
# Criterion 10 — sidebar entry under the Methodology group, position #3
# ---------------------------------------------------------------------------


def test_processes_is_third_methodology_entry():
    methodology = dict(SIDEBAR_GROUPS)["Methodology"]
    assert methodology[0] == "Domains"
    assert methodology[1] == "Entities"
    assert methodology[2] == "Processes"


def test_sidebar_renders_processes_under_methodology(qtbot):
    # v0.6 slice B retired uppercased header text per design pass §2.1;
    # see test_domains_panel.py for the pattern.
    from crmbuilder_v2.ui.sidebar import _HEADER_ROLE  # noqa: PLC0415

    sidebar = Sidebar()
    qtbot.addWidget(sidebar)
    items = [sidebar.item(r) for r in range(sidebar.count())]
    headers = {item.text(): i for i, item in enumerate(items) if item.data(_HEADER_ROLE)}
    entries = {
        item.text(): i for i, item in enumerate(items) if not item.data(_HEADER_ROLE)
    }
    assert "Methodology" in headers
    assert "Processes" in entries
    assert entries["Processes"] == entries["Entities"] + 1
    assert entries["Processes"] == headers["Methodology"] + 3


def test_main_window_processes_page_is_panel(
    qtbot, lifecycle_stub, process_client
):
    window = MainWindow(lifecycle=lifecycle_stub, client=process_client)
    qtbot.addWidget(window)
    page = window._stack.widget(window._pages_by_entry["Processes"])
    assert isinstance(page, ProcessesPanel)


# ---------------------------------------------------------------------------
# Criterion 11 — master-pane columns, sort, and context menu
# ---------------------------------------------------------------------------


def test_master_pane_columns_and_order(qtbot, process_client):
    panel = ProcessesPanel(process_client)
    qtbot.addWidget(panel)
    columns = panel.list_columns()
    assert [c.title for c in columns] == [
        "Identifier",
        "Name",
        "Classification",
        "Created",
    ]
    assert [c.field for c in columns] == [
        "process_identifier",
        "process_name",
        "process_classification",
        "created_at_display",
    ]
    # No Domain column in v0.4 (spec 3.6.2, PI-007).
    assert "process_domain_identifier" not in [c.field for c in columns]


def test_master_pane_sorted_by_identifier_ascending(qtbot, process_client):
    dom = _seed_domain(process_client)
    _seed_process(process_client, "Bravo", domain_identifier=dom)
    _seed_process(process_client, "Alpha", domain_identifier=dom)
    _seed_process(process_client, "Charlie", domain_identifier=dom)
    panel = ProcessesPanel(process_client)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 3)
    ids = [
        panel._model.record_at(r)["process_identifier"]
        for r in range(panel._model.rowCount())
    ]
    assert ids == ["PROC-001", "PROC-002", "PROC-003"]


def test_context_menu_actions_live_row(qtbot, process_client):
    dom = _seed_domain(process_client)
    _seed_process(process_client, "Mentor Recruit", domain_identifier=dom)
    panel = ProcessesPanel(process_client)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 1)
    menu = panel._build_context_menu(panel._model.index(0, 0))
    labels = [a.text() for a in menu.actions()]
    assert "New process" in labels
    assert "Edit" in labels
    assert "Delete" in labels
    assert "Restore" not in labels


def test_context_menu_offers_restore_on_soft_deleted_row(
    qtbot, process_client
):
    dom = _seed_domain(process_client)
    _seed_process(process_client, "Mentor Recruit", domain_identifier=dom)
    process_client.delete_process("PROC-001")
    panel = ProcessesPanel(process_client)
    qtbot.addWidget(panel)
    panel._show_deleted_check.setChecked(True)
    qtbot.waitUntil(lambda: panel._model.rowCount() == 1, timeout=3000)
    menu = panel._build_context_menu(panel._model.index(0, 0))
    labels = [a.text() for a in menu.actions()]
    assert "Restore" in labels
    assert "Delete" not in labels


# ---------------------------------------------------------------------------
# Criterion 12 — detail pane field layout
# ---------------------------------------------------------------------------


def test_detail_pane_renders_fields_in_order(qtbot, process_client):
    dom = _seed_domain(process_client)
    panel = ProcessesPanel(process_client)
    qtbot.addWidget(panel)
    record = {
        "process_identifier": "PROC-001",
        "process_name": "Mentor Recruit",
        "process_domain_identifier": dom,
        "process_purpose": "Bring mentors into the program",
        "process_classification": "mission_critical",
        "process_classification_rationale": "Mission stalls without mentors",
        "process_notes": "consultant scratchpad",
        "process_created_at": "2026-05-14T00:00:00+00:00",
        "process_updated_at": "2026-05-14T00:00:00+00:00",
        "process_deleted_at": None,
    }
    extras = panel.fetch_detail_extras(record)
    detail = panel.render_detail(record, extras)

    ordered = [
        w.objectName()
        for w in detail.findChildren(QWidget)
        if w.objectName().startswith("process_")
        and w.objectName().endswith(("_value", "_toggle"))
    ]
    # v0.8 (PI-005) — the Phase 3 detailed-process section value
    # widgets render between the v0.4 classification-rationale row
    # and the Internal notes section per process-v2.md §3.6.3.
    assert ordered == [
        "process_identifier_value",
        "process_name_value",
        "process_domain_identifier_value",
        "process_purpose_value",
        "process_classification_value",
        "process_classification_rationale_value",
        "process_steps_value",
        "process_triggers_value",
        "process_outcomes_value",
        "process_edge_cases_value",
        "process_frequency_value",
        "process_duration_estimate_value",
        "process_notes_toggle",
        "process_notes_value",
    ]

    assert isinstance(
        detail.findChild(QLabel, "process_identifier_value"), QLabel
    )
    name = detail.findChild(QLineEdit, "process_name_value")
    assert name.isReadOnly() and name.text() == "Mentor Recruit"
    # The domain line resolves to "DOM-NNN — Domain Name" for a live FK.
    domain_line = detail.findChild(
        QLineEdit, "process_domain_identifier_value"
    )
    assert dom in domain_line.text()
    assert "Mentoring" in domain_line.text()
    assert detail.findChild(
        QPlainTextEdit, "process_purpose_value"
    ).isReadOnly()
    assert isinstance(
        detail.findChild(QComboBox, "process_classification_value"), QComboBox
    )
    notes_value = detail.findChild(QPlainTextEdit, "process_notes_value")
    assert notes_value.isHidden() is True
    # ReferencesSection always present; no stale-domain warning when the
    # FK resolves to a live domain.
    assert detail.findChildren(ReferencesSection)
    assert detail.findChild(WarningCallout, "process_domain_warning") is None


def test_detail_pane_warns_on_stale_domain_reference(qtbot, process_client):
    """Soft-deleting the affiliated domain surfaces the re-affiliation
    warning above the domain line (spec section 3.4.5 / PRD 4.5)."""
    dom = _seed_domain(process_client)
    _seed_process(process_client, "Mentor Recruit", domain_identifier=dom)
    process_client.delete_domain(dom)  # FK now points at a soft-deleted domain
    panel = ProcessesPanel(process_client)
    qtbot.addWidget(panel)
    record = process_client.get_process("PROC-001")
    extras = panel.fetch_detail_extras(record)
    assert extras["domain"] is None
    detail = panel.render_detail(record, extras)
    warning = detail.findChild(WarningCallout, "process_domain_warning")
    assert warning is not None
    assert dom in warning.text()


# ---------------------------------------------------------------------------
# Criterion 13 — CRUD dialogs end to end
# ---------------------------------------------------------------------------


def test_create_dialog_persists_and_assigns_identifier(qtbot, process_client):
    dom = _seed_domain(process_client)
    dialog = ProcessCreateDialog(process_client)
    qtbot.addWidget(dialog)
    assert "process_identifier" not in dialog._widgets  # server-assigned
    dialog._widgets["process_name"].setText("Mentor Recruit")
    dialog._widgets["process_purpose"].setPlainText(
        "Bring mentors into the program."
    )
    # The domain picker is populated from GET /domains and defaults to
    # the first (only) live domain.
    domain_picker = dialog._field_widgets["process_domain_identifier"]
    assert domain_picker.selected_identifier() == dom
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    assert dialog.created_identifier() == "PROC-001"
    stored = process_client.get_process("PROC-001")
    assert stored["process_name"] == "Mentor Recruit"
    assert stored["process_domain_identifier"] == dom
    assert stored["process_classification"] == "unclassified"


def test_create_dialog_surfaces_duplicate_name_inline(qtbot, process_client):
    dom = _seed_domain(process_client)
    _seed_process(process_client, "Mentor Recruit", domain_identifier=dom)
    dialog = ProcessCreateDialog(process_client)
    qtbot.addWidget(dialog)
    dialog._widgets["process_name"].setText("mentor recruit")
    dialog._widgets["process_purpose"].setPlainText("p")
    dialog._on_save_clicked()
    qtbot.waitUntil(
        lambda: dialog._error_labels["process_name"].text() != "",
        timeout=3000,
    )
    assert dialog.result() != QDialog.DialogCode.Accepted


def test_edit_dialog_persists_classification_and_domain(qtbot, process_client):
    dom_a = _seed_domain(process_client, "Mentoring")
    dom_b = _seed_domain(process_client, "Fundraising")
    _seed_process(process_client, "Mentor Recruit", domain_identifier=dom_a)
    record = process_client.get_process("PROC-001")
    dialog = ProcessEditDialog(process_client, record)
    qtbot.addWidget(dialog)
    assert dialog._widgets["process_identifier"].isReadOnly()
    # The edit dialog restored the domain picker to the record's FK.
    domain_picker = dialog._field_widgets["process_domain_identifier"]
    assert domain_picker.selected_identifier() == dom_a
    # Re-classify and re-affiliate.
    classification = dialog._widgets["process_classification"]
    classification.setCurrentIndex(
        classification.findText("mission_critical")
    )
    dialog._set_widget_value(
        dialog._fields_by_key["process_domain_identifier"], dom_b
    )
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    stored = process_client.get_process("PROC-001")
    assert stored["process_classification"] == "mission_critical"
    assert stored["process_domain_identifier"] == dom_b


def test_delete_dialog_edge_text_then_soft_deletes(qtbot, process_client):
    dom = _seed_domain(process_client)
    _seed_process(process_client, "Mentor Recruit", domain_identifier=dom)
    dialog = ProcessDeleteDialog(process_client, "PROC-001", "Mentor Recruit")
    qtbot.addWidget(dialog)
    assert dialog._delete_btn.isEnabled() is False
    dialog._confirm_edit.setText("PROC-00")
    assert dialog._delete_btn.isEnabled() is False
    dialog._confirm_edit.setText("PROC-001")
    assert dialog._delete_btn.isEnabled() is True
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._delete_btn.click()
    assert process_client.list_processes() == []
    assert len(process_client.list_processes(include_deleted=True)) == 1


def test_panel_new_button_round_trip(qtbot, process_client, monkeypatch):
    dom = _seed_domain(process_client)
    panel = ProcessesPanel(process_client)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 0)

    class _StubCreate:
        def __init__(self, client, parent=None):
            client.create_process(
                {
                    "process_name": "Mentoring Session",
                    "process_domain_identifier": dom,
                    "process_purpose": "p",
                }
            )

        def exec(self):  # noqa: A003 — Qt naming
            return QDialog.DialogCode.Accepted

        def created_identifier(self):
            return "PROC-001"

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.processes.ProcessCreateDialog", _StubCreate
    )
    panel._new_button.click()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 1, timeout=3000)
    assert panel._model.record_at(0)["process_name"] == "Mentoring Session"


# ---------------------------------------------------------------------------
# File-watch refresh
# ---------------------------------------------------------------------------


def test_processes_snapshot_filename_is_mapped():
    assert ENTITY_TYPE_TO_SIDEBAR_LABEL["process"] == "Processes"
def test_kinds_for_pair_process_process_includes_hands_off():
    kinds = _kinds_for_pair("process", "process")
    assert "process_hands_off_to_process" in kinds
    assert "process_hands_off_to_process" in RELATIONSHIP_RULES[
        ("process", "process")
    ]


def test_post_handoff_reference_succeeds(process_client):
    dom = _seed_domain(process_client)
    _seed_process(process_client, "Mentor Recruit", domain_identifier=dom)
    _seed_process(process_client, "Mentor Screening", domain_identifier=dom)
    created = _attach_handoff(process_client, "PROC-001", "PROC-002")
    assert created["source_type"] == "process"
    assert created["target_type"] == "process"
    assert created["relationship"] == "process_hands_off_to_process"
    assert len(process_client.list_references()) == 1


def test_post_handoff_unsupported_kind_returns_422(process_client):
    """A (process, process) reference POST with the wrong/extra kind
    field is rejected with HTTP 422.

    The strict ``ReferenceCreateIn`` schema (``extra="forbid"``) names
    its kind field ``relationship``; a body using the spec-documented
    ``relationship_kind`` key fails request validation."""
    dom = _seed_domain(process_client)
    _seed_process(process_client, "Mentor Recruit", domain_identifier=dom)
    _seed_process(process_client, "Mentor Screening", domain_identifier=dom)
    raw = TestClient(create_app())
    response = raw.post(
        "/references",
        json={
            "source_type": "process",
            "source_id": "PROC-001",
            "target_type": "process",
            "target_id": "PROC-002",
            "relationship_kind": "covers",
        },
    )
    assert response.status_code == 422


def test_direct_db_insert_unknown_relationship_kind_rejected(v2_env):
    """The refs CHECK constraint rejects an unknown ``relationship_kind``
    at the database boundary."""
    with pytest.raises(IntegrityError):
        with session_scope() as s:
            s.add(
                Reference(
                    source_type="process",
                    source_id="PROC-001",
                    target_type="process",
                    target_id="PROC-002",
                    relationship_kind="not_a_real_kind",
                )
            )


def test_reference_create_dialog_enumerates_hands_off(qtbot, process_client):
    """The cascading dialog opened from a Processes-panel "Add reference"
    affordance offers ``process_hands_off_to_process`` for
    (process, process)."""
    dom = _seed_domain(process_client)
    _seed_process(process_client, "Mentor Recruit", domain_identifier=dom)
    dialog = ReferenceCreateDialog(
        process_client, pre_populated_source=("process", "PROC-001")
    )
    qtbot.addWidget(dialog)
    rel = dialog._field_widgets["relationship"]
    kinds = [rel.itemText(i) for i in range(rel.count())]
    assert "process_hands_off_to_process" in kinds
    rel.setCurrentText("process_hands_off_to_process")
    target_type = dialog._field_widgets["target_type"]
    target_types = [
        target_type.itemText(i) for i in range(target_type.count())
    ]
    assert target_types == ["process"]


def test_handoff_round_trips_directionally(qtbot, process_client):
    """A handoff renders outbound on the producer and inbound on the
    consumer, with the directional sub-headings."""
    dom = _seed_domain(process_client)
    _seed_process(process_client, "Mentor Recruit", domain_identifier=dom)
    _seed_process(process_client, "Mentor Screening", domain_identifier=dom)
    _attach_handoff(process_client, "PROC-001", "PROC-002")

    # From the producer's side the handoff is outbound (as_source).
    from_source = process_client.list_references_touching(
        "process", "PROC-001"
    )
    assert len(from_source["as_source"]) == 1
    # From the consumer's side the same handoff is inbound (as_target).
    from_target = process_client.list_references_touching(
        "process", "PROC-002"
    )
    assert len(from_target["as_target"]) == 1

    panel = ProcessesPanel(process_client)
    qtbot.addWidget(panel)

    # Producer detail pane: the handoff renders under "Hands off to".
    producer = process_client.get_process("PROC-001")
    producer_detail = panel.render_detail(
        producer, panel.fetch_detail_extras(producer)
    )
    # PRJ-015: ReferencesSection now renders a grid; the relationship
    # ("Hands off to") and the far-side identifier are cells, not labels.
    producer_cells = _refs_grid_texts(producer_detail)
    assert any("Hands off to" in c for c in producer_cells)
    assert any("PROC-002" in c for c in producer_cells)

    # Consumer detail pane: the handoff renders under "Receives from".
    consumer = process_client.get_process("PROC-002")
    consumer_detail = panel.render_detail(
        consumer, panel.fetch_detail_extras(consumer)
    )
    consumer_cells = _refs_grid_texts(consumer_detail)
    assert any("Receives from" in c for c in consumer_cells)
    assert any("PROC-001" in c for c in consumer_cells)

    # Soft-deleting the producer leaves the handoff in place.
    process_client.delete_process("PROC-001")
    assert len(
        process_client.list_references_touching("process", "PROC-001")[
            "as_source"
        ]
    ) == 1


# ---------------------------------------------------------------------------
# Criterion 15 — sample CBM-redo Phase 1 Prioritized Backbone
# ---------------------------------------------------------------------------


def test_sample_cbm_redo_backbone_persists_across_restart(
    qtbot, process_client
):
    dom_mr = _seed_domain(process_client, "Mentor Recruitment")
    dom_mn = _seed_domain(process_client, "Mentoring")
    dom_cr = _seed_domain(process_client, "Client Recruiting")
    dom_fu = _seed_domain(process_client, "Fundraising")

    # ~8 processes, 2 per domain, mixed classifications (a couple left
    # ``unclassified`` so the transition gate is exercised below).
    specs = [
        ("Mentor Recruit", dom_mr, "mission_critical"),
        ("Mentor Application Screening", dom_mr, "mission_critical"),
        ("Mentor-Mentee Matching", dom_mn, "mission_critical"),
        ("Mentoring Session", dom_mn, "supporting"),
        ("Client Recruit", dom_cr, "mission_critical"),
        ("Client Intake", dom_cr, "unclassified"),
        ("Annual Appeal", dom_fu, "deferred"),
        ("Grant Reporting", dom_fu, "unclassified"),
    ]
    for name, dom, classification in specs:
        body = {
            "process_name": name,
            "process_domain_identifier": dom,
            "process_purpose": f"{name} purpose",
        }
        if classification != "unclassified":
            body["process_classification"] = classification
        process_client.create_process(body)

    # Workability-checked handoff chain across PROC-001..005.
    handoffs = [
        ("PROC-001", "PROC-002"),  # Recruit -> Screening
        ("PROC-002", "PROC-003"),  # Screening -> Matching
        ("PROC-003", "PROC-004"),  # Matching -> Session
        ("PROC-005", "PROC-003"),  # Client Recruit -> Matching
        ("PROC-001", "PROC-003"),  # Recruit -> Matching (direct)
    ]
    for source_id, target_id in handoffs:
        _attach_handoff(process_client, source_id, target_id)

    # Re-affiliate one process to a different domain via PATCH — it
    # keeps its handoff references.
    process_client.patch_process(
        "PROC-006", {"process_domain_identifier": dom_mn}
    )

    # Promote a previously-unclassified process.
    process_client.patch_process(
        "PROC-008", {"process_classification": "supporting"}
    )

    # "Restart": a fresh client + app over the same on-disk database.
    restarted = StorageClient(
        base_url="http://testserver", client=TestClient(create_app())
    )
    restarted.set_active_engagement("ENG-001")  # PI-β: send X-Engagement
    panel = ProcessesPanel(restarted)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, len(specs))

    rows = [panel._model.record_at(r) for r in range(panel._model.rowCount())]
    assert {r["process_name"] for r in rows} == {name for name, _d, _c in specs}
    # Re-affiliation persisted.
    assert restarted.get_process("PROC-006")["process_domain_identifier"] == (
        dom_mn
    )
    # Classification promotion persisted.
    assert restarted.get_process("PROC-008")["process_classification"] == (
        "supporting"
    )
    # Handoffs survived: PROC-003 receives from three producers.
    assert len(
        restarted.list_references_touching("process", "PROC-003")["as_target"]
    ) == 3
    assert len(restarted.list_references()) == len(handoffs)

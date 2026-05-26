"""Personas panel / dialog tests — v0.5+ (PI-003).

Covers ``persona.md`` §3.7 acceptance criteria 9–12, 14: the "Personas"
sidebar entry under Methodology, the master-pane columns and context
menu, the detail-pane field layout (with two collapsible-section
treatments and the ReferencesSection widget for two outgoing reference
kinds), and the CRUD dialogs end to end.

The ``persona_client`` fixture wires a ``StorageClient`` over a real
FastAPI ``TestClient`` bound to the per-test SQLite database, so the
panel, dialogs, and reference flow exercise the genuine
access → REST → DB path.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.vocab import (
    RELATIONSHIP_RULES,
    _kinds_for_pair,
)
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.persona_crud import (
    PersonaCreateDialog,
    PersonaDeleteDialog,
    PersonaEditDialog,
)
from crmbuilder_v2.ui.main_window import (
    ENTITY_TYPE_TO_SIDEBAR_LABEL,
    MainWindow,
)
from crmbuilder_v2.ui.panels.persona import PersonasPanel
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
def persona_client(v2_env) -> StorageClient:
    """A StorageClient over a real TestClient bound to the per-test DB."""
    return StorageClient(
        base_url="http://testserver", client=TestClient(create_app())
    )


def _seed_persona(client: StorageClient, name: str, **overrides) -> dict:
    body = {
        "persona_name": name,
        "persona_role_summary": overrides.pop(
            "persona_role_summary", "What this role does"
        ),
    }
    body.update(overrides)
    return client.create_persona(body)


def _wait_rows(qtbot, panel: PersonasPanel, count: int) -> None:
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == count, timeout=3000)


# ---------------------------------------------------------------------------
# Criterion 9 — sidebar entry under the Methodology group
# ---------------------------------------------------------------------------


def test_personas_is_fifth_methodology_entry():
    methodology = dict(SIDEBAR_GROUPS)["Methodology"]
    assert methodology[0] == "Domains"
    assert methodology[1] == "Entities"
    assert methodology[2] == "Processes"
    # PI-004 cohort inserted "Requirements" at position #4, pushing
    # CRM Candidates to #5 and Personas to #6. Personas remains
    # present and follows CRM Candidates.
    assert "Personas" in methodology
    assert methodology.index("Personas") > methodology.index(
        "CRM Candidates"
    )


def test_sidebar_renders_personas_under_methodology(qtbot):
    from crmbuilder_v2.ui.sidebar import _HEADER_ROLE  # noqa: PLC0415

    sidebar = Sidebar()
    qtbot.addWidget(sidebar)
    items = [sidebar.item(r) for r in range(sidebar.count())]
    headers = {
        item.text(): i for i, item in enumerate(items) if item.data(_HEADER_ROLE)
    }
    entries = {
        item.text(): i
        for i, item in enumerate(items)
        if not item.data(_HEADER_ROLE)
    }
    assert "Methodology" in headers
    assert "Personas" in entries
    # Personas sits directly after CRM Candidates under Methodology.
    assert entries["Personas"] == entries["CRM Candidates"] + 1


def test_main_window_personas_page_is_panel(
    qtbot, lifecycle_stub, persona_client
):
    window = MainWindow(lifecycle=lifecycle_stub, client=persona_client)
    qtbot.addWidget(window)
    page = window._stack.widget(window._pages_by_entry["Personas"])
    assert isinstance(page, PersonasPanel)


# ---------------------------------------------------------------------------
# Criterion 10 — master-pane columns and context menu
# ---------------------------------------------------------------------------


def test_master_pane_columns_and_order(qtbot, persona_client):
    panel = PersonasPanel(persona_client)
    qtbot.addWidget(panel)
    columns = panel.list_columns()
    assert [c.title for c in columns] == [
        "Identifier",
        "Name",
        "Status",
        "Updated",
    ]
    assert [c.field for c in columns] == [
        "persona_identifier",
        "persona_name",
        "persona_status",
        "persona_updated_at",
    ]
    # No Domains or Realized-as column in v0.5+ (spec §3.6.2).
    assert "persona_domains" not in [c.field for c in columns]
    assert "persona_realized_as" not in [c.field for c in columns]


def test_master_pane_sorted_by_identifier_ascending(qtbot, persona_client):
    _seed_persona(persona_client, "Bravo")
    _seed_persona(persona_client, "Alpha")
    _seed_persona(persona_client, "Charlie")
    panel = PersonasPanel(persona_client)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 3)
    ids = [
        panel._model.record_at(r)["persona_identifier"]
        for r in range(panel._model.rowCount())
    ]
    assert ids == ["PER-001", "PER-002", "PER-003"]


def test_new_button_label_is_new_persona(qtbot, persona_client):
    panel = PersonasPanel(persona_client)
    qtbot.addWidget(panel)
    assert panel._new_button.text() == "New Persona"


def test_context_menu_actions_live_row(qtbot, persona_client):
    _seed_persona(persona_client, "Mentor Coordinator")
    panel = PersonasPanel(persona_client)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 1)
    menu = panel._build_context_menu(panel._model.index(0, 0))
    labels = [a.text() for a in menu.actions()]
    assert "New persona" in labels
    assert "Edit" in labels
    assert "Delete" in labels
    assert "Restore" not in labels


def test_context_menu_offers_restore_on_soft_deleted_row(
    qtbot, persona_client
):
    _seed_persona(persona_client, "Mentor Coordinator")
    persona_client.delete_persona("PER-001")
    panel = PersonasPanel(persona_client)
    qtbot.addWidget(panel)
    panel._show_deleted_check.setChecked(True)
    qtbot.waitUntil(lambda: panel._model.rowCount() == 1, timeout=3000)
    menu = panel._build_context_menu(panel._model.index(0, 0))
    labels = [a.text() for a in menu.actions()]
    assert "Restore" in labels
    assert "Delete" not in labels


# ---------------------------------------------------------------------------
# Criterion 11 — detail pane field layout
# ---------------------------------------------------------------------------


def test_detail_pane_renders_seven_fields_in_order(qtbot, persona_client):
    panel = PersonasPanel(persona_client)
    qtbot.addWidget(panel)
    record = {
        "persona_identifier": "PER-001",
        "persona_name": "Mentor Coordinator",
        "persona_status": "confirmed",
        "persona_role_summary": "Oversees the mentor program day-to-day",
        "persona_responsibilities": "- Approves applications\n- Pairs",
        "persona_notes": "consultant scratchpad",
        "persona_created_at": "2026-05-25T00:00:00+00:00",
        "persona_updated_at": "2026-05-25T00:00:00+00:00",
        "persona_deleted_at": None,
    }
    detail = panel.render_detail(
        record, {"references": {"as_source": [], "as_target": []}}
    )

    # Construction order of the prefixed value widgets equals the
    # §3.2 field order. The responsibilities section toggle precedes
    # its value widget; same for notes.
    ordered = [
        w.objectName()
        for w in detail.findChildren(QWidget)
        if w.objectName().startswith("persona_")
        and w.objectName().endswith(("_value", "_toggle"))
    ]
    assert ordered == [
        "persona_identifier_value",
        "persona_name_value",
        "persona_role_summary_value",
        "persona_responsibilities_toggle",
        "persona_responsibilities_value",
        "persona_notes_toggle",
        "persona_notes_value",
        "persona_status_value",
    ]

    # Identifier is a read-only label; name a read-only line editor;
    # role_summary a read-only multi-line; status a combo box.
    assert isinstance(
        detail.findChild(QLabel, "persona_identifier_value"), QLabel
    )
    name = detail.findChild(QLineEdit, "persona_name_value")
    assert name.isReadOnly() and name.text() == "Mentor Coordinator"
    assert detail.findChild(
        QPlainTextEdit, "persona_role_summary_value"
    ).isReadOnly()
    assert isinstance(
        detail.findChild(QComboBox, "persona_status_value"), QComboBox
    )

    # persona_responsibilities is **expanded by default** per spec §3.6.3.
    responsibilities_value = detail.findChild(
        QPlainTextEdit, "persona_responsibilities_value"
    )
    assert responsibilities_value.isHidden() is False
    # persona_notes is collapsed by default per spec §3.6.3.
    notes_value = detail.findChild(QPlainTextEdit, "persona_notes_value")
    assert notes_value.isHidden() is True
    # ReferencesSection is always present (renders outgoing affiliations
    # and realization plus any inbound kinds).
    assert detail.findChildren(ReferencesSection)


# ---------------------------------------------------------------------------
# Criterion 12 — CRUD dialogs end to end
# ---------------------------------------------------------------------------


def test_create_dialog_persists_and_assigns_identifier(qtbot, persona_client):
    dialog = PersonaCreateDialog(persona_client)
    qtbot.addWidget(dialog)
    assert "persona_identifier" not in dialog._widgets  # server-assigned
    dialog._widgets["persona_name"].setText("Mentor Coordinator")
    dialog._widgets["persona_role_summary"].setPlainText(
        "Oversees the mentor program day-to-day"
    )
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    assert dialog.created_identifier() == "PER-001"
    stored = persona_client.get_persona("PER-001")
    assert stored["persona_name"] == "Mentor Coordinator"
    assert stored["persona_status"] == "candidate"


def test_create_dialog_surfaces_duplicate_name_inline(qtbot, persona_client):
    _seed_persona(persona_client, "Mentor Coordinator")
    dialog = PersonaCreateDialog(persona_client)
    qtbot.addWidget(dialog)
    dialog._widgets["persona_name"].setText("mentor coordinator")
    dialog._widgets["persona_role_summary"].setPlainText("r")
    dialog._on_save_clicked()
    qtbot.waitUntil(
        lambda: dialog._error_labels["persona_name"].text() != "",
        timeout=3000,
    )
    assert dialog.result() != QDialog.DialogCode.Accepted


def test_edit_dialog_persists_status_change(qtbot, persona_client):
    _seed_persona(persona_client, "Mentor Coordinator")
    record = persona_client.get_persona("PER-001")
    dialog = PersonaEditDialog(persona_client, record)
    qtbot.addWidget(dialog)
    assert dialog._widgets["persona_identifier"].isReadOnly()
    status = dialog._widgets["persona_status"]
    status.setCurrentIndex(status.findText("confirmed"))
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    assert (
        persona_client.get_persona("PER-001")["persona_status"] == "confirmed"
    )


def test_delete_dialog_edge_text_then_soft_deletes(qtbot, persona_client):
    _seed_persona(persona_client, "Mentor Coordinator")
    dialog = PersonaDeleteDialog(
        persona_client, "PER-001", "Mentor Coordinator"
    )
    qtbot.addWidget(dialog)
    # Delete is disabled until the identifier is typed exactly.
    assert dialog._delete_btn.isEnabled() is False
    dialog._confirm_edit.setText("PER-00")
    assert dialog._delete_btn.isEnabled() is False
    dialog._confirm_edit.setText("PER-001")
    assert dialog._delete_btn.isEnabled() is True
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._delete_btn.click()
    assert persona_client.list_personas() == []
    assert len(persona_client.list_personas(include_deleted=True)) == 1


# ---------------------------------------------------------------------------
# File-watch + ENTITY_TYPE_TO_SIDEBAR_LABEL wiring
# ---------------------------------------------------------------------------


def test_personas_snapshot_filename_is_mapped():
    """Persona's snapshot filename routes to the persona entity type
    and the entity type maps to the 'Personas' sidebar label.
    """
    assert _FILENAME_TO_ENTITY_TYPE["personas.json"] == "persona"
    assert ENTITY_TYPE_TO_SIDEBAR_LABEL["persona"] == "Personas"


# ---------------------------------------------------------------------------
# Vocab integration (mirrors entity's criterion 13 test)
# ---------------------------------------------------------------------------


def test_kinds_for_pair_persona_domain_includes_scopes_to_domain():
    kinds = _kinds_for_pair("persona", "domain")
    assert "persona_scopes_to_domain" in kinds
    assert (
        "persona_scopes_to_domain"
        in RELATIONSHIP_RULES[("persona", "domain")]
    )


def test_kinds_for_pair_persona_entity_includes_realized_as_entity():
    kinds = _kinds_for_pair("persona", "entity")
    assert "persona_realized_as_entity" in kinds
    assert (
        "persona_realized_as_entity"
        in RELATIONSHIP_RULES[("persona", "entity")]
    )

"""Entities panel / dialog tests — UI v0.4 slice C.

Covers ``entity.md`` section 3.7 acceptance criteria 9–16: the
"Entities" sidebar entry at Methodology position #2, the master-pane
columns and context menu, the detail-pane field layout, the CRUD
dialogs end to end, file-watch refresh routing, the
``entity_scopes_to_domain`` vocab registration and constraint
enforcement, the bidirectional reference round-trip, and authoring a
small CBM-redo Phase 1 entity set (with domain affiliations) that
survives an app "restart".

The ``entity_client`` fixture wires a ``StorageClient`` over a real
FastAPI ``TestClient`` bound to the per-test SQLite database, so the
panel, dialogs, and reference flow exercise the genuine
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
from crmbuilder_v2.ui.dialogs.entity_crud import (
    EntityCreateDialog,
    EntityDeleteDialog,
    EntityEditDialog,
)
from crmbuilder_v2.ui.dialogs.reference_create import ReferenceCreateDialog
from crmbuilder_v2.ui.main_window import (
    ENTITY_TYPE_TO_SIDEBAR_LABEL,
    MainWindow,
)
from crmbuilder_v2.ui.panels.entities import EntitiesPanel
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
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def entity_client(v2_env) -> StorageClient:
    """A StorageClient over a real TestClient bound to the per-test DB."""
    return StorageClient(
        base_url="http://testserver", client=TestClient(create_app())
    )


def _seed_entity(client: StorageClient, name: str, **overrides) -> dict:
    body = {
        "entity_name": name,
        "entity_description": overrides.pop(
            "entity_description", "What kind of thing it is"
        ),
    }
    body.update(overrides)
    return client.create_entity(body)


def _seed_domain(client: StorageClient, name: str, **overrides) -> dict:
    body = {
        "domain_name": name,
        "domain_purpose": overrides.pop("domain_purpose", "Why it exists"),
        "domain_description": overrides.pop(
            "domain_description", "What it covers"
        ),
    }
    body.update(overrides)
    return client.create_domain(body)


def _attach_scope(
    client: StorageClient, entity_id: str, domain_id: str
) -> dict:
    return client.create_reference(
        {
            "source_type": "entity",
            "source_id": entity_id,
            "target_type": "domain",
            "target_id": domain_id,
            "relationship": "entity_scopes_to_domain",
        }
    )


def _wait_rows(qtbot, panel: EntitiesPanel, count: int) -> None:
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == count, timeout=3000)


# ---------------------------------------------------------------------------
# Criterion 9 — sidebar entry under the Methodology group, position #2
# ---------------------------------------------------------------------------


def test_entities_is_second_methodology_entry():
    methodology = dict(SIDEBAR_GROUPS)["Methodology"]
    assert methodology[0] == "Domains"
    assert methodology[1] == "Entities"


def test_sidebar_renders_entities_under_methodology(qtbot):
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
    assert "Entities" in entries
    # Entities sits directly after Domains, both under Methodology.
    assert entries["Entities"] == entries["Domains"] + 1
    assert entries["Entities"] == headers["Methodology"] + 2


def test_main_window_entities_page_is_panel(qtbot, lifecycle_stub, entity_client):
    window = MainWindow(lifecycle=lifecycle_stub, client=entity_client)
    qtbot.addWidget(window)
    page = window._stack.widget(window._pages_by_entry["Entities"])
    assert isinstance(page, EntitiesPanel)


# ---------------------------------------------------------------------------
# Criterion 10 — master-pane columns, sort, and context menu
# ---------------------------------------------------------------------------


def test_master_pane_columns_and_order(qtbot, entity_client):
    panel = EntitiesPanel(entity_client)
    qtbot.addWidget(panel)
    columns = panel.list_columns()
    assert [c.title for c in columns] == [
        "Identifier",
        "Name",
        "Status",
        "Created",
    ]
    assert [c.field for c in columns] == [
        "entity_identifier",
        "entity_name",
        "entity_status",
        "created_at_display",
    ]
    # No Domains column in v0.4 (spec 3.6.2, PI-009).
    assert "entity_domains" not in [c.field for c in columns]


def test_master_pane_sorted_by_identifier_ascending(qtbot, entity_client):
    _seed_entity(entity_client, "Bravo")
    _seed_entity(entity_client, "Alpha")
    _seed_entity(entity_client, "Charlie")
    panel = EntitiesPanel(entity_client)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 3)
    ids = [
        panel._model.record_at(r)["entity_identifier"]
        for r in range(panel._model.rowCount())
    ]
    assert ids == ["ENT-001", "ENT-002", "ENT-003"]


def test_context_menu_actions_live_row(qtbot, entity_client):
    _seed_entity(entity_client, "Contact")
    panel = EntitiesPanel(entity_client)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 1)
    menu = panel._build_context_menu(panel._model.index(0, 0))
    labels = [a.text() for a in menu.actions()]
    assert "New entity" in labels
    assert "Edit" in labels
    assert "Delete" in labels
    assert "Restore" not in labels


def test_context_menu_offers_restore_on_soft_deleted_row(qtbot, entity_client):
    _seed_entity(entity_client, "Contact")
    entity_client.delete_entity("ENT-001")
    panel = EntitiesPanel(entity_client)
    qtbot.addWidget(panel)
    panel._show_deleted_check.setChecked(True)  # toggles include_deleted
    qtbot.waitUntil(lambda: panel._model.rowCount() == 1, timeout=3000)
    menu = panel._build_context_menu(panel._model.index(0, 0))
    labels = [a.text() for a in menu.actions()]
    assert "Restore" in labels
    assert "Delete" not in labels


# ---------------------------------------------------------------------------
# Criterion 11 — detail pane field layout
# ---------------------------------------------------------------------------


def test_detail_pane_renders_seven_fields_in_order(qtbot, entity_client):
    panel = EntitiesPanel(entity_client)
    qtbot.addWidget(panel)
    record = {
        "entity_identifier": "ENT-001",
        "entity_name": "Mentor",
        "entity_status": "confirmed",
        "entity_description": "A person who provides mentoring guidance",
        "entity_notes": "consultant scratchpad",
        "entity_created_at": "2026-05-14T00:00:00+00:00",
        "entity_updated_at": "2026-05-14T00:00:00+00:00",
        "entity_deleted_at": None,
    }
    detail = panel.render_detail(
        record, {"references": {"as_source": [], "as_target": []}}
    )

    # Construction order of the prefixed value widgets equals the
    # section-3.2 field order (no purpose field — unlike domain).
    ordered = [
        w.objectName()
        for w in detail.findChildren(QWidget)
        if w.objectName().startswith("entity_") and w.objectName().endswith(
            ("_value", "_toggle")
        )
    ]
    assert ordered == [
        "entity_identifier_value",
        "entity_name_value",
        "entity_description_value",
        "entity_notes_toggle",
        "entity_notes_value",
        "entity_status_value",
        # PI-010 / DEC-292: entity_kind read-only label, "(unclassified)"
        # when NULL.
        "entity_kind_value",
    ]

    # Identifier is a read-only label; name a read-only line editor;
    # description a read-only multi-line; status a combo box.
    assert isinstance(
        detail.findChild(QLabel, "entity_identifier_value"), QLabel
    )
    name = detail.findChild(QLineEdit, "entity_name_value")
    assert name.isReadOnly() and name.text() == "Mentor"
    assert detail.findChild(
        QPlainTextEdit, "entity_description_value"
    ).isReadOnly()
    assert isinstance(
        detail.findChild(QComboBox, "entity_status_value"), QComboBox
    )

    # entity_notes is collapsed by default under the "Internal notes"
    # toggle.
    notes_value = detail.findChild(QPlainTextEdit, "entity_notes_value")
    assert notes_value.isHidden() is True
    # ReferencesSection is always present (renders outgoing affiliations
    # plus any inbound kinds).
    assert detail.findChildren(ReferencesSection)


# ---------------------------------------------------------------------------
# Criterion 12 — CRUD dialogs end to end
# ---------------------------------------------------------------------------


def test_create_dialog_persists_and_assigns_identifier(qtbot, entity_client):
    dialog = EntityCreateDialog(entity_client)
    qtbot.addWidget(dialog)
    assert "entity_identifier" not in dialog._widgets  # server-assigned
    dialog._widgets["entity_name"].setText("Engagement")
    dialog._widgets["entity_description"].setPlainText(
        "A formal pairing between a mentor and a mentee."
    )
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    assert dialog.created_identifier() == "ENT-001"
    stored = entity_client.get_entity("ENT-001")
    assert stored["entity_name"] == "Engagement"
    assert stored["entity_status"] == "candidate"


def test_create_dialog_surfaces_duplicate_name_inline(qtbot, entity_client):
    _seed_entity(entity_client, "Contact")
    dialog = EntityCreateDialog(entity_client)
    qtbot.addWidget(dialog)
    dialog._widgets["entity_name"].setText("contact")
    dialog._widgets["entity_description"].setPlainText("d")
    dialog._on_save_clicked()
    qtbot.waitUntil(
        lambda: dialog._error_labels["entity_name"].text() != "", timeout=3000
    )
    assert dialog.result() != QDialog.DialogCode.Accepted


def test_edit_dialog_persists_status_change(qtbot, entity_client):
    _seed_entity(entity_client, "Contact")
    record = entity_client.get_entity("ENT-001")
    dialog = EntityEditDialog(entity_client, record)
    qtbot.addWidget(dialog)
    assert dialog._widgets["entity_identifier"].isReadOnly()
    status = dialog._widgets["entity_status"]
    status.setCurrentIndex(status.findText("confirmed"))
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    assert entity_client.get_entity("ENT-001")["entity_status"] == "confirmed"


def test_delete_dialog_edge_text_then_soft_deletes(qtbot, entity_client):
    _seed_entity(entity_client, "Contact")
    dialog = EntityDeleteDialog(entity_client, "ENT-001", "Contact")
    qtbot.addWidget(dialog)
    # Delete is disabled until the identifier is typed exactly.
    assert dialog._delete_btn.isEnabled() is False
    dialog._confirm_edit.setText("ENT-00")
    assert dialog._delete_btn.isEnabled() is False
    dialog._confirm_edit.setText("ENT-001")
    assert dialog._delete_btn.isEnabled() is True
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._delete_btn.click()
    assert entity_client.list_entities() == []
    assert len(entity_client.list_entities(include_deleted=True)) == 1


def test_panel_new_button_round_trip(qtbot, entity_client, monkeypatch):
    """The New Entity button opens the create dialog; on accept the
    panel selects the freshly created row."""
    panel = EntitiesPanel(entity_client)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 0)

    class _StubCreate:
        def __init__(self, client, parent=None):
            client.create_entity(
                {
                    "entity_name": "Session",
                    "entity_description": "d",
                }
            )

        def exec(self):  # noqa: A003 — Qt naming
            return QDialog.DialogCode.Accepted

        def created_identifier(self):
            return "ENT-001"

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.entities.EntityCreateDialog", _StubCreate
    )
    panel._new_button.click()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 1, timeout=3000)
    assert panel._model.record_at(0)["entity_name"] == "Session"


# ---------------------------------------------------------------------------
# Criterion 13 — file-watch refresh
# ---------------------------------------------------------------------------


def test_entities_snapshot_filename_is_mapped():
    # Slice A registered the snapshot filename; slice C's panel consumes
    # the resulting ``data_changed`` events.
    assert _FILENAME_TO_ENTITY_TYPE["entities.json"] == "entity"
    assert ENTITY_TYPE_TO_SIDEBAR_LABEL["entity"] == "Entities"


def test_external_write_refreshes_current_entities_panel(
    qtbot, lifecycle_stub, entity_client, export_dir
):
    window = MainWindow(
        lifecycle=lifecycle_stub, client=entity_client, snapshot_dir=export_dir
    )
    qtbot.addWidget(window)
    window._sidebar.select_entry("Entities")
    panel = window._stack.widget(window._pages_by_entry["Entities"])
    _wait_rows(qtbot, panel, 0)

    # External REST write — the exporter rewrites entities.json.
    _seed_entity(entity_client, "Contact")

    # The file-watch service routes an ``entity`` change to the current
    # panel's refresh; drive that slot directly (the QFileSystemWatcher
    # plumbing itself is covered by test_refresh).
    window._on_data_changed("entity")
    qtbot.waitUntil(lambda: panel._model.rowCount() == 1, timeout=3000)
    assert panel._model.record_at(0)["entity_name"] == "Contact"


# ---------------------------------------------------------------------------
# Criterion 14 — entity_scopes_to_domain registered + constrained
# ---------------------------------------------------------------------------


def test_kinds_for_pair_entity_domain_includes_scopes_to_domain():
    kinds = _kinds_for_pair("entity", "domain")
    assert "entity_scopes_to_domain" in kinds
    assert "entity_scopes_to_domain" in RELATIONSHIP_RULES[("entity", "domain")]


def test_post_reference_entity_scopes_to_domain_succeeds(entity_client):
    _seed_entity(entity_client, "Contact")
    _seed_domain(entity_client, "Mentoring")
    created = _attach_scope(entity_client, "ENT-001", "DOM-001")
    assert created["source_type"] == "entity"
    assert created["target_type"] == "domain"
    assert created["relationship"] == "entity_scopes_to_domain"
    # The row landed in the refs table.
    assert len(entity_client.list_references()) == 1


def test_post_reference_unsupported_kind_returns_422(entity_client):
    """A (entity, domain) reference POST with the wrong/extra kind field
    is rejected with HTTP 422.

    The strict ``ReferenceCreateIn`` schema (``extra="forbid"``) names
    its kind field ``relationship``; a body using the spec-documented
    ``relationship_kind`` key — or any unsupported shape — fails request
    validation and never reaches the access layer.
    """
    _seed_entity(entity_client, "Contact")
    _seed_domain(entity_client, "Mentoring")
    raw = TestClient(create_app())
    response = raw.post(
        "/references",
        json={
            "source_type": "entity",
            "source_id": "ENT-001",
            "target_type": "domain",
            "target_id": "DOM-001",
            "relationship_kind": "covers",
        },
    )
    assert response.status_code == 422


def test_direct_db_insert_unknown_relationship_kind_rejected(v2_env):
    """The refs CHECK constraint (extended in slice A) rejects an unknown
    ``relationship_kind`` at the database boundary."""
    with pytest.raises(IntegrityError):
        with session_scope() as s:
            s.add(
                Reference(
                    source_type="entity",
                    source_id="ENT-001",
                    target_type="domain",
                    target_id="DOM-001",
                    relationship_kind="not_a_real_kind",
                )
            )


def test_reference_create_dialog_enumerates_entity_scopes_to_domain(
    qtbot, entity_client
):
    """The cascading dialog opened from an Entities-panel "Add reference"
    affordance offers ``entity_scopes_to_domain`` for (entity, domain)."""
    _seed_entity(entity_client, "Contact")
    _seed_domain(entity_client, "Mentoring")
    dialog = ReferenceCreateDialog(
        entity_client, pre_populated_source=("entity", "ENT-001")
    )
    qtbot.addWidget(dialog)
    rel = dialog._field_widgets["relationship"]
    kinds = [rel.itemText(i) for i in range(rel.count())]
    assert "entity_scopes_to_domain" in kinds
    # Selecting the kind narrows the target-type combo to ``domain``.
    rel.setCurrentText("entity_scopes_to_domain")
    target_type = dialog._field_widgets["target_type"]
    target_types = [target_type.itemText(i) for i in range(target_type.count())]
    assert target_types == ["domain"]


# ---------------------------------------------------------------------------
# Criterion 15 — bidirectional reference round-trip
# ---------------------------------------------------------------------------


def test_reference_round_trip_visible_from_both_sides(qtbot, entity_client):
    _seed_entity(entity_client, "Contact")
    _seed_domain(entity_client, "Mentoring")
    _attach_scope(entity_client, "ENT-001", "DOM-001")

    # From the entity side the reference is outgoing (as_source).
    from_entity = entity_client.list_references_touching("entity", "ENT-001")
    assert len(from_entity["as_source"]) == 1
    assert from_entity["as_source"][0]["relationship"] == (
        "entity_scopes_to_domain"
    )
    # From the domain side the same reference is inbound (as_target).
    from_domain = entity_client.list_references_touching("domain", "DOM-001")
    assert len(from_domain["as_target"]) == 1

    # The entity detail pane renders the affiliation under its
    # ReferencesSection.
    panel = EntitiesPanel(entity_client)
    qtbot.addWidget(panel)
    record = entity_client.get_entity("ENT-001")
    extras = panel.fetch_detail_extras(record)
    detail = panel.render_detail(record, extras)
    # PRJ-015: references render in a grid; the far-side identifier is a
    # cell value rather than a QLabel link.
    from crmbuilder_v2.ui.widgets.references_section import ReferencesSection

    section = detail.findChild(ReferencesSection)
    assert section is not None
    proxy = section._proxy
    cells = [
        str(proxy.data(proxy.index(r, c)) or "")
        for r in range(proxy.rowCount())
        for c in range(proxy.columnCount())
    ]
    assert any("DOM-001" in c for c in cells), (
        "domain affiliation should render in references grid"
    )

    # Soft-deleting the entity leaves the reference in place.
    entity_client.delete_entity("ENT-001")
    still_there = entity_client.list_references_touching("entity", "ENT-001")
    assert len(still_there["as_source"]) == 1
    # Restoring the entity keeps the reference live.
    entity_client.restore_entity("ENT-001")
    assert len(
        entity_client.list_references_touching("entity", "ENT-001")["as_source"]
    ) == 1


# ---------------------------------------------------------------------------
# Criterion 16 — sample CBM-redo Phase 1 records persist across restart
# ---------------------------------------------------------------------------


def test_sample_cbm_redo_records_persist_across_restart(qtbot, entity_client):
    domain_names = ["Mentoring", "Mentor Recruitment", "Fundraising"]
    for name in domain_names:
        _seed_domain(entity_client, name)
    domain_ids = ["DOM-001", "DOM-002", "DOM-003"]

    entity_names = [
        "Contact",
        "Account",
        "Engagement",
        "Session",
        "Mentor",
        "Mentor Application",
        "Client",
        "Dues",
        "Contribution",
        "Fundraising Campaign",
    ]
    for name in entity_names:
        _seed_entity(entity_client, name)

    # Each entity scopes to 1-3 domains.
    for index in range(len(entity_names)):
        entity_id = f"ENT-{index + 1:03d}"
        affiliations = domain_ids[: (index % 3) + 1]
        for domain_id in affiliations:
            _attach_scope(entity_client, entity_id, domain_id)

    # Transition every entity from candidate to confirmed.
    for index in range(len(entity_names)):
        entity_client.patch_entity(
            f"ENT-{index + 1:03d}", {"entity_status": "confirmed"}
        )

    # "Restart": a fresh client + app over the same on-disk database.
    restarted = StorageClient(
        base_url="http://testserver", client=TestClient(create_app())
    )
    panel = EntitiesPanel(restarted)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, len(entity_names))

    rows = [panel._model.record_at(r) for r in range(panel._model.rowCount())]
    assert {r["entity_name"] for r in rows} == set(entity_names)
    assert all(r["entity_status"] == "confirmed" for r in rows)

    # References survived too — ENT-001 scoped to one domain, ENT-003 to
    # three.
    assert len(
        restarted.list_references_touching("entity", "ENT-001")["as_source"]
    ) == 1
    assert len(
        restarted.list_references_touching("entity", "ENT-003")["as_source"]
    ) == 3

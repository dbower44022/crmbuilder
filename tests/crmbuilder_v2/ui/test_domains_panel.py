"""Domains panel / dialog tests — UI v0.4 slice B.

Covers ``domain.md`` section 3.7 acceptance criteria 9–14: the
"Domains" sidebar entry under the Methodology group, the master-pane
columns and context menu, the detail-pane field layout, the CRUD
dialogs end to end, file-watch refresh routing, and authoring a small
CBM-redo Phase 1 domain set that survives an app "restart".

The ``domain_client`` fixture wires a ``StorageClient`` over a real
FastAPI ``TestClient`` bound to the per-test SQLite database, so the
panel and dialogs exercise the genuine access → REST → DB path.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.domain_crud import (
    DomainCreateDialog,
    DomainDeleteDialog,
    DomainEditDialog,
)
from crmbuilder_v2.ui.main_window import (
    ENTITY_TYPE_TO_SIDEBAR_LABEL,
    MainWindow,
)
from crmbuilder_v2.ui.panels.domains import DomainsPanel
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
def domain_client(v2_env) -> StorageClient:
    """A StorageClient over a real TestClient bound to the per-test DB."""
    return StorageClient(
        base_url="http://testserver", client=TestClient(create_app())
    )


def _seed(client: StorageClient, name: str, **overrides) -> dict:
    body = {
        "domain_name": name,
        "domain_purpose": overrides.pop("domain_purpose", "Why it exists"),
        "domain_description": overrides.pop(
            "domain_description", "What it covers"
        ),
    }
    body.update(overrides)
    return client.create_domain(body)


def _wait_rows(qtbot, panel: DomainsPanel, count: int) -> None:
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == count, timeout=3000)


def _select_and_load_detail(qtbot, panel: DomainsPanel, row: int) -> QWidget:
    panel._select_row(row)
    qtbot.waitUntil(
        lambda: panel._detail_stack.currentWidget()
        not in (panel._loading_detail, panel._empty_detail),
        timeout=3000,
    )
    return panel._detail_stack.currentWidget()


# ---------------------------------------------------------------------------
# Criterion 9 — sidebar entry under the Methodology group
# ---------------------------------------------------------------------------


def test_domains_is_first_methodology_entry():
    methodology = dict(SIDEBAR_GROUPS)["Methodology"]
    assert methodology[0] == "Domains"


def test_sidebar_renders_domains_under_methodology(qtbot):
    # v0.6 slice B retired uppercased header text per design pass §2.1;
    # headers are sentence-cased ("Methodology") and distinguished from
    # entries via the per-item header role.
    from crmbuilder_v2.ui.sidebar import _HEADER_ROLE  # noqa: PLC0415

    sidebar = Sidebar()
    qtbot.addWidget(sidebar)
    items = [sidebar.item(r) for r in range(sidebar.count())]
    headers = {item.text(): i for i, item in enumerate(items) if item.data(_HEADER_ROLE)}
    entries = {
        item.text(): i for i, item in enumerate(items) if not item.data(_HEADER_ROLE)
    }
    assert "Methodology" in headers
    assert "Domains" in entries
    # Domains sits directly after the Methodology header.
    assert entries["Domains"] == headers["Methodology"] + 1


def test_main_window_domains_page_is_panel(qtbot, lifecycle_stub, domain_client):
    window = MainWindow(lifecycle=lifecycle_stub, client=domain_client)
    qtbot.addWidget(window)
    page = window._stack.widget(window._pages_by_entry["Domains"])
    assert isinstance(page, DomainsPanel)


# ---------------------------------------------------------------------------
# Criterion 10 — master-pane columns, sort, and context menu
# ---------------------------------------------------------------------------


def test_master_pane_columns_and_order(qtbot, domain_client):
    panel = DomainsPanel(domain_client)
    qtbot.addWidget(panel)
    columns = panel.list_columns()
    assert [c.title for c in columns] == [
        "Identifier",
        "Name",
        "Status",
        "Updated",
    ]
    assert [c.field for c in columns] == [
        "domain_identifier",
        "domain_name",
        "domain_status",
        "domain_updated_at",
    ]


def test_master_pane_sorted_by_identifier_ascending(qtbot, domain_client):
    _seed(domain_client, "Bravo")
    _seed(domain_client, "Alpha")
    _seed(domain_client, "Charlie")
    panel = DomainsPanel(domain_client)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 3)
    ids = [
        panel._model.record_at(r)["domain_identifier"]
        for r in range(panel._model.rowCount())
    ]
    assert ids == ["DOM-001", "DOM-002", "DOM-003"]


def test_context_menu_actions_live_row(qtbot, domain_client):
    _seed(domain_client, "Mentoring")
    panel = DomainsPanel(domain_client)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 1)
    menu = panel._build_context_menu(panel._model.index(0, 0))
    labels = [a.text() for a in menu.actions()]
    assert "New domain" in labels
    assert "Edit" in labels
    assert "Delete" in labels
    assert "Restore" not in labels


def test_context_menu_offers_restore_on_soft_deleted_row(qtbot, domain_client):
    _seed(domain_client, "Mentoring")
    domain_client.delete_domain("DOM-001")
    panel = DomainsPanel(domain_client)
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


def test_detail_pane_renders_seven_fields_in_order(qtbot, domain_client):
    panel = DomainsPanel(domain_client)
    qtbot.addWidget(panel)
    record = {
        "domain_identifier": "DOM-001",
        "domain_name": "Mentoring",
        "domain_status": "confirmed",
        "domain_purpose": "Why the mission needs it",
        "domain_description": "What it covers",
        "domain_notes": "consultant scratchpad",
        "domain_created_at": "2026-05-14T00:00:00+00:00",
        "domain_updated_at": "2026-05-14T00:00:00+00:00",
        "domain_deleted_at": None,
    }
    detail = panel.render_detail(
        record, {"references": {"as_source": [], "as_target": []}}
    )

    # Construction order of the prefixed value widgets equals the
    # section-3.2 field order.
    ordered = [
        w.objectName()
        for w in detail.findChildren(QWidget)
        if w.objectName().startswith("domain_") and w.objectName().endswith(
            ("_value", "_toggle")
        )
    ]
    assert ordered == [
        "domain_identifier_value",
        "domain_name_value",
        "domain_purpose_value",
        "domain_description_value",
        "domain_notes_toggle",
        "domain_notes_value",
        "domain_status_value",
    ]

    # Identifier is a read-only label; name/purpose read-only line
    # editors; description read-only multi-line; status a combo box.
    assert isinstance(detail.findChild(QLabel, "domain_identifier_value"), QLabel)
    name = detail.findChild(QLineEdit, "domain_name_value")
    assert name.isReadOnly() and name.text() == "Mentoring"
    assert detail.findChild(QLineEdit, "domain_purpose_value").isReadOnly()
    assert detail.findChild(
        QPlainTextEdit, "domain_description_value"
    ).isReadOnly()
    assert isinstance(
        detail.findChild(QComboBox, "domain_status_value"), QComboBox
    )

    # domain_notes is collapsed by default under the "Internal notes"
    # toggle.
    notes_value = detail.findChild(QPlainTextEdit, "domain_notes_value")
    assert notes_value.isHidden() is True
    # ReferencesSection is always present (inbound side only in v0.4).
    assert detail.findChildren(ReferencesSection)


# ---------------------------------------------------------------------------
# Criterion 12 — CRUD dialogs end to end
# ---------------------------------------------------------------------------


def test_create_dialog_persists_and_assigns_identifier(qtbot, domain_client):
    dialog = DomainCreateDialog(domain_client)
    qtbot.addWidget(dialog)
    assert "domain_identifier" not in dialog._widgets  # server-assigned
    dialog._widgets["domain_name"].setText("Mentor Recruitment")
    dialog._widgets["domain_purpose"].setText("Bring mentors into the program")
    dialog._widgets["domain_description"].setPlainText(
        "Sourcing, screening and onboarding volunteer mentors."
    )
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    assert dialog.created_identifier() == "DOM-001"
    stored = domain_client.get_domain("DOM-001")
    assert stored["domain_name"] == "Mentor Recruitment"
    assert stored["domain_status"] == "candidate"


def test_create_dialog_surfaces_duplicate_name_inline(qtbot, domain_client):
    _seed(domain_client, "Mentoring")
    dialog = DomainCreateDialog(domain_client)
    qtbot.addWidget(dialog)
    dialog._widgets["domain_name"].setText("mentoring")
    dialog._widgets["domain_purpose"].setText("p")
    dialog._widgets["domain_description"].setPlainText("d")
    dialog._on_save_clicked()
    qtbot.waitUntil(
        lambda: dialog._error_labels["domain_name"].text() != "", timeout=3000
    )
    assert dialog.result() != QDialog.DialogCode.Accepted


def test_edit_dialog_persists_status_change(qtbot, domain_client):
    _seed(domain_client, "Mentoring")
    record = domain_client.get_domain("DOM-001")
    dialog = DomainEditDialog(domain_client, record)
    qtbot.addWidget(dialog)
    assert dialog._widgets["domain_identifier"].isReadOnly()
    status = dialog._widgets["domain_status"]
    status.setCurrentIndex(status.findText("confirmed"))
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    assert domain_client.get_domain("DOM-001")["domain_status"] == "confirmed"


def test_delete_dialog_edge_text_then_soft_deletes(qtbot, domain_client):
    _seed(domain_client, "Mentoring")
    dialog = DomainDeleteDialog(domain_client, "DOM-001", "Mentoring")
    qtbot.addWidget(dialog)
    # Delete is disabled until the identifier is typed exactly.
    assert dialog._delete_btn.isEnabled() is False
    dialog._confirm_edit.setText("DOM-00")
    assert dialog._delete_btn.isEnabled() is False
    dialog._confirm_edit.setText("DOM-001")
    assert dialog._delete_btn.isEnabled() is True
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._delete_btn.click()
    assert domain_client.list_domains() == []
    assert len(domain_client.list_domains(include_deleted=True)) == 1


def test_panel_new_button_round_trip(qtbot, domain_client, monkeypatch):
    """The New Domain button opens the create dialog; on accept the
    panel selects the freshly created row."""
    panel = DomainsPanel(domain_client)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 0)

    class _StubCreate:
        def __init__(self, client, parent=None):
            client.create_domain(
                {
                    "domain_name": "Fundraising",
                    "domain_purpose": "p",
                    "domain_description": "d",
                }
            )

        def exec(self):  # noqa: A003 — Qt naming
            return QDialog.DialogCode.Accepted

        def created_identifier(self):
            return "DOM-001"

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.domains.DomainCreateDialog", _StubCreate
    )
    panel._new_button.click()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 1, timeout=3000)
    assert panel._model.record_at(0)["domain_name"] == "Fundraising"


# ---------------------------------------------------------------------------
# Criterion 13 — file-watch refresh
# ---------------------------------------------------------------------------


def test_domains_snapshot_filename_is_mapped():
    # Slice A registered the snapshot filename; slice B's panel consumes
    # the resulting ``data_changed`` events.
    assert _FILENAME_TO_ENTITY_TYPE["domains.json"] == "domain"
    assert ENTITY_TYPE_TO_SIDEBAR_LABEL["domain"] == "Domains"


def test_external_write_refreshes_current_domains_panel(
    qtbot, lifecycle_stub, domain_client, export_dir
):
    window = MainWindow(
        lifecycle=lifecycle_stub, client=domain_client, snapshot_dir=export_dir
    )
    qtbot.addWidget(window)
    window._sidebar.select_entry("Domains")
    panel = window._stack.widget(window._pages_by_entry["Domains"])
    _wait_rows(qtbot, panel, 0)

    # External REST write — the exporter rewrites domains.json.
    _seed(domain_client, "Mentoring")

    # The file-watch service routes a ``domain`` change to the current
    # panel's refresh; drive that slot directly (the QFileSystemWatcher
    # plumbing itself is covered by test_refresh).
    window._on_data_changed("domain")
    qtbot.waitUntil(lambda: panel._model.rowCount() == 1, timeout=3000)
    assert panel._model.record_at(0)["domain_name"] == "Mentoring"


# ---------------------------------------------------------------------------
# Criterion 14 — sample CBM-redo Phase 1 records persist across restart
# ---------------------------------------------------------------------------


def test_sample_cbm_redo_records_persist_across_restart(qtbot, domain_client):
    names = [
        "Mentoring",
        "Mentor Recruitment",
        "Client Recruiting",
        "Fundraising",
    ]
    for name in names:
        _seed(domain_client, name)
    for identifier in ("DOM-001", "DOM-002", "DOM-003", "DOM-004"):
        domain_client.patch_domain(identifier, {"domain_status": "confirmed"})

    # "Restart": a fresh client + app over the same on-disk database.
    restarted = StorageClient(
        base_url="http://testserver", client=TestClient(create_app())
    )
    panel = DomainsPanel(restarted)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 4)

    rows = [panel._model.record_at(r) for r in range(panel._model.rowCount())]
    assert {r["domain_name"] for r in rows} == set(names)
    assert all(r["domain_status"] == "confirmed" for r in rows)

"""Smoke tests for the UI scaffold.

Exercises the bare-minimum slice-A surface plus slice-B's main-window
constructor change (lifecycle now required, crash banner installed
hidden by default), plus slice-C's StorageClient threading and live
DecisionsPanel.
"""

from __future__ import annotations

from crmbuilder_v2.ui.main_window import MainWindow
from crmbuilder_v2.ui.panels.charter import CharterPanel
from crmbuilder_v2.ui.panels.decisions import DecisionsPanel
from crmbuilder_v2.ui.panels.planning_items import PlanningItemsPanel
from crmbuilder_v2.ui.panels.references import ReferencesPanel
from crmbuilder_v2.ui.panels.risks import RisksPanel
from crmbuilder_v2.ui.panels.sessions import SessionsPanel
from crmbuilder_v2.ui.panels.status import StatusPanel
from crmbuilder_v2.ui.panels.topics import TopicsPanel
from crmbuilder_v2.ui.sidebar import SIDEBAR_ENTRIES, Sidebar
from crmbuilder_v2.ui.splash import Splash

EXPECTED_ENTRIES = (
    "Charter",
    "Status",
    "Decisions",
    "Sessions",
    "Risks",
    "Planning Items",
    "Topics",
    "References",
    # Methodology group — Domains landed in UI v0.4 slice B,
    # Entities in slice C.
    "Domains",
    "Entities",
)


def test_sidebar_entries_constant():
    assert SIDEBAR_ENTRIES == EXPECTED_ENTRIES


def test_main_window_constructs(qapp, qtbot, lifecycle_stub, client_stub):
    window = MainWindow(lifecycle=lifecycle_stub, client=client_stub)
    qtbot.addWidget(window)

    sidebar = window._sidebar
    # The sidebar is grouped (UI v0.4 slice A): every selectable entry
    # plus a non-selectable header per group. The eight governance
    # entries all render; the "GOVERNANCE" and "METHODOLOGY" group
    # headers render too.
    rendered = [sidebar.item(r).text() for r in range(sidebar.count())]
    for expected in EXPECTED_ENTRIES:
        assert expected in rendered
    assert "GOVERNANCE" in rendered
    assert "METHODOLOGY" in rendered

    assert window._stack.count() == len(EXPECTED_ENTRIES)
    assert sidebar.currentItem().text() == "Decisions"


def test_main_window_crash_banner_hidden_by_default(
    qapp, qtbot, lifecycle_stub, client_stub
):
    window = MainWindow(lifecycle=lifecycle_stub, client=client_stub)
    qtbot.addWidget(window)

    assert window._crash_banner.isVisible() is False
    assert window._sidebar.isEnabled() is True
    assert window._stack.isEnabled() is True


def test_main_window_decisions_page_is_panel(
    qapp, qtbot, lifecycle_stub, client_stub
):
    window = MainWindow(lifecycle=lifecycle_stub, client=client_stub)
    qtbot.addWidget(window)

    decisions_index = window._pages_by_entry["Decisions"]
    page = window._stack.widget(decisions_index)
    assert isinstance(page, DecisionsPanel)


def test_main_window_sessions_page_is_panel(
    qapp, qtbot, lifecycle_stub, client_stub
):
    window = MainWindow(lifecycle=lifecycle_stub, client=client_stub)
    qtbot.addWidget(window)

    page = window._stack.widget(window._pages_by_entry["Sessions"])
    assert isinstance(page, SessionsPanel)


def test_main_window_risks_page_is_panel(
    qapp, qtbot, lifecycle_stub, client_stub
):
    window = MainWindow(lifecycle=lifecycle_stub, client=client_stub)
    qtbot.addWidget(window)

    page = window._stack.widget(window._pages_by_entry["Risks"])
    assert isinstance(page, RisksPanel)


def test_main_window_charter_page_is_panel(
    qapp, qtbot, lifecycle_stub, client_stub
):
    window = MainWindow(lifecycle=lifecycle_stub, client=client_stub)
    qtbot.addWidget(window)

    page = window._stack.widget(window._pages_by_entry["Charter"])
    assert isinstance(page, CharterPanel)


def test_main_window_status_page_is_panel(
    qapp, qtbot, lifecycle_stub, client_stub
):
    window = MainWindow(lifecycle=lifecycle_stub, client=client_stub)
    qtbot.addWidget(window)

    page = window._stack.widget(window._pages_by_entry["Status"])
    assert isinstance(page, StatusPanel)


def test_main_window_topics_page_is_panel(
    qapp, qtbot, lifecycle_stub, client_stub
):
    window = MainWindow(lifecycle=lifecycle_stub, client=client_stub)
    qtbot.addWidget(window)

    page = window._stack.widget(window._pages_by_entry["Topics"])
    assert isinstance(page, TopicsPanel)


def test_main_window_planning_items_page_is_panel(
    qapp, qtbot, lifecycle_stub, client_stub
):
    window = MainWindow(lifecycle=lifecycle_stub, client=client_stub)
    qtbot.addWidget(window)

    page = window._stack.widget(window._pages_by_entry["Planning Items"])
    assert isinstance(page, PlanningItemsPanel)


def test_main_window_references_page_is_panel(
    qapp, qtbot, lifecycle_stub, client_stub
):
    window = MainWindow(lifecycle=lifecycle_stub, client=client_stub)
    qtbot.addWidget(window)

    page = window._stack.widget(window._pages_by_entry["References"])
    assert isinstance(page, ReferencesPanel)


def test_sessions_panel_renders_references_section(qapp, qtbot, client_stub):
    """Slice E (v0.2): Sessions detail pane includes ReferencesSection."""
    from crmbuilder_v2.ui.widgets.references_section import ReferencesSection

    panel = SessionsPanel(client_stub)
    qtbot.addWidget(panel)
    record = {
        "identifier": "SES-001",
        "title": "Slice E v0.2 wiring",
        "session_date": "2026-05-09",
        "status": "complete",
        "topics_covered": "",
        "summary": "",
        "artifacts_produced": "",
        "in_flight_at_end": "",
        "conversation_reference": "",
    }
    rendered = panel.render_detail(record, {"references": {"as_source": [], "as_target": []}})
    assert rendered.findChildren(ReferencesSection)


def test_sidebar_set_stale_toggles_icon(qapp, qtbot):
    sidebar = Sidebar()
    qtbot.addWidget(sidebar)

    assert sidebar.is_stale("Decisions") is False
    sidebar.set_stale("Decisions", True)
    assert sidebar.is_stale("Decisions") is True
    sidebar.set_stale("Decisions", False)
    assert sidebar.is_stale("Decisions") is False


def test_sidebar_set_stale_unknown_label_is_noop(qapp, qtbot):
    sidebar = Sidebar()
    qtbot.addWidget(sidebar)

    # Should not raise.
    sidebar.set_stale("Nonexistent Entry", True)
    assert sidebar.is_stale("Nonexistent Entry") is False


def test_splash_constructs(qapp):
    splash = Splash()
    pixmap = splash.pixmap()
    assert not pixmap.isNull()
    assert pixmap.width() > 0
    assert pixmap.height() > 0

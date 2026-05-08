"""Smoke tests for the UI scaffold.

Exercises the bare-minimum slice-A surface plus slice-B's main-window
constructor change (lifecycle now required, crash banner installed
hidden by default), plus slice-C's StorageClient threading and live
DecisionsPanel.
"""

from __future__ import annotations

from crmbuilder_v2.ui.main_window import MainWindow
from crmbuilder_v2.ui.panels.decisions import DecisionsPanel
from crmbuilder_v2.ui.panels.risks import RisksPanel
from crmbuilder_v2.ui.panels.sessions import SessionsPanel
from crmbuilder_v2.ui.sidebar import SIDEBAR_ENTRIES
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
)


def test_sidebar_entries_constant():
    assert SIDEBAR_ENTRIES == EXPECTED_ENTRIES


def test_main_window_constructs(qapp, qtbot, lifecycle_stub, client_stub):
    window = MainWindow(lifecycle=lifecycle_stub, client=client_stub)
    qtbot.addWidget(window)

    sidebar = window._sidebar
    assert sidebar.count() == len(EXPECTED_ENTRIES)
    for row, expected in enumerate(EXPECTED_ENTRIES):
        assert sidebar.item(row).text() == expected

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


def test_splash_constructs(qapp):
    splash = Splash()
    pixmap = splash.pixmap()
    assert not pixmap.isNull()
    assert pixmap.width() > 0
    assert pixmap.height() > 0

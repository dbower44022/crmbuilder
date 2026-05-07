"""Smoke tests for the UI scaffold.

Exercises the bare-minimum slice-A surface: the main window can be
constructed, the sidebar has the eight expected entries, the content
stack has eight pages, and the splash renders without raising.
"""

from __future__ import annotations

from crmbuilder_v2.ui.main_window import MainWindow
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


def test_main_window_constructs(qapp, qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    sidebar = window._sidebar
    assert sidebar.count() == len(EXPECTED_ENTRIES)
    for row, expected in enumerate(EXPECTED_ENTRIES):
        assert sidebar.item(row).text() == expected

    assert window._stack.count() == len(EXPECTED_ENTRIES)
    assert sidebar.currentItem().text() == "Decisions"


def test_splash_constructs(qapp):
    splash = Splash()
    pixmap = splash.pixmap()
    assert not pixmap.isNull()
    assert pixmap.width() > 0
    assert pixmap.height() > 0

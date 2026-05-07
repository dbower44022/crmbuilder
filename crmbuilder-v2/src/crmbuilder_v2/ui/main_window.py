"""Main window — sidebar + stacked content area.

Per DEC-021 the main window structure is a sidebar (left, fixed-width)
plus a ``QStackedWidget`` (right, swapping per selection). In slice A
each stack page is a placeholder; later slices replace them with real
entity panels.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from crmbuilder_v2.ui.sidebar import SIDEBAR_ENTRIES, Sidebar

_DEFAULT_ENTRY = "Decisions"


class MainWindow(QMainWindow):
    """Top-level window containing the sidebar and the content stack."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CRMBuilder v2")
        self.resize(1200, 800)

        self._sidebar = Sidebar()
        self._stack = QStackedWidget()
        self._pages_by_entry: dict[str, int] = {}

        for entry in SIDEBAR_ENTRIES:
            placeholder = QLabel(
                f"Panel for {entry} — implemented in slice D or E."
            )
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setObjectName(f"placeholder_{entry.lower().replace(' ', '_')}")
            index = self._stack.addWidget(placeholder)
            self._pages_by_entry[entry] = index

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._sidebar)
        layout.addWidget(self._stack, stretch=1)
        self.setCentralWidget(container)

        self._sidebar.selection_changed.connect(self._on_sidebar_selected)

        self._build_menu_bar()

        default_row = list(SIDEBAR_ENTRIES).index(_DEFAULT_ENTRY)
        self._sidebar.setCurrentRow(default_row)

    def _on_sidebar_selected(self, entry: str) -> None:
        index = self._pages_by_entry.get(entry)
        if index is not None:
            self._stack.setCurrentIndex(index)

    def _build_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.setEnabled(False)
        help_menu.addAction(about_action)

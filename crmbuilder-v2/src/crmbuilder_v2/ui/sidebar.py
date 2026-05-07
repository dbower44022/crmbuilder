"""Left-hand navigation sidebar.

Per DEC-021, the UI uses a left-hand sidebar with one entry per entity
type. Selecting a sidebar entry swaps the right-hand content area to
that entity's panel.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QListWidget

SIDEBAR_ENTRIES: tuple[str, ...] = (
    "Charter",
    "Status",
    "Decisions",
    "Sessions",
    "Risks",
    "Planning Items",
    "Topics",
    "References",
)


class Sidebar(QListWidget):
    """Single-selection list of entity-type entries.

    Emits ``selection_changed(str)`` carrying the selected entry's text
    whenever the active row changes.
    """

    selection_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(200)
        self.addItems(SIDEBAR_ENTRIES)
        self.currentTextChanged.connect(self._on_current_text_changed)

    def _on_current_text_changed(self, text: str) -> None:
        if text:
            self.selection_changed.emit(text)

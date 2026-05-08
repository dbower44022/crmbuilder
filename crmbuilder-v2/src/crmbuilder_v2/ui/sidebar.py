"""Left-hand navigation sidebar.

Per DEC-021, the UI uses a left-hand sidebar with one entry per entity
type. Selecting a sidebar entry swaps the right-hand content area to
that entity's panel.

Slice F adds a staleness-indicator API: ``set_stale(label, bool)``
toggles a small navy-filled circle icon on a sidebar entry to signal
that its underlying data has changed in the storage system since the
user last viewed it.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
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

_STALE_DOT_SIZE = 8
_STALE_DOT_COLOR = "#1F3864"  # navy accent

_STALE_PIXMAP: QPixmap | None = None


def _stale_pixmap() -> QPixmap:
    """Return the shared stale-indicator pixmap (constructed lazily)."""
    global _STALE_PIXMAP
    if _STALE_PIXMAP is None:
        pixmap = QPixmap(_STALE_DOT_SIZE, _STALE_DOT_SIZE)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setBrush(QColor(_STALE_DOT_COLOR))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(0, 0, _STALE_DOT_SIZE, _STALE_DOT_SIZE)
        finally:
            painter.end()
        _STALE_PIXMAP = pixmap
    return _STALE_PIXMAP


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

    def current_text(self) -> str:
        """Return the text of the currently selected entry, or ``""``."""
        item = self.currentItem()
        return item.text() if item is not None else ""

    def set_stale(self, label: str, stale: bool) -> None:
        """Show or hide the staleness indicator for a sidebar entry.

        Unknown labels are silently ignored.
        """
        item = self._item_for_label(label)
        if item is None:
            return
        if stale:
            item.setIcon(QIcon(_stale_pixmap()))
        else:
            item.setIcon(QIcon())

    def is_stale(self, label: str) -> bool:
        """Whether the entry currently shows the staleness indicator."""
        item = self._item_for_label(label)
        if item is None:
            return False
        return not item.icon().isNull()

    def _item_for_label(self, label: str):
        for row in range(self.count()):
            item = self.item(row)
            if item is not None and item.text() == label:
                return item
        return None

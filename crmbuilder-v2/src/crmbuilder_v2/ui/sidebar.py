"""Left-hand navigation sidebar.

Per DEC-021, the UI uses a left-hand sidebar with one entry per entity
type. Selecting a sidebar entry swaps the right-hand content area to
that entity's panel.

Slice F adds a staleness-indicator API: ``set_stale(label, bool)``
toggles a small navy-filled circle icon on a sidebar entry to signal
that its underlying data has changed in the storage system since the
user last viewed it.

UI v0.4 slice A groups the sidebar into sections. ``SIDEBAR_GROUPS``
declares each section's title and ordered entries; a non-selectable
header item renders above each section. The "Governance" group holds
the eight v0.3 entity panels; the "Methodology" group is introduced
empty in slice A and is populated by slices B–E. ``SIDEBAR_ENTRIES``
remains the flat tuple of selectable entry labels in display order.

Slice B adds the first Methodology entry, "Domains", at position #1.
Slice C adds the second, "Entities", at position #2. Slice D adds the
third, "Processes", at position #3.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QListWidget, QListWidgetItem

# Ordered sidebar sections: (group title, ordered entry labels). The
# Methodology group gained "Domains" in v0.4 slice B, "Entities" in
# slice C, "Processes" in slice D, and "CRM Candidates" in slice E.
SIDEBAR_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Governance",
        (
            "Charter",
            "Status",
            "Decisions",
            "Sessions",
            "Risks",
            "Planning Items",
            "Topics",
            "References",
        ),
    ),
    (
        "Methodology",
        ("Domains", "Entities", "Processes", "CRM Candidates"),
    ),
)

# Flat tuple of selectable entry labels in display order, derived from
# SIDEBAR_GROUPS. Group headers are not entries.
SIDEBAR_ENTRIES: tuple[str, ...] = tuple(
    entry for _title, entries in SIDEBAR_GROUPS for entry in entries
)

# Item-data role marking a row as a non-selectable group header.
_HEADER_ROLE = Qt.ItemDataRole.UserRole + 1

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
    """Grouped single-selection list of entity-type entries.

    The list is divided into sections per :data:`SIDEBAR_GROUPS`. Each
    section is preceded by a non-selectable header item; only entry
    rows can be selected.

    Emits ``selection_changed(str)`` carrying the selected entry's text
    whenever the active row changes.
    """

    selection_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(200)
        self._build_items()
        self.currentTextChanged.connect(self._on_current_text_changed)

    def _build_items(self) -> None:
        """Populate the list with group headers and entry rows."""
        for title, entries in SIDEBAR_GROUPS:
            header = QListWidgetItem(title.upper())
            header.setData(_HEADER_ROLE, True)
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            font = QFont(self.font())
            font.setBold(True)
            header.setFont(font)
            self.addItem(header)
            for entry in entries:
                self.addItem(QListWidgetItem(entry))

    def _on_current_text_changed(self, text: str) -> None:
        if text and not self._is_header_text(text):
            self.selection_changed.emit(text)

    def _is_header_text(self, text: str) -> bool:
        item = self._item_for_label(text)
        return item is not None and bool(item.data(_HEADER_ROLE))

    def current_text(self) -> str:
        """Return the text of the currently selected entry, or ``""``."""
        item = self.currentItem()
        return item.text() if item is not None else ""

    def select_entry(self, label: str) -> None:
        """Select the entry row whose text matches ``label``.

        Unknown labels and header labels are silently ignored. Used in
        place of ``setCurrentRow`` by callers that address entries by
        label, since group headers offset the flat row index.
        """
        item = self._item_for_label(label)
        if item is None or item.data(_HEADER_ROLE):
            return
        self.setCurrentItem(item)

    def set_stale(self, label: str, stale: bool) -> None:
        """Show or hide the staleness indicator for a sidebar entry.

        Unknown labels and header labels are silently ignored.
        """
        item = self._item_for_label(label)
        if item is None or item.data(_HEADER_ROLE):
            return
        if stale:
            item.setIcon(QIcon(_stale_pixmap()))
        else:
            item.setIcon(QIcon())

    def is_stale(self, label: str) -> bool:
        """Whether the entry currently shows the staleness indicator."""
        item = self._item_for_label(label)
        if item is None or item.data(_HEADER_ROLE):
            return False
        return not item.icon().isNull()

    def _item_for_label(self, label: str):
        for row in range(self.count()):
            item = self.item(row)
            if item is not None and item.text() == label:
                return item
        return None

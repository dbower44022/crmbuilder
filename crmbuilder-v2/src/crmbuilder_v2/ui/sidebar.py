"""Left-hand navigation sidebar.

Per DEC-021, the UI uses a left-hand sidebar with one entry per entity
type. Selecting a sidebar entry swaps the right-hand content area to
that entity's panel.

Slice F adds a staleness-indicator API: ``set_stale(label, bool)``
toggles a small accent-filled circle icon on a sidebar entry to signal
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

UI v0.5 slice A adds an empty "Engagements" group above Governance.
The single entry is populated by v0.5 slice C.

UI v0.6 slice B applies design pass §2.1 + DEC-093: 220px container
with neutral.100 background and a right-edge hairline, group headers
in semibold caption-size sentence-case (not uppercased) with
letter-spacing, 32px entries, and the selected-state vocabulary —
3px left accent bar + accent.subtle background + neutral.900
medium-weight text — drawn by ``SidebarItemDelegate``. The stale dot
recolored from the legacy navy to ``color.accent.default``.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from crmbuilder_v2.ui.styling import t

# Ordered sidebar sections: (group title, ordered entry labels). The
# Methodology group gained "Domains" in v0.4 slice B, "Entities" in
# slice C, "Processes" in slice D, and "CRM Candidates" in slice E.
SIDEBAR_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    # v0.5 slice A: empty Engagements group container above Governance.
    # Slice C populates with the single "Engagements" entry.
    ("Engagements", ("Engagements",)),
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

_STALE_PIXMAP: QPixmap | None = None

# Geometry tokens resolved from the design system.
_SIDEBAR_WIDTH = 220
_ENTRY_HEIGHT = 32
_ACCENT_BAR_WIDTH = 3


def _px(token_key: str) -> int:
    """Resolve a spacing/size token to an int pixel value."""
    raw = t(token_key)
    if raw.endswith("px"):
        raw = raw[:-2]
    return int(raw)


def _stale_pixmap() -> QPixmap:
    """Return the shared stale-indicator pixmap (constructed lazily)."""
    global _STALE_PIXMAP
    if _STALE_PIXMAP is None:
        pixmap = QPixmap(_STALE_DOT_SIZE, _STALE_DOT_SIZE)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setBrush(QColor(t("color.accent.default")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(0, 0, _STALE_DOT_SIZE, _STALE_DOT_SIZE)
        finally:
            painter.end()
        _STALE_PIXMAP = pixmap
    return _STALE_PIXMAP


class SidebarItemDelegate(QStyledItemDelegate):
    """Per-DEC-093 selected-state custom rendering for sidebar entries.

    Group headers (non-selectable; ``_HEADER_ROLE == True``) fall
    through to the default paint so their per-item font / foreground
    color render through Qt's standard pipeline. Entries render the
    3px left accent bar + ``color.accent.subtle`` background +
    ``color.neutral.900`` medium-weight text on selection.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._accent_default = QColor(t("color.accent.default"))
        self._accent_subtle = QColor(t("color.accent.subtle"))
        self._neutral_200 = QColor(t("color.neutral.200"))
        self._neutral_800 = QColor(t("color.neutral.800"))
        self._neutral_900 = QColor(t("color.neutral.900"))

    def paint(self, painter, option, index):  # noqa: D401
        is_header = bool(index.data(_HEADER_ROLE))
        if is_header:
            super().paint(painter, option, index)
            return

        state = option.state
        is_selected = bool(state & QStyle.StateFlag.State_Selected)
        is_hover = bool(state & QStyle.StateFlag.State_MouseOver)

        # Background fills.
        rect = option.rect
        painter.save()
        try:
            if is_selected:
                painter.fillRect(rect, self._accent_subtle)
                bar = rect.adjusted(0, 0, -(rect.width() - _ACCENT_BAR_WIDTH), 0)
                painter.fillRect(bar, self._accent_default)
            elif is_hover:
                painter.fillRect(rect, self._neutral_200)

            # Strip Qt's default selection highlight so it doesn't
            # repaint over our custom fill.
            opt = QStyleOptionViewItem(option)
            opt.state &= ~QStyle.StateFlag.State_Selected
            opt.state &= ~QStyle.StateFlag.State_HasFocus
            opt.state &= ~QStyle.StateFlag.State_MouseOver

            # Text + icon recolor for selected state.
            if is_selected:
                opt.palette.setColor(opt.palette.ColorRole.Text, self._neutral_900)
                opt.palette.setColor(opt.palette.ColorRole.WindowText, self._neutral_900)
                font = QFont(opt.font)
                font.setWeight(QFont.Weight.Medium)
                opt.font = font
            else:
                opt.palette.setColor(opt.palette.ColorRole.Text, self._neutral_800)
                opt.palette.setColor(opt.palette.ColorRole.WindowText, self._neutral_800)

            super().paint(painter, opt, index)
        finally:
            painter.restore()

    def sizeHint(self, option, index):  # noqa: N802 — Qt naming
        if bool(index.data(_HEADER_ROLE)):
            return super().sizeHint(option, index)
        return QSize(option.rect.width(), _ENTRY_HEIGHT)


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
        self.setFixedWidth(_SIDEBAR_WIDTH)
        self.setObjectName("sidebar")
        # Container chrome per design pass §2.1: neutral.100 background,
        # right-edge hairline, top/bottom padding via QSS so the first
        # group header doesn't sit flush against the top edge.
        self.setStyleSheet(
            f"#sidebar {{"
            f"  background: {t('color.neutral.100')};"
            f"  border: none;"
            f"  border-right: 1px solid {t('color.neutral.200')};"
            f"  padding-top: {t('space.4')};"
            f"  padding-bottom: {t('space.4')};"
            f"}}"
        )
        self.setItemDelegate(SidebarItemDelegate(self))
        self._build_items()
        self.currentTextChanged.connect(self._on_current_text_changed)

    def _build_items(self) -> None:
        """Populate the list with group headers and entry rows."""
        for group_index, (title, entries) in enumerate(SIDEBAR_GROUPS):
            header = QListWidgetItem(title)
            header.setData(_HEADER_ROLE, True)
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            header_font = QFont(self.font())
            header_font.setFamily(t("font.family.default"))
            header_font.setPixelSize(_px("font.size.caption"))
            header_font.setWeight(QFont.Weight.DemiBold)
            header_font.setLetterSpacing(
                QFont.SpacingType.PercentageSpacing, 104.0
            )
            header.setFont(header_font)
            header.setForeground(QColor(t("color.neutral.500")))
            # Top padding for headers beyond the first.
            if group_index > 0:
                header.setSizeHint(
                    QSize(0, _px("space.4") + _px("font.size.body"))
                )
            self.addItem(header)
            for entry in entries:
                item = QListWidgetItem(entry)
                entry_font = QFont(self.font())
                entry_font.setFamily(t("font.family.default"))
                entry_font.setPixelSize(_px("font.size.body"))
                item.setFont(entry_font)
                self.addItem(item)

    def _on_current_text_changed(self, text: str) -> None:
        # The current item is what dispatches the signal. Header items
        # are flag-marked non-selectable, so currentItem() is always an
        # entry when this fires from a user interaction — but check the
        # role anyway in case programmatic selection somehow lands on
        # a header.
        current = self.currentItem()
        if (
            text
            and current is not None
            and not current.data(_HEADER_ROLE)
        ):
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

        Unknown labels are silently ignored. Used in place of
        ``setCurrentRow`` by callers that address entries by label,
        since group headers offset the flat row index. Header items
        sharing a label with an entry (e.g., the "Engagements" group
        header and the "Engagements" entry) are skipped explicitly.
        """
        item = self._entry_for_label(label)
        if item is None:
            return
        self.setCurrentItem(item)

    def set_stale(self, label: str, stale: bool) -> None:
        """Show or hide the staleness indicator for a sidebar entry.

        Unknown labels are silently ignored.
        """
        item = self._entry_for_label(label)
        if item is None:
            return
        if stale:
            item.setIcon(QIcon(_stale_pixmap()))
        else:
            item.setIcon(QIcon())

    def is_stale(self, label: str) -> bool:
        """Whether the entry currently shows the staleness indicator."""
        item = self._entry_for_label(label)
        if item is None:
            return False
        return not item.icon().isNull()

    def _entry_for_label(self, label: str):
        """Return the selectable entry with this label, ignoring headers.

        v0.6 slice B retired uppercased header text, so an entry can
        share a label with its containing group header (e.g.,
        "Engagements"). Header items always have the ``_HEADER_ROLE``
        flag set; this lookup filters them out so callers addressing
        entries by label aren't confused by a same-named header.
        """
        for row in range(self.count()):
            item = self.item(row)
            if (
                item is not None
                and item.text() == label
                and not item.data(_HEADER_ROLE)
            ):
                return item
        return None

    def _item_for_label(self, label: str):
        """Return the first item (header or entry) with this label.

        Preserved for internal callers that don't need to distinguish
        headers from entries (e.g., the ``_is_header_text`` lookup in
        the selection-change slot).
        """
        for row in range(self.count()):
            item = self.item(row)
            if item is not None and item.text() == label:
                return item
        return None

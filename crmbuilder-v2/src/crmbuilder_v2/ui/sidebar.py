"""Left-hand navigation sidebar.

Per DEC-021, the content area swaps to the panel of the selected sidebar
entry. REQ-526 / PI-432 (DEC-953) made the sidebar **phase-scoped**: each
phase tab owns one ``Sidebar`` built from three groups — the fixed
"Every session" group, the phase's numbered *step checklist*, and a
collapsed alphabetical "All panels" index. Groups are passed in at
construction (see :mod:`crmbuilder_v2.ui.navigation`); the module-level
``SIDEBAR_GROUPS`` is the fallback a bare ``Sidebar()`` renders — the
alphabetical index alone — and ``SIDEBAR_ENTRIES`` is the flat tuple of
every registered panel label, the smoke-test constant.

Step entries carry a number in a left gutter and an advisory marker:
``done`` (✓) when the step's panel has records, ``next`` (▶) for the first
step that has none. Markers never lock anything (PRF-006).

Design pass §2.1 / DEC-093 chrome: 220px container with neutral.100
background and a right-edge hairline, semibold caption-size sentence-case
group headers, 32px entries, and the selected-state vocabulary — 3px left
accent bar + accent.subtle background + neutral.900 medium-weight text —
drawn by ``SidebarItemDelegate``. REQ-136 (PI-177): a filter box above the
list narrows entries; headers click to collapse their group.
"""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from crmbuilder_v2.ui.panel_registry import ALL_PANEL_LABELS
from crmbuilder_v2.ui.styling import t

Groups = tuple[tuple[str, tuple[str, ...]], ...]

# Fallback grouping for a bare ``Sidebar()``: the alphabetical index of every
# registered panel. Phase tabs pass their own groups.
SIDEBAR_GROUPS: Groups = (("All panels", ALL_PANEL_LABELS),)

# Flat tuple of every selectable panel label (alphabetical). Group headers are
# not entries. This is the "one page per label" smoke constant.
SIDEBAR_ENTRIES: tuple[str, ...] = ALL_PANEL_LABELS

# Item-data roles.
_HEADER_ROLE = Qt.ItemDataRole.UserRole + 1  # bool: non-selectable group header
_STEP_ROLE = Qt.ItemDataRole.UserRole + 2  # int: 1-based step number, or None
_MARKER_ROLE = Qt.ItemDataRole.UserRole + 3  # "done" | "next" | None

_STALE_DOT_SIZE = 8
_STALE_PIXMAP: QPixmap | None = None

# Geometry tokens resolved from the design system.
_SIDEBAR_WIDTH = 220
_ENTRY_HEIGHT = 32
_ACCENT_BAR_WIDTH = 3
_STEP_GUTTER = 26


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
    """DEC-093 selected-state rendering plus the step gutter.

    Group headers (``_HEADER_ROLE``) fall through to the default paint.
    Entries render the 3px accent bar + accent.subtle background +
    neutral.900 medium text on selection. Step entries additionally draw
    their number — or ✓ / ▶ per the marker role — in a left gutter.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._accent_default = QColor(t("color.accent.default"))
        self._accent_subtle = QColor(t("color.accent.subtle"))
        self._neutral_200 = QColor(t("color.neutral.200"))
        self._neutral_500 = QColor(t("color.neutral.500"))
        self._neutral_800 = QColor(t("color.neutral.800"))
        self._neutral_900 = QColor(t("color.neutral.900"))
        self._success = QColor(t("color.success.default"))
        self._warning = QColor(t("color.warning.default"))

    def paint(self, painter, option, index):  # noqa: D401
        if bool(index.data(_HEADER_ROLE)):
            super().paint(painter, option, index)
            return

        state = option.state
        is_selected = bool(state & QStyle.StateFlag.State_Selected)
        is_hover = bool(state & QStyle.StateFlag.State_MouseOver)
        step = index.data(_STEP_ROLE)
        marker = index.data(_MARKER_ROLE)

        rect = option.rect
        painter.save()
        try:
            if is_selected:
                painter.fillRect(rect, self._accent_subtle)
                bar = rect.adjusted(0, 0, -(rect.width() - _ACCENT_BAR_WIDTH), 0)
                painter.fillRect(bar, self._accent_default)
            elif is_hover:
                painter.fillRect(rect, self._neutral_200)

            opt = QStyleOptionViewItem(option)
            opt.state &= ~QStyle.StateFlag.State_Selected
            opt.state &= ~QStyle.StateFlag.State_HasFocus
            opt.state &= ~QStyle.StateFlag.State_MouseOver

            if is_selected or marker == "next":
                opt.palette.setColor(opt.palette.ColorRole.Text, self._neutral_900)
                opt.palette.setColor(opt.palette.ColorRole.WindowText, self._neutral_900)
                font = QFont(opt.font)
                font.setWeight(QFont.Weight.Medium)
                opt.font = font
            else:
                opt.palette.setColor(opt.palette.ColorRole.Text, self._neutral_800)
                opt.palette.setColor(opt.palette.ColorRole.WindowText, self._neutral_800)

            if step is not None:
                gutter = QRect(rect.left() + _ACCENT_BAR_WIDTH, rect.top(), _STEP_GUTTER, rect.height())
                if marker == "done":
                    glyph, color = "✓", self._success
                elif marker == "next":
                    glyph, color = "▶", self._warning
                else:
                    glyph, color = str(step), self._neutral_500
                gutter_font = QFont(opt.font)
                gutter_font.setPixelSize(max(_px("font.size.caption"), 10))
                painter.setFont(gutter_font)
                painter.setPen(color)
                painter.drawText(gutter, Qt.AlignmentFlag.AlignCenter, glyph)
                opt.rect = rect.adjusted(_STEP_GUTTER, 0, 0, 0)

            super().paint(painter, opt, index)
        finally:
            painter.restore()

    def sizeHint(self, option, index):  # noqa: N802 — Qt naming
        if bool(index.data(_HEADER_ROLE)):
            return super().sizeHint(option, index)
        return QSize(option.rect.width(), _ENTRY_HEIGHT)


class Sidebar(QListWidget):
    """Grouped single-selection list of panel entries.

    :param groups: ``((title, (label, …)), …)`` in display order. Defaults to
        :data:`SIDEBAR_GROUPS` (the alphabetical index).
    :param numbered_groups: titles of groups whose entries are numbered steps.
    :param collapsed_groups: titles of groups that start collapsed.

    Emits ``selection_changed(str)`` with the selected entry's label.
    """

    selection_changed = Signal(str)

    def __init__(
        self,
        groups: Groups | None = None,
        parent=None,
        *,
        numbered_groups: Iterable[str] = (),
        collapsed_groups: Iterable[str] = (),
    ):
        super().__init__(parent)
        self.setFixedWidth(_SIDEBAR_WIDTH)
        self.setObjectName("sidebar")
        self.setStyleSheet(
            f"#sidebar {{"
            f"  background: {t('color.neutral.100')};"
            f"  border: none;"
            f"  border-right: 1px solid {t('color.neutral.200')};"
            f"  padding-top: {t('space.4')};"
            f"  padding-bottom: {t('space.4')};"
            f"}}"
        )
        self._groups: Groups = tuple(groups) if groups is not None else SIDEBAR_GROUPS
        self._numbered_groups = set(numbered_groups)
        self._filter_text: str = ""
        self._collapsed_groups: set[str] = set(collapsed_groups)
        self.setItemDelegate(SidebarItemDelegate(self))
        self._build_items()
        self._apply_visibility()
        self.currentTextChanged.connect(self._on_current_text_changed)
        self.itemClicked.connect(self._on_item_clicked)

    @property
    def groups(self) -> Groups:
        return self._groups

    def _build_items(self) -> None:
        """Populate the list with group headers and entry rows."""
        for group_index, (title, entries) in enumerate(self._groups):
            header = QListWidgetItem(title)
            header.setData(_HEADER_ROLE, True)
            header.setFlags(Qt.ItemFlag.ItemIsEnabled)
            header_font = QFont(self.font())
            header_font.setFamily(t("font.family.default"))
            header_font.setPixelSize(_px("font.size.caption"))
            header_font.setWeight(QFont.Weight.DemiBold)
            header_font.setLetterSpacing(
                QFont.SpacingType.PercentageSpacing, 104.0
            )
            header.setFont(header_font)
            header.setForeground(QColor(t("color.neutral.500")))
            if group_index > 0:
                header.setSizeHint(
                    QSize(0, _px("space.4") + _px("font.size.body"))
                )
            self.addItem(header)
            numbered = title in self._numbered_groups
            for position, entry in enumerate(entries, start=1):
                item = QListWidgetItem(entry)
                entry_font = QFont(self.font())
                entry_font.setFamily(t("font.family.default"))
                entry_font.setPixelSize(_px("font.size.body"))
                item.setFont(entry_font)
                if numbered:
                    item.setData(_STEP_ROLE, position)
                self.addItem(item)

    def _on_current_text_changed(self, text: str) -> None:
        current = self.currentItem()
        if text and current is not None and not current.data(_HEADER_ROLE):
            self.selection_changed.emit(text)

    # ------------------------------------------------------------------
    # Step markers (REQ-526 / PI-432)
    # ------------------------------------------------------------------

    def step_labels(self) -> tuple[str, ...]:
        """The numbered step entries, in order."""
        return tuple(
            self.item(r).text()
            for r in range(self.count())
            if self.item(r).data(_STEP_ROLE) is not None
        )

    def set_step_marker(self, label: str, marker: str | None) -> None:
        """Set a step entry's advisory marker: ``"done"``, ``"next"`` or ``None``."""
        for row in range(self.count()):
            item = self.item(row)
            if item.text() == label and item.data(_STEP_ROLE) is not None:
                item.setData(_MARKER_ROLE, marker)
                return

    def step_marker(self, label: str) -> str | None:
        for row in range(self.count()):
            item = self.item(row)
            if item.text() == label and item.data(_STEP_ROLE) is not None:
                return item.data(_MARKER_ROLE)
        return None

    # ------------------------------------------------------------------
    # Filter + collapse (REQ-136 / PI-177)
    # ------------------------------------------------------------------

    def _iter_groups(self) -> list[tuple[QListWidgetItem, list[QListWidgetItem]]]:
        groups: list[tuple[QListWidgetItem, list[QListWidgetItem]]] = []
        current_header: QListWidgetItem | None = None
        current_entries: list[QListWidgetItem] = []
        for row in range(self.count()):
            item = self.item(row)
            if item is None:
                continue
            if item.data(_HEADER_ROLE):
                if current_header is not None:
                    groups.append((current_header, current_entries))
                current_header = item
                current_entries = []
            else:
                current_entries.append(item)
        if current_header is not None:
            groups.append((current_header, current_entries))
        return groups

    def filter_entries(self, text: str) -> None:
        """Narrow the sidebar to entries matching ``text`` (case-insensitive).

        An active query overrides collapse state so every match shows; a
        header hides when none of its entries match.
        """
        self._filter_text = text or ""
        self._apply_visibility()

    def set_group_collapsed(self, title: str, collapsed: bool) -> None:
        if collapsed:
            self._collapsed_groups.add(title)
        else:
            self._collapsed_groups.discard(title)
        self._apply_visibility()

    def is_group_collapsed(self, title: str) -> bool:
        return title in self._collapsed_groups

    def _apply_visibility(self) -> None:
        query = self._filter_text.strip().lower()
        for header_item, entries in self._iter_groups():
            title = self._header_text(header_item.text(), False)
            collapsed = title in self._collapsed_groups
            any_visible = False
            for entry in entries:
                if query:
                    visible = query in entry.text().lower()
                else:
                    visible = not collapsed
                entry.setHidden(not visible)
                any_visible = any_visible or visible
            header_item.setHidden(bool(query) and not any_visible)
            if not query:
                header_item.setText(self._header_text(title, collapsed))

    @staticmethod
    def _header_text(text: str, collapsed: bool) -> str:
        base = text.rstrip(" ▸▾").rstrip()
        return f"{base} ▸" if collapsed else base

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        if item is None or not item.data(_HEADER_ROLE):
            return
        title = self._header_text(item.text(), False)
        self.set_group_collapsed(title, title not in self._collapsed_groups)

    def current_text(self) -> str:
        """Return the text of the currently selected entry, or ``""``."""
        item = self.currentItem()
        return item.text() if item is not None else ""

    def select_entry(self, label: str) -> None:
        """Select the entry row whose text matches ``label`` (headers skipped).

        A label present in two groups (a step that is also in the All-panels
        index) selects the first — the step row — and expands its group if
        it is collapsed so the selection is visible.
        """
        item = self._entry_for_label(label)
        if item is None:
            return
        if item.isHidden() and not self._filter_text.strip():
            for header_item, entries in self._iter_groups():
                if item in entries:
                    self.set_group_collapsed(
                        self._header_text(header_item.text(), False), False
                    )
                    break
        self.setCurrentItem(item)

    def set_stale(self, label: str, stale: bool) -> None:
        """Show or hide the staleness indicator on every row for ``label``."""
        for item in self._entries_for_label(label):
            item.setIcon(QIcon(_stale_pixmap()) if stale else QIcon())

    def is_stale(self, label: str) -> bool:
        item = self._entry_for_label(label)
        return item is not None and not item.icon().isNull()

    def _entries_for_label(self, label: str) -> list[QListWidgetItem]:
        return [
            self.item(r)
            for r in range(self.count())
            if self.item(r) is not None
            and self.item(r).text() == label
            and not self.item(r).data(_HEADER_ROLE)
        ]

    def _entry_for_label(self, label: str):
        """Return the first selectable entry with this label, ignoring headers."""
        entries = self._entries_for_label(label)
        return entries[0] if entries else None

    def _item_for_label(self, label: str):
        for row in range(self.count()):
            item = self.item(row)
            if item is not None and item.text() == label:
                return item
        return None

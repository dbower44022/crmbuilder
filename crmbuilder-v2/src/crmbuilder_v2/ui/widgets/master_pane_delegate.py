"""Shared ``QStyledItemDelegate`` for master-pane row rendering per DEC-093.

Used by every panel's master view via centralized registration in
``ListDetailPanel.__init__()``. The Topics panel overrides to the
``MasterPaneTreeDelegate`` subclass which adds Lucide chevron branch
indicators and indentation-aware accent-bar placement.

The delegate handles:

* 28px row height (design pass §1.1 density).
* Hover, selected, and focused state visuals per DEC-093: 3px left
  accent bar in ``color.accent.default`` + ``color.accent.subtle``
  background + ``color.neutral.900`` medium-weight text on selection;
  ``color.neutral.100`` background on hover; 1px focus ring on
  keyboard focus.
* Row dividers as 1px hairlines in ``color.neutral.200`` along the
  bottom of each row.
* Identifier-column mono-font rendering (``JetBrains Mono`` at
  ``font.size.small``).
* Soft-deleted-row treatment when the host panel exposes a
  ``is_soft_deleted`` callable: ``color.neutral.500`` text plus a
  leading Lucide ``trash-2`` icon in the identifier column.

The delegate is decoupled from any specific model — the host panel
passes callables that resolve a model index to (a) the record dict
and (b) the soft-deleted bool. Default callables produce "no record /
not soft-deleted" so the delegate is safe to instantiate with no
panel-side hooks.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QModelIndex, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPen
from PySide6.QtWidgets import (
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from crmbuilder_v2.ui.icons import lucide
from crmbuilder_v2.ui.styling import t

_ROW_HEIGHT = 28
_ACCENT_BAR_WIDTH = 3
_DIVIDER_THICKNESS = 1
_TRASH_ICON_SIZE = 14
_TRASH_ICON_TOKEN = "color.neutral.500"
_CHEVRON_ICON_SIZE = 12
_CHEVRON_ICON_TOKEN = "color.neutral.500"
_TREE_INDENTATION = 16


def _px(token_key: str) -> int:
    raw = t(token_key)
    if raw.endswith("px"):
        raw = raw[:-2]
    return int(raw)


def _identity_record(_index: QModelIndex) -> dict | None:
    return None


def _never_soft_deleted(_index: QModelIndex) -> bool:
    return False


class MasterPaneDelegate(QStyledItemDelegate):
    """Standard master-pane delegate; ``QTableView`` / ``QListView`` ready."""

    def __init__(
        self,
        parent=None,
        *,
        record_for_index: Callable[[QModelIndex], dict | None] | None = None,
        is_soft_deleted: Callable[[QModelIndex], bool] | None = None,
        identifier_column_index: int | None = None,
    ) -> None:
        super().__init__(parent)
        self._record_for_index = record_for_index or _identity_record
        self._is_soft_deleted = is_soft_deleted or _never_soft_deleted
        self._identifier_column_index = identifier_column_index
        self._accent_default = QColor(t("color.accent.default"))
        self._accent_subtle = QColor(t("color.accent.subtle"))
        self._neutral_100 = QColor(t("color.neutral.100"))
        self._neutral_200 = QColor(t("color.neutral.200"))
        self._neutral_500 = QColor(t("color.neutral.500"))
        self._neutral_800 = QColor(t("color.neutral.800"))
        self._neutral_900 = QColor(t("color.neutral.900"))
        # Resolve the focus-ring color: token value is an "rgba(...)"
        # string; QColor parses it directly.
        self._focus_ring = QColor.fromString(t("color.accent.focusring"))
        self._mono_family = t("font.family.mono")
        self._mono_pixel = _px("font.size.small")

    # ------------------------------------------------------------------
    # Public sizing
    # ------------------------------------------------------------------

    def sizeHint(self, option, index):  # noqa: N802 — Qt naming
        return QSize(option.rect.width(), _ROW_HEIGHT)

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paint(self, painter, option, index):  # noqa: D401
        state = option.state
        is_selected = bool(state & QStyle.StateFlag.State_Selected)
        is_hover = bool(state & QStyle.StateFlag.State_MouseOver)
        is_focused = bool(state & QStyle.StateFlag.State_HasFocus)

        rect = option.rect
        painter.save()
        try:
            # Background fill.
            if is_selected:
                painter.fillRect(rect, self._accent_subtle)
            elif is_hover:
                painter.fillRect(rect, self._neutral_100)

            # 3px left accent bar — drawn only on the first column so
            # multi-column rows render one bar at the row's left edge.
            if is_selected and index.column() == 0:
                bar = QRect(rect.left(), rect.top(), _ACCENT_BAR_WIDTH, rect.height())
                painter.fillRect(bar, self._accent_default)

            # Row divider hairline along the bottom edge.
            painter.setPen(QPen(self._neutral_200, _DIVIDER_THICKNESS))
            painter.drawLine(
                rect.left(), rect.bottom(), rect.right(), rect.bottom()
            )

            # Soft-deleted handling: identifier column gets a leading
            # trash icon; row text recolored neutral.500.
            is_soft = self._is_soft_deleted(index)

            # Build a paint-time copy of option with our token colors
            # and (where applicable) the mono font.
            opt = QStyleOptionViewItem(option)
            opt.state &= ~QStyle.StateFlag.State_Selected
            opt.state &= ~QStyle.StateFlag.State_HasFocus
            opt.state &= ~QStyle.StateFlag.State_MouseOver

            if is_soft:
                text_color = self._neutral_500
            elif is_selected:
                text_color = self._neutral_900
            else:
                text_color = self._neutral_800
            opt.palette.setColor(opt.palette.ColorRole.Text, text_color)
            opt.palette.setColor(
                opt.palette.ColorRole.HighlightedText, text_color
            )

            if (
                self._identifier_column_index is not None
                and index.column() == self._identifier_column_index
            ):
                mono = QFont(self._mono_family)
                mono.setPixelSize(self._mono_pixel)
                if is_selected:
                    mono.setWeight(QFont.Weight.Medium)
                opt.font = mono
                if is_soft:
                    # Reserve horizontal space for the trash icon at the
                    # leading edge of the cell.
                    icon_padding = _TRASH_ICON_SIZE + _px("space.1")
                    opt.rect = QRect(
                        rect.left() + _ACCENT_BAR_WIDTH + icon_padding,
                        rect.top(),
                        rect.width() - _ACCENT_BAR_WIDTH - icon_padding,
                        rect.height(),
                    )
                    icon = lucide(
                        "trash-2",
                        size=_TRASH_ICON_SIZE,
                        color_token=_TRASH_ICON_TOKEN,
                    )
                    icon_top = rect.top() + (rect.height() - _TRASH_ICON_SIZE) // 2
                    icon.paint(
                        painter,
                        QRect(
                            rect.left() + _ACCENT_BAR_WIDTH + _px("space.1") // 2,
                            icon_top,
                            _TRASH_ICON_SIZE,
                            _TRASH_ICON_SIZE,
                        ),
                    )
                elif is_selected:
                    opt.rect = QRect(
                        rect.left() + _ACCENT_BAR_WIDTH,
                        rect.top(),
                        rect.width() - _ACCENT_BAR_WIDTH,
                        rect.height(),
                    )
            else:
                if is_selected:
                    font = QFont(opt.font)
                    font.setWeight(QFont.Weight.Medium)
                    opt.font = font

            super().paint(painter, opt, index)

            # Focus ring (last so it sits above everything).
            if is_focused and is_selected:
                ring = rect.adjusted(0, 0, -1, -1)
                painter.setPen(QPen(self._focus_ring, 1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(ring)
        finally:
            painter.restore()


class MasterPaneTreeDelegate(MasterPaneDelegate):
    """Tree-view variant: Lucide chevrons + 16px indentation per design pass §2.3.

    The branch indicator rendering is owned by ``QTreeView`` via
    ``drawBranches``, not the item delegate, so the tree-view itself
    must opt in to chevron painting. This delegate exposes
    :meth:`paint_branch` for the panel's QTreeView subclass to call
    from ``drawBranches``. The selected-state accent bar inherited
    from the parent ``paint`` already starts at ``option.rect.left()``,
    which Qt offsets past the indentation gutter; no further adjustment
    needed for the bar itself.
    """

    @staticmethod
    def indentation_per_level() -> int:
        """Pixel indent used by the tree view per design pass §2.3."""
        return _TREE_INDENTATION

    @staticmethod
    def paint_branch(painter, rect, *, expanded: bool) -> None:
        """Paint a chevron-{right|down} into ``rect`` centered vertically.

        Called from a ``QTreeView`` subclass's ``drawBranches`` override;
        ``rect`` is the branch indicator's rectangle as supplied by Qt.
        """
        icon_name = "chevron-down" if expanded else "chevron-right"
        icon = lucide(
            icon_name,
            size=_CHEVRON_ICON_SIZE,
            color_token=_CHEVRON_ICON_TOKEN,
        )
        icon_top = rect.top() + (rect.height() - _CHEVRON_ICON_SIZE) // 2
        icon_left = rect.left() + (rect.width() - _CHEVRON_ICON_SIZE) // 2
        icon.paint(
            painter,
            QRect(icon_left, icon_top, _CHEVRON_ICON_SIZE, _CHEVRON_ICON_SIZE),
        )

"""Shared grid/table enhancement utilities.

Provides consistent behavior across all QTableWidget, QListWidget, and
QTreeWidget/QTreeView instances in the application:

- **Alternating row colors** for readability
- **Column resizing** via Interactive header mode
- **Right-click context menus** with per-widget action builders
- **Automatic tooltips** for cells whose text is truncated
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QModelIndex, QObject, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QListWidget,
    QMenu,
    QStyledItemDelegate,
    QTableWidget,
    QToolTip,
    QTreeView,
    QTreeWidget,
)

# Context menu item: (label, callback) or None for a separator.
ContextMenuItem = tuple[str, Callable[[], None]] | None

# Called each time the context menu is requested; returns the current
# list of menu items (may vary based on selection state).
ContextMenuBuilder = Callable[[], list[ContextMenuItem]]


class AutoTooltipDelegate(QStyledItemDelegate):
    """Item delegate that shows a tooltip only when cell text is truncated."""

    def helpEvent(
        self,
        event: QEvent,
        view: QAbstractItemView,
        option,
        index: QModelIndex,
    ) -> bool:
        if event.type() != QEvent.Type.ToolTip:
            return super().helpEvent(event, view, option, index)

        # If the item already carries an explicit tooltip, show it.
        tooltip = index.data(Qt.ItemDataRole.ToolTipRole)
        if tooltip:
            QToolTip.showText(event.globalPos(), str(tooltip), view)
            return True

        # Otherwise show the display text only when it is wider than
        # the visible cell.
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if text:
            text = str(text)
            rect = view.visualRect(index)
            fm = view.fontMetrics()
            if fm.horizontalAdvance(text) > rect.width() - 8:
                QToolTip.showText(event.globalPos(), text, view)
                return True

        QToolTip.hideText()
        return True


class _ListTooltipFilter(QObject):
    """Event filter that shows tooltips for truncated QListWidget items."""

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() != QEvent.Type.ToolTip:
            return False

        view = obj.parent()
        if not isinstance(view, QListWidget):
            return False

        index = view.indexAt(event.pos())
        if not index.isValid():
            QToolTip.hideText()
            return True

        item = view.itemFromIndex(index)
        if item is None:
            QToolTip.hideText()
            return True

        # If the item has an explicit tooltip, let Qt handle it.
        if item.toolTip():
            return False

        text = item.text()
        if text:
            rect = view.visualItemRect(item)
            fm = view.fontMetrics()
            if fm.horizontalAdvance(text) > rect.width() - 8:
                QToolTip.showText(event.globalPos(), text, view)
                return True

        QToolTip.hideText()
        return True


def _connect_context_menu(
    view: QAbstractItemView,
    builder: ContextMenuBuilder,
) -> None:
    """Wire a right-click context menu onto *view*.

    Right-clicking on an item selects it before the menu appears.
    """
    view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def _show_menu(pos) -> None:
        # Select the item under the cursor so the menu acts on it.
        index = view.indexAt(pos)
        if index.isValid() and not view.selectionModel().isSelected(index):
            view.setCurrentIndex(index)

        items = builder()
        if not items:
            return

        menu = QMenu(view)
        for entry in items:
            if entry is None:
                menu.addSeparator()
            else:
                label, callback = entry
                action = menu.addAction(label)
                action.triggered.connect(callback)
        menu.exec(view.viewport().mapToGlobal(pos))

    view.customContextMenuRequested.connect(_show_menu)


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


def enhance_table(
    table: QTableWidget,
    *,
    context_menu_builder: ContextMenuBuilder | None = None,
) -> None:
    """Apply standard grid enhancements to a *QTableWidget*.

    :param table: The table widget to enhance.
    :param context_menu_builder: Optional callable returning context
        menu items for the current selection state.
    """
    # Alternating row colors
    table.setAlternatingRowColors(True)

    # Column resizing — all columns user-resizable, last stretches.
    header = table.horizontalHeader()
    header.setStretchLastSection(True)
    for col in range(table.columnCount()):
        header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
    header.setMinimumSectionSize(40)

    # Tooltips for truncated text
    table.setItemDelegate(AutoTooltipDelegate(table))

    # Context menu
    if context_menu_builder:
        _connect_context_menu(table, context_menu_builder)


def enhance_list(
    list_widget: QListWidget,
    *,
    context_menu_builder: ContextMenuBuilder | None = None,
) -> None:
    """Apply standard enhancements to a *QListWidget*.

    :param list_widget: The list widget to enhance.
    :param context_menu_builder: Optional callable returning context
        menu items for the current selection state.
    """
    # Alternating row colors
    list_widget.setAlternatingRowColors(True)

    # Tooltips for truncated text
    tooltip_filter = _ListTooltipFilter(list_widget)
    list_widget.viewport().installEventFilter(tooltip_filter)

    # Context menu
    if context_menu_builder:
        _connect_context_menu(list_widget, context_menu_builder)


def enhance_tree(
    tree: QTreeView | QTreeWidget,
    *,
    context_menu_builder: ContextMenuBuilder | None = None,
) -> None:
    """Apply standard enhancements to a *QTreeView* or *QTreeWidget*.

    :param tree: The tree widget to enhance.
    :param context_menu_builder: Optional callable returning context
        menu items for the current selection state.
    """
    # Alternating row colors
    tree.setAlternatingRowColors(True)

    # Column resizing (multi-column trees only)
    header = tree.header()
    if header and not header.isHidden():
        header.setStretchLastSection(True)
        for col in range(header.count()):
            header.setSectionResizeMode(
                col, QHeaderView.ResizeMode.Interactive
            )
        header.setMinimumSectionSize(40)

    # Tooltips for truncated text
    tree.setItemDelegate(AutoTooltipDelegate(tree))

    # Context menu
    if context_menu_builder:
        _connect_context_menu(tree, context_menu_builder)

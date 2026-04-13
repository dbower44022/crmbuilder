"""Left-hand navigation tree widget (Section 14.8.1).

Hierarchical display of schema objects with search filtering.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from automation.ui.browser.tree_model import TreeNode, build_tree, filter_tree


class NavigationTree(QWidget):
    """Left-hand navigation tree for the Data Browser.

    :param parent: Parent widget.
    """

    record_selected = Signal(str, int)  # table_name, record_id

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._roots: list[TreeNode] = []
        self._conn: sqlite3.Connection | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Search field
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search records...")
        self._search.setStyleSheet("font-size: 12px; padding: 6px;")
        self._search.textChanged.connect(self._on_search)
        layout.addWidget(self._search)

        # Tree widget
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(16)
        self._tree.setStyleSheet(
            "QTreeWidget { font-size: 12px; } "
            "QTreeWidget::item { padding: 3px 0; }"
        )
        self._tree.currentItemChanged.connect(self._on_item_changed)
        layout.addWidget(self._tree, stretch=1)

    def refresh(self, conn: sqlite3.Connection) -> None:
        """Rebuild the tree from the database.

        :param conn: Client database connection.
        """
        self._conn = conn
        self._roots = build_tree(conn)
        self._populate_tree(self._roots)

    def select_record(self, table_name: str, record_id: int) -> None:
        """Programmatically select a record in the tree.

        :param table_name: Table name.
        :param record_id: Record ID.
        """
        target_id = f"{table_name}:{record_id}"
        item = self._find_item(self._tree.invisibleRootItem(), target_id)
        if item:
            self._tree.setCurrentItem(item)
            self._tree.scrollToItem(item)

    def _populate_tree(self, roots: list[TreeNode]) -> None:
        """Populate the QTreeWidget from TreeNode data."""
        self._tree.clear()
        for node in roots:
            item = self._create_item(node, [])
            self._tree.addTopLevelItem(item)

    def _create_item(
        self, node: TreeNode, ancestors: list[str]
    ) -> QTreeWidgetItem:
        """Create a QTreeWidgetItem from a TreeNode.

        :param node: The tree node data.
        :param ancestors: List of ancestor labels for building the tooltip path.
        """
        label = node.label
        if node.expandable and node.child_count > 0:
            label = f"{node.label} ({node.child_count})"

        item = QTreeWidgetItem([label])
        item.setData(0, Qt.ItemDataRole.UserRole, node)

        # Build multiline tooltip with hierarchy path
        tooltip_lines = [label]
        if ancestors:
            path = " > ".join(ancestors)
            tooltip_lines.append(f"\nPath: {path}")
        if node.table_name:
            tooltip_lines.append(f"Table: {node.table_name}")
        item.setToolTip(0, "\n".join(tooltip_lines))

        child_ancestors = [*ancestors, node.label]
        for child in node.children:
            item.addChild(self._create_item(child, child_ancestors))

        return item

    def _on_item_changed(
        self, current: QTreeWidgetItem | None, previous: QTreeWidgetItem | None
    ) -> None:
        """Handle tree selection change."""
        if not current:
            return
        node: TreeNode = current.data(0, Qt.ItemDataRole.UserRole)
        if node and node.table_name and node.record_id is not None:
            self.record_selected.emit(node.table_name, node.record_id)

    def _on_search(self, text: str) -> None:
        """Filter the tree based on search text."""
        if not text.strip():
            self._populate_tree(self._roots)
        else:
            filtered = filter_tree(self._roots, text.strip())
            self._populate_tree(filtered)
            # Expand all after filter
            self._tree.expandAll()

    def _find_item(
        self, parent: QTreeWidgetItem, target_id: str
    ) -> QTreeWidgetItem | None:
        """Recursively find a tree item by node_id."""
        for i in range(parent.childCount()):
            child = parent.child(i)
            node: TreeNode | None = child.data(0, Qt.ItemDataRole.UserRole)
            if node and node.node_id == target_id:
                return child
            found = self._find_item(child, target_id)
            if found:
                return found
        return None

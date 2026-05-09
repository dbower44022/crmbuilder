"""HierarchicalEntityPicker — modal tree picker for hierarchical fields.

Used by the Topics CRUD dialog (slice D) for the parent_topic field;
designed for general reuse on any future entity with a parent-child
hierarchy (process steps, requirement parents, etc., when methodology
entities arrive post-v0.2).

The constructor takes a flat list of nodes (id, label, optional
parent_id) and an optional ``selectable`` predicate that returns False
for nodes that should be visible-but-unselectable. Topics' Edit dialog
uses the predicate to exclude the topic itself and all its descendants
(cycle prevention).

Selecting a node and clicking OK accepts the dialog with
``selected_id()`` returning the chosen id. ``No selection`` accepts
with ``selected_id() is None``. Cancel rejects.

Added in v2-ui-v0.2-A per DEC-030.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QPushButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

_NODE_ROLE = Qt.ItemDataRole.UserRole + 1
_SELECTABLE_ROLE = Qt.ItemDataRole.UserRole + 2


@dataclass(frozen=True)
class _Node:
    """Public Node type for callers; aliased as ``HierarchicalEntityPicker.Node``."""

    id: str
    label: str
    parent_id: str | None = None


class HierarchicalEntityPicker(QDialog):
    """Modal tree picker for selecting an entity from a hierarchy."""

    Node = _Node

    def __init__(
        self,
        nodes: list[_Node],
        *,
        selectable: Callable[[_Node], bool] | None = None,
        title: str = "Select",
        current_id: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(420, 520)
        self._selected_id: str | None = None
        self._selectable_pred = selectable
        self._items_by_id: dict[str, QStandardItem] = {}

        layout = QVBoxLayout(self)

        self._tree = QTreeView()
        self._tree.setHeaderHidden(True)
        self._tree.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self._tree.setSelectionMode(QTreeView.SelectionMode.SingleSelection)
        self._model = QStandardItemModel()
        self._tree.setModel(self._model)
        self._populate(nodes)
        self._tree.expandAll()
        self._tree.selectionModel().currentChanged.connect(
            self._on_selection_changed
        )
        layout.addWidget(self._tree)

        # Button row: No selection | Cancel | OK
        button_row = QHBoxLayout()
        self._no_selection_btn = QPushButton("No selection")
        self._no_selection_btn.clicked.connect(self._on_no_selection)
        button_row.addWidget(self._no_selection_btn)
        button_row.addStretch(1)
        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self._ok_btn = self._button_box.button(
            QDialogButtonBox.StandardButton.Ok
        )
        self._ok_btn.setEnabled(False)
        self._button_box.accepted.connect(self._on_accept)
        self._button_box.rejected.connect(self.reject)
        button_row.addWidget(self._button_box)
        layout.addLayout(button_row)

        if current_id is not None and current_id in self._items_by_id:
            item = self._items_by_id[current_id]
            self._tree.setCurrentIndex(item.index())
            self._tree.scrollTo(item.index())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def selected_id(self) -> str | None:
        return self._selected_id

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _populate(self, nodes: list[_Node]) -> None:
        children_by_parent: dict[str | None, list[_Node]] = {}
        nodes_by_id: dict[str, _Node] = {}
        for node in nodes:
            nodes_by_id[node.id] = node
            children_by_parent.setdefault(node.parent_id, []).append(node)

        # Sort each level by label.
        for siblings in children_by_parent.values():
            siblings.sort(key=lambda n: n.label.lower())

        # Recursive insert from roots. A node whose parent_id is set but
        # missing from the input is treated as a root (defensive).
        def insert(parent_item: QStandardItem | None, child_nodes: list[_Node]) -> None:
            for node in child_nodes:
                item = QStandardItem(node.label)
                item.setEditable(False)
                item.setData(node, _NODE_ROLE)
                selectable = (
                    True if self._selectable_pred is None
                    else bool(self._selectable_pred(node))
                )
                item.setData(selectable, _SELECTABLE_ROLE)
                if not selectable:
                    item.setForeground(Qt.GlobalColor.gray)
                if parent_item is None:
                    self._model.appendRow(item)
                else:
                    parent_item.appendRow(item)
                self._items_by_id[node.id] = item
                if node.id in children_by_parent:
                    insert(item, children_by_parent[node.id])

        insert(None, children_by_parent.get(None, []))

        # Append orphans (parent_id pointing to a missing node) at root.
        roots_seen = {n.id for n in children_by_parent.get(None, [])}
        for node in nodes:
            if node.parent_id is not None and node.parent_id not in nodes_by_id:
                if node.id in self._items_by_id:
                    continue
                item = QStandardItem(node.label)
                item.setEditable(False)
                item.setData(node, _NODE_ROLE)
                selectable = (
                    True if self._selectable_pred is None
                    else bool(self._selectable_pred(node))
                )
                item.setData(selectable, _SELECTABLE_ROLE)
                if not selectable:
                    item.setForeground(Qt.GlobalColor.gray)
                self._model.appendRow(item)
                self._items_by_id[node.id] = item
                _ = roots_seen  # not used further; lint guard

    def _on_selection_changed(self, current, _previous) -> None:
        if not current.isValid():
            self._ok_btn.setEnabled(False)
            return
        item = self._model.itemFromIndex(current)
        if item is None:
            self._ok_btn.setEnabled(False)
            return
        selectable = bool(item.data(_SELECTABLE_ROLE))
        self._ok_btn.setEnabled(selectable)

    def _on_accept(self) -> None:
        index = self._tree.currentIndex()
        if not index.isValid():
            return
        item = self._model.itemFromIndex(index)
        if item is None:
            return
        if not bool(item.data(_SELECTABLE_ROLE)):
            return
        node = item.data(_NODE_ROLE)
        if node is not None:
            self._selected_id = node.id
        self.accept()

    def _on_no_selection(self) -> None:
        self._selected_id = None
        self.accept()

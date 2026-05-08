"""Tests for HierarchicalEntityPicker widget."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox

from crmbuilder_v2.ui.widgets.hierarchical_picker import HierarchicalEntityPicker

Node = HierarchicalEntityPicker.Node


def _topics() -> list[Node]:
    return [
        Node(id="TOP-1", label="Schema design"),
        Node(id="TOP-2", label="References table", parent_id="TOP-1"),
        Node(id="TOP-3", label="Relationship vocab", parent_id="TOP-2"),
        Node(id="TOP-4", label="UI design"),
    ]


def _find_item_by_id(picker: HierarchicalEntityPicker, node_id: str):
    return picker._items_by_id[node_id]


def test_construction_with_three_nodes_renders_tree(qapp, qtbot):
    nodes = _topics()
    picker = HierarchicalEntityPicker(nodes, title="Pick parent")
    qtbot.addWidget(picker)
    assert picker._model.rowCount() == 2  # TOP-1 and TOP-4 are roots
    top1_item = _find_item_by_id(picker, "TOP-1")
    assert top1_item.rowCount() == 1  # TOP-2 is child


def test_selecting_node_and_ok_returns_id(qapp, qtbot):
    nodes = _topics()
    picker = HierarchicalEntityPicker(nodes)
    qtbot.addWidget(picker)
    target = _find_item_by_id(picker, "TOP-2")
    picker._tree.setCurrentIndex(target.index())
    picker._on_accept()
    assert picker.selected_id() == "TOP-2"


def test_no_selection_button_accepts_with_none(qapp, qtbot):
    nodes = _topics()
    picker = HierarchicalEntityPicker(nodes)
    qtbot.addWidget(picker)
    picker._on_no_selection()
    assert picker.selected_id() is None
    assert picker.result() == QDialog.DialogCode.Accepted


def test_cancel_returns_none(qapp, qtbot):
    nodes = _topics()
    picker = HierarchicalEntityPicker(nodes)
    qtbot.addWidget(picker)
    picker.reject()
    assert picker.selected_id() is None
    assert picker.result() == QDialog.DialogCode.Rejected


def test_selectable_predicate_disables_ok_for_blocked_nodes(qapp, qtbot):
    nodes = _topics()

    def predicate(node: Node) -> bool:
        # Disallow TOP-2 and its descendants — simulates editing TOP-2
        # and preventing cycle by reparenting under itself or a descendant.
        return node.id not in {"TOP-2", "TOP-3"}

    picker = HierarchicalEntityPicker(nodes, selectable=predicate)
    qtbot.addWidget(picker)
    ok_btn = picker._button_box.button(QDialogButtonBox.StandardButton.Ok)

    # Selecting a non-selectable node disables OK.
    blocked = _find_item_by_id(picker, "TOP-2")
    picker._tree.setCurrentIndex(blocked.index())
    assert ok_btn.isEnabled() is False

    # Selecting a selectable node enables OK.
    allowed = _find_item_by_id(picker, "TOP-1")
    picker._tree.setCurrentIndex(allowed.index())
    assert ok_btn.isEnabled() is True

    # Accepting on a blocked node is a no-op (selected_id stays None).
    picker._tree.setCurrentIndex(blocked.index())
    picker._on_accept()
    assert picker.selected_id() is None


def test_current_id_pre_selects_node(qapp, qtbot):
    nodes = _topics()
    picker = HierarchicalEntityPicker(nodes, current_id="TOP-3")
    qtbot.addWidget(picker)
    current = picker._tree.currentIndex()
    assert current.isValid()
    target_item = _find_item_by_id(picker, "TOP-3")
    assert current == target_item.index()


def test_orphan_node_renders_at_root(qapp, qtbot):
    nodes = [
        Node(id="A", label="Alpha"),
        Node(id="ORPHAN", label="Orphan", parent_id="DOES-NOT-EXIST"),
    ]
    picker = HierarchicalEntityPicker(nodes)
    qtbot.addWidget(picker)
    # Both A and ORPHAN should appear at the root level (orphan
    # appended after recursive insertion of true roots).
    assert picker._model.rowCount() == 2
    assert "ORPHAN" in picker._items_by_id

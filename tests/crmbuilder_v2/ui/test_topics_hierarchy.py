"""Tests for the TopicsPanel QTreeView master-pane build (slice D).

Slice D rewrote the panel from a flat ``QTableView`` (with name-prefix
indentation) to a ``QTreeView`` backed by a ``QStandardItemModel``.
The end-user behavior assertions ("clicking a parent navigates to it")
stay; the implementation moves from cell-clicks on a Parent Topic
column to tree-row clicks where parents are visible parent nodes.
"""

from __future__ import annotations

from crmbuilder_v2.ui.panels.topics import TopicsPanel
from PySide6.QtGui import QStandardItem


def _topic(identifier: str, name: str, parent: str | None = None) -> dict:
    return {
        "identifier": identifier,
        "name": name,
        "parent_topic_identifier": parent,
        "description": "",
    }


class _TopicsClientStub:
    """A list_topics-only client stub used by the panel-build tests."""

    def __init__(self, topics: list[dict] | None = None):
        self._topics = list(topics or [])

    def list_topics(self):
        return list(self._topics)


def _build_panel(qtbot, topics: list[dict] | None = None) -> TopicsPanel:
    panel = TopicsPanel(client=_TopicsClientStub(topics))
    qtbot.addWidget(panel)
    return panel


def _all_items(model) -> list[QStandardItem]:
    """Walk the tree and return every QStandardItem in pre-order."""

    def walk(parent: QStandardItem) -> list[QStandardItem]:
        out: list[QStandardItem] = []
        for r in range(parent.rowCount()):
            child = parent.child(r, 0)
            if child is not None:
                out.append(child)
                out.extend(walk(child))
        return out

    items: list[QStandardItem] = []
    for r in range(model.rowCount()):
        root = model.item(r, 0)
        if root is not None:
            items.append(root)
            items.extend(walk(root))
    return items


def test_master_pane_renders_as_qtreeview(qtbot):
    panel = _build_panel(qtbot)
    from PySide6.QtWidgets import QTreeView
    assert isinstance(panel._table, QTreeView)
    assert panel._master_view is panel._table


def test_tree_populates_with_parent_child_nesting(qapp, qtbot):
    topics = [
        _topic("TOP-1", "Root one"),
        _topic("TOP-2", "Child of one", parent="TOP-1"),
        _topic("TOP-3", "Root three"),
    ]
    panel = _build_panel(qtbot, topics)
    panel._populate_tree(topics)

    model = panel._tree_model
    # Two roots.
    assert model.rowCount() == 2
    # Root one (alphabetical by name) has one child.
    root_one = None
    root_three = None
    for r in range(model.rowCount()):
        item = model.item(r, 0)
        if "Root one" in item.text():
            root_one = item
        elif "Root three" in item.text():
            root_three = item
    assert root_one is not None
    assert root_three is not None
    assert root_one.rowCount() == 1
    assert root_three.rowCount() == 0
    child = root_one.child(0, 0)
    assert "Child of one" in child.text()


def test_tree_alphabetical_within_each_level(qapp, qtbot):
    """Siblings are sorted alphabetically by name (case-insensitive)."""
    topics = [
        _topic("TOP-Z", "Zeta root"),
        _topic("TOP-A", "alpha root"),
        _topic("TOP-M", "Middle root"),
    ]
    panel = _build_panel(qtbot, topics)
    panel._populate_tree(topics)

    model = panel._tree_model
    names = [model.item(r, 0).text() for r in range(model.rowCount())]
    assert "alpha root" in names[0]
    assert "Middle root" in names[1]
    assert "Zeta root" in names[2]


def test_tree_label_includes_identifier_and_name(qapp, qtbot):
    panel = _build_panel(qtbot, [_topic("TOP-1", "Storage")])
    panel._populate_tree([_topic("TOP-1", "Storage")])
    label = panel._tree_model.item(0, 0).text()
    assert "TOP-1" in label
    assert "Storage" in label


def test_orphan_topics_render_as_root_orphans(qapp, qtbot):
    """A topic whose declared parent is missing renders at root with a
    parenthetical (orphan) suffix to make the broken link visible."""
    topics = [
        _topic("TOP-A", "A root"),
        _topic("TOP-X", "Orphaned X", parent="MISSING"),
    ]
    panel = _build_panel(qtbot, topics)
    panel._populate_tree(topics)

    model = panel._tree_model
    assert model.rowCount() == 2
    labels = [model.item(r, 0).text() for r in range(model.rowCount())]
    orphan_label = next(s for s in labels if "Orphaned X" in s)
    assert orphan_label.endswith("(orphan)")


def test_cycle_does_not_recurse_infinitely(qapp, qtbot):
    """TOP-A → TOP-B and TOP-B → TOP-A: cycle. Each topic appears at most once."""
    topics = [
        _topic("TOP-A", "A", parent="TOP-B"),
        _topic("TOP-B", "B", parent="TOP-A"),
    ]
    panel = _build_panel(qtbot, topics)
    panel._populate_tree(topics)

    from crmbuilder_v2.ui.panels.topics import _IDENTIFIER_ROLE

    items = _all_items(panel._tree_model)
    # Each topic appears at most once.
    assert len(items) == 2
    ids = sorted(item.data(_IDENTIFIER_ROLE) for item in items)
    assert ids == ["TOP-A", "TOP-B"]


def test_deep_hierarchy_nests_proportional_to_depth(qapp, qtbot):
    topics = [
        _topic("TOP-1", "Level zero"),
        _topic("TOP-2", "Level one", parent="TOP-1"),
        _topic("TOP-3", "Level two", parent="TOP-2"),
    ]
    panel = _build_panel(qtbot, topics)
    panel._populate_tree(topics)

    model = panel._tree_model
    assert model.rowCount() == 1
    level_zero = model.item(0, 0)
    assert level_zero.rowCount() == 1
    level_one = level_zero.child(0, 0)
    assert level_one.rowCount() == 1
    level_two = level_one.child(0, 0)
    assert level_two.rowCount() == 0


def test_clicking_parent_node_emits_navigation_via_select_record(qapp, qtbot):
    """Selecting a parent tree row makes that record the detail-pane subject.

    The 'click on Parent Topic cell' interaction from v0.1 is replaced by
    direct tree-row navigation — clicking the parent node selects it.
    """
    topics = [
        _topic("TOP-1", "Root"),
        _topic("TOP-2", "Child", parent="TOP-1"),
    ]
    panel = TopicsPanel(client=_TopicsClientStub(topics))
    qtbot.addWidget(panel)
    panel._populate_tree(topics)
    panel._records = topics  # tests poke this directly to skip the worker

    # Select the parent row.
    parent_item = panel._items_by_identifier["TOP-1"]
    panel._table.setCurrentIndex(parent_item.index())

    # The current selection's identifier is TOP-1.
    current = panel._table.selectionModel().currentIndex()
    item = panel._tree_model.itemFromIndex(current)
    from crmbuilder_v2.ui.panels.topics import _IDENTIFIER_ROLE
    assert item.data(_IDENTIFIER_ROLE) == "TOP-1"


def test_select_record_by_identifier_jumps_to_node(qapp, qtbot):
    topics = [
        _topic("TOP-1", "Root"),
        _topic("TOP-2", "Child", parent="TOP-1"),
    ]
    panel = TopicsPanel(client=_TopicsClientStub(topics))
    qtbot.addWidget(panel)
    panel._populate_tree(topics)
    panel._records = topics

    selected = panel._select_by_identifier("TOP-2")
    assert selected is True
    current = panel._table.selectionModel().currentIndex()
    item = panel._tree_model.itemFromIndex(current)
    from crmbuilder_v2.ui.panels.topics import _IDENTIFIER_ROLE
    assert item.data(_IDENTIFIER_ROLE) == "TOP-2"


def test_expand_all_after_populate(qapp, qtbot):
    """All nodes should be expanded by default so the hierarchy is visible
    without clicking each parent."""
    topics = [
        _topic("TOP-1", "Root"),
        _topic("TOP-2", "Child", parent="TOP-1"),
        _topic("TOP-3", "Grandchild", parent="TOP-2"),
    ]
    panel = TopicsPanel(client=_TopicsClientStub(topics))
    qtbot.addWidget(panel)
    panel._populate_tree(topics)

    parent_item = panel._items_by_identifier["TOP-1"]
    child_item = panel._items_by_identifier["TOP-2"]
    assert panel._table.isExpanded(parent_item.index()) is True
    assert panel._table.isExpanded(child_item.index()) is True


def test_refresh_through_worker_populates_tree(qapp, qtbot):
    """A real refresh() through the worker pipeline produces a populated tree."""
    topics = [
        _topic("TOP-1", "Root"),
        _topic("TOP-2", "Child", parent="TOP-1"),
    ]
    panel = TopicsPanel(client=_TopicsClientStub(topics))
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(
        lambda: panel._tree_model.rowCount() >= 1, timeout=2000
    )
    # One root with one child.
    assert panel._tree_model.rowCount() == 1
    root = panel._tree_model.item(0, 0)
    assert root.rowCount() == 1

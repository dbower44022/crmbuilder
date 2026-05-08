"""Tests for the TopicsPanel hierarchical view build."""

from __future__ import annotations

from crmbuilder_v2.ui.panels.topics import TopicsPanel


def _topic(identifier: str, name: str, parent: str | None = None) -> dict:
    return {
        "identifier": identifier,
        "name": name,
        "parent_topic_identifier": parent,
        "description": "",
    }


def _build_panel(qtbot, qapp):
    """Construct a TopicsPanel with no client; we exercise the build helper."""

    class _Stub:
        def list_topics(self):
            return []

    panel = TopicsPanel(client=_Stub())
    qtbot.addWidget(panel)
    return panel


def test_hierarchy_orders_parents_before_children_with_indent(qapp, qtbot):
    panel = _build_panel(qtbot, qapp)
    topics = [
        _topic("TOP-1", "Root one"),
        _topic("TOP-2", "Child of one", parent="TOP-1"),
        _topic("TOP-3", "Root three"),
        _topic("TOP-4", "Child of three", parent="TOP-3"),
    ]

    out = panel._build_hierarchical_view(topics)

    assert [r["identifier"] for r in out] == ["TOP-1", "TOP-2", "TOP-3", "TOP-4"]
    assert out[0]["_display_name"] == "Root one"
    assert out[1]["_display_name"] == "    Child of one"
    assert out[2]["_display_name"] == "Root three"
    assert out[3]["_display_name"] == "    Child of three"


def test_orphan_topics_are_appended_with_indicator(qapp, qtbot):
    panel = _build_panel(qtbot, qapp)
    topics = [
        _topic("TOP-A", "A root"),
        _topic("TOP-X", "Orphaned X", parent="MISSING"),
    ]

    out = panel._build_hierarchical_view(topics)

    assert [r["identifier"] for r in out] == ["TOP-A", "TOP-X"]
    assert out[1]["_display_name"].endswith("(orphan)")


def test_cycle_does_not_recurse_infinitely(qapp, qtbot):
    panel = _build_panel(qtbot, qapp)
    # TOP-A -> TOP-B and TOP-B -> TOP-A. Neither has a None parent, so
    # neither appears as a root; they fall through to the orphan path.
    topics = [
        _topic("TOP-A", "A", parent="TOP-B"),
        _topic("TOP-B", "B", parent="TOP-A"),
    ]

    out = panel._build_hierarchical_view(topics)
    identifiers = [r["identifier"] for r in out]
    assert sorted(identifiers) == ["TOP-A", "TOP-B"]
    # Each appears at most once.
    assert len(set(identifiers)) == len(identifiers)


def test_deep_hierarchy_indents_proportional_to_depth(qapp, qtbot):
    panel = _build_panel(qtbot, qapp)
    topics = [
        _topic("TOP-1", "Level zero"),
        _topic("TOP-2", "Level one", parent="TOP-1"),
        _topic("TOP-3", "Level two", parent="TOP-2"),
    ]

    out = panel._build_hierarchical_view(topics)

    assert out[0]["_display_name"] == "Level zero"
    assert out[1]["_display_name"] == "    Level one"
    assert out[2]["_display_name"] == "        Level two"


def test_click_on_parent_topic_cell_with_value_navigates(qapp, qtbot):
    """Single-click on a non-empty Parent Topic cell emits navigate_requested."""
    from PySide6.QtCore import QModelIndex

    class _Stub:
        def list_topics(self):
            return [
                {"identifier": "TOP-1", "name": "Root", "parent_topic_identifier": None, "description": ""},
                {"identifier": "TOP-2", "name": "Child", "parent_topic_identifier": "TOP-1", "description": ""},
            ]

    panel = TopicsPanel(client=_Stub())
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount(QModelIndex()) >= 2, timeout=2000)

    captured = []
    panel.navigate_requested.connect(lambda et, ident: captured.append((et, ident)))

    # Find the row whose identifier == 'TOP-2', click its Parent Topic column (index 2).
    target_row = None
    for r in range(panel._model.rowCount(QModelIndex())):
        rec = panel._model.record_at(r)
        if rec and rec.get("identifier") == "TOP-2":
            target_row = r
            break
    assert target_row is not None

    idx = panel._model.index(target_row, 2)
    panel._table.clicked.emit(idx)
    assert captured == [("topic", "TOP-1")]


def test_click_on_parent_topic_cell_with_empty_value_does_not_navigate(qapp, qtbot):
    from PySide6.QtCore import QModelIndex

    class _Stub:
        def list_topics(self):
            return [
                {"identifier": "TOP-1", "name": "Root", "parent_topic_identifier": None, "description": ""},
            ]

    panel = TopicsPanel(client=_Stub())
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount(QModelIndex()) >= 1, timeout=2000)

    captured = []
    panel.navigate_requested.connect(lambda et, ident: captured.append((et, ident)))

    idx = panel._model.index(0, 2)
    panel._table.clicked.emit(idx)
    assert captured == []


def test_click_on_other_columns_does_not_navigate(qapp, qtbot):
    from PySide6.QtCore import QModelIndex

    class _Stub:
        def list_topics(self):
            return [
                {"identifier": "TOP-1", "name": "Root", "parent_topic_identifier": None, "description": ""},
                {"identifier": "TOP-2", "name": "Child", "parent_topic_identifier": "TOP-1", "description": ""},
            ]

    panel = TopicsPanel(client=_Stub())
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount(QModelIndex()) >= 2, timeout=2000)

    captured = []
    panel.navigate_requested.connect(lambda et, ident: captured.append((et, ident)))

    target_row = None
    for r in range(panel._model.rowCount(QModelIndex())):
        rec = panel._model.record_at(r)
        if rec and rec.get("identifier") == "TOP-2":
            target_row = r
            break
    assert target_row is not None

    # Click Identifier column (0).
    panel._table.clicked.emit(panel._model.index(target_row, 0))
    # Click Name column (1).
    panel._table.clicked.emit(panel._model.index(target_row, 1))
    assert captured == []

"""Integration tests for PI-117 multi-sort + grouping on ReferencesSection.

Covers the delta WTK-068 adds over PI-116's single-column sort: the
group-by swap to a tree, collapse/expand, composition with the filter and
the multi-column sort, and navigation from a grouped row.
"""

from __future__ import annotations

from crmbuilder_v2.ui.widgets.references_section import ReferencesSection
from PySide6.QtCore import QModelIndex, Qt

# Column indices (mirror _COLUMNS).
_COL_RELATIONSHIP = 1
_COL_IDENTIFIER = 2
_COL_CREATED = 6

# Group-by combo option indices (mirror _GROUP_OPTIONS).
_GROUP_RELATIONSHIP = 1
_GROUP_TYPE = 2


def _row(source_id, rel, source_type, created):
    return {
        "source_type": source_type,
        "source_id": source_id,
        "target_type": "decision",
        "target_id": "DEC-001",
        "relationship": rel,
        "other_summary": {
            "identifier": source_id,
            "entity_type": source_type,
            "title": f"{source_id} title",
            "status": "complete",
            "created_at": created,
            "updated_at": created,
        },
    }


def _payload():
    return {
        "as_target": [
            _row("SES-002", "decided_in", "session", "2026-03-01T10:00:00+00:00"),
            _row("SES-001", "decided_in", "session", "2026-01-01T10:00:00+00:00"),
            _row("TOP-1", "is_about", "topic", "2026-02-01T10:00:00+00:00"),
        ],
        "as_source": [],
    }


def _section(qtbot):
    section = ReferencesSection("decision", "DEC-001", _payload())
    qtbot.addWidget(section)
    return section


def _group_labels(section):
    gm = section._group_model
    return [gm.group_label(g) for g in range(gm.group_count())]


def test_group_by_swaps_to_tree_and_restores_table(qapp, qtbot):
    section = _section(qtbot)
    assert section._stack.currentWidget() is section._table
    section._group_combo.setCurrentIndex(_GROUP_RELATIONSHIP)
    assert section._stack.currentWidget() is section._tree
    assert section._group_model is not None
    # Back to (none) restores the exact flat table.
    section._group_combo.setCurrentIndex(0)
    assert section._stack.currentWidget() is section._table
    assert section._group_model is None


def test_group_nodes_show_value_and_count(qapp, qtbot):
    section = _section(qtbot)
    section._group_combo.setCurrentIndex(_GROUP_RELATIONSHIP)
    # Inbound decided_in → "Decided in" (2); is_about → "Cited by" (1).
    assert "Decided in (2)" in _group_labels(section)
    assert "Cited by (1)" in _group_labels(section)


def test_grouping_composes_with_multi_sort_within_group(qapp, qtbot):
    section = _section(qtbot)
    # Build a Created-ascending sort, then group by relationship.
    section._proxy.set_primary(_COL_CREATED)
    section._group_combo.setCurrentIndex(_GROUP_RELATIONSHIP)
    gm = section._group_model
    # Find the "Decided in" group and read its children's identifiers.
    decided_group = next(
        g for g in range(gm.group_count())
        if gm.group_label(g).startswith("Decided in")
    )
    parent = gm.index(decided_group, 0, QModelIndex())
    idents = [
        gm.data(gm.index(c, _COL_IDENTIFIER, parent), Qt.ItemDataRole.DisplayRole)
        for c in range(gm.rowCount(parent))
    ]
    # Created ascending: SES-001 (Jan) before SES-002 (Mar).
    assert idents == ["SES-001", "SES-002"]


def test_sort_change_while_grouped_reorders_children(qapp, qtbot):
    section = _section(qtbot)
    section._group_combo.setCurrentIndex(_GROUP_RELATIONSHIP)
    # Now flip to Created descending; children must reorder live.
    section._proxy.set_primary(_COL_CREATED)
    section._proxy.set_primary(_COL_CREATED)  # toggle to descending
    gm = section._group_model
    decided_group = next(
        g for g in range(gm.group_count())
        if gm.group_label(g).startswith("Decided in")
    )
    parent = gm.index(decided_group, 0, QModelIndex())
    idents = [
        gm.data(gm.index(c, _COL_IDENTIFIER, parent), Qt.ItemDataRole.DisplayRole)
        for c in range(gm.rowCount(parent))
    ]
    assert idents == ["SES-002", "SES-001"]


def test_expand_collapse_all_changes_visible_rows(qapp, qtbot):
    section = _section(qtbot)
    section._group_combo.setCurrentIndex(_GROUP_RELATIONSHIP)
    expanded = section._visible_tree_rows()
    section._on_collapse_all()
    collapsed = section._visible_tree_rows()
    # Collapsed shows only the group nodes; expanded shows groups + children.
    assert collapsed == section._group_model.group_count()
    assert expanded > collapsed
    section._on_expand_all()
    assert section._visible_tree_rows() == expanded


def test_filter_excluding_all_shows_empty_state_no_groups(qapp, qtbot):
    section = _section(qtbot)
    section._group_combo.setCurrentIndex(_GROUP_RELATIONSHIP)
    with qtbot.waitSignal(section._filter.filterChanged, timeout=2000):
        section._filter.setText("zzz-no-match")
    assert section._proxy.rowCount() == 0
    assert section._group_model.group_count() == 0
    assert section._empty_state.isVisibleTo(section)
    assert not section._stack.isVisibleTo(section)


def test_navigation_from_grouped_row_emits(qapp, qtbot):
    section = _section(qtbot)
    section._group_combo.setCurrentIndex(_GROUP_TYPE)
    gm = section._group_model
    # Find the topic group and double-click its child.
    topic_group = next(
        g for g in range(gm.group_count())
        if gm.group_label(g).startswith("Topic")
    )
    parent = gm.index(topic_group, 0, QModelIndex())
    child = gm.index(0, 0, parent)
    received: list[tuple[str, str]] = []
    section.navigate_requested.connect(lambda t, i: received.append((t, i)))
    section._on_double_clicked(child)
    assert received == [("topic", "TOP-1")]


def test_double_click_group_node_does_not_navigate(qapp, qtbot):
    section = _section(qtbot)
    section._group_combo.setCurrentIndex(_GROUP_RELATIONSHIP)
    gm = section._group_model
    group_index = gm.index(0, 0, QModelIndex())
    received: list[tuple[str, str]] = []
    section.navigate_requested.connect(lambda t, i: received.append((t, i)))
    section._on_double_clicked(group_index)
    assert received == []

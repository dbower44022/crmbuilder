"""Integration tests for PI-117 sort + grouping on the standalone panel.

PI-116 left ``ReferencesPanel`` list-only; WTK-068 adds header-click
single- and multi-column sort plus a Group-by control, composing with the
existing source/target-type dropdowns and free-text filter.
"""

from __future__ import annotations

from typing import Any

from crmbuilder_v2.ui.panels.references import ReferencesPanel
from PySide6.QtCore import QModelIndex, Qt

# Group-by combo option indices (mirror _GROUP_OPTIONS).
_GROUP_SOURCE_TYPE = 1
_GROUP_RELATIONSHIP = 2


def _refs() -> list[dict[str, Any]]:
    return [
        {
            "source_type": "session",
            "source_id": "SES-004",
            "target_type": "decision",
            "target_id": "DEC-018",
            "relationship": "decided_in",
        },
        {
            "source_type": "decision",
            "source_id": "DEC-018",
            "target_type": "decision",
            "target_id": "DEC-001",
            "relationship": "supersedes",
        },
        {
            "source_type": "session",
            "source_id": "SES-005",
            "target_type": "topic",
            "target_id": "TOP-1",
            "relationship": "discusses",
        },
    ]


class _FakeClient:
    def __init__(self, records):
        self._records = list(records)

    def list_references(self):
        return list(self._records)


def _panel(qtbot, records=None):
    panel = ReferencesPanel(client=_FakeClient(records if records is not None else _refs()))
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 3, timeout=2000)
    return panel


def _proxy_column(panel, column):
    proxy = panel._proxy
    return [
        proxy.data(proxy.index(r, column), Qt.ItemDataRole.DisplayRole)
        for r in range(proxy.rowCount())
    ]


def test_header_click_sorts_previously_unsorted_list(qapp, qtbot):
    panel = _panel(qtbot)
    header = panel._table.horizontalHeader()
    # Column 0 = Source display. Plain click → ascending single-column sort.
    header._route_click(0, Qt.KeyboardModifier.NoModifier)
    sources = _proxy_column(panel, 0)
    assert sources == sorted(sources, key=str.lower)
    assert panel._proxy.sort_keys() == [(0, Qt.SortOrder.AscendingOrder)]


def test_modifier_click_builds_two_key_order(qapp, qtbot):
    panel = _panel(qtbot)
    header = panel._table.horizontalHeader()
    header._route_click(2, Qt.KeyboardModifier.NoModifier)  # Target
    header._route_click(0, Qt.KeyboardModifier.ControlModifier)  # + Source
    assert panel._proxy.sort_keys() == [
        (2, Qt.SortOrder.AscendingOrder),
        (0, Qt.SortOrder.AscendingOrder),
    ]


def test_group_by_swaps_to_tree_and_back(qapp, qtbot):
    panel = _panel(qtbot)
    # isHidden() reflects the explicit show/hide flag regardless of whether
    # the (offscreen) top-level panel is mapped.
    assert panel._tree.isHidden()
    panel._group_combo.setCurrentIndex(_GROUP_SOURCE_TYPE)
    assert not panel._tree.isHidden()
    assert panel._table.isHidden()
    assert panel._group_model is not None
    panel._group_combo.setCurrentIndex(0)
    assert not panel._table.isHidden()
    assert panel._tree.isHidden()
    assert panel._group_model is None


def test_group_nodes_label_value_and_count(qapp, qtbot):
    panel = _panel(qtbot)
    panel._group_combo.setCurrentIndex(_GROUP_SOURCE_TYPE)
    gm = panel._group_model
    labels = [gm.group_label(g) for g in range(gm.group_count())]
    # Two session-source rows, one decision-source row.
    assert "session (2)" in labels
    assert "decision (1)" in labels


def test_grouping_composes_with_source_dropdown(qapp, qtbot):
    panel = _panel(qtbot)
    # Filter to session-source rows, then group by relationship.
    index = panel._source_filter.findText("session")
    panel._source_filter.setCurrentIndex(index)
    qtbot.waitUntil(lambda: panel._model.rowCount() == 2, timeout=2000)
    panel._group_combo.setCurrentIndex(_GROUP_RELATIONSHIP)
    gm = panel._group_model
    # Only the two session rows survive → two relationship groups.
    total_children = sum(gm.child_count(g) for g in range(gm.group_count()))
    assert total_children == 2
    labels = [gm.group_label(g) for g in range(gm.group_count())]
    assert "decided_in (1)" in labels
    assert "discusses (1)" in labels


def test_grouping_composes_with_free_text_filter(qapp, qtbot):
    panel = _panel(qtbot)
    panel._group_combo.setCurrentIndex(_GROUP_SOURCE_TYPE)
    with qtbot.waitSignal(panel._text_filter.filterChanged, timeout=2000):
        panel._text_filter.setText("SES-005")
    qtbot.waitUntil(lambda: panel._model.rowCount() == 1, timeout=2000)
    gm = panel._group_model
    total_children = sum(gm.child_count(g) for g in range(gm.group_count()))
    assert total_children == 1


def test_click_navigation_from_grouped_row(qapp, qtbot):
    panel = _panel(qtbot)
    panel._group_combo.setCurrentIndex(_GROUP_SOURCE_TYPE)
    gm = panel._group_model
    # Find the 'session' group and click a child's Source cell (col 0).
    session_group = next(
        g for g in range(gm.group_count())
        if gm.group_label(g).startswith("session")
    )
    parent = gm.index(session_group, 0, QModelIndex())
    child_source_cell = gm.index(0, 0, parent)
    received: list[tuple[str, str]] = []
    panel.navigate_requested.connect(
        lambda t, i: received.append((t, i))
    )
    panel._on_cell_clicked(child_source_cell)
    assert received and received[0][0] == "session"


def test_existing_source_index_click_still_navigates(qapp, qtbot):
    # The pre-PI-117 test path passes a *source*-model index directly;
    # _record_at_index must still resolve it.
    panel = _panel(qtbot)
    received: list[tuple[str, str]] = []
    panel.navigate_requested.connect(lambda t, i: received.append((t, i)))
    panel._on_cell_clicked(panel._model.index(0, 0))
    assert received == [("session", "SES-004")]

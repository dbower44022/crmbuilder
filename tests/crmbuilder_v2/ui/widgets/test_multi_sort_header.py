"""Tests for MultiSortHeaderView — precedence indicator + click routing."""

from __future__ import annotations

from crmbuilder_v2.ui.widgets.multi_sort_header import MultiSortHeaderView
from crmbuilder_v2.ui.widgets.multi_sort_proxy import MultiSortProxyModel
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import QTableView


class _Model(QAbstractTableModel):
    def rowCount(self, _p: QModelIndex | None = None) -> int:  # noqa: N802
        return 2

    def columnCount(self, _p: QModelIndex | None = None) -> int:  # noqa: N802
        return 3

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.UserRole):
            return f"{index.row()}-{index.column()}"
        return None


def _build(qapp, qtbot):
    table = QTableView()
    qtbot.addWidget(table)
    proxy = MultiSortProxyModel()
    proxy.setSourceModel(_Model())
    table.setModel(proxy)
    header = MultiSortHeaderView(Qt.Orientation.Horizontal, table)
    table.setHorizontalHeader(header)
    header.attach_proxy(proxy)
    return proxy, header


def test_indicator_reflects_sort_keys(qapp, qtbot):
    proxy, header = _build(qapp, qtbot)
    proxy.set_primary(1)
    proxy.cycle_secondary(2)
    assert header.indicator_for(1) == (1, Qt.SortOrder.AscendingOrder)
    assert header.indicator_for(2) == (2, Qt.SortOrder.AscendingOrder)
    assert header.indicator_for(0) is None


def test_indicator_updates_on_clear(qapp, qtbot):
    proxy, header = _build(qapp, qtbot)
    proxy.set_primary(1)
    proxy.cycle_secondary(2)
    proxy.clear_sort()
    assert header.indicator_for(0) == (1, Qt.SortOrder.AscendingOrder)
    assert header.indicator_for(1) is None
    assert header.indicator_for(2) is None


def test_plain_click_sets_primary(qapp, qtbot):
    proxy, header = _build(qapp, qtbot)
    header._route_click(2, Qt.KeyboardModifier.NoModifier)
    assert proxy.sort_keys() == [(2, Qt.SortOrder.AscendingOrder)]


def test_modifier_click_adds_secondary(qapp, qtbot):
    proxy, header = _build(qapp, qtbot)
    header._route_click(1, Qt.KeyboardModifier.NoModifier)
    header._route_click(2, Qt.KeyboardModifier.ControlModifier)
    assert proxy.sort_keys() == [
        (1, Qt.SortOrder.AscendingOrder),
        (2, Qt.SortOrder.AscendingOrder),
    ]
    # Shift is accepted as an equivalent modifier.
    header._route_click(0, Qt.KeyboardModifier.ShiftModifier)
    assert proxy.sort_keys()[-1] == (0, Qt.SortOrder.AscendingOrder)


def test_sort_keys_changed_drives_indicator_refresh(qapp, qtbot):
    # The header repaints off the proxy's sortKeysChanged signal; assert
    # the signal fires on a key change so the indicator stays live.
    proxy, header = _build(qapp, qtbot)
    seen: list[int] = []
    proxy.sortKeysChanged.connect(lambda: seen.append(1))
    proxy.set_primary(1)
    assert seen
    assert header.indicator_for(1) == (1, Qt.SortOrder.AscendingOrder)

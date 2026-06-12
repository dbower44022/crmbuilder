"""Tests for MultiSortHeaderView — precedence indicator + click routing."""

from __future__ import annotations

import shiboken6
from crmbuilder_v2.ui.widgets.multi_sort_header import MultiSortHeaderView
from crmbuilder_v2.ui.widgets.multi_sort_proxy import MultiSortProxyModel
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QRect, Qt
from PySide6.QtGui import QPainter, QPixmap
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
    # Ownership per PI-159 §4.3: the table is the single root of the C++
    # tree — proxy and source model are parented to it, and the table is
    # returned so the test holds the root strongly for its whole duration
    # (qtbot.addWidget keeps only a weakref).
    table = QTableView()
    qtbot.addWidget(table)
    proxy = MultiSortProxyModel(table)
    proxy.setSourceModel(_Model(proxy))
    table.setModel(proxy)
    header = MultiSortHeaderView(Qt.Orientation.Horizontal, table)
    table.setHorizontalHeader(header)
    header.attach_proxy(proxy)
    return table, proxy, header


def test_indicator_reflects_sort_keys(qapp, qtbot):
    _table, proxy, header = _build(qapp, qtbot)
    proxy.set_primary(1)
    proxy.cycle_secondary(2)
    assert header.indicator_for(1) == (1, Qt.SortOrder.AscendingOrder)
    assert header.indicator_for(2) == (2, Qt.SortOrder.AscendingOrder)
    assert header.indicator_for(0) is None


def test_indicator_updates_on_clear(qapp, qtbot):
    _table, proxy, header = _build(qapp, qtbot)
    proxy.set_primary(1)
    proxy.cycle_secondary(2)
    proxy.clear_sort()
    assert header.indicator_for(0) == (1, Qt.SortOrder.AscendingOrder)
    assert header.indicator_for(1) is None
    assert header.indicator_for(2) is None


def test_plain_click_sets_primary(qapp, qtbot):
    _table, proxy, header = _build(qapp, qtbot)
    header._route_click(2, Qt.KeyboardModifier.NoModifier)
    assert proxy.sort_keys() == [(2, Qt.SortOrder.AscendingOrder)]


def test_modifier_click_adds_secondary(qapp, qtbot):
    _table, proxy, header = _build(qapp, qtbot)
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
    _table, proxy, header = _build(qapp, qtbot)
    seen: list[int] = []
    proxy.sortKeysChanged.connect(lambda: seen.append(1))
    proxy.set_primary(1)
    assert seen
    assert header.indicator_for(1) == (1, Qt.SortOrder.AscendingOrder)


# ----------------------------------------------------------------------
# Lifetime guards (PI-159 / WTK-119) — every torn-down state must paint
# as a no-op instead of crashing.
# ----------------------------------------------------------------------


def _paint(header, column: int = 0) -> None:
    """Drive paintSection directly with a real QPainter on a QPixmap."""
    pixmap = QPixmap(200, 40)
    painter = QPainter(pixmap)
    try:
        header.paintSection(painter, QRect(0, 0, 100, 30), column)
    finally:
        painter.end()


def test_paint_section_without_proxy_is_safe(qapp, qtbot):
    table = QTableView()
    qtbot.addWidget(table)
    header = MultiSortHeaderView(Qt.Orientation.Horizontal, table)
    table.setHorizontalHeader(header)
    assert header.indicator_for(0) is None
    _paint(header)


def test_paint_section_with_destroyed_proxy_is_safe(qapp, qtbot):
    _table, proxy, header = _build(qapp, qtbot)
    proxy.set_primary(1)
    shiboken6.delete(proxy)
    assert header.indicator_for(1) is None
    _paint(header, column=1)


def test_paint_section_with_destroyed_table_is_safe(qapp, qtbot):
    # Destroying the owning table tears down the header's C++ object; a
    # paint via the still-held Python wrapper must be a no-op.
    table, proxy, header = _build(qapp, qtbot)
    proxy.set_primary(1)
    shiboken6.delete(table)
    assert not shiboken6.isValid(header)
    pixmap = QPixmap(200, 40)
    painter = QPainter(pixmap)
    try:
        header.paintSection(painter, QRect(0, 0, 100, 30), 1)
    finally:
        painter.end()


def test_paint_section_with_inactive_painter_is_safe(qapp, qtbot):
    _table, proxy, header = _build(qapp, qtbot)
    proxy.set_primary(1)
    header.paintSection(QPainter(), QRect(0, 0, 100, 30), 1)


def test_proxy_destroyed_signal_clears_back_reference(qapp, qtbot):
    _table, proxy, header = _build(qapp, qtbot)
    shiboken6.delete(proxy)
    assert header._proxy is None


def test_detach_proxy_clears_and_disconnects(qapp, qtbot):
    _table, proxy, header = _build(qapp, qtbot)
    header.detach_proxy()
    assert header._proxy is None
    assert header.indicator_for(0) is None
    # Idempotent, and safe again after the proxy's C++ object is gone.
    header.detach_proxy()
    shiboken6.delete(proxy)
    header.detach_proxy()


def test_detach_proxy_stops_sort_key_refresh(qapp, qtbot):
    _table, proxy, header = _build(qapp, qtbot)
    header.detach_proxy()
    # A key change on the detached proxy must not reach the header.
    proxy.set_primary(2)
    assert header.indicator_for(2) is None

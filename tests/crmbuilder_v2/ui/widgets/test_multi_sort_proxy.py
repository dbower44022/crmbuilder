"""Tests for MultiSortProxyModel — composite multi-column sort (PI-117).

Model-level tests; no Qt event loop needed beyond the ``qapp`` fixture
that the widget suite already forces to offscreen.
"""

from __future__ import annotations

from typing import Any

from crmbuilder_v2.ui.widgets.multi_sort_proxy import MultiSortProxyModel
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

# Columns: 0 = type, 1 = date. UserRole returns the sort key (raw value);
# DisplayRole returns the same string for readability.
_COLS = ["type", "date"]


class _Model(QAbstractTableModel):
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        super().__init__()
        self._rows = rows

    def rowCount(self, _p: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self._rows)

    def columnCount(self, _p: QModelIndex | None = None) -> int:  # noqa: N802
        return len(_COLS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        value = self._rows[index.row()][_COLS[index.column()]]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.UserRole):
            return value
        return None


def _fixture() -> list[dict[str, Any]]:
    # Two types (a, b); dates chosen so type-then-date differs from
    # date-only ordering.
    return [
        {"type": "b", "date": "2026-01-01", "tag": "b1"},
        {"type": "a", "date": "2026-03-01", "tag": "a3"},
        {"type": "a", "date": "2026-01-01", "tag": "a1"},
        {"type": "b", "date": "2026-02-01", "tag": "b2"},
    ]


def _build(qapp, rows=None):
    model = _Model(rows if rows is not None else _fixture())
    proxy = MultiSortProxyModel()
    proxy.setSourceModel(model)
    proxy.setSortRole(Qt.ItemDataRole.UserRole)
    return model, proxy


def _ordered_tags(model, proxy) -> list[str]:
    return [
        model._rows[proxy.mapToSource(proxy.index(r, 0)).row()]["tag"]
        for r in range(proxy.rowCount())
    ]


def test_set_primary_single_key(qapp):
    model, proxy = _build(qapp)
    proxy.set_primary(0)  # type ascending
    assert proxy.sort_keys() == [(0, Qt.SortOrder.AscendingOrder)]
    # All a's before all b's; within a tie the source order holds (stable).
    assert _ordered_tags(model, proxy) == ["a3", "a1", "b1", "b2"]


def test_set_primary_toggles_direction(qapp):
    _model, proxy = _build(qapp)
    proxy.set_primary(0)
    proxy.set_primary(0)  # same column → toggle to descending
    assert proxy.sort_keys() == [(0, Qt.SortOrder.DescendingOrder)]


def test_multi_column_type_then_date(qapp):
    model, proxy = _build(qapp)
    proxy.set_primary(0)  # type asc
    proxy.cycle_secondary(1)  # + date asc
    assert proxy.sort_keys() == [
        (0, Qt.SortOrder.AscendingOrder),
        (1, Qt.SortOrder.AscendingOrder),
    ]
    # type asc, ties broken by date asc.
    assert _ordered_tags(model, proxy) == ["a1", "a3", "b1", "b2"]


def test_per_key_direction_type_asc_date_desc(qapp):
    model, proxy = _build(qapp)
    proxy.set_primary(0)  # type asc
    proxy.cycle_secondary(1)  # date asc
    proxy.cycle_secondary(1)  # cycle date → desc
    assert proxy.sort_keys() == [
        (0, Qt.SortOrder.AscendingOrder),
        (1, Qt.SortOrder.DescendingOrder),
    ]
    # Equal types are date-descending — the §4.1 tuple-rejection case.
    assert _ordered_tags(model, proxy) == ["a3", "a1", "b2", "b1"]


def test_cycle_secondary_asc_desc_remove(qapp):
    _model, proxy = _build(qapp)
    proxy.set_primary(0)
    proxy.cycle_secondary(1)
    assert proxy.sort_keys()[-1] == (1, Qt.SortOrder.AscendingOrder)
    proxy.cycle_secondary(1)
    assert proxy.sort_keys()[-1] == (1, Qt.SortOrder.DescendingOrder)
    proxy.cycle_secondary(1)  # removed
    assert proxy.sort_keys() == [(0, Qt.SortOrder.AscendingOrder)]


def test_set_primary_collapses_to_one_key(qapp):
    _model, proxy = _build(qapp)
    proxy.set_primary(0)
    proxy.cycle_secondary(1)
    assert len(proxy.sort_keys()) == 2
    proxy.set_primary(1)  # plain click resets to single key
    assert proxy.sort_keys() == [(1, Qt.SortOrder.AscendingOrder)]


def test_clear_sort_returns_default(qapp):
    _model, proxy = _build(qapp)
    proxy.set_primary(1)
    proxy.cycle_secondary(0)
    proxy.clear_sort()
    assert proxy.sort_keys() == [(0, Qt.SortOrder.AscendingOrder)]


def test_stable_tiebreaker_preserves_source_order(qapp):
    # All rows tie on every key → proxy order is the identity mapping.
    rows = [{"type": "x", "date": "d", "tag": f"r{i}"} for i in range(5)]
    model, proxy = _build(qapp, rows)
    proxy.set_primary(0)
    proxy.cycle_secondary(1)
    for r in range(proxy.rowCount()):
        assert proxy.mapToSource(proxy.index(r, 0)).row() == r


def test_sort_keys_changed_emits_on_mutation(qapp):
    _model, proxy = _build(qapp)
    seen: list[int] = []
    proxy.sortKeysChanged.connect(lambda: seen.append(1))
    proxy.set_primary(0)
    proxy.cycle_secondary(1)
    proxy.clear_sort()
    assert len(seen) == 3


def test_sortbycolumn_collapses_to_single_key(qapp):
    # Direct sort(col, order) — the PI-116 single-column entry point —
    # collapses to one key with the requested direction.
    _model, proxy = _build(qapp)
    proxy.set_primary(0)
    proxy.cycle_secondary(1)
    proxy.sort(1, Qt.SortOrder.DescendingOrder)
    assert proxy.sort_keys() == [(1, Qt.SortOrder.DescendingOrder)]


def test_filter_inherited_from_base(qapp):
    # The PI-116 filter contract survives unchanged on the subclass.
    model, proxy = _build(qapp)
    proxy.setFilterKeyColumn(-1)
    proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    proxy.setFilterFixedString("2026-03-01")
    assert proxy.rowCount() == 1
    assert _ordered_tags(model, proxy) == ["a3"]

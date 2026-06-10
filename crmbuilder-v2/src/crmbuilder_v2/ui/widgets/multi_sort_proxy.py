"""MultiSortProxyModel — composite multi-column sort over a proxy.

PI-117 / WTK-068. Qt's stock ``QSortFilterProxyModel`` tracks a single
sort column, so it cannot express *type then date* ordering. This
subclass keeps an ordered list of ``(column, direction)`` keys and a
composite ``lessThan`` that walks them in priority order, ending in a
stable tiebreaker on the source row index (§3.3 of the PI-117 design).

It reads the **existing PI-116 per-column sort keys** — it invents no new
per-cell data: for each key column it compares the source model's value
under the proxy's ``sortRole()`` (``UserRole`` on the embedded
``ReferencesSection`` grid; ``DisplayRole`` on the standalone
``ReferencesPanel``), honouring that proxy's ``sortCaseSensitivity()`` for
strings. Filtering is inherited unchanged from ``QSortFilterProxyModel``,
so the PI-116 ``setFilterFixedString`` / ``setFilterKeyColumn(-1)``
contract survives — the proxy is a drop-in replacement for the stock one.

The single-column entry points are preserved: ``sort(column, order)``
(hence ``QTableView.sortByColumn`` and a plain header click) collapses the
key list to that one key, exactly the PI-116 behaviour.
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel, Qt, Signal


class MultiSortProxyModel(QSortFilterProxyModel):
    """A filter/sort proxy with an ordered list of sort keys.

    State lives in :attr:`_sort_keys` — a list of ``(column, order)``
    pairs whose order *is* the precedence (index 0 is primary). The
    :data:`sortKeysChanged` signal fires on every mutation so a
    :class:`MultiSortHeaderView` can repaint its precedence indicators.
    """

    #: Emitted whenever the sort-key list changes (add / cycle / clear /
    #: single-column sort). The header subscribes to repaint its glyphs.
    sortKeysChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._sort_keys: list[tuple[int, Qt.SortOrder]] = []

    # ------------------------------------------------------------------
    # Sort-key API
    # ------------------------------------------------------------------

    def sort_keys(self) -> list[tuple[int, Qt.SortOrder]]:
        """Return a copy of the active ``(column, order)`` key list."""
        return list(self._sort_keys)

    def set_primary(self, column: int) -> None:
        """Replace the key list with a single key on ``column``.

        If ``column`` is already the sole key, its direction toggles
        ascending → descending (the PI-116 second-click behaviour). Backs
        a plain header click.
        """
        if len(self._sort_keys) == 1 and self._sort_keys[0][0] == column:
            col, order = self._sort_keys[0]
            order = self._toggled(order)
            self._sort_keys = [(col, order)]
        else:
            self._sort_keys = [(column, Qt.SortOrder.AscendingOrder)]
        self._apply_sort()

    def cycle_secondary(self, column: int) -> None:
        """Append ``column`` as a secondary key, or cycle it if present.

        A column absent from the list is appended ascending; a present
        column cycles ascending → descending → removed, without
        disturbing the other keys. Backs a modifier (Ctrl / Shift) header
        click.
        """
        idx = self._index_of(column)
        if idx is None:
            self._sort_keys.append((column, Qt.SortOrder.AscendingOrder))
        else:
            col, order = self._sort_keys[idx]
            if order == Qt.SortOrder.AscendingOrder:
                self._sort_keys[idx] = (col, Qt.SortOrder.DescendingOrder)
            else:
                self._sort_keys.pop(idx)
        self._apply_sort()

    def clear_sort(self) -> None:
        """Reset to the deterministic default: column 0, ascending."""
        self._sort_keys = [(0, Qt.SortOrder.AscendingOrder)]
        self._apply_sort()

    # ------------------------------------------------------------------
    # Single-column entry point (sortByColumn / header-driven sort)
    # ------------------------------------------------------------------

    def sort(  # noqa: A003 (Qt override)
        self,
        column: int,
        order: Qt.SortOrder = Qt.SortOrder.AscendingOrder,
    ) -> None:
        """Single-column sort — collapses the key list to one key.

        Called by ``QTableView.sortByColumn`` and any direct
        ``proxy.sort(col)``. ``column < 0`` clears all keys (source
        order). This keeps the PI-116 single-column contract intact while
        the multi-key API drives richer orderings.
        """
        if column is None or column < 0:
            self._sort_keys = []
            super().sort(-1)
            self.sortKeysChanged.emit()
            return
        self._sort_keys = [(int(column), Qt.SortOrder(order))]
        self._apply_sort()

    # ------------------------------------------------------------------
    # Comparator
    # ------------------------------------------------------------------

    def lessThan(  # noqa: N802 (Qt override)
        self, left: QModelIndex, right: QModelIndex
    ) -> bool:
        """Composite comparison over the active key list.

        Walks the keys in precedence order; the first column on which the
        two rows differ decides, honouring that key's own direction. Rows
        equal on every key fall back to the source row index so the order
        is stable and idempotent (§3.3).
        """
        src = self.sourceModel()
        role = self.sortRole()
        left_row = left.row()
        right_row = right.row()
        for column, order in self._sort_keys:
            lval = src.data(src.index(left_row, column), role)
            rval = src.data(src.index(right_row, column), role)
            cmp = self._compare(lval, rval)
            if cmp == 0:
                continue
            ascending = cmp < 0
            if order == Qt.SortOrder.AscendingOrder:
                return ascending
            return not ascending
        # Stable tiebreaker: preserve the source (flatten) order.
        return left_row < right_row

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _compare(self, lval, rval) -> int:
        """Return -1/0/1 for ``lval`` vs ``rval`` with a total order.

        ``None`` sorts last (greater) so missing values trail in ascending
        order, mirroring the ``"￿"`` sentinel the PI-116 grid model
        already emits. Strings compare case-insensitively when the proxy's
        ``sortCaseSensitivity`` is insensitive.
        """
        if lval is None and rval is None:
            return 0
        if lval is None:
            return 1
        if rval is None:
            return -1
        if (
            isinstance(lval, str)
            and isinstance(rval, str)
            and self.sortCaseSensitivity()
            == Qt.CaseSensitivity.CaseInsensitive
        ):
            lval = lval.lower()
            rval = rval.lower()
        if lval == rval:
            return 0
        try:
            return -1 if lval < rval else 1
        except TypeError:
            # Mixed, non-orderable types: fall back to string compare.
            ls, rs = str(lval), str(rval)
            if ls == rs:
                return 0
            return -1 if ls < rs else 1

    def _apply_sort(self) -> None:
        """Re-run the sort and notify the header.

        ``super().sort(-1)`` then a fresh ``super().sort(...)`` forces Qt
        to re-evaluate ``lessThan`` even when only a secondary key changed
        (the primary column is unchanged, which Qt would otherwise treat
        as a no-op). The proxy is always asked to sort **ascending** — all
        per-key direction lives inside ``lessThan``, so Qt must not also
        reverse.
        """
        primary_col = self._sort_keys[0][0] if self._sort_keys else 0
        super().sort(-1)
        super().sort(primary_col, Qt.SortOrder.AscendingOrder)
        self.sortKeysChanged.emit()

    def _index_of(self, column: int) -> int | None:
        for i, (col, _order) in enumerate(self._sort_keys):
            if col == column:
                return i
        return None

    @staticmethod
    def _toggled(order: Qt.SortOrder) -> Qt.SortOrder:
        if order == Qt.SortOrder.AscendingOrder:
            return Qt.SortOrder.DescendingOrder
        return Qt.SortOrder.AscendingOrder

"""GroupingTreeModel — a two-level group-by tree over ordered rows.

PI-117 / WTK-068. A flat ``QTableView`` cannot render group headers, so
when a group key is active the link panels swap to a ``QTreeView`` over
this model (§3.6 of the PI-117 design). It is a thin two-level tree:

- **Top level** — one *group node* per distinct key value, labelled
  ``"<value> (<n>)"`` (the key plus its child count) in column 0.
- **Children** — the matching reference rows, rendering identical cells
  to the flat table via a host-supplied ``cell_display(row, column)``.

The model is built from an **already-ordered** row list (read out of the
:class:`MultiSortProxyModel`), so the active multi-column sort is
preserved *within* each group: rows are bucketed preserving arrival order
(§3.7-1). Group nodes themselves are ordered ascending by key value, with
the ``"(none)"`` bucket always last (§3.7-2). The host rebuilds the model
(via :meth:`set_rows`) whenever the group key or the filtered/sorted set
changes.

Keeping grouping in a dedicated model — rather than inside the proxy —
means the *(none)* path is untouched: the flat table + proxy stay exactly
as PI-116 shipped.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt
from PySide6.QtGui import QFont

#: Bucket label for rows whose group key is missing/empty; always sorts
#: last, mirroring the missing-value rule used elsewhere.
NONE_GROUP = "(none)"

# internalId convention: a top-level group node carries id 0; a child row
# carries (group_index + 1) so :meth:`parent` can recover its group.
_GROUP_ID = 0


class GroupingTreeModel(QAbstractItemModel):
    """Two-level tree: group nodes over their member reference rows.

    :param rows: the row dicts in **final sorted order**.
    :param headers: column header strings (parallel to ``cell_display``'s
        column index).
    :param group_of: ``row -> str`` group-key function; return
        :data:`NONE_GROUP` (or an empty string) for the missing bucket.
    :param cell_display: ``(row, column) -> str`` producing the same
        display string the flat table shows for that cell.
    """

    def __init__(
        self,
        rows: list[dict[str, Any]],
        headers: list[str],
        group_of: Callable[[dict[str, Any]], str],
        cell_display: Callable[[dict[str, Any], int], Any],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._headers = list(headers)
        self._group_of = group_of
        self._cell_display = cell_display
        self._groups: list[dict[str, Any]] = []
        self._rebuild(rows)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        """Rebuild the tree from a fresh ordered row list."""
        self.beginResetModel()
        self._rebuild(rows)
        self.endResetModel()

    def group_count(self) -> int:
        return len(self._groups)

    def child_count(self, group_index: int) -> int:
        if 0 <= group_index < len(self._groups):
            return len(self._groups[group_index]["rows"])
        return 0

    def group_label(self, group_index: int) -> str:
        """Return the rendered ``"<value> (<n>)"`` label for a group."""
        group = self._groups[group_index]
        return f"{group['value']} ({len(group['rows'])})"

    def is_group_index(self, index: QModelIndex) -> bool:
        return index.isValid() and index.internalId() == _GROUP_ID

    def row_dict(self, index: QModelIndex) -> dict[str, Any] | None:
        """Return the underlying row dict for a child index (else ``None``).

        Group-node indices return ``None`` so navigation / delete map only
        through real reference rows, exactly as the flat-table path does.
        """
        if not index.isValid() or index.internalId() == _GROUP_ID:
            return None
        group_index = index.internalId() - 1
        rows = self._groups[group_index]["rows"]
        if 0 <= index.row() < len(rows):
            return rows[index.row()]
        return None

    # ------------------------------------------------------------------
    # QAbstractItemModel
    # ------------------------------------------------------------------

    def index(  # noqa: A003 (Qt override)
        self, row: int, column: int, parent: QModelIndex | None = None
    ) -> QModelIndex:
        parent = parent if parent is not None else QModelIndex()
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        if not parent.isValid():
            # Top-level group node.
            return self.createIndex(row, column, _GROUP_ID)
        # Child of the group node at parent.row().
        return self.createIndex(row, column, parent.row() + 1)

    def parent(self, index: QModelIndex) -> QModelIndex:  # noqa: A003
        if not index.isValid():
            return QModelIndex()
        internal = index.internalId()
        if internal == _GROUP_ID:
            return QModelIndex()
        group_index = internal - 1
        return self.createIndex(group_index, 0, _GROUP_ID)

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        parent = parent if parent is not None else QModelIndex()
        if not parent.isValid():
            return len(self._groups)
        if parent.internalId() == _GROUP_ID:
            return len(self._groups[parent.row()]["rows"])
        return 0

    def columnCount(self, _parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self._headers)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if index.internalId() == _GROUP_ID:
            # Group node: label in column 0, bold; nothing elsewhere.
            if index.column() != 0:
                return None
            if role == Qt.ItemDataRole.DisplayRole:
                return self.group_label(index.row())
            if role == Qt.ItemDataRole.FontRole:
                font = QFont()
                font.setBold(True)
                return font
            return None
        # Child row.
        if role == Qt.ItemDataRole.DisplayRole:
            row = self.row_dict(index)
            if row is None:
                return None
            return self._cell_display(row, index.column())
        return None

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(self._headers)
        ):
            return self._headers[section]
        return None

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _rebuild(self, rows: list[dict[str, Any]]) -> None:
        buckets: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            key = self._group_of(row)
            if not key:
                key = NONE_GROUP
            buckets.setdefault(key, []).append(row)
        named = sorted(
            (k for k in buckets if k != NONE_GROUP), key=lambda s: s.lower()
        )
        if NONE_GROUP in buckets:
            named.append(NONE_GROUP)
        self._groups = [{"value": k, "rows": buckets[k]} for k in named]

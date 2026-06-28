"""Native Qt models for the redesigned reconciliation surface — PI-333 (REL-027).

Two custom item models back the redesigned operator surface, both fed directly
from the extended ``GET /reconcile/compare`` payload (PI-331):

- :class:`ExistenceGridModel` — a ``QAbstractTableModel`` for the landing grid,
  one row per entity with a cell per location (the design + each instance) showing
  whether the entity is present, missing, or never audited there (REQ-368).
- :class:`EntityDetailModel` — a ``QAbstractItemModel`` two-level tree for the
  drill: the six object-type groups (Fields / Layouts / Relationships / Formulas /
  Settings / Other), each collapsible and showing how many of its rows differ,
  over the difference rows underneath (REQ-370).

Both speak **operator language** — no "presence", "capture", "publish", or "kind"
appears in any visible label (REQ-374) — and colour location/state cells while
*always* carrying a text label, so the surface is never colour-only (REQ-368).
Grid lines, alternating row colours, and virtualization are view properties set
by the host panel (REQ-373); these models stay pure data so they unit-test
without a window.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractItemModel, QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor, QFont

#: Presence tokens carried by the compare payload (engine vocabulary).
PRESENT = "present"
ABSENT = "absent"
UNKNOWN = "unknown"

#: Operator-language label for each presence token (REQ-374) — "In" / "Missing" /
#: "n/a" rather than present/absent/unknown. The text always accompanies the
#: colour so a cell is never colour-only (REQ-368).
STATE_LABELS = {PRESENT: "In", ABSENT: "Missing", UNKNOWN: "n/a"}

#: Background colour per state (soft, label always present alongside it).
_STATE_BG = {
    PRESENT: QColor("#E8F5E9"),   # green-tint: here
    ABSENT: QColor("#FFEBEE"),    # red-tint: missing
    UNKNOWN: QColor("#F5F5F5"),   # grey: never audited
}
_STATE_FG = {
    PRESENT: QColor("#2E7D32"),
    ABSENT: QColor("#C62828"),
    UNKNOWN: QColor("#9E9E9E"),
}

#: Operator-language heading for each object-type group (REQ-370/374).
OBJECT_GROUP_LABELS = {
    "fields": "Fields",
    "layouts": "Layouts",
    "relations": "Relationships",
    "formulas": "Formulas",
    "settings": "Settings",
    "other": "Other",
}

#: Role carrying the raw presence/state token for cell colouring/inspection.
STATE_ROLE = Qt.ItemDataRole.UserRole + 1
#: Role carrying the backing payload dict (existence row, group, or diff row).
RECORD_ROLE = Qt.ItemDataRole.UserRole + 2


def fmt_value(value: Any) -> str:
    """Render a difference-cell value in operator language.

    Presence tokens become "In" / "Missing" / "n/a"; ``None`` becomes an em dash;
    a list is comma-joined; everything else is its string form.
    """
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value) if value else "—"
    if isinstance(value, str) and value in STATE_LABELS:
        return STATE_LABELS[value]
    return str(value)


class ExistenceGridModel(QAbstractTableModel):
    """One row per entity × one column per location for the landing grid (REQ-368).

    Columns are **Entity**, **Master design**, then one per instance (labelled
    with the chosen instances). Each location cell shows In / Missing / n/a with a
    matching soft background; the entity column shows the entity's name (and its
    friendly label when distinct).
    """

    def __init__(
        self,
        rows: list[dict[str, Any]] | None = None,
        *,
        instance_a_label: str = "Instance A",
        instance_b_label: str = "Instance B",
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = list(rows or [])
        self._headers = ["Entity", "Master design", instance_a_label, instance_b_label]
        # column index -> existence-row key holding that location's state token
        self._loc_key = {1: "design", 2: "instance_a", 3: "instance_b"}

    def set_rows(
        self,
        rows: list[dict[str, Any]],
        *,
        instance_a_label: str | None = None,
        instance_b_label: str | None = None,
    ) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        if instance_a_label is not None:
            self._headers[2] = instance_a_label
        if instance_b_label is not None:
            self._headers[3] = instance_b_label
        self.endResetModel()

    # -- Qt model API --------------------------------------------------------
    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        parent = parent if parent is not None else QModelIndex()
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self._headers)

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(self._headers)
        ):
            return self._headers[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = index.column()
        if col == 0:
            if role == Qt.ItemDataRole.DisplayRole:
                name = row.get("entity") or row.get("entity_identifier") or "?"
                label = row.get("entity_label")
                return f"{name}  ·  {label}" if label and label != name else name
            if role == RECORD_ROLE:
                return row
            return None
        state = row.get(self._loc_key[col])
        if role == Qt.ItemDataRole.DisplayRole:
            return STATE_LABELS.get(state, fmt_value(state))
        if role == STATE_ROLE:
            return state
        if role == Qt.ItemDataRole.BackgroundRole:
            return _STATE_BG.get(state)
        if role == Qt.ItemDataRole.ForegroundRole:
            return _STATE_FG.get(state)
        if role == RECORD_ROLE:
            return row
        return None


# internalId convention (mirrors GroupingTreeModel): a top-level group node
# carries id 0; a child diff row carries (group_index + 1) so parent() recovers
# its group.
_GROUP_ID = 0


class EntityDetailModel(QAbstractItemModel):
    """Two-level tree over one entity's grouped differences (REQ-370).

    Top level: one node per object-type group present, labelled
    ``"Fields (2 differ)"`` etc. Children: the difference rows, each showing a
    plain label and the value in the design and each instance, with presence
    cells coloured (text label always present).
    """

    HEADERS = ["Difference", "Master design", "Instance A", "Instance B"]

    def __init__(
        self,
        object_groups: list[dict[str, Any]] | None = None,
        *,
        instance_a_label: str = "Instance A",
        instance_b_label: str = "Instance B",
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._groups: list[dict[str, Any]] = list(object_groups or [])
        self._headers = list(self.HEADERS)
        self._headers[2] = instance_a_label
        self._headers[3] = instance_b_label

    def set_groups(
        self,
        object_groups: list[dict[str, Any]],
        *,
        instance_a_label: str | None = None,
        instance_b_label: str | None = None,
    ) -> None:
        self.beginResetModel()
        self._groups = list(object_groups)
        if instance_a_label is not None:
            self._headers[2] = instance_a_label
        if instance_b_label is not None:
            self._headers[3] = instance_b_label
        self.endResetModel()

    # -- tree structure ------------------------------------------------------
    def index(
        self, row: int, column: int, parent: QModelIndex | None = None
    ) -> QModelIndex:
        parent = parent if parent is not None else QModelIndex()
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        if not parent.isValid():
            return self.createIndex(row, column, _GROUP_ID)
        return self.createIndex(row, column, parent.row() + 1)

    def parent(self, index: QModelIndex) -> QModelIndex:  # noqa: N802
        if not index.isValid():
            return QModelIndex()
        gid = index.internalId()
        if gid == _GROUP_ID:
            return QModelIndex()
        return self.createIndex(gid - 1, 0, _GROUP_ID)

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        parent = parent if parent is not None else QModelIndex()
        if not parent.isValid():
            return len(self._groups)
        if parent.internalId() == _GROUP_ID:
            return len(self._groups[parent.row()].get("rows", []))
        return 0

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self._headers)

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(self._headers)
        ):
            return self._headers[section]
        return None

    # -- data ----------------------------------------------------------------
    @staticmethod
    def _row_label(r: dict[str, Any]) -> str:
        label = r.get("member_name") or r.get("member_identifier") or "?"
        attr = r.get("attribute")
        if attr:
            label = f"{label} · {_humanize_attr(attr)}"
        return label

    def _group_for(self, index: QModelIndex) -> dict[str, Any]:
        gid = index.internalId()
        gi = index.row() if gid == _GROUP_ID else gid - 1
        return self._groups[gi]

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        col = index.column()
        if index.internalId() == _GROUP_ID:  # a group header
            grp = self._groups[index.row()]
            if role == Qt.ItemDataRole.DisplayRole and col == 0:
                label = OBJECT_GROUP_LABELS.get(grp["object_type"], grp["object_type"].title())
                return f"{label}  ({grp.get('differing_count', 0)} differ)"
            if role == Qt.ItemDataRole.FontRole and col == 0:
                f = QFont()
                f.setBold(True)
                return f
            if role == RECORD_ROLE and col == 0:
                return grp
            return None
        # a difference row
        grp = self._group_for(index)
        r = grp.get("rows", [])[index.row()]
        if role == RECORD_ROLE:
            return r
        if col == 0:
            if role == Qt.ItemDataRole.DisplayRole:
                return self._row_label(r)
            return None
        key = {1: "design", 2: "instance_a", 3: "instance_b"}[col]
        value = r.get(key)
        if role == Qt.ItemDataRole.DisplayRole:
            return fmt_value(value)
        if role == STATE_ROLE:
            return value if value in STATE_LABELS else None
        if role == Qt.ItemDataRole.BackgroundRole and value in _STATE_BG:
            return _STATE_BG[value]
        if role == Qt.ItemDataRole.ForegroundRole and value in _STATE_FG:
            return _STATE_FG[value]
        return None


#: The three reconciliation locations, in display order.
LOCATIONS = ("design", "instance_a", "instance_b")
#: Operator-language label for each location key.
LOCATION_LABELS = {
    "design": "Master design",
    "instance_a": "Instance A",
    "instance_b": "Instance B",
}


def plan_apply(
    row: dict[str, Any], source_loc: str, target_locs: list[str]
) -> dict[str, Any]:
    """Route one difference into capture/publish operations (REQ-371).

    Given the difference ``row`` (a compare attribute/presence row), the location
    holding the **correct** value, and the locations to bring into line, returns
    the ordered operations and any targets skipped (already matching, or the row
    is not reconcilable). The **design is the hub**: writing into the design is a
    capture; writing into an instance is a publish; an instance→instance move is a
    capture into the design followed by a publish out — never a direct
    instance-to-instance write.

    Operations reference *locations* (``design`` / ``instance_a`` / ``instance_b``);
    the panel resolves each to a concrete instance and member before calling the
    API. Pure logic, so the routing is unit-tested without a window or a network.

    :returns: ``{"ops": [{"kind": "capture"|"publish", "location": <loc>}],
        "skipped": [<reason str>]}``.
    """
    if not row.get("actionable"):
        return {"ops": [], "skipped": ["not reconcilable here — configure by hand"]}

    design_value = row.get("design")
    source_value = row.get(source_loc)
    targets = [t for t in target_locs if t != source_loc]
    ops: list[dict[str, str]] = []
    skipped: list[str] = []

    # A capture is needed only when the source is an instance whose value the
    # design does not already hold. After it, the design carries the chosen value.
    capture_needed = source_loc != "design" and source_value != design_value
    effective = source_value if capture_needed else design_value
    if capture_needed:
        ops.append({"kind": "capture", "location": source_loc})
    elif source_loc != "design" and "design" in targets:
        skipped.append(f"{LOCATION_LABELS['design']} already matches the chosen value")

    for t in targets:
        if t == "design":
            continue  # served by the capture above (or already matching)
        if row.get(t) == effective:
            skipped.append(f"{LOCATION_LABELS.get(t, t)} already matches the chosen value")
            continue
        ops.append({"kind": "publish", "location": t})

    return {"ops": ops, "skipped": skipped}


def _humanize_attr(attribute: str) -> str:
    """Turn a neutral attribute name into a readable label (REQ-374).

    ``field_max_length`` -> "Max length"; ``entity_default_sort_field`` -> "Default
    sort field". The leading ``field_`` / ``entity_`` namespace is dropped.
    """
    for prefix in ("field_", "entity_", "layout_", "association_"):
        if attribute.startswith(prefix):
            attribute = attribute[len(prefix):]
            break
    words = attribute.replace("_", " ").strip()
    return words[:1].upper() + words[1:] if words else attribute

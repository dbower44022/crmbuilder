"""Native Qt models for the redesigned reconciliation surface — PI-333 (REL-027).

Two custom item models back the redesigned operator surface, both fed directly
from the extended ``GET /reconcile/compare`` payload (PI-331):

- :class:`ExistenceGridModel` — a ``QAbstractTableModel`` for the landing grid,
  one row per entity with a cell per location (the design + each instance) showing
  whether the entity is Present, Not Found, or Not Captured there (REQ-368/434).
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

from crmbuilder_v2.access.reconcile_compare import (
    FIELD_OPTIONS_ATTR,
    normalize_option_set,
    option_sets_equal,
    summarize_option_diff,
)

#: Presence tokens carried by the compare payload (engine vocabulary).
PRESENT = "present"
ABSENT = "absent"
UNKNOWN = "unknown"

#: Operator-language label for each presence token (REQ-374/REQ-434). The three
#: states are deliberately distinct and glossary-defined:
#:   - ``present``  -> "Present"     — the member is carried on that location.
#:   - ``absent``   -> "Not Found"   — a member whose location was read and the
#:     member is confirmed not there (it has an absent membership record).
#:   - ``unknown``  -> "Not Captured" — there is no membership record for the
#:     member at that location; it has not been captured by an audit there.
#: "Not Captured" (REQ-434) replaces the earlier "Not audited" (REQ-390), whose
#: word collided with the "Audit" process step; "Not Found" replaces "Missing".
#: The text always accompanies the colour so a cell is never colour-only (REQ-368).
STATE_LABELS = {PRESENT: "Present", ABSENT: "Not Found", UNKNOWN: "Not Captured"}

#: Background colour per state (soft, label always present alongside it).
_STATE_BG = {
    PRESENT: QColor("#E8F5E9"),   # green-tint: here
    ABSENT: QColor("#FFEBEE"),    # red-tint: not found
    UNKNOWN: QColor("#F5F5F5"),   # grey: not captured
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

    Presence tokens become "Present" / "Not Found" / "Not Captured"; ``None`` -> em dash;
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


def fmt_option_list(value: Any) -> str:
    """Render an enum option set as a readable value list (REQ-442).

    Each option shows its value, with the display label in parentheses when it
    differs from the value: ``"active, closed (Closed out)"``. Empty -> em dash.
    """
    pairs = sorted(normalize_option_set(value))
    if not pairs:
        return "—"
    return ", ".join(v if v == lbl else f"{v} ({lbl})" for v, lbl in pairs)


def fmt_option_delta(design: Any, instance: Any) -> str:
    """Render how an instance's option set differs from the design (REQ-442).

    ``+value`` added, ``−value`` removed, ``~value (old → new)`` relabeled — far
    clearer than two raw lists side by side. Returns "Same options" when the sets
    match (the in-sync confirmation case).
    """
    diff = summarize_option_diff(design, instance)
    parts = [f"+{v}" for v in diff["added"]]
    parts += [f"−{v}" for v in diff["removed"]]
    parts += [f"~{v} ({old} → {new})" for v, old, new in diff["relabeled"]]
    return ", ".join(parts) if parts else "Same options"


class ExistenceGridModel(QAbstractTableModel):
    """One row per entity × one column per location for the landing grid (REQ-368).

    Columns are **Entity**, **Master design**, then one per instance (labelled
    with the chosen instances). Each location cell shows Present / Not Found / Not Captured with a
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


_COL_KEYS = {1: "design", 2: "instance_a", 3: "instance_b"}

#: Display text for an enum option that the field carries here but that does not
#: include this value, vs. carries it: rendered in the value columns of an option
#: child row (REQ-442). A field not carried at all shows its presence token instead.
_OPTION_PRESENT = PRESENT  # value is in this location's option set
_OPTION_MISSING = ABSENT   # field is here but this value is not in its set


def option_child_rows(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand an enum option-set difference row into one child per option value (REQ-442).

    Each child is scannable like a field under an entity: column 0 is the option
    value, and each location column shows the value's effective label where it is
    present, "Not present" where the field is carried but lacks the value, or the
    field's presence token where the field is not carried there at all. The union
    of values across the design and both instances is listed, sorted by value.

    ``RECORD_ROLE`` for a child resolves to the *parent* field row (via
    ``_parent_row``) so selecting or double-clicking a value acts on the field's
    whole option set — capturing/publishing a single option is not a separate
    operation.
    """
    locs = ("design", "instance_a", "instance_b")
    raw = {k: row.get(k) for k in locs}
    sets: dict[str, dict[str, str] | None] = {
        k: dict(normalize_option_set(v)) if isinstance(v, (list, tuple)) else None
        for k, v in raw.items()
    }
    values = sorted({val for m in sets.values() if m is not None for val in m})
    children: list[dict[str, Any]] = []
    for val in values:
        cells: dict[str, dict[str, str]] = {}
        for k in locs:
            m = sets[k]
            if m is None:  # the field is not carried here at all
                token = raw[k] if isinstance(raw[k], str) else UNKNOWN
                cells[k] = {"state": token, "text": STATE_LABELS.get(token, fmt_value(token))}
            elif val in m:
                cells[k] = {"state": _OPTION_PRESENT, "text": m[val]}
            else:
                cells[k] = {"state": _OPTION_MISSING, "text": "Not present"}
        children.append({
            "option_value": val,
            "attribute": FIELD_OPTIONS_ATTR,
            "_cells": cells,
            "_parent_row": row,
        })
    return children


def _is_option_parent(row: dict[str, Any]) -> bool:
    """Whether a difference row should expand into per-option child rows (REQ-442)."""
    if row.get("attribute") != FIELD_OPTIONS_ATTR:
        return False
    return any(isinstance(row.get(k), (list, tuple)) for k in _COL_KEYS.values())


class EntityDetailModel(QAbstractItemModel):
    """Tree over one entity's grouped differences (REQ-370, REQ-442).

    Top level: one node per object-type group present, labelled
    ``"Fields (2 differ)"`` etc. Second level: the difference rows, each showing a
    plain label and the value in the design and each instance, presence cells
    coloured (text label always present). Third level (REQ-442): an enum field's
    option-set difference row expands into one child per option value, so the
    operator scans the values exactly as they scan the fields — rather than reading
    a long comma-joined list jammed into a single cell.

    Backed by a flat node registry: ``createIndex`` carries each node's integer
    index in :attr:`_nodes`, so an arbitrary-depth tree resolves parents and rows
    without pointer-lifetime hazards.
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
        self._headers = list(self.HEADERS)
        self._headers[2] = instance_a_label
        self._headers[3] = instance_b_label
        self._build(object_groups or [])

    def _build(self, object_groups: list[dict[str, Any]]) -> None:
        """(Re)build the node registry from the grouped difference payload."""
        # each node: {"kind", "payload", "parent" (node id|None), "row" (row in
        # parent), "children" (node ids)}
        self._nodes: list[dict[str, Any]] = []
        self._roots: list[int] = []

        def add(kind: str, payload: Any, parent: int | None) -> int:
            nid = len(self._nodes)
            siblings = self._roots if parent is None else self._nodes[parent]["children"]
            node = {"kind": kind, "payload": payload, "parent": parent,
                    "row": len(siblings), "children": []}
            self._nodes.append(node)
            siblings.append(nid)
            return nid

        for grp in object_groups:
            gid = add("group", grp, None)
            for r in grp.get("rows", []):
                rid = add("row", r, gid)
                if _is_option_parent(r):
                    for child in option_child_rows(r):
                        add("option", child, rid)

    def set_groups(
        self,
        object_groups: list[dict[str, Any]],
        *,
        instance_a_label: str | None = None,
        instance_b_label: str | None = None,
    ) -> None:
        self.beginResetModel()
        if instance_a_label is not None:
            self._headers[2] = instance_a_label
        if instance_b_label is not None:
            self._headers[3] = instance_b_label
        self._build(object_groups)
        self.endResetModel()

    # -- tree structure ------------------------------------------------------
    def index(
        self, row: int, column: int, parent: QModelIndex | None = None
    ) -> QModelIndex:
        parent = parent if parent is not None else QModelIndex()
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        siblings = self._roots if not parent.isValid() else self._nodes[parent.internalId()]["children"]
        if row >= len(siblings):
            return QModelIndex()
        return self.createIndex(row, column, siblings[row])

    def parent(self, index: QModelIndex) -> QModelIndex:  # noqa: N802
        if not index.isValid():
            return QModelIndex()
        pid = self._nodes[index.internalId()]["parent"]
        if pid is None:
            return QModelIndex()
        return self.createIndex(self._nodes[pid]["row"], 0, pid)

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        parent = parent if parent is not None else QModelIndex()
        if not parent.isValid():
            return len(self._roots)
        return len(self._nodes[parent.internalId()]["children"])

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

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        node = self._nodes[index.internalId()]
        kind = node["kind"]
        if kind == "group":
            return self._group_data(node["payload"], index.column(), role)
        if kind == "option":
            return self._option_data(node["payload"], index.column(), role)
        return self._row_data(node["payload"], index.column(), role)

    @staticmethod
    def _group_data(grp: dict[str, Any], col: int, role: int):
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

    def _row_data(self, r: dict[str, Any], col: int, role: int):
        if role == RECORD_ROLE:
            return r
        if col == 0:
            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
                return self._row_label(r)
            return None
        key = _COL_KEYS[col]
        value = r.get(key)
        # REQ-442: an enum option-set parent row carries its values as child nodes,
        # so its own value columns show only a compact count (or the presence token
        # when the field is absent there) — never the long list that made the cell
        # unreadable.
        if _is_option_parent(r):
            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
                if isinstance(value, (list, tuple)):
                    n = len(normalize_option_set(value))
                    return f"{n} option" if n == 1 else f"{n} options"
                return fmt_value(value)
            is_state = isinstance(value, str)
            if role == STATE_ROLE:
                return value if (is_state and value in STATE_LABELS) else None
            if role == Qt.ItemDataRole.BackgroundRole and is_state and value in _STATE_BG:
                return _STATE_BG[value]
            if role == Qt.ItemDataRole.ForegroundRole and is_state and value in _STATE_FG:
                return _STATE_FG[value]
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return fmt_value(value)
        # The value columns share the viewport and elide (REQ-429); expose the full
        # text on hover so an elided layout payload is never lost.
        if role == Qt.ItemDataRole.ToolTipRole:
            return fmt_value(value)
        # State tokens are always strings; a list/dict cell value (e.g. a layout
        # or relationship payload) is unhashable, so never probe the state maps
        # with it — doing so raises ``TypeError: unhashable type`` inside the
        # Qt override and cascades as index/parent errors.
        is_state = isinstance(value, str)
        if role == STATE_ROLE:
            return value if (is_state and value in STATE_LABELS) else None
        if role == Qt.ItemDataRole.BackgroundRole and is_state and value in _STATE_BG:
            return _STATE_BG[value]
        if role == Qt.ItemDataRole.ForegroundRole and is_state and value in _STATE_FG:
            return _STATE_FG[value]
        return None

    @staticmethod
    def _option_data(child: dict[str, Any], col: int, role: int):
        # An option value scans like a field: col 0 is the value, each location
        # column shows the value's label where present, "Not present" where the
        # field lacks it, or the field's presence token where it is not carried.
        if role == RECORD_ROLE:
            return child["_parent_row"]
        if col == 0:
            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
                return child["option_value"]
            return None
        cell = child["_cells"][_COL_KEYS[col]]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return cell["text"]
        state = cell["state"]
        if role == STATE_ROLE:
            return state if state in STATE_LABELS else None
        if role == Qt.ItemDataRole.BackgroundRole:
            return _STATE_BG.get(state)
        if role == Qt.ItemDataRole.ForegroundRole:
            return _STATE_FG.get(state)
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

    # Relationships route differently from value attributes (REQ-443): a missing
    # link is publish-only; a cardinality difference is capture-only.
    if row.get("member_type") == "association":
        return _plan_association(row, source_loc, target_locs)

    design_value = row.get("design")
    source_value = row.get(source_loc)
    targets = [t for t in target_locs if t != source_loc]
    ops: list[dict[str, str]] = []
    skipped: list[str] = []

    # Value equality is option-aware for an enum option-set row (REQ-442) so an
    # order- or label-default-only difference in the raw lists doesn't force a
    # redundant capture/publish; every other attribute compares by ``==``.
    def _eq(a: Any, b: Any) -> bool:
        if row.get("attribute") == FIELD_OPTIONS_ATTR:
            return option_sets_equal(a, b)
        return a == b

    # A capture is needed only when the source is an instance whose value the
    # design does not already hold. After it, the design carries the chosen value.
    capture_needed = source_loc != "design" and not _eq(source_value, design_value)
    effective = source_value if capture_needed else design_value
    if capture_needed:
        ops.append({"kind": "capture", "location": source_loc})
    elif source_loc != "design" and "design" in targets:
        skipped.append(f"{LOCATION_LABELS['design']} already matches the chosen value")

    for t in targets:
        if t == "design":
            continue  # served by the capture above (or already matching)
        if _eq(row.get(t), effective):
            skipped.append(f"{LOCATION_LABELS.get(t, t)} already matches the chosen value")
            continue
        ops.append({"kind": "publish", "location": t})

    return {"ops": ops, "skipped": skipped}


def _plan_association(
    row: dict[str, Any], source_loc: str, target_locs: list[str]
) -> dict[str, Any]:
    """Route a relationship difference into capture/publish ops (REQ-443).

    Two direction-limited cases (Decisions 1 & 2):

    - **Missing link** (a *presence* row): the design defines the relationship and
      an instance lacks it — publish it to that instance (creating the link).
      Publishing to the design is meaningless (it already has it); a target that
      already carries the link is skipped.
    - **Cardinality drift** (an *attribute* row): capture the instance's
      cardinality into the design. The deploy engine cannot alter an existing
      link's cardinality, so a publish *to* an instance stays view-only and is
      reported as a configure-by-hand skip — never silently attempted.
    """
    targets = [t for t in target_locs if t != source_loc]
    ops: list[dict[str, str]] = []
    skipped: list[str] = []

    if row.get("kind") == "attribute":  # cardinality drift — capture only
        for t in targets:
            if t == "design":
                # design is a target only when an instance is the source (it is
                # filtered out when it is itself the source), so the capture source
                # is always an instance here.
                ops.append({"kind": "capture", "location": source_loc})
            else:
                skipped.append(
                    f"{LOCATION_LABELS.get(t, t)}: changing an existing link's "
                    "cardinality must be done by hand in the admin console"
                )
        return {"ops": ops, "skipped": skipped}

    # Missing link (presence) — publish the design's relationship to instances
    # that lack it; source is irrelevant (publish is always design → instance).
    for t in targets:
        if t == "design":
            skipped.append("the design already defines this relationship")
            continue
        if row.get(t) == PRESENT:
            skipped.append(f"{LOCATION_LABELS.get(t, t)} already has this relationship")
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

"""Work item mapping for Impact Analysis.

Implements L2 PRD Section 12.8.1 — maps flagged ChangeImpact records to
the work item that "owns" the affected record. When multiple flagged
impacts map to the same work item, groups them with count and summary.

Ownership rules follow the schema's scoping structure:
- Field, FieldOption → entity_prd work item (matching entity_id)
- Process, ProcessStep, Requirement, ProcessEntity, ProcessField,
  ProcessPersona → process_definition work item (matching process_id)
- Persona → master_prd work item
- LayoutPanel, LayoutRow, LayoutTab, ListColumn → entity_prd (matching entity_id)
- Domain → domain_overview work item (matching domain_id)
- Relationship → entity_prd work items for BOTH entities involved
"""

from __future__ import annotations

import dataclasses
import sqlite3


@dataclasses.dataclass
class AffectedWorkItem:
    """A work item affected by one or more ChangeImpact records."""

    work_item_id: int
    item_type: str
    domain_id: int | None
    entity_id: int | None
    process_id: int | None
    status: str
    impact_count: int
    impact_summaries: list[str]


def get_affected_work_items(
    conn: sqlite3.Connection,
    change_impact_ids: list[int],
) -> list[AffectedWorkItem]:
    """Group ChangeImpact records by their owning work item.

    :param conn: Open client database connection.
    :param change_impact_ids: ChangeImpact.id values to map.
    :returns: List of AffectedWorkItem, one per unique work item.
    """
    if not change_impact_ids:
        return []

    ph = ",".join("?" * len(change_impact_ids))
    impacts = conn.execute(
        f"SELECT id, affected_table, affected_record_id, impact_description "  # noqa: S608
        f"FROM ChangeImpact WHERE id IN ({ph})",
        change_impact_ids,
    ).fetchall()

    # Map each impact to work item id(s)
    wi_map: dict[int, list[tuple[int, str]]] = {}  # wi_id -> [(ci_id, desc)]

    for ci_id, table, record_id, desc in impacts:
        wi_ids = _find_owning_work_items(conn, table, record_id)
        for wi_id in wi_ids:
            wi_map.setdefault(wi_id, []).append((ci_id, desc))

    # Build results with work item details
    results: list[AffectedWorkItem] = []
    for wi_id, entries in wi_map.items():
        row = conn.execute(
            "SELECT item_type, domain_id, entity_id, process_id, status "
            "FROM WorkItem WHERE id = ?",
            (wi_id,),
        ).fetchone()
        if not row:
            continue
        results.append(
            AffectedWorkItem(
                work_item_id=wi_id,
                item_type=row[0],
                domain_id=row[1],
                entity_id=row[2],
                process_id=row[3],
                status=row[4],
                impact_count=len(entries),
                impact_summaries=[desc for _, desc in entries],
            )
        )

    return results


def _find_owning_work_items(
    conn: sqlite3.Connection,
    table_name: str,
    record_id: int,
) -> list[int]:
    """Find work item id(s) that own the given affected record.

    Returns a list because Relationship maps to two entity_prd work items.
    """
    finder = _OWNERSHIP_FINDERS.get(table_name)
    if not finder:
        return []
    return finder(conn, record_id)


# --- Ownership finder functions ---


def _find_wi_for_field(conn: sqlite3.Connection, field_id: int) -> list[int]:
    row = conn.execute(
        "SELECT entity_id FROM Field WHERE id = ?", (field_id,)
    ).fetchone()
    if not row:
        return []
    return _entity_prd_wi(conn, row[0])


def _find_wi_for_field_option(conn: sqlite3.Connection, fo_id: int) -> list[int]:
    row = conn.execute(
        "SELECT f.entity_id FROM FieldOption fo "
        "JOIN Field f ON fo.field_id = f.id WHERE fo.id = ?",
        (fo_id,),
    ).fetchone()
    if not row:
        return []
    return _entity_prd_wi(conn, row[0])


def _find_wi_for_process(conn: sqlite3.Connection, process_id: int) -> list[int]:
    return _process_def_wi(conn, process_id)


def _find_wi_for_process_step(conn: sqlite3.Connection, step_id: int) -> list[int]:
    row = conn.execute(
        "SELECT process_id FROM ProcessStep WHERE id = ?", (step_id,)
    ).fetchone()
    if not row:
        return []
    return _process_def_wi(conn, row[0])


def _find_wi_for_requirement(conn: sqlite3.Connection, req_id: int) -> list[int]:
    row = conn.execute(
        "SELECT process_id FROM Requirement WHERE id = ?", (req_id,)
    ).fetchone()
    if not row:
        return []
    return _process_def_wi(conn, row[0])


def _find_wi_for_process_entity(conn: sqlite3.Connection, pe_id: int) -> list[int]:
    row = conn.execute(
        "SELECT process_id FROM ProcessEntity WHERE id = ?", (pe_id,)
    ).fetchone()
    if not row:
        return []
    return _process_def_wi(conn, row[0])


def _find_wi_for_process_field(conn: sqlite3.Connection, pf_id: int) -> list[int]:
    row = conn.execute(
        "SELECT process_id FROM ProcessField WHERE id = ?", (pf_id,)
    ).fetchone()
    if not row:
        return []
    return _process_def_wi(conn, row[0])


def _find_wi_for_process_persona(conn: sqlite3.Connection, pp_id: int) -> list[int]:
    row = conn.execute(
        "SELECT process_id FROM ProcessPersona WHERE id = ?", (pp_id,)
    ).fetchone()
    if not row:
        return []
    return _process_def_wi(conn, row[0])


def _find_wi_for_persona(conn: sqlite3.Connection, persona_id: int) -> list[int]:
    """Persona → master_prd work item (project scope)."""
    row = conn.execute(
        "SELECT id FROM WorkItem WHERE item_type = 'master_prd'",
    ).fetchone()
    return [row[0]] if row else []


def _find_wi_for_layout_panel(conn: sqlite3.Connection, panel_id: int) -> list[int]:
    row = conn.execute(
        "SELECT entity_id FROM LayoutPanel WHERE id = ?", (panel_id,)
    ).fetchone()
    if not row:
        return []
    return _entity_prd_wi(conn, row[0])


def _find_wi_for_layout_row(conn: sqlite3.Connection, row_id: int) -> list[int]:
    row = conn.execute(
        "SELECT lp.entity_id FROM LayoutRow lr "
        "JOIN LayoutPanel lp ON lr.panel_id = lp.id WHERE lr.id = ?",
        (row_id,),
    ).fetchone()
    if not row:
        return []
    return _entity_prd_wi(conn, row[0])


def _find_wi_for_layout_tab(conn: sqlite3.Connection, tab_id: int) -> list[int]:
    row = conn.execute(
        "SELECT lp.entity_id FROM LayoutTab lt "
        "JOIN LayoutPanel lp ON lt.panel_id = lp.id WHERE lt.id = ?",
        (tab_id,),
    ).fetchone()
    if not row:
        return []
    return _entity_prd_wi(conn, row[0])


def _find_wi_for_list_column(conn: sqlite3.Connection, lc_id: int) -> list[int]:
    row = conn.execute(
        "SELECT entity_id FROM ListColumn WHERE id = ?", (lc_id,)
    ).fetchone()
    if not row:
        return []
    return _entity_prd_wi(conn, row[0])


def _find_wi_for_domain(conn: sqlite3.Connection, domain_id: int) -> list[int]:
    row = conn.execute(
        "SELECT id FROM WorkItem "
        "WHERE domain_id = ? AND item_type = 'domain_overview'",
        (domain_id,),
    ).fetchone()
    return [row[0]] if row else []


def _find_wi_for_relationship(conn: sqlite3.Connection, rel_id: int) -> list[int]:
    """Relationship → entity_prd for BOTH entities."""
    row = conn.execute(
        "SELECT entity_id, entity_foreign_id FROM Relationship WHERE id = ?",
        (rel_id,),
    ).fetchone()
    if not row:
        return []
    wi_ids: list[int] = []
    wi_ids.extend(_entity_prd_wi(conn, row[0]))
    wi_ids.extend(_entity_prd_wi(conn, row[1]))
    return wi_ids


# --- Helpers ---


def _entity_prd_wi(conn: sqlite3.Connection, entity_id: int) -> list[int]:
    row = conn.execute(
        "SELECT id FROM WorkItem "
        "WHERE entity_id = ? AND item_type = 'entity_prd'",
        (entity_id,),
    ).fetchone()
    return [row[0]] if row else []


def _process_def_wi(conn: sqlite3.Connection, process_id: int) -> list[int]:
    """Return all process-scoped work items for ``process_id``.

    Both ``process_definition`` (the requirements PRD) and
    ``user_process_guide`` (the end-user how-to) read from the same
    process scope, so a change to any owned record affects both.
    """
    rows = conn.execute(
        "SELECT id FROM WorkItem "
        "WHERE process_id = ? "
        "AND item_type IN ('process_definition', 'user_process_guide')",
        (process_id,),
    ).fetchall()
    return [r[0] for r in rows]


_OWNERSHIP_FINDERS: dict[str, object] = {
    "Field": _find_wi_for_field,
    "FieldOption": _find_wi_for_field_option,
    "Process": _find_wi_for_process,
    "ProcessStep": _find_wi_for_process_step,
    "Requirement": _find_wi_for_requirement,
    "ProcessEntity": _find_wi_for_process_entity,
    "ProcessField": _find_wi_for_process_field,
    "ProcessPersona": _find_wi_for_process_persona,
    "Persona": _find_wi_for_persona,
    "LayoutPanel": _find_wi_for_layout_panel,
    "LayoutRow": _find_wi_for_layout_row,
    "LayoutTab": _find_wi_for_layout_tab,
    "ListColumn": _find_wi_for_list_column,
    "Domain": _find_wi_for_domain,
    "Relationship": _find_wi_for_relationship,
}

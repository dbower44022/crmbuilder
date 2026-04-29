"""Document staleness detection for Impact Analysis.

Implements L2 PRD Section 12.10 — identifies work items whose documents
are stale because source data changed after the document was last produced.

A work item's document is stale when ANY ChangeLog entry affects a record
owned by that work item AND ChangeLog.changed_at > WorkItem.completed_at.

Ownership follows the same mapping as Section 12.8.1 (work_item_mapping).
"""

from __future__ import annotations

import dataclasses
import sqlite3


@dataclasses.dataclass
class StaleWorkItem:
    """A work item whose document is stale."""

    work_item_id: int
    item_type: str
    completed_at: str
    stale_change_count: int
    latest_change_at: str


def get_stale_work_items(conn: sqlite3.Connection) -> list[StaleWorkItem]:
    """Return all work items whose documents are stale.

    A document is stale when:
    1. The work item has status='complete' and a non-null completed_at.
    2. At least one ChangeImpact record targets a record owned by that
       work item, linked to a ChangeLog entry with changed_at later
       than the work item's completed_at.

    This function queries ChangeImpact + ChangeLog joined to WorkItem
    ownership. It does not modify any data.

    :param conn: Open client database connection.
    :returns: List of StaleWorkItem records.
    """
    # Find all completed work items
    completed = conn.execute(
        "SELECT id, item_type, completed_at, domain_id, entity_id, process_id "
        "FROM WorkItem WHERE status = 'complete' AND completed_at IS NOT NULL"
    ).fetchall()

    if not completed:
        return []

    results: list[StaleWorkItem] = []

    for wi_id, item_type, completed_at, domain_id, entity_id, process_id in completed:
        # Find ChangeLog entries that post-date this work item's completion
        # and affect records owned by this work item.
        #
        # We use ChangeImpact as the bridge: ChangeImpact.affected_table/record_id
        # identifies the affected record, and the ownership rules determine which
        # work item owns it. Instead of re-implementing ownership lookup per record,
        # we query ChangeImpact records that reference tables matching this work item's
        # scope.

        scope_conditions = _build_scope_conditions(
            item_type, domain_id, entity_id, process_id
        )
        if not scope_conditions:
            continue

        where_clause, params = scope_conditions
        query = (
            "SELECT COUNT(*), MAX(cl.changed_at) "
            "FROM ChangeImpact ci "
            "JOIN ChangeLog cl ON ci.change_log_id = cl.id "
            f"WHERE cl.changed_at > ? AND ({where_clause})"
        )
        row = conn.execute(query, [completed_at, *params]).fetchone()

        if row and row[0] > 0:
            results.append(
                StaleWorkItem(
                    work_item_id=wi_id,
                    item_type=item_type,
                    completed_at=completed_at,
                    stale_change_count=row[0],
                    latest_change_at=row[1],
                )
            )

    return results


def _build_scope_conditions(
    item_type: str,
    domain_id: int | None,
    entity_id: int | None,
    process_id: int | None,
) -> tuple[str, list] | None:
    """Build SQL WHERE conditions matching ChangeImpact records owned by this work item.

    Returns (where_clause, params) or None if no scope can be determined.
    """
    if item_type == "entity_prd" and entity_id is not None:
        # Affected tables: Field, FieldOption, LayoutPanel, LayoutRow, LayoutTab,
        # ListColumn, Relationship (partial)
        return (
            "("
            "(ci.affected_table = 'Field' AND ci.affected_record_id IN "
            "  (SELECT id FROM Field WHERE entity_id = ?)) OR "
            "(ci.affected_table = 'FieldOption' AND ci.affected_record_id IN "
            "  (SELECT fo.id FROM FieldOption fo JOIN Field f ON fo.field_id = f.id "
            "   WHERE f.entity_id = ?)) OR "
            "(ci.affected_table = 'LayoutPanel' AND ci.affected_record_id IN "
            "  (SELECT id FROM LayoutPanel WHERE entity_id = ?)) OR "
            "(ci.affected_table = 'LayoutRow' AND ci.affected_record_id IN "
            "  (SELECT lr.id FROM LayoutRow lr JOIN LayoutPanel lp ON lr.panel_id = lp.id "
            "   WHERE lp.entity_id = ?)) OR "
            "(ci.affected_table = 'LayoutTab' AND ci.affected_record_id IN "
            "  (SELECT lt.id FROM LayoutTab lt JOIN LayoutPanel lp ON lt.panel_id = lp.id "
            "   WHERE lp.entity_id = ?)) OR "
            "(ci.affected_table = 'ListColumn' AND ci.affected_record_id IN "
            "  (SELECT id FROM ListColumn WHERE entity_id = ?)) OR "
            "(ci.affected_table = 'Relationship' AND ci.affected_record_id IN "
            "  (SELECT id FROM Relationship WHERE entity_id = ? OR entity_foreign_id = ?))"
            ")",
            [entity_id] * 6 + [entity_id, entity_id],
        )

    if (
        item_type in ("process_definition", "user_process_guide")
        and process_id is not None
    ):
        return (
            "("
            "(ci.affected_table = 'Process' AND ci.affected_record_id = ?) OR "
            "(ci.affected_table = 'ProcessStep' AND ci.affected_record_id IN "
            "  (SELECT id FROM ProcessStep WHERE process_id = ?)) OR "
            "(ci.affected_table = 'Requirement' AND ci.affected_record_id IN "
            "  (SELECT id FROM Requirement WHERE process_id = ?)) OR "
            "(ci.affected_table = 'ProcessEntity' AND ci.affected_record_id IN "
            "  (SELECT id FROM ProcessEntity WHERE process_id = ?)) OR "
            "(ci.affected_table = 'ProcessField' AND ci.affected_record_id IN "
            "  (SELECT id FROM ProcessField WHERE process_id = ?)) OR "
            "(ci.affected_table = 'ProcessPersona' AND ci.affected_record_id IN "
            "  (SELECT id FROM ProcessPersona WHERE process_id = ?))"
            ")",
            [process_id] * 6,
        )

    if item_type == "master_prd":
        return (
            "(ci.affected_table = 'Persona')",
            [],
        )

    if item_type == "domain_overview" and domain_id is not None:
        return (
            "(ci.affected_table = 'Domain' AND ci.affected_record_id = ?)",
            [domain_id],
        )

    return None

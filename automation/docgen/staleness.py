"""Document staleness detection for the Document Generator.

Implements L2 PRD Section 13.6.1 — identifies documents that are stale because
source data changed after the document was last generated.

IMPORTANT DISTINCTION from automation/impact/staleness.py:
  - Impact Analysis staleness (Section 12.10) uses WorkItem.completed_at as
    the baseline. It answers: "has data changed since this work item was
    completed?"
  - Document Generator staleness (Section 13.6.1) uses GenerationLog.generated_at
    as the baseline. It answers: "has data changed since this document was last
    generated?" This means regeneration without revision clears staleness,
    and a work item can be completed without having a generated document.

The ownership mapping (which records belong to which work item) reuses the
same logic as automation/impact/work_item_mapping.py via
automation/impact/staleness._build_scope_conditions.
"""

from __future__ import annotations

import dataclasses
import sqlite3

from automation.impact.staleness import _build_scope_conditions


@dataclasses.dataclass
class StaleDocument:
    """A document that is stale because data changed after last generation."""

    work_item_id: int
    item_type: str
    last_generated_at: str
    latest_change_at: str
    change_count: int
    change_summary: str


def get_stale_documents(conn: sqlite3.Connection) -> list[StaleDocument]:
    """Return all documents that are stale.

    A document is stale when:
    1. The work item has status='complete'.
    2. At least one final GenerationLog entry exists for that work item.
    3. At least one ChangeLog entry affecting records within the work item's
       scope has changed_at later than the most recent
       GenerationLog.generated_at for that work item.

    If no GenerationLog record exists, the document has not been produced yet
    and is not considered stale.

    :param conn: Open client database connection.
    :returns: List of StaleDocument records.
    """
    # Find all completed work items that have at least one final generation
    completed = conn.execute(
        "SELECT wi.id, wi.item_type, wi.domain_id, wi.entity_id, wi.process_id, "
        "  (SELECT MAX(gl.generated_at) FROM GenerationLog gl "
        "   WHERE gl.work_item_id = wi.id AND gl.generation_mode = 'final') "
        "  AS last_generated_at "
        "FROM WorkItem wi "
        "WHERE wi.status = 'complete'"
    ).fetchall()

    if not completed:
        return []

    results: list[StaleDocument] = []

    for wi_id, item_type, domain_id, entity_id, process_id, last_gen_at in completed:
        # Skip work items with no final generation
        if not last_gen_at:
            continue

        scope = _build_scope_conditions(
            item_type, domain_id, entity_id, process_id
        )
        if not scope:
            continue

        where_clause, params = scope

        # Find ChangeLog entries that post-date the last generation
        query = (
            "SELECT COUNT(*), MAX(cl.changed_at) "
            "FROM ChangeImpact ci "
            "JOIN ChangeLog cl ON ci.change_log_id = cl.id "
            f"WHERE cl.changed_at > ? AND ({where_clause})"  # noqa: S608
        )
        row = conn.execute(query, [last_gen_at, *params]).fetchone()

        if row and row[0] > 0:
            # Build a summary from the post-generation ChangeLog entries
            summary_rows = conn.execute(
                "SELECT DISTINCT cl.table_name, cl.field_name, cl.change_type "
                "FROM ChangeImpact ci "
                "JOIN ChangeLog cl ON ci.change_log_id = cl.id "
                f"WHERE cl.changed_at > ? AND ({where_clause}) "  # noqa: S608
                "ORDER BY cl.changed_at DESC LIMIT 10",
                [last_gen_at, *params],
            ).fetchall()

            summary_parts = []
            for table, field, change_type in summary_rows:
                if field:
                    summary_parts.append(f"{change_type} {table}.{field}")
                else:
                    summary_parts.append(f"{change_type} {table}")
            change_summary = "; ".join(summary_parts)

            results.append(
                StaleDocument(
                    work_item_id=wi_id,
                    item_type=item_type,
                    last_generated_at=last_gen_at,
                    latest_change_at=row[1],
                    change_count=row[0],
                    change_summary=change_summary,
                )
            )

    return results

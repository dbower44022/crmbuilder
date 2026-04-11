"""Pre-commit analysis for direct implementor edits.

Implements L2 PRD Section 12.5 — evaluates the downstream impact of a
proposed edit or delete before the change is committed.

Pre-commit analysis does NOT write ChangeImpact rows. The caller (future
UI in Step 15) presents them to the implementor, who either confirms
(with rationale) or cancels.
"""

from __future__ import annotations

import dataclasses
import sqlite3

from automation.impact.queries import AffectedRecord, trace_change


@dataclasses.dataclass
class ProposedImpact:
    """An in-memory impact record for pre-commit analysis.

    Same shape as AffectedRecord but named distinctly to indicate these
    are not persisted until the implementor confirms.
    """

    affected_table: str
    affected_record_id: int
    impact_description: str
    requires_review: bool = True


def analyze_proposed_change(
    conn: sqlite3.Connection,
    table_name: str,
    record_id: int,
    change_type: str,
    new_values: dict | None = None,
    rationale: str | None = None,
) -> list[ProposedImpact]:
    """Analyze a proposed direct edit before commit.

    Runs cross-reference queries against current database state for the
    specified record. Returns in-memory ProposedImpact objects describing
    downstream effects. Does not write any data.

    Per Section 12.5.3, rationale is required when the impact set is
    non-empty — but enforcement is the UI's responsibility. This function
    accepts the parameter for API completeness.

    :param conn: Open client database connection.
    :param table_name: Table of the record being modified.
    :param record_id: ID of the record being modified.
    :param change_type: 'update' or 'delete'.
    :param new_values: For updates, dict of field_name -> new_value.
        Not used by queries but available for future refinement.
    :param rationale: Implementor's rationale for the change.
        Accepted but not enforced (UI responsibility).
    :returns: List of ProposedImpact objects (not persisted).
    """
    if change_type not in ("update", "delete"):
        return []

    affected: list[AffectedRecord] = trace_change(
        conn, table_name, record_id, change_type
    )

    return [
        ProposedImpact(
            affected_table=ar.table_name,
            affected_record_id=ar.record_id,
            impact_description=ar.impact_description,
            requires_review=ar.requires_review,
        )
        for ar in affected
    ]

"""ChangeImpact record creation for Impact Analysis.

Implements L2 PRD Section 12.4 — builds ChangeImpact rows from
cross-reference query results and writes them to the database.
"""

from __future__ import annotations

import dataclasses
import sqlite3

from automation.db.connection import transaction
from automation.impact.queries import AffectedRecord


@dataclasses.dataclass
class CandidateImpact:
    """A candidate impact before deduplication.

    Pairs a ChangeLog entry with an affected record found by
    cross-reference queries.
    """

    change_log_id: int
    affected_table: str
    affected_record_id: int
    impact_description: str
    requires_review: bool = True


def write_change_impacts(
    conn: sqlite3.Connection,
    candidates: list[CandidateImpact],
) -> list[int]:
    """Write deduplicated CandidateImpact records to the ChangeImpact table.

    Uses transaction() for atomic multi-row writes.

    :param conn: Open client database connection.
    :param candidates: Deduplicated candidate impacts to persist.
    :returns: List of newly created ChangeImpact.id values.
    """
    if not candidates:
        return []

    created_ids: list[int] = []
    with transaction(conn):
        for c in candidates:
            cursor = conn.execute(
                "INSERT INTO ChangeImpact "
                "(change_log_id, affected_table, affected_record_id, "
                "impact_description, requires_review, reviewed) "
                "VALUES (?, ?, ?, ?, ?, FALSE)",
                (
                    c.change_log_id,
                    c.affected_table,
                    c.affected_record_id,
                    c.impact_description,
                    c.requires_review,
                ),
            )
            created_ids.append(cursor.lastrowid)

    return created_ids


def build_candidates(
    change_log_id: int,
    affected_records: list[AffectedRecord],
) -> list[CandidateImpact]:
    """Convert AffectedRecords from queries into CandidateImpacts.

    :param change_log_id: The ChangeLog.id that triggered the query.
    :param affected_records: Results from trace_change().
    :returns: List of CandidateImpact instances.
    """
    return [
        CandidateImpact(
            change_log_id=change_log_id,
            affected_table=ar.table_name,
            affected_record_id=ar.record_id,
            impact_description=ar.impact_description,
            requires_review=ar.requires_review,
        )
        for ar in affected_records
    ]

"""Batch processing for Impact Analysis.

Implements L2 PRD Section 12.9 — processes a batch of ChangeLog entries
from a single session, traces each independently, deduplicates, and
writes ChangeImpact records.

Processing sequence (Section 12.9.2):
1. Trace each change independently via cross-reference queries.
2. Deduplicate candidate impacts by (affected_table, affected_record_id).
3. Write deduplicated set to ChangeImpact table.

Query consolidation (Section 12.9.3): when multiple changes affect the
same source table, queries are consolidated using batch_trace_changes().
"""

from __future__ import annotations

import sqlite3

from automation.impact.changeimpact import (
    CandidateImpact,
    build_candidates,
    write_change_impacts,
)
from automation.impact.deduplication import deduplicate
from automation.impact.queries import batch_trace_changes


def process_batch(
    conn: sqlite3.Connection,
    change_log_ids: list[int],
) -> list[CandidateImpact]:
    """Process a batch of ChangeLog entries and write ChangeImpact rows.

    Reads the specified ChangeLog entries, traces downstream effects with
    query consolidation, deduplicates, and writes results.

    :param conn: Open client database connection.
    :param change_log_ids: ChangeLog.id values to process.
    :returns: The deduplicated CandidateImpact list that was written.
    """
    if not change_log_ids:
        return []

    # Read ChangeLog entries — filter to updates and deletes (inserts exempt)
    ph = ",".join("?" * len(change_log_ids))
    rows = conn.execute(
        f"SELECT id, table_name, record_id, change_type "  # noqa: S608
        f"FROM ChangeLog WHERE id IN ({ph}) "
        f"AND change_type IN ('update', 'delete')",
        change_log_ids,
    ).fetchall()

    if not rows:
        return []

    # Deduplicate source changes: group by (table_name, record_id) to avoid
    # redundant traces. Multiple ChangeLog entries updating different fields
    # of the same record share one trace.
    source_map: dict[tuple[str, int], list[int]] = {}  # (table, rid) -> [cl_ids]
    change_types: dict[tuple[str, int], str] = {}
    for cl_id, table_name, record_id, change_type in rows:
        key = (table_name, record_id)
        source_map.setdefault(key, []).append(cl_id)
        # Use the strongest change_type: delete > update
        if change_types.get(key) != "delete":
            change_types[key] = change_type

    # Build consolidated change list
    changes = [
        (table, rid, change_types[(table, rid)])
        for table, rid in source_map
    ]

    # Trace with batch consolidation (Section 12.9.3)
    trace_results = batch_trace_changes(conn, changes)

    # Build CandidateImpact list — tag each with the first ChangeLog id
    all_candidates: list[CandidateImpact] = []
    for (table, rid), affected_records in trace_results.items():
        first_cl_id = source_map[(table, rid)][0]
        all_candidates.extend(build_candidates(first_cl_id, affected_records))

    # Deduplicate (Section 12.4.3)
    deduped = deduplicate(all_candidates)

    # Write to database
    write_change_impacts(conn, deduped)

    return deduped


def process_batch_precommit(
    conn: sqlite3.Connection,
    change_log_ids: list[int],
) -> list[CandidateImpact]:
    """Process a batch for pre-commit analysis — returns without writing.

    Same trace and dedup logic as process_batch, but does not persist
    ChangeImpact rows. Used for pre-commit analysis where the caller
    presents results before deciding to commit.

    :param conn: Open client database connection.
    :param change_log_ids: ChangeLog.id values to analyze.
    :returns: Deduplicated CandidateImpact list (not persisted).
    """
    if not change_log_ids:
        return []

    ph = ",".join("?" * len(change_log_ids))
    rows = conn.execute(
        f"SELECT id, table_name, record_id, change_type "  # noqa: S608
        f"FROM ChangeLog WHERE id IN ({ph}) "
        f"AND change_type IN ('update', 'delete')",
        change_log_ids,
    ).fetchall()

    if not rows:
        return []

    source_map: dict[tuple[str, int], list[int]] = {}
    change_types: dict[tuple[str, int], str] = {}
    for cl_id, table_name, record_id, change_type in rows:
        key = (table_name, record_id)
        source_map.setdefault(key, []).append(cl_id)
        if change_types.get(key) != "delete":
            change_types[key] = change_type

    changes = [
        (table, rid, change_types[(table, rid)])
        for table, rid in source_map
    ]

    trace_results = batch_trace_changes(conn, changes)

    all_candidates: list[CandidateImpact] = []
    for (table, rid), affected_records in trace_results.items():
        first_cl_id = source_map[(table, rid)][0]
        all_candidates.extend(build_candidates(first_cl_id, affected_records))

    return deduplicate(all_candidates)

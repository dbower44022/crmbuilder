"""Status transitions and side effects for CRM Builder Automation.

Implements L2 PRD Section 9.7:
- 9.7.1 Forward transitions: ready → in_progress, in_progress → complete
- 9.7.2 Revision transition: complete → in_progress with cascade regression
"""

import sqlite3

from automation.db.connection import transaction
from automation.workflow.status import calculate_status, recalculate_downstream

# Blocked reason prefix for automatic blocking from upstream revision.
UPSTREAM_REVISION_PREFIX = "UPSTREAM_REVISION: "


def _get_descriptive_name(conn: sqlite3.Connection, work_item_id: int) -> str:
    """Build a descriptive name for a work item for blocked_reason messages.

    Uses item_type plus domain/entity/process name when available.
    """
    row = conn.execute(
        """
        SELECT wi.item_type, d.name, e.name, p.name
        FROM WorkItem wi
        LEFT JOIN Domain d ON d.id = wi.domain_id
        LEFT JOIN Entity e ON e.id = wi.entity_id
        LEFT JOIN Process p ON p.id = wi.process_id
        WHERE wi.id = ?
        """,
        (work_item_id,),
    ).fetchone()
    if row is None:
        return f"Work Item #{work_item_id}"
    item_type, domain_name, entity_name, process_name = row
    parts = []
    if entity_name:
        parts.append(entity_name)
    if process_name:
        parts.append(process_name)
    if domain_name and not entity_name and not process_name:
        parts.append(domain_name)
    return " — ".join(parts) if parts else item_type


def _build_blocked_reason(
    conn: sqlite3.Connection,
    upstream_id: int,
) -> str:
    """Build the structured blocked_reason for upstream revision.

    Format: UPSTREAM_REVISION: {item_type} — {descriptive_name} (Work Item #{id})
    """
    row = conn.execute(
        "SELECT item_type FROM WorkItem WHERE id = ?", (upstream_id,)
    ).fetchone()
    item_type = row[0] if row else "unknown"
    desc = _get_descriptive_name(conn, upstream_id)
    return f"{UPSTREAM_REVISION_PREFIX}{item_type} — {desc} (Work Item #{upstream_id})"


def _get_all_downstream(
    conn: sqlite3.Connection,
    work_item_id: int,
) -> set[int]:
    """Get all downstream work item IDs (direct and transitive)."""
    visited = set()
    queue = [work_item_id]
    while queue:
        current = queue.pop()
        if current in visited:
            continue
        visited.add(current)
        rows = conn.execute(
            "SELECT work_item_id FROM Dependency WHERE depends_on_id = ?",
            (current,),
        ).fetchall()
        for (downstream_id,) in rows:
            if downstream_id not in visited:
                queue.append(downstream_id)
    visited.discard(work_item_id)  # Don't include the item itself
    return visited


def start(conn: sqlite3.Connection, work_item_id: int) -> None:
    """Transition a work item from ready to in_progress.

    Sets started_at to the current timestamp.

    :param conn: An open sqlite3.Connection.
    :param work_item_id: The WorkItem.id to start.
    :raises ValueError: If the work item is not in status ready.
    """
    row = conn.execute(
        "SELECT status FROM WorkItem WHERE id = ?", (work_item_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Work item {work_item_id} not found")
    if row[0] != "ready":
        raise ValueError(
            f"Cannot start work item {work_item_id}: "
            f"status is '{row[0]}', expected 'ready'"
        )
    with transaction(conn):
        conn.execute(
            "UPDATE WorkItem SET status = 'in_progress', "
            "started_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (work_item_id,),
        )


def complete(conn: sqlite3.Connection, work_item_id: int) -> list[int]:
    """Transition a work item from in_progress to complete.

    Sets completed_at to the current timestamp and triggers downstream
    recalculation — items depending on this one may become ready.

    :param conn: An open sqlite3.Connection.
    :param work_item_id: The WorkItem.id to complete.
    :returns: List of downstream work item IDs that transitioned to ready.
    :raises ValueError: If the work item is not in status in_progress.
    """
    row = conn.execute(
        "SELECT status FROM WorkItem WHERE id = ?", (work_item_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Work item {work_item_id} not found")
    if row[0] != "in_progress":
        raise ValueError(
            f"Cannot complete work item {work_item_id}: "
            f"status is '{row[0]}', expected 'in_progress'"
        )
    with transaction(conn):
        conn.execute(
            "UPDATE WorkItem SET status = 'complete', "
            "completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (work_item_id,),
        )
        transitioned = recalculate_downstream(conn, work_item_id)

        # Also check for blocked items that reference this upstream item
        # and unblock them if all deps are now complete
        blocked_rows = conn.execute(
            """
            SELECT id, status_before_blocked, blocked_reason
            FROM WorkItem
            WHERE status = 'blocked'
              AND blocked_reason LIKE ?
            """,
            (f"%Work Item #{work_item_id})%",),
        ).fetchall()
        for blocked_id, status_before, _reason in blocked_rows:
            # Check if all dependencies of this blocked item are complete
            new_status = calculate_status(conn, blocked_id)
            if new_status == "ready":
                # Restore to status_before_blocked
                restore_status = status_before if status_before else "ready"
                conn.execute(
                    "UPDATE WorkItem SET status = ?, blocked_reason = NULL, "
                    "status_before_blocked = NULL, updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = ?",
                    (restore_status, blocked_id),
                )
                transitioned.append(blocked_id)
            else:
                # Dependencies still incomplete — move to not_started
                conn.execute(
                    "UPDATE WorkItem SET status = 'not_started', blocked_reason = NULL, "
                    "status_before_blocked = NULL, updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = ?",
                    (blocked_id,),
                )

    return transitioned


def revise(conn: sqlite3.Connection, work_item_id: int) -> list[int]:
    """Transition a completed work item back to in_progress for revision.

    Section 9.7.2: Clears completed_at and triggers cascade regression
    on all downstream items (direct and transitive):
    - ready items → not_started
    - in_progress/complete items → blocked (with structured reason)
    - not_started items → unaffected
    - already blocked (different reason) → unaffected

    :param conn: An open sqlite3.Connection.
    :param work_item_id: The WorkItem.id to revise.
    :returns: List of downstream work item IDs that were affected.
    :raises ValueError: If the work item is not in status complete.
    """
    row = conn.execute(
        "SELECT status FROM WorkItem WHERE id = ?", (work_item_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Work item {work_item_id} not found")
    if row[0] != "complete":
        raise ValueError(
            f"Cannot revise work item {work_item_id}: "
            f"status is '{row[0]}', expected 'complete'"
        )

    with transaction(conn):
        # Revert to in_progress
        conn.execute(
            "UPDATE WorkItem SET status = 'in_progress', "
            "completed_at = NULL, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (work_item_id,),
        )

        # Build blocked reason
        blocked_reason = _build_blocked_reason(conn, work_item_id)

        # Find all downstream items
        downstream_ids = _get_all_downstream(conn, work_item_id)
        affected = []
        for ds_id in downstream_ids:
            ds_row = conn.execute(
                "SELECT status, blocked_reason FROM WorkItem WHERE id = ?",
                (ds_id,),
            ).fetchone()
            if ds_row is None:
                continue
            ds_status, ds_blocked_reason = ds_row

            if ds_status == "ready":
                # ready → not_started
                conn.execute(
                    "UPDATE WorkItem SET status = 'not_started', "
                    "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (ds_id,),
                )
                affected.append(ds_id)
            elif ds_status in ("in_progress", "complete"):
                # in_progress/complete → blocked
                conn.execute(
                    "UPDATE WorkItem SET status = 'blocked', "
                    "blocked_reason = ?, status_before_blocked = ?, "
                    "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (blocked_reason, ds_status, ds_id),
                )
                affected.append(ds_id)
            # not_started and already-blocked-for-different-reason: unaffected

    return affected

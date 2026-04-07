"""Status model and calculation for CRM Builder Automation work items.

Implements L2 PRD Sections 9.2 (status model) and 9.3 (status calculation).
Status values: not_started, ready, in_progress, complete, blocked.

A not_started item becomes ready when all its dependencies have status
complete. An item with zero dependencies is ready immediately upon creation.
"""

import sqlite3

# Valid status values matching the CHECK constraint on WorkItem.status.
VALID_STATUSES = frozenset({
    "not_started",
    "ready",
    "in_progress",
    "complete",
    "blocked",
})


def calculate_status(conn: sqlite3.Connection, work_item_id: int) -> str:
    """Calculate what status a work item should have based on dependencies.

    Returns "ready" if all dependencies are complete (or there are no
    dependencies). Returns "not_started" if any dependency is not complete.

    This function only evaluates the not_started/ready boundary. It does
    not override in_progress, complete, or blocked statuses — those are
    managed by explicit transitions.

    :param conn: An open sqlite3.Connection.
    :param work_item_id: The WorkItem.id to evaluate.
    :returns: "ready" or "not_started".
    """
    row = conn.execute(
        """
        SELECT COUNT(*) FROM Dependency d
        JOIN WorkItem w ON w.id = d.depends_on_id
        WHERE d.work_item_id = ?
          AND w.status != 'complete'
        """,
        (work_item_id,),
    ).fetchone()
    incomplete_count = row[0]
    return "not_started" if incomplete_count > 0 else "ready"


def recalculate_downstream(conn: sqlite3.Connection, completed_item_id: int) -> list[int]:
    """Recalculate status for all items that depend on the completed item.

    For each downstream item that is currently not_started, check if all
    its dependencies are now complete. If so, transition it to ready.

    :param conn: An open sqlite3.Connection.
    :param completed_item_id: The WorkItem.id that just completed.
    :returns: List of work item IDs that transitioned to ready.
    """
    # Find all items that depend on the completed item
    rows = conn.execute(
        """
        SELECT DISTINCT d.work_item_id
        FROM Dependency d
        JOIN WorkItem w ON w.id = d.work_item_id
        WHERE d.depends_on_id = ?
          AND w.status = 'not_started'
        """,
        (completed_item_id,),
    ).fetchall()

    transitioned = []
    for (downstream_id,) in rows:
        new_status = calculate_status(conn, downstream_id)
        if new_status == "ready":
            conn.execute(
                "UPDATE WorkItem SET status = 'ready', updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (downstream_id,),
            )
            transitioned.append(downstream_id)

    return transitioned

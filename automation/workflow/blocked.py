"""Blocked state handling for CRM Builder Automation work items.

Implements L2 PRD Section 9.8:
- 9.8.1 Causes: upstream revision (automatic) or implementor action (manual)
- 9.8.2 Unblocking: automatic (upstream revision resolved) or manual
- 9.8.3 Blocked reason format: UPSTREAM_REVISION: prefix for automatic

Automatic blocking and unblocking during upstream revision is handled by
transitions.revise() and transitions.complete(). This module provides the
manual block/unblock operations.
"""

import sqlite3

from automation.db.connection import transaction
from automation.workflow.status import calculate_status
from automation.workflow.transitions import UPSTREAM_REVISION_PREFIX


def is_automatic_block(blocked_reason: str | None) -> bool:
    """Return True if the blocked_reason was set by automatic cascade.

    :param blocked_reason: The WorkItem.blocked_reason value.
    :returns: True if the reason starts with the upstream revision prefix.
    """
    if blocked_reason is None:
        return False
    return blocked_reason.startswith(UPSTREAM_REVISION_PREFIX)


def block(conn: sqlite3.Connection, work_item_id: int, reason: str) -> None:
    """Manually block a work item (implementor-initiated).

    Section 9.8.1: The implementor blocks a work item for a reason outside
    the dependency graph. Can be applied to any status except not_started.

    :param conn: An open sqlite3.Connection.
    :param work_item_id: The WorkItem.id to block.
    :param reason: Free-text reason for blocking.
    :raises ValueError: If the work item is not found or is not_started.
    """
    row = conn.execute(
        "SELECT status FROM WorkItem WHERE id = ?", (work_item_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Work item {work_item_id} not found")
    current_status = row[0]
    if current_status == "not_started":
        raise ValueError(
            f"Cannot block work item {work_item_id}: "
            "status is 'not_started' — no meaningful work to block"
        )
    if current_status == "blocked":
        raise ValueError(
            f"Cannot block work item {work_item_id}: already blocked"
        )

    with transaction(conn):
        conn.execute(
            "UPDATE WorkItem SET status = 'blocked', "
            "blocked_reason = ?, status_before_blocked = ?, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (reason, current_status, work_item_id),
        )


def unblock(conn: sqlite3.Connection, work_item_id: int) -> None:
    """Manually unblock a work item (implementor-initiated).

    Section 9.8.2: Restores the item to status_before_blocked and clears
    blocked_reason and status_before_blocked. If the restored status is
    ready or higher and dependencies are not all complete, the item
    transitions to not_started instead.

    :param conn: An open sqlite3.Connection.
    :param work_item_id: The WorkItem.id to unblock.
    :raises ValueError: If the work item is not found or is not blocked.
    """
    row = conn.execute(
        "SELECT status, status_before_blocked FROM WorkItem WHERE id = ?",
        (work_item_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Work item {work_item_id} not found")
    current_status, status_before = row
    if current_status != "blocked":
        raise ValueError(
            f"Cannot unblock work item {work_item_id}: "
            f"status is '{current_status}', expected 'blocked'"
        )

    restore_status = status_before if status_before else "ready"

    with transaction(conn):
        # Check if dependencies allow the restored status
        if restore_status in ("ready", "in_progress", "complete"):
            dep_status = calculate_status(conn, work_item_id)
            if dep_status == "not_started":
                # Dependencies are not all complete — can't restore
                restore_status = "not_started"

        conn.execute(
            "UPDATE WorkItem SET status = ?, blocked_reason = NULL, "
            "status_before_blocked = NULL, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (restore_status, work_item_id),
        )

"""Available work calculation for CRM Builder Automation.

Implements L2 PRD Section 9.6: returns work items with status ready or
in_progress, ordered by phase ascending then by domain sort_order within
the same phase. Cross-domain items (NULL domain_id) sort last within
their phase.

Results are grouped into two lists:
- Continue Work: in_progress items (work already started)
- Ready to Start: ready items (new work available)
"""

import sqlite3

from automation.workflow.phases import get_phase


def get_available_work(conn: sqlite3.Connection) -> list[dict]:
    """Return available work items ordered for the Project Dashboard.

    Items are returned in two groups: in_progress first, then ready.
    Within each group, items are ordered by phase ascending, then by
    domain sort_order ascending. Items with NULL domain_id sort last
    within their phase.

    Each dict contains: id, item_type, status, domain_id, entity_id,
    process_id, phase, domain_name, domain_sort_order.

    :param conn: An open sqlite3.Connection.
    :returns: List of work item dicts.
    """
    rows = conn.execute(
        """
        SELECT
            wi.id,
            wi.item_type,
            wi.status,
            wi.domain_id,
            wi.entity_id,
            wi.process_id,
            d.is_service,
            d.name AS domain_name,
            d.sort_order AS domain_sort_order
        FROM WorkItem wi
        LEFT JOIN Domain d ON d.id = wi.domain_id
        WHERE wi.status IN ('in_progress', 'ready')
        """,
    ).fetchall()

    items = []
    for row in rows:
        (wid, item_type, status, domain_id, entity_id, process_id,
         is_service, domain_name, domain_sort_order) = row
        phase = get_phase(item_type, is_service=bool(is_service) if is_service is not None else False)
        items.append({
            "id": wid,
            "item_type": item_type,
            "status": status,
            "domain_id": domain_id,
            "entity_id": entity_id,
            "process_id": process_id,
            "phase": phase,
            "domain_name": domain_name,
            "domain_sort_order": domain_sort_order,
        })

    # Sort: status group (in_progress before ready), phase asc,
    # domain_sort_order asc (NULL last)
    def sort_key(item):
        status_rank = 0 if item["status"] == "in_progress" else 1
        dso = item["domain_sort_order"]
        # NULL domain_sort_order sorts last (use a large number)
        domain_rank = dso if dso is not None else 999999
        return (status_rank, item["phase"], domain_rank)

    items.sort(key=sort_key)
    return items

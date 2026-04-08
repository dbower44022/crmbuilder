"""Dashboard data assembly logic — pure Python, no Qt.

Assembles work item data for the Project Dashboard display.
All database queries and data shaping happen here; the Qt widgets
are thin display layers that consume these results.
"""

from __future__ import annotations

import dataclasses
import sqlite3

from automation.workflow.phases import get_phase, get_phase_name


@dataclasses.dataclass
class WorkItemRow:
    """A single work item row for dashboard display."""

    id: int
    item_type: str
    status: str
    phase: int
    phase_name: str
    domain_id: int | None
    domain_name: str | None
    domain_sort_order: int | None
    entity_id: int | None
    entity_name: str | None
    process_id: int | None
    process_name: str | None
    blocked_reason: str | None
    started_at: str | None
    completed_at: str | None


@dataclasses.dataclass
class ProjectSummary:
    """Summary counts for the project summary bar."""

    client_name: str
    total: int
    not_started: int
    ready: int
    in_progress: int
    complete: int
    blocked: int


@dataclasses.dataclass
class PhaseGroup:
    """A group of work items in a single phase for the inventory."""

    phase: int
    phase_name: str
    items: list[WorkItemRow]
    complete_count: int
    total_count: int


def load_all_work_items(conn: sqlite3.Connection) -> list[WorkItemRow]:
    """Load all work items with their scoping context.

    :param conn: Client database connection.
    :returns: List of WorkItemRow, unsorted.
    """
    rows = conn.execute(
        """
        SELECT
            wi.id, wi.item_type, wi.status,
            wi.domain_id, wi.entity_id, wi.process_id,
            wi.blocked_reason, wi.started_at, wi.completed_at,
            d.name AS domain_name, d.sort_order AS domain_sort_order,
            d.is_service,
            e.name AS entity_name,
            p.name AS process_name
        FROM WorkItem wi
        LEFT JOIN Domain d ON d.id = wi.domain_id
        LEFT JOIN Entity e ON e.id = wi.entity_id
        LEFT JOIN Process p ON p.id = wi.process_id
        """
    ).fetchall()

    items = []
    for row in rows:
        (wid, item_type, status, domain_id, entity_id, process_id,
         blocked_reason, started_at, completed_at,
         domain_name, domain_sort_order, is_service,
         entity_name, process_name) = row
        phase = get_phase(
            item_type,
            is_service=bool(is_service) if is_service is not None else False,
        )
        items.append(WorkItemRow(
            id=wid,
            item_type=item_type,
            status=status,
            phase=phase,
            phase_name=get_phase_name(phase),
            domain_id=domain_id,
            domain_name=domain_name,
            domain_sort_order=domain_sort_order,
            entity_id=entity_id,
            entity_name=entity_name,
            process_id=process_id,
            process_name=process_name,
            blocked_reason=blocked_reason,
            started_at=started_at,
            completed_at=completed_at,
        ))
    return items


def compute_summary(client_name: str, items: list[WorkItemRow]) -> ProjectSummary:
    """Compute project summary counts from work items.

    :param client_name: The client name for display.
    :param items: All work items.
    :returns: ProjectSummary with counts by status.
    """
    counts: dict[str, int] = {
        "not_started": 0, "ready": 0, "in_progress": 0,
        "complete": 0, "blocked": 0,
    }
    for item in items:
        if item.status in counts:
            counts[item.status] += 1
    return ProjectSummary(
        client_name=client_name,
        total=len(items),
        **counts,
    )


def build_work_queue(items: list[WorkItemRow]) -> list[WorkItemRow]:
    """Build the actionable work queue: in_progress first, then ready.

    Sorted by phase ascending, then domain_sort_order ascending.

    :param items: All work items.
    :returns: Filtered and sorted list.
    """
    queue = [i for i in items if i.status in ("in_progress", "ready")]
    queue.sort(key=_sort_key_phase_domain)
    # Stable sort: in_progress before ready
    queue.sort(key=lambda i: 0 if i.status == "in_progress" else 1)
    return queue


def build_phase_groups(items: list[WorkItemRow]) -> list[PhaseGroup]:
    """Group work items by phase for the full inventory.

    :param items: All work items.
    :returns: List of PhaseGroup sorted by phase number.
    """
    phase_map: dict[int, list[WorkItemRow]] = {}
    for item in items:
        phase_map.setdefault(item.phase, []).append(item)

    groups = []
    for phase_num in sorted(phase_map.keys()):
        phase_items = sorted(phase_map[phase_num], key=_sort_key_phase_domain)
        complete_count = sum(1 for i in phase_items if i.status == "complete")
        groups.append(PhaseGroup(
            phase=phase_num,
            phase_name=get_phase_name(phase_num),
            items=phase_items,
            complete_count=complete_count,
            total_count=len(phase_items),
        ))
    return groups


def filter_items(
    items: list[WorkItemRow],
    domain_filter: str | None = None,
    phase_filter: int | None = None,
    status_filter: str | None = None,
) -> list[WorkItemRow]:
    """Filter work items by domain, phase, and/or status.

    :param items: All work items.
    :param domain_filter: Domain name to filter by, or None for all.
    :param phase_filter: Phase number to filter by, or None for all.
    :param status_filter: Status string to filter by, or None for all.
    :returns: Filtered list.
    """
    result = items
    if domain_filter is not None:
        result = [i for i in result if i.domain_name == domain_filter]
    if phase_filter is not None:
        result = [i for i in result if i.phase == phase_filter]
    if status_filter is not None:
        result = [i for i in result if i.status == status_filter]
    return result


def get_unique_domains(items: list[WorkItemRow]) -> list[str]:
    """Extract unique domain names from work items, sorted.

    :param items: All work items.
    :returns: Sorted list of domain names (excludes None).
    """
    return sorted({i.domain_name for i in items if i.domain_name is not None})


def get_stale_count(conn: sqlite3.Connection) -> int:
    """Count completed work items with stale documents.

    A work item is stale if it has a GenerationLog entry and
    its completed_at is before the most recent upstream change.
    This is a simplified check — the full staleness logic is in
    automation.impact.staleness.

    :param conn: Client database connection.
    :returns: Count of stale work items.
    """
    try:
        from automation.impact.staleness import get_stale_work_items
        stale = get_stale_work_items(conn)
        return len(stale)
    except Exception:
        return 0


def has_incomplete_upstream(conn: sqlite3.Connection, work_item_id: int) -> bool:
    """Check if a work item has any incomplete upstream dependencies.

    :param conn: Client database connection.
    :param work_item_id: The work item to check.
    :returns: True if any upstream dependency is not complete.
    """
    rows = conn.execute(
        """
        SELECT wi.status
        FROM Dependency d
        JOIN WorkItem wi ON wi.id = d.depends_on_id
        WHERE d.work_item_id = ?
        """,
        (work_item_id,),
    ).fetchall()
    return any(row[0] != "complete" for row in rows)


def _sort_key_phase_domain(item: WorkItemRow) -> tuple:
    """Sort key: phase asc, domain_sort_order asc (NULL last)."""
    dso = item.domain_sort_order if item.domain_sort_order is not None else 999999
    return (item.phase, dso)

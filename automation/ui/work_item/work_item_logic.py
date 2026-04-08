"""Work item detail data assembly logic — pure Python, no Qt.

Loads work item details, dependencies, sessions, documents,
and impacts for the Work Item Detail view. Computes action
availability based on current status.
"""

from __future__ import annotations

import dataclasses
import sqlite3

from automation.workflow.phases import get_phase, get_phase_name


@dataclasses.dataclass
class WorkItemDetail:
    """Full detail for a single work item."""

    id: int
    item_type: str
    status: str
    phase: int
    phase_name: str
    domain_id: int | None
    domain_name: str | None
    entity_id: int | None
    entity_name: str | None
    process_id: int | None
    process_name: str | None
    blocked_reason: str | None
    started_at: str | None
    completed_at: str | None


@dataclasses.dataclass
class DependencyRow:
    """A dependency relationship for display."""

    work_item_id: int
    item_type: str
    status: str
    domain_name: str | None
    entity_name: str | None
    process_name: str | None
    direction: str  # "upstream" or "downstream"


@dataclasses.dataclass
class SessionRow:
    """An AI session record for display."""

    id: int
    session_type: str
    import_status: str
    started_at: str
    completed_at: str | None
    generated_prompt: str
    raw_output: str | None
    notes: str | None


@dataclasses.dataclass
class DocumentRow:
    """A document generation log entry for display."""

    id: int
    document_type: str
    file_path: str
    generated_at: str
    generation_mode: str
    git_commit_hash: str | None


@dataclasses.dataclass
class ImpactRow:
    """A change impact record for display."""

    id: int
    change_log_id: int
    affected_table: str
    affected_record_id: int
    impact_description: str | None
    requires_review: bool
    reviewed: bool
    reviewed_at: str | None
    action_required: bool


# --- Action availability ---

# All 9 actions from Section 14.3.3
ACTIONS = [
    "start_work",
    "mark_complete",
    "reopen_for_revision",
    "block",
    "unblock",
    "generate_prompt",
    "run_import",
    "generate_document",
    "view_impact_analysis",
]


def get_available_actions(status: str) -> dict[str, str | None]:
    """Determine which actions are available and why unavailable ones are not.

    Returns a dict mapping action name to None (available) or a string
    explaining why the action is not currently applicable.

    :param status: The work item's current status.
    :returns: Dict of action -> None or explanation string.
    """
    result: dict[str, str | None] = {}

    # start_work: only from ready
    if status == "ready":
        result["start_work"] = None
    else:
        result["start_work"] = (
            f"Cannot start work: item status is '{status}'. "
            f"Item must be in 'ready' status to start."
        )

    # mark_complete: only from in_progress
    if status == "in_progress":
        result["mark_complete"] = None
    else:
        result["mark_complete"] = (
            f"Cannot mark complete: item status is '{status}'. "
            f"Item must be 'in_progress' to mark complete."
        )

    # reopen_for_revision: only from complete
    if status == "complete":
        result["reopen_for_revision"] = None
    else:
        result["reopen_for_revision"] = (
            f"Cannot reopen: item status is '{status}'. "
            f"Item must be 'complete' to reopen for revision."
        )

    # block: from ready or in_progress
    if status in ("ready", "in_progress"):
        result["block"] = None
    else:
        result["block"] = (
            f"Cannot block: item status is '{status}'. "
            f"Item must be 'ready' or 'in_progress' to block."
        )

    # unblock: only from blocked
    if status == "blocked":
        result["unblock"] = None
    else:
        result["unblock"] = (
            f"Cannot unblock: item status is '{status}'. "
            f"Item must be 'blocked' to unblock."
        )

    # generate_prompt: from ready or in_progress
    if status in ("ready", "in_progress"):
        result["generate_prompt"] = None
    else:
        result["generate_prompt"] = (
            f"Cannot generate prompt: item status is '{status}'. "
            f"Item must be 'ready' or 'in_progress'."
        )

    # run_import: from in_progress
    if status == "in_progress":
        result["run_import"] = None
    else:
        result["run_import"] = (
            f"Cannot run import: item status is '{status}'. "
            f"Item must be 'in_progress' to import."
        )

    # generate_document: from in_progress or complete
    if status in ("in_progress", "complete"):
        result["generate_document"] = None
    else:
        result["generate_document"] = (
            f"Cannot generate document: item status is '{status}'. "
            f"Item must be 'in_progress' or 'complete'."
        )

    # view_impact_analysis: always available (read-only)
    result["view_impact_analysis"] = None

    return result


# --- Data loading ---

def load_work_item(conn: sqlite3.Connection, work_item_id: int) -> WorkItemDetail | None:
    """Load full work item detail from the database.

    :param conn: Client database connection.
    :param work_item_id: The work item ID.
    :returns: WorkItemDetail or None if not found.
    """
    row = conn.execute(
        """
        SELECT
            wi.id, wi.item_type, wi.status,
            wi.domain_id, wi.entity_id, wi.process_id,
            wi.blocked_reason, wi.started_at, wi.completed_at,
            d.name AS domain_name, d.is_service,
            e.name AS entity_name,
            p.name AS process_name
        FROM WorkItem wi
        LEFT JOIN Domain d ON d.id = wi.domain_id
        LEFT JOIN Entity e ON e.id = wi.entity_id
        LEFT JOIN Process p ON p.id = wi.process_id
        WHERE wi.id = ?
        """,
        (work_item_id,),
    ).fetchone()
    if row is None:
        return None

    (wid, item_type, status, domain_id, entity_id, process_id,
     blocked_reason, started_at, completed_at,
     domain_name, is_service, entity_name, process_name) = row
    phase = get_phase(
        item_type, is_service=bool(is_service) if is_service is not None else False
    )
    return WorkItemDetail(
        id=wid,
        item_type=item_type,
        status=status,
        phase=phase,
        phase_name=get_phase_name(phase),
        domain_id=domain_id,
        domain_name=domain_name,
        entity_id=entity_id,
        entity_name=entity_name,
        process_id=process_id,
        process_name=process_name,
        blocked_reason=blocked_reason,
        started_at=started_at,
        completed_at=completed_at,
    )


def load_dependencies(conn: sqlite3.Connection, work_item_id: int) -> list[DependencyRow]:
    """Load upstream and downstream dependencies for a work item.

    :param conn: Client database connection.
    :param work_item_id: The work item ID.
    :returns: List of DependencyRow (both upstream and downstream).
    """
    deps = []

    # Upstream: items this depends on
    upstream_rows = conn.execute(
        """
        SELECT wi.id, wi.item_type, wi.status,
               d.name AS domain_name, e.name AS entity_name, p.name AS process_name
        FROM Dependency dep
        JOIN WorkItem wi ON wi.id = dep.depends_on_id
        LEFT JOIN Domain d ON d.id = wi.domain_id
        LEFT JOIN Entity e ON e.id = wi.entity_id
        LEFT JOIN Process p ON p.id = wi.process_id
        WHERE dep.work_item_id = ?
        """,
        (work_item_id,),
    ).fetchall()
    for row in upstream_rows:
        deps.append(DependencyRow(
            work_item_id=row[0], item_type=row[1], status=row[2],
            domain_name=row[3], entity_name=row[4], process_name=row[5],
            direction="upstream",
        ))

    # Downstream: items that depend on this
    downstream_rows = conn.execute(
        """
        SELECT wi.id, wi.item_type, wi.status,
               d.name AS domain_name, e.name AS entity_name, p.name AS process_name
        FROM Dependency dep
        JOIN WorkItem wi ON wi.id = dep.work_item_id
        LEFT JOIN Domain d ON d.id = wi.domain_id
        LEFT JOIN Entity e ON e.id = wi.entity_id
        LEFT JOIN Process p ON p.id = wi.process_id
        WHERE dep.depends_on_id = ?
        """,
        (work_item_id,),
    ).fetchall()
    for row in downstream_rows:
        deps.append(DependencyRow(
            work_item_id=row[0], item_type=row[1], status=row[2],
            domain_name=row[3], entity_name=row[4], process_name=row[5],
            direction="downstream",
        ))

    return deps


def load_sessions(conn: sqlite3.Connection, work_item_id: int) -> list[SessionRow]:
    """Load AI sessions for a work item, descending by creation date.

    :param conn: Client database connection.
    :param work_item_id: The work item ID.
    :returns: List of SessionRow.
    """
    rows = conn.execute(
        """
        SELECT id, session_type, import_status, started_at, completed_at,
               generated_prompt, raw_output, notes
        FROM AISession
        WHERE work_item_id = ?
        ORDER BY created_at DESC
        """,
        (work_item_id,),
    ).fetchall()
    return [
        SessionRow(
            id=r[0], session_type=r[1], import_status=r[2],
            started_at=r[3], completed_at=r[4],
            generated_prompt=r[5], raw_output=r[6], notes=r[7],
        )
        for r in rows
    ]


def load_documents(conn: sqlite3.Connection, work_item_id: int) -> list[DocumentRow]:
    """Load document generation log entries for a work item.

    :param conn: Client database connection.
    :param work_item_id: The work item ID.
    :returns: List of DocumentRow.
    """
    rows = conn.execute(
        """
        SELECT id, document_type, file_path, generated_at,
               generation_mode, git_commit_hash
        FROM GenerationLog
        WHERE work_item_id = ?
        ORDER BY generated_at DESC
        """,
        (work_item_id,),
    ).fetchall()
    return [
        DocumentRow(
            id=r[0], document_type=r[1], file_path=r[2],
            generated_at=r[3], generation_mode=r[4], git_commit_hash=r[5],
        )
        for r in rows
    ]


def load_impacts(conn: sqlite3.Connection, work_item_id: int) -> list[ImpactRow]:
    """Load change impacts where this work item is affected.

    Joins through ChangeLog -> AISession -> WorkItem to find impacts
    where the affected record maps back to this work item's scope.

    For Step 15a, we load all ChangeImpact records linked to ChangeLog
    entries from sessions belonging to this work item. The full reverse
    direction lookup (Section 12.8.1) will be refined in Step 15b.

    :param conn: Client database connection.
    :param work_item_id: The work item ID.
    :returns: List of ImpactRow, unreviewed first.
    """
    rows = conn.execute(
        """
        SELECT ci.id, ci.change_log_id, ci.affected_table,
               ci.affected_record_id, ci.impact_description,
               ci.requires_review, ci.reviewed, ci.reviewed_at,
               ci.action_required
        FROM ChangeImpact ci
        JOIN ChangeLog cl ON cl.id = ci.change_log_id
        JOIN AISession s ON s.id = cl.session_id
        WHERE s.work_item_id = ?
        ORDER BY ci.reviewed ASC, ci.id DESC
        """,
        (work_item_id,),
    ).fetchall()
    return [
        ImpactRow(
            id=r[0], change_log_id=r[1], affected_table=r[2],
            affected_record_id=r[3], impact_description=r[4],
            requires_review=bool(r[5]), reviewed=bool(r[6]),
            reviewed_at=r[7], action_required=bool(r[8]),
        )
        for r in rows
    ]

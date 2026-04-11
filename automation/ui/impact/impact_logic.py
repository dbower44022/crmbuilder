"""Impact analysis display logic — pure Python, no Qt.

Data assembly, grouping, and review state computation for the
Impact Analysis Display (Section 14.6). Also holds the in-memory
revision reason cache for ISS-013.
"""

from __future__ import annotations

import dataclasses
import sqlite3
from datetime import UTC, datetime

# ---------------------------------------------------------------------------
# Revision reason cache (ISS-013)
# ---------------------------------------------------------------------------
# WorkflowEngine.revise() does not accept a revision reason.
# The UI collects the reason at "Reopen for Revision" and stores it here.
# The next PromptGenerator.generate() call reads it from here.
_revision_reasons: dict[int, str] = {}


def store_revision_reason(work_item_id: int, reason: str) -> None:
    """Store a revision reason for later use by PromptGenerator.

    :param work_item_id: The work item being reopened.
    :param reason: The implementor's revision reason.
    """
    _revision_reasons[work_item_id] = reason


def pop_revision_reason(work_item_id: int) -> str | None:
    """Retrieve and remove a stored revision reason.

    :param work_item_id: The work item ID.
    :returns: The reason, or None if no reason was stored.
    """
    return _revision_reasons.pop(work_item_id, None)


def get_revision_reason(work_item_id: int) -> str | None:
    """Retrieve a stored revision reason without removing it.

    :param work_item_id: The work item ID.
    :returns: The reason, or None if no reason was stored.
    """
    return _revision_reasons.get(work_item_id)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class ImpactDisplayRow:
    """A single ChangeImpact record for display."""

    id: int
    change_log_id: int
    affected_table: str
    affected_record_id: int
    impact_description: str | None
    requires_review: bool
    reviewed: bool
    reviewed_at: str | None
    action_required: bool
    source_summary: str  # e.g. "Updated field 'name' on Entity"


@dataclasses.dataclass
class ImpactSummary:
    """Summary counts for an impact set."""

    total: int
    requires_review: int
    informational: int
    reviewed: int


@dataclasses.dataclass
class ChangeSetEntry:
    """A group of ChangeImpact records from the same triggering transaction."""

    key: str  # "session:{id}" or "direct:{changed_at}"
    source_label: str  # e.g. "Initial — Entity PRD: Contact" or "Direct Edit"
    timestamp: str
    change_summary: str
    unreviewed_count: int
    total_count: int
    impact_ids: list[int]


@dataclasses.dataclass
class FlaggedWorkItemEntry:
    """A work item with flagged-for-revision impacts."""

    work_item_id: int
    item_type: str
    status: str
    domain_name: str | None
    entity_name: str | None
    process_name: str | None
    flagged_count: int
    impact_summaries: list[str]
    eligible: bool
    eligibility_reason: str


# ---------------------------------------------------------------------------
# Grouping helpers
# ---------------------------------------------------------------------------

def group_impacts_by_table(
    impacts: list[ImpactDisplayRow],
) -> dict[str, tuple[list[ImpactDisplayRow], list[ImpactDisplayRow]]]:
    """Group impacts by affected_table, split into requires_review and informational.

    :param impacts: Flat list of impact rows.
    :returns: Dict of table_name -> (requires_review_list, informational_list).
    """
    groups: dict[str, tuple[list[ImpactDisplayRow], list[ImpactDisplayRow]]] = {}
    for row in impacts:
        if row.affected_table not in groups:
            groups[row.affected_table] = ([], [])
        review_list, info_list = groups[row.affected_table]
        if row.requires_review:
            review_list.append(row)
        else:
            info_list.append(row)
    return groups


def compute_impact_summary(impacts: list[ImpactDisplayRow]) -> ImpactSummary:
    """Compute summary counts for an impact set.

    :param impacts: Flat list of impact rows.
    :returns: ImpactSummary with counts.
    """
    total = len(impacts)
    requires_review = sum(1 for i in impacts if i.requires_review)
    informational = total - requires_review
    reviewed = sum(1 for i in impacts if i.reviewed)
    return ImpactSummary(
        total=total,
        requires_review=requires_review,
        informational=informational,
        reviewed=reviewed,
    )


# ---------------------------------------------------------------------------
# Revision eligibility
# ---------------------------------------------------------------------------

def get_revision_eligibility(status: str) -> tuple[bool, str]:
    """Determine if a work item is eligible for revision.

    Per Section 12.8.2, only complete work items can be reopened.

    :param status: The work item's current status.
    :returns: Tuple of (eligible, reason_text).
    """
    if status == "complete":
        return True, "Eligible for revision"
    reasons = {
        "in_progress": (
            "Work item is in_progress — flagged impacts will be "
            "included in the next session prompt"
        ),
        "blocked": "Work item is blocked — unblock before revising",
        "not_started": "Work item has not started yet",
        "ready": (
            "Work item is ready but not yet started — flagged impacts "
            "will be included when work begins"
        ),
    }
    return False, reasons.get(status, f"Status '{status}' does not support revision")


# ---------------------------------------------------------------------------
# Database queries
# ---------------------------------------------------------------------------

def load_impacts_for_work_item(
    conn: sqlite3.Connection,
    work_item_id: int,
) -> list[ImpactDisplayRow]:
    """Load ChangeImpact records where this work item is affected.

    Joins ChangeImpact → ChangeLog → AISession to get source summary.

    :param conn: Client database connection.
    :param work_item_id: The work item ID.
    :returns: List of ImpactDisplayRow.
    """
    rows = conn.execute(
        """
        SELECT ci.id, ci.change_log_id, ci.affected_table,
               ci.affected_record_id, ci.impact_description,
               ci.requires_review, ci.reviewed, ci.reviewed_at,
               ci.action_required,
               cl.table_name, cl.change_type, cl.field_name
        FROM ChangeImpact ci
        JOIN ChangeLog cl ON cl.id = ci.change_log_id
        JOIN AISession s ON s.id = cl.session_id
        WHERE s.work_item_id = ?
        ORDER BY ci.reviewed ASC, ci.id DESC
        """,
        (work_item_id,),
    ).fetchall()

    return [
        ImpactDisplayRow(
            id=r[0], change_log_id=r[1], affected_table=r[2],
            affected_record_id=r[3], impact_description=r[4],
            requires_review=bool(r[5]), reviewed=bool(r[6]),
            reviewed_at=r[7], action_required=bool(r[8]),
            source_summary=_build_source_summary(r[9], r[10], r[11]),
        )
        for r in rows
    ]


def load_change_sets(conn: sqlite3.Connection) -> list[ChangeSetEntry]:
    """Load all change sets with at least one unreviewed ChangeImpact.

    Groups by session_id for imports, by changed_at for direct edits.

    :param conn: Client database connection.
    :returns: List of ChangeSetEntry, newest first.
    """
    # Get all unreviewed impact ids with their ChangeLog info
    rows = conn.execute(
        """
        SELECT ci.id, ci.reviewed,
               cl.session_id, cl.changed_at, cl.table_name, cl.change_type,
               cl.field_name
        FROM ChangeImpact ci
        JOIN ChangeLog cl ON cl.id = ci.change_log_id
        ORDER BY cl.changed_at DESC
        """,
    ).fetchall()

    if not rows:
        return []

    # Group into change sets
    sets: dict[str, list[tuple]] = {}
    for row in rows:
        ci_id, reviewed, session_id, changed_at, table_name, change_type, field_name = row
        if session_id is not None:
            key = f"session:{session_id}"
        else:
            key = f"direct:{changed_at}"
        sets.setdefault(key, []).append(row)

    # Build entries, keeping only sets with at least one unreviewed
    entries: list[ChangeSetEntry] = []
    for key, group_rows in sets.items():
        unreviewed = sum(1 for r in group_rows if not r[1])
        if unreviewed == 0:
            continue

        total = len(group_rows)
        impact_ids = [r[0] for r in group_rows]
        first_row = group_rows[0]
        session_id = first_row[2]
        changed_at = first_row[3] or ""

        if session_id is not None:
            source_label = _get_session_source_label(conn, session_id)
            timestamp = _get_session_timestamp(conn, session_id) or changed_at
        else:
            source_label = "Direct Edit"
            timestamp = changed_at

        # Build change summary from the ChangeLog entries
        tables_changed = set()
        for r in group_rows:
            tables_changed.add(r[4])
        if len(tables_changed) == 1:
            summary = f"Changed {total} record(s) in {next(iter(tables_changed))}"
        else:
            summary = f"Changed {total} record(s) across {len(tables_changed)} tables"

        entries.append(ChangeSetEntry(
            key=key,
            source_label=source_label,
            timestamp=timestamp,
            change_summary=summary,
            unreviewed_count=unreviewed,
            total_count=total,
            impact_ids=impact_ids,
        ))

    # Sort newest first
    entries.sort(key=lambda e: e.timestamp, reverse=True)
    return entries


def load_impacts_for_change_set(
    conn: sqlite3.Connection,
    impact_ids: list[int],
) -> list[ImpactDisplayRow]:
    """Load ImpactDisplayRow records for a specific set of impact IDs.

    :param conn: Client database connection.
    :param impact_ids: The ChangeImpact.id values.
    :returns: List of ImpactDisplayRow.
    """
    if not impact_ids:
        return []

    ph = ",".join("?" * len(impact_ids))
    rows = conn.execute(
        f"SELECT ci.id, ci.change_log_id, ci.affected_table, "  # noqa: S608
        f"ci.affected_record_id, ci.impact_description, "
        f"ci.requires_review, ci.reviewed, ci.reviewed_at, "
        f"ci.action_required, "
        f"cl.table_name, cl.change_type, cl.field_name "
        f"FROM ChangeImpact ci "
        f"JOIN ChangeLog cl ON cl.id = ci.change_log_id "
        f"WHERE ci.id IN ({ph}) "
        f"ORDER BY ci.reviewed ASC, ci.id DESC",
        impact_ids,
    ).fetchall()

    return [
        ImpactDisplayRow(
            id=r[0], change_log_id=r[1], affected_table=r[2],
            affected_record_id=r[3], impact_description=r[4],
            requires_review=bool(r[5]), reviewed=bool(r[6]),
            reviewed_at=r[7], action_required=bool(r[8]),
            source_summary=_build_source_summary(r[9], r[10], r[11]),
        )
        for r in rows
    ]


def load_flagged_work_items(conn: sqlite3.Connection) -> list[FlaggedWorkItemEntry]:
    """Load work items that have action_required=TRUE ChangeImpact records.

    Groups impacts by owning work item using the mapping rules from
    Section 12.8.1.

    :param conn: Client database connection.
    :returns: List of FlaggedWorkItemEntry.
    """
    # Get all flagged impacts
    flagged = conn.execute(
        """
        SELECT ci.id, ci.affected_table, ci.affected_record_id,
               ci.impact_description
        FROM ChangeImpact ci
        WHERE ci.action_required = 1 AND ci.reviewed = 1
        """,
    ).fetchall()

    if not flagged:
        return []

    # Group by work item using simplified mapping
    wi_groups: dict[int, list[str]] = {}
    for _ci_id, table, record_id, desc in flagged:
        wi_ids = _map_to_work_items(conn, table, record_id)
        for wi_id in wi_ids:
            wi_groups.setdefault(wi_id, []).append(desc or "Impact flagged")

    # Build entries
    entries: list[FlaggedWorkItemEntry] = []
    for wi_id, summaries in wi_groups.items():
        row = conn.execute(
            """
            SELECT wi.item_type, wi.status,
                   d.name, e.name, p.name
            FROM WorkItem wi
            LEFT JOIN Domain d ON d.id = wi.domain_id
            LEFT JOIN Entity e ON e.id = wi.entity_id
            LEFT JOIN Process p ON p.id = wi.process_id
            WHERE wi.id = ?
            """,
            (wi_id,),
        ).fetchone()
        if row is None:
            continue

        item_type, status, domain_name, entity_name, process_name = row
        eligible, reason = get_revision_eligibility(status)

        entries.append(FlaggedWorkItemEntry(
            work_item_id=wi_id,
            item_type=item_type,
            status=status,
            domain_name=domain_name,
            entity_name=entity_name,
            process_name=process_name,
            flagged_count=len(summaries),
            impact_summaries=summaries[:5],  # Cap for display
            eligible=eligible,
            eligibility_reason=reason,
        ))

    return entries


def mark_impact_reviewed(
    conn: sqlite3.Connection,
    impact_id: int,
    action_required: bool,
) -> None:
    """Mark a single ChangeImpact as reviewed.

    :param conn: Client database connection.
    :param impact_id: The ChangeImpact.id.
    :param action_required: True for "Flag for Revision", False for
        "No Action Needed" or "Acknowledge".
    """
    from automation.db.connection import transaction

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    with transaction(conn):
        conn.execute(
            "UPDATE ChangeImpact SET reviewed = 1, action_required = ?, "
            "reviewed_at = ? WHERE id = ?",
            (1 if action_required else 0, now, impact_id),
        )


def mark_impacts_reviewed_bulk(
    conn: sqlite3.Connection,
    impact_ids: list[int],
    action_required: bool,
) -> None:
    """Mark multiple ChangeImpact records as reviewed in a single transaction.

    :param conn: Client database connection.
    :param impact_ids: The ChangeImpact.id values.
    :param action_required: True for "Flag for Revision", False for
        "No Action Needed" or "Acknowledge".
    """
    if not impact_ids:
        return

    from automation.db.connection import transaction

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    with transaction(conn):
        for cid in impact_ids:
            conn.execute(
                "UPDATE ChangeImpact SET reviewed = 1, action_required = ?, "
                "reviewed_at = ? WHERE id = ?",
                (1 if action_required else 0, now, cid),
            )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _build_source_summary(table_name: str, change_type: str, field_name: str | None) -> str:
    """Build a human-readable source change summary."""
    if field_name:
        return f"{change_type.title()}d field '{field_name}' on {table_name}"
    return f"{change_type.title()}d {table_name} record"


def _get_session_source_label(conn: sqlite3.Connection, session_id: int) -> str:
    """Build a source label for an AI session-triggered change set."""
    row = conn.execute(
        """
        SELECT a.session_type, w.item_type,
               d.name AS domain_name, e.name AS entity_name, p.name AS process_name
        FROM AISession a
        JOIN WorkItem w ON w.id = a.work_item_id
        LEFT JOIN Domain d ON d.id = w.domain_id
        LEFT JOIN Entity e ON e.id = w.entity_id
        LEFT JOIN Process p ON p.id = w.process_id
        WHERE a.id = ?
        """,
        (session_id,),
    ).fetchone()

    if row is None:
        return f"Session #{session_id}"

    session_type, item_type, domain_name, entity_name, process_name = row

    # Build work item description
    from automation.ui.common.readable_first import format_work_item_name
    wi_name = format_work_item_name(item_type, domain_name, entity_name, process_name)

    return f"{session_type.title()} — {wi_name}"


def _get_session_timestamp(conn: sqlite3.Connection, session_id: int) -> str | None:
    """Get the timestamp for an AI session."""
    row = conn.execute(
        "SELECT started_at FROM AISession WHERE id = ?",
        (session_id,),
    ).fetchone()
    return row[0] if row else None


def _map_to_work_items(
    conn: sqlite3.Connection,
    table_name: str,
    record_id: int,
) -> list[int]:
    """Map an affected record to owning work item(s).

    Simplified mapping based on Section 12.8.1 ownership rules.
    """
    # Tables scoped by entity
    entity_tables = {
        "Field", "FieldOption", "LayoutPanel", "LayoutRow", "LayoutTab", "ListColumn",
    }
    # Tables scoped by process
    process_tables = {
        "ProcessStep", "Requirement", "ProcessEntity", "ProcessField", "ProcessPersona",
    }

    if table_name in entity_tables:
        # Look up entity_id from the record, then find entity_prd work item
        row = conn.execute(
            f"SELECT entity_id FROM {table_name} WHERE id = ?",  # noqa: S608
            (record_id,),
        ).fetchone()
        if row and row[0]:
            wi = conn.execute(
                "SELECT id FROM WorkItem WHERE item_type = 'entity_prd' AND entity_id = ?",
                (row[0],),
            ).fetchone()
            return [wi[0]] if wi else []

    elif table_name == "Entity":
        wi = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'entity_prd' AND entity_id = ?",
            (record_id,),
        ).fetchone()
        return [wi[0]] if wi else []

    elif table_name in process_tables or table_name == "Process":
        if table_name == "Process":
            process_id = record_id
        else:
            row = conn.execute(
                f"SELECT process_id FROM {table_name} WHERE id = ?",  # noqa: S608
                (record_id,),
            ).fetchone()
            process_id = row[0] if row and row[0] else None

        if process_id:
            wi = conn.execute(
                "SELECT id FROM WorkItem WHERE item_type = 'process_definition' AND process_id = ?",
                (process_id,),
            ).fetchone()
            return [wi[0]] if wi else []

    elif table_name == "Domain":
        wi = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'domain_overview' AND domain_id = ?",
            (record_id,),
        ).fetchone()
        return [wi[0]] if wi else []

    elif table_name == "Persona":
        wi = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'master_prd'",
        ).fetchone()
        return [wi[0]] if wi else []

    elif table_name == "Relationship":
        # Relationship affects entity_prd for both entities
        row = conn.execute(
            "SELECT entity_id, related_entity_id FROM Relationship WHERE id = ?",
            (record_id,),
        ).fetchone()
        if row:
            wi_ids = []
            for eid in (row[0], row[1]):
                if eid:
                    wi = conn.execute(
                        "SELECT id FROM WorkItem WHERE item_type = 'entity_prd' AND entity_id = ?",
                        (eid,),
                    ).fetchone()
                    if wi:
                        wi_ids.append(wi[0])
            return wi_ids

    return []

"""Status snapshot — assemble a Status payload from stored records (PI-433).

The Status singleton is the engagement's versioned state-of-play document
(REQ-527 / DEC-954). Hand-written versions drifted twice, so each new
version is now *generated*: the facts come from the records the store
already keeps, and the user contributes at most a narrative paragraph.

The five legacy payload keys (``title``, ``phase``, ``version_label``,
``metadata``, ``active_work``) are kept for continuity; ``generated``
carries the assembled facts. This module is a pure read — it never
writes a version; :func:`crmbuilder_v2.access.repositories.status.generate`
does that.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2 import __version__
from crmbuilder_v2.access import engagement as engagement_access
from crmbuilder_v2.access.engagement_scope import get_active_engagement
from crmbuilder_v2.access.models import Status
from crmbuilder_v2.access.repositories import planning_items as pi_repo
from crmbuilder_v2.access.repositories import projects as project_repo
from crmbuilder_v2.access.repositories import releases as release_repo
from crmbuilder_v2.access.repositories import sessions as session_repo
from crmbuilder_v2.access.vocab import RELEASE_STATUS_TRANSITIONS

# Planning-item statuses that count as open work (the six-state lifecycle
# minus its three exits; see PLANNING_ITEM_STATUSES).
_OPEN_PI_STATUSES: tuple[str, ...] = (
    "Draft",
    "Decomposed",
    "Ready",
    "In Progress",
    "In Review",
)
# The subset listed item-by-item (the rest are counted only).
_LISTED_PI_STATUSES: frozenset[str] = frozenset({"Ready", "In Progress", "In Review"})
_RECENT_SESSION_LIMIT = 5
_TERMINAL_RELEASE_STATUSES: frozenset[str] = frozenset(
    status for status, nxt in RELEASE_STATUS_TRANSITIONS.items() if not nxt
)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _engagement_title(session: Session) -> str:
    identifier = get_active_engagement()
    if identifier:
        engagement = engagement_access.get_engagement(session, identifier)
        if engagement is not None:
            return f"{engagement.engagement_name} status"
    return "Engagement status"


def build_status_payload(
    session: Session, *, narrative: str | None = None, now: datetime | None = None
) -> dict:
    """Return the Status payload a generate call would write.

    ``narrative`` lands verbatim in ``active_work``; ``now`` is injectable
    for tests. The previous *current* version (if any) sets the
    "resolved since" cut-off.
    """
    now = now or datetime.now(UTC)
    previous = session.scalar(select(Status).where(Status.is_current.is_(True)))
    previous_version = previous.version if previous else None
    since = previous.created_at if previous else None
    if since is not None and since.tzinfo is None:
        since = since.replace(tzinfo=UTC)

    projects = project_repo.list_projects(session, status="in_flight")
    releases = [
        r
        for r in release_repo.list_releases(session)
        if r["release_status"] not in _TERMINAL_RELEASE_STATUSES
    ]

    all_pis = pi_repo.list_all(session)
    resolved_since = [
        p
        for p in all_pis
        if p["status"] == "Resolved"
        and (since is None or (_parse_iso(p["updated_at"]) or now) > since)
    ]
    open_pis = [p for p in all_pis if p["status"] in _OPEN_PI_STATUSES]
    counts = {s: sum(1 for p in open_pis if p["status"] == s) for s in _OPEN_PI_STATUSES}
    listed = [p for p in open_pis if p["status"] in _LISTED_PI_STATUSES]

    sessions = sorted(
        session_repo.list_sessions(session),
        key=lambda s: s["session_created_at"] or "",
        reverse=True,
    )[:_RECENT_SESSION_LIMIT]

    phase = (
        "; ".join(p["project_name"] for p in projects)
        if projects
        else "No project in flight"
    )
    return {
        "title": _engagement_title(session),
        "phase": phase,
        "version_label": __version__,
        "metadata": {
            "Last Updated": now.strftime("%m-%d-%y"),
            "Generated At": now.isoformat(),
            "Previous Version": previous_version,
        },
        "active_work": narrative or "",
        "generated": {
            "previous_version_created_at": since.isoformat() if since else None,
            "in_flight_projects": [
                {"identifier": p["project_identifier"], "name": p["project_name"]}
                for p in projects
            ],
            "active_releases": [
                {
                    "identifier": r["release_identifier"],
                    "title": r["release_title"],
                    "status": r["release_status"],
                }
                for r in releases
            ],
            "resolved_since_previous": [
                {"identifier": p["identifier"], "title": p["title"]}
                for p in resolved_since
            ],
            "open_planning_items": {
                "counts": counts,
                "items": [
                    {
                        "identifier": p["identifier"],
                        "title": p["title"],
                        "status": p["status"],
                    }
                    for p in listed
                ],
            },
            "recent_sessions": [
                {
                    "identifier": s["session_identifier"],
                    "title": s["session_title"],
                    "status": s["session_status"],
                }
                for s in sessions
            ],
        },
    }

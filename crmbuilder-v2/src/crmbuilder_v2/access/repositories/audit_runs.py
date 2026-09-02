"""Audit-run repository — PI-448 (REQ-551 / DEC-994).

The job record behind an audit area too long for one HTTP request (today only
the opt-in utilization area). Mirrors :mod:`deploy_runs`: create queued, a
worker claims with a heartbeat, progress and log accrete while it runs, and a
terminal status lands at the end with the reconciler's summary. Evidence and
the deposit event are written by the reconciler at completion, never here.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import (
    next_prefixed_identifier,
    serialize_identifier_assignment,
    to_dict,
)
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import AuditRun
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import (
    AUDIT_RUN_AREAS,
    AUDIT_RUN_STATUSES,
    AUDIT_RUN_TERMINAL_STATUSES,
)

_IDENTIFIER_PREFIX = "ARN"
_MAX_AUTOASSIGN_ATTEMPTS = 50
LOG_CAP = 2000


def _now() -> datetime:
    return datetime.now(UTC)


def next_audit_run_identifier(session: Session) -> str:
    identifiers = session.scalars(select(AuditRun.audit_run_identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


def _find(session: Session, identifier: str) -> AuditRun | None:
    return session.scalars(
        select(AuditRun).where(AuditRun.audit_run_identifier == identifier)
    ).one_or_none()


def _require(session: Session, identifier: str) -> AuditRun:
    row = _find(session, identifier)
    if row is None:
        raise ConflictError(f"audit run {identifier} does not exist")
    return row


def list_audit_runs(
    session: Session,
    *,
    instance_identifier: str | None = None,
    status: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    stmt = select(AuditRun).order_by(AuditRun.id.desc())
    if instance_identifier is not None:
        stmt = stmt.where(AuditRun.instance_identifier == instance_identifier)
    if status is not None:
        status = gov.require_in(status, AUDIT_RUN_STATUSES, field="status")
        stmt = stmt.where(AuditRun.audit_run_status == status)
    if limit is not None:
        stmt = stmt.limit(limit)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_audit_run(session: Session, identifier: str) -> dict | None:
    row = _find(session, identifier)
    return to_dict(row) if row else None


def active_run_for(
    session: Session, *, instance_identifier: str, area: str
) -> dict | None:
    """The queued/running run for this instance+area, if one exists."""
    row = session.scalars(
        select(AuditRun)
        .where(
            AuditRun.instance_identifier == instance_identifier,
            AuditRun.audit_run_area == area,
            AuditRun.audit_run_status.in_(("queued", "running")),
        )
        .order_by(AuditRun.id.asc())
    ).first()
    return to_dict(row) if row else None


def create_audit_run(
    session: Session, *, instance_identifier: str, area: str
) -> dict:
    """Queue one audit run, auto-assigning the next ``ARN-NNN`` identifier."""
    instance_identifier = gov.require_nonempty(
        instance_identifier, field="instance_identifier"
    )
    area = gov.require_in(area, AUDIT_RUN_AREAS, field="area")
    serialize_identifier_assignment(session, _IDENTIFIER_PREFIX)
    candidate = next_audit_run_identifier(session)
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = AuditRun(
            audit_run_identifier=candidate,
            instance_identifier=instance_identifier,
            audit_run_area=area,
            audit_run_status="queued",
            audit_run_progress={},
            audit_run_log=[],
        )
        session.add(row)
        try:
            session.flush()
        except IntegrityError as exc:
            last_error = exc
            savepoint.rollback()
            candidate = next_prefixed_identifier([candidate], _IDENTIFIER_PREFIX)
            continue
        savepoint.commit()
        return to_dict(row)
    raise ConflictError(
        "could not assign a unique audit_run identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


# ---------------------------------------------------------------------------
# Worker-side transitions (the deploy_runs claim pattern)
# ---------------------------------------------------------------------------


def claim_next_run(
    session: Session,
    *,
    worker_id: str,
    stale_after_seconds: int = 180,
) -> dict | None:
    """Atomically take the oldest claimable run for this worker, or ``None``.

    Claimable means ``queued``, or ``running`` with a stale (or absent)
    heartbeat — the worker that held it is gone; the reclaimed run restarts
    profiling, which is safe because evidence lands only at completion.
    """
    worker_id = gov.require_nonempty(worker_id, field="worker_id")
    now = _now()
    stale_before = now - timedelta(seconds=stale_after_seconds)
    claimable = or_(
        AuditRun.audit_run_status == "queued",
        (AuditRun.audit_run_status == "running")
        & or_(
            AuditRun.audit_run_heartbeat_at.is_(None),
            AuditRun.audit_run_heartbeat_at < stale_before,
        ),
    )
    candidates = session.scalars(
        select(AuditRun.id).where(claimable).order_by(AuditRun.id.asc())
    ).all()
    for row_id in candidates:
        result = session.execute(
            update(AuditRun)
            .where(AuditRun.id == row_id, claimable)
            .values(
                audit_run_status="running",
                audit_run_worker_id=worker_id,
                audit_run_heartbeat_at=now,
                updated_at=now,
            )
            .execution_options(synchronize_session="fetch")
        )
        if result.rowcount == 1:
            row = session.get(AuditRun, row_id)
            if row.audit_run_started_at is None:
                row.audit_run_started_at = now
            session.flush()
            return to_dict(row)
    return None


def heartbeat(session: Session, identifier: str, *, worker_id: str) -> None:
    """Refresh the heartbeat on a run this worker holds; conflict if lost."""
    row = _require(session, identifier)
    if row.audit_run_worker_id != worker_id or row.audit_run_status != "running":
        raise ConflictError(
            f"{identifier} is no longer held by {worker_id} "
            f"(status={row.audit_run_status}, worker={row.audit_run_worker_id})"
        )
    row.audit_run_heartbeat_at = _now()
    session.flush()


def append_log(
    session: Session,
    identifier: str,
    lines: list[tuple[str, str] | list],
    *,
    cap: int = LOG_CAP,
) -> int:
    """Append ``(level, message)`` lines (timestamped here); return new length."""
    row = _require(session, identifier)
    stamp = _now().isoformat()
    existing = list(row.audit_run_log or [])
    for entry in lines:
        level, message = entry[0], entry[1]
        existing.append([stamp, str(level), str(message)])
    if len(existing) > cap:
        existing = existing[-cap:]
    row.audit_run_log = existing
    row.audit_run_heartbeat_at = _now()
    session.flush()
    return len(existing)


def set_progress(session: Session, identifier: str, progress: dict) -> dict:
    """Merge ``progress`` counters into the run's live progress object."""
    if not isinstance(progress, dict):
        raise UnprocessableError(
            [FieldError("progress", "invalid_value", "progress must be an object")]
        )
    row = _require(session, identifier)
    current = dict(row.audit_run_progress or {})
    current.update(progress)
    row.audit_run_progress = current
    row.audit_run_heartbeat_at = _now()
    session.flush()
    return to_dict(row)


def finish(
    session: Session,
    identifier: str,
    *,
    status: str,
    summary: dict | None = None,
    error: str | None = None,
) -> dict:
    """Land a terminal status. The progress, summary and log are retained."""
    status = gov.require_in(status, AUDIT_RUN_TERMINAL_STATUSES, field="status")
    row = _require(session, identifier)
    row.audit_run_status = status
    row.audit_run_error = error
    if summary is not None:
        row.audit_run_summary = summary
    row.audit_run_ended_at = _now()
    session.flush()
    return to_dict(row)

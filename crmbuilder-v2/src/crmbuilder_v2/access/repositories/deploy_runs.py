"""Deploy-run repository — PI-419 (REQ-522, PRJ-111).

A ``deploy_run`` (``DEP-NNN``) is the engagement-scoped record of one
provisioning job: created ``queued`` by the API, claimed and driven by a deploy
worker through the ordered deploy phases, and landed on a terminal status. It
is an operational log, not a governance entity — no ``change_log`` / ``refs``
participation (the ``publish_runs`` precedent, DEC-447).

The repo owns everything the worker needs to run safely across restarts:

* :func:`claim_next_run` — a single conditional UPDATE that takes a ``queued``
  run, or a ``running`` run whose heartbeat has gone stale (the service that
  owned it restarted), so no two workers ever hold the same run;
* :func:`heartbeat` / :func:`append_log` / :func:`set_phase` — progress
  writes that reassign whole JSON columns so SQLAlchemy sees the change;
* :func:`finish` / :func:`request_cancel` / :func:`requeue` — the terminal
  transitions. A failed run keeps its ``state`` (the droplet it created, the
  phase it reached) so a retry resumes rather than starting over (DEC-945).
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
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import DeployRun
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import (
    DEPLOY_RUN_PHASES,
    DEPLOY_RUN_STATUSES,
    DEPLOY_RUN_TERMINAL_STATUSES,
)

_IDENTIFIER_PREFIX = "DEP"
_MAX_AUTOASSIGN_ATTEMPTS = 50
#: Log lines kept per run; older lines are dropped from the front.
LOG_CAP = 2000


def _now() -> datetime:
    return datetime.now(UTC)


def next_deploy_run_identifier(session: Session) -> str:
    """Compute the next free ``DEP-NNN`` identifier for the active engagement."""
    identifiers = session.scalars(select(DeployRun.deploy_run_identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


def _find(session: Session, identifier: str) -> DeployRun | None:
    return session.scalars(
        select(DeployRun).where(DeployRun.deploy_run_identifier == identifier)
    ).first()


def _require(session: Session, identifier: str) -> DeployRun:
    row = _find(session, identifier)
    if row is None:
        raise NotFoundError("deploy_run", identifier)
    return row


def list_deploy_runs(
    session: Session,
    *,
    instance_identifier: str | None = None,
    status: str | None = None,
    limit: int | None = None,
    include_log: bool = False,
) -> list[dict]:
    """Return deploy runs (newest first), optionally filtered.

    The log is omitted unless ``include_log`` — a list view never needs it and
    it is the one column that grows.
    """
    stmt = select(DeployRun).order_by(DeployRun.id.desc())
    if instance_identifier is not None:
        stmt = stmt.where(DeployRun.instance_identifier == instance_identifier)
    if status is not None:
        status = gov.require_in(status, DEPLOY_RUN_STATUSES, field="status")
        stmt = stmt.where(DeployRun.deploy_run_status == status)
    if limit is not None:
        stmt = stmt.limit(limit)
    rows = [to_dict(r) for r in session.scalars(stmt).all()]
    if not include_log:
        for r in rows:
            r.pop("deploy_run_log", None)
    return rows


def get_deploy_run(session: Session, identifier: str) -> dict | None:
    """Return one deploy run by its ``DEP-NNN`` identifier, or ``None``."""
    row = _find(session, identifier)
    return to_dict(row) if row is not None else None


def active_run_for_domain(session: Session, domain: str) -> dict | None:
    """Return the ``queued``/``running`` run targeting ``domain``, if any.

    Guards the API against queuing two runs that would race to create the same
    server and DNS record.
    """
    stmt = select(DeployRun).where(
        DeployRun.deploy_run_status.in_(("queued", "running"))
    )
    for row in session.scalars(stmt).all():
        if (row.deploy_run_spec or {}).get("domain") == domain:
            return to_dict(row)
    return None


def create_deploy_run(
    session: Session,
    *,
    spec: dict,
    secret_refs: dict | None = None,
    requested_by: str | None = None,
    instance_identifier: str | None = None,
    provider: str | None = None,
) -> dict:
    """Queue one deploy run, auto-assigning the next ``DEP-NNN`` identifier.

    :param spec: the non-secret request (provider choices, domain, admin
        username / email, instance name). Never a plaintext secret.
    :param secret_refs: ``{name: secret_ref}`` for the run's secrets.
    :param requested_by: the principal that queued the run.
    :param instance_identifier: set only when re-provisioning a known instance.
    :param provider: the hosting provider this run provisions against
        (PI-442 / REQ-544), stamped so the history row is self-describing.
    """
    if not isinstance(spec, dict) or not spec:
        raise UnprocessableError(
            [FieldError("spec", "required", "spec must be a non-empty object")]
        )
    serialize_identifier_assignment(session, _IDENTIFIER_PREFIX)
    candidate = next_deploy_run_identifier(session)
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = DeployRun(
            deploy_run_identifier=candidate,
            instance_identifier=instance_identifier,
            deploy_run_status="queued",
            deploy_run_spec=spec,
            deploy_run_secret_refs=secret_refs or {},
            deploy_run_state={"phases": {}},
            deploy_run_log=[],
            deploy_run_provider=provider,
            deploy_run_requested_by=requested_by,
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
        "could not assign a unique deploy_run identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


# ---------------------------------------------------------------------------
# Worker-side transitions
# ---------------------------------------------------------------------------


def claim_next_run(
    session: Session,
    *,
    worker_id: str,
    stale_after_seconds: int = 180,
) -> dict | None:
    """Atomically take the oldest claimable run for this worker, or ``None``.

    Claimable means ``queued``, or ``running`` with a heartbeat older than
    ``stale_after_seconds`` (or none at all) — the worker that held it is gone.
    The take is one conditional UPDATE keyed on the row id *and* the claimable
    predicate, so two workers racing for the same row see one success and one
    ``rowcount == 0``; the loser simply tries the next candidate.
    """
    worker_id = gov.require_nonempty(worker_id, field="worker_id")
    now = _now()
    stale_before = now - timedelta(seconds=stale_after_seconds)
    claimable = or_(
        DeployRun.deploy_run_status == "queued",
        (DeployRun.deploy_run_status == "running")
        & or_(
            DeployRun.deploy_run_heartbeat_at.is_(None),
            DeployRun.deploy_run_heartbeat_at < stale_before,
        ),
    )
    candidates = session.scalars(
        select(DeployRun.id).where(claimable).order_by(DeployRun.id.asc())
    ).all()
    for row_id in candidates:
        result = session.execute(
            update(DeployRun)
            .where(DeployRun.id == row_id, claimable)
            .values(
                deploy_run_status="running",
                deploy_run_worker_id=worker_id,
                deploy_run_heartbeat_at=now,
                deploy_run_started_at=DeployRun.deploy_run_started_at,
                updated_at=now,
            )
            .execution_options(synchronize_session="fetch")
        )
        if result.rowcount == 1:
            row = session.get(DeployRun, row_id)
            if row.deploy_run_started_at is None:
                row.deploy_run_started_at = now
            session.flush()
            return to_dict(row)
    return None


def heartbeat(session: Session, identifier: str, *, worker_id: str) -> None:
    """Refresh the heartbeat on a run this worker holds.

    Raises :class:`ConflictError` if another worker has since reclaimed it —
    the caller must stop working on the run.
    """
    row = _require(session, identifier)
    if row.deploy_run_worker_id != worker_id or row.deploy_run_status != "running":
        raise ConflictError(
            f"{identifier} is no longer held by {worker_id} "
            f"(status={row.deploy_run_status}, worker={row.deploy_run_worker_id})"
        )
    row.deploy_run_heartbeat_at = _now()
    session.flush()


def append_log(
    session: Session,
    identifier: str,
    lines: list[tuple[str, str] | list],
    *,
    cap: int = LOG_CAP,
) -> int:
    """Append ``(level, message)`` lines (timestamped here) and return the new length.

    Lines must already be masked — this layer never sees a secret to hide.
    """
    row = _require(session, identifier)
    stamp = _now().isoformat()
    existing = list(row.deploy_run_log or [])
    for entry in lines:
        level, message = entry[0], entry[1]
        existing.append([stamp, str(level), str(message)])
    if len(existing) > cap:
        existing = existing[-cap:]
    row.deploy_run_log = existing
    row.deploy_run_heartbeat_at = _now()
    session.flush()
    return len(existing)


def set_phase(
    session: Session,
    identifier: str,
    phase: str,
    *,
    state: dict | None = None,
    phase_status: str | None = None,
    error: str | None = None,
) -> dict:
    """Record that the run is in ``phase`` and merge ``state`` into the checkpoint.

    ``state`` is merged shallowly into ``deploy_run_state``; ``phase_status``
    (``running`` / ``done`` / ``failed`` / ``skipped``) and ``error`` are stored
    under ``state["phases"][phase]`` with timestamps so a resumed run can tell
    which phases already completed.
    """
    phase = gov.require_in(phase, DEPLOY_RUN_PHASES, field="phase")
    row = _require(session, identifier)
    current = dict(row.deploy_run_state or {})
    if state:
        current.update(state)
    phases = dict(current.get("phases") or {})
    entry = dict(phases.get(phase) or {})
    now = _now().isoformat()
    if phase_status is not None:
        entry["status"] = phase_status
        if phase_status == "running" and "started_at" not in entry:
            entry["started_at"] = now
        if phase_status in ("done", "failed", "skipped"):
            entry["ended_at"] = now
    if error is not None:
        entry["error"] = error
    phases[phase] = entry
    current["phases"] = phases
    row.deploy_run_phase = phase
    row.deploy_run_state = current
    row.deploy_run_heartbeat_at = _now()
    session.flush()
    return to_dict(row)


def finish(
    session: Session,
    identifier: str,
    *,
    status: str,
    error: str | None = None,
    instance_identifier: str | None = None,
) -> dict:
    """Land a terminal status. The checkpoint and log are always retained."""
    status = gov.require_in(status, DEPLOY_RUN_TERMINAL_STATUSES, field="status")
    row = _require(session, identifier)
    row.deploy_run_status = status
    row.deploy_run_error = error
    row.deploy_run_ended_at = _now()
    if instance_identifier is not None:
        row.instance_identifier = instance_identifier
    session.flush()
    return to_dict(row)


# ---------------------------------------------------------------------------
# Operator-side transitions
# ---------------------------------------------------------------------------


def request_cancel(session: Session, identifier: str) -> dict:
    """Ask the worker to stop between phases; a ``queued`` run cancels at once.

    Raises :class:`ConflictError` for a run that is already terminal.
    """
    row = _require(session, identifier)
    if row.deploy_run_status == "queued":
        row.deploy_run_status = "cancelled"
        row.deploy_run_ended_at = _now()
    elif row.deploy_run_status == "running":
        current = dict(row.deploy_run_state or {})
        current["cancel_requested"] = True
        row.deploy_run_state = current
    else:
        raise ConflictError(
            f"{identifier} is {row.deploy_run_status}; only queued or running "
            "runs can be cancelled"
        )
    session.flush()
    return to_dict(row)


def requeue(session: Session, identifier: str) -> dict:
    """Retry a ``failed`` or ``cancelled`` run in place, keeping its checkpoint.

    The run goes back to ``queued`` with its error, worker, heartbeat and end
    time cleared and the cancel flag dropped; completed phases stay marked
    ``done`` so the worker resumes at the one that did not finish.
    """
    row = _require(session, identifier)
    if row.deploy_run_status not in ("failed", "cancelled"):
        raise ConflictError(
            f"{identifier} is {row.deploy_run_status}; only failed or cancelled "
            "runs can be retried"
        )
    current = dict(row.deploy_run_state or {})
    current.pop("cancel_requested", None)
    phases = dict(current.get("phases") or {})
    for name, entry in phases.items():
        if isinstance(entry, dict) and entry.get("status") in ("failed", "running"):
            phases[name] = {k: v for k, v in entry.items() if k != "error"} | {
                "status": "retry"
            }
    current["phases"] = phases
    row.deploy_run_state = current
    row.deploy_run_status = "queued"
    row.deploy_run_error = None
    row.deploy_run_worker_id = None
    row.deploy_run_heartbeat_at = None
    row.deploy_run_ended_at = None
    session.flush()
    return to_dict(row)

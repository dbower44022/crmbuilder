"""Project repository — the first governance entity type (UI v0.7).

Per ``governance-schema-specs/workstream.md``. Eight module-level functions
back the ``/projects`` REST endpoints and the desktop panel, plus the
``PRJ-NNN`` allocator helper. Five-status workflow lifecycle with truly
-terminal terminals; the ``superseded`` terminal requires an outbound
``supersedes`` edge (DEC-125). Per-status lifecycle timestamps are server
-set on transition; client-supplied values are ignored except on a
backfill create (a create with a non-default status accepts the matching
lifecycle timestamps verbatim).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import (
    get_by_identifier,
    next_prefixed_identifier,
    require_in,
    serialize_identifier_assignment,
    to_dict,
)
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import Project
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import (
    DEFAULT_EXECUTION_MODE,
    EXECUTION_MODES,
    PROJECT_STATUS_TRANSITIONS,
    PROJECT_STATUSES,
)

_ENTITY_TYPE = "project"
_IDENTIFIER_PREFIX = "PRJ"
_IDENTIFIER_RE = re.compile(r"^PRJ-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_PATCHABLE_FIELDS = frozenset(
    {"name", "purpose", "description", "notes", "status", "execution_mode"}
)

# status value -> per-status lifecycle timestamp column.
_STATUS_TIMESTAMP = {
    "in_flight": "project_started_at",
    "complete": "project_completed_at",
    "cancelled": "project_cancelled_at",
    "superseded": "project_superseded_at",
}


def _require_status(status: object) -> str:
    return gov.require_in(status, PROJECT_STATUSES, field="project_status")


def _reject_duplicate_name(
    session: Session, name: str, *, exclude_identifier: str | None = None
) -> None:
    stmt = select(Project).where(
        func.lower(Project.project_name) == name.lower(),
        Project.project_deleted_at.is_(None),
    )
    if exclude_identifier is not None:
        stmt = stmt.where(Project.project_identifier != exclude_identifier)
    if session.scalar(stmt) is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "project_name",
                    "duplicate",
                    f"a workstream named {name!r} already exists",
                )
            ]
        )


def _get_row(session: Session, identifier: str) -> Project:
    row = get_by_identifier(session, Project, Project.project_identifier, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


def _validate_terminal_edges(session: Session, identifier: str, status: str) -> None:
    """Enforce the supersession-requires-edge rule at the access layer."""
    if status == "superseded":
        gov.reject_missing_supersedes_edge(
            session, entity_type=_ENTITY_TYPE, identifier=identifier
        )


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_projects(
    session: Session, *, include_deleted: bool = False, status: str | None = None
) -> list[dict]:
    stmt = select(Project).order_by(Project.project_identifier)
    if not include_deleted:
        stmt = stmt.where(Project.project_deleted_at.is_(None))
    if status is not None:
        stmt = stmt.where(Project.project_status == status)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_project(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    row = get_by_identifier(session, Project, Project.project_identifier, identifier)
    if row is None:
        return None
    if row.project_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_project_identifier(session: Session) -> str:
    identifiers = session.scalars(select(Project.project_identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_row(
    identifier, name, purpose, description, notes, status, execution_mode
) -> Project:
    return Project(
        project_identifier=identifier,
        project_name=name,
        project_purpose=purpose,
        project_description=description,
        project_notes=notes,
        project_status=status,
        project_execution_mode=execution_mode,
    )


def _insert_with_autoassign(
    session, name, purpose, description, notes, status, execution_mode
):
    # REQ-446 / PI-384: serialize per-prefix assignment so concurrent
    # Postgres writers don't race the read-then-probe loop (no-op on SQLite).
    serialize_identifier_assignment(session, _IDENTIFIER_PREFIX)
    candidate = next_project_identifier(session)
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_row(
            candidate, name, purpose, description, notes, status, execution_mode
        )
        session.add(row)
        try:
            session.flush()
        except IntegrityError as exc:
            last_error = exc
            savepoint.rollback()
            candidate = _increment_identifier(candidate)
            continue
        savepoint.commit()
        return row
    raise ConflictError(
        "could not assign a unique workstream identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_project(
    session: Session,
    *,
    name: str,
    purpose: str,
    description: str,
    notes: str | None = None,
    status: str = "planned",
    identifier: str | None = None,
    references: list[dict] | None = None,
    timestamps: dict | None = None,
    execution_mode: str = DEFAULT_EXECUTION_MODE,
) -> dict:
    """Create a workstream.

    ``status`` defaults to ``planned``. A create with a non-default status
    is the backfill path: the matching lifecycle timestamps may be supplied
    in ``timestamps`` (a dict of column-name → ISO/datetime) and are applied
    verbatim; otherwise the matching status timestamp is server-set to now.
    ``references`` is an optional list of edge specs created in the same
    transaction (used to supply the ``supersedes`` edge for a ``superseded``
    create).
    """
    name = gov.require_nonempty(name, field="project_name")
    purpose = gov.require_nonempty(purpose, field="project_purpose")
    description = gov.require_nonempty(description, field="project_description")
    if status is None:
        status = "planned"
    _require_status(status)
    require_in(execution_mode, EXECUTION_MODES, field="execution_mode")
    _reject_duplicate_name(session, name)

    if identifier is None:
        row = _insert_with_autoassign(
            session, name, purpose, description, notes, status, execution_mode
        )
    else:
        gov.require_identifier_format(
            identifier, regex=_IDENTIFIER_RE, field="project_identifier",
            example="PRJ-001",
        )
        if get_by_identifier(session, Project, Project.project_identifier, identifier) is not None:
            raise ConflictError(f"workstream {identifier!r} already exists")
        row = _new_row(
            identifier, name, purpose, description, notes, status, execution_mode
        )
        session.add(row)
        session.flush()

    # Backfill lifecycle timestamps (verbatim) or server-set the matching one.
    if status != "planned":
        gov.apply_timestamps(row, timestamps)
        gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)
    session.flush()

    gov.apply_reference_list(session, references)
    _validate_terminal_edges(session, row.project_identifier, status)

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.project_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_project(
    session: Session,
    identifier: str,
    *,
    project_identifier: str | None = None,
    name: str | None = None,
    purpose: str | None = None,
    description: str | None = None,
    notes: str | None = None,
    status: str | None = None,
    references: list[dict] | None = None,
    execution_mode: str | None = None,
) -> dict:
    row = _get_row(session, identifier)
    if project_identifier is not None and project_identifier != identifier:
        raise UnprocessableError(
            [
                FieldError(
                    "project_identifier",
                    "path_mismatch",
                    "identifier in body must match the path",
                )
            ]
        )
    before = to_dict(row)

    name = gov.require_nonempty(name, field="project_name")
    purpose = gov.require_nonempty(purpose, field="project_purpose")
    description = gov.require_nonempty(description, field="project_description")
    if name.lower() != row.project_name.lower():
        _reject_duplicate_name(session, name, exclude_identifier=identifier)

    gov.apply_reference_list(session, references)

    if status is not None and status != row.project_status:
        _require_status(status)
        gov.check_transition(
            row.project_status, status, PROJECT_STATUS_TRANSITIONS
        )
        row.project_status = status
        gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)

    if execution_mode is not None:
        require_in(execution_mode, EXECUTION_MODES, field="execution_mode")
        row.project_execution_mode = execution_mode

    row.project_name = name
    row.project_purpose = purpose
    row.project_description = description
    row.project_notes = notes
    session.flush()
    _validate_terminal_edges(session, identifier, row.project_status)

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after


def patch_project(
    session: Session, identifier: str, *, references: list[dict] | None = None, **fields
) -> dict:
    unknown = set(fields) - _PATCHABLE_FIELDS
    if unknown:
        raise UnprocessableError(
            [
                FieldError(
                    "fields",
                    "unknown_field",
                    f"unknown patchable fields: {sorted(unknown)}",
                )
            ]
        )
    row = _get_row(session, identifier)
    before = to_dict(row)

    gov.apply_reference_list(session, references)

    if "name" in fields:
        name = gov.require_nonempty(fields["name"], field="project_name")
        if name.lower() != row.project_name.lower():
            _reject_duplicate_name(session, name, exclude_identifier=identifier)
        row.project_name = name
    if "purpose" in fields:
        row.project_purpose = gov.require_nonempty(
            fields["purpose"], field="project_purpose"
        )
    if "description" in fields:
        row.project_description = gov.require_nonempty(
            fields["description"], field="project_description"
        )
    if "notes" in fields:
        row.project_notes = fields["notes"]
    if "execution_mode" in fields:
        row.project_execution_mode = require_in(
            fields["execution_mode"], EXECUTION_MODES, field="execution_mode"
        )
    if "status" in fields:
        status = _require_status(fields["status"])
        if status != row.project_status:
            gov.check_transition(
                row.project_status, status, PROJECT_STATUS_TRANSITIONS
            )
            row.project_status = status
            gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)

    session.flush()
    _validate_terminal_edges(session, identifier, row.project_status)

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after


def delete_project(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.project_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.project_deleted_at = datetime.now(UTC)
    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after


def restore_project(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.project_deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "project_deleted_at",
                    "not_deleted",
                    "workstream is not soft-deleted",
                )
            ]
        )
    before = to_dict(row)
    row.project_deleted_at = None
    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after


# ---------------------------------------------------------------------------
# Build-run claim — the heartbeat lease (REQ-423 / PI-364)
# ---------------------------------------------------------------------------

# The default lease staleness: a claim whose `project_claimed_at` is older than
# this is treated as abandoned (a crashed runtime) and may be reclaimed. Chosen
# comfortably larger than the runtime's heartbeat interval so a live, long-running
# build (its heartbeat keeps the claim fresh) is never wrongly reclaimed.
DEFAULT_CLAIM_STALE_SECONDS = 300


def _as_aware(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; treat a naive value as UTC."""
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def claim_project(
    session: Session,
    identifier: str,
    *,
    claimed_by: str,
    stale_seconds: float = DEFAULT_CLAIM_STALE_SECONDS,
) -> dict:
    """Acquire the exclusive build-run claim (heartbeat lease) for a project.

    Grants when the project is unclaimed, already held by this claimant
    (idempotent — also refreshes the lease), or the current holder's lease is
    stale (``project_claimed_at`` older than ``stale_seconds`` — a crashed
    runtime). Raises :class:`ConflictError` only when the project is held by a
    *different* runtime whose lease is still fresh. Sets both ``project_claimed_by``
    and ``project_claimed_at`` (now) together.
    """
    if not isinstance(claimed_by, str) or not claimed_by:
        raise UnprocessableError(
            [FieldError("claimed_by", "required", "claimed_by is required")]
        )
    row = _get_row(session, identifier)
    now = datetime.now(UTC)
    holder = row.project_claimed_by
    if holder is not None and holder != claimed_by:
        at = _as_aware(row.project_claimed_at)
        fresh = at is not None and (now - at).total_seconds() < stale_seconds
        if fresh:
            raise ConflictError(
                f"project {identifier!r} is being driven by {holder!r} since "
                f"{at.isoformat()}; its build-run lease is still fresh."
            )
    before = to_dict(row)
    row.project_claimed_by = claimed_by
    row.project_claimed_at = now
    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after


def heartbeat_project(
    session: Session, identifier: str, *, claimed_by: str
) -> dict:
    """Refresh the lease (``project_claimed_at`` = now), only while still held.

    Raises :class:`ConflictError` if the claim was lost (the project is now
    unclaimed or claimed by a different runtime) so the heartbeating runtime
    learns it must stop driving.
    """
    if not isinstance(claimed_by, str) or not claimed_by:
        raise UnprocessableError(
            [FieldError("claimed_by", "required", "claimed_by is required")]
        )
    row = _get_row(session, identifier)
    if row.project_claimed_by != claimed_by:
        raise ConflictError(
            f"project {identifier!r} is no longer claimed by {claimed_by!r} "
            f"(now {row.project_claimed_by!r}); the build-run claim was lost."
        )
    before = to_dict(row)
    row.project_claimed_at = datetime.now(UTC)
    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after


def release_project(
    session: Session, identifier: str, *, claimed_by: str, force: bool = False
) -> dict:
    """Release the build-run claim — clears both claim columns.

    Idempotent when already unclaimed. Raises :class:`ConflictError` if held by a
    different claimant unless ``force`` is set (the deliberate override for an
    operator clearing a confirmed-dead run).
    """
    row = _get_row(session, identifier)
    holder = row.project_claimed_by
    if holder is None:
        return to_dict(row)
    if holder != claimed_by and not force:
        raise ConflictError(
            f"project {identifier!r} is claimed by {holder!r}, not "
            f"{claimed_by!r}; pass force to override."
        )
    before = to_dict(row)
    row.project_claimed_by = None
    row.project_claimed_at = None
    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after

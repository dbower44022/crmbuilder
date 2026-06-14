"""Work Task repository — PI-112 Phase 4b governance entity.

The single-area unit of execution within a Workstream (WTK- identifier).
Carries exactly one ``area`` (validated against System ∪ this engagement's
Engagement areas) and is agent-claimable. Lifecycle Planned → Ready → Claimed
→ In Progress → Complete, with Blocked and Failed states. Membership in a
Workstream is a ``work_task_belongs_to_workstream`` edge supplied inline via
``references``.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import (
    get_by_identifier,
    next_prefixed_identifier,
    to_dict,
)
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import WorkTask
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.repositories.engagement_areas import valid_area_names
from crmbuilder_v2.access.vocab import (
    WORK_TASK_STATUS_TRANSITIONS,
    WORK_TASK_STATUSES,
)

_ENTITY_TYPE = "work_task"
_IDENTIFIER_PREFIX = "WTK"
_IDENTIFIER_RE = re.compile(r"^WTK-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_PATCHABLE_FIELDS = frozenset({"title", "description", "notes", "status", "area"})
_STATUS_TIMESTAMP = {
    "In Progress": "work_task_started_at",
    "Complete": "work_task_completed_at",
}


def _require_status(status: object) -> str:
    return gov.require_in(status, WORK_TASK_STATUSES, field="work_task_status")


def _require_area(session: Session, area: object) -> str:
    if not isinstance(area, str) or not area:
        raise UnprocessableError(
            [FieldError("work_task_area", "required", "a single area is required")]
        )
    allowed = valid_area_names(session)
    if area not in allowed:
        raise UnprocessableError(
            [
                FieldError(
                    "work_task_area",
                    "unknown_area",
                    f"'{area}' is not a valid area (System ∪ Engagement)",
                )
            ]
        )
    return area


def _get_row(session: Session, identifier: str) -> WorkTask:
    row = get_by_identifier(session, WorkTask, WorkTask.work_task_identifier, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# --- reads ------------------------------------------------------------------


def list_work_tasks(
    session: Session,
    *,
    include_deleted: bool = False,
    status: str | None = None,
    area: str | None = None,
) -> list[dict]:
    stmt = select(WorkTask).order_by(WorkTask.work_task_identifier)
    if not include_deleted:
        stmt = stmt.where(WorkTask.work_task_deleted_at.is_(None))
    if status is not None:
        stmt = stmt.where(WorkTask.work_task_status == status)
    if area is not None:
        stmt = stmt.where(WorkTask.work_task_area == area)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_work_task(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    row = get_by_identifier(session, WorkTask, WorkTask.work_task_identifier, identifier)
    if row is None:
        return None
    if row.work_task_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_work_task_identifier(session: Session) -> str:
    identifiers = session.scalars(select(WorkTask.work_task_identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# --- writes -----------------------------------------------------------------


def _new_row(identifier, title, description, area, notes, status) -> WorkTask:
    return WorkTask(
        work_task_identifier=identifier,
        work_task_title=title,
        work_task_description=description,
        work_task_area=area,
        work_task_notes=notes,
        work_task_status=status,
    )


def _insert_with_autoassign(session, title, description, area, notes, status):
    candidate = next_work_task_identifier(session)
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_row(candidate, title, description, area, notes, status)
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
        "could not assign a unique work_task identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_work_task(
    session: Session,
    *,
    title: str,
    area: str,
    description: str | None = None,
    notes: str | None = None,
    status: str = "Planned",
    identifier: str | None = None,
    references: list[dict] | None = None,
    timestamps: dict | None = None,
) -> dict:
    """Create a single-area work task.

    ``references`` typically carries the ``work_task_belongs_to_workstream``
    edge to its parent Workstream. ``area`` must be a member of System ∪ this
    engagement's Engagement areas.
    """
    title = gov.require_nonempty(title, field="work_task_title")
    area = _require_area(session, area)
    if status is None:
        status = "Planned"
    _require_status(status)

    if identifier is None:
        row = _insert_with_autoassign(
            session, title, description, area, notes, status
        )
    else:
        gov.require_identifier_format(
            identifier, regex=_IDENTIFIER_RE, field="work_task_identifier",
            example="WTK-001",
        )
        if get_by_identifier(session, WorkTask, WorkTask.work_task_identifier, identifier) is not None:
            raise ConflictError(f"work_task {identifier!r} already exists")
        row = _new_row(identifier, title, description, area, notes, status)
        session.add(row)
        session.flush()

    if status != "Planned":
        gov.apply_timestamps(row, timestamps)
        gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)
    session.flush()

    gov.apply_reference_list(session, references)

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.work_task_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def _apply_status(row: WorkTask, status: str) -> None:
    _require_status(status)
    if status != row.work_task_status:
        gov.check_transition(
            row.work_task_status, status, WORK_TASK_STATUS_TRANSITIONS
        )
        row.work_task_status = status
        gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)


def update_work_task(
    session: Session,
    identifier: str,
    *,
    work_task_identifier: str | None = None,
    title: str | None = None,
    area: str | None = None,
    description: str | None = None,
    notes: str | None = None,
    status: str | None = None,
    references: list[dict] | None = None,
) -> dict:
    row = _get_row(session, identifier)
    if work_task_identifier is not None and work_task_identifier != identifier:
        raise UnprocessableError(
            [
                FieldError(
                    "work_task_identifier",
                    "path_mismatch",
                    "identifier in body must match the path",
                )
            ]
        )
    before = to_dict(row)

    title = gov.require_nonempty(title, field="work_task_title")
    area = _require_area(session, area)

    gov.apply_reference_list(session, references)

    if status is not None:
        _apply_status(row, status)

    row.work_task_title = title
    row.work_task_area = area
    row.work_task_description = description
    row.work_task_notes = notes
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


def patch_work_task(
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

    if "title" in fields:
        row.work_task_title = gov.require_nonempty(
            fields["title"], field="work_task_title"
        )
    if "area" in fields:
        row.work_task_area = _require_area(session, fields["area"])
    if "description" in fields:
        row.work_task_description = fields["description"]
    if "notes" in fields:
        row.work_task_notes = fields["notes"]
    if "status" in fields:
        _apply_status(row, fields["status"])

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


def claim_work_task(session: Session, identifier: str, *, claimed_by: str) -> dict:
    """Atomically claim a task for an agent.

    Sets ``claimed_by``/``claimed_at`` and advances the lifecycle ``Ready →
    Claimed`` (PI-137) so a claimed task carries the ``Claimed`` status the
    lifecycle defines, not a still-``Ready`` row with a claimant attached.
    Idempotent for the same claimant; raises ConflictError if already claimed
    by a different agent.
    """
    if not isinstance(claimed_by, str) or not claimed_by:
        raise UnprocessableError(
            [FieldError("claimed_by", "required", "claimed_by is required")]
        )
    row = _get_row(session, identifier)
    # PI-190 / REQ-165: an interactive PI is ADO-invisible at every tier — its
    # Work Tasks must not be claimed for ADO execution (DEC-425). Lazy import to
    # keep this low-level repo free of a module-level dependency on pm.
    from crmbuilder_v2.access.repositories import pm as _pm

    if _pm.work_task_is_ado_interactive(session, identifier):
        raise ConflictError(
            f"work_task {identifier!r} belongs to an execution_mode "
            f"'interactive' planning item; the ADO must not claim it — "
            f"interactive work is executed by a human."
        )
    if row.work_task_claimed_by is not None:
        if row.work_task_claimed_by == claimed_by:
            return to_dict(row)
        raise ConflictError(
            f"work_task {identifier!r} already claimed by "
            f"{row.work_task_claimed_by!r}"
        )
    before = to_dict(row)
    row.work_task_claimed_by = claimed_by
    row.work_task_claimed_at = datetime.now(UTC)
    if row.work_task_status == "Ready":
        _apply_status(row, "Claimed")
    session.flush()
    after = to_dict(row)
    emit(
        session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
        operation="update", before=before, after=after,
    )
    return after


def release_work_task(session: Session, identifier: str, *, claimed_by: str) -> dict:
    """Release a claim. Idempotent if unclaimed; rejects a wrong claimant."""
    row = _get_row(session, identifier)
    if row.work_task_claimed_by is None:
        return to_dict(row)
    if row.work_task_claimed_by != claimed_by:
        raise ConflictError(
            f"work_task {identifier!r} is claimed by "
            f"{row.work_task_claimed_by!r}, not {claimed_by!r}"
        )
    before = to_dict(row)
    row.work_task_claimed_by = None
    row.work_task_claimed_at = None
    session.flush()
    after = to_dict(row)
    emit(
        session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
        operation="update", before=before, after=after,
    )
    return after


def delete_work_task(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.work_task_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.work_task_deleted_at = datetime.now(UTC)
    session.flush()
    after = to_dict(row)
    emit(
        session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
        operation="update", before=before, after=after,
    )
    return after


def restore_work_task(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.work_task_deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "work_task_deleted_at", "not_deleted",
                    "work_task is not soft-deleted",
                )
            ]
        )
    before = to_dict(row)
    row.work_task_deleted_at = None
    session.flush()
    after = to_dict(row)
    emit(
        session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
        operation="update", before=before, after=after,
    )
    return after

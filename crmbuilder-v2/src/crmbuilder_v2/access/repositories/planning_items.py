"""Planning items repository."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import (
    next_prefixed_identifier,
    require_in,
    require_string,
    to_dict,
    validate_optional_length,
    validate_optional_value_list,
)
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
    ValidationError,
)
from crmbuilder_v2.access.models import PlanningItem
from crmbuilder_v2.access.vocab import (
    AREAS,
    PLANNING_ITEM_STATUSES,
    PLANNING_ITEM_TYPES,
)

_ENTITY_TYPE = "planning_item"
_IDENTIFIER_PREFIX = "PI"
_IDENTIFIER_RE = re.compile(r"^PI-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50


def compute_next_identifier(session: Session) -> str:
    """Return the next available ``PI-NNN`` identifier."""
    identifiers = session.scalars(select(PlanningItem.identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        raise UnprocessableError(
            [
                FieldError(
                    "identifier",
                    "invalid_format",
                    r"must match ^PI-\d{3}$ (e.g. PI-001)",
                )
            ]
        )
    return identifier


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"

_UPDATABLE_FIELDS = frozenset(
    {
        "title",
        "item_type",
        "description",
        "status",
        "resolution_reference",
        "executive_summary",
        "area",
    }
)

_EXECUTIVE_SUMMARY_MIN = 200
_EXECUTIVE_SUMMARY_MAX = 800


def get(session: Session, identifier: str) -> dict:
    row = session.scalar(
        select(PlanningItem).where(PlanningItem.identifier == identifier)
    )
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return to_dict(row)


def list_all(session: Session) -> list[dict]:
    rows = session.scalars(select(PlanningItem).order_by(PlanningItem.identifier)).all()
    return [to_dict(r) for r in rows]


def _new_planning_item_row(
    identifier: str,
    title: str,
    item_type: str,
    description: str,
    status: str,
    resolution_reference: str | None,
    executive_summary: str | None,
    area: list[str] | None,
) -> PlanningItem:
    return PlanningItem(
        identifier=identifier,
        title=title,
        item_type=item_type,
        description=description,
        status=status,
        resolution_reference=resolution_reference,
        executive_summary=executive_summary,
        area=area,
    )


def _insert_with_autoassign(
    session: Session,
    title: str,
    item_type: str,
    description: str,
    status: str,
    resolution_reference: str | None,
    executive_summary: str | None,
    area: list[str] | None,
) -> PlanningItem:
    """Insert a planning_item with a server-assigned identifier (PI-002)."""
    candidate = compute_next_identifier(session)
    last_error: IntegrityError | None = None
    for _attempt in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_planning_item_row(
            candidate,
            title,
            item_type,
            description,
            status,
            resolution_reference,
            executive_summary,
            area,
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
        "could not assign a unique planning_item identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create(
    session: Session,
    *,
    identifier: str | None = None,
    title: str,
    item_type: str,
    description: str = "",
    status: str,
    resolution_reference: str | None = None,
    executive_summary: str | None = None,
    area: list[str] | None = None,
) -> dict:
    """Create a planning_item.

    ``identifier`` is server-assigned when omitted (``None``). When
    supplied it must match ``^PI-\\d{3}$`` and not already exist.

    ``executive_summary`` (PI-074) is optional in v0.8; when supplied it
    must be a 200-800 character audience-facing summary. PI-075 will
    backfill and tighten the column to NOT NULL.

    ``area`` (PI-076) is optional until PI-083 backfills open items and
    tightens the column to NOT NULL; when supplied it must be a non-empty
    list of distinct values drawn from :data:`vocab.AREAS`.
    """
    require_string(title, field="title")
    require_in(item_type, PLANNING_ITEM_TYPES, field="item_type")
    require_in(status, PLANNING_ITEM_STATUSES, field="status")
    executive_summary = validate_optional_length(
        executive_summary,
        field="executive_summary",
        min_len=_EXECUTIVE_SUMMARY_MIN,
        max_len=_EXECUTIVE_SUMMARY_MAX,
    )
    area = validate_optional_value_list(area, field="area", allowed=AREAS)

    if identifier is None:
        row = _insert_with_autoassign(
            session,
            title,
            item_type,
            description or "",
            status,
            resolution_reference,
            executive_summary,
            area,
        )
    else:
        _require_identifier_format(identifier)
        if (
            session.scalar(
                select(PlanningItem).where(PlanningItem.identifier == identifier)
            )
            is not None
        ):
            raise ConflictError(f"planning_item {identifier!r} already exists")
        row = _new_planning_item_row(
            identifier,
            title,
            item_type,
            description or "",
            status,
            resolution_reference,
            executive_summary,
            area,
        )
        session.add(row)
        session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update(session: Session, identifier: str, **fields) -> dict:
    row = session.scalar(
        select(PlanningItem).where(PlanningItem.identifier == identifier)
    )
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    unknown = set(fields) - _UPDATABLE_FIELDS
    if unknown:
        raise ValidationError(
            [
                FieldError(
                    "fields",
                    "unknown_field",
                    f"unknown updatable fields: {sorted(unknown)}",
                )
            ]
        )
    if "item_type" in fields:
        require_in(fields["item_type"], PLANNING_ITEM_TYPES, field="item_type")
    if "status" in fields:
        require_in(fields["status"], PLANNING_ITEM_STATUSES, field="status")
    if "executive_summary" in fields:
        fields["executive_summary"] = validate_optional_length(
            fields["executive_summary"],
            field="executive_summary",
            min_len=_EXECUTIVE_SUMMARY_MIN,
            max_len=_EXECUTIVE_SUMMARY_MAX,
        )
    if "area" in fields:
        fields["area"] = validate_optional_value_list(
            fields["area"], field="area", allowed=AREAS
        )
    before = to_dict(row)
    for k, v in fields.items():
        setattr(row, k, v)
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


def delete(session: Session, identifier: str) -> dict:
    row = session.scalar(
        select(PlanningItem).where(PlanningItem.identifier == identifier)
    )
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    before = to_dict(row)
    session.delete(row)
    session.flush()
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="delete",
        before=before,
        after=None,
    )
    return before


def upsert(session: Session, *, identifier: str, **fields) -> dict:
    existing = session.scalar(
        select(PlanningItem).where(PlanningItem.identifier == identifier)
    )
    if existing is None:
        return create(session, identifier=identifier, **fields)
    return update(session, identifier, **fields)


# ---------------------------------------------------------------------------
# PI-077 — orchestrator claim management (claimed_by / claimed_at)
# ---------------------------------------------------------------------------


def claim_planning_item(session: Session, identifier: str, claimant: str) -> dict:
    """Atomically claim an unclaimed planning_item for ``claimant``.

    ``claimant`` is the conversation identifier (``CONV-NNN``) of the
    agent taking the item. Sets ``claimed_by`` + ``claimed_at`` together.

    Optimistic concurrency: a claim on an item already held by a
    *different* claimant raises :class:`ConflictError`. A re-claim by the
    *same* claimant is idempotent (returns the row unchanged) so an agent
    retrying after a transient failure does not fail. The access engine's
    ``BEGIN IMMEDIATE`` + ``busy_timeout`` serialise concurrent writers,
    so the read-check-write below is race-safe across processes.
    """
    require_string(claimant, field="claimant")
    row = session.scalar(
        select(PlanningItem).where(PlanningItem.identifier == identifier)
    )
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    if row.claimed_by is not None:
        if row.claimed_by == claimant:
            return to_dict(row)
        raise ConflictError(
            f"planning_item {identifier!r} already claimed by {row.claimed_by!r}"
        )
    before = to_dict(row)
    row.claimed_by = claimant
    row.claimed_at = datetime.now(UTC)
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


def release_planning_item(
    session: Session, identifier: str, claimant: str | None = None
) -> dict:
    """Release a planning_item's claim, clearing ``claimed_by`` + ``claimed_at``.

    When ``claimant`` is supplied the release only proceeds if the item
    is held by that claimant (else :class:`ConflictError`) — this guards
    an agent from releasing another agent's claim. Releasing an already-
    unclaimed item is idempotent.
    """
    row = session.scalar(
        select(PlanningItem).where(PlanningItem.identifier == identifier)
    )
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    if row.claimed_by is None:
        return to_dict(row)
    if claimant is not None and row.claimed_by != claimant:
        raise ConflictError(
            f"planning_item {identifier!r} is claimed by {row.claimed_by!r}, "
            f"not {claimant!r}"
        )
    before = to_dict(row)
    row.claimed_by = None
    row.claimed_at = None
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

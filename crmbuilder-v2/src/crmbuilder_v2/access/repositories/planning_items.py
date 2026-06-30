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
    serialize_identifier_assignment,
    to_dict,
    validate_optional_value_list,
    validate_required_length,
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
from crmbuilder_v2.access.repositories._governance import check_transition
from crmbuilder_v2.access.repositories.engagement_areas import valid_area_names
from crmbuilder_v2.access.vocab import (
    DEFAULT_EXECUTION_MODE,
    EXECUTION_MODES,
    PLANNING_ITEM_STATUS_TRANSITIONS,
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
        # PI-183: a PI's own execution_mode is editable; dispatch_approved is
        # NOT (REQ-155 — its only write path is approve-dispatch).
        "execution_mode",
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
    executive_summary: str,
    area: list[str] | None,
    execution_mode: str,
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
        execution_mode=execution_mode,
    )


def _insert_with_autoassign(
    session: Session,
    title: str,
    item_type: str,
    description: str,
    status: str,
    resolution_reference: str | None,
    executive_summary: str,
    area: list[str] | None,
    execution_mode: str,
) -> PlanningItem:
    """Insert a planning_item with a server-assigned identifier (PI-002)."""
    # REQ-446 / PI-384: serialize per-prefix assignment (PG advisory lock;
    # SQLite no-op) so concurrent writers don't race the read-then-probe loop.
    serialize_identifier_assignment(session, _IDENTIFIER_PREFIX)
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
            execution_mode,
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
    status: str = "Draft",
    resolution_reference: str | None = None,
    executive_summary: str,
    area: list[str] | None = None,
    execution_mode: str = DEFAULT_EXECUTION_MODE,
) -> dict:
    """Create a planning_item.

    ``identifier`` is server-assigned when omitted (``None``). When
    supplied it must match ``^PI-\\d{3}$`` and not already exist.

    ``executive_summary`` (PI-074) is required since PI-075 (migration
    0023 tightened the column to NOT NULL): a 200-800 character
    audience-facing summary. Omitting it raises a ``ValidationError``
    (422) rather than a database ``IntegrityError`` (500).

    ``area`` (PI-076) is optional until PI-083 backfills open items and
    tightens the column to NOT NULL; when supplied it must be a non-empty
    list of distinct values, each a valid area (System ∪ this engagement's
    Engagement areas; see ``engagement_areas.valid_area_names``).
    """
    require_string(title, field="title")
    require_in(item_type, PLANNING_ITEM_TYPES, field="item_type")
    require_in(status, PLANNING_ITEM_STATUSES, field="status")
    require_in(execution_mode, EXECUTION_MODES, field="execution_mode")
    executive_summary = validate_required_length(
        executive_summary,
        field="executive_summary",
        min_len=_EXECUTIVE_SUMMARY_MIN,
        max_len=_EXECUTIVE_SUMMARY_MAX,
    )
    area = validate_optional_value_list(area, field="area", allowed=valid_area_names(session))

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
            execution_mode,
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
            execution_mode,
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
    if "execution_mode" in fields:
        require_in(fields["execution_mode"], EXECUTION_MODES, field="execution_mode")
    if "status" in fields:
        require_in(fields["status"], PLANNING_ITEM_STATUSES, field="status")
        check_transition(
            row.status, fields["status"], PLANNING_ITEM_STATUS_TRANSITIONS
        )
        # REQ-323 / PI-288: transitioning a planning item into development
        # (In Progress) or delivery (Resolved) requires it to be in a frozen
        # release's scope. Covers the conversation ``resolves`` edge too — it
        # routes through ``update(status="Resolved")``. No-op when the gate flag
        # is off (REQ-324). Lazy import avoids a module-load cycle.
        if fields["status"] in ("In Progress", "Resolved"):
            from crmbuilder_v2.access import release_gate

            release_gate.assert_developable(
                session,
                identifier,
                action=(
                    "moved to In Progress"
                    if fields["status"] == "In Progress"
                    else "resolved"
                ),
            )
    if "executive_summary" in fields:
        # NOT NULL since PI-075 — a present value must be a valid
        # 200-800 char string; the column cannot be cleared via update.
        fields["executive_summary"] = validate_required_length(
            fields["executive_summary"],
            field="executive_summary",
            min_len=_EXECUTIVE_SUMMARY_MIN,
            max_len=_EXECUTIVE_SUMMARY_MAX,
        )
    if "area" in fields:
        fields["area"] = validate_optional_value_list(
            fields["area"], field="area", allowed=valid_area_names(session)
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


# ---------------------------------------------------------------------------
# PI-183 — ADO execution_mode approval (dispatch_approved)
# ---------------------------------------------------------------------------


def approve_dispatch(session: Session, identifier: str) -> dict:
    """Record a human approval for an ``ado_with_approval`` planning_item.

    Sets ``dispatch_approved`` to True so the PM dispatcher will treat the item
    as eligible (REQ-155). This is the *only* write path for the flag — it is
    deliberately excluded from the generic ``update`` field set (DEC-424). The
    flip is recorded in the change_log. Idempotent: approving an
    already-approved item returns it unchanged.
    """
    row = session.scalar(
        select(PlanningItem).where(PlanningItem.identifier == identifier)
    )
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    if row.dispatch_approved:
        return to_dict(row)
    before = to_dict(row)
    row.dispatch_approved = True
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

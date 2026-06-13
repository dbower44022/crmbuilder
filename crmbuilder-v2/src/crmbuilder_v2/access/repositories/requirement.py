"""Requirement repository — PI-004 cohort methodology entity (v0.5+).

Per ``methodology-schema-specs/requirement.md`` v1.0. The eight
module-level functions back the ``/requirements`` REST endpoints and
the desktop panel:

* :func:`list_requirements` / :func:`get_requirement` — reads.
* :func:`create_requirement` — insert with server-side identifier
  auto-assignment (collision-safe retry, per spec acceptance criterion 8).
* :func:`update_requirement` — full replace (PUT).
* :func:`patch_requirement` — partial update (PATCH).
* :func:`delete_requirement` / :func:`restore_requirement` —
  soft-delete round-trip.
* :func:`next_requirement_identifier` — the ``REQ-NNN`` allocator helper.

Validation posture (``requirement.md`` §3.5): identifier-format,
case-insensitive global name-uniqueness, status-enum, priority-enum,
and PUT identifier/path mismatches raise :class:`UnprocessableError`
(HTTP 422); disallowed status transitions raise
:class:`StatusTransitionError` (HTTP 422 with the dedicated body
shape). Missing requirements raise :class:`NotFoundError` (404); an
explicit-identifier collision on create raises :class:`ConflictError`
(409).

The repository mirrors ``entity.py`` exactly with requirement-specific
adjustments:

* **Priority field with unconstrained transitions** per spec §3.2.3 /
  §3.4.3. The four MoSCoW values (``must`` / ``should`` / ``could`` /
  ``wont``) may freely follow any other value — there is no transition
  map for priority, only enum-membership validation. This intentionally
  differs from status, which uses the one-way propose-verify gate.
* **Global, not per-domain, name uniqueness** per spec §3.2.1 — mirrors
  ``entity.py`` exactly. A requirement is a global statement; the same
  capability scoped to two domains is one requirement with two
  ``requirement_scopes_to_domain`` edges, not two requirements.
* **Acceptance summary field** is separate from description and required
  on both POST and PUT. Plain text in v0.5+; structured Given / When /
  Then deferred per spec §3.8.
* Soft-deleting a requirement does NOT cascade-delete its outbound
  references (mirrors ``entity.py``). Those rows live in the ``refs``
  table and the soft-delete here never touches it.
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
    to_dict,
)
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import Reference, Requirement
from crmbuilder_v2.access.repositories import _rejection
from crmbuilder_v2.access.vocab import (
    REQUIREMENT_PRIORITIES,
    REQUIREMENT_STATUS_TRANSITIONS,
    REQUIREMENT_STATUSES,
)

_ENTITY_TYPE = "requirement"
_IDENTIFIER_PREFIX = "REQ"
_IDENTIFIER_RE = re.compile(r"^REQ-\d{3}$")

# Upper bound on identifier-collision retries inside
# :func:`_insert_with_autoassign`. Far above any plausible concurrent
# burst; exhausting it indicates a genuine fault, surfaced as a 409.
_MAX_AUTOASSIGN_ATTEMPTS = 50

# Fields accepted by :func:`patch_requirement`. The identifier and the
# timestamps are not patchable.
_PATCHABLE_FIELDS = frozenset(
    {"name", "description", "acceptance_summary", "notes", "priority", "status"}
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        raise UnprocessableError(
            [
                FieldError(
                    "requirement_identifier",
                    "invalid_format",
                    r"must match ^REQ-\d{3}$ (e.g. REQ-001)",
                )
            ]
        )
    return identifier


def _require_nonempty(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UnprocessableError(
            [FieldError(field, "missing_or_empty", "must be a non-empty string")]
        )
    return value.strip()


def _require_status(status: object) -> str:
    if status not in REQUIREMENT_STATUSES:
        raise UnprocessableError(
            [
                FieldError(
                    "requirement_status",
                    "invalid_value",
                    f"must be one of {sorted(REQUIREMENT_STATUSES)}",
                )
            ]
        )
    return status  # type: ignore[return-value]


def _require_priority(priority: object) -> str:
    """Validate ``requirement_priority`` against the MoSCoW enum.

    Per spec §3.2.3 / §3.4.3, priority transitions are unconstrained —
    this helper does enum-membership validation only. There is no
    paired transition map (cf. :data:`REQUIREMENT_STATUS_TRANSITIONS`).
    """
    if priority not in REQUIREMENT_PRIORITIES:
        raise UnprocessableError(
            [
                FieldError(
                    "requirement_priority",
                    "invalid_value",
                    f"must be one of {sorted(REQUIREMENT_PRIORITIES)}",
                )
            ]
        )
    return priority  # type: ignore[return-value]


def _check_transition(current: str, requested: str) -> None:
    """Raise :class:`StatusTransitionError` for a disallowed status move.

    A no-op (``requested == current``) is always permitted; otherwise
    ``requested`` must appear in the current value's successor set per
    :data:`REQUIREMENT_STATUS_TRANSITIONS`. Per ``requirement.md``
    §3.4.4 this check consults only the requirement's own status —
    never the statuses of any affiliated domains / entities / fields /
    processes / test specs.
    """
    if requested == current:
        return
    if requested not in REQUIREMENT_STATUS_TRANSITIONS.get(
        current, frozenset()
    ):
        raise StatusTransitionError(current, requested)


def _reject_duplicate_name(
    session: Session, name: str, *, exclude_identifier: str | None = None
) -> None:
    """Reject a case-insensitive ``requirement_name`` collision.

    Only non-soft-deleted rows participate in the uniqueness check, per
    ``requirement.md`` §3.2.1. Uniqueness is engagement-global (no
    domain-scoping), matching ``entity_name``'s posture and contrasting
    with ``process_name``'s per-domain posture. ``exclude_identifier``
    lets the update paths ignore the row being modified.
    """
    stmt = select(Requirement).where(
        func.lower(Requirement.requirement_name) == name.lower(),
        Requirement.requirement_deleted_at.is_(None),
    )
    if exclude_identifier is not None:
        stmt = stmt.where(
            Requirement.requirement_identifier != exclude_identifier
        )
    if session.scalar(stmt) is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "requirement_name",
                    "duplicate",
                    f"a requirement named {name!r} already exists",
                )
            ]
        )


def _get_row(session: Session, identifier: str) -> Requirement:
    """Return the ORM row (including soft-deleted) or raise NotFoundError."""
    row = get_by_identifier(session, Requirement, Requirement.requirement_identifier, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    """Return the next ``REQ-NNN`` after ``identifier`` (collision retry)."""
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_requirements(
    session: Session, *, include_deleted: bool = False
) -> list[dict]:
    """Return all requirements ordered by identifier ascending.

    Soft-deleted rows are excluded unless ``include_deleted`` is True.
    """
    stmt = select(Requirement).order_by(Requirement.requirement_identifier)
    if not include_deleted:
        stmt = stmt.where(Requirement.requirement_deleted_at.is_(None))
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_requirement(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    """Return a single requirement by identifier, or ``None`` if not visible.

    A soft-deleted row reads as ``None`` unless ``include_deleted`` is
    True — the REST layer translates ``None`` to HTTP 404.
    """
    row = get_by_identifier(session, Requirement, Requirement.requirement_identifier, identifier)
    if row is None:
        return None
    if row.requirement_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_requirement_identifier(session: Session) -> str:
    """Return the next available ``REQ-NNN`` identifier.

    Scans every row including soft-deleted ones so a retired identifier
    is never reused.
    """
    identifiers = session.scalars(
        select(Requirement.requirement_identifier)
    ).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_requirement_row(
    identifier: str,
    name: str,
    description: str,
    acceptance_summary: str,
    priority: str,
    notes: str | None,
    status: str,
) -> Requirement:
    return Requirement(
        requirement_identifier=identifier,
        requirement_name=name,
        requirement_description=description,
        requirement_acceptance_summary=acceptance_summary,
        requirement_priority=priority,
        requirement_notes=notes,
        requirement_status=status,
    )


def _insert_with_autoassign(
    session: Session,
    name: str,
    description: str,
    acceptance_summary: str,
    priority: str,
    notes: str | None,
    status: str,
) -> Requirement:
    """Insert a requirement with a server-assigned identifier, collision-safe.

    Computes the next ``REQ-NNN`` and attempts the INSERT inside a
    SAVEPOINT. A concurrent transaction that committed the same
    identifier first raises ``IntegrityError`` on flush; the savepoint
    rolls that INSERT back, the candidate is incremented, and the
    attempt repeats. Satisfies spec acceptance criterion 8 — two
    concurrent POSTs never share an identifier.
    """
    candidate = next_requirement_identifier(session)
    last_error: IntegrityError | None = None
    for _attempt in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_requirement_row(
            candidate, name, description, acceptance_summary, priority,
            notes, status,
        )
        session.add(row)
        try:
            session.flush()
        except IntegrityError as exc:
            # Another transaction committed this identifier first. Roll
            # the SAVEPOINT back (the outer transaction stays intact),
            # bump the candidate, and retry.
            last_error = exc
            savepoint.rollback()
            candidate = _increment_identifier(candidate)
            continue
        savepoint.commit()
        return row
    raise ConflictError(
        "could not assign a unique requirement identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_requirement(
    session: Session,
    *,
    name: str,
    description: str,
    acceptance_summary: str,
    priority: str | None = None,
    notes: str | None = None,
    status: str | None = None,
    identifier: str | None = None,
) -> dict:
    """Create a requirement.

    ``identifier`` is server-assigned when omitted (``None``). When
    supplied it must match ``^REQ-\\d{3}$`` and not already exist.
    ``priority`` defaults to ``should`` when None per spec §3.2.3 —
    consultants must affirmatively escalate to ``must``. ``status``
    defaults to ``candidate`` but may be set to any valid enum value
    on create (e.g. importing already-confirmed requirements).
    """
    name = _require_nonempty(name, field="requirement_name")
    description = _require_nonempty(
        description, field="requirement_description"
    )
    acceptance_summary = _require_nonempty(
        acceptance_summary, field="requirement_acceptance_summary"
    )
    if priority is None:
        priority = "should"
    _require_priority(priority)
    if status is None:
        status = "candidate"
    _require_status(status)
    _reject_duplicate_name(session, name)

    if identifier is None:
        row = _insert_with_autoassign(
            session, name, description, acceptance_summary, priority,
            notes, status,
        )
    else:
        _require_identifier_format(identifier)
        if get_by_identifier(session, Requirement, Requirement.requirement_identifier, identifier) is not None:
            raise ConflictError(f"requirement {identifier!r} already exists")
        row = _new_requirement_row(
            identifier, name, description, acceptance_summary, priority,
            notes, status,
        )
        session.add(row)
        session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.requirement_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_requirement(
    session: Session,
    identifier: str,
    *,
    requirement_identifier: str | None = None,
    name: str | None = None,
    description: str | None = None,
    acceptance_summary: str | None = None,
    priority: str | None = None,
    notes: str | None = None,
    status: str | None = None,
    rejected_by_decision: str | None = None,
) -> dict:
    """Full-replace update (PUT).

    ``requirement_identifier`` (the identifier echoed in the request
    body) must match the path ``identifier`` — a mismatch raises
    :class:`UnprocessableError`. ``name`` / ``description`` /
    ``acceptance_summary`` / ``priority`` / ``status`` are required (a
    full replace cannot blank them); ``notes`` is replaced wholesale
    (``None`` clears it). A ``status`` change is transition-validated;
    a ``priority`` change is enum-validated only (no transition rules
    per spec §3.2.3).
    """
    row = _get_row(session, identifier)
    if (
        requirement_identifier is not None
        and requirement_identifier != identifier
    ):
        raise UnprocessableError(
            [
                FieldError(
                    "requirement_identifier",
                    "path_mismatch",
                    "identifier in body must match the path",
                )
            ]
        )
    before = to_dict(row)

    name = _require_nonempty(name, field="requirement_name")
    description = _require_nonempty(
        description, field="requirement_description"
    )
    acceptance_summary = _require_nonempty(
        acceptance_summary, field="requirement_acceptance_summary"
    )
    _require_priority(priority)
    if name.lower() != row.requirement_name.lower():
        _reject_duplicate_name(session, name, exclude_identifier=identifier)
    if status is not None and status != row.requirement_status:
        _require_status(status)
        _check_transition(row.requirement_status, status)
        if status == "rejected":
            _rejection.enforce_rejected_status(
                session,
                source_type=_ENTITY_TYPE,
                source_identifier=identifier,
                decision_identifier=rejected_by_decision,
            )
            rejected_by_decision = None
        row.requirement_status = status
    if rejected_by_decision is not None:
        _rejection.attach_decision(
            session,
            source_type=_ENTITY_TYPE,
            source_identifier=identifier,
            decision_identifier=rejected_by_decision,
            current_status=row.requirement_status,
        )

    row.requirement_name = name
    row.requirement_description = description
    row.requirement_acceptance_summary = acceptance_summary
    row.requirement_priority = priority
    row.requirement_notes = notes
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
# Requirements-provenance model (Phase 2) — decision-outcome flips.
#
# A decision resolves a requirement three ways (anchor §"the decision outcomes"):
#   - deliver  -> activate_by_decision  (candidate/deferred -> confirmed)
#   - change   -> reopen_by_decision    (gated reopen -> candidate + needs_review)
#   - decline  -> the existing _rejection path (rejected_by_decision edge + flip)
# These are invoked atomically by references.create when the corresponding
# requirement->decision edge is created, mirroring the PI-030 `resolves` flip.
# ---------------------------------------------------------------------------


def _resolves_via_ancestry(
    session: Session,
    identifier: str,
    kind: str,
    _seen: set[str] | None = None,
) -> bool:
    """True if the requirement carries an outbound edge of ``kind``, or
    inherits one through an ancestor up the ``requirement_refines_requirement``
    (child -> parent) chain.

    Used for both activation gates: provenance
    (``requirement_defined_in_conversation``) so the requirement is rooted in a
    conversation, and topic (``requirement_belongs_to_topic``) so it is
    reachable under a topic for review. The visited-set bound tolerates an
    accidental cycle in the parent edges.
    """
    seen = _seen if _seen is not None else set()
    if identifier in seen:
        return False
    seen.add(identifier)
    own = session.scalar(
        select(func.count(Reference.id)).where(
            Reference.source_type == _ENTITY_TYPE,
            Reference.source_id == identifier,
            Reference.relationship_kind == kind,
        )
    )
    if own and own > 0:
        return True
    parents = session.scalars(
        select(Reference.target_id).where(
            Reference.source_type == _ENTITY_TYPE,
            Reference.source_id == identifier,
            Reference.target_type == _ENTITY_TYPE,
            Reference.relationship_kind == "requirement_refines_requirement",
        )
    ).all()
    return any(_resolves_via_ancestry(session, p, kind, seen) for p in parents)


def activate_by_decision(session: Session, identifier: str) -> dict:
    """Deliver outcome (A1): a decision approves a requirement for delivery.

    Flips ``candidate`` / ``deferred`` -> ``confirmed`` and stamps
    ``requirement_approved_at``, but only if the requirement both (a) is rooted
    in a conversation and (b) resolves to a topic — each via its own edge or an
    ancestor's. (a) is the no-orphan-capability rule (you can't activate an
    unrooted requirement); (b) makes it reachable under a topic, so it can't be
    activated without first being reviewable (review is topic-first). Both
    enforced at activation per decisions A1 + topic-gate. Idempotent if already
    ``confirmed``; a ``rejected`` requirement cannot be approved.
    """
    row = _get_row(session, identifier)
    if row.requirement_status == "confirmed":
        return to_dict(row)
    if row.requirement_status == "rejected":
        raise UnprocessableError(
            [
                FieldError(
                    "requirement_status",
                    "invalid_transition",
                    "a rejected requirement cannot be approved for delivery",
                )
            ]
        )
    if not _resolves_via_ancestry(
        session, identifier, "requirement_defined_in_conversation"
    ):
        raise UnprocessableError(
            [
                FieldError(
                    "relationship",
                    "provenance_required",
                    f"requirement {identifier} cannot be activated without "
                    "provenance: it (or an ancestor) needs a "
                    "requirement_defined_in_conversation edge",
                )
            ]
        )
    if not _resolves_via_ancestry(
        session, identifier, "requirement_belongs_to_topic"
    ):
        raise UnprocessableError(
            [
                FieldError(
                    "relationship",
                    "topic_required",
                    f"requirement {identifier} cannot be activated without a "
                    "topic: it (or an ancestor) needs a "
                    "requirement_belongs_to_topic edge so it is reachable for "
                    "review",
                )
            ]
        )
    before = to_dict(row)
    row.requirement_status = "confirmed"
    row.requirement_approved_at = datetime.now(UTC)
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


def reopen_by_decision(session: Session, identifier: str) -> dict:
    """Change outcome (B1): a decision requires the requirement to change.

    Gated reopen — returns the requirement to ``candidate`` and flags it
    ``needs_review``, clearing any prior approval. This is the one path
    permitted to regress out of ``confirmed`` / ``deferred``; the normal
    one-way propose-verify gate (``_check_transition``) still governs manual
    moves. A ``rejected`` (terminal) requirement is not reopened — that would
    be a new requirement, not a change.
    """
    row = _get_row(session, identifier)
    if row.requirement_status == "rejected":
        raise UnprocessableError(
            [
                FieldError(
                    "requirement_status",
                    "invalid_transition",
                    "a rejected requirement is terminal; a change decision "
                    "cannot reopen it (create a new requirement instead)",
                )
            ]
        )
    before = to_dict(row)
    row.requirement_status = "candidate"
    row.requirement_review_state = "needs_review"
    row.requirement_approved_at = None
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


def patch_requirement(session: Session, identifier: str, **fields) -> dict:
    """Partial update (PATCH). Only the supplied fields are touched.

    Recognised keys: ``name``, ``description``, ``acceptance_summary``,
    ``notes``, ``priority``, ``status``, ``rejected_by_decision``. A
    ``status`` change is transition-validated; a move to ``rejected``
    requires either the ``rejected_by_decision`` key (atomic edge +
    flip, PI-153 §3.4) or a pre-existing ``rejected_by_decision`` edge.
    A ``priority`` change is enum-validated only (any-to-any movement
    permitted per spec §3.2.3).
    """
    rejected_by_decision = fields.pop("rejected_by_decision", None)
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

    if "name" in fields:
        name = _require_nonempty(fields["name"], field="requirement_name")
        if name.lower() != row.requirement_name.lower():
            _reject_duplicate_name(
                session, name, exclude_identifier=identifier
            )
        row.requirement_name = name
    if "description" in fields:
        row.requirement_description = _require_nonempty(
            fields["description"], field="requirement_description"
        )
    if "acceptance_summary" in fields:
        row.requirement_acceptance_summary = _require_nonempty(
            fields["acceptance_summary"],
            field="requirement_acceptance_summary",
        )
    if "notes" in fields:
        row.requirement_notes = fields["notes"]
    if "priority" in fields:
        # Priority transitions are unconstrained per spec §3.2.3 — just
        # enum-validate and assign.
        row.requirement_priority = _require_priority(fields["priority"])
    if "status" in fields:
        status = _require_status(fields["status"])
        if status != row.requirement_status:
            _check_transition(row.requirement_status, status)
            if status == "rejected":
                _rejection.enforce_rejected_status(
                    session,
                    source_type=_ENTITY_TYPE,
                    source_identifier=identifier,
                    decision_identifier=rejected_by_decision,
                )
                rejected_by_decision = None
            row.requirement_status = status
    if rejected_by_decision is not None:
        _rejection.attach_decision(
            session,
            source_type=_ENTITY_TYPE,
            source_identifier=identifier,
            decision_identifier=rejected_by_decision,
            current_status=row.requirement_status,
        )

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


def delete_requirement(session: Session, identifier: str) -> dict:
    """Soft-delete: set ``requirement_deleted_at`` to now.

    Idempotent — DELETE on an already-soft-deleted row is a no-op that
    returns the record unchanged. Outbound references (all five kinds)
    are NOT cascade-deleted per spec §3.4.7: this function never
    touches the ``refs`` table.
    """
    row = _get_row(session, identifier)
    if row.requirement_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.requirement_deleted_at = datetime.now(UTC)
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


def restore_requirement(session: Session, identifier: str) -> dict:
    """Clear ``requirement_deleted_at``. Raises if the row is not soft-deleted."""
    row = _get_row(session, identifier)
    if row.requirement_deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "requirement_deleted_at",
                    "not_deleted",
                    "requirement is not soft-deleted",
                )
            ]
        )
    before = to_dict(row)
    row.requirement_deleted_at = None
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

"""Engagement repository (v0.5 slice B; PI-β: now over the unified DB).

Operates on the **unified** DB's ``engagements`` table — the single registry the
per-request scope resolver already reads — via a normal access-layer session.
(PI-β collapsed the redundant second copy that lived in a separate meta DB at
``crmbuilder-v2/data/engagements.db``; writes now go through the unified
``session_scope``, so there is no separate meta-snapshot hook.)
Eight standard methods with validation per
``methodology-schema-specs/engagement.md`` §3.5.

Validation posture:

* ``engagement_identifier`` format ``^ENG-\\d{3}$`` (422 on mismatch).
* ``engagement_code`` format ``^[A-Z][A-Z0-9]{1,9}$`` (mirrors v1's
  ``Client.code`` constraint exactly), case-insensitive unique.
* ``engagement_name`` non-empty trimmed, case-insensitive unique.
* ``engagement_purpose`` non-empty trimmed.
* ``engagement_status`` enum: ``active`` | ``paused`` | ``archived``;
  free transitions (no map needed).
* ``engagement_code`` is immutable post-creation.
* Soft-delete sets ``engagement_deleted_at``; restore clears it.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import next_prefixed_identifier
from crmbuilder_v2.access.engagement_models import (
    Engagement,
    EngagementStatus,
)
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import EngagementRow

_ENTITY_TYPE = "engagement"
_IDENTIFIER_PREFIX = "ENG"
_IDENTIFIER_RE = re.compile(r"^ENG-\d{3}$")
_CODE_RE = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")

_MAX_AUTOASSIGN_ATTEMPTS = 50

_VALID_STATUSES: frozenset[str] = frozenset(s.value for s in EngagementStatus)

_PATCHABLE_FIELDS = frozenset(
    {
        "engagement_name",
        "engagement_purpose",
        "engagement_status",
        "engagement_last_opened_at",
    }
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        raise UnprocessableError(
            [
                FieldError(
                    "engagement_identifier",
                    "invalid_format",
                    r"must match ^ENG-\d{3}$ (e.g. ENG-001)",
                )
            ]
        )
    return identifier


def _require_code_format(code: str) -> str:
    if not isinstance(code, str) or not _CODE_RE.match(code):
        raise UnprocessableError(
            [
                FieldError(
                    "engagement_code",
                    "invalid_format",
                    "must match ^[A-Z][A-Z0-9]{1,9}$ "
                    "(2-10 uppercase letters and digits, starting "
                    "with a letter)",
                )
            ]
        )
    return code


def _require_nonempty(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UnprocessableError(
            [
                FieldError(
                    field, "missing_or_empty", "must be a non-empty string"
                )
            ]
        )
    return value.strip()


def _normalise_status(value: object) -> EngagementStatus:
    if isinstance(value, EngagementStatus):
        return value
    if isinstance(value, str) and value in _VALID_STATUSES:
        return EngagementStatus(value)
    raise UnprocessableError(
        [
            FieldError(
                "engagement_status",
                "invalid_enum_value",
                f"must be one of {sorted(_VALID_STATUSES)}",
            )
        ]
    )


def _reject_duplicate_code(
    session: Session, code: str, *, exclude_identifier: str | None = None
) -> None:
    stmt = select(EngagementRow).where(
        func.lower(EngagementRow.engagement_code) == code.lower()
    )
    if exclude_identifier is not None:
        stmt = stmt.where(
            EngagementRow.engagement_identifier != exclude_identifier
        )
    if session.scalar(stmt) is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "engagement_code",
                    "not_unique",
                    f"an engagement with code {code!r} already exists",
                )
            ]
        )


def _reject_duplicate_name(
    session: Session, name: str, *, exclude_identifier: str | None = None
) -> None:
    stmt = select(EngagementRow).where(
        func.lower(EngagementRow.engagement_name) == name.lower()
    )
    if exclude_identifier is not None:
        stmt = stmt.where(
            EngagementRow.engagement_identifier != exclude_identifier
        )
    if session.scalar(stmt) is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "engagement_name",
                    "not_unique",
                    f"an engagement named {name!r} already exists",
                )
            ]
        )


def _get_row(session: Session, identifier: str) -> EngagementRow:
    row = session.get(EngagementRow, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    n = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{n + 1:03d}"


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_engagements(
    session: Session, *, include_deleted: bool = False
) -> list[Engagement]:
    """Return engagements ordered by ``engagement_last_opened_at DESC NULLS LAST``,
    then by ``engagement_identifier`` ascending as a stable tiebreaker.
    """
    stmt = select(EngagementRow).order_by(
        # CASE-based ordering for nulls-last on the last_opened_at column.
        (EngagementRow.engagement_last_opened_at.is_(None)).asc(),
        EngagementRow.engagement_last_opened_at.desc(),
        EngagementRow.engagement_identifier.asc(),
    )
    if not include_deleted:
        stmt = stmt.where(EngagementRow.engagement_deleted_at.is_(None))
    return [Engagement.from_row(r) for r in session.scalars(stmt).all()]


def get_engagement(
    session: Session, identifier: str
) -> Engagement | None:
    """Return a single engagement (including soft-deleted) or None."""
    row = session.get(EngagementRow, identifier)
    if row is None:
        return None
    return Engagement.from_row(row)


def next_engagement_identifier(session: Session) -> str:
    """Compute the next available ``ENG-NNN``.

    Scans all rows (including soft-deleted) so a retired identifier
    is never reused.
    """
    identifiers = session.scalars(
        select(EngagementRow.engagement_identifier)
    ).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_row(
    *,
    identifier: str,
    code: str,
    name: str,
    purpose: str,
    status: str,
    now: datetime,
) -> EngagementRow:
    return EngagementRow(
        engagement_identifier=identifier,
        engagement_code=code,
        engagement_name=name,
        engagement_purpose=purpose,
        engagement_status=status,
        engagement_last_opened_at=None,
        engagement_created_at=now,
        engagement_updated_at=now,
        engagement_deleted_at=None,
    )


def _insert_with_autoassign(
    session: Session,
    *,
    code: str,
    name: str,
    purpose: str,
    status: str,
    now: datetime,
) -> EngagementRow:
    """Insert with a server-assigned identifier, collision-safe.

    Uses SAVEPOINTs so an identifier collision under concurrent inserts
    rolls back the candidate and retries with the next.
    """
    candidate = next_engagement_identifier(session)
    last_error: IntegrityError | None = None
    for _attempt in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_row(
            identifier=candidate,
            code=code,
            name=name,
            purpose=purpose,
            status=status,
            now=now,
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
        "could not assign a unique engagement identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_engagement(
    session: Session,
    *,
    engagement_code: str,
    engagement_name: str,
    engagement_purpose: str,
    engagement_status: str | EngagementStatus = EngagementStatus.ACTIVE,
    engagement_identifier: str | None = None,
) -> Engagement:
    code = _require_code_format(engagement_code)
    name = _require_nonempty(engagement_name, field="engagement_name")
    purpose = _require_nonempty(
        engagement_purpose, field="engagement_purpose"
    )
    status = _normalise_status(engagement_status)

    _reject_duplicate_code(session, code)
    _reject_duplicate_name(session, name)

    now = datetime.now(UTC)

    if engagement_identifier is None:
        row = _insert_with_autoassign(
            session,
            code=code,
            name=name,
            purpose=purpose,
            status=status.value,
            now=now,
        )
    else:
        _require_identifier_format(engagement_identifier)
        if session.get(EngagementRow, engagement_identifier) is not None:
            raise ConflictError(
                f"engagement {engagement_identifier!r} already exists"
            )
        row = _new_row(
            identifier=engagement_identifier,
            code=code,
            name=name,
            purpose=purpose,
            status=status.value,
            now=now,
        )
        session.add(row)
        session.flush()

    return Engagement.from_row(row)


def update_engagement(
    session: Session,
    identifier: str,
    *,
    engagement_identifier: str | None = None,
    engagement_code: str | None = None,
    engagement_name: str | None = None,
    engagement_purpose: str | None = None,
    engagement_status: str | EngagementStatus | None = None,
    engagement_last_opened_at: object = ...,
) -> Engagement:
    """Full-replace PUT.

    The body identifier (if present) must match the path. ``engagement_code``
    is immutable post-creation: an attempt to change it raises
    ``UnprocessableError`` with code ``immutable_field``.
    ``engagement_last_opened_at`` defaults to ``...`` (sentinel meaning
    "not provided"); explicit ``None`` clears it.
    """
    row = _get_row(session, identifier)
    if (
        engagement_identifier is not None
        and engagement_identifier != identifier
    ):
        raise UnprocessableError(
            [
                FieldError(
                    "engagement_identifier",
                    "identifier_mismatch",
                    "identifier in body must match the path",
                )
            ]
        )

    if engagement_code is not None and engagement_code != row.engagement_code:
        raise UnprocessableError(
            [
                FieldError(
                    "engagement_code",
                    "immutable_field",
                    "engagement_code cannot be changed after creation",
                )
            ]
        )

    name = _require_nonempty(engagement_name, field="engagement_name")
    purpose = _require_nonempty(
        engagement_purpose, field="engagement_purpose"
    )
    status = _normalise_status(
        engagement_status if engagement_status is not None else row.engagement_status
    )

    if name.lower() != row.engagement_name.lower():
        _reject_duplicate_name(
            session, name, exclude_identifier=identifier
        )

    row.engagement_name = name
    row.engagement_purpose = purpose
    row.engagement_status = status.value
    if engagement_last_opened_at is not ...:
        row.engagement_last_opened_at = engagement_last_opened_at  # type: ignore[assignment]
    session.flush()
    return Engagement.from_row(row)


def patch_engagement(
    session: Session, identifier: str, **fields
) -> Engagement:
    """Partial PATCH. Only specified fields are validated and updated.

    ``engagement_code`` rejection: any attempt to patch it raises
    ``UnprocessableError`` with code ``immutable_field``.
    """
    if "engagement_code" in fields and fields["engagement_code"] is not None:
        # Allow only no-op patches (same code).
        existing = session.get(EngagementRow, identifier)
        if existing is None:
            raise NotFoundError(_ENTITY_TYPE, identifier)
        if fields["engagement_code"] != existing.engagement_code:
            raise UnprocessableError(
                [
                    FieldError(
                        "engagement_code",
                        "immutable_field",
                        "engagement_code cannot be changed after creation",
                    )
                ]
            )
        del fields["engagement_code"]

    if "engagement_identifier" in fields:
        # Bodies may echo the identifier; reject mismatch.
        body_id = fields.pop("engagement_identifier")
        if body_id is not None and body_id != identifier:
            raise UnprocessableError(
                [
                    FieldError(
                        "engagement_identifier",
                        "identifier_mismatch",
                        "identifier in body must match the path",
                    )
                ]
            )

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

    if "engagement_name" in fields:
        name = _require_nonempty(
            fields["engagement_name"], field="engagement_name"
        )
        if name.lower() != row.engagement_name.lower():
            _reject_duplicate_name(
                session, name, exclude_identifier=identifier
            )
        row.engagement_name = name
    if "engagement_purpose" in fields:
        row.engagement_purpose = _require_nonempty(
            fields["engagement_purpose"], field="engagement_purpose"
        )
    if "engagement_status" in fields:
        status = _normalise_status(fields["engagement_status"])
        row.engagement_status = status.value
    if "engagement_last_opened_at" in fields:
        value = fields["engagement_last_opened_at"]
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        row.engagement_last_opened_at = value

    session.flush()
    return Engagement.from_row(row)


def delete_engagement(session: Session, identifier: str) -> Engagement:
    """Soft-delete: set ``engagement_deleted_at``. Idempotent."""
    row = _get_row(session, identifier)
    if row.engagement_deleted_at is None:
        row.engagement_deleted_at = datetime.now(UTC)
        session.flush()
    return Engagement.from_row(row)


def restore_engagement(session: Session, identifier: str) -> Engagement:
    """Clear ``engagement_deleted_at``. Raises if not soft-deleted."""
    row = _get_row(session, identifier)
    if row.engagement_deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "engagement_deleted_at",
                    "not_soft_deleted",
                    "engagement is not soft-deleted",
                )
            ]
        )
    row.engagement_deleted_at = None
    session.flush()
    return Engagement.from_row(row)


# Module-level convenience wrappers that open a unified-DB session internally.
# Useful for scripts and the per-request scope resolver. (PI-β: the registry now
# lives only in the unified ``engagements`` table — the separate meta DB is gone —
# so ``EngagementRow`` above is the unified model and these open a normal session.)


def _open_unified_session():
    from crmbuilder_v2.access.db import get_session_factory

    return get_session_factory()()


def list_engagements_in_meta(
    *, include_deleted: bool = False
) -> list[Engagement]:
    """Back-compat alias — reads the unified ``engagements`` table.

    The historical name is retained for callers (scripts, routing) that have
    not been renamed; it no longer touches a meta DB.
    """
    session = _open_unified_session()
    try:
        return list_engagements(session, include_deleted=include_deleted)
    finally:
        session.close()


# Canonical name for reading the unified registry (the per-request scope resolver
# uses this); ``list_engagements_in_meta`` is the back-compat alias above.
def list_engagements_unified(
    *, include_deleted: bool = False
) -> list[Engagement]:
    """List engagements from the unified DB's ``engagements`` table.

    The ``engagements`` table is un-scoped, so this query is never engagement-
    filtered and is safe to run with no active engagement.
    """
    session = _open_unified_session()
    try:
        return list_engagements(session, include_deleted=include_deleted)
    finally:
        session.close()


def get_engagement_in_meta(identifier: str) -> Engagement | None:
    session = _open_unified_session()
    try:
        return get_engagement(session, identifier)
    finally:
        session.close()

"""Engine-override repository — composite design record (PRJ-025 PI-189
slice 1).

Per ``engine-neutral-design-model-and-adapters.md`` §9. An ``engine_override``
(``OVR-NNN``) is the sparse per-engine escape hatch that adjusts how one
design construct (``entity`` / ``field`` / ``association``) renders for one
target engine. There is **no status lifecycle** — an override either exists or
it does not. The module-level functions back the ``/engine-overrides`` REST
endpoints and any access-layer caller (the adapter, MCP tools):

* :func:`list_engine_overrides` / :func:`get_engine_override` — reads, with
  optional ``target_engine`` / ``subject_type`` / ``subject_identifier``
  filters.
* :func:`create_engine_override` — insert with a server-assigned (or explicit)
  identifier. The ``(engagement_id, target_engine, subject_type,
  subject_identifier, attribute)`` tuple is unique (one override per engine
  per construct per attribute) — a duplicate raises :class:`ConflictError`.
* :func:`update_engine_override` / :func:`patch_engine_override` — full /
  partial update; the uniqueness tuple is re-checked when any of its members
  change.
* :func:`delete_engine_override` / :func:`restore_engine_override` —
  soft-delete round-trip.
* :func:`next_engine_override_identifier` — the ``OVR-NNN`` allocator helper.

Validation posture: identifier-format, ``target_engine`` /
``subject_type`` enum membership, a non-empty ``subject_identifier`` /
``attribute``, and a PUT identifier/path mismatch raise
:class:`UnprocessableError` (422); a missing record raises
:class:`NotFoundError` (404); an explicit-identifier collision or a
uniqueness-tuple collision raises :class:`ConflictError` (409). The
uniqueness tuple is pre-checked (including soft-deleted rows, since
``deleted_at`` is not part of the unique key) so a clear 409 is returned
rather than an opaque IntegrityError.
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
from crmbuilder_v2.access.models import EngineOverride
from crmbuilder_v2.access.vocab import (
    OVERRIDE_SUBJECT_TYPES,
    TARGET_ENGINES,
)

_ENTITY_TYPE = "engine_override"
_IDENTIFIER_PREFIX = "OVR"
_IDENTIFIER_RE = re.compile(r"^OVR-\d{3}$")

# Upper bound on identifier-collision retries inside
# :func:`_insert_with_autoassign` (the field.py posture).
_MAX_AUTOASSIGN_ATTEMPTS = 50

# Fields accepted by :func:`patch_engine_override`. The identifier and
# timestamps are server-owned and not patchable.
_PATCHABLE_FIELDS = frozenset(
    {
        "target_engine",
        "subject_type",
        "subject_identifier",
        "attribute",
        "value",
        "notes",
    }
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _fail(field: str, code: str, message: str) -> None:
    raise UnprocessableError([FieldError(field, code, message)])


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        _fail(
            "override_identifier",
            "invalid_format",
            r"must match ^OVR-\d{3}$ (e.g. OVR-001)",
        )
    return identifier


def _require_nonempty(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(field, "missing_or_empty", "must be a non-empty string")
    return value.strip()  # type: ignore[union-attr]


def _require_target_engine(engine: object) -> str:
    if engine not in TARGET_ENGINES:
        _fail(
            "override_target_engine",
            "invalid_value",
            f"must be one of {sorted(TARGET_ENGINES)}",
        )
    return engine  # type: ignore[return-value]


def _require_subject_type(subject_type: object) -> str:
    if subject_type not in OVERRIDE_SUBJECT_TYPES:
        _fail(
            "override_subject_type",
            "invalid_value",
            f"must be one of {sorted(OVERRIDE_SUBJECT_TYPES)}",
        )
    return subject_type  # type: ignore[return-value]


def _optional_text(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        _fail(field, "invalid_value", "must be a string or null")
    return value


def _check_unique(
    session: Session,
    target_engine: str,
    subject_type: str,
    subject_identifier: str,
    attribute: str,
    *,
    exclude_identifier: str | None = None,
) -> None:
    """Reject a uniqueness-tuple collision (engagement auto-scoped).

    Includes soft-deleted rows: ``override_deleted_at`` is not part of the
    unique key, so a soft-deleted row with the same tuple still collides at
    the DB level. Pre-checking returns a clear 409.
    """
    stmt = select(EngineOverride.override_identifier).where(
        EngineOverride.override_target_engine == target_engine,
        EngineOverride.override_subject_type == subject_type,
        EngineOverride.override_subject_identifier == subject_identifier,
        EngineOverride.override_attribute == attribute,
    )
    if exclude_identifier is not None:
        stmt = stmt.where(
            EngineOverride.override_identifier != exclude_identifier
        )
    existing = session.scalar(stmt)
    if existing is not None:
        raise ConflictError(
            f"an engine_override for {target_engine!r} {subject_type!r} "
            f"{subject_identifier!r} attribute {attribute!r} already exists "
            f"({existing})"
        )


def _get_row(session: Session, identifier: str) -> EngineOverride:
    """Return the ORM row (including soft-deleted) or raise NotFoundError."""
    row = get_by_identifier(
        session,
        EngineOverride,
        EngineOverride.override_identifier,
        identifier,
    )
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_engine_overrides(
    session: Session,
    *,
    target_engine: str | None = None,
    subject_type: str | None = None,
    subject_identifier: str | None = None,
    include_deleted: bool = False,
) -> list[dict]:
    """Return engine overrides ordered by identifier ascending.

    Soft-deleted rows are excluded unless ``include_deleted`` is True. The
    three filters narrow on the corresponding columns.
    """
    stmt = select(EngineOverride).order_by(
        EngineOverride.override_identifier
    )
    if target_engine is not None:
        stmt = stmt.where(
            EngineOverride.override_target_engine == target_engine
        )
    if subject_type is not None:
        stmt = stmt.where(
            EngineOverride.override_subject_type == subject_type
        )
    if subject_identifier is not None:
        stmt = stmt.where(
            EngineOverride.override_subject_identifier == subject_identifier
        )
    if not include_deleted:
        stmt = stmt.where(EngineOverride.override_deleted_at.is_(None))
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_engine_override(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    """Return a single override by identifier, or ``None`` if not visible."""
    row = get_by_identifier(
        session,
        EngineOverride,
        EngineOverride.override_identifier,
        identifier,
    )
    if row is None:
        return None
    if row.override_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_engine_override_identifier(session: Session) -> str:
    """Return the next available ``OVR-NNN`` (soft-deleted rows included)."""
    identifiers = session.scalars(
        select(EngineOverride.override_identifier)
    ).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_row(
    identifier: str,
    target_engine: str,
    subject_type: str,
    subject_identifier: str,
    attribute: str,
    value: object,
    notes: str | None,
) -> EngineOverride:
    return EngineOverride(
        override_identifier=identifier,
        override_target_engine=target_engine,
        override_subject_type=subject_type,
        override_subject_identifier=subject_identifier,
        override_attribute=attribute,
        override_value=value,
        override_notes=notes,
    )


def _insert_with_autoassign(session: Session, **columns) -> EngineOverride:
    """Insert with a server-assigned identifier, SAVEPOINT-collision-safe.

    The uniqueness tuple is pre-checked by the caller, so an IntegrityError
    here is an identifier collision; the savepoint rolls it back and the
    candidate is incremented.
    """
    # REQ-446 / PI-384: serialize per-prefix assignment so concurrent
    # Postgres writers don't race the read-then-probe loop (no-op on SQLite).
    serialize_identifier_assignment(session, _IDENTIFIER_PREFIX)
    candidate = next_engine_override_identifier(session)
    last_error: IntegrityError | None = None
    for _attempt in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_row(candidate, **columns)
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
        "could not assign a unique engine_override identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_engine_override(
    session: Session,
    *,
    target_engine: str,
    subject_type: str,
    subject_identifier: str,
    attribute: str,
    value: object = None,
    notes: str | None = None,
    identifier: str | None = None,
) -> dict:
    """Create an engine override.

    Validation order: ``target_engine`` / ``subject_type`` in vocab;
    ``subject_identifier`` / ``attribute`` non-empty; uniqueness tuple free;
    then insert (server-assigned id when ``identifier`` is ``None``).
    ``value`` is stored verbatim as dialect-portable JSON (any scalar, list,
    or object; ``None`` clears).
    """
    target_engine = _require_target_engine(target_engine)
    subject_type = _require_subject_type(subject_type)
    subject_identifier = _require_nonempty(
        subject_identifier, field="override_subject_identifier"
    )
    attribute = _require_nonempty(attribute, field="override_attribute")
    notes = _optional_text(notes, field="override_notes")

    _check_unique(
        session, target_engine, subject_type, subject_identifier, attribute
    )

    columns = {
        "target_engine": target_engine,
        "subject_type": subject_type,
        "subject_identifier": subject_identifier,
        "attribute": attribute,
        "value": value,
        "notes": notes,
    }
    if identifier is None:
        row = _insert_with_autoassign(session, **columns)
    else:
        _require_identifier_format(identifier)
        if (
            get_by_identifier(
                session,
                EngineOverride,
                EngineOverride.override_identifier,
                identifier,
            )
            is not None
        ):
            raise ConflictError(
                f"engine_override {identifier!r} already exists"
            )
        row = _new_row(identifier, **columns)
        session.add(row)
        session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.override_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_engine_override(
    session: Session,
    identifier: str,
    *,
    override_identifier: str | None = None,
    target_engine: str,
    subject_type: str,
    subject_identifier: str,
    attribute: str,
    value: object = None,
    notes: str | None = None,
) -> dict:
    """Full-replace update (PUT).

    ``override_identifier`` (the identifier echoed in the body) must match the
    path ``identifier``. The uniqueness tuple is re-checked (excluding this
    row).
    """
    row = _get_row(session, identifier)
    if override_identifier is not None and override_identifier != identifier:
        _fail(
            "override_identifier",
            "path_mismatch",
            "identifier in body must match the path",
        )
    before = to_dict(row)

    target_engine = _require_target_engine(target_engine)
    subject_type = _require_subject_type(subject_type)
    subject_identifier = _require_nonempty(
        subject_identifier, field="override_subject_identifier"
    )
    attribute = _require_nonempty(attribute, field="override_attribute")
    notes = _optional_text(notes, field="override_notes")

    _check_unique(
        session,
        target_engine,
        subject_type,
        subject_identifier,
        attribute,
        exclude_identifier=identifier,
    )

    row.override_target_engine = target_engine
    row.override_subject_type = subject_type
    row.override_subject_identifier = subject_identifier
    row.override_attribute = attribute
    row.override_value = value
    row.override_notes = notes
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


def patch_engine_override(session: Session, identifier: str, **fields) -> dict:
    """Partial update (PATCH). Only the supplied fields are touched.

    Recognised keys: ``target_engine``, ``subject_type``,
    ``subject_identifier``, ``attribute``, ``value``, ``notes``. The
    uniqueness tuple is re-checked when any of its members change.
    """
    unknown = set(fields) - _PATCHABLE_FIELDS
    if unknown:
        _fail(
            "fields",
            "unknown_field",
            f"unknown patchable fields: {sorted(unknown)}",
        )
    row = _get_row(session, identifier)
    before = to_dict(row)

    target_engine = row.override_target_engine
    subject_type = row.override_subject_type
    subject_identifier = row.override_subject_identifier
    attribute = row.override_attribute
    tuple_changed = False

    if "target_engine" in fields:
        target_engine = _require_target_engine(fields["target_engine"])
        tuple_changed = True
    if "subject_type" in fields:
        subject_type = _require_subject_type(fields["subject_type"])
        tuple_changed = True
    if "subject_identifier" in fields:
        subject_identifier = _require_nonempty(
            fields["subject_identifier"],
            field="override_subject_identifier",
        )
        tuple_changed = True
    if "attribute" in fields:
        attribute = _require_nonempty(
            fields["attribute"], field="override_attribute"
        )
        tuple_changed = True

    if tuple_changed:
        _check_unique(
            session,
            target_engine,
            subject_type,
            subject_identifier,
            attribute,
            exclude_identifier=identifier,
        )
        row.override_target_engine = target_engine
        row.override_subject_type = subject_type
        row.override_subject_identifier = subject_identifier
        row.override_attribute = attribute

    if "value" in fields:
        row.override_value = fields["value"]
    if "notes" in fields:
        row.override_notes = _optional_text(
            fields["notes"], field="override_notes"
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


def delete_engine_override(session: Session, identifier: str) -> dict:
    """Soft-delete the override. Idempotent."""
    row = _get_row(session, identifier)
    if row.override_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.override_deleted_at = datetime.now(UTC)
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


def restore_engine_override(session: Session, identifier: str) -> dict:
    """Clear ``override_deleted_at``. Raises 422 if the row is live.

    No tuple re-check is needed: the uniqueness constraint spans soft-deleted
    rows (``override_deleted_at`` is not part of the key), so the create-time
    pre-check already forbids any sibling — live or deleted — from sharing a
    soft-deleted row's tuple. Restore is therefore a pure row-level un-stamp.
    """
    row = _get_row(session, identifier)
    if row.override_deleted_at is None:
        _fail(
            "override_deleted_at",
            "not_deleted",
            "engine_override is not soft-deleted",
        )
    before = to_dict(row)
    row.override_deleted_at = None
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

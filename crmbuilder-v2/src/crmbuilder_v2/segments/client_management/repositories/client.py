"""Client repository: the organisation above the engagement (PI-512 /
REQ-589, DEC-1077, DEC-1092).

A client is system-wide, like a principal: the ``clients`` table carries no
engagement scope and every engagement can see every client. One client
holds many engagements; a chapter engagement serves several clients. The
link is the one table ``engagement_clients`` (design note, shape A): an
ordinary engagement has one row marked primary, a chapter engagement one
row per member client with one primary, an engagement with no client no
rows.

The module-level functions back the ``/clients`` endpoints and the two
client routes on ``/engagements``:

* :func:`list_clients` / :func:`get_client` / :func:`next_client_identifier`
* :func:`create_client` / :func:`update_client` / :func:`patch_client`
* :func:`delete_client` / :func:`restore_client`; a client that still holds
  engagements cannot be deleted (DEC-1092, question 6)
* :func:`list_client_engagements` / :func:`get_engagement_clients` /
  :func:`set_engagement_clients` / :func:`primary_client_for_engagement`

No change-log rows are emitted for clients in this planning item, matching
the engagement record (DEC-1092, question 4).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import func, select
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
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.segments.client_management.models import (
    ClientRow,
    EngagementClientRow,
    EngagementRow,
)
from crmbuilder_v2.segments.client_management.vocab import (
    CLIENT_STATUS_TRANSITIONS,
    CLIENT_STATUSES,
)

_ENTITY_TYPE = "client"
_IDENTIFIER_PREFIX = "CLI"
_IDENTIFIER_RE = re.compile(r"^CLI-\d{3,}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_PATCHABLE_FIELDS = frozenset({"name", "notes", "status"})


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        raise UnprocessableError(
            [
                FieldError(
                    "client_identifier",
                    "invalid_format",
                    r"must match ^CLI-\d{3,}$ (e.g. CLI-001)",
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
    if status not in CLIENT_STATUSES:
        raise UnprocessableError(
            [
                FieldError(
                    "client_status",
                    "invalid_value",
                    f"must be one of {sorted(CLIENT_STATUSES)}",
                )
            ]
        )
    return status  # type: ignore[return-value]


def _check_transition(current: str, requested: str) -> None:
    if requested == current:
        return
    if requested not in CLIENT_STATUS_TRANSITIONS.get(current, frozenset()):
        raise StatusTransitionError(current, requested)


def _reject_duplicate_name(
    session: Session, name: str, *, exclude_identifier: str | None = None
) -> None:
    """Reject a case-insensitive ``client_name`` collision among live rows
    (DEC-1092, question 5: unique across the whole store)."""
    stmt = select(ClientRow).where(
        func.lower(ClientRow.client_name) == name.lower(),
        ClientRow.client_deleted_at.is_(None),
    )
    if exclude_identifier is not None:
        stmt = stmt.where(ClientRow.client_identifier != exclude_identifier)
    if session.scalar(stmt) is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "client_name",
                    "duplicate",
                    f"a client named {name!r} already exists",
                )
            ]
        )


def _get_row(session: Session, identifier: str) -> ClientRow:
    row = session.get(ClientRow, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _get_engagement_row(session: Session, identifier: str) -> EngagementRow:
    row = session.get(EngagementRow, identifier)
    if row is None:
        raise NotFoundError("engagement", identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def _engagement_identifiers_for(session: Session, client_identifier: str) -> list[str]:
    stmt = (
        select(EngagementClientRow.engagement_id)
        .where(EngagementClientRow.client_id == client_identifier)
        .order_by(EngagementClientRow.engagement_id)
    )
    return list(session.scalars(stmt).all())


def _serialise(session: Session, row: ClientRow) -> dict:
    record = to_dict(row)
    record["engagements"] = _engagement_identifiers_for(
        session, row.client_identifier
    )
    return record


def list_clients(session: Session, *, include_deleted: bool = False) -> list[dict]:
    """Return clients ordered by identifier, each with its engagement
    identifiers under ``engagements``."""
    stmt = select(ClientRow).order_by(ClientRow.client_identifier)
    if not include_deleted:
        stmt = stmt.where(ClientRow.client_deleted_at.is_(None))
    return [_serialise(session, r) for r in session.scalars(stmt).all()]


def get_client(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    row = session.get(ClientRow, identifier)
    if row is None:
        return None
    if row.client_deleted_at is not None and not include_deleted:
        return None
    return _serialise(session, row)


def next_client_identifier(session: Session) -> str:
    identifiers = session.scalars(select(ClientRow.client_identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


def list_client_engagements(session: Session, identifier: str) -> list[dict]:
    """The engagements a client serves, as engagement records, with
    ``is_primary`` saying whether this client is the engagement's primary."""
    _get_row(session, identifier)
    stmt = (
        select(EngagementRow, EngagementClientRow.is_primary)
        .join(
            EngagementClientRow,
            EngagementClientRow.engagement_id == EngagementRow.engagement_identifier,
        )
        .where(EngagementClientRow.client_id == identifier)
        .order_by(EngagementRow.engagement_identifier)
    )
    out = []
    for engagement, is_primary in session.execute(stmt).all():
        record = to_dict(engagement)
        record["is_primary"] = bool(is_primary)
        out.append(record)
    return out


def get_engagement_clients(session: Session, engagement_identifier: str) -> dict:
    """``{"engagement": ..., "clients": [...], "primary": ...}`` for one
    engagement; ``clients`` are client records, ``primary`` an identifier or
    ``None``."""
    _get_engagement_row(session, engagement_identifier)
    stmt = (
        select(ClientRow, EngagementClientRow.is_primary)
        .join(
            EngagementClientRow,
            EngagementClientRow.client_id == ClientRow.client_identifier,
        )
        .where(EngagementClientRow.engagement_id == engagement_identifier)
        .order_by(EngagementClientRow.is_primary.desc(), ClientRow.client_identifier)
    )
    clients: list[dict] = []
    primary: str | None = None
    for client, is_primary in session.execute(stmt).all():
        record = to_dict(client)
        record["is_primary"] = bool(is_primary)
        clients.append(record)
        if is_primary:
            primary = client.client_identifier
    return {
        "engagement": engagement_identifier,
        "clients": clients,
        "primary": primary,
    }


def primary_client_for_engagement(
    session: Session, engagement_identifier: str
) -> dict | None:
    """The engagement's primary client record, or ``None``."""
    stmt = (
        select(ClientRow)
        .join(
            EngagementClientRow,
            EngagementClientRow.client_id == ClientRow.client_identifier,
        )
        .where(
            EngagementClientRow.engagement_id == engagement_identifier,
            EngagementClientRow.is_primary.is_(True),
        )
    )
    row = session.scalar(stmt)
    return None if row is None else to_dict(row)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_row(identifier: str, name: str, notes: str | None, status: str) -> ClientRow:
    now = datetime.now(UTC)
    return ClientRow(
        client_identifier=identifier,
        client_name=name,
        client_notes=notes,
        client_status=status,
        client_created_at=now,
        client_updated_at=now,
        client_deleted_at=None,
    )


def _insert_with_autoassign(
    session: Session, name: str, notes: str | None, status: str
) -> ClientRow:
    """Insert with a server-assigned identifier, collision-safe, as the
    engagement and participant repositories do."""
    serialize_identifier_assignment(session, _IDENTIFIER_PREFIX)
    candidate = next_client_identifier(session)
    last_error: IntegrityError | None = None
    for _attempt in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_row(candidate, name, notes, status)
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
        "could not assign a unique client identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_client(
    session: Session,
    *,
    name: str,
    notes: str | None = None,
    status: str | None = "active",
    identifier: str | None = None,
) -> dict:
    name = _require_nonempty(name, field="client_name")
    if status is None:
        status = "active"
    _require_status(status)
    _reject_duplicate_name(session, name)

    if identifier is None:
        row = _insert_with_autoassign(session, name, notes, status)
    else:
        _require_identifier_format(identifier)
        if session.get(ClientRow, identifier) is not None:
            raise ConflictError(f"client {identifier!r} already exists")
        row = _new_row(identifier, name, notes, status)
        session.add(row)
        session.flush()
    return _serialise(session, row)


def update_client(
    session: Session,
    identifier: str,
    *,
    client_identifier: str | None = None,
    name: str | None = None,
    notes: str | None = None,
    status: str | None = None,
) -> dict:
    """Full replace (PUT)."""
    row = _get_row(session, identifier)
    if client_identifier is not None and client_identifier != identifier:
        raise UnprocessableError(
            [
                FieldError(
                    "client_identifier",
                    "path_mismatch",
                    "identifier in body must match the path",
                )
            ]
        )
    name = _require_nonempty(name, field="client_name")
    if name.lower() != row.client_name.lower():
        _reject_duplicate_name(session, name, exclude_identifier=identifier)
    if status is not None and status != row.client_status:
        _require_status(status)
        _check_transition(row.client_status, status)
        row.client_status = status
    row.client_name = name
    row.client_notes = notes
    session.flush()
    return _serialise(session, row)


def patch_client(session: Session, identifier: str, **fields) -> dict:
    """Partial update (PATCH): ``name``, ``notes``, ``status``."""
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
    if "name" in fields:
        name = _require_nonempty(fields["name"], field="client_name")
        if name.lower() != row.client_name.lower():
            _reject_duplicate_name(session, name, exclude_identifier=identifier)
        row.client_name = name
    if "notes" in fields:
        row.client_notes = fields["notes"]
    if "status" in fields:
        status = _require_status(fields["status"])
        if status != row.client_status:
            _check_transition(row.client_status, status)
            row.client_status = status
    session.flush()
    return _serialise(session, row)


def delete_client(session: Session, identifier: str) -> dict:
    """Soft-delete. Refused while the client still holds engagements
    (DEC-1092, question 6): unlink first. Idempotent otherwise."""
    row = _get_row(session, identifier)
    if row.client_deleted_at is not None:
        return _serialise(session, row)
    held = _engagement_identifiers_for(session, identifier)
    if held:
        raise UnprocessableError(
            [
                FieldError(
                    "engagements",
                    "client_holds_engagements",
                    "a client that still holds engagements cannot be deleted; "
                    f"unlink {', '.join(held)} first",
                )
            ]
        )
    row.client_deleted_at = datetime.now(UTC)
    session.flush()
    return _serialise(session, row)


def restore_client(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.client_deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "client_deleted_at",
                    "not_deleted",
                    "client is not soft-deleted",
                )
            ]
        )
    row.client_deleted_at = None
    session.flush()
    return _serialise(session, row)


def set_engagement_clients(
    session: Session,
    engagement_identifier: str,
    *,
    clients: list[str],
    primary: str | None = None,
) -> dict:
    """Replace the set of clients an engagement serves.

    ``clients`` may be empty (the engagement then belongs to no client).
    Every client must exist and be live. ``primary`` must be one of
    ``clients``; it defaults to the first. Returns
    :func:`get_engagement_clients`.
    """
    _get_engagement_row(session, engagement_identifier)
    wanted = list(dict.fromkeys(clients))  # de-duplicate, keep order
    for client_identifier in wanted:
        row = session.get(ClientRow, client_identifier)
        if row is None or row.client_deleted_at is not None:
            raise UnprocessableError(
                [
                    FieldError(
                        "clients",
                        "unknown_client",
                        f"client {client_identifier!r} does not exist or is deleted",
                    )
                ]
            )
    if wanted:
        if primary is None:
            primary = wanted[0]
        if primary not in wanted:
            raise UnprocessableError(
                [
                    FieldError(
                        "primary",
                        "not_in_set",
                        "primary must be one of the clients listed",
                    )
                ]
            )
    elif primary is not None:
        raise UnprocessableError(
            [FieldError("primary", "not_in_set", "no clients listed")]
        )

    existing = session.scalars(
        select(EngagementClientRow).where(
            EngagementClientRow.engagement_id == engagement_identifier
        )
    ).all()
    for link in existing:
        session.delete(link)
    session.flush()
    now = datetime.now(UTC)
    for client_identifier in wanted:
        session.add(
            EngagementClientRow(
                engagement_id=engagement_identifier,
                client_id=client_identifier,
                is_primary=(client_identifier == primary),
                created_at=now,
            )
        )
    session.flush()
    return get_engagement_clients(session, engagement_identifier)

"""Role repository — PI-194 (PRJ-027).

A role (``ROL-NNN``) is one engine-neutral security role: a scope-access matrix
plus system permissions. Standard CRUD backing the ``/roles`` REST endpoints
plus the allocator; ``role_status`` is a controlled vocabulary. Reconcile
matches by name via :func:`list_roles`.
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
from crmbuilder_v2.access.models import Role
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import ROLE_STATUSES

_ENTITY_TYPE = "role"
_PREFIX = "ROL"
_IDENTIFIER_RE = re.compile(r"^ROL-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_PATCHABLE = frozenset(
    {"name", "scope_access", "system_permissions", "description", "status",
     "notes"}
)


def _require_status(v: object) -> str:
    return gov.require_in(v, ROLE_STATUSES, field="role_status")


def _get_row(session: Session, identifier: str) -> Role:
    row = get_by_identifier(session, Role, Role.role_identifier, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment(identifier: str) -> str:
    return f"{_PREFIX}-{int(identifier.split('-', 1)[1]) + 1:03d}"


def list_roles(
    session: Session,
    *,
    include_deleted: bool = False,
    name: str | None = None,
) -> list[dict]:
    stmt = select(Role).order_by(Role.role_identifier)
    if not include_deleted:
        stmt = stmt.where(Role.role_deleted_at.is_(None))
    if name is not None:
        stmt = stmt.where(Role.role_name == name)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_role(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    row = get_by_identifier(session, Role, Role.role_identifier, identifier)
    if row is None or (row.role_deleted_at is not None and not include_deleted):
        return None
    return to_dict(row)


def next_role_identifier(session: Session) -> str:
    return next_prefixed_identifier(
        session.scalars(select(Role.role_identifier)).all(), _PREFIX
    )


def _new_row(identifier, name, scope_access, system_permissions, description,
             status, notes):
    return Role(
        role_identifier=identifier,
        role_name=name,
        role_scope_access=scope_access,
        role_system_permissions=system_permissions,
        role_description=description,
        role_status=status,
        role_notes=notes,
    )


def _insert_with_autoassign(session, **kw) -> Role:
    # REQ-446 / PI-384: serialize per-prefix assignment so concurrent
    # Postgres writers don't race the read-then-probe loop (no-op on SQLite).
    serialize_identifier_assignment(session, _PREFIX)
    candidate = next_role_identifier(session)
    last: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        sp = session.begin_nested()
        row = _new_row(candidate, **kw)
        session.add(row)
        try:
            session.flush()
        except IntegrityError as exc:
            last = exc
            sp.rollback()
            candidate = _increment(candidate)
            continue
        sp.commit()
        return row
    raise ConflictError("could not assign a unique role identifier") from last


def create_role(
    session: Session,
    *,
    name: str,
    scope_access: dict | None = None,
    system_permissions: dict | None = None,
    description: str | None = None,
    status: str = "candidate",
    notes: str | None = None,
    identifier: str | None = None,
) -> dict:
    name = gov.require_nonempty(name, field="role_name")
    status = _require_status(status or "candidate")
    kw = {
        "name": name,
        "scope_access": scope_access,
        "system_permissions": system_permissions,
        "description": description,
        "status": status,
        "notes": notes,
    }
    if identifier is None:
        row = _insert_with_autoassign(session, **kw)
    else:
        gov.require_identifier_format(
            identifier, regex=_IDENTIFIER_RE, field="role_identifier",
            example="ROL-001",
        )
        if get_by_identifier(
            session, Role, Role.role_identifier, identifier
        ) is not None:
            raise ConflictError(f"role {identifier!r} already exists")
        row = _new_row(identifier, **kw)
        session.add(row)
        session.flush()
    after = to_dict(row)
    emit(session, entity_type=_ENTITY_TYPE,
         entity_identifier=row.role_identifier, operation="insert",
         before=None, after=after)
    return after


def update_role(
    session: Session, identifier: str, *,
    role_identifier: str | None = None,
    name: str,
    scope_access: dict | None = None,
    system_permissions: dict | None = None,
    description: str | None = None,
    status: str = "candidate",
    notes: str | None = None,
) -> dict:
    row = _get_row(session, identifier)
    if role_identifier is not None and role_identifier != identifier:
        raise UnprocessableError([FieldError(
            "role_identifier", "path_mismatch",
            "identifier in body must match the path")])
    before = to_dict(row)
    row.role_name = gov.require_nonempty(name, field="role_name")
    row.role_status = _require_status(status or "candidate")
    row.role_scope_access = scope_access
    row.role_system_permissions = system_permissions
    row.role_description = description
    row.role_notes = notes
    session.flush()
    after = to_dict(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="update", before=before, after=after)
    return after


def patch_role(session: Session, identifier: str, **fields) -> dict:
    unknown = set(fields) - _PATCHABLE
    if unknown:
        raise UnprocessableError([FieldError(
            "fields", "unknown_field",
            f"unknown patchable fields: {sorted(unknown)}")])
    row = _get_row(session, identifier)
    before = to_dict(row)
    if "name" in fields:
        row.role_name = gov.require_nonempty(fields["name"], field="role_name")
    if "status" in fields:
        row.role_status = _require_status(fields["status"])
    if "scope_access" in fields:
        row.role_scope_access = fields["scope_access"]
    if "system_permissions" in fields:
        row.role_system_permissions = fields["system_permissions"]
    if "description" in fields:
        row.role_description = fields["description"]
    if "notes" in fields:
        row.role_notes = fields["notes"]
    session.flush()
    after = to_dict(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="update", before=before, after=after)
    return after


def delete_role(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.role_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.role_deleted_at = datetime.now(UTC)
    session.flush()
    after = to_dict(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="update", before=before, after=after)
    return after


def restore_role(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.role_deleted_at is None:
        raise UnprocessableError([FieldError(
            "role_deleted_at", "not_deleted", "role is not soft-deleted")])
    before = to_dict(row)
    row.role_deleted_at = None
    session.flush()
    after = to_dict(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="update", before=before, after=after)
    return after

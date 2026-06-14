"""Layout repository — PI-193 (PRJ-027).

A layout (``LAY-NNN``) is one engine-neutral detail/list/etc. layout of an
entity. Standard CRUD backing the ``/layouts`` REST endpoints plus the
allocator; ``layout_type`` / ``layout_status`` are controlled vocabularies.
Reconcile matches by (entity, type) via :func:`list_layouts`.
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
from crmbuilder_v2.access.models import Layout
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import LAYOUT_STATUSES, LAYOUT_TYPES

_ENTITY_TYPE = "layout"
_PREFIX = "LAY"
_IDENTIFIER_RE = re.compile(r"^LAY-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_PATCHABLE = frozenset(
    {"entity_identifier", "layout_type", "content", "status", "notes"}
)


def _require_type(v: object) -> str:
    return gov.require_in(v, LAYOUT_TYPES, field="layout_type")


def _require_status(v: object) -> str:
    return gov.require_in(v, LAYOUT_STATUSES, field="layout_status")


def _get_row(session: Session, identifier: str) -> Layout:
    row = get_by_identifier(session, Layout, Layout.layout_identifier, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment(identifier: str) -> str:
    return f"{_PREFIX}-{int(identifier.split('-', 1)[1]) + 1:03d}"


def list_layouts(
    session: Session,
    *,
    include_deleted: bool = False,
    entity_identifier: str | None = None,
    layout_type: str | None = None,
) -> list[dict]:
    stmt = select(Layout).order_by(Layout.layout_identifier)
    if not include_deleted:
        stmt = stmt.where(Layout.layout_deleted_at.is_(None))
    if entity_identifier is not None:
        stmt = stmt.where(Layout.layout_entity_identifier == entity_identifier)
    if layout_type is not None:
        stmt = stmt.where(Layout.layout_type == layout_type)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_layout(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    row = get_by_identifier(session, Layout, Layout.layout_identifier, identifier)
    if row is None or (row.layout_deleted_at is not None and not include_deleted):
        return None
    return to_dict(row)


def next_layout_identifier(session: Session) -> str:
    return next_prefixed_identifier(
        session.scalars(select(Layout.layout_identifier)).all(), _PREFIX
    )


def _new_row(identifier, entity_identifier, layout_type, content, status, notes):
    return Layout(
        layout_identifier=identifier,
        layout_entity_identifier=entity_identifier,
        layout_type=layout_type,
        layout_content=content,
        layout_status=status,
        layout_notes=notes,
    )


def _insert_with_autoassign(session, **kw) -> Layout:
    candidate = next_layout_identifier(session)
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
    raise ConflictError("could not assign a unique layout identifier") from last


def create_layout(
    session: Session,
    *,
    entity_identifier: str,
    layout_type: str,
    content: dict | None = None,
    status: str = "candidate",
    notes: str | None = None,
    identifier: str | None = None,
) -> dict:
    entity_identifier = gov.require_nonempty(
        entity_identifier, field="layout_entity_identifier"
    )
    layout_type = _require_type(layout_type)
    status = _require_status(status or "candidate")
    kw = {
        "entity_identifier": entity_identifier,
        "layout_type": layout_type,
        "content": content,
        "status": status,
        "notes": notes,
    }
    if identifier is None:
        row = _insert_with_autoassign(session, **kw)
    else:
        gov.require_identifier_format(
            identifier, regex=_IDENTIFIER_RE, field="layout_identifier",
            example="LAY-001",
        )
        if get_by_identifier(
            session, Layout, Layout.layout_identifier, identifier
        ) is not None:
            raise ConflictError(f"layout {identifier!r} already exists")
        row = _new_row(identifier, **kw)
        session.add(row)
        session.flush()
    after = to_dict(row)
    emit(session, entity_type=_ENTITY_TYPE,
         entity_identifier=row.layout_identifier, operation="insert",
         before=None, after=after)
    return after


def update_layout(
    session: Session, identifier: str, *,
    layout_identifier: str | None = None,
    entity_identifier: str, layout_type: str,
    content: dict | None = None, status: str = "candidate",
    notes: str | None = None,
) -> dict:
    row = _get_row(session, identifier)
    if layout_identifier is not None and layout_identifier != identifier:
        raise UnprocessableError([FieldError(
            "layout_identifier", "path_mismatch",
            "identifier in body must match the path")])
    before = to_dict(row)
    row.layout_entity_identifier = gov.require_nonempty(
        entity_identifier, field="layout_entity_identifier")
    row.layout_type = _require_type(layout_type)
    row.layout_status = _require_status(status or "candidate")
    row.layout_content = content
    row.layout_notes = notes
    session.flush()
    after = to_dict(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="update", before=before, after=after)
    return after


def patch_layout(session: Session, identifier: str, **fields) -> dict:
    unknown = set(fields) - _PATCHABLE
    if unknown:
        raise UnprocessableError([FieldError(
            "fields", "unknown_field",
            f"unknown patchable fields: {sorted(unknown)}")])
    row = _get_row(session, identifier)
    before = to_dict(row)
    if "entity_identifier" in fields:
        row.layout_entity_identifier = gov.require_nonempty(
            fields["entity_identifier"], field="layout_entity_identifier")
    if "layout_type" in fields:
        row.layout_type = _require_type(fields["layout_type"])
    if "status" in fields:
        row.layout_status = _require_status(fields["status"])
    if "content" in fields:
        row.layout_content = fields["content"]
    if "notes" in fields:
        row.layout_notes = fields["notes"]
    session.flush()
    after = to_dict(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="update", before=before, after=after)
    return after


def delete_layout(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.layout_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.layout_deleted_at = datetime.now(UTC)
    session.flush()
    after = to_dict(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="update", before=before, after=after)
    return after


def restore_layout(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.layout_deleted_at is None:
        raise UnprocessableError([FieldError(
            "layout_deleted_at", "not_deleted", "layout is not soft-deleted")])
    before = to_dict(row)
    row.layout_deleted_at = None
    session.flush()
    after = to_dict(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="update", before=before, after=after)
    return after

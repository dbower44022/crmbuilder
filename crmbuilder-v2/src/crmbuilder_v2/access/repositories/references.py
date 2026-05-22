"""Universal references repository (DEC-006).

References are identified by the tuple (source_type, source_id, target_type,
target_id, relationship). There is no separate ``identifier`` column; the
tuple itself is the identity. The repository accepts either an integer
``id`` or the full tuple for lookups.

References cannot be updated — to "change" one, delete and recreate.
"""

from __future__ import annotations

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import require_in, require_string, to_dict
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
)
from crmbuilder_v2.access.models import Reference
from crmbuilder_v2.access.vocab import ENTITY_TYPES, REFERENCE_RELATIONSHIPS

_ENTITY_TYPE = "reference"


def next_reference_identifier(session: Session) -> str:
    """Return the next available ``REF-NNNN`` external identifier (v0.7).

    References gained a prefixed external identifier in v0.7 so individual
    rows can be targeted by ``deposit_event_wrote_record`` back-references.
    The value is server-assigned on insert; this scans the existing
    identifiers for the highest ``REF-NNNN`` and increments, zero-padded
    to four digits.
    """
    existing = session.scalars(
        select(Reference.reference_identifier).where(
            Reference.reference_identifier.is_not(None)
        )
    ).all()
    highest = 0
    for ident in existing:
        if ident and ident.startswith("REF-"):
            try:
                highest = max(highest, int(ident.split("-", 1)[1]))
            except ValueError:
                continue
    return f"REF-{highest + 1:04d}"


def compute_next_identifier(session: Session) -> int:
    """Return the next reference primary-key ``id``.

    References are tuple-identified and carry no prefixed identifier;
    their addressable identity is the integer ``id`` primary key (see
    :func:`get`, :func:`delete_by_id`). For API-surface consistency
    with the other prefixed-identifier governance entity types
    (DEC-043), this returns the next autoincrement id.
    """
    highest = session.scalar(select(func.max(Reference.id)))
    return (highest or 0) + 1


def _row_dict(row: Reference) -> dict:
    base = to_dict(row)
    # Surface the column under a vocabulary-friendly name for clients.
    base["relationship"] = base.pop("relationship_kind")
    return base


def _identifier(row: Reference) -> str:
    return f"{row.source_type}:{row.source_id} -[{row.relationship_kind}]-> {row.target_type}:{row.target_id}"


def get(session: Session, ref_id: int) -> dict:
    row = session.get(Reference, ref_id)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, str(ref_id))
    return _row_dict(row)


def list_all(session: Session) -> list[dict]:
    rows = session.scalars(
        select(Reference).order_by(
            Reference.source_type,
            Reference.source_id,
            Reference.relationship_kind,
            Reference.target_type,
            Reference.target_id,
        )
    ).all()
    return [_row_dict(r) for r in rows]


def list_from(session: Session, *, source_type: str, source_id: str) -> list[dict]:
    require_in(source_type, ENTITY_TYPES, field="source_type")
    rows = session.scalars(
        select(Reference)
        .where(
            and_(
                Reference.source_type == source_type,
                Reference.source_id == source_id,
            )
        )
        .order_by(Reference.relationship_kind, Reference.target_type, Reference.target_id)
    ).all()
    return [_row_dict(r) for r in rows]


def list_to(session: Session, *, target_type: str, target_id: str) -> list[dict]:
    require_in(target_type, ENTITY_TYPES, field="target_type")
    rows = session.scalars(
        select(Reference)
        .where(
            and_(
                Reference.target_type == target_type,
                Reference.target_id == target_id,
            )
        )
        .order_by(Reference.relationship_kind, Reference.source_type, Reference.source_id)
    ).all()
    return [_row_dict(r) for r in rows]


def list_touching(session: Session, *, entity_type: str, entity_id: str) -> dict:
    require_in(entity_type, ENTITY_TYPES, field="entity_type")
    rows = session.scalars(
        select(Reference).where(
            or_(
                and_(
                    Reference.source_type == entity_type,
                    Reference.source_id == entity_id,
                ),
                and_(
                    Reference.target_type == entity_type,
                    Reference.target_id == entity_id,
                ),
            )
        )
    ).all()
    sources = []
    targets = []
    for r in rows:
        d = _row_dict(r)
        if r.source_type == entity_type and r.source_id == entity_id:
            sources.append(d)
        if r.target_type == entity_type and r.target_id == entity_id:
            targets.append(d)
    return {
        "as_source": sources,
        "as_target": targets,
    }


def create(
    session: Session,
    *,
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str,
    relationship: str,
) -> dict:
    require_in(source_type, ENTITY_TYPES, field="source_type")
    require_in(target_type, ENTITY_TYPES, field="target_type")
    require_in(relationship, REFERENCE_RELATIONSHIPS, field="relationship")
    require_string(source_id, field="source_id")
    require_string(target_id, field="target_id")

    existing = session.scalar(
        select(Reference).where(
            and_(
                Reference.source_type == source_type,
                Reference.source_id == source_id,
                Reference.target_type == target_type,
                Reference.target_id == target_id,
                Reference.relationship_kind == relationship,
            )
        )
    )
    if existing is not None:
        raise ConflictError(f"reference already exists: {_identifier(existing)}")

    row = Reference(
        reference_identifier=next_reference_identifier(session),
        source_type=source_type,
        source_id=source_id,
        target_type=target_type,
        target_id=target_id,
        relationship_kind=relationship,
    )
    session.add(row)
    session.flush()
    after = _row_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=_identifier(row),
        operation="insert",
        before=None,
        after=after,
    )
    return after


def delete_by_id(session: Session, ref_id: int) -> dict:
    """Hard-delete a reference by integer primary key.

    Mirrors :func:`delete` but addresses the row by ``id`` instead of
    by the full tuple. Used by the v0.3 ``DELETE /references/{id}``
    REST endpoint (added in slice C) so the UI can issue a delete
    using the integer id surfaced on every reference row.
    """
    row = session.get(Reference, ref_id)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, str(ref_id))
    before = _row_dict(row)
    identifier = _identifier(row)
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


def delete(
    session: Session,
    *,
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str,
    relationship: str,
) -> dict:
    row = session.scalar(
        select(Reference).where(
            and_(
                Reference.source_type == source_type,
                Reference.source_id == source_id,
                Reference.target_type == target_type,
                Reference.target_id == target_id,
                Reference.relationship_kind == relationship,
            )
        )
    )
    if row is None:
        raise NotFoundError(
            _ENTITY_TYPE,
            f"{source_type}:{source_id} -[{relationship}]-> {target_type}:{target_id}",
        )
    before = _row_dict(row)
    identifier = _identifier(row)
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


def upsert(
    session: Session,
    *,
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str,
    relationship: str,
) -> dict:
    """Idempotent insert; returns existing row if the reference already exists."""
    existing = session.scalar(
        select(Reference).where(
            and_(
                Reference.source_type == source_type,
                Reference.source_id == source_id,
                Reference.target_type == target_type,
                Reference.target_id == target_id,
                Reference.relationship_kind == relationship,
            )
        )
    )
    if existing is not None:
        return _row_dict(existing)
    return create(
        session,
        source_type=source_type,
        source_id=source_id,
        target_type=target_type,
        target_id=target_id,
        relationship=relationship,
    )

"""Source mapping targets repository — PI-255 (PRJ-027 / SES-230).

The design-entity targets of an entity-level source mapping. A direct or
referential mapping has one target; a decomposition has several. A lightweight
child-table repository (integer PK, no prefixed identifier, no change_log /
refs participation), mirroring the ``instance_membership`` pattern. The parent
link is a soft reference; the access layer treats the (mapping, entity) pair as
the natural key and is idempotent on add.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import to_dict
from crmbuilder_v2.access.models import SourceMappingTarget


def list_targets(
    session: Session, *, source_mapping_identifier: str
) -> list[dict]:
    stmt = (
        select(SourceMappingTarget)
        .where(
            SourceMappingTarget.source_mapping_identifier
            == source_mapping_identifier
        )
        .order_by(SourceMappingTarget.entity_identifier)
    )
    return [to_dict(r) for r in session.scalars(stmt).all()]


def _find(
    session: Session, source_mapping_identifier: str, entity_identifier: str
) -> SourceMappingTarget | None:
    stmt = select(SourceMappingTarget).where(
        SourceMappingTarget.source_mapping_identifier == source_mapping_identifier,
        SourceMappingTarget.entity_identifier == entity_identifier,
    )
    return session.scalars(stmt).first()


def add_target(
    session: Session, *, source_mapping_identifier: str, entity_identifier: str
) -> dict:
    """Add a design-entity target, idempotent on (mapping, entity)."""
    existing = _find(session, source_mapping_identifier, entity_identifier)
    if existing is not None:
        return to_dict(existing)
    row = SourceMappingTarget(
        source_mapping_identifier=source_mapping_identifier,
        entity_identifier=entity_identifier,
    )
    session.add(row)
    session.flush()
    return to_dict(row)


def remove_target(
    session: Session, *, source_mapping_identifier: str, entity_identifier: str
) -> None:
    """Hard-delete one target (child table, no soft-delete)."""
    row = _find(session, source_mapping_identifier, entity_identifier)
    if row is not None:
        session.delete(row)
        session.flush()


def set_targets(
    session: Session,
    *,
    source_mapping_identifier: str,
    entity_identifiers: list[str],
) -> list[dict]:
    """Replace all targets of a source mapping atomically."""
    current = session.scalars(
        select(SourceMappingTarget).where(
            SourceMappingTarget.source_mapping_identifier
            == source_mapping_identifier
        )
    ).all()
    for row in current:
        session.delete(row)
    session.flush()
    out: list[dict] = []
    for entity_identifier in dict.fromkeys(entity_identifiers):
        row = SourceMappingTarget(
            source_mapping_identifier=source_mapping_identifier,
            entity_identifier=entity_identifier,
        )
        session.add(row)
        out.append(row)
    session.flush()
    return [to_dict(r) for r in out]

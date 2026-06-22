"""Mapping candidate repository — PI-255 reconciler output (PRJ-027 / SES-230).

The reconciler writes discovery candidates here — never directly to the mapping
tables (DEC-575). A candidate is an unmatched source entity / field / value
surfaced by an audit, optionally carrying a confidence-ranked suggested mapping.
A human resolves it into a real mapping. Integer-PK with no prefixed identifier,
but in ENTITY_TYPES so single creates and resolutions emit a change_log row keyed
by the integer id; ``bulk_create_candidates`` (the reconciler's batch path) does
not emit per-row change_log by design.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import to_dict
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.models import MappingCandidate
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import (
    MAPPING_CANDIDATE_TYPES,
    MAPPING_SUGGESTION_CONFIDENCES,
)

_ENTITY_TYPE = "mapping_candidate"


def _require_candidate_type(value: object) -> str:
    return gov.require_in(value, MAPPING_CANDIDATE_TYPES, field="candidate_type")


def _require_confidence(value: object) -> str:
    return gov.require_in(
        value, MAPPING_SUGGESTION_CONFIDENCES, field="suggestion_confidence"
    )


def _get_row(session: Session, id_: int) -> MappingCandidate:
    row = session.get(MappingCandidate, id_)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, str(id_))
    return row


def list_candidates(
    session: Session,
    *,
    instance_identifier: str | None = None,
    candidate_type: str | None = None,
    resolved: bool | None = None,
) -> list[dict]:
    stmt = select(MappingCandidate).order_by(MappingCandidate.id)
    if instance_identifier is not None:
        stmt = stmt.where(
            MappingCandidate.instance_identifier == instance_identifier
        )
    if candidate_type is not None:
        stmt = stmt.where(MappingCandidate.candidate_type == candidate_type)
    if resolved is not None:
        stmt = stmt.where(MappingCandidate.resolved.is_(resolved))
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_candidate(session: Session, id_: int) -> dict | None:
    row = session.get(MappingCandidate, id_)
    return to_dict(row) if row is not None else None


def _new_row(
    *,
    instance_identifier: str,
    candidate_type: str,
    source_entity_name: str,
    source_field_name: str | None = None,
    source_value: str | None = None,
    audit_event_identifier: str | None = None,
    suggested_source_mapping_identifier: str | None = None,
    suggested_field_mapping_identifier: str | None = None,
    suggestion_confidence: str | None = None,
    suggestion_basis: str | None = None,
) -> MappingCandidate:
    instance_identifier = gov.require_nonempty(
        instance_identifier, field="instance_identifier"
    )
    candidate_type = _require_candidate_type(candidate_type)
    source_entity_name = gov.require_nonempty(
        source_entity_name, field="source_entity_name"
    )
    if suggestion_confidence is not None:
        suggestion_confidence = _require_confidence(suggestion_confidence)
    return MappingCandidate(
        instance_identifier=instance_identifier,
        candidate_type=candidate_type,
        source_entity_name=source_entity_name,
        source_field_name=source_field_name,
        source_value=source_value,
        audit_event_identifier=audit_event_identifier,
        suggested_source_mapping_identifier=suggested_source_mapping_identifier,
        suggested_field_mapping_identifier=suggested_field_mapping_identifier,
        suggestion_confidence=suggestion_confidence,
        suggestion_basis=suggestion_basis,
        resolved=False,
    )


def create_candidate(
    session: Session,
    *,
    instance_identifier: str,
    candidate_type: str,
    source_entity_name: str,
    source_field_name: str | None = None,
    source_value: str | None = None,
    audit_event_identifier: str | None = None,
    suggested_source_mapping_identifier: str | None = None,
    suggested_field_mapping_identifier: str | None = None,
    suggestion_confidence: str | None = None,
    suggestion_basis: str | None = None,
) -> dict:
    row = _new_row(
        instance_identifier=instance_identifier,
        candidate_type=candidate_type,
        source_entity_name=source_entity_name,
        source_field_name=source_field_name,
        source_value=source_value,
        audit_event_identifier=audit_event_identifier,
        suggested_source_mapping_identifier=suggested_source_mapping_identifier,
        suggested_field_mapping_identifier=suggested_field_mapping_identifier,
        suggestion_confidence=suggestion_confidence,
        suggestion_basis=suggestion_basis,
    )
    session.add(row)
    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=str(row.id),
        operation="insert",
        before=None,
        after=after,
    )
    return after


def bulk_create_candidates(
    session: Session, candidates: list[dict]
) -> list[dict]:
    """Batch-insert candidates (reconciler path). No per-row change_log."""
    rows = [_new_row(**spec) for spec in candidates]
    session.add_all(rows)
    session.flush()
    return [to_dict(r) for r in rows]


def resolve_candidate(
    session: Session,
    id_: int,
    *,
    resolved_to_source_mapping_identifier: str | None = None,
    resolved_to_field_mapping_identifier: str | None = None,
) -> dict:
    row = _get_row(session, id_)
    before = to_dict(row)
    row.resolved = True
    row.resolved_at = datetime.now(UTC)
    row.resolved_to_source_mapping_identifier = (
        resolved_to_source_mapping_identifier
    )
    row.resolved_to_field_mapping_identifier = resolved_to_field_mapping_identifier
    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=str(row.id),
        operation="update",
        before=before,
        after=after,
    )
    return after

"""Shared enforcement for the terminal ``rejected`` lifecycle status.

PI-153 / WTK-088 design spec §3.4 (D1). The seven status-bearing
methodology entity types share one rejection mechanism: a record may sit
at ``rejected`` only while it carries at least one live outbound
``rejected_by_decision`` edge to the Decision that rejected it
(invariant I3), and that supporting edge cannot be deleted while the
record remains at ``rejected`` (invariant I4, the v0.7
consumed-requires-edge precedent).

Two admission paths, mirroring the PI-030 ``resolves`` atomic
edge-and-flip pattern:

1. **Atomic edge + flip** — the status PATCH/PUT carries the rejecting
   Decision's identifier (``rejected_by_decision: "DEC-NNN"``); the
   repository validates the Decision exists and creates the edge in the
   same transaction as the status flip.
2. **Edge-first** — a client POSTs the ``rejected_by_decision``
   reference first and then PATCHes the status without the key; the
   pre-existing live edge admits the transition.

The per-type repositories call :func:`enforce_rejected_status` from
their status-change branches and :func:`attach_decision` for a
``rejected_by_decision`` key supplied outside a transition (a later
superseding Decision adding a second edge per spec §3.4 cardinality).
``references.py`` calls :func:`guard_edge_delete` from its two delete
paths.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.exceptions import FieldError, UnprocessableError
from crmbuilder_v2.access.models import (
    Decision,
    Domain,
    Entity,
    Field,
    ManualConfig,
    MigrationMapping,
    Persona,
    Reference,
    Requirement,
    TestSpec,
)

_KIND = "rejected_by_decision"

# The §3.1 scope: every status-bearing methodology entity type, mapped to
# (model, identifier attribute, status attribute). `process` carries no
# lifecycle status and is deliberately absent (WTK-088 §3.1).
# `migration_mapping` joined per WTK-106 (the vocab pair rule landed with
# the storage slice; the repository wiring is WTK-107).
_REJECTABLE_SOURCES: dict[str, tuple[type, str, str]] = {
    "domain": (Domain, "domain_identifier", "domain_status"),
    "entity": (Entity, "entity_identifier", "entity_status"),
    "field": (Field, "field_identifier", "field_status"),
    "persona": (Persona, "persona_identifier", "persona_status"),
    "requirement": (Requirement, "requirement_identifier", "requirement_status"),
    "test_spec": (TestSpec, "test_spec_identifier", "test_spec_status"),
    "manual_config": (
        ManualConfig,
        "manual_config_identifier",
        "manual_config_status",
    ),
    "migration_mapping": (
        MigrationMapping,
        "migration_mapping_identifier",
        "migration_mapping_status",
    ),
}


def _has_rejection_edge(
    session: Session, source_type: str, source_identifier: str
) -> bool:
    row = session.scalar(
        select(Reference).where(
            Reference.source_type == source_type,
            Reference.source_id == source_identifier,
            Reference.target_type == "decision",
            Reference.relationship_kind == _KIND,
        )
    )
    return row is not None


def _require_decision(session: Session, decision_identifier: object) -> str:
    """Validate the rejecting Decision identifier resolves to a real record.

    Decisions carry no soft-delete column (supersession is their retirement
    mechanism), so existence is the liveness check.
    """
    if not isinstance(decision_identifier, str) or not decision_identifier.strip():
        raise UnprocessableError(
            [
                FieldError(
                    "rejected_by_decision",
                    "missing_or_empty",
                    "must be a non-empty Decision identifier (DEC-NNN)",
                )
            ]
        )
    decision_identifier = decision_identifier.strip()
    decision = get_by_identifier(
        session, Decision, Decision.identifier, decision_identifier
    )
    if decision is None:
        raise UnprocessableError(
            [
                FieldError(
                    "rejected_by_decision",
                    "decision_not_found",
                    f"decision {decision_identifier!r} not found",
                )
            ]
        )
    return decision_identifier


def _create_edge(
    session: Session,
    source_type: str,
    source_identifier: str,
    decision_identifier: str,
) -> None:
    # Imported locally to avoid a module-load cycle (references.py imports
    # this module from its delete paths).
    from crmbuilder_v2.access.repositories import references

    references.upsert(
        session,
        source_type=source_type,
        source_id=source_identifier,
        target_type="decision",
        target_id=decision_identifier,
        relationship=_KIND,
    )


def enforce_rejected_status(
    session: Session,
    *,
    source_type: str,
    source_identifier: str,
    decision_identifier: str | None,
) -> None:
    """Admit a status transition to ``rejected`` (invariant I3).

    With ``decision_identifier`` supplied this is the atomic
    edge-and-flip path: the Decision is validated and the
    ``rejected_by_decision`` edge is created (idempotently) in the
    caller's transaction. Without it, a pre-existing live edge must
    already be in place or the transition is refused (422).
    """
    if decision_identifier is not None:
        decision_identifier = _require_decision(session, decision_identifier)
        _create_edge(session, source_type, source_identifier, decision_identifier)
        return
    if not _has_rejection_edge(session, source_type, source_identifier):
        raise UnprocessableError(
            [
                FieldError(
                    "rejected_by_decision",
                    "rejected_requires_decision_edge",
                    "a transition to 'rejected' requires either a "
                    "rejected_by_decision key naming the rejecting Decision "
                    "or a pre-existing rejected_by_decision reference edge",
                )
            ]
        )


def attach_decision(
    session: Session,
    *,
    source_type: str,
    source_identifier: str,
    decision_identifier: str,
    current_status: str,
) -> None:
    """Handle a ``rejected_by_decision`` key outside a status transition.

    Valid only while the record is at ``rejected`` (a later superseding
    Decision adding a second edge per spec §3.4 cardinality); any other
    status refuses the key.
    """
    if current_status != "rejected":
        raise UnprocessableError(
            [
                FieldError(
                    "rejected_by_decision",
                    "invalid_usage",
                    "rejected_by_decision is only accepted alongside a "
                    "status change to 'rejected' or on a record already "
                    "at 'rejected'",
                )
            ]
        )
    decision_identifier = _require_decision(session, decision_identifier)
    _create_edge(session, source_type, source_identifier, decision_identifier)


def guard_edge_delete(session: Session, row: Reference) -> None:
    """Refuse deleting a ``rejected_by_decision`` edge of a rejected record.

    Invariant I4 (consumed-requires-edge precedent): the supporting edge
    is locked while the source record's status is ``rejected`` — even
    when the record is soft-deleted, because restore preserves
    ``rejected`` and must come back edge-backed. A missing source row
    permits the orphan-edge cleanup.
    """
    if row.relationship_kind != _KIND:
        return
    spec = _REJECTABLE_SOURCES.get(row.source_type)
    if spec is None:
        return
    model, identifier_attr, status_attr = spec
    source = get_by_identifier(
        session, model, getattr(model, identifier_attr), row.source_id
    )
    if source is None:
        return
    if getattr(source, status_attr) == "rejected":
        raise UnprocessableError(
            [
                FieldError(
                    "relationship",
                    "rejected_edge_locked",
                    f"{row.source_type} {row.source_id} is at 'rejected'; "
                    "its rejected_by_decision edge cannot be deleted while "
                    "the record remains rejected",
                )
            ]
        )

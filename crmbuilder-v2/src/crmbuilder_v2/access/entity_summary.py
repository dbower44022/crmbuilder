"""Reference-target summary resolver (PI under PRJ-015 — references grid).

The references UI (``ReferencesSection``) historically rendered each edge
as just ``identifier + type`` — you could not tell *what* ``PI-048`` was
without navigating to it. To show key fields (title, status, created,
updated) inline in a sortable/filterable grid, each edge needs the *other*
record's summary joined in.

This module is the single per-entity-type registry mapping every
``ENTITY_TYPES`` member to the columns that hold its display title, status,
and lifecycle timestamps. :func:`summarize` resolves one ``(entity_type,
identifier)`` to a uniform summary dict; :func:`list_touching` in the
references repository calls it for the far side of every edge.

Coverage is exhaustive by construction: every member of ``ENTITY_TYPES`` is
either in ``_SPECS`` or ``_NO_SUMMARY``. ``test_entity_summary.py`` asserts
this and asserts every named column actually exists on its model, so adding
a new entity type to the vocab fails the test until it is mapped here.

Status note: a few types have no literal ``status`` column but carry a
status-like enum that is the natural thing to surface — ``process`` →
classification, ``deposit_event`` → outcome. Those are mapped to the
status slot deliberately. ``topic`` and ``commit`` have nothing status-like
and map to ``None``.

Performance: one lookup per edge (N+1 across a record's references). This
is bounded — references render in a detail pane for a single record — and
kept simple on purpose; batching by type is a possible later optimization.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access import models
from crmbuilder_v2.access.vocab import ENTITY_TYPES


@dataclass(frozen=True)
class _Spec:
    """Column map for one entity type's summary fields."""

    model: type
    id_col: str
    title_col: str
    status_col: str | None
    created_col: str | None
    updated_col: str | None


# entity_type -> column map. Verified against the live models by
# ``test_entity_summary.py``'s introspection test.
_SPECS: dict[str, _Spec] = {
    # Core / "old eight" (unprefixed columns).
    "decision": _Spec(models.Decision, "identifier", "title", "status", "created_at", "updated_at"),
    "planning_item": _Spec(models.PlanningItem, "identifier", "title", "status", "created_at", "updated_at"),
    "risk": _Spec(models.Risk, "identifier", "title", "status", "created_at", "updated_at"),
    "session": _Spec(models.Session, "session_identifier", "session_title", "session_status", "session_created_at", "session_updated_at"),
    "topic": _Spec(models.Topic, "identifier", "name", None, "created_at", None),
    # Methodology entities (prefixed columns).
    "domain": _Spec(models.Domain, "domain_identifier", "domain_name", "domain_status", "domain_created_at", "domain_updated_at"),
    "entity": _Spec(models.Entity, "entity_identifier", "entity_name", "entity_status", "entity_created_at", "entity_updated_at"),
    "field": _Spec(models.Field, "field_identifier", "field_name", "field_status", "field_created_at", "field_updated_at"),
    "requirement": _Spec(models.Requirement, "requirement_identifier", "requirement_name", "requirement_status", "requirement_created_at", "requirement_updated_at"),
    "persona": _Spec(models.Persona, "persona_identifier", "persona_name", "persona_status", "persona_created_at", "persona_updated_at"),
    "process": _Spec(models.Process, "process_identifier", "process_name", "process_classification", "process_created_at", "process_updated_at"),
    "manual_config": _Spec(models.ManualConfig, "manual_config_identifier", "manual_config_name", "manual_config_status", "manual_config_created_at", "manual_config_updated_at"),
    "test_spec": _Spec(models.TestSpec, "test_spec_identifier", "test_spec_name", "test_spec_status", "test_spec_created_at", "test_spec_updated_at"),
    "crm_candidate": _Spec(models.CrmCandidate, "crm_candidate_identifier", "crm_candidate_name", "crm_candidate_status", "crm_candidate_created_at", "crm_candidate_updated_at"),
    # Governance entities (prefixed columns).
    "project": _Spec(models.Project, "project_identifier", "project_name", "project_status", "project_created_at", "project_updated_at"),
    "workstream": _Spec(models.Workstream, "workstream_identifier", "workstream_title", "workstream_status", "workstream_created_at", "workstream_updated_at"),
    "work_task": _Spec(models.WorkTask, "work_task_identifier", "work_task_title", "work_task_status", "work_task_created_at", "work_task_updated_at"),
    "conversation": _Spec(models.Conversation, "conversation_identifier", "conversation_title", "conversation_status", "conversation_created_at", "conversation_updated_at"),
    "reference_book": _Spec(models.ReferenceBook, "reference_book_identifier", "reference_book_title", "reference_book_status", "reference_book_created_at", "reference_book_updated_at"),
    "work_ticket": _Spec(models.WorkTicket, "work_ticket_identifier", "work_ticket_title", "work_ticket_status", "work_ticket_created_at", "work_ticket_updated_at"),
    "close_out_payload": _Spec(models.CloseOutPayload, "close_out_payload_identifier", "close_out_payload_title", "close_out_payload_status", "close_out_payload_created_at", "close_out_payload_updated_at"),
    "deposit_event": _Spec(models.DepositEvent, "deposit_event_identifier", "deposit_event_title", "deposit_event_outcome", "deposit_event_created_at", None),
    "commit": _Spec(models.Commit, "commit_identifier", "commit_message_first_line", None, "commit_created_at", "commit_updated_at"),
}

# Members of ENTITY_TYPES that intentionally carry no inline summary:
# version-keyed singletons (charter, status) have no identifier or title,
# and the catalog tables use an integer PK / display_name rather than a
# string identifier that matches a reference's source_id/target_id. These
# resolve to ``None`` and the grid shows just identifier + type for them.
_NO_SUMMARY: frozenset[str] = frozenset(
    {"charter", "status", "catalog_entity", "catalog_attribute"}
)


def summarize(
    session: Session, entity_type: str, identifier: str
) -> dict | None:
    """Resolve ``(entity_type, identifier)`` to a uniform summary dict.

    Returns ``{identifier, entity_type, title, status, created_at,
    updated_at}`` (timestamps as ``datetime``; the API envelope serializes
    them to ISO strings). Returns ``None`` when the type carries no summary
    (``_NO_SUMMARY``), is unknown, or the row does not exist.
    """
    spec = _SPECS.get(entity_type)
    if spec is None:
        return None
    row = session.scalar(
        select(spec.model).where(
            getattr(spec.model, spec.id_col) == identifier
        )
    )
    if row is None:
        return None

    def _g(col: str | None):
        return getattr(row, col) if col else None

    return {
        "identifier": identifier,
        "entity_type": entity_type,
        "title": _g(spec.title_col),
        "status": _g(spec.status_col),
        "created_at": _g(spec.created_col),
        "updated_at": _g(spec.updated_col),
    }


# Exposed for the coverage test: the set of types this module knows how to
# handle one way or another. Must equal ENTITY_TYPES.
KNOWN_TYPES: frozenset[str] = frozenset(_SPECS) | _NO_SUMMARY

assert KNOWN_TYPES == ENTITY_TYPES, (  # noqa: S101 — import-time coverage guard
    "entity_summary coverage drifted from ENTITY_TYPES: "
    f"missing={sorted(ENTITY_TYPES - KNOWN_TYPES)} "
    f"extra={sorted(KNOWN_TYPES - ENTITY_TYPES)}"
)

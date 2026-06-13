"""Capability-coverage report (requirements-provenance Phase 3).

The no-orphan-capability check, run in both directions:

- **orphan planning items** — planned/built work with no requirement above it.
  This is the exact gap that let the agent-rules capability ship un-specified:
  work existed, but no requirement traced to it.
- **unbuilt requirements** — active (``confirmed``) requirements with no planned
  work below them: specified, committed-to, but never planned.
- **conversations without a requirement** — completed conversations that
  produced no requirement, a candidate list of dropped intents for the PM to
  scan (soft signal: many conversations legitimately produce no requirement).

Read-only and engagement-scoped — the ORM execute hook in
:mod:`crmbuilder_v2.access.engagement_scope` applies the active-engagement
filter to every select automatically, so the plain selects below never leak
across engagements.

This is a **report, not a hard gate**: it surfaces gaps for the PM's
coverage-gaps review queue rather than blocking creation, because the existing
record corpus predates the provenance model. A creation-time enforcement gate is
a deliberate later step.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access.models import (
    Conversation,
    PlanningItem,
    Reference,
    Requirement,
)

_IMPLEMENTS = "planning_item_implements_requirement"
_DEFINED_IN = "requirement_defined_in_conversation"


def capability_coverage(session: Session) -> dict:
    """Return the bidirectional no-orphan-capability coverage report."""
    implemented_pi = set(
        session.scalars(
            select(Reference.source_id).where(
                Reference.source_type == "planning_item",
                Reference.relationship_kind == _IMPLEMENTS,
            )
        ).all()
    )
    built_requirements = set(
        session.scalars(
            select(Reference.target_id).where(
                Reference.target_type == "requirement",
                Reference.relationship_kind == _IMPLEMENTS,
            )
        ).all()
    )
    productive_conversations = set(
        session.scalars(
            select(Reference.target_id).where(
                Reference.target_type == "conversation",
                Reference.relationship_kind == _DEFINED_IN,
            )
        ).all()
    )

    orphan_planning_items = [
        {
            "identifier": pi.identifier,
            "title": pi.title,
            "item_type": pi.item_type,
            "status": pi.status,
        }
        for pi in session.scalars(
            select(PlanningItem).where(PlanningItem.status != "Cancelled")
        ).all()
        if pi.identifier not in implemented_pi
    ]

    unbuilt_requirements = [
        {
            "requirement_identifier": r.requirement_identifier,
            "requirement_name": r.requirement_name,
            "requirement_status": r.requirement_status,
        }
        for r in session.scalars(
            select(Requirement).where(
                Requirement.requirement_status == "confirmed",
                Requirement.requirement_deleted_at.is_(None),
            )
        ).all()
        if r.requirement_identifier not in built_requirements
    ]

    conversations_without_requirement = [
        {
            "conversation_identifier": c.conversation_identifier,
            "conversation_title": c.conversation_title,
            "conversation_status": c.conversation_status,
        }
        for c in session.scalars(
            select(Conversation).where(
                Conversation.conversation_status == "complete",
                Conversation.conversation_deleted_at.is_(None),
            )
        ).all()
        if c.conversation_identifier not in productive_conversations
    ]

    return {
        "orphan_planning_items": orphan_planning_items,
        "unbuilt_requirements": unbuilt_requirements,
        "conversations_without_requirement": conversations_without_requirement,
        "summary": {
            "orphan_planning_items": len(orphan_planning_items),
            "unbuilt_requirements": len(unbuilt_requirements),
            "conversations_without_requirement": len(
                conversations_without_requirement
            ),
        },
    }

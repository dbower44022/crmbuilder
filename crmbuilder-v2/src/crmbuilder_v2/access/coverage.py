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

**Baseline cutoff.** The existing corpus predates the provenance model, so every
pre-model record shows as a gap and swamps the genuinely-new ones. An optional
``since`` cutoff partitions each category by the record's ``created_at``: gaps
created at/after the cutoff are *live* (returned in the main lists and counted in
``summary``); gaps created before it are *baseline* (legacy debt, counted only in
``baseline_summary``). With no cutoff the report is unchanged — every gap is
"live" and ``baseline_summary`` is all zeros — so existing callers are
unaffected.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access.models import (
    Conversation,
    Entity,
    Field,
    Persona,
    PlanningItem,
    Reference,
    Requirement,
)

_IMPLEMENTS = "planning_item_implements_requirement"
_DEFINED_IN = "requirement_defined_in_conversation"
_WROTE_RECORD = "deposit_event_wrote_record"


def _as_naive(value: object) -> datetime | None:
    """Coerce a stored timestamp (datetime or ISO string) to a naive datetime.

    The corpus stores naive UTC timestamps; the ``since`` cutoff is normalized
    the same way so comparisons never mix aware/naive. Unparseable values yield
    ``None`` (treated as live — never hidden as baseline on a parse failure).
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    try:
        return datetime.fromisoformat(str(value)).replace(tzinfo=None)
    except ValueError:
        return None


def _partition(
    items: list[dict], *, since: datetime | None
) -> tuple[list[dict], list[dict]]:
    """Split items into (live, baseline) by their ``created_at`` against ``since``.

    With ``since=None`` everything is live (baseline empty), preserving the
    pre-cutoff behavior.
    """
    if since is None:
        return items, []
    live: list[dict] = []
    baseline: list[dict] = []
    for item in items:
        ts = _as_naive(item.get("created_at"))
        (baseline if (ts is not None and ts < since) else live).append(item)
    return live, baseline


def capability_coverage(session: Session, *, since: datetime | None = None) -> dict:
    """Return the bidirectional no-orphan-capability coverage report.

    ``since`` is an optional baseline cutoff: gaps whose record was created
    before it are reported as legacy *baseline* debt (counted in
    ``baseline_summary``, kept out of the main lists) rather than live gaps.
    """
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
            "created_at": pi.created_at,
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
            "created_at": r.requirement_created_at,
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
            "created_at": c.conversation_created_at,
        }
        for c in session.scalars(
            select(Conversation).where(
                Conversation.conversation_status == "complete",
                Conversation.conversation_deleted_at.is_(None),
            )
        ).all()
        if c.conversation_identifier not in productive_conversations
    ]

    opi_live, opi_base = _partition(orphan_planning_items, since=since)
    req_live, req_base = _partition(unbuilt_requirements, since=since)
    conv_live, conv_base = _partition(conversations_without_requirement, since=since)

    return {
        "orphan_planning_items": opi_live,
        "unbuilt_requirements": req_live,
        "conversations_without_requirement": conv_live,
        "summary": {
            "orphan_planning_items": len(opi_live),
            "unbuilt_requirements": len(req_live),
            "conversations_without_requirement": len(conv_live),
        },
        "baseline_since": since.isoformat() if since else None,
        "baseline_summary": {
            "orphan_planning_items": len(opi_base),
            "unbuilt_requirements": len(req_base),
            "conversations_without_requirement": len(conv_base),
        },
    }


def provenance_gaps(session: Session, *, since: datetime | None = None) -> dict:
    """Audit-discovered design records lacking deposit provenance (REQ-339).

    Every record the audit deposits should carry an inbound
    ``deposit_event_wrote_record`` edge to the deposit that produced it, so it
    is traceable to its source observation and usable as a migration source.
    This reports the live design records (entities, fields, personas) in the
    active engagement that have no such edge — candidates that entered the
    design without provenance — so the gap is surfaced and reported rather than
    silently accepted. Engagement-scoped via the ORM execute hook.

    With a ``since`` cutoff, records created before it that lack provenance are
    counted as pre-capability legacy debt (``baseline_summary``) rather than
    live gaps — the same baseline-cutoff stance as :func:`capability_coverage`.

    :returns: ``{provenanced_records, unprovenanced: {entities, fields,
        personas}, unprovenanced_count, clean, baseline_since,
        baseline_summary}``.
    """
    provenanced: set[str] = set(
        session.scalars(
            select(Reference.target_id).where(
                Reference.relationship_kind == _WROTE_RECORD
            )
        ).all()
    )
    gaps: dict[str, list[str]] = {"entities": [], "fields": [], "personas": []}
    baseline: dict[str, int] = {"entities": 0, "fields": 0, "personas": 0}
    specs = (
        (Entity.entity_identifier, Entity.entity_deleted_at,
         Entity.entity_created_at, "entities"),
        (Field.field_identifier, Field.field_deleted_at,
         Field.field_created_at, "fields"),
        (Persona.persona_identifier, Persona.persona_deleted_at,
         Persona.persona_created_at, "personas"),
    )
    for ident_col, deleted_col, created_col, key in specs:
        rows = session.execute(
            select(ident_col, created_col)
            .where(deleted_col.is_(None))
            .order_by(ident_col)
        ).all()
        for ident, created in rows:
            if ident in provenanced:
                continue
            if since is not None and _as_naive(created) is not None \
                    and _as_naive(created) < since:
                baseline[key] += 1
            else:
                gaps[key].append(ident)
    total = sum(len(v) for v in gaps.values())
    return {
        "provenanced_records": len(provenanced),
        "unprovenanced": gaps,
        "unprovenanced_count": total,
        "clean": total == 0,
        "baseline_since": since.isoformat() if since else None,
        "baseline_summary": baseline,
    }

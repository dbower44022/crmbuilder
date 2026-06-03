"""Registry write-back lifecycle (PI-122 slice 4 — PRD §13.2/§13.4, D-δ7).

The propose → promote workflow and the curate sweep, on top of the slice-1/3
catalog + learning entities. Promotion reuses the registry's hybrid governance
as the safety net — it does **not** add a new enforcement engine:

* promote a learning to a **skill** — float/pin (versioning) governs adoption.
* promote a learning to an **advisory governance_rule** — free.
* promote a learning to an **enforced** rule — **human review required, always**
  (``human_approved=True``); an agent must never self-grant a blocking
  constraint. This is the Needs Attention hard line (D-δ7).

A promoted learning is linked to what it became via ``learning_promoted_to`` and
flipped to ``status="promoted"``. The promoted skill/rule inherits the learning's
scope (system vs engagement).

Curation (``curate_area``) is the per-(release, area) sweep mechanism: it flips
contradicted, zero-confidence active learnings to ``stale``. The per-release
*cadence* (the Release entity) is the runtime follow-on; this is the mechanism.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from crmbuilder_v2.access.exceptions import FieldError, UnprocessableError
from crmbuilder_v2.access.repositories import (
    governance_rules,
    learnings,
    references,
    skills,
)

_PROMOTED_TO = "learning_promoted_to"
_CONTRADICTED_BY = "learning_contradicted_by"
_ENFORCED = {"enforced", "enforced_with_override"}


def promote_to_skill(
    session: Session,
    learning_id: str,
    *,
    name: str,
    kind: str,
    description: str | None = None,
) -> dict:
    """Promote a learning to a skill (float/pin is the adoption safety net)."""
    lrn = learnings.get(session, learning_id)
    skill = skills.create(
        session,
        name=name,
        kind=kind,
        description=description or lrn["content"],
        scope=lrn["scope"],
    )
    references.create(
        session,
        source_type="learning",
        source_id=learning_id,
        target_type="skill",
        target_id=skill["identifier"],
        relationship=_PROMOTED_TO,
    )
    learnings.update(session, learning_id, status="promoted")
    return {"learning": learning_id, "skill": skill}


def promote_to_rule(
    session: Session,
    learning_id: str,
    *,
    enforcement: str,
    body: str | None = None,
    severity: str | None = None,
    rule_type: str | None = None,
    human_approved: bool = False,
) -> dict:
    """Promote a learning to a governance_rule.

    Promoting to an **enforced** rule requires ``human_approved=True`` — the
    permanent hard line (D-δ7); advisory promotion is free.
    """
    if enforcement in _ENFORCED and not human_approved:
        raise UnprocessableError(
            [
                FieldError(
                    "human_approved",
                    "human_review_required",
                    "promoting a learning to an enforced rule requires human "
                    "review (human_approved=True); an agent must never self-grant "
                    "a blocking constraint",
                )
            ]
        )
    lrn = learnings.get(session, learning_id)
    rule = governance_rules.create(
        session,
        body=body or lrn["content"],
        enforcement=enforcement,
        severity=severity,
        rule_type=rule_type,
        scope=lrn["scope"],
    )
    references.create(
        session,
        source_type="learning",
        source_id=learning_id,
        target_type="governance_rule",
        target_id=rule["identifier"],
        relationship=_PROMOTED_TO,
    )
    learnings.update(session, learning_id, status="promoted")
    return {"learning": learning_id, "governance_rule": rule}


def curate_area(session: Session, *, area: str, scope: str | None = None) -> dict:
    """Sweep an area's active learnings, retiring contradicted, zero-confidence ones.

    The per-(release, area) curate mechanism (PRD §13.2). Flips a learning to
    ``stale`` when it has a contradiction edge AND confidence has fallen to 0.
    Returns a summary of what was retired. The per-release cadence + merge-
    duplicates are the runtime follow-on.
    """
    candidates = learnings.list_all(session, area=area, status="active", scope=scope)
    retired: list[str] = []
    for lrn in candidates:
        contra = references.list_references(
            session,
            source_type="learning",
            source_id=lrn["identifier"],
            relationship_kind=_CONTRADICTED_BY,
        )
        if contra and lrn["confidence"] == 0:
            learnings.update(session, lrn["identifier"], status="stale")
            retired.append(lrn["identifier"])
    return {"area": area, "scope": scope or "system", "retired": retired}

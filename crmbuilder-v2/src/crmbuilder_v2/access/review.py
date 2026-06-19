"""Review surface data layer (requirements-provenance Phase 6).

The data behind the topic-first review process (anchor §"How a review works"):

- ``topic_review`` — a topic's requirement tree (top-down), each node annotated
  with status, review_state, origin, provenance (the conversations it traces to),
  and spine flags (planned / verified). Descent stops where a descendant re-links
  to a sub-topic, per the topic-inheritance rule.
- ``topic_readback_document`` — a plain-language render of that tree, the artifact
  a PM reads top to bottom away from the app.
- ``approval_queue`` — candidates awaiting activation, with what each still needs.
- ``drift_queue`` — everything flagged ``needs_review`` by living drift.

Engagement-scoped automatically via the ORM execute hook. The Qt panel and the
recorded sign-off (Phase 6b) render/extend this layer; this is the testable
substance underneath them.
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access import rbac
from crmbuilder_v2.access.engagement_scope import get_active_engagement
from crmbuilder_v2.access.exceptions import (
    FieldError,
    NotFoundError,
    UnprocessableError,
    ValidationError,
)
from crmbuilder_v2.access.models import Reference, Requirement
from crmbuilder_v2.access.repositories import decisions as _decisions
from crmbuilder_v2.access.repositories import references as _references
from crmbuilder_v2.access.repositories import requirement as _requirement


def _refines_maps(session: Session) -> tuple[dict[str, list[str]], dict[str, str]]:
    """``requirement_refines_requirement`` edges as children-of and parent-of maps."""
    children_of: dict[str, list[str]] = defaultdict(list)
    parent_of: dict[str, str] = {}
    for child, parent in session.execute(
        select(Reference.source_id, Reference.target_id).where(
            Reference.source_type == "requirement",
            Reference.target_type == "requirement",
            Reference.relationship_kind == "requirement_refines_requirement",
        )
    ).all():
        children_of[parent].append(child)
        parent_of[child] = parent
    return children_of, parent_of


def _own_topic(session: Session) -> dict[str, str]:
    """Each requirement's directly-linked topic identifier (first if several)."""
    out: dict[str, str] = {}
    for src, tgt in session.execute(
        select(Reference.source_id, Reference.target_id).where(
            Reference.source_type == "requirement",
            Reference.target_type == "topic",
            Reference.relationship_kind == "requirement_belongs_to_topic",
        )
    ).all():
        out.setdefault(src, tgt)
    return out


def _defined_in(session: Session) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for src, tgt in session.execute(
        select(Reference.source_id, Reference.target_id).where(
            Reference.source_type == "requirement",
            Reference.target_type == "conversation",
            Reference.relationship_kind == "requirement_defined_in_conversation",
        )
    ).all():
        out[src].append(tgt)
    return out


def _ids_with(session: Session, *, side: str, kind: str, etype: str) -> set[str]:
    col = Reference.source_id if side == "source" else Reference.target_id
    type_col = Reference.source_type if side == "source" else Reference.target_type
    return set(
        session.scalars(
            select(col).where(type_col == etype, Reference.relationship_kind == kind)
        ).all()
    )


def topic_review(session: Session, topic_identifier: str) -> dict:
    """A topic's requirement tree with provenance + spine annotations."""
    reqs = {
        r.requirement_identifier: r
        for r in session.scalars(
            select(Requirement).where(Requirement.requirement_deleted_at.is_(None))
        ).all()
    }
    children_of, parent_of = _refines_maps(session)
    own_topic = _own_topic(session)
    defined_in = _defined_in(session)
    planned = _ids_with(
        session, side="target", kind="planning_item_implements_requirement",
        etype="requirement",
    )
    verified = _ids_with(
        session, side="source", kind="requirement_verified_by_test_spec",
        etype="requirement",
    )

    # Members = requirements that resolve to this topic: those directly linked,
    # plus descendants that have not re-linked to a different (sub)topic.
    members: set[str] = set()

    def _collect(rid: str) -> None:
        if rid in members or rid not in reqs:
            return
        members.add(rid)
        for child in children_of.get(rid, []):
            child_topic = own_topic.get(child)
            if child_topic is not None and child_topic != topic_identifier:
                continue
            _collect(child)

    for rid, topic in own_topic.items():
        if topic == topic_identifier and rid in reqs:
            _collect(rid)

    def _node(rid: str) -> dict:
        r = reqs[rid]
        return {
            "identifier": rid,
            "name": r.requirement_name,
            "status": r.requirement_status,
            "review_state": r.requirement_review_state,
            "origin": r.requirement_origin,
            "priority": r.requirement_priority,
            "acceptance_summary": r.requirement_acceptance_summary,
            "defined_in_conversations": defined_in.get(rid, []),
            "planned": rid in planned,
            "verified": rid in verified,
            "children": [
                _node(c) for c in sorted(children_of.get(rid, [])) if c in members
            ],
        }

    roots = sorted(m for m in members if parent_of.get(m) not in members)
    return {"topic": topic_identifier, "requirements": [_node(r) for r in roots]}


def topic_readback_document(session: Session, topic_identifier: str) -> str:
    """A plain-language render of a topic's requirement tree for human review."""
    review = topic_review(session, topic_identifier)
    lines = [f"# Requirements review — topic {topic_identifier}", ""]
    if not review["requirements"]:
        lines.append("_No requirements are linked to this topic yet._")
        return "\n".join(lines)

    def _render(node: dict, depth: int) -> None:
        indent = "  " * depth
        flags = []
        if node["review_state"] == "needs_review":
            flags.append("NEEDS REVIEW")
        if node["status"] == "confirmed" and not node["planned"]:
            flags.append("unbuilt")
        if node["status"] == "confirmed" and not node["verified"]:
            flags.append("unverified")
        suffix = f"  _({', '.join(flags)})_" if flags else ""
        lines.append(
            f"{indent}- **{node['identifier']}** [{node['status']}] "
            f"{node['name']}{suffix}"
        )
        lines.append(f"{indent}  - _acceptance:_ {node['acceptance_summary']}")
        if node["defined_in_conversations"]:
            lines.append(
                f"{indent}  - _defined in:_ "
                f"{', '.join(node['defined_in_conversations'])}"
            )
        for child in node["children"]:
            _render(child, depth + 1)

    for root in review["requirements"]:
        _render(root, 0)
    return "\n".join(lines)


def approval_queue(session: Session) -> list[dict]:
    """Candidate requirements awaiting activation, with what each still needs."""
    from crmbuilder_v2.access.repositories.requirement import _resolves_via_ancestry

    out = []
    for r in session.scalars(
        select(Requirement).where(
            Requirement.requirement_status == "candidate",
            Requirement.requirement_deleted_at.is_(None),
        )
    ).all():
        rid = r.requirement_identifier
        out.append(
            {
                "identifier": rid,
                "name": r.requirement_name,
                "origin": r.requirement_origin,
                "has_provenance": _resolves_via_ancestry(
                    session, rid, "requirement_defined_in_conversation"
                ),
                "has_topic": _resolves_via_ancestry(
                    session, rid, "requirement_belongs_to_topic"
                ),
            }
        )
    return out


def drift_queue(session: Session) -> list[dict]:
    """Requirements flagged ``needs_review`` by living drift."""
    return [
        {
            "identifier": r.requirement_identifier,
            "name": r.requirement_name,
            "status": r.requirement_status,
            "origin": r.requirement_origin,
        }
        for r in session.scalars(
            select(Requirement).where(
                Requirement.requirement_review_state == "needs_review",
                Requirement.requirement_deleted_at.is_(None),
            )
        ).all()
    ]


# ---------------------------------------------------------------------------
# Reviewer-driven approval (PI-229 / REQ-251) — the Requirements Review panel's
# approve action, so a human completes the review IN the panel rather than only
# through hand-assembled interface calls.
# ---------------------------------------------------------------------------


def approve_requirements(
    session: Session,
    *,
    requirement_identifiers: list[str],
    reviewer: str,
    decision_date: str,
    note: str | None = None,
) -> list[dict]:
    """Reviewer-driven approval of one or more candidate requirements (REQ-251).

    For each identifier — independently and in its own savepoint — record a
    governed approving decision authored by ``reviewer``, then create the
    ``requirement_approved_by_decision`` edge (which triggers
    ``activate_by_decision`` and its readability / provenance / topic gates
    atomically, confirming the requirement). Returns a per-requirement result
    (order-preserving with the input); one requirement's gate failure neither
    rolls back nor blocks the others. Confirming is *only* via this governed
    path — never a status edit (the bypass closed by PI-228).

    Authorization: the whole action is gated by the ``approve`` permission — the
    reviewer capability granted to the ``owner`` and ``editor`` roles, withheld
    from ``viewer`` and the agent tiers (WTK-177 / REQ-251). The check is a no-op
    when ``principal_auth_enabled`` is off (the default-owner localhost flow) and
    raises :class:`~crmbuilder_v2.access.rbac.PermissionDenied` (→ 403) otherwise.
    """
    rbac.check("approve", engagement_id=get_active_engagement())
    reviewer = (reviewer or "").strip()
    if not reviewer:
        raise UnprocessableError(
            [FieldError("reviewer", "missing_or_empty", "a reviewer is required")]
        )
    return [
        _approve_one(session, rid, reviewer=reviewer,
                     decision_date=decision_date, note=note)
        for rid in requirement_identifiers
    ]


def _approve_one(
    session: Session, rid: str, *, reviewer: str, decision_date: str,
    note: str | None,
) -> dict:
    try:
        row = _requirement.get_requirement(session, rid)
    except NotFoundError:
        return {"identifier": rid, "outcome": "failed",
                "decision_identifier": None,
                "reason": f"requirement {rid} not found"}
    if row["requirement_status"] == "confirmed":
        return {"identifier": rid, "outcome": "already_confirmed",
                "decision_identifier": None, "reason": None}

    note_clause = f" Reviewer note: {note}" if note else ""
    summary = (
        f"Records {reviewer}'s human review and approval of requirement {rid} "
        "for delivery. The reviewer examined the requirement's current statement "
        "in the Requirements Review panel and approved it through the governed "
        "approving-decision path, which confirms the requirement only after its "
        "readability, provenance, and topic gates pass — never by editing the "
        f"status field.{note_clause}"
    )
    try:
        with session.begin_nested():
            dec = _decisions.create(
                session,
                title=f"Approve {rid} for delivery",
                decision_date=decision_date,
                status="Active",
                context=(
                    f"{reviewer} reviewed requirement {rid} in the Requirements "
                    f"Review panel and approved it for delivery.{note_clause}"
                ),
                decision=(
                    f"Approve {rid} for delivery through the governed "
                    "approving-decision path."
                ),
                rationale=(
                    "Human review and approval recorded as a governed decision, "
                    "not a status edit; the approving-decision edge confirms the "
                    "requirement only if its gates pass."
                ),
                executive_summary=summary,
            )
            did = dec["identifier"]
            _references.create(
                session,
                source_type="requirement", source_id=rid,
                target_type="decision", target_id=did,
                relationship="requirement_approved_by_decision",
            )
        return {"identifier": rid, "outcome": "confirmed",
                "decision_identifier": did, "reason": None}
    except (UnprocessableError, ValidationError) as exc:
        # The savepoint rolled the decision + edge back; surface the gate's own
        # message so the reviewer learns *what to fix*, not merely *that* it failed.
        reason = str(exc.errors[0]) if getattr(exc, "errors", None) else str(exc)
        return {"identifier": rid, "outcome": "failed",
                "decision_identifier": None, "reason": reason}

"""Agent Profile Registry resolver (PI-122 slice 2, D-δ4).

Compose an ``agent_profile`` identifier into a **runtime-ready effective
contract**:

```
Contract = { profile_id, area, tier, scope, system_prompt, tools,
             advisory_rules, enforced_ruleset, active_learnings, version_stamp }
```

The scope merge (D-δ2/D-δ4) keeps **system rows ∪ the active engagement's
overlay rows**: a bound skill/rule is included iff it is ``active`` and its scope
is ``system`` (``engagement_id IS NULL``) or the active engagement. On top of that
merge, governance rules pass through an **overlay-resolution** step (WTK-001): an
engagement rule overrides a system rule of the same ``rule_type``, and an
engagement ``"disable:<id-or-rule_type>"`` rule suppresses a named system rule —
see :func:`_resolve_rule_overlay`. Active
(area, tier) learnings are injected from slice 4; this slice returns an empty
``active_learnings`` list. ``version_stamp`` is a deterministic hash that changes
whenever the profile or any bound item changes, so the runtime can cache and
re-resolve on change.
"""

from __future__ import annotations

import hashlib
import json

from sqlalchemy.orm import Session

from crmbuilder_v2.access.repositories import (
    agent_profiles,
    governance_rules,
    learnings,
    references,
    skills,
)
from crmbuilder_v2.access.vocab import LEARNING_TIERS

_HAS_SKILL = "agent_profile_has_skill"
_GOVERNED_BY = "agent_profile_governed_by_rule"
_ENFORCED = {"enforced", "enforced_with_override"}
_DISABLE_PREFIX = "disable:"


def _visible(record: dict, engagement_id: str | None) -> bool:
    """True if a registry record is in scope for ``engagement_id`` and active."""
    if record.get("status") != "active":
        return False
    row_engagement = record.get("engagement_id")
    return row_engagement is None or row_engagement == engagement_id


def _is_engagement_rule(rule: dict) -> bool:
    """True if a visible governance rule is an engagement overlay (not a system row).

    ``_visible`` has already kept only system rows (``engagement_id IS NULL``) and
    rows belonging to the active engagement, so any rule with a non-``None``
    ``engagement_id`` here is the active engagement's overlay.
    """
    return rule.get("engagement_id") is not None


def _resolve_rule_overlay(visible_rules: list[dict]) -> list[dict]:
    """Apply engagement override + disable semantics to the in-scope rules (WTK-001).

    Two engagement-overlay mechanisms shape the effective ruleset; both treat a
    system rule (``engagement_id IS NULL``) as the inheritable baseline and let the
    active engagement's overlay reshape it:

    - **Override.** An engagement rule with the same non-null ``rule_type`` as a
      system rule wins: the system rule of that ``rule_type`` is dropped and the
      engagement rule takes its place. Engagement rules with no ``rule_type`` (or a
      ``rule_type`` no system rule shares) add to the contract without displacing
      anything.
    - **Disable.** An engagement rule whose ``rule_type`` is ``"disable:<target>"``
      suppresses a matching system rule and is itself never emitted. ``<target>``
      matches a system rule by its ``identifier`` (e.g. ``"disable:GVR-007"``) or by
      its ``rule_type`` (e.g. ``"disable:no_force_push"``). A disable directive that
      matches nothing is simply dropped (no error — overlays are additive-by-intent).

    ``visible_rules`` is already scope-filtered and active-only. Order is preserved
    for every rule that survives, so downstream prompt/ruleset composition is stable.
    """
    # Partition the active engagement's overlay rules into disable directives
    # (control records, never emitted) and ordinary overlay rules.
    disable_targets: set[str] = set()
    overlay_rule_types: set[str] = set()
    is_disable: dict[int, bool] = {}
    for rule in visible_rules:
        if not _is_engagement_rule(rule):
            continue
        rule_type = rule.get("rule_type")
        if isinstance(rule_type, str) and rule_type.startswith(_DISABLE_PREFIX):
            disable_targets.add(rule_type[len(_DISABLE_PREFIX):].strip())
            is_disable[id(rule)] = True
        elif rule_type is not None:
            overlay_rule_types.add(rule_type)

    def _keep(rule: dict) -> bool:
        if _is_engagement_rule(rule):
            # Drop disable directives; keep every other overlay rule.
            return not is_disable.get(id(rule), False)
        # System rule: suppressed by a same-rule_type override or a disable target.
        rule_type = rule.get("rule_type")
        if rule_type is not None and rule_type in overlay_rule_types:
            return False
        if rule["identifier"] in disable_targets:
            return False
        return not (rule_type is not None and rule_type in disable_targets)

    return [r for r in visible_rules if _keep(r)]


# REQ-464 / PI-393: the reserved name of the per-engagement repo-context record.
# One active engagement-scoped instruction skill with this name describes the
# engagement's target repository/stack; it composes into every contract resolved
# for that engagement — no per-profile binding — and supersedes any host-repo
# description baked into the profile role text.
_REPO_CONTEXT_SKILL_NAME = "engagement-repo-context"


def _engagement_repo_context(session: Session, engagement_id: str | None) -> dict | None:
    """The engagement's repo-context skill, or ``None`` (system scope has none)."""
    if engagement_id is None:
        return None
    try:
        rows = skills.list_all(
            session, kind="instruction", status="active", scope=engagement_id
        )
    except Exception:
        # An engagement the scope resolver doesn't know (D-δ4 permits resolving
        # for any engagement id) simply has no repo context.
        return None
    for row in rows:
        if row.get("name") == _REPO_CONTEXT_SKILL_NAME:
            return row
    return None


def _bound_targets(session: Session, profile_id: str, relationship: str) -> list[str]:
    edges = references.list_references(
        session,
        source_type="agent_profile",
        source_id=profile_id,
        relationship_kind=relationship,
    )
    return [e["target_id"] for e in edges]


def resolve_contract(
    session: Session,
    profile_id: str,
    *,
    engagement_id: str | None = None,
    min_confidence: int = 1,
) -> dict:
    """Resolve ``profile_id`` → an effective contract for ``engagement_id``.

    Only **evidenced** learnings reach the contract: an active (area, tier)
    learning is injected iff its ``confidence`` is at least ``min_confidence``
    (default 1), so confidence-0 hunches — captured without supporting evidence
    — never pollute a runtime contract.

    Raises ``NotFoundError`` if the profile does not exist (via
    :func:`agent_profiles.get`).
    """
    profile = agent_profiles.get(session, profile_id)

    skill_records = [
        skills.get(session, sid)
        for sid in _bound_targets(session, profile_id, _HAS_SKILL)
    ]
    rule_records = [
        governance_rules.get(session, rid)
        for rid in _bound_targets(session, profile_id, _GOVERNED_BY)
    ]
    visible_skills = [s for s in skill_records if _visible(s, engagement_id)]
    visible_rules = _resolve_rule_overlay(
        [r for r in rule_records if _visible(r, engagement_id)]
    )

    instruction_skills = [s for s in visible_skills if s["kind"] == "instruction"]
    tool_skills = [s for s in visible_skills if s["kind"] == "tool"]
    advisory_rules = [r for r in visible_rules if r["enforcement"] == "advisory"]
    enforced_rules = [r for r in visible_rules if r["enforcement"] in _ENFORCED]

    # Composed system prompt: profile description + engagement repo context
    # (REQ-464) + instruction-skill text + advisory-rule bodies (the
    # pure-guidance half; PRD §4/§5).
    repo_context = _engagement_repo_context(session, engagement_id)
    prompt_parts = [profile["description"]]
    if repo_context is not None:
        prompt_parts.append(
            "ENGAGEMENT TARGET REPOSITORY — this contract is resolved for "
            f"{engagement_id}. The build runs against the repository described "
            "below; where the role text above describes a different codebase or "
            "technology stack, THIS section governs.\n\n"
            f"{repo_context['description']}"
        )
    prompt_parts += [s["description"] for s in instruction_skills]
    prompt_parts += [f"RULE (advisory): {r['body']}" for r in advisory_rules]
    system_prompt = "\n\n".join(p for p in prompt_parts if p)

    tools = [
        {
            "identifier": s["identifier"],
            "name": s["name"],
            "description": s.get("description"),
            "io_contract": s.get("io_contract"),
            "backing_callable": s.get("backing_callable"),
        }
        for s in tool_skills
    ]
    enforced_ruleset = [
        {
            "identifier": r["identifier"],
            "enforcement": r["enforcement"],
            "severity": r.get("severity"),
            "body": r["body"],
            "predicate": r.get("predicate"),
        }
        for r in enforced_rules
    ]

    contract = {
        "profile_id": profile["identifier"],
        "area": profile["area"],
        "tier": profile["tier"],
        "scope": profile["scope"],
        "engagement_id": engagement_id,
        "system_prompt": system_prompt,
        "tools": tools,
        "advisory_rules": [
            {"identifier": r["identifier"], "body": r["body"]} for r in advisory_rules
        ],
        "enforced_ruleset": enforced_ruleset,
        "active_learnings": _active_learnings(
            session, profile, engagement_id, min_confidence
        ),
    }
    stamped_skills = visible_skills + ([repo_context] if repo_context else [])
    contract["version_stamp"] = _version_stamp(profile, stamped_skills, visible_rules)
    return contract


def _active_learnings(
    session: Session,
    profile: dict,
    engagement_id: str | None,
    min_confidence: int = 1,
) -> list[dict]:
    """Inject the active (area, tier) learnings in scope (PRD §13.2 / D-δ4).

    Matched by the profile's area + tier (when the tier is a learning tier —
    orchestrator/pi_lead profiles carry none) and gated on evidence: a learning
    is injected only if its ``confidence >= min_confidence``, so confidence-0
    hunches are excluded by the default. A relevance-retrieval step at scale is
    an open question (PRD §10.6).
    """
    if profile["tier"] not in LEARNING_TIERS:
        return []
    candidates = learnings.list_all(
        session, area=profile["area"], tier=profile["tier"], status="active"
    )
    return [
        {
            "identifier": lrn["identifier"],
            "category": lrn["category"],
            "content": lrn["content"],
            "confidence": lrn["confidence"],
        }
        for lrn in candidates
        if lrn["confidence"] >= min_confidence
        and (lrn.get("engagement_id") is None or lrn.get("engagement_id") == engagement_id)
    ]


def _version_stamp(profile: dict, skill_records: list[dict], rule_records: list[dict]) -> str:
    """A deterministic stamp that changes when the profile or any bound item does."""
    material = {
        "profile": (profile["identifier"], str(profile.get("updated_at"))),
        "skills": sorted(
            (s["identifier"], s.get("version"), str(s.get("updated_at")))
            for s in skill_records
        ),
        "rules": sorted(
            (r["identifier"], r.get("version"), str(r.get("updated_at")))
            for r in rule_records
        ),
    }
    blob = json.dumps(material, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

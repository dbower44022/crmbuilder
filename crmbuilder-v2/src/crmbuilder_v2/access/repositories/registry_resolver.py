"""Agent Profile Registry resolver (PI-122 slice 2, D-δ4).

Compose an ``agent_profile`` identifier into a **runtime-ready effective
contract**:

```
Contract = { profile_id, area, tier, scope, system_prompt, tools,
             advisory_rules, enforced_ruleset, active_learnings, version_stamp }
```

The scope merge (D-δ2/D-δ4) keeps **system rows ∪ the active engagement's
overlay rows**: a bound skill/rule is included iff it is ``active`` and its scope
is ``system`` (``engagement_id IS NULL``) or the active engagement. Active
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
    references,
    skills,
)

_HAS_SKILL = "agent_profile_has_skill"
_GOVERNED_BY = "agent_profile_governed_by_rule"
_ENFORCED = {"enforced", "enforced_with_override"}


def _visible(record: dict, engagement_id: str | None) -> bool:
    """True if a registry record is in scope for ``engagement_id`` and active."""
    if record.get("status") != "active":
        return False
    row_engagement = record.get("engagement_id")
    return row_engagement is None or row_engagement == engagement_id


def _bound_targets(session: Session, profile_id: str, relationship: str) -> list[str]:
    edges = references.list_references(
        session,
        source_type="agent_profile",
        source_id=profile_id,
        relationship_kind=relationship,
    )
    return [e["target_id"] for e in edges]


def resolve_contract(
    session: Session, profile_id: str, *, engagement_id: str | None = None
) -> dict:
    """Resolve ``profile_id`` → an effective contract for ``engagement_id``.

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
    visible_rules = [r for r in rule_records if _visible(r, engagement_id)]

    instruction_skills = [s for s in visible_skills if s["kind"] == "instruction"]
    tool_skills = [s for s in visible_skills if s["kind"] == "tool"]
    advisory_rules = [r for r in visible_rules if r["enforcement"] == "advisory"]
    enforced_rules = [r for r in visible_rules if r["enforcement"] in _ENFORCED]

    # Composed system prompt: profile description + instruction-skill text +
    # advisory-rule bodies (the pure-guidance half; PRD §4/§5).
    prompt_parts = [profile["description"]]
    prompt_parts += [s["description"] for s in instruction_skills]
    prompt_parts += [f"RULE (advisory): {r['body']}" for r in advisory_rules]
    system_prompt = "\n\n".join(p for p in prompt_parts if p)

    tools = [
        {
            "identifier": s["identifier"],
            "name": s["name"],
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
        # Injected from slice 4 (the write-back lifecycle); empty until then.
        "active_learnings": [],
    }
    contract["version_stamp"] = _version_stamp(profile, visible_skills, visible_rules)
    return contract


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

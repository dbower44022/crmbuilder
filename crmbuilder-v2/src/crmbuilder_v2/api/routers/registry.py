"""Agent Profile Registry endpoints (PI-122 — the ADO §10 follow-on).

Three catalog entities (slice 1): agent_profile / skill / governance_rule. Each
gets the standard list / next-identifier / get / create (POST) / update (PATCH) /
delete set under the ``{data, meta, errors}`` envelope. The ``learning`` entity +
the binding edges + the resolver land in later slices.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.engagement_scope import get_active_engagement
from crmbuilder_v2.access.repositories import (
    agent_profiles,
    governance_rules,
    learnings,
    registry_lifecycle,
    registry_resolver,
    skills,
)
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    AgentProfileCreateIn,
    AgentProfileUpdateIn,
    CurateAreaIn,
    GovernanceRuleCreateIn,
    GovernanceRuleUpdateIn,
    LearningCaptureIn,
    LearningCreateIn,
    LearningEvidenceIn,
    LearningPromoteRuleIn,
    LearningPromoteSkillIn,
    LearningUpdateIn,
    SkillCreateIn,
    SkillUpdateIn,
)

# --------------------------------------------------------------------------
# agent_profiles
# --------------------------------------------------------------------------
agent_profiles_router = APIRouter(prefix="/agent-profiles", tags=["agent_profiles"])


@agent_profiles_router.get("")
def list_agent_profiles(
    area: str | None = None,
    tier: str | None = None,
    status: str | None = None,
    scope: str | None = None,
):
    with readonly_session() as s:
        return ok(agent_profiles.list_all(s, area=area, tier=tier, status=status, scope=scope))


@agent_profiles_router.get("/next-identifier")
def agent_profile_next_identifier():
    with readonly_session() as s:
        return ok({"next": agent_profiles.compute_next_identifier(s)})


@agent_profiles_router.get("/{identifier}/contract")
def resolve_agent_profile_contract(identifier: str, engagement: str | None = None):
    """Resolve the profile into an effective contract (D-δ4).

    The scope merge uses ``engagement`` when given, else the request's active
    engagement (the ``X-Engagement`` header); ``system`` rows are always
    included, engagement-overlay rows only for that engagement.
    """
    active = engagement if engagement is not None else get_active_engagement()
    with readonly_session() as s:
        return ok(registry_resolver.resolve_contract(s, identifier, engagement_id=active))


@agent_profiles_router.get("/{identifier}")
def get_agent_profile(identifier: str):
    with readonly_session() as s:
        return ok(agent_profiles.get(s, identifier))


@agent_profiles_router.post("", status_code=201)
def create_agent_profile(body: AgentProfileCreateIn):
    with writable_session() as s:
        return ok(agent_profiles.create(s, **body.model_dump()))


@agent_profiles_router.patch("/{identifier}")
def update_agent_profile(identifier: str, body: AgentProfileUpdateIn):
    provided = body.model_dump(exclude_unset=True)
    scope = provided.pop("scope", None)
    with writable_session() as s:
        return ok(agent_profiles.update(s, identifier, scope=scope, **provided))


@agent_profiles_router.delete("/{identifier}")
def delete_agent_profile(identifier: str):
    with writable_session() as s:
        return ok(agent_profiles.delete(s, identifier))


# --------------------------------------------------------------------------
# skills
# --------------------------------------------------------------------------
skills_router = APIRouter(prefix="/skills", tags=["skills"])


@skills_router.get("")
def list_skills(kind: str | None = None, status: str | None = None, scope: str | None = None):
    with readonly_session() as s:
        return ok(skills.list_all(s, kind=kind, status=status, scope=scope))


@skills_router.get("/next-identifier")
def skill_next_identifier():
    with readonly_session() as s:
        return ok({"next": skills.compute_next_identifier(s)})


@skills_router.get("/{identifier}")
def get_skill(identifier: str):
    with readonly_session() as s:
        return ok(skills.get(s, identifier))


@skills_router.post("", status_code=201)
def create_skill(body: SkillCreateIn):
    with writable_session() as s:
        return ok(skills.create(s, **body.model_dump()))


@skills_router.patch("/{identifier}")
def update_skill(identifier: str, body: SkillUpdateIn):
    provided = body.model_dump(exclude_unset=True)
    scope = provided.pop("scope", None)
    with writable_session() as s:
        return ok(skills.update(s, identifier, scope=scope, **provided))


@skills_router.delete("/{identifier}")
def delete_skill(identifier: str):
    with writable_session() as s:
        return ok(skills.delete(s, identifier))


# --------------------------------------------------------------------------
# governance_rules
# --------------------------------------------------------------------------
governance_rules_router = APIRouter(prefix="/governance-rules", tags=["governance_rules"])


@governance_rules_router.get("")
def list_governance_rules(
    enforcement: str | None = None, status: str | None = None, scope: str | None = None
):
    with readonly_session() as s:
        return ok(governance_rules.list_all(s, enforcement=enforcement, status=status, scope=scope))


@governance_rules_router.get("/next-identifier")
def governance_rule_next_identifier():
    with readonly_session() as s:
        return ok({"next": governance_rules.compute_next_identifier(s)})


@governance_rules_router.get("/{identifier}")
def get_governance_rule(identifier: str):
    with readonly_session() as s:
        return ok(governance_rules.get(s, identifier))


@governance_rules_router.post("", status_code=201)
def create_governance_rule(body: GovernanceRuleCreateIn):
    with writable_session() as s:
        return ok(governance_rules.create(s, **body.model_dump()))


@governance_rules_router.patch("/{identifier}")
def update_governance_rule(identifier: str, body: GovernanceRuleUpdateIn):
    provided = body.model_dump(exclude_unset=True)
    scope = provided.pop("scope", None)
    with writable_session() as s:
        return ok(governance_rules.update(s, identifier, scope=scope, **provided))


@governance_rules_router.delete("/{identifier}")
def delete_governance_rule(identifier: str):
    with writable_session() as s:
        return ok(governance_rules.delete(s, identifier))


# --------------------------------------------------------------------------
# learnings (PI-122 slice 3)
# --------------------------------------------------------------------------
learnings_router = APIRouter(prefix="/learnings", tags=["learnings"])


@learnings_router.get("")
def list_learnings(
    area: str | None = None,
    tier: str | None = None,
    category: str | None = None,
    status: str | None = None,
    scope: str | None = None,
):
    with readonly_session() as s:
        return ok(learnings.list_all(
            s, area=area, tier=tier, category=category, status=status, scope=scope
        ))


@learnings_router.get("/next-identifier")
def learning_next_identifier():
    with readonly_session() as s:
        return ok({"next": learnings.compute_next_identifier(s)})


@learnings_router.post("", status_code=201)
def create_learning(body: LearningCreateIn):
    with writable_session() as s:
        return ok(learnings.create(s, **body.model_dump()))


@learnings_router.post("/capture", status_code=201)
def capture_learning(body: LearningCaptureIn):
    with writable_session() as s:
        return ok(learnings.capture(s, **body.model_dump()))


@learnings_router.post("/curate")
def curate_learnings(body: CurateAreaIn):
    with writable_session() as s:
        return ok(registry_lifecycle.curate_area(s, area=body.area, scope=body.scope))


@learnings_router.get("/{identifier}")
def get_learning(identifier: str):
    with readonly_session() as s:
        return ok(learnings.get(s, identifier))


@learnings_router.post("/{identifier}/evidence")
def add_learning_evidence(identifier: str, body: LearningEvidenceIn):
    with writable_session() as s:
        return ok(learnings.add_evidence(s, identifier, **body.model_dump()))


@learnings_router.post("/{identifier}/promote-to-skill", status_code=201)
def promote_learning_to_skill(identifier: str, body: LearningPromoteSkillIn):
    with writable_session() as s:
        return ok(registry_lifecycle.promote_to_skill(s, identifier, **body.model_dump()))


@learnings_router.post("/{identifier}/promote-to-rule", status_code=201)
def promote_learning_to_rule(identifier: str, body: LearningPromoteRuleIn):
    with writable_session() as s:
        return ok(registry_lifecycle.promote_to_rule(s, identifier, **body.model_dump()))


@learnings_router.patch("/{identifier}")
def update_learning(identifier: str, body: LearningUpdateIn):
    provided = body.model_dump(exclude_unset=True)
    scope = provided.pop("scope", None)
    with writable_session() as s:
        return ok(learnings.update(s, identifier, scope=scope, **provided))


@learnings_router.delete("/{identifier}")
def delete_learning(identifier: str):
    with writable_session() as s:
        return ok(learnings.delete(s, identifier))

"""Planning-org registry profiles — PI-221 (PRJ-033), AL-7.

The three release-pipeline planning agents (Reconciliation / Architect Planning /
Release Lead) are seeded as durable, system-scoped registry rows; resolve_contract
reconstructs their composed contract; the runtime resolves them by (area, tier).
See release-pipeline-agent-layer-architecture.md §6.
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.models import AgentProfileRow
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.repositories import registry_resolver, registry_seed
from sqlalchemy import select

_PLANNING_CELLS = {("model", "architect"), ("planning", "architect"),
                   ("release", "pi_lead")}


def _profile(s, area, tier):
    return s.scalars(
        select(AgentProfileRow).where(
            AgentProfileRow.area == area, AgentProfileRow.tier == tier,
            AgentProfileRow.engagement_id.is_(None),
        )
    ).first()


def test_seed_creates_planning_org_profiles_with_bindings(v2_env):
    with session_scope() as s:
        registry_seed.seed_system_profiles(s)
        for area, tier in _PLANNING_CELLS:
            row = _profile(s, area, tier)
            assert row is not None, f"missing profile ({area}, {tier})"
            # bound skills + rules
            skills = gov.outbound_edges(
                s, source_type="agent_profile", source_id=row.identifier,
                relationship="agent_profile_has_skill", target_type="skill")
            rules = gov.outbound_edges(
                s, source_type="agent_profile", source_id=row.identifier,
                relationship="agent_profile_governed_by_rule",
                target_type="governance_rule")
            assert skills, f"({area},{tier}) has no skills"
            assert rules, f"({area},{tier}) has no rules"


def test_seed_is_idempotent(v2_env):
    with session_scope() as s:
        registry_seed.seed_system_profiles(s)
        first = s.scalars(select(AgentProfileRow)).all()
    with session_scope() as s:
        created = registry_seed.seed_system_profiles(s)
        assert created == []  # nothing new on re-run
        second = s.scalars(select(AgentProfileRow)).all()
    assert len(first) == len(second)


def test_resolve_contract_reconstructs_reconciliation_agent(v2_env):
    with session_scope() as s:
        registry_seed.seed_system_profiles(s)
        row = _profile(s, "model", "architect")
        contract = registry_resolver.resolve_contract(s, row.identifier)
    assert contract["area"] == "model" and contract["tier"] == "architect"
    # the proven system-prompt body + a bound tool + advisory rules are composed in
    assert "Reconciliation" in contract["system_prompt"]
    assert any("demand" in t["name"].lower() for t in contract["tools"])
    assert contract["advisory_rules"]  # AL-1/AL-2/RC-6 guidance


def test_runtime_resolves_system_prompt_from_registry(v2_env):
    from crmbuilder_v2.runtime import release_runtime as rr

    with session_scope() as s:
        registry_seed.seed_system_profiles(s)
    # resolves the seeded planning prompts; misses fall back to None
    assert "Reconciliation" in (rr._registry_system_prompt("model", "architect") or "")
    assert "Architect Planning" in (
        rr._registry_system_prompt("planning", "architect") or "")
    assert rr._registry_system_prompt("nope", "developer") is None

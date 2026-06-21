"""Per-(area, tier) agent profile catalog — PI-240 (PRJ-041 / REQ-286), Phase 3.

seed_system_profiles seeds the full catalog (target-model §4.12): the 9 System
build areas at Architect / Developer / Tester (27) + the 4 methodology areas at
Architect (4), plus the 3 release-level agents — 34 system profiles. Every cell
resolves a sensible contract; methodology areas are Architect-only; the seed is
idempotent.
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.models import AgentProfileRow
from crmbuilder_v2.access.repositories import registry_resolver, registry_seed
from crmbuilder_v2.access.repositories.registry_seed import (
    _BUILD_AREAS,
    _METHODOLOGY_AREAS,
)
from sqlalchemy import select


def _profile(s, area, tier):
    return s.scalars(
        select(AgentProfileRow).where(
            AgentProfileRow.area == area,
            AgentProfileRow.tier == tier,
            AgentProfileRow.engagement_id.is_(None),
        )
    ).first()


def test_catalog_covers_every_build_and_methodology_cell(v2_env):
    with session_scope() as s:
        registry_seed.seed_system_profiles(s)
        for area in _BUILD_AREAS:
            for tier in ("architect", "developer", "tester"):
                assert _profile(s, area, tier) is not None, f"missing ({area},{tier})"
        for area in _METHODOLOGY_AREAS:
            assert _profile(s, area, "architect") is not None, f"missing ({area})"
            # Methodology areas are Architect-only — no build tiers (DEC-368).
            assert _profile(s, area, "developer") is None
            assert _profile(s, area, "tester") is None


def test_every_catalog_cell_resolves_a_sensible_contract(v2_env):
    with session_scope() as s:
        registry_seed.seed_system_profiles(s)
        cells = (
            [(a, t) for a in _BUILD_AREAS
             for t in ("architect", "developer", "tester")]
            + [(a, "architect") for a in _METHODOLOGY_AREAS]
        )
        for area, tier in cells:
            prof = _profile(s, area, tier)
            contract = registry_resolver.resolve_contract(s, prof.identifier)
            assert contract["area"] == area and contract["tier"] == tier
            assert contract["system_prompt"].strip(), f"empty prompt ({area},{tier})"
            assert contract["version_stamp"]
            # every starter profile composes at least its advisory ruleset
            assert contract["advisory_rules"], f"no rules ({area},{tier})"


def test_build_developer_and_tester_carry_tools(v2_env):
    with session_scope() as s:
        registry_seed.seed_system_profiles(s)
        for area, tier in (("access", "developer"), ("api", "tester"),
                           ("ui", "developer")):
            prof = _profile(s, area, tier)
            contract = registry_resolver.resolve_contract(s, prof.identifier)
            assert contract["tools"], f"({area},{tier}) has no tools"
            assert any("/work-tasks/" in t["backing_callable"]
                       for t in contract["tools"])


def test_tester_rules_are_blind_verification(v2_env):
    with session_scope() as s:
        registry_seed.seed_system_profiles(s)
        prof = _profile(s, "access", "tester")
        contract = registry_resolver.resolve_contract(s, prof.identifier)
        text = " ".join(r["body"].lower() for r in contract["advisory_rules"])
        assert "blind" in text
        assert "bounce" in text or "do not fix" in text


def test_seed_is_idempotent(v2_env):
    with session_scope() as s:
        first = registry_seed.seed_system_profiles(s)
        assert len(first) == 34
    with session_scope() as s:
        assert registry_seed.seed_system_profiles(s) == []

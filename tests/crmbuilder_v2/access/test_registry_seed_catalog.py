"""Per-(area, tier) agent profile catalog — PI-240 (PRJ-041 / REQ-286), Phase 3.

seed_system_profiles seeds the full catalog (target-model §4.12): the 9 System
build areas at Architect / Developer / Tester (27) + the 4 methodology areas at
Architect + Tester (8, no Developer — DEC-764), plus the 3 release-level agents —
38 system profiles. Every cell resolves a sensible contract; the seed is
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
            # Architect + Tester now that content has a real Develop/Test (DEC-764).
            assert _profile(s, area, "architect") is not None, f"missing ({area},architect)"
            assert _profile(s, area, "tester") is not None, f"missing ({area},tester)"
            # No Developer tier — Design and Develop are one act for content.
            assert _profile(s, area, "developer") is None


def test_every_catalog_cell_resolves_a_sensible_contract(v2_env):
    with session_scope() as s:
        registry_seed.seed_system_profiles(s)
        cells = (
            [(a, t) for a in _BUILD_AREAS
             for t in ("architect", "developer", "tester")]
            + [(a, t) for a in _METHODOLOGY_AREAS
               for t in ("architect", "tester")]
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
        assert len(first) == 38
    with session_scope() as s:
        assert registry_seed.seed_system_profiles(s) == []


# --- real per-area content (REQ-386 / PI-346) -----------------------------


def test_seed_ships_real_area_specific_prompts_and_rules(v2_env):
    """A freshly seeded build-area profile carries a real area-specific prompt,
    its area governance rules, and a capability description — not a generic
    template (REQ-386)."""
    with session_scope() as s:
        registry_seed.seed_system_profiles(s)
        api_dev = _profile(s, "api", "developer")
        ui_dev = _profile(s, "ui", "developer")
        # Real, area-specific prompts that name the actual area, not a generic body.
        assert "API Developer" in api_dev.description
        assert "envelope" in api_dev.description
        assert "UI Developer" in ui_dev.description
        assert api_dev.description != ui_dev.description  # not the same template
        # Capability description populated (so agent search ranks them).
        assert api_dev.capability_description
        assert "fastapi routers" in api_dev.capability_description["specialties"]
        # Area governance rules resolved into the contract.
        contract = registry_resolver.resolve_contract(s, api_dev.identifier)
        bodies = " ".join(r["body"] for r in contract["advisory_rules"])
        assert "route" in bodies.lower()  # the api_route_ordering rule
        assert "envelope" in bodies.lower()  # the api_envelope rule


def test_bespoke_profiles_keep_prompt_but_gain_capability(v2_env):
    """model/planning/release keep their bespoke seed prompts and gain a
    capability description (description not overridden)."""
    with session_scope() as s:
        registry_seed.seed_system_profiles(s)
        release = _profile(s, "release", "pi_lead")
        assert release.capability_description
        assert "release pipeline" in release.capability_description["specialties"]

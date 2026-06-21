"""PI-232 / REQ-252 — the fleet resolves a contract for every build area.

REQ-252: the agent fleet has developer and architect profiles for the build areas
it must work in. **Since PI-240 (Phase 3) seeds the full per-(area, tier) catalog**,
every System build area resolves its OWN exact profile — the dispatcher's
tier-level fallback (``select_profile_id``) now only catches genuinely non-catalog
areas (e.g. per-engagement areas), which still resolve to a proven
area-parameterized profile (the storage cell, whose ``{AREA}`` is injected per
invocation). These tests pin both guarantees against the *actual* seeded profile
set, so a real fleet build never stalls on a missing profile.
"""

from __future__ import annotations

from crmbuilder_v2.access.repositories.registry_seed import _SEED_PROFILES
from crmbuilder_v2.scheduler.dispatcher import select_profile_id

# The system-profile view the resolver sees, derived from what the seeder
# actually creates (area, tier per cell) — not hand-maintained.
_SYSTEM = [
    {
        "identifier": f"AGP-{i:03d}",
        "scope": "system",
        "area": area,
        "tier": tier,
    }
    for i, (area, tier, *_rest) in enumerate(_SEED_PROFILES, start=1)
]

# The areas PRJ-037's build batch touches (desktop UI, data-access, service API).
_BUILD_AREAS = ("ui", "access", "api")


def test_seeder_provides_the_fallback_tiers():
    """The fallback only works if the seeder ships a developer and an architect
    profile (the area-parameterized proven prompts the non-catalog fallback uses)."""
    tiers = {tier for _area, tier, *_rest in _SEED_PROFILES}
    assert "developer" in tiers
    assert "architect" in tiers


def test_every_build_area_resolves_developer_and_architect():
    """REQ-252 acceptance: each build area resolves BOTH a developer and an
    architect contract, so the fleet never stalls on a missing profile."""
    for area in _BUILD_AREAS:
        assert select_profile_id(_SYSTEM, area, "developer") is not None, (
            f"no developer contract resolves for build area {area!r}"
        )
        assert select_profile_id(_SYSTEM, area, "architect") is not None, (
            f"no architect contract resolves for build area {area!r}"
        )


def test_catalog_build_area_resolves_its_own_profile():
    """PI-240: a System build area now resolves its OWN exact (area, tier)
    profile — no longer borrowing the storage cell."""
    by_cell = {(p["area"], p["tier"]): p["identifier"] for p in _SYSTEM}
    for area in _BUILD_AREAS:
        for tier in ("developer", "architect", "tester"):
            assert select_profile_id(_SYSTEM, area, tier) == by_cell[(area, tier)], (
                f"({area},{tier}) did not resolve to its own profile"
            )


def test_noncatalog_area_falls_back_to_the_proven_profile():
    """A genuinely unseeded area (e.g. a per-engagement area) has no per-area
    profile, so it falls back to a proven area-parameterized profile of the tier
    (the storage cell, first in seed order)."""
    by_cell = {(p["area"], p["tier"]): p["identifier"] for p in _SYSTEM}
    assert select_profile_id(_SYSTEM, "billing", "developer") == by_cell[("storage", "developer")]
    assert select_profile_id(_SYSTEM, "billing", "architect") == by_cell[("storage", "architect")]

"""PI-232 / REQ-252 — the fleet resolves a contract for every build area.

REQ-252: the agent fleet has developer and architect profiles for the build
areas it must work in. The mechanism is the dispatcher's tier-level fallback
(``select_profile_id``) to the **area-parameterized** proven profiles: there is
no per-area profile for ``ui`` / ``access`` / ``api``, but a request for any of
them at the developer or architect tier resolves to the proven storage-area
profile (whose ``{AREA}`` is injected per invocation). These tests pin that
guarantee against the *actual* seeded profile set, so a real fleet build never
stalls on a missing profile — and they break if the seeder ever drops the
developer or architect tier the fallback depends on.
"""

from __future__ import annotations

from crmbuilder_v2.access.repositories.registry_seed import _SEED_PROFILES
from crmbuilder_v2.runtime.dispatcher import select_profile_id

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
    profile (the area-parameterized proven prompts)."""
    tiers = {tier for _area, tier, *_rest in _SEED_PROFILES}
    assert "developer" in tiers
    assert "architect" in tiers


def test_every_build_area_resolves_developer_and_architect():
    """REQ-252 acceptance: each build area resolves BOTH a developer and an
    architect contract (exact or via the tier fallback), so the fleet never
    stalls on a missing profile."""
    for area in _BUILD_AREAS:
        assert select_profile_id(_SYSTEM, area, "developer") is not None, (
            f"no developer contract resolves for build area {area!r}"
        )
        assert select_profile_id(_SYSTEM, area, "architect") is not None, (
            f"no architect contract resolves for build area {area!r}"
        )


def test_unseeded_area_uses_the_parameterized_storage_profile():
    """The resolution for an unseeded area is the area-parameterized proven
    profile (storage cell), since no per-area profile exists for it."""
    by_cell = {(p["area"], p["tier"]): p["identifier"] for p in _SYSTEM}
    storage_dev = by_cell[("storage", "developer")]
    storage_arch = by_cell[("storage", "architect")]
    assert select_profile_id(_SYSTEM, "ui", "developer") == storage_dev
    assert select_profile_id(_SYSTEM, "ui", "architect") == storage_arch

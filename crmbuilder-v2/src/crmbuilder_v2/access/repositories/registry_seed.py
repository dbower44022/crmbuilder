"""Seed the proven ADO agent prompts as system agent profiles (PI-122 slice 6, D-δ3).

Two prompts were proven end-to-end before the registry existed and live under
``PRDs/product/crmbuilder-v2/agent-profile-registry/profiles/``. This seeds them
as **system-scoped** ``agent_profile`` rows on the (area × tier) axis so the
registry holds a real, proven artifact from day one. Idempotent: skips a
(area, tier, system) profile that already exists.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access.models import AgentProfileRow
from crmbuilder_v2.access.repositories import agent_profiles

# (area, tier, description) — descriptions point at the proven prompt files;
# the full prompt text is authored as the registry is populated for real.
_SEED_PROFILES: tuple[tuple[str, str, str], ...] = (
    (
        "storage",
        "architect",
        "Derived from the proven Development Phase Specialist prompt "
        "(agent-profile-registry/profiles/development-phase-specialist.md): the "
        "standing design-tier expert for a build area — scopes the phase's Work "
        "Tasks, sequences by layer rank, and reconciles against recorded "
        "Architecture decisions.",
    ),
    (
        "storage",
        "developer",
        "Derived from the proven Area Specialist prompt "
        "(agent-profile-registry/profiles/area-specialist.md): the per-Work-Task "
        "executor of a clean spec for a single area — claims a Work Task, "
        "implements it, and captures learnings at close.",
    ),
)


def seed_system_profiles(session: Session) -> list[dict]:
    """Create the proven system profiles that are missing. Returns the created rows."""
    created: list[dict] = []
    for area, tier, description in _SEED_PROFILES:
        exists = session.scalar(
            select(AgentProfileRow).where(
                AgentProfileRow.area == area,
                AgentProfileRow.tier == tier,
                AgentProfileRow.engagement_id.is_(None),
            )
        )
        if exists is not None:
            continue
        created.append(
            agent_profiles.create(
                session, area=area, tier=tier, description=description, scope="system"
            )
        )
    return created

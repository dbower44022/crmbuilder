"""Client Management vocabulary (PI-508 / REQ-591): the participant
lifecycle, the principal kinds and statuses, and the role set.

The five tables' CHECK constraints are literal SQL, not built from these
sets, so moving them here needs no migration. ``access.vocab`` re-exports
every name for the import paths that predate the package.
"""

from __future__ import annotations

# Methodology entity `participant` lifecycle (REL-040 / PI-094).
# A participant is the real engagement person/role a Persona is backed
# by; its lifecycle is a simple active/inactive toggle (no candidate /
# confirmed / rejected propose-verify gate — that governs the abstract
# Persona, not the concrete participant record).
PARTICIPANT_STATUSES: frozenset[str] = frozenset({"active", "inactive"})

PARTICIPANT_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "active": frozenset({"inactive"}),
    "inactive": frozenset({"active"}),
}

# ---------------------------------------------------------------------------
# Identity / authentication / RBAC (PI-γ — PRJ-019 / PI-127).
# ---------------------------------------------------------------------------

# A principal is an authenticated actor — a human user or an AI service agent.
PRINCIPAL_KINDS: frozenset[str] = frozenset({"human", "service_agent"})

PRINCIPAL_STATUSES: frozenset[str] = frozenset({"active", "disabled"})

# Roles are a small fixed set rather than a table (PI-γ D-γ3): three
# human-facing roles plus four agent-tier roles aligned to the ADO tiers. A
# ``role_assignment`` row's ``role`` is CHECK-constrained to this set.
RBAC_ROLES: frozenset[str] = frozenset(
    {
        "owner",
        "editor",
        "viewer",
        "orchestrator",
        "pi_lead",
        "phase_specialist",
        "area_specialist",
    }
)


# ---------------------------------------------------------------------------
# Client (PI-512 / REQ-589, DEC-1092): the organisation above the engagement.
# ---------------------------------------------------------------------------

CLIENT_STATUSES: frozenset[str] = frozenset({"active", "inactive"})

# A free toggle, as for participants: each value admits the other.
CLIENT_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "active": frozenset({"inactive"}),
    "inactive": frozenset({"active"}),
}

"""PI-γ slice 4 — change_log principal attribution + claim-identity guard."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access import change_log
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.models import ChangeLog
from crmbuilder_v2.access.principal_scope import (
    DEFAULT_OWNER,
    Principal,
    reset_active_principal,
    set_active_principal,
)
from sqlalchemy import select


def _emit_and_read(principal):
    token = set_active_principal(principal) if principal is not None else None
    try:
        with session_scope() as s:
            change_log.emit(
                s,
                entity_type="decision",
                entity_identifier="DEC-001",
                operation="insert",
                before=None,
                after={"x": 1},
            )
        with session_scope() as s:
            row = s.execute(
                select(ChangeLog).where(ChangeLog.entity_identifier == "DEC-001")
            ).scalars().first()
            return row.actor, row.principal_id
    finally:
        if token is not None:
            reset_active_principal(token)


def test_attribution_for_service_agent(v2_env):
    agent = Principal(
        principal_id="PRN-007",
        kind="service_agent",
        roles=frozenset({"area_specialist"}),
        roles_by_engagement={"ENG-001": frozenset({"area_specialist"})},
        allowed_engagements=frozenset({"ENG-001"}),
    )
    actor, principal_id = _emit_and_read(agent)
    assert actor == "service_agent"
    assert principal_id == "PRN-007"


def test_attribution_for_human(v2_env):
    human = Principal(
        principal_id="PRN-003",
        kind="human",
        roles=frozenset({"editor"}),
        roles_by_engagement={"ENG-001": frozenset({"editor"})},
        allowed_engagements=frozenset({"ENG-001"}),
    )
    actor, principal_id = _emit_and_read(human)
    assert actor == "user"
    assert principal_id == "PRN-003"


def test_attribution_default_owner_is_unchanged(v2_env):
    # The synthetic default-owner (auth off) must not change attribution.
    actor, principal_id = _emit_and_read(DEFAULT_OWNER)
    assert actor == "claude_session"
    assert principal_id is None


def test_attribution_no_principal_is_unchanged(v2_env):
    actor, principal_id = _emit_and_read(None)
    assert actor == "claude_session"
    assert principal_id is None


# --------------------------------------------------------------------------
# claim-identity guard
# --------------------------------------------------------------------------
def test_enforce_claim_identity(monkeypatch):
    from crmbuilder_v2.access import rbac
    from crmbuilder_v2.api import principal_deps

    class _S:
        principal_auth_enabled = True

    monkeypatch.setattr(principal_deps, "get_settings", lambda: _S())

    agent = Principal(principal_id="PRN-009", kind="service_agent")
    token = set_active_principal(agent)
    try:
        # Claiming as itself: allowed.
        principal_deps.enforce_claim_identity("PRN-009")
        # Claiming as someone else: denied.
        with pytest.raises(rbac.PermissionDenied):
            principal_deps.enforce_claim_identity("PRN-010")
        # Owner may claim on anyone's behalf.
        reset_active_principal(token)
        otok = set_active_principal(DEFAULT_OWNER)
        principal_deps.enforce_claim_identity("PRN-999")
        reset_active_principal(otok)
    finally:
        pass


def test_enforce_claim_identity_noop_when_auth_off(monkeypatch):
    from crmbuilder_v2.api import principal_deps

    class _S:
        principal_auth_enabled = False

    monkeypatch.setattr(principal_deps, "get_settings", lambda: _S())
    # No active principal, auth off → passes.
    principal_deps.enforce_claim_identity("anyone")

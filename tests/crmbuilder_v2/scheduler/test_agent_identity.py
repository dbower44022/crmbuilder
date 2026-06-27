"""Per-agent service-agent principal minting at spawn (REQ-381 / PI-340).

When ``principal_auth_enabled`` is on, the runtime mints each spawned agent its
own service-agent principal + bearer token, injects the token into the agent's
API calls, has the agent claim its Work Task as that principal, and revokes the
token when the run ends. When auth is off, everything is a no-op and the spawn
path is unchanged.
"""

from __future__ import annotations

from crmbuilder_v2.access import principal as P
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.config import get_settings
from crmbuilder_v2.scheduler import agent_identity
from crmbuilder_v2.scheduler.coordinating_scheduler import operating_protocol


def _enable_auth(monkeypatch):
    # Flip only the flag on the cached settings singleton, leaving DB config
    # (which session_scope reads) intact; monkeypatch reverts it after the test.
    monkeypatch.setattr(get_settings(), "principal_auth_enabled", True)


# --- operating_protocol injection (pure) ----------------------------------


def _proto(**kw):
    base = {
        "work_task_id": "WTK-001", "area": "api", "api_base": "http://127.0.0.1:8765",
        "engagement": "ENG-001", "branch": "ado/wtk-001",
    }
    base.update(kw)
    return operating_protocol(**base)


def test_operating_protocol_without_identity_is_unchanged():
    text = _proto()
    assert "Authorization: Bearer" not in text
    assert '"claimed_by": "AGP-runtime"' in text


def test_operating_protocol_injects_bearer_and_claims_as_principal():
    text = _proto(agent_token="crmbv2_secrettoken", agent_principal_id="PRN-042")
    assert "Authorization: Bearer crmbv2_secrettoken" in text
    assert '"claimed_by": "PRN-042"' in text
    assert '"claimed_by": "AGP-runtime"' not in text


# --- mint_for_spawn -------------------------------------------------------


def test_mint_for_spawn_noop_when_auth_off(v2_env):
    # Default settings have auth off → no identity, no rows.
    assert agent_identity.mint_for_spawn(
        "ENG-001", area="api", tier="developer", work_task_id="WTK-001"
    ) is None


def test_mint_for_spawn_mints_and_token_validates(v2_env, monkeypatch):
    _enable_auth(monkeypatch)
    identity = agent_identity.mint_for_spawn(
        "ENG-001", area="api", tier="developer", work_task_id="WTK-001"
    )
    assert identity is not None
    assert identity.principal_id.startswith("PRN-")
    assert identity.token.startswith("crmbv2_")
    assert identity.token_id.startswith("TOK-")

    # The token resolves to a service-agent principal carrying its area/tier.
    with session_scope() as s:
        resolved = P.validate_token(s, identity.token)
        assert resolved is not None
        assert resolved.principal_id == identity.principal_id
        row = P.get_principal(s, identity.principal_id)
        assert row.kind == "service_agent"
        assert row.agent_area == "api"
        assert row.agent_tier == "developer"


def test_revoke_after_run_invalidates_the_token(v2_env, monkeypatch):
    _enable_auth(monkeypatch)
    identity = agent_identity.mint_for_spawn(
        "ENG-001", area="api", tier="developer", work_task_id="WTK-002"
    )
    assert identity is not None
    # Valid before revoke...
    with session_scope() as s:
        assert P.validate_token(s, identity.token) is not None
    agent_identity.revoke("ENG-001", identity.token_id)
    # ...and rejected after.
    with session_scope() as s:
        assert P.validate_token(s, identity.token) is None


def test_revoke_is_noop_for_missing_token():
    # No token id (auth was off) — must not raise.
    agent_identity.revoke("ENG-001", None)

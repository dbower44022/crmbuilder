"""PI-γ — principal / api_token / role_assignment + RBAC access-layer tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from crmbuilder_v2.access import principal as P
from crmbuilder_v2.access import rbac
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.principal_scope import (
    DEFAULT_OWNER,
    Principal,
)


# v2_env seeds ENG-001, the engagement role assignments FK against.


def test_create_principal_assigns_identifier(v2_env):
    with session_scope() as s:
        row = P.create_principal(
            s, kind="human", display_name="Doug", identity="doug@x.com"
        )
        assert row.principal_id == "PRN-001"
        assert row.status == "active"


def test_create_principal_rejects_bad_kind(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        P.create_principal(s, kind="robot", display_name="x", identity="y")


def test_mint_validate_token_round_trip(v2_env):
    with session_scope() as s:
        owner = P.create_principal(
            s, kind="human", display_name="Doug", identity="doug@x.com"
        )
        P.assign_role(
            s, principal_id=owner.principal_id, engagement_id="ENG-001", role="owner"
        )
        minted = P.mint_token(s, principal_id=owner.principal_id, label="cli")
        assert minted.plaintext.startswith("crmbv2_")
        resolved = P.validate_token(s, minted.plaintext)
        assert resolved is not None
        assert resolved.principal_id == owner.principal_id
        assert resolved.is_owner
        assert resolved.all_engagements
        # last_used_at stamped.
        tok = P.list_tokens(s, principal_id=owner.principal_id)[0]
        assert tok.last_used_at is not None


def test_validate_token_rejects_unknown_revoked_expired_disabled(v2_env):
    with session_scope() as s:
        p = P.create_principal(
            s, kind="human", display_name="A", identity="a@x.com"
        )
        P.assign_role(
            s, principal_id=p.principal_id, engagement_id="ENG-001", role="editor"
        )
        assert P.validate_token(s, "bogus") is None

        live = P.mint_token(s, principal_id=p.principal_id)
        assert P.validate_token(s, live.plaintext) is not None
        P.revoke_token(s, live.token_id)
        assert P.validate_token(s, live.plaintext) is None

        expired = P.mint_token(
            s,
            principal_id=p.principal_id,
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        assert P.validate_token(s, expired.plaintext) is None

        ok = P.mint_token(s, principal_id=p.principal_id)
        assert P.validate_token(s, ok.plaintext) is not None
        P.disable_principal(s, p.principal_id)
        assert P.validate_token(s, ok.plaintext) is None


def test_assign_role_is_idempotent_and_validates(v2_env):
    with session_scope() as s:
        p = P.create_principal(
            s, kind="human", display_name="A", identity="a@x.com"
        )
        a1 = P.assign_role(
            s, principal_id=p.principal_id, engagement_id="ENG-001", role="viewer"
        )
        a2 = P.assign_role(
            s, principal_id=p.principal_id, engagement_id="ENG-001", role="viewer"
        )
        assert a1.role_assignment_id == a2.role_assignment_id
        with pytest.raises(UnprocessableError):
            P.assign_role(
                s,
                principal_id=p.principal_id,
                engagement_id="ENG-001",
                role="superuser",
            )


def test_build_principal_roles_by_engagement(v2_env):
    with session_scope() as s:
        # A second engagement to spread assignments across.
        from crmbuilder_v2.access.models import EngagementRow

        s.add(
            EngagementRow(
                engagement_identifier="ENG-002",
                engagement_code="BRAVO",
                engagement_name="Bravo",
                engagement_purpose="p",
                engagement_status="active",
            )
        )
        s.flush()
        p = P.create_principal(
            s, kind="human", display_name="A", identity="a@x.com"
        )
        P.assign_role(
            s, principal_id=p.principal_id, engagement_id="ENG-001", role="editor"
        )
        P.assign_role(
            s, principal_id=p.principal_id, engagement_id="ENG-002", role="viewer"
        )
        tok = P.mint_token(s, principal_id=p.principal_id)
        pr = P.validate_token(s, tok.plaintext)
        assert pr.allowed_engagements == frozenset({"ENG-001", "ENG-002"})
        assert pr.is_engagement_allowed("ENG-001")
        assert not pr.is_engagement_allowed("ENG-999")
        assert not pr.all_engagements  # no owner role anywhere


def test_mint_agent_principal_is_engagement_scoped(v2_env):
    with session_scope() as s:
        agent_row, minted = P.mint_agent_principal(
            s,
            engagement_id="ENG-001",
            role="area_specialist",
            agent_tier="area",
            agent_area="storage",
        )
        assert agent_row.kind == "service_agent"
        assert agent_row.agent_area == "storage"
        pr = P.validate_token(s, minted.plaintext)
        assert pr.kind == "service_agent"
        assert pr.is_engagement_allowed("ENG-001")
        assert not pr.is_engagement_allowed("ENG-002")
        assert not pr.is_owner


def test_get_or_create_owner_is_idempotent(v2_env):
    with session_scope() as s:
        a = P.get_or_create_owner(s, identity="doug@x.com", display_name="Doug")
        b = P.get_or_create_owner(s, identity="doug@x.com")
        assert a.principal_id == b.principal_id


# --------------------------------------------------------------------------
# RBAC
# --------------------------------------------------------------------------
def _auth(monkeypatch, enabled: bool):
    class _S:
        principal_auth_enabled = enabled

    monkeypatch.setattr(rbac, "get_settings", lambda: _S())


def test_rbac_check_noop_when_auth_off(monkeypatch):
    _auth(monkeypatch, False)
    # No active principal, auth off → passes.
    rbac.check("admin", engagement_id="ENG-001")


def test_rbac_check_enforces_when_auth_on(monkeypatch):
    _auth(monkeypatch, True)
    viewer = Principal(
        principal_id="PRN-009",
        kind="human",
        roles=frozenset({"viewer"}),
        roles_by_engagement={"ENG-001": frozenset({"viewer"})},
        allowed_engagements=frozenset({"ENG-001"}),
    )
    rbac.check("read", engagement_id="ENG-001", principal=viewer)
    with pytest.raises(rbac.PermissionDenied):
        rbac.check("create", engagement_id="ENG-001", principal=viewer)
    # Owner passes everything everywhere.
    rbac.check("admin", engagement_id="ENG-001", principal=DEFAULT_OWNER)
    rbac.check("admin", engagement_id="ENG-777", principal=DEFAULT_OWNER)


def test_rbac_check_denies_anonymous_when_auth_on(monkeypatch):
    _auth(monkeypatch, True)
    with pytest.raises(rbac.PermissionDenied):
        rbac.check("read", engagement_id="ENG-001", principal=None)

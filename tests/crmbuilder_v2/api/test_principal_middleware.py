"""PI-γ slice 2 — principal-resolution + bearer middleware tests.

Auth is off by default (a synthetic default-owner), so the rest of the suite is
unaffected; these tests flip ``principal_auth_enabled`` on via a monkeypatched
settings stub to exercise the bearer-required path.
"""

from __future__ import annotations

from crmbuilder_v2.access import principal as P
from crmbuilder_v2.access import rbac
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.api import principal_middleware, scope_middleware

# Uses the shared ``client`` fixture from api/conftest.py (a TestClient with a
# default X-Engagement: ENG-001 header bound to a fresh per-test DB).


class _Settings:
    def __init__(self, on: bool) -> None:
        self.principal_auth_enabled = on
        # The scope middleware also reads engagement_scoping_enabled.
        self.engagement_scoping_enabled = True


def _enable_auth(monkeypatch, on: bool):
    # Patch every module whose get_settings gates an auth/scope decision: the
    # principal middleware (resolve), the scope middleware (engagement-selection
    # check), and the rbac guard.
    stub = lambda: _Settings(on)  # noqa: E731
    monkeypatch.setattr(principal_middleware, "get_settings", stub)
    monkeypatch.setattr(scope_middleware, "get_settings", stub)
    monkeypatch.setattr(rbac, "get_settings", stub)


def test_auth_off_sets_default_owner(v2_env):
    # resolve_principal with auth off yields the default owner regardless of token.
    pr = principal_middleware.resolve_principal(None)
    assert pr is not None
    assert pr.is_owner and pr.all_engagements


def test_auth_on_rejects_missing_token(monkeypatch, client):
    _enable_auth(monkeypatch, True)
    resp = client.get("/charter")
    assert resp.status_code == 401
    body = resp.json()
    assert body["errors"][0]["code"] == "unauthenticated"


def test_auth_on_allows_public_paths_without_token(monkeypatch, client):
    _enable_auth(monkeypatch, True)
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200


def test_auth_on_accepts_valid_bearer(monkeypatch, client):
    _enable_auth(monkeypatch, True)
    with session_scope() as s:
        owner = P.create_principal(
            s, kind="human", display_name="Doug", identity="doug@x.com"
        )
        P.assign_role(
            s, principal_id=owner.principal_id, engagement_id="ENG-001", role="owner"
        )
        minted = P.mint_token(s, principal_id=owner.principal_id)
    resp = client.get(
        "/charter", headers={"Authorization": f"Bearer {minted.plaintext}"}
    )
    # Past auth: a valid bearer never yields 401 (200/404 depending on data).
    assert resp.status_code != 401


def test_auth_on_rejects_bogus_bearer(monkeypatch, client):
    _enable_auth(monkeypatch, True)
    resp = client.get("/charter", headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401


# --------------------------------------------------------------------------
# Slice 3 — engagement-selection enforcement (D5-final)
# --------------------------------------------------------------------------
def _seed_engagement(code: str, identifier: str) -> None:
    from crmbuilder_v2.access.models import EngagementRow

    with session_scope() as s:
        s.add(
            EngagementRow(
                engagement_identifier=identifier,
                engagement_code=code,
                engagement_name=code,
                engagement_purpose="p",
                engagement_status="active",
            )
        )


def test_engagement_selection_rejected_for_unassigned(monkeypatch, client):
    _enable_auth(monkeypatch, True)
    _seed_engagement("BRAVO", "ENG-002")
    with session_scope() as s:
        p = P.create_principal(
            s, kind="human", display_name="A", identity="a@x.com"
        )
        P.assign_role(
            s, principal_id=p.principal_id, engagement_id="ENG-001", role="editor"
        )
        minted = P.mint_token(s, principal_id=p.principal_id)
    auth = {"Authorization": f"Bearer {minted.plaintext}"}
    # Allowed engagement: past the engagement gate (not 403/401).
    ok = client.get("/charter", headers={**auth, "X-Engagement": "ENG-001"})
    assert ok.status_code not in (401, 403)
    # Unassigned engagement: 403 engagement_forbidden.
    bad = client.get("/charter", headers={**auth, "X-Engagement": "ENG-002"})
    assert bad.status_code == 403
    assert bad.json()["errors"][0]["code"] == "engagement_forbidden"


def test_require_permission_dependency(monkeypatch):
    """The require_permission dependency raises PermissionDenied per the active
    principal/engagement, and is a no-op when auth is off."""
    from crmbuilder_v2.access import engagement_scope, principal_scope
    from crmbuilder_v2.api.principal_deps import require_permission

    _enable_auth(monkeypatch, True)
    viewer = principal_scope.Principal(
        principal_id="PRN-050",
        kind="human",
        roles=frozenset({"viewer"}),
        roles_by_engagement={"ENG-001": frozenset({"viewer"})},
        allowed_engagements=frozenset({"ENG-001"}),
    )
    ptok = principal_scope.set_active_principal(viewer)
    etok = engagement_scope.set_active_engagement("ENG-001")
    try:
        require_permission("read")()  # viewer can read
        with __import__("pytest").raises(rbac.PermissionDenied):
            require_permission("create")()
    finally:
        engagement_scope.reset_active_engagement(etok)
        principal_scope.reset_active_principal(ptok)

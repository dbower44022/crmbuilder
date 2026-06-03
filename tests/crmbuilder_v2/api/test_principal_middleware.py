"""PI-γ slice 2 — principal-resolution + bearer middleware tests.

Auth is off by default (a synthetic default-owner), so the rest of the suite is
unaffected; these tests flip ``principal_auth_enabled`` on via a monkeypatched
settings stub to exercise the bearer-required path.
"""

from __future__ import annotations

from crmbuilder_v2.access import principal as P
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.api import principal_middleware

# Uses the shared ``client`` fixture from api/conftest.py (a TestClient with a
# default X-Engagement: ENG-001 header bound to a fresh per-test DB).


class _Settings:
    def __init__(self, on: bool) -> None:
        self.principal_auth_enabled = on


def _enable_auth(monkeypatch, on: bool):
    monkeypatch.setattr(
        principal_middleware, "get_settings", lambda: _Settings(on)
    )


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

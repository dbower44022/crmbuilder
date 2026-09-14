"""PI-γ slices 5-6 — /admin principals/tokens/agents endpoints.

Auth is off by default, so require_permission("admin") is a no-op and the
localhost flow can provision the first owner + token. The owner-gating path is
exercised by flipping auth on with a viewer token.
"""

from __future__ import annotations

from crmbuilder_v2.access import principal as P
from crmbuilder_v2.access import rbac
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.api import principal_middleware, scope_middleware


class _Settings:
    def __init__(self, on: bool) -> None:
        self.principal_auth_enabled = on
        self.engagement_scoping_enabled = True


def _enable_auth(monkeypatch, on: bool):
    stub = lambda: _Settings(on)  # noqa: E731
    monkeypatch.setattr(principal_middleware, "get_settings", stub)
    monkeypatch.setattr(scope_middleware, "get_settings", stub)
    monkeypatch.setattr(rbac, "get_settings", stub)


def test_provision_owner_and_token_auth_off(client):
    # Create an owner principal, assign a role, mint a token — all without auth.
    resp = client.post(
        "/admin/principals",
        json={"kind": "human", "display_name": "Doug", "identity": "doug@x.com"},
    )
    assert resp.status_code == 201, resp.text
    pid = resp.json()["data"]["principal_id"]

    resp = client.post(
        f"/admin/principals/{pid}/roles",
        json={"engagement_id": "ENG-001", "role": "owner"},
    )
    assert resp.status_code == 201, resp.text

    resp = client.post("/admin/tokens", json={"principal_id": pid, "label": "cli"})
    assert resp.status_code == 201, resp.text
    body = resp.json()["data"]
    assert body["token"].startswith("crmbv2_")
    token_id = body["token_id"]

    # Token is listed.
    listed = client.get("/admin/tokens").json()["data"]
    assert any(t["token_id"] == token_id for t in listed)

    # Revoke it.
    assert client.delete(f"/admin/tokens/{token_id}").status_code == 200
    revoked = client.get("/admin/tokens").json()["data"]
    assert next(t for t in revoked if t["token_id"] == token_id)["revoked_at"]


def test_mint_agent_endpoint(client):
    resp = client.post(
        "/admin/agents",
        json={
            "engagement_id": "ENG-001",
            "role": "area_specialist",
            "agent_tier": "area",
            "agent_area": "storage",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["principal"]["kind"] == "service_agent"
    assert data["principal"]["agent_area"] == "storage"
    assert data["token"].startswith("crmbv2_")


def test_admin_is_owner_gated_when_auth_on(monkeypatch, client):
    _enable_auth(monkeypatch, True)
    with session_scope() as s:
        viewer = P.create_principal(
            s, kind="human", display_name="V", identity="v@x.com"
        )
        P.assign_role(
            s, principal_id=viewer.principal_id, engagement_id="ENG-001", role="viewer"
        )
        vtok = P.mint_token(s, principal_id=viewer.principal_id)
        owner = P.create_principal(
            s, kind="human", display_name="O", identity="o@x.com"
        )
        P.assign_role(
            s, principal_id=owner.principal_id, engagement_id="ENG-001", role="owner"
        )
        otok = P.mint_token(s, principal_id=owner.principal_id)

    # Viewer is denied the admin surface.
    r = client.get(
        "/admin/principals",
        headers={"Authorization": f"Bearer {vtok.plaintext}"},
    )
    assert r.status_code == 403

    # Owner is allowed.
    r = client.get(
        "/admin/principals",
        headers={"Authorization": f"Bearer {otok.plaintext}"},
    )
    assert r.status_code == 200


def test_mcp_server_forwards_bearer_token(monkeypatch):
    import httpx
    from crmbuilder_v2.config import Settings
    from crmbuilder_v2.mcp_server import server as server_module

    captured = {}
    real = httpx.AsyncClient

    def _fake(*args, **kwargs):
        captured["headers"] = kwargs.get("headers")
        return real(base_url="http://testserver")

    monkeypatch.setattr(
        server_module,
        "get_settings",
        lambda: Settings(mcp_token="crmbv2_abc", mcp_engagement="CRMBUILDER"),
    )
    monkeypatch.setattr(server_module.httpx, "AsyncClient", _fake)
    server_module.build_server()
    assert captured["headers"]["Authorization"] == "Bearer crmbv2_abc"
    assert captured["headers"]["X-Engagement"] == "CRMBUILDER"

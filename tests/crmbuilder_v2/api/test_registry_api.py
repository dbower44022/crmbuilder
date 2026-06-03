"""PI-122 slice 1 — Agent Profile Registry REST endpoints."""

from __future__ import annotations

# Uses the shared ``client`` fixture (TestClient with X-Engagement: ENG-001).


def test_agent_profile_crud(client):
    resp = client.post(
        "/agent-profiles",
        json={"area": "storage", "tier": "architect", "description": "Storage architect."},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()["data"]
    assert body["identifier"] == "AGP-001"
    assert body["scope"] == "system"

    assert client.get("/agent-profiles/AGP-001").json()["data"]["tier"] == "architect"
    assert client.get("/agent-profiles/next-identifier").json()["data"]["next"] == "AGP-002"

    patched = client.patch("/agent-profiles/AGP-001", json={"status": "retired"})
    assert patched.json()["data"]["status"] == "retired"

    listed = client.get("/agent-profiles?status=retired").json()["data"]
    assert [p["identifier"] for p in listed] == ["AGP-001"]

    assert client.delete("/agent-profiles/AGP-001").status_code == 200
    assert client.get("/agent-profiles/AGP-001").status_code == 404


def test_skill_and_rule_create(client):
    s = client.post(
        "/skills",
        json={"name": "diff", "kind": "tool", "description": "compute a diff",
              "io_contract": {"type": "object"}},
    )
    assert s.status_code == 201
    assert s.json()["data"]["identifier"] == "SKL-001"

    r = client.post(
        "/governance-rules",
        json={"body": "prefer additive replanning", "enforcement": "advisory"},
    )
    assert r.status_code == 201
    assert r.json()["data"]["enforcement"] == "advisory"


def test_engagement_scope_overlay(client):
    resp = client.post(
        "/agent-profiles",
        json={"area": "api", "tier": "developer", "description": "API dev (overlay).",
              "scope": "ENG-001"},
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["scope"] == "ENG-001"
    # Filter by engagement scope.
    listed = client.get("/agent-profiles?scope=ENG-001").json()["data"]
    assert all(p["scope"] == "ENG-001" for p in listed)


def test_bad_vocab_is_422(client):
    resp = client.post(
        "/skills", json={"name": "x", "kind": "bogus", "description": "y"}
    )
    assert resp.status_code == 422

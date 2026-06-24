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


def test_agent_profile_capability_description_round_trips(client):
    # PI-301 (DEC-677): the searchable capability object round-trips via the API.
    cap = {
        "summary": "Builds PySide6 desktop panels.",
        "specialties": ["forms", "tables"],
        "builds": ["dialogs"],
        "constraints": ["never raw QMessageBox"],
    }
    resp = client.post(
        "/agent-profiles",
        json={
            "area": "ui", "tier": "developer", "description": "Qt UI dev.",
            "capability_description": cap,
        },
    )
    assert resp.status_code == 201, resp.text
    identifier = resp.json()["data"]["identifier"]
    assert resp.json()["data"]["capability_description"] == cap
    assert client.get(
        f"/agent-profiles/{identifier}"
    ).json()["data"]["capability_description"] == cap

    # Omitted on create → null; settable via PATCH.
    bare = client.post(
        "/agent-profiles",
        json={"area": "ui", "tier": "developer", "description": "No cap doc."},
    ).json()["data"]
    assert bare["capability_description"] is None
    patched = client.patch(
        f"/agent-profiles/{bare['identifier']}",
        json={"capability_description": cap},
    )
    assert patched.json()["data"]["capability_description"] == cap


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


def test_agent_profile_bindings(client):
    profile = client.post(
        "/agent-profiles",
        json={"area": "api", "tier": "developer", "description": "API dev."},
    )
    assert profile.status_code == 201, profile.text
    profile_id = profile.json()["data"]["identifier"]

    skill = client.post(
        "/skills",
        json={"name": "diff", "kind": "tool", "description": "compute a diff",
              "io_contract": {"type": "object"}},
    )
    assert skill.status_code == 201, skill.text
    skill_id = skill.json()["data"]["identifier"]

    rule = client.post(
        "/governance-rules",
        json={"body": "prefer additive replanning", "enforcement": "advisory"},
    )
    assert rule.status_code == 201, rule.text
    rule_id = rule.json()["data"]["identifier"]

    assert client.post("/references", json={
        "source_type": "agent_profile", "source_id": profile_id,
        "target_type": "skill", "target_id": skill_id,
        "relationship": "agent_profile_has_skill",
    }).status_code == 201
    assert client.post("/references", json={
        "source_type": "agent_profile", "source_id": profile_id,
        "target_type": "governance_rule", "target_id": rule_id,
        "relationship": "agent_profile_governed_by_rule",
    }).status_code == 201

    resp = client.get(f"/agent-profiles/{profile_id}/bindings")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert [s["identifier"] for s in data["skills"]] == [skill_id]
    assert data["skills"][0]["relationship"] == "agent_profile_has_skill"
    assert [r["identifier"] for r in data["governance_rules"]] == [rule_id]
    assert data["governance_rules"][0]["relationship"] == "agent_profile_governed_by_rule"


def test_agent_profile_bindings_unknown_is_404(client):
    assert client.get("/agent-profiles/AGP-999/bindings").status_code == 404


def test_bad_vocab_is_422(client):
    resp = client.post(
        "/skills", json={"name": "x", "kind": "bogus", "description": "y"}
    )
    assert resp.status_code == 422

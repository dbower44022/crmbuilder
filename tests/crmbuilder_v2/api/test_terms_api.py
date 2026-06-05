"""PI-061 — glossary term REST endpoints (/terms).

Uses the shared ``client`` fixture (TestClient with X-Engagement: ENG-001) and a
fresh per-test database, so ``term`` is created by ``create_all`` and the
change_log / refs CHECKs include it.
"""

from __future__ import annotations


def test_term_crud(client):
    resp = client.post(
        "/terms",
        json={
            "name": "Engagement",
            "definition": "A defined unit of work applying the process for one client.",
            "usage_scope": "Used throughout the Master CRMBuilder PRD.",
            "examples": "The CRMBUILDER dogfood engagement.",
            "distinguishing_notes": "Not the same as a Client.",
            "related_terms": "Client, Session",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()["data"]
    assert body["identifier"] == "TERM-001"
    assert body["scope"] == "system"
    assert body["status"] == "active"
    assert body["version"] == 1
    assert body["usage_scope"].startswith("Used throughout")

    assert client.get("/terms/TERM-001").json()["data"]["name"] == "Engagement"
    assert client.get("/terms/next-identifier").json()["data"]["next"] == "TERM-002"

    patched = client.patch("/terms/TERM-001", json={"status": "draft", "version": 2})
    assert patched.json()["data"]["status"] == "draft"
    assert patched.json()["data"]["version"] == 2

    listed = client.get("/terms?status=draft").json()["data"]
    assert [t["identifier"] for t in listed] == ["TERM-001"]

    assert client.delete("/terms/TERM-001").status_code == 200
    assert client.get("/terms/TERM-001").status_code == 404


def test_term_explicit_identifier(client):
    resp = client.post(
        "/terms",
        json={"identifier": "TERM-005", "name": "Client", "definition": "An organization."},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["identifier"] == "TERM-005"
    # A duplicate explicit identifier is a conflict.
    dup = client.post(
        "/terms",
        json={"identifier": "TERM-005", "name": "Client2", "definition": "x"},
    )
    assert dup.status_code == 409, dup.text


def test_term_list_sorted_by_name(client):
    client.post("/terms", json={"name": "Skill", "definition": "guidance file."})
    client.post("/terms", json={"name": "Engagement", "definition": "a unit of work."})
    client.post("/terms", json={"name": "Client", "definition": "an organization."})
    names = [t["name"] for t in client.get("/terms").json()["data"]]
    assert names == ["Client", "Engagement", "Skill"]


def test_term_system_vs_engagement_scope(client):
    # A default term is system-scoped (visible to every engagement).
    sys_term = client.post(
        "/terms", json={"name": "Agent", "definition": "A spawned worker."}
    ).json()["data"]
    assert sys_term["scope"] == "system"

    # An engagement overlay is visible only under that engagement's scope filter.
    overlay = client.post(
        "/terms",
        json={"name": "Pass", "definition": "One sweep across areas.", "scope": "ENG-001"},
    ).json()["data"]
    assert overlay["scope"] == "ENG-001"

    eng_only = client.get("/terms?scope=ENG-001").json()["data"]
    assert [t["identifier"] for t in eng_only] == [overlay["identifier"]]

    system_only = client.get("/terms?scope=system").json()["data"]
    assert sys_term["identifier"] in [t["identifier"] for t in system_only]
    assert overlay["identifier"] not in [t["identifier"] for t in system_only]


def test_term_bad_status_is_422(client):
    resp = client.post(
        "/terms", json={"name": "x", "definition": "y", "status": "bogus"}
    )
    assert resp.status_code == 422, resp.text


def test_term_unknown_scope_is_400(client):
    resp = client.post(
        "/terms", json={"name": "x", "definition": "y", "scope": "ENG-999"}
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["errors"][0]["field"] == "scope"

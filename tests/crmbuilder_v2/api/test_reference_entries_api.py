"""Reference Entry REST endpoint tests — REL-016 / PI-063 (REQ-398).

Covers the /reference-entries surface: create with server-assigned identifier,
list (+ kind/scope filters), get, patch (incl. content revalidation), delete,
the system|engagement scope, and per-kind content validation errors.
"""

from __future__ import annotations

_DK = {"body": "How this domain works."}


def _make(client, **overrides) -> dict:
    body = {
        "name": overrides.pop("name", "Nonprofit Mentoring Organization"),
        "kind": overrides.pop("kind", "domain_knowledge"),
        "content": overrides.pop("content", _DK),
    }
    body.update(overrides)
    r = client.post("/reference-entries", json=body)
    assert r.status_code == 201, r.text
    return r.json()["data"]


def test_post_creates_with_server_assigned_identifier(client):
    rec = _make(client)
    assert rec["identifier"] == "RFE-001"
    assert rec["kind"] == "domain_knowledge"
    assert rec["scope"] == "system"
    assert rec["status"] == "active"


def test_next_identifier(client):
    _make(client)
    r = client.get("/reference-entries/next-identifier")
    assert r.status_code == 200
    assert r.json()["data"]["next"] == "RFE-002"


def test_get_and_list_with_filters(client):
    _make(client, name="A", kind="domain_knowledge")
    _make(
        client,
        name="OrgB",
        kind="organization_structure",
        content={
            "typical_entities": ["Grant"],
            "typical_relationships": ["A Grant is awarded to a Grantee"],
        },
    )
    assert len(client.get("/reference-entries").json()["data"]) == 2
    dk = client.get("/reference-entries?kind=domain_knowledge").json()["data"]
    assert [r["name"] for r in dk] == ["A"]
    single = client.get("/reference-entries/RFE-001")
    assert single.status_code == 200
    assert single.json()["data"]["name"] == "A"


def test_get_missing_returns_404(client):
    r = client.get("/reference-entries/RFE-404")
    assert r.status_code == 404
    assert r.json()["errors"][0]["code"] == "not_found"


def test_domain_knowledge_requires_body_422(client):
    r = client.post(
        "/reference-entries",
        json={"name": "A", "kind": "domain_knowledge", "content": {"x": 1}},
    )
    assert r.status_code == 422


def test_invalid_kind_422(client):
    r = client.post(
        "/reference-entries",
        json={"name": "A", "kind": "bogus", "content": _DK},
    )
    assert r.status_code == 422


def test_organization_structure_valid_and_invalid(client):
    ok = client.post(
        "/reference-entries",
        json={
            "name": "Org",
            "kind": "organization_structure",
            "content": {
                "typical_entities": ["Grant"],
                "typical_relationships": ["A Grant is awarded to a Grantee"],
            },
        },
    )
    assert ok.status_code == 201, ok.text
    bad = client.post(
        "/reference-entries",
        json={
            "name": "OrgBad",
            "kind": "organization_structure",
            "content": {"typical_entities": []},
        },
    )
    assert bad.status_code == 422


def test_inventory_items_valid_and_invalid(client):
    ok = client.post(
        "/reference-entries",
        json={
            "name": "Inv",
            "kind": "inventory_items",
            "content": {"entities": ["Grant"], "personas": [], "processes": []},
        },
    )
    assert ok.status_code == 201, ok.text
    bad = client.post(
        "/reference-entries",
        json={
            "name": "InvBad",
            "kind": "inventory_items",
            "content": {"entities": [], "personas": [], "processes": []},
        },
    )
    assert bad.status_code == 422


def test_engagement_scope_and_filter(client):
    _make(client, name="Sys", scope="system")
    _make(client, name="Eng", scope="ENG-001")
    sys_only = client.get("/reference-entries?scope=system").json()["data"]
    assert "Eng" not in {r["name"] for r in sys_only}
    eng = client.get("/reference-entries?scope=ENG-001").json()["data"]
    assert {r["name"] for r in eng} == {"Eng"}


def test_patch_updates_and_revalidates_content(client):
    _make(client, name="A")
    ok = client.patch("/reference-entries/RFE-001", json={"name": "A2"})
    assert ok.status_code == 200
    assert ok.json()["data"]["name"] == "A2"
    bad = client.patch("/reference-entries/RFE-001", json={"content": {"no": "body"}})
    assert bad.status_code == 422


def test_delete(client):
    _make(client, name="A")
    assert client.delete("/reference-entries/RFE-001").status_code == 200
    assert client.get("/reference-entries/RFE-001").status_code == 404


# --- contextual loader (PI-066 / REQ-401) ---


def test_search_by_q(client):
    _make(
        client,
        name="Mentoring",
        content={"body": "x"},
        trigger_keywords=["mentoring", "mentor"],
        applies_to="nonprofit mentoring",
    )
    _make(
        client,
        name="Foundation",
        content={"body": "x"},
        trigger_keywords=["grantmaking"],
        applies_to="charitable foundation",
    )
    r = client.get("/reference-entries/search?q=we run a mentoring program")
    assert r.status_code == 200, r.text
    names = {e["name"] for e in r.json()["data"]}
    assert names == {"Mentoring"}


def test_search_keywords_and_kind(client):
    _make(
        client,
        name="Mentoring",
        content={"body": "x"},
        trigger_keywords=["mentoring"],
    )
    _make(
        client,
        name="MentorOrg",
        kind="organization_structure",
        content={
            "typical_entities": ["Mentor"],
            "typical_relationships": [],
        },
        trigger_keywords=["mentoring"],
    )
    both = client.get("/reference-entries/search?keywords=mentoring").json()["data"]
    assert {e["name"] for e in both} == {"Mentoring", "MentorOrg"}
    dk = client.get(
        "/reference-entries/search?keywords=mentoring&kind=domain_knowledge"
    ).json()["data"]
    assert {e["name"] for e in dk} == {"Mentoring"}


def test_search_route_not_shadowed_by_identifier(client):
    """`/search` resolves to the loader, not the get-by-identifier route."""
    r = client.get("/reference-entries/search")
    assert r.status_code == 200
    assert isinstance(r.json()["data"], list)

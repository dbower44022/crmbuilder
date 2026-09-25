"""Application REST endpoint tests (PI-575 / REQ-653, DEC-1183): the two
application attributes on ``/engagements`` bodies and responses, and the
``/applications`` routes that serve the same rows under the model's name.

``v2_env`` seeds ``ENG-001`` with no client: it stands in for an engagement
that is not an application."""

from __future__ import annotations


def _identifiers(body: dict) -> set[str]:
    return {e["engagement_identifier"] for e in _ok(body)}


def _ok(body: dict) -> dict:
    assert body["errors"] is None
    return body["data"]


def _make_client(client, name: str) -> str:
    r = client.post("/clients", json={"client_name": name})
    assert r.status_code == 201, r.text
    return _ok(r.json())["client_identifier"]


def _make_engagement(client, identifier: str, code: str, **extra) -> dict:
    r = client.post(
        "/engagements",
        json={
            "engagement_identifier": identifier,
            "engagement_code": code,
            "engagement_name": f"Engagement {code}",
            "engagement_purpose": "p",
            **extra,
        },
    )
    assert r.status_code == 201, r.text
    return _ok(r.json())


def test_engagement_bodies_and_responses_carry_the_attributes(client):
    a = _make_client(client, "Cleveland Business Mentors")
    # Default visibility is private; no client unless named.
    plain = _make_engagement(client, "ENG-002", "ALPHA")
    assert plain["engagement_visibility"] == "private"
    assert plain["engagement_defining_client"] is None
    assert plain["engagement_defining_client_name"] is None

    # Create with both attributes.
    made = _make_engagement(
        client,
        "ENG-003",
        "BETA",
        engagement_visibility="public",
        engagement_defining_client=a,
    )
    assert made["engagement_visibility"] == "public"
    assert made["engagement_defining_client"] == a
    assert made["engagement_defining_client_name"] == "Cleveland Business Mentors"
    holding = _ok(client.get("/engagements/ENG-003/clients").json())
    assert holding["primary"] == a

    # The list and the single fetch carry them.
    listed = {e["engagement_identifier"]: e for e in _ok(client.get("/engagements").json())}
    assert listed["ENG-003"]["engagement_defining_client"] == a
    assert listed["ENG-002"]["engagement_defining_client"] is None
    got = _ok(client.get("/engagements/ENG-003").json())
    assert got["engagement_visibility"] == "public"

    # Replace without the attributes leaves them unchanged (existing callers).
    r = client.put(
        "/engagements/ENG-003",
        json={
            "engagement_name": "Renamed",
            "engagement_purpose": "p",
            "engagement_status": "active",
        },
    )
    replaced = _ok(r.json())
    assert replaced["engagement_name"] == "Renamed"
    assert replaced["engagement_visibility"] == "public"
    assert replaced["engagement_defining_client"] == a

    # Replace and patch change them.
    r = client.put(
        "/engagements/ENG-003",
        json={
            "engagement_name": "Renamed",
            "engagement_purpose": "p",
            "engagement_status": "active",
            "engagement_visibility": "private",
        },
    )
    assert _ok(r.json())["engagement_visibility"] == "private"
    b = _make_client(client, "CRMBuilder")
    r = client.patch("/engagements/ENG-002", json={"engagement_defining_client": b})
    patched = _ok(r.json())
    assert patched["engagement_defining_client"] == b
    assert patched["engagement_defining_client_name"] == "CRMBuilder"
    r = client.patch("/engagements/ENG-002", json={"engagement_visibility": "public"})
    assert _ok(r.json())["engagement_visibility"] == "public"


def test_missing_client_is_refused_with_the_envelope(client):
    r = client.post(
        "/engagements",
        json={
            "engagement_code": "ALPHA",
            "engagement_name": "Alpha",
            "engagement_purpose": "p",
            "engagement_defining_client": "CLI-404",
        },
    )
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["data"] is None
    assert [(e["field"], e["code"]) for e in body["errors"]] == [
        ("engagement_defining_client", "client_not_found")
    ]
    assert _identifiers(client.get("/engagements").json()) == {"ENG-001"}

    r = client.post(
        "/applications",
        json={
            "engagement_code": "ALPHA",
            "engagement_name": "Alpha",
            "engagement_purpose": "p",
            "engagement_defining_client": "CLI-404",
        },
    )
    assert r.status_code == 422
    assert r.json()["errors"][0]["code"] == "client_not_found"
    assert _identifiers(client.get("/engagements").json()) == {"ENG-001"}

    # A bad visibility is refused the same way.
    r = client.post(
        "/engagements",
        json={
            "engagement_code": "ALPHA",
            "engagement_name": "Alpha",
            "engagement_purpose": "p",
            "engagement_visibility": "secret",
        },
    )
    assert r.status_code == 422
    assert r.json()["errors"][0]["field"] == "engagement_visibility"


def test_applications_alias_serves_the_same_rows(client):
    a = _make_client(client, "Cleveland Business Mentors")
    b = _make_client(client, "CRMBuilder")
    _make_engagement(client, "ENG-002", "NOCLIENT")

    # The application create requires the client.
    r = client.post(
        "/applications",
        json={
            "engagement_code": "ALPHA",
            "engagement_name": "Alpha",
            "engagement_purpose": "p",
        },
    )
    assert r.status_code == 422
    r = client.post(
        "/applications",
        json={
            "engagement_identifier": "ENG-003",
            "engagement_code": "ALPHA",
            "engagement_name": "Alpha",
            "engagement_purpose": "p",
            "engagement_defining_client": a,
        },
    )
    assert r.status_code == 201, r.text
    made = _ok(r.json())
    assert made["engagement_identifier"] == "ENG-003"
    assert made["engagement_visibility"] == "private"
    assert made["engagement_defining_client"] == a

    # Same row on both paths, same shape.
    assert _ok(client.get("/applications/ENG-003").json()) == _ok(
        client.get("/engagements/ENG-003").json()
    )

    # The engagement no client holds lists as an engagement, not an application.
    assert _identifiers(client.get("/engagements").json()) == {
        "ENG-001",
        "ENG-002",
        "ENG-003",
    }
    assert [e["engagement_identifier"] for e in _ok(client.get("/applications").json())] == [
        "ENG-003"
    ]
    r = client.get("/applications/ENG-002")
    assert r.status_code == 422
    assert r.json()["errors"][0]["code"] == "no_defining_client"
    assert client.get("/applications/ENG-404").status_code == 404

    # Applications of one client.
    r = client.post(
        "/applications",
        json={
            "engagement_identifier": "ENG-004",
            "engagement_code": "BETA",
            "engagement_name": "Beta",
            "engagement_purpose": "p",
            "engagement_defining_client": b,
            "engagement_visibility": "public",
        },
    )
    assert r.status_code == 201, r.text
    assert [
        e["engagement_identifier"]
        for e in _ok(client.get("/applications", params={"client": a}).json())
    ] == ["ENG-003"]
    assert [
        e["engagement_identifier"]
        for e in _ok(client.get("/applications", params={"client": b}).json())
    ] == ["ENG-004"]
    assert client.get("/applications", params={"client": "CLI-404"}).status_code == 404

    # Replace requires both attributes; patch takes either.
    r = client.put(
        "/applications/ENG-004",
        json={
            "engagement_name": "Beta",
            "engagement_purpose": "p",
            "engagement_status": "active",
        },
    )
    assert r.status_code == 422
    r = client.put(
        "/applications/ENG-004",
        json={
            "engagement_name": "Beta",
            "engagement_purpose": "p",
            "engagement_status": "active",
            "engagement_defining_client": a,
            "engagement_visibility": "private",
        },
    )
    replaced = _ok(r.json())
    assert replaced["engagement_defining_client"] == a
    assert replaced["engagement_visibility"] == "private"
    r = client.patch("/applications/ENG-004", json={"engagement_visibility": "public"})
    assert _ok(r.json())["engagement_visibility"] == "public"
    r = client.patch("/applications/ENG-004", json={"engagement_defining_client": None})
    assert r.status_code == 422
    assert r.json()["errors"][0]["code"] == "missing_or_empty"

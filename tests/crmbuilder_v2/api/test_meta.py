"""Meta endpoints — root and OpenAPI."""

from __future__ import annotations


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "crmbuilder-v2"
    assert body["version"] == "0.1.0"


def test_openapi(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    body = r.json()
    assert body["info"]["title"] == "CRMBuilder v2 — Storage System"
    paths = body["paths"]
    # spot-check that each entity surface is present
    for expected in ("/charter", "/decisions", "/sessions", "/references"):
        assert expected in paths, f"missing {expected}"

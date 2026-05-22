"""Meta endpoints — root and OpenAPI."""

from __future__ import annotations

import crmbuilder_v2


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "crmbuilder-v2"
    # Assert against the live package version rather than a hardcoded
    # string so the test survives version bumps (the root endpoint renders
    # ``crmbuilder_v2.__version__``).
    assert body["version"] == crmbuilder_v2.__version__


def test_openapi(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    body = r.json()
    assert body["info"]["title"] == "CRMBuilder v2 — Storage System"
    paths = body["paths"]
    # spot-check that each entity surface is present
    for expected in ("/charter", "/decisions", "/sessions", "/references"):
        assert expected in paths, f"missing {expected}"

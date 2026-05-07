"""Health endpoint — liveness probe used by the UI's lifecycle (DEC-023)."""

from __future__ import annotations


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["data"] == {"ok": True}
    assert body["errors"] is None

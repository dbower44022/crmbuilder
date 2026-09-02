"""Conformance evaluation + override endpoints — PI-410 (REQ-493/494)."""

from __future__ import annotations


def _instance(client, name="chapter"):
    r = client.post("/instances", json={
        "instance_name": name,
        "instance_url": f"https://{name}.example.org",
        "instance_role": "both",
    })
    assert r.status_code == 201, r.text
    return r.json()["data"]["instance_identifier"]


def test_conformance_evaluates_and_404s_unknown_instances(client):
    iid = _instance(client)
    r = client.get(f"/instances/{iid}/conformance")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["instance"] == iid
    assert data["status"] in {
        "conformant", "drifted", "unable_to_be_checked",
        "named_but_unwritable",
    }
    assert client.get("/instances/INST-999/conformance").status_code == 404


def test_override_lifecycle_over_http(client):
    iid = _instance(client)
    r = client.post(
        f"/instances/{iid}/conformance-overrides",
        json={"authorized_by": "Doug", "reason": "hotfix deploy"},
    )
    assert r.status_code == 201, r.text
    listed = client.get(f"/instances/{iid}/conformance-overrides").json()["data"]
    assert len(listed) == 1 and listed[0]["consumed_at"] is None

    spent = client.post(f"/instances/{iid}/conformance-overrides/consume")
    assert spent.status_code == 200, spent.text
    assert spent.json()["data"]["consumed_at"] is not None
    # Single deploy: a second consume finds nothing.
    assert (
        client.post(f"/instances/{iid}/conformance-overrides/consume")
        .status_code
        == 404
    )

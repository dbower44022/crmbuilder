"""API test — POST /planning-items/{id}/decompose (ADO structural step, WTK-002)."""

from __future__ import annotations

_EXEC = "Decompose-route test executive summary, comfortably above the floor. " * 4


def _make_pi(client, identifier="PI-810", title="Ship it"):
    r = client.post(
        "/planning-items",
        json={
            "identifier": identifier,
            "title": title,
            "item_type": "pending_work",
            "status": "Draft",
            "executive_summary": _EXEC,
        },
    )
    assert r.status_code == 201, r.text
    return identifier


def test_decompose_route_creates_six_workstreams(client):
    pid = _make_pi(client)
    r = client.post(f"/planning-items/{pid}/decompose")
    assert r.status_code == 201, r.text
    created = r.json()["data"]
    assert [w["workstream_phase_type"] for w in created] == [
        "Architecture", "Development", "Testing", "Documentation",
        "Data Migration", "Deployment",
    ]
    assert all(w["workstream_status"] == "Planned" for w in created)

    # The blocked_by chain is queryable through the references endpoint.
    refs = client.get(
        "/references",
        params={"source_type": "workstream", "target_type": "workstream",
                "relationship_kind": "blocked_by"},
    ).json()["data"]
    assert len(refs) == 5


def test_decompose_route_is_once_only(client):
    pid = _make_pi(client, identifier="PI-811")
    assert client.post(f"/planning-items/{pid}/decompose").status_code == 201
    assert client.post(f"/planning-items/{pid}/decompose").status_code == 409


def test_decompose_route_unknown_pi_404(client):
    assert client.post("/planning-items/PI-998/decompose").status_code == 404

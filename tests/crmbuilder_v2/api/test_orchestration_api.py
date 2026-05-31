"""Orchestration ready-batches endpoint (PI-079)."""

from __future__ import annotations


_EXEC_SUMMARY = (
    "This planning item reconciles stale test fixtures with the current "
    "governance schema so the suite validates real behavior; it carries no "
    "production code change and exists purely to keep the regression net "
    "aligned with the PI-073 and PI-102 data-model decisions now in effect."
)


def _mk(client, ident, **extra):
    body = {
        "identifier": ident,
        "title": ident,
        "item_type": "pending_work",
        "status": "Open",
        "executive_summary": _EXEC_SUMMARY,
    }
    body.update(extra)
    r = client.post("/planning-items", json=body)
    assert r.status_code == 201, r.json()


def test_ready_batches_envelope_and_shape(client):
    _mk(client, "PI-001", area=["api"])
    _mk(client, "PI-002", area=["ui"])
    client.post("/planning-items/PI-002/claim", json={"claimant": "CONV-5"})

    r = client.get("/orchestration/ready-batches")
    assert r.status_code == 200, r.json()
    data = r.json()["data"]
    assert set(data) == {"batches", "cyclic", "warnings"}
    items = {i["identifier"]: i for b in data["batches"] for i in b["items"]}
    assert items["PI-001"]["area"] == ["api"]
    assert items["PI-002"]["claimed_by"] == "CONV-5"


def test_ready_batches_area_filter(client):
    _mk(client, "PI-001", area=["api"])
    _mk(client, "PI-002", area=["ui"])
    r = client.get("/orchestration/ready-batches", params={"area": ["api"]})
    assert r.status_code == 200, r.json()
    ids = [i["identifier"] for b in r.json()["data"]["batches"] for i in b["items"]]
    assert ids == ["PI-001"]


def test_ready_batches_unknown_area_returns_400(client):
    r = client.get("/orchestration/ready-batches", params={"area": ["nope"]})
    assert r.status_code == 400, r.json()


def test_ready_batches_max_depth_param_accepted(client):
    _mk(client, "PI-001")
    r = client.get("/orchestration/ready-batches", params={"max_depth": 0})
    assert r.status_code == 200, r.json()

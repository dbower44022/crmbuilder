"""API tests — POST /workstreams/{id}/scope + GET prior-phase-outputs (WTK-003)."""

from __future__ import annotations

_EXEC = "Scope-route test executive summary, comfortably above the floor. " * 4


def _decompose(client, pid="PI-830"):
    r = client.post(
        "/planning-items",
        json={"identifier": pid, "title": "Deliver", "item_type": "pending_work",
              "status": "Draft", "executive_summary": _EXEC},
    )
    assert r.status_code == 201, r.text
    created = client.post(f"/planning-items/{pid}/decompose").json()["data"]
    return [w["workstream_identifier"] for w in created]


def test_scope_route_creates_work_tasks_and_readies(client):
    ids = _decompose(client)
    r = client.post(
        f"/workstreams/{ids[1]}/scope",  # Development
        json={"work_tasks": [
            {"title": "storage layer", "area": "storage"},
            {"title": "access layer", "area": "access"},
        ]},
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["workstream"]["workstream_status"] == "Ready"
    assert len(data["work_tasks"]) == 2


def test_scope_route_empty_is_not_applicable(client):
    ids = _decompose(client, pid="PI-831")
    r = client.post(f"/workstreams/{ids[4]}/scope", json={"work_tasks": []})
    assert r.status_code == 201, r.text
    assert r.json()["data"]["workstream"]["workstream_status"] == "Not Applicable"


def test_scope_route_rescope_conflicts(client):
    ids = _decompose(client, pid="PI-832")
    assert client.post(
        f"/workstreams/{ids[0]}/scope",
        json={"work_tasks": [{"title": "t", "area": "access"}]},
    ).status_code == 201
    assert client.post(
        f"/workstreams/{ids[0]}/scope",
        json={"work_tasks": [{"title": "t2", "area": "api"}]},
    ).status_code == 409


def test_prior_phase_outputs_route(client):
    ids = _decompose(client, pid="PI-833")
    client.post(
        f"/workstreams/{ids[0]}/scope",
        json={"work_tasks": [{"title": "Add entity", "area": "methodology-product"}]},
    )
    ctx = client.get(f"/workstreams/{ids[1]}/prior-phase-outputs").json()["data"]
    assert [p["phase_type"] for p in ctx["prior_phases"]] == ["Architecture"]
    assert ctx["prior_phases"][0]["work_tasks"][0]["work_task_title"] == "Add entity"

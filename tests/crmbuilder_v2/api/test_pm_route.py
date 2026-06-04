"""API tests — Project Manager substrate (WTK-006) + a full-org capstone.

The capstone walks every ADO tier over the REST API: the PM dispatches an
eligible PI; the Lead decomposes it, the phase specialists scope it, and the
phases execute through the serial gate; the PI is resolved; and the PM then sees
the downstream PI (previously blocked_by it) become eligible and dispatches it.
"""

from __future__ import annotations

_EXEC = "ADO PM route test executive summary, comfortably above the floor. " * 4


def _data(r):
    assert r.status_code in (200, 201), r.text
    return r.json()["data"]


def _project(client, ident="PRJ-910"):
    assert client.post("/projects", json={
        "project_identifier": ident, "project_name": "Engagement",
        "project_purpose": "p", "project_description": "d",
        "project_status": "planned",
    }).status_code == 201
    return ident


def _pi(client, ident, project_id, blocked_by=None):
    assert client.post("/planning-items", json={
        "identifier": ident, "title": f"PI {ident}", "item_type": "pending_work",
        "status": "Draft", "executive_summary": _EXEC,
    }).status_code == 201
    client.post("/references", json={
        "source_type": "planning_item", "source_id": ident,
        "target_type": "project", "target_id": project_id,
        "relationship": "planning_item_belongs_to_project"})
    for b in blocked_by or []:
        client.post("/references", json={
            "source_type": "planning_item", "source_id": ident,
            "target_type": "planning_item", "target_id": b,
            "relationship": "blocked_by"})
    return ident


def test_backlog_and_eligibility(client):
    pid = _project(client, "PRJ-911")
    _pi(client, "PI-970", pid)
    _pi(client, "PI-971", pid, blocked_by=["PI-970"])
    b = _data(client.get(f"/projects/{pid}/backlog"))
    assert b["eligible"] == ["PI-970"]
    assert b["blocked"] == ["PI-971"]
    elig = [i["identifier"] for i in _data(client.get(f"/projects/{pid}/eligible-planning-items"))]
    assert elig == ["PI-970"]


def test_dispatch_route_and_block(client):
    pid = _project(client, "PRJ-912")
    _pi(client, "PI-980", pid)
    _pi(client, "PI-981", pid, blocked_by=["PI-980"])
    assert client.post("/planning-items/PI-980/dispatch").status_code == 201
    assert _data(client.get("/planning-items/PI-980"))["status"] == "In Progress"
    # PI-981 is still blocked by the un-Resolved PI-980.
    assert client.post("/planning-items/PI-981/dispatch").status_code == 409


def _drive_pi_through_lead(client, pid):
    """Decompose -> scope every phase -> execute every phase via the gate."""
    created = _data(client.post(f"/planning-items/{pid}/decompose"))
    phases = {w["workstream_phase_type"]: w["workstream_identifier"] for w in created}
    for ph, wid in phases.items():
        client.post(f"/workstreams/{wid}/scope",
                    json={"work_tasks": [{"title": f"{ph} task", "area": "access"}]})
    ordered = ["Design", "Develop", "Test"]
    for ph in ordered:
        wid = phases[ph]
        started = _data(client.post(f"/workstreams/{wid}/start-execution"))
        for wt in started["readied_work_tasks"]:
            wtid = wt["work_task_identifier"]
            client.post(f"/work-tasks/{wtid}/claim", json={"claimed_by": "area-specialist"})
            for st in ("Claimed", "In Progress", "Complete"):
                client.patch(f"/work-tasks/{wtid}", json={"work_task_status": st})
        client.post(f"/workstreams/{wid}/complete-phase")


def test_full_org_capstone(client):
    pid = _project(client, "PRJ-913")
    a = _pi(client, "PI-990", pid)
    b = _pi(client, "PI-991", pid, blocked_by=["PI-990"])

    # PM: only PI-990 is eligible; dispatch it to a Lead.
    assert _data(client.get(f"/projects/{pid}/backlog"))["eligible"] == [a]
    assert client.post(f"/planning-items/{a}/dispatch").status_code == 201

    # Lead + phase specialists + area specialists drive PI-990 to all-terminal.
    _drive_pi_through_lead(client, a)
    assert _data(client.get(f"/planning-items/{a}/phase-overview"))["all_terminal"] is True

    # Resolve PI-990 (the Lead's close-out resolves edge; simulated via status).
    client.patch(f"/planning-items/{a}", json={"status": "Resolved"})

    # PM: the downstream PI-991 is now unblocked and dispatchable.
    backlog = _data(client.get(f"/projects/{pid}/backlog"))
    assert a in backlog["resolved"]
    assert b in backlog["eligible"]
    assert client.post(f"/planning-items/{b}/dispatch").status_code == 201

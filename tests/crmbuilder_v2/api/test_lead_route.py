"""API tests — PI Lead substrate (WTK-005): phase-overview + start/complete phase.

Includes a Lead-DRIVEN end-to-end (contrast test_ado_end_to_end.py, which drives
execution by hand): the gate exposes the next executable phase, start-execution
readies its Work Tasks, and complete-phase advances only when they are all done.
"""

from __future__ import annotations

_EXEC = "PI Lead route test executive summary, comfortably above the floor. " * 4


def _data(r):
    assert r.status_code in (200, 201), r.text
    return r.json()["data"]


def _scoped_pi(client, pid="PI-860"):
    assert client.post(
        "/planning-items",
        json={"identifier": pid, "title": "Deliver", "item_type": "pending_work",
              "status": "Draft", "executive_summary": _EXEC},
    ).status_code == 201
    created = _data(client.post(f"/planning-items/{pid}/decompose"))
    phases = {w["workstream_phase_type"]: w["workstream_identifier"] for w in created}
    for ph, wid in phases.items():
        client.post(f"/workstreams/{wid}/scope",
                    json={"work_tasks": [{"title": f"{ph} task", "area": "access"}]})
    return pid, phases


def test_phase_overview_gate(client):
    pid, phases = _scoped_pi(client, pid="PI-861")
    ov = _data(client.get(f"/planning-items/{pid}/phase-overview"))
    assert ov["all_scoped"] is True
    assert ov["all_terminal"] is False
    assert ov["next_executable"] == phases["Design"]


def test_start_execution_blocked_returns_409(client):
    pid, phases = _scoped_pi(client, pid="PI-862")
    # Develop is blocked_by Design (not yet terminal).
    assert client.post(f"/workstreams/{phases['Develop']}/start-execution").status_code == 409


def test_complete_phase_requires_tasks_complete(client):
    pid, phases = _scoped_pi(client, pid="PI-863")
    design = phases["Design"]
    assert client.post(f"/workstreams/{design}/start-execution").status_code == 201
    # Work Tasks are Ready, not Complete → cannot advance.
    assert client.post(f"/workstreams/{design}/complete-phase").status_code == 409


def test_lead_driven_end_to_end(client):
    pid, phases = _scoped_pi(client, pid="PI-864")
    ordered = ["Design", "Develop", "Test"]
    for phase in ordered:
        wid = phases[phase]
        ov = _data(client.get(f"/planning-items/{pid}/phase-overview"))
        assert ov["next_executable"] == wid  # the gate exposes exactly this phase

        started = _data(client.post(f"/workstreams/{wid}/start-execution"))
        assert started["workstream"]["workstream_status"] == "In Progress"
        # Area specialists complete the readied Work Tasks.
        for wt in started["readied_work_tasks"]:
            wtid = wt["work_task_identifier"]
            client.post(f"/work-tasks/{wtid}/claim", json={"claimed_by": "area-specialist"})
            for st in ("Claimed", "In Progress", "Complete"):
                client.patch(f"/work-tasks/{wtid}", json={"work_task_status": st})
        done = _data(client.post(f"/workstreams/{wid}/complete-phase"))
        assert done["workstream"]["workstream_status"] == "Complete"

    final = _data(client.get(f"/planning-items/{pid}/phase-overview"))
    assert final["all_terminal"] is True
    assert final["next_executable"] is None

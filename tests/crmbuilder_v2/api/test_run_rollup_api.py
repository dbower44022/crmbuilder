"""Run-level rollup read endpoint — PI-305 (stamping design §4 / DEC-692).

``GET /releases/{id}/run-rollup`` surfaces ``task_transitions.run_rollup`` under
the ``{data, meta, errors}`` envelope: the release's status plus per-task
transition histories, anchored on the halt point for a failed run (REQ-263).
"""

from __future__ import annotations

_EXEC = "Run-rollup API test executive summary line. " * 7  # ~300 chars


def _release(client, title="Run-rollup release"):
    r = client.post(
        "/releases",
        json={"release_title": title, "release_description": "d"},
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["release_identifier"]


def _project(client, name="Run-rollup project"):
    r = client.post(
        "/projects",
        json={
            "project_name": name,
            "project_purpose": "p",
            "project_description": "d",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["project_identifier"]


def _pi(client, title="Run-rollup PI"):
    r = client.post(
        "/planning-items",
        json={
            "title": title,
            "item_type": "pending_work",
            "status": "Draft",
            "executive_summary": _EXEC,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["identifier"]


def _workstream(client, title="Run-rollup WS"):
    r = client.post(
        "/workstreams",
        json={"workstream_phase_type": "Develop", "workstream_title": title},
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["workstream_identifier"]


def _work_task(client, title, area="storage"):
    r = client.post(
        "/work-tasks",
        json={"work_task_title": title, "work_task_area": area},
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["work_task_identifier"]


def _ref(client, st, si, tt, ti, rel):
    r = client.post(
        "/references",
        json={
            "source_type": st,
            "source_id": si,
            "target_type": tt,
            "target_id": ti,
            "relationship": rel,
        },
    )
    assert r.status_code in (200, 201), r.text


def _patch_status(client, wt, status):
    # The work-task PATCH schema carries no agent_report (out of scope for the
    # PI-304 stamping surface), so terminal transitions through the API stamp via
    # the internal-stamp path — a terminal row with no captured report.
    r = client.patch(f"/work-tasks/{wt}", json={"work_task_status": status})
    assert r.status_code == 200, r.text


def _scoped_task(client, ws, title, area="storage"):
    wt = _work_task(client, title, area)
    _ref(client, "work_task", wt, "workstream", ws,
         "work_task_belongs_to_workstream")
    return wt


def _wired_release(client, *, n_tasks=1, area="storage"):
    rel = _release(client)
    prj = _project(client)
    _ref(client, "project", prj, "release", rel, "project_belongs_to_release")
    pi = _pi(client)
    _ref(client, "planning_item", pi, "project", prj,
         "planning_item_belongs_to_project")
    ws = _workstream(client)
    _ref(client, "workstream", ws, "planning_item", pi,
         "workstream_belongs_to_planning_item")
    tasks = [_scoped_task(client, ws, f"WT{i}", area) for i in range(n_tasks)]
    return rel, tasks


def _rollup(client, rel):
    r = client.get(f"/releases/{rel}/run-rollup")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["errors"] is None
    return body["data"]


def test_run_rollup_returns_histories_under_envelope(client):
    rel, (wt,) = _wired_release(client)
    for nxt in ("Ready", "Claimed", "In Progress", "Complete"):
        _patch_status(client, wt, nxt)

    data = _rollup(client, rel)
    assert data["release_identifier"] == rel
    assert data["failed"] is False
    assert data["halt_point"] is None
    assert len(data["tasks"]) == 1
    task = data["tasks"][0]
    assert task["task_identifier"] == wt
    assert task["current_status"] == "Complete"
    assert [t["task_transition_to_status"] for t in task["transitions"]] == [
        "Ready", "Claimed", "In Progress", "Complete",
    ]
    # The API PATCH surface stamps no agent report (internal-stamp path).
    assert task["terminal_report"] is None


def test_run_rollup_anchors_failed_run(client):
    rel, (wt,) = _wired_release(client)
    for nxt in ("Ready", "Claimed", "In Progress", "Blocked"):
        _patch_status(client, wt, nxt)

    data = _rollup(client, rel)
    assert data["failed"] is True
    halt = data["halt_point"]
    assert halt["task_identifier"] == wt
    assert halt["to_status"] == "Blocked"
    # The cause's reason is stamped even without an agent report.
    assert halt["reason"].strip() != ""
    assert halt["agent_report"] is None


def test_run_rollup_empty_release(client):
    rel = _release(client, title="Empty rollup release")
    data = _rollup(client, rel)
    assert data["tasks"] == []
    assert data["failed"] is False
    assert data["halt_point"] is None


def test_run_rollup_unknown_release_404(client):
    r = client.get("/releases/REL-999/run-rollup")
    assert r.status_code == 404, r.text

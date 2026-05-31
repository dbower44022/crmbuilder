"""ADO end-to-end integration test — decompose → scope → execute one PI.

Walks a Planning Item through the Agent Delivery Organization substrate via the
real REST endpoints, with the test standing in for the (not-yet-built) PI Lead /
Project Manager judgment: decompose into six phases, let each "phase specialist"
scope (Architecture/Development/Testing/Deployment produce Work Tasks;
Documentation/Data Migration assert Not Applicable), feed-forward verified, then
execute every Work Task and drive every phase to a terminal state.
"""

from __future__ import annotations

_EXEC = "ADO end-to-end test executive summary, comfortably above the floor. " * 4


def _get(client, path):
    r = client.get(path)
    assert r.status_code == 200, r.text
    return r.json()["data"]


def test_full_pi_lifecycle_through_the_substrate(client):
    pid = "PI-840"
    assert client.post(
        "/planning-items",
        json={"identifier": pid, "title": "Add mentor matching", "item_type": "pending_work",
              "status": "Draft", "executive_summary": _EXEC},
    ).status_code == 201

    # 1. Structural decomposition → six Planned phases + serial blocked_by chain.
    decomposed = client.post(f"/planning-items/{pid}/decompose")
    assert decomposed.status_code == 201, decomposed.text
    phases = {w["workstream_phase_type"]: w["workstream_identifier"]
              for w in decomposed.json()["data"]}
    assert set(phases) == {"Architecture", "Development", "Testing",
                           "Documentation", "Data Migration", "Deployment"}
    chain = client.get("/references", params={
        "source_type": "workstream", "target_type": "workstream",
        "relationship_kind": "blocked_by"}).json()["data"]
    assert len(chain) == 5

    # 2. Phase specialists scope, in canonical feed-forward order.
    # Architecture: no prior context; produces methodology Work Tasks.
    assert _get(client, f"/workstreams/{phases['Architecture']}/prior-phase-outputs")[
        "prior_phases"] == []
    arch = client.post(f"/workstreams/{phases['Architecture']}/scope", json={"work_tasks": [
        {"title": "Add entity Match", "area": "methodology-product"}]})
    assert arch.json()["data"]["workstream"]["workstream_status"] == "Ready"

    # Development scopes against Architecture's output, one Work Task per area.
    dev_ctx = _get(client, f"/workstreams/{phases['Development']}/prior-phase-outputs")
    assert [p["phase_type"] for p in dev_ctx["prior_phases"]] == ["Architecture"]
    dev = client.post(f"/workstreams/{phases['Development']}/scope", json={"work_tasks": [
        {"title": "Match schema", "area": "storage"},
        {"title": "Match repository", "area": "access"},
        {"title": "Match endpoints", "area": "api"}]})
    assert dev.json()["data"]["workstream"]["workstream_status"] == "Ready"

    # Testing produces one task; Documentation + Data Migration are Not Applicable.
    client.post(f"/workstreams/{phases['Testing']}/scope", json={"work_tasks": [
        {"title": "Match tests", "area": "access"}]})
    for empty_phase in ("Documentation", "Data Migration"):
        r = client.post(f"/workstreams/{phases[empty_phase]}/scope", json={"work_tasks": []})
        assert r.json()["data"]["workstream"]["workstream_status"] == "Not Applicable"
    client.post(f"/workstreams/{phases['Deployment']}/scope", json={"work_tasks": [
        {"title": "Release + verify", "area": "infrastructure"}]})

    # 3. Every phase is now terminal-scoped (Ready or Not Applicable).
    for wsid in phases.values():
        status = _get(client, f"/workstreams/{wsid}")["workstream_status"]
        assert status in ("Ready", "Not Applicable")

    # 4. Execute: drive each scoped phase Ready → In Progress → Complete, taking
    #    its Work Tasks Planned → Ready → Claimed → In Progress → Complete.
    completed_tasks = 0
    for wsid in phases.values():
        ws = _get(client, f"/workstreams/{wsid}")
        if ws["workstream_status"] == "Not Applicable":
            continue
        assert client.patch(f"/workstreams/{wsid}",
                            json={"workstream_status": "In Progress"}).status_code == 200
        wt_edges = client.get("/references", params={
            "target_type": "workstream", "target_id": wsid,
            "relationship_kind": "work_task_belongs_to_workstream"}).json()["data"]
        for edge in wt_edges:
            wtid = edge["source_id"]
            client.patch(f"/work-tasks/{wtid}", json={"work_task_status": "Ready"})
            client.post(f"/work-tasks/{wtid}/claim", json={"claimed_by": "area-specialist"})
            client.patch(f"/work-tasks/{wtid}", json={"work_task_status": "Claimed"})
            client.patch(f"/work-tasks/{wtid}", json={"work_task_status": "In Progress"})
            assert client.patch(f"/work-tasks/{wtid}",
                                json={"work_task_status": "Complete"}).status_code == 200
            completed_tasks += 1
        assert client.patch(f"/workstreams/{wsid}",
                            json={"workstream_status": "Complete"}).status_code == 200

    # 5. End state: 1 + 3 + 1 + 1 = 6 Work Tasks complete; every phase terminal.
    assert completed_tasks == 6
    for wsid in phases.values():
        assert _get(client, f"/workstreams/{wsid}")["workstream_status"] in (
            "Complete", "Not Applicable")

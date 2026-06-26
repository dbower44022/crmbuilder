"""Release-run API tests — PI-326 (PRJ-065), REQ-262 / DEC-742.

POST + GET only surface under the ``{data, meta, errors}`` envelope: create,
get-by-id, the release-nested list, findings edges, the outcome CHECK, and the
born-terminal append-only shape (no PUT/PATCH/DELETE route). See
preserve-failed-run-history-design.md §3.3.
"""

from __future__ import annotations


def _release(client, title="Run-outcome release"):
    r = client.post(
        "/releases",
        json={"release_title": title, "release_description": "d"},
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["release_identifier"]


def _finding(client, summary="dup phase", ftype="conflict", severity="blocking"):
    r = client.post(
        "/findings",
        json={
            "finding_type": ftype,
            "finding_severity": severity,
            "finding_summary": summary,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["finding_identifier"]


_SCOPE = {"projects": ["PRJ-037"], "planning_items": ["PI-229", "PI-230"]}
_PHASES = [
    {"workstream": "WSK-144", "phase_type": "Design", "terminal_status": "Complete"},
    {"workstream": "WSK-145", "phase_type": "Develop", "terminal_status": "Ready"},
]


def _create_run(client, **overrides):
    body = {
        "release_run_outcome": "abandoned",
        "release_run_scope": _SCOPE,
        "release_run_phases_run": _PHASES,
        "release_run_halt_point": "development",
        "release_run_cause": "malformed duplicate-phase decomposition",
        "release_run_cause_code": "malformed_decomposition",
    }
    body.update(overrides)
    return client.post("/release-runs", json=body)


def test_create_and_get(client):
    rel = _release(client)
    r = _create_run(client, release_identifier=rel)
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    run_id = data["release_run_identifier"]
    assert run_id.startswith("RUN-")
    assert data["release_run_outcome"] == "abandoned"
    assert data["release_run_scope"] == _SCOPE
    assert data["release_run_phases_run"] == _PHASES

    g = client.get(f"/release-runs/{run_id}")
    assert g.status_code == 200, g.text
    assert g.json()["data"]["release_run_identifier"] == run_id


def test_get_unknown_404(client):
    r = client.get("/release-runs/RUN-999")
    assert r.status_code == 404, r.text


def test_list_for_release_multiple_runs_newest_first(client):
    rel = _release(client)
    r1 = _create_run(client, release_identifier=rel)
    r2 = _create_run(client, release_identifier=rel, release_run_outcome="shipped",
                     release_run_halt_point=None, release_run_cause=None,
                     release_run_cause_code=None)
    assert r1.status_code == 201 and r2.status_code == 201
    listing = client.get(f"/releases/{rel}/runs")
    assert listing.status_code == 200, listing.text
    runs = listing.json()["data"]
    assert len(runs) == 2
    # Newest first — the second-created run leads.
    assert runs[0]["release_run_identifier"] == r2.json()["data"]["release_run_identifier"]


def test_findings_edges_persist(client):
    rel = _release(client)
    f1 = _finding(client, summary="dup phase")
    f2 = _finding(client, summary="missing design", ftype="gap", severity="advisory")
    r = _create_run(client, release_identifier=rel, finding_identifiers=[f1, f2])
    assert r.status_code == 201, r.text
    run_id = r.json()["data"]["release_run_identifier"]
    refs = client.get(
        "/references",
        params={"source_id": run_id, "relationship_kind": "release_run_relates_to_finding"},
    )
    assert refs.status_code == 200, refs.text
    targets = {e["target_id"] for e in refs.json()["data"]}
    assert targets == {f1, f2}


def test_outcome_check_rejects_bad_value(client):
    rel = _release(client)
    r = _create_run(client, release_identifier=rel, release_run_outcome="exploded")
    assert r.status_code == 422, r.text


def test_unknown_release_404(client):
    r = _create_run(client, release_identifier="REL-999")
    assert r.status_code == 404, r.text


def test_append_only_no_mutation_routes(client):
    rel = _release(client)
    run_id = _create_run(client, release_identifier=rel).json()["data"][
        "release_run_identifier"
    ]
    # Born-terminal: no PUT / PATCH / DELETE on the registered paths.
    assert client.put(f"/release-runs/{run_id}", json={}).status_code == 405
    assert client.patch(f"/release-runs/{run_id}", json={}).status_code == 405
    assert client.delete(f"/release-runs/{run_id}").status_code == 405

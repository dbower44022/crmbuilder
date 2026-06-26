"""Release abandon API tests — PI-327 (PRJ-065), REQ-260/264 / DEC-742.

POST /releases/{id}/abandon under the ``{data, meta, errors}`` envelope: the
happy path (write the run + transition + preserve the evidence), and the
rejections (404 unknown, 422 bad outcome, 409 pre-lane). The lane-entered release
is built at the access layer (gates make reaching a lane state via the API
heavyweight); both layers run under the default ENG-001 engagement. See
preserve-failed-run-history-design.md §3.1.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.models import Release
from crmbuilder_v2.access.repositories import (
    planning_items,
    projects,
    references,
    releases,
    workstreams,
)


def _link(s, st, sid, tt, tid, rel):
    references.create(
        s, source_type=st, source_id=sid, target_type=tt, target_id=tid,
        relationship=rel,
    )


def _lane_release(status="development"):
    """Build a release-scoped, decomposed release driven into ``status`` and return
    (rel, prj, pi, ws_design, ws_dev)."""
    with session_scope() as s:
        prj = projects.create_project(s, name="P", purpose="p", description="d")[
            "project_identifier"
        ]
        rel = releases.create_release(s, title="R", description="d")[
            "release_identifier"
        ]
        _link(s, "project", prj, "release", rel, "project_belongs_to_release")
        pi = planning_items.create(
            s, title="PI", item_type="pending_work",
            executive_summary="x" * 250, area=["storage"],
        )["identifier"]
        _link(s, "planning_item", pi, "project", prj,
              "planning_item_belongs_to_project")
        ws_design = workstreams.create_workstream(
            s, phase_type="Design", title="Design", status="Complete"
        )["workstream_identifier"]
        _link(s, "workstream", ws_design, "planning_item", pi,
              "workstream_belongs_to_planning_item")
        ws_dev = workstreams.create_workstream(
            s, phase_type="Develop", title="Develop", status="Ready"
        )["workstream_identifier"]
        _link(s, "workstream", ws_dev, "planning_item", pi,
              "workstream_belongs_to_planning_item")
        row = get_by_identifier(s, Release, Release.release_identifier, rel)
        row.release_status = status
        s.flush()
    return rel, prj, pi, ws_design, ws_dev


def test_abandon_endpoint_round_trips(client):
    rel, prj, pi, ws_design, ws_dev = _lane_release()
    r = client.post(
        f"/releases/{rel}/abandon",
        json={
            "reason": "malformed duplicate-phase decomposition",
            "halt_point": "development",
            "cause_code": "malformed_decomposition",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["errors"] is None
    data = body["data"]
    assert data["release"]["release_status"] == "cancelled"
    run = data["run"]
    assert run["release_run_identifier"].startswith("RUN-")
    assert run["release_run_outcome"] == "abandoned"
    assert run["release_run_halt_point"] == "development"

    # the run is queryable on the release-nested list
    runs = client.get(f"/releases/{rel}/runs")
    assert runs.status_code == 200, runs.text
    assert run["release_run_identifier"] in {
        x["release_run_identifier"] for x in runs.json()["data"]
    }

    # the no-delete guarantee: the scope edge survives, so composition is intact
    comp = client.get(f"/releases/{rel}/composition")
    assert comp.status_code == 200, comp.text
    projects_out = comp.json()["data"]["projects"]
    assert [p["project_identifier"] for p in projects_out] == [prj]
    assert pi in projects_out[0]["planning_items"]


def test_abandon_unknown_release_404(client):
    r = client.post("/releases/REL-999/abandon", json={"reason": "x"})
    assert r.status_code == 404, r.text


def test_abandon_bad_outcome_422(client):
    rel, *_ = _lane_release()
    r = client.post(
        f"/releases/{rel}/abandon", json={"reason": "x", "outcome": "shipped"}
    )
    assert r.status_code == 422, r.text


def test_abandon_pre_lane_release_409(client):
    rel, *_ = _lane_release(status="ready")  # never entered a lane
    r = client.post(f"/releases/{rel}/abandon", json={"reason": "x"})
    assert r.status_code == 409, r.text


@pytest.mark.parametrize("to_status", ["cancelled", "superseded"])
def test_direct_terminal_transition_from_lane_refused(client, to_status):
    rel, *_ = _lane_release()
    r = client.post(f"/releases/{rel}/transition", json={"to_status": to_status})
    assert r.status_code == 409, r.text

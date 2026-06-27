"""Release abandon tests — PI-327 (PRJ-065), REQ-260/264 / DEC-742.

The retire-not-delete operation + its lane gate. Abandoning a run that actually
ran writes a born-terminal ``release_run`` outcome record and transitions the
release to its terminal status WITHOUT deleting the scope edges or phase
workstreams (the no-delete guarantee). A plain transition to a terminal from a
lane state is refused; from a pre-lane state it is still allowed. See
preserve-failed-run-history-design.md §3.1.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import Release
from crmbuilder_v2.access.repositories import (
    findings,
    planning_items,
    projects,
    references,
    release_runs,
    releases,
    workstreams,
)


def _link(s, st, sid, tt, tid, rel):
    references.create(
        s, source_type=st, source_id=sid, target_type=tt, target_id=tid,
        relationship=rel,
    )


def _set_status(s, rel, status):
    row = get_by_identifier(s, Release, Release.release_identifier, rel)
    row.release_status = status
    s.flush()


def _lane_release(s, *, status="development", with_finding=False):
    """A release-scoped project → PI → two phase workstreams (Design Complete,
    Develop Ready — mirroring the REL-004 halt), driven directly into a lane
    status. Returns (rel, prj, pi, [ws_design, ws_dev], finding_id|None)."""
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
    fnd = None
    if with_finding:
        fnd = findings.create_finding(
            s, type="conflict", severity="blocking", summary="dup phase",
        )["finding_identifier"]
        _link(s, "finding", fnd, "workstream", ws_dev, "finding_relates_to")
    _set_status(s, rel, status)
    return rel, prj, pi, [ws_design, ws_dev], fnd


# ---------------------------------------------------------------------------
# abandon — writes the run record, transitions, preserves the evidence
# ---------------------------------------------------------------------------


def test_abandon_writes_run_and_transitions_to_cancelled(v2_env):
    with session_scope() as s:
        rel, prj, pi, (ws_design, ws_dev), _ = _lane_release(s)
        out = releases.abandon(
            s, rel,
            reason="malformed duplicate-phase decomposition",
            halt_point="development",
            cause_code="malformed_decomposition",
        )
        # the release reached its terminal status
        assert out["release"]["release_status"] == "cancelled"
        # a born-terminal run-outcome record was written
        run = out["run"]
        assert run["release_run_identifier"].startswith("RUN-")
        assert run["release_identifier"] == rel
        assert run["release_run_outcome"] == "abandoned"
        assert run["release_run_halt_point"] == "development"
        assert run["release_run_cause"] == "malformed duplicate-phase decomposition"
        assert run["release_run_cause_code"] == "malformed_decomposition"
        # scope snapshot: the project + its planning item
        scope = run["release_run_scope"]
        assert scope["projects"][0]["project_identifier"] == prj
        assert pi in scope["projects"][0]["planning_items"]
        # phases_run snapshot: both phase workstreams with their statuses
        by_ws = {p["workstream"]: p for p in run["release_run_phases_run"]}
        assert by_ws[ws_design]["status"] == "Complete"
        assert by_ws[ws_design]["phase_type"] == "Design"
        assert by_ws[ws_dev]["status"] == "Ready"
        # the run is queryable for the release
        listed = release_runs.list_for_release(s, rel)
        assert [r["release_run_identifier"] for r in listed] == [
            run["release_run_identifier"]
        ]


def test_abandon_preserves_scope_edges_and_workstreams(v2_env):
    """The no-delete guarantee (REQ-264): abandon keeps the scope edges and the
    phase workstreams attached as the run's evidence."""
    with session_scope() as s:
        rel, prj, pi, (ws_design, ws_dev), _ = _lane_release(s)
        releases.abandon(s, rel, reason="halt", halt_point="development")
        # the project_belongs_to_release scope edge survives
        assert releases._in_scope_projects(s, rel) == [prj]
        # the phase workstreams survive (NOT cleared, unlike a plain cancel)
        assert sorted(releases._pi_workstreams(s, pi)) == sorted([ws_design, ws_dev])


def test_abandon_links_workstream_findings(v2_env):
    with session_scope() as s:
        rel, prj, pi, wss, fnd = _lane_release(s, with_finding=True)
        out = releases.abandon(s, rel, reason="halt", halt_point="development")
        run_id = out["run"]["release_run_identifier"]
        edges = references.list_references(
            s, source_id=run_id,
            relationship_kind="release_run_relates_to_finding",
        )
        assert {e["target_id"] for e in edges} == {fnd}


def test_abandon_superseded_outcome_maps_to_superseded(v2_env):
    with session_scope() as s:
        rel, prj, pi, wss, _ = _lane_release(s)
        # superseded requires an inbound release_corrects_release edge — a correction
        # release that corrects this one (releases express supersession through
        # correction, not a generic supersedes edge).
        correction = releases.open_correction_release(
            s, rel, title="R2", description="d"
        )["release_identifier"]
        assert correction != rel
        out = releases.abandon(s, rel, reason="re-attempted", outcome="superseded")
        assert out["release"]["release_status"] == "superseded"
        assert out["run"]["release_run_outcome"] == "superseded"
        # evidence still preserved
        assert releases._in_scope_projects(s, rel) == [prj]
        assert releases._pi_workstreams(s, pi)


def test_abandon_superseded_without_correction_edge_rejected(v2_env):
    """superseded must have a correcting successor — abandon(outcome="superseded")
    on a lane release with no correction edge is rejected."""
    with session_scope() as s:
        rel, *_ = _lane_release(s)
        with pytest.raises(
            UnprocessableError, match="correction release corrects it"
        ):
            releases.abandon(s, rel, reason="x", outcome="superseded")


def test_direct_supersede_without_correction_edge_rejected(v2_env):
    """The correction-edge guard is not abandon-specific: a plain transition to
    superseded from a pre-lane state (no lane-terminal guard in the way) is still
    rejected when no correction release corrects it."""
    with session_scope() as s:
        rel, *_ = _lane_release(s, status="ready")  # pre-lane: lane guard passes
        with pytest.raises(
            UnprocessableError, match="correction release corrects it"
        ):
            releases.transition(s, rel, "superseded")


def test_direct_supersede_with_correction_edge_allowed(v2_env):
    """A pre-lane release that a correction release corrects may plainly supersede."""
    with session_scope() as s:
        rel, *_ = _lane_release(s, status="ready")  # pre-lane
        releases.open_correction_release(s, rel, title="R2", description="d")
        out = releases.transition(s, rel, "superseded")
        assert out["release_status"] == "superseded"


# ---------------------------------------------------------------------------
# the lane gate — abandon is the ONLY terminal path once in a lane
# ---------------------------------------------------------------------------


def test_direct_cancel_from_lane_state_is_refused(v2_env):
    with session_scope() as s:
        rel, *_ = _lane_release(s)
        with pytest.raises(ConflictError, match="only through abandon"):
            releases.transition(s, rel, "cancelled")


def test_direct_supersede_from_lane_state_is_refused(v2_env):
    with session_scope() as s:
        rel, *_ = _lane_release(s)
        with pytest.raises(ConflictError, match="only through abandon"):
            releases.transition(s, rel, "superseded")


def test_direct_cancel_from_pre_lane_state_is_allowed(v2_env):
    """A pre-lane release never ran — nothing to preserve — so it may still plainly
    cancel (the existing REQ-275 clear path is unchanged)."""
    with session_scope() as s:
        rel, prj, pi, wss, _ = _lane_release(s, status="ready")
        out = releases.transition(s, rel, "cancelled")
        assert out["release_status"] == "cancelled"
        # ready is pre-lane, so the existing decomposition-clear still applies
        assert releases._pi_workstreams(s, pi) == []


# ---------------------------------------------------------------------------
# abandon rejections — pre-lane, terminal, bad outcome
# ---------------------------------------------------------------------------


def test_abandon_pre_lane_release_rejected(v2_env):
    with session_scope() as s:
        rel, *_ = _lane_release(s, status="ready")  # never entered a lane
        with pytest.raises(ConflictError, match="never entered a lane"):
            releases.abandon(s, rel, reason="x")


def test_abandon_terminal_release_rejected(v2_env):
    with session_scope() as s:
        rel, *_ = _lane_release(s, status="shipped")  # already terminal
        with pytest.raises(ConflictError, match="already terminal"):
            releases.abandon(s, rel, reason="x")


def test_abandon_shipped_outcome_rejected(v2_env):
    with session_scope() as s:
        rel, *_ = _lane_release(s)
        with pytest.raises(UnprocessableError):
            releases.abandon(s, rel, reason="x", outcome="shipped")


def test_abandon_unknown_release_404(v2_env):
    from crmbuilder_v2.access.exceptions import NotFoundError

    with session_scope() as s:
        with pytest.raises(NotFoundError):
            releases.abandon(s, "REL-999", reason="x")

"""Release-stage driver tests — PI-217 + PI-218 (PRJ-033).

The deterministic agent-layer spine: run_reconciliation (from the persisted
demand-set), reconciled_delta_sets (re-runnable read), run_architecture_planning
(author vN+1), decompose_planning_item_direct (DEC-425 carve-out), finalize_planning
(readiness + interactive→ado flip + enter ready). See
release-pipeline-agent-layer-architecture.md §3-§5.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from crmbuilder_v2.access import release_orchestration as orch
from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError
from crmbuilder_v2.access.models import Release
from crmbuilder_v2.access.repositories import (
    artifact_versions,
    planning_items,
    projects,
    references,
    release_demands,
    releases,
)
from crmbuilder_v2.access.repositories import reconciliation as recon

_SUMMARY = (
    "A planning item exercised by the release-pipeline agent-layer orchestration "
    "tests; it carries enough audience-facing text to satisfy the 200-800 character "
    "executive-summary requirement that the planning_items repository enforces on "
    "create, so the scaffolding builds a valid in-scope item for the readiness gate."
)


def _set_status(s, rel, status, *, frozen=False):
    row = get_by_identifier(s, Release, Release.release_identifier, rel)
    row.release_status = status
    if frozen:
        row.release_frozen_at = datetime.now(UTC)
    s.flush()


def _demand(req, atype, aid, field, facet, op, value=None):
    return {
        "requirement_identifier": req, "artifact_type": atype,
        "artifact_identifier": aid, "field": field, "facet": facet,
        "op": op, "value": value,
    }


# --- PI-217: reconciliation driver -----------------------------------------


def test_run_reconciliation_clean_then_advance(v2_env):
    with session_scope() as s:
        rel = releases.create_release(s, title="R", description="d")[
            "release_identifier"
        ]
        _set_status(s, rel, "reconciliation")
        release_demands.add_demands(
            s, rel,
            [
                _demand("REQ-1", "entity", "ENT-1", "email", "required", "set", True),
                _demand("REQ-2", "entity", "ENT-1", "email", "maxLength", "set", 255),
            ],
            authored_by="AGP-recon",
        )
        out = orch.run_reconciliation(s, rel)
        assert out["has_open_conflicts"] is False
        assert out["open_conflicts"] == []
        assert out["delta_sets"][0]["merged"]["fields"]["email"] == {
            "required": True, "maxLength": 255
        }
        # gate opens with no conflicts
        assert releases.transition(s, rel, "architecture_planning")[
            "release_status"
        ] == "architecture_planning"


def test_run_reconciliation_surfaces_conflict(v2_env):
    with session_scope() as s:
        rel = releases.create_release(s, title="R", description="d")[
            "release_identifier"
        ]
        _set_status(s, rel, "reconciliation")
        release_demands.add_demands(
            s, rel,
            [
                _demand("REQ-1", "entity", "ENT-1", "email", "required", "set", True),
                _demand("REQ-2", "entity", "ENT-1", "email", "required", "set", False),
            ],
            authored_by="AGP-recon",
        )
        out = orch.run_reconciliation(s, rel)
        assert out["has_open_conflicts"] is True
        assert len(out["open_conflicts"]) == 1


# --- PI-217/218: re-runnable delta-set read --------------------------------


def test_reconciled_delta_sets_folds_resolution(v2_env):
    with session_scope() as s:
        rel = releases.create_release(s, title="R", description="d")[
            "release_identifier"
        ]
        _set_status(s, rel, "reconciliation")
        demands = [
            _demand("REQ-1", "entity", "ENT-1", "email", "required", "set", True),
            _demand("REQ-2", "entity", "ENT-1", "email", "required", "set", False),
        ]
        release_demands.add_demands(s, rel, demands, authored_by="AGP-recon")
        orch.run_reconciliation(s, rel)
        cid = recon.list_conflicts(s, rel, status="open")[0]["id"]
        recon.resolve_conflict(
            s, cid, decision_identifier="DEC-1", resolved_value={"value": True}
        )
        # move past the gate; the non-gated read re-derives the same merge.
        _set_status(s, rel, "architecture_planning")
        ds = orch.reconciled_delta_sets(s, rel)
        assert ds[0]["merged"]["fields"]["email"] == {"required": True}


# --- PI-218: architecture-planning drivers ---------------------------------


def test_run_architecture_planning_authors_designs(v2_env):
    with session_scope() as s:
        rel = releases.create_release(s, title="R", description="d")[
            "release_identifier"
        ]
        _set_status(s, rel, "architecture_planning")
        delta_sets = [{
            "artifact_type": "entity", "artifact_identifier": "ENT-1",
            "merged": {"fields": {"email": {"required": True}}, "attributes": {}},
        }]
        out = orch.run_architecture_planning(s, rel, delta_sets)
        assert out["readiness"]["designs_authored"] == 1
        live = artifact_versions.versions_for_release(s, rel)
        assert any(v["artifact_identifier"] == "ENT-1" for v in live)


def _scaffold(s, *, decompose=True):
    """A frozen, architecture_planning release with one in-scope, decomposed PI."""
    prj = projects.create_project(
        s, name="P", purpose="p", description="d"
    )["project_identifier"]
    pi = planning_items.create(
        s, title="T", item_type="pending_work", executive_summary=_SUMMARY,
        execution_mode="interactive",
    )["identifier"]
    rel = releases.create_release(s, title="R", description="d")[
        "release_identifier"
    ]
    references.create(s, source_type="project", source_id=prj,
                      target_type="release", target_id=rel,
                      relationship="project_belongs_to_release")
    references.create(s, source_type="planning_item", source_id=pi,
                      target_type="project", target_id=prj,
                      relationship="planning_item_belongs_to_project")
    _set_status(s, rel, "architecture_planning", frozen=True)
    if decompose:
        orch.decompose_planning_item_direct(s, pi, [
            {"phase_type": "Develop", "title": "Build",
             "work_tasks": [{"title": "do it", "area": "storage"}]},
        ])
    return rel, prj, pi


def test_decompose_planning_item_direct_creates_structure(v2_env):
    with session_scope() as s:
        rel, prj, pi = _scaffold(s)
        # the PI now has a workstream (readiness sees it)
        ws = releases._pi_workstreams(s, pi)
        assert len(ws) == 1
        assert len(releases._ws_work_tasks(s, ws[0])) == 1
        readiness = orch.run_architecture_planning(s, rel, [])["readiness"]
        assert readiness["undecomposed_planning_items"] == []


def test_decompose_drives_workstreams_to_scoped(v2_env):
    """The architect's decomposition IS the scoping: development executes it (§5.2),
    so a phase with work is Ready and an empty phase is Not Applicable — not Planned
    (which the ADO runtime would re-scope)."""
    from crmbuilder_v2.access.repositories import workstreams as wsr

    with session_scope() as s:
        pi = planning_items.create(
            s, title="T", item_type="pending_work", executive_summary=_SUMMARY,
            execution_mode="interactive")["identifier"]
        orch.decompose_planning_item_direct(s, pi, [
            {"phase_type": "Design", "title": "Design", "work_tasks": []},
            {"phase_type": "Develop", "title": "Build",
             "work_tasks": [{"title": "do it", "area": "storage"}]},
        ])
        by_phase = {
            wsr.get_workstream(s, w)["workstream_phase_type"]:
            wsr.get_workstream(s, w)["workstream_status"]
            for w in releases._pi_workstreams(s, pi)
        }
        assert by_phase == {"Design": "Not Applicable", "Develop": "Ready"}


def test_finalize_planning_flips_to_ado_and_advances(v2_env):
    with session_scope() as s:
        rel, prj, pi = _scaffold(s)
        out = orch.finalize_planning(s, rel)
        assert out["release"]["release_status"] == "ready"
        assert pi in out["flipped_to_ado"]
        assert planning_items.get(s, pi)["execution_mode"] == "ado"


def test_finalize_planning_rejects_when_not_ready(v2_env):
    with session_scope() as s:
        rel, prj, pi = _scaffold(s, decompose=False)
        with pytest.raises(ConflictError, match="not planned completely"):
            orch.finalize_planning(s, rel)
        # still interactive, still in architecture_planning
        assert planning_items.get(s, pi)["execution_mode"] == "interactive"


def test_decompose_rejects_duplicate_phase_types(v2_env):
    """REQ-258 / PI-233: a decomposition that repeats a delivery phase is
    rejected — duplicate phase triples tangle the dev-lane walk and stranded a
    real fleet build after Design. The substrate guarantees a well-formed,
    one-workstream-per-phase structure regardless of what the agent proposes."""
    with session_scope() as s:
        pi = planning_items.create(
            s, title="T", item_type="pending_work", executive_summary=_SUMMARY,
            execution_mode="interactive")["identifier"]
        with pytest.raises(ConflictError, match="repeats phase"):
            orch.decompose_planning_item_direct(s, pi, [
                {"phase_type": "Design", "title": "D1", "work_tasks": []},
                {"phase_type": "Develop", "title": "Build",
                 "work_tasks": [{"title": "do it", "area": "storage"}]},
                {"phase_type": "Test", "title": "T1", "work_tasks": []},
                {"phase_type": "Design", "title": "D2 (dup)", "work_tasks": []},
                {"phase_type": "Develop", "title": "Build2 (dup)", "work_tasks": []},
                {"phase_type": "Test", "title": "T2 (dup)", "work_tasks": []},
            ])
    # nothing was created — the guard runs before any workstream is made
    with session_scope() as s:
        assert releases._pi_workstreams(s, pi) == []

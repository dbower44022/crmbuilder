"""PI-269 — upstream planning filters (REQ-266/274/275/276).

REQ-266 (scope per planning item) is covered by the pure ``_scope_designs_to_pi``
in the scheduler tests; here we cover the decomposition guards that live in the
access layer:

* REQ-274 — a decomposition is re-validated as well-formed before execution (and
  the create-time order check that prevents building a malformed graph),
* REQ-275 — cancelling a release clears its planning items' phase plans,
* REQ-276 — a runaway decomposition (over the fan-out cap) is rejected.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access import release_orchestration as orch
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError
from crmbuilder_v2.access.repositories import (
    planning_items,
    projects,
    references,
    releases,
    workstreams,
)

_SUMMARY = "x" * 250


def _pi(s):
    return planning_items.create(
        s, title="T", item_type="pending_work",
        executive_summary=_SUMMARY, execution_mode="interactive",
    )["identifier"]


def _ws(s, phase, title, tasks=()):
    return [{"phase_type": phase, "title": title,
             "work_tasks": [{"title": t, "area": "storage"} for t in tasks]}]


# --- REQ-274 / REQ-258: create-time well-formedness ------------------------


def test_decompose_rejects_out_of_order_phases(v2_env):
    with session_scope() as s:
        pi = _pi(s)
        with pytest.raises(ConflictError, match="subsequence"):
            orch.decompose_planning_item_direct(s, pi, [
                {"phase_type": "Test", "title": "T", "work_tasks": []},
                {"phase_type": "Design", "title": "D", "work_tasks": []},
            ])


def test_decompose_accepts_valid_subsequence(v2_env):
    with session_scope() as s:
        pi = _pi(s)
        # Design then Test (skipping Develop) is a valid subsequence.
        out = orch.decompose_planning_item_direct(s, pi, [
            {"phase_type": "Design", "title": "D", "work_tasks": []},
            {"phase_type": "Test", "title": "T",
             "work_tasks": [{"title": "t", "area": "storage"}]},
        ])
        assert len(out["workstreams"]) == 2


# --- REQ-276: runaway fan-out cap ------------------------------------------


def test_decompose_rejects_runaway_task_count(v2_env):
    cap = orch._MAX_WORK_TASKS_PER_PLANNING_ITEM
    with session_scope() as s:
        pi = _pi(s)
        with pytest.raises(ConflictError, match="cap"):
            orch.decompose_planning_item_direct(s, pi, [
                {"phase_type": "Develop", "title": "Build",
                 "work_tasks": [
                     {"title": f"t{i}", "area": "storage"}
                     for i in range(cap + 1)
                 ]},
            ])


# --- REQ-274: re-validate the persisted graph before execution -------------


def test_validate_decomposition_passes_well_formed(v2_env):
    with session_scope() as s:
        pi = _pi(s)
        orch.decompose_planning_item_direct(s, pi, [
            {"phase_type": "Design", "title": "D", "work_tasks": []},
            {"phase_type": "Develop", "title": "B",
             "work_tasks": [{"title": "t", "area": "storage"}]},
        ])
        orch.validate_decomposition(s, pi)  # no raise


def test_validate_decomposition_empty_is_vacuous(v2_env):
    with session_scope() as s:
        pi = _pi(s)
        orch.validate_decomposition(s, pi)  # no decomposition → no raise


def test_validate_decomposition_rejects_backwards_blocked_by(v2_env):
    # Simulate a stale/malformed graph: a Design phase blocked_by a Test phase
    # (the REL-005 deadlock). Built by hand to bypass the create-time order check.
    with session_scope() as s:
        pi = _pi(s)
        design = workstreams.create_workstream(
            s, phase_type="Design", title="D")["workstream_identifier"]
        test = workstreams.create_workstream(
            s, phase_type="Test", title="T")["workstream_identifier"]
        for ws in (design, test):
            references.create(s, source_type="workstream", source_id=ws,
                              target_type="planning_item", target_id=pi,
                              relationship="workstream_belongs_to_planning_item")
        # Design blocked_by Test — backwards.
        references.create(s, source_type="workstream", source_id=design,
                          target_type="workstream", target_id=test,
                          relationship="blocked_by")
        with pytest.raises(ConflictError, match="Design -> Develop -> Test"):
            orch.validate_decomposition(s, pi)


def test_validate_decomposition_rejects_duplicate_phase(v2_env):
    with session_scope() as s:
        pi = _pi(s)
        for title in ("D1", "D2"):
            ws = workstreams.create_workstream(
                s, phase_type="Design", title=title)["workstream_identifier"]
            references.create(s, source_type="workstream", source_id=ws,
                              target_type="planning_item", target_id=pi,
                              relationship="workstream_belongs_to_planning_item")
        with pytest.raises(ConflictError, match="repeats phase"):
            orch.validate_decomposition(s, pi)


# --- REQ-275: cancelling a release clears its decompositions ----------------


def _scoped_decomposed_release(s):
    prj = projects.create_project(
        s, name="P", purpose="p", description="d")["project_identifier"]
    pi = _pi(s)
    rel = releases.create_release(s, title="R", description="d")["release_identifier"]
    references.create(s, source_type="project", source_id=prj,
                      target_type="release", target_id=rel,
                      relationship="project_belongs_to_release")
    references.create(s, source_type="planning_item", source_id=pi,
                      target_type="project", target_id=prj,
                      relationship="planning_item_belongs_to_project")
    orch.decompose_planning_item_direct(s, pi, [
        {"phase_type": "Design", "title": "D", "work_tasks": []},
        {"phase_type": "Develop", "title": "B",
         "work_tasks": [{"title": "t", "area": "storage"}]},
    ])
    return rel, prj, pi


def test_cancel_clears_decompositions(v2_env):
    with session_scope() as s:
        rel, prj, pi = _scoped_decomposed_release(s)
        assert releases._pi_workstreams(s, pi)  # has a decomposition
        releases.transition(s, rel, "cancelled")
        # the phase plan is gone — a later run inherits nothing
        assert releases._pi_workstreams(s, pi) == []


def test_cancel_clears_is_idempotent_when_nothing_to_clear(v2_env):
    with session_scope() as s:
        prj = projects.create_project(
            s, name="P", purpose="p", description="d")["project_identifier"]
        pi = _pi(s)
        rel = releases.create_release(
            s, title="R", description="d")["release_identifier"]
        references.create(s, source_type="project", source_id=prj,
                          target_type="release", target_id=rel,
                          relationship="project_belongs_to_release")
        references.create(s, source_type="planning_item", source_id=pi,
                          target_type="project", target_id=prj,
                          relationship="planning_item_belongs_to_project")
        releases.transition(s, rel, "cancelled")  # no decomposition → no error
        assert releases._pi_workstreams(s, pi) == []

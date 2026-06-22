"""PI-273 — durable pipeline progress + agent-activity log (REQ-312/313/314).

The ``pipeline_events`` repository records one durable event per pipeline step /
agent invocation (REQ-312/313) and reconstructs a release's ordered history by
traversing the release down to its work tasks (REQ-314).
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access import release_orchestration as orch
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import UnprocessableError
from crmbuilder_v2.access.repositories import (
    pipeline_events as pe,
)
from crmbuilder_v2.access.repositories import (
    projects,
    references,
    releases,
)


def _rec(s, **kw):
    return pe.record(s, **kw)


# --- REQ-312/313: record + validation --------------------------------------


def test_record_persists_an_agent_outcome(v2_env):
    with session_scope() as s:
        row = _rec(s, kind="agent_outcome", outcome="no_op",
                   summary="already satisfied", detail={"transcript_path": "/tmp/x"},
                   work_task="WTK-1", area="storage")
        assert row["event_kind"] == "agent_outcome"
        assert row["outcome"] == "no_op"
        assert row["detail"]["transcript_path"] == "/tmp/x"
        assert row["work_task"] == "WTK-1"


def test_record_rejects_unknown_kind(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError, match="event_kind"):
            _rec(s, kind="bogus")


def test_record_rejects_unknown_outcome(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError, match="outcome"):
            _rec(s, kind="agent_outcome", outcome="bogus")


def test_record_rejects_unknown_correlation_key(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError, match="correlation"):
            _rec(s, kind="dispatch", sprint="x")


def test_recent_is_newest_first_and_filterable(v2_env):
    with session_scope() as s:
        _rec(s, kind="dispatch", work_task="WTK-1")
        _rec(s, kind="merge", work_task="WTK-1")
        _rec(s, kind="dispatch", work_task="WTK-2")
        only_wtk1 = pe.recent(s, work_task="WTK-1")
        assert {e["event_kind"] for e in only_wtk1} == {"dispatch", "merge"}
        assert len(pe.recent(s)) == 3


# --- REQ-314: release history reconstructs across the hierarchy ------------


def _release_with_decomp(s):
    prj = projects.create_project(
        s, name="P", purpose="p", description="d")["project_identifier"]
    rel = releases.create_release(s, title="R", description="d")["release_identifier"]
    pi = _pi_in(s, prj)
    out = orch.decompose_planning_item_direct(s, pi, [
        {"phase_type": "Develop", "title": "B",
         "work_tasks": [{"title": "t", "area": "storage"}]},
    ])
    ws = out["workstreams"][0]["workstream_identifier"]
    wt = out["work_tasks"][0]["work_task_identifier"]
    references.create(s, source_type="project", source_id=prj,
                      target_type="release", target_id=rel,
                      relationship="project_belongs_to_release")
    return rel, pi, ws, wt


def _pi_in(s, prj):
    from crmbuilder_v2.access.repositories import planning_items
    pi = planning_items.create(
        s, title="T", item_type="pending_work",
        executive_summary="x" * 250, execution_mode="interactive")["identifier"]
    references.create(s, source_type="planning_item", source_id=pi,
                      target_type="project", target_id=prj,
                      relationship="planning_item_belongs_to_project")
    return pi


def test_history_unions_release_and_work_task_events_in_order(v2_env):
    with session_scope() as s:
        rel, pi, ws, wt = _release_with_decomp(s)
        # a release-level event (the conductor), then a work-task agent event
        _rec(s, kind="transition", summary="ready -> development",
             release_identifier=rel)
        _rec(s, kind="dispatch", work_task=wt, workstream=ws, area="storage")
        _rec(s, kind="agent_outcome", outcome="delivered",
             summary="merged", work_task=wt, workstream=ws, area="storage")
        # an unrelated event for another release must NOT appear
        _rec(s, kind="transition", summary="x", release_identifier="REL-OTHER")

        hist = pe.history(s, rel)
        kinds = [e["event_kind"] for e in hist]
        assert kinds == ["transition", "dispatch", "agent_outcome"]
        assert hist[-1]["outcome"] == "delivered"
        # newest event belongs to this release's work task, reached via traversal
        assert hist[1]["work_task"] == wt


def test_history_empty_for_release_with_no_events(v2_env):
    with session_scope() as s:
        rel, *_ = _release_with_decomp(s)
        assert pe.history(s, rel) == []

"""Orchestration ready-batches tests (PI-079)."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access import orchestration
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ValidationError
from crmbuilder_v2.access.repositories import planning_items, references


_EXEC_SUMMARY = (
    "This planning item reconciles stale test fixtures with the current governance "
    "schema so the suite validates real behavior; it carries no production code change "
    "and exists purely to keep the regression net aligned with the PI-073 and PI-102 "
    "data-model decisions now in effect."
)


def _pi(s, ident, *, status="Ready", area=None):
    planning_items.create(
        s, identifier=ident, title=ident, item_type="pending_work",
        status=status, executive_summary=_EXEC_SUMMARY, area=area,
    )


def _blocked_by(s, src, tgt):
    references.create(
        s, source_type="planning_item", source_id=src,
        target_type="planning_item", target_id=tgt, relationship="blocked_by",
    )


def _flat_ids(result):
    return [i["identifier"] for b in result["batches"] for i in b["items"]]


def test_empty(v2_env):
    with session_scope() as s:
        result = orchestration.compute_ready_batches(s)
    assert result == {"batches": [], "cyclic": [], "warnings": []}


def test_independent_items_all_depth_0(v2_env):
    with session_scope() as s:
        _pi(s, "PI-001")
        _pi(s, "PI-002")
        result = orchestration.compute_ready_batches(s)
    assert len(result["batches"]) == 1
    assert result["batches"][0]["depth"] == 0
    assert {i["identifier"] for i in result["batches"][0]["items"]} == {
        "PI-001",
        "PI-002",
    }


def test_linear_chain_depths(v2_env):
    with session_scope() as s:
        _pi(s, "PI-001")
        _pi(s, "PI-002")
        _pi(s, "PI-003")
        _blocked_by(s, "PI-002", "PI-001")
        _blocked_by(s, "PI-003", "PI-002")
        result = orchestration.compute_ready_batches(s)
    depths = {b["depth"]: [i["identifier"] for i in b["items"]] for b in result["batches"]}
    assert depths == {0: ["PI-001"], 1: ["PI-002"], 2: ["PI-003"]}


def test_resolved_blocker_not_counted(v2_env):
    with session_scope() as s:
        _pi(s, "PI-001", status="Resolved")
        _pi(s, "PI-002")
        _blocked_by(s, "PI-002", "PI-001")
        result = orchestration.compute_ready_batches(s)
    # Resolved PI-001 is excluded; PI-002's only blocker is satisfied -> depth 0.
    assert _flat_ids(result) == ["PI-002"]
    assert result["batches"][0]["depth"] == 0


def test_claimed_item_present_with_claimed_by(v2_env):
    with session_scope() as s:
        _pi(s, "PI-001")
        planning_items.claim_planning_item(s, "PI-001", "CONV-9")
        result = orchestration.compute_ready_batches(s)
    item = result["batches"][0]["items"][0]
    assert item["claimed_by"] == "CONV-9"


def test_cycle_surfaced_in_cyclic_bucket(v2_env):
    with session_scope() as s:
        _pi(s, "PI-001")
        _pi(s, "PI-002")
        _blocked_by(s, "PI-001", "PI-002")
        _blocked_by(s, "PI-002", "PI-001")
        result = orchestration.compute_ready_batches(s)
    assert result["batches"] == []
    assert {i["identifier"] for i in result["cyclic"]} == {"PI-001", "PI-002"}
    assert result["warnings"]


def test_dependent_on_cycle_is_tainted(v2_env):
    with session_scope() as s:
        _pi(s, "PI-001")
        _pi(s, "PI-002")
        _pi(s, "PI-003")
        _blocked_by(s, "PI-001", "PI-002")
        _blocked_by(s, "PI-002", "PI-001")
        _blocked_by(s, "PI-003", "PI-001")  # depends on a cyclic node
        result = orchestration.compute_ready_batches(s)
    assert {i["identifier"] for i in result["cyclic"]} == {"PI-001", "PI-002", "PI-003"}


def test_area_filter(v2_env):
    with session_scope() as s:
        _pi(s, "PI-001", area=["api"])
        _pi(s, "PI-002", area=["ui"])
        _pi(s, "PI-003")  # no area -> excluded under area filter
        result = orchestration.compute_ready_batches(s, areas=["api"])
    assert _flat_ids(result) == ["PI-001"]


def test_area_filter_unknown_area_rejected(v2_env):
    with session_scope() as s, pytest.raises(ValidationError):
        orchestration.compute_ready_batches(s, areas=["bogus"])


def test_max_depth_cutoff(v2_env):
    with session_scope() as s:
        _pi(s, "PI-001")
        _pi(s, "PI-002")
        _pi(s, "PI-003")
        _blocked_by(s, "PI-002", "PI-001")
        _blocked_by(s, "PI-003", "PI-002")
        result = orchestration.compute_ready_batches(s, max_depth=1)
    assert [b["depth"] for b in result["batches"]] == [0, 1]

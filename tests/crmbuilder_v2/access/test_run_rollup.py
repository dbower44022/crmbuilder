"""Run-level rollup tests — PI-305 (stamping design §4 / DEC-692).

``task_transitions.run_rollup`` is the single durable account of a release run
(REQ-277): walk ``release → projects → planning_items → workstreams →
work_tasks`` and fold in each task's append-only transition history. For a failed
run it anchors on the halt point — the task that stopped the run (``Failed`` /
``Blocked``) and its cause (REQ-263). The view is derived at read time from the
canonical transition rows, never a stored summary.
"""

from __future__ import annotations

from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.models import Release
from crmbuilder_v2.access.repositories import (
    planning_items,
    projects,
    references,
    releases,
    task_transitions,
    work_tasks,
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


def _release_with_tasks(s, *, areas, link_release=True):
    """A release-scoped PI→workstream with one Planned Work Task per area entry.

    Returns ``(release_id|None, [work_task_ids])``. Tasks start ``Planned``; the
    test drives them through the status chokepoint so transitions get stamped.
    """
    rel = None
    prj = projects.create_project(s, name="P", purpose="p", description="d")[
        "project_identifier"
    ]
    if link_release:
        rel = releases.create_release(s, title="R", description="d")[
            "release_identifier"
        ]
        _link(s, "project", prj, "release", rel, "project_belongs_to_release")
    pi = planning_items.create(
        s, title="PI", item_type="pending_work",
        executive_summary="x" * 250, area=["storage"],
    )["identifier"]
    _link(s, "planning_item", pi, "project", prj, "planning_item_belongs_to_project")
    ws = workstreams.create_workstream(s, phase_type="Develop", title="WS")[
        "workstream_identifier"
    ]
    _link(s, "workstream", ws, "planning_item", pi,
          "workstream_belongs_to_planning_item")
    wt_ids = []
    for i, area in enumerate(areas):
        wt = work_tasks.create_work_task(s, title=f"WT{i}", area=area)[
            "work_task_identifier"
        ]
        _link(s, "work_task", wt, "workstream", ws,
              "work_task_belongs_to_workstream")
        wt_ids.append(wt)
    return rel, wt_ids


def _drive(s, wt, statuses, *, agent_report=None):
    """Patch ``wt`` through ``statuses`` in order, stamping each transition."""
    for nxt in statuses:
        report = agent_report if nxt in ("Complete", "Failed", "Blocked") else None
        work_tasks.patch_work_task(s, wt, status=nxt, agent_report=report)


def _terminal_report(outcome="delivered", reasoning="all done", escalation=None):
    report = {"outcome": outcome, "reasoning_summary": reasoning}
    if escalation is not None:
        report["escalation"] = escalation
    return report


# ---------------------------------------------------------------------------
# Happy path — histories assembled correctly and in order
# ---------------------------------------------------------------------------


def test_rollup_assembles_per_task_histories_in_order(v2_env):
    with session_scope() as s:
        rel, (wt1, wt2) = _release_with_tasks(s, areas=["storage", "access"])
    with session_scope() as s:
        _drive(s, wt1, ["Ready", "Claimed", "In Progress", "Complete"],
               agent_report=_terminal_report())
    with session_scope() as s:
        _drive(s, wt2, ["Ready", "Claimed"])

    with session_scope() as s:
        roll = task_transitions.run_rollup(s, rel)

    assert roll["release_identifier"] == rel
    assert roll["failed"] is False
    assert roll["halt_point"] is None
    by_id = {t["task_identifier"]: t for t in roll["tasks"]}
    assert set(by_id) == {wt1, wt2}

    t1 = by_id[wt1]
    assert t1["current_status"] == "Complete"
    assert t1["area"] == "storage"
    # Complete history, gap-free, chained.
    assert [r["task_transition_sequence"] for r in t1["transitions"]] == [1, 2, 3, 4]
    assert [
        (r["task_transition_from_status"], r["task_transition_to_status"])
        for r in t1["transitions"]
    ] == [
        ("Planned", "Ready"),
        ("Ready", "Claimed"),
        ("Claimed", "In Progress"),
        ("In Progress", "Complete"),
    ]
    assert t1["terminal_report"] == {
        "outcome": "delivered",
        "reasoning_summary": "all done",
        "escalation": None,
    }

    t2 = by_id[wt2]
    assert t2["current_status"] == "Claimed"
    assert [r["task_transition_to_status"] for r in t2["transitions"]] == [
        "Ready", "Claimed",
    ]
    assert t2["terminal_report"] is None


# ---------------------------------------------------------------------------
# Failed run — anchored on the halt point + its cause (REQ-263)
# ---------------------------------------------------------------------------


def test_rollup_anchors_failed_run_on_halt_point(v2_env):
    with session_scope() as s:
        rel, (wt1, wt2) = _release_with_tasks(s, areas=["storage", "access"])
    # wt1 succeeds; wt2 halts with a Blocked (needs-human) terminal report.
    with session_scope() as s:
        _drive(s, wt1, ["Ready", "Claimed", "In Progress", "Complete"],
               agent_report=_terminal_report())
    with session_scope() as s:
        _drive(
            s, wt2, ["Ready", "Claimed", "In Progress", "Blocked"],
            agent_report=_terminal_report(
                outcome="halted", reasoning="dependency missing",
                escalation={"decision": "need a human"},
            ),
        )

    with session_scope() as s:
        roll = task_transitions.run_rollup(s, rel)

    assert roll["failed"] is True
    halt = roll["halt_point"]
    assert halt is not None
    assert halt["task_identifier"] == wt2
    assert halt["to_status"] == "Blocked"
    # The cause: the transition reason + the terminal agent report on it.
    assert halt["reason"].strip() != ""
    assert halt["agent_report"] == {
        "outcome": "halted",
        "reasoning_summary": "dependency missing",
        "escalation": {"decision": "need a human"},
    }
    # Only the halted task appears in halt_points; the succeeded one does not.
    assert [h["task_identifier"] for h in roll["halt_points"]] == [wt2]


def test_rollup_anchors_on_most_recent_halt(v2_env):
    # Two tasks halt; the anchor is the later halt (by transition time/sequence).
    with session_scope() as s:
        rel, (wt1, wt2) = _release_with_tasks(s, areas=["storage", "access"])
    with session_scope() as s:
        _drive(s, wt1, ["Ready", "Claimed", "In Progress", "Failed"],
               agent_report=_terminal_report(outcome="failed", reasoning="first"))
    with session_scope() as s:
        _drive(s, wt2, ["Ready", "Claimed", "In Progress", "Failed"],
               agent_report=_terminal_report(outcome="failed", reasoning="second"))

    with session_scope() as s:
        roll = task_transitions.run_rollup(s, rel)

    assert roll["failed"] is True
    assert {h["task_identifier"] for h in roll["halt_points"]} == {wt1, wt2}
    # Anchor is the most-recently-halted task.
    assert roll["halt_point"]["task_identifier"] == wt2


# ---------------------------------------------------------------------------
# Clean / empty edges
# ---------------------------------------------------------------------------


def test_rollup_empty_release(v2_env):
    with session_scope() as s:
        rel = releases.create_release(s, title="Empty", description="d")[
            "release_identifier"
        ]
    with session_scope() as s:
        roll = task_transitions.run_rollup(s, rel)
    assert roll == {
        "release_identifier": rel,
        "status": "preliminary_planning",
        "failed": False,
        "halt_point": None,
        "halt_points": [],
        "tasks": [],
    }


def test_rollup_tasks_without_transitions(v2_env):
    # A scoped task that never moved status has an empty transition list and is
    # not a halt — the rollup still reports it.
    with session_scope() as s:
        rel, (wt1,) = _release_with_tasks(s, areas=["storage"])
    with session_scope() as s:
        roll = task_transitions.run_rollup(s, rel)
    assert roll["failed"] is False
    assert len(roll["tasks"]) == 1
    task = roll["tasks"][0]
    assert task["task_identifier"] == wt1
    assert task["current_status"] == "Planned"
    assert task["transitions"] == []
    assert task["terminal_report"] is None

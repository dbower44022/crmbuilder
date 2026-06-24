"""Task-transition log tests — PI-304 / DEC-692 (storage §3.7 + stamping §6).

Two halves:

* **Storage (task-transition.md §3.7)** — append-only (never mutated, never
  deleted), complete reconstructable history per task, terminal report
  present-at-terminal + the repository 422s, and per-task ordering identity.
* **Stamping (pi-304-scheduler-task-transition-stamping-design.md §6)** — exactly
  one row per real status change through ``update``/``patch``/``claim``; zero rows
  for ``release`` (no status change), a no-op PATCH, and a rejected transition;
  atomicity (a forced ``record`` failure rolls the status update back too); the
  terminal report captured; and ordering under repeated appends.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import StatusTransitionError, UnprocessableError
from crmbuilder_v2.access.repositories import (
    references,
    task_transitions,
    work_tasks,
)
from sqlalchemy import inspect

_EXPECTED_COLUMNS = {
    "task_transition_identifier",
    "task_transition_task_type",
    "task_transition_task_identifier",
    "task_transition_from_status",
    "task_transition_to_status",
    "task_transition_reason",
    "task_transition_sequence",
    "task_transition_at",
    "task_transition_outcome",
    "task_transition_reasoning_summary",
    "task_transition_escalation",
    "task_transition_created_at",
    "engagement_id",
}


def _make_task(s, ident="WTK-001", *, status=None, area="storage"):
    return work_tasks.create_work_task(
        s, title="t", area=area, identifier=ident, status=status
    )["work_task_identifier"]


def _terminal_report(outcome="delivered", reasoning="all done", escalation=None):
    report = {"outcome": outcome, "reasoning_summary": reasoning}
    if escalation is not None:
        report["escalation"] = escalation
    return report


# ---------------------------------------------------------------------------
# Storage — schema shape + append-only construction
# ---------------------------------------------------------------------------


def test_table_shape(v2_env):
    inspector = inspect(get_engine())
    assert "task_transitions" in inspector.get_table_names()
    cols = {c["name"] for c in inspector.get_columns("task_transitions")}
    assert cols == _EXPECTED_COLUMNS
    # Append-only: no soft-delete / touch-on-update columns (mirror deposit_event).
    assert "task_transition_updated_at" not in cols
    assert "task_transition_deleted_at" not in cols


def test_repository_exposes_no_update_or_delete(v2_env):
    # §3.7.1 / §3.7.2: the only write verb is ``record``; there is no update or
    # delete path on the module.
    public = {n for n in dir(task_transitions) if not n.startswith("_")}
    writes = {n for n in public if any(n.startswith(p) for p in ("update", "delete", "patch", "restore"))}
    assert writes == set(), f"unexpected mutating verbs exported: {writes}"
    assert "record" in public


def test_unique_per_task_sequence_constraint(v2_env):
    uniques = inspect(get_engine()).get_unique_constraints("task_transitions")
    cols = {tuple(u["column_names"]) for u in uniques}
    assert (
        "engagement_id",
        "task_transition_task_type",
        "task_transition_task_identifier",
        "task_transition_sequence",
    ) in cols


# ---------------------------------------------------------------------------
# Storage — complete reconstructable history (§3.7.3)
# ---------------------------------------------------------------------------


def test_complete_history_reconstructable_per_task(v2_env):
    with session_scope() as s:
        _make_task(s, "WTK-010")
    # Drive a full multi-step lifecycle through the chokepoint.
    for nxt in ("Ready", "Claimed", "In Progress", "Complete"):
        with session_scope() as s:
            report = _terminal_report() if nxt == "Complete" else None
            work_tasks.patch_work_task(s, "WTK-010", status=nxt, agent_report=report)
    with session_scope() as s:
        rows = task_transitions.list_for_task(s, "WTK-010")
    # One row per change, gap-free 1..N, chained from/to statuses.
    assert [r["task_transition_sequence"] for r in rows] == [1, 2, 3, 4]
    path = [
        (r["task_transition_from_status"], r["task_transition_to_status"])
        for r in rows
    ]
    assert path == [
        ("Planned", "Ready"),
        ("Ready", "Claimed"),
        ("Claimed", "In Progress"),
        ("In Progress", "Complete"),
    ]
    # The graph-form parent edge exists for each transition.
    with session_scope() as s:
        edges = references.list_references(
            s, target_id="WTK-010", relationship_kind="task_transition_records_task"
        )
    assert len(edges) == 4


def test_inaugural_row_carries_real_from_status(v2_env):
    # The work_task lifecycle has no not_started creation-into state, so the
    # inaugural stamped transition legitimately carries a real from_status.
    with session_scope() as s:
        _make_task(s, "WTK-011")
    with session_scope() as s:
        work_tasks.patch_work_task(s, "WTK-011", status="Ready")
    with session_scope() as s:
        rows = task_transitions.list_for_task(s, "WTK-011")
    assert len(rows) == 1
    assert rows[0]["task_transition_sequence"] == 1
    assert rows[0]["task_transition_from_status"] == "Planned"


# ---------------------------------------------------------------------------
# Storage — append-only survives a parent retire (§3.7.2)
# ---------------------------------------------------------------------------


def test_history_survives_parent_soft_delete(v2_env):
    with session_scope() as s:
        _make_task(s, "WTK-012")
    with session_scope() as s:
        work_tasks.patch_work_task(s, "WTK-012", status="Ready")
    with session_scope() as s:
        before = task_transitions.list_for_task(s, "WTK-012")
    # Retire the parent task.
    with session_scope() as s:
        work_tasks.delete_work_task(s, "WTK-012")
    with session_scope() as s:
        after = task_transitions.list_for_task(s, "WTK-012")
    assert after == before
    assert len(after) == 1


# ---------------------------------------------------------------------------
# Storage — terminal report present-at-terminal + the repository 422s (§3.7.4)
# ---------------------------------------------------------------------------


def test_terminal_report_persisted_and_readable(v2_env):
    with session_scope() as s:
        _make_task(s, "WTK-020", status="In Progress")
    with session_scope() as s:
        work_tasks.patch_work_task(
            s, "WTK-020", status="Complete", agent_report=_terminal_report()
        )
    with session_scope() as s:
        rows = task_transitions.list_for_task(s, "WTK-020")
        report = task_transitions.terminal_report(s, "WTK-020")
    assert rows[-1]["task_transition_outcome"] == "delivered"
    assert rows[-1]["task_transition_reasoning_summary"] == "all done"
    assert report == {
        "outcome": "delivered",
        "reasoning_summary": "all done",
        "escalation": None,
    }


def test_terminal_report_none_before_terminal(v2_env):
    with session_scope() as s:
        _make_task(s, "WTK-021")
    with session_scope() as s:
        work_tasks.patch_work_task(s, "WTK-021", status="Ready")
    with session_scope() as s:
        assert task_transitions.terminal_report(s, "WTK-021") is None


def test_non_terminal_with_report_rejected(v2_env):
    with session_scope() as s:
        _make_task(s, "WTK-022")
    with session_scope() as s, pytest.raises(UnprocessableError):
        task_transitions.record(
            s,
            task_identifier="WTK-022",
            from_status=None,
            to_status="Ready",
            reason="r",
            agent_report=_terminal_report(),
        )


def test_terminal_with_incomplete_report_rejected(v2_env):
    with session_scope() as s:
        _make_task(s, "WTK-023", status="In Progress")
    # Missing reasoning_summary.
    with session_scope() as s, pytest.raises(UnprocessableError):
        task_transitions.record(
            s,
            task_identifier="WTK-023",
            from_status=None,
            to_status="Complete",
            reason="r",
            agent_report={"outcome": "delivered"},
        )
    # Invalid outcome.
    with session_scope() as s, pytest.raises(UnprocessableError):
        task_transitions.record(
            s,
            task_identifier="WTK-023",
            from_status=None,
            to_status="Complete",
            reason="r",
            agent_report={"outcome": "nope", "reasoning_summary": "x"},
        )


def test_blocked_requires_escalation(v2_env):
    with session_scope() as s:
        _make_task(s, "WTK-024", status="In Progress")
    # Blocked (needs-human-equivalent) with a report but no escalation → 422.
    with session_scope() as s, pytest.raises(UnprocessableError):
        task_transitions.record(
            s,
            task_identifier="WTK-024",
            from_status=None,
            to_status="Blocked",
            reason="r",
            agent_report=_terminal_report(outcome="halted"),
        )
    # With an escalation → accepted.
    with session_scope() as s:
        out = task_transitions.record(
            s,
            task_identifier="WTK-024",
            from_status=None,
            to_status="Blocked",
            reason="r",
            agent_report=_terminal_report(
                outcome="halted", escalation={"decision": "needs review"}
            ),
        )
    assert out["task_transition_escalation"] == {"decision": "needs review"}


def test_complete_forbids_escalation(v2_env):
    with session_scope() as s:
        _make_task(s, "WTK-025", status="In Progress")
    with session_scope() as s, pytest.raises(UnprocessableError):
        task_transitions.record(
            s,
            task_identifier="WTK-025",
            from_status=None,
            to_status="Complete",
            reason="r",
            agent_report=_terminal_report(escalation={"x": 1}),
        )


def test_empty_reason_rejected(v2_env):
    with session_scope() as s:
        _make_task(s, "WTK-026")
    with session_scope() as s, pytest.raises(UnprocessableError):
        task_transitions.record(
            s,
            task_identifier="WTK-026",
            from_status=None,
            to_status="Ready",
            reason="   ",
        )


# ---------------------------------------------------------------------------
# Storage — chain consistency (§3.4)
# ---------------------------------------------------------------------------


def test_null_from_status_only_on_inaugural(v2_env):
    with session_scope() as s:
        _make_task(s, "WTK-030")
        task_transitions.record(
            s, task_identifier="WTK-030", from_status=None, to_status="Ready", reason="r"
        )
    # A second row with a NULL from_status is rejected (NULL only on inaugural).
    with session_scope() as s, pytest.raises(UnprocessableError):
        task_transitions.record(
            s,
            task_identifier="WTK-030",
            from_status=None,
            to_status="Claimed",
            reason="r",
        )


def test_chain_break_rejected(v2_env):
    with session_scope() as s:
        _make_task(s, "WTK-031")
        task_transitions.record(
            s, task_identifier="WTK-031", from_status=None, to_status="Ready", reason="r"
        )
    # from_status must equal the prior row's to_status ("Ready").
    with session_scope() as s, pytest.raises(UnprocessableError):
        task_transitions.record(
            s,
            task_identifier="WTK-031",
            from_status="Planned",
            to_status="Claimed",
            reason="r",
        )


def test_ordering_identity_sequences_increment(v2_env):
    with session_scope() as s:
        _make_task(s, "WTK-032")
        task_transitions.record(
            s, task_identifier="WTK-032", from_status=None, to_status="Ready", reason="r"
        )
        task_transitions.record(
            s,
            task_identifier="WTK-032",
            from_status="Ready",
            to_status="Claimed",
            reason="r",
        )
    with session_scope() as s:
        rows = task_transitions.list_for_task(s, "WTK-032")
    assert [r["task_transition_sequence"] for r in rows] == [1, 2]
    # Sequences are per-task: a different task restarts at 1.
    with session_scope() as s:
        _make_task(s, "WTK-033")
        out = task_transitions.record(
            s, task_identifier="WTK-033", from_status=None, to_status="Ready", reason="r"
        )
    assert out["task_transition_sequence"] == 1


def test_polymorphic_workstream_parent(v2_env):
    # The schema is polymorphic; a workstream parent is admitted by the CHECK and
    # the records_task edge pair rule.
    from crmbuilder_v2.access.repositories import workstreams

    with session_scope() as s:
        workstreams.create_workstream(
            s, phase_type="Development", title="ws", identifier="WSK-100"
        )
        out = task_transitions.record(
            s,
            task_type="workstream",
            task_identifier="WSK-100",
            from_status=None,
            to_status="Scoping",
            reason="r",
        )
    assert out["task_transition_task_type"] == "workstream"
    assert out["task_transition_to_status"] == "Scoping"


# ---------------------------------------------------------------------------
# Stamping (§6)
# ---------------------------------------------------------------------------


def test_exactly_one_row_per_real_change_update_and_patch(v2_env):
    with session_scope() as s:
        _make_task(s, "WTK-040")
    with session_scope() as s:
        work_tasks.update_work_task(s, "WTK-040", title="t", area="storage", status="Ready")
    with session_scope() as s:
        assert len(task_transitions.list_for_task(s, "WTK-040")) == 1
    with session_scope() as s:
        work_tasks.patch_work_task(s, "WTK-040", status="Claimed")
    with session_scope() as s:
        rows = task_transitions.list_for_task(s, "WTK-040")
    assert len(rows) == 2
    assert rows[-1]["task_transition_to_status"] == "Claimed"


def test_claim_stamps_one_row(v2_env):
    with session_scope() as s:
        _make_task(s, "WTK-041", status="Ready")
    with session_scope() as s:
        work_tasks.claim_work_task(s, "WTK-041", claimed_by="CNV-001")
    with session_scope() as s:
        rows = task_transitions.list_for_task(s, "WTK-041")
    assert len(rows) == 1
    assert (rows[0]["task_transition_from_status"], rows[0]["task_transition_to_status"]) == (
        "Ready",
        "Claimed",
    )
    # A default non-empty reason is stamped (defect #2).
    assert rows[0]["task_transition_reason"].strip() != ""


def test_release_writes_zero_rows(v2_env):
    with session_scope() as s:
        _make_task(s, "WTK-042", status="Ready")
    with session_scope() as s:
        work_tasks.claim_work_task(s, "WTK-042", claimed_by="CNV-001")
    with session_scope() as s:
        count_before = len(task_transitions.list_for_task(s, "WTK-042"))
    with session_scope() as s:
        work_tasks.release_work_task(s, "WTK-042", claimed_by="CNV-001")
    with session_scope() as s:
        count_after = len(task_transitions.list_for_task(s, "WTK-042"))
    assert count_after == count_before  # release is not a status change


def test_no_op_patch_writes_zero_rows(v2_env):
    with session_scope() as s:
        _make_task(s, "WTK-043", status="Ready")
    # PATCH to the SAME status — no real change, stamps nothing.
    with session_scope() as s:
        work_tasks.patch_work_task(s, "WTK-043", status="Ready")
    with session_scope() as s:
        assert task_transitions.list_for_task(s, "WTK-043") == []


def test_rejected_transition_writes_zero_rows(v2_env):
    with session_scope() as s:
        _make_task(s, "WTK-044")  # Planned
    # Planned -> In Progress is illegal; raises before any stamp.
    with session_scope() as s, pytest.raises(StatusTransitionError):
        work_tasks.patch_work_task(s, "WTK-044", status="In Progress")
    with session_scope() as s:
        assert task_transitions.list_for_task(s, "WTK-044") == []
        # And the status is unchanged.
        assert work_tasks.get_work_task(s, "WTK-044")["work_task_status"] == "Planned"


def test_atomicity_rollback(v2_env, monkeypatch):
    with session_scope() as s:
        _make_task(s, "WTK-045")

    def _boom(*args, **kwargs):
        raise RuntimeError("forced transition-insert failure")

    monkeypatch.setattr(
        "crmbuilder_v2.access.repositories.task_transitions.record", _boom
    )
    with pytest.raises(RuntimeError):
        with session_scope() as s:
            work_tasks.patch_work_task(s, "WTK-045", status="Ready")
    monkeypatch.undo()
    # Both the status UPDATE and the (would-be) row are rolled back.
    with session_scope() as s:
        assert work_tasks.get_work_task(s, "WTK-045")["work_task_status"] == "Planned"
        assert task_transitions.list_for_task(s, "WTK-045") == []


def test_terminal_report_captured_via_patch(v2_env):
    with session_scope() as s:
        _make_task(s, "WTK-046", status="In Progress")
    with session_scope() as s:
        work_tasks.patch_work_task(
            s,
            "WTK-046",
            status="Complete",
            agent_report=_terminal_report(outcome="delivered", reasoning="shipped"),
        )
    with session_scope() as s:
        report = task_transitions.terminal_report(s, "WTK-046")
    assert report["outcome"] == "delivered"
    assert report["reasoning_summary"] == "shipped"

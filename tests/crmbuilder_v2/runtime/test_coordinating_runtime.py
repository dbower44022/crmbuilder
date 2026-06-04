"""PI-132 Layer 1 — coordinating-runtime decision logic + loop control flow.

These tests cover the *pure* decisions (verify, pause, merge-reading) and the
loop's control flow with the I/O seams (assignment resolution, agent spawn, git
worktree, merge) injected — so the loop's spawn→verify→merge→pause behavior is
exercised without a server, a real worktree, or a spawned agent. The genuine
end-to-end spawn/merge is proven by the demo (see the apply prompt), not here.
"""

from __future__ import annotations

import subprocess

import pytest

from crmbuilder_v2.runtime import coordinating_runtime as cr
from crmbuilder_v2.runtime.coordinating_runtime import (
    CoordinatingRuntime,
    MergeResult,
    MergeStatus,
    RuntimeConfig,
    StepResult,
    VerifyOutcome,
    interpret_merge,
    minimal_contract_prompt,
    operating_protocol,
    pause_reason_for,
    verify_result,
)


# --------------------------------------------------------------------------
# Pure decision helpers
# --------------------------------------------------------------------------


def test_verify_ok_requires_complete_and_commits():
    assert verify_result({"work_task_status": "Complete"}, True) is VerifyOutcome.OK


def test_verify_not_complete_when_status_not_complete():
    assert (
        verify_result({"work_task_status": "In Progress"}, True)
        is VerifyOutcome.NOT_COMPLETE
    )
    assert (
        verify_result({"work_task_status": "Claimed"}, True)
        is VerifyOutcome.NOT_COMPLETE
    )


def test_verify_no_commits_when_complete_but_branch_empty():
    assert (
        verify_result({"work_task_status": "Complete"}, False)
        is VerifyOutcome.NO_COMMITS
    )


def test_pause_none_when_nothing_flagged():
    assert pause_reason_for({"work_task_status": "Ready"}, None) is None
    assert pause_reason_for({}, {"workstream_status": "In Progress"}) is None


def test_pause_on_work_task_flag():
    reason = pause_reason_for(
        {"work_task_needs_attention": True, "work_task_needs_attention_reason": "why"},
        None,
    )
    assert reason == "why"


def test_pause_on_workstream_flag_when_task_clean():
    reason = pause_reason_for(
        {"work_task_needs_attention": False},
        {"workstream_needs_attention": True},
    )
    assert reason == "Workstream flagged needs_attention"


def test_pause_default_message_when_no_reason_given():
    assert (
        pause_reason_for({"work_task_needs_attention": True}, None)
        == "Work Task flagged needs_attention"
    )


def test_interpret_merge_clean():
    assert interpret_merge(0, "Merge made by the 'ort' strategy").status is MergeStatus.CLEAN


def test_interpret_merge_conflict():
    r = interpret_merge(1, "Automatic merge failed; fix conflicts")
    assert r.status is MergeStatus.CONFLICT


def test_interpret_merge_nonzero_without_marker_is_conflict():
    # Any non-zero merge that did not cleanly complete is held for a human.
    assert interpret_merge(128, "fatal: something").status is MergeStatus.CONFLICT


# --------------------------------------------------------------------------
# Prompt assembly
# --------------------------------------------------------------------------


def test_operating_protocol_names_task_engagement_and_branch():
    text = operating_protocol(
        work_task_id="WTK-099",
        area="api",
        api_base="http://x:8765",
        engagement="CRMBUILDER",
        branch="ado/wtk-099",
    )
    assert "WTK-099" in text
    assert "X-Engagement: CRMBUILDER" in text
    assert "ado/wtk-099" in text
    assert "/claim" in text and "Complete" in text


def test_minimal_contract_prompt_includes_task_fields():
    wt = {
        "work_task_identifier": "WTK-099",
        "work_task_title": "Do a thing",
        "work_task_description": "the details",
    }
    text = minimal_contract_prompt(wt, area="api")
    assert "WTK-099" in text and "Do a thing" in text and "the details" in text


# --------------------------------------------------------------------------
# Loop control flow with injected seams
# --------------------------------------------------------------------------


class _FakeWorktree:
    """Stands in for a real git worktree — records lifecycle, no git calls."""

    def __init__(self, has_commits: bool):
        self._has_commits = has_commits
        self.created = False
        self.removed = False
        self.path = "/tmp/fake-worktree"

    def create(self):
        self.created = True
        return self.path

    def has_commits_beyond(self, base_ref):
        return self._has_commits

    def remove(self):
        self.removed = True


def _proc(rc=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=stdout, stderr=stderr)


def _build_runtime(monkeypatch, *, assignment, task_after, has_commits, merge_result,
                   workstream=None, spawn_rc=0):
    """Wire a CoordinatingRuntime with all I/O seams stubbed."""
    cfg = RuntimeConfig(target_work_task="WTK-099", dry_run=False)
    rt = CoordinatingRuntime(config=cfg, spawn_fn=lambda p, wp: _proc(rc=spawn_rc), log=lambda m: None)

    monkeypatch.setattr(rt, "_next_assignment", lambda: assignment)
    monkeypatch.setattr(rt, "_owning_workstream", lambda wt: workstream)
    monkeypatch.setattr(rt, "_merge", lambda branch: merge_result)
    flagged = {}
    monkeypatch.setattr(
        rt, "_flag_needs_attention", lambda wt, reason: flagged.update({wt: reason})
    )
    rt._flagged = flagged

    fake_wt = _FakeWorktree(has_commits)
    monkeypatch.setattr(cr, "Worktree", lambda **kw: fake_wt)
    rt._fake_wt = fake_wt

    # The post-spawn re-read of the Work Task.
    monkeypatch.setattr(cr.dispatcher, "_get", lambda api, path, eng: task_after)
    return rt


def _assignment(task):
    return cr._ResolvedAssignment(
        work_task=task,
        work_task_id="WTK-099",
        area="api",
        profile_id="AGP-runtime",
        branch="ado/wtk-099",
        prompt="do it",
    )


def test_drained_when_no_assignment(monkeypatch):
    cfg = RuntimeConfig()
    rt = CoordinatingRuntime(config=cfg, log=lambda m: None)
    monkeypatch.setattr(rt, "_next_assignment", lambda: None)
    report = rt.run_one()
    assert report.result is StepResult.DRAINED


def test_happy_path_verifies_and_merges(monkeypatch):
    task = {"work_task_identifier": "WTK-099", "work_task_status": "Ready"}
    rt = _build_runtime(
        monkeypatch,
        assignment=_assignment(task),
        task_after={"work_task_status": "Complete"},
        has_commits=True,
        merge_result=MergeResult(MergeStatus.CLEAN, "merged"),
    )
    report = rt.run_one()
    assert report.result is StepResult.MERGED
    assert report.verify is VerifyOutcome.OK
    assert report.merge.status is MergeStatus.CLEAN
    assert rt._fake_wt.created and rt._fake_wt.removed  # worktree cleaned up
    assert rt._flagged == {}  # nothing flagged on a clean run


def test_pauses_and_flags_when_agent_did_not_complete(monkeypatch):
    task = {"work_task_identifier": "WTK-099", "work_task_status": "Ready"}
    rt = _build_runtime(
        monkeypatch,
        assignment=_assignment(task),
        task_after={"work_task_status": "In Progress"},  # agent didn't finish
        has_commits=True,
        merge_result=MergeResult(MergeStatus.CLEAN, "merged"),
    )
    report = rt.run_one()
    assert report.result is StepResult.PAUSED
    assert report.verify is VerifyOutcome.NOT_COMPLETE
    assert "WTK-099" in rt._flagged  # human-attention flag set
    assert rt._fake_wt.removed


def test_pauses_on_merge_conflict_after_verify(monkeypatch):
    task = {"work_task_identifier": "WTK-099", "work_task_status": "Ready"}
    rt = _build_runtime(
        monkeypatch,
        assignment=_assignment(task),
        task_after={"work_task_status": "Complete"},
        has_commits=True,
        merge_result=MergeResult(MergeStatus.CONFLICT, "CONFLICT in f.py"),
    )
    report = rt.run_one()
    assert report.result is StepResult.PAUSED
    assert report.verify is VerifyOutcome.OK
    assert report.merge.status is MergeStatus.CONFLICT
    assert "WTK-099" in rt._flagged


def test_pauses_before_spawn_when_task_pre_flagged(monkeypatch):
    task = {
        "work_task_identifier": "WTK-099",
        "work_task_status": "Ready",
        "work_task_needs_attention": True,
        "work_task_needs_attention_reason": "human please look",
    }
    rt = _build_runtime(
        monkeypatch,
        assignment=_assignment(task),
        task_after={"work_task_status": "Complete"},
        has_commits=True,
        merge_result=MergeResult(MergeStatus.CLEAN, "merged"),
    )
    report = rt.run_one()
    assert report.result is StepResult.PAUSED
    assert report.pause_reason == "human please look"
    # No agent should have been spawned: the worktree was never created.
    assert rt._fake_wt.created is False


def test_dry_run_resolves_but_does_not_spawn(monkeypatch):
    task = {"work_task_identifier": "WTK-099", "work_task_status": "Ready"}
    cfg = RuntimeConfig(target_work_task="WTK-099", dry_run=True)
    rt = CoordinatingRuntime(config=cfg, log=lambda m: None)
    monkeypatch.setattr(rt, "_next_assignment", lambda: _assignment(task))
    monkeypatch.setattr(rt, "_owning_workstream", lambda wt: None)
    report = rt.run_one()
    assert report.result is StepResult.PAUSED
    assert report.pause_reason == "dry-run"


def test_run_stops_at_first_pause(monkeypatch):
    task = {"work_task_identifier": "WTK-099", "work_task_status": "Ready"}
    cfg = RuntimeConfig(target_work_task="WTK-099", max_iterations=5, dry_run=True)
    rt = CoordinatingRuntime(config=cfg, log=lambda m: None)
    monkeypatch.setattr(rt, "_next_assignment", lambda: _assignment(task))
    monkeypatch.setattr(rt, "_owning_workstream", lambda wt: None)
    reports = rt.run()
    assert len(reports) == 1  # dry-run pause stops the loop immediately

"""PI-132 Layer 1 — coordinating-runtime decision logic + loop control flow.

These tests cover the *pure* decisions (verify, pause, merge-reading) and the
loop's control flow with the I/O seams (assignment resolution, agent spawn, git
worktree, merge) injected — so the loop's spawn→verify→merge→pause behavior is
exercised without a server, a real worktree, or a spawned agent. The genuine
end-to-end spawn/merge is proven by the demo (see the apply prompt), not here.
"""

from __future__ import annotations

import json
import re
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request

import pytest
import uvicorn
from crmbuilder_v2.runtime import coordinating_runtime as cr
from crmbuilder_v2.runtime.coordinating_runtime import (
    _TIMEOUT_RC,
    CoordinatingRuntime,
    MergeResult,
    MergeStatus,
    RuntimeConfig,
    StepResult,
    TestRunResult,
    VerifyOutcome,
    _is_harness_crash,
    _safe_run_tests,
    interpret_merge,
    is_doc_only_change,
    minimal_contract_prompt,
    operating_protocol,
    pause_reason_for,
    select_test_target,
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


# --------------------------------------------------------------------------
# PI-147: select_test_target — pure mapping (touched src files → pytest target)
# --------------------------------------------------------------------------

_P = "crmbuilder-v2/src/crmbuilder_v2/"


def test_select_target_single_mirrored_subtree_runtime():
    assert select_test_target([f"{_P}runtime/coordinating_runtime.py"]) == (
        "tests/crmbuilder_v2/runtime"
    )


def test_select_target_single_mirrored_subtree_ui():
    assert select_test_target([f"{_P}ui/widgets/foo.py"]) == "tests/crmbuilder_v2/ui"


def test_select_target_two_mirrored_subtrees_runs_their_union():
    # PI-200: two mirrored subtrees no longer fall back to the slow full suite —
    # the gate runs just those two fast packages (union, sorted for determinism).
    target = select_test_target([f"{_P}runtime/a.py", f"{_P}ui/b.py"])
    assert target == "tests/crmbuilder_v2/runtime tests/crmbuilder_v2/ui"


def test_select_target_mirrored_plus_unmirrored_falls_back_to_full_suite():
    # A mirrored subtree alongside one with no mirror package can't be localized
    # to packages-only → conservative full suite (widen, never narrow).
    target = select_test_target([f"{_P}runtime/a.py", f"{_P}brandnew/b.py"])
    assert target == "tests/crmbuilder_v2"


def test_select_target_top_level_module_falls_back():
    assert select_test_target([f"{_P}cli.py"]) == "tests/crmbuilder_v2"


def test_select_target_path_outside_src_falls_back():
    assert select_test_target(["PRDs/product/x.md"]) == "tests/crmbuilder_v2"


def test_select_target_empty_falls_back():
    assert select_test_target([]) == "tests/crmbuilder_v2"


def test_select_target_unmirrored_subtree_falls_back():
    # A real src subtree with no mirroring tests package (e.g. a future one).
    assert select_test_target([f"{_P}brandnew/x.py"]) == "tests/crmbuilder_v2"


def test_select_target_src_plus_its_mirror_test_stays_localized():
    # The WTK-151 case: a ui change + its ui test must map to the fast ui package,
    # not the full-suite fallback (which then times out).
    target = select_test_target([
        f"{_P}ui/widgets/linked_record_preview.py",
        f"{_P}ui/assets/icons/lucide/eye.svg",
        "tests/crmbuilder_v2/ui/widgets/test_linked_record_preview.py",
    ])
    assert target == "tests/crmbuilder_v2/ui"


def test_select_target_test_only_change_localizes_to_subtree():
    assert select_test_target(
        ["tests/crmbuilder_v2/runtime/test_x.py"]
    ) == "tests/crmbuilder_v2/runtime"


def test_select_target_ignores_docs_in_mixed_change():
    # A src/ui change plus a spec .md → the .md is ignored, target is ui.
    assert select_test_target(
        [f"{_P}ui/x.py", "PRDs/product/spec.md"]
    ) == "tests/crmbuilder_v2/ui"


def test_select_target_top_level_test_file_falls_back():
    # tests/crmbuilder_v2/conftest.py (no <sub>/ segment) affects everything.
    assert select_test_target(["tests/crmbuilder_v2/conftest.py"]) == "tests/crmbuilder_v2"


# --------------------------------------------------------------------------
# Doc-only change → skip the test gate (a .md spec cannot break tests)
# --------------------------------------------------------------------------


def test_is_doc_only_change_true_for_docs():
    assert is_doc_only_change(["PRDs/product/crmbuilder-v2/pi-148-design.md"]) is True
    assert is_doc_only_change(["docs/whatever.rst", "notes.txt"]) is True
    assert is_doc_only_change([f"{_P}ui/x.md"]) is True  # a .md anywhere


def test_is_doc_only_change_false_for_code_or_mixed_or_empty():
    assert is_doc_only_change([f"{_P}ui/foo.py"]) is False
    assert is_doc_only_change(["spec.md", f"{_P}runtime/x.py"]) is False  # mixed
    assert is_doc_only_change([]) is False  # unknown → not doc-only (run the gate)
    assert is_doc_only_change(["pyproject.toml"]) is False  # config can affect tests


def test_affected_tests_skips_gate_for_doc_only(monkeypatch):
    # PI-148 case: a Design Work Task that writes only a spec .md must NOT run
    # (and time out) the full suite — the gate is skipped, verdict OK, no run.
    class _DocWorktree:
        path = "/tmp/fake-doc-wt"

        def changed_files(self, base_ref):
            return ["PRDs/product/crmbuilder-v2/pi-148-design.md"]

    called = {"n": 0}

    def _runner(wp, target):
        called["n"] += 1
        return TestRunResult(passed=True, returncode=0, target=target)

    rt = _runtime_for_affected_tests(monkeypatch, _runner)
    verdict, log_path = rt._run_affected_tests(_DocWorktree(), "WTK-1")
    assert verdict is VerifyOutcome.OK
    assert log_path is None
    assert called["n"] == 0  # the test runner was never invoked


# --------------------------------------------------------------------------
# PI-147 crash-tolerance: a signal-kill is a flaky harness crash, retried once;
# a real rc=1 test failure is not retried.
# --------------------------------------------------------------------------


def test_is_harness_crash_distinguishes_signal_from_test_failure():
    assert _is_harness_crash(139) is True  # SIGSEGV
    assert _is_harness_crash(134) is True  # SIGABRT
    assert _is_harness_crash(128) is True
    assert _is_harness_crash(1) is False  # a real pytest test failure
    assert _is_harness_crash(0) is False
    assert _is_harness_crash(5) is False  # pytest "no tests collected"
    assert _is_harness_crash(_TIMEOUT_RC) is False  # a timeout fails, not retried


def test_run_pytest_timeout_does_not_propagate(monkeypatch):
    # A test run that overruns the deadline must become a failing result, not an
    # unhandled exception that crashes the whole driver (the real 30-min incident).
    import subprocess as _sp

    from crmbuilder_v2.runtime import coordinating_runtime as cr

    def _boom(*a, **k):
        raise _sp.TimeoutExpired(cmd="pytest", timeout=1800, output="partial output")

    monkeypatch.setattr(cr.subprocess, "run", _boom)
    result = cr.run_pytest("/tmp/wt", "tests/crmbuilder_v2")
    assert result.passed is False
    assert result.returncode == _TIMEOUT_RC
    assert "timed out" in result.output


def test_run_pytest_splits_multi_package_target_into_separate_args(monkeypatch):
    # PI-200: select_test_target may return several space-separated packages for
    # a multi-subtree change — run_pytest must pass each as its own pytest path
    # arg, not one bogus space-joined path.
    from crmbuilder_v2.runtime import coordinating_runtime as cr

    captured = {}

    class _Proc:
        returncode = 0
        stdout = ""
        stderr = ""

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["timeout"] = kwargs.get("timeout")
        return _Proc()

    monkeypatch.setattr(cr.subprocess, "run", _fake_run)
    result = cr.run_pytest(
        "/tmp/wt", "tests/crmbuilder_v2/runtime tests/crmbuilder_v2/ui"
    )
    assert result.passed is True
    assert captured["cmd"] == [
        "uv", "run", "pytest",
        "tests/crmbuilder_v2/runtime", "tests/crmbuilder_v2/ui",
        "-q",
    ]


def test_run_pytest_default_timeout_is_raised_for_full_suite_backstop(monkeypatch):
    # PI-200: the default deadline backstops the residual full-suite fallback,
    # which outgrew the old 1800s kill — it must be larger than 1800s.
    from crmbuilder_v2.runtime import coordinating_runtime as cr

    captured = {}

    class _Proc:
        returncode = 0
        stdout = ""
        stderr = ""

    def _fake_run(cmd, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        return _Proc()

    monkeypatch.setattr(cr.subprocess, "run", _fake_run)
    cr.run_pytest("/tmp/wt", "tests/crmbuilder_v2")
    assert captured["timeout"] > 1800


def test_safe_run_tests_never_propagates():
    # Any runner exception (timeout or otherwise) becomes a failing result.
    import subprocess as _sp

    def _timeout_runner(wp, target):
        raise _sp.TimeoutExpired(cmd="pytest", timeout=1800)

    def _other_runner(wp, target):
        raise RuntimeError("kaboom")

    r1 = _safe_run_tests(_timeout_runner, "/tmp/wt", "tests/crmbuilder_v2")
    assert r1.passed is False and r1.returncode == _TIMEOUT_RC

    r2 = _safe_run_tests(_other_runner, "/tmp/wt", "tests/crmbuilder_v2")
    assert r2.passed is False and r2.returncode == 1


def test_affected_tests_timeout_fails_gracefully_no_retry(monkeypatch):
    # End-to-end: a runner that times out yields TESTS_FAILED (driver continues),
    # is NOT retried (timeout != crash), and never raises.
    import subprocess as _sp

    calls = {"n": 0}

    def _timeout_runner(wp, target):
        calls["n"] += 1
        raise _sp.TimeoutExpired(cmd="pytest", timeout=1800)

    rt = _runtime_for_affected_tests(monkeypatch, _timeout_runner)
    verdict, _ = rt._run_affected_tests(_FakeWorktree(has_commits=True), "WTK-1")
    assert verdict is VerifyOutcome.TESTS_FAILED
    assert calls["n"] == 1  # a timeout is a failure, not a retryable crash


class _StatefulRunner:
    """A fake test runner returning a scripted result per call (PI-147 retry)."""

    def __init__(self, results):
        self._results = list(results)
        self.calls = 0

    def __call__(self, worktree_path, target):
        result = self._results[self.calls]
        self.calls += 1
        return result


def _runtime_for_affected_tests(monkeypatch, runner):
    cfg = RuntimeConfig(target_work_task="WTK-099", dry_run=False)
    rt = CoordinatingRuntime(config=cfg, log=lambda m: None, test_runner_fn=runner)
    # Avoid touching the real verify-log dir in a unit test.
    monkeypatch.setattr(rt, "_persist_verify_output", lambda *a, **k: None)
    return rt


def test_affected_tests_retries_once_on_crash_then_passes(monkeypatch):
    runner = _StatefulRunner([
        TestRunResult(passed=False, returncode=139, target="t"),  # SIGSEGV
        TestRunResult(passed=True, returncode=0, target="t"),  # retry is clean
    ])
    rt = _runtime_for_affected_tests(monkeypatch, runner)
    verdict, _ = rt._run_affected_tests(_FakeWorktree(has_commits=True), "WTK-1")
    assert verdict is VerifyOutcome.OK
    assert runner.calls == 2  # crashed once, retried, passed


def test_affected_tests_fails_after_second_crash(monkeypatch):
    runner = _StatefulRunner([
        TestRunResult(passed=False, returncode=139, target="t"),
        TestRunResult(passed=False, returncode=134, target="t"),
    ])
    rt = _runtime_for_affected_tests(monkeypatch, runner)
    verdict, _ = rt._run_affected_tests(_FakeWorktree(has_commits=True), "WTK-1")
    assert verdict is VerifyOutcome.TESTS_FAILED
    assert runner.calls == 2  # two crashes → block


def test_affected_tests_real_failure_is_not_retried(monkeypatch):
    runner = _StatefulRunner([
        TestRunResult(passed=False, returncode=1, target="t"),  # real failure
        TestRunResult(passed=True, returncode=0, target="t"),  # must NOT run
    ])
    rt = _runtime_for_affected_tests(monkeypatch, runner)
    verdict, _ = rt._run_affected_tests(_FakeWorktree(has_commits=True), "WTK-1")
    assert verdict is VerifyOutcome.TESTS_FAILED
    assert runner.calls == 1  # a genuine rc=1 failure blocks immediately


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

    def changed_files(self, base_ref):
        return []  # PI-147: no git read in the fake → full-suite target

    def remove(self):
        self.removed = True


def _proc(rc=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=stdout, stderr=stderr)


def _pass_runner(worktree_path, target):
    """PI-147: a fake test runner that always passes (no subprocess)."""
    return TestRunResult(passed=True, returncode=0, target=target)


def _build_runtime(monkeypatch, *, assignment, task_after, has_commits, merge_result,
                   workstream=None, spawn_rc=0):
    """Wire a CoordinatingRuntime with all I/O seams stubbed."""
    cfg = RuntimeConfig(target_work_task="WTK-099", dry_run=False)
    rt = CoordinatingRuntime(config=cfg, spawn_fn=lambda p, wp: _proc(rc=spawn_rc),
                             log=lambda m: None, test_runner_fn=_pass_runner)

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


def test_pauses_and_flags_when_affected_tests_fail(monkeypatch):
    # PI-147: a lifecycle-clean task (Complete + commits) whose affected tests
    # are red must NOT merge — it routes through the existing fail path.
    task = {"work_task_identifier": "WTK-099", "work_task_status": "Ready"}
    rt = _build_runtime(
        monkeypatch,
        assignment=_assignment(task),
        task_after={"work_task_status": "Complete"},
        has_commits=True,
        merge_result=MergeResult(MergeStatus.CLEAN, "merged"),
    )
    rt.test_runner_fn = lambda wp, target: TestRunResult(
        passed=False, returncode=1, target=target, output="boom"
    )
    report = rt.run_one()
    assert report.result is StepResult.PAUSED
    assert report.verify is VerifyOutcome.TESTS_FAILED
    assert "WTK-099" in rt._flagged  # workstream flagged needs_attention
    assert rt._fake_wt.removed  # branch never merged


# --------------------------------------------------------------------------
# PI-157: verify-failure output persistence (serial site, fake runner — §5g)
# --------------------------------------------------------------------------


def _tests_failed_runtime(monkeypatch):
    task = {"work_task_identifier": "WTK-099", "work_task_status": "Ready"}
    return _build_runtime(
        monkeypatch,
        assignment=_assignment(task),
        task_after={"work_task_status": "Complete"},
        has_commits=True,
        merge_result=MergeResult(MergeStatus.CLEAN, "merged"),
    )


def test_verify_failure_persists_output_log(monkeypatch, tmp_path):
    rt = _tests_failed_runtime(monkeypatch)
    rt.test_runner_fn = lambda wp, target: TestRunResult(
        passed=False, returncode=1, target=target, output="FAILED test_x — boom"
    )
    monkeypatch.setattr(cr, "verify_log_dir", lambda: tmp_path / "verify")
    report = rt.run_one()
    assert report.verify is VerifyOutcome.TESTS_FAILED
    files = list((tmp_path / "verify").glob("WTK-099-*.log"))
    assert len(files) == 1
    text = files[0].read_text()
    assert "FAILED test_x" in text          # the captured pytest output
    assert "work_task:  WTK-099" in text    # the header fields
    assert "returncode: 1" in text
    assert report.verify_log_path == str(files[0])
    # The needs_attention reason carries the path — the operator never has to
    # know the directory convention.
    assert str(files[0]) in rt._flagged["WTK-099"]


def test_green_run_writes_no_verify_log(monkeypatch, tmp_path):
    rt = _tests_failed_runtime(monkeypatch)  # default _pass_runner stays
    monkeypatch.setattr(cr, "verify_log_dir", lambda: tmp_path / "verify")
    report = rt.run_one()
    assert report.result is StepResult.MERGED
    assert not (tmp_path / "verify").exists()  # directory not even created
    assert report.verify_log_path is None


def test_not_complete_verdict_writes_no_verify_log(monkeypatch, tmp_path):
    task = {"work_task_identifier": "WTK-099", "work_task_status": "Ready"}
    rt = _build_runtime(
        monkeypatch,
        assignment=_assignment(task),
        task_after={"work_task_status": "In Progress"},  # never reaches the test step
        has_commits=True,
        merge_result=MergeResult(MergeStatus.CLEAN, "merged"),
    )
    monkeypatch.setattr(cr, "verify_log_dir", lambda: tmp_path / "verify")
    report = rt.run_one()
    assert report.verify is VerifyOutcome.NOT_COMPLETE
    assert not (tmp_path / "verify").exists()
    assert report.verify_log_path is None
    assert "output:" not in rt._flagged["WTK-099"]  # no path to point at


def test_verify_log_write_failure_never_masks_tests_failed(monkeypatch, tmp_path):
    # §3.2 best-effort discipline: an OSError on the log write is itself logged
    # as a warning and never masks the TESTS_FAILED verdict; the flag reason
    # then carries no path (there is none to point at).
    rt = _tests_failed_runtime(monkeypatch)
    rt.test_runner_fn = lambda wp, target: TestRunResult(
        passed=False, returncode=1, target=target, output="FAILED test_x — boom"
    )
    blocker = tmp_path / "verify"
    blocker.write_text("a file where the log dir should go")  # mkdir → OSError
    monkeypatch.setattr(cr, "verify_log_dir", lambda: blocker)
    lines: list[str] = []
    rt.log = lines.append
    report = rt.run_one()
    assert report.result is StepResult.PAUSED
    assert report.verify is VerifyOutcome.TESTS_FAILED
    assert report.verify_log_path is None
    assert any("could not persist verify output" in ln for ln in lines)
    assert "output:" not in rt._flagged["WTK-099"]


def test_verify_log_filename_matches_spec_naming(monkeypatch, tmp_path):
    # §3.1: ``{work_task_id}-{UTC timestamp}.log`` — timestamped so a retry
    # after a fix writes a second file rather than overwriting the evidence.
    rt = _tests_failed_runtime(monkeypatch)
    rt.test_runner_fn = lambda wp, target: TestRunResult(
        passed=False, returncode=1, target=target, output="boom"
    )
    monkeypatch.setattr(cr, "verify_log_dir", lambda: tmp_path / "verify")
    rt.run_one()
    [logfile] = (tmp_path / "verify").iterdir()
    assert re.fullmatch(r"WTK-099-\d{8}T\d{6}Z\.log", logfile.name)


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


# --------------------------------------------------------------------------
# Real-API regression (WTK-082 / DEC-410)
#
# ``_flag_needs_attention`` must raise the human-escape flag on the Work Task's
# OWNING WORKSTREAM, not the Work Task — ``work_task`` has no needs_attention
# column, so PATCHing ``/work-tasks/{id}`` with those fields is rejected 422 and
# the flag silently never sets. Per DEC-410, an injected seam (monkeypatched
# ``_patch`` / ``_owning_workstream``) would never run the real route + Pydantic
# schema and so would never catch the 422; this drives the genuine HTTP path
# against a live uvicorn server bound to the per-test DB.
# --------------------------------------------------------------------------


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture
def live_api(v2_env):
    """A real uvicorn API on a socket, bound to the per-test database.

    The runtime talks to the API over genuine HTTP (``urllib``), so the real
    route + request schema must run behind a socket to reproduce the 422 — a
    ``TestClient`` or injected seam would bypass exactly the validation this
    regression guards (DEC-410).
    """
    from crmbuilder_v2.api.main import create_app

    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:  # pragma: no cover - startup failure is environmental
        raise RuntimeError("live API did not start")
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def _api(base: str, method: str, path: str, *, body: dict | None = None):
    """One HTTP round-trip to the live API, returning ``(status, json_body)``."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        base + path,
        data=data,
        method=method,
        headers={"X-Engagement": "ENG-001", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_flag_needs_attention_flags_owning_workstream_over_real_http(live_api):
    base = live_api

    # Seed a Workstream and a Work Task that belongs to it.
    status, ws = _api(
        base,
        "POST",
        "/workstreams",
        body={"workstream_phase_type": "Development", "workstream_title": "WTK-082"},
    )
    assert status == 201, ws
    ws_id = ws["data"]["workstream_identifier"]

    status, wt = _api(
        base,
        "POST",
        "/work-tasks",
        body={"work_task_title": "do a thing", "work_task_area": "api"},
    )
    assert status == 201, wt
    wt_id = wt["data"]["work_task_identifier"]

    status, edge = _api(
        base,
        "POST",
        "/references",
        body={
            "source_type": "work_task",
            "source_id": wt_id,
            "target_type": "workstream",
            "target_id": ws_id,
            "relationship": "work_task_belongs_to_workstream",
        },
    )
    assert status == 201, edge

    # The bug this guards: the Work Task has no needs_attention column, so the
    # old PATCH /work-tasks/{id} with these fields is rejected 422.
    status, _ = _api(
        base,
        "PATCH",
        f"/work-tasks/{wt_id}",
        body={
            "work_task_needs_attention": True,
            "work_task_needs_attention_reason": "x",
        },
    )
    assert status == 422  # documents why the flag must target the Workstream

    # Drive the real runtime helper over HTTP — no seam: real _owning_workstream
    # + real _patch + real route/schema.
    logs: list[str] = []
    rt = CoordinatingRuntime(
        config=RuntimeConfig(api_base=base, engagement="ENG-001"), log=logs.append
    )
    rt._flag_needs_attention(
        wt_id, "verification failed: not_complete (agent rc=1)"
    )

    # No 422 swallowed: the best-effort except would have logged this warning.
    assert not any("could not flag needs_attention" in m for m in logs), logs

    # The OWNING WORKSTREAM ends flagged, with the reason populated.
    status, refreshed = _api(base, "GET", f"/workstreams/{ws_id}")
    assert status == 200, refreshed
    assert refreshed["data"]["workstream_needs_attention"] is True
    assert "verification failed" in (
        refreshed["data"]["workstream_needs_attention_reason"] or ""
    )

    # The Work Task itself was never touched with the bogus fields.
    status, wt_after = _api(base, "GET", f"/work-tasks/{wt_id}")
    assert status == 200, wt_after
    assert not wt_after["data"].get("work_task_needs_attention")

"""ADO orchestration driver (PI-143 slices 1–2) — pure decisions + the loop.

Mirrors the module's pure/I-O split:

* **pure decision** — :func:`decide_next` is exercised directly for every outcome
  (pause / done / scope / start / blocked) and their precedence, no I/O;
* **the loop** — the substrate HTTP seams (``_get`` / ``_post`` /
  ``_patch_pi_status``), the scoping-agent seam, the Develop-gate seam, and the
  pool runner are all injected against an in-memory fake of the PM/Lead/decompose
  substrate, so the orchestration is proven (dispatch → decompose → per-phase
  scope → start → run → complete → advance) without a server or a real agent.
"""

from __future__ import annotations

import io
import urllib.error

from crmbuilder_v2.scheduler import ado_scheduler as ado
from crmbuilder_v2.scheduler.ado_scheduler import (
    AdoRunReport,
    AdoScheduler,
    AdoSchedulerConfig,
    ProjectScheduler,
    ProjectSchedulerConfig,
    StepKind,
    decide_next,
    eligible_batch,
    select_next_pi,
)
from crmbuilder_v2.scheduler.parallel_scheduler import PoolRunReport
from crmbuilder_v2.scheduler.reconciliation import GateDecision
from crmbuilder_v2.scheduler.task_contract import TaskStatus

_TERMINAL = {"Complete", "Not Applicable"}
_PHASE_TYPES = ["Design", "Develop", "Test"]


# --------------------------------------------------------------------------
# pure decision
# --------------------------------------------------------------------------


def _phase(wsid, status, ptype="Design", preds_ok=True, attention=False):
    return {
        "workstream": {"workstream_identifier": wsid, "workstream_needs_attention": attention},
        "status": status,
        "phase_type": ptype,
        "predecessors_terminal": preds_ok,
        "blocked_by": [],
    }


def _ov(phases=(), all_terminal=False, attention=()):
    return {
        "decomposed": bool(phases),
        "phases": list(phases),
        "all_terminal": all_terminal,
        "needs_attention": list(attention),
    }


def test_decide_scope_when_phase_is_planned():
    step = decide_next(_ov([_phase("WSK-1", "Planned")]))
    assert step.kind is StepKind.SCOPE and step.workstream == "WSK-1"
    assert step.phase_type == "Design"


def test_decide_start_when_phase_is_ready():
    step = decide_next(_ov([_phase("WSK-1", "Ready")]))
    assert step.kind is StepKind.START and step.workstream == "WSK-1"


def test_decide_skips_terminal_phases_to_the_next_actionable():
    step = decide_next(_ov([
        _phase("WSK-1", "Complete"),
        _phase("WSK-2", "Planned", ptype="Develop"),
    ]))
    assert step.kind is StepKind.SCOPE and step.workstream == "WSK-2"


def test_decide_done_when_all_terminal():
    assert decide_next(_ov([_phase("WSK-1", "Complete")], all_terminal=True)).kind is StepKind.DONE


def test_decide_blocked_when_not_decomposed():
    assert decide_next(_ov([])).kind is StepKind.BLOCKED


def test_attention_takes_precedence():
    step = decide_next(_ov([_phase("WSK-1", "Ready", attention=True)], attention=["WSK-1"]))
    assert step.kind is StepKind.PAUSE and "WSK-1" in step.reason


def test_decide_resume_when_phase_is_in_progress():
    # PI-157 §5a: an interrupted run's In Progress phase is adopted, not refused.
    step = decide_next(_ov([_phase("WSK-1", "In Progress")]))
    assert step.kind is StepKind.RESUME and step.workstream == "WSK-1"
    assert step.phase_type == "Design"


def test_decide_blocked_when_in_progress_predecessors_not_terminal():
    step = decide_next(_ov([_phase("WSK-1", "In Progress", preds_ok=False)]))
    assert step.kind is StepKind.BLOCKED  # the unchanged guard still wins


def test_decide_scoping_phase_stays_blocked():
    # A Scoping row persisted between runs is a crash mid-scope — a person looks.
    step = decide_next(_ov([_phase("WSK-1", "Scoping")]))
    assert step.kind is StepKind.BLOCKED and "Scoping" in step.reason


def test_attention_takes_precedence_over_resume():
    step = decide_next(
        _ov([_phase("WSK-1", "In Progress", attention=True)], attention=["WSK-1"])
    )
    assert step.kind is StepKind.PAUSE


# --------------------------------------------------------------------------
# the loop — driven against an in-memory substrate fake
# --------------------------------------------------------------------------


class _World:
    """A minimal stand-in for the PM/Lead/decompose substrate state."""

    def __init__(self, n_phases=3):
        self.pi_status = "Draft"
        self.decomposed = False
        self.phase_ids = [f"WSK-{i + 1}" for i in range(n_phases)]
        self.phase_type = {pid: _PHASE_TYPES[i] for i, pid in enumerate(self.phase_ids)}
        self.phase_status = dict.fromkeys(self.phase_ids, "Planned")
        self.attention: set[str] = set()
        self.calls: list[str] = []
        # PI-157 RESUME state: per-task rows + the recorded release/PATCH calls.
        self.tasks: dict[str, dict] = {}        # wtid -> {workstream, status, claimed_by}
        self.released: list[tuple[str, str]] = []   # (wtid, claimed_by echoed)
        self.patches: list[tuple[str, str]] = []    # (wtid, new status), in order

    def add_task(self, ws, wtid, status, claimed_by=None):
        self.tasks[wtid] = {"workstream": ws, "status": status, "claimed_by": claimed_by}

    def overview(self):
        if not self.decomposed:
            return _ov([])
        phases = []
        for i, p in enumerate(self.phase_ids):
            preds_ok = all(self.phase_status[q] in _TERMINAL for q in self.phase_ids[:i])
            phases.append(_phase(
                p, self.phase_status[p], self.phase_type[p], preds_ok, p in self.attention
            ))
        return _ov(
            phases,
            all_terminal=all(self.phase_status[p] in _TERMINAL for p in self.phase_ids),
            attention=[p for p in self.phase_ids if p in self.attention],
        )


class _FakeDriver(AdoScheduler):
    """AdoScheduler with the HTTP seams routed to a :class:`_World`."""

    def __init__(self, world, **kw):
        super().__init__(**kw)
        self.world = world
        if "reconcile_runner" not in kw:
            self.reconcile_runner = lambda c, w: None  # no real agent under test
        if "unmerged_check" not in kw:
            self.unmerged_check = lambda c, t: False  # no real git under test

    def _get(self, path):
        if path.endswith("/phase-overview"):
            return self.world.overview()
        if path.startswith("/references?"):
            ws = path.split("target_id=")[1].split("&")[0]
            return [
                {"source_id": tid, "source_type": "work_task", "target_id": ws}
                for tid, t in self.world.tasks.items() if t["workstream"] == ws
            ]
        if path.startswith("/work-tasks/"):
            tid = path.split("/")[2]
            t = self.world.tasks[tid]
            return {
                "work_task_identifier": tid,
                "work_task_status": t["status"],
                "work_task_claimed_by": t.get("claimed_by"),
            }
        return {"status": self.world.pi_status}  # GET /planning-items/{id}

    def _post(self, path, body=None):
        self.world.calls.append(path)
        if path.endswith("/dispatch"):
            self.world.pi_status = "In Progress"
        elif path.endswith("/decompose"):
            self.world.decomposed = True  # phases stay Planned until scoped
        elif path.endswith("/start-execution"):
            self.world.phase_status[path.split("/")[2]] = "In Progress"
        elif path.endswith("/complete-phase"):
            self.world.phase_status[path.split("/")[2]] = "Complete"
        elif path.endswith("/release"):
            tid = path.split("/")[2]
            self.world.released.append((tid, (body or {}).get("claimed_by")))
            self.world.tasks[tid]["claimed_by"] = None
        return {}

    def _patch(self, path, body):
        self.world.calls.append(f"PATCH {path}")
        if path.startswith("/work-tasks/"):
            tid = path.split("/")[2]
            self.world.patches.append((tid, body["work_task_status"]))
            self.world.tasks[tid]["status"] = body["work_task_status"]
        return {}

    def _patch_pi_status(self, status):
        self.world.pi_status = status


def _cfg(**kw):
    kw.setdefault("log", lambda _m: None)
    return AdoSchedulerConfig(planning_item="PI-900", **kw)


def _clean_pool(cfg, ws):
    return PoolRunReport(paused=False)


def _open_gate(cfg, ws):
    return GateDecision(True, "ok")


def _scopes_to_ready(world):
    """A fake Architect: scoping a phase makes it Ready (Work Tasks created)."""
    def _runner(cfg, ws, phase_type):
        world.calls.append(f"scope:{ws}")
        world.phase_status[ws] = "Ready"
    return _runner


def test_run_pool_for_workstream_builds_a_valid_config(monkeypatch):
    # Regression: the default pool seam must construct a real ParallelSchedulerConfig
    # (no bad kwargs) and pass `log` to the runtime, not the config. Faked tests
    # inject pool_runner and never exercise this, so a live run was the only path
    # that caught `log=` being passed to the config.
    captured = {}

    class _FakePool:
        def __init__(self, config, repo_lock=None, log=None):
            captured["config"] = config
            captured["log"] = log
            captured["repo_lock"] = repo_lock

        def run(self):
            return PoolRunReport(paused=False)

    monkeypatch.setattr(ado, "ParallelCoordinatingScheduler", _FakePool)
    cfg = AdoSchedulerConfig(planning_item="PI-1", log=lambda _m: None)
    report = ado.run_pool_for_workstream(cfg, "WSK-1")
    assert report.paused is False
    # real ParallelSchedulerConfig built (would TypeError on a bad kwarg), and log
    # routed to the runtime instance, not the config.
    assert captured["log"] is cfg.log
    assert captured["config"].target_workstream == "WSK-1"


def test_spawn_scoping_agent_degrades_on_timeout(monkeypatch):
    # Regression: an API-only agent (scope/reconcile/review) that overruns or
    # fails to spawn must return None, not raise — a crashed agent crashed the
    # whole PM run in rung 5 before this.
    import subprocess

    def _timeout(*a, **k):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=1)

    monkeypatch.setattr(subprocess, "run", _timeout)
    assert ado.spawn_scoping_agent("prompt", timeout=1) is None


def test_review_close_pi_verifies_by_result(monkeypatch):
    # Even when the closure agent fails/overruns (spawn → None), the outcome is
    # decided by the PI's actual status, not the subprocess.
    monkeypatch.setattr(ado, "spawn_scoping_agent", lambda *a, **k: None)
    cfg = ProjectSchedulerConfig(project="PRJ-9", log=lambda _m: None)

    monkeypatch.setattr(ado.dispatcher, "_get", lambda *a, **k: {"status": "Resolved"})
    assert ado.review_close_pi(cfg, "PI-1") is True

    monkeypatch.setattr(ado.dispatcher, "_get", lambda *a, **k: {"status": "In Review"})
    assert ado.review_close_pi(cfg, "PI-1") is False


def test_drives_all_phases_scope_then_execute():
    world = _World(3)
    driver = _FakeDriver(
        world, config=_cfg(),
        pool_runner=_clean_pool, scope_runner=_scopes_to_ready(world), gate_checker=_open_gate,
    )
    report = driver.run()
    assert report.status is TaskStatus.SUCCEEDED
    assert report.completed_phases == ["WSK-1", "WSK-2", "WSK-3"]
    assert world.pi_status == "In Review"
    # every phase was scoped before it was started.
    for ws in world.phase_ids:
        assert world.calls.index(f"scope:{ws}") < world.calls.index(f"/workstreams/{ws}/start-execution")


def test_incomplete_phase_halts_this_pi_not_the_whole_run():
    # REQ-422: the pool drained without pausing, but the phase cannot complete
    # (a Work Task left not Complete — e.g. reverted out-of-band by a concurrent
    # runtime), so complete-phase 409s. An uncaught 409 used to crash the whole
    # multi-PI run; now the driver catches it and halts THIS planning item
    # gracefully (NEEDS_HUMAN), surfacing the 409 detail.
    world = _World(1)
    world.pi_status = "In Progress"
    world.decomposed = True
    world.phase_status["WSK-1"] = "Ready"

    class _Driver(_FakeDriver):
        def _post(self, path, body=None):
            if path.endswith("/complete-phase"):
                raise urllib.error.HTTPError(
                    path, 409,
                    "workstream 'WSK-1' has non-Complete Work Task(s) ['WTK-2']",
                    {}, io.BytesIO(b"non-Complete Work Task(s) ['WTK-2']"),
                )
            return super()._post(path, body)

    driver = _Driver(
        world, config=_cfg(),
        pool_runner=_clean_pool, scope_runner=_scopes_to_ready(world),
        gate_checker=_open_gate,
    )
    report = driver.run()
    assert report.status is TaskStatus.NEEDS_HUMAN
    assert "cannot complete" in report.reason
    # the run did not crash, and the phase was not marked complete.
    assert world.phase_status["WSK-1"] != "Complete"


def test_reconcile_runs_after_design_only():
    world = _World(3)  # Design, Develop, Test
    reconciled: list[str] = []
    driver = _FakeDriver(
        world, config=_cfg(),
        pool_runner=_clean_pool, scope_runner=_scopes_to_ready(world), gate_checker=_open_gate,
        reconcile_runner=lambda c, w: reconciled.append(w),
    )
    report = driver.run()
    assert report.status is TaskStatus.SUCCEEDED
    # reconciliation ran exactly once, over the Design phase (WSK-1).
    assert reconciled == ["WSK-1"]


def test_not_applicable_phase_is_skipped():
    world = _World(2)
    world.pi_status = "In Progress"
    world.decomposed = True

    def _na_first(cfg, ws, phase_type):
        world.phase_status[ws] = "Not Applicable" if ws == "WSK-1" else "Ready"

    driver = _FakeDriver(
        world, config=_cfg(),
        pool_runner=_clean_pool, scope_runner=_na_first, gate_checker=_open_gate,
    )
    report = driver.run()
    assert report.status is TaskStatus.SUCCEEDED
    # WSK-1 was Not Applicable → never started; WSK-2 executed.
    assert "/workstreams/WSK-1/start-execution" not in world.calls
    assert report.completed_phases == ["WSK-2"]


def test_pauses_when_scoping_does_not_complete():
    world = _World(1)
    world.pi_status = "In Progress"
    world.decomposed = True

    def _scope_noop(cfg, ws, phase_type):
        world.calls.append(f"scope:{ws}")  # leaves the phase Planned

    driver = _FakeDriver(
        world, config=_cfg(),
        pool_runner=_clean_pool, scope_runner=_scope_noop, gate_checker=_open_gate,
    )
    report = driver.run()
    assert report.status is TaskStatus.NEEDS_HUMAN and "scope" in report.reason.lower()


def test_scoping_retries_once_then_succeeds():
    # Per-agent retry: a scoping agent that leaves the phase 'Planned' on the
    # first attempt is re-spawned once; if the retry drives it Ready, the driver
    # proceeds instead of pausing (the dominant transient-incompletion case).
    world = _World(1)
    world.pi_status = "In Progress"
    world.decomposed = True
    calls = {"n": 0}

    def _flaky_scope(cfg, ws, phase_type):
        calls["n"] += 1
        if calls["n"] >= 2:  # the retry succeeds
            world.phase_status[ws] = "Ready"
        # first attempt leaves the phase Planned

    driver = _FakeDriver(
        world, config=_cfg(),
        pool_runner=_clean_pool, scope_runner=_flaky_scope, gate_checker=_open_gate,
    )
    report = driver.run()
    assert report.status is TaskStatus.SUCCEEDED
    assert calls["n"] == 2  # scoped once, retried once → succeeded


def test_develop_gate_holds_on_open_blocking_finding():
    world = _World(2)
    world.pi_status = "In Progress"
    world.decomposed = True
    world.phase_status = {"WSK-1": "Complete", "WSK-2": "Ready"}  # Design done, Develop ready
    held = GateDecision(False, "open blocking findings ['FND-1']", open_blocking=["FND-1"])
    driver = _FakeDriver(
        world, config=_cfg(),
        pool_runner=_clean_pool, scope_runner=_scopes_to_ready(world),
        gate_checker=lambda c, w: held,
    )
    report = driver.run()
    assert report.status is TaskStatus.NEEDS_HUMAN and "gate held" in report.reason.lower()
    # the Develop phase was never started.
    assert "/workstreams/WSK-2/start-execution" not in world.calls


def test_develop_gate_consulted_only_for_develop():
    # A Design phase (first) does not consult the gate; only Develop does.
    world = _World(2)
    world.pi_status = "In Progress"
    world.decomposed = True
    world.phase_status = {"WSK-1": "Ready", "WSK-2": "Planned"}
    seen: list[str] = []
    driver = _FakeDriver(
        world, config=_cfg(),
        pool_runner=_clean_pool, scope_runner=_scopes_to_ready(world),
        gate_checker=lambda c, w: (seen.append(w) or GateDecision(True, "ok")),
    )
    report = driver.run()
    assert report.status is TaskStatus.SUCCEEDED
    assert seen == ["WSK-2"]  # only the Develop phase was gate-checked


def test_pauses_when_the_pool_pauses():
    world = _World(1)
    world.pi_status = "In Progress"
    world.decomposed = True
    world.phase_status["WSK-1"] = "Ready"
    driver = _FakeDriver(
        world, config=_cfg(),
        pool_runner=lambda c, w: PoolRunReport(paused=True),
        scope_runner=_scopes_to_ready(world), gate_checker=_open_gate,
    )
    report = driver.run()
    assert report.status is TaskStatus.NEEDS_HUMAN and "WSK-1" in report.reason


def test_orchestrator_does_not_advance_phase_when_pool_rolls_back():
    # PI-145 (a)/(c) "phase not advanced": an atomic-rollback pool report is
    # paused, so the orchestrator short-circuits on `report.paused` — it never
    # POSTs /complete-phase, leaving the phase un-advanced for a human (the
    # rollback already restored main).
    world = _World(1)
    world.pi_status = "In Progress"
    world.decomposed = True
    world.phase_status["WSK-1"] = "Ready"
    rolled_back = PoolRunReport(
        paused=True,
        rolled_back=True,
        rolled_back_to="abc1234",
        pre_phase_head="abc1234",
    )
    driver = _FakeDriver(
        world, config=_cfg(),
        pool_runner=lambda c, w: rolled_back,
        scope_runner=_scopes_to_ready(world), gate_checker=_open_gate,
    )
    report = driver.run()
    assert report.status is TaskStatus.NEEDS_HUMAN
    assert not any("complete-phase" in c for c in world.calls)
    assert world.phase_status["WSK-1"] != "Complete"


def test_resume_without_redispatch_and_dry_run():
    # resume: already In Progress + decomposed → no dispatch/decompose re-issued.
    world = _World(1)
    world.pi_status = "In Progress"
    world.decomposed = True
    driver = _FakeDriver(
        world, config=_cfg(dry_run=True),
        pool_runner=_clean_pool, scope_runner=_scopes_to_ready(world), gate_checker=_open_gate,
    )
    report = driver.run()
    assert report.dry_run is True and report.status is TaskStatus.NOT_STARTED
    assert "/planning-items/PI-900/dispatch" not in world.calls
    assert not any("start-execution" in c for c in world.calls)


# --------------------------------------------------------------------------
# PI-157 — the RESUME recovery pass (the two 06-11-26 production shapes + table)
# --------------------------------------------------------------------------


def _resume_world(n_phases=1):
    """A world whose (first) phase an interrupted run left In Progress."""
    world = _World(n_phases)
    world.pi_status = "In Progress"
    world.decomposed = True
    world.phase_status["WSK-1"] = "In Progress"
    return world


def test_resume_all_tasks_complete_auto_completes_phase():
    # PI-153/WSK-072 shape (§5b): every task Complete, the run died before
    # complete-phase. RESUME issues complete-phase directly — no pool run, no
    # start-execution, no Workstream status write besides complete-phase.
    world = _resume_world()
    world.add_task("WSK-1", "WTK-1", "Complete")
    world.add_task("WSK-1", "WTK-2", "Complete")
    pool_calls = []
    driver = _FakeDriver(
        world, config=_cfg(),
        pool_runner=lambda c, w: pool_calls.append(w) or PoolRunReport(paused=False),
        scope_runner=_scopes_to_ready(world), gate_checker=_open_gate,
    )
    report = driver.run()
    assert report.status is TaskStatus.SUCCEEDED
    assert report.completed_phases == ["WSK-1"]
    assert pool_calls == []
    assert "/workstreams/WSK-1/start-execution" not in world.calls
    assert "/workstreams/WSK-1/complete-phase" in world.calls
    assert not any(c.startswith("PATCH /workstreams") for c in world.calls)
    assert world.pi_status == "In Review"


def test_resume_partial_completion_releases_stale_claim_and_runs_pool():
    # PI-150/WSK-076 shape (§5c): task A Complete, task B stale-claimed. RESUME
    # releases B with B's RECORDED claimant, rewinds Claimed → Ready, runs the
    # pool — with no start-execution and no Workstream rewind PATCH.
    world = _resume_world()
    world.add_task("WSK-1", "WTK-1", "Complete")
    world.add_task("WSK-1", "WTK-2", "Claimed", claimed_by="AGP-other-identity")
    pool_calls = []

    def _pool(cfg, ws):
        pool_calls.append(ws)
        world.tasks["WTK-2"]["status"] = "Complete"
        return PoolRunReport(paused=False)

    driver = _FakeDriver(
        world, config=_cfg(),
        pool_runner=_pool, scope_runner=_scopes_to_ready(world), gate_checker=_open_gate,
    )
    report = driver.run()
    assert report.status is TaskStatus.SUCCEEDED
    assert world.released == [("WTK-2", "AGP-other-identity")]
    assert world.patches == [("WTK-2", "Ready")]
    assert pool_calls == ["WSK-1"]
    assert "/workstreams/WSK-1/start-execution" not in world.calls
    assert "/workstreams/WSK-1/complete-phase" in world.calls
    assert not any(c.startswith("PATCH /workstreams") for c in world.calls)


def test_resume_ready_claimed_row_releases_without_status_patch():
    # A pre-PI-137-shaped row: claim attached without the Claimed status.
    world = _resume_world()
    world.add_task("WSK-1", "WTK-1", "Ready", claimed_by="AGP-x")
    driver = _FakeDriver(
        world, config=_cfg(),
        pool_runner=_clean_pool, scope_runner=_scopes_to_ready(world), gate_checker=_open_gate,
    )
    report = driver.run()
    assert report.status is TaskStatus.SUCCEEDED
    assert world.released == [("WTK-1", "AGP-x")]
    assert world.patches == []  # already Ready — release only


def test_resume_in_progress_task_rewinds_via_failed():
    # §5d: no legal In Progress → Ready transition — the recorded sequence is
    # release, then In Progress → Failed, then Failed → Ready, in that order.
    world = _resume_world()
    world.add_task("WSK-1", "WTK-1", "In Progress", claimed_by="AGP-x")
    driver = _FakeDriver(
        world, config=_cfg(),
        pool_runner=_clean_pool, scope_runner=_scopes_to_ready(world), gate_checker=_open_gate,
    )
    report = driver.run()
    assert report.status is TaskStatus.SUCCEEDED
    assert world.released == [("WTK-1", "AGP-x")]
    assert world.patches == [("WTK-1", "Failed"), ("WTK-1", "Ready")]


def test_resume_failed_and_planned_tasks_re_readied():
    world = _resume_world()
    world.add_task("WSK-1", "WTK-1", "Failed")           # unclaimed retry path
    world.add_task("WSK-1", "WTK-2", "Planned")          # scoped after start
    driver = _FakeDriver(
        world, config=_cfg(),
        pool_runner=_clean_pool, scope_runner=_scopes_to_ready(world), gate_checker=_open_gate,
    )
    report = driver.run()
    assert report.status is TaskStatus.SUCCEEDED
    assert world.released == []  # no claims to release
    assert world.patches == [("WTK-1", "Ready"), ("WTK-2", "Ready")]


def test_resume_blocked_task_pauses_not_guesses():
    # §5e: a person parked it; RESUME must not auto-unblock.
    world = _resume_world()
    world.add_task("WSK-1", "WTK-1", "Blocked")
    pool_calls = []
    driver = _FakeDriver(
        world, config=_cfg(),
        pool_runner=lambda c, w: pool_calls.append(w) or PoolRunReport(paused=False),
        scope_runner=_scopes_to_ready(world), gate_checker=_open_gate,
    )
    report = driver.run()
    assert report.status is TaskStatus.NEEDS_HUMAN
    assert "WTK-1" in report.reason and "Blocked" in report.reason
    assert pool_calls == []
    assert world.patches == []  # the Blocked task was never PATCHed


def test_resume_unmerged_complete_residue_pauses():
    # §5e/§2.6: a Complete task whose branch was un-merged by a PI-145 rollback
    # pauses with the residue reason — no auto-re-merge, no complete-phase.
    world = _resume_world()
    world.add_task("WSK-1", "WTK-1", "Complete")
    driver = _FakeDriver(
        world, config=_cfg(),
        pool_runner=_clean_pool, scope_runner=_scopes_to_ready(world), gate_checker=_open_gate,
        unmerged_check=lambda c, t: True,
    )
    report = driver.run()
    assert report.status is TaskStatus.NEEDS_HUMAN
    assert "WTK-1" in report.reason and "rollback residue" in report.reason
    assert "/workstreams/WSK-1/complete-phase" not in world.calls


def test_resume_develop_gate_rechecked():
    # §2.4: a Develop phase resuming consults the gate exactly as START does.
    world = _World(2)
    world.pi_status = "In Progress"
    world.decomposed = True
    world.phase_status = {"WSK-1": "Complete", "WSK-2": "In Progress"}  # Develop resuming
    world.add_task("WSK-2", "WTK-1", "Ready")
    held = GateDecision(False, "open blocking findings ['FND-9']", open_blocking=["FND-9"])
    driver = _FakeDriver(
        world, config=_cfg(),
        pool_runner=_clean_pool, scope_runner=_scopes_to_ready(world),
        gate_checker=lambda c, w: held,
    )
    report = driver.run()
    assert report.status is TaskStatus.NEEDS_HUMAN and "gate held" in report.reason.lower()


def test_resume_idempotent_after_second_pause():
    # §5f: a resume that pauses again leaves the phase In Progress with the task
    # states recorded; a fresh driver RESUMEs again from exactly there.
    world = _resume_world()
    world.add_task("WSK-1", "WTK-1", "Complete")
    world.add_task("WSK-1", "WTK-2", "Claimed", claimed_by="AGP-x")

    def _pausing_pool(cfg, ws):
        # A second verify failure: the pool's agent died mid-task again.
        world.tasks["WTK-2"].update(status="In Progress", claimed_by="AGP-x")
        return PoolRunReport(paused=True)

    first = _FakeDriver(
        world, config=_cfg(),
        pool_runner=_pausing_pool, scope_runner=_scopes_to_ready(world), gate_checker=_open_gate,
    )
    assert first.run().status is TaskStatus.NEEDS_HUMAN
    assert world.phase_status["WSK-1"] == "In Progress"  # never rewound

    def _clean_second(cfg, ws):
        world.tasks["WTK-2"]["status"] = "Complete"
        return PoolRunReport(paused=False)

    second = _FakeDriver(
        world, config=_cfg(),
        pool_runner=_clean_second, scope_runner=_scopes_to_ready(world), gate_checker=_open_gate,
    )
    report = second.run()
    assert report.status is TaskStatus.SUCCEEDED
    # The second pass released the new stale claim and rewound via Failed.
    assert world.released[-1] == ("WTK-2", "AGP-x")
    assert world.patches[-2:] == [("WTK-2", "Failed"), ("WTK-2", "Ready")]


def test_resume_mid_sequence_then_later_phases_follow_normally():
    # §2.4: a run interrupted mid-PI resumes mid-sequence — earlier terminal
    # phases skip, the In Progress phase RESUMEs (no start-execution), and the
    # later phases follow normally (SCOPE → START) once it completes.
    world = _World(3)  # Design, Develop, Test
    world.pi_status = "In Progress"
    world.decomposed = True
    world.phase_status = {"WSK-1": "Complete", "WSK-2": "In Progress", "WSK-3": "Planned"}
    world.add_task("WSK-2", "WTK-1", "Ready")
    pool_calls = []

    def _pool(cfg, ws):
        pool_calls.append(ws)
        if ws == "WSK-2":
            world.tasks["WTK-1"]["status"] = "Complete"
        return PoolRunReport(paused=False)

    driver = _FakeDriver(
        world, config=_cfg(),
        pool_runner=_pool, scope_runner=_scopes_to_ready(world), gate_checker=_open_gate,
    )
    report = driver.run()
    assert report.status is TaskStatus.SUCCEEDED
    assert report.completed_phases == ["WSK-2", "WSK-3"]
    assert pool_calls == ["WSK-2", "WSK-3"]
    # The resumed phase was never re-opened or re-scoped; the following phase
    # went through the unchanged SCOPE → START path.
    assert "/workstreams/WSK-2/start-execution" not in world.calls
    assert "scope:WSK-2" not in world.calls
    assert "scope:WSK-3" in world.calls
    assert "/workstreams/WSK-3/start-execution" in world.calls
    assert world.pi_status == "In Review"


def test_resume_develop_gate_open_proceeds_to_pool():
    # §2.4 complement to the held case: a resuming Develop phase consults the
    # gate, and an open gate lets the pool run and the phase complete.
    world = _World(2)
    world.pi_status = "In Progress"
    world.decomposed = True
    world.phase_status = {"WSK-1": "Complete", "WSK-2": "In Progress"}  # Develop resuming
    world.add_task("WSK-2", "WTK-1", "Ready")
    seen: list[str] = []
    pool_calls = []

    def _pool(cfg, ws):
        pool_calls.append(ws)
        world.tasks["WTK-1"]["status"] = "Complete"
        return PoolRunReport(paused=False)

    driver = _FakeDriver(
        world, config=_cfg(),
        pool_runner=_pool, scope_runner=_scopes_to_ready(world),
        gate_checker=lambda c, w: (seen.append(w) or GateDecision(True, "ok")),
    )
    report = driver.run()
    assert report.status is TaskStatus.SUCCEEDED
    assert seen == ["WSK-2"]  # the gate WAS consulted on resume
    assert pool_calls == ["WSK-2"]
    assert "/workstreams/WSK-2/start-execution" not in world.calls


def test_resume_residue_guard_checks_only_complete_tasks():
    # §2.6: the rollback-residue guard costs two git reads per COMPLETE task —
    # it is never consulted for a task in any other state.
    world = _resume_world()
    world.add_task("WSK-1", "WTK-1", "Complete")
    world.add_task("WSK-1", "WTK-2", "Ready")
    world.add_task("WSK-1", "WTK-3", "Failed")
    checked: list[str] = []
    driver = _FakeDriver(
        world, config=_cfg(),
        pool_runner=_clean_pool, scope_runner=_scopes_to_ready(world), gate_checker=_open_gate,
        unmerged_check=lambda c, t: (checked.append(t) or False),
    )
    report = driver.run()
    assert report.status is TaskStatus.SUCCEEDED
    assert checked == ["WTK-1"]


# --------------------------------------------------------------------------
# slice 3 — PM auto-dispatch over a Project backlog
# --------------------------------------------------------------------------

_STARTABLE = {"Draft", "Decomposed", "Ready"}


def test_select_next_pi_skips_attempted():
    backlog = {"eligible": ["PI-1", "PI-2"]}
    assert select_next_pi(backlog, {}) == "PI-1"
    assert select_next_pi(backlog, {"PI-1": "paused"}) == "PI-2"
    assert select_next_pi(backlog, {"PI-1": "x", "PI-2": "y"}) is None


class _Backlog:
    """In-memory Project backlog: PI statuses + blocked_by, eligibility derived."""

    def __init__(self, pis, blocked_by=None):
        self.pis = dict(pis)                       # pid -> status
        self.blocked_by = blocked_by or {}         # pid -> [blockers]

    def snapshot(self):
        eligible, blocked = [], []
        for pid, st in self.pis.items():
            unresolved = [b for b in self.blocked_by.get(pid, []) if self.pis.get(b) != "Resolved"]
            if st in _STARTABLE and not unresolved:
                eligible.append(pid)
            elif st in _STARTABLE and unresolved:
                blocked.append(pid)
        return {
            "eligible": eligible,
            "blocked": blocked,
            "all_resolved": all(s == "Resolved" for s in self.pis.values()),
        }


class _FakePm(ProjectScheduler):
    def __init__(self, backlog, **kw):
        super().__init__(**kw)
        self.backlog = backlog

    def _backlog(self):
        return self.backlog.snapshot()

    def _resolve_pi(self, pi):
        self.backlog.pis[pi] = "Resolved"


_OUTCOME_STATUS = {"complete": TaskStatus.SUCCEEDED, "paused": TaskStatus.NEEDS_HUMAN}


def _pi_driver(backlog, outcomes=None):
    """Fake per-PI driver: reflects the outcome into the backlog and reports it.

    ``outcomes`` is keyed by the test-facing words ("complete"/"paused"); the
    driver maps them onto the uniform ``TaskStatus`` the report carries."""
    outcomes = outcomes or {}

    def _driver(ado_cfg):
        pid = ado_cfg.planning_item
        word, reason = outcomes.get(pid, ("complete", None))
        backlog.pis[pid] = "In Review" if word == "complete" else "In Progress"
        return AdoRunReport(
            planning_item=pid, status=_OUTCOME_STATUS[word], reason=reason
        )

    return _driver


def _pm_cfg(**kw):
    kw.setdefault("log", lambda _m: None)
    return ProjectSchedulerConfig(project="PRJ-9", **kw)


def test_pm_dispatches_all_independent_eligible_pis():
    bl = _Backlog({"PI-1": "Draft", "PI-2": "Ready"})
    pm = _FakePm(bl, config=_pm_cfg(), pi_driver=_pi_driver(bl))
    report = pm.run()
    assert [d["planning_item"] for d in report.driven] == ["PI-1", "PI-2"]
    assert all(d["status"] is TaskStatus.SUCCEEDED for d in report.driven)
    assert report.eligible_remaining == []  # both at In Review, none re-eligible


def test_eligible_batch_caps_and_skips_attempted():
    bl = {"eligible": ["PI-1", "PI-2", "PI-3"]}
    assert eligible_batch(bl, {}, 2) == ["PI-1", "PI-2"]
    assert eligible_batch(bl, {"PI-1": "x"}, 2) == ["PI-2", "PI-3"]
    assert eligible_batch(bl, {}, 1) == ["PI-1"]


def test_pm_drives_independent_pis_in_parallel():
    import threading
    import time

    bl = _Backlog({"PI-1": "Ready", "PI-2": "Ready", "PI-3": "Ready"})
    starts: list[tuple[str, float]] = []
    lock = threading.Lock()

    def _slow_driver(ado_cfg):
        pid = ado_cfg.planning_item
        with lock:
            starts.append((pid, time.monotonic()))
        time.sleep(0.05)  # hold the slot so concurrency is observable
        bl.pis[pid] = "In Review"
        return AdoRunReport(planning_item=pid, status=TaskStatus.SUCCEEDED)

    pm = _FakePm(bl, config=_pm_cfg(max_parallel_pis=3), pi_driver=_slow_driver)
    report = pm.run()
    assert {d["planning_item"] for d in report.driven} == {"PI-1", "PI-2", "PI-3"}
    # all three started within a small window → they ran concurrently, not serially.
    span = max(t for _, t in starts) - min(t for _, t in starts)
    assert span < 0.05, f"starts spread over {span:.3f}s — not parallel"


def test_pm_records_a_paused_pi_and_does_not_retry():
    bl = _Backlog({"PI-1": "Ready", "PI-2": "Ready"})
    pm = _FakePm(bl, config=_pm_cfg(),
                 pi_driver=_pi_driver(bl, {"PI-1": ("paused", "needs a human")}))
    report = pm.run()
    statuses = {d["planning_item"]: d["status"] for d in report.driven}
    assert statuses == {"PI-1": TaskStatus.NEEDS_HUMAN, "PI-2": TaskStatus.SUCCEEDED}
    # PI-1 was driven exactly once (In Progress now → not re-eligible).
    assert [d["planning_item"] for d in report.driven].count("PI-1") == 1


def test_pm_flows_a_dependency_chain_when_resolve_on_complete():
    # PI-2 blocked_by PI-1: only PI-1 is eligible first; resolving it unblocks PI-2.
    bl = _Backlog({"PI-1": "Ready", "PI-2": "Ready"}, {"PI-2": ["PI-1"]})
    pm = _FakePm(bl, config=_pm_cfg(resolve_on_complete=True), pi_driver=_pi_driver(bl))
    report = pm.run()
    assert [d["planning_item"] for d in report.driven] == ["PI-1", "PI-2"]
    assert bl.pis == {"PI-1": "Resolved", "PI-2": "Resolved"}
    assert report.all_resolved is True


def test_pm_review_agent_resolves_and_flows_the_chain():
    # Chain PI-2 blocked_by PI-1; a closure agent that approves resolves each
    # completed PI, so the chain flows in the default (non-blunt) path.
    bl = _Backlog({"PI-1": "Ready", "PI-2": "Ready"}, {"PI-2": ["PI-1"]})

    def _approve(cfg, pi):
        bl.pis[pi] = "Resolved"
        return True

    pm = _FakePm(bl, config=_pm_cfg(review_on_complete=True),
                 pi_driver=_pi_driver(bl), closure_runner=_approve)
    report = pm.run()
    assert [d["planning_item"] for d in report.driven] == ["PI-1", "PI-2"]
    assert report.all_resolved is True


def test_pm_review_decline_leaves_pi_in_review():
    bl = _Backlog({"PI-1": "Ready"})

    def _decline(cfg, pi):
        return False  # reviewer not satisfied; PI stays In Review

    pm = _FakePm(bl, config=_pm_cfg(review_on_complete=True),
                 pi_driver=_pi_driver(bl), closure_runner=_decline)
    report = pm.run()
    assert bl.pis["PI-1"] == "In Review"  # not resolved
    assert report.driven[0]["status"] is TaskStatus.SUCCEEDED


def test_pm_stops_at_chain_boundary_without_resolve_on_complete():
    # Same chain, default mode: PI-1 reaches In Review (not Resolved), so PI-2
    # stays blocked and the PM stops at the frontier — the governance boundary.
    bl = _Backlog({"PI-1": "Ready", "PI-2": "Ready"}, {"PI-2": ["PI-1"]})
    pm = _FakePm(bl, config=_pm_cfg(), pi_driver=_pi_driver(bl))
    report = pm.run()
    assert [d["planning_item"] for d in report.driven] == ["PI-1"]
    assert report.blocked_remaining == ["PI-2"]
    assert report.all_resolved is False


# --------------------------------------------------------------------------
# PI-190 / REQ-165 — per-PI runtime guard: the single-PI driver re-checks the
# effective execution_mode and skips+logs interactive / unapproved items
# rather than 409ing at dispatch/decompose (the project loop already filters
# via backlog["eligible"], but the per-PI entry can be pointed at any PI).
# --------------------------------------------------------------------------


def test_run_skips_interactive_pi_without_dispatch(monkeypatch):
    world = _World(1)
    world.pi_status = "Draft"
    driver = _FakeDriver(world, config=_cfg())
    monkeypatch.setattr(
        driver, "_pi", lambda: {"status": "Draft", "execution_mode": "interactive"}
    )
    report = driver.run()
    assert report.status is TaskStatus.NEEDS_HUMAN
    assert "interactive" in report.reason
    assert "/planning-items/PI-900/dispatch" not in world.calls
    assert world.decomposed is False


def test_run_skips_unapproved_ado_with_approval_pi(monkeypatch):
    world = _World(1)
    world.pi_status = "Draft"
    driver = _FakeDriver(world, config=_cfg())
    monkeypatch.setattr(
        driver, "_pi",
        lambda: {"status": "Draft", "execution_mode": "ado_with_approval",
                 "dispatch_approved": False},
    )
    report = driver.run()
    assert report.status is TaskStatus.NEEDS_HUMAN
    assert "approved" in report.reason
    assert "/planning-items/PI-900/dispatch" not in world.calls


def test_run_proceeds_for_approved_ado_with_approval_pi(monkeypatch):
    world = _World(1)
    world.pi_status = "Draft"
    driver = _FakeDriver(
        world, config=_cfg(dry_run=True),
        pool_runner=_clean_pool, scope_runner=_scopes_to_ready(world),
        gate_checker=_open_gate,
    )
    monkeypatch.setattr(
        driver, "_pi",
        lambda: {"status": "Draft", "execution_mode": "ado_with_approval",
                 "dispatch_approved": True},
    )
    report = driver.run()
    # approved → not gated; dry-run proceeds past the gate to planning.
    assert report.dry_run is True and report.status is TaskStatus.NOT_STARTED


# --------------------------------------------------------------------------
# Content-work execution lane (PI-202 / REQ-187, WTK-219)
# --------------------------------------------------------------------------


def _content_pi():
    # A content PI: every area is methodology-* (REQ-185).
    return lambda: {"status": "In Progress", "area": ["methodology-process"]}


def test_is_content_reads_pi_area():
    world = _World(3)
    driver = _FakeDriver(
        world, config=_cfg(), pool_runner=_clean_pool,
        scope_runner=_scopes_to_ready(world), gate_checker=_open_gate,
    )
    # default fake PI has no area -> software
    assert driver._is_content() is False
    driver._pi = _content_pi()
    assert driver._is_content() is True


def test_content_pi_routes_to_review_lane_not_git_pool():
    """A content PI runs every phase through the content (review) lane; the git
    verify-by-commit pool is never used (REQ-187)."""
    world = _World(3)  # Design, Develop, Test
    git_calls: list[str] = []
    content_calls: list[tuple[str, str]] = []

    def _git_pool(cfg, ws):
        git_calls.append(ws)
        return PoolRunReport(paused=False)

    def _content_pool(cfg, ws, phase_type):
        content_calls.append((ws, phase_type))
        return PoolRunReport(paused=False)

    driver = _FakeDriver(
        world, config=_cfg(),
        pool_runner=_git_pool, content_pool_runner=_content_pool,
        scope_runner=_scopes_to_ready(world), gate_checker=_open_gate,
    )
    driver._pi = _content_pi()
    report = driver.run()

    assert report.status is TaskStatus.SUCCEEDED
    assert git_calls == []  # the git pool never ran for content
    assert [ws for ws, _ in content_calls] == ["WSK-1", "WSK-2", "WSK-3"]
    # the content lane receives the phase_type so it can author (Develop) vs review (Test)
    phase_types = dict(content_calls)
    assert phase_types["WSK-2"] == "Develop"
    assert phase_types["WSK-3"] == "Test"


def test_software_pi_still_uses_the_git_pool():
    world = _World(3)
    git_calls: list[str] = []
    content_calls: list[str] = []
    driver = _FakeDriver(
        world, config=_cfg(),
        pool_runner=lambda c, w: (git_calls.append(w), PoolRunReport(paused=False))[1],
        content_pool_runner=lambda c, w, p: (content_calls.append(w), PoolRunReport(paused=False))[1],
        scope_runner=_scopes_to_ready(world), gate_checker=_open_gate,
    )
    # default fake PI -> software
    report = driver.run()
    assert report.status is TaskStatus.SUCCEEDED
    assert git_calls == ["WSK-1", "WSK-2", "WSK-3"]
    assert content_calls == []


def test_content_resume_skips_unmerged_residue_check():
    """Content tasks have no git branch, so the unmerged-residue check (a
    software-lane concern) is skipped on resume (REQ-187)."""
    world = _World(3)
    world.decomposed = True
    world.phase_status["WSK-1"] = "Complete"
    world.phase_status["WSK-2"] = "In Progress"  # Develop resumes
    world.add_task("WSK-2", "WTK-1", "Complete")
    checked: list[str] = []
    driver = _FakeDriver(
        world, config=_cfg(),
        pool_runner=_clean_pool,
        content_pool_runner=lambda c, w, p: PoolRunReport(paused=False),
        scope_runner=_scopes_to_ready(world), gate_checker=_open_gate,
        unmerged_check=lambda c, t: checked.append(t) or False,
    )
    driver._pi = _content_pi()
    driver.run()
    assert checked == []  # never probed git for a content task


def test_content_work_prompt_develop_authors_test_reviews():
    cfg = _cfg()
    dev = ado.build_content_work_prompt(cfg, "WSK-2", "Develop")
    assert "AUTHOR" in dev
    assert "records" in dev
    assert "no git" in dev.lower()
    test = ado.build_content_work_prompt(cfg, "WSK-3", "Test")
    assert "Tester" in test
    assert "REVIEW" in test
    assert "acceptance criteria" in test


def test_content_pool_verifies_by_result(monkeypatch):
    monkeypatch.setattr(ado, "spawn_scoping_agent", lambda *a, **k: None)

    def _get_status(status):
        def _get(api, path, eng):
            if path.startswith("/references?"):
                return [{"source_id": "WTK-1", "source_type": "work_task"}]
            return {"work_task_status": status}
        return _get

    # a non-terminal task pauses the phase for a person
    monkeypatch.setattr(ado.dispatcher, "_get", _get_status("In Progress"))
    paused = ado.run_content_pool_for_workstream(_cfg(), "WSK-2", "Develop")
    assert paused.paused is True

    # all terminal -> the phase advances
    monkeypatch.setattr(ado.dispatcher, "_get", _get_status("Complete"))
    assert ado.run_content_pool_for_workstream(_cfg(), "WSK-2", "Develop").paused is False

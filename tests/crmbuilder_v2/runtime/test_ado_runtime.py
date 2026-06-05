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

from crmbuilder_v2.runtime.ado_runtime import (
    AdoRunReport,
    AdoRuntime,
    AdoRuntimeConfig,
    ProjectRuntime,
    ProjectRuntimeConfig,
    StepKind,
    decide_next,
    select_next_pi,
)
from crmbuilder_v2.runtime.parallel_runtime import PoolRunReport
from crmbuilder_v2.runtime.reconciliation import GateDecision

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


class _FakeDriver(AdoRuntime):
    """AdoRuntime with the HTTP seams routed to a :class:`_World`."""

    def __init__(self, world, **kw):
        super().__init__(**kw)
        self.world = world
        if "reconcile_runner" not in kw:
            self.reconcile_runner = lambda c, w: None  # no real agent under test

    def _get(self, path):
        if path.endswith("/phase-overview"):
            return self.world.overview()
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
        return {}

    def _patch_pi_status(self, status):
        self.world.pi_status = status


def _cfg(**kw):
    kw.setdefault("log", lambda _m: None)
    return AdoRuntimeConfig(planning_item="PI-900", **kw)


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


def test_drives_all_phases_scope_then_execute():
    world = _World(3)
    driver = _FakeDriver(
        world, config=_cfg(),
        pool_runner=_clean_pool, scope_runner=_scopes_to_ready(world), gate_checker=_open_gate,
    )
    report = driver.run()
    assert report.status == "complete"
    assert report.completed_phases == ["WSK-1", "WSK-2", "WSK-3"]
    assert world.pi_status == "In Review"
    # every phase was scoped before it was started.
    for ws in world.phase_ids:
        assert world.calls.index(f"scope:{ws}") < world.calls.index(f"/workstreams/{ws}/start-execution")


def test_reconcile_runs_after_design_only():
    world = _World(3)  # Design, Develop, Test
    reconciled: list[str] = []
    driver = _FakeDriver(
        world, config=_cfg(),
        pool_runner=_clean_pool, scope_runner=_scopes_to_ready(world), gate_checker=_open_gate,
        reconcile_runner=lambda c, w: reconciled.append(w),
    )
    report = driver.run()
    assert report.status == "complete"
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
    assert report.status == "complete"
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
    assert report.status == "paused" and "scope" in report.reason.lower()


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
    assert report.status == "paused" and "gate held" in report.reason.lower()
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
    assert report.status == "complete"
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
    assert report.status == "paused" and "WSK-1" in report.reason


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
    assert report.status == "dry_run"
    assert "/planning-items/PI-900/dispatch" not in world.calls
    assert not any("start-execution" in c for c in world.calls)


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


class _FakePm(ProjectRuntime):
    def __init__(self, backlog, **kw):
        super().__init__(**kw)
        self.backlog = backlog

    def _backlog(self):
        return self.backlog.snapshot()

    def _resolve_pi(self, pi):
        self.backlog.pis[pi] = "Resolved"


def _pi_driver(backlog, outcomes=None):
    """Fake per-PI driver: reflects the outcome into the backlog and reports it."""
    outcomes = outcomes or {}

    def _driver(ado_cfg):
        pid = ado_cfg.planning_item
        status, reason = outcomes.get(pid, ("complete", None))
        backlog.pis[pid] = "In Review" if status == "complete" else "In Progress"
        return AdoRunReport(planning_item=pid, status=status, reason=reason)

    return _driver


def _pm_cfg(**kw):
    kw.setdefault("log", lambda _m: None)
    return ProjectRuntimeConfig(project="PRJ-9", **kw)


def test_pm_dispatches_all_independent_eligible_pis():
    bl = _Backlog({"PI-1": "Draft", "PI-2": "Ready"})
    pm = _FakePm(bl, config=_pm_cfg(), pi_driver=_pi_driver(bl))
    report = pm.run()
    assert [d["planning_item"] for d in report.driven] == ["PI-1", "PI-2"]
    assert all(d["status"] == "complete" for d in report.driven)
    assert report.eligible_remaining == []  # both at In Review, none re-eligible


def test_pm_records_a_paused_pi_and_does_not_retry():
    bl = _Backlog({"PI-1": "Ready", "PI-2": "Ready"})
    pm = _FakePm(bl, config=_pm_cfg(),
                 pi_driver=_pi_driver(bl, {"PI-1": ("paused", "needs a human")}))
    report = pm.run()
    statuses = {d["planning_item"]: d["status"] for d in report.driven}
    assert statuses == {"PI-1": "paused", "PI-2": "complete"}
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
    assert report.driven[0]["status"] == "complete"


def test_pm_stops_at_chain_boundary_without_resolve_on_complete():
    # Same chain, default mode: PI-1 reaches In Review (not Resolved), so PI-2
    # stays blocked and the PM stops at the frontier — the governance boundary.
    bl = _Backlog({"PI-1": "Ready", "PI-2": "Ready"}, {"PI-2": ["PI-1"]})
    pm = _FakePm(bl, config=_pm_cfg(), pi_driver=_pi_driver(bl))
    report = pm.run()
    assert [d["planning_item"] for d in report.driven] == ["PI-1"]
    assert report.blocked_remaining == ["PI-2"]
    assert report.all_resolved is False

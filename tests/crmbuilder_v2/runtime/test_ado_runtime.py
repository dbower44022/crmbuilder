"""ADO orchestration driver (PI-143 slice 1) — pure decisions + the loop.

Mirrors the module's pure/I-O split:

* **pure decision** — :func:`decide_next` is exercised directly for all four
  outcomes and their precedence, no I/O;
* **the loop** — the substrate HTTP seams (``_get`` / ``_post`` /
  ``_patch_pi_status``) and the pool runner are injected against an in-memory
  fake of the PM/Lead/decompose substrate, so the orchestration is proven
  (dispatch → decompose → per-phase start/run/complete → advance) without a
  server or a real agent.
"""

from __future__ import annotations

from crmbuilder_v2.runtime.ado_runtime import (
    AdoRuntime,
    AdoRuntimeConfig,
    StepKind,
    decide_next,
)
from crmbuilder_v2.runtime.parallel_runtime import PoolRunReport

_TERMINAL = {"Complete", "Not Applicable"}


# --------------------------------------------------------------------------
# pure decision
# --------------------------------------------------------------------------


def _ov(*, decomposed=True, phases=(), all_terminal=False, attention=(), nxt=None):
    return {
        "decomposed": decomposed,
        "phases": list(phases),
        "all_terminal": all_terminal,
        "needs_attention": list(attention),
        "next_executable": nxt,
    }


def test_decide_start_when_executable():
    step = decide_next(_ov(nxt="WSK-2"))
    assert step.kind is StepKind.START and step.workstream == "WSK-2"


def test_decide_done_when_all_terminal():
    assert decide_next(_ov(all_terminal=True)).kind is StepKind.DONE


def test_decide_blocked_when_nothing_executable():
    step = decide_next(_ov(nxt=None))
    assert step.kind is StepKind.BLOCKED and step.reason


def test_attention_takes_precedence_over_executable():
    # A human-attention flag stops everything, even if a phase is executable.
    step = decide_next(_ov(attention=["WSK-1"], nxt="WSK-2", all_terminal=False))
    assert step.kind is StepKind.PAUSE and "WSK-1" in step.reason


# --------------------------------------------------------------------------
# the loop — driven against an in-memory substrate fake
# --------------------------------------------------------------------------


class _World:
    """A minimal stand-in for the PM/Lead/decompose substrate state."""

    def __init__(self, phase_ids):
        self.pi_status = "Draft"
        self.decomposed = False
        self.phase_ids = list(phase_ids)
        self.phase_status = dict.fromkeys(phase_ids, "Planned")
        self.attention: set[str] = set()
        self.calls: list[str] = []

    def overview(self):
        if not self.decomposed:
            return _ov(decomposed=False)
        phases = [
            {
                "workstream": {
                    "workstream_identifier": p,
                    "workstream_needs_attention": p in self.attention,
                },
                "status": self.phase_status[p],
            }
            for p in self.phase_ids
        ]
        next_exec = None
        for i, p in enumerate(self.phase_ids):
            preds_ok = all(self.phase_status[q] in _TERMINAL for q in self.phase_ids[:i])
            if self.phase_status[p] == "Ready" and preds_ok:
                next_exec = p
                break
        return _ov(
            phases=phases,
            all_terminal=all(self.phase_status[p] in _TERMINAL for p in self.phase_ids),
            attention=[p for p in self.phase_ids if p in self.attention],
            nxt=next_exec,
        )


class _FakeDriver(AdoRuntime):
    """AdoRuntime with the HTTP seams routed to a :class:`_World`."""

    def __init__(self, world, **kw):
        super().__init__(**kw)
        self.world = world

    def _get(self, path):
        if path.endswith("/phase-overview"):
            return self.world.overview()
        return {"status": self.world.pi_status}  # GET /planning-items/{id}

    def _post(self, path, body=None):
        self.world.calls.append(path)
        if path.endswith("/dispatch"):
            self.world.pi_status = "In Progress"
        elif path.endswith("/decompose"):
            self.world.decomposed = True
            # slice 1: scoping is supplied, so phases come up Ready.
            for p in self.world.phase_ids:
                self.world.phase_status[p] = "Ready"
        elif path.endswith("/start-execution"):
            ws = path.split("/")[2]
            self.world.phase_status[ws] = "In Progress"
        elif path.endswith("/complete-phase"):
            ws = path.split("/")[2]
            self.world.phase_status[ws] = "Complete"
        return {}

    def _patch_pi_status(self, status):
        self.world.pi_status = status


def _cfg(**kw):
    kw.setdefault("log", lambda _m: None)
    return AdoRuntimeConfig(planning_item="PI-900", **kw)


def _clean_pool(cfg, ws):
    return PoolRunReport(paused=False)


def test_drives_all_phases_to_in_review():
    world = _World(["WSK-1", "WSK-2", "WSK-3"])
    driver = _FakeDriver(world, config=_cfg(), pool_runner=_clean_pool)
    report = driver.run()
    assert report.status == "complete"
    assert report.completed_phases == ["WSK-1", "WSK-2", "WSK-3"]
    assert world.pi_status == "In Review"
    # phases ran in serial order: each started before the next.
    assert world.calls.count("/planning-items/PI-900/dispatch") == 1
    assert world.calls.count("/planning-items/PI-900/decompose") == 1


def test_resumes_without_redispatching_a_started_pi():
    # Already In Progress + decomposed + scoped: no dispatch/decompose re-issued.
    world = _World(["WSK-1"])
    world.pi_status = "In Progress"
    world.decomposed = True
    world.phase_status["WSK-1"] = "Ready"
    driver = _FakeDriver(world, config=_cfg(), pool_runner=_clean_pool)
    report = driver.run()
    assert report.status == "complete"
    assert "/planning-items/PI-900/dispatch" not in world.calls
    assert "/planning-items/PI-900/decompose" not in world.calls


def test_pauses_when_a_phase_needs_attention():
    world = _World(["WSK-1", "WSK-2"])
    world.pi_status = "In Progress"
    world.decomposed = True
    world.phase_status = {"WSK-1": "Ready", "WSK-2": "Ready"}
    world.attention.add("WSK-2")
    driver = _FakeDriver(world, config=_cfg(), pool_runner=_clean_pool)
    report = driver.run()
    assert report.status == "paused" and "WSK-2" in report.reason
    # No phase was completed — the loop stopped at the attention flag.
    assert world.phase_status["WSK-1"] != "Complete"


def test_pauses_when_the_pool_pauses():
    world = _World(["WSK-1"])
    world.pi_status = "In Progress"
    world.decomposed = True
    world.phase_status["WSK-1"] = "Ready"
    driver = _FakeDriver(
        world, config=_cfg(), pool_runner=lambda c, w: PoolRunReport(paused=True)
    )
    report = driver.run()
    assert report.status == "paused" and "WSK-1" in report.reason
    # The phase was started but not completed (execution paused mid-phase).
    assert world.phase_status["WSK-1"] == "In Progress"


def test_blocked_when_a_phase_is_unscoped():
    # decomposed but a phase never reached Ready (scoping not supplied).
    world = _World(["WSK-1"])
    world.pi_status = "In Progress"
    world.decomposed = True  # phases stay Planned, not Ready
    driver = _FakeDriver(world, config=_cfg(), pool_runner=_clean_pool)
    report = driver.run()
    assert report.status == "blocked"


def test_dry_run_plans_without_executing():
    world = _World(["WSK-1"])
    driver = _FakeDriver(world, config=_cfg(dry_run=True), pool_runner=_clean_pool)
    report = driver.run()
    assert report.status == "dry_run"
    # dry-run issues no start/complete calls.
    assert not any("start-execution" in c or "complete-phase" in c for c in world.calls)

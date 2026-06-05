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
    AdoRuntime,
    AdoRuntimeConfig,
    StepKind,
    decide_next,
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

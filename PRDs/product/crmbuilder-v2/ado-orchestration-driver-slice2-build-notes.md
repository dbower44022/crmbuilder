# ADO orchestration driver — slice 2 build notes (PI-143)

Status: **Built on branch `pi-137-claim-lifecycle`** (stacked on slice 1 + the
PI-137 claim fix). Left for a PM session to run the live demo, merge, and advance
PI-143. Planned in **DEC-407**; this executes its slice-2 scope unchanged (no new
design decision needed).

Slice 1 drove a **pre-scoped** PI (scoping supplied). Slice 2 adds the two pieces
that remove that caveat: **scoping judgment** and the **Design reconciliation
gate**.

## What slice 2 adds

**1. Scoping agents.** `decide_next` gained a `SCOPE` action: the first
non-terminal phase that is still `Planned` is scoped before it is started. The
driver spawns an **Architect agent** (`scope_phase_agent` → `build_scoping_prompt`
+ `spawn_scoping_agent`) whose one job is to read the Planning Item and the prior
phases' outputs (`prior-phase-outputs`), **decide** the phase's Work Tasks (one per
area it touches), and create them in a single `POST /workstreams/{id}/scope` call —
an empty list asserts `Not Applicable`. The scoping agent writes **no code and uses
no worktree** (it only records Work Tasks via the API), so its spawn is lighter than
an execution agent. Success is **verified by result** (DEC-396): the driver re-reads
the phase and proceeds only if it reached `Ready` (or `Not Applicable`); otherwise it
pauses for a person.

**2. Design reconciliation gate.** Before starting a **Develop** phase the driver
consults the gate (`develop_gate_open`, reusing `reconciliation.develop_gate` /
`evaluate_develop_gate`): if an open *blocking* finding holds the Design, the driver
pauses with a reconciliation reason instead of running a futile pool (REQ-027/033).
The per-Work-Task gate was **already enforced in the pool**
(`coordinating_runtime` calls `reconciliation.develop_gate` at dispatch); this
phase-level consult makes the driver pause *cleanly and early* rather than spinning
on tasks the pool would withhold.

The loop is now: dispatch → decompose → for each phase: **scope (Architect)** →
*(Develop only)* **gate** → start → run pool → complete → advance to `In Review`.

## Where it lives

- `crmbuilder-v2/src/crmbuilder_v2/runtime/ado_runtime.py` — extended:
  - `decide_next` now returns `SCOPE`/`START` for the first non-terminal phase
    (serial), carrying `phase_type`; still a pure function of the `phase-overview`
    payload.
  - `scope_phase_agent` / `build_scoping_prompt` / `spawn_scoping_agent` — the
    scoping-agent seam (injectable; default spawns a real Architect).
  - `develop_gate_open` — the phase-level gate consult (injectable).
  - `AdoRuntime` gained `scope_runner` and `gate_checker` injectable fields.
- `tests/crmbuilder_v2/runtime/test_ado_runtime.py` — 13 tests: the five
  `decide_next` outcomes (incl. SCOPE and skip-terminal); a full run that scopes
  each phase before starting it; a `Not Applicable` phase skipped; a pause when
  scoping doesn't complete; the Develop gate holding on an open blocking finding;
  the gate consulted *only* for Develop; a paused pool; resume + dry-run.

## How to run it

```bash
# Drive one PI end to end — the driver scopes each phase (real Architect agents)
# and executes it (real Developer/Tester agents via the pool):
crmbuilder-v2-ado PI-NNN --repo-root /path/to/repo --base-branch main --max-concurrent 2

# Plan only — no agents, no mutation:
crmbuilder-v2-ado PI-NNN --dry-run
```

A live `--dry-run` against PI-143 confirmed the slice-2 wiring and mutated nothing.

## Requirements coverage

Extends the runtime topic (TOP-012): scoping is now agent-driven judgment (the
matrix's Architect tier doing the Design pass's "decide the Work Tasks" job);
REQ-027/033 (Design reconciled before Develop) is enforced at the phase boundary in
addition to the pool's per-task enforcement.

## Deferred (slice 3)

- **PM auto-dispatch.** The PM watches the project backlog, dispatches each eligible
  PI to a driver, and the whole portfolio runs with `needs_attention` pauses.
- The **reconcile agent that raises findings** (the Architect detecting cross-area
  conflicts during Design) — slice 2 *enforces* the gate; the finding *producer* is
  the next agent-layer piece. With no findings raised yet the gate passes vacuously,
  which is correct.

## The acceptance bar (to run attended)

The deterministic orchestration is pinned by the unit tests; the end-to-end run —
a PI whose phases are **scoped by real Architect agents** and **executed by real
Developer/Tester agents**, advanced to `In Review` on an isolated repo — is the
acceptance demo, run attended (it spawns real agents and makes commits).

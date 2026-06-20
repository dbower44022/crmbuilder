# ADO orchestration driver — slice 1 build notes (PI-143)

Status: **Built on branch `pi-137-claim-lifecycle`** (stacked on the PI-137 claim
fix it depends on). Left for a PM session to run the live end-to-end demo, merge
to `main`, and resolve PI-143.

This is the **top half** of the delivery loop — the PI-level scheduler the
runtime lacked. The L1/L2 runtime (`coordinating_runtime` / `parallel_runtime`)
drives the *bottom* half (find a `Ready` Work Task → spawn → verify → merge) but
nothing turned a dispatched Planning Item into `Ready` Work Tasks and advanced it
phase by phase — that was hand-operated, endpoint by endpoint. Slice 1 closes
that gap deterministically.

## What slice 1 is

A deterministic outer loop that **composes the already-built substrate with the
already-built execution pool**:

```
dispatch (PM)  →  decompose  →  for each phase in serial order:
    start_phase (Lead)  →  run the L2 pool over the phase  →  complete_phase (Lead)
→  advance the Planning Item to In Review
```

**Slice 1 supplies phase scoping** — each phase's Work Tasks are created
beforehand (by hand or an external step), so the driver only needs the phase to be
`Ready`. It does **not** yet spawn the Architect/phase-specialist agents that
*decide* a phase's Work Tasks (slice 2), nor auto-dispatch from the project
backlog (slice 3).

The driver is **DB-backed-stateless**: every iteration re-reads
`GET /planning-items/{id}/phase-overview` and continues from wherever the records
say things stand, so it is fully resumable. Dispatch and decompose are idempotent
(a started PI is not re-dispatched; a decomposed PI is not re-decomposed).

It **pauses for a human** at the same reserved points as the rest of the runtime:
a phase flagged `needs_attention`, or the pool pausing mid-phase on a
verify-failure / merge-conflict. It never force-resolves.

## Where it lives

- `crmbuilder-v2/src/crmbuilder_v2/runtime/ado_runtime.py` — the driver.
  - **Pure decision** `decide_next(overview) → AdoStep` (no I/O, unit-tested
    directly): from a `phase-overview` payload, decide PAUSE (needs_attention,
    highest precedence) / DONE (all phases terminal) / START (the
    `next_executable` phase) / BLOCKED (nothing executable and not done — in
    slice 1, an unscoped phase).
  - `AdoRuntime.run()` — the loop, with the substrate HTTP seams (`_get` /
    `_post` / `_patch_pi_status`) and the pool runner (`run_pool_for_workstream`,
    which builds a `ParallelRuntimeConfig(target_workstream=…)` and runs the L2
    pool over exactly that phase) injectable for tests.
- `crmbuilder-v2-ado` — console entry point (in `pyproject.toml`).
- `tests/crmbuilder_v2/runtime/test_ado_runtime.py` — the four pure-decision
  outcomes + the loop driven against an in-memory substrate fake: full run to
  `In Review`, resume-without-redispatch, pause on a phase `needs_attention`,
  pause when the pool pauses, blocked on an unscoped phase, dry-run plans without
  executing. 10 tests.

## How to run it

```bash
# Drive one pre-scoped PI through all its phases (real agents via the L2 pool):
crmbuilder-v2-ado PI-NNN --repo-root /path/to/repo --base-branch main --max-concurrent 2

# Plan only — dispatch/decompose intent + the next step, spawn nothing, mutate nothing:
crmbuilder-v2-ado PI-NNN --dry-run
```

A `--dry-run` against a real PI was used as the live-API smoke test: it correctly
read the PI status and `phase-overview`, reported the next step, and left the PI
untouched.

## What it composes (all already built)

| Step | Substrate call (endpoint) |
|---|---|
| dispatch | `POST /planning-items/{id}/dispatch` (PM, `pm.dispatch_planning_item`) |
| decompose | `POST /planning-items/{id}/decompose` (`decomposition.decompose_planning_item`) |
| read state | `GET /planning-items/{id}/phase-overview` (`lead.phase_overview`) |
| start phase | `POST /workstreams/{id}/start-execution` (`lead.start_phase`) |
| execute phase | `ParallelCoordinatingRuntime.run(target_workstream=…)` (the L2 pool) |
| complete phase | `POST /workstreams/{id}/complete-phase` (`lead.complete_phase`) |
| advance PI | `PATCH /planning-items/{id}` → `In Review` |

The driver stops at `In Review`: final `Resolved` is a governance closure act (the
`resolves` edge), not the driver's call.

## Requirements coverage (REQ-052…058 under TOP-012)

Slice 1 extends the runtime requirements from Work-Task-level execution to
PI-level orchestration: **REQ-052** (the scheduler runs the loop) now holds for the
whole PI, not just one task; **REQ-055** (order) is honored by serial phase
advancement gated on `phase-overview.next_executable`; **REQ-057** (verify before
advancing) is enforced phase-by-phase by `complete_phase`'s all-Work-Tasks-Complete
gate; **REQ-058** (pause at human-judgment points) covers a phase `needs_attention`
and a paused pool. Built on **PI-137** (claim advances `Ready → Claimed`) so the
phase Work Tasks carry the lifecycle states the gate signals read.

## Deferred (slices 2–3, explicitly NOT here)

- **Slice 2 — scoping agents.** Spawn an Architect/phase-specialist agent per phase
  that decides and creates the phase's Work Tasks from the registry contract
  (judgment), replacing the supplied/manual scoping; wire the Design-phase
  reconciliation gate (no Develop until Design is complete with no open blocking
  findings).
- **Slice 3 — PM auto-dispatch.** The PM watches the project backlog, dispatches
  each eligible PI to a driver, and the whole portfolio runs with `needs_attention`
  pauses.

## The acceptance bar (to run attended)

The deterministic orchestration is pinned by the unit tests; the genuine
end-to-end run — a pre-scoped PI driven through its phases with **real Claude
agents** spawned by the pool in worktrees, each phase verified and the PI advanced
to `In Review` on an isolated demo repo — is the slice-1 acceptance demo, to be run
attended (it spawns real agents and makes commits), mirroring the L1/L2 demos.

# ADO orchestration driver — slice 3 build notes (PI-143)

Status: **Built on branch `pi-137-claim-lifecycle`** (stacked on slices 1–2 + the
PI-137 claim fix). Left for a PM session to run the live demo, merge, and resolve
PI-143. Planned in **DEC-407**; the one new design choice (the In-Review→Resolved
boundary) is **DEC-408**.

Slices 1–2 drive **one** Planning Item through its phases. Slice 3 adds the top
tier: the **Project Manager auto-dispatch** loop that drives a whole Project's
backlog.

## What slice 3 adds

`ProjectRuntime` wraps the per-PI `AdoRuntime` (slices 1–2) in a PM loop:

```
while there is an eligible PI not yet attempted this run:
    pick the next eligible PI (backlog/priority order)
    drive it through its phases (AdoRuntime: scope → start → run → complete)
    record the outcome; (optionally) resolve it so dependents unblock
```

**Eligibility respects dependencies.** `pm.project_backlog` already computes
`eligible` = *startable* **and** every `blocked_by` predecessor **Resolved**, so the
PM only ever dispatches the dependency-clean frontier. The pure
`select_next_pi(backlog, attempted)` picks the next eligible PI not yet attempted
this run (so a PI that paused/blocked is recorded once and not re-driven).

**The In-Review→Resolved boundary (DEC-408).** A PI driven to `In Review` is *not*
`Resolved`, so PIs `blocked_by` it stay blocked. By default the PM **stops at that
frontier** — final resolution is the `resolves`-edge governance closure act, not the
runtime's call. The opt-in `--resolve-on-complete` lever (config
`resolve_on_complete`) treats execution-complete (all phases verified) as
resolution and marks the PI `Resolved`, so a dependency chain flows end to end
under fully-autonomous operation. Off by default = faithful to governance; on =
demonstrable autonomous chains.

## Where it lives

- `crmbuilder-v2/src/crmbuilder_v2/runtime/ado_runtime.py` — added:
  - `select_next_pi(backlog, attempted)` — the pure frontier pick.
  - `ProjectRuntimeConfig`, `ProjectRunReport`, `ProjectRuntime` — the PM loop,
    with `_backlog()` (GET `/projects/{id}/backlog`), `_resolve_pi()`, and an
    injectable `pi_driver` seam (default `drive_planning_item` = run `AdoRuntime`).
  - `project_main` CLI + `crmbuilder-v2-ado-pm` entry point.
- `tests/crmbuilder_v2/runtime/test_ado_runtime.py` — 18 tests total; the 5 new
  ones: `select_next_pi` precedence; PM dispatches all independent eligible PIs; a
  paused PI is recorded and not retried; a dependency chain flows under
  `resolve_on_complete`; and the PM stops cleanly at the chain boundary without it.

## How to run it

```bash
# Drive a Project's eligible backlog (stops each PI at In Review):
crmbuilder-v2-ado-pm PRJ-NNN --repo-root /path/to/repo --base-branch main --max-concurrent 2

# Fully autonomous — resolve each completed PI so dependents unblock and chains flow:
crmbuilder-v2-ado-pm PRJ-NNN --resolve-on-complete
```

A read-only smoke test against `PRJ-018` confirmed the live wiring: the PM correctly
reported `PI-143` as **blocked** (its `blocked_by` `PI-137` is not yet Resolved) with
`PI-131`/`PI-137` eligible — the dependency frontier resolved end to end against live
data, no agents spawned.

## What this completes

With slice 3 the deterministic ADO orchestration spine is whole — **PM → per-PI
Lead → phase scope → reconciliation gate → execution pool → advance** — every tier
composing the substrate that PI-112/PI-114 built and the runtime that PI-132/139
built. The remaining open pieces are the *agent-layer* refinements, not the
orchestration:

- the **reconcile agent that raises findings** (slice 2 enforces the Design gate; a
  finding *producer* makes it bite);
- **parallel independent PIs** (slice 3 dispatches serially; the design permits
  concurrent drivers for PIs with no `blocked_by` between them);
- a **review/closure agent** that resolves an `In Review` PI (so the default,
  governance-faithful mode advances chains without the autonomous lever).

## The acceptance bar (to run attended)

The deterministic PM loop is pinned by the unit tests; the end-to-end run — the PM
dispatching a Project's backlog, each PI scoped by real Architect agents and
executed by real Developer/Tester agents, dependents unblocking in order — is the
acceptance demo, run attended (it spawns real agents and makes commits).

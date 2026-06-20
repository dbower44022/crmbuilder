# Coordinating runtime — Layer 2 build notes (PI-139)

Status: **Built on branch `pi-139`** (Develop WSK-028 + Test WSK-029). Left
**In Progress** for a separate PM session to verify the working-demo bar (≥2
agents in parallel, both merged), merge to `main`, and resolve PI-139.

This documents what Layer 2 is, how it is wired, and the end-to-end demo that
proves it. The spec is **DEC-397**; the requirements are **REQ-052…058** under
topic **TOP-012**; Layer 1 is **DEC-395** / PI-132.

## What Layer 2 is

Layer 1 (`runtime/coordinating_runtime.py`) closed the loop — it spawns a real
Claude Code agent in a worktree, verifies by result, merges, and pauses for a
human — but **one agent at a time** (serial, DEC-395). Layer 2
(`runtime/parallel_runtime.py`) generalizes that single-spawn unit into a
**concurrency-safe capped parallel pool** (DEC-397):

1. **capped pool** — up to `max_concurrent` Claude agents run at once, each in
   its **own** git worktree taken from current `main`;
2. **start-on-slot-free** — whenever a slot frees and eligible (unblocked) work
   exists, a new agent starts, up to the cap;
3. **merge-as-complete** — as each agent finishes, the runtime verifies by
   result and merges its branch back (`--no-ff`) **in completion order**; a
   merge conflict halts *that* merge, records a finding, raises
   `needs_attention`, and stops new dispatch — never force-resolved;
4. **the runtime owns the API process** — it starts it if needed, monitors
   `/health`, and restarts it on crash, so **no agent ever restarts it**.

This is where the multi-user safety of the agent system lands. The exclusive
migration lock (PI-133) and the reconciliation-gate enforcement (PI-134) are
**separate PIs built on this engine** and are deliberately not here.

## Where it lives

- `crmbuilder-v2/src/crmbuilder_v2/runtime/parallel_runtime.py` — the pool.
  - **Pure decisions** (no I/O, unit-tested directly): `slots_available` (the
    cap), `select_to_dispatch` (cap + no-double-dispatch + blocker-awareness +
    deterministic order), `should_restart_api` (API ownership).
  - **`ParallelCoordinatingRuntime`** — the pool loop. Composition over
    inheritance: it holds a Layer-1 `CoordinatingRuntime` as `_l1` and reuses
    its proven per-task I/O unit (`_assignment_for`, `_merge`,
    `_flag_needs_attention`, `_owning_workstream`) plus the module-level
    `Worktree` / `spawn_claude_agent` / `verify_result` / `interpret_merge`, so
    it only adds the orchestration.
  - **`ApiProcess`** — the API process under the runtime's ownership
    (`ensure_started` / `ensure_alive` / `stop`), with injectable health/spawn
    seams so ownership is testable without a real process.
- `crmbuilder-v2-runtime-pool` — console-script entry point (in `pyproject.toml`).
- `tests/crmbuilder_v2/runtime/test_parallel_runtime.py` — 19 tests: the pure
  decisions, the API-ownership lifecycle, and the pool loop with injected seams
  (two agents overlap in wall-clock time; the cap holds with more work than
  slots; results merge in completion order; a verify-failure / merge-conflict
  pauses new dispatch and flags for a human while in-flight agents drain).

## How the parallelism actually works (the concurrency model)

- The long part — spawning and running the `claude -p` agent — happens in
  worker threads via a `ThreadPoolExecutor(max_workers=max_concurrent)`, so N
  agents genuinely run **at the same time**.
- The short, conflict-prone parts — `git worktree add/remove` (mutates
  `.git/worktrees`) and the `git checkout main && git merge` — are serialized
  under one repo lock. Only **one branch lands on the base at a time**, in the
  order results arrive on a completion queue (= completion order).
- A worker, on finishing, pushes its result onto a `queue.Queue`; the main
  thread consumes it, verifies by result (DEC-396), and merges. The queue is
  the synchronization point, which is what makes "merge in completion order"
  exact rather than dependent on executor internals.

## Two correctness strengthenings beyond DEC-397's letter

DEC-397 assumes reconciliation (PI-134) ran first, so parallel merges are
clean. Layer 2 is nonetheless built to be safe when that assumption is tested:

1. **Blocker-awareness keeps a task "active" until it is *merged*, not merely
   Complete.** An agent marks its Work Task `Complete` in the DB *before* the
   runtime merges its branch. A dependent that became eligible on that
   `Complete` would fork from a `main` that does not yet contain the
   predecessor's work. So `select_to_dispatch` will not start a task while any
   of its `blocked_by` predecessors is still in the pool (in-flight **or**
   awaiting merge). Dependents serialize correctly; independents run in
   parallel.
2. **A verify-failure or merge-conflict halts that merge AND stops new
   dispatch.** Per DEC-397 a conflict "halts that merge, records a finding, and
   raises needs_attention." Layer 2 additionally stops dispatching *new* work
   on the first such pause and drains the already-in-flight agents (merging the
   clean ones), then returns `paused=True`. This keeps a dependent from ever
   starting off a non-merged blocker and matches REQ-058 (pause for a person at
   the reserved points). It is an elaboration of the pause semantics, not a
   change to the merge strategy.

Both are recorded in the governance trail for PI-139 rather than left implicit.

## API ownership (REQ — the runtime owns the API process)

`ApiProcess` + the pure `should_restart_api(health_ok, owned)` implement single-
owner semantics: the runtime (re)starts the API **only if it owns it** (it
started it) **and** it is unhealthy. An API already reachable at launch is
treated as externally owned and never touched; an agent is never given any
instruction to restart it. With `--manage-api`, the pool calls
`ensure_started()` before the first dispatch and `ensure_alive()` on every
loop tick (so a crash mid-run is caught within `poll_interval`), and `stop()`s
only what it started on exit.

## Requirements coverage (REQ-052…058)

- **REQ-052** (scheduler runs the loop) — `ParallelCoordinatingRuntime.run()`
  drives fill → spawn → verify → merge → refill with no per-step human op.
- **REQ-053** (spawned on demand, exits when done) — one `claude -p` per task;
  verify-by-result (DEC-396) means a killed/overrun agent whose work is recorded
  still completes correctly.
- **REQ-054** (resolve contract from registry first) — reuses Layer 1's
  `_assignment_for`: registry contract via `build_agent_prompt` when a profile
  exists (the demo resolved `AGP-002`), built-in fallback otherwise.
- **REQ-055** (order + concurrency limit) — **this is the Layer-2 deliverable:**
  `slots_available` + `select_to_dispatch` cap concurrency and honor
  `blocked_by` order; the `ThreadPoolExecutor` enforces the cap a second time.
- **REQ-056** (isolation + merge; conflict recorded) — each agent in its own
  worktree from current `main`; clean branches merge `--no-ff` in completion
  order; a conflict is aborted, flagged `needs_attention`, recorded, never
  force-resolved.
- **REQ-057** (verify before advancing) — `verify_result` gates every merge; a
  failure pauses and is flagged.
- **REQ-058** (pause at human-judgment points) — a verify-failure / conflict /
  pre-flagged task stops new dispatch and records the pause.

## Findings recorded during the build

- **Registry contract path now resolves on the live DB.** Layer 1's build noted
  PI-138 (the live `change_log` CHECK omitted the PI-122 registry entity types,
  500-ing `POST /agent-profiles`). This Layer-2 demo resolved a real system
  profile (`AGP-002`) for `(api, developer)` and ran on the genuine registry
  contract — so the contract-resolution path is exercised end to end here, not
  just the fallback.

## End-to-end demo (the acceptance bar)

Two **independent** Work Tasks (`WTK-049`, `WTK-050`), an isolated demo repo,
`max_concurrent=2`. The runtime spawned **two real Claude Code agents at once**,
each in its own worktree from `main`, and merged **both** back cleanly. Real
run output:

```
▶ dispatching WTK-049 (area=api, profile=AGP-002) → worktree branch ado/wtk-049
  [WTK-049] spawning agent in /tmp/claude-1000/ado-ado-wtk-049-688wbplp …
▶ dispatching WTK-050 (area=api, profile=AGP-002) → worktree branch ado/wtk-050
  [WTK-050] spawning agent in /tmp/claude-1000/ado-ado-wtk-050-m_w5jzyv …
  [WTK-049] agent exited rc=0
  [WTK-049] verify: ok (branch_has_commits=True)
  [WTK-049] merge: clean
✔ WTK-049 verified + merged into main
  [WTK-050] agent exited rc=0
  [WTK-050] verify: ok (branch_has_commits=True)
  [WTK-050] merge: clean
✔ WTK-050 verified + merged into main
```

**Timestamps prove the overlap** — both agents were spawned ~21 ms apart and
both were still running ~50 s later:

```
WTK-049: spawned_at=1780611451.638  finished_at=1780611502.560  merged_at=1780611502.578
WTK-050: spawned_at=1780611451.659  finished_at=1780611516.670  merged_at=1780611516.682
PARALLEL OVERLAP (both agents ran at once): True
merged: ['WTK-049', 'WTK-050']  paused: False
```

Durable result on the isolated demo repo's `main` (two independent branches,
each with the agent's own commit, both `--no-ff` merged in completion order):

```
*   906997a ado: merge ado/wtk-050 (coordinating runtime)
|\
| * 84db411 WTK-050: add proof-B.txt (PI-139 Layer 2 parallel demo task B)
* |   aff4c8f ado: merge ado/wtk-049 (coordinating runtime)
|\ \
| |/
|/|
| * 990861c WTK-049: add proof-A.txt (PI-139 Layer 2 parallel demo task A)
|/
* cce04f9 demo: initial commit

$ cat proof-A.txt
PI-139 Layer 2 parallel agent A — spawned, worked, merged.
$ cat proof-B.txt
PI-139 Layer 2 parallel agent B — spawned, worked, merged.
```

Both tasks ended `Complete` (claimed by `AGP-runtime`); both worktrees were
removed. The demo runner is `/tmp/pi139-demo/run_demo.py` (isolated; not
committed).

## How to run it

```bash
# Two specific Work Tasks in parallel, isolated demo repo, cap 2:
crmbuilder-v2-runtime-pool --work-task WTK-049 --work-task WTK-050 \
  --repo-root /path/to/repo --base-branch main --max-concurrent 2

# A whole Workstream's eligible tasks, cap 3, runtime owns the API:
crmbuilder-v2-runtime-pool --workstream WSK-NNN --max-concurrent 3 --manage-api
```

## Layer 3+ (explicitly NOT built here)

The exclusive migration lock (PI-133) and the reconciliation-gate enforcement
(PI-134) build on this pool. The `finding` (`FND-`) entity that DEC-397's
"records a finding" ultimately targets is a PI-134 reconciliation-gate build;
until it lands, the `needs_attention` flag is the recorded, queryable human
signal (`_record_finding` is best-effort and falls back to that flag).

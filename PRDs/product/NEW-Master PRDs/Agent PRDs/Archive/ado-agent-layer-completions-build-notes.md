# ADO agent-layer completions — build notes (PI-143 follow-ons, DEC-409)

Status: **Built on branch `pi-137-claim-lifecycle`** (stacked on PI-143 slices 1–3).
Three agent-layer refinements that were deferred after the deterministic
orchestration spine was whole. Each is a pure/injectable-seam addition with
deterministic tests; the real agents/git run in the attended end-to-end demo.

## 1. Reconcile agent — the finding *producer*

Slice 2 *enforced* the Develop gate but nothing *raised* findings, so it passed
vacuously. Now, after a Design phase completes, the driver spawns a reconciliation
reviewer (`build_reconcile_prompt` + `reconcile_phase_agent`, injectable
`reconcile_runner`) that reads the per-area design specs, checks them across areas,
and raises a `finding` per problem (`conflict | gap | dependency | overlap`, each
`blocking | advisory`) via `POST /findings` with a `finding_relates_to` edge to the
Design Workstream. A coherent design raises nothing. The slice-2 Develop gate then
holds the build on any open *blocking* finding. Runs only after a `Design` phase
(not Develop/Test); no code, no worktree — API writes only.

## 2. Parallel independent PIs

The PM can drive up to `max_parallel_pis` eligible PIs at once. **Safety is implied
by eligibility:** an eligible PI has every `blocked_by` predecessor Resolved, so no
two eligible PIs can block each other — the eligible-not-attempted set is a safe
parallel batch. Pure `eligible_batch(backlog, attempted, cap)` selects it; a round
runs the batch in a `ThreadPoolExecutor`, closes out each result in stable order,
and re-queries.

**Cross-PI git safety:** concurrent PIs' pools would otherwise each take their own
`_repo_lock` and race on `.git`. `ParallelCoordinatingRuntime` gained an optional
**shared `repo_lock`**; the PM creates one lock per run and threads it through
`AdoRuntimeConfig.repo_lock → run_pool_for_workstream`, so every PI's pool
serializes its worktree/merge git ops on the one repo. `max_parallel_pis=1`
(default) is the unchanged serial path.

## 3. Review/closure agent

A governance-faithful resolution path that the blunt `resolve_on_complete` (DEC-408)
lacked. With `review_on_complete`, the PM spawns a closure agent per completed PI
(`build_review_prompt` + `review_close_pi`, injectable `closure_runner`) that reviews
the delivered work and **resolves the PI only if it satisfies its requirements**;
a declined review leaves the PI `In Review` and flags it for a person. Verified by
result (PI reached `Resolved`). Takes precedence over the blunt lever, and lets
dependency chains flow *with judgment*.

## Where it lives

- `runtime/ado_runtime.py` — new seams `reconcile_runner` / `closure_runner`, pure
  `eligible_batch`, parallel `ProjectRuntime.run()`, `AdoRuntimeConfig.repo_lock`,
  config flags `review_on_complete` / `max_parallel_pis`, CLI flags
  `--review-on-complete` / `--max-parallel-pis`.
- `runtime/parallel_runtime.py` — optional shared `repo_lock` on
  `ParallelCoordinatingRuntime`.
- `tests/crmbuilder_v2/runtime/test_ado_runtime.py` — 23 tests total; the new ones:
  reconcile-after-Design-only; `eligible_batch` cap/skip; parallel start-window
  (proves concurrency); review resolves + flows a chain; review-decline leaves
  In Review.

## CLI

```bash
# Whole project, 3 PIs at a time, each completed PI reviewed + resolved:
crmbuilder-v2-ado-pm PRJ-NNN --max-parallel-pis 3 --review-on-complete --repo-root /path/to/repo
```

## What remains (the attended demo + tuning)

The deterministic harness is complete and pinned by tests. The remaining work is
**real-agent prompt tuning** discovered by running the end-to-end demo — a Project
whose PIs are scoped + reconciled + executed + reviewed by real agents, dependents
unblocking in order — which is run attended (it spawns real agents and makes
commits). Verification of the reconcile/closure prompts against real agent behavior
is part of that demo.

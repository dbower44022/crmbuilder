# Kick-off — Build the scheduler-resilience hardening (REL-055 / PRJ-093)

**Purpose:** build the two scheduler-resilience fixes captured after the REL-038
build. Engagement `ENG-001` (`X-Engagement: CRMBUILDER`), V2 API at
`http://127.0.0.1:8765`. Repo root `/home/doug/Dropbox/Projects/crmbuilder`.
Authored 2026-06-30 (the session that fought through the REL-038 build and hit
both failure modes live).

This is a **Claude Code build session**, not a deterministic script — the fixes
need real implementation + tests. Open a fresh session and work this prompt.

---

## 0. Governance is already in place — requirement-first is satisfied

You do **not** author requirements or PIs — they exist and are confirmed. Build
directly.

- **REL-055** — "Scheduler resilience hardening II" (manual execution_mode).
- **PRJ-093** — its project (`project_belongs_to_release` → REL-055).
- **REQ-440** (confirmed, via DEC-863) → **PI-379** (Draft) — pool-worker-failure halt.
- **REQ-441** (confirmed, via DEC-863) → **PI-380** (Draft) — concurrent-build guard.
- Provenance conversation `CNV-268` (under session `SES-301`), topic `TOP-099`
  (scheduler hardening — same topic as REQ-426/427).

Verify at start (heads churn): `curl -s -H "X-Engagement: CRMBUILDER"
http://127.0.0.1:8765/planning-items/PI-379` and `…/PI-380` — both should be
`Draft` under PRJ-093/REL-055. Read `REQ-440`/`REQ-441` and their
`requirement_notes` for the authoritative statement; read the "HARD LESSONS"
in the memory file `project_rel038_audit_role_reconcile` for the live context.

---

## 1. PI-379 / REQ-440 — a pool-worker failure must halt cleanly, never hang

**The bug (observed live):** a single-PI ADO driver (`crmbuilder-v2-ado PI-352`)
**slept ~2.5h with no progress** after a work-task pool worker failed
`git worktree add -b ado/wtk-256 … main` with **exit 255** (the branch already
existed — stale crash debris). The failure set `workstream_needs_attention`, but
the driver never terminated the pool / halted the phase — it blocked indefinitely
waiting on a slot that would never complete.

**Where it lives:**
- `/home/doug/Dropbox/Projects/crmbuilder/crmbuilder-v2/src/crmbuilder_v2/scheduler/parallel_scheduler.py`
  - `_spawn_one` (~L447) — creates the worktree (`with self._repo_lock:` ~L456)
    and spawns the agent. **This is where `git worktree add` can raise.**
  - `_worker` (~L507) — runs `_spawn_one`, puts the result on the completion
    queue. Its own comment (~L509) flags that `_spawn_one` makes "unprotected I/O
    calls." **If `_spawn_one` raises and `_worker` never enqueues a result, the
    `_fill_slots`/drain loop (~L754-L822) waits forever for that slot.**
- The coordinating (serial) path
  `…/scheduler/coordinating_scheduler.py` has the analogous spawn/verify/merge
  loop — fix both if both can hang. (`_git` there is already timeout-bounded by
  PI-366; the gap is the *spawn/worktree-add* failure, not a slow git call.)

**Fix direction:** make a worker that fails to start or errors **before** producing
a result always enqueue a *failure* result (so the slot frees and the pool drains),
**and** make the driver treat that as a clean phase halt → flag
`workstream_needs_attention` and **return** within the agent time budget. Never
`await`/join a slot whose worker died. (REQ-271 already forbids spin-waiting; this
is the structural sibling — don't block on a dead worker.)

**Test (regression):** in
`/home/doug/Dropbox/Projects/crmbuilder/tests/crmbuilder_v2/scheduler/test_parallel_scheduler.py`
(and/or `test_coordinating_scheduler.py`), monkeypatch the worktree-add / spawn
step to raise (simulate exit 255), run the pool, and assert it **returns / halts
within the budget** with the workstream flagged — not hangs. Mirror the existing
timeout-style tests (`test_run_pytest_timeout_does_not_propagate`,
`test_git_timeout_becomes_a_recoverable_failure`).

---

## 2. PI-380 / REQ-441 — concurrent builds on one working copy must not corrupt each other

**The bug (observed live):** two single-PI drivers (`crmbuilder-v2-ado PI-353` and
`crmbuilder-v2-ado PI-354`) were run **in parallel** against the one working copy.
PI-354's rollback (`git reset --hard <base>` + `git worktree prune`) **deleted
PI-353's live test worktree mid-`pytest`**, producing a `FileNotFoundError` flood
the affected-tests gate read as a **false `tests_failed`**. Good code was reverted.

**Why the existing locks don't cover it:**
- `parallel_scheduler.py` `_repo_lock` (~L325/335, used at ~L456/495/596/637/769/821)
  serializes git ops **within one pool** — but two **separate driver processes**
  each have their **own** `_repo_lock` instance, so they don't serialize against
  each other.
- The PI-364 run-lock (`ado_scheduler.py` ~L1058, `enforce_run_lock`) is **per
  Project** and DB-backed, and the **single-PI driver doesn't use it** (it's a
  `ProjectSchedulerConfig` field). REQ-441 needs a guard at the **working-copy**
  granularity, across processes.

**Fix direction (pick one, justify in the design):**
- **A repo/working-copy lock:** a file lock (e.g. `flock` on
  `<repo_root>/.git/crmbuilder-build.lock`) acquired by *any* build driver
  (single-PI `main`, PM `project_main`, the coordinating/parallel pools) at start
  and released at end; a second driver **refuses** (clean message) while held.
  Simplest; matches the "one builder per working copy" reality.
- **Per-driver worktree isolation:** each driver operates in its own checkout so a
  reset/prune can't reach another's worktree. More robust for true parallelism but
  larger.
  Recommend A unless you have reason for B; record the choice as a decision.

**Test:** assert a second build driver against a working copy already held is
**refused** (or isolated) — e.g. acquire the lock, then assert a second
acquisition fails fast / the second driver returns a "repo busy" result without
touching git. Keep it hermetic (a temp dir as the fake repo_root).

---

## 3. Build protocol (Model A) + close-out

- **Branch** off current `main` HEAD (`git rev-parse main` — agents/worktrees
  build on stale code otherwise). One branch is fine, e.g.
  `pi-379-380-scheduler-resilience`, or one per PI.
- Implement → **`ruff check` clean** on touched files → **`pytest` green** on the
  scheduler suites you touched + your new tests. Commit with explicit pathspec.
  **In Claude Code, you commit; Doug pushes.** (End commit trailers per CLAUDE.md.)
- **Governance bookkeeping lands on `main` after merge** (Branch-work protocol):
  do **not** resolve the PIs from the branch. After merge, a build-closure
  conversation (real-time, direct API POST — DEC-383) with `resolves` edges flips
  **PI-379** and **PI-380** → Resolved (mirror CNV-267 / CNV-266 from 2026-06-30).
- **Finalize REL-055:** like REL-043, this is hand-built off the pipeline, so the
  truthful terminal is **`delivered_off_pipeline`** (transition from
  `preliminary_planning`), **not** `shipped` — do not fabricate
  reconciliation/architecture/qa/test sign-offs for stages that never ran.

## 4. Heed the lessons that produced these requirements

- **Never run two single-PI drivers concurrently** against this repo while
  testing your fix (that's literally REQ-441's bug). Run serially, or via the PM
  (`ado-pm`, which shares one `_repo_lock`).
- The API on 8765 is desktop-owned and respawns; a brief outage can hand a driver
  an unhandled `Connection refused`. Restart it to load new scheduler code only
  if you run an actual ADO build; for unit tests it's irrelevant.
- `git worktree prune` + stale `ado/wtk-*` branches are the debris that triggers
  the worktree-add failure — clean them before any real driver run.

## 5. Deliverable

The two fixes + tests merged to `main` (Doug pushes), PI-379/PI-380 Resolved via
build-closure, REL-055 → `delivered_off_pipeline`. Update the memory file
`project_rel038_audit_role_reconcile` (and/or a new scheduler-resilience memory)
to mark REL-055 delivered.

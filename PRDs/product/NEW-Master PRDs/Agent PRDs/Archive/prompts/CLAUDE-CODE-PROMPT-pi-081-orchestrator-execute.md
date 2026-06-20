# CLAUDE-CODE-PROMPT — Implement the parallel-agent orchestrator execute path (PI-081) and run the WS-012 acceptance test

**Last Updated:** 05-30-26 15:30
**Operating mode:** DETAIL — concrete file-level edits, tests, commits. One logical unit at a time. Do not stay at the architecture level.
**Engagement:** Customer Relationship Management Builder dogfood engagement (CRMBUILDER).
**Repo:** `dbower44022/crmbuilder`, local clone at `~/Dropbox/Projects/crmbuilder/`.

---

## Purpose

Finish the one deliberately-unbuilt piece of the Parallel Agent Orchestrator (workstream WS-012): the live dispatch path `_execute()` in `crmbuilder-v2/scripts/orchestrator/run.py`, which today raises `NotImplementedError` by design. This is Planning Item PI-081 (orchestrator driver). The implementation is proven by running it — per Success Criterion §7.2 of the design doc, **the first orchestrator run is the acceptance test, not a separate phase.**

The orchestrator reads the open Planning Item backlog, partitions each dependency-depth wave into area-disjoint clusters (one child agent per cluster), and dispatches one Claude Code subagent per cluster. The pure planning/rendering cores in `planning.py` and `kickoff.py` are already built and unit-tested; this work is the I/O glue (identifier reservation, item claiming, git worktrees, subprocess spawn, wave-join, orchestrates-edge recording, and the orchestrator's own supervising close-out).

### Net effect on success
- `_execute()` implemented in `crmbuilder-v2/scripts/orchestrator/run.py`; `main()` already routes `--execute` into it under the singleton orchestrator lock.
- `tests/crmbuilder_v2/scripts/test_orchestrator_run.py` updated: the `test_execute_is_guarded` NotImplementedError test is replaced with real coverage of the execute glue (mocked subprocess/API/git). Pure-core tests stay green.
- One **bounded, watched acceptance run** dispatched: a single wave (`--max-depth 0`) with **at least two concurrent child agents**, each producing its own close-out payload, and the orchestrator producing its own supervising close-out that references each child via the `conversation_orchestrates_conversation` reference edge.
- One **operator guide** authored at `PRDs/product/crmbuilder-v2/orchestrator/operator-guide.md`, written against the working driver (real commands, flag values, log paths, and the halt-recovery/unclaim/worktree-cleanup steps).
- Two `reference_book` governance records created — one for `orchestrator/overview.md`, one for `orchestrator/operator-guide.md` — so both docs are queryable as first-class artifacts (consistent with the single-source-of-truth principle; methodology guides and schema specs are already tracked this way).
- One **builder-session close-out** authored and applied that **resolves PI-081** and records the wiring decisions below.

### Wiring decisions already made (do not re-litigate; implement as stated)
1. **Per-child git worktree.** Each cluster's child runs in its own `git worktree` on its own branch cut from `origin/main`. Concurrent children never share a working tree. This is what makes the area-disjoint conflict model safe on disk.
2. **Child autonomy = `--dangerously-skip-permissions`.** Children spawn non-interactively via `claude -p` with `--dangerously-skip-permissions` so they run fully unattended. (Accepted risk: this is the real repo, not a sandbox; containment is worktree isolation + area-disjoint scope + clean-git pre-flight + halt-on-failure + a watched first run.)
3. **Completion detection + halt-on-failure.** The orchestrator waits on each child subprocess, then verifies the child actually applied its close-out and resolved/addressed its Planning Items. Any child failure **halts the wave**, surfaces the failure and its log path, leaves the failed child's `claimed_by` in place for forensic review, dispatches no further waves, and exits non-zero. No retry, no requeue (design doc §4).
4. **First run is bounded and watched.** The first live `--execute` runs `--max-depth 0` (depth-0 wave only) and is gated behind an explicit human go (see the Checkpoint). Wider multi-wave runs come in later sessions.

---

## Halt-on-failure discipline
Every step verifies its outcome before the next begins. If a verification fails, STOP, print the failure, and do not proceed. Do not "work around" a failed governance write or a failed child.

---

## Step 0 — Orientation reads (do these first)

1. `CLAUDE.md` (repo root) — the operative engagement context and Working conventions. Note the **push convention**: in Claude Code you commit; **Doug pushes**. Do not push.
2. `specifications/governance-recording-rules.md` — authoritative governance recording rules. **Read before authoring any governance record.** Record creation goes through the API or `apply_close_out.py`, never the desktop UI. Pay attention to §3 Session Authoring, §4 Conversation Authoring, §7 Reference Authoring, §9 Close-Out Payload Authoring.
3. `PRDs/product/crmbuilder-v2/orchestrator/overview.md` — the living technical reference for the orchestrator (how it works: two layers, area-disjoint conflict model, static waves, governance grain, the dispatch lifecycle). Its §6 lifecycle is the same contract restated below; if anything conflicts, stop and flag it. The original planning doc `PRDs/product/crmbuilder-v2/orchestrator-planning.md` is retained as design history (architectural decisions and success criteria §7).
4. The existing orchestrator code, in full, before editing:
   - `crmbuilder-v2/scripts/orchestrator/run.py` (your edit target — `_execute` is the stub; `preflight`, `orchestrator_lock`, `fetch_ready_batches`, `plan_waves`, `render_child_kickoff`, `_load_template` already exist and are reused as-is)
   - `crmbuilder-v2/scripts/orchestrator/planning.py` and `kickoff.py` (pure cores — read, do not modify unless a test proves a defect)
   - `PRDs/product/crmbuilder-v2/orchestrator/child-agent-kickoff-template.md` (what each child receives; the placeholder contract `render_child_kickoff` must satisfy)
5. The contracts the glue calls into — read each to confirm exact request/response shapes rather than assuming:
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/identifiers.py` + `IdentifierReserveIn` in `schemas.py` — `POST /identifiers/reserve {entity_type, count, reserved_by, ttl_seconds}`.
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/planning_items.py` + `PlanningItemClaimIn` — `POST /planning-items/{identifier}/claim {claimant}`; **`claimant` is the child's conversation identifier (`CNV-NNN`/`CONV-NNN`)**, not the session id.
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/orchestration.py` — `GET /orchestration/ready-batches`.
   - The references and conversation/session create endpoints + `governance-recording-rules.md` §4/§7 for how to create the conversation, session, and the orchestrates edge. **Confirm the reference-create body key** (the API surface uses `relationship`, while the DB column/vocab use `relationship_kind`) against the live `POST /references` contract before posting.
   - The `{data, meta, errors}` envelope rule (CLAUDE.md): any inline read of an API response must unwrap `.data` first.

---

## Step 1 — Engagement guard (pre-flight, before any write)

The multi-tenancy routing bug means a running API can silently serve the wrong engagement database. Guard explicitly:

1. Confirm `crmbuilder-v2/data/current_engagement.json` resolves to **CRMBUILDER**.
2. Ensure the API on `http://127.0.0.1:8765` is up **and serving CRMBUILDER**: `GET /health`, then read the session head (`GET /sessions`, newest first, unwrap `.data`) and confirm it matches the CRMBUILDER lineage you expect from the snapshot under `PRDs/product/crmbuilder-v2/db-export/sessions.json`. Do not trust config alone — prove it by content.
3. If the API is absent or serving the wrong database: `fuser -k 8765/tcp`, then restart with `CRMBUILDER_V2_DB_PATH` set explicitly to the CRMBUILDER database, and re-verify (2).
4. Clean working tree (`git status --porcelain` empty), git identity set (`doug@dougbower.com` / `Doug Bower`), `git pull --rebase origin main`.

If any check fails, STOP. Do not write records against an unverified database.

---

## Step 2 — Implement `_execute()`

Implement the live dispatch in `run.py`. `main()` already calls it inside `orchestrator_lock()`. The contract, in order:

**Per run (once):**
1. `preflight(args.api_base, require_clean_git=True)` (already exists — reuse).
2. Create the orchestrator's **own supervising conversation + session** (design §2.3 / DEC-248), created `in_flight`, with the conversation joined to **WS-012** via the `conversation_belongs_to_workstream` edge. The child kickoffs reference this conversation as `{{orchestrator_conversation_identifier}}`.
3. `fetch_ready_batches(...)` then `plan_waves(...)` (already exist).

**Per wave, in ascending depth order:**
4. For every cluster in the wave, **concurrently**:
   a. **Reserve** the child's session and conversation identifiers via `POST /identifiers/reserve` (`count: 1` each, `reserved_by` = orchestrator conversation id). Use the reserved values; never compute next-available for a child.
   b. **Claim** each Planning Item in the cluster via `POST /planning-items/{id}/claim` with `claimant` = the child's reserved conversation id.
   c. **Create a git worktree** for the child: a fresh branch (e.g. `orch-wave{depth}-child{n}`) cut from `origin/main`, in its own working directory (e.g. under `~/.crmbuilder-v2/worktrees/` or a run-scoped temp dir). Children must not share a tree.
   d. **Render** the child kickoff with `render_child_kickoff(...)` using the reserved session/conversation ids, the orchestrator conversation id, the branch, the cluster's areas, and the cluster's Planning Items; **write the rendered file into the child's worktree** as its sole kickoff.
   e. **Spawn** one Claude Code subagent: `claude -p "<read and execute the kickoff at <path>, then stop>" --dangerously-skip-permissions` with `cwd` = the worktree path. Tee each child's stdout/stderr to a per-child log (e.g. `crmbuilder-v2/data/logs/orchestrator/<run-id>/child-wave{depth}-child{n}.log`). Consider `--output-format stream-json` for machine-readable progress and a `--max-turns` cap.
5. **Wait for the whole wave** (join all child subprocesses) before dispatching the next wave (static-wave scheduling, §2.4).
6. **Verify each child** succeeded: non-zero exit → failure; also confirm the child applied its close-out (its `ses_NNN.json` exists and was applied, its Planning Items moved to `Resolved`/addressed, a `deposit_event` landed). 
7. **On any child failure:** halt — print the failing child, its log path, and the unresolved Planning Items; **leave its `claimed_by` in place**; dispatch no further waves; transition the orchestrator session to a non-complete terminal state per the session lifecycle; exit non-zero.
8. **On wave success:** for each child, record the orchestrator→child edge `conversation_orchestrates_conversation` (source = orchestrator conversation, target = child conversation) via `POST /references`. (Children are instructed **not** to write this edge — the orchestrator owns it.)

**After all waves succeed:**
9. Author and apply the orchestrator's **supervising close-out** (its conversation + session), transitioning them to `complete`, summarizing the run and referencing each child. Follow the nine-section payload shape and the standard `apply_close_out.py` path from `governance-recording-rules.md` §9.

Keep `_execute` as thin I/O glue; if any non-trivial decision logic appears (e.g. branch naming, worktree pathing, child-success predicate), factor the pure part into a helper so it can be unit-tested without subprocesses.

---

## Step 3 — Tests

In `tests/crmbuilder_v2/scripts/test_orchestrator_run.py`:
- **Replace** `test_execute_is_guarded` (it asserts `NotImplementedError`, which is no longer true).
- Add coverage for the execute glue with `subprocess`, `requests`, and `git` mocked (no real API, no real spawns):
  - reserve happens before claim; claim happens before spawn;
  - one worktree + one rendered kickoff + one spawn per cluster, spawn invoked with `--dangerously-skip-permissions` and the child's worktree as `cwd`;
  - the wave join waits for all children before the next wave;
  - a simulated child failure halts the run, dispatches no further waves, leaves claims, and returns non-zero;
  - on success, one `conversation_orchestrates_conversation` edge is posted per child.
- Keep the pure-core tests (`test_orchestrator_planning.py`, `test_orchestrator_kickoff.py`) and the existing plan/render tests green.
- Run the orchestrator test files and the access/api orchestration tests; all green before proceeding.

---

## Step 4 — CHECKPOINT (human-watched; wait for go)

Before any live dispatch:
1. Run `--dry-run` (default) against the live backlog: `uv run python crmbuilder-v2/scripts/orchestrator/run.py --dry-run --max-depth 0 --out-dir /tmp/crmbuilder-orchestrator`.
2. Print the dispatch plan and confirm the **depth-0 wave has at least two area-disjoint clusters** (≥2 concurrent children) — the minimum to satisfy acceptance criterion §7.2.
3. **If depth-0 does not yield ≥2 disjoint clusters, STOP and report it** — the current backlog can't satisfy the concurrent-children acceptance test; do not improvise a workaround.
4. Surface the plan and the rendered child kickoffs to Doug and **wait for an explicit go**. Do not run `--execute` until Doug confirms.

---

## Step 5 — Acceptance run (after go)

Run the bounded, watched live dispatch:
```
uv run python crmbuilder-v2/scripts/orchestrator/run.py --execute --max-depth 0
```
Watch it. Verify Success Criterion §7.2:
- at least two child agents ran concurrently;
- each child produced and applied its own close-out payload;
- the orchestrator produced its own supervising close-out referencing each child via `conversation_orchestrates_conversation`.

If any child halts the run, follow Step 2.7 — surface the failure; do not retry blind.

---

## Step 6 — Operator guide (now that the driver works)

Author `PRDs/product/crmbuilder-v2/orchestrator/operator-guide.md` — the "how to run it" reference, written against the *working* driver so its commands match real behavior. Cover: the dry-run → read-plan → give-go → live-run loop; what "≥2 area-disjoint clusters at depth 0" means and when the backlog can't satisfy it; `--max-depth` / `--area` to bound a run; where per-child logs land and how to read them; and the halt-recovery path (claims left set on failure, releasing them via `POST /planning-items/{id}/release`, and cleaning up child worktrees with `git worktree remove`). Standard doc header: revision control + change log, `Last Updated` in `MM-DD-YY HH:MM`. Cross-link it from `orchestrator/overview.md` §9 (the pointer is already there).

---

## Step 7 — Builder-session close-out (resolve PI-081)

This builder session (the one implementing `_execute`) gets its own close-out, separate from the governance the orchestrator run produced:
1. Verify the next session identifier head (`GET /sessions`, unwrap `.data`; re-key if claimed in parallel per the SES-077 precedent). Author `PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json` — nine sections — listing **PI-081 under `resolves_planning_items`**, recording your implementation commits in `commits`, and capturing decisions for: per-child worktree isolation, `--dangerously-skip-permissions` child autonomy, completion-detection + halt-on-failure, and the bounded-first-run (`--max-depth 0`) policy. Reference the orchestrator run's supervising conversation as the acceptance evidence.
2. In the same close-out, create two `reference_book` records (per `governance-recording-rules.md`) pointing at `PRDs/product/crmbuilder-v2/orchestrator/overview.md` and `PRDs/product/crmbuilder-v2/orchestrator/operator-guide.md`, so both are first-class queryable artifacts.
3. Author the apply prompt `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md`.
4. Apply: `cd crmbuilder-v2 && uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json`.
5. Do not duplicate or re-apply the orchestrator's auto-produced governance (its supervising close-out and the children's close-outs were already applied during the run).

---

## Step 8 — Commit (Doug pushes)

Commit in logical units, all subjects prefixed `v2:` (this is v2 work):
- the `_execute` implementation + tests;
- the operator guide;
- the regenerated `db-export/*.json` snapshots + new `deposit-event-logs/dep_NNN.log` + builder close-out payload + apply prompt, in one commit per the close-out convention.

Per the Working conventions, **commit only — Doug pushes.** Do not push.

---

## Done block (reply with)
- session head before/after, and the builder session identifier that resolved PI-081;
- the acceptance run result: number of concurrent children, their conversation/session identifiers and close-out payload paths, and the orchestrator's supervising conversation/session identifiers;
- count of `conversation_orchestrates_conversation` edges written;
- the commit SHAs to push;
- whether all WS-012 §7.2 acceptance conditions were met, and if not, exactly what halted.

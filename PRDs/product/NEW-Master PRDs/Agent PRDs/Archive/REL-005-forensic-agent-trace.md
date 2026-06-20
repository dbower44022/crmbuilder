# REL-005 dev-lane run — full agent forensic trace

Forensic reconstruction of the REL-005 pipeline run (2026-06-18), built from the
live governance DB, the run log, the persisted LLM demand-set, and the 16
`claude -p` agent session transcripts under `~/.claude/projects/-tmp-ado-ado-wtk-*`.
Purpose: trace what every agent was *told* and what it *did*, to redesign the
instructions and guardrails. Governance: DEC-549 (the engagement-scoping fix that
let the run start), DEC-550 (the run findings).

> **Framing correction:** the deadlock that halted PI-231 was **not** produced by
> this run. PI-230/231's workstreams were created at **17:50** (an earlier REL-004
> attempt); my 21:21 run found them already decomposed and only *executed* the
> stale, malformed graph (`_plan` skips PIs that already have workstreams). The
> guard (`be02d792`) was not effective in the tree at 17:50. So the run is two
> separate stories: (A) the **LLM planning layer** that over-produced, and (B) the
> **16 area agents** that executed it — most discovering their work was already done.

---

## Layer 0 — the agent contract (identical template for all 16)

Every area agent received this exact prompt, varying only in the `### Your
assigned Work Task` block:

```
SYSTEM ROLE — you are an ADO Area Specialist (Developer tier) for the {AREA} area,
working in an isolated git worktree spawned from current `main`.
… Do the single-area work and produce the deliverable …
How: (1) Orient first … (2) Implement your one Work Task … (3) Self-verify.
(4) Commit on your worktree branch …
### Hard gates (ENFORCED — you may not mark the Work Task Complete until these pass)
- (ENFORCED) Self-verify … `ruff check` clean … and `pytest` green on the tests you
  wrote plus the existing tests for any module you edited. In a fresh worktree run
  only what you touched, not the full suite.
### Your assigned Work Task
- identifier / area / title / description
### How to operate … claim → do the work → commit → mark Complete → exit.
```

**Structural guardrail gaps visible in the template itself:**
- It says **"produce the deliverable"** — there is **no "already done / nothing to
  do → stop" path.** An agent that discovers its work exists must still manufacture
  *something* to satisfy "produce a deliverable."
- It has **no done-condition / acceptance criteria** for the work task beyond
  "self-verify with pytest." Fatal for "harden/already-built" tasks.
- The ENFORCED pytest self-verify has **no time budget** and **no guidance to run
  synchronously** — the agent is free to background-and-poll a slow Qt suite forever.
- It says commit *after* implement+verify (step 4) — so a kill before that step
  **loses all work** (exactly what happened to WTK-176's first run).
- There is **no "halt / needs-attention" exit** — an agent that detects a
  mis-scoped or duplicate task can only "flag for others" while still completing.

---

## Layer 1 — the reconciliation (demands) agent

Produced **10 demands; 6 of them for REQ-251, which was already shipped** (PI-229,
Resolved). Input was every *confirmed* in-scope requirement with **no delivered/Resolved
filter** (`_confirmed_requirements`, `release_runtime.py:662`), and the agent was never
told any were already built (input carries only name/description/acceptance).

| req | demands | already shipped? |
|-----|---------|------------------|
| REQ-251 | 6 | **YES (PI-229)** |
| REQ-249 | 2 | no |
| REQ-242 | 2 | no |

## Layer 2 — the architect (decomposition) agent

Given the **whole release's** delta-set per PI (`_plan` passes the same `delta_sets`
to every PI — `release_runtime.py:303,313`), so it decomposed **each PI as "build the
entire release."**

- **PI-230** → 12 work tasks covering REQ-249 + REQ-251 + **REQ-242** (WSK-152 status
  counts — *PI-231's* job, bundled in).
- **PI-231** → 15 work tasks (WTK-182–196): a **near-complete duplicate of PI-230** —
  approval (REQ-251/249, already built) **plus** status-counts (REQ-242) again — as
  **two feature tracks, each its own Design→Develop→Test triple**, serially chained →
  the Design-blocked-by-Test deadlock. Only the 4 Design agents (182–185) ran before
  the halt; WTK-186–196 never ran (the deadlock *saved* that spend).

---

## Layer 3 — the 16 area agents (what each was told vs. did)

### PI-230 Design (WSK-150) — all wrote markdown only; ruff/pytest "vacuous"
- **WTK-170** (methodology-product) — *"Design reviewer persona approval capability (REQ-251)."* 3.9 min. Read the **already-shipped** `access/review.py` + `ui/panels/review.py`, wrote a 166-line doc describing shipped behavior. **Waste: re-documented built code.**
- **WTK-171** (storage) — *"Design review_state post-approval semantics (REQ-249)."* 4.9 min. **The one with real value** — identified a genuine unbuilt gap (`activate_by_decision` doesn't reset `review_state`). Design-only, prose "test specs."
- **WTK-172** (methodology-process) — *"Design approve_requirement process contract."* 2.6 min. By its own report **mirrors WTK-170** — two docs for one shipped capability. **Waste: most redundant.**
- **WTK-173** (api) — *"Design status-counts read API (REQ-242)."* 3.5 min. Designs genuinely new functionality. Noted REQ-242 is `needs_review` and built against it anyway (borderline).

### PI-230 Develop (WSK-151/152)
- **WTK-174** (storage) — *"Implement review_state→current on approval (REQ-249)."* 3.0 min, **clean, real code**, single pytest run, caught a real edge case. **The model of a good run.**
- **WTK-175** (api) — *"Implement approve_requirement backend."* 5.0 min. **Discovered the backend was already fully built + tested (PI-229, `c47030d8`)**, did not duplicate it, added 2 gap-closing tests. Correctly flagged the REQ-249 postcondition as out-of-area. Mostly orientation.
- **WTK-176** (ui) — *"Implement panel approval affordances (REQ-251)."* **THE SPIN — see below.**
- **WTK-177** (access) — *"Wire reviewer authorization for approval."* Genuinely unbuilt, real code.

### PI-230 status-counts + Test (WSK-152/153)
- **WTK-178** (api) — *"Implement status-counts process (REQ-242)."* 3.9 min, **clean real build**, ran only the 2 relevant test files.
- **WTK-179** (ui) — *"Test approval workflow end-to-end."* 3.9 min. **Found workflow already built**, added 4 tests; ran the Qt suite **once, offscreen, single file** — well-behaved.
- **WTK-180** (access) — *"Test reviewer authorization."* 3.5 min. **Found the gate already shipped (WTK-177)**, added 5 tests, sub-second non-Qt run. Tightest run.
- **WTK-181** (api) — *"Test status-counts API."* 3.5 min. **WTK-178 had already written this test file** — extended it with 4 more. Modest Develop/Test overlap on one endpoint.

### PI-231 Design (WSK-154) — all four redundant; all four *knew* it
Every one **explicitly detected the capability already existed** and proceeded anyway:
- **WTK-182** (access) — *"Specify reviewer persona approval capability (REQ-251)."* Found "all pre-existing (PI-229)", wrote a new "access facet" doc anyway. **Independently flagged the PI-231 title mismatch** ("orchestration churn worth a coordinating-session check") — but had no way to halt.
- **WTK-183** (storage) — *"Design review_state transition (REQ-249)."* "the implementation already landed (commit `e2c2868a`)." Wrote a near-copy of WTK-171's doc under a new filename "to avoid merge conflicts with the parallel siblings." Also flagged the title mismatch.
- **WTK-184** (methodology-process) — *"Define approve_requirement process semantics."* "the behavior has already landed." Wrote a 354-line doc that *supersedes* WTK-172's.
- **WTK-185** (ui) — *"Design panel Approve affordances (REQ-251)."* **Reasoned about the duplication explicitly**: "Building affordances that already exist would have duplicated WTK-176" → so it wrote a 295-line doc of shipped UI instead, citing its siblings' identical redundant behavior as proof it was right.

**The decisive behavioral finding:** all four agents *quoted their own evidence* that
the work was already done, and **nothing in their contract made "already built" a stop
condition** — so each manufactured a redundant design doc. Two flagged the upstream
mis-scope but could only note-to-others while completing.

---

## The WTK-176 spin — precise anatomy of the 30-minute / SIGKILL failure

**Killed run** (`-nxxm-7g0`, 37 recorded tool calls, then hung to the 1800 s kill):
- **Real work done in ~90 seconds.** By call [8] it confirmed via
  `git merge-base --is-ancestor c47030d8 HEAD` that the entire deliverable was
  **already merged** (PI-229). Its own words at [13]: *"The implementation fully
  satisfies WTK-176 — it shipped in `c47030d8`."* Made 2 trivial test edits ([14],[15]).
- **Then ~13 min spinning on a pytest result it never received.** The pytest run was
  dispatched into a background-task channel whose `.output` file stayed empty. It
  **launched pytest 4 times** ([16],[19],[22],[25]) and cycled through
  `sleep 12; cat …output` → `sleep 18; cat` → `sleep 25; cat` → two
  `until grep -qE "passed|failed" …; do sleep; done` loops ([26],[29]) → a 180 s
  `Monitor` watcher ([34]) → finally `ps aux | grep -c "[p]ytest"` ([37]) to see how
  many pytest processes had piled up. Last text: *"I'll wait for the monitor
  notification rather than polling."* → **SIGKILL.**
- **It never committed** (commit is step 4, after verify) — so the kill **discarded
  everything**; `verify_result` saw no commits → `NOT_COMPLETE` → retry.

**Retry run** (`-t4qqwe2m`): hit the same output-capture bug but **escaped** by switching
to a bounded, self-marking pattern — `( … pytest > /tmp/r.txt; touch /tmp/done.txt ) &`
then `for i in $(seq 1 30); do [ -f /tmp/done.txt ] && break; sleep 2; done`. Did a real
testability refactor (extracted `_build_approval_context_menu() -> QMenu | None`,
matching the codebase convention because `monkeypatch QMenu.exec` **segfaults**), 6+6
tests green, committed `c745be74`. Succeeded — on essentially redundant work.

**Root causes of the spin (all citable):**
1. **Build task for already-built code** — no "already done → exit" path, so it stayed to verify a green test.
2. **Background-poll instead of synchronous run** — the agent backgrounded pytest and looped on an output channel that never delivered; no instruction to run tests in the foreground with a bounded wait.
3. **No time budget** — it polled patiently into the 1800 s kill.
4. **Commit after verify** — the kill lost all work; nothing was salvaged.
5. **Slow/flaky Qt suite** — `tests/crmbuilder_v2/ui` is hundreds of PySide6 tests with a known SIGSEGV flake; verifying it is exactly where an unbounded poll-loop is most dangerous.
6. **Wrong-area contract** — no `(ui, developer)` profile exists; the dispatcher fell back to **AGP-002 (storage-developer)** with `{AREA}`→`ui` string-substituted, so the orientation cues ("sibling endpoint", "edge direction") were storage-shaped, not Qt-shaped.

---

## Guardrail / instruction redesign (by failure mode)

**G1 — Don't dispatch already-delivered or out-of-scope work (upstream, highest leverage).**
- Exclude requirements whose implementing PI is terminal/Resolved from
  `_confirmed_requirements` and the in-scope traversals (`release_runtime.py:662`,
  `releases._in_scope_planning_items`).
- Slice the delta-set to the single PI before decomposing; the architect prompt must
  decompose **only the named PI's own requirement(s)**, never the whole release.

**G2 — Give every agent an "already satisfied → no-op exit" as step 0.**
Mandatory first action: check whether the work task is already satisfied on `main`
(feature present + tests green). If yes → mark the task **Not Applicable / Complete
(no-op)** with the evidence and **exit without manufacturing a deliverable.** This
alone would have ended ~8 of the 16 agents in under a minute.

**G3 — A "Design" phase must precede real Develop work, not retro-document shipped code.**
If the design already exists (or the code already ships), the Design workstream is
**Not Applicable**, not an excuse to write a superseding doc. Forbid "realized-contract"
/ "vN+1 facet" doc-versioning over built code.

**G4 — Fix the self-verify gate.**
- Run tests **synchronously in the foreground with a bounded timeout** — never via
  background-poll loops. Ship the retry's `seq … done-marker` pattern as the canonical
  snippet, or better, have the *runtime* (not the agent) run the affected-tests gate
  and tell the agent the result.
- **Commit before verify** (or auto-commit on exit) so a kill never discards work.
- Give the agent an explicit **time budget**; on overrun, commit-and-report rather than
  poll into a SIGKILL.

**G5 — Give agents a real "HALT / needs-attention" exit.**
When an agent detects a mis-scoped task, a title/linkage mismatch, or duplicate work
(as WTK-182/183/185 all did), it must be able to **stop the work task and escalate**,
not be forced to complete by producing filler. Route to the workstream
`needs_attention` flag the substrate already has.

**G6 — Real per-(area,tier) agent profiles, or refuse an area mismatch.**
No more handing a storage-developer contract to a ui task via tier-fallback. Either
seed per-area profiles or make `dispatcher.select_profile_id` refuse a mismatched area.

**G7 — Validate the whole decomposition graph (extend the PI-233 guard).**
At decompose time **and** before execution: at most one workstream per phase, phases a
subsequence of `Design→Develop→Test`, blocked_by acyclic. Re-validate an existing
decomposition before executing it (so stale/malformed graphs from a prior run can't be
inherited, as happened here). Clear a release's decompositions on cancel.

**G8 — Cap fan-out by requirement size.** Two trivial requirements produced 16 agents
(8 doc-only). The decomposer needs a size→task-count discipline and must skip
already-delivered work before spawning anything (folds into G1/G2).

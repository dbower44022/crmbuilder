# Build kickoff — PI-268: Redundant-work killers (the urgent trio)

**Session type:** BUILD (write code), not design. The design and decisions are done.
**Project:** PRJ-039 "Release Pipeline Agent Hardening".
**Planning item:** PI-268 (execution_mode `interactive` — built by hand/Claude Code, NOT the ADO fleet).
**Build order:** this is item 1 of 6 (DEC-613); it has no blockers and is the highest priority. Nothing else in the hardening set should be built before it, and the development lane must NOT be re-run until this lands.
**Branch:** create `pi-268-redundant-work-killers` off current `main` HEAD.

## Why this is first

The REL-005 run burned ~2 hours and ~$40 rebuilding already-shipped work. These three
requirements kill that failure mode at its three points: don't *plan* delivered work,
don't *build* a satisfied task, and let an agent *stop* when it spots redundancy. Full
forensics: `Archive/agent-pipeline-annotated-map.md` and `Archive/REL-005-forensic-agent-trace.md`
(in this folder), failure modes G1, G2, G5.

## Governance precondition — ALREADY MET (do not re-litigate)

All three requirements are **confirmed + human-approved**, and this PI implements them
(`planning_item_implements_requirement` edges exist). You are clear to write code. This is
the binding "requirement-first" precondition from the repo `CLAUDE.md`, already satisfied —
verify once at the API if you want (`GET /requirements/REQ-265` etc. → `confirmed`), then build.

## The three requirements (the contract you are building to)

**REQ-265 — Planning excludes already-delivered requirements.**
> When planning a release, the pipeline considers only requirements whose implementing work
> is not yet delivered. A finished capability is never planned, designed, or built again.
> **Acceptance:** a release whose scope includes an already-delivered requirement produces
> no demands, workstreams, or work tasks for that requirement.

**REQ-267 — Agents stop when the work is already done.**
> Before doing any work, an area agent checks whether its assigned task is already satisfied
> in the codebase. When it is, the agent records that no work is needed, with evidence, and
> exits without manufacturing a filler deliverable.
> **Acceptance:** an agent assigned an already-satisfied task exits reporting no work needed
> and creates no new artifact.

**REQ-272 — Agents can halt and escalate.**
> An agent can stop its task and raise it for human attention when it finds the task
> mis-scoped, duplicated, or already satisfied. It is never forced to finish by inventing a
> deliverable.
> **Acceptance:** an agent that detects a mis-scoped or duplicate task halts the task and
> raises it for human attention.

## The exact code seams (verified current as of this kickoff)

> Note: the scheduler files were renamed from `*_runtime.py` to `scheduler/*_scheduler.py`.
> Per the terminology governance, the scheduling layer is the **scheduler** (not "runtime"/
> "orchestrator"); keep that vocabulary in new code, comments, and docstrings. Agent display
> names end in "Agent"; the scheduler is not an agent and carries no suffix.

### REQ-265 — exclude already-delivered (the planning filter)
- **`crmbuilder-v2/src/crmbuilder_v2/scheduler/release_scheduler.py:689`** — `_confirmed_requirements(session, rid)` gathers in-scope confirmed requirements with **no delivered filter** (this is the G1 wound — it fed REL-005 six demands of already-shipped REQ-251).
- **`crmbuilder-v2/src/crmbuilder_v2/access/repositories/releases.py:192–214`** — `_in_scope_projects` / `_in_scope_planning_items` / `_in_scope_requirements`, the traversal the demands + decompose paths share.
- **Change:** exclude a requirement whose implementing planning item is terminal/`Resolved` (and, defensively, a requirement already `confirmed`-and-delivered). Decide one chokepoint — filtering in `_confirmed_requirements` AND wherever decompose re-derives in-scope items — so neither demands nor decomposition emit work for delivered requirements. "Delivered" = the implementing PI (via `planning_item_implements_requirement`) is `Resolved` (or `In Review`, matching `delivered_statuses`).
- **Acceptance test:** a release scoping one delivered + one undelivered requirement → demands/workstreams/work-tasks only for the undelivered one.

### REQ-267 — no-op exit when already satisfied (step 0 for the worker)
- **`crmbuilder-v2/src/crmbuilder_v2/scheduler/coordinating_scheduler.py:338`** — `operating_protocol(...)`. Today step 1 = claim, **step 2 = "Do the work"** — there is NO "is it already done?" step 0.
- **Change:** insert a mandatory **step 0**: before doing anything, the agent checks whether the task is already satisfied on `main` (feature present + its tests green). If yes, it records the evidence and marks the Work Task **Complete as a no-op / or Not Applicable** with a reason, and exits **without creating an artifact**. Define the no-op outcome explicitly (a recorded reason on the work task, and no commit) so the scheduler's verify step can tell a legitimate no-op from an empty failure — coordinate with `verify_result` (same file) which today treats Complete-with-no-commits as suspect (`NO_COMMITS`). A no-op needs a first-class signal, not a silent empty branch.
- **Acceptance test:** an agent given an already-satisfied task exits reporting no work needed, creates no new file/commit, and the scheduler accepts that as a clean no-op (not a retry).

### REQ-272 — halt and escalate (agent-facing path to needs_attention)
- **`scheduler/coordinating_scheduler.py:862`** — `_flag_needs_attention(...)` sets `workstream_needs_attention` + reason, but it is **scheduler-side only**; the agent has no instructed path. `pause_reason_for(...)` (line 296) + `run_one` (line 624) already make the scheduler **pause** when the flag is set — so the runtime half of halt largely exists.
- **`crmbuilder-v2/src/crmbuilder_v2/api/routers/workstreams.py:93–94`** — `PATCH /workstreams/{id}` already accepts `workstream_needs_attention` + `_reason`, so an agent *can* set it over the API.
- **Change:** give the agent an explicit **HALT affordance** in the operating protocol: when it detects a mis-scoped, duplicated, or already-satisfied task it cannot honestly complete, it sets the owning workstream's `needs_attention` flag (with a concrete reason) over the API and exits **without inventing a deliverable**. Confirm the scheduler then routes that workstream to a human pause rather than a retry loop (it should, via `pause_reason_for`; verify and close any gap). Distinguish halt (something is wrong → human) from no-op (nothing to do → clean exit) — REQ-267 vs REQ-272.
- **Acceptance test:** an agent that detects a mis-scoped/duplicate task flags the workstream `needs_attention` and exits; the scheduler pauses for a human and does not re-dispatch it as filler.

## Build conventions (repo CLAUDE.md — the ones that bite here)

- **Branch-work protocol (Model A):** the `pi-268-...` branch carries only code + tests. Do
  NOT run `apply_close_out.py` and do NOT commit under `deposit-event-logs/` on the branch —
  governance bookkeeping (the session/decision records) lands on `main` after merge.
- **Commit with explicit pathspec** (`git commit -- <files>`), never a bare `git commit` —
  parallel ADO schedulers stage files on the shared tree and a bare commit sweeps them in.
- **Spawn worktrees from current `main` HEAD** if you sub-spawn anything (you shouldn't need to).
- **Full absolute file paths** when naming files. **Plain language** in any report to Doug.
- **Real-time governance** is for `main`; on the branch just build + test. The session record,
  the implementing-decision, and the deposit-event log are authored on `main` at merge/close.

## Definition of done for PI-268

1. All three acceptance criteria above hold, each with a test that exercises it.
2. `ruff check` clean on touched files; `pytest` green on the touched scheduler/access modules
   (run the affected tests synchronously — do not background-poll; this PI is literally about
   not doing that).
3. The trio is mergeable to `main` as the first hardening tranche.
4. On `main` after merge: author the build-closure governance (a session record + an
   implementing decision noting the trio landed; resolve PI-268 via its delivering close-out),
   per the DEC-232 / build-closure pattern.

## Orientation reads (Tier 1–4)

1. This kickoff + the three requirement records (`GET /requirements/REQ-265|267|272`).
2. `Archive/agent-pipeline-annotated-map.md` (the whole-picture map; the trio is in cluster 1–2).
3. `Archive/REL-005-forensic-agent-trace.md` — G1 (don't dispatch delivered work), G2
   (already-satisfied → no-op exit), G5 (halt/needs_attention). The WTK-176 spin anatomy shows
   exactly why no-op + halt matter.
4. The seams above, read live before editing (other sessions move this tree; re-confirm
   line numbers).

## Carried-in guardrails

- Do NOT touch the `pi-261-scoped-publish` branch or the PI-230/231 tree — other sessions own those.
- Do NOT re-run the development lane until this PI is merged.
- The remaining build order after this (DEC-613): PI-269 planning filters, PI-273 observability,
  PI-270 worker guardrails, PI-271 contract infrastructure, PI-272 execution model.

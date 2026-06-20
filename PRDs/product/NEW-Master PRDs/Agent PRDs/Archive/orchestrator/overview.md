# Parallel Agent Orchestrator — Technical Overview

**Document type:** Internal V2 technical reference (not a client-facing methodology document).
**Repository:** `crmbuilder`
**Path:** `PRDs/product/crmbuilder-v2/orchestrator/overview.md`
**Workstream:** Parallel Agent Orchestrator (WS-012)
**Last Updated:** 05-30-26 15:45
**Version:** 1.0

---

## Status

This is the living technical reference for the parallel agent orchestrator. It supersedes the original planning artifact (`PRDs/product/crmbuilder-v2/orchestrator-planning.md`) as the description of *how the system works*; the planning doc is retained as the historical design record and its roadmap is reproduced, demoted, in Appendix A.

The live-dispatch path of the driver (`_execute()` in `crmbuilder-v2/scripts/orchestrator/run.py`) is the final piece being completed under the orchestrator-driver planning item (PI-081); until it lands, `--execute` raises `NotImplementedError` by design and only the `--dry-run` planning/rendering path is exercised. The architecture below is settled regardless of that wiring. A companion operator guide (`PRDs/product/crmbuilder-v2/orchestrator/operator-guide.md`) — the step-by-step "how to run it" reference — is authored against the working driver as part of the PI-081 build, so its exact commands and recovery steps match real behavior.

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-30-26 15:45 | Doug Bower / Claude | Initial technical overview. Evolved from the WS-012 planning document: architecture, governance model, and dispatch lifecycle promoted to present-tense reference; ten-PI roadmap and the six SES-079 architectural decisions demoted to Appendix A (planning history). |

---

## Change Log

**Version 1.0 (05-30-26 15:45):** Created as the living technical reference, splitting "how it works" (this document) from "how it was planned" (the retained planning doc) and "how to run it" (the forthcoming operator guide). Describes the two-layer orchestrator/child model, the area-disjoint conflict model, static-wave scheduling over `blocked_by` dependencies, the per-agent-plus-supervisor governance grain, and the concrete dispatch lifecycle the driver performs.

---

## 1. What it is

The orchestrator is internal development tooling. It changes the throughput model for working through the open planning-item backlog of a single engagement from "one developer-driven Claude Code session at a time" to "several area-disjoint child agents at once, supervised."

It queries open work, partitions it by **area** so two agents cannot trample each other on the same files, respects declared dependencies between planning items, and dispatches one Claude Code subagent per area-disjoint work cluster. Each child runs to completion on its own branch and produces its own governance close-out. The orchestrator's own conversation supervises the run and records a parent/child link to each child conversation, so the governance timeline has a walkable supervisor → child structure.

It is *not* part of the client-implementation methodology (the Master CRMBuilder PRD) and *not* part of the CRM Builder product the end customer uses. It is a tool an operator runs at the terminal via Claude Code.

It sits on top of substrate that already exists: the v0.7 governance entities (workstream, conversation, work_ticket, close_out_payload, deposit_event) and the v0.8 code-change-lifecycle methodology (planning-item `blocked_by` dependencies, `resolves`/`addresses` edges, atomic commit ingestion). What the orchestrator adds is the partition-and-dispatch layer over that substrate.

## 2. The two layers

**The orchestrator (supervisor).** One process, run at the operator's terminal. It plans the run, dispatches children, waits for each wave, records the supervisory governance, and halts on failure. It produces its own conversation + session pair.

**Child agents (workers).** One Claude Code subagent per area-disjoint cluster, each spawned non-interactively in its own git worktree on its own branch, each reading a rendered kickoff as its sole instruction, each producing its own conversation + session pair and applying its own close-out. Children stay strictly inside their claimed areas; cross-area work is the orchestrator's to sequence, not a child's to grab.

## 3. Work partitioning — the area model

**Area-level parallelism.** The orchestrator spawns one agent per *area* of work, not one per planning item. An area is a label that maps to filesystem topology (for example `v2-storage`, `v2-access`, `v2-api`, `v2-mcp`, `v2-ui`, the CBM domain areas, the methodology areas, `infrastructure`, and the v1 areas). The registered set is the single source of truth in `crmbuilder_v2.access.vocab.AREAS` — consult it there rather than relying on any list copied into prose, which can drift.

**Multi-valued area.** A planning item's `area` is a set (JSON array), not a scalar. An item that crosses subsystem boundaries declares every area it touches. This lets cross-cutting work be labelled honestly instead of being forced into one bucket.

**The conflict rule (hard).** Two planning items conflict iff their area sets intersect. Two clusters in the same wave must have disjoint area sets, so their agents never touch the same files concurrently. An item with no area cannot be parallelised — its file footprint is unknown — so it is set aside as *unclustered* rather than dispatched. These unclustered items, along with any items in a dependency cycle, are precisely the work that needs human design attention before it can be automated.

## 4. Scheduling — static waves

The orchestrator computes a dependency depth for every open planning item from the existing `blocked_by` references (planning-item → planning-item): depth 0 has no unresolved open blockers, depth 1 depends only on depth 0, and so on. A `blocked_by` edge to an already-resolved item is treated as satisfied. Cycles cannot be assigned a finite depth and are surfaced separately with a warning rather than failing the run.

All items at depth N run concurrently as one **wave**; the orchestrator waits for that wave to finish before dispatching wave N+1. Dynamic dispatch — recomputing the ready set on every completion and dispatching immediately — is deferred (see §8); for the current backlog's modest depth and wave size, static waves cost little and are far simpler.

The depth-grouped, area-annotated open backlog for one engagement is served by the orchestration ready-batches query (`GET /orchestration/ready-batches`), which returns each item's identifier, title, executive summary, area set, and current claim holder.

## 5. Governance model

**Per-agent grain.** Each child produces one conversation and one session record; the orchestrator produces its own conversation + session pair. A session is the unit of coherent work by one worker, and a child agent is one worker — consolidating all children into one mega-session would lose the per-agent boundary the governance model already supports.

**Supervisor → child links.** The orchestrator's conversation references each child's conversation via the `conversation_orchestrates_conversation` reference edge. The orchestrator owns and writes these edges when it ingests each child's close-out; children are explicitly instructed not to write them.

**Identifier reservation.** Child agents never compute next-available identifiers themselves — concurrent writers would race. The orchestrator reserves a block of identifiers per child up front via the reservation endpoint (`POST /identifiers/reserve`, taking `entity_type`, `count`, an optional `reserved_by` conversation claim, and a TTL), and hands the child its pre-allocated session and conversation identifiers in the rendered kickoff.

**Claiming.** Before a child is dispatched, each planning item in its cluster is claimed atomically (`POST /planning-items/{identifier}/claim`), with the claimant being the child's conversation identifier. A claim prevents any other agent from grabbing the same item. On child failure the claim is deliberately left in place for forensic review; releasing it (`POST /planning-items/{identifier}/release`) is a manual or future-automated cleanup step.

**Executive summaries.** The `executive_summary` field on planning items, decisions, and sessions is the legibility companion to orchestration: every dispatch logs which items each agent is working, and a non-technical reviewer needs to understand what is in flight without parsing implementer-facing description text.

## 6. Dispatch lifecycle

What a live run performs, in order:

1. Acquire the singleton orchestrator file lock (no two orchestrators run at once) and pre-flight: clean git working tree, API healthy, an engagement is set.
2. Create the orchestrator's own supervising conversation + session (created in-flight), with the conversation joined to the workstream.
3. Fetch the ready batches and plan each wave into area-disjoint clusters.
4. For each wave, in ascending depth order, and for each cluster concurrently:
   a. Reserve the child's session and conversation identifiers.
   b. Claim every planning item in the cluster under the child's conversation identifier.
   c. Create a git worktree for the child on a fresh branch cut from `origin/main`, in its own working directory.
   d. Render the child kickoff from the template, substituting the reserved identifiers, the supervising conversation, the branch, the claimed areas, and the cluster's planning items; write it into the worktree.
   e. Spawn one Claude Code subagent non-interactively (`claude -p … --dangerously-skip-permissions`) with the worktree as its working directory, teeing its output to a per-child log.
5. Wait for the whole wave to finish before dispatching the next (static-wave scheduling).
6. Verify each child succeeded — non-zero exit is failure, and success additionally requires the child to have applied its close-out and moved its planning items to resolved or addressed.
7. On any child failure: halt the wave, surface the failure and its log path, leave the failed child's claim in place, dispatch no further waves, and exit non-zero. No retry, no requeue.
8. On wave success: record the `conversation_orchestrates_conversation` edge from the orchestrator to each child.
9. After all waves succeed: author and apply the orchestrator's own supervising close-out, transitioning its conversation and session to complete.

## 7. API and code surface

**Endpoints the orchestrator uses:** the ready-batches query (`GET /orchestration/ready-batches`), identifier reservation (`POST /identifiers/reserve`), and planning-item claim/release (`POST /planning-items/{identifier}/claim` and `/release`). All API responses use the `{data, meta, errors}` envelope; any direct read unwraps `.data` first.

**Code:** the driver (`crmbuilder-v2/scripts/orchestrator/run.py`, the I/O glue — file lock, git, subprocess, API) on top of two pure, unit-tested cores: wave partitioning (`planning.py`) and kickoff rendering (`kickoff.py`). The child-agent kickoff template lives at `PRDs/product/crmbuilder-v2/orchestrator/child-agent-kickoff-template.md`; the driver renders a concrete copy per child at dispatch time.

**Isolation and autonomy:** each child runs in its own git worktree (separate working directory per branch, so concurrent branches never collide on disk) and is spawned with `--dangerously-skip-permissions` so it runs fully unattended. The containment around that autonomy is worktree isolation, the area-disjoint scope rule, a clean-git pre-flight, halt-on-failure, and a human-watched first run — not a sandboxed container.

## 8. Out of scope (deferred)

- **Dynamic dispatch scheduling.** Static waves only; an upgrade candidate once real runs reveal throughput cost from wave-join idle time.
- **Cross-engagement orchestration.** One engagement per invocation. A run spanning CRMBUILDER and Cleveland Business Mentoring is two separate invocations.
- **Automated failure recovery.** Halt-and-surface only; no retry, no requeue. Crashed agents leave their claim set for manual cleanup.
- **Work-ticket dispatch.** The child kickoff is a markdown template, not a work_ticket record. Promoting it is a later candidate.
- **Orchestrator UI.** Runs at the terminal; visibility comes from per-child logs and the governance records each agent produces.

## 9. Pointers

- **How to run it:** `PRDs/product/crmbuilder-v2/orchestrator/operator-guide.md` (authored against the working driver under PI-081).
- **Design history:** `PRDs/product/crmbuilder-v2/orchestrator-planning.md` (the original planning artifact) and Appendix A below.
- **Child kickoff template:** `PRDs/product/crmbuilder-v2/orchestrator/child-agent-kickoff-template.md`.
- **Governance recording rules:** `specifications/governance-recording-rules.md` (authoritative for how any of these records are written).

---

## Appendix A — Planning history

Reproduced from the original planning document for traceability. These are the decisions and roadmap as taken at the planning session (SES-079); the present-tense sections above are authoritative for current behavior.

**Architectural decisions (SES-079).** Full context, rationale, alternatives, and consequences live in the decision records:
- Area-level parallelism (DEC-246) — one agent per area, not per planning item.
- Multi-valued area (DEC-247) — `area` is a set; items conflict iff their area sets intersect.
- Per-agent conversation+session plus an orchestrator conversation+session (DEC-248).
- Static-wave scheduling (DEC-249) — topological sort over `blocked_by`, dispatch by depth.
- Executive summary as a structured field (DEC-250) — required on planning items, decisions, sessions.
- Executive-summary work bundled into this workstream (DEC-251) rather than carved out separately.

**Ten-planning-item roadmap (PI-053 through PI-062), in two tracks.**

*Bootstrap track:* add the executive-summary field (PI-053) and backfill it (PI-054); add the multi-valued `area` field and vocabulary (PI-055); add `claimed_by`/`claimed_at` (PI-056); register the `conversation_orchestrates_conversation` reference kind (PI-059).

*Orchestrator track:* the identifier reservation API (PI-057); the orchestration ready-batches API (PI-058); the child-agent kickoff template (PI-061); backfill `area` on open items (PI-062); the orchestrator driver script (PI-060). The live-dispatch path of that driver is completed under PI-081.

**Original success criteria.** The workstream is complete when all ten planning items resolve; a test run dispatches at least two child agents concurrently, each producing its own close-out, with the orchestrator producing a supervising close-out referencing both children via `conversation_orchestrates_conversation`; and the executive-summary field is populated on every planning item, decision, and session in the CRMBUILDER engagement database. The first orchestrator run is the acceptance test, not a separate validation phase.

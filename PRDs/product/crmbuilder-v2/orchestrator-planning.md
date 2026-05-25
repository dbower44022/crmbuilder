# Parallel Agent Orchestrator — Planning Document

**Document type:** Application development planning (planning only; not implementation)
**Repository:** `crmbuilder`
**Path:** `PRDs/product/crmbuilder-v2/orchestrator-planning.md`
**Workstream:** WS-012 (Parallel agent orchestrator and executive summary)
**Last Updated:** 05-25-26 22:00
**Version:** 1.0 (initial draft)

---

## Status

This document is the **planning artifact** for WS-012 — a Claude Code orchestrator that spins up multiple parallel agents to work through the open planning-item backlog. It captures the architectural decisions made at SES-079, lays out the planning-item roadmap, and serves as the design authority for the implementation work that follows.

The workstream also covers a cross-cutting governance legibility extension — adding an `executive_summary` structured field to `planning_items`, `decisions`, and `sessions` — that the orchestrator depends on. The exec-summary work is folded into this workstream rather than carved out separately because (a) it is small, (b) the orchestrator is its first real consumer (every PI it dispatches needs a PM/exec-readable summary the dispatcher logs), and (c) splitting would create workstream proliferation without clarity benefit.

The work is anticipated to span ten planning items (PI-053 through PI-062), divided into a foundational bootstrap (schema + vocabulary + backfill) and the orchestrator proper (APIs + driver + child prompt template).

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-25-26 22:00 | Doug Bower / Claude | Initial planning document. Captures six architectural decisions from SES-079 (area-level parallelism, multi-valued area, per-agent conversation+session pairs, static-wave scheduling, executive-summary as structured field, exec-summary bundled into orchestrator workstream). Lays out the ten-PI roadmap with dependencies. |

---

## Change Log

**Version 1.0 (05-25-26 22:00):** Initial creation. Architects a parallel agent orchestrator using area-level work partitioning, multi-valued area sets for cross-cutting items, static-wave scheduling via the existing `blocked_by` reference kind, and per-agent conversation+session pairs supervised by an orchestrator conversation+session pair. Adds executive-summary structured field across PI/DEC/SES as the bootstrap that makes orchestrator-dispatched work legible to non-technical reviewers. Documents the ten planning items in dependency order. Notes that the v0.7 governance entity model (workstream, conversation, work_ticket, close_out_payload, deposit_event) and the v0.8 code-change-lifecycle methodology (`blocked_by`, `resolves`, `addresses`, commit ingestion) provide most of the substrate; this workstream adds the orchestration layer on top.

---

## 1. Motivation

The CRMBUILDER engagement carries 33 open planning items as of SES-079. Most are independent of each other (different subsystems, different domains, different abstraction layers); a smaller number form short dependency chains. Working through them serially via single-conversation Claude Code sessions is the current pattern, and it scales linearly with developer time.

A parallel agent orchestrator changes the throughput model. The orchestrator queries open work, partitions it by area (so two agents can't trample each other on the same files), respects declared dependencies via `blocked_by`, and dispatches one Claude Code subagent per area-disjoint work cluster. Each agent runs to completion on its own branch and produces its own close-out payload. The orchestrator's own conversation supervises the run and records the parent-child relationship to each child conversation.

The model leverages the v0.7 governance entity substrate (workstream, conversation, work_ticket, close_out_payload, deposit_event) and the v0.8 code-change-lifecycle methodology (`blocked_by` PI dependencies, `resolves`/`addresses` edges, atomic commit ingestion). What it adds is (a) the `area` field on planning items so the orchestrator can partition work safely, (b) `claimed_by`/`claimed_at` so two agents never grab the same item, (c) an identifier reservation API so child agents don't race on next-available identifiers, (d) an orchestration query API that returns ready batches grouped by dependency depth, (e) a new `conversation_orchestrates_conversation` reference kind for the supervisor/child relationship, (f) the orchestrator driver script itself, and (g) the standardized child-agent kickoff prompt template.

The executive summary field is the legibility companion: every orchestrator dispatch logs which planning items each agent is working on, and a non-technical reviewer reading that log needs to understand what's in flight without parsing implementer-facing description text.

---

## 2. Architectural Decisions

Six decisions taken at SES-079 govern this workstream. They are summarized below in the order taken; full context, rationale, alternatives, and consequences for each are captured in the `decisions` table records DEC-246 through DEC-251.

### 2.1 Area-level parallelism (DEC-246)

The orchestrator spawns one agent per **area** of work, not one agent per planning item. Area is a label that maps to filesystem topology (`v2-storage`, `v2-access`, `v2-api`, `v2-mcp`, `v2-ui`, `cbm-mn`, `cbm-mr`, `cbm-cr`, `cbm-fu`, `cbm-services`, `methodology-interviews`, `methodology-process`, `methodology-templates`, `methodology-product`, `infrastructure`, `v1-automation`, `v1-espo`, `v1-programs`). Two agents whose work overlaps on an area are not allowed to run concurrently — the orchestrator serializes them.

Alternatives considered: per-PI parallelism (every PI gets an agent; maximum throughput but requires file-level conflict detection that PI metadata doesn't currently support) and file-affected-set parallelism (each PI declares the files it touches; theoretically right but requires authoring discipline that doesn't yet exist). Area-level sits in the middle: more parallel than serial, less complex than per-PI, naturally aligned with the codebase's existing module boundaries.

### 2.2 Multi-valued area (DEC-247)

A planning item's `area` field is a **set** (JSON array), not a scalar. A PI that crosses subsystem boundaries (e.g., a refactor that touches both `v2-access` and `v2-api`) declares both areas. The orchestrator's conflict-detection rule is: two PIs conflict iff their area sets intersect. This lets cross-cutting items be labeled honestly rather than forced into a single primary bucket.

Cost: slightly more conflict-detection logic in the orchestrator (set intersection rather than equality) and slightly more authoring discipline ("what does this PI touch" rather than "which bucket"). Both are small relative to the correctness gain.

### 2.3 Per-agent conversation+session, plus an orchestrator conversation+session (DEC-248)

Each child agent produces its own `conversation` record and its own `session` record (one CONV, one SES per agent). The orchestrator itself also produces a CONV+SES pair. The orchestrator's CONV references each child's CONV via a new reference kind `conversation_orchestrates_conversation`, giving the governance timeline a parent/child structure that audit queries can walk.

This is the right grain because a session is the unit of coherent work by one worker; an agent is one worker. Consolidating all agents' work into one mega-session would lose the per-agent boundary that the governance model already supports.

### 2.4 Static-wave scheduling (DEC-249)

The orchestrator computes a topological sort of open PIs (using existing `blocked_by` references) into dependency depths. All PIs at depth N run concurrently, then the orchestrator waits for that wave to complete before dispatching wave N+1.

Dynamic dispatch — recomputing the ready set on every agent completion and dispatching immediately — is a future optimization. It is meaningfully more complex to implement (state machine vs. serial driver) and the throughput gain depends on PI duration variance and DAG shape; for current backlog characteristics (modest depth, modest wave size), static waves cost little.

### 2.5 Executive summary as a structured field (DEC-250)

`executive_summary` becomes a required field on `planning_items`, `decisions`, and `sessions`. Type TEXT NOT NULL with a length check of 200–800 characters. Written for PMs and executives; the implementer-facing description (or `summary`/`topics_covered` on sessions) remains separately. The field is queryable, displayable independently in lists, and validated at the access layer.

The convention was a real fork — markdown-convention inside the existing description field was the alternative. Field beats convention because the audience separation belongs in the data model, not in author discipline.

### 2.6 Executive-summary work bundled into WS-012 (DEC-251)

The exec-summary schema/backfill work lives in WS-012 alongside the orchestrator work rather than as its own separate workstream. Reasoning: with the workstream entity itself already shipped in v0.7, the residual cross-cutting "governance platform extension" content is just exec-summary, which is small enough that splitting into its own workstream creates more bookkeeping than clarity. The orchestrator is also the first real consumer of the field, so the dependency direction is natural.

---

## 3. Planning Item Roadmap

Ten planning items, PI-053 through PI-062, in two tracks. Dependencies declared via the existing `blocked_by` reference kind (planning_item → planning_item).

### 3.1 Bootstrap track (exec summary, schema groundwork)

| PI | Title | Blocked by |
|----|-------|-----------|
| PI-053 | Add `executive_summary` field on planning_items, decisions, sessions | — |
| PI-054 | Backfill `executive_summary` on existing records | PI-053 |
| PI-055 | Add `area` field on planning_items (multi-valued JSON, vocabulary) | — |
| PI-056 | Add `claimed_by` / `claimed_at` fields on planning_items | — |
| PI-059 | Register `conversation_orchestrates_conversation` reference kind | — |

### 3.2 Orchestrator track

| PI | Title | Blocked by |
|----|-------|-----------|
| PI-057 | Implement identifier reservation API (`POST /identifiers/reserve`) | — |
| PI-058 | Implement orchestration ready-batches API (`GET /orchestration/ready-batches`) | PI-055, PI-056 |
| PI-061 | Build child agent kickoff prompt template | PI-055, PI-059 |
| PI-062 | Backfill `area` on currently-open planning items | PI-055 |
| PI-060 | Build orchestrator driver script (Python, runs in Claude Code) | PI-053, PI-054, PI-055, PI-056, PI-057, PI-058, PI-059, PI-061, PI-062 |

### 3.3 Wave structure under static-wave scheduling

When this workstream itself is dispatched (manually, until PI-060 lands), the implementation waves are:

- **Wave 1:** PI-053, PI-055, PI-056, PI-057, PI-059 (all unblocked).
- **Wave 2:** PI-054 (after PI-053), PI-058 (after PI-055+055), PI-061 (after PI-055+058), PI-062 (after PI-055).
- **Wave 3:** PI-060 (driver, after everything).

Wave 1's five items are independent and can land in any order. Wave 2's four items can land concurrently. Wave 3 is single.

---

## 4. Out of Scope (Deferred)

Explicitly not in WS-012:

- **Dynamic dispatch scheduling.** Static waves only in this workstream. Upgrade-path candidate once orchestrator runs reveal real throughput cost from wave-join idle time.
- **Cross-engagement orchestration.** WS-012 operates within a single engagement at a time. A run that needs to touch CRMBUILDER and Cleveland Business Mentoring is two separate orchestrator invocations.
- **Automated failure recovery.** If a child agent fails, the orchestrator halts the wave and surfaces the failure for human review. No automated retry, no automated requeue. Crashed agents leave their `claimed_by` set; a manual cleanup step (or a future PI) handles unclaim.
- **Work-ticket integration as the orchestrator's dispatch mechanism.** The kickoff template for each child agent is a markdown template, not a `work_ticket` record. Promoting it to a work_ticket is a candidate enhancement once the basic orchestrator runs, but adds complexity that isn't justified for v1.
- **Orchestrator UI.** The driver runs at Doug's terminal via Claude Code. No desktop panel, no progress dashboard. Visibility comes from the per-agent log files and the governance records produced at each agent's close-out.

---

## 5. Dependencies on External Work

- **`blocked_by` reference kind.** Already exists (v0.8 vocab). Used as-is.
- **`conversation_belongs_to_workstream` reference kind.** Already exists (v0.7 vocab). Used for orchestrator and child conversation membership in WS-012.
- **`conversation_records_session` reference kind.** Already exists (v0.7 vocab).
- **`workstream` entity.** Already exists (v0.7 schema). WS-012 itself is created out-of-band in the SES-079 close-out apply prompt's pre-step (per the v0.8 convention).
- **`conversation_orchestrates_conversation` reference kind.** PI-059 adds this. New addition to `REFERENCE_RELATIONSHIPS` and `_kinds_for_pair`, with Alembic migration to extend the `refs.relationship_kind` CHECK constraint.

---

## 6. Open Questions Deferred to Implementation

Items that will be settled when their owning PI is opened, not now:

- Exact JSON shape of the `POST /identifiers/reserve` request and response (PI-057).
- Whether `claimed_by` references a session identifier (SES-NNN) or a conversation identifier (CONV-NNN). The conversation identifier is more semantically accurate (the conversation is what's holding the claim) but the session identifier is simpler to write into the field at start-of-work. Decided in PI-056.
- Whether the orchestrator driver runs as a Python script invoked from the command line, a slash-command inside Claude Code, or a subagent-template that Claude Code natively spawns. Decided in PI-060 after a brief implementation-mode reconsideration.
- The exact format of the child-agent kickoff template — Markdown with frontmatter? Plain Markdown with conventional headings? Settled in PI-061.

---

## 7. Success Criteria

WS-012 is complete when:

1. All ten planning items (PI-053 through PI-062) resolve.
2. A test run of the orchestrator dispatches at least two child agents concurrently against the open backlog, each producing its own close-out payload, with the orchestrator producing its own supervising close-out that references both children via `conversation_orchestrates_conversation`.
3. The executive_summary field is populated on every PI, DEC, and SES record in the CRMBUILDER engagement database.

The first orchestrator run is the acceptance test, not a separate validation phase.

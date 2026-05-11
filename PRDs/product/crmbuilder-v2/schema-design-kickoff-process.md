# Methodology Entity Schema Design — `process` — Kickoff Prompt

**Last Updated:** 05-11-26 16:00
**Purpose:** Seed prompt for a new Claude.ai conversation that designs the `process` entity type schema for v0.4.
**Position in workstream:** **Third of four** schema-design conversations. Predecessors: `domain`, `entity` (both must be complete before this conversation opens). Successor: `crm_candidate`.
**Workstream master:** `PRDs/product/crmbuilder-v2/methodology-schema-workstream-plan.md`
**Schema spec template:** `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md`

---

## The task

Design the `process` entity type schema for v2's storage layer. A "process" in the methodology sense is a sequence of work the organization does to advance its mission — Client Intake, Mentor Onboarding, Annual Dues Cycle, etc. — the things that get full Process Documents in Phase 3 of the evolved methodology and that constitute the **Prioritized Backbone** in Phase 1.

Drive a structured architectural discussion that produces one deliverable:

**`PRDs/product/crmbuilder-v2/methodology-schema-specs/process.md`** — the complete schema specification per the template in `methodology-entity-schema-spec-guide.md`.

Cadence matches SES-011 and the prior schema-design conversations: one architectural question at a time, building toward the spec section by section.

At conversation close: decisions written via direct API; deferred items written as PIs; session record written by Doug through the v0.3 desktop New Session dialog.

---

## Context — why process is the most relational

`process` is the most relational of the four entity types. It touches:

- **`domain`** — every process belongs to a domain. Likely a direct FK (one-to-one cardinality, settled at the methodology level).
- **`entity`** — every process touches entities (entity records are read, created, or modified during the process). Many-to-many; uses the references infrastructure with a new `relationship_kind` (e.g., `process_touches_entity`).
- **Other `process` records** — the Prioritized Backbone explicitly includes "connections between processes" (Phase 1 output). One process feeds another, or follows another, or runs concurrently. Many-to-many; uses references with a `relationship_kind` like `process_connects_to`.

Designing `process` third in the workstream means both `domain` and `entity` already exist as settled schemas. This is the rationale for the ordering choice — `process`'s referents don't need placeholders.

---

## Methodology context

Evolved Phase 1 produces a **Prioritized Backbone**: the named set of processes (drawn from across whichever domains are needed) that constitute the mission-critical thread for end-to-end work, plus the connections between them, plus a deferred-processes list. Proposed by CRM Builder, verified by client.

In Phase 1, processes are **named tokens**, not fully defined. The Prioritized Backbone is a list of names plus priority classifications plus connections. Full process definitions — steps, actors, fields touched, edge cases — are Phase 3 work (Iteration Build and Deploy).

So `process` in v0.4 needs to host:

- Per-record: identifier, name, brief description, priority classification, domain reference, connections to other processes
- **Priority classification** is critical — it's the core organizing principle of the evolved methodology (Principle 3: "Priority is established at the process level and inherited downward"). Three values: `mission_critical`, `supporting`, `deferred`.
- Lifecycle status separate from priority — a process can be `candidate` (Phase 1 surface) vs. `confirmed` (Phase 1 lock or later) vs. `deprecated` (later iterations remove it from scope).
- Connections to other processes via references (m:m, `relationship_kind: process_connects_to`)

What `process` does *not* yet need in v0.4 (all tracked as PI-005 — full process schema growth):

- **Steps** — ordered list of sub-actions within the process. Phase 3 territory.
- **Actors** — which personas perform the process. Personas don't exist as records until v0.5+ (PI-003).
- **Entity-field touches** — which fields on which entities the process reads/writes. Fields don't exist as records until v0.5+ (PI-004).
- **Triggers and outcomes** — what initiates and concludes the process. Phase 3 territory.
- **Cycle time, frequency, volume** — Phase 4 review territory.

The schema in v0.4 is therefore thin enough that "process" is more a **structured token** than a full definition. That thinness is intentional — Phase 1 produces tokens; Phase 3 fleshes them out.

---

## Read this first

1. `crmbuilder/CLAUDE.md` — universal session-startup entry.
2. `PRDs/product/crmbuilder-v2/methodology-schema-workstream-plan.md` — workstream master plan.
3. `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md` — schema spec template.
4. `PRDs/product/crmbuilder-v2/methodology-schema-specs/domain.md` — first predecessor schema; honor its conventions.
5. `PRDs/product/crmbuilder-v2/methodology-schema-specs/entity.md` — second predecessor schema; honor its conventions; understand its domain-affiliation mechanism (likely a guide for process's analogous design).
6. `PRDs/process/research/evolved-methodology/evolved-methodology-phase-outline.md` — sections 3 (Phase 1, Phase 3). Phase 1 produces the Prioritized Backbone; Phase 3 produces full Process Documents.
7. `PRDs/process/research/evolved-methodology/phase-1-interview-guide.md` v0.2 — search for "Prioritized Backbone" and "process" sections.
8. `PRDs/product/crmbuilder-v2/db-export/sessions.json` — read SES-011 and the `domain`/`entity` schema-design conversations' session records.
9. `PRDs/product/crmbuilder-v2/db-export/decisions.json` — read decisions from the `domain` and `entity` conversations.

---

## Architectural questions likely to arise

The conversation will surface these in some order; the list is illustrative.

- **Identifier prefix.** Working assumption: `PROC`. Alternatives: `PRC` (shorter), `PR` (collision risk), `P` (too short).
- **Field inventory.** Working minimum: `identifier`, `name`, `description`, `priority`, `status`, `domain` (FK or reference). Anything else for v0.4? Working hypothesis: priority classification rationale (a short note explaining why this process is mission-critical or deferred) — Principle 4 says CRM Builder proposes with grounded reasoning, and that reasoning belongs *somewhere* per process.
- **Priority vs. status — are they the same field or two?** Priority is the methodology's organizing principle (mission-critical / supporting / deferred); status is the record's lifecycle position (candidate / confirmed / deprecated). They're different concepts and almost certainly need different fields. Confirm.
- **Domain affiliation: direct FK or reference?** Process is single-domain (methodology says so); direct FK is the natural choice. `domain` field type is `string` (the domain's identifier), validated at the access layer.
- **Process-to-process connections.** References infrastructure with a new `relationship_kind: process_connects_to`. Cardinality: m:m. Semantics: undirected (process A connects to process B without strict ordering) or directed (A feeds B)? The methodology's "connections between processes" language is ambiguous; this conversation decides.
- **Process-to-entity touches.** References with `relationship_kind: process_touches_entity`. m:m. Phase 1 may not surface these directly (Phase 1 focuses on process names and priority); v0.4 schema enables them for Phase 3 work to attach later.
- **Lifecycle status values.** Working set: `candidate` → `confirmed` → `deprecated`. Plus `deferred` (the Phase 1 "deferred-processes list" is just rows with this status, per workstream plan). So: 4 values total. Confirm.
- **UI considerations.** Default panel layout. Worth checking: master pane benefits from showing priority and domain as columns; detail pane benefits from a "connected processes" section rendered via the references infrastructure.
- **Acceptance criteria.** Round-trip a sample CBM Phase 1 Prioritized Backbone (e.g., "Client Intake" process, mission-critical, MN domain, connects to "Mentor Matching") through the UI.

---

## Working style

Per Doug's preferences:

- Discuss one architectural decision at a time. Wait for explicit approval before moving to the next.
- Plain text. Bold section headings OK. Avoid bullet-point overload.
- Terse approvals sufficient.
- Propose outlines; user approves before drafting begins. Once architectural questions are settled, execute the spec drafting end-to-end.

For repo work: sparse checkout, set git identity, `git pull --rebase origin main` before pushing.

---

## Pre-flight checks

1. `curl -sf http://127.0.0.1:8765/health` — API up.
2. `uv run pytest tests/crmbuilder_v2/ -v` — test suite green.
3. `git pull --rebase origin main` — clone current.
4. Read items 1–9 in "Read this first."

---

## Governance — at conversation close

Per DEC-013, one Claude.ai conversation produces one session record. This conversation's record is written **at the actual close of the conversation**, by Doug, through the v0.3 desktop New Session dialog.

Record contents follow the SES-011 / `domain` / `entity` pattern:

- `identifier`: next available SES-NNN
- `conversation_reference`: e.g., `"Claude.ai schema-design conversation that produced methodology-schema-specs/process.md. No transcript preserved per DEC-025."`
- `topics_covered`: seed prompt verbatim, then structured architectural-question summary
- `artifacts_produced`: `methodology-schema-specs/process.md`, plus DEC-NNNs and PI-NNNs authored
- `in_flight_at_end`: `"Next workstream conversation: crm_candidate schema design. Kickoff at schema-design-kickoff-crm_candidate.md."`

---

## What this conversation does NOT do

- Build code.
- Modify v2's storage architecture beyond additive extensions for `process` and the new relationship-kind values.
- Plan beyond `process`.
- Define process **steps**. Tracked as PI-005.
- Address persona affiliation (which personas perform the process). Personas don't exist as records yet (PI-003).
- Address field-touch detail (which entity fields the process reads/writes). Fields don't exist as records yet (PI-004).

---

End of kickoff prompt.

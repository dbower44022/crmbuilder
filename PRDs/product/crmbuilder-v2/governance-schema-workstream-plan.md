# Governance Entity Schema-Design Workstream — Plan

**Last Updated:** 05-20-26 22:00
**Status:** Active — workstream in flight (workstream-establishing conversation is the first conversation; six per-entity schema-design conversations and a build-planning conversation follow).
**Predecessor:** Strategic scoping conversation closed out as Session 046 (SES-046) on 05-20-26. That conversation surfaced the governance gap and formalized six principle-level decisions (DEC-117 through DEC-122) that this workstream is built on. The kickoff prompt for this workstream-establishing conversation (`governance-entity-schema-workstream-establishing-kickoff.md`) was itself authored as part of SES-046's artifacts.

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-20-26 22:00 | Doug Bower / Claude (workstream-establishing conversation, session identifier assigned at close) | Initial workstream plan. Produced by the workstream-establishing conversation opened against `governance-entity-schema-workstream-establishing-kickoff.md`. Establishes six per-entity schema-design conversations (workstream, conversation, reference book, work ticket, close-out payload, deposit event), a schema-spec methodology guide, six per-entity kickoff prompts, and a follow-on build-planning conversation. References DEC-117 through DEC-122 as the workstream's foundation. |

---

## Change Log

**Version 1.0 (05-20-26 22:00):** Initial creation. Establishes the governance entity schema-design workstream that produces six governance entity schemas (workstream, conversation, reference book, work ticket, close-out payload, deposit event) under minimum-viable scope, sequenced as workstream → conversation → reference book → work ticket → close-out payload → deposit event, designed in six separate Claude.ai conversations (one per entity type, design only — no build prompts), with a build-planning conversation following to integrate the six specs into a coherent release. Foundation decisions DEC-117 through DEC-122 were recorded by the predecessor scoping conversation (SES-046) and are referenced rather than re-recorded.

---

## 1. Purpose

This document is the master plan for the governance entity schema-design workstream — the set of conversations and artifacts that close the gap between the V2 governance database's stated single-source-of-truth role and its actual coverage.

It exists because the predecessor scoping conversation (SES-046) walked through the planning-and-execution workflow step by step and surfaced a category-defining gap: V2 tracks sessions, decisions, planning items, risks, topics, references, and the methodology entities shipped in user-interface versions 0.4 and 0.5, but it does not track any of the operational artifacts the workflow itself produces and consumes — kickoff prompts, workstream master plans, Product Requirements Documents, close-out payloads, deposit events, or the conversational and organizational units (conversations, workstreams) that contain them. The scoping conversation formalized six principles for closing that gap and authored the kickoff prompt that opened this workstream-establishing conversation.

---

## 2. Origin and foundation

### 2.1 The gap

V2's governance database covers what has happened (sessions are after-the-fact records per DEC-013, append-only) and what was decided (decisions are immutable per DEC-013), but it does not cover the planning-and-execution machinery itself. Concrete consequences observed during the scoping conversation:

- No way to query "what conversations are queued up next" without filesystem scanning of kickoff prompt files.
- No way to confirm "did this close-out payload apply succeed and produce the records it should have" without reading the apply script's output log.
- No way to ask "what version of the Product Requirements Document was in force at the time of Session NNN" without git archaeology against the PRD file's commit history.
- No first-class concept of a workstream — workstreams are real organizing units in practice, but exist only implicitly in document content and naming conventions.
- No first-class concept of a conversation as a unit through its full lifecycle (planned, kickoff-drafted, ready, in-flight, complete, cancelled, superseded). A session record captures what happened after the fact; nothing captures the work unit before it has happened.

### 2.2 The six foundation decisions

The scoping conversation resolved six principle-level questions and recorded them as decisions at its close:

- **Three purpose-built workflow-file families (DEC-117)** — track workflow files as three families (reference book, work ticket, deposit bucket) rather than one generalized governed-artifact type, because the families have meaningfully different lifecycles.
- **Two entities within the deposit bucket (DEC-118)** — separate the close-out payload (the slip) from the deposit event (the record of when it was applied), because their lifecycles diverge after production.
- **Conversation as first-class (DEC-119)** — a conversation entity represents the unit of conversational work through its full lifecycle, distinct from the after-the-fact session record.
- **Workstream as first-class (DEC-120)** — a workstream entity represents a coherent line of related conversations, with its own lifecycle.
- **Single-source-of-truth coverage extension (DEC-121)** — the six new entity types close the gap between the database's stated role and its actual coverage.
- **Workstream opens immediately (DEC-122)** — this workstream opens in parallel to other in-flight work; it does not gate on Cleveland Business Mentors Planning Item 001 (sub-domain hierarchy) or the multi-tenancy routing fix slices.

These six decisions are the workstream's foundation. They are referenced by this plan and by every per-entity schema-design conversation; they are not re-litigated.

### 2.3 What this workstream-establishing conversation produces

Five categories of deliverable (down from the six categories named in the kickoff, because the foundation decisions DEC-117 through DEC-122 were recorded by SES-046 rather than waiting for this conversation's close):

1. This workstream plan (the master document for the redirected effort).
2. A schema-spec methodology guide (the template every per-entity schema-design conversation follows).
3. Six per-entity kickoff prompts (one for each schema-design conversation).
4. Acknowledgement and link-out to DEC-117 through DEC-122 (already recorded; no new decisions written at this conversation's close beyond any that arise during the planning work itself).
5. One session record at the conversation's actual close, capturing the seed prompt verbatim and the artifacts produced.

---

## 3. Scope

### 3.1 What this workstream produces

Six governance entity schemas, designed under minimum-viable scope (only what the next Cleveland Business Mentors redo cycle and the next routine close-out cycle need):

- **`workstream`** — A coherent line of related conversations. Identifier prefix to be set by the workstream entity's schema-design conversation (working assumption: `WS-NNN`). Lifecycle: planned, in-flight, complete. Fields and relationships designed in the first per-entity schema-design conversation.
- **`conversation`** — A unit of conversational work through its full lifecycle: planned, kickoff-drafted, ready, in-flight, complete, cancelled, superseded. Identifier prefix to be set (working assumption: `CONV-NNN`). References its parent workstream and its kickoff prompt's reference book record (when one exists).
- **`reference_book`** — A long-lived versioned document (Product Requirements Documents, implementation plans, workstream plans, methodology guides, kickoff prompts that are referenced repeatedly). Identifier prefix to be set (working assumption: `RB-NNN`). Includes version history and "in force at" semantics.
- **`work_ticket`** — A single-use seed document (kickoff prompts, ad-hoc prompts produced for one specific conversation). Distinguished from reference books by single-use semantics — produced for one conversation and not revisited as a reference. Identifier prefix to be set (working assumption: `WT-NNN`).
- **`close_out_payload`** — The structured payload produced at conversation close, intended for application to the governance database. Paired one-to-one with a conversation that produced it. Identifier prefix to be set (working assumption: `COP-NNN`).
- **`deposit_event`** — The record of a close-out payload being applied to the database, with outcome (success or failure), timestamp, and back-references to the records the deposit wrote. Paired with its close-out payload but distinct lifecycle. Identifier prefix to be set (working assumption: `DEP-NNN`).

Each entity's identifier prefix, status posture, soft-delete posture, field set, and relationship vocabulary are the per-entity schema-design conversation's call, constrained by the methodology guide.

### 3.2 What this workstream does not produce

Deliberately out of scope:

- **Build code.** The build-planning conversation that follows the six per-entity schema-design conversations produces the Product Requirements Document, implementation plan, and per-slice build prompts. This workstream stops at six schema specifications.
- **Backfill of historical records.** Retroactive population of workstream and conversation entity records for prior workstreams and conversations (including this one) is deferred to a post-build cleanup planning item authored by the build-planning conversation. During the workstream, the session record on the append-only sessions table remains the only governance record per conversation, per DEC-013.
- **Resolution of the nested-workstream question.** Whether a workstream can contain a sub-workstream is deferred to the workstream entity's own schema-design conversation.
- **Resolution of the retroactive-migration mechanism.** The mechanism (how to write workstream and conversation records for past work) is deferred to PI-022 (already authored by the predecessor scoping conversation, SES-046).
- **Touching methodology entities.** The methodology entities (domain, entity, process, candidate Customer Relationship Management product, engagement) shipped in user-interface versions 0.4 and 0.5 remain unchanged.
- **Touching in-flight multi-tenancy routing work.** Sessions 044 and 045 plus remaining slices are parallel; no overlap with the governance entity scope.
- **Opening the Cleveland Business Mentors redo Phase 1 conversation.** That conversation waits on Planning Item 001 (sub-domain hierarchy amendment) in the Cleveland Business Mentors engagement, which is a separate parallel workstream.

### 3.3 Per-engagement isolation posture

V2's per-engagement isolation architecture (documented in `multi-engagement-architecture.md` and refined by DEC-115 / DEC-116) means governance entities live in the per-engagement SQLite file. The CRMBuilder dogfood engagement (`CRMBUILDER`) is where this workstream's first records land. Other engagements receive the new entity types as part of their initialization once the build is shipped. No engagement-specific schema branches; one schema set, one build, deployed everywhere.

---

## 4. Methodology

The workstream follows the same shape that the methodology entity schema-design workstream pioneered (SES-011 through SES-015, with the build-planning conversation that followed):

- One Claude.ai conversation per entity, design only — no build prompts produced inside a schema-design conversation.
- Each schema-design conversation produces one schema specification file at `PRDs/product/crmbuilder-v2/governance-schema-specs/{entity_name}.md`, conforming to the structure defined in `governance-entity-schema-spec-guide.md`.
- Decisions made during a schema-design conversation are written via direct API at the conversation's close as decision records.
- One session record per conversation, written through the V2 desktop New Session dialog at the conversation's actual close, per DEC-013.
- The build-planning conversation after the six schema-design conversations consumes all six specifications and produces the Product Requirements Document, implementation plan, and per-slice build prompts.

The choice has one notable effect on cadence: the workstream's total conversation count is **eight** (this workstream-establishing conversation + six schema-design conversations + one build-planning conversation), longer than the methodology workstream's six. The extra conversations reflect the larger entity count (six vs. four) and the relational interdependence of the close-out payload / deposit event pair.

---

## 5. Workstream structure

### 5.1 Conversations

```
[This conversation]  Workstream-establishing conversation
                     (produces this plan + spec guide + six kickoff prompts)
                              ↓
Conversation 1       Schema-design: workstream
                              ↓
Conversation 2       Schema-design: conversation
                              ↓
Conversation 3       Schema-design: reference book
                              ↓
Conversation 4       Schema-design: work ticket
                              ↓
Conversation 5       Schema-design: close-out payload
                              ↓
Conversation 6       Schema-design: deposit event
                              ↓
Conversation 7       Build-planning conversation
                     (takes the six specs as input, produces the
                     governance entity Product Requirements Document,
                     implementation plan, and per-slice build prompts;
                     target user-interface version to be set in coordination
                     with the active version sequence at that time)
                              ↓
[Claude Code execution of the build slice prompts]
                              ↓
[Build closeout session, written through the New Session dialog at ship]
```

Session identifiers beyond the workstream-establishing conversation are unassigned and will be assigned at each conversation's close per DEC-025.

### 5.2 What each schema-design conversation produces

Per the methodology pattern, each schema-design conversation produces **design only**:

- One **schema specification document** at `PRDs/product/crmbuilder-v2/governance-schema-specs/{entity_name}.md`, conforming to `governance-entity-schema-spec-guide.md`.
- The **decisions** made during the conversation, written via direct API at the conversation's close.
- One **session record** at the conversation's actual close, written through the V2 desktop New Session dialog.

Build prompts are *not* produced in schema-design conversations. The build-planning conversation produces them all.

### 5.3 Order and dependencies

Conversations run **sequentially**, in this order, with no parallelism:

1. **workstream** — most independent; references nothing else in the new entity set. Designing first lets all downstream schemas treat workstream as a settled referent. Includes the deferred nested-workstream question (handled inside this conversation, not deferred further).
2. **conversation** — references workstream (every conversation belongs to a workstream). Designing second means workstream is already settled.
3. **reference book** — conversations reference reference books (a conversation's kickoff prompt may point at a Product Requirements Document, an implementation plan, prior session records). Designing reference book third — after conversation — lets it design against a known set of incoming references from conversation.
4. **work ticket** — references conversation (one work ticket is consumed by one conversation). Designing after conversation and reference book lets work ticket's schema distinguish itself cleanly from reference book by single-use semantics.
5. **close-out payload** — produced by a specific conversation; references the conversation that produced it. Designed after conversation is settled.
6. **deposit event** — references close-out payload (its parent) and the records the deposit wrote (back-references into existing entity types). Designed last because it depends on close-out payload's schema being settled.

### 5.4 The build-planning conversation

After all six schema specifications exist, a single build-planning conversation takes them as input and produces the actual release artifacts: the governance entity Product Requirements Document, the implementation plan, and per-slice build prompts under `PRDs/product/crmbuilder-v2/prompts/`. Target user-interface version is open at this writing — set by the build-planning conversation in coordination with the active version sequence at that time.

Build planning is *not* attempted in this workstream-establishing conversation because the schemas it would integrate do not yet exist. It is also not attempted inside each schema-design conversation because the cross-cutting concerns (migration sequencing, sidebar ordering, About bump, README update, test target, closeout, reference-vocabulary aggregation) need to be designed with all six schemas visible at once.

The build-planning conversation also refines **PI-022** (retroactive backfill of workstream and conversation records for prior workstreams, including this one) — already authored by the predecessor scoping conversation SES-046 — into a concrete execution plan.

---

## 6. Independence — parallel work this workstream does not gate on

Per DEC-122, this workstream opens immediately and operates against the CRMBuilder dogfood engagement. It does not gate on:

- **Cleveland Business Mentors Planning Item 001** — the paper test's sub-domain hierarchy amendment to the domain entity. The amendment lives in the methodology entity workstream's domain spec and the Cleveland Business Mentors engagement's planning items; the governance workstream's entity set is disjoint from methodology entities, so no schema-level coupling exists.
- **Multi-tenancy routing fix slices in flight** — Sessions 044 and 045 plus the remaining slices in `multi-tenancy-routing-fix-slice-plan.md`. The routing fix changes how V2 selects which engagement's database serves a request; it does not change schema. The governance entity schemas can be designed without the routing fix being complete, and the build-planning conversation can be timed against whichever release sequence makes sense at that point.
- **Cleveland Business Mentors redo Phase 1 conversation** — explicitly waits on Cleveland Business Mentors Planning Item 001 regardless. The governance workstream operates in the CRMBuilder dogfood engagement and does not touch Cleveland Business Mentors content.

Each per-entity schema-design conversation may surface frictions with the current V2 (the same production-use feedback pattern the methodology workstream used). Those frictions feed candidate planning items for the build-planning conversation to consider; they do not back-pressure the parallel workstreams above.

---

## 7. Bootstrap — the chicken-and-egg

This workstream designs the workstream and conversation entities. But the conversations doing the designing are themselves conversations inside a workstream — and neither has records in the database yet, because the entity types they would populate are exactly what is being designed.

The bootstrap is handled this way:

- During the workstream, the session record (on the existing sessions table, append-only per DEC-013) remains the only governance record per conversation. Each schema-design conversation closes out with one session record, as today.
- The workstream itself has no database record during its lifetime. It exists in this plan and in the kickoff prompts; that is sufficient continuity for the workstream's duration.
- Retroactive population — writing workstream and conversation records for this workstream-establishing conversation, the six schema-design conversations, and any prior workstreams worth tracking — is tracked by **PI-022** (authored by the predecessor scoping conversation SES-046). Refinement of PI-022's resolution path (go-forward only, selective backfill, or full backfill with reconstructed outcomes) is the build-planning conversation's responsibility. It runs as post-build cleanup, after the entity types are buildable.
- The schema-design conversations themselves design without depending on backfill ordering. The schemas must support retroactive population (records can be inserted with historical timestamps and "complete" status), but the cleanup itself is not part of this workstream's deliverable set.

---

## 8. Governance

### 8.1 Decisions

**The six foundation decisions (DEC-117 through DEC-122) were recorded by the predecessor scoping conversation (SES-046).** This plan references them as the workstream's foundation; this workstream-establishing conversation does not re-record them.

Any additional decisions arising in this workstream-establishing conversation (about workstream structure, naming conventions, the methodology guide's required sections, etc.) are written via direct API at the conversation's close as decision records, assigned identifiers from DEC-123 onward in order of recording. If no such decisions arise — that is, if the workstream-establishing conversation simply executes the kickoff's deliverable plan with no consequential choices — no new decisions are written at close.

Each per-entity schema-design conversation will record its own decisions (typically several per conversation, covering identifier prefix, status posture, soft-delete posture, field set, relationship-vocabulary additions, validation rules) at its close.

### 8.2 Planning items

This workstream-establishing conversation **does not author new planning items**. The retroactive-backfill planning item is **PI-022**, authored by the predecessor scoping conversation (SES-046) with extensive description of the resolution paths to consider (go-forward only, selective backfill, full backfill with reconstructed outcomes). Refinement of PI-022 is the build-planning conversation's responsibility.

Additional planning items may arise during the schema-design conversations (typically for deferred fields, deferred relationship vocabulary, or schema growth into later releases). Those are authored at each conversation's close.

### 8.3 Session record

The session record for this workstream-establishing conversation is written at the conversation's *actual* close, through the V2 desktop New Session dialog or via the standard close-out apply script. Identifier assigned at close (working assumption: SES-047, the next identifier after SES-046).

The session record captures the seed prompt verbatim, the conversational decisions reached, the artifacts produced (this plan + the methodology guide + six kickoff prompts), and what's in flight at conversation end (the six schema-design conversations queued up against their kickoff prompts, the build-planning conversation queued after them).

### 8.4 Status

No status update from this workstream-establishing conversation. Status remains at whatever value it holds at the start of the conversation — the workstream is mid-flight; status reflects last shipped state.

---

## 9. Architectural disciplines that schema-design conversations must apply

These disciplines have evolved since the methodology entity schema-design workstream completed. Each per-entity schema-design conversation applies them in its outputs:

- **Reference relationship vocabulary discipline.** New relationship kinds must be added to `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` (`REFERENCE_RELATIONSHIPS` set and `_kinds_for_pair` source-target constraint mapping), and require an Alembic migration on the `refs.relationship_kind` CHECK constraint. Per-entity schema specifications name the vocabulary additions they require; the build-planning conversation aggregates them.
- **API envelope discipline.** Any new apply script or API-touching code must unwrap the `{data, meta, errors}` envelope before reading the payload. Canonical pattern at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-025.md`.
- **Client-side identifier computation.** Prefixed-identifier entity types compute their identifier client-side from a `compute_next_identifier(client.list_<entity>())` style helper. Each schema specification declares the prefix and identifier format explicitly.
- **Per-engagement isolation.** New entity types live in the per-engagement SQLite file. The CRMBuilder dogfood database is where this workstream's first records land. Other engagements receive the new entity types as part of their initialization once the schema is built.
- **Source-first relationship-kind naming (DEC-048).** When a new relationship kind is added, the verb tense and orientation follow source-first convention as established in the methodology workstream.
- **Parent-prefix field naming (DEC-046).** Field names use the parent entity's prefix when the field refers to a parent (e.g., `workstream_id` on a conversation record, not just `id`).

These disciplines are also reproduced in the methodology guide so each per-entity conversation has them at hand.

---

## 10. Open questions and deferred design

Things not settled by this workstream-establishing conversation that future workstream conversations will need to answer:

- **Identifier prefix conventions for the six new entity types.** This plan names `WS`, `CONV`, `RB`, `WT`, `COP`, `DEP` as working assumptions, but the actual prefix is each schema-design conversation's call. `CONV` may collide visually with the existing `CHR` (charter) and `STA` (status) prefixes; `RB` may be ambiguous against existing prefixes; `COP` is unidiomatic.
- **Nested workstreams.** Whether a workstream can contain a sub-workstream (and how the relationship is modeled) is the workstream entity's schema-design conversation's call.
- **Conversation lifecycle granularity.** The set of conversation states (planned, kickoff-drafted, ready, in-flight, complete, cancelled, superseded) named in DEC-119 is a starting hypothesis. The conversation entity's schema-design conversation may refine, collapse, or extend it.
- **Reference book versioning model.** How reference books carry version history (separate version records, embedded JSON history, content-addressed snapshots, links to git commits) is the reference book entity's schema-design conversation's call.
- **Deposit event back-references.** How a deposit event references the records its apply wrote (one-to-many references into multiple entity types via the existing references table, or a dedicated columnar schema) is the deposit event entity's schema-design conversation's call.
- **Cross-spec consistency.** The methodology guide lists categories where consistency is expected (identifier format, status-field naming, soft-delete pattern, parent-id field naming, reference-vocabulary verb tense). The first schema-design conversation (workstream) effectively decides them; subsequent conversations follow unless they have a strong reason to deviate.

---

## 11. The schema-spec methodology guide

Each schema-design conversation produces a schema specification conforming to `governance-entity-schema-spec-guide.md`, which is the second artifact this workstream-establishing conversation produces alongside this plan. The guide defines what a complete schema specification looks like — required sections, conversation cadence, decision and session governance, cross-spec consistency requirements, validation gates before build planning.

See `governance-entity-schema-spec-guide.md` for the full template.

---

## 12. The six per-entity kickoff prompts

Each schema-design conversation opens against a per-entity kickoff prompt at the root of `PRDs/product/crmbuilder-v2/`:

- `schema-design-kickoff-workstream.md`
- `schema-design-kickoff-conversation.md`
- `schema-design-kickoff-reference-book.md`
- `schema-design-kickoff-work-ticket.md`
- `schema-design-kickoff-close-out-payload.md`
- `schema-design-kickoff-deposit-event.md`

Each is structured to match the existing planning-prompt cadence (purpose, predecessor, read-first list, working style, governance, pre-flight, scope, what NOT to do). Per-entity content distinguishes them: scope of that entity type's role in the planning-and-execution workflow, prior schemas to read (e.g., the conversation kickoff references the already-completed workstream specification), specific design questions likely to arise.

---

## 13. Glossary

- **Workflow file** — a file that exists to drive the planning-and-execution workflow forward: a kickoff prompt, a master plan, a Product Requirements Document, a close-out payload. Distinct from output artifacts of the work itself (e.g., generated YAML or generated Word documents).
- **Reference book** — a long-lived versioned workflow file referenced by many conversations over its lifetime.
- **Work ticket** — a single-use workflow file produced for one specific conversation and not revisited as a reference afterward.
- **Deposit bucket** — the close-out payload paired with its deposit event. A two-entity family per DEC-118.
- **Close-out payload** — the structured payload produced at a conversation's close, intended for application to the governance database.
- **Deposit event** — the record of a close-out payload being applied to the governance database, with outcome, timestamp, and back-references.
- **Conversation** — a unit of conversational work through its full lifecycle (planned, kickoff-drafted, ready, in-flight, complete, cancelled, superseded). Distinct from a session record, which captures what happened after the conversation completes.
- **Workstream** — a coherent line of related conversations.
- **Bootstrap** — the chicken-and-egg situation where this workstream designs the workstream and conversation entities while operating inside a workstream and conversations that have no database records yet. Resolved by deferring retroactive population to a planning item executed after the build ships.
- **Governance entity types** — entity types that hold metadata about the project itself (decisions, sessions, charter, status, risks, planning items, topics, references, and after this workstream: workstream, conversation, reference book, work ticket, close-out payload, deposit event). Contrast with methodology entity types (domain, entity, process, candidate Customer Relationship Management product, engagement) which hold methodology content.

---

*End of document.*

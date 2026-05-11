# Methodology Entity Schema-Design Workstream — Plan

**Last Updated:** 05-11-26 16:00
**Status:** Active — workstream in flight.
**Supersedes:** `ui-v0.4-planning-prompt.md` (the original v0.4 kickoff, redirected during planning on 05-11-26; retained for history with a supersession header in place).

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-11-26 16:00 | Doug Bower / Claude (SES-011) | Initial workstream plan. Produced by the planning conversation that redirected v0.4 from a UI-polish release to a methodology-entity-schema-design workstream. |

---

## Change Log

**Version 1.0 (05-11-26 16:00):** Initial creation. Establishes the workstream that produces four methodology-entity schemas (domain, entity, process, crm_candidate) under minimum-viable scope, sequenced as domain → entity → process → crm_candidate, designed in four separate Claude.ai conversations (one per entity type, design only — no build prompts), with a fifth v0.4-build-planning conversation following to integrate the four specs into a coherent release. PI-001 (styling pass) deferred a fourth time with a CBM-redo-friction-trigger mechanism; SES-010 identifier-asymmetry friction resolved via `GET /<entity>/next-identifier` helper endpoints applied to all twelve prefixed entity types in v0.4 build.

---

## 1. Purpose

This document is the master plan for the methodology-entity-schema-design workstream — the set of conversations and artifacts that prepare v2 to host methodology *content* (not just governance about it) for the upcoming real-world CBM redo test.

It exists because the original v0.4 kickoff (`ui-v0.4-planning-prompt.md`) framed v0.4 as a UI-polish release, and the planning conversation that opened against that kickoff established that the more valuable next step was redirecting v0.4 entirely toward enabling CBM redo to use v2 as its system of record for both governance and methodology content. That redirection is not a small change of scope; it is a different release shape with different deliverables, a different conversation count, and a different cadence — which is why a fresh master plan replaces the original kickoff rather than amending it in place.

---

## 2. What changed and why

### 2.1 The original v0.4 frame

The committed kickoff at `ui-v0.4-planning-prompt.md` named v0.4 as "deliberately open" and listed four candidate buckets: PI-001 styling discharge (forcing function), v0.3 deferral polish (reference filtering, JSON diff, global search, keyboard shortcuts, exports, bulk ops), forward expansion (methodology entity schema design), and reimplementation workstreams (saved views / duplicate-check rules / workflow managers — blocked on EspoCRM's lack of public REST write paths). The kickoff's "On timing" section noted that production-use friction is the highest-weight signal for choosing among candidates and explicitly suggested waiting for some weeks of real v0.3 use before starting v0.4 planning.

### 2.2 The redirection

The planning conversation (captured as SES-011) opened with no real production use of v0.3 yet — closeout had completed only days earlier, and SES-010 captured the closeout-and-kickoff-prep work itself rather than substantive governance use. With production-use signal effectively empty, the conversation pivoted on a question from the user: the natural next step was preparing for a real-world test by redoing the CBM design, not iterating the v2 UI on speculation about which features mattered.

That reframe surfaced an architectural fact the original kickoff had treated as one option among several: CBM redo on v2 as the system of record for *both* governance and methodology content requires v2 to have entity types for methodology content (domains, entities, processes, etc.), which v0.3 does not have. v0.3 has CRUD for governance entities only (decisions, sessions, charter, status, risks, planning items, topics, references). So methodology entity schema design — Bucket C in the original kickoff — became v0.4's primary frame.

### 2.3 What the planning conversation could not do

The original kickoff explicitly forbade designing schemas inline in the planning conversation, on the principle that schema design tends to get rushed when embedded in planning. That constraint, combined with the redirection, meant the planning conversation could not produce a complete v0.4 PRD by itself — the schemas have to be designed somewhere, and that somewhere isn't the planning conversation.

The resolution was to pivot the planning conversation's deliverables. Instead of producing a v0.4 PRD, implementation plan, and slice build prompts, the planning conversation produces:

1. This workstream plan (the master document for the redirected effort)
2. A schema-spec methodology guide (the template every schema-design conversation follows)
3. Four per-entity kickoff prompts (one for each of the four schema-design conversations)

The v0.4 PRD, implementation plan, and build prompts come later — produced by a v0.4-build-planning conversation that takes all four schema specs as input.

---

## 3. Scope

### 3.1 What this workstream produces

Four methodology entity schemas, designed under minimum-viable scope (only what CBM redo's evolved-methodology Phase 1 needs to host as content):

- **`domain`** — Domain Inventory members. Phase 1 produces a short list of domains with one-paragraph descriptions.
- **`entity`** — the CRM-modeled noun (Contact, Account, Session, etc.). Phase 1 surfaces entity names as nouns the client uses but does not produce full Entity PRDs. Thin schema in v0.4 — name, brief description, status — growing in v0.5+ as Phase 3 work demands.
- **`process`** — Prioritized Backbone members. Phase 1 produces the named set of mission-critical processes plus connections and deferred list. Thin schema in v0.4 — name, priority classification, domain reference, connections via existing references infrastructure — growing in v0.5+ as Phase 3 work fleshes out full process definitions.
- **`crm_candidate`** — Initial CRM Candidate Set entries. Phase 1 produces 2–3 CRM products selected for multi-deploy on coarse fit (open source vs commercial, hosting, budget, integrations, team-IT). Small schema — name, fit reason, status.

### 3.2 What this workstream does not produce

Deliberately deferred to v0.5+:

- **`persona`** — evolved Phase 1 explicitly does not elicit personas in the interview; persona context comes from pre-engagement reading of operational role definitions, used as consultant background rather than captured as records. Tracked as **PI-003**.
- **`field`** — entity fields are a Phase 3 deliverable (Entity PRDs). v0.4 ships entity as a thin name-only record; fields attach in v0.5+. Tracked as **PI-004**.
- **Full process schema** — process beyond the Phase 1 thin shape (steps, actors, fields touched, etc.) — Phase 3 territory. Tracked as **PI-005**.
- **`requirement`, `manual_config`, `test_spec`** — late-phase methodology entity types. Tracked as **PI-004** (grouped).

### 3.3 Multi-tenancy posture (finding, not a decision)

v2 was built as a single-engagement governance store; its current instance hosts the CRM Builder project itself. The original v0.4 kickoff forbids fundamental storage architecture changes, which puts multi-tenant v2 out of scope. The natural model is therefore **one v2 instance per engagement**: CBM redo gets its own v2 instance (separate SQLite, separate API port); v0.4 ships entity types into v2's codebase and both instances pick them up.

Important consequence: CBM's **Mission Statement is hosted by Charter** (the existing v2 entity, versioned-replace + Make Current pattern). No new entity type for Mission Statement.

---

## 4. Methodology

CBM redo uses the **evolved methodology** at `PRDs/process/research/evolved-methodology/`, which structures engagement around five phases (Phase 1: Mission and Backbone Identification; Phase 2: Slice Planning; Phase 3: Iteration Build and Deploy; Phase 4: Iteration Review and Comparison; Phase 5: Engagement Closure and Adoption) and emphasizes running software over upfront specifications.

The choice has two effects on this workstream's scope:

- The four entity types above are the *minimum* needed for evolved Phase 1's outputs. The original 13-phase methodology's Phase 1 (Master PRD) would require a different inventory (it formally produces candidate entity and candidate persona inventories, which evolved Phase 1 does not).
- This CBM redo simultaneously functions as the evolved methodology's adoption pilot. The methodology is currently labeled "research / not adopted" and was simulator-tested against CBM source material on 04-30-26; a real-world test is the next validation step. v0.4 enables the pilot, but adoption is gated on what the pilot reveals.

---

## 5. Workstream structure

### 5.1 Conversations

```
SES-011  This planning conversation (produces this plan + spec guide + four kickoff prompts)
         ↓
SES-?    Schema-design conversation: domain
         ↓
SES-?    Schema-design conversation: entity
         ↓
SES-?    Schema-design conversation: process
         ↓
SES-?    Schema-design conversation: crm_candidate
         ↓
SES-?    v0.4-build-planning conversation (takes the four specs as input, produces the v0.4 PRD, implementation plan, and slice build prompts)
         ↓
[Claude Code execution of the v0.4 build slice prompts]
         ↓
SES-?    v0.4 build closeout (written through the New Session dialog at v0.4 ship)
```

Session identifiers beyond SES-011 are unassigned and will be assigned at each conversation's close per DEC-025.

### 5.2 What each schema-design conversation produces

Per the decision in this planning conversation, each schema-design conversation produces **design only**:

- One **schema spec document** at `PRDs/product/crmbuilder-v2/methodology-schema-specs/<entity_type>.md`, conforming to the structure defined in `methodology-entity-schema-spec-guide.md`
- The **decisions** made during the conversation, written via direct API at the conversation's close as DEC-NNN records
- One **session record** at the conversation's actual close, written through the v0.3 desktop New Session dialog per the session-record-at-close pattern

Build prompts are *not* produced in schema-design conversations. The v0.4-build-planning conversation produces them all.

### 5.3 Order and dependencies

Conversations run **sequentially**, in this order, with no parallelism:

1. **domain** — foundational; both entity and process reference it. Designing domain first means downstream conversations can use it as a settled referent rather than placeholder.
2. **entity** — independent of process; designed before process so process's references to entity are against a settled schema. Thin schema in v0.4 (name, description, status); v0.5+ adds fields and relationships.
3. **process** — most relational of the four (touches both domain and entity). Designed third so both referents already exist.
4. **crm_candidate** — independent of the other three; designed last as a coda that exercises the spec methodology on a simpler schema after the more interconnected ones are done.

### 5.4 The v0.4-build-planning conversation

After all four schema specs exist, a single v0.4-build-planning conversation takes them as input and produces the actual v0.4 release artifacts: the `ui-PRD-v0.4.md` PRD, the `ui-v0.4-implementation-plan.md` slice breakdown, and slice build prompts under `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.4-{A..*}-*.md`.

Build planning is *not* attempted in this planning conversation because the schemas it would integrate do not yet exist. It is also not attempted inside each schema-design conversation because v0.4's cross-cutting concerns (migration sequencing, sidebar ordering, About bump, README update, test target, closeout) need to be designed with all four schemas visible at once.

---

## 6. PI-001 fourth deferral

The styling pass tracked as **PI-001** has been deferred three times — DEC-024 (v0.1 → v0.2), DEC-026 (v0.2 → v0.3), and DEC-037 (v0.3 → "future styling release"). The original v0.4 kickoff treated PI-001 as a forcing function: v0.4 must engage it explicitly, either by adopting it as the primary frame, including partial styling for real-use pain points, or making a fourth deferral explicit with a new tracking mechanism plus rationale.

This workstream **defers PI-001 a fourth time** with the following tracking mechanism (recorded in DEC-042):

**Rationale.** Methodology entity schema design is the v0.4 frame; minimum-viable scope precludes partial styling carve-ins. Styling continues to be lower-priority than enabling CBM redo to run on v2 as content system of record.

**Tracking mechanism — CBM-redo trigger.** If CBM redo Phase 1 (running against the four new methodology entity panels delivered in v0.4) surfaces visual friction on any of those panels, PI-001 gets pulled to v0.5 ahead of any other v0.5 candidate, regardless of v0.5 planning's other priorities. "Visual friction" is intentionally fuzzy — Doug's judgment as the consultant running the redo determines whether something he sees while working bugs him enough to count.

The trigger ties styling priority to real-world evidence rather than calendar. It does not impose a calendar cap (option γ, the "must ship by v0.5 or v0.6" pattern) because the working hypothesis is that real use will produce the right signal on its own.

---

## 7. SES-010 identifier-asymmetry resolution

SES-010 documented a friction: the desktop dialog auto-assigns identifiers via `compute_next_session_identifier`-style helpers, but `POST /<entity>` requires the identifier in the request body, so direct-API consumers (curl, MCP, scripts) hit `request_validation_error: body.identifier — Field required` if they don't compute and supply it. Three resolutions were named in the original v0.4 kickoff: (A) document only — already in place via post-SES-010 CLAUDE.md updates; (B) add `GET /<entity>/next-identifier` helper endpoints; (C) make `identifier` optional in POST bodies with server-side auto-assignment on omission.

This workstream **engages option (B) for all twelve prefixed-identifier entity types** (recorded in DEC-043):

- Existing prefixed entity types receive helper endpoints retrofitted in v0.4 build: decision (DEC-NNN), session (SES-NNN), risk (RSK-NNN), planning item (PI-NNN), topic (TOP-NNN), reference (REF-NNN), charter version (CHR-NNN), status version (STA-NNN). (Of these, charter and status use version-numbered identifiers via versioned-replace; helper semantics need to follow the access-layer pattern, not literally next-integer.)
- New entity types in v0.4 ship with helpers from the start: domain (DOM-NNN), entity (ENT-NNN), process (PROC-NNN), crm_candidate (CRM-NNN).

Reasoning: inconsistency is its own friction — a consultant who learns `GET /domains/next-identifier` works will reasonably expect `GET /decisions/next-identifier` to work too. Retrofitting is mechanical (each helper is ~10 lines) and the work is well-scoped at v0.4 build planning.

**PI-002** tracks option (C) — making `identifier` optional in POST bodies — as a future ergonomic improvement that needs more design (default-vs-required ambiguity for clients that want to specify identifier).

---

## 8. Governance

### 8.1 Decisions

Six decisions consolidate this planning conversation's twelve architectural questions, written via direct API at conversation close:

- **DEC-038** — v0.4 redirect: methodology entity schema design as primary frame, path (b-α) (this conversation pivots to workstream kickoff rather than producing v0.4 PRD directly), minimum-viable scope philosophy, evolved methodology for CBM redo
- **DEC-039** — minimum entity inventory (domain, entity, process, crm_candidate) plus multi-tenancy finding (one v2 instance per engagement)
- **DEC-040** — schema-design workstream structure: design-only conversations, sequential order domain → entity → process → crm_candidate, schema-spec methodology guide as the template
- **DEC-041** — existing v0.4 kickoff supersession: in-place mark
- **DEC-042** — PI-001 fourth deferral with CBM-redo-friction trigger mechanism
- **DEC-043** — SES-010 resolution: `GET /<entity>/next-identifier` helpers for all twelve prefixed entity types in v0.4 build, with PI-002 tracking option (C) as future work

### 8.2 Planning items

- **PI-001** — updated to reflect fourth deferral; cites DEC-042
- **PI-002** — new: make `identifier` optional in POST bodies (option C for SES-010); future ergonomic improvement
- **PI-003** — new: persona entity type for v0.5+ (deferred from minimum-viable inventory choice)
- **PI-004** — new: additional methodology entity types (field, requirement, manual_config, test_spec) for v0.5+
- **PI-005** — new: process schema growth beyond Phase 1 thin (full process schema for Phase 3+ Iteration Build and Deploy work)

### 8.3 Session record

SES-011 is **not** written during this conversation. It is written at the conversation's *actual* close, through the v0.3 desktop New Session dialog, per the session-record-at-close pattern introduced after SES-008's coverage gap. The session record captures the seed prompt verbatim, the architectural questions asked and answered, the artifacts produced (this plan + the spec guide + four kickoff prompts + the supersession edit + the six decisions + the five planning items), and what's in flight at conversation end (the four schema-design conversations queued up, the v0.4-build-planning conversation queued after them).

### 8.4 Status

No status update from this planning conversation. Status remains **v1.0 / `"v0.3 complete"`** until v0.4 actually ships. The workstream is mid-flight; status reflects last shipped state.

---

## 9. Production-use feedback loop

This workstream is itself a production-use exercise of v0.3. Each schema-design conversation:

- Reads from v0.3's REST API and MCP (decisions, sessions, planning items, references)
- Records new decisions via direct API
- Closes with a session record authored through the v0.3 desktop New Session dialog

Frictions encountered during the workstream feed back into v0.5 candidate scope. If a schema-design conversation surfaces "I wish v0.3 did X," X becomes a v0.5 candidate — recorded either as a new planning item or as in-flight notes in that conversation's session record.

This is the closest thing to the kickoff's "On timing" advisory ("Consider running v0.4 planning after some weeks of v0.3 production use") that the workstream can produce on its own schedule: rather than waiting for governance friction to surface in the abstract, the workstream generates the governance friction directly by doing real schema-design work in v2.

---

## 10. Open questions and deferred design

Things not settled by this planning conversation that future workstream conversations will need to answer:

- **Identifier prefix conventions for the four new entity types.** The plan names DOM, ENT, PROC, CRM as working assumptions, but the actual prefix is each schema-design conversation's call (PROC may want to be PRC; CRM is potentially ambiguous if abbreviated; ENT versus E).
- **Cross-spec consistency conventions.** The schema-spec methodology guide lists categories (identifier format, status-field naming, soft-delete pattern, reference-vocabulary verb tense) but does not pre-decide the conventions. The first schema-design conversation (domain) effectively decides them; subsequent conversations follow unless they have a strong reason to deviate.
- **Reference vocabulary additions.** New relationship-kind values needed to express process-to-process connections, process-to-entity touches, entity-scoped-to-domain, etc. Drafted in each schema-design conversation; consolidated at the v0.4-build-planning conversation.
- **Whether the v0.4-build-planning conversation produces a v0.4 PRD with `ui-PRD-v0.4.md` shape, or something different.** Working assumption: the same PRD shape as v0.1/v0.2/v0.3, since v0.4 is a UI release at heart (it ships UI panels backing four new entity types).

---

## 11. The schema-spec methodology guide

Each schema-design conversation produces a schema spec conforming to `methodology-entity-schema-spec-guide.md`, which is the second artifact this planning conversation produces alongside this workstream plan. The guide defines what a complete schema spec looks like — required sections, conversation cadence, decision/session governance per (b-α), cross-spec consistency requirements, validation gates before v0.4-build planning.

See `methodology-entity-schema-spec-guide.md` for the full template.

---

## 12. The four per-entity kickoff prompts

Each schema-design conversation opens against a per-entity kickoff prompt at the root of `PRDs/product/crmbuilder-v2/`:

- `schema-design-kickoff-domain.md`
- `schema-design-kickoff-entity.md`
- `schema-design-kickoff-process.md`
- `schema-design-kickoff-crm_candidate.md`

Each is structured to match the v0.2/v0.3/v0.4 planning-prompt cadence (purpose, predecessor, read-first list, working style, governance, pre-flight, scope, what NOT to do). Per-entity content distinguishes them: scope of that entity type's role in evolved Phase 1, prior schemas to read (e.g., `entity`'s kickoff references the already-completed `domain` spec), specific design questions likely to arise.

---

## 13. Glossary

- **(b-α)** — The path under option (b) of this planning conversation's first architectural fork: v0.4 frame is methodology entity schema design, but rather than designing schemas inline (forbidden by the original kickoff), the planning conversation pivots to producing a kickoff for a separate schema-design workstream.
- **Evolved methodology** — The 5-phase iteration-oriented restructure at `PRDs/process/research/evolved-methodology/`, currently labeled research / not adopted; the CBM redo serves as both adoption pilot and v2-content-store real-world test.
- **Methodology entity types** — Entity types that hold methodology *content* (domains, entities, processes, etc.), as opposed to **governance entity types** which hold metadata about the project itself (decisions, sessions, charter, status, risks, planning items, topics, references).
- **Production-use friction** — The kickoff's term for evidence about what features matter that comes from actually using v2 for real work, as opposed to speculation about what features would be valuable.
- **Real-world test** — Using v2 to host a real client engagement's methodology content end to end, as opposed to a simulated test or research exercise.

---

*End of document.*

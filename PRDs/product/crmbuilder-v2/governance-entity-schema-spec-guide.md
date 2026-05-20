# Governance Entity Schema Specification — Methodology Guide

**Last Updated:** 05-20-26 22:30
**Status:** Active — template for the six schema-design conversations in the governance-entity-schema-design workstream.
**Companion document:** `governance-schema-workstream-plan.md`

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-20-26 22:30 | Doug Bower / Claude (workstream-establishing conversation, session identifier assigned at close) | Initial guide. Produced alongside `governance-schema-workstream-plan.md` by the workstream-establishing conversation. Inherits conventions from the methodology entity schema-design workstream where compatible: parent-prefix field naming (DEC-046), source-first relationship-kind naming (DEC-048), prefer-simple-lifecycle posture. References DEC-117 through DEC-122 as workstream foundation. |

---

## Change Log

**Version 1.0 (05-20-26 22:30):** Initial creation. Defines what a complete governance entity schema specification contains, how a schema-design conversation runs, what decisions and session records the conversation produces, and what consistency conventions apply across all six schemas. Conventions inherited from the methodology entity schema-design workstream (parent-prefix field naming, source-first relationship-kind naming, default soft-delete posture, default identifier auto-assignment helper); no "methodology only" scope qualifier on those rows because they are now policy for new entity types regardless of category. Lifecycle posture differs from methodology: governance entities track workflow state (planned → in-flight → complete and similar), so lifecycle tables are expected to be richer than the methodology workstream's typical `candidate`/`confirmed` pair, while still preferring the smallest viable set of states.

---

## 1. Purpose and scope

This guide is the **template every governance entity schema specification must follow.** It exists so the six schema-design conversations in the workstream produce specifications that are structurally consistent — the same sections in the same order with the same content shape — and so the build-planning conversation can take all six specifications as inputs without translation overhead.

The guide is *not* any specific entity type's schema. The six schema specifications (`workstream.md`, `conversation.md`, `reference_book.md`, `work_ticket.md`, `close_out_payload.md`, `deposit_event.md` at `PRDs/product/crmbuilder-v2/governance-schema-specs/`) are the per-entity-type instances produced under this template.

The guide is *not* a V2 storage-layer or REST-API design document. It assumes the existing storage layer (SQLite + Alembic + access layer + REST API at `127.0.0.1:8765` + MCP server) is the home for the new entity types. Schema specifications describe what each new entity *is*; the build-planning conversation describes how it gets integrated into V2's existing infrastructure.

---

## 2. Definition of "complete schema spec"

A schema specification is **complete** when a developer could implement the entity type in V2 from this specification alone, without needing to reopen any design question. Concretely, a complete specification answers:

- What is this entity type called and how is it identified?
- What fields does it have, with what types, defaults, and validation?
- What does it relate to, and how (via foreign-key fields, via the references entity, or via hierarchy)?
- What lifecycle states does a record pass through, and what transitions are valid?
- What REST endpoints does it expose, and what is the identifier-assignment behavior?
- How does it render in the desktop user interface — sidebar position, master columns, detail layout, CRUD dialog shape, reference rendering?
- What does "this entity type is correctly implemented" look like as acceptance criteria?
- What is *not* settled in this specification, and where does the deferred question land (build prompt, retroactive backfill, future user-interface version)?

If any of these is missing or hand-waved, the specification is not complete. The validation gate at section 7 makes this concrete.

---

## 3. Required sections of every schema specification

Every schema specification must include the following sections, in this order, with the section numbers shown. Section content is structured per the conventions below.

### 3.1 Identity

What this entity type is called, how it appears in the user interface, and how individual records are identified.

| Field | Required | Notes |
|-------|----------|-------|
| Entity type name (storage) | yes | `snake_case`, singular (e.g., `workstream`, `close_out_payload`) |
| Display name (singular) | yes | Title-cased noun phrase (e.g., "Workstream", "Close-Out Payload") |
| Display name (plural) | yes | User interface sidebar and panel-title use (e.g., "Workstreams", "Close-Out Payloads") |
| Identifier prefix | yes | 2–5 uppercase letters; must not collide with existing prefixes — see section 6 for the current collision list |
| Identifier format | yes | Default is `{PREFIX}-NNN` zero-padded to 3 digits, matching existing entity types |
| Identifier auto-assignment | yes | Default: assigned server-side on POST when omitted, accessible via `GET /{plural}/next-identifier`; deviation requires justification |

### 3.2 Fields

The full list of fields on the entity type, organized by category. Each field has: name, type, required, default, validation, description.

**Field categories** (every specification uses these category headers, in this order):

1. **Identity fields.** The identifier and any human-readable name or title field. Always required.
2. **Content fields.** Text, structured-text, or JSON fields that hold the entity's substantive content (descriptions, summaries, payload blobs, etc.).
3. **Classification fields.** Status, kind, type, priority — enumerated fields that constrain or categorize a record.
4. **Relationship fields.** Foreign-key fields linking to other entity types' identifiers. Soft foreign keys (string columns referencing identifiers) per existing V2 storage conventions; not enforced at the database layer but validated at the access layer.
5. **Timestamp fields.** Inherited from base: `created_at`, `updated_at`, `deleted_at`. Specifications do not redeclare these unless deviating from base behavior. Entity-specific lifecycle timestamps (e.g., `planned_at`, `started_at`, `completed_at`, `applied_at`) are declared here when relevant.

Field declarations use this table shape:

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|

Empty cells are explicitly `—` (em dash), not blank, so readers can distinguish "no default" from "I forgot to fill this in."

Per parent-prefix convention (DEC-046, inherited from methodology workstream): fields are named with the parent entity's prefix when the field belongs to that entity (e.g., `workstream_identifier`, `workstream_name`, `workstream_status` on the workstream entity). Fields that reference another entity carry that entity's name as a suffix on `_id` (e.g., `workstream_id` on a conversation record, naming the workstream the conversation belongs to).

### 3.3 Relationships

How this entity type relates to other entity types. Three relationship mechanisms are available in V2:

1. **Direct foreign-key fields** in section 3.2.4 — a single foreign-key column on this entity's table. Use when the relationship is one-to-many and the cardinality is settled (e.g., a `conversation` belongs to one `workstream`).
2. **References entity** — the cross-entity-type edge store at V2's `reference` table, governed by `RELATIONSHIP_RULES` in `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`. Use when the relationship is many-to-many, when multiple kinds of edge are needed, or when the relationship has its own metadata.
3. **Hierarchy** — parent-of pattern via a self-referential foreign key, per the `topic` entity's `parent_topic` field. Use when the entity is naturally tree-shaped (the nested-workstream question for the workstream entity may invoke this pattern, depending on that conversation's resolution).

Each relationship gets a short subsection describing: relationship name, mechanism, cardinality, validation rules, lifecycle semantics (does deletion of one side imply anything about the other?).

New relationship-kind vocabulary entries are listed as a table:

| relationship_kind | source entity type | target entity type | semantics |
|-------------------|--------------------|--------------------|-----------|

Per source-first convention (DEC-048, inherited from methodology workstream): relationship-kind values use `{source}_{verb}_{target}` style (e.g., `conversation_belongs_to_workstream`, `deposit_event_applies_close_out_payload`). The vocabulary additions each schema specification requires are aggregated by the build-planning conversation and translated into one `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` update plus one Alembic migration on `refs.relationship_kind`'s CHECK constraint.

### 3.4 Lifecycle

Statuses and transitions a record passes through, plus soft-delete semantics.

**Status declarations** use a table:

| Status value | Description | Valid predecessors | Valid successors |
|--------------|-------------|--------------------|-----------------|

Cross-spec consistency: status values use lowercase `snake_case`; the default starter status is named in the table.

Lifecycle posture for governance entities: prefer the smallest viable status set, but governance entities legitimately need richer lifecycles than methodology entities — the workflow they track has more states. The conversation entity's lifecycle is the obvious example (planned, kickoff-drafted, ready, in-flight, complete, cancelled, superseded per DEC-119; the per-entity conversation may refine). Specifications with more than three statuses are expected and do not need special justification, provided the states are operationally meaningful and transitions are well-defined.

**Soft-delete semantics** follow V2 base behavior unless the specification deviates: `deleted_at` set on delete; soft-deleted records do not appear in list endpoints; "show deleted" toggle (per Decisions panel pattern) supported.

Append-only behavior — the pattern decisions and sessions use per DEC-013 — is also available. The deposit event entity is an obvious candidate (apply outcomes are facts; rewriting them would erase history). Specifications that choose append-only over soft-delete document the rationale in this section.

### 3.5 API surface

REST endpoints and identifier-assignment behavior.

**Endpoints** are listed as a table:

| Method | Path | Body | Notes |
|--------|------|------|-------|

Standard endpoints (every specification includes these unless explicitly deviating):

- `GET /{plural}` — list, supports `?include_deleted=true` flag
- `GET /{plural}/{identifier}` — single fetch
- `POST /{plural}` — create
- `PUT /{plural}/{identifier}` — full replace
- `PATCH /{plural}/{identifier}` — partial update
- `DELETE /{plural}/{identifier}` — soft delete
- `POST /{plural}/{identifier}/restore` — restore from soft delete
- `GET /{plural}/next-identifier` — identifier-asymmetry helper per the SES-010 resolution rolled out in user-interface version 0.4

Deviations (e.g., append-only — no PUT, PATCH, DELETE; or single-shot — no PATCH) are explicitly noted with rationale. The deposit event entity is expected to be append-only; the close-out payload entity may be append-only after apply.

**Identifier auto-assignment** subsection: confirms the entity uses the default server-side auto-assignment-on-omit pattern, or describes how it differs.

All API responses return the `{data, meta, errors}` envelope per existing convention. Specifications do not redeclare this; the envelope is a property of the API, not of any entity type.

### 3.6 User interface considerations

Sidebar position, master/detail panel layout, dialog shape. **This section uses the template-with-deviation pattern**: a default layout is given, and a specification may diverge from it with explicit justification in the same section.

**Default layout** (deviation requires rationale):

- **Sidebar position.** New governance entity types appear in the existing "Governance" sidebar group; order within the group follows workstream order (workstream, conversation, reference book, work ticket, close-out payload, deposit event) at the end of the group. The build-planning conversation may decide to introduce a sub-grouping if the Governance group grows unwieldy.
- **Master pane.** `ListDetailPanel`-backed list with columns: `identifier`, primary name field, `status`, `updated_at`. Default sort by identifier ascending. Right-click context menu offers New / Edit / Delete / Restore (matching user-interface version 0.3 patterns).
- **Detail pane.** Vertical layout: identifier (read-only), name, content fields in section 3.2 order, classification fields, relationship fields rendered via the existing `ReferencesSection` widget. "Add reference" affordance on detail pane per user-interface version 0.3.
- **Create dialog.** Modal `EntityCrudDialog` subclass. Field order matches section 3.2. Required fields validated client-side; server-side errors surface inline. Identifier auto-assigned (not editable in create mode); default-fill behaviors per section 3.2.
- **Edit dialog.** Same shape as create, identifier read-only. Append-only entities omit the edit dialog.
- **Delete dialog.** `EntityCrudDeleteDialog` with edge-text confirmation matching user-interface version 0.3 patterns. Append-only entities omit the delete dialog.

Specifications that deviate from the default layout must include a "Deviation rationale" subsection explaining what changed and why.

### 3.7 Acceptance criteria

What "this entity type is correctly implemented in the eventual build" looks like. Acceptance criteria are concrete, testable statements, written as a numbered list. Categories typically include:

- Schema migration applies cleanly against an existing engagement database
- Access-layer methods exist with expected signatures and pass unit tests
- REST endpoints return expected responses for representative cases, including envelope shape
- Identifier auto-assignment helper returns next ID without race conditions
- User interface panel appears in sidebar in correct position
- Master pane lists records with correct columns and sort
- Detail pane renders all fields including references
- CRUD dialogs work end to end (create round-trips; edit persists; delete soft-deletes; restore reverses), with append-only deviations honored
- File-watch refresh picks up external changes
- Sample governance records representative of the entity type's intended use can be authored through the dialog without leaving the user interface

Each criterion is testable in the eventual build, not in the schema-design conversation. Schema specifications *list* the criteria; build planning translates them into test cases.

### 3.8 Open questions and deferred decisions

Anything the schema-design conversation did not settle and does not need to settle. Categorized:

- **For the build-planning conversation to settle.** Implementation-level questions (migration ordering, exact endpoint test fixtures, sidebar sub-grouping if needed, etc.) that depend on cross-schema visibility.
- **For retroactive backfill to surface.** Things that the act of populating historical records will answer better than design speculation (e.g., "should workstream's `started_at` accept a historical timestamp or always be wall-clock at creation?" might fall here).
- **For future user-interface version.** Deferred features explicitly captured as planning items, with the planning item identifier cited.

Each open question is one paragraph maximum, with a category tag.

### 3.9 Cross-references

Decisions cited by this specification, related schemas (other entries in `governance-schema-specs/`), and external references (the workstream master plan, this guide, the multi-engagement architecture document, the methodology workstream's relevant artifacts where the methodology workstream's pattern is being followed). One-line entries; the rest of the specification sources its substance from the linked documents rather than restating them.

The foundation decisions DEC-117 through DEC-122 are cited by every specification; each specification names which of the six it most directly extends (typically one or two).

---

## 4. Schema-design conversation cadence

Each per-entity schema-design conversation follows this cadence:

### 4.1 Pre-flight (before the first architectural question)

The conversation reads:

1. `crmbuilder/CLAUDE.md` — universal session-startup entry.
2. `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md` — workstream master plan.
3. This guide (`governance-entity-schema-spec-guide.md`).
4. The per-entity kickoff prompt (`schema-design-kickoff-{entity_name}.md`).
5. The foundation decisions DEC-117 through DEC-122, with focus on the one or two most directly relevant to the entity being designed.
6. All previously-completed schema specifications in `governance-schema-specs/` (so later conversations see the conventions established by earlier ones).
7. The session record for SES-046 (predecessor scoping conversation), and subsequent schema-design conversations' session records, for context on what was already decided.
8. The relevant V2 architecture documents:
   - `multi-engagement-architecture.md` — engagement isolation; new entity types are per-engagement.
   - `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — current reference vocabulary; new relationship-kind values declared by each specification are aggregated by the build-planning conversation.
   - Existing entity types' migrations under `crmbuilder-v2/alembic/versions/` — Alembic patterns to follow.
9. For specific entities, also:
   - For `conversation`: the workstream specification just completed.
   - For `reference_book` and `work_ticket`: any prior specifications, plus the conversation specification (these entities are referenced by conversations).
   - For `close_out_payload`: the conversation specification (close-out payloads are produced by conversations) and the existing close-out payload format documented in `prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-025.md` and the JSON files under `close-out-payloads/`.
   - For `deposit_event`: the close-out payload specification just completed, plus existing apply scripts as the operational model.

Pre-flight also runs the standard checks: API health at `http://127.0.0.1:8765/health`, V2 test suite (`uv run pytest tests/crmbuilder_v2/ -v`), `git pull --rebase origin main`.

### 4.2 Discussion structure

The conversation drives **one architectural question at a time** in plain text, matching the methodology workstream's working style:

- Bold section headings acceptable; bullet-point overload avoided.
- Terse approvals ("yes", "confirm", "a", "1 good") sufficient; no re-summary needed.
- Propose document structures and outlines; user approves before drafting begins.
- Once outline is confirmed and section content is approved, execute the drafting end-to-end without per-step confirmation.

Architectural questions typically include:

- Identifier prefix and format (does the working assumption hold or change?)
- Field inventory — which fields does the entity type have under minimum-viable scope?
- Required vs. optional fields and their defaults
- Relationships — direct foreign key, references entity, or hierarchy? What relationship-kind values?
- Lifecycle — how many statuses, what transitions, append-only or soft-delete?
- API deviations — does this entity type need anything beyond the standard endpoint set?
- User interface deviations — does the default layout fit, or does this entity need a different shape?

### 4.3 Drafting

After all architectural questions are settled, the schema specification is drafted in one pass per section 3's structure (`PRDs/product/crmbuilder-v2/governance-schema-specs/{entity_name}.md`). The drafting phase reuses the planning-conversation language but adapts it into the specification format.

### 4.4 Governance recording (at conversation close, not during)

At the conversation's actual close, the conversation records:

- **Decisions.** Each architectural question's resolution becomes a decision record, authored via direct API. Decisions reference the specification produced and any prior schemas they extend.
- **Planning items.** Anything explicitly deferred is authored as a planning item, with the planning item identifier cited in the specification's section 3.8.
- **Session record.** The conversation closes with a session record written through the V2 desktop New Session dialog, following the session-record-at-close pattern. `topics_covered` opens with the seed prompt verbatim; `artifacts_produced` lists the specification and any planning items; `in_flight_at_end` names the next schema-design conversation in the workstream (or, for the sixth conversation, the build-planning conversation).

The session-record-at-close pattern matters because it prevents the SES-008 coverage gap pattern from recurring: if the record were written mid-conversation, subsequent conversation turns would not be captured.

---

## 5. Governance discipline

The following disciplines apply to every schema-design conversation:

- **No build prompts.** Schema-design conversations produce design only. Build prompts come from the build-planning conversation.
- **No storage architecture changes.** New entity types extend the storage layer additively (new tables, new endpoints, new access-layer methods); they do not modify existing entity types' shapes or behaviors. Reference vocabulary additions are extensions, not modifications.
- **No fundamental user interface architecture changes.** New panels extend the existing pattern (ListDetailPanel-backed, sidebar-grouped); they do not introduce new top-level user interface structures.
- **No touching of the methodology entity types** shipped in user-interface versions 0.4 and 0.5. Those remain unchanged.
- **No touching of in-flight parallel work** (multi-tenancy routing fix slices, Cleveland Business Mentors Planning Item 001). Governance entity schema design is independent of those workstreams per DEC-122.

If a schema-design conversation surfaces a need for fundamental change (e.g., "this entity type needs a tab-bar instead of a sidebar entry"), the conversation flags it as an open question for the build-planning conversation rather than designing inline.

---

## 6. Cross-spec consistency requirements

Conventions all six schemas share, validated at the consistency check before the build-planning conversation opens:

| Convention | Value |
|------------|-------|
| Identifier prefix style | 2–5 uppercase letters, no digits, no underscores. Must not collide with existing prefixes: DEC, SES, RSK, PI, TOP, REF, CHR, STA (governance) and DOM, ENT, PROC, CRM, ENG (methodology, including engagement). |
| Identifier format | `{PREFIX}-NNN`, zero-padded to 3 digits |
| Status field name | `{parent}_status` per parent-prefix convention (DEC-046). E.g., `workstream_status`, `conversation_status`. |
| Status values | lowercase `snake_case` |
| Default starter status | named explicitly in each specification's section 3.4 |
| Relationship-kind naming | `{source}_{verb}_{target}` source-first pattern per DEC-048. E.g., `conversation_belongs_to_workstream`, `close_out_payload_produced_by_conversation`. |
| Field naming | `snake_case`, with all fields including identifier and timestamps prefixed with the parent entity name per DEC-046. E.g., `workstream_identifier`, `workstream_name`, `workstream_created_at`. Singular nouns for scalar fields; plural for collection/JSON fields. |
| Timestamp inheritance | Inherit base `created_at`, `updated_at`, `deleted_at` without redeclaring; entity-specific lifecycle timestamps declared in section 3.2.5 |
| Soft-delete behavior | Default (filtered from list endpoints, restorable via `/restore` endpoint), unless the entity adopts append-only (declared explicitly in section 3.4) |
| Identifier auto-assignment | Default (server-side on POST omission, helper at `GET /{plural}/next-identifier`) |
| Lifecycle preference | Prefer the smallest viable status set; richer lifecycles acceptable for entities that legitimately need them (conversation, workstream) without requiring special justification |
| API envelope | All endpoints return `{data, meta, errors}` per existing V2 convention; no per-entity declaration needed |

A specification that deviates from any of these must explicitly call out the deviation and justify it in the relevant section. The methodology workstream produced three documented deviations across its four specifications, all accepted as well-justified; the same pattern applies here.

**Scope note.** These conventions apply to the six governance entity types designed in this workstream and to any new entity types introduced after them. They do NOT apply retroactively to V2's pre-workstream governance entity types (decision, session, risk, planning item, topic, reference, charter, status); those retain their pre-workstream conventions until and unless the retrofit tracked as PI-006 (from the methodology workstream) lands. This guide does not amend PI-006.

---

## 7. Validation gates

Two gates apply before a schema specification is considered ready to feed the build-planning conversation:

### 7.1 Per-spec completeness

A schema specification passes the per-spec completeness gate when:

- All nine subsections of section 3 are present and substantively filled (no `TBD` or placeholder content)
- Section 3.7 (Acceptance criteria) has at least ten concrete, testable statements
- Section 3.8 (Open questions) has explicit category tags on every entry
- Section 3.9 (Cross-references) cites at least the workstream plan, this guide, the foundation decisions DEC-117 through DEC-122, and any prior governance schemas this entity type relates to

Per-spec completeness is the schema-design conversation's responsibility; the conversation does not close until the specification passes.

### 7.2 Cross-spec consistency

After all six schema specifications exist, before the build-planning conversation opens, the cross-spec consistency check verifies:

- No identifier prefix collisions (against the list in section 6 and against any prefixes the six specifications themselves introduce)
- All six specifications use the conventions in section 6 (or explicitly justify deviations)
- Relationship-kind vocabulary additions across the six specifications do not conflict (no two specifications declaring the same `relationship_kind` with different semantics)
- Status-value naming is consistent across specifications where the same concept is reused (a `complete` status means the same thing in workstream and conversation, for instance)
- Lifecycle interactions across specifications are coherent (e.g., a conversation cannot be `complete` if its workstream is `planned` — or if it can, the conversation specification documents that explicitly)
- User interface panel layouts (section 3.6) are either default or have rationale-justified deviations
- Append-only versus soft-delete choices across specifications are coherent and intentional

Cross-spec consistency is the build-planning conversation's first task. If inconsistencies surface, they are resolved by reopening the affected schemas (small revisions) before build planning proper begins.

---

## 8. Open methodology questions

Things this guide does not yet specify; expected to surface during the first schema-design conversation (workstream) and get folded back into the guide for subsequent conversations.

- **Workstream identifier prefix collision check.** `WS` is the working assumption but is not yet confirmed. The workstream conversation has first refusal; the chosen prefix is locked into section 6 once that conversation closes.
- **Reference-book identifier collision risk.** `RB` is short and may collide visually with future prefixes. The reference-book conversation revisits.
- **Append-only as a section-3.4 first-class option.** The methodology workstream did not need append-only; this workstream likely does (deposit event, possibly close-out payload). Section 3.4 names it as available; the first append-only specification refines what "append-only" means concretely at the API surface (no PUT, no PATCH, no DELETE; or some of these still permitted under restricted semantics).
- **Lifecycle interaction across entities.** Section 7.2 names this as a consistency check item, but the methodology workstream had no equivalent — its entities were largely independent. The governance entities are interdependent (a conversation cannot complete without a workstream context; a deposit event cannot exist without a close-out payload). The first specification with rich lifecycle (workstream or conversation) sets the precedent for how cross-entity lifecycle constraints are expressed.
- **Whether section 3.6's default sidebar grouping suffices for six new entries in the Governance group.** If the existing Governance group has eight entries and gains six more, the group becomes hard to scan. The build-planning conversation may introduce a sub-grouping (e.g., "Governance — workflow" for the new six) or reorder. Schema specifications declare default position; the build-planning conversation may overrule.
- **Spec-versioning policy.** If a schema specification needs to be revised after its conversation closes (e.g., the cross-spec consistency check surfaces an issue), is that a new version of the same specification (revision history grows) or a new conversation? Working assumption inherited from the methodology workstream: revision in place with a change-log entry citing the source of the change; new conversation only if the revision is large enough to warrant its own architectural discussion.

---

*End of document.*

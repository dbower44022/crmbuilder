# Methodology Entity Schema Specification — Methodology Guide

**Last Updated:** 05-11-26 16:00
**Status:** Active — template for the four schema-design conversations in the methodology-entity-schema-design workstream.
**Companion document:** `methodology-schema-workstream-plan.md`

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-11-26 16:00 | Doug Bower / Claude (SES-011) | Initial guide. Produced alongside the workstream plan that redirected v0.4 to methodology entity schema design. |

---

## Change Log

**Version 1.0 (05-11-26 16:00):** Initial creation. Defines what a complete methodology-entity schema spec contains, how a schema-design conversation runs, what decisions and session records the conversation produces, and what consistency conventions apply across all four schemas. Section 3.6 (UI considerations) uses the template-with-deviation-by-justification pattern: a default panel layout that any schema may diverge from with explicit rationale in its spec.

---

## 1. Purpose and scope

This guide is the **template every methodology-entity schema spec must follow.** It exists so that the four schema-design conversations in the workstream produce specs that are structurally consistent — the same sections in the same order with the same content shape — and so that the v0.4-build-planning conversation can take all four specs as inputs without translation overhead.

The guide is *not* any specific entity type's schema. The four schema specs (`domain.md`, `entity.md`, `process.md`, `crm_candidate.md` at `PRDs/product/crmbuilder-v2/methodology-schema-specs/`) are the per-entity-type instances produced under this template.

The guide is *not* a v2 storage-layer or REST-API design document. It assumes the existing storage layer (SQLite + Alembic + access layer + REST API at `127.0.0.1:8765` + MCP server) is the home for the new entity types. Schema specs describe what each new entity *is*; the v0.4-build-planning conversation describes how it gets integrated into v2's existing infrastructure.

---

## 2. Definition of "complete schema spec"

A schema spec is **complete** when a developer could implement the entity type in v2 from this spec alone, without needing to reopen any design question. Concretely, a complete spec answers:

- What is this entity type called and how is it identified?
- What fields does it have, with what types, defaults, and validation?
- What does it relate to, and how (via FKs, via the references entity, or via hierarchy)?
- What lifecycle states does a record pass through, and what transitions are valid?
- What REST endpoints does it expose, and what's the identifier-assignment behavior?
- How does it render in the desktop UI — sidebar position, master columns, detail layout, CRUD dialog shape, reference rendering?
- What does "this entity type is correctly implemented" look like as acceptance criteria?
- What's *not* settled in this spec, and where does the deferred question land (build prompt, CBM redo, v0.5+)?

If any of these is missing or hand-waved, the spec is not complete. The validation gate at section 7 makes this concrete.

---

## 3. Required sections of every schema spec

Every schema spec must include the following sections, in this order, with the section numbers shown. Section content is structured per the conventions below.

### 3.1 Identity

What this entity type is called, how it appears in the UI, and how individual records are identified.

| Field | Required | Notes |
|-------|----------|-------|
| Entity type name (storage) | yes | `snake_case`, singular (e.g., `domain`, `crm_candidate`) |
| Display name (singular) | yes | Title-cased noun phrase (e.g., "Domain", "CRM Candidate") |
| Display name (plural) | yes | UI sidebar and panel-title use (e.g., "Domains", "CRM Candidates") |
| Identifier prefix | yes | 3–5 uppercase letters (e.g., `DOM`, `PROC`); must not collide with existing prefixes (DEC, SES, RSK, PI, TOP, REF, CHR, STA) |
| Identifier format | yes | Default is `{PREFIX}-NNN` zero-padded to 3 digits, matching existing entity types |
| Identifier auto-assignment | yes | Default: assigned server-side on POST when omitted, accessible via `GET /{plural}/next-identifier`; deviation requires justification |

### 3.2 Fields

The full list of fields on the entity type, organized by category. Each field has: name, type, required, default, validation, description.

**Field categories** (every spec uses these category headers, in this order):

1. **Identity fields.** The identifier and any human-readable name field. Always required.
2. **Content fields.** Text, structured-text, or JSON fields that hold the entity's substantive content. The bulk of most schemas lives here.
3. **Classification fields.** Status, priority, kind, type — enumerated fields that constrain or categorize a record.
4. **Relationship fields.** FK fields linking to other entity types' identifiers. Soft FKs (string columns referencing identifiers) per existing v2 storage conventions; not enforced at the DB layer but validated at the access layer.
5. **Timestamp fields.** Inherited from base: `created_at`, `updated_at`, `deleted_at`. Schemas do not redeclare these unless deviating from base behavior.

Field declarations use this table shape:

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|

Empty cells are explicitly `—` (em dash), not blank, so readers can distinguish "no default" from "I forgot to fill this in."

### 3.3 Relationships

How this entity type relates to other entity types. Three relationship mechanisms are available in v2:

1. **Direct FK fields** in section 3.2.4 — a single FK column on this entity's table. Use when the relationship is one-to-many and the cardinality is settled (e.g., a `process` belongs to one `domain`).
2. **References entity** — the cross-entity-type edge store at v2's `reference` table, governed by `RELATIONSHIP_RULES`. Use when the relationship is many-to-many, when multiple kinds of edge are needed, or when the relationship has its own metadata (creation date, who created it, etc.). New `relationship_kind` values needed for the new entity types are declared here.
3. **Hierarchy** — parent-of pattern via a self-referential FK, per the `topic` entity's `parent_topic` field. Use when the entity is naturally tree-shaped.

Each relationship gets a short subsection describing: relationship name, mechanism, cardinality, validation rules, lifecycle semantics (does deletion of one side imply anything about the other?).

New relationship-kind vocabulary entries are listed as a table:

| relationship_kind | source entity type | target entity type | semantics |
|-------------------|--------------------|--------------------|-----------|

Cross-spec consistency: relationship-kind values use **verb_phrase** style (e.g., `process_connects_to`, not `process_connection`).

### 3.4 Lifecycle

Statuses and transitions a record passes through, plus soft-delete semantics.

**Status declarations** use a table:

| Status value | Description | Valid predecessors | Valid successors |
|--------------|-------------|--------------------|-----------------|

Cross-spec consistency: status values use lowercase `snake_case` (e.g., `candidate`, `confirmed`, `deferred`, `archived`); the default starter status is named in the table.

**Soft-delete semantics** follow v2 base behavior unless the spec deviates: `deleted_at` set on delete; soft-deleted records do not appear in list endpoints; "show deleted" toggle (per Decisions panel pattern) supported.

### 3.5 API surface

REST endpoints and identifier-assignment behavior.

**Endpoints** are listed as a table:

| Method | Path | Body | Notes |
|--------|------|------|-------|

Standard endpoints (every spec includes these unless explicitly deviating):

- `GET /{plural}` — list, supports `?include_deleted=true` flag
- `GET /{plural}/{identifier}` — single fetch
- `POST /{plural}` — create
- `PUT /{plural}/{identifier}` — full replace
- `PATCH /{plural}/{identifier}` — partial update
- `DELETE /{plural}/{identifier}` — soft delete
- `POST /{plural}/{identifier}/restore` — restore from soft delete
- `GET /{plural}/next-identifier` — identifier-asymmetry helper per SES-010 resolution

Deviations (e.g., create-only like sessions; no PATCH like topics) are explicitly noted with rationale.

**Identifier auto-assignment** subsection: confirms the entity uses the default server-side auto-assignment-on-omit pattern, or describes how it differs.

### 3.6 UI considerations

Sidebar position, master/detail panel layout, dialog shape. **This section uses the template-with-deviation pattern**: a default layout is given, and a spec may diverge from it with explicit justification in the same section.

**Default layout** (deviation requires rationale):

- **Sidebar position.** New methodology entity types appear in a "Methodology" group below the existing "Governance" group; order within the group follows workstream order (domain, entity, process, crm_candidate).
- **Master pane.** `ListDetailPanel`-backed list with columns: `identifier`, `name`, `status`, `updated_at`. Default sort by identifier ascending. Right-click context menu offers New/Edit/Delete/Restore (matching v0.3 patterns).
- **Detail pane.** Vertical layout: identifier (read-only), name, content fields in section-3.2 order, classification fields, relationship fields rendered via the existing `ReferencesSection` widget. "Add reference" affordance on detail pane per v0.3.
- **Create dialog.** Modal `EntityCrudDialog` subclass. Field order matches section 3.2. Required fields validated client-side; server-side errors surface inline. Identifier auto-assigned (not editable in create mode); default-fill behaviors per section 3.2.
- **Edit dialog.** Same shape as create, identifier read-only.
- **Delete dialog.** `EntityCrudDeleteDialog` with edge-text confirmation matching v0.3 patterns.

Specs that deviate from the default layout must include a "Deviation rationale" subsection explaining what changed and why.

### 3.7 Acceptance criteria

What "this entity type is correctly implemented in v0.4" looks like. Acceptance criteria are concrete, testable statements, written as a numbered list. Categories typically include:

- Schema migration applies cleanly
- Access-layer methods exist with expected signatures and pass unit tests
- REST endpoints return expected responses for representative cases
- Identifier auto-assignment helper returns next ID without race conditions
- UI panel appears in sidebar in correct position
- Master pane lists records with correct columns and sort
- Detail pane renders all fields including references
- CRUD dialogs work end to end (create round-trips; edit persists; delete soft-deletes; restore reverses)
- File-watch refresh picks up external changes
- Sample CBM-redo Phase 1 records can be authored through the dialog without leaving the UI

Each criterion is testable in the v0.4 build, not in the schema-design conversation. Schema specs *list* the criteria; build planning translates them into test cases.

### 3.8 Open questions and deferred decisions

Anything the schema-design conversation did not settle and does not need to settle. Categorized:

- **For v0.4 build to settle.** Implementation-level questions (migration ordering, exact endpoint test fixtures, etc.) that depend on cross-schema visibility.
- **For CBM redo to surface.** Things that real use will answer better than design speculation (e.g., "should `domain.description` be plain text or markdown?" might fall here).
- **For v0.5+.** Deferred features explicitly captured as planning items (PI-NNN), with the PI identifier cited.

Each open question is one paragraph maximum, with a category tag.

### 3.9 Cross-references

Decisions cited by this spec (DEC-NNN), related schemas (other entries in `methodology-schema-specs/`), and external references (the evolved-methodology phase outline, the Phase 1 interview guide, prior simulator findings, etc.). One-line entries; the rest of the spec sources its substance from the linked documents rather than restating them.

---

## 4. Schema-design conversation cadence

Each per-entity schema-design conversation follows this cadence:

### 4.1 Pre-flight (before the first architectural question)

The conversation reads:

1. `crmbuilder/CLAUDE.md` — universal session-startup entry.
2. `PRDs/product/crmbuilder-v2/methodology-schema-workstream-plan.md` — workstream master plan.
3. This guide (`methodology-entity-schema-spec-guide.md`).
4. The per-entity kickoff prompt (`schema-design-kickoff-{entity_type}.md`).
5. All previously-completed schema specs in `methodology-schema-specs/` (so later conversations see the conventions established by earlier ones).
6. SES-011's session record (and subsequent schema-design conversations' session records) for context on what was already decided.
7. The relevant evolved-methodology documents for the entity type being designed:
   - For all: `evolved-methodology-phase-outline.md` (especially section 3, Phase 1)
   - For all: `phase-1-interview-guide.md` (where in the guide does this entity type get surfaced?)
   - For `process` specifically: also section 3, Phase 3 (where full process definitions land)
   - For `entity` specifically: line 62 of the Phase 1 guide (entity names surface but PRDs are not produced)

Pre-flight also runs the standard checks: API health at `http://127.0.0.1:8765/health`, v2 test suite (`uv run pytest tests/crmbuilder_v2/ -v`), `git pull --rebase origin main`.

### 4.2 Discussion structure

The conversation drives **one architectural question at a time** in plain text, matching SES-011's working style:

- Bold section headings acceptable; bullet-point overload avoided.
- Terse approvals ("yes", "confirm", "a", "1 good") sufficient; no re-summary.
- Propose document structures and outlines; user approves before drafting begins.
- Once outline is confirmed and section content is approved, execute the drafting end-to-end without per-step confirmation.

Architectural questions typically include:

- Identifier prefix and format (does the working assumption hold or change?)
- Field inventory — which fields does the entity type have in v0.4's thin shape?
- Required vs. optional fields and their defaults
- Relationships — direct FK, references, or hierarchy? what relationship-kind values?
- Status lifecycle — how many statuses, what transitions?
- API deviations — does this entity type need anything beyond the standard endpoint set?
- UI deviations — does the default layout fit, or does this entity need a different shape?

### 4.3 Drafting

After all architectural questions are settled, the schema spec is drafted in one pass per section 3's structure (`PRDs/product/crmbuilder-v2/methodology-schema-specs/{entity_type}.md`). The drafting phase reuses the planning-conversation language but adapts it into the spec format.

### 4.4 Governance recording (at conversation close, not during)

At the conversation's actual close, the conversation records:

- **Decisions.** Each architectural question's resolution becomes a DEC-NNN record, authored via direct API. Decisions reference the spec produced and any prior schemas they extend.
- **Planning items.** Anything explicitly deferred to v0.5+ becomes a PI-NNN record (or updates an existing PI if it was already tracked).
- **Session record.** The conversation closes with SES-NNN written through the v0.3 desktop New Session dialog, following the session-record-at-close pattern. `topics_covered` opens with the seed prompt verbatim; `artifacts_produced` lists the schema spec and any planning items; `in_flight_at_end` names the next schema-design conversation in the workstream (or, for the fourth conversation, the v0.4-build-planning conversation).

The session-record-at-close pattern matters because it prevents the SES-008 coverage gap pattern from recurring: if the record were written mid-conversation (e.g., as part of the spec draft), subsequent conversation turns would not be captured.

---

## 5. Governance per (b-α)

The (b-α) discipline applies to every schema-design conversation:

- **No build prompts.** Schema-design conversations produce design only. Build prompts come from the v0.4-build-planning conversation.
- **No storage architecture changes.** New entity types extend the storage layer additively (new tables, new endpoints, new access-layer methods); they do not modify existing entity types' shapes or behaviors. Reference vocabulary additions are extensions, not modifications.
- **No fundamental UI architecture changes.** New panels extend the existing pattern (ListDetailPanel-backed, sidebar-grouped); they do not introduce new top-level UI structures.

If a schema-design conversation surfaces a need for fundamental change (e.g., "this entity type needs a tab-bar instead of a sidebar entry"), the conversation flags it as an open question for v0.4 build planning rather than designing inline.

---

## 6. Cross-spec consistency requirements

Conventions that all four schemas share, validated at the consistency check before v0.4-build planning:

| Convention | Value |
|------------|-------|
| Identifier prefix style | 3–5 uppercase letters, no digits, no underscores |
| Identifier format | `{PREFIX}-NNN`, zero-padded to 3 digits |
| Status field name | `status` (not `state`, `lifecycle_status`, etc.) |
| Status values | lowercase `snake_case` |
| Default starter status | named explicitly in each spec; typically `candidate` for evolving methodology entities |
| Relationship-kind naming | `verb_phrase` style (e.g., `process_belongs_to_domain`, not `process_domain_membership`) |
| Field naming | `snake_case`, singular nouns for scalar fields, plural nouns for collection/JSON fields |
| Timestamp inheritance | Inherit base `created_at`, `updated_at`, `deleted_at` without redeclaring |
| Soft-delete behavior | Default (filtered from list endpoints, restorable via `/restore` endpoint) |
| Identifier auto-assignment | Default (server-side on POST omission, helper at `GET /{plural}/next-identifier`) |

A spec that deviates from any of these must explicitly call out the deviation and justify it in the relevant section.

---

## 7. Validation gates

Two gates apply before a schema spec is considered ready to feed v0.4-build planning:

### 7.1 Per-spec completeness

A schema spec passes the per-spec completeness gate when:

- All nine subsections of section 3 are present and substantively filled (no `TBD` or placeholder content)
- Section 3.7 (Acceptance criteria) has at least ten concrete, testable statements
- Section 3.8 (Open questions) has explicit category tags on every entry
- Section 3.9 (Cross-references) cites at least the workstream plan, this guide, the relevant evolved-methodology document(s), and any prior schemas this entity type relates to

Per-spec completeness is the schema-design conversation's responsibility; the conversation does not close until the spec passes.

### 7.2 Cross-spec consistency

After all four schema specs exist, before v0.4-build planning opens, the cross-spec consistency check verifies:

- No identifier prefix collisions
- All four specs use the conventions in section 6 (or explicitly justify deviations)
- Relationship-kind vocabulary additions across the four specs do not conflict (no two specs declaring the same `relationship_kind` with different semantics)
- Status-value naming is consistent across specs (a `candidate` status means the same thing in domain, entity, process, and crm_candidate)
- UI panel layouts (section 3.6) are either default or have rationale-justified deviations

Cross-spec consistency is the v0.4-build-planning conversation's first task. If inconsistencies surface, they're resolved by reopening the affected schemas (small revisions) before build planning proper begins.

---

## 8. Open methodology questions

Things this guide does not yet specify; expected to surface during the first schema-design conversation (domain) and get folded back into the guide for subsequent conversations.

- **Section 3.3 mechanism granularity.** When does a relationship warrant a direct FK versus a references edge? The guide gives general guidance ("cardinality settled", "many-to-many or with edge metadata") but the domain schema's design will surface the first concrete case.
- **Section 3.6 deviation precedent.** How heavy a deviation needs how much rationale? The first deviation in any of the four schemas sets the bar.
- **Spec-versioning policy.** If a schema spec needs to be revised after its conversation closes (e.g., the cross-spec consistency check surfaces an issue), is that a new version of the same spec (revision history grows) or a new conversation? Working assumption: revision in place with a change-log entry citing the source of the change; new conversation only if the revision is large enough to warrant its own architectural discussion.
- **Whether multiple thin schemas in v0.4 lead to a forced refactor in v0.5.** Each of the four entity types ships thin in v0.4 (Phase 1 only) and grows in v0.5+. If the growth turns out to require schema-level changes (e.g., entity needs a fields-collection added in v0.5), is that a migration story or a re-design? Working assumption: migration story; thin schemas are designed with future growth in mind.

---

*End of document.*

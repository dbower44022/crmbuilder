# Methodology Entity Schema Spec — `process` (v2 growth)

**Last Updated:** 05-25-26
**Status:** Draft v2.0 — schema-growth spec for the existing `process` entity, satisfying PI-005.
**Position in workstream:** Schema-growth spec that supersedes the v0.4 thin shape at v0.6+.
**Predecessor:** `process.md` v1.0 (the v0.4 thin schema produced by SES-014).
**Conditional dependencies:** **PI-003** (`persona` entity type) and **PI-004** (`field` and `requirement` entity types) must land before the new vocabulary kinds introduced here can be registered. The schema growth itself (the six new TEXT columns) is independent of those PIs and can ship first.
**Sibling specs:** `domain.md`, `entity.md`, `process.md` (the v0.4 predecessor this spec grows), `crm_candidate.md`, `engagement.md`, `persona.md`.

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 2.0 | 05-25-26 | Doug Bower / Claude | Schema-growth spec for the existing `process` entity. Adds six TEXT columns to host Phase 3 process-definition content (steps, triggers, outcomes, edge cases, frequency, duration); registers two new references-entity relationship kinds (`process_performed_by_persona`, `process_touches_field`) and anticipates a third (`requirement_realized_by_process`) declared on the requirement side; defers structured (non-text) forms of these fields to v0.7+; preserves every v0.4 field, classification, status posture, and existing relationship verbatim; defines the Alembic migration story; reframes section 3.6 UI to add collapsible Phase 3 sections to the detail pane without changing the master pane. Authored as a sibling document to `process.md` so the v0.4 thin-spec history remains an intact reference. |

---

## Change Log

**Version 2.0 (05-25-26):** Initial creation of the v2 growth spec. The v0.4 schema produced by SES-014 is preserved intact: identifier, name, purpose, classification, classification rationale, notes, domain FK, soft-delete timestamps, `process_hands_off_to_process` references — all carry forward with no behavioral change. Six new content fields are added via Alembic migration (`process_steps`, `process_triggers`, `process_outcomes`, `process_edge_cases`, `process_frequency`, `process_duration_estimate`), all TEXT and nullable, defaulted NULL on existing v0.4 records (no backfill). Two new references-entity relationship kinds are registered: `process_performed_by_persona` (process → persona, many-to-many) and `process_touches_field` (process → field, many-to-many). A third anticipated kind, `requirement_realized_by_process`, is declared on the requirement side (PI-004 design) and surfaces here as an inbound edge only — not a separately-registered process-side kind. The pre-existing v0.5 anticipation in `process.md` section 3.3.2 of `process_touches_entity` is honored: that kind is registered as part of this growth spec (this corrects the earlier deferral). Section 3.4 lifecycle remains unchanged (the existing four-value `process_classification` enum and one-way `unclassified` gate are preserved). Section 3.6 UI grows the detail pane with six new collapsible sections, one per new content field; the master pane is unchanged. Twelve testable acceptance criteria added. Open questions cover the v0.7+ structured-steps question, telemetry-vs-authored frequency/duration ambiguity, process-variants entity type, and step-as-first-class-record extraction.

---

## 1. Purpose and Position

This document specifies the v2 schema for the `process` entity — the schema-grown form that takes over at v0.6+ when the surrounding methodology entity types catch up enough that Phase 3 of the evolved methodology can produce its full Process Documents into v2's storage layer rather than into Word documents.

The v0.4 spec (`process.md` v1.0, SES-014) defined `process` as the thinnest shape that could host Phase 1's Prioritized Backbone: name, purpose, classification (mission_critical / supporting / deferred / unclassified), domain affiliation via direct FK, process-to-process handoffs via the references entity. That shape was correct for Phase 1, where processes are *named tokens* the consultant captures from Session 1 / Session 2 and arranges into a workability-checked Prioritized Backbone. The v0.4 spec was deliberately thin and deliberately growth-ready; PI-005 was authored at that conversation's close to track the growth this spec now delivers.

The growth target is the **evolved methodology's Phase 3 — Iteration Build and Deploy.** Phase 3 turns a Phase 1 Prioritized Backbone member into a fully-defined Process Document covering: the ordered steps the process executes; the actors (personas) who perform each step or the process overall; the entity-fields the process reads or writes; the triggers that initiate the process; the outcomes that mark success; the edge cases (error paths, retries, exceptions); the operational characteristics (how often it runs, how long it takes). The v0.4 schema can host *names* of these; it cannot host the *content*. v2 grows the schema to host the content.

The growth is **additive**, not redesign. Every v0.4 field, constraint, lifecycle rule, and relationship is preserved. The new columns are TEXT and nullable, default NULL, with no backfill required — v0.4 records continue to validate as legal v2 records, with their Phase 3 sections simply rendering empty in the UI. The migration is fully reversible. The position note at the top of this document is the only place the predecessor relationship is named; the rest of this spec reads as a standalone growth specification.

The conditional dependencies (PI-003 for `persona`, PI-004 for `field` and `requirement`) constrain the *relationships* added in section 3.3, not the *fields* added in section 3.2. The six new TEXT columns can ship as a standalone Alembic migration the moment v0.6 work opens; the new vocabulary kinds register when their target entity types exist. The spec is explicit about this split so the v0.6 build does not block on PI-003/PI-004 just to land the column growth.

This spec **supersedes** `process.md` v1.0 at v0.6+. The v0.4 thin spec remains in the repo for historical reference (and because design conversations may want to read the pre-growth shape), but new build prompts, test fixtures, and methodology documentation should treat this v2 spec as authoritative once the migration applies.

---

## 2. Summary

A `process` record in v2 (post-growth) represents one of the client's named business processes at any methodology completion level — from a Phase 1 token (name + classification + domain) up through a Phase 3 Process Document (all of Phase 1 plus steps, triggers, outcomes, edge cases, operational characteristics, performing personas, touched entity-fields, realized requirements). The schema accommodates both extremes and everything in between: an unclassified Session 1 capture (Phase 1 surface, nothing else) is as legal as a fully-elaborated Phase 3 record with six populated content sections and dozens of inbound and outbound references.

The growth adds **six new content fields** — `process_steps`, `process_triggers`, `process_outcomes`, `process_edge_cases`, `process_frequency`, `process_duration_estimate` — all TEXT, all nullable, all defaulting to NULL. The fields are plain text in v0.6+ to match the methodology's "evolve the schema to fit real authoring patterns" posture; structured representations (numbered-step records, frequency-as-cron, etc.) are deferred to v0.7+ planning items because authoring them prematurely risks shipping the wrong structure.

The growth adds **two new outgoing relationship kinds** in v2's references entity: `process_performed_by_persona` (process → persona, many-to-many; resolves which actors perform the process) and `process_touches_field` (process → field, many-to-many; resolves which entity-fields the process reads or writes). It also registers `process_touches_entity` (process → entity, many-to-many; was anticipated in `process.md` section 3.3.2 as a v0.5+ kind), promoting that relationship from anticipation to live registration. The corresponding requirement-realization relationship is registered on the requirement side as `requirement_realized_by_process`; the process detail pane surfaces it as an inbound edge.

The lifecycle is **unchanged**: the same four-value `process_classification` enum (`unclassified | mission_critical | supporting | deferred`) governs engagement-scope position; soft-delete handles rejection; no status field is introduced. The methodology's classification mechanic is orthogonal to the Phase 1 / Phase 3 completion-level distinction the growth fields capture.

The UI grows additively: the master pane is unchanged (column-set decision deferred to v0.7+ work), and the detail pane gains six new collapsible sections — Steps, Triggers, Outcomes, Edge Cases, Frequency, Duration — each collapsed by default when its underlying field is NULL or empty, expanded when it has content. The detail pane also surfaces three new reference rendering slots, one per new vocabulary kind. The CRUD dialog grows to include the six new fields as multi-line text editors below the existing Phase 1 fields.

---

## 3. Schema Specification

### 3.1 Identity

**Unchanged from v0.4.** The identity block carries forward verbatim from `process.md` section 3.1.

| Field | Value |
|-------|-------|
| Entity type name (storage) | `process` |
| Display name (singular) | Process |
| Display name (plural) | Processes |
| Identifier prefix | `PROC` |
| Identifier format | `PROC-NNN`, zero-padded to 3 digits |
| Identifier auto-assignment | Server-side on POST omission; helper at `GET /processes/next-identifier` |

No change to prefix, format, auto-assignment behavior, or endpoint surface. Records authored under v0.4 continue to use the same identifier values; no renumbering, no migration of identifiers.

### 3.2 Fields

The v0.4 field inventory (section 3.2 of `process.md`) is preserved in full. This section documents all fields — v0.4-preserved and v2-added — together so the reader does not have to cross-reference. Carried-from-v0.4 entries are marked **[v0.4]**; new-in-v2 entries are marked **[v2 new]**.

Field naming continues to follow the parent-prefix convention established by `domain.md` (DEC-046). All new TEXT columns are prefixed `process_`.

#### 3.2.1 Identity fields

| Field name | Type | Required | Default | Validation | Description | Status |
|------------|------|----------|---------|------------|-------------|--------|
| `process_identifier` | TEXT | yes | server-assigned | `^PROC-\d{3}$`, unique | The methodology-entity identifier. | [v0.4] |
| `process_name` | TEXT | yes | — | non-empty trimmed; case-insensitive unique within the engagement | Process name in the client's language. | [v0.4] |

#### 3.2.2 Content fields

| Field name | Type | Required | Default | Validation | Description | Status |
|------------|------|----------|---------|------------|-------------|--------|
| `process_purpose` | TEXT | yes | — | non-empty trimmed | One-sentence statement of what the process does. Phase 1 content. | [v0.4] |
| `process_classification_rationale` | TEXT | no | — | — | Reasoning behind the current classification value. Phase 1 / between-session content. | [v0.4] |
| `process_notes` | TEXT | no | — | — | Internal consultant scratchpad. Not part of any client-facing render. | [v0.4] |
| `process_steps` | TEXT | no | NULL | — | The ordered steps the process executes. Plain text in v0.6+; numbered or bulleted list authored at the consultant's discretion. Phase 3 content. Example: "1. Mentor coordinator receives application notification. 2. Coordinator reviews application against eligibility checklist. 3. If eligible, coordinator schedules screening interview. 4. If ineligible, coordinator sends decline email." Structured-form representation (per-step actor / entity / outcome columns, or first-class `step` records) deferred to v0.7+ under the open question in section 3.8. | [v2 new] |
| `process_triggers` | TEXT | no | NULL | — | What initiates the process. Plain text in v0.6+. Phase 3 content. Examples: "Mentor application submitted via web form"; "Calendar trigger at 9 AM each Monday"; "Mentor coordinator manual initiation"; "Inbound email matching `mentors-apply@*` pattern". A process may have multiple triggers; the consultant lists them in the same field separated by newlines or bullets. Multi-trigger structured representation deferred to v0.7+. | [v2 new] |
| `process_outcomes` | TEXT | no | NULL | — | What success looks like — the state changes, records created, communications sent, or downstream-handed-off artifacts produced when the process completes successfully. Plain text in v0.6+. Phase 3 content. Examples: "Mentor application screening record created with eligibility verdict, screening interview scheduled in coordinator's calendar, applicant receives confirmation email"; "Funds deposited in operating account; donor receipt generated; donor record updated with cumulative-giving total." | [v2 new] |
| `process_edge_cases` | TEXT | no | NULL | — | Known exceptions, error paths, retry semantics, manual-intervention cases. Plain text in v0.6+. Phase 3 content. Examples: "Duplicate application detected by email match — coordinator notified, original application linked"; "Email delivery failure on decline notification — retry 3x with exponential backoff, then flag for manual outreach"; "Applicant withdraws mid-screening — record marked withdrawn, screening interview cancelled, no decline email sent." | [v2 new] |
| `process_frequency` | TEXT | no | NULL | — | How often the process runs. Plain text in v0.6+. Phase 3 content. Examples: "On demand per applicant (averages 8-12 per month)"; "Quarterly (March / June / September / December)"; "Continuously throughout business hours"; "Once per engagement". May contain seasonality, volume, or operating-window context the consultant judges relevant. Telemetry-vs-authored ambiguity flagged in section 3.8. | [v2 new] |
| `process_duration_estimate` | TEXT | no | NULL | — | Typical wall-clock duration of one process instance from trigger to completion. Plain text in v0.6+. Phase 3 content. Distinguishes between active human time and total elapsed time when both matter. Examples: "10 minutes manual review plus 24-72 hours waiting for applicant scheduling response"; "~5 minutes per record, 30-50 records per quarterly batch"; "Effectively instant (sub-second; serverless trigger)." | [v2 new] |

**Why plain TEXT, not JSON or structured columns, for the six new fields.** The v0.6+ shape mirrors the v0.4 posture for `process_purpose` and `process_classification_rationale`: the methodology hasn't yet produced enough real-use signal to know whether structured representations would help or constrain. Phase 3 work in the CBM redo and any subsequent engagements will surface the patterns; v0.7+ planning items track the structured-form question per category. Authoring structure prematurely (per-step actor columns, frequency-as-cron, duration-as-ISO-8601-period) risks shipping the wrong structure and forcing a painful migration. Plain TEXT is the additive, growth-ready choice.

**No required transitions among the new fields.** A record may have `process_steps` populated and `process_outcomes` NULL, or any other combination. The methodology does not impose an authoring order; the consultant fills sections as Phase 3 work produces the content. The UI respects this by collapsing empty sections rather than gating one on another.

#### 3.2.3 Classification fields

| Field name | Type | Required | Default | Validation | Description | Status |
|------------|------|----------|---------|------------|-------------|--------|
| `process_classification` | TEXT | yes | `unclassified` | enum: `unclassified` \| `mission_critical` \| `supporting` \| `deferred`; valid transitions per section 3.4 | Methodology priority classification. | [v0.4] |

**No change.** The four-value enum, one-way `unclassified` gate, and free movement among the three classified values per `process.md` section 3.4.2 are preserved verbatim. The classification mechanic is orthogonal to the Phase 1 / Phase 3 completion-level distinction the new content fields capture; a `mission_critical` process may have all six Phase 3 sections empty (it's known important but not yet defined in detail), and a `supporting` process may have all six populated (it's not on the critical path but the consultant chose to define it fully anyway).

#### 3.2.4 Relationship fields

| Field name | Type | Required | Default | Validation | Description | Status |
|------------|------|----------|---------|------------|-------------|--------|
| `process_domain_identifier` | TEXT | yes | — | matches `^DOM-\d{3}$`; refers to a live `domain` record | Direct FK to the affiliated domain (many-to-one). | [v0.4] |

**No new FK columns.** All new v2 relationships (persona, field, entity, requirement) are many-to-many and live in the references entity, not as FK columns on the `processes` table. This is consistent with the v0.4 design choice (DEC-058) and with `entity.md`'s posture for `entity_scopes_to_domain`.

#### 3.2.5 Timestamp fields

**Unchanged from v0.4.** `process_created_at`, `process_updated_at`, `process_deleted_at` carry forward with their inherited base behavior.

### 3.3 Relationships

The v0.4 relationships (one direct-FK affiliation, one references-entity edge) are preserved. v2 adds three new references-entity outgoing kinds and anticipates one inbound kind declared by the requirement spec.

#### 3.3.1 Outgoing relationships — preserved from v0.4

**`process_belongs_to_domain` — direct FK, conceptual relationship name only.** Unchanged from `process.md` section 3.3.1. The mechanism is the `process_domain_identifier` column declared in section 3.2.4; no references-table involvement, no vocabulary registration, no change in behavior.

**`process_hands_off_to_process` — references-entity edge, directional.** Unchanged from `process.md` section 3.3.1. The vocabulary kind is already registered in `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` (see lines 220–221 — added in the v0.4 build per DEC-058). The migration story for this kind is complete; v2 introduces no further changes.

#### 3.3.2 Outgoing relationships — new in v2

This section declares the three new kinds. The single inbound-side kind (`requirement_realized_by_process`) is declared on the requirement side per `crmbuilder-v2/PRDs/.../methodology-schema-specs/requirement.md` (PI-004 design) and listed in section 3.3.3 as an anticipated inbound edge.

| relationship_kind | source | target | mechanism | cardinality | semantics |
|-------------------|--------|--------|-----------|-------------|-----------|
| `process_performed_by_persona` | `process` | `persona` | references-entity edge | many-to-many | Persona performs the process (or some portion of it). A process may be performed by zero, one, or many personas; a persona may perform zero, one, or many processes. |
| `process_touches_field` | `process` | `field` | references-entity edge | many-to-many | The process reads, creates, updates, or deletes the value of this entity-field during its execution. Fine-grained read/write distinction deferred to v0.7+ (open question in section 3.8). |
| `process_touches_entity` | `process` | `entity` | references-entity edge | many-to-many | The process reads, creates, updates, or deletes records of this entity type during its execution. Coarser than `process_touches_field` (entity-level, not field-level); both are registered because consultants may know the entity-level touch before drilling down to specific fields. Promoted from v0.4-anticipated to v2-registered. |

**Mechanism rationale — references entity, not FK columns.**

- All three relationships are many-to-many, so a multi-value FK column on the `processes` table would either need a side table (effectively the references table without the vocabulary-governance benefits) or a denormalized comma-separated column (not v2 convention).
- The references entity is the established v2 mechanism for many-to-many cross-entity-type edges (DEC-006).
- Existing references-section UI widgets render the new edges with no widget rewrite.
- Reverse queries ("which processes touch this field?", "which processes does this persona perform?") are trivial via the existing references-table reverse lookup.

**Mechanical additions per CLAUDE.md line 48 — three triads:**

1. **Register kinds in `REFERENCE_RELATIONSHIPS`** in `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`:
   - `process_performed_by_persona`
   - `process_touches_field`
   - `process_touches_entity`

2. **Extend `_kinds_for_pair`** so the following return the new kinds:
   - `(process, persona)` → adds `process_performed_by_persona` (alongside the existing generic kinds and any others applicable)
   - `(process, field)` → adds `process_touches_field`
   - `(process, entity)` → adds `process_touches_entity`

3. **Alembic migration** extending the `refs.relationship_kind` CHECK constraint to include all three new values. The migration may be a single Alembic revision authoring all three, or three sequential revisions if the v0.6 build's slice plan prefers to land them one PI at a time. Either form is correct.

**Conditional dependency.** Registering `process_performed_by_persona` requires `persona` to be a valid value in `ENTITY_TYPES` (PI-003 lands this), and registering `process_touches_field` requires `field` to be a valid value in `ENTITY_TYPES` (PI-004 lands this). If v0.6 work opens the column-growth migration before PI-003 or PI-004 land, the vocabulary registration is split off into a follow-up migration whose CHECK constraint update applies after the target entity types are registered. The column-growth migration itself does not depend on either PI.

**Cardinality, validation, and lifecycle semantics for the three new kinds:**

- Many-to-many in both directions; zero edges permitted (a process may have no persona / field / entity references; this is the default state at Phase 1 capture).
- Source must be a live `process` record; target must be a live record of the named target type. Existing references-table validation handles this.
- Duplicate `(source_id, target_id, relationship_kind)` tuples are rejected by the references-table uniqueness constraint.
- Soft-deleting a process does not cascade-delete its outbound references of any of the three new kinds. The references persist; show-deleted toggles surface them.
- Soft-deleting the target (a persona, field, or entity) leaves the reference in place pointing to a now-soft-deleted target; the UI surfaces this with a warning on the process detail pane and offers the consultant the option to re-target or remove the reference. This mirrors the existing posture for `process_belongs_to_domain` per `process.md` section 3.5.4.

**Self-loops are not meaningful for the three new kinds** (a process performing itself, touching itself as a field, touching itself as an entity all make no methodological sense), but the references table does not actively prevent them. The UI's reference-create dialog filters by `(source_type, target_type)` so self-loops are unreachable through the normal authoring path; direct API calls could create them but would not break anything.

#### 3.3.3 Inbound relationships (anticipated; declared by source-side specs)

Two anticipated v0.6+ inbound kinds. Both are declared on the source-side spec; this section is informational so the `process` detail pane's inbound-references rendering is forward-aware.

| relationship_kind | source | target | declared by | semantics |
|-------------------|--------|--------|-------------|-----------|
| `requirement_realized_by_process` | `requirement` | `process` | `requirement.md` (PI-004 design) | A requirement is realized (delivered, satisfied) by this process. Many-to-many: a requirement may be realized by multiple processes acting together; a process may realize multiple requirements. **Registered on the requirement side, not the process side**, per the deliberate single-side registration discipline (see paragraph below). |
| (future) `step_belongs_to_process` | `step` | `process` | (v0.7+ if PI for step-as-first-class-record lands) | A step (one ordered sub-action) belongs to a process. Anticipated only; no current PI authored. |

**Why `requirement_realized_by_process` is registered on the requirement side, not here.** A single semantic relationship between two entity types is registered as one `relationship_kind`, not two parallel kinds for the two directions. Registering both would create vocabulary redundancy (consultants would have to know which kind to use for which direction), validation ambiguity (two valid kinds for the same `(requirement, process)` pair), and rendering duplication (the references-section widget would need to deduplicate). The convention is: each cross-entity-type relationship has exactly one registered kind; the kind's name encodes the direction; reverse queries surface the edge from the non-registered side via the existing reverse-lookup mechanism.

`requirement_realized_by_process` reads naturally as source=requirement, target=process. The process detail pane surfaces the inbound edge as "Realizes requirement: REQ-NNN ..." via the existing references-section widget; no special process-side registration is needed.

#### 3.3.4 Cross-spec relationship-kind naming convention — adopted, not established

This spec continues to follow the `{source}_{verb}_{target}` convention established by `domain.md` section 3.3.3 (DEC-048). All three new outgoing kinds conform: `process_performed_by_persona`, `process_touches_field`, `process_touches_entity`. The convention is not re-decided here.

#### 3.3.5 Hierarchy

Unchanged from v0.4. The v0.4 spec deferred sub-process hierarchy to v0.5+ under PI-005; v2's plain-text `process_steps` field implements the within-process step content without introducing structural hierarchy, leaving the question of step-as-first-class-record entity type to v0.7+ (open question in section 3.8). The `processes` table remains hierarchy-unaware; no `process_parent_identifier` self-FK in v2.

### 3.4 Lifecycle

**Unchanged from v0.4.** This section explicitly states no change so the reader does not have to compare against `process.md` to confirm.

The four-value `process_classification` enum (`unclassified` | `mission_critical` | `supporting` | `deferred`), the one-way `unclassified` gate, the free movement among the three classified values, and the rejection-via-soft-delete posture per `process.md` sections 3.4.1–3.4.5 carry forward verbatim. No new lifecycle field is introduced; no transitions are amended; no archived status is added.

The Phase 1 / Phase 3 completion-level distinction the new content fields capture is **not** modeled as a lifecycle field in v2. The motivation:

- A definitional-completeness field (working name `process_definition_level` or similar) was anticipated in `process.md` section 3.4.1 as v0.5+ work. v2 considered introducing it but rejects the field for the same reason `process.md` rejected `entity`'s status pattern: definitional completeness is a derived signal, not an asserted state. "Has all six Phase 3 sections populated" is computable from the data itself (NOT NULL counts); asserting a separate field would create staleness risk (the field says "complete" but the sections are empty, or vice versa).
- If the methodology surfaces a need to distinguish "fully defined" from "in-progress defining" in a way that cannot be derived from the data, v0.7+ may introduce the field then. This is captured as an open question in section 3.8.

Soft-delete semantics per `process.md` section 3.4.5 carry forward with no change. The new references (`process_performed_by_persona`, `process_touches_field`, `process_touches_entity`) follow the same non-cascading soft-delete behavior as existing references.

### 3.5 API Surface

#### 3.5.1 Endpoints

**Unchanged endpoint set from v0.4.** The eight standard endpoints listed in `process.md` section 3.5.1 carry forward verbatim: GET list, GET single, POST, PUT, PATCH, DELETE, POST restore, GET next-identifier. The endpoint *bodies* admit the six new fields (PATCH-able individually; included in PUT full-record bodies; returned in GET responses), but the endpoint *set* is the same.

#### 3.5.2 PATCH semantics for new fields

Each of the six new content fields is independently PATCH-able. A PATCH body containing only `{"process_steps": "1. Receive application. 2. Review for eligibility."}` updates only `process_steps`, leaving every other field (including the other five new content fields) untouched. PATCHing a field to JSON `null` clears it (sets the column to NULL); PATCHing a field to the empty string `""` sets it to the empty string (which the UI treats the same as NULL for collapse-when-empty purposes, but the storage layer preserves the distinction).

This independence matters for Phase 3 authoring: a consultant may populate `process_steps` in one session and `process_edge_cases` in a later session without needing to re-author the rest of the record.

#### 3.5.3 Reference-creation API surface for new kinds

The decomposed-reference posture from `process.md` section 3.5.5 carries forward. Attaching a `process_performed_by_persona`, `process_touches_field`, or `process_touches_entity` reference is a separate `POST /references` call with the appropriate `relationship_kind`, source, and target. No inline-attach convenience endpoints are introduced; the New and Edit dialogs and the detail pane's "Add reference" affordance hide the multi-call sequence behind single user gestures.

#### 3.5.4 Validation behaviors carried forward

- Classification-transition validation per `process.md` section 3.5.3: unchanged.
- Domain-affiliation validation per `process.md` section 3.5.4: unchanged.
- The 4xx error envelope per `process.md` section 3.5.6: unchanged.

#### 3.5.5 Identifier auto-assignment

Unchanged from v0.4. The `GET /processes/next-identifier` helper continues to behave per DEC-043.

### 3.6 UI Considerations

The v0.4 UI shape (sidebar position, master pane columns, detail pane layout, CRUD dialog shape) is preserved as the baseline. v2 grows the detail pane and CRUD dialog to host the new content; the master pane is intentionally unchanged.

#### 3.6.1 Sidebar

Unchanged from v0.4. `Processes` remains at position #3 in the Methodology group (after Domains and Entities, before CRM Candidates).

#### 3.6.2 Master pane

**Unchanged from v0.4.** Columns: Identifier, Name, Classification, Updated. Default sort by Identifier ascending. No new columns in v2.

Master-pane column growth is deferred to v0.7+ because:

- No single new v2 field is a high-value "scan at a glance" candidate the way `entity_name` or `process_classification` are. Steps / triggers / outcomes are inherently multi-line; rendering them in a column would either truncate awkwardly or break the row-density convention.
- A "completion level" column (counting populated new fields, rendering a 0/6 to 6/6 indicator) is an appealing future addition but is itself a UI design question whose value isn't validated against real-use signal yet.
- Persona / field / entity / requirement counts (rendered as e.g., "3 personas, 12 fields") would require batched references-table joins of the kind PI-009 anticipates for the Entities-panel Domains column; the same architectural work would unblock both.

A new planning item for v0.7+ should track master-pane growth for Processes; this spec does not author one to keep the v0.6 build's scope tight.

#### 3.6.3 Detail pane

The v0.4 detail pane layout per `process.md` section 3.6.3 is preserved as the upper portion. The lower portion grows with six new collapsible sections plus the references-section's new inbound/outbound rendering.

**Full detail pane layout in v2:**

1. `process_identifier` — read-only label *(v0.4)*
2. `process_name` — single-line text editor *(v0.4)*
3. `process_domain_identifier` — combo box backed by live domains *(v0.4)*
4. `process_purpose` — multi-line text editor *(v0.4)*
5. `process_classification` — combo box *(v0.4)*
6. `process_classification_rationale` — multi-line text editor with placeholder text varying by classification *(v0.4)*
7. **Phase 3 sections — collapsible group.** A new sub-container holding six collapsible sub-sections, each headed by the field's display label. Default collapse-state per sub-section is: collapsed if the underlying column is NULL or empty string; expanded if the column has any non-whitespace content. The collapse-state is rendered, not persisted (no user-collapse memory across sessions in v0.6+). The group as a whole carries a header label "Phase 3 — Detailed Process Definition" so the consultant sees the methodological framing at a glance.
   - **Steps** — multi-line text editor bound to `process_steps`, placeholder "Numbered or bulleted list of process steps in execution order"
   - **Triggers** — multi-line text editor bound to `process_triggers`, placeholder "What initiates this process"
   - **Outcomes** — multi-line text editor bound to `process_outcomes`, placeholder "What success looks like — state changes, records created, communications sent"
   - **Edge Cases** — multi-line text editor bound to `process_edge_cases`, placeholder "Known exceptions, error paths, retry semantics"
   - **Frequency** — multi-line text editor bound to `process_frequency`, placeholder "How often this process runs"
   - **Duration** — multi-line text editor bound to `process_duration_estimate`, placeholder "Typical wall-clock duration"
8. `process_notes` — multi-line text editor under "Internal notes" collapsible header, collapsed by default *(v0.4)*
9. `ReferencesSection` widget — grown to render the new kinds in addition to the v0.4 kinds. Sub-section breakdown:
   - **Hands off to:** outgoing `process_hands_off_to_process` edges *(v0.4)*
   - **Receives from:** inbound `process_hands_off_to_process` edges *(v0.4)*
   - **Performed by:** outgoing `process_performed_by_persona` edges *(v2 new)*
   - **Touches fields:** outgoing `process_touches_field` edges *(v2 new)*
   - **Touches entities:** outgoing `process_touches_entity` edges *(v2 new)*
   - **Realizes requirements:** inbound `requirement_realized_by_process` edges (rendered from the inbound side; the kind is registered on the requirement spec, not here) *(v2 new, inbound)*
   - **Other inbound references:** any future inbound kinds not yet registered

**Optional architectural recommendation — bundled Phase 3 widget.** Rather than wiring the six new collapsible sub-sections directly into the detail pane, the v0.6 build may introduce a `ProcessExecutionContextSection` (or similarly-named) composite widget that internally manages the six sub-sections plus the group header. This bundles the Phase 3 content into a single inserted widget the parent detail pane composes alongside the Phase 1 fields, simplifying the detail-pane layout code and making future additions (a seventh content field; collapse-state persistence) localized changes. The exact widget shape is a v0.6+ build decision; the spec does not mandate either approach.

#### 3.6.4 Create dialog

The v0.4 create dialog per `process.md` section 3.6.4 grows to include the six new content fields as multi-line text editors. Placement: below `process_classification_rationale`, above `process_notes`, in the same Phase-3-sections sub-container shape as the detail pane.

All six new fields are optional at create time; the user may save a process record with only the v0.4-required fields filled (name, purpose, classification, domain), or may pre-populate any subset of the six Phase 3 fields when the content is already in hand at create time. The "create-then-edit" pattern (create with v0.4 fields, populate Phase 3 fields later via the detail-pane edit affordance) remains fully supported.

The open question on create-dialog handoff flow per `process.md` section 3.6.4 carries forward unchanged. Whether new-kind references (persona, field, entity, requirement) get a create-with-attach multi-select in the dialog or a create-then-attach detail-pane flow is the same UI-layer question; the v0.6 build decides.

#### 3.6.5 Edit dialog

Same shape as the create dialog with `process_identifier` displayed as read-only. Classification-transition validation per `process.md` section 3.6.5 continues to apply.

#### 3.6.6 Delete dialog

Unchanged from v0.4 per `process.md` section 3.6.6. Edge-text confirmation; new-kind references (persona, field, entity, requirement) on the soft-deleted process persist per section 3.3.2's non-cascading semantics.

### 3.7 Acceptance Criteria

The following 13 statements define what "v2 schema growth is correctly implemented" looks like. Each is concrete and testable. The v0.6+ build planning translates these into specific test cases.

1. **Forward migration applies cleanly.** The Alembic migration adding the six new TEXT columns to the `processes` table runs without error against a database containing any number of v0.4 process records. Each existing row receives NULL for all six new columns. Schema introspection confirms the columns are nullable and default NULL.

2. **Backward migration applies cleanly.** Running the migration's `down()` removes the six new columns from the `processes` table without error. Records authored under v2 with values in the new columns lose those values on downgrade (this is expected behavior; downgrade is a recovery operation, not a routine reversal). Records authored under v0.4 are completely unaffected by the downgrade.

3. **Existing v0.4 records survive intact.** After the forward migration, every v0.4 record is reachable via GET, PATCH-able on its v0.4 fields without specifying any v2 field, and renders in the UI master pane and detail pane with no visible regressions. The new Phase-3-sections group in the detail pane appears with all six sub-sections collapsed-empty.

4. **New fields are PATCH-able individually.** A PATCH body containing only one of the six new fields updates that field and no others. PATCH to JSON `null` clears the field to NULL; PATCH to `""` sets it to empty string; PATCH to non-empty text sets it. The other five new fields and all v0.4 fields are untouched.

5. **POST and PUT round-trip new fields.** Creating a process with any subset of the six new fields populated persists those values; subsequent GET returns them unchanged. PUT (full replace) including the new fields persists the new state; omitting them from a PUT body clears them (per PUT semantics).

6. **`process_performed_by_persona` registered, constrained, and round-tripping.** `REFERENCE_RELATIONSHIPS` includes the kind. `_kinds_for_pair((process, persona))` returns a frozenset including `process_performed_by_persona`. POST `/references` with `source_type=process, source_id=PROC-NNN, target_type=persona, target_id=PER-NNN, relationship_kind=process_performed_by_persona` creates the row. POST with an unsupported kind for the `(process, persona)` pair returns 422. The Alembic migration extends the `refs.relationship_kind` CHECK constraint; direct DB insert with an unknown kind is rejected. Fetching the process surfaces the reference under "Performed by:" in the detail pane; fetching the persona surfaces the same reference inbound (subject to PI-003's persona spec defining its inbound-references rendering).

7. **`process_touches_field` registered, constrained, and round-tripping.** Same shape as criterion 6 with `(process, field)` and `PER → FLD`. Verifies the kind is registered, the migration extends the CHECK, and the reference round-trips end-to-end.

8. **`process_touches_entity` registered, constrained, and round-tripping.** Same shape as criterion 6 with `(process, entity)` and `PER → ENT`. Promotes the v0.4-anticipated relationship (per `process.md` section 3.3.2) to a live registration.

9. **Anticipated inbound `requirement_realized_by_process` query works.** Given a registered `requirement_realized_by_process` kind (registered on the requirement side per PI-004) and a row of `(source_type=requirement, source_id=REQ-NNN, target_type=process, target_id=PROC-NNN, relationship_kind=requirement_realized_by_process)`, fetching `PROC-NNN` surfaces the reference under "Realizes requirements:" in the detail pane via the existing inbound-references rendering mechanism. The process spec adds no source-side registration; the process panel just consumes inbound edges.

10. **Master pane unchanged.** The Processes panel renders the same four columns (Identifier, Name, Classification, Updated) with the same sort order as before the migration. No new columns appear in v2; the previously-deferred Domain column is still not present.

11. **Detail pane renders new sections collapsed when empty.** For a v0.4-authored record (all six new columns NULL after migration), the detail pane displays the Phase-3-sections group with the group header visible and all six sub-sections collapsed (only the sub-section headers visible). For a record with `process_steps` populated and the other five NULL, only the Steps sub-section is expanded; the other five are collapsed. Empty-string columns are treated the same as NULL for collapse purposes.

12. **CRUD dialog round-trip on new fields.** Creating a process through the dialog with all six new fields populated persists all six. Editing an existing process and changing any subset of new fields persists the changes. Editing and leaving new fields untouched preserves their existing values. Server-side validation errors (none specific to the new fields in v0.6+; all are TEXT nullable) surface inline if added in future versions.

13. **Lifecycle behavior unchanged.** The classification transition rules from `process.md` section 3.4.2 continue to apply unchanged. Soft-delete and restore behave exactly as in v0.4. The new outbound references and the inbound `requirement_realized_by_process` follow non-cascading semantics on soft-delete of either endpoint.

### 3.8 Open Questions and Deferred Decisions

Categorized per the spec guide section 3.8 convention. Each entry is one paragraph with an explicit category tag.

#### 3.8.1 For v0.6+ build to settle

**[v0.6+ build] Bundled Phase-3-sections widget shape.** Section 3.6.3 recommends an optional `ProcessExecutionContextSection` composite widget bundling the six new collapsible sub-sections. Whether the v0.6 build adopts the bundled-widget approach or wires the six sub-sections directly into the detail pane is a UI-layer decision the build conversation settles. Either approach satisfies the acceptance criteria.

**[v0.6+ build] Migration sequencing relative to PI-003 and PI-004.** The column-growth migration is independent of PI-003 (persona) and PI-004 (field, requirement); it can ship first. The vocabulary-registration migration for the three new relationship kinds depends on the target entity types being registered in `ENTITY_TYPES`. The v0.6 build decides whether to ship a single migration (after PI-003 and PI-004 land) or split into column-growth (first) + vocabulary-registration (after deps land) sub-migrations.

**[v0.6+ build] Reference-attach flow in the Create dialog for new kinds.** The v0.4 open question on create-dialog handoff flow (create-then-attach vs create-with-attach) extends to the three new kinds. The v0.6 build settles a single pattern that applies to all four (handoff, persona, field, entity) consistently rather than mixing patterns within one dialog.

#### 3.8.2 For CBM redo to surface

**[CBM redo] `process_frequency` and `process_duration_estimate` source-of-truth.** Both fields are authored plain text in v0.6+. The CBM redo will surface whether these values are consultant-authored ahead of time (the methodology produces them as part of Phase 3 work) or are derived from CRM-engine telemetry after deployment (the CRM tracks process invocations and reports actuals). If telemetry is the better source, both fields may be deprecated in v0.7+ in favor of a telemetry-fed surface — or the fields may stay as the consultant's pre-deployment estimate with telemetry alongside as a separate v0.7+ surface. The decision deliberately waits on real-use signal.

**[CBM redo] Markdown rendering for the six new fields.** All six are plain TEXT in v0.6+. The CBM redo will surface whether steps, outcomes, edge cases, etc. benefit from emphasis, bullet lists, or inline links beyond what plain text supports. If so, a v0.7+ migration introduces markdown rendering. Same posture as v0.4's deferral on `process_purpose` and `process_classification_rationale` markdown.

**[CBM redo] Read/write decomposition on `process_touches_field`.** v0.6+ ships one coarse relationship kind. The CBM redo will surface whether read vs. write distinction matters in practice — does the consultant routinely need to know which processes write a field and which only read it? If so, v0.7+ decomposes into `process_reads_field`, `process_creates_field`, `process_updates_field`, `process_deletes_field` (or similar). The same question applies to `process_touches_entity`.

**[CBM redo] Step-level persona attribution.** Consultants may want to know not just "which personas perform this process" (the v0.6+ `process_performed_by_persona` semantics) but "which persona performs step N of this process." Resolving this is hard without step-as-first-class-record extraction (see v0.7+ open question below); the CBM redo will surface whether the coarse process-level attribution is sufficient or whether the step-level demand is real.

**[CBM redo] Phase-3-sections collapse-state persistence.** v0.6+ renders collapse state from data shape (NULL → collapsed) without persisting user collapse choices across sessions. The CBM redo will surface whether consultants want their per-record collapse choices remembered (e.g., a consultant working on edge cases for a week wants the Edge Cases sub-section to stay expanded across desktop restarts).

#### 3.8.3 For v0.7+

**[v0.7+] PI for structured `process_steps`.** v0.6+ ships steps as plain text. v0.7+ may grow steps into a structured form: a numbered list with per-step actor (persona reference), entity touched (entity / field reference), expected outcome, and optional duration. Two sub-questions: (a) does the structured form live as JSON in the `process_steps` column (column type changes from TEXT to JSON with a migration), or (b) do steps become first-class `step` records in their own table with a `step_belongs_to_process` references-entity edge? Option (b) is structurally analogous to PI-010's entity-variants pattern. The CBM redo and v0.6+ use surface the choice.

**[v0.7+] PI for process variants.** Consultants may surface that "Mentor application — paper intake" and "Mentor application — digital intake" are two variants of the same logical process — same outcomes and personas, different triggers and steps. The v0.6+ schema models these as two independent process records. v0.7+ may introduce a `process_variant_of_process` self-referential relationship or a separate `process_variant` entity, structurally analogous to PI-010's entity-variant question. New PI to be authored at v0.7+ open if the CBM redo confirms the demand.

**[v0.7+] PI for step as first-class record.** Distinct from but related to the structured-`process_steps` question above. If steps become first-class records (`step` entity type with `STEP-NNN` identifiers), they get their own panel, their own CRUD, their own references (`step_performed_by_persona`, `step_touches_field`, etc.), and `process_steps` either retires or becomes a derived rendering. Larger scope than the JSON-on-column option; v0.7+ open if the CBM redo's Phase 3 authoring patterns warrant it.

**[v0.7+] `process_definition_level` lifecycle field.** Section 3.4 declines to introduce this field in v2, deriving completeness from the data instead. If v0.7+ methodology work surfaces a need to assert completion level orthogonally to data shape (e.g., "this is reviewed and signed off as complete" vs. "all sections populated but not yet reviewed"), a `process_definition_level` enum field becomes a candidate. PI to be authored at v0.7+ open if the demand surfaces.

**[v0.7+] Master-pane growth for Processes.** Section 3.6.2 explicitly defers master-pane growth. v0.7+ candidates include: a completion-level indicator column (0/6 to 6/6); a Domain column (paired with PI-007 short codes); persona / field / entity / requirement count columns (requires batched-join architectural work paired with PI-009 for the Entities panel). PI to be authored at v0.7+ open if the demand surfaces.

### 3.9 Cross-References

#### 3.9.1 Planning items cited by this spec

- **PI-003** — `persona` entity type. Conditional dependency for `process_performed_by_persona` kind registration.
- **PI-004** — additional methodology entity types (`field`, `requirement`, `manual_config`, `test_spec`). Conditional dependency for `process_touches_field` and `process_touches_entity` (insofar as `entity` already exists since v0.4, the entity dep is satisfied) and for the inbound `requirement_realized_by_process` kind registered on the requirement side.
- **PI-005** — full process schema growth beyond Phase 1 thin shape. This spec is the deliverable for PI-005.

#### 3.9.2 Decisions cited by this spec

- **DEC-006** — Universal references table as the cross-entity-type edge store. Direct architectural foundation for the three new references-entity edges in section 3.3.2.
- **DEC-039** — Minimum entity inventory and multi-tenancy posture. Establishes the methodology entity types `process` is part of; this spec extends `process` within that posture without disturbing it.
- **DEC-046** — Parent-prefix field-naming convention. Continues to apply to the six new field names; all use `process_` prefix.
- **DEC-048** — `{source}_{verb}_{target}` relationship-kind naming convention. The three new outgoing kinds conform.
- **DEC-057** — `process_classification` four-value enum and transition map. Preserved unchanged in section 3.4.
- **DEC-058** — `process` relationship architecture (direct FK for domain, references-entity edge for process-to-process handoffs, defer process-to-entity). v2 preserves the first two and promotes the deferred `process_touches_entity` to live registration.

#### 3.9.3 External references

- `crmbuilder/CLAUDE.md` — universal session-startup entry; documents the `REFERENCE_RELATIONSHIPS` / `_kinds_for_pair` / Alembic-migration triad section 3.3.2 follows.
- `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md` — schema spec template this document follows. The growth-spec pattern (sibling document supersedes thin predecessor) is a new convention this spec exercises; future growth specs (`entity` growth for PI-010, `domain` growth if PI-007 short codes warrant it) may follow the same shape.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/process.md` — predecessor thin spec, v1.0. Preserved in the repo; this v2 spec supersedes it at v0.6+ for authoritative reference.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/persona.md` — sibling spec defining the `persona` entity type (`PER` prefix). Target of the new `process_performed_by_persona` references-entity edge.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/entity.md` — sibling spec defining the `entity` entity type (`ENT` prefix). Target of the promoted `process_touches_entity` references-entity edge.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/` (forthcoming `field.md`, `requirement.md` under PI-004) — sibling specs that will define `field` (`FLD` prefix) and `requirement` (`REQ` prefix). Target of `process_touches_field`; source of the inbound `requirement_realized_by_process` registered on the requirement side.
- `PRDs/process/CRM-Builder-Document-Production-Process.docx` — current 13-phase Document Production Process. Phase 4 (Domain Overview + Process Definition) is the historical analogue of the evolved methodology's Phase 3; the historical process produces full Process Documents into Word, which v2's grown schema replaces with structured-database authoring.
- (Evolved methodology Phase 3 / Iteration Build and Deploy reference, if/when authored under PRDs/process/research/evolved-methodology/) — the methodology-side specification of what Phase 3 produces. The six new content fields map directly to the Phase 3 Process Document section headers.

## 4. Migration from v0.4

This section is specific to the growth-spec shape (not present in `process.md` v1.0 which had no predecessor to migrate from). It documents the migration sequence, reversibility, backfill posture, and v0.4-record handling.

### 4.1 Alembic migration sequence

The growth is delivered as **one or two Alembic migrations**, the v0.6 build's choice:

- **Option A — single migration.** One Alembic revision adds the six new TEXT columns to the `processes` table AND extends the `refs.relationship_kind` CHECK constraint to include the three new kinds. The build sequences this after PI-003 and PI-004 land so `persona`, `field`, and `requirement` are valid `ENTITY_TYPES` values when the references-side work runs.

- **Option B — split migration.** Two Alembic revisions: the first adds the six new TEXT columns to `processes` (independent of PI-003/PI-004; can land immediately at v0.6 open); the second extends the references CHECK constraint and registers the three new kinds in vocab.py (lands after PI-003 and PI-004 have created `persona` and `field` and `requirement` records).

Both options produce the same end state. The choice is a build-sequencing preference, not a spec-mandated structure.

### 4.2 Forward migration mechanics

For each of the six new columns, the migration runs an `ALTER TABLE processes ADD COLUMN process_<name> TEXT` (no DEFAULT clause; SQLite columns added without DEFAULT default to NULL). Existing rows receive NULL for the new column at the moment of ALTER. No backfill is performed.

The references-side portion (whether in Option A or Option B) does two things:

1. Updates `REFERENCE_RELATIONSHIPS` in `vocab.py` to include `process_performed_by_persona`, `process_touches_field`, and `process_touches_entity`.
2. Updates `_kinds_for_pair` so the three new `(source_type, target_type)` pairs return the new kinds (in addition to the generic `is_about` / `references` and any others applicable).
3. Issues an Alembic migration extending the `refs.relationship_kind` CHECK constraint to include the new values, following the existing SQLite CHECK-extension recipe (rebuild the constraint via the standard SQLAlchemy-on-SQLite pattern, since SQLite does not support `ALTER TABLE ... ALTER CONSTRAINT`).

### 4.3 Reversibility

Both options' `down()` methods drop the new state:

- Drop the six new columns from `processes` via `ALTER TABLE processes DROP COLUMN process_<name>`. SQLite's column-drop support is recent (3.35+); the v2 storage layer targets a SQLite version that supports it. (If the targeted SQLite version does not support direct column drops, the standard table-rebuild pattern is used.)
- Restore the `refs.relationship_kind` CHECK constraint to its pre-migration form (omitting the three new kinds). Any references rows holding the new kinds must be deleted before the down-migration runs, or the CHECK rebuild fails. The down-migration includes a guarded `DELETE FROM refs WHERE relationship_kind IN (...)` step that runs before the CHECK rebuild; the guard surfaces a warning if any rows are deleted so the operator is aware data was lost.
- Remove the three new kinds from `REFERENCE_RELATIONSHIPS` and `_kinds_for_pair` (reverting the vocab.py changes).

Down-migration is intended for recovery, not routine reversal. A v2-authored record with values in the new columns loses those values on downgrade; this is expected and documented.

### 4.4 v0.4-record handling

Records authored under v0.4 (before this migration) are fully preserved. After the forward migration:

- Every v0.4 record reaches v2 schema state by acquiring NULL values for all six new columns. No data is rewritten; no identifier is changed.
- GET responses for v0.4 records include the six new keys with `null` values. Clients that consume the API and were written against the v0.4 response shape see additional keys but no removed keys; they continue to function unchanged.
- The UI master pane renders v0.4 records with no visible difference.
- The UI detail pane renders v0.4 records with the Phase-3-sections group present but all six sub-sections collapsed-empty.

A v0.4 record may transition to v2 content level by PATCHing any subset of the new fields with values. No special "promote to v2" endpoint or status flip is required; the column values themselves are the content state. This is consistent with the section 3.4 rejection of `process_definition_level` as an asserted field.

### 4.5 No backfill required

No automated backfill is performed. The six new columns hold Phase 3 content that the methodology produces through consultant + client work; there is no source of truth elsewhere from which the column values could be auto-populated. Phase 3 work in the CBM redo (or any subsequent engagement) populates the columns as it happens, on a per-record basis.

If a prior engagement's Word-document Process Documents could be programmatically parsed into the six new columns (e.g., section-header pattern matching), a one-off backfill script may be authored for that engagement. This is engagement-specific tooling, not part of the v2 schema-growth deliverable; if it becomes a pattern, a future PI captures it.

---

*End of document.*

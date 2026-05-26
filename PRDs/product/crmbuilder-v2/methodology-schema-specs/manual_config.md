# Methodology Entity Schema Spec — `manual_config`

**Last Updated:** 05-25-26 12:00
**Status:** Draft v1.0 — produced as part of PI-004 resolution
**Position in PI-004:** Sibling of `field`, `persona`, `requirement`, `test_spec` — the v0.5+ methodology entity types extending the v0.4 baseline (`domain`, `entity`, `process`, `crm_candidate`, `engagement`)
**Predecessor specs:** `domain.md`, `entity.md`, `process.md`, `crm_candidate.md`, `engagement.md`
**Successor specs:** `field.md`, `requirement.md`, `test_spec.md` (PI-004 siblings)

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-25-26 12:00 | Doug Bower / Claude | Initial draft. Produced as part of PI-004 (additional methodology entity types for v0.5+). Defines `manual_config` as the v2 methodology entity type that captures discrete pieces of CRM configuration that cannot be applied automatically via the deploy pipeline and must be configured by a human operator in the CRM admin UI. Inherits conventions established by `domain.md` and applied across `entity.md`, `process.md`, `crm_candidate.md`, `engagement.md` (parent-prefix field naming, `{source}_{verb}_{target}` relationship-kind naming, soft-3-letter prefix posture). Introduces an explicit deviation from the standard three-status lifecycle by adding a `completed` terminal status, justified by the operator-completion event being a meaningful verification artifact distinct from client-scope confirmation. |

---

## Change Log

**Version 1.0 (05-25-26 12:00):** Initial creation. Defines eight substantive fields (`manual_config_identifier`, `manual_config_name`, `manual_config_description`, `manual_config_category`, `manual_config_instructions`, `manual_config_notes`, `manual_config_status`, `manual_config_completed_at`, `manual_config_completed_by`) plus inherited timestamps; four-status lifecycle (`candidate` / `confirmed` / `deferred` / `completed`) with explicit deviation rationale for the additional `completed` terminal status; four outbound relationship kinds via the references entity (`manual_config_scopes_to_domain`, `manual_config_touches_entity`, `manual_config_touches_field`, `manual_config_realizes_requirement`); standard endpoint set with status-transition validation that additionally requires `manual_config_completed_at` and `manual_config_completed_by` populated on any transition into `completed`. Establishes `MCF` as the identifier prefix under the soft-3-letter posture, with explicit justification for the unusual three-letter mapping of a two-word entity name. Defers free-text "other"-category sub-classification and automatic linkage to deploy-side NOT_SUPPORTED emissions to v0.6+ planning items. Acceptance criteria captured as 16 testable statements, including category-enum and four-status-lifecycle validation, the completed-status field-population enforcement rule, vocabulary registration for the four outbound relationship kinds, and a sample acceptance using approximately six CBM manual configs.

---

## 1. Purpose and Position

This document specifies the `manual_config` entity type for v2's storage layer. It is part of the PI-004 group of v0.5+ methodology entity types that extend the v0.4 baseline produced by the methodology-entity-schema-design workstream (`domain`, `entity`, `process`, `crm_candidate`, `engagement`). PI-004 enumerates four such types — `field`, `requirement`, `manual_config`, `test_spec` — each of which addresses a methodology need that Phase 1 does not produce but later phases (Phase 3 iteration, verification, stakeholder review) require.

`manual_config` exists to give the methodology a first-class record of the configuration the human operator must perform on the live CRM after the deploy pipeline has done what it can. CRMBuilder v1's deploy engine already surfaces these items at deployment time — under the `MANUAL CONFIGURATION REQUIRED` block emitted by `RunWorker._run_full()` when a deploy step returns `NOT_SUPPORTED`. That mechanism is reactive and ephemeral: items appear only when a YAML triggers them, the log scrolls past, and the long-lived companion artifact (a `MANUAL-CONFIG.md` file the operator hand-maintains in the client repository) holds the durable record. v2's methodology layer needs the same content as durable, queryable records that can be cross-referenced from requirements, surfaced in stakeholder reviews, traced into verification specs, and reported on across an engagement.

The mapping between deploy-time NOT_SUPPORTED emissions and `manual_config` records is logical, not automatic in v0.5+. A `manual_config` record represents *a methodology decision* that operator action is required, authored at the time the team realizes such action will be needed (typically during Phase 3 process or entity work, or during YAML authoring in the evolved methodology's equivalent of Phase 9). The deploy pipeline's NOT_SUPPORTED emissions are *runtime evidence* that the operator action is in fact required and not happenable automatically. v0.5+ keeps these decoupled: the methodology team authors `manual_config` records based on knowledge of the platform constraints documented in `CLAUDE.md` (saved views, duplicate checks, workflows, deferred-options enum fields, role/field-level permissions, dynamic logic with role conditions, etc.); the deploy engine independently surfaces NOT_SUPPORTED items at runtime; automatic linkage between the two streams is tracked as a v0.6+ planning item.

The four sibling PI-004 entity types differ in which methodology question they answer:

- **`field`** answers "what attributes does an entity have, with what types and validation?"
- **`requirement`** answers "what business need does the engagement need to satisfy?"
- **`manual_config`** answers "what platform-bounded gaps need operator action to close?" (this spec)
- **`test_spec`** answers "how do we verify the implementation satisfies a requirement?"

Each of these is target-referenceable by the others (a requirement may be realized by both a process and a manual_config; a test_spec may verify a manual_config; a field may be the subject of a manual_config). This spec declares the outbound relationship kinds the `manual_config` source-side requires; the inverse-side declarations belong to those entities' specs.

---

## 2. Summary

A `manual_config` record in v2 represents one discrete piece of CRM configuration that the deploy pipeline cannot apply automatically and a human operator must perform in the CRM admin UI. Concrete examples include: a saved view whose `clientDefs` JSON requires disk-level editing and cache rebuild; a workflow gated on the EspoCRM Advanced Pack with no REST write path; a duplicate-check rule that has no public REST endpoint; an enum field declared with `optionsDeferred: true` because its option list comes from a master source (zip codes, industry codes) the YAML doesn't carry; a role with field-level permission grants that has no v1.0 declarative shape; dynamic logic with role conditions that requires Dynamic Handler JS or Layout Sets + Teams. Each record captures the operator-facing instructions for performing the configuration, a consultant-facing notes scratchpad, a category classifying the kind of manual action required, and a lifecycle status tracking the record from candidate-proposal through client-confirmation, optional deferral, and ultimately operator-completion in the live CRM.

The schema in v0.5 is the thinnest shape that supports the methodology's three durable uses for these records: (a) **stakeholder review** — the consultant can produce a per-engagement list of manual configurations the client should expect their operator to perform; (b) **requirement traceability** — a requirement can be realized by a manual_config alongside or instead of a process, giving a complete realization picture in the methodology; (c) **verification accounting** — a verification spec can ask the operator to confirm a manual_config has been performed, and the `completed` status acts as the durable answer. The schema deliberately omits automatic linkage to deploy-side NOT_SUPPORTED emissions, free-text follow-up on the "other" category, and a strong-typed completed-by reference to a user or persona entity — each is a v0.6+ candidate awaiting CBM-redo signal.

---

## 3. Schema Specification

### 3.1 Identity

| Field | Value |
|-------|-------|
| Entity type name (storage) | `manual_config` |
| Display name (singular) | Manual Config |
| Display name (plural) | Manual Configs |
| Identifier prefix | `MCF` |
| Identifier format | `MCF-NNN`, zero-padded to 3 digits (e.g., `MCF-001`, `MCF-042`) |
| Identifier auto-assignment | Server-side on POST omission; helper at `GET /manual-configs/next-identifier` |

**Identifier-prefix justification.** `MCF` is three letters and adheres to the soft-3-letter prefix posture established in `domain.md` section 3.1. The choice deserves explicit justification because the entity name `manual_config` is two words with an underscore — three reasonable abbreviation candidates exist:

- **`MAN`** — first three letters of "manual". Rejected because it is generic ("manual" alone could mean documentation, a user manual, a manual-override, a manual test) and provides no signal that the identifier refers to configuration.
- **`MAC`** — first letter of "manual" plus first two of "config". Rejected because it strongly suggests Apple's macOS / Macintosh product line, creating a cross-domain name collision in any reader's mental model.
- **`MCF`** — first letter of "manual" plus first two letters of "config" (M-anual C-on-F-ig). Chosen because it disambiguates against both rejected alternatives, has no collision with existing v2 prefixes (DEC, SES, RSK, PI, TOP, REF, CHR, STA, DOM, ENT, PROC, CRM, WS, CONV, RB, WT, COP, DEP, CM, PER, FLD, REQ), and reads unambiguously as "Manual ConFig" once the convention is documented. The slight mnemonic awkwardness (it is not a straight prefix-of-the-name extraction) is the smaller cost than either of the alternatives' confusion costs.

The identifier-asymmetry helper endpoint per DEC-043 ships alongside the standard endpoint set.

### 3.2 Fields

Field naming follows the parent-prefix convention established by `domain.md` (DEC-046): all non-identifier, non-timestamp fields are prefixed with the parent entity name (`manual_config_`). All fields including identifier and timestamps adopt the prefix for full convention consistency.

#### 3.2.1 Identity fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `manual_config_identifier` | TEXT | yes | server-assigned | `^MCF-\d{3}$`, unique | The methodology-entity identifier in `MCF-NNN` format. Server-assigned when omitted from POST body. |
| `manual_config_name` | TEXT | yes | — | non-empty trimmed; case-insensitive unique within the engagement | Short human-readable name for the manual config (e.g., "Saved view: Mentors needing dues invoice"; "Workflow: Auto-assign client on engagement create"; "Deferred options: Industry subsector master list"; "Duplicate check: Account by name + zip"). |

#### 3.2.2 Content fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `manual_config_description` | TEXT | yes | — | non-empty trimmed | Brief description of what the manual config is and why it exists (the platform constraint or methodology rationale). Plain text in v0.5; markdown support deferred to CBM-redo signal. Example: "Industry subsector enum needs roughly 50 options sourced from the BLS NAICS master list. Operator pastes the list into the field's options panel after deploy." |
| `manual_config_instructions` | TEXT | yes | — | non-empty trimmed | Operator-facing step-by-step instructions for performing the configuration in the CRM admin UI. Authored at the level of detail a competent operator who is not the methodology consultant can follow. Plain text in v0.5 (no markdown / fenced code blocks); whether SSH command snippets and structural markdown are needed is a CBM-redo signal open question (section 3.8). Example: "1. Admin → Entity Manager → Account → Fields → industrySubsector. 2. In the Options panel, paste the list from PRD section 6.2.1 (one option per line). 3. Save. 4. Clear Cache." |
| `manual_config_notes` | TEXT | no | — | — | Internal consultant scratchpad. Not part of any client-facing render. Used to capture rationale, between-session reasoning, links to platform-constraint documentation, push-back trails (e.g., "Considered Path B: declarative role permission schema. Rejected because v1.0 has no REST write path."). Plain text in v0.5. |

#### 3.2.3 Classification fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `manual_config_category` | TEXT | yes | — | enum: `saved_view` \| `duplicate_check` \| `workflow` \| `deferred_options_enum` \| `role_permission` \| `dynamic_logic` \| `other` | Classifies the kind of manual configuration. Vocabulary aligned with the historical deploy-pipeline NOT_SUPPORTED categories documented in `CLAUDE.md` ("Three features have no public REST API write path" plus the v1.1 schema's deferred-options pattern and the role/dynamic-logic items deferred from v1.0). `other` is a generic bucket in v0.5; free-text sub-classification deferred to v0.6+ (section 3.8.3). |
| `manual_config_status` | TEXT | yes | `candidate` | enum: `candidate` \| `confirmed` \| `deferred` \| `completed`; valid transitions per section 3.4 | Lifecycle status. **Deviation from the standard three-status pattern** — see section 3.4 for the four-status rationale. |

**Category vocabulary justification.** The seven category values map onto the platform-constraint categories surfaced in CRMBuilder v1's history:

- `saved_view` — requires disk-level edits to `custom/Espo/Custom/Resources/metadata/clientDefs/{Entity}.json` plus cache rebuild (`CLAUDE.md` "Three features have no public REST API write path").
- `duplicate_check` — needs reimplementation against the EntityManager endpoint; no current REST write path (same reference).
- `workflow` — needs reimplementation against the Workflow entity CRUD API, gated on Advanced Pack detection (same reference).
- `deferred_options_enum` — the `optionsDeferred: true` flag on enum/multiEnum fields per the v1.1 schema, where the option list comes from a master source the YAML doesn't carry (commit `fb50b95`).
- `role_permission` — role definitions with field-level permission grants, deferred from v1.0 (Category 6 of the YAML schema v1.1 series, deferred to v1.2).
- `dynamic_logic` — Section 12.5 role-aware visibility (per Audit feature `feat-audit.md` §9), which has no Dynamic Logic shape in EspoCRM 9.x and requires Dynamic Handler JS or Layout Sets + Teams configured manually.
- `other` — generic bucket for cases the above seven do not cover (e.g., post-deploy data seeding, third-party integration configuration, license activation). v0.5+ accepts the generic bucket; v0.6+ may introduce a `manual_config_category_other` free-text sub-classification field, tracked as a planning item.

#### 3.2.4 Relationship fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `manual_config_completed_at` | DATETIME | conditionally required | null | ISO 8601 UTC when set; required when `manual_config_status = completed` | Timestamp recording when the operator performed the configuration in the live CRM. Null in all non-`completed` statuses. Required (server-side enforced) at any transition into `completed` per section 3.5.3. Not a relationship-to-another-entity field; included here per the section 3.2 timestamp-vs-content distinction because it represents a specific lifecycle event rather than a generic update. |
| `manual_config_completed_by` | TEXT | conditionally required | null | non-empty trimmed when set; required when `manual_config_status = completed` | Free-text identifier of the operator who performed the configuration. Examples: "doug@dougbower.com", "CBM administrator (handover Jan 2026)". Free text in v0.5; v0.6+ may upgrade to a FK to a `user` or `persona` entity once those exist (section 3.8.3). |

No outgoing FK columns to other methodology entities in v0.5. The four outbound relationship kinds (scopes_to_domain, touches_entity, touches_field, realizes_requirement) are captured via the references entity (see section 3.3.1) rather than table columns. This matches `entity.md`'s posture for `entity_scopes_to_domain` and keeps the `manual_configs` table small.

#### 3.2.5 Timestamp fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `manual_config_created_at` | DATETIME | yes | server-set on insert | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `manual_config_updated_at` | DATETIME | yes | server-set on insert and on each update | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `manual_config_deleted_at` | DATETIME | no | null until soft-delete | ISO 8601 UTC when set | Inherited base behavior. Set on DELETE; cleared on POST `/restore`. |

**No storage-level length caps.** Text fields are unconstrained at the storage layer in v0.5. The UI provides soft guidance via placeholder text. Pathological-input handling deferred to CBM-redo signal; mirrors `domain` and `entity` postures.

### 3.3 Relationships

#### 3.3.1 Outgoing relationships

`manual_config` declares four outgoing relationship kinds in v0.5, all via the references entity:

| relationship_kind | source | target | mechanism | cardinality | semantics |
|-------------------|--------|--------|-----------|-------------|-----------|
| `manual_config_scopes_to_domain` | `manual_config` | `domain` | references-entity edge | many-to-many | A manual config is relevant to one or more engagement domains. Mirrors the `entity_scopes_to_domain` shape. Zero-affiliation permitted. |
| `manual_config_touches_entity` | `manual_config` | `entity` | references-entity edge | many-to-many | A manual config concerns one or more methodology entities (e.g., a saved view on Contact; a duplicate check on Account). |
| `manual_config_touches_field` | `manual_config` | `field` | references-entity edge | many-to-many | A manual config concerns one or more specific fields (e.g., a deferred-options enum on `industrySubsector`). Anticipates `field.md` per PI-004; the relationship-kind value is registered when the `field` entity type ships and may register no-op until then. |
| `manual_config_realizes_requirement` | `manual_config` | `requirement` | references-entity edge | many-to-many | A manual config realizes (helps satisfy) one or more requirements. The inverse of the `process_realizes_requirement` working pattern; a requirement may be realized by a mix of processes and manual configs. Anticipates `requirement.md` per PI-004. |

The mechanism for all four is the references entity at v2's `refs` table, governed by the existing `RELATIONSHIP_RULES` infrastructure (DEC-006). The choice over table-side multi-value FK columns is the same as `entity.md` section 3.3.1: references discipline keeps the entity-table schema small, supports the same edge-creation/lookup semantics already used for governance and other methodology entities, and makes inverse queries trivial through the existing reverse-edge query.

**Mechanical additions per CLAUDE.md line 48:**

1. All four kinds added to `REFERENCE_RELATIONSHIPS` in `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`.
2. `_kinds_for_pair` extended for the four `(manual_config, *)` pairs to return the corresponding singleton sets:
   - `(manual_config, domain) → {manual_config_scopes_to_domain}`
   - `(manual_config, entity) → {manual_config_touches_entity}`
   - `(manual_config, field) → {manual_config_touches_field}`
   - `(manual_config, requirement) → {manual_config_realizes_requirement}`
3. Alembic migration extending the `refs.relationship_kind` CHECK constraint to include the four new values.
4. The two PI-004 dependencies (`field`, `requirement`) must land before or alongside the corresponding `_kinds_for_pair` entries; if `manual_config` ships before its siblings, the `(manual_config, field)` and `(manual_config, requirement)` pair-registrations are deferred until those types exist (PI-004 build planning sequences this).

**Cardinality and validation:**

- All four kinds are many-to-many. No upper bound on either side.
- Zero-affiliation permitted for all four. A manual_config can exist with no scoping, no entity touch, no field touch, no requirement realization — the consultant may author the record before its connections are settled.
- Source must be a live manual_config record; targets must be live records of the appropriate type. (Existing access-layer rules.)
- Duplicate `(source_id, target_id, relationship_kind)` tuples are rejected by the references-table uniqueness constraint.

**Lifecycle semantics:**

- Soft-deleting a manual_config does not cascade-delete its outbound references; the references persist and remain visible via the show-deleted UI toggle on either side. Matches v2's existing references-table behavior.
- Same for soft-deleting any target.
- Restoring either endpoint restores its relationship rows in place.

#### 3.3.2 Inbound relationships (anticipated; declared by source-side specs)

`manual_config` is the anticipated target of one inbound relationship kind:

| relationship_kind | source | target | semantics |
|-------------------|--------|--------|-----------|
| `test_spec_verifies_manual_config` (working name; declared by `test_spec.md`) | `test_spec` | `manual_config` | A test spec verifies that a manual config has been performed correctly in the live CRM. The methodology's verification artifact for the operator-action stream. v0.5+ if `test_spec` ships in the same release; otherwise registered when `test_spec.md` lands. |

The formal vocabulary registration belongs to the source-side spec (`test_spec.md`). This subsection exists for forward awareness; the `manual_config` panel's `ReferencesSection` widget will render inbound references once they exist.

#### 3.3.3 Cross-spec relationship-kind naming convention — adopted, not established

This spec adopts the `{source}_{verb}_{target}` relationship-kind naming convention established by `domain.md` section 3.3.3 (DEC-048) and applied across `entity.md` (`entity_scopes_to_domain`) and the rest of the v0.4 workstream. The four vocabulary entries this spec registers all conform to the pattern: source entity first (`manual_config`), verb phrase (`scopes_to`, `touches`, `realizes`), target entity. The convention is not re-decided here; it carries forward from the predecessor conversations.

#### 3.3.4 Hierarchy

`manual_config` does not use the self-referential parent-child hierarchy pattern in v0.5. There is no precedent in v1's deploy-time NOT_SUPPORTED model for parent/child relationships among manual configurations, and no Phase 3 methodology signal requesting one. If real-engagement experience surfaces a need (e.g., a parent role-permission rollup containing per-field child grants), the v0.6+ schema migration adds a `manual_config_parent_identifier` self-FK following the existing `topic.parent_topic` pattern.

### 3.4 Lifecycle

#### 3.4.1 Status values

| Status value | Description | Valid predecessors | Valid successors |
|--------------|-------------|--------------------|------------------|
| `candidate` | CRM Builder has proposed; awaiting client verification. **Default starter status.** | (none — starter) | `confirmed`, `deferred` |
| `confirmed` | Client has verified this manual config is needed; not yet performed in the CRM. | `candidate`, `deferred` | `deferred`, `completed` |
| `deferred` | Client has acknowledged this manual config but it is out of current engagement scope. | `candidate`, `confirmed` | `confirmed` |
| `completed` | Operator has performed the configuration in the live CRM. **Terminal status** — only escapable via soft-delete-and-restore-and-redo. | `confirmed` | (none — terminal) |

#### 3.4.2 Deviation rationale — four-status lifecycle vs. the cross-spec three-status default

This is the **only material deviation** of this spec from the cross-spec defaults established by `domain.md` and adopted across the v0.4 workstream. All other v0.4 methodology entities use the three-status `candidate` / `confirmed` / `deferred` lifecycle with rejection-via-soft-delete. `manual_config` adds a fourth value, `completed`, as a terminal status reachable only from `confirmed`.

The rationale: operator-completion of a manual configuration is a meaningful event in the methodology lifecycle that is distinct from client-scope confirmation. Without the fourth status, the methodology would have to express "operator has done it" via one of three alternatives, all of which are worse than a status:

- **A timestamp-only encoding** — set `manual_config_completed_at` on a still-`confirmed` record, treat null/non-null as the completion signal. Rejected because it obscures the verification story: a query "show me all manual configs not yet completed for this engagement" becomes a status-AND-timestamp clause rather than a single status filter, which is friction every time the question is asked (which is often — every stakeholder review, every verification pass, every operator handover).
- **A separate `verified` entity** — model completion as an independent record (e.g., a `manual_config_completion` row keyed by manual_config_identifier with a completed_at and completed_by). Rejected because it adds an entity type for a 1:1 relationship that already lives naturally on the manual_config record; it inflates the schema for no expressive gain and breaks the symmetry with how other lifecycle events get tracked.
- **An external system of record** — track completion in an Excel sheet or a per-engagement checklist outside v2. Rejected because it splits the methodology from the implementation, making cross-cutting queries (e.g., "show me the verification status across all engagements") impossible without out-of-band data wrangling.

The four-status lifecycle keeps verification cohesive: one status field, one set of transitions, one query shape. The cost is the documented deviation from the cross-spec default, which this section captures explicitly per the spec guide section 6 closing-paragraph rule that documented deviations are acceptable when well-justified.

#### 3.4.3 Transition semantics

The base pattern from `domain.md` (the one-way propose-verify gate: no regression to `candidate` from `confirmed` or `deferred`) is preserved. The additional transition is `confirmed → completed`, gated by the field-population requirement of section 3.5.3. The `completed` status is terminal — no successor states — because once the operator has performed the configuration in the live CRM, reversing the methodology's record of it would create an audit gap. If the operator subsequently un-does the configuration (e.g., a CRM redeploy wipes it), the right action is to soft-delete the `completed` record and author a new `manual_config` record reflecting the new state; this preserves the historical trail of what was true when.

Movement between `confirmed` and `deferred` in either direction is permitted to support mid-engagement scope changes, matching `domain` and `entity` patterns.

The full transition map is:

- `candidate → confirmed` — client verifies the manual config is needed.
- `candidate → deferred` — client verifies the manual config is real but out of scope.
- `confirmed → deferred` — previously-in-scope manual config moved out of scope.
- `confirmed → completed` — operator performed the configuration in the live CRM. `manual_config_completed_at` and `manual_config_completed_by` must be populated in the same write per section 3.5.3.
- `deferred → confirmed` — previously-deferred manual config pulled back into scope.

All other transitions return HTTP 422.

#### 3.4.4 Rejection via soft-delete

When the client rejects a CRM-Builder-proposed manual config candidate ("no, that's not actually a configuration we need"), the rejection is handled by soft-delete rather than a `rejected` status value. `DELETE /manual-configs/{manual_config_identifier}` sets `manual_config_deleted_at`; the record persists for audit and history, surfaces under the `?include_deleted=true` toggle, and is restorable via POST `/restore`. Matches the cross-spec principle established in `domain.md` section 3.4.3 and adopted across the v0.4 workstream: **status values track engagement-scope lifecycle; soft-delete tracks existence-in-the-record.**

#### 3.4.5 No `archived` status

`archived` is not introduced in v0.5. Soft-delete combined with the "show deleted" toggle already covers the "retained for record, not in active scope" use case. The terminal `completed` status fills the closest adjacent role (record kept active, configuration done) and is preferable to `archived` because it carries the operator-action semantics. Mirrors `domain.md` section 3.4.4.

#### 3.4.6 Soft-delete semantics

Soft-delete inherits v2's standard behavior:

- DELETE sets `manual_config_deleted_at` to the current ISO 8601 UTC timestamp.
- Soft-deleted records do not appear in `GET /manual-configs` by default.
- `GET /manual-configs?include_deleted=true` returns soft-deleted records alongside live ones.
- POST `/manual-configs/{manual_config_identifier}/restore` clears `manual_config_deleted_at` and reappears the record in the default list.
- Restore on a record that is not soft-deleted returns HTTP 422.

Outbound references on a soft-deleted manual_config are NOT cascade-deleted. They persist in the references table; show-deleted toggles on either side surface them.

### 3.5 API Surface

#### 3.5.1 Endpoints

| Method | Path | Body | Notes |
|--------|------|------|-------|
| GET | `/manual-configs` | — | List endpoint. Returns active records by default. Supports `?include_deleted=true` to include soft-deleted records. |
| GET | `/manual-configs/{manual_config_identifier}` | — | Single fetch by identifier. Returns 404 if not found. |
| POST | `/manual-configs` | full record minus `manual_config_identifier` (server-assigned) | Create. Returns 201 with the assigned identifier in the response body. Server-side validation per section 3.2 and 3.5.3 applied. |
| PUT | `/manual-configs/{manual_config_identifier}` | full record | Full replace. `manual_config_identifier` in body must match the path; mismatch returns 422. |
| PATCH | `/manual-configs/{manual_config_identifier}` | partial record | Partial update. Status-transition validation and completed-field-population validation applied (see 3.5.3). |
| DELETE | `/manual-configs/{manual_config_identifier}` | — | Soft-delete; sets `manual_config_deleted_at`. Idempotent. |
| POST | `/manual-configs/{manual_config_identifier}/restore` | — | Clears `manual_config_deleted_at`. Returns 422 if the record is not soft-deleted. |
| GET | `/manual-configs/next-identifier` | — | Returns `{"next": "MCF-NNN"}` for the next available identifier. Per DEC-043. |

**Path note.** The URL plural uses a hyphen (`manual-configs`) per common REST convention for multi-word resource names. The storage entity-type name keeps its underscore (`manual_config`) per the snake_case convention in section 3.1.

**No deviations from the cross-spec default endpoint set.** No bulk operations, no webhooks, no `/mark-completed` convenience endpoint (the convenience is in the UI; the API stays decomposed via PATCH).

#### 3.5.2 Identifier auto-assignment

`manual_config_identifier` is server-assigned on POST when omitted from the request body, via the standard SAVEPOINT-retry helper described in `CLAUDE.md`. The `GET /manual-configs/next-identifier` helper exposes the same logic for clients that want to know the assigned identifier before POSTing. Per DEC-043 / PI-002, supplying an explicit identifier is also supported.

#### 3.5.3 Status-transition and completed-field validation

Status transitions are validated server-side at the access layer per section 3.4.3. PATCH or PUT requests that specify a `manual_config_status` value that is not a valid successor of the current value return HTTP 422 with:

```
{
  "error": "invalid_status_transition",
  "from": "<current status>",
  "to": "<requested status>"
}
```

**Additional rule unique to this spec — completed-field-population enforcement.** Any transition that results in `manual_config_status = completed` requires `manual_config_completed_at` and `manual_config_completed_by` to be populated in the same write. A request that sets `manual_config_status` to `completed` while leaving either field null (or omitting it from a PATCH whose target record has it null) returns HTTP 422 with:

```
{
  "error": "completed_status_requires_completion_fields",
  "missing": ["<field name>", ...]
}
```

Conversely, setting `manual_config_completed_at` or `manual_config_completed_by` on a record whose status is not `completed` is permitted but discouraged (the UI does not expose the affordance); the access layer accepts the values without applying the status check.

The default-`candidate` rule applies on POST: if `manual_config_status` is omitted, the server assigns `candidate`. POST with `manual_config_status` explicitly set to `completed` is permitted (e.g., bulk-importing already-performed manual configs from a prior engagement's records), provided the two completion fields are populated in the same body.

#### 3.5.4 Decomposed reference handling

Outbound references (`manual_config_scopes_to_domain`, `manual_config_touches_entity`, `manual_config_touches_field`, `manual_config_realizes_requirement`) are NOT inlined into the manual_config create or update bodies. To attach a reference, the client makes a separate `POST /references` with the standard envelope. Matches `entity.md` section 3.5.4 and v2's references-first discipline (DEC-006).

The New dialog and detail-pane "Add reference" affordance hide the multi-call sequence behind UI gestures, but the API stays decomposed; no convenience shortcut endpoints are introduced.

#### 3.5.5 Other endpoint specifics

- All endpoints return JSON wrapped in the v2 `{data, meta, errors}` envelope.
- 4xx error responses use the v2 error envelope shape.
- No additional list query parameters beyond `?include_deleted=true` in v0.5. Client-side filtering over expected manual_config counts (roughly six to twenty per engagement) is sufficient. Server-side filtering by status / category deferred to CBM-redo signal.

### 3.6 UI Considerations

This spec adopts the spec guide's default `ListDetailPanel` layout with no architectural deviations. Specifics for `manual_config` follow.

#### 3.6.1 Sidebar

The "Methodology" sidebar group introduced by `domain.md` section 3.6.1 hosts the new `manual_config` entry. Position within the group depends on PI-004 sibling ship sequence; the working ordering proposed for the PI-004 ship is:

1. Domains
2. Entities
3. Processes
4. CRM Candidates
5. (engagement-tab or alternate group placement per `engagement.md`)
6. Personas (PI-003)
7. Fields (PI-004 sibling)
8. Requirements (PI-004 sibling)
9. **Manual Configs** (this spec)
10. Test Specs (PI-004 sibling)

The exact position resolves at PI-004 build planning. The display name in the sidebar is "Manual Configs" per section 3.1.

#### 3.6.2 Master pane

`ListDetailPanel`-backed list with these columns:

| Stored field | Display header | Width | Notes |
|--------------|----------------|-------|-------|
| `manual_config_identifier` | Identifier | narrow | Default sort key, ascending |
| `manual_config_name` | Name | wide | Short human-readable name |
| `manual_config_category` | Category | narrow | Enum value rendered as-is (e.g., "saved_view", "workflow") |
| `manual_config_status` | Status | narrow | Enum value rendered as-is; the four-status set |
| `manual_config_updated_at` | Updated | narrow | Localized date/time |

Right-click context menu offers New / Edit / Delete / Restore, consistent with v0.3 governance-entity panels per DEC-035 and DEC-036.

The Category column is included in v0.5 (unlike `entity.md`'s deferred Domains column) because category is a single scalar field on the entity table — no batched join required — and category-at-a-glance is high-value for the consultant scanning what kinds of manual action are pending. Domain affiliation (via `manual_config_scopes_to_domain`) is intentionally NOT a master column in v0.5 for the same reasons `entity.md` deferred Domains: it requires a join through references, and without `domain.short_code` (PI-007) it renders as opaque DOM-NNN values. Detail pane exposes it one click away.

#### 3.6.3 Detail pane

Vertical layout, fields in section-3.2 order:

1. `manual_config_identifier` — read-only label
2. `manual_config_name` — single-line text editor
3. `manual_config_category` — combo box with the seven enum values
4. `manual_config_description` — multi-line text editor with placeholder "Brief description of the manual config and why it exists"
5. `manual_config_instructions` — multi-line text editor (taller than description) with placeholder "Step-by-step instructions for the operator"
6. `manual_config_notes` — multi-line text editor under a collapsible "Internal notes" section header, collapsed by default
7. `manual_config_status` — combo box with the four enum values; transitions enforced per section 3.4.3
8. `manual_config_completed_at` — datetime picker; visible only when status is `completed` or transitioning to `completed`
9. `manual_config_completed_by` — single-line text editor; visible only when status is `completed` or transitioning to `completed`
10. `ReferencesSection` widget — renders the four outbound reference kinds plus any inbound `test_spec_verifies_manual_config` references once `test_spec` lands. The widget exposes the existing "Add reference" affordance.

The collapsed-by-default treatment of `manual_config_notes` matches `domain_notes` and `entity_notes` — internal consultant scratchpad, not part of any operator-facing or client-facing render.

#### 3.6.4 Create dialog

Modal `EntityCrudDialog` subclass with field order matching the detail pane. Specifics:

- `manual_config_identifier` not shown in create mode (server-assigned).
- `manual_config_category` required; combo defaults to no selection (forces explicit choice).
- `manual_config_status` defaults to `candidate`; user may select `confirmed` if importing established records, or `completed` if importing already-performed configs (in which case the two completion fields appear in the dialog and are required-on-submit).
- The `manual_config_completed_at` and `manual_config_completed_by` fields are hidden in create mode unless the user selects a status that requires them.
- Required-field validation client-side before submit.
- Server-side validation errors (uniqueness, format, transition, completed-field-population) surface inline.

#### 3.6.5 Edit dialog

Same shape as create. `manual_config_identifier` displayed as read-only label. Status transitions enforced per section 3.4.3; invalid selections in the status combo are either prevented (recommended UX) or rejected by the server with the 422 surfacing inline.

**Mark-Completed UX — open question for v0.5+ build.** Two reasonable patterns for the common "operator performed the config" flow:

- **Status-combo-driven.** The user changes the status combo from `confirmed` to `completed`; the dialog reveals the two completion fields (datetime defaults to "now"; completed-by prefilled if the engagement has an associated operator) and the user submits.
- **Dedicated "Mark Completed" button.** Alongside the standard Save / Cancel buttons, a "Mark Completed" button appears when the current status is `confirmed`. Clicking it prompts a small sub-dialog asking for the completion fields, then patches the record in one step.

Both satisfy the acceptance criterion that the user can transition records to `completed` without leaving the UI. The choice is UI-layer; PI-004 build planning decides. Listed as an open question in section 3.8.

#### 3.6.6 Delete dialog

`EntityCrudDeleteDialog` with edge-text confirmation. The user types the `manual_config_identifier` value (e.g., `MCF-002`) to enable the Delete button, matching v0.3 governance-entity patterns. Confirmation soft-deletes the record. Outbound references on the soft-deleted record persist per section 3.4.6.

### 3.7 Acceptance Criteria

The following 16 statements define what "this entity type is correctly implemented in v0.5+" looks like. Each is concrete and testable; PI-004 build planning translates these into specific test cases.

1. **Schema migration applies cleanly.** Alembic migration creates the `manual_configs` table with all twelve columns (`manual_config_identifier`, `manual_config_name`, `manual_config_description`, `manual_config_category`, `manual_config_instructions`, `manual_config_notes`, `manual_config_status`, `manual_config_completed_at`, `manual_config_completed_by`, `manual_config_created_at`, `manual_config_updated_at`, `manual_config_deleted_at`), correct types and constraints, and runs both forward and backward without error.

2. **`manual_config_identifier` format constraint enforced.** Insertions with `manual_config_identifier` not matching `^MCF-\d{3}$` raise a validation error at the access layer.

3. **`manual_config_name` uniqueness enforced case-insensitively.** Inserting a second row whose `manual_config_name` matches an existing row by lowercase comparison raises a uniqueness violation.

4. **`manual_config_category` enum validation.** Insertions with `manual_config_category` outside `{saved_view, duplicate_check, workflow, deferred_options_enum, role_permission, dynamic_logic, other}` are rejected at the access layer with HTTP 422.

5. **`manual_config_status` enum and four-status transition validation.** Insertions with `manual_config_status` outside `{candidate, confirmed, deferred, completed}` are rejected. PATCH/PUT requesting an invalid transition (e.g., `candidate → completed` direct, or `completed → confirmed` regression, or `deferred → completed` skipping confirmed) returns HTTP 422 with `{"error": "invalid_status_transition", "from": ..., "to": ...}`. The valid transitions (per section 3.4.3) round-trip end-to-end: `candidate → confirmed → completed`, `candidate → confirmed → deferred → confirmed → completed`, `candidate → deferred → confirmed → completed`.

6. **Completed-status field-population enforcement.** A PATCH or PUT that sets `manual_config_status = completed` without populating both `manual_config_completed_at` and `manual_config_completed_by` (either omitted from the body or set to null) returns HTTP 422 with `{"error": "completed_status_requires_completion_fields", "missing": [...]}`. The same applies to POST that explicitly sets `manual_config_status = completed`. A valid `confirmed → completed` PATCH populating both fields succeeds.

7. **Access-layer methods exist with expected signatures.** `client.list_manual_configs()`, `client.get_manual_config(identifier)`, `client.create_manual_config(...)`, `client.update_manual_config(identifier, ...)`, `client.patch_manual_config(identifier, ...)`, `client.delete_manual_config(identifier)`, `client.restore_manual_config(identifier)`, `client.next_manual_config_identifier()` exist and pass unit tests covering happy path and at least one error case each, including the completed-field-population rule.

8. **REST endpoints return expected responses for representative cases.** All eight endpoints from section 3.5 return correct HTTP status and JSON bodies for happy-path and validation-failure cases; 4xx errors use the v2 `{data, meta, errors}` envelope.

9. **Identifier auto-assignment helper returns next ID without race conditions.** `GET /manual-configs/next-identifier` returns `{"next": "MCF-NNN"}` for the next available number. POST with `manual_config_identifier` omitted assigns the same value (per the SAVEPOINT-retry helper). Two concurrent POSTs do not assign the same identifier (verified by a concurrent-insert test).

10. **Soft-delete and restore round-trip correctly.** DELETE sets `manual_config_deleted_at`; the record disappears from `GET /manual-configs`. `GET /manual-configs?include_deleted=true` shows it. POST `/restore` clears `manual_config_deleted_at`; the record reappears in the default list. Restore on a record that is not soft-deleted returns 422. Outbound references survive the soft-delete-and-restore cycle in place.

11. **`Manual Configs` sidebar entry appears under the Methodology group.** Position resolves at PI-004 build planning per section 3.6.1; the entry is present in the v0.5+ ship under the Methodology group below Governance.

12. **Master pane columns and default sort.** The Manual Configs panel shows columns Identifier / Name / Category / Status / Updated, sorted by Identifier ascending. Right-click context menu offers New / Edit / Delete / Restore.

13. **Detail pane renders all fields in section-3.2 order including completion fields and ReferencesSection.** Identifier (read-only), Name, Category combo, Description, Instructions, Notes (collapsed under "Internal notes" header), Status combo, completion datetime (visible only when status is `completed` or being transitioned to `completed`), completed-by text field (same visibility rule), ReferencesSection — all present and bound to the correct fields. The ReferencesSection renders all four outbound kinds and any inbound `test_spec_verifies_manual_config` references once `test_spec` lands.

14. **CRUD dialogs work end to end.** Create assigns identifier server-side, persists all fields, surfaces server-side validation errors inline (including completed-field-population errors when POSTing a completed record). Edit persists field changes including status transitions; the completed-field-population error surfaces inline when an invalid completion transition is attempted. Delete prompts for edge-text confirmation (user types the identifier) and soft-deletes on confirm. Restore reappears the record.

15. **All four outbound relationship kinds registered, constrained, and round-trip bidirectionally.** `REFERENCE_RELATIONSHIPS` includes `manual_config_scopes_to_domain`, `manual_config_touches_entity`, `manual_config_touches_field` (or deferred), `manual_config_realizes_requirement` (or deferred). `_kinds_for_pair` returns the correct singleton sets for each `(manual_config, *)` pair. The Alembic migration extends the `refs.relationship_kind` CHECK constraint. POST `/references` with valid `(source_type, source_id, target_type, target_id, relationship_kind)` creates the row; inverse query from the target side returns it; soft-deleting either endpoint preserves the reference; attempting unsupported pairs returns 422. The detail-pane ReferencesSection round-trips creation, display, and deletion through the UI.

16. **Sample CBM manual configs authored through the UI.** A consultant can author roughly six manual_config records spanning multiple categories (e.g., MCF-001 saved_view "Mentors needing dues invoice"; MCF-002 deferred_options_enum "industrySubsector master list"; MCF-003 deferred_options_enum "geographicServiceArea zip codes"; MCF-004 workflow "Send mentor application decline email"; MCF-005 duplicate_check "Account by name + zip"; MCF-006 role_permission "Mentor coordinator field-level grants"), attach `manual_config_scopes_to_domain` references to authored `domain` records, transition through status lifecycles (some `candidate → confirmed`, at least one `confirmed → completed` populating the completion fields, at least one `candidate → deferred`), and the records and references persist correctly across application restart and across REST/MCP refetch.

### 3.8 Open Questions and Deferred Decisions

Categorized per the spec guide section 3.8 convention. Each entry is one paragraph with an explicit category tag.

#### 3.8.1 For v0.5+ build to settle

**[v0.5 build] `manual_config_completed_by` field shape.** The field is free text in v0.5 — accepts any non-empty string. The alternative is an FK (or references edge) to a user / persona entity. Free text is correct for v0.5 because no `user` entity exists in v2 and the `persona` entity tracked by PI-003 is engagement-side modeling rather than authentication. The CBM redo's operator-handover step will surface whether operator identification needs strong-typing; if so, v0.6+ migrates to an FK paired with whichever entity type the strong-typing lands on (likely `persona` or a new `operator` type). Tracked as a v0.6+ candidate.

**[v0.5 build] Mark-Completed UX affordance.** Section 3.6.5 describes two reasonable UI patterns for transitioning a record to `completed` (status-combo-driven vs. dedicated "Mark Completed" button). Both satisfy the acceptance criterion. The PI-004 build-planning conversation decides which pattern ships. Likely the status-combo-driven approach for v0.5 (lower UI complexity, matches the existing Edit dialog shape) with a dedicated button as a v0.6+ refinement if operator workflow signals demand it.

**[v0.5 build] Concurrent identifier-assignment behavior.** The mechanism for preventing two concurrent POSTs from assigning the same `MCF-NNN` is the standard SAVEPOINT-retry helper described in `CLAUDE.md`. Acceptance criterion #9 requires correctness; implementation follows the established pattern. No new design work needed.

**[v0.5 build] Sequencing with PI-004 sibling specs.** The `manual_config_touches_field` and `manual_config_realizes_requirement` relationship kinds depend on `field` and `requirement` existing. If the PI-004 ship sequence puts `manual_config` before either sibling, the corresponding `_kinds_for_pair` entries are deferred until the targets exist (with the vocabulary entries themselves registered upfront so the validation surface is stable). PI-004 build planning sequences the four entity types and resolves any inter-spec dependencies.

#### 3.8.2 For CBM redo to surface

**[CBM redo] Markdown / fenced code blocks in `manual_config_instructions`.** Plain text in v0.5. Real instructions may benefit from numbered-step structure, fenced code blocks for SSH command snippets or JSON payloads (e.g., for the `saved_view` category whose actual work is disk-level `clientDefs/Entity.json` editing), inline-code formatting for field names, and bold for UI element names. If the CBM redo's first round of authored instructions trips on plain-text limitations, a v0.6 migration introduces markdown rendering on this field specifically (the description and notes fields are unlikely to need it as urgently). The signal is operator readability of the rendered instructions, not consultant authoring convenience.

**[CBM redo] Text-field length caps.** No storage-level length constraints in v0.5; UI placeholder text provides soft guidance. If the CBM redo produces pathological inputs (5000-character "instructions"), caps are added via migration in v0.6. Same posture as `domain` and `entity`.

**[CBM redo] `manual_config_notes` structure.** Flat plain text in v0.5. Same posture as `domain_notes` and `entity_notes`.

**[CBM redo] Master-pane Domains column.** Section 3.6.2 defers the Domains column (via `manual_config_scopes_to_domain`) to v0.6+ paired with PI-007 short codes. Same posture as `entity.md` section 3.6.2 deferring its Domains column. The CBM redo signal on whether scanning manual-config-by-domain at the master pane is high-value feeds the same PI-009 prioritization that the entity panel feeds.

**[CBM redo] Per-engagement completion-progress view.** Not in v0.5 scope. The CBM redo may surface a desire to see a per-engagement summary ("4 of 6 manual configs completed; 2 outstanding"). If so, this could land as a per-engagement detail-pane section or a Methodology sidebar dashboard entry, both of which are v0.6+ candidates. The acceptance criteria above cover the underlying data shape (status + completion fields); UI surfacing follows from real-use signal.

**[CBM redo] Reactivation pattern after deploy wipe.** Section 3.4.3 notes that if the operator un-does a configuration (e.g., a CRM redeploy wipes it), the right action is to soft-delete the `completed` record and author a new one. The CBM redo will test whether this is workable in practice or whether a "redo" affordance (e.g., a Clone + new-MCF-NNN flow) is needed in the UI. Tracked as a v0.6+ candidate pending real-use signal.

#### 3.8.3 For v0.6+

**[v0.6+] PI — free-text "other"-category sub-classification.** The `other` enum value in `manual_config_category` is a generic bucket in v0.5. A new planning item authored at PI-004 build close should add a `manual_config_category_other` free-text field (visible only when category is `other`) so consultants can record what kind of other-category configuration is meant without inventing new enum values. Trivial migration (one nullable TEXT column, one visibility rule in the UI). Deferred from v0.5 because v0.5's vocabulary covers the historical NOT_SUPPORTED categories and the `other` bucket is expected to be rare in early use.

**[v0.6+] PI — automatic linkage from deploy-side NOT_SUPPORTED emissions to manual_config records.** The deploy engine emits NOT_SUPPORTED items at deployment time per `CLAUDE.md`'s "Three features have no public REST API write path" section; v0.5 keeps these decoupled from the methodology-side `manual_config` records. A v0.6+ planning item should evaluate whether to introduce an automatic lookup that, at deploy time, queries the methodology's `manual_config` records for the engagement and (a) annotates the deploy log with the matched MCF-NNN identifiers, (b) flags any NOT_SUPPORTED emission that lacks a methodology-side record as a methodology-coverage gap. Either direction requires careful design — the matching key is non-obvious (entity + field + category? entity + name?) and the deploy engine is a v1 component that doesn't yet know about v2's methodology layer. Likely needs a methodology-side authored attribute on the manual_config record indicating its deploy-time fingerprint.

**[v0.6+] PI — `manual_config_completed_by` strong-typing.** Already noted in 3.8.1. Migrate from free-text to an FK paired with whichever entity type emerges (`persona`, a new `operator` type, or `user` if v2 ever introduces authenticated users).

**[v0.6+] PI — `manual_config_parent_identifier` for hierarchical manual configs.** Not introduced in v0.5 per section 3.3.4. Add via self-referential FK if real-engagement signal surfaces (e.g., a parent role-permission rollup containing per-field child grants).

**[v0.6+] PI — server-side list filters.** Only `?include_deleted=true` in v0.5. Server-side filters by `manual_config_status` and `manual_config_category` become v0.6+ candidates if list sizes grow enough that client-side filtering causes UI responsiveness issues. More likely to bite for manual_config than for `domain` or `entity` at scale because cross-engagement reporting is a plausible v0.6+ use case.

**[v0.6+] PI — verification-progress reporting.** The four-status lifecycle (specifically the `completed` terminal state) enables verification-progress queries ("show me % of manual_configs completed per engagement") that v0.5 does not expose as a first-class report. A v0.6+ PI for a methodology-layer reporting surface (CSV export, dashboard widget, or both) is a natural fit.

### 3.9 Cross-References

#### 3.9.1 Decisions cited by this spec

The following decisions are authored when the spec is approved and the build kicks off (DEC numbers assigned at payload time and may shift based on intervening sessions; the placeholders below name the architectural questions each decision resolves):

- **DEC-MCF-prefix — `manual_config` identifier prefix and format.** Adopts `MCF` under the soft-3-letter posture (see section 3.1) with explicit justification for the non-straight-prefix mapping of a two-word entity name.
- **DEC-MCF-fields — `manual_config` field inventory and validation under v0.5+ scope.** Eight substantive fields plus inherited timestamps; seven-value `manual_config_category` enum; required `manual_config_description` and `manual_config_instructions`; optional `manual_config_notes`; conditionally-required `manual_config_completed_at` and `manual_config_completed_by`; no storage-level length caps; case-insensitive `manual_config_name` uniqueness within the engagement (see section 3.2).
- **DEC-MCF-lifecycle — `manual_config` four-status lifecycle with explicit deviation.** Four values (`candidate`, `confirmed`, `deferred`, `completed`) instead of the cross-spec three-status default; one-way propose-verify gate preserved; `completed` as terminal status reachable only from `confirmed`; rejection handled by soft-delete; no `archived` status; explicit deviation rationale captured per spec guide section 6 (see section 3.4).
- **DEC-MCF-references — `manual_config` outbound relationship kinds and vocabulary registration.** Four outbound kinds (`manual_config_scopes_to_domain`, `manual_config_touches_entity`, `manual_config_touches_field`, `manual_config_realizes_requirement`); references-entity mechanism for all four; new vocabulary entries registered in `REFERENCE_RELATIONSHIPS` and `_kinds_for_pair`; Alembic migration extends the `refs.relationship_kind` CHECK constraint; PI-004 sibling sequencing affects when the field- and requirement-side pair-registrations land (see section 3.3.1).
- **DEC-MCF-api-and-completion — `manual_config` API surface, completed-field-population rule, UI defaults, acceptance criteria for v0.5+.** Standard endpoint set with no deviations; decomposed reference handling; default `ListDetailPanel` UI under the Methodology sidebar group; Category column included in master pane (unlike entity's deferred Domains column); Domains column deferred to v0.6+ paired with PI-007; Mark-Completed UX affordance left as a build-time decision; completed-status-field-population enforcement rule unique to this spec; 16 testable acceptance criteria (see sections 3.5, 3.6, 3.7).

#### 3.9.2 External references

- `crmbuilder/CLAUDE.md` — universal session-startup entry; documents the `REFERENCE_RELATIONSHIPS` / `_kinds_for_pair` / Alembic-migration triad; documents the deploy-pipeline NOT_SUPPORTED behavior and the historical companion-artifact `MANUAL-CONFIG.md` pattern that motivates this entity type; documents the v2 `{data, meta, errors}` API envelope; documents the SAVEPOINT-retry identifier-assignment helper.
- `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md` — schema spec template this document follows.
- `PRDs/product/crmbuilder-v2/methodology-schema-workstream-plan.md` — workstream master plan (v0.4 baseline; PI-004 extends).
- `PRDs/product/app-yaml-schema.md` — v1.1 schema with `optionsDeferred` flag and the companion-artifact `MANUAL-CONFIG.md` pattern explicitly documented (`deferred_options_enum` category source).
- `PRDs/product/features/feat-audit.md` §9 — Section 12.5 role-aware-visibility `NOT_AUDITABLE` posture (`dynamic_logic` category source).

#### 3.9.3 Related prior decisions informing this spec

- **DEC-006** — Universal references table as the cross-entity-type edge store. Direct architectural foundation for the four outbound `manual_config_*` relationship kinds in section 3.3.1.
- **DEC-039** — Minimum entity inventory and multi-tenancy posture. Informs the thin-shape framing in section 1.
- **DEC-043** — SES-010 identifier-asymmetry resolution. Mandates the `GET /manual-configs/next-identifier` helper endpoint cited in section 3.5.1.
- **DEC-046** — Parent-prefix field-naming convention for methodology entities. Establishes the field-naming pattern this spec inherits and applies (see section 3.2).
- **DEC-047** — `domain` status lifecycle, propose-verify gate, and rejection-via-soft-delete posture. Establishes the lifecycle pattern this spec adopts as a baseline and deviates from with the `completed` terminal status (see section 3.4).
- **DEC-048** — `domain` relationship posture and `{source}_{verb}_{target}` relationship-kind naming convention. Establishes the relationship-kind naming pattern this spec applies in registering the four outbound `manual_config_*` kinds (see section 3.3.3).

#### 3.9.4 Sibling specs

- **`domain.md`** — convention-establishing predecessor; field-naming and relationship-kind-naming conventions; soft-3-letter prefix posture; three-status lifecycle template that this spec deviates from with a fourth status.
- **`entity.md`** — worked-example predecessor for many-to-many references-entity mechanism; sidebar group; Domains-column deferral pattern; sample acceptance-criteria shape.
- **`process.md`** — sibling with target-side anticipations for `process_realizes_requirement` (the working pattern inverse to this spec's `manual_config_realizes_requirement`).
- **`crm_candidate.md`** — sibling using the same Methodology sidebar group; reference for how to handle thin-schema methodology entities under v0.4 baseline.
- **`engagement.md`** — sibling providing the per-engagement scoping context; manual configs ultimately scope to engagements via their domain affiliations (or via a future direct edge if PI-004 surfaces the need).
- **`field.md`** (forthcoming, PI-004 sibling) — target of `manual_config_touches_field`. Pair-registration sequencing depends on which entity type ships first.
- **`requirement.md`** (forthcoming, PI-004 sibling) — target of `manual_config_realizes_requirement`. Same sequencing dependency.
- **`test_spec.md`** (forthcoming, PI-004 sibling) — anticipated inbound source via `test_spec_verifies_manual_config`. Vocabulary registration belongs to the source-side spec.

#### 3.9.5 Related planning items

- **PI-003** — `persona` entity type. Possible v0.6+ host for `manual_config_completed_by` strong-typing.
- **PI-004** — Additional methodology entity types for v0.5+ (`field`, `requirement`, `manual_config`, `test_spec`). This spec resolves the `manual_config` portion of PI-004.
- **PI-005** — Process schema growth beyond Phase 1 thin shape. Adjacent v0.5+ methodology work; the eventual `process_realizes_requirement` relationship pairs with this spec's `manual_config_realizes_requirement` as the two realization mechanisms.
- **PI-007** — `domain.short_code` field. Joint enabler for a future Domains column on the manual_configs master pane.
- **PI-009** — Master-pane Domains column on the Entities panel. The manual_configs panel inherits the same deferral posture and would benefit from the same column when PI-007 and PI-009 land.
- **PI-010** — Entity-schema v0.5+ extensions (variants, base-type/kind). Adjacent but independent; no direct dependency.

---

*End of document.*

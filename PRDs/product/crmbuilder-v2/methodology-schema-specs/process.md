# Methodology Entity Schema Spec — `process`

**Last Updated:** 05-12-26 04:30
**Status:** Draft v1.0 — produced by schema-design conversation
**Position in workstream:** Third of four methodology-entity schema specs (`domain` → `entity` → `process` → `crm_candidate`)
**Predecessor conversation:** `entity` schema-design conversation (close-out payload at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_013.json`)
**Successor conversation:** `crm_candidate` schema design — kickoff at `PRDs/product/crmbuilder-v2/schema-design-kickoff-crm_candidate.md`

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-12-26 04:30 | Doug Bower / Claude | Initial draft. Produced by the third schema-design conversation in the methodology-entity-schema-design workstream. Defines `process` as the v2 methodology entity type that hosts evolved-methodology Phase 1 Prioritized Backbone members under minimum-viable v0.4 scope. Inherits conventions established by `domain.md` (parent-prefix field naming, `{source}_{verb}_{target}` relationship-kind naming, soft-3-letter prefix posture, status lifecycle semantics — though this spec deviates on status, see section 3.4) and applied by `entity.md` (cross-spec relationship vocabulary additive pattern). Establishes `process_hands_off_to_process` as the second formal cross-entity vocabulary entry in the methodology workstream, directional. |

---

## Change Log

**Version 1.0 (05-12-26 04:30):** Initial creation. Defines five substantive fields plus inherited timestamps; replaces the conventional status field with `process_classification` carrying the methodology's Principle 3 priority taxonomy (`unclassified | mission_critical | supporting | deferred`) and uses soft-delete for rejection without a separate lifecycle field; engagement-global unique `process_name` mirroring the domain/entity precedent; many-to-one domain affiliation via direct FK column (no references-table edge); directional many-to-many process-to-process handoffs via the references entity using the new `process_hands_off_to_process` kind. Defers process-to-entity touches entirely (no vocab registration in v0.4) under PI-005. Five decisions produced (DEC-055 through DEC-059) and one new planning item (PI-011 future scalar implementation-priority field). Acceptance criteria captured as 15 testable statements.

---

## 1. Purpose and Position

This document specifies the `process` entity type for v2's storage layer. It is the third of four schema specs produced by the methodology-entity-schema-design workstream — the workstream that prepares v2 to host methodology *content* (not just governance about it) in time for the CBM redo, which will use the evolved methodology and v2 as its system of record.

The workstream is governed by `methodology-schema-workstream-plan.md`. Each schema spec conforms to the template in `methodology-entity-schema-spec-guide.md`. The two predecessor specs (`domain.md` and `entity.md`) established cross-spec conventions that this spec inherits:

- **Parent-prefix field naming** (DEC-046): all non-identifier, non-timestamp fields are prefixed with the parent entity name. All fields including identifier and timestamps adopt the prefix in v0.4 for full convention consistency.
- **`{source}_{verb}_{target}` relationship-kind naming** (DEC-048): vocabulary entries involving methodology entities are named source-first, with the source entity name, a verb phrase, and the target entity name.
- **Soft-3-letter prefix posture** (DEC-044): three letters preferred, four letters acceptable where three would be ambiguous.
- **Engagement-global case-insensitive name uniqueness** (DEC-045, DEC-051): adopted unchanged.
- **Rejection via soft-delete; no `archived` status** (DEC-047, DEC-052): adopted unchanged.

This spec adopts those conventions without re-establishing them. It does, however, deviate from the predecessors on one structural point: **`process` does not have a `status` field**. The rationale is documented in section 3.4 and reflects the methodology's distinction between propose-verify lifecycle (the meaning of `status` for `domain` and `entity`) and definitional completeness (the meaning a process status field would have in a richer v0.5+ schema). In v0.4 the schema captures only the Phase 1 "identified" level of completeness, so the field would be empty — and the priority/scope information that `domain` and `entity` carry via `status=deferred` is captured for `process` via the `process_classification` field instead.

`process` is the third spec because it is the most relational of the four. It belongs to one `domain` (many-to-one), connects to other `process` records through directional handoffs (many-to-many), and is anticipated to touch `entity` records in v0.5+ once Phase 3 work demands. Designing `process` third lets both `domain` and `entity` exist as settled referents.

`process`'s primary scope in v0.4 is the Phase 1 Prioritized Backbone output (section 7.3 of `phase-1-interview-guide.md`): the named set of mission-critical processes drawn from across whichever domains are needed, plus supporting and deferred processes, plus the connections between them. Phase 1 explicitly names processes and identifies their connections; it does *not* define them in detail. Detailed process definitions (steps, actors, fields touched, triggers, outcomes, edge cases) are Phase 3 work, deferred to v0.5+ under PI-005. The v0.4 schema is intentionally thin enough that a `process` record is more a structured token than a full definition. That thinness is methodology-driven; Phase 1 produces tokens.

---

## 2. Summary

A `process` record in v2 represents one member of a Phase 1 Prioritized Backbone, supporting process list, or deferred process list: one of the named activities the client's organization performs that the methodology has captured as worth tracking. Phase 1 surfaces process names from two sources — directly from the client's description of what they do (Session 1 Part C) and from the consultant's workability-check additions where end-to-end work flow requires a process the client didn't think to mention. Either way, the client confirms the process in Session 2.

Each `process` record carries a client-language name, a one-sentence purpose, a methodology priority classification (mission-critical / supporting / deferred), the reasoning behind that classification (the priority-test answer for backbone processes; the one-line reason for supporting and deferred), an optional internal-notes scratchpad, and a required affiliation to exactly one domain via a direct FK column. Process-to-process handoffs — the directional dependencies that constitute the Prioritized Backbone's connection structure — are captured via the universal references store using the new `process_hands_off_to_process` vocabulary kind.

The schema in v0.4 is the thinnest shape that can faithfully host Phase 1's Prioritized Backbone output. It deliberately omits process steps, actors / personas performing the process, fields touched on entities the process consumes or produces, trigger and outcome semantics, cycle time and frequency and volume metrics, and any sub-process hierarchy — all of these belong to Phase 3 work or to subsequent v2 releases. The minimum-viable shape grows additively in v0.5+ as Phase 3 iteration work reveals what `process` needs to carry.

---

## 3. Schema Specification

### 3.1 Identity

| Field | Value |
|-------|-------|
| Entity type name (storage) | `process` |
| Display name (singular) | Process |
| Display name (plural) | Processes |
| Identifier prefix | `PROC` |
| Identifier format | `PROC-NNN`, zero-padded to 3 digits (e.g., `PROC-001`, `PROC-042`) |
| Identifier auto-assignment | Server-side on POST omission; helper at `GET /processes/next-identifier` |

**Prefix rationale.** `PROC` is four letters, invoking the soft-3-letter posture's explicit deviation clause from `domain.md` section 3.1: *"Downstream conversations may adopt 4-letter prefixes if the 3-letter form is ambiguous (e.g., `PROC` over `PRC` for clarity)."* The three-letter candidate `PRC` is bad — reads as a typo, has no natural disambiguation against random acronyms, and forces the consultant to mentally re-expand it every time. `PR` collides with public relations (which a CRM context might legitimately encounter as a domain) and is also only two letters, which the spec guide disallows. `P` is too short. No collision with existing prefixes (DEC, SES, RSK, PI, TOP, REF, CHR, STA, DOM, ENT). The identifier-asymmetry helper endpoint per DEC-043 ships alongside the standard endpoint set.

### 3.2 Fields

Field naming follows the parent-prefix convention established by `domain.md` (DEC-046): all non-identifier, non-timestamp fields are prefixed with the parent entity name (`process_`). All fields including identifier and timestamps adopt the prefix in v0.4 for full convention consistency.

#### 3.2.1 Identity fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `process_identifier` | TEXT | yes | server-assigned | `^PROC-\d{3}$`, unique | The methodology-entity identifier in `PROC-NNN` format. Server-assigned when omitted from POST body. |
| `process_name` | TEXT | yes | — | non-empty trimmed; case-insensitive unique within the engagement | Process name in the client's language. The engagement-global uniqueness rule means consultants name processes distinctly across the engagement — e.g., "Mentor Recruit" and "Client Recruit" rather than two records both named "Recruit." This matches `domain` and `entity` precedent and avoids rendering ambiguity wherever process names appear without domain context (handoff lists, audit logs, search results, future Phase 3 cross-domain reports). |

#### 3.2.2 Content fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `process_purpose` | TEXT | yes | — | non-empty trimmed | One-sentence statement of what the process does. Phase 1 guide section 7.3 explicitly produces "One-sentence purpose" for each backbone process; the same field carries the corresponding content for supporting and deferred processes. Plain text in v0.4; markdown support deferred to CBM-redo signal. |
| `process_classification_rationale` | TEXT | no | — | — | Reasoning behind the current `process_classification` value. For `mission_critical` processes, this carries the priority-test answer ("if this stopped tomorrow, the mission would..."); for `supporting`, the one-line reason it isn't on the critical path; for `deferred`, the one-line reason it's parked. Phase 1 guide section 7.3 produces this content for all three classifications under different field names. Optional rather than conditionally required because the field is empty when `process_classification = unclassified`; UI placeholder text cues the consultant to fill it once classification is set. |
| `process_notes` | TEXT | no | — | — | Internal consultant scratchpad. Not part of any client-facing render. Used to capture pattern-library rationale, push-back trails from Session 2, between-session reasoning about why the process exists in its current shape. Plain text in v0.4. |

**No separate `process_description` field.** For `domain`, purpose (mission relationship) and description (work content) were genuinely different content. For `process`, both questions reduce to "what does this process do?" and one field handles it. If the CBM redo surfaces a need for a richer description distinct from purpose, v0.5 adds it via migration.

#### 3.2.3 Classification fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `process_classification` | TEXT | yes | `unclassified` | enum: `unclassified` \| `mission_critical` \| `supporting` \| `deferred`; valid transitions per section 3.4 | Methodology priority classification per Principle 3 ("Priority is established at the process level and inherited downward"). See section 3.4 for the transition map. |

**No `process_kind` (process-type) classification in v0.4.** Process-type taxonomies (procedural / collaborative / approval / etc.) belong to Phase 3 work; their absence here keeps the v0.4 schema neutral about process-shape specifics. Deferred under PI-005.

#### 3.2.4 Relationship fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `process_domain_identifier` | TEXT | yes | — | matches `^DOM-\d{3}$`; refers to a live `domain` record | Direct FK to the affiliated domain. Each process belongs to exactly one domain (many-to-one cardinality, settled at the methodology level — Phase 1's Prioritized Backbone groups processes by domain, and the Phase 1 output document renders processes within their parent domain). Validated at the access layer (the v2 storage convention; not enforced at the SQLite layer). |

No other outgoing FK columns on the `process` table. Process-to-process handoffs are stored via the references entity (see section 3.3.1) rather than as FK columns; process-to-entity touches are deferred entirely to v0.5+ (PI-005).

#### 3.2.5 Timestamp fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `process_created_at` | DATETIME | yes | server-set on insert | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `process_updated_at` | DATETIME | yes | server-set on insert and on each update | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `process_deleted_at` | DATETIME | no | null until soft-delete | ISO 8601 UTC when set | Inherited base behavior. Set on DELETE; cleared on POST `/restore`. |

**No storage-level length caps.** Text fields are unconstrained at the storage layer in v0.4. The UI provides soft guidance via placeholder text. Pathological-input handling deferred to CBM-redo signal; length caps are easy to add via migration in v0.5 if needed. Mirrors `domain` and `entity` posture.

### 3.3 Relationships

#### 3.3.1 Outgoing relationships

`process` participates in two outgoing relationships in v0.4. One is via direct FK column (not the references table; no vocabulary entry); the other is via the references entity.

**`process_belongs_to_domain` — direct FK, conceptual relationship name only.**

| relationship_kind (conceptual) | source | target | mechanism | cardinality | semantics |
|-------------------|--------|--------|-----------|-------------|-----------|
| `process_belongs_to_domain` | `process` | `domain` | direct FK column (`process_domain_identifier`) | many-to-one | A process belongs to exactly one domain. Mirrors the Phase 1 Prioritized Backbone's domain-grouped process listing. |

`process_belongs_to_domain` is a *conceptual* relationship name. The mechanism is the FK column declared in section 3.2.4, not a row in the references table. **The kind is NOT registered in `REFERENCE_RELATIONSHIPS` or `_kinds_for_pair`** because the references vocab governs the references table only; a direct FK column doesn't produce references rows, so registering the kind would be misleading. This is a small correction to `domain.md` section 3.3.2's anticipated-relationships table — the row stays informational, but no `vocab.py` registration follows.

The choice over a references-entity edge per `entity.md`'s pattern is per the spec guide section 3.3 case for direct FK: cardinality is settled at the methodology level (a process can't legitimately span multiple domains in the way an entity can — the Phase 1 guide and the workability check both produce per-domain process listings), no edge metadata is needed, and lookup is trivial via the FK column. The choice differs from `entity.md`'s many-to-many references edge (`entity_scopes_to_domain`) because the underlying cardinality differs.

**`process_hands_off_to_process` — references-entity edge, directional.**

| relationship_kind | source | target | mechanism | cardinality | semantics |
|-------------------|--------|--------|-----------|-------------|-----------|
| `process_hands_off_to_process` | `process` | `process` | references-entity edge | many-to-many, directional | Process A hands off to Process B if A produces records or state that B requires to do its work. Source = producer; target = consumer. |

The mechanism is the references entity at v2's `refs` table, governed by the existing `RELATIONSHIP_RULES` infrastructure (DEC-006). The choice over an undirected representation is per DEC-058: the methodology's language is inherently directional (Phase 1 guide section 4.1: *"Process A hands off to Process B if A produces records or state that B requires"*), and Phase 1's output document (section 7.3) asks for "Handoffs to/from other backbone processes" per process — naming both sides distinguished, not symmetrically related. An undirected representation would force the consultant to track direction outside the system; a directional representation captures it in the data.

**Mechanical additions per CLAUDE.md line 48:**

1. `process_hands_off_to_process` added to `REFERENCE_RELATIONSHIPS` in `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`.
2. `_kinds_for_pair` extended so `(process, process)` returns `{process_hands_off_to_process}` (the only kind for this pair in v0.4).
3. Alembic migration extending the `refs.relationship_kind` CHECK constraint to include the new value.

**Cardinality and validation:**

- Many-to-many, directional. A process may have any number of outbound handoffs to other processes and any number of inbound handoffs from other processes; the two directions are tracked independently.
- Zero-handoff is permitted. A process may stand alone in the Prioritized Backbone if its work is fully self-contained, or may have its handoffs added later as the consultant identifies them.
- Source must be a live `process` record; target must be a live `process` record. (Existing access-layer rules for the references table.)
- Source and target may be the same record — a self-loop is technically valid (a process that hands off to itself across iterations of its own execution). Unusual but not invalid; no constraint prevents it.
- Duplicate `(source_id, target_id, relationship_kind)` tuples are rejected by the references-table uniqueness constraint. To represent a bidirectional handoff (A produces for B *and* B produces for A — a feedback loop), the consultant authors two distinct edges (A → B and B → A).

**Lifecycle semantics:**

- Soft-deleting a process does not cascade-delete its outbound or inbound handoff references; the references persist (existing v2 behavior) and remain visible via the show-deleted UI toggle on either side.
- Restoring either endpoint restores its relationship rows in place.

**The verb "hands off to" means:** the source process produces records or state that the target process consumes. This is a workflow-dependency notion, not strict ownership, sequencing-in-time, or containment.

#### 3.3.2 Inbound relationships (anticipated; declared by future source-side specs)

No inbound relationships are declared by source-side specs in v0.4. The two anticipated v0.5+ vocabulary kinds are listed for reference:

| relationship_kind (anticipated v0.5+) | source | target | semantics |
|-------------------|--------|--------|-----------|
| `process_touches_entity` (working name; v0.5+) | `process` | `entity` | A process reads, creates, updates, or deletes records of an entity. The relationship may decompose into finer kinds (`process_reads_entity`, `process_creates_entity`, etc.) at v0.5+ design time. Deferred from v0.4 because Phase 1 does not formally produce this data (Phase 3 territory); pre-committing to a coarse vocab name risks shipping the wrong shape. PI-005 tracks this work. |
| `step_belongs_to_process` (working name; v0.5+) | `step` | `process` | A step (one ordered sub-action within a process) belongs to a process. Phase 3 territory; the `step` entity type does not exist in v0.4. PI-005. |

The v0.4-build-planning conversation's cross-spec consistency check verifies that the working names above do not collide with any vocab kinds registered by `crm_candidate.md`.

#### 3.3.3 Cross-spec relationship-kind naming convention — adopted, not established

This spec adopts the `{source}_{verb}_{target}` relationship-kind naming convention established by `domain.md` section 3.3.3 (DEC-048). The single vocabulary entry this spec registers (`process_hands_off_to_process`) conforms to the pattern: source entity first, verb phrase, target entity. "Process A hands off to Process B" reads naturally as source=A, target=B, kind=`process_hands_off_to_process`. The convention is not re-decided here; it carries forward from the predecessor conversations.

#### 3.3.4 Hierarchy

`process` does not use the self-referential parent-child hierarchy pattern in v0.4. Sub-process structure (Phase 3 territory where a top-level process decomposes into steps, sub-processes, or workflow branches) is deferred to v0.5+ under PI-005. The v0.4 schema is hierarchy-unaware: every process record is a top-level token in the Prioritized Backbone. If the CBM redo's Phase 3 work surfaces a need for sub-process containment before PI-005 lands, the v0.5 schema migration adds a `process_parent_identifier` self-FK following the existing `topic.parent_topic` pattern.

### 3.4 Lifecycle

**This spec deviates from `domain.md` and `entity.md` precedent: `process` does not have a `status` field.** The deviation is explicit and justified in section 3.4.1. Soft-delete continues to handle rejection per the established cross-spec posture (DEC-047, DEC-052).

#### 3.4.1 No status field — deviation rationale

`domain` and `entity` adopted a three-status lifecycle (`candidate` / `confirmed` / `deferred`) tracking propose-verify engagement scope. `process` does not adopt this pattern in v0.4 because:

- **The methodology's lifecycle on process is about definitional completeness, not existence verification.** A process record represents a real process the client does (or is captured for Phase 1 verification in Session 2; if the client rejects it as not real, the record is soft-deleted, not kept with some "fake" status). The interesting lifecycle distinction for process is *how completely the process has been defined*: Phase 1 produces "identified" depth (name, domain, overview, classification); Phase 3 produces "detailed" depth (steps, actors, fields touched). In v0.4, only the identified level exists in the schema, so a status field tracking definitional completeness would have exactly one value — which is no field at all.

- **The "deferred" semantic that `status` carries for `domain` and `entity` is captured for `process` by `process_classification = deferred` instead.** Overloading both fields with a `deferred` value would create field-collision ambiguity (which "deferred" applies? both? either?) and add no methodology meaning. The Phase 1 Prioritized Backbone output explicitly produces three priority buckets (Backbone, Supporting, Deferred) — that's `process_classification`'s work, not a status field's.

- **Rejection is handled by soft-delete**, following the cross-spec posture established for `domain` and `entity` (DEC-047, DEC-052). A consultant who proposes a process the client rejects in Session 2 soft-deletes the record. The record persists for audit and history; surfaces under the `?include_deleted=true` toggle; is restorable via POST `/restore`. **Status values track engagement-scope lifecycle** for `domain` and `entity`; **for `process`, classification tracks engagement-scope lifecycle** and soft-delete continues to track existence-in-the-record. The cross-spec principle survives intact; only the field carrying engagement-scope information differs.

A definitional-completeness field (working name `process_definition_level` or similar) is anticipated in v0.5+ once Phase 3 work produces multiple completeness levels distinguishable in the schema. PI-005 absorbs this.

#### 3.4.2 Classification transitions

`process_classification` is mutable but transition-constrained.

| Classification value | Description | Valid predecessors | Valid successors |
|--------------|-------------|--------------------|------------------|
| `unclassified` | **Default starter status.** Process name captured (Session 1) but consultant has not yet performed between-session classification work. Transient state, expected to depart before Session 2. | (none — starter) | `mission_critical`, `supporting`, `deferred` |
| `mission_critical` | On the Prioritized Backbone. Passes the priority test ("if this stopped tomorrow, the mission would..."). | `unclassified`, `supporting`, `deferred` | `supporting`, `deferred` |
| `supporting` | Real work the client does, but not on the critical path for the current iteration. Likely candidate to graduate to backbone in a future iteration. | `unclassified`, `mission_critical`, `deferred` | `mission_critical`, `deferred` |
| `deferred` | Acknowledged but parked indefinitely. Not currently expected to graduate. | `unclassified`, `mission_critical`, `supporting` | `mission_critical`, `supporting` |

**Transition semantics.** The lifecycle implements a **one-way `unclassified` gate**: once a process has moved out of `unclassified`, it does not regress to `unclassified`. The rationale: classification work is a meaningful engagement event (between Session 1 and Session 2); if the consultant later wants to fundamentally rethink a classified process, the right action is to *change* the classification value, not to revert to the unclassified state. Once classified, stay classified.

Movement freely among the three classified values (`mission_critical`, `supporting`, `deferred`) is permitted to support mid-engagement scope changes per Principle 7 ("Decisions inside shipped iterations are locked; priority is not"). A process initially backbone may be demoted to supporting after iteration 1 reveals it's less critical than expected; a previously-deferred process may be promoted to backbone for a later iteration. All transitions among classified values are valid both directions.

#### 3.4.3 Rejection via soft-delete

When the client rejects a CRM-Builder-proposed process candidate in Session 2 ("no, that's not actually a process we do, that's not the right granularity") or when later iteration review surfaces that a process should not exist in the engagement record, the rejection is handled by soft-delete rather than a status value. `DELETE /processes/{process_identifier}` sets `process_deleted_at`; the record persists for audit and history, surfaces under the `?include_deleted=true` toggle, and is restorable via POST `/restore`.

The cross-spec principle established in `domain.md` section 3.4.3 carries forward unchanged: **engagement-scope lifecycle information is tracked in one designated field; soft-delete tracks existence-in-the-record.** For `domain` and `entity`, the designated field is `status`; for `process`, the designated field is `process_classification`.

#### 3.4.4 No `archived` status

Mirrors `domain` and `entity`: soft-delete combined with the `?include_deleted=true` toggle already covers the "retained for record, not in active scope" case. No `archived` value introduced in v0.4.

#### 3.4.5 Soft-delete semantics

Soft-delete inherits v2's standard behavior:

- DELETE sets `process_deleted_at` to the current ISO 8601 UTC timestamp.
- Soft-deleted records do not appear in `GET /processes` by default.
- `GET /processes?include_deleted=true` returns soft-deleted records alongside live ones.
- POST `/processes/{process_identifier}/restore` clears `process_deleted_at` and reappears the record in the default list.
- Restore on a record that is not soft-deleted returns HTTP 422.

Outbound and inbound `process_hands_off_to_process` references on a soft-deleted process are NOT cascade-deleted. They persist in the references table; show-deleted toggles on either side surface them. This matches v2's existing references-table soft-delete behavior.

### 3.5 API Surface

#### 3.5.1 Endpoints

| Method | Path | Body | Notes |
|--------|------|------|-------|
| GET | `/processes` | — | List endpoint. Returns active records by default. Supports `?include_deleted=true` to include soft-deleted records. |
| GET | `/processes/{process_identifier}` | — | Single fetch by identifier. Returns 404 if not found. |
| POST | `/processes` | full record minus `process_identifier` (server-assigned) | Create. Returns 201 with the assigned identifier in the response body. Server-side validation per section 3.2 applied. |
| PUT | `/processes/{process_identifier}` | full record | Full replace. `process_identifier` in body must match the path; mismatch returns 422. |
| PATCH | `/processes/{process_identifier}` | partial record | Partial update. Classification-transition validation applied (see 3.5.3). |
| DELETE | `/processes/{process_identifier}` | — | Soft-delete; sets `process_deleted_at`. Idempotent (DELETE on an already-soft-deleted record returns 200 with no state change). |
| POST | `/processes/{process_identifier}/restore` | — | Clears `process_deleted_at`. Returns 422 if the record is not soft-deleted. |
| GET | `/processes/next-identifier` | — | Returns `{"next": "PROC-NNN"}` for the next available identifier. Per SES-010 resolution (DEC-043). |

**No deviations from the cross-spec default endpoint set.** No bulk operations, no webhooks, no event streams, no inline-handoff or inline-affiliation convenience endpoints.

#### 3.5.2 Identifier auto-assignment

`process_identifier` is server-assigned on POST when omitted from the request body. The assignment logic queries the current maximum `process_identifier` (including soft-deleted records, to avoid identifier reuse) and increments the numeric suffix. The `GET /processes/next-identifier` helper exposes the same logic for clients that want to know the assigned identifier before POSTing.

Concurrent identifier-assignment behavior (locking, optimistic retry, advisory locks, etc.) is implementation-level and decided by the v0.4 build, consistent with how `domain` and `entity` handle concurrency. Acceptance criterion #6 in section 3.7 requires correctness under concurrent POSTs.

#### 3.5.3 Classification-transition validation

Classification transitions are validated server-side at the access layer. PATCH or PUT requests that specify a `process_classification` value that is not a valid successor of the current value (per section 3.4.2) return HTTP 422 with a body of the form:

```
{
  "error": "invalid_classification_transition",
  "from": "<current classification>",
  "to": "<requested classification>"
}
```

The default-`unclassified` rule applies on POST: if `process_classification` is omitted, the server assigns `unclassified`. POST with `process_classification` explicitly set to a classified value is permitted (e.g., bulk-importing already-classified processes from prior engagement records, or programmatic creation by a consultant who has already done the between-session classification work).

#### 3.5.4 Domain affiliation validation

`process_domain_identifier` is required on POST. The access layer validates that the referenced `DOM-NNN` exists and is not soft-deleted; references to a missing or soft-deleted domain return HTTP 422 with:

```
{
  "error": "invalid_domain_reference",
  "domain_identifier": "<requested>"
}
```

PATCH and PUT may change `process_domain_identifier` to a different live domain. There is no cascade from domain soft-delete to process records — a process whose domain is soft-deleted continues to reference the now-soft-deleted domain by FK; the UI surfaces this with a warning on the process detail pane and offers the consultant the option to either restore the domain or re-affiliate the process.

#### 3.5.5 Decomposed handoff handling

Process-to-process handoffs are NOT inlined into the process create or update bodies. To attach a `process_hands_off_to_process` reference, the client makes a separate `POST /references` with:

```
{
  "source_type": "process",
  "source_id": "PROC-NNN",
  "target_type": "process",
  "target_id": "PROC-MMM",
  "relationship_kind": "process_hands_off_to_process"
}
```

This decomposed posture matches `entity.md`'s decomposed-reference handling (DEC-053 / section 3.5.4) and keeps the process API consistent with v2's references-first discipline (DEC-006). The New dialog and detail-pane "Add reference" affordance hide the multi-call sequence behind single user gestures, but the API stays decomposed; no `/processes/{id}/handoffs` or similar shortcut endpoint is introduced.

#### 3.5.6 Other endpoint specifics

- All endpoints return JSON.
- 4xx error responses use the existing v2 error envelope shape.
- No additional list query parameters beyond `?include_deleted=true` in v0.4. Client-side filtering over the expected process count (a typical Phase 1 Prioritized Backbone has 6-15 processes across all classification buckets) is sufficient. Server-side filtering deferred to CBM-redo signal.

### 3.6 UI Considerations

This spec adopts the spec guide's default `ListDetailPanel` layout with no architectural deviations. Specifics for `process` follow.

#### 3.6.1 Sidebar

The "Methodology" sidebar group introduced by `domain.md` section 3.6.1 hosts the new `process` entry. Position #3 in the group, between Entities and CRM Candidates:

1. Domains
2. Entities
3. **Processes** (this spec)
4. CRM Candidates (`crm_candidate.md`, forthcoming)

All four entries ship together in v0.4.

#### 3.6.2 Master pane

`ListDetailPanel`-backed list with these columns:

| Stored field | Display header | Width | Notes |
|--------------|----------------|-------|-------|
| `process_identifier` | Identifier | narrow | Default sort key, ascending |
| `process_name` | Name | wide | Client-language name |
| `process_classification` | Classification | narrow | Enum value rendered as-is |
| `process_updated_at` | Updated | narrow | Localized date/time |

Right-click context menu offers New / Edit / Delete / Restore, consistent with v0.3 governance-entity panels per DEC-035 and DEC-036.

**No Domain column in v0.4.** Mirrors `entity.md`'s posture (DEC-054): without `domain.short_code` (tracked as PI-007), the column would render `DOM-001, DOM-002, DOM-003` — identifiers that don't tell a consultant anything at a glance. The detail pane exposes domain affiliation one click away; the absence of the master-pane column is not a coverage gap, just a UX-density tradeoff awaiting real-use signal. Deferred to v0.5+ paired with PI-007.

#### 3.6.3 Detail pane

Vertical layout, fields in section-3.2 order:

1. `process_identifier` — read-only label
2. `process_name` — single-line text editor
3. `process_domain_identifier` — combo box backed by `GET /domains`; required field; selecting a domain that doesn't exist or is soft-deleted is impossible (the combo only enumerates live records)
4. `process_purpose` — multi-line text editor with placeholder "One sentence — what does this process do?"
5. `process_classification` — combo box with the four enum values
6. `process_classification_rationale` — multi-line text editor with placeholder text that varies by current classification ("Priority-test answer" for `mission_critical`; "Why this is supporting rather than mission-critical" for `supporting`; "Why this is deferred" for `deferred`; "Pending classification — populate after Session 2" for `unclassified`)
7. `process_notes` — multi-line text editor under a collapsible "Internal notes" section header, collapsed by default
8. `ReferencesSection` widget — renders outgoing `process_hands_off_to_process` edges (rendered as "Hands off to: ..."), inbound `process_hands_off_to_process` edges where this process is the target (rendered as "Receives from: ..."), and any other inbound references that future source-side specs declare. In v0.4 the only registered methodology kind involving process-as-target is `process_hands_off_to_process` itself; the widget is always present and the two directions render in separate sub-sections of the references panel for clarity.

The collapsed-by-default treatment of `process_notes` matches `domain_notes` and `entity_notes` — internal consultant scratchpad, not part of any client-facing render.

#### 3.6.4 Create dialog

Modal `EntityCrudDialog` subclass with field order matching the detail pane. Specifics:

- `process_identifier` not shown in create mode (server-assigned).
- `process_domain_identifier` selection required before submit (it's a required FK; the combo defaults to the first live domain alphabetically, or to the user's last-selected domain if a per-session memory exists).
- `process_classification` defaults to `unclassified`; user may select a different starter value if importing already-classified processes.
- `process_classification_rationale` placeholder updates dynamically based on the selected classification value (per section 3.6.3 placeholder pattern).
- Required-field validation client-side before submit (`process_name`, `process_purpose`, `process_domain_identifier`).
- Server-side validation errors (uniqueness, format, domain-existence, classification-transition) surface inline.

**Process-to-process handoff flow — open question for v0.4 build.** Two reasonable patterns, mirroring `entity.md`'s deferred decision on its create-dialog affiliation flow:

- **Create-then-attach.** The New dialog creates the process record only; the user adds handoff references from the detail pane via the existing "Add reference" affordance after the process exists. Two or more gestures per process.
- **Create-with-attach.** The New dialog includes a multi-select for upstream-handoff sources and downstream-handoff targets; on submit, the UI runs POST `/processes` followed by N × POST `/references` in sequence. One gesture per process regardless of handoff count.

Both satisfy the acceptance criterion that the user can attach handoffs through the UI without leaving it. The choice is UI-layer, not schema-layer; the v0.4-build-planning conversation decides which pattern is implemented, ideally coordinating with the parallel decision for `entity` affiliations.

#### 3.6.5 Edit dialog

Same shape as create. `process_identifier` displayed as read-only label. Classification transitions enforced per section 3.4.2; invalid selections in the classification combo are either prevented (recommended UX) or rejected by the server with the 422 surfacing inline (acceptable fallback).

#### 3.6.6 Delete dialog

`EntityCrudDeleteDialog` with edge-text confirmation. The user types the `process_identifier` value (e.g., `PROC-002`) to enable the Delete button, matching v0.3 governance-entity patterns. Confirmation soft-deletes the record. Outbound and inbound `process_hands_off_to_process` references on the soft-deleted process persist per section 3.4.5.

### 3.7 Acceptance Criteria

The following 15 statements define what "this entity type is correctly implemented in v0.4" looks like. Each is concrete and testable; v0.4 build planning translates these into specific test cases.

1. **Schema migration applies cleanly.** Alembic migration creates the `processes` table with all nine columns (`process_identifier`, `process_name`, `process_domain_identifier`, `process_purpose`, `process_classification`, `process_classification_rationale`, `process_notes`, `process_created_at`, `process_updated_at`, `process_deleted_at`), correct types and constraints, and runs both forward and backward without error.

2. **`process_identifier` format constraint enforced.** Insertions with `process_identifier` not matching `^PROC-\d{3}$` raise a validation error at the access layer.

3. **`process_name` uniqueness enforced engagement-globally and case-insensitively.** Inserting a second row whose `process_name` matches an existing row by lowercase comparison raises a uniqueness violation, regardless of `process_domain_identifier`.

4. **`process_classification` enum and transition validation.** Insertions with `process_classification` outside `{unclassified, mission_critical, supporting, deferred}` are rejected. PATCH/PUT requesting an invalid transition (e.g., `mission_critical` → `unclassified`) returns HTTP 422 with `{"error": "invalid_classification_transition", "from": ..., "to": ...}`.

5. **`process_domain_identifier` FK validation.** Insertions with `process_domain_identifier` not matching `^DOM-\d{3}$`, or referring to a non-existent or soft-deleted domain, return HTTP 422 with `{"error": "invalid_domain_reference", "domain_identifier": ...}`.

6. **Access-layer methods exist with expected signatures.** `client.list_processes()`, `client.get_process(identifier)`, `client.create_process(...)`, `client.update_process(identifier, ...)`, `client.patch_process(identifier, ...)`, `client.delete_process(identifier)`, `client.restore_process(identifier)`, `client.next_process_identifier()` exist and pass unit tests covering happy path and at least one error case each.

7. **REST endpoints return expected responses for representative cases.** All eight endpoints from section 3.5 return correct HTTP status and JSON bodies for happy-path and validation-failure cases; 4xx errors use the v2 error envelope.

8. **Identifier auto-assignment helper returns next ID without race conditions.** `GET /processes/next-identifier` returns `{"next": "PROC-NNN"}` for the next available number. POST with `process_identifier` omitted assigns the same value. Two concurrent POSTs do not assign the same identifier (verified by a concurrent-insert test).

9. **Soft-delete and restore round-trip correctly.** DELETE sets `process_deleted_at`; the record disappears from `GET /processes`. `GET /processes?include_deleted=true` shows it. POST `/restore` clears `process_deleted_at`; the record reappears in the default list. Restore on a record that is not soft-deleted returns 422.

10. **`Processes` sidebar entry appears under the Methodology group, position #3.** After Domains and Entities, before CRM Candidates (all four ship together in v0.4).

11. **Master pane columns and default sort.** The Processes panel shows columns Identifier / Name / Classification / Updated, sorted by Identifier ascending. Right-click context menu offers New / Edit / Delete / Restore.

12. **Detail pane renders all fields in section-3.2 order.** Identifier (read-only), Name, Domain (combo box backed by live domains), Purpose, Classification, Classification Rationale, Notes (collapsed under "Internal notes" header), ReferencesSection with separate Hands-off-to and Receives-from sub-sections — all present and bound to the correct fields.

13. **CRUD dialogs work end to end.** Create assigns identifier server-side, persists all fields including the FK to domain, surfaces server-side validation errors inline. Edit persists field changes including classification transitions and domain re-affiliations. Delete prompts for edge-text confirmation (user types the identifier) and soft-deletes on confirm. Restore reappears the record.

14. **`process_hands_off_to_process` registered, constrained, and round-tripping correctly.** `REFERENCE_RELATIONSHIPS` includes the new kind. `_kinds_for_pair((process, process))` returns `{process_hands_off_to_process}`. POST `/references` with `(process, process)` and an unsupported kind returns 422. The Alembic migration extends the `refs.relationship_kind` CHECK constraint; direct DB insert with an unknown kind is rejected. POST `/references` with `source_type=process, source_id=PROC-NNN, target_type=process, target_id=PROC-MMM, relationship_kind=process_hands_off_to_process` creates the row. Fetching either endpoint surfaces the reference in its detail-pane ReferencesSection in the appropriate direction (outbound on source; inbound on target). Soft-deleting either endpoint leaves the reference in place; restoring either side keeps the reference live.

15. **Sample CBM-redo Phase 1 Prioritized Backbone authored through the UI.** A consultant can author roughly 8-12 process records spanning 3-4 domains (e.g., Mentor Application Screening in MR, Mentor-Mentee Matching in MN, Mentor Recruit in MR, Client Recruit in CR, Mentor Onboarding in MR, Mentoring Session in MN, etc.), affiliate each to its parent domain via the create-dialog combo, classify them as mission-critical / supporting / deferred via the classification combo, populate purpose and classification rationale, attach `process_hands_off_to_process` references representing the workability-checked handoff chain (e.g., Mentor Recruit → Mentor Application Screening → Mentor Onboarding → Mentor-Mentee Matching → Mentoring Session), and the records, classifications, FK affiliations, and references all persist correctly across application restart and across REST/MCP refetch.

### 3.8 Open Questions and Deferred Decisions

Categorized per the spec guide section 3.8 convention. Each entry is one paragraph with an explicit category tag.

#### 3.8.1 For v0.4 build to settle

**[v0.4 build] Create-dialog handoff flow.** Two reasonable UI patterns for letting the user attach `process_hands_off_to_process` references at create time, mirroring `entity.md`'s deferred decision on its affiliation create-flow: (a) create-then-attach (the New dialog creates the process only; the user adds handoffs from the detail pane afterward); (b) create-with-attach (the New dialog includes upstream/downstream multi-selects; on submit the UI runs POST `/processes` then N × POST `/references` in sequence). The v0.4-build-planning conversation decides which pattern is implemented, ideally coordinating with the parallel `entity` affiliation decision so both panels behave consistently.

**[v0.4 build] Concurrent identifier-assignment behavior.** The mechanism for preventing two concurrent POSTs from assigning the same `PROC-NNN` (row-level locking, optimistic retry, advisory locks, etc.) is implementation-level and not specified by this spec. Acceptance criterion #8 requires correctness; the *how* is the v0.4 build's call, consistent with whatever pattern the `domain` and `entity` builds adopt.

**[v0.4 build] Cross-spec consistency check on inbound vocabulary.** Once `crm_candidate.md` lands, the v0.4-build-planning conversation's cross-spec consistency check verifies that no relationship-kind name collisions exist between the four schemas' vocabulary additions. The expectation is no collision (`process_hands_off_to_process` and `entity_scopes_to_domain` are clearly distinct), but the check is the formal gate.

#### 3.8.2 For CBM redo to surface

**[CBM redo] Markdown for `process_purpose` and `process_classification_rationale`.** Both fields are plain text in v0.4. The CBM redo's actual Phase 1 work will reveal whether purposes or rationales need emphasis, bullet lists, or inline links. If so, a v0.5 migration introduces markdown rendering on these fields. The decision deliberately waits on real-use signal rather than speculating in design.

**[CBM redo] Text-field length caps.** No storage-level length constraints in v0.4; UI placeholder text provides soft guidance. If the CBM redo produces pathological inputs (5000-character "one-sentence purposes," sprawling rationales), caps are added via migration in v0.5. Same posture as `domain` and `entity`.

**[CBM redo] `process_notes` structure.** Flat plain text in v0.4. If consultant notes accrete substantially across an engagement, a structured-journal pattern becomes a v0.5 candidate. Same posture as `domain_notes` and `entity_notes`.

**[CBM redo] One-way `unclassified` gate.** Section 3.4.2 prohibits regression from any classified value back to `unclassified`. The CBM redo will surface whether this constraint creates friction in practice; if so, a v0.5 transition-map amendment can open up regression paths.

**[CBM redo] Domain re-affiliation friction.** Section 3.5.4 permits PATCH/PUT to change `process_domain_identifier` to a different live domain. The CBM redo will surface whether re-affiliation happens often enough to warrant additional UI affordances (a dedicated "Re-affiliate" button, a domain-change audit trail, a warning when re-affiliation would change which references render on each side).

**[CBM redo] Self-loop handoffs.** Section 3.3.1 permits `process_hands_off_to_process` edges where source and target are the same process record. Unusual but not prevented. The CBM redo will surface whether self-loops occur in practice (a process whose iterations feed each other across cycle boundaries) and whether the UI needs special rendering for them.

**[CBM redo] Master-pane Domain column.** Section 3.6.2 defers the Domain column to v0.5+ paired with PI-007 short codes. The CBM redo will validate whether scanning process-to-domain affiliation at the master pane is high-value, or whether the detail-pane domain combo plus the Phase 1 output document's domain-grouped render together suffice. The signal feeds PI-009 prioritization (the parallel column for Entities) and a new follow-on PI if Processes needs its own.

#### 3.8.3 For v0.5+

**[v0.5+] PI-003 — `persona` entity type.** Already tracked. Phase 3 Process Documents identify which personas perform each step of a process; once `persona` lands, a `persona_performs_process` (or step-level) relationship attaches the data. No v0.4 impact for `process`.

**[v0.5+] PI-004 — additional methodology entity types (`field`, `requirement`, `manual_config`, `test_spec`).** Already tracked. Once `field` lands, the process-to-entity touch relationship (`process_touches_entity` working name, possibly decomposed into read/create/update/delete kinds) attaches via the references entity. PI-005 absorbs the schema-level work; the vocabulary additions land at that time.

**[v0.5+] PI-005 — full process schema growth beyond Phase 1 thin shape.** Already tracked. Steps (ordered sub-actions), actors (which personas perform which step), entity-field touches, triggers, outcomes, cycle time, frequency, volume, sub-process hierarchy. Phase 3 territory. Process-to-entity vocabulary, persona-to-process vocabulary, and step-to-process vocabulary all defer to this PI.

**[v0.5+] PI-007 — `domain.short_code` field.** Already tracked. Joint enabler for the master-pane Domain column on the Processes panel (parallel to PI-009 on the Entities panel).

**[v0.5+] PI-011 — Future scalar implementation-priority field.** New planning item authored at this conversation's close. Adds a separate scalar priority field (working name `process_priority`, values `critical | high | medium | low` or similar) for ranking processes for implementation effort *within* their methodology classification bucket. Distinct from `process_classification`: classification is the methodology's mission-criticality bucket (Backbone / Supporting / Deferred); priority is the implementation-ranking scalar (which mission-critical process do we build first?). Deferred because Phase 1 does not formally produce per-process implementation priority — that emerges from Phase 2 Slice Planning, which v0.4 does not yet host as content. When Phase 2 (Slice Planning) iteration entities land in v0.5+, the scalar priority field is part of that work.

**[v0.5+] Process definitional-completeness lifecycle field.** Anticipated v0.5+ work tracked under PI-005. The deviation rationale in section 3.4.1 names this field's absence in v0.4 (working name `process_definition_level` or similar) as a direct consequence of v0.4 carrying only the Phase 1 "identified" level. When PI-005 introduces detailed-process schema content, the lifecycle field returns to mark which records are at which level of completeness.

### 3.9 Cross-References

#### 3.9.1 Decisions cited by this spec

The following five decisions are authored by running `crmbuilder-v2/scripts/apply_close_out.py` against `PRDs/product/crmbuilder-v2/close-out-payloads/ses_014.json` at conversation close. Each is linked to SES-014 via a `decided_in` reference recorded in the same payload. The DEC numbers assume SES-012 and SES-013 close-out payloads have been applied first; if not, numbers shift accordingly and are recomputed at payload-generation time.

- **DEC-055 — `process` identifier prefix and format.** Adopts `PROC` (four letters) under `domain.md`'s soft-3-letter posture explicit deviation clause; three-letter `PRC` rejected for ambiguity (see section 3.1).
- **DEC-056 — `process` field inventory under minimum-viable v0.4 scope, with no-status-field deviation rationale and engagement-global name uniqueness.** Three substantive content fields (`process_purpose` required; `process_classification_rationale` optional; `process_notes` optional); no `process_description` separate from purpose; direct FK to domain (`process_domain_identifier` required); engagement-global case-insensitive uniqueness on `process_name` mirroring domain/entity precedent (rejects the per-domain-unique alternative because handoff lists and other downstream renderers reference process names without domain context — see section 3.2.1); no storage-level length caps; no status field (rationale in section 3.4.1 — `domain`/`entity` use `status` for engagement-scope lifecycle, `process` uses `process_classification` for that role, and no second field is needed); parent-prefix field naming inherited from DEC-046 without re-establishment (see section 3.2).
- **DEC-057 — `process_classification` field with `unclassified` default and four-value enum.** Values: `unclassified | mission_critical | supporting | deferred`. Default `unclassified` reflects the Session-1-capture-before-classification state explicitly named in the Phase 1 interview guide. Transitions: one-way out of `unclassified`; free movement among the three classified values per Principle 7. Replaces the working name `process_priority` (proposed during the conversation; rejected for conventional-priority semantic mismatch — see section 3.2.3). Future scalar implementation-priority field tracked separately as PI-011 (see section 3.9.1 reference to that PI).
- **DEC-058 — `process` relationship architecture: direct FK for domain affiliation, references-entity edge for process-to-process handoffs (directional, `process_hands_off_to_process`), defer process-to-entity entirely.** Domain affiliation via `process_domain_identifier` column (many-to-one, settled cardinality, no references-table involvement, no vocab registration). Process-to-process handoffs via references entity with new `process_hands_off_to_process` kind registered in `REFERENCE_RELATIONSHIPS` and `_kinds_for_pair`; directional (source = producer, target = consumer) reflecting the methodology's directional handoff language; Alembic migration extends the CHECK constraint. Process-to-entity touches deferred entirely (no vocab registration in v0.4) because Phase 1 does not formally produce this data and Phase 3 may need finer-grained kinds (PI-005 tracks).
- **DEC-059 — `process` API surface, UI defaults, and acceptance criteria for v0.4.** Standard endpoint set with no deviations; decomposed reference handling for handoffs (matching `entity.md` decomposed posture for affiliations); default `ListDetailPanel` UI under the existing Methodology sidebar group at position #3; master-pane Domain column deferred to v0.5+ paired with PI-007 (mirroring `entity.md`'s posture); detail pane renders bidirectional `process_hands_off_to_process` references in separate Hands-off-to and Receives-from sub-sections; create-dialog handoff flow (create-then-attach vs create-with-attach) left as a v0.4-build decision matching the open question on `entity` affiliations; 15 testable acceptance criteria (see sections 3.5, 3.6, 3.7).

#### 3.9.2 External references

- `crmbuilder/CLAUDE.md` — universal session-startup entry; documents the `REFERENCE_RELATIONSHIPS` / `_kinds_for_pair` / Alembic-migration triad that section 3.3.1's mechanical additions follow.
- `PRDs/product/crmbuilder-v2/methodology-schema-workstream-plan.md` — workstream master plan governing this and the remaining schema-design conversation.
- `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md` — schema spec template this document follows.
- `PRDs/product/crmbuilder-v2/schema-design-kickoff-process.md` — this conversation's seed prompt.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/domain.md` — first predecessor spec; source of inherited conventions (parent-prefix field naming, `{source}_{verb}_{target}` relationship-kind naming, soft-3-letter prefix posture, rejection-via-soft-delete posture, no-archived posture).
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/entity.md` — second predecessor spec; source of inherited conventions (decomposed reference handling for create dialogs, master-pane column deferral posture paired with PI-007).
- `PRDs/process/research/evolved-methodology/phase-1-interview-guide.md` v0.2 — section 3.5 (process surfacing in Session 1 Part C, with the explicit "do not yet propose classification — that's between-session work" discipline at line 237); section 4.1 (between-session drafting; classification + handoff identification + workability check); section 7.3 (Prioritized Backbone output specification including per-process name + domain + one-sentence purpose + mission-critical reasoning + handoffs).
- `PRDs/process/research/evolved-methodology/evolved-methodology-phase-outline.md` — section 2 Principle 3 (priority is established at the process level); Principle 7 (decisions are locked, priority is not); section 3 Phase 1 / Phase 3 boundary.

#### 3.9.3 Related prior decisions informing this spec

- **DEC-006** — Universal references table as the cross-entity-type edge store. Direct architectural foundation for the `process_hands_off_to_process` mechanism choice in section 3.3.1.
- **DEC-035** — `ListDetailPanel` master-widget + context-menu factory refactor. Informs master pane patterns in section 3.6.2.
- **DEC-036** — Right-click context menus uniform across all entity rows. Informs context-menu behavior in section 3.6.2.
- **DEC-039** — Minimum entity inventory and multi-tenancy posture. Directly justifies `process`'s inclusion in v0.4's minimum-viable set as a Phase 1-driven content entity.
- **DEC-043** — SES-010 identifier-asymmetry resolution. Mandates the `GET /processes/next-identifier` helper endpoint cited in section 3.5.1.
- **DEC-044** — `domain` identifier prefix and format; establishes the soft-3-letter prefix posture that section 3.1 invokes for `PROC`'s four-letter form.
- **DEC-046** — Parent-prefix field-naming convention for methodology entities. Establishes the field-naming pattern this spec inherits and applies (see section 3.2).
- **DEC-047** — `domain` status lifecycle, propose-verify gate, and rejection-via-soft-delete posture. Establishes the rejection-via-soft-delete cross-spec pattern this spec adopts unchanged (see section 3.4.3), even though `process` does not adopt the rest of the status pattern (see section 3.4.1).
- **DEC-048** — `domain` relationship posture and `{source}_{verb}_{target}` relationship-kind naming convention. Establishes the relationship-kind naming pattern this spec applies in registering `process_hands_off_to_process` (see section 3.3.3).
- **DEC-049** — `domain` API surface, UI defaults, acceptance criteria for v0.4. Establishes the API-and-UI default patterns this spec adopts (see sections 3.5, 3.6, 3.7).
- **DEC-052** — `entity` status lifecycle adoption. Establishes the cross-spec rejection-via-soft-delete pattern for the second time; this spec adopts the rejection part while diverging on the status field (see section 3.4.1).
- **DEC-053** — `entity`-to-`domain` affiliation mechanism via references-entity edge and `entity_scopes_to_domain` vocabulary registration. Sets the pattern this spec invokes for `process_hands_off_to_process`; differs on the FK-versus-edge choice for the domain-affiliation case because process-to-domain cardinality is many-to-one (settled) rather than many-to-many.
- **DEC-054** — `entity` API surface, UI defaults, deferred Domains-column posture. Establishes the master-pane column-deferral pattern this spec mirrors for the Domain column on the Processes panel (see section 3.6.2).

#### 3.9.4 Predecessor and successor conversations

- **Predecessor:** `entity` schema-design conversation. SES-013 close-out payload at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_013.json`. Produced `entity.md` v1.0, DEC-050 through DEC-054, and PI-009 / PI-010.
- **Successor:** `crm_candidate` schema-design conversation. Kickoff at `PRDs/product/crmbuilder-v2/schema-design-kickoff-crm_candidate.md`. Will inherit the conventions established by `domain.md` and applied by `entity.md` and this spec (parent-prefix field naming, `{source}_{verb}_{target}` relationship-kind naming, soft-3-letter prefix posture with explicit deviation clause, status-lifecycle shape with explicit deviation allowed when methodology semantics warrant). The cross-spec consistency check at the v0.4-build-planning conversation validates that the four schemas' vocabulary additions do not collide.

---

*End of document.*

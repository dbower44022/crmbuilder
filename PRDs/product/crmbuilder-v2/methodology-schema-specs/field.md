# Methodology Entity Schema Spec — `field`

**Last Updated:** 05-25-26 12:00
**Status:** Draft v1.0 — produced under PI-004
**Position in workstream:** Most urgent of three independent v0.5+ entity specs satisfying PI-004 (the others being `persona` under PI-003 and the remaining PI-004 trio: `requirement`, `manual_config`, `test_spec`). Sequenced first because the existing `entity` schema (shipped thin in v0.4) gains real utility only when fields can attach.
**Predecessor schemas in workstream lineage:** `domain.md` → `entity.md` → `process.md` → `crm_candidate.md` → `engagement.md` (conventions inherited; no per-conversation predecessor in the v0.4 four-conversation workstream sense).
**Companion documents:** `methodology-entity-schema-spec-guide.md` (template); `entity.md` (parent entity type fields attach to).

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-25-26 12:00 | Doug Bower / Claude | Initial draft. Produced under PI-004 as the most urgent of the v0.5+ methodology entity types. Defines `field` as the v2 methodology entity type that captures one attribute on a CRM-modeled entity, surfaced in evolved-methodology Phase 3 iteration build conversations and feeding the downstream YAML deploy spec. Inherits conventions established by `domain.md` and applied across `entity.md` / `process.md` / `crm_candidate.md` / `engagement.md` (parent-prefix field naming per DEC-046, source-first `{source}_{verb}_{target}` relationship-kind naming per DEC-048, soft-3-letter prefix posture, three-status propose-verify lifecycle). Establishes `field_belongs_to_entity` as the first methodology-side many-to-one (1:1 mandatory at the access layer) references-entity edge, with the discipline rationale that field tables stay small and the reference store stays the uniform shape for methodology cross-edges. |

---

## Change Log

**Version 1.0 (05-25-26 12:00):** Initial creation. Defines seven substantive fields (`field_identifier`, `field_name`, `field_description`, `field_type`, `field_required`, `field_notes`, `field_status`) plus inherited timestamps; an 11-value v0.5 field-type vocabulary (`text` / `long_text` / `enum` / `multi_enum` / `date` / `datetime` / `money` / `boolean` / `number` / `reference` / `derived`) with richer typing (`formula`, `link`) deferred to v0.6+; three-status lifecycle mirroring `domain` and `entity` (`candidate` / `confirmed` / `deferred`) with one-way propose-verify gate; mandatory 1:1 affiliation to a parent entity via the new `field_belongs_to_entity` references-entity edge (single edge per field enforced at the access layer); per-entity-scoped uniqueness of `field_name` (the same client-language column name may appear on more than one entity); no FK columns on the field table; standard endpoint set with decomposed reference handling and a single deviation around POST atomicity (the parent entity reference is required in the POST body so the row + edge land in one transaction). Six decisions produced (DEC-246 through DEC-251) and seven new planning items (PI-053 through PI-059). Acceptance criteria captured as 17 testable statements, four of which specifically cover the parent-entity edge mechanism, cardinality enforcement, and POST atomicity.

---

## 1. Purpose and Position

This document specifies the `field` entity type for v2's storage layer. It resolves the first (and most urgent) portion of **PI-004**, the planning item that tracks v0.5+ methodology entity types beyond the four-spec v0.4 workstream. `field` is sequenced ahead of `persona` (PI-003), `requirement`, `manual_config`, and `test_spec` because the existing `entity` schema — shipped thin in v0.4 under `entity.md` — gains real methodology utility only when its attributes can be captured against it. Until fields can attach, an `entity` record holds a name, a description, an optional notes scratchpad, and lifecycle status; the question "what data does the CRM need to capture for this entity?" has no home.

The schema follows the template in `methodology-entity-schema-spec-guide.md` and inherits the conventions established by `domain.md` and applied unchanged across `entity.md`, `process.md`, `crm_candidate.md`, and `engagement.md`:

- **Parent-prefix field naming** (DEC-046): all non-identifier, non-timestamp fields are prefixed with the parent entity name. All fields including identifier and timestamps adopt the prefix for full convention consistency.
- **`{source}_{verb}_{target}` relationship-kind naming** (DEC-048): vocabulary entries involving methodology entities are named source-first, with the source entity name, a verb phrase, and the target entity name.
- **Soft-3-letter identifier prefix posture** (DEC-044): `FLD` is three letters and reads unambiguously as "field" with no collision against the existing prefix space (DEC, SES, RSK, PI, TOP, REF, CHR, STA, DOM, ENT, PROC, CRM, WS, CONV, RB, WT, COP, DEP, CM).
- **Three-status propose-verify lifecycle** (DEC-047): `candidate` / `confirmed` / `deferred`, with a one-way propose-verify gate (no regression from `confirmed` or `deferred` back to `candidate`) and rejection-via-soft-delete.

The methodology `field` entity is **not** the deploy-side YAML field declaration documented in `PRDs/product/app-yaml-schema.md` Section 6. The two are cognate — both describe one attribute on an entity — but they live at different layers and answer different questions. The methodology field is the upstream record produced in evolved-methodology Phase 3 iteration build conversations: a client-language name, a plain-text description, a methodology-level type-shape, a methodology-level required-ness signal, and a lifecycle status. The deploy-side YAML field is the downstream artifact generated from (or hand-authored alongside) the methodology record: the EspoCRM-specific `lowerCamelCase` internal name, the platform-specific type enum, the layout category, the formula block, the conditional-visibility expression, all of which the deploy engine consumes via `validate_program()` and the field manager.

The thinness of the v0.5 shape is deliberate. Phase 3 iteration build conversations surface fields naturally as the consultant walks the client through what data each in-scope entity must capture; v0.5 captures that surfacing without preempting the downstream YAML deploy decisions. Richer methodology-level constructs (formula expressions, derived-field lineage tracing per DEC-038, validation-rule capture, field-to-field dependencies, history/audit, default values, role-based field permissions) are deferred to v0.6+ with explicit planning items.

---

## 2. Summary

A `field` record in v2 represents one attribute on one CRM-modeled entity — `mentor_status` on Mentor, `email_address` on Contact, `payment_date` on Dues, `topics_covered` on Session. Phase 3 iteration build conversations surface fields naturally as the consultant walks the client through what data each in-scope entity must capture; the consultant captures them as `field` records so the downstream YAML deploy spec, manual-config artifact, and verification spec can be generated from settled methodology records rather than retrofitted from prose. Each `field` record holds a client-language name, a brief plain-text description of what the field conceptually represents, a methodology-level type drawn from an 11-value vocabulary, a methodology-level required-ness boolean, an optional internal-notes scratchpad for consultant rationale, and a lifecycle status tracking whether the field is a CRM-Builder-proposed candidate, a client-confirmed in-scope attribute, or an acknowledged-but-deferred capture. Parent-entity affiliation — which `entity` record this field belongs to — is captured as a mandatory single `field_belongs_to_entity` reference in v2's universal references store, supporting the discipline that the field table stays small and cross-entity edges share one uniform mechanism.

The schema in v0.5 is the thinnest shape that can faithfully host Phase 3 iteration build surfacing. It deliberately omits formula expressions at the methodology level, derived-field lineage tracing (DEC-038's posture lands here in v0.6+ when the access-layer machinery exists), validation-rule capture beyond required/not-required, field-to-field dependencies, field history and audit, default values, role-based field permissions, multi-entity scoping (a field belongs to exactly one entity in v0.5; cross-entity field reuse is handled by authoring twin records), and any process-touches-field edges from the source-side `process` spec. All of these are tracked as planning items for v0.6+ with explicit CBM-redo signal as the gating consideration on most.

---

## 3. Schema Specification

### 3.1 Identity

| Field | Value |
|-------|-------|
| Entity type name (storage) | `field` |
| Display name (singular) | Field |
| Display name (plural) | Fields |
| Identifier prefix | `FLD` |
| Identifier format | `FLD-NNN`, zero-padded to 3 digits (e.g., `FLD-001`, `FLD-042`) |
| Identifier auto-assignment | Server-side on POST omission per PI-002; helper at `GET /fields/next-identifier` per DEC-043 |

`FLD` is three letters and adheres to the soft-3-letter prefix posture established in `domain.md` section 3.1. The prefix reads unambiguously as "field", has no collision with existing prefixes (DEC, SES, RSK, PI, TOP, REF, CHR, STA, DOM, ENT, PROC, CRM, WS, CONV, RB, WT, COP, DEP, CM), and matches the existing v2 governance-entity norm. No deviation from defaults; the identifier-asymmetry helper endpoint per DEC-043 ships alongside the standard endpoint set, and `POST /fields` accepts `field_identifier: null` (or omitted) under the PI-002 server-assignment rule.

### 3.2 Fields

Field naming follows the parent-prefix convention established by `domain.md` (DEC-046) and applied across the four v0.4 specs: all non-identifier, non-timestamp fields are prefixed with the parent entity name (`field_`). All fields including identifier and timestamps adopt the prefix in v0.5 for full convention consistency.

#### 3.2.1 Identity fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `field_identifier` | TEXT | yes | server-assigned | `^FLD-\d{3}$`, unique | The methodology-entity identifier in `FLD-NNN` format. Server-assigned when omitted from POST body per PI-002. |
| `field_name` | TEXT | yes | — | non-empty trimmed; case-insensitive unique within the parent entity (see 3.2.3 note) | Field name in the client's language (e.g., "mentor_status", "email_address", "payment_date", "topics_covered"). Methodology-level naming — `snake_case` is conventional but not enforced; the downstream YAML deploy spec converts to platform-specific naming. |

#### 3.2.2 Content fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `field_description` | TEXT | yes | — | non-empty trimmed | Brief description of what this field conceptually represents (e.g., "Tracks the lifecycle stage of a mentor — proposed candidate, active engagement, departed"; "Primary email address used for application correspondence and ongoing program communication"; "Date the mentor paid annual dues, recorded when payment is reconciled"). Plain text in v0.5; markdown support deferred to CBM-redo signal. |
| `field_notes` | TEXT | no | — | — | Internal consultant scratchpad. Not part of any client-facing render and not consumed by the downstream YAML deploy spec. Used to capture pattern-library rationale, push-back trails, between-session reasoning about why the field exists in the form it does, prior-engagement-CRM history, etc. Plain text in v0.5. |

**No `field_default_value` in v0.5.** Default values are a deploy-side concern (YAML schema Section 6.1, `default:`) — the methodology record captures *that* the field is captured, not what value it starts with. The CBM redo will surface whether consultants need to capture defaults at the methodology level (e.g., for fields whose default carries methodology meaning rather than convenience); if so, a v0.6 migration adds the field. Tracked as PI-055.

**No `field_label` in v0.5.** Display labels are a deploy-side concern. The methodology record carries one name (`field_name`); when the YAML deploy spec is generated from the methodology record, the label is derived from the name or hand-authored alongside the YAML.

#### 3.2.3 Classification fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `field_type` | TEXT | yes | — | enum: `text` \| `long_text` \| `enum` \| `multi_enum` \| `date` \| `datetime` \| `money` \| `boolean` \| `number` \| `reference` \| `derived` | Methodology-level type shape. Eleven values in v0.5; richer types (`formula`, `link`, `address`, `phone`, `url`) deferred to v0.6+ per PI-054. The vocabulary is intentionally narrower than the YAML deploy schema's type list — methodology cares about the shape of the value (is it text? a date? a category drawn from a list? a pointer to another entity?), not the platform-specific rendering. |
| `field_required` | BOOLEAN | yes | `false` | — | Whether the field is required at the methodology level — i.e., the client has indicated this attribute must be captured for every record of the parent entity. Methodology-only signal; the deploy-side `required: true` and `requiredWhen:` (YAML schema Section 6.1.1) are downstream artifacts that may or may not follow the methodology signal exactly. Required-ness rules richer than a single boolean (conditional requirement based on other field values, role-based requirement) deferred to v0.6+ per PI-056. |
| `field_status` | TEXT | yes | `candidate` | enum: `candidate` \| `confirmed` \| `deferred`; valid transitions per section 3.4 | Lifecycle status. See section 3.4 for the transition map. |

**`field_name` uniqueness is scoped per parent entity, not globally.** A `Contact` may have a "status" field (`FLD-NNN` with `field_name = "status"`, `field_belongs_to_entity` → `ENT-001`) and a `Mentor` may also have a "status" field (`FLD-MMM` with `field_name = "status"`, `field_belongs_to_entity` → `ENT-002`); both are valid because uniqueness is enforced on the `(parent_entity_identifier, field_name)` pair, not on `field_name` alone. The access layer resolves the parent entity by querying the `field_belongs_to_entity` edge before evaluating uniqueness — see section 3.5 for the POST-time atomicity story. The CBM history's pattern of repeating common fields ("email_address", "phone_number", "notes") across multiple entity types makes per-entity scoping the only sane discipline.

#### 3.2.4 Relationship fields

None in v0.5. `field` has no outgoing FK columns on its table. The mandatory parent-entity affiliation is captured via the references entity (see section 3.3.1) rather than as an FK column, in keeping with the references-first discipline established in DEC-006 and consistent with how `entity_scopes_to_domain` is handled in `entity.md`. The 1:1 mandatory cardinality is enforced at the access layer rather than at the schema layer.

#### 3.2.5 Timestamp fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `field_created_at` | DATETIME | yes | server-set on insert | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `field_updated_at` | DATETIME | yes | server-set on insert and on each update | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `field_deleted_at` | DATETIME | no | null until soft-delete | ISO 8601 UTC when set | Inherited base behavior. Set on DELETE; cleared on POST `/restore`. |

**No storage-level length caps.** Text fields are unconstrained at the storage layer in v0.5. The UI provides soft guidance via placeholder text ("Brief description", "Internal notes"). Pathological-input handling deferred to CBM-redo signal; length caps are easy to add via migration in v0.6 if needed. This mirrors the posture in `domain.md` and `entity.md`.

### 3.3 Relationships

#### 3.3.1 Outgoing relationships

`field` declares one outgoing relationship kind in v0.5: `field_belongs_to_entity`.

| relationship_kind | source | target | mechanism | cardinality | semantics |
|-------------------|--------|--------|-----------|-------------|-----------|
| `field_belongs_to_entity` | `field` | `entity` | references-entity edge | many-to-one (1:1 mandatory at the source side) | A field belongs to exactly one entity. Every live (non-soft-deleted) field MUST have exactly one outgoing edge of this kind. An entity may have zero, one, or many inbound `field_belongs_to_entity` edges. |

The mechanism is the references entity at v2's `refs` table, governed by the existing `RELATIONSHIP_RULES` infrastructure (DEC-006). The choice over a direct FK column (`field_entity_identifier` on the `fields` table) is per **DEC-249**, and the rationale is worth stating in full because the relationship is strictly 1:1 and mandatory — the conditions under which a direct FK is sometimes argued cleaner:

**Why references, not FK:**

1. **References-first discipline.** Every methodology-to-methodology cross-edge in the workstream so far (`entity_scopes_to_domain`, `process_handles_off_to_process`, `crm_candidate_evaluated_against_engagement`, etc.) uses the references store. Introducing the first FK column for a methodology cross-edge would break the discipline and create a "sometimes FK, sometimes references" decision tree that every subsequent spec would have to relitigate. The cost of *not* breaking the discipline is a small amount of access-layer machinery to enforce the 1:1 mandatory cardinality; the cost of breaking it is a permanent architectural inconsistency.
2. **Uniform edge-query semantics.** Listing all fields on an entity is `GET /references?source_type=field&target_id=ENT-NNN&relationship_kind=field_belongs_to_entity` — the same shape as listing all entities on a domain or all processes on a domain. The MCP tools, the desktop `ReferencesSection` widget, and the inline-affiliation patterns all work without special-casing.
3. **Anticipated future edges.** `process_touches_field` (PI-005), field-to-field dependencies (PI-057), derived-field lineage (DEC-038's posture realized under PI-058) are all references-edge designs. Once `field` participates in the references store as the source of `field_belongs_to_entity`, those future edges plug in without re-architecting.
4. **Soft-delete and restore consistency.** The references store handles soft-delete and restore of edges uniformly; an FK column would need bespoke handling for the case where the parent entity is soft-deleted (cascade? reject? null-out?) that the references store has already settled.
5. **Cardinality enforcement is access-layer logic, not schema logic.** The references store has no native 1:1-mandatory cardinality constraint, but the access layer's `create_field()` method enforces it atomically (see section 3.5.4 on POST atomicity). The enforcement is a single small block of code in one place; an FK column would push the same logic into the schema migration and the column constraints, distributing complexity across more surfaces.

**Why not FK (the alternative rejected):**

- A direct FK column (`field_entity_identifier TEXT NOT NULL REFERENCES entities(entity_identifier)`) would make the cardinality enforcement structural and the `field_name` uniqueness constraint declarable as `UNIQUE (field_entity_identifier, LOWER(field_name))`. Both are real wins on a per-spec basis.
- But the wins are local; the cost (discipline break, query non-uniformity, future-edge friction) is workstream-wide. The methodology workstream has consistently chosen workstream-wide consistency over per-spec local optimization (see `entity.md` section 3.3.1 for the same posture on `entity_scopes_to_domain`).

**Mechanical additions per CLAUDE.md line 48:**

1. `field_belongs_to_entity` added to `REFERENCE_RELATIONSHIPS` in `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`.
2. `_kinds_for_pair` extended so `(field, entity)` returns `{field_belongs_to_entity}` (the only kind for this pair in v0.5).
3. Alembic migration extending the `refs.relationship_kind` CHECK constraint to include the new value.

**Cardinality and validation:**

- 1:1 mandatory on the source side. Every live `field` record must have exactly one live outgoing `field_belongs_to_entity` edge. Zero edges and more-than-one edges are both invalid.
- Zero-or-many on the target side. An `entity` record may have zero, one, or many inbound `field_belongs_to_entity` edges.
- Source must be a live field record; target must be a live entity record. (Existing access-layer rules for the references table.)
- Duplicate `(source_id, target_id, relationship_kind)` tuples are rejected by the references-table uniqueness constraint.

**Lifecycle semantics:**

- Soft-deleting a field also soft-deletes the field's outgoing `field_belongs_to_entity` edge (so the live-edge invariant holds at all times for live fields). Restoring a field restores the edge.
- Soft-deleting an entity does NOT cascade-soft-delete its inbound `field_belongs_to_entity` edges or their source fields; the fields persist and, if the entity is restored, the edges are still live. If the entity is not restored, the fields enter an inconsistent state visible to the show-deleted-on-the-entity-side UI toggle. The CBM redo will surface whether this leniency is right or whether soft-deleting an entity should cascade to its fields; tracked as PI-059.

**The verb "belongs to" means:** this field is owned by, declared on, an attribute of this entity. It is a containment notion: the field has no meaningful existence apart from its parent entity, in the way that a database column has no meaning apart from its parent table.

#### 3.3.2 Inbound relationships (anticipated; declared by future source-side specs)

`field` is the anticipated target of references from `process` (extended under PI-005), from a v0.6+ field-to-field dependency mechanism (PI-057), and from a v0.6+ derived-field lineage mechanism (PI-058 realizing DEC-038). None of these are declared in v0.5; their formal vocabulary registration belongs to the source-side specs that introduce them. This subsection exists for forward awareness; the `field` panel's `ReferencesSection` widget will render inbound references once they exist.

Anticipated inbound kinds (informational from this spec's perspective; declared in their source-side specs):

| relationship_kind | source | target | semantics |
|-------------------|--------|--------|-----------|
| `process_touches_field` (working name; declared by `process.md` extension under PI-005) | `process` | `field` | A process reads or writes records' values for this field. Phase 3 work; the v0.4 thin `process` schema does not capture field-level interaction. |
| `field_depends_on_field` (working name; v0.6+ under PI-057) | `field` | `field` | A field's meaning, validity, or required-ness depends on another field's value. Methodology-level dependency tracking, distinct from the deploy-side `requiredWhen:` / `visibleWhen:` mechanisms. |
| `derived_field_derived_from_field` (working name; v0.6+ under PI-058 realizing DEC-038) | `field` | `field` | A derived field (`field_type = derived`) is computed from one or more source fields. Carries the lineage-tracing posture from DEC-038. |
| `derived_field_traverses_relationship` (working name; v0.6+ under PI-058 realizing DEC-038) | `field` | (relationship-kind value; mechanism TBD) | A derived field's computation crosses a relationship to reach its source field. DEC-038's two-edge lineage shape; mechanism for the second edge is open. |

The cross-spec consistency check at PI-005 build planning validates that no name collisions emerge when `process_touches_field` is registered.

#### 3.3.3 Cross-spec relationship-kind naming convention — adopted, not established

This spec adopts the `{source}_{verb}_{target}` relationship-kind naming convention established by `domain.md` section 3.3.3 (DEC-048). The single vocabulary entry this spec registers (`field_belongs_to_entity`) conforms to the pattern: source entity first, verb phrase, target entity. The convention is not re-decided here; it carries forward from the workstream lineage.

#### 3.3.4 Hierarchy

`field` does not use the self-referential parent-child hierarchy pattern in v0.5. Field-to-field dependency relationships (e.g., the deploy-side pattern where one field's validity or required-ness depends on another field's value) are deferred to v0.6+ under PI-057 and will land as a references-entity edge (`field_depends_on_field` working name) rather than a hierarchy. Derived-field lineage tracing (DEC-038) likewise lands as a references-entity edge rather than a hierarchy.

### 3.4 Lifecycle

#### 3.4.1 Status values

| Status value | Description | Valid predecessors | Valid successors |
|--------------|-------------|--------------------|------------------|
| `candidate` | CRM Builder has proposed; awaiting client verification. **Default starter status.** | (none — starter) | `confirmed`, `deferred` |
| `confirmed` | Client has verified this is a field in scope for the engagement. | `candidate`, `deferred` | `deferred` |
| `deferred` | Client has acknowledged this is a real attribute but capturing it is out of current engagement scope. | `candidate`, `confirmed` | `confirmed` |

The structure mirrors `domain.md` section 3.4.1 and `entity.md` section 3.4.1 exactly; the semantics map cleanly: fields, like domains and entities, are surfaced by the consultant and verified by the client.

#### 3.4.2 Transition semantics

The status lifecycle implements the same **one-way propose-verify gate** established for `domain` (DEC-047): once a field has moved out of `candidate` (in either direction, to `confirmed` or to `deferred`), it does not regress to `candidate`. The rationale: the propose-verify moment is a meaningful client-engagement event; if the consultant later wants to fundamentally rethink a verified field, the right action is to edit the record's content (rename, re-type, re-describe), not to regress its status. Status reflects engagement-scope position, not deliberation state.

Movement between `confirmed` and `deferred` in either direction is permitted to support mid-engagement scope changes (e.g., a field initially confirmed but later deprioritized; a previously-deferred field pulled back into scope at a later iteration build).

#### 3.4.3 Status independence from parent-entity status

A field's `field_status` is its own field on its own table, set by the consultant based on client verification of the field itself. **It is not derived from the status of the parent entity.** This independence matters because a field's lifecycle position is meaningful even when its parent entity is `candidate` (the consultant may be sketching a candidate entity along with its candidate fields, with the goal of verifying both in the same conversation) and conversely the parent entity may be `confirmed` while individual fields are still being negotiated (`Mentor` is in scope, but whether to capture `mentor_status` as an enum or two booleans is still open).

The implication for the UI and access layer: edit affordances on `field_status` do not consult the parent entity's status, and changing an entity's status does not cascade to its inbound `field_belongs_to_entity` edges' source-side records' statuses. The two lifecycles are managed independently. This mirrors the posture established in `entity.md` section 3.4.3 for entity-status-independent-of-domain-status.

#### 3.4.4 Rejection via soft-delete

When the client rejects a CRM-Builder-proposed field candidate ("no, we don't actually need to capture that"), the rejection is handled by soft-delete rather than a `rejected` status value. `DELETE /fields/{field_identifier}` sets `field_deleted_at`; the record persists for audit and history, surfaces under the `?include_deleted=true` toggle, and is restorable via POST `/restore`. This piggybacks v2's existing soft-delete infrastructure rather than introducing a status value that duplicates the mechanism. The cross-spec principle established in `domain.md` section 3.4.3 carries forward unchanged: **status values track engagement-scope lifecycle; soft-delete tracks existence-in-the-record.**

#### 3.4.5 No `archived` status

`archived` is not introduced in v0.5. Soft-delete combined with the "show deleted" toggle already covers the "retained for record, not in active scope" use case. Mirrors `domain.md` section 3.4.4 and `entity.md` section 3.4.5.

#### 3.4.6 Soft-delete semantics

Soft-delete inherits v2's standard behavior with one extension for the mandatory edge:

- DELETE sets `field_deleted_at` to the current ISO 8601 UTC timestamp.
- DELETE also soft-deletes the field's outgoing `field_belongs_to_entity` edge atomically in the same transaction (so the live-edge invariant holds for all live fields).
- Soft-deleted records do not appear in `GET /fields` by default.
- `GET /fields?include_deleted=true` returns soft-deleted records alongside live ones.
- POST `/fields/{field_identifier}/restore` clears `field_deleted_at` AND restores the previously-attached `field_belongs_to_entity` edge in the same transaction. Restore on a record whose previously-attached parent entity is itself soft-deleted returns HTTP 422 with `{"error": "parent_entity_soft_deleted", "parent_entity_identifier": "ENT-NNN"}` — the consultant must restore the parent entity first.
- Restore on a record that is not soft-deleted returns HTTP 422.

### 3.5 API Surface

#### 3.5.1 Endpoints

| Method | Path | Body | Notes |
|--------|------|------|-------|
| GET | `/fields` | — | List endpoint. Returns active records by default. Supports `?include_deleted=true` to include soft-deleted records. Supports `?entity_identifier=ENT-NNN` filter (see 3.5.5). |
| GET | `/fields/{field_identifier}` | — | Single fetch by identifier. Returns 404 if not found. |
| POST | `/fields` | full record minus `field_identifier` (server-assigned), PLUS mandatory `field_belongs_to_entity_identifier` body key for atomic edge creation | Create. Returns 201 with the assigned identifier in the response body. Server-side validation per section 3.2 applied. See 3.5.4 for the POST atomicity deviation rationale. |
| PUT | `/fields/{field_identifier}` | full record | Full replace. `field_identifier` in body must match the path; mismatch returns 422. Does NOT accept `field_belongs_to_entity_identifier` — re-parenting requires separate edge management (delete old edge, create new edge). |
| PATCH | `/fields/{field_identifier}` | partial record | Partial update. Status-transition validation applied (see 3.5.3). Does NOT accept `field_belongs_to_entity_identifier`. |
| DELETE | `/fields/{field_identifier}` | — | Soft-delete; sets `field_deleted_at` AND soft-deletes the outgoing `field_belongs_to_entity` edge atomically. Idempotent (DELETE on an already-soft-deleted record returns 200 with no state change). |
| POST | `/fields/{field_identifier}/restore` | — | Clears `field_deleted_at` AND restores the previously-attached edge atomically. Returns 422 if the record is not soft-deleted; returns 422 if the parent entity is itself soft-deleted (see 3.4.6). |
| GET | `/fields/next-identifier` | — | Returns `{"next": "FLD-NNN"}` for the next available identifier. Per SES-010 resolution (DEC-043). |

**One deviation from the cross-spec default endpoint set** documented in section 3.5.4: POST `/fields` accepts (and requires) an extra body key `field_belongs_to_entity_identifier` so the row + edge land atomically, in keeping with the live-edge invariant on the mandatory 1:1 affiliation. No bulk operations, no webhooks, no event streams.

#### 3.5.2 Identifier auto-assignment

`field_identifier` is server-assigned on POST when omitted from the request body per PI-002. The assignment logic uses the SAVEPOINT-retry helper that is safe under concurrent writes (the same helper used across the v0.4 methodology entity types and the v0.7 governance entity types). The `GET /fields/next-identifier` helper exposes the next-available value for clients that want to know the assigned identifier before POSTing.

#### 3.5.3 Status-transition validation

Status transitions are validated server-side at the access layer. PATCH or PUT requests that specify a `field_status` value that is not a valid successor of the current value (per section 3.4.1) return HTTP 422 with a body of the form:

```
{
  "error": "invalid_status_transition",
  "from": "<current status>",
  "to": "<requested status>"
}
```

The default-`candidate` rule applies on POST: if `field_status` is omitted, the server assigns `candidate`. POST with `field_status` explicitly set to a non-starter value is permitted (e.g., bulk-importing already-confirmed fields from prior engagement records or from a CBM-redo seed-data load).

#### 3.5.4 POST atomicity for the mandatory parent-entity edge

POST `/fields` deviates from the cross-spec default in one bounded way: the request body MUST include `field_belongs_to_entity_identifier` (an `ENT-NNN` value pointing to a live entity record), and the access layer creates the field row, the `field_belongs_to_entity` edge, and any back-references in a single transaction. This is the atomicity story for the live-edge invariant on the 1:1 mandatory affiliation per **DEC-250**.

The decomposed alternative — POST the field row first, then POST the edge via `/references` separately — was rejected because it leaves the field in a transient invalid state (a live field with no live outgoing edge) between the two calls. In a multi-client environment a concurrent reader could observe the invalid state; in a single-client environment a network failure between the two calls leaves the database in a permanent invalid state requiring manual cleanup. The atomic POST avoids both.

Body shape:

```
POST /fields
{
  "field_name": "mentor_status",
  "field_description": "Tracks the lifecycle stage of a mentor",
  "field_type": "enum",
  "field_required": false,
  "field_notes": null,
  "field_status": "candidate",
  "field_belongs_to_entity_identifier": "ENT-002"
}
```

The `field_belongs_to_entity_identifier` body key is consumed by the access layer for edge creation, then stripped before the field row is constructed. It does not become a column on the `fields` table; the parent entity is queryable via the `field_belongs_to_entity` edge in the references store.

Validation:

- `field_belongs_to_entity_identifier` is required on POST. Missing or null returns 422 with `{"error": "missing_parent_entity", "expected": "field_belongs_to_entity_identifier"}`.
- The target entity must exist and be live (not soft-deleted). Otherwise 422 with `{"error": "invalid_parent_entity", "field_belongs_to_entity_identifier": "ENT-NNN", "reason": "not_found" | "soft_deleted"}`.
- The `field_name` uniqueness check is evaluated against the resolved parent entity's existing live fields. Collisions return 422 with `{"error": "duplicate_field_name", "field_belongs_to_entity_identifier": "ENT-NNN", "field_name": "<value>"}`.

PUT and PATCH do NOT accept `field_belongs_to_entity_identifier`. Re-parenting a field to a different entity (rare in practice; typically resolved by deleting and re-creating) requires explicit edge management: DELETE the existing edge via `/references/{ref_identifier}`, POST the new edge via `/references`, in a sequence the desktop UI hides behind a "Move to entity" affordance. Whether to expose a `POST /fields/{field_identifier}/reparent` convenience endpoint is tracked as PI-053 (a v0.5 build decision).

#### 3.5.5 Per-entity list filter

`GET /fields?entity_identifier=ENT-NNN` returns only the fields whose `field_belongs_to_entity` edge points to the named entity. This is a small deviation from the cross-spec default of "only `?include_deleted=true` in v0.5"; the justification is that listing fields on an entity is by far the most common access pattern (the desktop detail pane for an entity needs it, the YAML generator needs it, MCP tool consumers need it), and forcing every caller to fetch all fields and filter client-side is gratuitously wasteful as soon as the field count grows past a few dozen. Server-side filtering on other axes (`?field_status=confirmed`, `?field_type=enum`) deferred to CBM-redo signal per PI-055's general "more filters as needed" trail.

#### 3.5.6 Decomposed reference handling beyond the parent-entity edge

Any future references on a field (anticipated inbound from `process` under PI-005, future field-to-field dependencies under PI-057, future derived-field lineage under PI-058) are managed via the standard `POST /references` / `DELETE /references/{ref_identifier}` shape. The POST atomicity deviation in 3.5.4 applies only to the mandatory `field_belongs_to_entity` edge; everything else follows the v2 references-first discipline (DEC-006).

#### 3.5.7 Other endpoint specifics

- All endpoints return JSON via the v2 `{data, meta, errors}` envelope per the CLAUDE.md v2 API responses note.
- 4xx error responses use the existing v2 error envelope shape.
- No additional list query parameters beyond `?include_deleted=true` and `?entity_identifier=ENT-NNN` in v0.5.

### 3.6 UI Considerations

This spec adopts the spec guide's default `ListDetailPanel` layout with one minor deviation in the master pane (per-entity grouping; see 3.6.2). Specifics for `field` follow.

#### 3.6.1 Sidebar

The "Methodology" sidebar group introduced by `domain.md` section 3.6.1 hosts the new `field` entry. Position #5 in the group, after the four v0.4 methodology entries (with `engagement.md`'s entry added at its appropriate position by that spec's UI placement):

1. Domains
2. Entities
3. Processes
4. CRM Candidates
5. **Fields** (this spec)

Plus `Engagements` at its spec-determined position. `field` ships alone in its v0.5 ship; the other PI-004 entries (`persona`, `requirement`, `manual_config`, `test_spec`) follow as their own specs land.

#### 3.6.2 Master pane

`ListDetailPanel`-backed list with these columns:

| Stored field | Display header | Width | Notes |
|--------------|----------------|-------|-------|
| `field_identifier` | Identifier | narrow | Default sort key, ascending within parent-entity grouping |
| Entity (derived) | Entity | narrow | Renders the parent entity's `entity_identifier`. Sortable; clicking the header re-groups (see deviation note below). |
| `field_name` | Name | wide | Client-language name |
| `field_type` | Type | narrow | Enum value rendered as-is |
| `field_status` | Status | narrow | Enum value rendered as-is |
| `field_updated_at` | Updated | narrow | Localized date/time |

Right-click context menu offers New / Edit / Delete / Restore, consistent with v0.3 governance-entity panels per DEC-035 and DEC-036.

**Master-pane deviation: grouping by parent entity.** The default sort is by Identifier ascending *within* a primary grouping by `entity_identifier` ascending — fields are visually clustered by their parent entity, with section breaks between groups. This deviates from the cross-spec default of a flat identifier-sorted list because the field count grows fast (a single entity may have 20+ fields, a CBM-scale engagement may have 200+ fields total across all entities) and flat-sorting becomes unscannable. The grouped view is the only sane scan affordance at that scale.

The deviation is local to the `field` master pane and does not propagate to other methodology entity types. Clicking the Entity column header toggles to flat sort (a v0.5 build can implement this as a simple group-on/group-off setting persisted in user preferences); clicking the Identifier column header restores the grouped default.

#### 3.6.3 Detail pane

Vertical layout, fields in section-3.2 order:

1. `field_identifier` — read-only label
2. `field_name` — single-line text editor
3. Parent entity — rendered as a read-only label with a "Move to entity" link affordance (consults PI-053 to decide whether the affordance opens a sub-dialog or a bare reference picker)
4. `field_description` — multi-line text editor with placeholder "Brief description of what this field conceptually represents"
5. `field_type` — combo box with the 11 enum values, grouped visually by family (scalar: text / long_text / number / boolean / money / date / datetime; structured: enum / multi_enum / reference / derived)
6. `field_required` — checkbox with label "Required for every record"
7. `field_notes` — multi-line text editor under a collapsible "Internal notes" section header, collapsed by default
8. `field_status` — combo box with the three enum values
9. `ReferencesSection` widget — renders any inbound references once future source-side specs declare them. In v0.5 there are no inbound kinds declared; the widget is still always present for forward consistency. The outgoing `field_belongs_to_entity` edge is rendered separately at position #3 above, not in the generic `ReferencesSection`, because its mandatory 1:1 status makes it conceptually part of the field's identity, not a peer relationship.

The collapsed-by-default treatment of `field_notes` matches `domain_notes` and `entity_notes` — internal consultant scratchpad, not part of any client-facing render.

#### 3.6.4 Create dialog

Modal `EntityCrudDialog` subclass with field order matching the detail pane. Specifics:

- `field_identifier` not shown in create mode (server-assigned).
- Parent entity selector (required) — a combo box or searchable picker populated by `GET /entities?include_deleted=false`. Pre-selected if the dialog was opened from an entity's detail pane via an "Add field" affordance; user-selected if opened from the Fields sidebar entry directly.
- `field_status` defaults to `candidate`; user may select a different starter value if importing established field records.
- `field_required` defaults to `false`.
- Required-field validation client-side before submit; server-side validation errors (uniqueness, format, transition, invalid parent entity) surface inline.

On submit, the dialog POSTs `/fields` with the parent entity identifier in the body per section 3.5.4. The atomic-POST shape means the user authors one form and one server round-trip produces both the field and the edge.

#### 3.6.5 Edit dialog

Same shape as create, with two differences:

- `field_identifier` displayed as read-only label.
- Parent entity displayed as read-only label with a separate "Move to entity" link affordance that opens the re-parenting flow (sub-dialog or bare reference picker per PI-053). The Edit dialog itself does not include a parent-entity editor because re-parenting requires explicit edge management (DELETE then POST), not a PATCH on the field row.

Status transitions enforced per section 3.4.1; invalid selections in the status combo are either prevented (recommended UX) or rejected by the server with the 422 surfacing inline (acceptable fallback).

#### 3.6.6 Delete dialog

`EntityCrudDeleteDialog` with edge-text confirmation. The user types the `field_identifier` value (e.g., `FLD-017`) to enable the Delete button, matching v0.3 governance-entity patterns. Confirmation soft-deletes the record and the outgoing `field_belongs_to_entity` edge atomically per section 3.4.6.

### 3.7 Acceptance Criteria

The following 17 statements define what "this entity type is correctly implemented in v0.5" looks like. Each is concrete and testable; v0.5 build planning translates these into specific test cases.

1. **Schema migration applies cleanly.** Alembic migration creates the `fields` table with all nine columns (`field_identifier`, `field_name`, `field_description`, `field_type`, `field_required`, `field_notes`, `field_status`, `field_created_at`, `field_updated_at`, `field_deleted_at`), correct types and constraints, and runs both forward and backward without error. The same migration extends the `refs.relationship_kind` CHECK constraint to include `field_belongs_to_entity`.

2. **`field_identifier` format constraint enforced.** Insertions with `field_identifier` not matching `^FLD-\d{3}$` raise a validation error at the access layer.

3. **`field_name` uniqueness enforced case-insensitively per parent entity.** Inserting a second field whose `(parent_entity_identifier, lower(field_name))` matches an existing field raises a uniqueness violation. The same `field_name` value on different parent entities is accepted (e.g., `Contact.status` and `Mentor.status` both exist).

4. **`field_type` enum validation.** Insertions with `field_type` outside the 11 v0.5 values (`text`, `long_text`, `enum`, `multi_enum`, `date`, `datetime`, `money`, `boolean`, `number`, `reference`, `derived`) are rejected.

5. **`field_status` enum and transition validation.** Insertions with `field_status` outside `{candidate, confirmed, deferred}` are rejected. PATCH/PUT requesting an invalid transition (e.g., `confirmed` → `candidate`) returns HTTP 422 with `{"error": "invalid_status_transition", "from": ..., "to": ...}`.

6. **Access-layer methods exist with expected signatures.** `client.list_fields(entity_identifier=None, include_deleted=False)`, `client.get_field(identifier)`, `client.create_field(field_belongs_to_entity_identifier, ...)`, `client.update_field(identifier, ...)`, `client.patch_field(identifier, ...)`, `client.delete_field(identifier)`, `client.restore_field(identifier)`, `client.next_field_identifier()` exist and pass unit tests covering happy path and at least one error case each.

7. **REST endpoints return expected responses for representative cases.** All eight endpoints from section 3.5 return correct HTTP status and JSON bodies for happy-path and validation-failure cases; 4xx errors use the v2 `{data, meta, errors}` envelope.

8. **Identifier auto-assignment helper returns next ID without race conditions.** `GET /fields/next-identifier` returns `{"next": "FLD-NNN"}` for the next available number. POST with `field_identifier` omitted assigns the same value. Two concurrent POSTs do not assign the same identifier (verified by a concurrent-insert test using the SAVEPOINT-retry helper).

9. **Soft-delete and restore round-trip correctly, including the mandatory edge.** DELETE sets `field_deleted_at` AND soft-deletes the outgoing `field_belongs_to_entity` edge atomically; the record disappears from `GET /fields`. `GET /fields?include_deleted=true` shows the record and the `?include_deleted=true` references query shows the edge. POST `/restore` clears `field_deleted_at` AND restores the edge atomically. Restore on a record whose previously-attached parent entity is itself soft-deleted returns 422 with `parent_entity_soft_deleted`. Restore on a record that is not soft-deleted returns 422.

10. **`Fields` sidebar entry appears under the Methodology group, position #5.** After Domains, Entities, Processes, CRM Candidates (with Engagements at its spec-determined position).

11. **Master pane columns, grouping, and sort.** The Fields panel shows columns Identifier / Entity / Name / Type / Status / Updated, primary-grouped by Entity ascending and secondary-sorted by Identifier ascending within each group. Right-click context menu offers New / Edit / Delete / Restore. Clicking the Entity column header toggles flat sort; clicking Identifier restores the grouped default.

12. **Detail pane renders all fields in section-3.2 order, including parent entity at position #3.** Identifier (read-only), Name, Parent Entity (read-only label with "Move to entity" affordance), Description, Type (combo box visually grouped by family), Required (checkbox), Notes (collapsed under "Internal notes" header), Status, ReferencesSection — all present and bound to the correct fields and edges.

13. **CRUD dialogs work end to end.** Create resolves the parent entity from the selector, POSTs with `field_belongs_to_entity_identifier` per section 3.5.4, server assigns identifier and creates the edge atomically, surfaces validation errors inline. Edit persists field changes including status transitions; parent entity is read-only with a "Move to entity" affordance for re-parenting. Delete prompts for edge-text confirmation and soft-deletes both record and edge atomically. Restore reappears both record and edge atomically.

14. **File-watch refresh picks up external changes.** Authoring a `field` row via direct REST call (curl or MCP) causes the desktop master pane to reflect the change within the file-watch interval without manual reload, including correct entity-grouping placement.

15. **`field_belongs_to_entity` registered in vocabulary and constrained correctly.** `REFERENCE_RELATIONSHIPS` includes the new kind. `_kinds_for_pair((field, entity))` returns `{field_belongs_to_entity}`. Attempting to POST `/references` with `(field, entity)` and an unsupported kind returns 422. Direct DB insert with an unknown kind is rejected by the extended CHECK constraint.

16. **`field_belongs_to_entity` cardinality enforced: exactly one live edge per live field.** Attempting to POST `/fields` without `field_belongs_to_entity_identifier` in the body returns 422 with `missing_parent_entity`. Attempting to POST `/references` to attach a second `field_belongs_to_entity` edge to a field that already has one returns 422 with `{"error": "cardinality_violation", "relationship_kind": "field_belongs_to_entity", "max_outgoing": 1}`. Attempting to DELETE the only `field_belongs_to_entity` edge of a live field via `DELETE /references/{ref_identifier}` (rather than via `DELETE /fields/{field_identifier}`, which deletes both atomically) returns 422 with `{"error": "cardinality_violation", "relationship_kind": "field_belongs_to_entity", "min_outgoing": 1}`.

17. **Sample CBM-redo Phase 3 records authored through the UI, including parent-entity affiliations.** A consultant can author roughly 15 field records spanning at least three entity types (e.g., on Contact: `email_address`, `phone_number`, `first_name`, `last_name`; on Mentor: `mentor_status`, `expertise_areas`, `availability_window`, `recruitment_source`, `commitment_start_date`, `commitment_end_date`; on Dues: `dues_year`, `dues_amount`, `payment_status`, `payment_date`, `payment_method`), each with type, required flag, and an attached `field_belongs_to_entity` edge to a confirmed `entity` record, transition statuses from `candidate` to `confirmed`, and the records and edges persist correctly across application restart and across REST/MCP refetch.

### 3.8 Open Questions and Deferred Decisions

Categorized per the spec guide section 3.8 convention. Each entry is one paragraph with an explicit category tag.

#### 3.8.1 For v0.5 build to settle

**[v0.5 build] Parent-entity cardinality enforcement mechanism.** Two reasonable implementation patterns for the 1:1 mandatory constraint: (a) require the `field_belongs_to_entity_identifier` body key on POST and create the edge in the same transaction as the row (section 3.5.4's posture; cleaner UX and atomicity); (b) allow a transient invalid state (POST the row, then POST the edge separately) and enforce the constraint via deferred validation at transaction commit time. Pattern (a) is recommended by this spec but the v0.5-build conversation may choose differently based on access-layer implementation cost. The acceptance criteria are pattern-agnostic except for criterion #16 which assumes (a).

**[v0.5 build] Field-type vocabulary final list.** This spec proposes 11 values for v0.5 (`text`, `long_text`, `enum`, `multi_enum`, `date`, `datetime`, `money`, `boolean`, `number`, `reference`, `derived`). The v0.5-build conversation may lobby for additions (e.g., `address`, `phone`, `url` as common patterns lifted from the deploy-side YAML schema Section 6.2) or subtractions (e.g., deferring `derived` to v0.6+ until lineage tracing exists). The 11-value list is the recommended baseline; deviations get documented in the build's DEC record.

**[v0.5 build] "Move to entity" UX affordance shape.** Section 3.6.5 leaves open whether the Edit dialog's "Move to entity" affordance opens a sub-dialog (modal-on-modal pattern; user picks the new entity, the system DELETEs the old edge and POSTs the new edge) or a bare reference picker (smaller pop-over; same backend flow). Tracked as PI-053 for v0.5-build decision.

**[v0.5 build] Concurrent identifier-assignment behavior.** Uses the same SAVEPOINT-retry helper as the v0.4 methodology entity types and the v0.7 governance entity types per PI-002. Acceptance criterion #8 requires correctness; the mechanism is settled at the workstream level, not per-spec.

#### 3.8.2 For CBM redo to surface

**[CBM redo] Markdown for `field_description`.** Plain text in v0.5. The CBM redo's actual Phase 3 iteration build work will reveal whether descriptions need emphasis, bullet lists, or inline links. If so, a v0.6 migration introduces markdown rendering. The decision deliberately waits on real-use signal.

**[CBM redo] Text-field length caps.** No storage-level length constraints in v0.5; UI placeholder text provides soft guidance. If the CBM redo produces pathological inputs, caps are added via migration in v0.6. Same posture as `domain` and `entity`.

**[CBM redo] `field_notes` structure.** Flat plain text in v0.5. If consultant notes accrete substantially across an engagement (which is plausible — fields are the densest methodology entity and notes naturally cluster around each), a structured-journal pattern becomes a v0.6 candidate. Same posture as `domain_notes` and `entity_notes`.

**[CBM redo] `field_default_value` at the methodology level.** v0.5 does not capture default values at the methodology level — they are treated as a deploy-side concern (YAML schema Section 6.1, `default:`). The CBM redo will surface whether defaults carry methodology meaning frequently enough to warrant capture (e.g., a default that reflects a business policy rather than a UX convenience). If yes, a v0.6 migration adds the field per PI-055.

**[CBM redo] `field_required_when_conditions` (richer required-ness).** v0.5 captures required-ness as a single boolean. The deploy-side schema (Section 6.1.1) supports `requiredWhen:` condition expressions; whether the methodology record should mirror that complexity, or stay at the boolean level and delegate condition authoring to the YAML, is a CBM-redo question. PI-056 tracks the v0.6+ extension.

**[CBM redo] Cardinality leniency on entity-soft-delete.** Section 3.3.1's lifecycle semantics specify that soft-deleting an entity does NOT cascade-soft-delete its inbound `field_belongs_to_entity` edges' source fields. Whether this leniency is right (preserves field records for restore-from-soft-delete recovery) or wrong (leaves fields in an inconsistent state with no live parent) is a CBM-redo question. PI-059 tracks the v0.6+ posture decision.

**[CBM redo] Per-entity vs cross-entity field reuse pattern.** v0.5 treats each field as belonging to exactly one entity. Common attributes that conceptually recur across multiple entities (e.g., `email_address` on Contact and Mentor and Client) are handled by authoring twin records, one per entity. The CBM redo will surface how much friction the twin-record pattern creates compared to a shared-field-with-multiple-attachments alternative; if the friction is high, a v0.6 mechanism for cross-entity reuse becomes a candidate.

**[CBM redo] Server-side list filters.** Only `?include_deleted=true` and `?entity_identifier=ENT-NNN` are supported in v0.5. Client-side filtering over remaining axes (status, type) is sufficient at expected scale. If list sizes grow large enough to cause UI responsiveness issues, server-side filters (e.g., `?field_status=confirmed`, `?field_type=enum`) become v0.6 candidates per PI-055's general "more filters as needed" trail.

#### 3.8.3 For v0.6+

**[v0.6+] PI-053 — Re-parenting UX flow.** New planning item authored at this spec's authoring conversation close. Tracks the "Move to entity" affordance shape and the access-layer support for atomic edge swap (`POST /fields/{field_identifier}/reparent` convenience endpoint vs explicit DELETE-then-POST flow).

**[v0.6+] PI-054 — Richer field-type vocabulary.** New planning item authored at this spec's authoring conversation close. Covers `formula`, `link`, `address`, `phone`, `url` and the question of whether `derived` should split into a distinct entity type (per DEC-038's posture) once lineage tracing lands. Gated on CBM-redo signal.

**[v0.6+] PI-055 — `field_default_value` and additional list filters.** New planning item authored at this spec's authoring conversation close. Captures the default-value-at-methodology-level question and the server-side-list-filters general expansion in one combined item because both are surfaced by the same real-use signal pattern.

**[v0.6+] PI-056 — Richer required-ness rules.** New planning item authored at this spec's authoring conversation close. Covers the question of whether the methodology record should capture conditional required-ness (mirroring the deploy-side `requiredWhen:`) or stay at the boolean level. Gated on CBM-redo signal and on PI-057 (field-to-field dependencies) prerequisite analysis.

**[v0.6+] PI-057 — Field-to-field dependencies.** New planning item authored at this spec's authoring conversation close. Tracks the `field_depends_on_field` references-edge mechanism for methodology-level dependency capture. Likely lands as part of the same v0.6 release as PI-056.

**[v0.6+] PI-058 — Derived-field lineage tracing per DEC-038.** New planning item authored at this spec's authoring conversation close. Realizes DEC-038's posture (first-class methodology entity with explicit references for lineage tracing) in concrete schema-and-references shape. Covers the `derived_field_derived_from_field` and `derived_field_traverses_relationship` edge kinds (working names) and the access-layer logic for traversing the lineage graph.

**[v0.6+] PI-059 — Entity-soft-delete cascade posture for inbound fields.** New planning item authored at this spec's authoring conversation close. Decides whether soft-deleting an entity should cascade-soft-delete its inbound `field_belongs_to_entity` edges' source fields (strict-consistency posture) or leave them in place (restore-from-soft-delete-friendly posture, the v0.5 default). Tracked separately because the posture decision affects every methodology entity-to-child relationship subsequently introduced.

**[v0.6+] PI-005 — Process schema growth surfacing `process_touches_field`.** Already tracked. When `process` grows beyond its v0.4 thin shape, the process-to-field edge becomes the first inbound references kind on `field`.

**[v0.6+] DEC-038 — Derived-fields posture.** Already-decided architectural direction. The v0.5 `field_type = derived` enum value provides the slot; the realization (lineage tracing, source-field references, traversed-relationship references) lands under PI-058.

### 3.9 Cross-References

#### 3.9.1 Decisions cited by this spec

The following six decisions are authored by running `crmbuilder-v2/scripts/apply_close_out.py` against the close-out payload for this spec's authoring conversation. Each is linked to its session via a `decided_in` reference recorded in the same payload. The DEC numbers assume the heads at this spec's authoring time (DEC-245 latest) hold through close-out; if parallel-sandbox work has claimed numbers in the interim, the close-out re-keys per the SES-077 pattern (CLAUDE.md "v2 session lifecycle — planning item resolution").

- **DEC-246 — `field` identifier prefix and format.** Adopts `FLD` under the soft-3-letter posture established by `domain.md` section 3.1 (DEC-044). Three letters, no collision against the existing prefix space, reads unambiguously as "field" (see section 3.1).
- **DEC-247 — `field` field inventory and validation under minimum-viable v0.5 scope.** Seven substantive fields plus inherited timestamps; one description field (no `field_label`); optional `field_notes`; no `field_default_value`; methodology-level required-ness captured as a boolean (`field_required`), with conditional required-ness deferred to PI-056; no storage-level length caps; per-parent-entity case-insensitive `field_name` uniqueness (see section 3.2).
- **DEC-248 — `field` status lifecycle.** Adopts the `domain` / `entity` pattern (three values, one-way propose-verify gate, rejection-via-soft-delete, no `archived`) without modification, and documents the field-status-independent-of-parent-entity-status posture (see section 3.4).
- **DEC-249 — `field`-to-`entity` affiliation mechanism and `field_belongs_to_entity` vocabulary registration.** Many-to-one (1:1 mandatory at source) via the references entity, NOT a direct FK column. Rationale: references-first discipline, uniform edge-query semantics, future-edge friction avoidance, soft-delete consistency, cardinality enforcement as access-layer logic. New vocabulary entry registered in `REFERENCE_RELATIONSHIPS` and `_kinds_for_pair`; Alembic migration extends the `refs.relationship_kind` CHECK constraint (see section 3.3.1).
- **DEC-250 — `field_type` vocabulary for v0.5 and POST atomicity for the mandatory parent-entity edge.** 11-value enum (`text`, `long_text`, `enum`, `multi_enum`, `date`, `datetime`, `money`, `boolean`, `number`, `reference`, `derived`) — narrower than the deploy-side YAML schema's type list, oriented to value-shape rather than platform rendering; richer types deferred per PI-054. POST `/fields` requires `field_belongs_to_entity_identifier` body key for atomic row + edge + back-reference creation in a single transaction, deviating from the cross-spec default decomposed-references posture; rationale: live-edge invariant on the 1:1 mandatory affiliation (see sections 3.2.3, 3.5.4).
- **DEC-251 — `field` API surface, UI defaults, master-pane grouping deviation, acceptance criteria for v0.5.** Standard endpoint set with the POST atomicity deviation (DEC-250) and the `?entity_identifier=ENT-NNN` list filter; decomposed reference handling beyond the parent-entity edge; default `ListDetailPanel` UI under the Methodology sidebar group at position #5; master-pane primary-grouped by parent entity (deviation from the cross-spec flat sort; rationale: field-count density); parent entity rendered at detail-pane position #3 outside the generic `ReferencesSection`; 17 testable acceptance criteria (see sections 3.5, 3.6, 3.7).

#### 3.9.2 External references

- `crmbuilder/CLAUDE.md` — universal session-startup entry; documents the `REFERENCE_RELATIONSHIPS` / `_kinds_for_pair` / Alembic-migration triad that section 3.3.1's mechanical additions follow; documents the v2 `{data, meta, errors}` envelope discipline that section 3.5.7 follows.
- `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md` — schema spec template this document follows.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/entity.md` — predecessor schema for the parent entity type this spec attaches to; source of the references-first posture inherited here (entity scopes to domain via references; field belongs to entity via references; same discipline).
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/domain.md` — establishes the conventions inherited by this document (parent-prefix field naming, `{source}_{verb}_{target}` relationship-kind naming, soft-3-letter prefix posture, status-lifecycle shape, rejection-via-soft-delete posture, no-archived posture).
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/process.md` — anticipated source-side of `process_touches_field` once PI-005 lands.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/engagement.md` — sibling methodology entity; informs the sidebar position discussion.
- `PRDs/product/app-yaml-schema.md` — deploy-side YAML schema; Section 6 (Field Definitions) is the downstream artifact this methodology record feeds. The methodology `field_type` vocabulary is intentionally narrower than the YAML schema's; the methodology required-ness is intentionally a single boolean rather than mirroring `requiredWhen:`.
- `PRDs/process/research/evolved-methodology/evolved-methodology-phase-outline.md` — Phase 3 iteration build conversations are the primary methodology surface for field-record authoring.

#### 3.9.3 Related prior decisions informing this spec

- **DEC-006** — Universal references table as the cross-entity-type edge store. Direct architectural foundation for the `field_belongs_to_entity` mechanism choice in section 3.3.1; the references-first discipline this spec affirms even for a 1:1 mandatory relationship.
- **DEC-035** — `ListDetailPanel` master-widget + context-menu factory refactor. Informs master pane patterns in section 3.6.2, including the grouping deviation.
- **DEC-036** — Right-click context menus uniform across all entity rows. Informs context-menu behavior in section 3.6.2.
- **DEC-038** — Derived fields as first-class methodology entities with explicit references for lineage tracing. Forward-looking architectural posture realized under PI-058 in v0.6+; the v0.5 schema provides the `field_type = derived` slot.
- **DEC-039** — Minimum entity inventory and multi-tenancy posture. Indirectly relevant: justifies why `field` is the right urgency-ordered first PI-004 entity (entity inventory is in v0.4; fields make it useful).
- **DEC-043** — SES-010 identifier-asymmetry resolution. Mandates the `GET /fields/next-identifier` helper endpoint cited in section 3.5.1.
- **DEC-046** — Parent-prefix field-naming convention for methodology entities. Establishes the field-naming pattern this spec inherits and applies (see section 3.2).
- **DEC-047** — `domain` status lifecycle, propose-verify gate, and rejection-via-soft-delete posture. Establishes the lifecycle pattern this spec adopts unchanged (see section 3.4).
- **DEC-048** — `domain` relationship posture and `{source}_{verb}_{target}` relationship-kind naming convention. Establishes the relationship-kind naming pattern this spec applies in registering `field_belongs_to_entity` (see section 3.3.3).
- **PI-002** — Identifier-on-POST optionality across prefixed-identifier entity types. Informs the section 3.5.2 server-assignment behavior and the section 3.1 identifier auto-assignment posture; `field` joins the entity types that accept `identifier: null` on POST.
- **PI-004** — Additional methodology entity types beyond the v0.4 workstream. This spec resolves the first (most urgent) portion of PI-004; the remaining portions (`requirement`, `manual_config`, `test_spec`) are resolved by subsequent specs in the same planning item.
- **PI-005** — Process schema growth beyond the v0.4 thin shape. Anticipated source of the first inbound references kind on `field` (`process_touches_field`).

#### 3.9.4 Predecessor and successor conversations

- **Predecessor (workstream lineage):** the v0.4 four-conversation methodology-entity-schema-design workstream (`domain` → `entity` → `process` → `crm_candidate`) plus the subsequent `engagement` spec. This spec inherits the conventions established across that workstream without re-establishing them.
- **Predecessor (immediate):** the conversation closing this spec is opened directly under PI-004; there is no per-conversation predecessor in the v0.4 four-conversation workstream sense.
- **Successor:** the next PI-004 entity spec to be drafted is the consultant's choice — likely `requirement` (most logically adjacent to `field`, since requirements often resolve to specific field captures) or `persona` (already tracked as PI-003). Each subsequent spec inherits the conventions affirmed here and registers its own `{source}_{verb}_{target}` vocabulary entries.

---

*End of document.*

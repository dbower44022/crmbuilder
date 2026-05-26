# Methodology Entity Schema Spec — `entity`

**Last Updated:** 05-26-26
**Status:** v1.1 — PI-010 satisfier amendment landed; v0.5+ growth shipped
**Position in workstream:** Second of four methodology-entity schema specs (`domain` → `entity` → `process` → `crm_candidate`)
**Predecessor conversation:** `domain` schema-design conversation (close-out payload at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_012.json`)
**Successor conversation:** `process` schema design — kickoff at `PRDs/product/crmbuilder-v2/schema-design-kickoff-process.md`

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.1 | 05-26-26 | Doug Bower / Claude | PI-010 satisfier amendment. v0.5+ schema growth shipped: (1) new `entity_kind` TEXT NULL column (`person` \| `organization` \| `event` \| `transaction` \| `other`, or NULL) per DEC-292; (2) new `entity_variant_of_entity` reference kind (entity → entity, many-to-one at source side, cardinality enforced at access layer) per DEC-291. Migration is additive; v1.0 records survive intact with `entity_kind` NULL and no inbound/outbound variant edges. Migration story (DEC-293) is no-op — no production variant data existed at amendment time. Resolves PI-010. |
| 1.0 | 05-12-26 02:00 | Doug Bower / Claude | Initial draft. Produced by the second schema-design conversation in the methodology-entity-schema-design workstream. Defines `entity` as the v2 methodology entity type that hosts CRM-modeled nouns surfaced in evolved-methodology Phase 1 conversations under minimum-viable v0.4 scope. Inherits conventions established by `domain.md` (parent-prefix field naming, `{source}_{verb}_{target}` relationship-kind naming, soft-3-letter prefix posture). Establishes `entity_scopes_to_domain` as the first formal cross-entity vocabulary entry in the methodology workstream. |

---

## Change Log

**Version 1.1 (05-26-26):** PI-010 satisfier amendment. Adds the `entity_kind` classification column (TEXT NULL; five-value enum `person | organization | event | transaction | other` plus NULL — per DEC-292), promoting the schema from eight columns to nine. Adds the `entity_variant_of_entity` relationship kind (entity → entity, first entity-to-entity edge in v2's vocabulary; many-to-one at source side via access-layer cardinality guard — per DEC-291). Includes self-reference rejection and one-step cycle guard at the access layer. Migration 0019_v0_5_entity_kind_and_variants ships the additive growth: ALTER TABLE adds the column with a CHECK admitting NULL or any of the five enum values; refs.relationship_kind CHECK extends to admit the new kind. Migration is fully reversible. No production variant data existed at amendment time (smoke-test entities only on the live engagement DB), so the migration story (DEC-293) is no-op for v0.4 records — they survive intact with `entity_kind` NULL and zero variant edges. 17 new tests across the entity access suite cover the five-value round-trip, the null-coercion path, PUT-clears semantics, the variant-edge round-trip, the cardinality guard, self-reference rejection, the one-step cycle guard, and the vocab registration. Resolves PI-010.

**Version 1.0 (05-12-26 02:00):** Initial creation. Defines five substantive fields (`entity_identifier`, `entity_name`, `entity_description`, `entity_notes`, `entity_status`) plus inherited timestamps; three-status lifecycle mirroring `domain` (`candidate` / `confirmed` / `deferred`) with one-way propose-verify gate; entity status independent of any affiliated-domain statuses; many-to-many domain affiliation via the references entity using the new `entity_scopes_to_domain` relationship kind; no FK columns on the entity table; standard endpoint set with decomposed reference handling. Defers Domains-column in the master pane to v0.5+ paired with PI-007 short codes. Five decisions produced (DEC-050 through DEC-054) and two new planning items (PI-009 master-pane Domains column, PI-010 entity-schema v0.5+ extensions covering variants and base-type/kind). Acceptance criteria captured as 16 testable statements, three of which specifically cover the vocabulary registration and references-mechanism behavior.

---

## 1. Purpose and Position

This document specifies the `entity` entity type for v2's storage layer. It is the second of four schema specs produced by the methodology-entity-schema-design workstream — the workstream that prepares v2 to host methodology *content* (not just governance about it) in time for the CBM redo, which will use the evolved methodology and v2 as its system of record.

The workstream is governed by `methodology-schema-workstream-plan.md`. Each schema spec conforms to the template in `methodology-entity-schema-spec-guide.md`. The predecessor spec (`domain.md`) established two cross-spec conventions that this spec inherits:

- **Parent-prefix field naming** (DEC-046): all non-identifier, non-timestamp fields are prefixed with the parent entity name. All fields including identifier and timestamps adopt the prefix in v0.4 for full convention consistency.
- **`{source}_{verb}_{target}` relationship-kind naming** (DEC-048): vocabulary entries involving methodology entities are named source-first, with the source entity name, a verb phrase, and the target entity name.

This spec adopts both conventions without re-establishing them; the structural amendments to the spec guide section 6 reflecting the conventions are queued for the v0.4-build-planning conversation.

`entity` is the second spec because it depends on `domain` (every `entity` may scope to one or more domains via the `entity_scopes_to_domain` references mechanism this spec introduces) but is itself referenced by the not-yet-designed `process` and by future v0.5+ entity types (notably `field` per PI-004). Designing `entity` second lets `process.md` treat both `domain` and `entity` as settled referents.

`entity`'s primary scope in v0.4 is intentionally thin. Evolved-methodology Phase 1 explicitly does not produce Entity PRDs (line 62 of the Phase 1 interview guide: *"Phase 1 may surface entity names as nouns the client uses, but does not produce Entity PRDs"*); Phase 1 surfaces entity names naturally as the consultant talks through the Prioritized Backbone, leaving full entity definition to Phase 3. v0.4 captures that Phase 1 surfacing: a client-language name, a brief plain-text description, an optional consultant scratchpad, and a lifecycle status — plus the relational shape that links each entity to the domains it scopes to. The schema grows in v0.5+ as Phase 3 demands attach fields (PI-004), variants (PI-010), and CRM-base-type/kind classification (PI-010).

---

## 2. Summary

An `entity` record in v2 represents one CRM-modeled noun a client uses — Contact, Account, Mentor, Session, Dues, Engagement, etc. Phase 1 surfaces these names naturally as the consultant walks the client through the Prioritized Backbone; the consultant captures them as `entity` records so subsequent Phase 3 work can attach fields and definitions to a settled identifier rather than retrofitting from prose. Each `entity` record holds a client-language name, a brief description of what kind of thing the entity represents, an optional internal-notes scratchpad for consultant rationale, and a lifecycle status tracking whether the entity is a CRM-Builder-proposed candidate, a client-confirmed in-scope record, or an acknowledged-but-deferred area. Domain affiliation — which engagement domains the entity is relevant to — is captured separately as `entity_scopes_to_domain` references in v2's universal references store, supporting the methodology reality that an entity (like CBM's Contact) may legitimately span multiple domains.

The schema in v0.4 is the thinnest shape that can faithfully host Phase 1's entity-surfacing. It deliberately omits a fields collection, variant relationships (Mentor Contact vs Client Contact pattern), CRM-base-type/kind classification (person / organization / event / transaction), and any process-touches-entity edges — all belong to subsequent methodology phases or to subsequent v2 releases. The minimum-viable shape grows additively in v0.5+ as the evolved methodology's Phase 3 iteration work reveals what `entity` needs to carry.

---

## 3. Schema Specification

### 3.1 Identity

| Field | Value |
|-------|-------|
| Entity type name (storage) | `entity` |
| Display name (singular) | Entity |
| Display name (plural) | Entities |
| Identifier prefix | `ENT` |
| Identifier format | `ENT-NNN`, zero-padded to 3 digits (e.g., `ENT-001`, `ENT-042`) |
| Identifier auto-assignment | Server-side on POST omission; helper at `GET /entities/next-identifier` |

`ENT` is three letters and adheres to the soft-3-letter prefix posture established in `domain.md` section 3.1. The prefix reads unambiguously as "entity", has no collision with existing prefixes (DEC, SES, RSK, PI, TOP, REF, CHR, STA, DOM), and matches the existing v2 governance-entity norm. No deviation from defaults; the identifier-asymmetry helper endpoint per DEC-043 ships alongside the standard endpoint set.

### 3.2 Fields

Field naming follows the parent-prefix convention established by `domain.md` (DEC-046): all non-identifier, non-timestamp fields are prefixed with the parent entity name (`entity_`). All fields including identifier and timestamps adopt the prefix in v0.4 for full convention consistency.

#### 3.2.1 Identity fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `entity_identifier` | TEXT | yes | server-assigned | `^ENT-\d{3}$`, unique | The methodology-entity identifier in `ENT-NNN` format. Server-assigned when omitted from POST body. |
| `entity_name` | TEXT | yes | — | non-empty trimmed; case-insensitive unique within the engagement | Entity name in the client's language (e.g., "Contact", "Mentor", "Engagement", "Dues"). |

#### 3.2.2 Content fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `entity_description` | TEXT | yes | — | non-empty trimmed | Brief description of what kind of thing this entity represents (e.g., "A person who provides mentoring guidance to clients"; "A formal pairing between a mentor and a mentee"; "A periodic monetary obligation owed by a mentor to the program"). Plain text in v0.4; markdown support deferred to CBM-redo signal. |
| `entity_notes` | TEXT | no | — | — | Internal consultant scratchpad. Not part of any client-facing render. Used to capture pattern-library rationale, push-back trails, between-session reasoning about why the entity exists in the form it does. Plain text in v0.4. |

**No `entity_purpose` field.** Unlike `domain` — where `domain_purpose` answers the priority-test question "why does the mission require this domain?" — an entity has no comparable mission relationship. An entity is a noun the client uses; the question "why is this entity relevant to the engagement?" is answered by the entity's `entity_scopes_to_domain` references, not by a free-text purpose. Adding `entity_purpose` would either duplicate `entity_description` or invent a methodology concept Phase 1 doesn't produce.

#### 3.2.3 Classification fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `entity_status` | TEXT | yes | `candidate` | enum: `candidate` \| `confirmed` \| `deferred`; valid transitions per section 3.4 | Lifecycle status. See section 3.4 for the transition map. |
| `entity_kind` | TEXT | no (v1.1+) | NULL | NULL or enum: `person` \| `organization` \| `event` \| `transaction` \| `other` | CRM base-type classification (PI-010 / DEC-292). NULL means classification deferred; operators set explicitly when Phase 1 surfacing is firm enough. Informs Phase 3 field-shape defaults and Phase 5 CRM-engine evaluation scoring. |

The `entity_kind` enum was deferred from v0.4 under PI-010; v1.1 ships it as TEXT NULL with a CHECK constraint admitting NULL or any of the five values (DEC-292). Nullability is intentional — Phase 1 sometimes surfaces an entity before its kind is settled, and DEC-051's "don't force methodology concepts Phase 1 doesn't always produce" posture extends here. Operator-deferred classification is the legitimate default. The five-value set is exhaustive for the CBM-redo-era methodology; the `other` sentinel covers ambiguous cases (e.g. Campaign / Engagement, which carry dual event/transaction readings) and future patterns we haven't surfaced yet. Richer kind taxonomies (subtypes, secondary-kind tags, kind-inheritance from a parent variant) are deferred to v0.6+ pending CBM-redo signal.

#### 3.2.4 Relationship fields

None in v0.4 or v1.1. `entity` has no outgoing FK columns on its table — including the new variant relationship from PI-010, which is implemented as a `refs`-table edge rather than a self-referential FK column (DEC-291). Domain affiliation is captured via the references entity (see section 3.3.1); the entity variant relationship is captured the same way (see section 3.3.1, `entity_variant_of_entity`). Future inter-entity relationships (entity-to-process, entity-to-field) likewise use references rather than FK columns.

#### 3.2.5 Timestamp fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `entity_created_at` | DATETIME | yes | server-set on insert | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `entity_updated_at` | DATETIME | yes | server-set on insert and on each update | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `entity_deleted_at` | DATETIME | no | null until soft-delete | ISO 8601 UTC when set | Inherited base behavior. Set on DELETE; cleared on POST `/restore`. |

**No storage-level length caps.** Text fields are unconstrained at the storage layer in v0.4. The UI provides soft guidance via placeholder text ("Brief description"). Pathological-input handling deferred to CBM-redo signal; length caps are easy to add via migration in v0.5 if needed. This mirrors `domain`'s posture.

### 3.3 Relationships

#### 3.3.1 Outgoing relationships

`entity` declares two outgoing relationship kinds as of v1.1: `entity_scopes_to_domain` (v0.4) and `entity_variant_of_entity` (PI-010, DEC-291).

| relationship_kind | source | target | mechanism | cardinality | semantics |
|-------------------|--------|--------|-----------|-------------|-----------|
| `entity_scopes_to_domain` | `entity` | `domain` | references-entity edge | many-to-many | An entity is scoped to one or more domains. An entity may have zero, one, or many such references; a domain may have zero or many inbound references of this kind. |
| `entity_variant_of_entity` | `entity` | `entity` | references-entity edge | many-to-one at source side (access-layer enforced); zero-or-one outbound per entity | An entity is a variant of another entity — the "Mentor Contact / Client Contact" pattern. Per DEC-291 the mechanism is a `refs`-table edge rather than a self-referential FK column or a separate variant entity type, matching DEC-053's default posture for methodology-entity many-to-many but constraining cardinality at the source side. Self-references and one-step cycles are rejected at the access layer. Deeper-cycle prevention is operator-responsibility. |

The mechanism for `entity_scopes_to_domain` is the references entity at v2's `refs` table, governed by the existing `RELATIONSHIP_RULES` infrastructure (DEC-006). The choice over an entity-table multi-value FK column is per DEC-053: references discipline keeps the entity-table schema small, supports the same edge-creation/lookup semantics already used for governance-entity references, and makes the inverse query ("what entities scope to this domain?") trivial through the existing reverse-edge query. A direct single-value FK was a non-starter because it would contradict the methodology reality that entities span domains (CBM's Contact lives in MN, MR, and FU simultaneously).

The mechanism for `entity_variant_of_entity` is the same references entity (DEC-291). Three candidates were considered: (A) references-edge with new vocab kind, (B) self-referential FK `entity_parent_identifier` on the entity table, (C) separate variant entity type. Option A wins on three grounds: (i) DEC-053 establishes the references-edge mechanism as the default for methodology-entity many-to-many, and the variant relationship is structurally many-to-one (which the references mechanism handles with an access-layer cardinality guard), so there is no substantive reason to deviate from the default; (ii) option A reuses the existing `ReferencesSection` widget in the UI for both rendering and authoring with zero new widget code; (iii) option A is the first entity-to-entity edge kind in v2's vocabulary, which exercises the cascading-filter infrastructure cleanly. Option B would have added schema-table surface and prevented the inverse query ("what entities are variants of this entity?") from sharing the unified references-query path. Option C would have added a third entity type just to express "variant of," and the references table already does this.

**Cardinality at the source side is enforced at the access layer, not the schema layer.** This matches the `field_belongs_to_entity` precedent from PI-004's first slice: an entity may have AT MOST ONE outbound `entity_variant_of_entity` edge. A POST that would create a second outbound edge of this kind from the same source entity returns 422 with the `cardinality_violation` code. Self-references (`source_id == target_id`) and one-step cycles (creating B→A when A→B already exists) are rejected with `self_reference` and `cycle_violation` codes respectively. Deeper cycles (A→B→C→A) are operator-responsibility — the access layer does not perform graph walks at edge-create time.

**Mechanical additions per CLAUDE.md line 48:**

1. `entity_scopes_to_domain` added to `REFERENCE_RELATIONSHIPS` in `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`.
2. `_kinds_for_pair` extended so `(entity, domain)` returns `{entity_scopes_to_domain}` (the only kind for this pair in v0.4).
3. Alembic migration extending the `refs.relationship_kind` CHECK constraint to include the new value.

**Cardinality and validation:**

- Many-to-many. No upper bound on either side.
- Zero-affiliation is permitted. Phase 1 sometimes surfaces an entity name before its domain scoping is settled; the references discipline must not force pre-decided affiliation.
- Source must be a live entity record; target must be a live domain record. (Existing access-layer rules for the references table.)
- Duplicate `(source_id, target_id, relationship_kind)` tuples are rejected by the references-table uniqueness constraint.

**Lifecycle semantics:**

- Soft-deleting an entity does not cascade-delete its `entity_scopes_to_domain` references; the references persist (existing v2 behavior) and remain visible via the show-deleted UI toggle on either side.
- Same for soft-deleting a domain.
- Restoring either endpoint restores its relationship rows in place.

**The verb "scopes to" means:** this entity is relevant to / appears in / is used by work in this domain. It is a scoping or affiliation notion, not containment (the same entity can scope to multiple domains simultaneously) or strict ownership.

#### 3.3.2 Inbound relationships (anticipated; declared by future source-side specs)

`entity` is the anticipated target of references from `process` and from future v0.5+ entity types (notably `field` per PI-004, and a v0.5+ entity-variant relationship per PI-010). None of these are declared in v0.4; their formal vocabulary registration belongs to the source-side specs that introduce them. This subsection exists for forward awareness; the `entity` panel's `ReferencesSection` widget will render inbound references once they exist.

Anticipated inbound kinds (informational from this spec's perspective; declared in their source-side specs):

| relationship_kind | source | target | semantics |
|-------------------|--------|--------|-----------|
| `process_touches_entity` (working name; declared by `process.md`) | `process` | `entity` | A process reads, writes, or otherwise operates on records of this entity type. Phase 3 work; Phase 1 doesn't draw process-to-entity edges. |
| `field_belongs_to_entity` (working name; v0.5+) | `field` | `entity` | A field is owned by an entity. v0.5+ schema extension per PI-004. |
| `entity_variant_of_entity` (working name; v0.5+) | `entity` | `entity` | An entity is a variant of another entity (Mentor Contact / Client Contact pattern). v0.5+ schema extension per PI-010. |

The v0.4-build-planning conversation's cross-spec consistency check will validate that no name collisions emerge once `process.md` registers its source-side kind for the entity-touching relationship.

#### 3.3.3 Cross-spec relationship-kind naming convention — adopted, not established

This spec adopts the `{source}_{verb}_{target}` relationship-kind naming convention established by `domain.md` section 3.3.3 (DEC-048). The single vocabulary entry this spec registers (`entity_scopes_to_domain`) conforms to the pattern: source entity first, verb phrase, target entity. The convention is not re-decided here; it carries forward from the predecessor conversation.

#### 3.3.4 Hierarchy

`entity` does not use the self-referential parent-child hierarchy pattern as a schema-table column. v1.1 ships the variant relationship (Mentor Contact / Client Contact pattern from CBM) as a `refs`-table edge (`entity_variant_of_entity`) per DEC-291 — see section 3.3.1 for the cardinality and semantics. The v0.4 workaround of suffixing `entity_name` ("Contact — Mentor", "Contact — Client") remains operator-accessible as a naming-only convention but is no longer the recommended pattern; v1.1+ records should attach an explicit `entity_variant_of_entity` edge from the variant to the base entity. Migration story for legacy suffix-named records is no-op per DEC-293 — no production variant data existed at v1.1 amendment time, and CBM-redo will go directly to the v1.1 mechanism without re-keying legacy records.

### 3.4 Lifecycle

#### 3.4.1 Status values

| Status value | Description | Valid predecessors | Valid successors |
|--------------|-------------|--------------------|------------------|
| `candidate` | CRM Builder has proposed; awaiting client verification. **Default starter status.** | (none — starter) | `confirmed`, `deferred` |
| `confirmed` | Client has verified this is an entity in scope for the engagement. | `candidate`, `deferred` | `deferred` |
| `deferred` | Client has acknowledged this is a real entity but it is out of current engagement scope. | `candidate`, `confirmed` | `confirmed` |

The structure mirrors `domain.md` section 3.4.1 exactly; the semantics map cleanly: entities, like domains, are surfaced by the consultant and verified by the client.

#### 3.4.2 Transition semantics

The status lifecycle implements the same **one-way propose-verify gate** established for `domain` (DEC-047): once an entity has moved out of `candidate` (in either direction, to `confirmed` or to `deferred`), it does not regress to `candidate`. The rationale: the propose-verify moment is a meaningful client-engagement event; if the consultant later wants to fundamentally rethink a verified entity, the right action is to edit the record's content, not to regress its status. Status reflects engagement-scope position, not deliberation state.

Movement between `confirmed` and `deferred` in either direction is permitted to support mid-engagement scope changes (e.g., an entity initially confirmed but later deprioritized; a previously-deferred entity pulled back into scope at a later iteration).

#### 3.4.3 Status independence from affiliation status

An entity's `entity_status` is its own field on its own table, set by the consultant based on client verification of the entity itself. **It is not derived from the statuses of the domains it scopes to.** This independence matters because an entity may legitimately span domains at different lifecycle positions: Contact in CBM might scope to MN (`confirmed`), MR (`confirmed`), and FU (`deferred`) simultaneously, and Contact's own status is `confirmed` because the client has agreed Contact is a thing in their world — that judgment doesn't depend on which specific domains the entity ends up in.

The implication for the UI and access layer: edit affordances on `entity_status` do not consult the affiliated domains' statuses, and changing a domain's status does not cascade to its inbound `entity_scopes_to_domain` references' source-side records. The two lifecycles are managed independently.

#### 3.4.4 Rejection via soft-delete

When the client rejects a CRM-Builder-proposed entity candidate ("no, that's not actually an entity for us"), the rejection is handled by soft-delete rather than a `rejected` status value. `DELETE /entities/{entity_identifier}` sets `entity_deleted_at`; the record persists for audit and history, surfaces under the `?include_deleted=true` toggle, and is restorable via POST `/restore`. This piggybacks v2's existing soft-delete infrastructure rather than introducing a status value that duplicates the mechanism. The cross-spec principle established in `domain.md` section 3.4.3 carries forward unchanged: **status values track engagement-scope lifecycle; soft-delete tracks existence-in-the-record.**

#### 3.4.5 No `archived` status

`archived` is not introduced in v0.4. Soft-delete combined with the "show deleted" toggle already covers the "retained for record, not in active scope" use case. Mirrors `domain.md` section 3.4.4.

#### 3.4.6 Soft-delete semantics

Soft-delete inherits v2's standard behavior:

- DELETE sets `entity_deleted_at` to the current ISO 8601 UTC timestamp.
- Soft-deleted records do not appear in `GET /entities` by default.
- `GET /entities?include_deleted=true` returns soft-deleted records alongside live ones.
- POST `/entities/{entity_identifier}/restore` clears `entity_deleted_at` and reappears the record in the default list.
- Restore on a record that is not soft-deleted returns HTTP 422.

Outbound `entity_scopes_to_domain` references on a soft-deleted entity are NOT cascade-deleted. They persist in the references table; show-deleted toggles on either side surface them. This matches v2's existing references-table soft-delete behavior.

### 3.5 API Surface

#### 3.5.1 Endpoints

| Method | Path | Body | Notes |
|--------|------|------|-------|
| GET | `/entities` | — | List endpoint. Returns active records by default. Supports `?include_deleted=true` to include soft-deleted records. |
| GET | `/entities/{entity_identifier}` | — | Single fetch by identifier. Returns 404 if not found. |
| POST | `/entities` | full record minus `entity_identifier` (server-assigned) | Create. Returns 201 with the assigned identifier in the response body. Server-side validation per section 3.2 applied. |
| PUT | `/entities/{entity_identifier}` | full record | Full replace. `entity_identifier` in body must match the path; mismatch returns 422. |
| PATCH | `/entities/{entity_identifier}` | partial record | Partial update. Status-transition validation applied (see 3.5.3). |
| DELETE | `/entities/{entity_identifier}` | — | Soft-delete; sets `entity_deleted_at`. Idempotent (DELETE on an already-soft-deleted record returns 200 with no state change). |
| POST | `/entities/{entity_identifier}/restore` | — | Clears `entity_deleted_at`. Returns 422 if the record is not soft-deleted. |
| GET | `/entities/next-identifier` | — | Returns `{"next": "ENT-NNN"}` for the next available identifier. Per SES-010 resolution (DEC-043). |

**No deviations from the cross-spec default endpoint set.** No bulk operations, no webhooks, no event streams, no inline-affiliation convenience endpoints.

#### 3.5.2 Identifier auto-assignment

`entity_identifier` is server-assigned on POST when omitted from the request body. The assignment logic queries the current maximum `entity_identifier` (including soft-deleted records, to avoid identifier reuse) and increments the numeric suffix. The `GET /entities/next-identifier` helper exposes the same logic for clients that want to know the assigned identifier before POSTing.

Concurrent identifier-assignment behavior (locking, optimistic retry, advisory locks, etc.) is implementation-level and decided by the v0.4 build, consistent with how v0.3 governance-entity identifier assignment handles concurrency. Acceptance criterion #7 in section 3.7 requires correctness under concurrent POSTs.

#### 3.5.3 Status-transition validation

Status transitions are validated server-side at the access layer. PATCH or PUT requests that specify an `entity_status` value that is not a valid successor of the current value (per section 3.4.1) return HTTP 422 with a body of the form:

```
{
  "error": "invalid_status_transition",
  "from": "<current status>",
  "to": "<requested status>"
}
```

The default-`candidate` rule applies on POST: if `entity_status` is omitted, the server assigns `candidate`. POST with `entity_status` explicitly set to a non-starter value is permitted (e.g., bulk-importing already-confirmed entities from prior engagement records).

#### 3.5.4 Decomposed reference handling

Domain affiliations are NOT inlined into the entity create or update bodies. To attach an `entity_scopes_to_domain` reference, the client makes a separate `POST /references` with:

```
{
  "source_type": "entity",
  "source_id": "ENT-NNN",
  "target_type": "domain",
  "target_id": "DOM-NNN",
  "relationship_kind": "entity_scopes_to_domain"
}
```

This decomposed posture keeps the entity API consistent with v2's references-first discipline (DEC-006) and matches how the v0.3 desktop UI handles references for governance entities. The New dialog and detail-pane "Add reference" affordance hide the two-call sequence behind a single user gesture, but the API stays decomposed; no `/entities/{id}/scopes` or similar shortcut endpoint is introduced.

#### 3.5.5 Other endpoint specifics

- All endpoints return JSON.
- 4xx error responses use the existing v2 error envelope shape.
- No additional list query parameters beyond `?include_deleted=true` in v0.4. Client-side filtering over the expected entity count (a typical engagement has roughly two dozen entities) is sufficient. Server-side filtering deferred to CBM-redo signal.

### 3.6 UI Considerations

This spec adopts the spec guide's default `ListDetailPanel` layout with no architectural deviations. Specifics for `entity` follow.

#### 3.6.1 Sidebar

The "Methodology" sidebar group introduced by `domain.md` section 3.6.1 hosts the new `entity` entry. Position #2 in the group, after Domains:

1. Domains
2. **Entities** (this spec)
3. Processes (`process.md`, forthcoming)
4. CRM Candidates (`crm_candidate.md`, forthcoming)

All four entries ship together in v0.4.

#### 3.6.2 Master pane

`ListDetailPanel`-backed list with these columns:

| Stored field | Display header | Width | Notes |
|--------------|----------------|-------|-------|
| `entity_identifier` | Identifier | narrow | Default sort key, ascending |
| `entity_name` | Name | wide | Client-language name |
| `entity_status` | Status | narrow | Enum value rendered as-is |
| `entity_updated_at` | Updated | narrow | Localized date/time |

Right-click context menu offers New / Edit / Delete / Restore, consistent with v0.3 governance-entity panels per DEC-035 and DEC-036.

**No Domains column in v0.4.** The column has natural value once consultants are scanning 20+ entities and want to spot affiliation at a glance, but two factors argue against shipping it in v0.4: (a) without `domain.short_code` (tracked as PI-007), the column would render `DOM-001, DOM-002, DOM-003` — identifiers that don't tell a consultant anything at a glance; (b) the column requires a batched join through the references table, which is design work whose value isn't validated against real-engagement signal yet. Deferred to v0.5+ paired with PI-007 short codes; new PI-009 tracks the column itself.

The detail pane exposes domain affiliations one click away via the `ReferencesSection` widget; the absence of the master-pane column is not a coverage gap, just a UX-density tradeoff awaiting real-use signal.

#### 3.6.3 Detail pane

Vertical layout, fields in section-3.2 order:

1. `entity_identifier` — read-only label
2. `entity_name` — single-line text editor
3. `entity_description` — multi-line text editor with placeholder "Brief description of what kind of thing this entity represents"
4. `entity_notes` — multi-line text editor under a collapsible "Internal notes" section header, collapsed by default
5. `entity_status` — combo box with the three enum values
6. `ReferencesSection` widget — renders both outgoing `entity_scopes_to_domain` references (entity-to-domain affiliations) and any inbound references. In v0.4 there are no inbound kinds declared by source-side specs yet; the widget is still always present, and the outgoing affiliations are the primary user-facing content. The widget exposes the existing "Add reference" affordance for attaching new affiliations after the entity record exists.

The collapsed-by-default treatment of `entity_notes` matches `domain_notes` — internal consultant scratchpad, not part of any client-facing render.

#### 3.6.4 Create dialog

Modal `EntityCrudDialog` subclass with field order matching the detail pane. Specifics:

- `entity_identifier` not shown in create mode (server-assigned).
- `entity_status` defaults to `candidate`; user may select a different starter value if importing established entity records.
- Required-field validation client-side before submit.
- Server-side validation errors (uniqueness, format, transition) surface inline.

**Domain-affiliation flow — open question for v0.4 build.** Two reasonable patterns:

- **Create-then-attach.** The New dialog creates the entity record only; the user adds domain affiliations from the detail pane via the existing "Add reference" affordance after the entity exists. Two gestures (one to create, one or more to attach).
- **Create-with-attach.** The New dialog includes a multi-select for domains; on submit, the UI runs POST `/entities` followed by N × POST `/references` in sequence. One gesture per entity, regardless of affiliation count.

Both satisfy the acceptance criterion that the user can attach domain affiliations through the UI without leaving it. The choice is UI-layer, not schema-layer; the v0.4-build-planning conversation decides which pattern to implement.

#### 3.6.5 Edit dialog

Same shape as create. `entity_identifier` displayed as read-only label. Status transitions enforced per section 3.4.1; invalid selections in the status combo are either prevented (recommended UX) or rejected by the server with the 422 surfacing inline (acceptable fallback).

#### 3.6.6 Delete dialog

`EntityCrudDeleteDialog` with edge-text confirmation. The user types the `entity_identifier` value (e.g., `ENT-002`) to enable the Delete button, matching v0.3 governance-entity patterns. Confirmation soft-deletes the record. Outbound `entity_scopes_to_domain` references on the soft-deleted entity persist per section 3.4.6.

### 3.7 Acceptance Criteria

The following 16 statements define what "this entity type is correctly implemented in v0.4" looks like. Each is concrete and testable; v0.4 build planning translates these into specific test cases.

1. **Schema migration applies cleanly.** Alembic migration creates the `entities` table with all eight columns (`entity_identifier`, `entity_name`, `entity_status`, `entity_description`, `entity_notes`, `entity_created_at`, `entity_updated_at`, `entity_deleted_at`), correct types and constraints, and runs both forward and backward without error.

2. **`entity_identifier` format constraint enforced.** Insertions with `entity_identifier` not matching `^ENT-\d{3}$` raise a validation error at the access layer.

3. **`entity_name` uniqueness enforced case-insensitively.** Inserting a second row whose `entity_name` matches an existing row by lowercase comparison raises a uniqueness violation.

4. **`entity_status` enum and transition validation.** Insertions with `entity_status` outside `{candidate, confirmed, deferred}` are rejected. PATCH/PUT requesting an invalid transition (e.g., `confirmed` → `candidate`) returns HTTP 422 with `{"error": "invalid_status_transition", "from": ..., "to": ...}`.

5. **Access-layer methods exist with expected signatures.** `client.list_entities()`, `client.get_entity(identifier)`, `client.create_entity(...)`, `client.update_entity(identifier, ...)`, `client.patch_entity(identifier, ...)`, `client.delete_entity(identifier)`, `client.restore_entity(identifier)`, `client.next_entity_identifier()` exist and pass unit tests covering happy path and at least one error case each.

6. **REST endpoints return expected responses for representative cases.** All eight endpoints from section 3.5 return correct HTTP status and JSON bodies for happy-path and validation-failure cases; 4xx errors use the v2 error envelope.

7. **Identifier auto-assignment helper returns next ID without race conditions.** `GET /entities/next-identifier` returns `{"next": "ENT-NNN"}` for the next available number. POST with `entity_identifier` omitted assigns the same value. Two concurrent POSTs do not assign the same identifier (verified by a concurrent-insert test).

8. **Soft-delete and restore round-trip correctly.** DELETE sets `entity_deleted_at`; the record disappears from `GET /entities`. `GET /entities?include_deleted=true` shows it. POST `/restore` clears `entity_deleted_at`; the record reappears in the default list. Restore on a record that is not soft-deleted returns 422.

9. **`Entities` sidebar entry appears under the Methodology group, position #2.** After Domains, before Processes and CRM Candidates (all three forthcoming ship together with this entry in v0.4).

10. **Master pane columns and default sort.** The Entities panel shows columns Identifier / Name / Status / Updated, sorted by Identifier ascending. Right-click context menu offers New / Edit / Delete / Restore.

11. **Detail pane renders all fields in section-3.2 order.** Identifier (read-only), Name, Description, Notes (collapsed under "Internal notes" header), Status, ReferencesSection — all present and bound to the correct fields.

12. **CRUD dialogs work end to end.** Create assigns identifier server-side, persists all fields, surfaces server-side validation errors inline. Edit persists field changes including status transitions. Delete prompts for edge-text confirmation (user types the identifier) and soft-deletes on confirm. Restore reappears the record.

13. **File-watch refresh picks up external changes.** Authoring an `entity` row via direct REST call (curl or MCP) causes the desktop master pane to reflect the change within the file-watch interval without manual reload.

14. **`entity_scopes_to_domain` registered in vocabulary and constrained correctly.** `REFERENCE_RELATIONSHIPS` includes the new kind. `_kinds_for_pair((entity, domain))` returns `{entity_scopes_to_domain}`. Attempting to POST `/references` with `(entity, domain)` and an unsupported kind returns 422. The Alembic migration extends the `refs.relationship_kind` CHECK constraint to include the new value; direct DB insert with an unknown kind is rejected.

15. **`entity_scopes_to_domain` references created and queryable bidirectionally.** POST `/references` with `source_type=entity, source_id=ENT-NNN, target_type=domain, target_id=DOM-NNN, relationship_kind=entity_scopes_to_domain` creates the row. Fetching the entity returns the reference via its ReferencesSection; the inverse query from the domain side returns the same reference. Soft-deleting either endpoint leaves the reference in place; restoring either side keeps the reference live.

16. **Sample CBM-redo Phase 1 records authored through the UI, including domain affiliations.** A consultant can author roughly 10 entity records (e.g., Contact, Account, Engagement, Session, Mentor, Mentor Application, Client, Dues, Contribution, Fundraising Campaign), attach one or more `entity_scopes_to_domain` references per entity to authored `domain` records, transition statuses from `candidate` to `confirmed`, and the records and references persist correctly across application restart and across REST/MCP refetch.

### 3.8 Open Questions and Deferred Decisions

Categorized per the spec guide section 3.8 convention. Each entry is one paragraph with an explicit category tag.

#### 3.8.1 For v0.4 build to settle

**[v0.4 build] Create-dialog domain-affiliation flow.** Two reasonable UI patterns for letting the user attach `entity_scopes_to_domain` references at create time: (a) create-then-attach (the New dialog creates the entity only; the user adds affiliations from the detail pane afterward); (b) create-with-attach (the New dialog includes a multi-select for domains; on submit the UI runs POST `/entities` then N × POST `/references` in sequence). Both satisfy the acceptance criterion that the user can attach affiliations without leaving the UI. The v0.4-build-planning conversation decides which pattern is implemented; the spec is agnostic.

**[v0.4 build] Concurrent identifier-assignment behavior.** The mechanism for preventing two concurrent POSTs from assigning the same `ENT-NNN` (row-level locking, optimistic retry, advisory locks, etc.) is implementation-level and not specified by this spec. Acceptance criterion #7 requires correctness; the *how* is the v0.4 build's call. Likely solution is consistent with how v0.3 governance-entity identifier assignment handles concurrency and with whatever pattern the `domain` build adopts.

**[v0.4 build] Cross-spec consistency check on inbound vocabulary.** Once `process.md` and `crm_candidate.md` land, the v0.4-build-planning conversation's cross-spec consistency check verifies that no relationship-kind name collisions exist (e.g., the process-to-entity edge name chosen in `process.md` does not collide with `entity_scopes_to_domain` or with any other vocab entry). The expectation is no collision, but the check is the formal gate.

#### 3.8.2 For CBM redo to surface

**[CBM redo] Markdown for `entity_description`.** Plain text in v0.4. The CBM redo's actual Phase 1 work will reveal whether descriptions need emphasis, bullet lists, or inline links. If so, a v0.5 migration introduces markdown rendering. The decision deliberately waits on real-use signal.

**[CBM redo] Text-field length caps.** No storage-level length constraints in v0.4; UI placeholder text provides soft guidance. If the CBM redo produces pathological inputs (5000-character "brief descriptions," sprawling "notes"), caps are added via migration in v0.5. Same posture as `domain`.

**[CBM redo] `entity_notes` structure.** Flat plain text in v0.4. If consultant notes accrete substantially across an engagement, a structured-journal pattern becomes a v0.5 candidate. Same posture as `domain_notes`.

**[CBM redo] Master-pane Domains column.** Section 3.6.2 defers the Domains column to v0.5+ paired with PI-007. The CBM redo will validate whether scanning entity-to-domain affiliation at the master pane is high-value, or whether the detail-pane `ReferencesSection` suffices. The signal feeds PI-009 prioritization.

**[CBM redo] Entity variant friction.** v0.4 does not introduce variant relationships; the Mentor Contact / Client Contact pattern from CBM history must be handled by name-suffixing in v0.4 (two independent records like "Contact — Mentor" and "Contact — Client"). The CBM redo will surface how much friction the workaround creates and inform PI-010 prioritization.

**[CBM redo] Entity-status "defined" vs "confirmed" distinction.** v0.4 collapses "the client agreed this entity is in scope" and "we have a full definition of this entity" into a single `confirmed` status, because v0.4 has no fields and the latter distinction has no expressive shape. v0.5+ may surface a need for a separate `defined` (or `specified`) status once fields land; alternatively, the references-table cardinality between `entity` and `field` may suffice as the implicit "defined" signal. Tracked alongside PI-004.

**[CBM redo] Server-side list filters.** Only `?include_deleted=true` is supported in v0.4. Client-side filtering over a moderate entity count is sufficient. If list sizes grow large enough to cause UI responsiveness issues, server-side filters (e.g., `?entity_status=confirmed`, `?scopes_to_domain=DOM-NNN`) become v0.5 candidates. More likely to bite for `entity` and `process` at scale than for `domain`.

#### 3.8.3 For v0.5+

**[v0.5+] PI-004 — additional methodology entity types.** Already tracked. `field`, `requirement`, `manual_config`, `test_spec`. Once `field` lands, the entity-to-field relationship (`field_belongs_to_entity` working name) attaches the entity's full PRD-equivalent content to the entity record. Phase 3 work; absorbs the entity-status "defined vs confirmed" question.

**[v0.5+] PI-007 — `domain.short_code` field.** Already tracked. Joint enabler for PI-009 master-pane Domains column on the Entities panel.

**[v0.5+] PI-009 — master-pane Domains column on the Entities panel.** New planning item authored at this conversation's close. Adds a Domains column rendering affiliated domains as comma-separated short codes (e.g., "MN, MR, FU") once PI-007 lands. Requires batched-join query at the access layer (`list_entities_with_affiliations()` or equivalent) and a column-rendering update on the `ListDetailPanel` view-model.

**[Resolved] PI-010 — entity-schema v0.5+ extensions.** Shipped in v1.1 (this amendment). Variant mechanism landed as references-edge with new vocab kind `entity_variant_of_entity` per DEC-291 — first entity-to-entity edge kind in v2's vocabulary. Kind classification landed as TEXT NULL column `entity_kind` with five-value enum (`person | organization | event | transaction | other`) per DEC-292. Migration story landed as no-op-additive per DEC-293 (no production variant data existed at amendment time). See section 3.2.3, section 3.3.1, section 3.3.4, and section 4 (migration and reversibility).

**[v0.5+] DEC-038 — derived-fields entity type.** Already-decided architectural direction from SES-011. When fields land in v0.5+ (PI-004), the derived-fields posture from DEC-038 (first-class methodology entity with explicit references for lineage tracing) integrates naturally with the entity-to-field relationship. No `entity`-side schema change needed; the derived-field tracking lives on the field side.

### 3.9 Cross-References

#### 3.9.1 Decisions cited by this spec

The following five decisions are authored by running `crmbuilder-v2/scripts/apply_close_out.py` against `PRDs/product/crmbuilder-v2/close-out-payloads/ses_013.json` at conversation close. Each is linked to SES-013 via a `decided_in` reference recorded in the same payload. The DEC numbers assume SES-012's close-out payload has been applied first; if not, numbers shift accordingly and are recomputed at payload-generation time.

- **DEC-050 — `entity` identifier prefix and format.** Adopts `ENT` under `domain`'s soft-3-letter posture (see section 3.1).
- **DEC-051 — `entity` field inventory and validation under minimum-viable v0.4 scope.** Five substantive fields plus inherited timestamps; one description field (no `entity_purpose`); optional `entity_notes`; no base-type / kind classification; no storage-level length caps; case-insensitive `entity_name` uniqueness within the engagement (see section 3.2).
- **DEC-052 — `entity` status lifecycle.** Adopts the `domain` pattern (three values, one-way propose-verify gate, rejection-via-soft-delete, no `archived`) without modification, and documents the entity-status-independent-of-affiliation-status posture (see section 3.4).
- **DEC-053 — `entity`-to-`domain` affiliation mechanism and `entity_scopes_to_domain` vocabulary registration.** Many-to-many via the references entity; new vocabulary entry registered in `REFERENCE_RELATIONSHIPS` and `_kinds_for_pair`; Alembic migration extends the `refs.relationship_kind` CHECK constraint. Rejects entity-table multi-value FK alternative. Zero-affiliation explicitly permitted (see section 3.3.1).
- **DEC-054 — `entity` API surface, UI defaults, deferred Domains-column posture, acceptance criteria for v0.4.** Standard endpoint set with no deviations; decomposed reference handling (no inline-affiliation convenience endpoints); default `ListDetailPanel` UI under the existing Methodology sidebar group at position #2; Domains column deferred to v0.5+ paired with PI-007; create-dialog affiliation flow left as a v0.4-build decision; 16 testable acceptance criteria (see sections 3.5, 3.6, 3.7).

#### 3.9.2 External references

- `crmbuilder/CLAUDE.md` — universal session-startup entry; documents the `REFERENCE_RELATIONSHIPS` / `_kinds_for_pair` / Alembic-migration triad that section 3.3.1's mechanical additions follow.
- `PRDs/product/crmbuilder-v2/methodology-schema-workstream-plan.md` — workstream master plan governing this and the next two schema-design conversations.
- `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md` — schema spec template this document follows.
- `PRDs/product/crmbuilder-v2/schema-design-kickoff-entity.md` — this conversation's seed prompt.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/domain.md` — predecessor spec; source of conventions inherited by this document (parent-prefix field naming, `{source}_{verb}_{target}` relationship-kind naming, soft-3-letter prefix posture, status-lifecycle shape, rejection-via-soft-delete posture, no-archived posture).
- `PRDs/process/research/evolved-methodology/phase-1-interview-guide.md` v0.2 — line 62 (entity-definition scope statement); section 7.2 (Domain Inventory output specification noting candidate entities are deferred to Phase 3); section 4.3 ("Do not start drafting Entity PRDs" — between-sessions discipline).
- `PRDs/process/research/evolved-methodology/evolved-methodology-phase-outline.md` — section 3 Phase 1 / Phase 3 boundary; informs the thin-shape posture.

#### 3.9.3 Related prior decisions informing this spec

- **DEC-006** — Universal references table as the cross-entity-type edge store. Direct architectural foundation for the `entity_scopes_to_domain` mechanism choice in section 3.3.1.
- **DEC-035** — `ListDetailPanel` master-widget + context-menu factory refactor. Informs master pane patterns in section 3.6.2.
- **DEC-036** — Right-click context menus uniform across all entity rows. Informs context-menu behavior in section 3.6.2.
- **DEC-038** — Derived fields as first-class methodology entities with explicit references to traversed relationship and source field. Forward-looking architectural posture for when fields land in v0.5+; no v0.4 implication for `entity`'s schema but cited for completeness.
- **DEC-039** — Minimum entity inventory and multi-tenancy posture. Directly justifies `entity`'s inclusion in v0.4's minimum-viable set despite Phase 1 not formally producing an Entity Inventory output; informs the thin-shape framing in section 1.
- **DEC-043** — SES-010 identifier-asymmetry resolution. Mandates the `GET /entities/next-identifier` helper endpoint cited in section 3.5.1.
- **DEC-046** — Parent-prefix field-naming convention for methodology entities. Establishes the field-naming pattern this spec inherits and applies (see section 3.2).
- **DEC-047** — `domain` status lifecycle, propose-verify gate, and rejection-via-soft-delete posture. Establishes the lifecycle pattern this spec adopts unchanged (see section 3.4).
- **DEC-048** — `domain` relationship posture and `{source}_{verb}_{target}` relationship-kind naming convention. Establishes the relationship-kind naming pattern this spec applies in registering `entity_scopes_to_domain` (see section 3.3.3).
- **DEC-049** — `domain` API surface, UI defaults, acceptance criteria for v0.4. Establishes the API-and-UI default patterns this spec adopts (see sections 3.5, 3.6, 3.7).

#### 3.9.4 Predecessor and successor conversations

- **Predecessor:** `domain` schema-design conversation. SES-012 close-out payload at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_012.json`. Produced `domain.md` v1.0, DEC-044 through DEC-049, and PI-006 / PI-007 / PI-008.
- **Successor:** `process` schema-design conversation. Kickoff at `PRDs/product/crmbuilder-v2/schema-design-kickoff-process.md`. Will inherit the conventions established in `domain.md` and applied here (parent-prefix field naming, `{source}_{verb}_{target}` relationship-kind naming, soft-3-letter prefix posture, status-lifecycle shape). Will register process-side relationship kinds (likely `process_belongs_to_domain` as a direct FK column per the `domain.md` working assumption, and `process_touches_entity` or similar as a references-entity edge per section 3.3.2 of this spec). The cross-spec consistency check at the v0.4-build-planning conversation validates that the source-side mechanism choices align with this spec's section 3.3.2 anticipations.

---

## 4. Migration and Reversibility (v1.1+)

### 4.1 Migration 0019_v0_5_entity_kind_and_variants

The PI-010 satisfier migration is additive and reversible. Operations, in order:

1. Add `entity_kind` TEXT NULL column to the `entities` table with a CHECK constraint admitting NULL or any of the five enum values (`person | organization | event | transaction | other`). Existing v0.4 records acquire NULL on upgrade and continue to validate as legal v1.1+ records.
2. Extend `refs.relationship_kind` CHECK to admit `entity_variant_of_entity`. The `refs.source_type` / `refs.target_type` CHECKs already admit `entity` from migration 0006, so no source/target CHECK changes are needed.

### 4.2 Backward compatibility

- `entity_kind` NULL is a first-class state — operator-deferred classification per DEC-292. No code path requires a non-NULL value.
- No `entity_variant_of_entity` edges are auto-created. Variant relationships are added by operators after v1.1 ships; legacy suffix-named records (none existed at v1.1 amendment time) remain operator-editable.
- Existing `entity_scopes_to_domain` references are unaffected.
- All 36 prior reference kinds remain admitted.

### 4.3 Reversibility

The `downgrade()` reverses both operations:

1. Hand-delete any rows in `refs` holding `entity_variant_of_entity`, then revert the CHECK to its 0018 form. Row loss in this step is documented behavior — variant edges created under v1.1+ are lost on downgrade; v0.4 records are unaffected.
2. Drop the `entity_kind` column and its CHECK constraint. Records authored under v1.1+ with a non-NULL `entity_kind` lose that value on downgrade.

### 4.4 No data migration required

DEC-293 records that no production variant data existed at v1.1 amendment time (the live engagement DB held only smoke-test entities). CBM-redo Phase 1 captures variants directly using the v1.1+ mechanism; no rewrite of suffix-named legacy records is performed. If a later engagement has accreted suffix-named variants between v0.4 and v1.1, operators may either (a) attach explicit `entity_variant_of_entity` edges between the records, leaving the names unchanged, or (b) rename the variant records and attach edges. Either pattern is forward-compatible.

### 4.5 Smoke verification

After applying migration 0019 to an engagement DB and restarting the API, a smoke check verifies the surface:

```bash
# 1. New column visible.
sqlite3 data/engagements/CRMBUILDER.db \\
  "SELECT entity_kind FROM entities LIMIT 1;"
# (expected: empty row — entity_kind is NULL for v0.4 records)

# 2. Vocab kind admitted.
curl -s http://127.0.0.1:8765/references -H 'Content-Type: application/json' \\
  -d '{"source_type":"entity","source_id":"ENT-001","target_type":"entity","target_id":"ENT-002","relationship":"entity_variant_of_entity"}'
# (expected: 201 + reference body)

# 3. Cardinality enforced.
curl -s http://127.0.0.1:8765/references -H 'Content-Type: application/json' \\
  -d '{"source_type":"entity","source_id":"ENT-001","target_type":"entity","target_id":"ENT-003","relationship":"entity_variant_of_entity"}'
# (expected: 422 cardinality_violation)
```

---

*End of document.*

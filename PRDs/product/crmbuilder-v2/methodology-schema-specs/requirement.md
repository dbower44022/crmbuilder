# Methodology Entity Schema Spec — `requirement`

**Last Updated:** 05-25-26
**Status:** Draft v1.0 — produced as part of PI-004 resolution
**Position in workstream:** PI-004 methodology-entity expansion (v0.5+). Sibling of `field` (most urgent), `persona` (PI-003), `manual_config`, `test_spec`. Inherits conventions established by the v0.4 methodology-entity-schema-design workstream (`domain` → `entity` → `process` → `crm_candidate`).
**Predecessor specs (conventions inherited):** `domain.md`, `entity.md`, `process.md`, `crm_candidate.md`
**Sibling specs (PI-004 cohort):** `field.md` (most urgent — `requirement_touches_field` declared here as outbound, anticipates `field.md`'s registration), `persona.md` (PI-003), `manual_config.md`, `test_spec.md` (anticipates `requirement_verified_by_test_spec` as inbound)

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-25-26 | Doug Bower / Claude | Initial draft. Produced as a PI-004 deliverable. Defines `requirement` as the v2 methodology entity type that hosts the testable statements of what the CRM must do — surfaced in iteration build conversations and verified by `test_spec` records once that sibling lands. Adopts conventions established by the v0.4 workstream (parent-prefix field naming per DEC-046, source-first relationship-kind naming per DEC-048, soft-3-letter prefix posture, three-status propose-verify lifecycle, rejection-via-soft-delete, no `archived`). Establishes five outbound relationship kinds — `requirement_scopes_to_domain`, `requirement_touches_entity`, `requirement_touches_field`, `requirement_realized_by_process`, `requirement_verified_by_test_spec` — three of which target sibling PI-004 entities not yet specified. |

---

## Change Log

**Version 1.0 (05-25-26):** Initial creation. Defines seven substantive fields (`requirement_identifier`, `requirement_name`, `requirement_description`, `requirement_priority`, `requirement_acceptance_summary`, `requirement_notes`, `requirement_status`) plus inherited timestamps; four-value MoSCoW priority enum (`must` / `should` / `could` / `wont`); three-status lifecycle mirroring `domain` and `entity` (`candidate` / `confirmed` / `deferred`) with one-way propose-verify gate; case-insensitive **global** name uniqueness within the engagement (a requirement is a global statement, not scoped per-domain); no FK columns on the requirement table; five outbound relationship kinds declared via the references entity (`requirement_scopes_to_domain`, `requirement_touches_entity`, `requirement_touches_field`, `requirement_realized_by_process`, `requirement_verified_by_test_spec`); standard endpoint set with decomposed reference handling. Master pane defers the Priority column choice as an open question for the v0.5 build conversation (mirrors the entity-panel Domains-column posture). Five decisions produced (DEC placeholders DEC-AAA through DEC-EEE — numbers assigned at conversation close) and four new planning items surfaced (requirement-to-requirement dependencies, structured acceptance shape, effort estimates, stakeholder attribution). Acceptance criteria captured as 15 testable statements covering schema migration, vocabulary registration for all five outbound kinds, MoSCoW enum validation, and a 10-record CBM sample.

---

## 1. Purpose and Position

This document specifies the `requirement` entity type for v2's storage layer. It is one of four PI-004 deliverables that extends v2's methodology-entity coverage beyond the v0.4 workstream's `domain` / `entity` / `process` / `crm_candidate` foundation. PI-004 covers `field`, `requirement`, `manual_config`, and `test_spec`; this spec is the requirement portion.

A `requirement` is a discrete, testable statement of what the CRM must do — e.g., "Mentor application form must capture availability slots", "Email confirmation sent when mentor application status changes to approved". Requirements are surfaced in the evolved methodology's iteration build conversations (Phase 3+ in the evolved-methodology phase outline) and are the testable units that `test_spec` records verify once the system is deployed. Where `entity` records describe the nouns the CRM models and `process` records describe the workflows clients run, `requirement` records describe the discrete capabilities the CRM exposes to support those processes operating on those entities.

This spec inherits the conventions established by the v0.4 methodology-entity-schema-design workstream:

- **Parent-prefix field naming** (DEC-046): all non-identifier, non-timestamp fields are prefixed with the parent entity name. All fields including identifier and timestamps adopt the prefix in this spec for full convention consistency.
- **`{source}_{verb}_{target}` relationship-kind naming** (DEC-048): vocabulary entries involving methodology entities are named source-first, with the source entity name, a verb phrase, and the target entity name.
- **Soft-3-letter prefix posture** (DEC-044 working assumption): three-letter identifier prefixes adopted unless 3-letter ambiguity forces 4. `REQ` reads unambiguously and has no collision with the existing prefix set (DEC, SES, RSK, PI, TOP, REF, CHR, STA, DOM, ENT, PROC, CRM, WS, CONV, RB, WT, COP, DEP, CM, PER, FLD).
- **Three-status propose-verify lifecycle** (DEC-047): `candidate` / `confirmed` / `deferred` with one-way gate out of `candidate` and bidirectional movement between `confirmed` and `deferred`. Rejection handled by soft-delete; no `archived` status.

`requirement` is the connective tissue of the methodology entity graph in PI-004's cohort: it scopes to domains (like `entity`), touches one or more entities (the noun the requirement operates on), touches one or more fields (the column-level specificity once `field` lands), is realized by one or more processes (the workflows that satisfy it), and is verified by one or more test specs (the checks that confirm it). Five outbound relationship kinds — more than any v0.4 methodology entity — reflect this position. Three of the five targets are sibling PI-004 entities not yet specified (`field`, `test_spec`); the spec declares the source-side kinds here and notes the inbound anticipations on the target-side specs, mirroring the `entity.md` → `process.md` source-of-truth pattern.

The schema in v0.5+ shipping shape is thin in the same sense `entity` was thin in v0.4: a name, a description, a priority classification, a plain-text acceptance summary, an optional consultant scratchpad, and a lifecycle status. Structured acceptance shapes (Given / When / Then), requirement-to-requirement dependencies, effort estimates, and stakeholder attribution are explicitly deferred to subsequent planning items.

---

## 2. Summary

A `requirement` record in v2 represents one testable statement of what the CRM must do for the engagement. The consultant surfaces requirements during iteration build conversations as the team walks through each process step by step and asks "what must the CRM do to support this?". Each `requirement` record captures a short client-language name (e.g., "Capture mentor availability slots"), a plain-text description of the capability in enough depth to scope the work, a MoSCoW priority classification (`must` / `should` / `could` / `wont`), a plain-text acceptance summary describing what "this is satisfied" looks like at the methodology level, an optional internal-notes scratchpad for consultant rationale, and a lifecycle status tracking whether the requirement is a CRM-Builder-proposed candidate, a client-confirmed scope member, or an acknowledged-but-deferred capability.

Domain affiliation, entity coverage, field coverage, process realization, and test-spec verification are all captured separately as references in v2's universal references store, supporting the methodology reality that a single requirement may span multiple domains (e.g., "Send an email confirmation on status change" applies wherever status changes exist), touch multiple entities (e.g., the same notification requirement touches Contact and Engagement), and be realized by multiple processes (a requirement may be partially satisfied by several workflows acting together).

The shipping shape in v0.5+ is the thinnest shape that can faithfully host iteration build conversation output. It deliberately omits structured acceptance (Given / When / Then is plain-text-in-the-summary in this shipping shape; structured tracked as a future PI), requirement-to-requirement dependencies (tracked separately), effort estimates / sizing (tracked as a v0.6+ PI), and stakeholder attribution (tracked as a v0.6+ PI). The minimum-viable shape grows additively as iteration build experience reveals what `requirement` needs to carry.

---

## 3. Schema Specification

### 3.1 Identity

| Field | Value |
|-------|-------|
| Entity type name (storage) | `requirement` |
| Display name (singular) | Requirement |
| Display name (plural) | Requirements |
| Identifier prefix | `REQ` |
| Identifier format | `REQ-NNN`, zero-padded to 3 digits (e.g., `REQ-001`, `REQ-042`) |
| Identifier auto-assignment | Server-side on POST omission per PI-002; helper at `GET /requirements/next-identifier` per DEC-043 |

`REQ` is three letters under the soft-3-letter posture established by `domain.md` section 3.1 and carried through `entity.md` section 3.1. The prefix reads unambiguously as "requirement", has no collision with existing prefixes (DEC, SES, RSK, PI, TOP, REF, CHR, STA, DOM, ENT, PROC, CRM, WS, CONV, RB, WT, COP, DEP, CM, PER, FLD), and matches the existing v2 governance- and methodology-entity norm. No deviation from defaults; PI-002 makes identifier optional on POST and DEC-043's `GET /requirements/next-identifier` helper ships alongside the standard endpoint set.

### 3.2 Fields

Field naming follows the parent-prefix convention established by `domain.md` (DEC-046) and carried through every subsequent methodology spec: all non-identifier, non-timestamp fields are prefixed with the parent entity name (`requirement_`). All fields including identifier and timestamps adopt the prefix in v0.5+ for full convention consistency.

#### 3.2.1 Identity fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `requirement_identifier` | TEXT | yes | server-assigned | `^REQ-\d{3}$`, unique | The methodology-entity identifier in `REQ-NNN` format. Server-assigned when omitted from POST body per PI-002. |
| `requirement_name` | TEXT | yes | — | non-empty trimmed; case-insensitive **globally unique within the engagement** | Short client-language name of the requirement (e.g., "Capture mentor availability slots", "Email confirmation on mentor approval"). |

**Global, not per-domain, name uniqueness.** A requirement is a global statement of what the system must do; the same capability scoped to two domains would be one requirement with two `requirement_scopes_to_domain` edges, not two requirements. The uniqueness check is case-insensitive across the entire `requirements` table, independent of any domain affiliations. This mirrors `entity_name`'s posture (case-insensitive global within the engagement per `entity.md` section 3.2.1) and contrasts with `process_name`'s per-domain uniqueness (a process is owned by exactly one domain so its name uniqueness scopes there).

#### 3.2.2 Content fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `requirement_description` | TEXT | yes | — | non-empty trimmed | Plain-text description of the capability in enough depth to scope the work. Typically a paragraph or two captured from the iteration build conversation (e.g., "When a mentor application moves to status `approved`, send a confirmation email to the applicant's primary email address using the mentor-application-confirmation template. The email must include the mentor's first name, the orientation session date, and a link to the orientation prep page."). Plain text in v0.5+; markdown support deferred to CBM-redo signal. |
| `requirement_acceptance_summary` | TEXT | yes | — | non-empty trimmed | Plain-text summary of what "this requirement is satisfied" looks like at a methodology level — the consultant's articulation of the success condition, not yet decomposed into structured test steps. (e.g., "An approved mentor receives a confirmation email within 5 minutes containing their first name, the orientation date, and the prep-page link. The email arrives in the inbox not the spam folder when sent to a Gmail address."). Plain text in v0.5+; structured Given / When / Then shape tracked as a future PI (see section 3.8). |
| `requirement_notes` | TEXT | no | — | — | Internal consultant scratchpad. Not part of any client-facing render. Used to capture iteration-conversation rationale, push-back trails, between-session reasoning about scope and priority. Plain text in v0.5+. Mirrors `domain_notes` and `entity_notes`. |

**Separation of description and acceptance summary.** `requirement_description` answers "what is the capability?"; `requirement_acceptance_summary` answers "how do we know it works?". The two fields are kept distinct because the iteration build conversation surfaces them at different moments (description as the team walks through what the CRM must do; acceptance as the team turns to "and how would we test this?"), and because the two map cleanly onto the eventual `test_spec` decomposition: each `requirement_verified_by_test_spec` edge points to a test spec that operationalizes the acceptance summary as discrete test steps. Collapsing the two fields would lose the methodology-level success articulation that survives even when no test specs are authored yet.

#### 3.2.3 Classification fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `requirement_priority` | TEXT | yes | `should` | enum: `must` \| `should` \| `could` \| `wont` | MoSCoW priority classification. `must` — required for the engagement to be considered successful; `should` — important but not blocking; `could` — desirable if cheap; `wont` — explicitly out of scope but recorded to prevent re-litigation. Default starter value is `should` rather than `must` so consultants must affirmatively escalate to `must` (preserves MoSCoW discipline). |
| `requirement_status` | TEXT | yes | `candidate` | enum: `candidate` \| `confirmed` \| `deferred`; valid transitions per section 3.4 | Lifecycle status. See section 3.4 for the transition map. |

**`wont` vs `deferred` distinction.** `requirement_priority = wont` and `requirement_status = deferred` look superficially similar but carry distinct semantics. `wont` is a priority statement — "we have considered this capability and consciously decided not to include it in this engagement's scope" — and lives alongside the requirement so it remains visible in MoSCoW-grouped renders as the explicit non-promise. `deferred` is a lifecycle statement — "this is a real capability we acknowledge but are not pursuing right now" — and is more time-bounded; a `deferred` requirement may later move back to `confirmed` if circumstances change. A requirement may be both `wont`-priority and `deferred`-status (we declined it; we're not actively reconsidering); a requirement may also be `wont`-priority and `confirmed`-status (we firmly agreed this is out of scope, and that decision itself is verified). The two fields are kept independent rather than collapsed into a five-value status enum to preserve the MoSCoW vocabulary's clarity for client-facing renders.

**No `must`-promotion gate.** The schema does not prevent freely moving a requirement from `should` to `must`. MoSCoW discipline is conversational, not algorithmic; the consultant's job is to surface promotion moments. A future PI may add a "must promotion requires citation" rule once the iteration build conversation accumulates enough data to know whether the gate adds value.

#### 3.2.4 Relationship fields

None in v0.5+. `requirement` has no outgoing FK columns on its table. Domain affiliation, entity coverage, field coverage, process realization, and test-spec verification are all captured via the references entity (see section 3.3); inter-requirement dependencies are deferred (see section 3.8).

#### 3.2.5 Timestamp fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `requirement_created_at` | DATETIME | yes | server-set on insert | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `requirement_updated_at` | DATETIME | yes | server-set on insert and on each update | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `requirement_deleted_at` | DATETIME | no | null until soft-delete | ISO 8601 UTC when set | Inherited base behavior. Set on DELETE; cleared on POST `/restore`. |

**No storage-level length caps.** Text fields are unconstrained at the storage layer in v0.5+. The UI provides soft guidance via placeholder text. Pathological-input handling deferred to CBM-redo signal; length caps are easy to add via migration later if needed. Mirrors `domain` and `entity` posture.

### 3.3 Relationships

#### 3.3.1 Outgoing relationships

`requirement` declares five outgoing relationship kinds in v0.5+. Three target sibling PI-004 entities (`field`, `test_spec`) not yet specified; those targets must exist as live entity types in the same v0.5+ release before this spec's vocabulary registrations land cleanly. The build-planning conversation that integrates PI-004's cohort sequences the migrations accordingly.

| relationship_kind | source | target | mechanism | cardinality | semantics |
|-------------------|--------|--------|-----------|-------------|-----------|
| `requirement_scopes_to_domain` | `requirement` | `domain` | references-entity edge | many-to-many | A requirement is scoped to one or more domains. Mirrors `entity_scopes_to_domain`'s posture — a single requirement may legitimately span domains (e.g., "Send email on status change" applies wherever status changes exist). |
| `requirement_touches_entity` | `requirement` | `entity` | references-entity edge | many-to-many | A requirement reads, writes, or otherwise operates on records of one or more entity types. Phase 3+ iteration build work surfaces these edges as the team articulates which nouns the requirement involves. |
| `requirement_touches_field` | `requirement` | `field` | references-entity edge | many-to-many | A requirement reads or writes specific fields on entities it touches. Provides the column-level specificity once `field` lands. Anticipates `field.md` registering `field` as a live entity type. |
| `requirement_realized_by_process` | `requirement` | `process` | references-entity edge | many-to-many | A requirement is satisfied by the execution of one or more processes. Mirrors the iteration build pattern where the consultant traces a requirement to the process(es) that operationalize it; one requirement may be realized by several processes acting together (e.g., a notification requirement may be realized by both the application-approval process and the renewal process). Anticipates `process` schema growth per PI-005. |
| `requirement_verified_by_test_spec` | `requirement` | `test_spec` | references-entity edge | many-to-many | A requirement is verified by one or more test specs. A single requirement may decompose into multiple discrete tests (each acceptance-summary clause becoming its own spec); a single test spec may verify multiple requirements when one check exercises overlapping capability. Anticipates `test_spec.md` registering `test_spec` as a live entity type — `test_spec.md` section 3.3.2 will note this as anticipated inbound. |

All five mechanisms are the references entity at v2's `refs` table, governed by the existing `RELATIONSHIP_RULES` infrastructure (DEC-006). Direct FK columns were rejected per the same reasoning DEC-053 applied to `entity_scopes_to_domain`: the cardinalities are all many-to-many, references-discipline keeps the requirement-table schema small, the inverse queries ("what requirements touch this entity?", "what requirements are realized by this process?") are trivial through the existing reverse-edge query, and the build-planning conversation can sequence the five vocabulary registrations alongside the field- and test_spec-entity migrations in a single coordinated v0.5+ release.

**Mechanical additions per CLAUDE.md line 48:**

1. All five new kinds added to `REFERENCE_RELATIONSHIPS` in `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`.
2. `_kinds_for_pair` extended so:
   - `(requirement, domain)` returns `{requirement_scopes_to_domain}`
   - `(requirement, entity)` returns `{requirement_touches_entity}`
   - `(requirement, field)` returns `{requirement_touches_field}`
   - `(requirement, process)` returns `{requirement_realized_by_process}`
   - `(requirement, test_spec)` returns `{requirement_verified_by_test_spec}`
3. Alembic migration extending the `refs.relationship_kind` CHECK constraint to include all five new values.

**Cardinality and validation (all five kinds):**

- Many-to-many. No upper bound on either side.
- Zero-affiliation is permitted on the requirement side for every kind; iteration build conversations sometimes surface a requirement before its domain / entity / field / process / test_spec touchpoints are settled, and the references discipline must not force pre-decided affiliation.
- Source must be a live requirement record; target must be a live record of the corresponding type.
- Duplicate `(source_id, target_id, relationship_kind)` tuples are rejected by the references-table uniqueness constraint.

**Lifecycle semantics (all five kinds):**

- Soft-deleting a requirement does not cascade-delete its outbound references; the references persist (existing v2 behavior) and remain visible via the show-deleted UI toggle on either side.
- Same for soft-deleting any of the five target types.
- Restoring either endpoint restores its relationship rows in place.

**Verb-phrase semantics for the five kinds:**

- "scopes to" — relevance / appears in / applies within the named domain. Affiliation, not ownership. Identical semantics to `entity_scopes_to_domain`.
- "touches" — reads, writes, or otherwise operates on records of the named entity / values of the named field. Used for both entity-level and field-level coverage to preserve a consistent verb across the granularity tiers.
- "realized by" — satisfied by the execution of the named process. The requirement's capability is delivered by running the process; multiple processes may collectively realize a single requirement.
- "verified by" — confirmed correct by passing the named test spec. The verification edge is the seam between the requirement-as-statement and the test-as-evidence.

#### 3.3.2 Inbound relationships (anticipated; declared by future source-side specs)

`requirement` is not currently the target of any source-side relationship in the v0.5+ PI-004 cohort as drafted. Future v0.6+ entity types may anchor inbound edges (e.g., a `release` or `iteration` entity type binding a requirement to the release in which it is intended to ship; a `stakeholder` entity type expressing requirement-to-stakeholder attribution per the v0.6+ PI surfaced in section 3.8). None are declared in v0.5+; their formal vocabulary registration belongs to the source-side specs that introduce them.

Inter-requirement dependencies (e.g., `requirement_blocks_requirement`) are deferred to a CBM-redo-informed PI rather than declared inbound here. The pattern is genuinely useful in the abstract — capabilities A and B may need to land in a particular order, with A blocking B — but the iteration build conversation may surface these dependencies as conversational ordering hints that don't need formal vocabulary, or it may surface them as a strict dependency graph that needs schema-level treatment. v0.5+ ships without inter-requirement edges; the CBM-redo iteration build experience decides whether the schema gap is real.

#### 3.3.3 Cross-spec relationship-kind naming convention — adopted, not established

This spec adopts the `{source}_{verb}_{target}` relationship-kind naming convention established by `domain.md` section 3.3.3 (DEC-048) and applied across `entity.md`, `process.md`, and `crm_candidate.md`. All five vocabulary entries this spec registers conform to the pattern: source entity first, verb phrase, target entity. The convention is not re-decided here; it carries forward from the v0.4 workstream.

#### 3.3.4 Hierarchy

`requirement` does not use the self-referential parent-child hierarchy pattern in v0.5+. Requirement decomposition (a high-level requirement broken into sub-requirements) is genuinely a hierarchical pattern in some methodologies, but the evolved methodology's iteration build conversation produces flat lists of testable statements rather than tree-shaped requirement hierarchies; the consultant's discipline is to author each statement at the same granularity rather than mix levels. If real-engagement experience surfaces a need for hierarchy, a future PI adds a `requirement_parent_identifier` self-FK following the existing `topic.parent_topic` pattern. Listed as a CBM-redo open question in section 3.8.

### 3.4 Lifecycle

#### 3.4.1 Status values

| Status value | Description | Valid predecessors | Valid successors |
|--------------|-------------|--------------------|------------------|
| `candidate` | CRM Builder has proposed; awaiting client verification. **Default starter status.** | (none — starter) | `confirmed`, `deferred` |
| `confirmed` | Client has verified this is a requirement in scope for the engagement. | `candidate`, `deferred` | `deferred` |
| `deferred` | Client has acknowledged this is a real requirement but it is out of current engagement scope. | `candidate`, `confirmed` | `confirmed` |

The structure mirrors `domain.md` section 3.4.1 and `entity.md` section 3.4.1 exactly; the semantics map cleanly: requirements, like domains and entities, are surfaced by the consultant and verified by the client.

#### 3.4.2 Transition semantics

The status lifecycle implements the same **one-way propose-verify gate** established for `domain` (DEC-047) and inherited by `entity`: once a requirement has moved out of `candidate` (in either direction, to `confirmed` or to `deferred`), it does not regress to `candidate`. The rationale: the propose-verify moment is a meaningful client-engagement event; if the consultant later wants to fundamentally rethink a verified requirement, the right action is to edit the record's content (or its priority), not to regress its status. Status reflects engagement-scope position, not deliberation state.

Movement between `confirmed` and `deferred` in either direction is permitted to support mid-engagement scope changes (e.g., a requirement initially confirmed but later deprioritized; a previously-deferred requirement pulled back into scope at a later iteration).

#### 3.4.3 Status independence from priority

A requirement's `requirement_status` and `requirement_priority` are independent. A `must` requirement may be `deferred` (we agree this is critical; we are not actively pursuing it right now); a `wont` requirement may be `confirmed` (we firmly agreed this is out of scope, and that decision itself is verified). The two fields track different facets — priority answers "how important?", status answers "what is its current scope position in our engagement?" — and collapsing them would lose expressiveness in client-facing renders. Edit affordances on each field operate independently; changing one does not cascade to the other.

#### 3.4.4 Status independence from affiliation status

Mirroring the cross-spec principle established in `entity.md` section 3.4.3: a requirement's `requirement_status` is its own field on its own table, set by the consultant based on client verification of the requirement itself. **It is not derived from the statuses of the domains, entities, fields, processes, or test specs the requirement references.** A requirement may legitimately span domains at different lifecycle positions; changing a domain's status does not cascade to the inbound `requirement_scopes_to_domain` references' source-side records.

#### 3.4.5 Rejection via soft-delete

When the client rejects a CRM-Builder-proposed requirement candidate ("no, that's not actually a capability we need"), the rejection is handled by soft-delete rather than a `rejected` status value. `DELETE /requirements/{requirement_identifier}` sets `requirement_deleted_at`; the record persists for audit and history, surfaces under the `?include_deleted=true` toggle, and is restorable via POST `/restore`. The cross-spec principle established in `domain.md` section 3.4.3 carries forward unchanged: **status values track engagement-scope lifecycle; soft-delete tracks existence-in-the-record.** Note that `wont`-priority is a distinct posture (see section 3.2.3) — a `wont` requirement is kept in the record explicitly so it remains visible as the consciously-declined capability; soft-delete is for capabilities that turned out not to be real requirements at all.

#### 3.4.6 No `archived` status

`archived` is not introduced in v0.5+. Soft-delete combined with the "show deleted" toggle and the explicit `wont` priority value already cover the "retained for record, not in active scope" use cases. Mirrors `domain.md` section 3.4.4 and `entity.md` section 3.4.5.

#### 3.4.7 Soft-delete semantics

Soft-delete inherits v2's standard behavior:

- DELETE sets `requirement_deleted_at` to the current ISO 8601 UTC timestamp.
- Soft-deleted records do not appear in `GET /requirements` by default.
- `GET /requirements?include_deleted=true` returns soft-deleted records alongside live ones.
- POST `/requirements/{requirement_identifier}/restore` clears `requirement_deleted_at` and reappears the record in the default list.
- Restore on a record that is not soft-deleted returns HTTP 422.

All five outbound reference kinds on a soft-deleted requirement are NOT cascade-deleted. They persist in the references table; show-deleted toggles on either side surface them. This matches v2's existing references-table soft-delete behavior.

### 3.5 API Surface

#### 3.5.1 Endpoints

| Method | Path | Body | Notes |
|--------|------|------|-------|
| GET | `/requirements` | — | List endpoint. Returns active records by default. Supports `?include_deleted=true` to include soft-deleted records. |
| GET | `/requirements/{requirement_identifier}` | — | Single fetch by identifier. Returns 404 if not found. |
| POST | `/requirements` | full record minus `requirement_identifier` (server-assigned per PI-002) | Create. Returns 201 with the assigned identifier in the response body. Server-side validation per section 3.2 applied. |
| PUT | `/requirements/{requirement_identifier}` | full record | Full replace. `requirement_identifier` in body must match the path; mismatch returns 422. |
| PATCH | `/requirements/{requirement_identifier}` | partial record | Partial update. Status-transition validation applied (see 3.5.3). |
| DELETE | `/requirements/{requirement_identifier}` | — | Soft-delete; sets `requirement_deleted_at`. Idempotent (DELETE on an already-soft-deleted record returns 200 with no state change). |
| POST | `/requirements/{requirement_identifier}/restore` | — | Clears `requirement_deleted_at`. Returns 422 if the record is not soft-deleted. |
| GET | `/requirements/next-identifier` | — | Returns `{"next": "REQ-NNN"}` for the next available identifier. Per SES-010 resolution (DEC-043). |

**No deviations from the cross-spec default endpoint set.** No bulk operations, no inline-reference convenience endpoints, no priority-grouped list endpoints. All endpoints follow the `{data, meta, errors}` envelope per CLAUDE.md's v2 API conventions; any inline `jq` or shell snippet reading responses unwraps `.data` first.

#### 3.5.2 Identifier auto-assignment

`requirement_identifier` is server-assigned on POST when omitted from the request body per PI-002. The assignment logic queries the current maximum `requirement_identifier` (including soft-deleted records, to avoid identifier reuse) and increments the numeric suffix via the SAVEPOINT-retry helper that backs PI-002's concurrent-safe assignment. The `GET /requirements/next-identifier` helper exposes the same logic for clients that want to know the assigned identifier before POSTing.

Supplying an explicit identifier on POST is still supported per PI-002: the value must match `^REQ-\d{3}$` and not collide with an existing row (collision → 409, malformed → 422).

#### 3.5.3 Status-transition validation

Status transitions are validated server-side at the access layer. PATCH or PUT requests that specify a `requirement_status` value that is not a valid successor of the current value (per section 3.4.1) return HTTP 422 with a body of the form:

```
{
  "error": "invalid_status_transition",
  "from": "<current status>",
  "to": "<requested status>"
}
```

The default-`candidate` rule applies on POST: if `requirement_status` is omitted, the server assigns `candidate`. POST with `requirement_status` explicitly set to a non-starter value is permitted (e.g., bulk-importing already-confirmed requirements from prior engagement records). The default-`should` rule for `requirement_priority` applies symmetrically: omission assigns `should`; any of the four enum values is permitted on POST.

#### 3.5.4 Priority enum validation

`requirement_priority` is validated against the four-value enum `{must, should, could, wont}` on POST, PUT, and PATCH. Insertions or updates with a value outside the enum return HTTP 422 with the v2 error envelope. The four values are stored verbatim as lowercase strings; the UI is responsible for any display transformation (e.g., rendering "Must" with title-case in the master pane).

#### 3.5.5 Decomposed reference handling

References to domains, entities, fields, processes, and test specs are NOT inlined into the requirement create or update bodies. To attach any of the five outbound reference kinds, the client makes a separate `POST /references` with the appropriate `source_type`, `source_id`, `target_type`, `target_id`, and `relationship_kind`. For example:

```
{
  "source_type": "requirement",
  "source_id": "REQ-NNN",
  "target_type": "process",
  "target_id": "PROC-NNN",
  "relationship_kind": "requirement_realized_by_process"
}
```

This decomposed posture keeps the requirement API consistent with v2's references-first discipline (DEC-006) and matches how every other methodology entity handles references. The New dialog and detail-pane "Add reference" affordance hide the multi-call sequence behind UI gestures, but the API stays decomposed; no `/requirements/{id}/touches` or similar shortcut endpoint is introduced.

#### 3.5.6 Other endpoint specifics

- All endpoints return JSON.
- 4xx error responses use the existing v2 error envelope shape per CLAUDE.md's `{data, meta, errors}` convention.
- No additional list query parameters beyond `?include_deleted=true` in v0.5+. Client-side filtering over the expected requirement count is sufficient for the CBM redo's first iteration; server-side filtering deferred to CBM-redo signal.

### 3.6 UI Considerations

This spec adopts the spec guide's default `ListDetailPanel` layout with no architectural deviations. Specifics for `requirement` follow.

#### 3.6.1 Sidebar

The "Methodology" sidebar group introduced by `domain.md` section 3.6.1 hosts the new `requirement` entry. Position within the Methodology group follows PI-004 cohort order (sibling-spec sequencing is decided in the v0.5+ build-planning conversation, but a reasonable working sequence is):

1. Domains
2. Entities
3. Fields (PI-004)
4. Processes
5. **Requirements** (this spec)
6. Manual Configs (PI-004)
7. Test Specs (PI-004)
8. CRM Candidates
9. Personas (PI-003)

The five PI-004 entries and the PI-003 entry ship together in the same v0.5+ release; the exact ordering within the Methodology group is a UI-layer decision that the v0.5+ build-planning conversation finalizes. The schema does not constrain ordering.

#### 3.6.2 Master pane

`ListDetailPanel`-backed list with five columns:

| Stored field | Display header | Width | Notes |
|--------------|----------------|-------|-------|
| `requirement_identifier` | Identifier | narrow | Default sort key, ascending |
| `requirement_name` | Name | wide | Client-language name |
| `requirement_priority` | Priority | narrow | Enum value rendered title-cased ("Must", "Should", "Could", "Won't") |
| `requirement_status` | Status | narrow | Enum value rendered as-is |
| `requirement_updated_at` | Updated | narrow | Localized date/time |

Right-click context menu offers New / Edit / Delete / Restore, consistent with v0.3 governance-entity panels per DEC-035 and DEC-036.

**Priority column included by default, but deferred for v0.5 build conversation review.** The Priority column has natural value for MoSCoW-informed scanning ("show me all the musts at a glance") and is one of the five master-pane columns called out in this spec's acceptance criteria. However, the same logic that deferred the `entity` panel's Domains column to PI-009 (`domain.short_code` would render bare DOM-NNN identifiers without mnemonic value) might argue the Priority column adds little if the CBM redo's iteration build conversations rarely surface MoSCoW scans at the master-pane level. The v0.5 build conversation reviews this column choice against `entity.md`'s deferred-column precedent before shipping. Listed as an open question in section 3.8.

#### 3.6.3 Detail pane

Vertical layout, fields in section-3.2 order:

1. `requirement_identifier` — read-only label
2. `requirement_name` — single-line text editor
3. `requirement_description` — multi-line text editor with placeholder "Plain-text description of the capability"
4. `requirement_acceptance_summary` — multi-line text editor with placeholder "What 'this is satisfied' looks like at a methodology level"
5. `requirement_notes` — multi-line text editor under a collapsible "Internal notes" section header, collapsed by default
6. `requirement_priority` — combo box with the four enum values rendered title-cased
7. `requirement_status` — combo box with the three enum values
8. `ReferencesSection` widget — renders all five outbound reference kinds (`requirement_scopes_to_domain`, `requirement_touches_entity`, `requirement_touches_field`, `requirement_realized_by_process`, `requirement_verified_by_test_spec`) plus any inbound references introduced by future source-side specs. The widget groups references by kind for readability, exposes the existing "Add reference" affordance for attaching new references after the requirement record exists, and renders each reference as a clickable identifier link to the target record.

The collapsed-by-default treatment of `requirement_notes` matches `domain_notes` and `entity_notes` — internal consultant scratchpad, not part of any client-facing render.

#### 3.6.4 Create dialog

Modal `EntityCrudDialog` subclass with field order matching the detail pane. Specifics:

- `requirement_identifier` not shown in create mode (server-assigned per PI-002).
- `requirement_priority` defaults to `should`; user may select any of the four values.
- `requirement_status` defaults to `candidate`; user may select a different starter value if importing established requirement records.
- Required-field validation client-side before submit.
- Server-side validation errors (uniqueness, format, transition, priority-enum) surface inline.

**Reference attachment flow — open question for v0.5 build.** Same two patterns as `entity.md` section 3.6.4: (a) create-then-attach (the New dialog creates the requirement record only; the user adds references from the detail pane afterward); (b) create-with-attach (the New dialog includes multi-selects for the various reference kinds; on submit the UI runs POST `/requirements` followed by N × POST `/references` in sequence). The v0.5 build-planning conversation decides which pattern to implement, with consistency across all PI-004 entity types preferred over per-entity-type variation.

#### 3.6.5 Edit dialog

Same shape as create. `requirement_identifier` displayed as read-only label. Status transitions enforced per section 3.4.1; invalid selections in the status combo are either prevented (recommended UX) or rejected by the server with the 422 surfacing inline (acceptable fallback). Priority changes have no transition rules — any-to-any movement among the four enum values is permitted.

#### 3.6.6 Delete dialog

`EntityCrudDeleteDialog` with edge-text confirmation. The user types the `requirement_identifier` value (e.g., `REQ-002`) to enable the Delete button, matching v0.3 governance-entity patterns. Confirmation soft-deletes the record. All five outbound reference kinds on the soft-deleted requirement persist per section 3.4.7.

### 3.7 Acceptance Criteria

The following 15 statements define what "this entity type is correctly implemented in the v0.5+ PI-004 cohort release" looks like. Each is concrete and testable; v0.5+ build planning translates these into specific test cases.

1. **Schema migration applies cleanly.** Alembic migration creates the `requirements` table with all ten columns (`requirement_identifier`, `requirement_name`, `requirement_description`, `requirement_acceptance_summary`, `requirement_priority`, `requirement_status`, `requirement_notes`, `requirement_created_at`, `requirement_updated_at`, `requirement_deleted_at`), correct types and constraints, and runs both forward and backward without error.

2. **`requirement_identifier` format constraint enforced.** Insertions with `requirement_identifier` not matching `^REQ-\d{3}$` raise a validation error at the access layer. Omitted identifier on POST is auto-assigned per PI-002.

3. **`requirement_name` uniqueness enforced case-insensitively and globally.** Inserting a second row whose `requirement_name` matches an existing row by lowercase comparison raises a uniqueness violation, independent of any domain affiliations. (Distinct from `process_name`'s per-domain uniqueness; this is the same posture as `entity_name`.)

4. **`requirement_priority` enum validation enforced.** Insertions or updates with `requirement_priority` outside `{must, should, could, wont}` return HTTP 422. Omitted priority on POST defaults to `should`. Any-to-any transitions among the four values are permitted (no priority transition rules).

5. **`requirement_status` enum and transition validation.** Insertions with `requirement_status` outside `{candidate, confirmed, deferred}` are rejected. PATCH/PUT requesting an invalid transition (e.g., `confirmed` → `candidate`) returns HTTP 422 with `{"error": "invalid_status_transition", "from": ..., "to": ...}`. Default-on-POST is `candidate`.

6. **Access-layer methods exist with expected signatures.** `client.list_requirements()`, `client.get_requirement(identifier)`, `client.create_requirement(...)`, `client.update_requirement(identifier, ...)`, `client.patch_requirement(identifier, ...)`, `client.delete_requirement(identifier)`, `client.restore_requirement(identifier)`, `client.next_requirement_identifier()` exist and pass unit tests covering happy path and at least one error case each.

7. **REST endpoints return expected responses for representative cases.** All eight endpoints from section 3.5 return correct HTTP status and JSON bodies (wrapped in the `{data, meta, errors}` envelope) for happy-path and validation-failure cases.

8. **Identifier auto-assignment safe under concurrency.** `GET /requirements/next-identifier` returns `{"next": "REQ-NNN"}` for the next available number. POST with `requirement_identifier` omitted assigns the same value via the PI-002 SAVEPOINT-retry helper. Two concurrent POSTs do not assign the same identifier (verified by a concurrent-insert test).

9. **Soft-delete and restore round-trip correctly.** DELETE sets `requirement_deleted_at`; the record disappears from `GET /requirements`. `GET /requirements?include_deleted=true` shows it. POST `/restore` clears `requirement_deleted_at`; the record reappears in the default list. Restore on a record that is not soft-deleted returns 422. Outbound references on a soft-deleted requirement persist.

10. **`Requirements` sidebar entry appears under the Methodology group.** Position within the group is set by the v0.5+ build conversation; the schema does not constrain it. The entry uses the standard `ListDetailPanel` widget per DEC-035.

11. **Master pane columns and default sort.** The Requirements panel shows columns Identifier / Name / Priority / Status / Updated (five columns), sorted by Identifier ascending. Right-click context menu offers New / Edit / Delete / Restore. (Priority column is shipped by default per section 3.6.2 but is open for v0.5 build conversation review.)

12. **Detail pane renders all fields and reference kinds in section-3.2 / 3.3.1 order.** Identifier (read-only), Name, Description, Acceptance Summary, Notes (collapsed under "Internal notes" header), Priority, Status, ReferencesSection — all present and bound to the correct fields. The ReferencesSection groups references by kind across all five outbound kinds.

13. **CRUD dialogs work end to end.** Create assigns identifier server-side, persists all fields including both enums at their default-or-selected values, surfaces server-side validation errors inline. Edit persists field changes including priority changes (no rules) and status transitions (rules enforced). Delete prompts for edge-text confirmation (user types the identifier) and soft-deletes on confirm. Restore reappears the record.

14. **All five outbound relationship kinds registered in vocabulary and constrained correctly.** `REFERENCE_RELATIONSHIPS` includes `requirement_scopes_to_domain`, `requirement_touches_entity`, `requirement_touches_field`, `requirement_realized_by_process`, `requirement_verified_by_test_spec`. `_kinds_for_pair` returns the expected set for each of the five `(requirement, target_type)` pairs. Attempting to POST `/references` with `(requirement, target_type)` and an unsupported kind returns 422. The Alembic migration extends the `refs.relationship_kind` CHECK constraint to include all five new values; direct DB insert with an unknown kind is rejected. References to `field` and `test_spec` targets require those sibling entity types to be live (build-planning sequencing concern).

15. **Sample CBM-redo iteration-build records authored through the UI, including reference round-tripping for all five kinds.** A consultant can author roughly 10 requirement records (e.g., "Capture mentor availability slots", "Email confirmation on mentor approval", "Match mentor expertise to client need", "Track mentor capacity vs commitments", "Record dues payment history per mentor", "Notify on dues overdue", "Capture contribution receipt details", "Aggregate fundraising campaign progress", "Restrict client PII visibility by role", "Export engagement summary per quarter"), set priorities across the four MoSCoW values, attach references to existing `domain`, `entity`, `field`, `process`, and `test_spec` records covering all five outbound kinds, transition statuses from `candidate` to `confirmed`, and the records and references persist correctly across application restart and across REST/MCP refetch. Bidirectional reference query (from each target side back to the requirement) returns the same edges.

### 3.8 Open Questions and Deferred Decisions

Categorized per the spec guide section 3.8 convention. Each entry is one paragraph with an explicit category tag.

#### 3.8.1 For v0.5 build to settle

**[v0.5 build] Master-pane Priority column.** Section 3.6.2 ships a Priority column by default but flags it for review. The argument for shipping it: MoSCoW-informed scanning is a natural use of master-pane real estate ("show me all the musts"); the column is a single enum value, not a join, so it has no rendering cost. The argument against: `entity.md` deferred its Domains column on the same review premise (PI-009), and the CBM-redo iteration-build conversation may rarely surface MoSCoW scans at master-pane granularity if the consultant works one process at a time. The v0.5 build conversation decides whether to ship the column as drafted or defer it to a follow-on PI, with consistency across the PI-004 cohort's column choices preferred over per-entity-type variation.

**[v0.5 build] Sidebar ordering within the Methodology group.** Section 3.6.1 proposes a working ordering of nine Methodology entries (Domains, Entities, Fields, Processes, Requirements, Manual Configs, Test Specs, CRM Candidates, Personas) but defers the authoritative ordering to the v0.5+ build conversation. The build conversation finalizes ordering across all five PI-004 entries and the PI-003 entry in one pass, with consistency cues (foundational-first; iteration-surfacing entries grouped) preferred over alphabetical.

**[v0.5 build] Create-dialog reference attachment flow.** Same two patterns as `entity.md` section 3.6.4: create-then-attach versus create-with-attach. Five reference kinds make the multi-select interface more complex for `requirement` than for `entity` (which had one), so the build conversation must weigh dialog-UX complexity against the per-requirement reference attachment burden. Consistency across all PI-004 entity types preferred over per-entity variation.

**[v0.5 build] Migration sequencing across the PI-004 cohort.** Three of this spec's five outbound reference kinds target sibling PI-004 entities (`field`, `test_spec`) not yet live. The build-planning conversation sequences the migrations so the target tables and entity-type registrations exist before `requirement`'s vocabulary registrations land; otherwise the Alembic constraint extension would reference unregistered entity types. Likely solution: a single coordinated PI-004 release migration that creates all five entity tables, then registers all cross-entity vocabulary, then opens the REST endpoints.

#### 3.8.2 For CBM redo to surface

**[CBM redo] Structured shape for `requirement_acceptance_summary`.** Plain text in v0.5+. The CBM-redo iteration-build conversations will reveal whether acceptance summaries naturally fall into Given / When / Then structure or remain free-form narrative. If structured shape would clarify the eventual `test_spec` decomposition, a future PI introduces explicit Given / When / Then columns or a JSON-shaped acceptance object. The decision waits on real-use signal.

**[CBM redo] Requirement-to-requirement dependencies.** Not introduced in v0.5+. The pattern is genuinely useful in abstract — "requirement A blocks requirement B" — but the iteration build conversation may surface these as conversational ordering hints that don't need formal vocabulary, or as a strict dependency graph that needs schema-level treatment. CBM redo will surface whether the schema gap is real. If yes, a future PI introduces `requirement_blocks_requirement` (or a similar verb) as a references-edge kind with cycle-detection validation at the access layer.

**[CBM redo] Requirement hierarchy.** Section 3.3.4 declines a self-referential parent-child pattern in v0.5+, on the premise that the evolved methodology produces flat lists of testable statements at consistent granularity. CBM redo will surface whether consultants reach for hierarchy in practice (e.g., a high-level capability that decomposes into specific sub-requirements). If yes, a future PI adds `requirement_parent_identifier` following the `topic.parent_topic` pattern.

**[CBM redo] Markdown for `requirement_description` and `requirement_acceptance_summary`.** Both fields are plain text in v0.5+. CBM redo will reveal whether descriptions need emphasis, bullet lists, or inline links. If so, a future migration introduces markdown rendering. Mirrors `domain` and `entity` posture.

**[CBM redo] Text-field length caps.** No storage-level length constraints in v0.5+; UI placeholder text provides soft guidance. If CBM redo produces pathological inputs, caps are added via migration. Same posture as `domain` and `entity`.

**[CBM redo] `requirement_notes` structure.** Flat plain text in v0.5+. If consultant notes accrete substantially across an engagement, a structured-journal pattern becomes a candidate. Same posture as `domain_notes` and `entity_notes`.

**[CBM redo] Server-side list filters.** Only `?include_deleted=true` is supported in v0.5+. Client-side filtering over the expected requirement count is sufficient initially. If list sizes grow to cause UI responsiveness issues, server-side filters (e.g., `?requirement_priority=must`, `?scopes_to_domain=DOM-NNN`) become future candidates. Likely to bite earlier for `requirement` than for `domain` or `entity` because requirement counts may run into the hundreds per engagement.

**[CBM redo] Priority-as-status reconciliation.** Section 3.2.3 keeps `requirement_priority` and `requirement_status` independent and articulates the `wont` vs `deferred` distinction. CBM redo will surface whether consultants and clients understand the distinction or whether the two fields' independence creates confusion. If the latter, a future revision could either collapse the fields into a richer single enum or strengthen UI cues to keep them visually distinct.

#### 3.8.3 For v0.6+

**[v0.6+] PI for requirement effort estimates / sizing.** A new planning item to be authored alongside this spec's close-out. Captures the methodology question of whether requirements should carry effort estimates (story points, t-shirt sizes, hour ranges) for release planning, and the schema implication of adding a `requirement_estimate` field (single value vs structured range). Deferred from v0.5+ because effort estimation is a separate methodological discipline that needs its own conversation; CBM redo may inform whether the methodology adopts a specific estimation approach.

**[v0.6+] PI for requirement-to-stakeholder attribution.** A new planning item to be authored alongside this spec's close-out. Captures the methodology question of tracking which stakeholders surfaced or championed each requirement, with the schema implication of either adding a `stakeholder` entity type (broader scope, addresses persona-style needs more comprehensively) or a `requirement_attributed_to_persona` references edge (narrower, leverages PI-003 if `persona` lands first). The choice depends on whether attribution is requirement-specific or whether broader engagement-history attribution is needed.

**[v0.6+] Anticipated source-side specs targeting `requirement` as inbound.** Future entity types (e.g., a `release` or `iteration` entity binding requirements to specific shipping bundles) will declare inbound edges to `requirement`. The vocabulary registrations belong to those source-side specs. Listed here for forward awareness.

**[v0.6+] DEC-038 lineage integration.** When `field` lands per PI-004, the derived-fields posture from DEC-038 (first-class methodology entity with explicit references for lineage tracing) integrates naturally with `requirement_touches_field`. A requirement that touches a derived field implicitly touches the field's source fields through DEC-038's lineage chain; whether the requirement's reference graph should auto-include those transitively-touched fields, or whether transitive coverage stays implicit, is a v0.6+ question that depends on `field`'s shipping shape.

### 3.9 Cross-References

#### 3.9.1 Decisions cited by this spec

The following five decisions are authored by running `crmbuilder-v2/scripts/apply_close_out.py` against the close-out payload for this conversation. Each is linked to the session via a `decided_in` reference recorded in the same payload. The DEC numbers are placeholders assigned at payload-generation time alongside the other PI-004 cohort spec decisions.

- **DEC-AAA — `requirement` identifier prefix and format.** Adopts `REQ` under the soft-3-letter posture established by `domain.md` and inherited by `entity.md` (see section 3.1).
- **DEC-BBB — `requirement` field inventory and validation under v0.5+ shipping scope.** Seven substantive fields plus inherited timestamps; separate `requirement_description` and `requirement_acceptance_summary` (acceptance summary plain text in v0.5+; structured Given / When / Then deferred); four-value MoSCoW priority enum (`must` / `should` / `could` / `wont`) with default `should`; optional `requirement_notes`; no storage-level length caps; case-insensitive global `requirement_name` uniqueness within the engagement (mirrors `entity_name`'s posture, not `process_name`'s per-domain posture) (see section 3.2).
- **DEC-CCC — `requirement` status lifecycle, propose-verify gate, rejection-via-soft-delete posture, and status independence from priority.** Three-status mirroring `domain` and `entity` with the same one-way propose-verify gate (DEC-047). `wont` priority preserved as a distinct concept from `deferred` status to keep MoSCoW vocabulary intact in client-facing renders. No `archived` status (see section 3.4).
- **DEC-DDD — `requirement` relationship posture: five outbound kinds via references entity.** All five mechanisms are references-entity edges; no direct FK columns. Vocabulary registrations: `requirement_scopes_to_domain`, `requirement_touches_entity`, `requirement_touches_field`, `requirement_realized_by_process`, `requirement_verified_by_test_spec`. Three target sibling PI-004 entities (`field`, `test_spec`) requiring coordinated migration sequencing in the v0.5+ build-planning conversation. Zero-affiliation permitted on all five kinds. Source-first naming convention per DEC-048 applied across all five (see section 3.3.1).
- **DEC-EEE — `requirement` API surface, UI defaults, deferred Priority-column posture, acceptance criteria for v0.5+.** Standard endpoint set with no deviations; decomposed reference handling (no inline-affiliation convenience endpoints); default `ListDetailPanel` UI under the existing Methodology sidebar group at a position to be finalized by the v0.5+ build conversation; Priority column shipped by default but flagged for build-conversation review against `entity.md`'s deferred-column precedent; create-dialog attachment flow left as a v0.5+ build decision; 15 testable acceptance criteria (see sections 3.5, 3.6, 3.7).

#### 3.9.2 External references

- `crmbuilder/CLAUDE.md` — universal session-startup entry; documents the `REFERENCE_RELATIONSHIPS` / `_kinds_for_pair` / Alembic-migration triad that section 3.3.1's mechanical additions follow; documents the `{data, meta, errors}` envelope referenced by section 3.5.6.
- `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md` — schema spec template this document follows.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/domain.md` — convention-establishing predecessor spec (parent-prefix field naming, source-first relationship-kind naming, soft-3-letter prefix posture, status-lifecycle shape, rejection-via-soft-delete posture, no-archived posture).
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/entity.md` — worked-example predecessor spec; source of the case-insensitive global name uniqueness posture adopted in section 3.2.1, the entity-status-independent-of-affiliation-status posture adopted in section 3.4.4, the references-not-FK posture for many-to-many edges adopted in section 3.3.1, and the deferred-column posture cited in section 3.6.2 as precedent for the Priority-column open question.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/process.md` — sibling predecessor spec; source of the contrast for `requirement_name`'s global (not per-domain) uniqueness posture.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/crm_candidate.md` — sibling predecessor spec; informs the cross-spec consistency posture.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/field.md` (forthcoming, PI-004) — sibling spec; will register `field` as a live entity type, the target of `requirement_touches_field`.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/test_spec.md` (forthcoming, PI-004) — sibling spec; will register `test_spec` as a live entity type, the target of `requirement_verified_by_test_spec`. Its section 3.3.2 will note this spec's `requirement_verified_by_test_spec` as anticipated inbound.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/manual_config.md` (forthcoming, PI-004) — sibling spec; informs cohort sequencing.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/persona.md` (forthcoming, PI-003) — sibling spec; informs the v0.6+ requirement-to-stakeholder attribution open question.

#### 3.9.3 Related prior decisions informing this spec

- **DEC-006** — Universal references table as the cross-entity-type edge store. Direct architectural foundation for all five outbound reference mechanisms in section 3.3.1.
- **DEC-039** — Minimum entity inventory and multi-tenancy posture. Informs the thin-shape framing in section 1 (PI-004 entity types ship at the thinnest faithful shape).
- **DEC-043** — SES-010 identifier-asymmetry resolution. Mandates the `GET /requirements/next-identifier` helper endpoint cited in section 3.5.1.
- **DEC-046** — Parent-prefix field-naming convention for methodology entities. Establishes the field-naming pattern this spec inherits and applies (see section 3.2).
- **DEC-047** — `domain` status lifecycle, propose-verify gate, and rejection-via-soft-delete posture. Establishes the lifecycle pattern this spec adopts unchanged (see section 3.4).
- **DEC-048** — `domain` relationship posture and `{source}_{verb}_{target}` relationship-kind naming convention. Establishes the relationship-kind naming pattern this spec applies in registering all five outbound kinds (see section 3.3.3).

#### 3.9.4 Planning items cited

- **PI-003** — `persona` entity type. Sibling cohort member; informs the v0.6+ requirement-to-stakeholder attribution open question (section 3.8.3).
- **PI-004** — Additional methodology entity types for v0.5+ (`field`, `requirement`, `manual_config`, `test_spec`). This spec satisfies the `requirement` portion. The `field` and `test_spec` portions are direct dependencies for three of this spec's five outbound vocabulary registrations.
- **PI-005** — Process schema growth beyond Phase 1 thin shape. The `requirement_realized_by_process` edge anticipates the richer `process` shape that PI-005 delivers; the edge works with the v0.4 thin `process` but takes on more semantic weight as PI-005 lands.

#### 3.9.5 Predecessor and successor context

- **Predecessor cohort (v0.4 workstream):** `domain.md`, `entity.md`, `process.md`, `crm_candidate.md` — established the conventions this spec inherits.
- **Sibling cohort (PI-004 + PI-003, v0.5+):** `field.md` (most urgent — three of this spec's outbound edges or their target-side complements depend on it), `persona.md`, `manual_config.md`, `test_spec.md`. The five PI-004 cohort entries are produced as deliverables resolving PI-004; sequencing across the cohort is decided in the v0.5+ build-planning conversation.

---

*End of document.*

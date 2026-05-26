# Methodology Entity Schema Spec — `persona`

**Last Updated:** 05-25-26 16:30
**Status:** Draft v1.0 — produced under PI-003 resolution
**Position in workstream:** First of three independent v0.5+ methodology entity schema specs (`persona` — PI-003; `field` — PI-004; `requirement` / `manual_config` / `test_spec` — also PI-004). Authored as part of the v0.5+ methodology entity workstream successor to the original methodology-entity-schema-design workstream (`domain` / `entity` / `process` / `crm_candidate`).
**Predecessor conventions inherited from:** `domain.md` (DEC-046 parent-prefix field naming, DEC-048 `{source}_{verb}_{target}` relationship-kind naming, DEC-047 propose-verify lifecycle, rejection-via-soft-delete posture) and `entity.md` (references-over-FK posture for many-to-many affiliation per DEC-053, thin-shape minimum-viable scoping discipline).

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-25-26 16:30 | Doug Bower / Claude | Initial draft. Produced under PI-003 resolution. Defines `persona` as the v2 methodology entity type that hosts human-role/actor records surfaced in Phase 2 or 3 of the evolved methodology (Phase 1 explicitly does not elicit personas; persona context comes from pre-engagement reading of operational role definitions per the Phase 1 interview guide v0.2). Inherits conventions established by `domain.md` and `entity.md`: parent-prefix field naming, `{source}_{verb}_{target}` relationship-kind naming, three-status propose-verify lifecycle, rejection-via-soft-delete, references-entity edges for many-to-many affiliation. Establishes `persona_scopes_to_domain` (many-to-many) and `persona_realized_as_entity` (optional, persona-backed-by-entity-record) as new vocabulary entries. |

---

## Change Log

**Version 1.0 (05-25-26 16:30):** Initial creation. Defines five substantive fields (`persona_identifier`, `persona_name`, `persona_role_summary`, `persona_responsibilities`, `persona_notes`, `persona_status`) plus inherited timestamps; three-status lifecycle mirroring `domain` and `entity` (`candidate` / `confirmed` / `deferred`) with one-way propose-verify gate; persona status independent of any affiliated-domain statuses; many-to-many domain affiliation via the references entity using the new `persona_scopes_to_domain` relationship kind; optional persona-to-entity realization via the new `persona_realized_as_entity` references kind; no FK columns on the persona table; standard endpoint set with decomposed reference handling. Defers persona authority / access-boundary fields, persona-to-user membership cardinality, and process-performed-by-persona inbound edges to v0.6+ planning items. Five decisions captured as DEC-XXX placeholders to be renumbered at close-out, and three new planning items proposed (persona authority/access-boundary, persona membership cardinality, persona-to-entity realization mechanism reconsideration). Acceptance criteria captured as 14 testable statements.

---

## 1. Purpose and Position

This document specifies the `persona` entity type for v2's storage layer. It satisfies PI-003 by providing the schema spec the v0.5+ build will implement.

PI-003's deferral history matters for framing. DEC-039 deferred `persona` from v0.4's minimum-viable inventory because the evolved methodology's Phase 1 interview guide v0.2 explicitly excludes persona elicitation in Phase 1: persona context comes from pre-engagement reading of operational role definitions, used as consultant background rather than captured as records. Phase 2 (Persona / Process Inventory) or Phase 3 (Process Definition) of the evolved methodology may surface persona records — actors performing process steps, role boundaries for access control, organizational roles distinct from individual users. v0.5+ is when those records need a place to live.

The workstream of origin (`domain` / `entity` / `process` / `crm_candidate`) closed at v0.4. This spec is the first of three independent specs authored under the v0.5+ methodology entity workstream successor; the other two are `field` (PI-004) and the trio of `requirement` / `manual_config` / `test_spec` (also PI-004). The three specs are independent in that they have no inter-dependencies — each can be designed and built without waiting on the others — but they share the conventions established in the original workstream's `domain.md` and `entity.md`.

`persona`'s primary scope in v0.5+ is intentionally thin, mirroring the entity.md thin-shape posture. The v0.5+ schema captures what Phase 2 and early Phase 3 work surface — a role name in the client's language, a brief plain-text role summary, optional responsibilities, an optional internal-notes scratchpad, a lifecycle status, and the relational shape that links each persona to the domains it scopes to and (optionally) to the entity record that backs it. The schema grows in v0.6+ as later methodology work and CBM-redo signal reveal what `persona` needs to carry (authority/access-boundary fields, membership cardinality, etc.) — deferred under explicit planning items called out in section 3.8.

---

## 2. Summary

A `persona` record in v2 represents one human role or actor that performs work in the client's organization — Mentor Coordinator, Program Manager, Volunteer Mentor, Client, Donor, Board Member, etc. A persona may map 1:1 with one or more system users (an individual Mentor Coordinator is a real person with a CRM login), may serve as a role boundary for access control (the Mentor Coordinator role can edit Mentor records; the Volunteer Mentor role can only edit their own profile), and is typically the actor in a process step (Mentor Coordinator approves Mentor Applications). Each `persona` record holds a client-language role name, a brief plain-text summary of the role, optional plain-text responsibilities or behaviors, an optional consultant scratchpad for rationale and pattern-library reasoning, and a lifecycle status tracking whether the persona is a CRM-Builder-proposed candidate, a client-confirmed in-scope role, or an acknowledged-but-deferred role.

Domain affiliation — which engagement domains the persona is relevant to — is captured separately as `persona_scopes_to_domain` references in v2's universal references store, supporting the reality that a persona (like CBM's Program Manager) may legitimately span multiple domains. An optional `persona_realized_as_entity` references edge marks the cases where the persona is backed by a record in some CRM-modeled entity (e.g., the Volunteer Mentor persona is realized as records in the Mentor entity) — this captures the design-time intent that "this role lives in this entity's table" without forcing it: a persona may legitimately exist as a role boundary without any entity-table realization (e.g., a CRM Administrator persona that is purely a permissions-level role).

The schema in v0.5+ is the thinnest shape that can faithfully host Phase 2 and early Phase 3 persona-surfacing work. It deliberately omits authority/access-boundary fields, persona-to-user membership cardinality (a Volunteer Mentor persona may correspond to many user accounts; a Mentor Coordinator user may play multiple personas), and any process-performed-by-persona edges — all belong to subsequent methodology phases or to subsequent v2 releases. The minimum-viable shape grows additively in v0.6+ as the evolved methodology's iteration work reveals what `persona` needs to carry.

---

## 3. Schema Specification

### 3.1 Identity

| Field | Value |
|-------|-------|
| Entity type name (storage) | `persona` |
| Display name (singular) | Persona |
| Display name (plural) | Personas |
| Identifier prefix | `PER` |
| Identifier format | `PER-NNN`, zero-padded to 3 digits (e.g., `PER-001`, `PER-042`) |
| Identifier auto-assignment | Server-side on POST omission; helper at `GET /personas/next-identifier` |

`PER` is three letters and adheres to the soft-3-letter prefix posture established in `domain.md` section 3.1. The prefix reads unambiguously as "persona", has no collision with the existing v2 prefix set (DEC, SES, RSK, PI, TOP, REF, CHR, STA, DOM, ENT, PROC, CRM, WS, CONV, RB, WT, COP, DEP, CM), and matches the existing v2 methodology- and governance-entity norm. No deviation from defaults; the identifier-asymmetry helper endpoint per DEC-043 ships alongside the standard endpoint set, and per PI-002 the identifier is optional on POST.

### 3.2 Fields

Field naming follows the parent-prefix convention established by `domain.md` (DEC-046): all non-identifier, non-timestamp fields are prefixed with the parent entity name (`persona_`). All fields including identifier and timestamps adopt the prefix for full convention consistency.

#### 3.2.1 Identity fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `persona_identifier` | TEXT | yes | server-assigned | `^PER-\d{3}$`, unique | The methodology-entity identifier in `PER-NNN` format. Server-assigned when omitted from POST body per PI-002. |
| `persona_name` | TEXT | yes | — | non-empty trimmed; case-insensitive unique within the engagement | Persona role name in the client's language (e.g., "Mentor Coordinator", "Program Manager", "Volunteer Mentor", "Client", "Donor"). |

#### 3.2.2 Content fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `persona_role_summary` | TEXT | yes | — | non-empty trimmed | Brief plain-text description of what this role does in the organization (e.g., "Oversees the mentor program day-to-day; recruits and onboards new mentors; pairs mentors with clients; tracks engagement progress"). One to three sentences typical. Plain text in v0.5+; markdown support deferred to CBM-redo signal. |
| `persona_responsibilities` | TEXT | no | — | — | Optional plain-text bullet-form responsibilities or characteristic behaviors. Used when the role summary needs to be decomposed into discrete responsibilities for clarity (e.g., "- Approves Mentor Applications\n- Schedules onboarding sessions\n- Sets monthly engagement targets"). Plain text in v0.5+; structured-list pattern deferred to CBM-redo signal. |
| `persona_notes` | TEXT | no | — | — | Internal consultant scratchpad. Not part of any client-facing render. Used to capture pattern-library rationale, push-back trails, between-session reasoning about why the persona exists in the form it does, and any history of role-name negotiations with the client. Plain text in v0.5+. |

**No `persona_purpose` field.** The Phase 2 / Phase 3 surfacing pattern for personas does not produce a separate "why does this role exist" artifact distinct from the role summary itself; the role summary already explains what the role does and why it's distinct from adjacent roles. Adding `persona_purpose` would either duplicate `persona_role_summary` or invent a methodology concept that the evolved methodology does not produce.

#### 3.2.3 Classification fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `persona_status` | TEXT | yes | `candidate` | enum: `candidate` \| `confirmed` \| `deferred`; valid transitions per section 3.4 | Lifecycle status. See section 3.4 for the transition map. |

No `persona_authority` or access-boundary classification in v0.5+. Access-boundary semantics (read-only vs read-write per entity; record-scoped vs collection-scoped access; admin vs operator distinction) belong to a later release once the methodology surfaces what level of granularity is required and how it integrates with CRM-engine-specific roles models. Deferred under a new planning item (PI-XXX-A, "persona authority / access-boundary fields") authored at this conversation's close.

#### 3.2.4 Relationship fields

None in v0.5+. `persona` has no outgoing FK columns on its table. Domain affiliation and entity realization are captured via the references entity (see section 3.3); future inter-persona and persona-to-user relationships are deferred to v0.6+ and likewise will use references rather than FK columns when introduced.

#### 3.2.5 Timestamp fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `persona_created_at` | DATETIME | yes | server-set on insert | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `persona_updated_at` | DATETIME | yes | server-set on insert and on each update | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `persona_deleted_at` | DATETIME | no | null until soft-delete | ISO 8601 UTC when set | Inherited base behavior. Set on DELETE; cleared on POST `/restore`. |

**No storage-level length caps.** Text fields are unconstrained at the storage layer in v0.5+. The UI provides soft guidance via placeholder text ("Brief description of the role"). Pathological-input handling deferred to CBM-redo signal; length caps are easy to add via migration if needed. This mirrors the `domain` and `entity` posture.

### 3.3 Relationships

#### 3.3.1 Outgoing relationships

`persona` declares two outgoing relationship kinds in v0.5+: `persona_scopes_to_domain` and `persona_realized_as_entity`.

| relationship_kind | source | target | mechanism | cardinality | semantics |
|-------------------|--------|--------|-----------|-------------|-----------|
| `persona_scopes_to_domain` | `persona` | `domain` | references-entity edge | many-to-many | A persona is scoped to one or more domains. A persona may have zero, one, or many such references; a domain may have zero or many inbound references of this kind. |
| `persona_realized_as_entity` | `persona` | `entity` | references-entity edge | many-to-one in practice; technically many-to-many | A persona is realized as records in a CRM-modeled entity (e.g., the Volunteer Mentor persona is realized as records in the Mentor entity). Optional: a persona may exist as a pure role boundary without any entity-table realization. Most personas realize as at most one entity, but the references mechanism permits more than one (e.g., a Coordinator persona realized across both a Staff entity and a Volunteer entity if the methodology surfaces that pattern). |

The mechanism for both is the references entity at v2's `refs` table, governed by the existing `RELATIONSHIP_RULES` infrastructure (DEC-006). The choice over persona-table FK columns is per DEC-053 precedent — references discipline keeps the persona-table schema small, supports the same edge-creation/lookup semantics already used for governance- and methodology-entity references, and makes inverse queries trivial through the existing reverse-edge query ("what personas scope to this domain?", "what personas are realized as this entity?"). A direct single-value FK for either was a non-starter: `persona_scopes_to_domain` because personas legitimately span domains; `persona_realized_as_entity` because while most personas realize as at most one entity, the few that need more than one would break a single-value FK without warning.

**Mechanical additions per CLAUDE.md line 48 (the vocab.py / `_kinds_for_pair` / Alembic-migration triad):**

1. `persona_scopes_to_domain` and `persona_realized_as_entity` added to `REFERENCE_RELATIONSHIPS` in `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`.
2. `_kinds_for_pair` extended so `(persona, domain)` returns `{persona_scopes_to_domain}` and `(persona, entity)` returns `{persona_realized_as_entity}`.
3. Alembic migration extending the `refs.relationship_kind` CHECK constraint to include the two new values.

**Cardinality and validation:**

- `persona_scopes_to_domain` is many-to-many with no upper bound on either side. Zero-affiliation is permitted (Phase 2 may surface a persona name before its domain scoping is settled).
- `persona_realized_as_entity` is conceptually optional and most often single-target per persona; the references mechanism permits multi-target without validation overhead. Zero is the default state (the persona has no entity realization recorded yet, or it is a pure role-boundary persona).
- Sources must be live `persona` records; targets must be live `domain` or `entity` records respectively (existing access-layer rules for the references table).
- Duplicate `(source_id, target_id, relationship_kind)` tuples are rejected by the references-table uniqueness constraint.

**Lifecycle semantics:**

- Soft-deleting a persona does not cascade-delete its `persona_scopes_to_domain` or `persona_realized_as_entity` references; the references persist (existing v2 behavior) and remain visible via the show-deleted UI toggle on either side.
- Same for soft-deleting a domain or entity on the target side.
- Restoring either endpoint restores the relationship rows in place.

**The verbs:** "scopes to" means the persona is relevant to / appears in / performs work in this domain (same semantics as `entity_scopes_to_domain` for consistency). "Realized as" means a persona of this role corresponds in practice to records in this CRM-modeled entity — capturing design-time intent rather than enforcing a hard mapping at the storage layer.

#### 3.3.2 Inbound relationships (anticipated; declared by future source-side specs)

`persona` is the anticipated target of references from `process` (process-performed-by-persona pattern) and potentially from a future v0.6+ user-persona membership entity type. None of these are declared in v0.5+; their formal vocabulary registration belongs to the source-side specs that introduce them. This subsection exists for forward awareness; the `persona` panel's `ReferencesSection` widget will render inbound references once they exist.

Anticipated inbound kinds (informational from this spec's perspective; declared in their source-side specs):

| relationship_kind | source | target | semantics |
|-------------------|--------|--------|-----------|
| `process_performed_by_persona` (working name; declared by `process.md` growth spec under PI-005) | `process` | `persona` | A process step is performed by an actor in this persona's role. Phase 3 work; process schema growth attaches this once full process definition lands. |
| `user_plays_persona` (working name; v0.6+) | `user` (or equivalent) | `persona` | A system user account is mapped to a persona. Membership cardinality (one user can play many personas; one persona can be played by many users) deferred under PI-XXX-B. |

The `process.md` growth spec (PI-005) will register the source-side `process_performed_by_persona` vocabulary entry when it lands; the user-persona membership pattern is a v0.6+ planning item. No cross-spec consistency conflict is anticipated because the source-side specs name their own vocab; the v0.5+-build-planning conversation's cross-spec consistency check is the formal gate.

#### 3.3.3 Cross-spec relationship-kind naming convention — adopted, not established

This spec adopts the `{source}_{verb}_{target}` relationship-kind naming convention established by `domain.md` section 3.3.3 (DEC-048) and applied by `entity.md` section 3.3.3. Both vocabulary entries this spec registers (`persona_scopes_to_domain` and `persona_realized_as_entity`) conform to the pattern: source entity first, verb phrase, target entity. The convention is not re-decided here; it carries forward from the predecessor specs.

#### 3.3.4 Hierarchy

`persona` does not use the self-referential parent-child hierarchy pattern in v0.5+. Persona hierarchy (e.g., "Senior Mentor Coordinator is-a Mentor Coordinator") is not surfaced by the evolved methodology's Phase 2 or early Phase 3 work. If real-engagement experience surfaces a need for persona hierarchy or specialization, the mechanism design (self-referential FK vs `persona_specializes_persona` references edge) is a v0.6+ question — currently not tracked under a dedicated PI because there is no methodology pressure for it yet.

### 3.4 Lifecycle

#### 3.4.1 Status values

| Status value | Description | Valid predecessors | Valid successors |
|--------------|-------------|--------------------|------------------|
| `candidate` | CRM Builder has proposed; awaiting client verification. **Default starter status.** | (none — starter) | `confirmed`, `deferred` |
| `confirmed` | Client has verified this is a persona in scope for the engagement. | `candidate`, `deferred` | `deferred` |
| `deferred` | Client has acknowledged this is a real persona but it is out of current engagement scope. | `candidate`, `confirmed` | `confirmed` |

The structure mirrors `domain.md` section 3.4.1 and `entity.md` section 3.4.1 exactly; the semantics map cleanly: personas, like domains and entities, are surfaced by the consultant and verified by the client.

#### 3.4.2 Transition semantics

The status lifecycle implements the same **one-way propose-verify gate** established for `domain` (DEC-047) and adopted by `entity` (DEC-052): once a persona has moved out of `candidate` (in either direction, to `confirmed` or to `deferred`), it does not regress to `candidate`. The rationale: the propose-verify moment is a meaningful client-engagement event; if the consultant later wants to fundamentally rethink a verified persona, the right action is to edit the record's content, not to regress its status. Status reflects engagement-scope position, not deliberation state.

Movement between `confirmed` and `deferred` in either direction is permitted to support mid-engagement scope changes (e.g., a persona initially confirmed but later deprioritized; a previously-deferred persona pulled back into scope at a later iteration).

#### 3.4.3 Status independence from affiliation status and from realization status

A persona's `persona_status` is its own field on its own table, set by the consultant based on client verification of the persona itself. **It is not derived from the statuses of the domains it scopes to, nor from the status of the entity it realizes as.** This independence matters because a persona may legitimately span domains at different lifecycle positions and realize as an entity at a different lifecycle position: a Program Manager persona in CBM might scope to MN (`confirmed`), MR (`confirmed`), and FU (`deferred`) simultaneously, and the persona's own status is `confirmed` because the client has agreed the Program Manager role exists in their world — that judgment doesn't depend on which specific domains the persona ends up in or whether its backing entity is itself fully confirmed.

The implication for the UI and access layer: edit affordances on `persona_status` do not consult the affiliated domains' statuses or the realization entity's status, and changing those upstream statuses does not cascade to inbound `persona_scopes_to_domain` or `persona_realized_as_entity` references' source-side records. The lifecycles are managed independently.

#### 3.4.4 Rejection via soft-delete

When the client rejects a CRM-Builder-proposed persona candidate ("no, that's not actually a distinct role for us — that's just what the Program Manager does"), the rejection is handled by soft-delete rather than a `rejected` status value. `DELETE /personas/{persona_identifier}` sets `persona_deleted_at`; the record persists for audit and history, surfaces under the `?include_deleted=true` toggle, and is restorable via POST `/restore`. This piggybacks v2's existing soft-delete infrastructure rather than introducing a status value that duplicates the mechanism. The cross-spec principle established in `domain.md` section 3.4.3 carries forward unchanged: **status values track engagement-scope lifecycle; soft-delete tracks existence-in-the-record.**

#### 3.4.5 No `archived` status

`archived` is not introduced in v0.5+. Soft-delete combined with the "show deleted" toggle already covers the "retained for record, not in active scope" use case. Mirrors `domain.md` section 3.4.4 and `entity.md` section 3.4.5.

#### 3.4.6 Soft-delete semantics

Soft-delete inherits v2's standard behavior:

- DELETE sets `persona_deleted_at` to the current ISO 8601 UTC timestamp.
- Soft-deleted records do not appear in `GET /personas` by default.
- `GET /personas?include_deleted=true` returns soft-deleted records alongside live ones.
- POST `/personas/{persona_identifier}/restore` clears `persona_deleted_at` and reappears the record in the default list.
- Restore on a record that is not soft-deleted returns HTTP 422.

Outbound `persona_scopes_to_domain` and `persona_realized_as_entity` references on a soft-deleted persona are NOT cascade-deleted. They persist in the references table; show-deleted toggles on either side surface them. This matches v2's existing references-table soft-delete behavior.

### 3.5 API Surface

#### 3.5.1 Endpoints

| Method | Path | Body | Notes |
|--------|------|------|-------|
| GET | `/personas` | — | List endpoint. Returns active records by default. Supports `?include_deleted=true` to include soft-deleted records. |
| GET | `/personas/{persona_identifier}` | — | Single fetch by identifier. Returns 404 if not found. |
| POST | `/personas` | full record; `persona_identifier` optional (server-assigned when omitted per PI-002) | Create. Returns 201 with the assigned identifier in the response body. Server-side validation per section 3.2 applied. |
| PUT | `/personas/{persona_identifier}` | full record | Full replace. `persona_identifier` in body must match the path; mismatch returns 422. |
| PATCH | `/personas/{persona_identifier}` | partial record | Partial update. Status-transition validation applied (see 3.5.3). |
| DELETE | `/personas/{persona_identifier}` | — | Soft-delete; sets `persona_deleted_at`. Idempotent (DELETE on an already-soft-deleted record returns 200 with no state change). |
| POST | `/personas/{persona_identifier}/restore` | — | Clears `persona_deleted_at`. Returns 422 if the record is not soft-deleted. |
| GET | `/personas/next-identifier` | — | Returns `{"next": "PER-NNN"}` for the next available identifier. Per SES-010 resolution (DEC-043). |

**No deviations from the cross-spec default endpoint set.** No bulk operations, no webhooks, no event streams, no inline-affiliation or inline-realization convenience endpoints.

All endpoints return responses through the v2 `{data, meta, errors}` envelope per CLAUDE.md's envelope-discipline rule; inline `jq` / curl pipelines reading from these endpoints must unwrap `.data` first.

#### 3.5.2 Identifier auto-assignment

`persona_identifier` is server-assigned on POST when omitted from the request body, per PI-002 which lifted the requirement on the five remaining "old eight" entity types and which applies uniformly to every prefixed-identifier entity type in v0.5+ scope. The assignment logic queries the current maximum `persona_identifier` (including soft-deleted records, to avoid identifier reuse) and increments the numeric suffix via the SAVEPOINT-retry helper that is safe under concurrent writes. The `GET /personas/next-identifier` helper exposes the same logic for clients that want to know the assigned identifier before POSTing.

Supplying an explicit identifier on POST is supported: the value must match `^PER-\d{3}$` and not collide with an existing row (collision → 409, malformed → 422).

#### 3.5.3 Status-transition validation

Status transitions are validated server-side at the access layer. PATCH or PUT requests that specify a `persona_status` value that is not a valid successor of the current value (per section 3.4.1) return HTTP 422 with a body of the form:

```
{
  "error": "invalid_status_transition",
  "from": "<current status>",
  "to": "<requested status>"
}
```

The default-`candidate` rule applies on POST: if `persona_status` is omitted, the server assigns `candidate`. POST with `persona_status` explicitly set to a non-starter value is permitted (e.g., bulk-importing already-confirmed personas from prior engagement records or from pre-engagement operational-role-definition reading).

#### 3.5.4 Decomposed reference handling

Domain affiliations and entity realizations are NOT inlined into the persona create or update bodies. To attach a `persona_scopes_to_domain` reference, the client makes a separate `POST /references` with:

```
{
  "source_type": "persona",
  "source_id": "PER-NNN",
  "target_type": "domain",
  "target_id": "DOM-NNN",
  "relationship_kind": "persona_scopes_to_domain"
}
```

To attach a `persona_realized_as_entity` reference, the same pattern with `target_type: "entity"`, `target_id: "ENT-NNN"`, and `relationship_kind: "persona_realized_as_entity"`.

This decomposed posture keeps the persona API consistent with v2's references-first discipline (DEC-006) and matches how the v0.3 desktop UI and the v0.4 entity panel handle references for governance and methodology entities. The New dialog and detail-pane "Add reference" affordance hide the two- or three-call sequence behind a single user gesture, but the API stays decomposed; no `/personas/{id}/scopes` or `/personas/{id}/realizes` shortcut endpoint is introduced.

#### 3.5.5 Other endpoint specifics

- All endpoints return JSON wrapped in the `{data, meta, errors}` envelope.
- 4xx error responses use the existing v2 error envelope shape (or FastAPI's standard error shape for handler-level exceptions per the `crmbuilder-v2/src/crmbuilder_v2/api/errors.py` note in CLAUDE.md).
- No additional list query parameters beyond `?include_deleted=true` in v0.5+. Client-side filtering over the expected persona count (a typical engagement has fewer than two dozen personas) is sufficient. Server-side filtering deferred to CBM-redo signal.

### 3.6 UI Considerations

This spec adopts the spec guide's default `ListDetailPanel` layout with no architectural deviations. Specifics for `persona` follow.

#### 3.6.1 Sidebar

The "Methodology" sidebar group introduced by `domain.md` section 3.6.1 hosts the new `persona` entry. Position within the group is appended after the v0.4 entries, ordered by spec-introduction sequence:

1. Domains (v0.4)
2. Entities (v0.4)
3. Processes (v0.4)
4. CRM Candidates (v0.4)
5. Engagements (v0.4.x — `engagement.md`)
6. **Personas** (this spec, v0.5+)
7. Fields (v0.5+, `field.md` under PI-004)
8. Requirements / Manual Configs / Test Specs (v0.5+, separate spec under PI-004)

The `persona` sidebar entry ships independently of `field` and the requirement/manual_config/test_spec trio because the three v0.5+ specs are independent and may build/ship on different cadences.

#### 3.6.2 Master pane

`ListDetailPanel`-backed list with these columns:

| Stored field | Display header | Width | Notes |
|--------------|----------------|-------|-------|
| `persona_identifier` | Identifier | narrow | Default sort key, ascending |
| `persona_name` | Name | wide | Client-language role name |
| `persona_status` | Status | narrow | Enum value rendered as-is |
| `persona_updated_at` | Updated | narrow | Localized date/time |

Right-click context menu offers New / Edit / Delete / Restore, consistent with v0.3 governance-entity panels and v0.4 methodology-entity panels per DEC-035 and DEC-036.

**No Domains or Realized-as-entity column in v0.5+.** Same logic as `entity.md` section 3.6.2: without `domain_short_code` (PI-007), the columns would render `DOM-001, DOM-002` and `ENT-005` — identifiers that don't tell a consultant anything at a glance. Detail-pane `ReferencesSection` widget exposes affiliations and realization one click away. Deferred to a future master-pane enrichment paired with PI-007 short codes; the persona-side master-pane column work piggybacks on whatever pattern lands for the entity-side via PI-009.

#### 3.6.3 Detail pane

Vertical layout, fields in section-3.2 order:

1. `persona_identifier` — read-only label
2. `persona_name` — single-line text editor
3. `persona_role_summary` — multi-line text editor with placeholder "Brief description of what this role does in the organization"
4. `persona_responsibilities` — multi-line text editor under a collapsible "Responsibilities" section header, expanded by default (the field is optional, but when populated it carries client-visible content distinct from the consultant scratchpad)
5. `persona_notes` — multi-line text editor under a collapsible "Internal notes" section header, collapsed by default
6. `persona_status` — combo box with the three enum values
7. `ReferencesSection` widget — renders outgoing `persona_scopes_to_domain` references (persona-to-domain affiliations), outgoing `persona_realized_as_entity` references (persona-to-entity realization), and any inbound references. In v0.5+ there are no inbound kinds declared by source-side specs yet (PI-005 process growth will register `process_performed_by_persona` when it lands); the widget is still always present, and the outgoing affiliations and realization are the primary user-facing content. The widget exposes the existing "Add reference" affordance for attaching new affiliations and realizations after the persona record exists.

The collapsed-by-default treatment of `persona_notes` matches `domain_notes` and `entity_notes` — internal consultant scratchpad, not part of any client-facing render. The expanded-by-default treatment of `persona_responsibilities` reflects that it is client-facing content (a render artifact) when populated, distinct from the always-internal notes field.

#### 3.6.4 Create dialog

Modal `EntityCrudDialog` subclass with field order matching the detail pane. Specifics:

- `persona_identifier` not shown in create mode (server-assigned).
- `persona_status` defaults to `candidate`; user may select a different starter value if importing established persona records or pre-engagement-derived personas.
- Required-field validation client-side before submit.
- Server-side validation errors (uniqueness, format, transition) surface inline.

**Domain-affiliation and entity-realization flow — open question for v0.5+ build.** Same two reasonable patterns as `entity.md` section 3.6.4 surfaced for domain affiliation, now multiplied across two reference kinds:

- **Create-then-attach.** The New dialog creates the persona record only; the user adds domain affiliations and (optionally) entity realization from the detail pane via the existing "Add reference" affordance after the persona exists. Two or more gestures.
- **Create-with-attach.** The New dialog includes a multi-select for domains and a single-select (with "none" as default) for entity realization; on submit, the UI runs POST `/personas` followed by N × POST `/references` in sequence. One gesture per persona, regardless of affiliation/realization count.

Both satisfy the acceptance criterion that the user can attach domain affiliations and entity realization through the UI without leaving it. The v0.5+-build-planning conversation decides which pattern is implemented. (The reasonable expectation is that whatever pattern the v0.4 build adopted for `entity` is reused here for consistency, but that is a build-time call.)

#### 3.6.5 Edit dialog

Same shape as create. `persona_identifier` displayed as read-only label. Status transitions enforced per section 3.4.1; invalid selections in the status combo are either prevented (recommended UX) or rejected by the server with the 422 surfacing inline (acceptable fallback).

#### 3.6.6 Delete dialog

`EntityCrudDeleteDialog` with edge-text confirmation. The user types the `persona_identifier` value (e.g., `PER-002`) to enable the Delete button, matching v0.3/v0.4 patterns. Confirmation soft-deletes the record. Outbound `persona_scopes_to_domain` and `persona_realized_as_entity` references on the soft-deleted persona persist per section 3.4.6.

### 3.7 Acceptance Criteria

The following 14 statements define what "this entity type is correctly implemented in v0.5+" looks like. Each is concrete and testable; v0.5+ build planning translates these into specific test cases.

1. **Schema migration applies cleanly.** Alembic migration creates the `personas` table with all nine columns (`persona_identifier`, `persona_name`, `persona_status`, `persona_role_summary`, `persona_responsibilities`, `persona_notes`, `persona_created_at`, `persona_updated_at`, `persona_deleted_at`), correct types and constraints, and runs both forward and backward without error.

2. **`persona_identifier` format constraint enforced.** Insertions with `persona_identifier` not matching `^PER-\d{3}$` raise a validation error at the access layer. POST without `persona_identifier` succeeds and the server-assigned value matches the format.

3. **`persona_name` uniqueness enforced case-insensitively.** Inserting a second row whose `persona_name` matches an existing row by lowercase comparison raises a uniqueness violation.

4. **`persona_status` enum and transition validation.** Insertions with `persona_status` outside `{candidate, confirmed, deferred}` are rejected. PATCH/PUT requesting an invalid transition (e.g., `confirmed` → `candidate`) returns HTTP 422 with `{"error": "invalid_status_transition", "from": ..., "to": ...}`.

5. **Access-layer methods exist with expected signatures.** `client.list_personas()`, `client.get_persona(identifier)`, `client.create_persona(...)`, `client.update_persona(identifier, ...)`, `client.patch_persona(identifier, ...)`, `client.delete_persona(identifier)`, `client.restore_persona(identifier)`, `client.next_persona_identifier()` exist and pass unit tests covering happy path and at least one error case each.

6. **REST endpoints return expected responses for representative cases.** All eight endpoints from section 3.5 return correct HTTP status and JSON bodies wrapped in the `{data, meta, errors}` envelope for happy-path and validation-failure cases; 4xx errors use the v2 error envelope per CLAUDE.md.

7. **Identifier auto-assignment helper returns next ID without race conditions.** `GET /personas/next-identifier` returns `{"next": "PER-NNN"}` for the next available number. POST with `persona_identifier` omitted assigns the same value via the SAVEPOINT-retry helper. Two concurrent POSTs do not assign the same identifier (verified by a concurrent-insert test).

8. **Soft-delete and restore round-trip correctly.** DELETE sets `persona_deleted_at`; the record disappears from `GET /personas`. `GET /personas?include_deleted=true` shows it. POST `/restore` clears `persona_deleted_at`; the record reappears in the default list. Restore on a record that is not soft-deleted returns 422.

9. **`Personas` sidebar entry appears under the Methodology group, position #6.** After the v0.4 entries (Domains, Entities, Processes, CRM Candidates, Engagements) and ahead of the planned but possibly not-yet-shipped Fields entry. Position #6 if Personas ships first of the v0.5+ trio; position adjusts if Fields ships first.

10. **Master pane columns and default sort.** The Personas panel shows columns Identifier / Name / Status / Updated, sorted by Identifier ascending. Right-click context menu offers New / Edit / Delete / Restore.

11. **Detail pane renders all fields in section-3.2 order.** Identifier (read-only), Name, Role Summary, Responsibilities (collapsible, expanded by default), Notes (collapsed under "Internal notes" header), Status, ReferencesSection — all present and bound to the correct fields.

12. **CRUD dialogs work end to end.** Create assigns identifier server-side, persists all fields, surfaces server-side validation errors inline. Edit persists field changes including status transitions. Delete prompts for edge-text confirmation (user types the identifier) and soft-deletes on confirm. Restore reappears the record.

13. **`persona_scopes_to_domain` and `persona_realized_as_entity` registered in vocabulary and constrained correctly.** `REFERENCE_RELATIONSHIPS` includes both new kinds. `_kinds_for_pair((persona, domain))` returns `{persona_scopes_to_domain}`. `_kinds_for_pair((persona, entity))` returns `{persona_realized_as_entity}`. Attempting to POST `/references` with `(persona, domain)` or `(persona, entity)` and an unsupported kind returns 422. The Alembic migration extends the `refs.relationship_kind` CHECK constraint to include both new values; direct DB insert with an unknown kind is rejected.

14. **Sample CBM-redo Phase 2 / Phase 3 records authored through the UI, including domain affiliations and entity realizations.** A consultant can author roughly 5–8 persona records (e.g., Program Manager, Mentor Coordinator, Volunteer Mentor, Client, Donor, Board Member), attach one or more `persona_scopes_to_domain` references per persona to authored `domain` records, attach `persona_realized_as_entity` references for those personas backed by an entity (e.g., Volunteer Mentor → Mentor entity, Client → Contact entity), transition statuses from `candidate` to `confirmed`, and the records and references persist correctly across application restart and across REST/MCP refetch.

### 3.8 Open Questions and Deferred Decisions

Categorized per the spec guide section 3.8 convention. Each entry is one paragraph with an explicit category tag.

#### 3.8.1 For v0.5+ build to settle

**[v0.5+ build] Create-dialog domain-affiliation and entity-realization flow.** Two reasonable UI patterns for letting the user attach `persona_scopes_to_domain` and `persona_realized_as_entity` references at create time: (a) create-then-attach (the New dialog creates the persona only; the user adds affiliations and realization from the detail pane afterward); (b) create-with-attach (the New dialog includes a multi-select for domains and a single-select for entity realization; on submit the UI runs POST `/personas` then N × POST `/references` in sequence). Both satisfy the acceptance criterion that the user can attach references without leaving the UI. The v0.5+-build-planning conversation decides which pattern is implemented; the reasonable default is whatever pattern the v0.4 build adopted for `entity`, for cross-entity-type consistency. The spec is agnostic.

#### 3.8.2 For CBM redo to surface

**[CBM redo] Markdown for `persona_role_summary` and `persona_responsibilities`.** Plain text in v0.5+. The CBM redo's actual Phase 2 / Phase 3 work will reveal whether role summaries or responsibility lists need emphasis, bullet structure beyond newline-separated items, or inline links. If so, a v0.6 migration introduces markdown rendering. The decision deliberately waits on real-use signal. Same posture as `domain` and `entity`.

**[CBM redo] Entity-realization mechanism friction.** `persona_realized_as_entity` is a references-entity edge per section 3.3.1, chosen for consistency with the references-first discipline despite the fact that most personas realize as at most one entity (a single-value FK could be defensible). The CBM redo will surface whether consultants find the references-edge approach natural or whether the indirection (two API calls; "Add reference" affordance vs an inline field on the persona record) creates noticeable friction. If yes, a new PI to reconsider as a nullable FK column (`persona_realized_as_entity_identifier`) on the `personas` table is in scope. Tracked as PI-XXX-C ("persona-to-entity realization mechanism reconsideration") authored at this conversation's close.

#### 3.8.3 For v0.6+

**[v0.6+] PI-XXX-A — persona authority / access-boundary fields.** New planning item authored at this conversation's close. Captures the deferred classification fields that would express role-based authority (read-only vs read-write per entity; record-scoped vs collection-scoped access; admin vs operator distinction) and that would integrate with CRM-engine-specific role models. v0.5+ ships without these because the evolved methodology has not yet surfaced the granularity required and because the access-boundary mapping is CRM-engine-coupled (the EspoCRM `Role` entity model has specific shape that may or may not be the right design pivot). PI scope: discovery work informed by Phase 2 / Phase 3 use of the v0.5+ thin schema, followed by a schema-extension spec when the methodology surfaces a concrete need.

**[v0.6+] PI-XXX-B — persona membership cardinality (user-persona mapping).** New planning item authored at this conversation's close. Captures the deferred question of how to represent the cardinality that one system user can play many personas (a single individual is both the Program Manager and a Volunteer Mentor) and that one persona can be played by many users (the Volunteer Mentor persona is realized as many Mentor records, each of which corresponds to a user account). PI scope: a `user_plays_persona` references edge from a v0.6+ user entity type (or whatever construct represents system users in v2) to the `persona` table, with cardinality unbounded on both sides. May or may not require a v0.6+ user-or-equivalent entity type to land first.

**[v0.6+] PI-XXX-C — persona-to-entity realization mechanism reconsideration.** New planning item authored at this conversation's close. The `persona_realized_as_entity` edge is implemented as a references-entity many-to-many in v0.5+ for consistency with the references-first discipline. If CBM-redo signal indicates that the references-edge mechanism is friction (see section 3.8.2), a v0.6+ schema migration replaces the references mechanism with a nullable `persona_realized_as_entity_identifier` FK column on the `personas` table. The PI tracks the decision: keep as references (status quo) or migrate to FK (with the accompanying data migration and references-table cleanup).

**[v0.6+] PI-XXX-D — `persona`-to-`process` linkage in `process` growth spec.** Already in scope for PI-005 (process schema growth beyond Phase 1 thin shape). The source-side `process_performed_by_persona` vocabulary entry is registered when the process growth spec lands; this spec's section 3.3.2 documents the anticipated inbound shape for forward awareness.

#### 3.8.4 Cross-spec consistency notes

This spec was authored after the v0.4 methodology workstream closed and is one of three independent v0.5+ specs (`persona`, `field`, requirement/manual_config/test_spec). The cross-spec consistency conventions established at the v0.4-build-planning conversation (DEC-068 spec guide section 6 amendment) apply forward unchanged. Two notes:

- **No prefix collision.** `PER` is checked against all v2 prefixes in section 3.1 and is collision-free.
- **No vocabulary conflict.** `persona_scopes_to_domain` and `persona_realized_as_entity` are new vocab entries that have no naming collision with v0.4-shipped vocab (`entity_scopes_to_domain`, `process_belongs_to_domain`, `process_touches_entity`, `process_connects_to_process`, `process_hands_off_to_process`, etc.). The semantic pattern `_scopes_to_domain` is now shared between `entity` and `persona`; this is a deliberate vocabulary regularity, not a conflict.

### 3.9 Cross-References

#### 3.9.1 Decisions cited by this spec

The following five decisions are authored by running `crmbuilder-v2/scripts/apply_close_out.py` against the close-out payload at conversation close. DEC numbers are placeholders (DEC-XXX-1 through DEC-XXX-5) to be renumbered by the close-out conversation based on the current decision-table head at apply time. Each is linked to this conversation's session record via a `decided_in` reference recorded in the same payload.

- **DEC-XXX-1 — `persona` identifier prefix and format.** Adopts `PER` under the soft-3-letter posture established by `domain.md` (see section 3.1).
- **DEC-XXX-2 — `persona` field inventory and validation under v0.5+ thin shape.** Five substantive fields plus inherited timestamps (`persona_name`, `persona_role_summary`, `persona_responsibilities` optional, `persona_notes` optional, `persona_status`); no `persona_purpose`; no authority/access-boundary classification; no storage-level length caps; case-insensitive `persona_name` uniqueness within the engagement (see section 3.2).
- **DEC-XXX-3 — `persona` status lifecycle.** Adopts the `domain` / `entity` pattern (three values, one-way propose-verify gate, rejection-via-soft-delete, no `archived`) without modification, and documents the persona-status-independent-of-affiliation-and-realization-status posture (see section 3.4).
- **DEC-XXX-4 — `persona`-to-`domain` affiliation and `persona`-to-`entity` realization mechanisms; `persona_scopes_to_domain` and `persona_realized_as_entity` vocabulary registration.** Both relationships implemented via the references entity (many-to-many semantics; `persona_realized_as_entity` is conceptually optional and most often single-target, but the references mechanism permits multi-target). New vocabulary entries registered in `REFERENCE_RELATIONSHIPS` and `_kinds_for_pair`; Alembic migration extends the `refs.relationship_kind` CHECK constraint. Rejects persona-table FK alternatives for both. Zero-affiliation and zero-realization explicitly permitted (see section 3.3.1).
- **DEC-XXX-5 — `persona` API surface, UI defaults, and acceptance criteria for v0.5+.** Standard endpoint set with no deviations; decomposed reference handling (no inline-affiliation or inline-realization convenience endpoints); default `ListDetailPanel` UI under the existing Methodology sidebar group; Domains and Realized-as columns deferred to a future master-pane enrichment paired with PI-007 short codes; create-dialog affiliation/realization flow left as a v0.5+-build decision; 14 testable acceptance criteria (see sections 3.5, 3.6, 3.7).

#### 3.9.2 External references

- `crmbuilder/CLAUDE.md` — universal session-startup entry; documents the `REFERENCE_RELATIONSHIPS` / `_kinds_for_pair` / Alembic-migration triad that section 3.3.1's mechanical additions follow, the `{data, meta, errors}` envelope rule referenced by section 3.5, the PI-002 identifier-optional-on-POST rule referenced by section 3.1 and 3.5.2, and the v0.7 governance entity context within which this v0.5+ methodology entity lands.
- `PRDs/product/crmbuilder-v2/methodology-entity-schema-spec-guide.md` — schema spec template this document follows.
- `PRDs/process/research/evolved-methodology/phase-1-interview-guide.md` v0.2 — the document that originally deferred persona elicitation out of Phase 1 (the deferral PI-003 records). Personas surface in Phase 2 or 3 work; this spec is the storage shape that captures them when they do.
- `PRDs/process/research/evolved-methodology/evolved-methodology-phase-outline.md` — section 3 Phase 2 and Phase 3 boundaries; informs the thin-shape posture and the "when does this entity type need to exist" rationale.

#### 3.9.3 Related prior decisions informing this spec

- **DEC-006** — Universal references table as the cross-entity-type edge store. Direct architectural foundation for both the `persona_scopes_to_domain` and `persona_realized_as_entity` mechanism choices in section 3.3.1.
- **DEC-039** — Minimum entity inventory and multi-tenancy posture. The decision that deferred `persona` from v0.4's minimum-viable inventory; PI-003 (resolved by this spec going into build) is the resulting deferred work.
- **DEC-043** — SES-010 identifier-asymmetry resolution. Mandates the `GET /personas/next-identifier` helper endpoint cited in section 3.5.1; subsequently relaxed by PI-002 to make identifier optional on POST entirely.
- **DEC-046** — Parent-prefix field-naming convention for methodology entities. Establishes the field-naming pattern this spec inherits and applies (see section 3.2).
- **DEC-047** — `domain` status lifecycle, propose-verify gate, and rejection-via-soft-delete posture. Establishes the lifecycle pattern this spec adopts unchanged (see section 3.4).
- **DEC-048** — `domain` relationship posture and `{source}_{verb}_{target}` relationship-kind naming convention. Establishes the relationship-kind naming pattern this spec applies in registering `persona_scopes_to_domain` and `persona_realized_as_entity` (see section 3.3.3).
- **Sibling-spec carryovers (`entity.md`):** DEC-053 (references-over-FK for many-to-many methodology affiliations) — directly applied here for both `persona_scopes_to_domain` (same mechanism as `entity_scopes_to_domain`) and `persona_realized_as_entity`.

#### 3.9.4 Related sibling specs

- `PRDs/product/crmbuilder-v2/methodology-schema-specs/domain.md` — predecessor spec; source of conventions inherited by this document (parent-prefix field naming, `{source}_{verb}_{target}` relationship-kind naming, soft-3-letter prefix posture, status-lifecycle shape, rejection-via-soft-delete posture, no-archived posture). `persona_scopes_to_domain` targets `domain` records.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/entity.md` — predecessor spec; source of references-over-FK posture for many-to-many affiliation. `persona_realized_as_entity` targets `entity` records.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/process.md` — sibling spec; future `process_performed_by_persona` source-side registration will be added in the process growth spec under PI-005.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/engagement.md` — sibling spec (v0.4.x); informs the v0.5+ multi-tenancy / engagement-scoping posture for personas if/when engagement scoping is generalized across methodology entity types.
- (Forthcoming) `PRDs/product/crmbuilder-v2/methodology-schema-specs/field.md` under PI-004 — independent v0.5+ sibling.
- (Forthcoming) requirement / manual_config / test_spec specs under PI-004 — independent v0.5+ siblings.

#### 3.9.5 Planning items cited

- **PI-002** — identifier optional on POST for every prefixed-identifier entity type. Applied uniformly to `persona` in section 3.5.2.
- **PI-003** — `persona` entity type deferred from v0.4. **Resolved by this spec going into build.** Section 1 and section 2 frame the deferral history.
- **PI-004** — additional methodology entity types (`field`, `requirement`, `manual_config`, `test_spec`). `persona` is independent of PI-004 but ships in the same v0.5+ methodology entity workstream successor.
- **PI-005** — process schema growth beyond Phase 1 thin shape. Will register the source-side `process_performed_by_persona` vocabulary entry referenced in section 3.3.2.
- **PI-007** — `domain_short_code` field. Joint enabler for the deferred Domains-column on the persona master pane (section 3.6.2), piggybacking on PI-009.
- **PI-009** — master-pane Domains column on the Entities panel. The persona-side master-pane column work piggybacks on whatever pattern lands here.
- **(New) PI-XXX-A — persona authority / access-boundary fields.** Authored at this conversation's close.
- **(New) PI-XXX-B — persona membership cardinality (user-persona mapping).** Authored at this conversation's close.
- **(New) PI-XXX-C — persona-to-entity realization mechanism reconsideration.** Authored at this conversation's close.

---

*End of document.*

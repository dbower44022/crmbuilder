# Methodology Entity Schema Spec — `service`

**Last Updated:** 06-12-26
**Status:** Draft v1.0 — produced under WTK-132 (storage-area design-spec deliverable for the cross-domain service record type; PI-161)
**Position in workstream:** Resolves the Master CRMBuilder PRD v0.3 mechanics gap — "the cross-domain service entity type remains unbuilt (PI-161); Phase 1 carries services in charter scope text transitionally." The PRD names cross-domain services as a first-class methodology object (§"Methodology layer": *domains, cross-domain services, entities, fields, processes, …*), requires Phase 1 to capture each service's name, purpose, capabilities, and any entities it may own, and stages the four services from the first dogfood run (SES-166) in charter scope text pending this type. This spec closes the gap at the design level; the implementing Work Tasks build from it.
**Companion documents:** `methodology-entity-schema-spec-guide.md` (template); `domain.md` / `persona.md` (lifecycle and references-discipline conventions inherited); `process.md` / `process-v2.md` (the consuming-side entity type and its scalar `process_domain_identifier` parent linkage, which makes domain coverage derivable); `candidate-lifecycle-rejected-and-utilization-evidence.md` (WTK-088 — the `rejected` terminal status + `rejected_by_decision` edge this type joins); `specifications/master-crmbuilder-PRD.md` v0.3 (Phase 1 §"Captured V2 Records" transitional row; §"Activity" item 4).

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 06-12-26 | ADO Area Specialist (storage) / Claude | Initial draft under WTK-132. Defines `service` (`SVC-NNN`) as the methodology record for one cross-domain service: name, purpose, capabilities, notes, standard four-status propose-verify lifecycle. Registers two new reference kinds — `process_consumes_service` (process → service; the primary edge, making cross-domain-ness empirically derivable) and `service_owns_entity` (service → entity; the PRD's "any entities it may own" capture item) — and explicitly rejects `service_scopes_to_domain` with rationale (§3.3.2). Adds `service` to the `rejected_by_decision` source set. Specifies the dual-head CHECK-rebuild migration pair with mid-stream guards per the WTK-106 (0048 / pg-0010) pattern, verification criteria including five example queries and the migration up/down contract, and the backfill representation of the four SES-166 dogfood services (§6). |

---

## Change Log

**Version 1.0 (06-12-26):** Initial creation. No code, vocab, or migration changes ship with this document — it is the design the implementing Work Tasks build from. §5 defines the verification criteria (schema constraints, migration behavior, example queries); §6 defines how the four SES-166 services backfill from charter scope text into proper records; §10 enumerates the build surface.

---

## 1. Purpose and Position

Master CRMBuilder PRD v0.3, Phase 1 Activity item 4:

> **Cross-domain services** — for each: name, purpose, capabilities, any entities it may own.

and the Captured V2 Records table:

> | Cross-domain services | *Transitional:* charter scope text | Methodology | The service entity type does not exist yet (PI-161). Until it lands, capture each service's name and one-line purpose in the charter's scope section; backfill service records when the type ships |

A cross-domain service is a capability the CRM system provides that is not owned by any single business domain — document storage, notifications, user accounts, AI agent orchestration (the four surfaced by the first dogfood run, SES-166). Domains are sequential or parallel slices of the business; services are the horizontal substrate those slices share. The distinction matters for the methodology because services are elicited differently (Phase 1 captures them as a flat list, not via per-domain SME discovery), are consumed rather than owned by processes, and may own entities of their own (a user-accounts service plausibly owns a User entity that no business domain would claim).

The first dogfood run had nowhere to put them: SES-166 captured the four services as a single line in the charter's scope markdown ("**Cross-domain services:** document storage, notifications, user accounts, AI agent orchestration") and PI-161 records the gap. This spec defines the storage shape that closes it, following the per-entity template (`methodology-entity-schema-spec-guide.md`) and the conventions inherited across the workstream lineage (`domain.md` → `entity.md` → `persona.md` → the PI-004 cohort → `migration_mapping.md`):

- parent-prefix field naming (DEC-046),
- `{source}_{verb}_{target}` relationship-kind naming (DEC-048),
- the standard four-status propose-verify lifecycle with terminal `rejected` (DEC-047 + PI-153 / WTK-088),
- references-entity edges over FK columns for inter-record linkage (DEC-006, DEC-053),
- identifier optional on POST with server assignment (PI-002),
- engagement scoping via the row-level discriminator (PI-123).

---

## 2. Summary

A `service` record represents one cross-domain service in the client's target system. Each record holds a client-language service name, a brief plain-text purpose, an optional plain-text capabilities list, an optional consultant scratchpad, and the standard methodology lifecycle status. Two reference kinds give the type its relational shape: `process_consumes_service` edges (inbound, from `process`) record which business processes depend on the service — the empirical content of "cross-domain" — and `service_owns_entity` edges (outbound, to `entity`) record the entities the service owns, per the PRD's Phase 1 capture item. Deliberately, there is **no** `service_scopes_to_domain` kind: a cross-domain service is by definition not domain-bound, and its effective domain coverage is derivable by joining its consuming processes to their parent domains (§3.3.2).

The shape is the thinnest that can faithfully host the Phase 1 capture (name, purpose, capabilities, owned entities) plus the Phase 3 consumption linkage. Like `persona`, the schema grows additively as later methodology phases reveal what `service` needs to carry (provisioning detail, engine mapping, integration boundaries are all explicitly out of scope here).

---

## 3. Schema Specification

### 3.1 Identity

| Field | Value |
|-------|-------|
| Entity type name (storage) | `service` |
| Display name (singular) | Cross-Domain Service |
| Display name (plural) | Cross-Domain Services |
| Identifier prefix | `SVC` |
| Identifier format | `SVC-NNN`, zero-padded to 3 digits (e.g., `SVC-001`) |
| Identifier auto-assignment | Server-side on POST omission; helper at `GET /services/next-identifier` |
| Table name | `services` |
| Engagement scoping | Engagement-scoped (`EngagementScopedPKMixin`) — services are per-engagement methodology records, like `persona` / `finding` / `migration_mapping`, not nullable-scope system records like the PI-122 registry types |

`SVC` is three letters per the soft-3-letter posture (`domain.md` §3.1), reads unambiguously as "service", and has no collision with the live prefix set (checked against every `_IdentifierFormatCheck` registration in `models.py` / `engagement_models.py` as of migration 0048: AGP, CM, COP, CRM, DEC, DEP, DOM, ENG, ENT, FLD, FND, GVR, LRN, MCF, MIG, PER, PI, PRJ, PRN, PROC, RB, REF, REQ, RSK, SES, SKL, STA, TERM, TOK, TOP, TST, WSK, WT, WTK). The storage type name is the one-word `service`, matching the one-word methodology norm (`domain`, `entity`, `field`, `persona`, `process`); "cross-domain" is the display qualifier, not part of the type name.

### 3.2 Fields

Parent-prefix naming per DEC-046: every column is prefixed `service_`. The primary key is the prefixed-string identifier — no integer surrogate `id` column, matching `persona` / `migration_mapping`.

#### 3.2.1 Identity fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `service_identifier` | String(32), PK | yes | server-assigned | `^SVC-\d{3}$` (table CHECK `ck_service_identifier_format` via `_IdentifierFormatCheck`); unique by PK | Server-assigned on POST omission per PI-002 via the SAVEPOINT-retry helper. Explicit supply supported: malformed → 422, collision → 409. |
| `service_name` | String(255) | yes | — | non-empty trimmed; case-insensitive unique within the engagement (repository layer, per the `persona_name` posture — no schema-level expression index) | Service name in the client's language (e.g., "Document Storage", "Notifications", "User Accounts", "AI Agent Orchestration"). |

#### 3.2.2 Content fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `service_purpose` | Text | yes | — | non-empty trimmed | Brief plain-text statement of what the service provides and why it is cross-domain (one to three sentences typical). The PRD's "purpose" capture item. |
| `service_capabilities` | Text | no | — | — | Optional plain-text bullet-form capabilities list (the PRD's "capabilities" capture item), e.g. "- Store and version uploaded documents\n- Attach documents to any record\n- Full-text search". Plain text, newline-separated bullets, mirroring `persona_responsibilities`; a structured-list representation is deferred to real-use signal (§8). |
| `service_notes` | Text | no | — | — | Internal consultant scratchpad. Not part of any client-facing render. Captures elicitation provenance, owned-entity intent before entity records exist (§3.3.1), and rationale trails. |

**No `service_owned_entities` text column.** "Any entities it may own" is relational data, not prose — it lives as `service_owns_entity` edges once entity records exist (§3.3.1). At Phase 1 capture time, before any entity records exist, ownership intent is prose in `service_notes` or `service_capabilities`; the edge is attached when Phase 2/3 surfaces the candidate entity. Adding a text column would create a stored-vs-edges drift hazard for no capture benefit.

#### 3.2.3 Classification fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `service_status` | String(16) | yes | `candidate` | enum CHECK `ck_service_status` over `SERVICE_STATUSES`; transitions per §3.4 | Standard methodology lifecycle. POST directly at `confirmed` is legitimate for records captured live with the stakeholder present (the SES-166 backfill case; precedent `migration_mapping.md` §3.2.3). |

#### 3.2.4 Relationship fields

None. `service` carries no FK columns; both relationship kinds live in the `refs` table (§3.3). This mirrors `persona` exactly and differs from `process` (whose mandatory single-parent domain justified a scalar FK — `service` has no mandatory single parent of any type).

#### 3.2.5 Timestamp fields

| Field name | Type | Required | Default | Description |
|------------|------|----------|---------|-------------|
| `service_created_at` | DateTime(timezone=True) | yes | `_utcnow` on insert | Standard base behavior. |
| `service_updated_at` | DateTime(timezone=True) | yes | `_utcnow` on insert, `onupdate` | Standard base behavior. |
| `service_deleted_at` | DateTime(timezone=True) | no | NULL until soft-delete | Set on DELETE; cleared on POST `/restore`. |

Indexes per the `persona` posture: `ix_services_service_status`, `ix_services_service_deleted_at`. No storage-level length caps on the Text columns (PI-α note: title-class columns that overran `VARCHAR(n)` on Postgres were widened to `Text`; `service_name` at String(255) matches `persona_name` and the widened norm is available if real data overruns it).

### 3.3 Relationships

#### 3.3.1 Registered kinds

Two new reference kinds, both governed by the existing `RELATIONSHIP_RULES` infrastructure (DEC-006), named per `{source}_{verb}_{target}` (DEC-048):

| relationship_kind | source | target | mechanism | cardinality | semantics |
|-------------------|--------|--------|-----------|-------------|-----------|
| `process_consumes_service` | `process` | `service` | references-entity edge | many-to-many | A business process depends on this cross-domain service to execute (e.g., SME Requirements Interview consumes Document Storage and AI Agent Orchestration). Source side is `process` per the naming convention — the process is the actor doing the consuming, exactly as `process_performed_by_persona` and `process_touches_entity` made `process` the source for its other dependency edges (PI-005 precedent). Zero inbound edges is valid (a Phase 1-captured service whose consumers are not yet defined); a process may consume zero or many services. |
| `service_owns_entity` | `service` | `entity` | references-entity edge | many-to-many (typically few) | The service owns this entity — the entity's records exist because of the service, not because of any business domain (e.g., User Accounts owns a User entity; Notifications owns a Notification Preference entity). The PRD's "any entities it may own" Phase 1 capture item. Zero is the common case. An entity owned by a service would not normally also carry `entity_scopes_to_domain` edges; that exclusivity is advisory (consultant discipline), not schema-enforced. |

**Plus one source-set extension to an existing kind:** `service` joins the `rejected_by_decision` source set (PI-153 / WTK-088 §3.4 — uniform across the status-bearing methodology types, which `migration_mapping` extended to eight and `service` extends to nine). The mandatory rejecting-Decision edge accompanying a flip to `rejected` is repository-layer enforcement, exactly as for the other eight. No `ck_ref_relationship` change is needed for this (the kind is already admitted); only the `_kinds_for_pair` source tuple grows.

**Mechanical additions (the CLAUDE.md vocab triad):**

1. `process_consumes_service` and `service_owns_entity` added to `REFERENCE_RELATIONSHIPS` in `access/vocab.py`; `service` added to `ENTITY_TYPES` (and thereby `CHANGE_LOG_ENTITY_TYPES`, which is derived).
2. `_kinds_for_pair` clauses: `(process, service)` adds `process_consumes_service`; `(service, entity)` adds `service_owns_entity`; `service` appended to the `rejected_by_decision` source tuple. Both target types (`process`, `entity`) are live in `ENTITY_TYPES`, so every clause activates unconditionally — no dormant TODOs.
3. The dual-head migration pair rebuilding the `refs` / `change_log` CHECKs (§4).

**Cardinality and validation:** sources and targets must be live records of the named types (existing references-table access rules); duplicate `(source_id, target_id, relationship_kind)` tuples rejected by the existing uniqueness constraint; no per-kind cardinality caps. Soft-deleting either endpoint does not cascade-delete edges (standard v2 behavior); restore reappears them in place.

#### 3.3.2 `service_scopes_to_domain` — considered and rejected

The Work Task's decision point: register `service_scopes_to_domain`, `process_consumes_service`, or both. This spec registers `process_consumes_service` and **rejects** `service_scopes_to_domain`, for three reasons:

1. **It contradicts the type's definition.** A cross-domain service is precisely the thing that is *not* scoped to a domain. The four dogfood services are platform-wide: scoping edges would either enumerate every domain (pure noise, plus a maintenance obligation every time a domain is added — the dogfood already has seven) or, worse, record a subset and thereby misrepresent the service as domain-bound. The `_scopes_to_domain` pattern (`entity`, `persona`, `requirement`, `manual_config`) fits record types whose domain affiliation is real elicited information; for services it is a category error.
2. **Domain coverage is derivable, and derivable beats stored.** Every `process` carries a mandatory scalar `process_domain_identifier`. A service's effective domain coverage is therefore one join: the distinct parent domains of its consuming processes (verification query Q3, §5.1). Storing scoping edges alongside that derivation invites drift — the stored claim and the observed consumption disagree, and nothing reconciles them. This is the same stored-vs-derived discipline the ADO substrate applies to needs-attention rollups (derived at query time, not a stored column).
3. **Phase 1 doesn't elicit it.** The PRD's Phase 1 capture item for services is name / purpose / capabilities / owned entities — domain affiliation is not asked for, so there is no capture moment that would populate the edge. `process_consumes_service`, by contrast, has a natural capture moment: Phase 3 process definition, where each process's dependencies are elicited in detail.

If a future methodology phase surfaces a genuine need for asserted (rather than derived) domain coverage — e.g., a service deliberately restricted to a domain subset — the kind can be added then with one vocab entry, one `_kinds_for_pair` clause, and one CHECK-rebuild migration. Cheap to add, expensive to retire; defer until demanded (§8).

#### 3.3.3 Inbound relationships (anticipated)

Beyond `process_consumes_service` (registered here, declared from the process side semantically but landing in this build), plausible future inbound kinds — **not** registered now: `requirement_realized_by_service` (a requirement satisfied by a service rather than a process; requirement-side spec growth would declare it) and `manual_config_touches_service` (engine-side service configuration items). Their formal registration belongs to source-side spec growth, per the once-per-kind rule.

#### 3.3.4 Hierarchy

None. No service-to-service composition or dependency edges in v1 — the four dogfood services are flat peers, and no methodology pressure for service composition exists yet.

### 3.4 Lifecycle

#### 3.4.1 Status values and transitions

`service` adopts the standard four-status propose-verify lifecycle exactly as the other status-bearing methodology types — no per-type variation:

| Status value | Description | Valid successors |
|--------------|-------------|------------------|
| `candidate` | Proposed (by CRM Builder or surfaced in interview); awaiting client verification. **Default starter.** | `confirmed`, `deferred`, `rejected` |
| `confirmed` | Client has verified the service is in scope. | `deferred` |
| `deferred` | Acknowledged real but out of current engagement scope. | `confirmed`, `rejected` |
| `rejected` | Dropped at triage; truly terminal. | (none) |

The vocab constants are `SERVICE_STATUSES` / `SERVICE_STATUS_TRANSITIONS`, byte-for-byte the same shape as `PERSONA_STATUS_TRANSITIONS`: one-way gate out of `candidate`; `confirmed ⇄ deferred` free movement; `rejected` reachable from `candidate` and `deferred` only (never directly from `confirmed` — two-step demotion via `deferred`); `rejected` has an empty successor set. A no-op transition (target equals current) is always valid.

#### 3.4.2 Transition enforcement

Schema layer: `ck_service_status` CHECK over `SERVICE_STATUSES` membership. Repository layer: transition validation against `SERVICE_STATUS_TRANSITIONS` (invalid → 422 `invalid_status_transition` with `from`/`to`), and the mandatory `rejected_by_decision` edge atomically accompanying any flip to `rejected` (the PI-030 `resolves` atomic edge+flip precedent, as applied by WTK-088 §3.4).

#### 3.4.3 Status independence

`service_status` is independent of the statuses of consuming processes' classifications and owned entities' statuses — set by client verification of the service itself, never derived or cascaded. Mirrors `persona.md` §3.4.3.

#### 3.4.4 Rejection, soft-delete, no `archived`

Standard postures carried forward unchanged: `rejected` is the triage *drop* disposition with its mandatory Decision edge; soft-delete (`service_deleted_at`) tracks existence-in-the-record and is the path for mistaken creations; no `archived` value. DELETE is idempotent; `/restore` on a non-deleted record → 422.

### 3.5 API Surface

Standard endpoint set, no deviations, all wrapped in the `{data, meta, errors}` envelope:

| Method | Path | Notes |
|--------|------|-------|
| GET | `/services` | List; `?include_deleted=true`; `?status=<value>` filter (the one list filter — Phase 1 service counts are small, single digits typical). |
| GET | `/services/{service_identifier}` | 404 if absent. |
| POST | `/services` | `service_identifier` optional (server-assigned per PI-002); `service_status` may be any valid value at POST (the live-capture / backfill case). |
| PUT | `/services/{service_identifier}` | Full replace; body/path identifier mismatch → 422. |
| PATCH | `/services/{service_identifier}` | Partial; transition validation per §3.4.2. |
| DELETE | `/services/{service_identifier}` | Soft-delete; idempotent. |
| POST | `/services/{service_identifier}/restore` | 422 if not soft-deleted. |
| GET | `/services/next-identifier` | `{"next": "SVC-NNN"}` per DEC-043. |

Reference handling is decomposed (DEC-006 discipline): `process_consumes_service` and `service_owns_entity` edges attach via separate `POST /references` calls; no inline-edge convenience endpoints. Unlike `migration_mapping`, no edge is mandatory at POST time, so no atomic row+edges POST machinery is needed — a plain create suffices. MCP tools mirror the REST surface per the established per-entity tool pattern.

### 3.6 UI Considerations

Standard `ListDetailPanel` under the Methodology sidebar group, appended after Migration Mappings. Master pane columns: Identifier / Name / Status / Updated (identifier ascending default sort). Detail pane in §3.2 field order with `service_notes` collapsed by default ("Internal notes") and `service_capabilities` expanded (client-facing render content), then the `ReferencesSection` widget (inbound `process_consumes_service`, outbound `service_owns_entity`). Standard CRUD dialogs with edge-text delete confirmation. The panel is a deferred follow-on of the storage/API build, per the recent-entity norm (the PI-122 registry panels precedent); record creation goes through API/MCP per TOP-013 regardless.

### 3.7 Template section mapping

This spec follows the guide template with one promotion: the SES-166 backfill representability analysis is promoted to its own top-level section (§6) because the Work Task names it as a deliverable; verification criteria are §5 per the `migration_mapping.md` precedent.

---

## 4. Migrations — the dual-head CHECK-rebuild pair

The migration shape follows the WTK-106 pair (`migrations/versions/0048_wtk_106_migration_mapping_entity.py` / `migrations/pg/versions/0010_wtk_106_migration_mapping_entity.py`) exactly — it is the current canonical instance of the pattern. Chain positions stated here assume the heads at authoring time (SQLite `0048`, PG `0010`); the implementing Work Task renumbers to whatever the heads are at build time.

### 4.1 SQLite chain — `0049_pi_161_service_entity.py`

`down_revision = "0048_wtk_106_migration_mapping_entity"`. Module-level deltas derived from the current vocab so the predicates cannot drift from the models:

```python
_NEW_TYPE = "service"
_NEW_KINDS = frozenset({"process_consumes_service", "service_owns_entity"})
_TYPES_NEW / _TYPES_OLD = ENTITY_TYPES / ENTITY_TYPES - {_NEW_TYPE}
_LOG_TYPES_NEW / _LOG_TYPES_OLD = CHANGE_LOG_ENTITY_TYPES / … - {_NEW_TYPE}
_KINDS_NEW / _KINDS_OLD = REFERENCE_RELATIONSHIPS / … - _NEW_KINDS
```

**upgrade():**

1. `Service.__table__.create(bind, checkfirst=True)` — ORM-derived so the table carries the `ck_service_identifier_format` / `ck_service_status` CHECKs and indexes; `checkfirst` keeps it idempotent on the create_all-then-upgrade-head test path.
2. Rebuild `ck_changelog_entity_type` (the known live-DB gotcha: tests build via create_all and miss it; the live DB 500s on the first service change-log write without it — see 0034/0043/0045/0048).
3. Rebuild `ck_ref_source_type` / `ck_ref_target_type` over `_TYPES_NEW` and `ck_ref_relationship` over `_KINDS_NEW`, all via `batch_alter_table` (SQLite table-rebuild semantics).

**Mid-stream guards:** every rebuild helper first inspects `sa.inspect(op.get_bind()).get_table_names()` and skips tables that are absent — the chain must be enterable mid-stream (the stamp-0036 isolated-migration test path), where `refs` / `change_log` don't exist yet. The guarded-create plus guarded-rebuild combination is what makes the migration safe on all three entry paths: fresh chain replay, create_all-then-stamp, and mid-stream stamp.

**downgrade()** (delete-then-rebuild posture per 0045/0048): delete `refs` rows where `source_type`/`target_type` = `'service'` or `relationship_kind` in the two new kinds; delete `change_log` rows with `entity_type = 'service'`; rebuild all four CHECKs over the `_OLD` sets; drop the `services` table (guarded). Deleting first means the narrower CHECKs never fail against surviving rows. Edges created under `rejected_by_decision` with a service source are caught by the `source_type = 'service'` clause — the kind itself stays admitted (it predates this migration).

**Superset property:** every rebuilt CHECK admits a strict superset of the old predicate, so no existing row is invalidated by upgrade — assert this in review by construction (the new sets are the old sets plus the new members), not by row scanning.

### 4.2 PG chain — `0011_pi_161_service_entity.py`

`down_revision = "0010_wtk_106_migration_mapping_entity"`. Same deltas; three differences from the SQLite file, all per the 0010 precedent:

- table create is inspector-guarded (`if Service.__tablename__ not in _tables(): …create(bind)`) rather than `checkfirst` — the PG baseline (`0001_pg_baseline`) is `create_all` from the live ORM, so a freshly-built PG DB already carries the table and the vocab-derived CHECK texts; on such a DB the create is skipped and the constraint rebuilds are same-text no-op-equivalents, while on a pre-existing PG store they are real changes;
- plain `op.drop_constraint` / `op.create_check_constraint` (no `batch_alter_table` — PG alters in place);
- no `_tables()` guard inside the rebuild helpers (`refs` / `change_log` always exist on the PG chain; there is no PG mid-stream-entry path).

Never replay the SQLite chain on a Postgres DB; the two files are siblings, not a sequence.

---

## 5. Verification Criteria

### 5.1 Example queries the schema must answer

- **Q1 — Phase 1 service inventory.** `GET /services?status=confirmed` lists the engagement's confirmed services with purpose and capabilities. Against the dogfood after backfill: exactly the four SES-166 services (§6).
- **Q2 — service consumers.** Inbound `process_consumes_service` refs at a service target → the processes that depend on it. ("What breaks if Notifications is descoped?")
- **Q3 — effective domain coverage (the cross-domain verification).** Join Q2's consuming processes to their `process_domain_identifier`, distinct: the domains a service actually serves. A service whose coverage resolves to one domain is a smell the consultant should triage — it may be domain functionality misfiled as a service. This query is the reason `service_scopes_to_domain` is not stored (§3.3.2).
- **Q4 — owned entities.** Outbound `service_owns_entity` refs → the entities whose existence the service explains. Inverse: an entity's inbound edge of this kind answers "why does this entity exist if no domain claims it?"
- **Q5 — drop rationale.** A `rejected` service's `rejected_by_decision` edge → the Decision recording why it was dropped.

### 5.2 Schema constraints to assert (test surface)

1. `ck_service_identifier_format` — insert with identifier not matching `^SVC-\d{3}$` rejected; POST without identifier assigns a conforming value via the SAVEPOINT-retry helper; explicit malformed → 422, collision → 409.
2. `ck_service_status` — insert outside `SERVICE_STATUSES` rejected at the schema layer; invalid transition (e.g., `confirmed → candidate`, `confirmed → rejected`, anything out of `rejected`) → 422 at the repository layer.
3. Case-insensitive `service_name` uniqueness within the engagement (repository layer) — second insert differing only by case → uniqueness error; same name in a *different* engagement succeeds.
4. Engagement scoping — rows stamp `engagement_id` from the request scope; the standard cross-engagement leak test (a row created under ENG-001 is invisible under ENG-002) passes for `services`.
5. Vocab triad — `RELATIONSHIP_RULES[("process", "service")] ⊇ {process_consumes_service}`; `RELATIONSHIP_RULES[("service", "entity")] ⊇ {service_owns_entity}`; `RELATIONSHIP_RULES[("service", "decision")] ⊇ {rejected_by_decision}`; POST `/references` with an unsupported kind for these pairs → 422; direct DB insert of a `refs` row with an unadmitted kind or type rejected by the rebuilt CHECKs.
6. Change-log admittance — a service create/update/delete writes `change_log` rows with `entity_type = 'service'` without violating `ck_changelog_entity_type` **on a chain-migrated DB**, not only a create_all DB (the 0034 gotcha; test via the stamp-then-upgrade path).
7. Soft-delete round-trip — DELETE sets `service_deleted_at` and hides the row from the default list; `?include_deleted=true` shows it; `/restore` reappears it; restore on a live row → 422; edges survive both directions.

### 5.3 Migration up/down behavior to assert

1. **Fresh-chain replay:** `alembic upgrade head` from empty creates `services` with both table CHECKs and both indexes, and the four rebuilt CHECKs admit the new type/kinds.
2. **create_all-then-upgrade-head:** idempotent — `checkfirst` skips the existing table; constraint rebuilds succeed (same-text on SQLite batch rebuild).
3. **Mid-stream entry (stamp-0036 path):** stamping mid-chain and upgrading through this migration does not error on absent `refs`/`change_log` — the `_tables()` guards skip them.
4. **Downgrade:** with service rows, service-touching refs (including a `rejected_by_decision` edge from a service), and service change-log rows present, downgrade deletes exactly those rows, restores the narrower CHECKs without violation, and drops the table; a subsequent upgrade round-trips cleanly.
5. **Superset check:** upgrade invalidates no pre-existing row (by-construction review per §4.1; the PG file's rebuilds are no-op-equivalent on a baseline-built DB).
6. **PG chain:** the companion migration applies on a PG store materialised from an earlier baseline (real changes) and on a fresh baseline (guarded no-op), per the `CRMBUILDER_V2_TEST_PG_URL`-gated test env.

---

## 6. Representing the four SES-166 dogfood services

The SES-166 charter (v1.0 payload markdown, scope section) carries the transitional capture verbatim:

> **Cross-domain services:** document storage, notifications, user accounts, AI agent orchestration.

Backfill, once the type ships — four POSTs under `X-Engagement: CRMBUILDER`, each directly at `confirmed` (administrator-confirmed live in SES-166; §3.2.3):

| Identifier (expected) | `service_name` | `service_purpose` (drafted from SES-166 context; the backfill session confirms wording) |
|---|---|---|
| `SVC-001` | Document Storage | Store, version, and attach documents across all domains' records — requirements artifacts, specifications, deliverables. |
| `SVC-002` | Notifications | Notify users of events and state changes across domains — approvals due, gates reached, feedback received. |
| `SVC-003` | User Accounts | Account, identity, and access for every persona across the system; the cross-domain substrate role-based access builds on. |
| `SVC-004` | AI Agent Orchestration | Coordinate the AI agents that execute methodology work across domains — the delivery organization's runtime substrate. |

Backfill mechanics, per the PRD's "backfill service records when the type ships" note and TOP-013 recording rules:

1. The four service rows POST at `confirmed` with `service_notes` recording provenance ("captured in SES-166 charter scope text; backfilled per PI-161").
2. No `process_consumes_service` edges at backfill — the dogfood's seven processes (PROC-002…008) have not had Phase 3 dependency elicitation; consumption edges attach when that pass runs. Zero-inbound is a valid state (§3.3.1).
3. No `service_owns_entity` edges at backfill — no entity records exist yet in ENG-001; ownership intent (e.g., User Accounts → a future User entity) is prose in `service_notes` until Phase 2/3 surfaces candidates.
4. A Decision records the backfill and supersedes the charter's transitional line as the source of truth; the charter markdown itself is versioned history and is not edited retroactively — the next charter version drops the transitional line, per the PRD's Captured V2 Records table note.
5. The Master PRD v0.3 transitional rows (Phase 1 capture table, completeness criterion, §"remains unbuilt" bullet) update to point at the service record type — that PRD edit is part of PI-161's resolution, not of this storage build.

This is the spec's existence proof: every Phase 1 capture item for the four real services has a home (name → `service_name`, purpose → `service_purpose`, capabilities → `service_capabilities`, owned entities → `service_owns_entity` edges or notes-prose pre-entity), and nothing about them requires a field this spec doesn't define.

---

## 7. Acceptance Criteria

1. Alembic migrations (both heads) apply and downgrade per §5.3.
2. `services` table constraints behave per §5.2 items 1–4.
3. Vocab triad registered and enforced per §5.2 item 5; change-log admittance per item 6.
4. Standard endpoint set live per §3.5 with envelope discipline, identifier auto-assignment, transition validation, soft-delete/restore per §5.2 item 7.
5. The four SES-166 services backfill per §6 and Q1 returns exactly them.
6. `rejected` flip requires the atomic `rejected_by_decision` edge (repository layer), matching the other eight status-bearing types.
7. Queries Q2–Q4 answerable via existing `/references` reads; Q3's join produces multi-domain coverage once consumption edges exist.

---

## 8. Open Questions and Deferred Decisions

**[Build] Migration numbering.** §4's `0049`/`0011` assume the authoring-time heads; the implementing Work Task renumbers to the build-time heads (parallel ADO work may claim numbers first — the WTK-106 pair itself landed the same day as this spec).

**[Real-use signal] Structured capabilities.** `service_capabilities` is newline-bulleted plain text. If later phases need per-capability records (e.g., requirements tracing to individual capabilities), a `capability` child type or structured JSON column is a future PI; deferred until a methodology phase actually consumes capability-level granularity.

**[Real-use signal] Asserted domain coverage.** §3.3.2 rejects `service_scopes_to_domain` in favor of derivation. If an engagement surfaces a service deliberately restricted to a domain subset where the restriction must be asserted before consumption edges exist, register the kind then (one vocab entry, one clause, one CHECK-rebuild pair).

**[Source-side growth] `requirement_realized_by_service` / `manual_config_touches_service`.** Anticipated inbound kinds (§3.3.3); registration belongs to those types' spec growth.

**[Follow-on] UI panel and MCP tools.** §3.6 panel and the per-entity MCP tool set follow the storage/API build per the recent-entity norm.

---

## 9. Cross-References

**Decisions to be authored at build-closure** (descriptive, unnumbered — identifiers claimed on `main` at apply time per the Model A branch protocol): (a) `service` identity/prefix/lifecycle adoption; (b) the `process_consumes_service` + `service_owns_entity` registration and the explicit rejection of `service_scopes_to_domain` with the derivability rationale; (c) the no-owned-entities-column posture (edges + notes-prose pre-entity); (d) the SES-166 backfill-at-confirmed posture and charter-supersession mechanics.

- `specifications/master-crmbuilder-PRD.md` v0.3 — the Phase 1 capture requirement, transitional charter-scope rows, and backfill note this spec implements.
- `methodology-entity-schema-spec-guide.md` — the template; §3.7 documents the one section promotion.
- `domain.md` / `persona.md` / `migration_mapping.md` — lifecycle, naming, references-discipline, and migration-pattern precedents.
- `candidate-lifecycle-rejected-and-utilization-evidence.md` (WTK-088) — the `rejected` terminal status and `rejected_by_decision` mechanics `service` joins.
- `process-v2.md` — the consuming-side type; `process_domain_identifier` (the Q3 derivation walk); the PI-005 process-as-source edge precedent.
- Migrations `0048` / pg `0010` (WTK-106) — the canonical dual-head CHECK-rebuild pair §4 instantiates.
- DEC-006 (references-first), DEC-043 (next-identifier helpers), DEC-046 (parent-prefix naming), DEC-047 (lifecycle), DEC-048 (relationship-kind naming), PI-002 (identifier optional on POST), PI-123 (engagement scoping), PI-153 (`rejected` uniformity), PI-161 (the gap this spec closes), SES-166 (the dogfood run that surfaced it).

---

## 10. Implementation Notes (build surface for the implementing Work Tasks)

This spec ships no code. The build surface:

- **vocab.py:** `SERVICE_STATUSES` / `SERVICE_STATUS_TRANSITIONS` (standard four-status, the `PERSONA_*` shape verbatim); `process_consumes_service` + `service_owns_entity` in `REFERENCE_RELATIONSHIPS`; `service` in `ENTITY_TYPES`; `_kinds_for_pair` clauses for `(process, service)` and `(service, entity)`; `service` appended to the `rejected_by_decision` source tuple.
- **models.py:** `Service(EngagementScopedPKMixin, Base)` per §3.2 — String(32) PK, String(255) name, three Text content columns, String(16) status, three timestamps, two CHECKs (`_IdentifierFormatCheck`, `_check_in` over `SERVICE_STATUSES`), two indexes.
- **Migrations, dual-head:** §4's pair — SQLite chain with `checkfirst` create, `batch_alter_table` CHECK rebuilds (change_log + refs ×3), `_tables()` mid-stream guards, delete-then-rebuild downgrade; PG chain with inspector-guarded create and in-place rebuilds; never replay the SQLite chain on PG.
- **Repository layer:** standard CRUD repo per `repositories/persona.py`; CI name uniqueness; transition validation; the atomic `rejected_by_decision` edge+flip (reuse the WTK-088 mechanism, extended to the ninth type); the `?status=` list filter.
- **API:** standard endpoint set (§3.5), envelope, next-identifier helper.
- **MCP tools + UI panel:** follow-on per §8.
- **Backfill:** the four SES-166 POSTs + provenance Decision per §6 — a governance apply on `main`, not part of the branch build (Model A).

---

*End of document.*

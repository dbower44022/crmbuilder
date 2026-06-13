# Methodology API Spec — Cross-Domain Service V2 API

**Last Updated:** 06-12-26
**Status:** Draft v1.0 — produced under WTK-133 (api-area spec deliverable for the PI-161 cross-domain service REST surface)
**Position in workstream:** API companion to `service.md` (WTK-132), which defines the `service` record type (`SVC-NNN`), its two reference kinds (`process_consumes_service`, `service_owns_entity`), and its standard four-status lifecycle. That spec's §3.5 sketches the endpoint set; this spec is the full API design: per-endpoint request/response contracts, lifecycle-transition handling on the wire, the validation sequence and error-semantics assignment against the live handler taxonomy in `api/errors.py`, the edge-management surface (decomposed through `/references`, per the chosen vocab pattern), and per-endpoint acceptance checks. Where the two documents state the same rule, WTK-132 owns the *storage* semantics and this spec owns the *wire* semantics; on endpoint shapes this spec supersedes the §3.5 sketch.
**Companion documents:** `service.md` (WTK-132 — schema, §3.3 edge model and the `service_scopes_to_domain` rejection, §5 verification queries Q1–Q5, §6 SES-166 backfill); `migration-mapping-api.md` (WTK-105 — the api-area sibling-spec template and the freshest wire-convention precedent, now implemented as WTK-107); `persona.md` §3.5 + `api/routers/persona.py` (the cohort surface `service` mirrors — no FK columns, no mandatory edges, plain create); `candidate-lifecycle-rejected-and-utilization-evidence.md` (WTK-088 — the `rejected_by_decision` admission paths live in `access/repositories/_rejection.py`); `specifications/master-crmbuilder-PRD.md` v0.3 (Phase 1 §"Captured V2 Records" transitional row this surface retires).

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 06-12-26 | ADO Area Specialist (api) / Claude | Initial draft under WTK-133. Full contracts for the eight standard endpoints (the persona shape — no derived check endpoints, no embedded-links block, no inline-evidence param, each omission documented). One list filter: validated `?status=` per `service.md` §3.5, following the WTK-107 `invalid_filter` precedent. POST refuses explicit `rejected` as a starter (a deliberate tightening over the persona cohort's latent permissiveness; §4.4). PATCH exposes the unprefixed `rejected_by_decision` atomic-admission key (the WTK-105 §4.9 API-first-authoring posture; `service` joins `_rejection._REJECTABLE_SOURCES` as the ninth type). Edge management fully decomposed through `/references` with wire-level contracts for both kinds plus the rejection-edge delete guard (§5). Zero new exception classes or handlers — every refusal renders through existing machinery (§7). Acceptance checks per endpoint including the SES-166 four-service backfill drive (§8). |

---

## Change Log

**Version 1.0 (06-12-26):** Initial creation. Spec only — no code ships with this document; §10 enumerates the build surface for the implementing Work Task.

---

## 1. Purpose and Position

Master CRMBuilder PRD v0.3 requires Phase 1 to capture each cross-domain service's name, purpose, capabilities, and any entities it may own, and carries the four SES-166 dogfood services transitionally in charter scope text pending the entity type (PI-161). WTK-132 designed the record type; this spec designs the REST surface those records are authored and read through — the surface the SES-166 backfill (four POSTs at `confirmed`), Phase 1 service capture, and Phase 3 consumption-edge attachment all run against.

Authoring context shapes the design less dramatically than it did for migration mappings: services arrive in Phase 1 as a flat list of single digits, not triage batches of hundreds, and a service record is self-contained — no edge is mandatory at create time (`service.md` §3.5: "a plain create suffices"). The surface therefore needs no atomic row+edges POST, no derived gate endpoints, and no embedded-links read block. What it does need is exact cohort parity — the persona shape, byte-for-byte conventions — so the ninth status-bearing methodology type costs the API layer nothing new: zero exception classes, zero handlers, one router, three schemas, one repository.

## 2. Conventions Inherited (verified against source)

The surface follows the live methodology-entity cohort exactly; the facts below were verified against the code, not assumed:

- **Envelope.** Success bodies are `ok(payload)` → `{"data": ..., "meta": {}, "errors": null}` (`api/envelope.py`). Access-layer refusals render through `access_layer_handler` as `errors: [{code, field, message}]` lists; disallowed status transitions bypass the envelope through the dedicated `status_transition_handler` flat shape `{"error": "invalid_status_transition", "from": ..., "to": ...}` (`api/errors.py`).
- **Error taxonomy.** Access-layer exceptions carry `http_status` class attributes: `UnprocessableError` 422, `NotFoundError` 404, `ConflictError` 409 (`access/exceptions.py`). FastAPI body-shape failures render as 422 `request_validation_error` envelopes via `request_validation_handler`.
- **Pydantic boundary.** All bodies subclass `_Base` (`model_config = ConfigDict(extra="forbid")`) in `api/schemas.py`; unknown keys are 422 at the boundary. Body keys are parent-prefixed (`service_*`); repository kwargs are unprefixed; the PATCH router strips the prefix from `model_dump(exclude_unset=True)` so explicit-null (clear) is distinct from omitted (unchanged) — the `persona.py` router pattern, where the strip constant is `_FIELD_PREFIX`.
- **Sessions and scoping.** Reads use `readonly_session()`, writes `writable_session()` (`api/deps.py`). Every request is engagement-scoped by the `X-Engagement` header through `scope_middleware`; `services` is engagement-scoped (`service.md` §3.1), so all reads filter and all writes stamp `engagement_id` without endpoint-level code.
- **Identifier handling.** `service_identifier` is optional on POST, server-assigned via the SAVEPOINT-retry helper (PI-002; `persona._insert_with_autoassign` is the function shape, with its `_MAX_AUTOASSIGN_ATTEMPTS` ceiling surfacing as 409 on exhaustion); `GET /services/next-identifier` per DEC-043, declared **before** `/{identifier}` in the router (static-before-dynamic route order is load-bearing — the `field.py` precedent, repeated in `migration_mappings.py`).
- **Status transitions.** Disallowed transitions raise `StatusTransitionError` and render through the existing handler; the `rejected` terminal uses the shared `_rejection.py` enforcement (edge-first or atomic key; §4.6). A no-op transition (target equals current) is always permitted (`persona._check_transition`).
- **Repository idiom.** The repository mirrors `repositories/persona.py` function-for-function: module-level `list_/get_/create_/update_/patch_/delete_/restore_/next_*_identifier`, `to_dict` wire dicts, `change_log.emit` on every write, `_PATCHABLE_FIELDS` allowlist, case-insensitive name uniqueness over live rows only.

**No pagination in v1.** Cohort list endpoints are unbounded; an engagement's services are single digits (`service.md` §3.5). Parity is kept; `limit`/`offset` is deferred to real-use signal.

**No `include_evidence` parameter — deliberate omission.** The persona/entity/field/process/manual-config routes carry the `embed_inline_evidence` opt-in because those five are exactly `BASELINE_CAPTURE_TYPES` — the types an existing-system audit deposits as candidates, which utilization evidence attaches to (`vocab.py`: `EVIDENCE_SUBJECT_TYPES = BASELINE_CAPTURE_TYPES`). Services are charter/interview-born, never audit-deposited; `service` does not join `BASELINE_CAPTURE_TYPES`, so the parameter would be dead surface. If a future audit pass ever deposits service candidates, the embed is a two-line router addition then.

## 3. Endpoint Inventory

| # | Method | Path | Purpose | Success |
|---|--------|------|---------|---------|
| E1 | GET | `/services` | List, optional `?status=` filter | 200 |
| E2 | GET | `/services/next-identifier` | Next `SVC-NNN` (DEC-043) | 200 |
| E3 | GET | `/services/{identifier}` | Single fetch | 200 |
| E4 | POST | `/services` | Create (plain — no edges) | 201 |
| E5 | PUT | `/services/{identifier}` | Full replace | 200 |
| E6 | PATCH | `/services/{identifier}` | Partial update, status transitions | 200 |
| E7 | DELETE | `/services/{identifier}` | Soft-delete (row only; edges untouched) | 200 |
| E8 | POST | `/services/{identifier}/restore` | Restore | 200 |

Router: `api/routers/services.py`, `APIRouter(prefix="/services", tags=["services"])`, registered in `api/main.py` after `migration_mappings` in the methodology block. E2 is declared before E3.

Edge operations (consumption, ownership, rejection provenance) are **not** service routes — they are `/references` calls per the decomposed-reference discipline (DEC-006); §5 gives their wire contracts as part of this surface's design.

## 4. Per-Endpoint Contracts

### 4.1 The record shape on the wire (all reads and write responses)

Every endpoint that returns a service returns the repository `to_dict` of the full column set — no embedded blocks:

```json
{
  "service_identifier": "SVC-002",
  "service_name": "Notifications",
  "service_purpose": "Notify users of events and state changes across domains — approvals due, gates reached, feedback received.",
  "service_capabilities": "- Notify on approval due\n- Notify on gate reached\n- Digest mode",
  "service_notes": "captured in SES-166 charter scope text; backfilled per PI-161",
  "service_status": "confirmed",
  "service_created_at": "2026-06-12T14:03:11+00:00",
  "service_updated_at": "2026-06-12T14:03:11+00:00",
  "service_deleted_at": null,
  "engagement_id": "ENG-001"
}
```

**Why no embedded links block.** `migration_mapping` embeds its two edges on every read because they are *constitutive* — the record has no name column and is unreadable without its source → target pair (WTK-105 §4.1). A service is the opposite case: `service_name` is its label, both edge kinds are auxiliary (zero edges is the common, valid state — `service.md` §3.3.1), and the known consumers of edge data (queries Q2–Q4) are reference-shaped reads, not row reads. Embedding would buy nothing and cost the batched-assembly machinery. Consumers needing edges call `/references` (§5.3).

### 4.2 E1 — `GET /services`

Query parameters (all optional, combinable):

| Param | Values | Semantics |
|-------|--------|-----------|
| `status` | a `SERVICE_STATUSES` member | Filter on `service_status`. Other values → 422 envelope, code `invalid_filter`, field `status` (the WTK-107 `level`-filter precedent in `migration_mapping.list_migration_mappings`). |
| `include_deleted` | `true` | Include soft-deleted rows. Default excludes. |

Response: 200, `data` = list of §4.1 records ordered by `service_identifier` ascending. Unknown query params are ignored (FastAPI default), matching the cohort. `GET /services?status=confirmed` is query Q1 (`service.md` §5.1) — the Phase 1 service inventory.

### 4.3 E2 — `GET /services/next-identifier`

200, `data` = `{"next": "SVC-NNN"}`. Read-only; the allocator scans all rows including soft-deleted so a retired identifier is never reused (`persona.next_persona_identifier` posture); concurrent-POST safety comes from the SAVEPOINT-retry assigner, not this read (DEC-043).

### 4.4 E3 — `GET /services/{identifier}`

200 with the §4.1 record. `?include_deleted=true` admits a soft-deleted row. Unknown or (without the flag) soft-deleted identifier → 404 via `NotFoundError("service", identifier)`, standard envelope.

### 4.5 E4 — `POST /services`

Plain create — row + change-log emit; no edges (none are mandatory, `service.md` §3.5). Body (`ServiceCreateIn`):

| Key | Type | Required | Notes |
|-----|------|----------|-------|
| `service_name` | str | yes | non-empty trimmed; case-insensitive unique among live rows in the engagement |
| `service_purpose` | str | yes | non-empty trimmed |
| `service_capabilities` | str \| null | no | newline-bulleted plain text (`service.md` §3.2.2) |
| `service_notes` | str \| null | no | — |
| `service_status` | str \| null | no | server default `candidate`; explicit `confirmed` / `deferred` permitted (the live-capture / SES-166 backfill posture, `service.md` §3.2.3); explicit `rejected` refused as a starter |
| `service_identifier` | str \| null | no | server-assigned when omitted; explicit must match `^SVC-\d{3}$` (422) and not collide (409) |

**Validation sequence (deterministic; first failure wins, tests assert the order):**

1. Boundary: body shape, unknown keys (`extra="forbid"`), missing required keys → 422 `request_validation_error` envelope.
2. `service_name` non-empty trimmed → 422 `missing_or_empty`.
3. `service_purpose` non-empty trimmed → 422 `missing_or_empty`.
4. `service_status` ∈ `SERVICE_STATUSES` → 422 `invalid_value`; explicit `rejected` → 422 `invalid_starter_status` (§4.5.1).
5. Name uniqueness: case-insensitive collision with a live service in the engagement → 422 `duplicate` on field `service_name` (`persona._reject_duplicate_name` shape; soft-deleted rows do not participate).
6. Identifier: explicit malformed → 422 `invalid_format`; explicit collision → 409 `ConflictError`; omitted → SAVEPOINT-retry assignment (exhaustion → 409).

Success: 201, `data` = the §4.1 record. A failure at any step leaves no row (single transaction).

#### 4.5.1 `rejected` refused as a starter — a deliberate cohort tightening

The persona-cohort repositories validate create-time status by enum membership only, so a POST at `rejected` would currently slip past the WTK-088 invariant (a record sits at `rejected` only while edge-backed — create has no edge mechanism, and the atomic key is a PATCH/PUT concept). WTK-105 §4.7 already closed this for mappings ("explicit `rejected` refused as a starter"); `service` adopts the same rule rather than the cohort's latent permissiveness. There is no legitimate birth-rejected case: a service dropped at triage was first a `candidate`. Error: 422 envelope, field `service_status`, code `invalid_starter_status`, message directing the caller to create-then-PATCH with `rejected_by_decision`. Retrofitting the same refusal onto the older cohort types is noted as a follow-on (§9), not done here.

### 4.6 E5 — `PUT /services/{identifier}`

Full replace of the §4.5 scalar columns. `service_identifier` optional-but-must-match the path if supplied (mismatch → 422 `path_mismatch`); `service_name` / `service_purpose` required (a full replace cannot blank them); `service_capabilities` / `service_notes` replaced wholesale (`null` clears); `service_status` **required** (the `PersonaReplaceIn` posture — a full replace states the whole record). Status changes are transition-validated exactly as on PATCH, including the `rejected` admission (the repository `update_*` accepts the unprefixed `rejected_by_decision` kwarg, as `persona.update_persona` does, but the key is **not** exposed in `ServiceReplaceIn` — rejection over REST goes through PATCH, §4.7, or edge-first; matching `MigrationMappingReplaceIn`). Name changes re-run the uniqueness check excluding the row itself. 404 on unknown identifier.

### 4.7 E6 — `PATCH /services/{identifier}`

Partial update; `model_dump(exclude_unset=True)`, prefix-stripped, forwarded to the repository (`patch_service(s, identifier, **fields)` with a `_PATCHABLE_FIELDS` allowlist). Patchable: `name`, `purpose`, `capabilities`, `notes`, `status`, plus the **unprefixed** `rejected_by_decision` admission key. Not patchable: identifier, timestamps. Unknown body keys → boundary 422; an explicit `service_notes: null` clears, an omitted key leaves unchanged.

Status semantics:

- Transitions validated against `SERVICE_STATUS_TRANSITIONS` (the standard four-status table, `service.md` §3.4.1: one-way gate out of `candidate`; `confirmed ⇄ deferred`; `rejected` from `candidate`/`deferred` only, never directly from `confirmed`; terminal). Refusal renders through the **existing** `status_transition_handler`: 422 `{"error": "invalid_status_transition", "from": ..., "to": ...}`. No-op is always permitted.
- `→ rejected` requires the WTK-088 admission: either `rejected_by_decision: "DEC-NNN"` in the same PATCH (atomic edge + flip via `_rejection.enforce_rejected_status`) or a pre-existing live `rejected_by_decision` edge. Without either → 422 envelope, code `rejected_requires_decision_edge` (the `_rejection.py` shape, not redefined here). `service` joins `_rejection._REJECTABLE_SOURCES` as the ninth type.
- `rejected_by_decision` supplied outside a transition is valid only on a record already at `rejected` (a superseding Decision adding a second edge — `_rejection.attach_decision`); any other status → 422 `invalid_usage`.
- **REST exposure of the atomic key, per the WTK-105 §4.9 posture:** the older cohort supports the key in the repository but not in its `PatchIn` schemas (verified: `PersonaPatchIn` carries no `rejected_by_decision`), making those types edge-first-only over REST. Services are authored API-first (TOP-013: record creation goes through API/MCP), so `ServicePatchIn` carries `rejected_by_decision: str | None` — two calls where one is atomic is exactly the gap to avoid. This matches `MigrationMappingPatchIn`; the cohort retrofit remains the §9 follow-on.

### 4.8 E7 — `DELETE /services/{identifier}`

Soft-delete: stamps `service_deleted_at`. Idempotent — deleting an already-deleted service is 200 with the unchanged record. 404 on unknown identifier. **Edges are not cascade-deleted** (`service.md` §3.3.1; the persona §3.4.6 posture — the repository never touches the `refs` table): inbound `process_consumes_service` and outbound `service_owns_entity` / `rejected_by_decision` rows persist and surface via the show-deleted toggles on either side. Soft-delete is the bookkeeping exit for mistaken creations; governed withdrawal is `PATCH → rejected` (the WTK-088 three-exit distinction).

### 4.9 E8 — `POST /services/{identifier}/restore`

Clears `service_deleted_at`. 422 envelope, code `not_deleted`, if the row is live; 404 on unknown identifier. No edge re-checks apply (nothing was deleted with the row, and `service_name` uniqueness only considers live rows — see the restore-collision note in §6). A restored service reappears at its pre-delete status, including `rejected` (its decision edge was locked in place throughout by `guard_edge_delete`).

## 5. Edge Management (the `/references` surface for services)

Reference handling is decomposed (DEC-006; `service.md` §3.5): no inline edge fields in any service body, no `/services/{id}/consumers` or `/owns` shortcut routes. The contracts below are part of this surface's design even though they execute on the existing `/references` routes — the implementing Work Task's contract tests exercise them (§8, group K).

### 5.1 Writes

| Operation | Call | Outcome |
|-----------|------|---------|
| Attach a consumer | `POST /references` `{source_type: "process", source_id: "PROC-NNN", target_type: "service", target_id: "SVC-NNN", relationship: "process_consumes_service"}` | 201; refused 422 if the kind is not admitted for the pair (vocab), either endpoint is absent, or the `(source, target, kind)` tuple already exists (the refs-table uniqueness). |
| Attach an owned entity | `POST /references` `{source_type: "service", source_id: "SVC-NNN", target_type: "entity", target_id: "ENT-NNN", relationship: "service_owns_entity"}` | Same semantics, service on the source side. |
| Attach rejection provenance | `POST /references` with `relationship: "rejected_by_decision"`, service source, decision target | The edge-first admission path for §4.7's `→ rejected`. |
| Detach | the existing `/references` delete path | Refused 422 `rejected_edge_locked` for a `rejected_by_decision` edge while the service sits at `rejected` (`_rejection.guard_edge_delete` — activates for services exactly when `service` joins `_REJECTABLE_SOURCES`; no new code). Consumption/ownership edges detach freely. |

`POST /references` with `service_scopes_to_domain` (or any service/domain pairing) → 422: the kind deliberately does not exist (`service.md` §3.3.2); domain coverage is derived, never stored.

### 5.2 Reads (the wire forms of Q2, Q4, Q5)

| Query | Call |
|-------|------|
| Q2 — who consumes this service | `GET /references?target_id=SVC-NNN&relationship=process_consumes_service` |
| Q4 — what entities does it own | `GET /references?source_id=SVC-NNN&relationship=service_owns_entity` (inverse: `?target_id=ENT-NNN&...` answers "which service explains this entity") |
| Q5 — why was it rejected | `GET /references?source_id=SVC-NNN&relationship=rejected_by_decision` |

Q3 (effective domain coverage — Q2's consuming processes joined to their `process_domain_identifier`, distinct) is a client-side composition of Q2 plus process reads; it gets no dedicated endpoint in v1. Unlike the PRD §8 completeness rule that justified `/triage-completeness` for mappings, no methodology gate consumes Q3 — it is a consultant triage aid ("single-domain coverage is a smell"). A derived read can be added when a phase-close check actually wants it (§9).

## 6. Validation Rules (consolidated)

| Rule | Where enforced | Error |
|------|----------------|-------|
| `service_name` / `service_purpose` non-empty trimmed | repo (create/PUT; PATCH when touched) | 422 `missing_or_empty` |
| `service_name` case-insensitive unique among live rows, engagement-scoped | repo, all write paths that touch name | 422 `duplicate` |
| `service_status` ∈ `SERVICE_STATUSES` | repo | 422 `invalid_value` |
| No birth at `rejected` | repo, create only | 422 `invalid_starter_status` (§4.5.1) |
| Transitions per `SERVICE_STATUS_TRANSITIONS` | repo | 422 flat `invalid_status_transition` |
| `→ rejected` edge-backed (atomic key or pre-existing edge) | `_rejection.enforce_rejected_status` | 422 `rejected_requires_decision_edge` |
| `rejected_by_decision` key outside a transition only at `rejected` | `_rejection.attach_decision` | 422 `invalid_usage` |
| Identifier format `^SVC-\d{3}$` (explicit) | repo | 422 `invalid_format` |
| Identifier collision (explicit) / assigner exhaustion | repo | 409 `ConflictError` |
| PUT body/path identifier mismatch | repo | 422 `path_mismatch` |
| Restore of a live row | repo | 422 `not_deleted` |
| `?status=` filter domain | repo list | 422 `invalid_filter` |
| Edge vocab (pair → kinds), endpoint existence, tuple uniqueness | existing `/references` machinery | 422 / 409, unchanged |

**Name-uniqueness corner (documented, by design):** uniqueness considers live rows only, so "Notifications" can be re-created while a soft-deleted "Notifications" exists; the old row is then restorable into a duplicate-name state. This is the live persona behavior, accepted there and accepted here for parity — restore is a rare recovery action and the consultant resolves the duplicate by renaming. Tightening restore to re-check the name is a cohort-wide question, not a service-specific one (§9).

## 7. Error Semantics (consolidated)

**Zero new exception classes, zero new handlers.** Every refusal above renders through machinery that already exists — this is the payoff of the persona-shape surface:

| Condition | HTTP | Body shape | Mechanism |
|-----------|------|------------|-----------|
| Body shape / unknown key / missing required key | 422 | envelope, `code: request_validation_error` per error | existing `request_validation_handler` |
| Every §6 rule except transitions | 422 | envelope, `errors: [{code, field, message}]` with the §6 codes | `UnprocessableError([FieldError(...)])` through `access_layer_handler` |
| Disallowed status transition | 422 | flat `{"error": "invalid_status_transition", "from": ..., "to": ...}` | existing `StatusTransitionError` + handler |
| Unknown identifier | 404 | envelope | `NotFoundError("service", id)` |
| Explicit identifier collision / assigner exhaustion | 409 | envelope | `ConflictError` |
| RBAC (when enforcement on) | 403 | envelope | existing `permission_denied_handler` |

Contrast with WTK-105, which minted one flat shape (`duplicate_mapping_for_candidate`) for its single-cause domain conflict: a service name collision is garden-variety field validation with no record-finding recovery story beyond the message, so it stays in the envelope as `{code: "duplicate", field: "service_name"}` — the live persona shape.

## 8. Acceptance Checks (per endpoint)

Verification criteria for the implementing Work Task: contract tests at `tests/crmbuilder_v2/api/test_services_api.py` over the live-app `client` fixture (`tests/crmbuilder_v2/api/conftest.py` — TestClient with the default `X-Engagement: ENG-001` header), following `test_personas_api.py` / `test_migration_mappings_api.py` in structure. WTK-132 §5.2–5.3 cover the storage and migration semantics beneath these; this list is the wire layer.

**E1 — list.**
- A1. Empty engagement → 200 `data: []`.
- A2. Seeded fixture (the four SES-166 services at `confirmed` plus one `candidate` and one `deferred`): unfiltered list returns all six ordered by identifier.
- A3. `?status=confirmed` returns exactly the four (Q1); `?status=candidate` / `?status=deferred` partition the rest; `?status=bogus` → 422 `invalid_filter`.
- A4. Soft-delete one service: it vanishes from the default list, appears with `?include_deleted=true` carrying `service_deleted_at`.
- A5. A second engagement's services never appear (`X-Engagement` swap test; the standard cross-engagement leak pattern).

**E2 — next-identifier.**
- B1. Fresh engagement → `SVC-001`; after two creates → `SVC-003`; agrees with what the next identifier-omitted POST assigns; a soft-deleted `SVC-002` still advances it to `SVC-003` (no reuse).

**E3 — get.**
- C1. 200 round-trips every column byte-identically POST → GET, including multi-line `service_capabilities`.
- C2. Unknown → 404 envelope; soft-deleted → 404 without flag, 200 with `?include_deleted=true`.

**E4 — create.**
- D1. Minimal body (`name` + `purpose`) → 201 at `candidate` with a server-assigned identifier; change-log `insert` row emitted.
- D2. Full body with explicit `service_status: "confirmed"` and explicit free identifier → 201 (the SES-166 backfill shape).
- D3. Each validation step refuses with its documented status + shape: empty/whitespace `service_name` and `service_purpose` (`missing_or_empty`), bad status value (`invalid_value`), explicit `rejected` (`invalid_starter_status`), case-folded name collision (`duplicate` — assert `"NOTIFICATIONS"` vs `"Notifications"`), malformed explicit identifier (422 `invalid_format`) vs colliding (409).
- D4. Ordering: a body with an empty name AND a bad status fails on the name (first-failure determinism, steps 2 < 4).
- D5. Unknown body key → 422 `request_validation_error` (`extra="forbid"`); same for a `rejected_by_decision` key on POST (not in `ServiceCreateIn`).
- D6. Any refusal leaves zero rows (orphan probe).
- D7. A name colliding only with a soft-deleted service succeeds (live-rows-only uniqueness).

**E5 — replace.**
- F1. Full replace round-trips; omitted-from-body is impossible (all keys stated); `service_capabilities: null` clears.
- F2. Body identifier mismatching the path → 422 `path_mismatch`; matching → 200.
- F3. Missing `service_status` → 422 boundary refusal (required on PUT).
- F4. Status change via PUT is transition-validated (flat shape on refusal); `rejected_by_decision` in the PUT body → 422 boundary refusal (not in `ServiceReplaceIn`).
- F5. Renaming onto another live service's name (case-folded) → 422 `duplicate`; renaming onto its own name with different case succeeds.

**E6 — patch.**
- G1. Explicit `service_notes: null` clears; omitted leaves unchanged (`exclude_unset`).
- G2. `candidate → confirmed` succeeds; `confirmed → candidate` → flat `invalid_status_transition`; `confirmed → rejected` → flat refusal (two-step demotion rule); no-op (`confirmed → confirmed`) succeeds.
- G3. `candidate → rejected` with `rejected_by_decision: "DEC-NNN"` flips and creates the edge atomically (probe the refs row); with an unknown decision → 422 `decision_not_found`, no flip, no edge; without the key and without a pre-existing edge → 422 `rejected_requires_decision_edge`.
- G4. Edge-first then keyless PATCH succeeds (both WTK-088 admission paths).
- G5. `rejected_by_decision` on a `confirmed` service without a status change → 422 `invalid_usage`; on an already-`rejected` service → second edge attached.
- G6. `service_identifier` in the PATCH body → 422 boundary refusal.

**E7 — delete.**
- H1. DELETE soft-deletes; repeat DELETE → 200 idempotent, timestamps unchanged.
- H2. Inbound `process_consumes_service` and outbound `service_owns_entity` refs survive the delete untouched (edge probe — the repository never touches `refs`).

**E8 — restore.**
- I1. Restore after H1 round-trips to the pre-delete state, status included.
- I2. Restore of a live service → 422 `not_deleted`; unknown → 404.
- I3. A `rejected` service deleted and restored comes back at `rejected`, still edge-backed.

**Edge management (the §5 contracts).**
- K1. `POST /references` attaches `process_consumes_service` (process → service) and `service_owns_entity` (service → entity); reversed direction for either kind → 422 (vocab pair rule).
- K2. Any service/domain pairing → 422 (`service_scopes_to_domain` does not exist).
- K3. Duplicate `(source, target, kind)` tuple → refused (refs uniqueness).
- K4. The §5.2 reads return the attached edges (Q2 by `target_id`, Q4 by `source_id`, Q5 by `source_id` + kind).
- K5. Deleting the `rejected_by_decision` edge of a service at `rejected` → 422 `rejected_edge_locked`; after the service is restored-then-still-rejected the lock holds; deleting a consumption edge succeeds at any status.

**Cross-cutting.**
- L1. Change-log rows emitted for create/update/delete/restore under entity type `service` on a *migrated* (non-create_all) DB — the `ck_changelog_entity_type` rebuild regression (`service.md` §5.2 item 6; the 0034 gotcha).
- L2. Both endpoints reachable through the live router order (`next-identifier` not captured by `/{identifier}`).
- L3. The SES-166 backfill drive: the four §6 POSTs from `service.md` (explicit `confirmed`, provenance in `service_notes`) succeed in sequence, `GET /services?status=confirmed` then returns exactly the four (acceptance criterion 5 of WTK-132).
- L4. Engagement stamping: a created service carries the request engagement's `engagement_id`; the A5 swap test covers read isolation.

## 9. Open Questions and Follow-ons

**[build] Cohort `invalid_starter_status` + `rejected_by_decision` REST retrofit.** §4.5.1 refuses birth-at-`rejected` and §4.7 exposes the atomic admission key — both for `service` (and already for `migration_mapping`), neither for the seven older types. Retrofitting the cohort is a small dedicated Work Task (one schema line + one create-guard per type, plus tests); out of scope here, flagged in WTK-105 §8 already for the key half.

**[build] Restore-time name re-check.** §6's documented corner (restore into a duplicate-name state) is live persona behavior; if it is ever tightened, tighten the cohort together.

**[v-next] Q3 as a derived read.** A `/services/{id}/domain-coverage` (or a `coverage` block on the record) becomes worth building when a phase-close gate consumes it; today it is a two-call client composition (§5.2).

**[v-next] Pagination.** With the cohort, on real-use signal.

**[follow-on] MCP tools + UI panel.** The per-entity MCP tool set mirrors E1–E8 reusing the repository functions directly; the Qt panel per `service.md` §3.6. Both follow the storage/API build per the recent-entity norm.

## 10. Build Surface (for the implementing Work Task)

- **`api/schemas.py`:** `ServiceCreateIn` / `ServiceReplaceIn` / `ServicePatchIn` on `_Base`, per §4.5–4.7 — the `Persona*In` trio shape with `purpose`/`capabilities` in place of `role_summary`/`responsibilities`; `ServicePatchIn` additionally carries `rejected_by_decision: str | None`; `ServiceReplaceIn` requires `service_status`.
- **`api/routers/services.py`:** the eight routes per §3, `next-identifier` before `/{identifier}`, delegating to the repository; module docstring states the decomposed-reference and no-evidence-param design per the `persona.py` docstring idiom; `_FIELD_PREFIX = "service_"` with the unprefixed `rejected_by_decision` passing through the strip untouched (the `migration_mappings.py` comment idiom).
- **`api/main.py`:** import + `app.include_router(services.router)` after `migration_mappings` in the methodology block. No handler registrations (§7).
- **`access/repositories/service.py`:** mirror `repositories/persona.py` function-for-function (`list_services`, `get_service`, `create_service`, `update_service`, `patch_service`, `delete_service`, `restore_service`, `next_service_identifier`) with the §4.5 starter-status guard and the §4.2 `status` list filter added; `_PATCHABLE_FIELDS = {"name", "purpose", "capabilities", "notes", "status"}`.
- **`access/repositories/_rejection.py`:** add `"service": (Service, "service_identifier", "service_status")` to `_REJECTABLE_SOURCES` — this alone activates the §5.1 delete guard and both admission paths.
- **Vocab/models/migrations:** per WTK-132 §10 (owned by the storage build task, not re-specified here).
- **Tests:** `tests/crmbuilder_v2/api/test_services_api.py` per §8 over the `client` fixture; the §8 edge-management group may live there or extend `test_references.py`, implementer's choice.
- **MCP (follow-on):** per §9.

---

*End of document.*

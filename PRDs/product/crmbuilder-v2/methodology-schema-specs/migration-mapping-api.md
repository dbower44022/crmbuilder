# Methodology API Spec — Migration Mapping V2 API

**Last Updated:** 06-12-26
**Status:** Draft v1.0 — produced under WTK-105 (api-area spec deliverable for the Phase 3 migration-mapping API surface)
**Position in workstream:** API companion to `migration_mapping.md` (WTK-104), which defines the `migration_mapping` record type, its two-edge linkage model, and the closed transform-rule vocabulary. That spec's §3.5 sketches the endpoint set; this spec is the full API design: per-endpoint request/response contracts, the validation sequence (reference validity, transform-rule well-formedness), the error-semantics assignment against the live handler taxonomy in `api/errors.py`, the REST surface for the Master PRD v0.2 §8 completeness rule ("a keep/transform without a recorded mapping is incomplete triage"), and per-endpoint acceptance checks. Where the two documents state the same rule, WTK-104 owns the *storage* semantics and this spec owns the *wire* semantics; on endpoint shapes this spec supersedes the §3.5 sketch.
**Companion documents:** `migration_mapping.md` (WTK-104 — schema, §4 rule model, §5 invariants I1–I12 and queries Q1–Q6, §6 compile contract); `field.md` §3.5 (the atomic-mandatory-edge POST precedent, DEC-249/250); `candidate-lifecycle-rejected-and-utilization-evidence.md` (WTK-088 — the `rejected_by_decision` admission paths now live in `access/repositories/_rejection.py`); `specifications/master-crmbuilder-PRD.md` §8 (the triage completion criteria the checks endpoints serve).

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 06-12-26 | ADO Area Specialist (api) / Claude | Initial draft under WTK-105. Full contracts for the eight standard endpoints plus two derived check endpoints (`/triage-completeness`, the PRD §8 completion gate; `/compile-preflight`, the Q5/Q6 gate). Always-embedded `migration_mapping_links` block on reads (batch-assembled, not N+1). POST validation sequence with deterministic first-error ordering. Error assignment: existing `status_transition_handler` for transitions; one new dedicated flat-shape handler (`duplicate_mapping_for_candidate`); everything else `UnprocessableError` through the standard envelope. Settles the API half of WTK-104's rule-schema open question: repository-layer validation authoritative, pydantic boundary structurally loose. Exposes `rejected_by_decision` in the PATCH body (a deliberate REST-surface extension over the field cohort, which today admits rejection edge-first only). |

---

## Change Log

**Version 1.0 (06-12-26):** Initial creation. Spec only — no code ships with this document; §9 enumerates the build surface for the implementing Work Task.

---

## 1. Purpose and Position

Master CRMBuilder PRD v0.2 §8 requires that every *keep* and *transform* disposition record a migration mapping at triage time, and makes the rule hard: *"A keep/transform without a recorded mapping is incomplete triage."* Its Completion Criteria repeat it as a Phase 3 close gate ("Every keep and transform has a migration mapping recorded"). WTK-104 designed the record type; this spec designs the REST surface consultants and agents actually author against during a live triage session, and the derived read that makes the completeness rule *checkable from the API* rather than only from SQL sketched in a spec.

Authoring context shapes the design: triage produces mappings in batches (CBM-scale: 100+), live with the stakeholder, via REST/MCP rather than the desktop dialogs (WTK-104 §3.6.4). The API must therefore (a) make each create atomic and self-contained (row + both mandatory edges in one POST), (b) fail loudly and specifically — every refusal names a code the authoring agent can act on, and (c) expose the completion and compile gates as zero-row-style checks callable at any point mid-session.

## 2. Conventions Inherited (verified against source)

The surface follows the live methodology-entity cohort exactly; the facts below were verified against the code, not assumed:

- **Envelope.** Success bodies are `ok(payload)` → `{"data": ..., "meta": {}, "errors": null}`; error bodies are `err([...])` → `{"data": null, "meta": {}, "errors": [...]}` (`api/envelope.py`). Two exception families bypass the envelope with dedicated flat shapes via per-class handlers registered before the generic `AccessLayerError` handler in `api/main.py` (`status_transition_handler`, `invalid_domain_reference_handler`, `selected_candidate_conflict_handler`, …).
- **Error taxonomy.** Access-layer exceptions carry `http_status` class attributes (`ValidationError` 400, `UnprocessableError` 422, `NotFoundError` 404, `ConflictError` 409); `access_layer_handler` honours them and renders `ValidationError` subclasses as `errors: [{code, field, message}]` lists (`api/errors.py`, `access/exceptions.py`). FastAPI body-shape failures render as 422 `request_validation_error` envelopes via `request_validation_handler`.
- **Pydantic boundary.** All bodies subclass `_Base` (`model_config = ConfigDict(extra="forbid")`) in `api/schemas.py`; unknown keys are 422 at the boundary. Body keys are parent-prefixed (`migration_mapping_*`); repository kwargs are unprefixed; PATCH routers strip the prefix from `model_dump(exclude_unset=True)` so explicit-null (clear) is distinct from omitted (unchanged) — the `field.py` router pattern.
- **Sessions and scoping.** Reads use `readonly_session()`, writes `writable_session()` (`api/deps.py`). Every request is engagement-scoped by the `X-Engagement` header through `scope_middleware`; `migration_mappings` is `EngagementScopedMixin`, so all reads filter and all writes stamp `engagement_id` without endpoint-level code.
- **Identifier handling.** `migration_mapping_identifier` is optional on POST, server-assigned via the SAVEPOINT-retry helper (PI-002); `GET /migration-mappings/next-identifier` per DEC-043. Static routes are declared **before** `/{identifier}` in the router — the `next_identifier` ordering already load-bearing in `field.py`; the two check endpoints in §4.9–4.10 ride the same rule.
- **Status transitions.** Disallowed transitions raise `StatusTransitionError` and render through the existing `status_transition_handler` flat shape; no new code is needed for that path. The `rejected` terminal uses the shared `_rejection.py` enforcement (edge-first or atomic key; see §4.6).

**No pagination in v1.** Cohort list endpoints (`/fields`, `/entities`, …) are unbounded; mappings are bounded by triage scale (low hundreds). Parity is kept; `limit`/`offset` is deferred to real-use signal, as it was for the cohort (and as WTK-060 did for `/references/touching`).

## 3. Endpoint Inventory

| # | Method | Path | Purpose | Success |
|---|--------|------|---------|---------|
| E1 | GET | `/migration-mappings` | List, with triage/compile filters | 200 |
| E2 | GET | `/migration-mappings/next-identifier` | Next `MIG-NNN` (DEC-043) | 200 |
| E3 | GET | `/migration-mappings/triage-completeness` | PRD §8 completion gate (Q1) | 200 |
| E4 | GET | `/migration-mappings/compile-preflight` | Merge coherence + entity context (Q5, Q6) | 200 |
| E5 | GET | `/migration-mappings/{identifier}` | Single fetch | 200 |
| E6 | POST | `/migration-mappings` | Atomic create: row + both mandatory edges | 201 |
| E7 | PUT | `/migration-mappings/{identifier}` | Full replace (no edge keys) | 200 |
| E8 | PATCH | `/migration-mappings/{identifier}` | Partial update, status transitions | 200 |
| E9 | DELETE | `/migration-mappings/{identifier}` | Soft-delete row + both edges atomically | 200 |
| E10 | POST | `/migration-mappings/{identifier}/restore` | Restore row + both edges atomically | 200 |

Router: `api/routers/migration_mappings.py`, `APIRouter(prefix="/migration-mappings", tags=["migration-mappings"])`, registered in `api/main.py` after `utilization_evidence` in the methodology block. E2–E4 are declared before E5.

## 4. Per-Endpoint Contracts

### 4.1 The record shape on the wire (all reads and write responses)

Every endpoint that returns a mapping returns the full column set (the repository `to_dict`) **plus an always-embedded, read-only `migration_mapping_links` block** derived from the two mandatory edges:

```json
{
  "migration_mapping_identifier": "MIG-007",
  "migration_mapping_level": "field",
  "migration_mapping_disposition": "transform",
  "migration_mapping_source_system_label": "espocrm @ crm.cbmentors.org",
  "migration_mapping_source_entity_name": "Contact",
  "migration_mapping_source_attribute_name": "cContactType",
  "migration_mapping_transform_rules": [
    {"rule_kind": "enum_value_map",
     "value_map": {"Mentor Candidate": "candidate", "Active Mentor": "active"},
     "unmapped_policy": "error"}
  ],
  "migration_mapping_notes": null,
  "migration_mapping_status": "confirmed",
  "migration_mapping_created_at": "2026-06-12T14:03:11+00:00",
  "migration_mapping_updated_at": "2026-06-12T14:03:11+00:00",
  "migration_mapping_deleted_at": null,
  "engagement_id": "ENG-001",
  "migration_mapping_links": {
    "migrates_from": {"identifier": "FLD-041", "entity_type": "field", "name": "Contact Type", "status": "rejected"},
    "migrates_to": [{"identifier": "FLD-118", "entity_type": "field", "name": "Mentor Stage", "status": "confirmed"}]
  }
}
```

**Why embedded and not opt-in.** The cohort's `include_evidence` opt-in (`utilization_evidence.embed_inline_evidence`) covers *auxiliary* data; the two edges here are *constitutive* — a mapping is unreadable without its source/target (the record has no name column; the source → target pair is its label, WTK-104 §3.2.1). Every consumer (triage UI master pane, the migration worksheet Q2, merge-group assembly) needs them on every row. The block is assembled **batched** — one edge query plus one summary query per *request*, keyed by the page's mapping identifiers — not one per row; the WTK-060 spec documented `list_touching`'s per-edge N+1 as a defect, and this surface must not reproduce it. Summary fields per edge target reuse `access/entity_summary.summarize`'s column map (identifier, type, title/name, status).

`migration_mapping_links` is response-only: supplying it in any write body is refused by `extra="forbid"`.

### 4.2 E1 — `GET /migration-mappings`

Query parameters (all optional, combinable, validated):

| Param | Values | Semantics |
|-------|--------|-----------|
| `level` | `entity` \| `field` | Filter on `migration_mapping_level`. Other values → 422 `invalid_filter` (envelope). |
| `source_identifier` | `ENT-NNN` \| `FLD-NNN` | Mappings whose live `migrates_from_record` edge targets the named candidate — the disposition lookup. At most one live row by I3. |
| `target_identifier` | `ENT-NNN` \| `FLD-NNN` | Mappings with a live `migrates_to_record` edge to the named record — merge-group assembly reads this. |
| `include_deleted` | `true` | Include soft-deleted rows (their `links` block resolves through soft-deleted edges). Default excludes. |

Response: 200, `data` = list of §4.1 records ordered by `migration_mapping_identifier` ascending. Unknown query params are ignored (FastAPI default), matching the cohort.

### 4.3 E2 — `GET /migration-mappings/next-identifier`

200, `data` = `{"next": "MIG-NNN"}`. Read-only; concurrent POST safety comes from the SAVEPOINT-retry assigner, not from this read (DEC-043 posture).

### 4.4 E3 — `GET /migration-mappings/triage-completeness`

The REST form of WTK-104 Q1 and the PRD §8 rule: **every keep and transform must have a recorded mapping; this endpoint lists the ones that don't.** Phase 3 may not close while `complete` is false.

```json
{
  "data": {
    "complete": false,
    "unmapped": [
      {"identifier": "FLD-093", "entity_type": "field", "name": "Referral Source",
       "disposition": "keep", "detail": "confirmed baseline candidate with no live mapping"},
      {"identifier": "ENT-014", "entity_type": "entity", "name": "Workshop",
       "disposition": "transform", "detail": "rejected baseline candidate superseded by ENT-031 with no live mapping"}
    ],
    "counts": {"keep_unmapped": 1, "transform_unmapped": 1, "mapped": 41}
  },
  "meta": {}, "errors": null
}
```

Semantics (exactly Q1's two arms, both levels):

- A **keep** awaiting a mapping is a live *baseline* candidate (deposited by an audit — has an inbound `deposit_event_wrote_record` edge) at `confirmed` with no live inbound `migrates_from_record` edge from a live, non-rejected mapping.
- A **transform** awaiting a mapping is a baseline candidate at `rejected` that is the target of a live variant/supersession edge (`entity_variant_of_entity` at entity level, same-type `supersedes` at field level) with no live inbound `migrates_from_record` edge.
- Candidates with no disposition yet (still `candidate`) and drops (rejected *without* a supersession edge) do not appear — they are not migration obligations; the former are Phase 3's general no-candidate-left rule, the latter need a Decision, not a mapping.

`complete` is `unmapped == []`. Optional `?level=entity|field` narrows the sweep (domain-batch triage checks one level mid-session). This is a read — it never blocks writes; *enforcement* of the rule is process-level (the Phase 3 close and the compiler both require zero rows), deliberately not write-level, because mappings and dispositions are recorded in either order within a session (WTK-104 I8).

### 4.5 E4 — `GET /migration-mappings/compile-preflight`

The REST form of Q5 + Q6, the gates the compiler runs before emitting batches (WTK-104 §6.2). Two sections, both must be empty for `ready: true`:

```json
{
  "data": {
    "ready": false,
    "incoherent_merge_groups": [
      {"merge_group": "contact-full-name",
       "mappings": ["MIG-011", "MIG-012"],
       "problems": ["distinct_targets", "duplicate_merge_order"]}
    ],
    "fields_without_entity_context": [
      {"mapping": "MIG-019", "source_field": "FLD-041", "source_entity": "ENT-002",
       "problem": "no confirmed entity-level mapping migrates from ENT-002"}
    ]
  },
  "meta": {}, "errors": null
}
```

- `incoherent_merge_groups`: per `merge_group` across live **confirmed** mappings — more than one distinct target record, more than one distinct `combinator`/`separator`, or non-distinct `merge_order` (I10). `problems` uses the closed vocabulary `{distinct_targets, distinct_combinators, distinct_separators, duplicate_merge_order}`.
- `fields_without_entity_context`: confirmed field-level mappings whose source field's parent entity (via `field_belongs_to_entity`) is not the source of a confirmed entity-level mapping, or whose target field's parent is not that entity-level mapping's target (Q6, the derived grouping of WTK-104 §3.3.3).

Triage-completeness (E3) is deliberately *not* folded in: E3 gates Phase 3 close, E4 gates compile, and the compiler's full pre-flight is E3 ∧ E4 — two calls, two independently meaningful results.

### 4.6 E5 — `GET /migration-mappings/{identifier}`

200 with the §4.1 record. `?include_deleted=true` admits a soft-deleted row. Unknown or (without the flag) soft-deleted identifier → 404 via `NotFoundError("migration_mapping", identifier)`, standard envelope.

### 4.7 E6 — `POST /migration-mappings`

The atomic create — row, one `migrates_from_record` edge, ≥1 `migrates_to_record` edges, and the change-log emit in **one transaction** (the `field_belongs_to_entity` DEC-249/250 pattern extended to a two-kind edge set). Body (`MigrationMappingCreateIn`):

| Key | Type | Required | Notes |
|-----|------|----------|-------|
| `migration_mapping_level` | str | yes | `entity` \| `field` |
| `migration_mapping_disposition` | str | yes | `keep` \| `transform` |
| `migration_mapping_source_system_label` | str | yes | non-empty trimmed |
| `migration_mapping_source_entity_name` | str | yes | non-empty trimmed |
| `migration_mapping_source_attribute_name` | str \| null | conditional | required iff `level = field`, must be absent/null at `entity` (I11) |
| `migration_mapping_transform_rules` | list \| null | no | rule objects per WTK-104 §4; must be empty/null for `keep` |
| `migration_mapping_notes` | str \| null | no | — |
| `migration_mapping_status` | str \| null | no | server default `candidate`; explicit `confirmed` permitted (live-triage posture, WTK-104 §3.2.3); explicit `rejected` refused as a starter |
| `migration_mapping_identifier` | str \| null | no | server-assigned when omitted; explicit must match `^MIG-\d{3}$` (422) and not collide (409) |
| `migration_mapping_migrates_from_identifier` | str | yes | the disposed baseline candidate (`ENT-NNN`/`FLD-NNN`) |
| `migration_mapping_migrates_to_identifiers` | list[str] | yes | ≥1 confirmed target record(s) |

**Validation sequence (deterministic; first failure wins, tests assert the order):**

1. Boundary: body shape, unknown keys (`extra="forbid"`), missing required keys → 422 `request_validation_error` envelope.
2. Scalar domain: `level`, `disposition`, `status` enum membership; non-empty trimmed strings; identifier format → 422 envelope (codes `invalid_level`, `invalid_disposition`, `invalid_status`, `nonempty_required`, `invalid_identifier_format`).
3. I11 agreement: `source_attribute_name` presence ⇔ `level = field` → 422 `attribute_name_level_mismatch`.
4. Rule-list well-formedness (§5.2) → 422 `invalid_transform_rule`, `field` = `migration_mapping_transform_rules[<index>]`.
5. Source edge: key present and non-null (`missing_source_candidate`); target exists, live, type = `level`, baseline candidate of a data-bearing type (`invalid_source_candidate`, message states which condition failed).
6. Source uniqueness (I3): candidate already sourced by a live mapping → 422 **flat shape** `{"error": "duplicate_mapping_for_candidate", "candidate_identifier": "FLD-041", "existing_mapping": "MIG-007"}` (§6).
7. Target edges: list non-empty (`missing_target_record`); each exists, live, type = `level`, status `confirmed` (`invalid_target_record`, message names the offending identifier and condition); no duplicate identifiers in the list.
8. Shape coupling: `keep` ⇒ exactly one target ∧ target = source ∧ rules empty (`invalid_keep_shape`); `transform` ⇒ source ∉ targets (`invalid_transform_shape`); >1 target ⇒ a `split` rule whose `assignments` target set equals the target list exactly (`split_rule_required` when absent; `invalid_transform_rule` when mismatched).
9. Identifier assignment (SAVEPOINT-retry) or explicit-identifier collision → 409 `ConflictError`.

Success: 201, `data` = the §4.1 record with both edges resolved in `migration_mapping_links`. A failure at any step leaves no orphan row or edge (single transaction; the PI-153-era transaction-control posture).

### 4.8 E7 — `PUT /migration-mappings/{identifier}`

Full replace of the §4.7 scalar columns (same table minus the two edge keys; `migration_mapping_identifier` optional-but-must-match if supplied). **Does not accept** `migrates_from_identifier`/`migrates_to_identifiers` — re-pointing is explicit reference management via `/references` (normally: soft-delete the mapping and re-create), per the cohort's PUT posture (`field.md` §3.5.4). Validation steps 2–4 and the *shape* half of step 8 re-run against the record's **existing** edges (e.g., replacing rules with a list that drops the `split` rule while two target edges live → 422 `split_rule_required`). Status changes are transition-validated (§4.9-style); 404 on unknown identifier.

### 4.9 E8 — `PATCH /migration-mappings/{identifier}`

Partial update; `model_dump(exclude_unset=True)`, prefix-stripped, forwarded to the repository. Patchable: `source_system_label`, `source_entity_name`, `source_attribute_name`, `transform_rules`, `notes`, `status`, plus the **unprefixed** `rejected_by_decision` admission key. Not patchable: `level`, `disposition` (constitutive — a level or disposition change is a different mapping; re-create), edge keys. Unknown keys → boundary 422.

Status semantics:

- Transitions validated against the standard four-status table; refusal renders through the **existing** `status_transition_handler`: 422 `{"error": "invalid_status_transition", "from": ..., "to": ...}`.
- `→ rejected` requires the WTK-088 admission: either the `rejected_by_decision: "DEC-NNN"` key in the same PATCH (atomic edge + flip via `_rejection.enforce_rejected_status`) or a pre-existing live `rejected_by_decision` edge. `migration_mapping` joins `_rejection._REJECTABLE_SOURCES`.
- **Cohort deviation, deliberate:** the live field/entity cohort supports the atomic key in the repository but does **not** expose it in its `PatchIn` schemas (verified: no `rejected_by_decision` in `api/schemas.py`), so over REST those types are edge-first only. Mappings are authored API-first at triage speed; two calls where one is atomic is exactly the gap this entity will hit. `MigrationMappingPatchIn` therefore carries `rejected_by_decision: str | None`. Retrofitting the cohort schemas is noted as a follow-on (§8), not done here.

Cross-field checks re-run where touched: patching `transform_rules` re-validates §5.2 plus the split/keep coupling against existing edges; patching `source_attribute_name` re-checks I11.

### 4.10 E9 — `DELETE /migration-mappings/{identifier}`

Soft-delete: stamps `migration_mapping_deleted_at` and soft-deletes **both outgoing edges in the same transaction** (WTK-104 §3.3.1). Idempotent — deleting an already-deleted mapping is 200 with the unchanged record. 404 on unknown identifier. Soft-delete is the bookkeeping exit; governed withdrawal is `PATCH → rejected` (the WTK-088 three-exit distinction).

### 4.11 E10 — `POST /migration-mappings/{identifier}/restore`

Restores row + both edges atomically. 422 envelope `not_deleted` if the row is live; 422 envelope `restore_blocked` naming the blocked side (`{"code": "restore_blocked", "field": "migrates_to[FLD-118]", "message": ...}`) if any edge target is itself soft-deleted (`field.md` §3.4.6 pattern). Restore re-checks source uniqueness (I3): if the candidate acquired a new live mapping while this one was deleted, restore is refused with the `duplicate_mapping_for_candidate` flat shape.

## 5. Validation Rules (consolidated)

### 5.1 Reference validity (source/target entity-field references)

| Rule | Where enforced | Error |
|------|----------------|-------|
| Source key present, target list non-empty | repo, POST step 5/7 | `missing_source_candidate` / `missing_target_record` |
| Referenced records exist and are live | repo | `invalid_source_candidate` / `invalid_target_record` |
| Both sides' entity types equal `level` (I5) | repo | same codes, condition in message |
| Source is a *baseline* candidate (audit-deposited) of a data-bearing type (`entity`/`field` only — `persona`/`process`/`manual_config` unrepresentable by the vocab pair rules, I12) | repo + vocab | `invalid_source_candidate` |
| Targets at `confirmed` status (I4) | repo | `invalid_target_record` |
| One live mapping per candidate (I3) | repo, POST + restore | `duplicate_mapping_for_candidate` (flat) |
| No duplicate `(source, target, kind)` edge tuples | refs-table uniqueness | 409 |

### 5.2 Transform-rule well-formedness (I9)

**Location decision — settles the API half of WTK-104 §8's open question:** authoritative validation lives in the **repository layer** as a vocab-adjacent schema table (`MIGRATION_TRANSFORM_RULE_SCHEMAS` beside `MIGRATION_TRANSFORM_RULE_KINDS` in `access/vocab.py`-adjacent code), NOT as pydantic models on the API boundary. Reason: the MCP tools and any future access-layer caller (the compiler, backfills) must get identical enforcement, and the desktop dialogs validate client-side against the same published table; pydantic-only validation would gate just one of three doors. The boundary keeps `migration_mapping_transform_rules: list[dict] | None` structurally loose.

Checks per rule object, in list order, all rendered as 422 `invalid_transform_rule` with `field` = `migration_mapping_transform_rules[<index>]` and a message naming the violated key:

1. `rule_kind` ∈ `{type_change, enum_value_map, merge, split}`.
2. Required keys per kind present; unknown keys refused (mirror of `extra="forbid"`).
3. Kind admissible at the mapping's `level` (WTK-104 §4.6: `type_change`/`enum_value_map` field-only; entity-level `merge` only with `combinator = coalesce`; entity-level `split` only with `value_router` extractors + `unrouted_policy`).
4. Conditional couplings: `default_value` ⇔ `unmapped_policy = "default"`; `separator` ⇔ `combinator = "concat"`; `unrouted_policy` required at entity-level `split`; `to_type ≠ from_type`; both ∈ `FIELD_TYPES`; `merge_order` integer ≥ 1; `value_map` non-empty str→str.
5. Cross-rule-vs-edge coupling (split target set = edge target set; keep ⇒ no rules) per §4.7 step 8.

Cross-*mapping* coherence (merge groups, I10) is **not** a write-time gate — it spans rows authored in any order mid-session — and surfaces through E4.

### 5.3 The completeness rule (PRD §8)

*"A keep or transform disposition without a recorded mapping is incomplete triage."* This is a **state of the engagement, not of any one write**, so it is enforced as a gate, not a constraint: E3 (`/triage-completeness`) is its callable form; the Phase 3 Completion Criteria and the compiler's pre-flight both require `complete: true`. No write is ever refused for the engagement being incomplete — refusing dispositions until mappings exist (or vice versa) would force an authoring order the triage conversation doesn't follow (WTK-104 I8's deferred-state rationale).

## 6. Error Semantics (consolidated)

One new dedicated exception + handler; everything else reuses existing machinery.

| Condition | HTTP | Body shape | Mechanism |
|-----------|------|------------|-----------|
| Body shape / unknown key / missing required key | 422 | envelope, `code: request_validation_error` per error | existing `request_validation_handler` |
| Scalar domain, I11, rule well-formedness, missing/invalid source or target, keep/transform/split shape, `invalid_filter`, `not_deleted`, `restore_blocked` | 422 | envelope, `errors: [{code, field, message}]` with the §4–§5 codes | `UnprocessableError([FieldError(...)])` through `access_layer_handler` |
| Duplicate mapping for a candidate (I3) | 422 | **flat** `{"error": "duplicate_mapping_for_candidate", "candidate_identifier": ..., "existing_mapping": ...}` | new `DuplicateMappingForCandidateError(UnprocessableError-ranked, http_status=422)` + dedicated handler, registered before `AccessLayerError` (the `selected_candidate_conflict_handler` precedent) |
| Disallowed status transition | 422 | flat `{"error": "invalid_status_transition", "from": ..., "to": ...}` | existing `StatusTransitionError` + handler |
| `→ rejected` without admission | 422 | envelope, code `rejected_requires_decision` | shared `_rejection.py` (its existing error shape; not redefined here) |
| Unknown identifier | 404 | envelope | `NotFoundError("migration_mapping", id)` |
| Explicit identifier collision | 409 | envelope | `ConflictError` |
| RBAC (when enforcement on) | 403 | envelope | existing `permission_denied_handler` |

**Why exactly one flat shape.** WTK-104 §3.3.1 specifies the `duplicate_mapping_for_candidate` flat literal, and it matches the precedent class (a named, single-cause domain conflict like `selected_candidate_already_exists` — the caller's recovery is specific: find and resolve `existing_mapping`). The other seven POST refusals are garden-variety field validation; minting seven exception classes + handlers would bloat `errors.py` for no client benefit — the envelope's `{code, field, message}` already names them machine-readably. WTK-104's prose listed them as named 422s; the names survive as `code` values.

## 7. Acceptance Checks (per endpoint)

Verification criteria for the implementing Work Task; each is a test (or test group) over the live FastAPI app fixture. WTK-104 §7's criteria 4–12 cover the storage semantics beneath these; this list is the wire layer.

**E1 — list.**
- A1. Empty engagement → 200 `data: []`.
- A2. Seeded fixture (one keep, one rename-only transform, one enum-map transform, one two-mapping merge, one split — the WTK-104 §7.13 fixture): unfiltered list returns all six ordered by identifier; each row carries a `migration_mapping_links` block with resolved summaries.
- A3. `?level=field` / `?level=entity` partition the six correctly; `?level=bogus` → 422 `invalid_filter`.
- A4. `?source_identifier=` of a disposed candidate returns exactly its one live mapping; of an unmapped candidate → `[]`.
- A5. `?target_identifier=` of the merge target returns both merge-member mappings.
- A6. Soft-delete one mapping: it vanishes from the default list, appears with `?include_deleted=true` carrying `deleted_at` and links resolved through soft-deleted edges.
- A7. Query count for the list is constant in row count (batched links assembly — assert via SQLAlchemy statement counting, the N+1 guard).
- A8. A second engagement's mappings never appear (scoping; `X-Engagement` swap test).

**E2 — next-identifier.**
- B1. Fresh engagement → `MIG-001`; after two creates → `MIG-003`; agrees with what the next identifier-omitted POST assigns.

**E3 — triage-completeness.**
- C1. Fixture with one unmapped confirmed baseline field (keep) and one unmapped rejected+superseded baseline entity (transform): both listed with correct `disposition` and `detail`; `complete: false`; counts agree.
- C2. POST the two missing mappings → `complete: true`, `unmapped: []`.
- C3. An undisposed candidate (still `candidate`) and a drop (rejected, no supersession edge) never appear.
- C4. A mapping at `rejected` does not satisfy its candidate (the candidate reappears); a `deferred` mapping does satisfy it.
- C5. `?level=field` restricts the sweep to the field arm.
- C6. Non-baseline records (no `deposit_event_wrote_record` provenance — interview-born candidates) never appear at any status.

**E4 — compile-preflight.**
- D1. Coherent fixture → `ready: true`, both lists empty.
- D2. Two merge-member mappings patched to different targets → `incoherent_merge_groups` names the group, both members, `problems: ["distinct_targets"]`; duplicate `merge_order` adds its problem code.
- D3. A confirmed field-level mapping whose source entity has no confirmed entity-level mapping → listed in `fields_without_entity_context` with the parent-entity identifier; adding the entity-level mapping clears it.
- D4. Only **confirmed** mappings participate: setting a merge member to `deferred` removes the group from D2's incoherence (and surfaces nothing else).

**E5 — get.**
- E1t. 200 round-trips every column byte-identically POST → GET, including a four-kind rule list (WTK-104 §7.9's round-trip at the wire level); links block present.
- E2t. Unknown → 404 envelope; soft-deleted → 404 without flag, 200 with `?include_deleted=true`.

**E6 — create.**
- F1. The §4.7 happy path → 201; row + both edges + change-log emit visible; `migration_mapping_links` resolved in the response.
- F2. Each validation step refuses with its documented status + shape: missing source key (`missing_source_candidate`), entity-typed source on a field-level body (`invalid_source_candidate`), unconfirmed target (`invalid_target_record`), second mapping for a mapped candidate (flat `duplicate_mapping_for_candidate` with `existing_mapping`), two targets sans split (`split_rule_required`), keep with rules (`invalid_keep_shape`), transform with source ∈ targets (`invalid_transform_shape`), rule with unknown kind / missing key / wrong level / broken coupling (`invalid_transform_rule` naming the index), `source_attribute_name` on an entity-level body (`attribute_name_level_mismatch`), bad explicit identifier format (422) vs collision (409).
- F3. Ordering: a body violating both step 4 and step 6 fails with step 4's error (first-failure determinism).
- F4. Any refusal leaves zero rows and zero edges (orphan probe after each F2 case).
- F5. Explicit `migration_mapping_status: "confirmed"` accepted; explicit `"rejected"` refused as a starter.
- F6. Unknown body key → 422 `request_validation_error` (`extra="forbid"`).

**E7 — replace.**
- G1. Full replace of scalars round-trips; edges untouched.
- G2. Body containing either edge key → 422 boundary refusal.
- G3. Replacing a split mapping's rules with a list lacking the split rule → 422 `split_rule_required` (validated against existing edges).
- G4. Status change via PUT is transition-validated (flat shape on refusal).

**E8 — patch.**
- H1. Explicit `migration_mapping_notes: null` clears; omitted leaves unchanged (`exclude_unset`).
- H2. `level`/`disposition`/edge keys → 422 boundary refusal.
- H3. `candidate → confirmed` succeeds; `confirmed → candidate` → flat `invalid_status_transition`.
- H4. `→ rejected` with `rejected_by_decision: "DEC-NNN"` flips and creates the edge atomically; without the key and without a pre-existing edge → 422; edge-first then keyless PATCH succeeds (both WTK-088 admission paths).
- H5. Patching rules re-validates §5.2 and the edge coupling.
- H6. Patching `source_attribute_name` to null on a field-level mapping → 422 `attribute_name_level_mismatch`.

**E9 — delete.**
- I1t. DELETE soft-deletes row + both edges in one transaction (edge probe); repeat DELETE → 200 idempotent.
- I2t. The freed candidate accepts a new mapping (I3 released).

**E10 — restore.**
- J1. Restore after I1t brings back row + both edges; round-trip equals pre-delete state.
- J2. Restore of a live mapping → 422 `not_deleted`.
- J3. Restore with a soft-deleted edge target → 422 `restore_blocked` naming the side.
- J4. Restore after the candidate was re-mapped → flat `duplicate_mapping_for_candidate`.

**Cross-cutting.**
- K1. Change-log rows emitted for create/update/delete/restore under entity type `migration_mapping` on a *migrated* (non-create_all) DB — the CHECK-rebuild gotcha regression (WTK-104 §7.14).
- K2. All ten endpoints reachable through the live router order (static-before-dynamic: `next-identifier`, `triage-completeness`, `compile-preflight` are not captured by `/{identifier}`).
- K3. The WTK-104 §7.16 CBM-scale batch (≈20 mappings, both levels, all four kinds, authored in triage order) drives E3 from `complete: false` to `true` and E4 to `ready: true` with no write ever blocked by engagement-level incompleteness.

## 8. Open Questions and Follow-ons

**[build] Cohort `rejected_by_decision` REST exposure.** §4.9 exposes the atomic admission key for mappings; the seven existing rejectable types support it in the repository but not in their `PatchIn` schemas. Retrofitting them is a one-line-per-schema change plus tests — worth a small dedicated Work Task; out of scope here.

**[build] `?status=` / `?disposition=` list filters.** Deferred with the same real-use-signal posture as WTK-104 §3.5.5; E3/E4 already cover the known derived-read needs.

**[v-next] Worksheet export.** Q2 (the migration worksheet) is fully assemblable from E1 + links; a dedicated `/migration-mappings/worksheet` flattened read belongs to the compiler/report design, not this surface.

**[v-next] Pagination.** Revisit with the cohort when any engagement's mapping count makes unbounded lists hurt; the links batching (A7) keeps the constant-factor honest until then.

## 9. Build Surface (for the implementing Work Task)

- **`api/schemas.py`:** `MigrationMappingCreateIn` / `MigrationMappingReplaceIn` / `MigrationMappingPatchIn` on `_Base`, per §4.7–4.9 (PatchIn carries `rejected_by_decision: str | None`; rules typed `list[dict] | None`).
- **`api/routers/migration_mappings.py`:** the ten routes per §3, static routes first, delegating to the repository; module docstring states the embedded-links and two-gate design per the `field.py` docstring idiom.
- **`access/repositories/migration_mapping.py`:** CRUD + the two check reads (`triage_completeness(session, level=None)`, `compile_preflight(session)`) — callable forms of Q1/Q5/Q6 per WTK-104 §10, shared by API and any future compiler; batched links assembly helper.
- **`access/exceptions.py` + `api/errors.py` + `api/main.py`:** `DuplicateMappingForCandidateError` (carries `candidate_identifier`, `existing_mapping`) + its flat-shape handler, registered before the generic handler; router registration after `utilization_evidence`.
- **`access/_rejection.py`:** add `migration_mapping` to `_REJECTABLE_SOURCES`.
- **Vocab/models/migrations:** per WTK-104 §10 (owned by the storage build task, not re-specified here); the rule-schema table per §5.2 lands vocab-adjacent.
- **MCP (follow-on):** create/list/get/check tools mirroring E1/E3–E6, reusing the repository functions directly.

---

*End of document.*

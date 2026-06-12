# Methodology Entity Schema Spec — `migration_mapping`

**Last Updated:** 06-12-26
**Status:** Draft v1.0 — produced under WTK-104 (storage-area spec deliverable for the Phase 3 migration-mapping record type)
**Position in workstream:** Resolves the Master CRMBuilder PRD v0.2 §8 mechanics gap — "the migration-mapping record type does not yet exist in the V2 schema" — so the Phase 3 baseline-triage *keep* and *transform* dispositions have a storage target for the data-migration obligation they create, and so mappings can later compile into executable migration via the existing data-import machinery (`espo_impl/core/import_manager.py`). Sibling to the Phase 1.5 / Phase 3 design lineage: WTK-088 (`candidate-lifecycle-rejected-and-utilization-evidence.md`, which named this record type as its deferred §7 item), WTK-090 (audit → candidate deposit), WTK-096 (data profiling), WTK-102 (catalog normalizer).
**Companion documents:** `methodology-entity-schema-spec-guide.md` (template); `entity.md` and `field.md` (the two subject entity types mappings reference); `candidate-lifecycle-rejected-and-utilization-evidence.md` (the disposition lifecycle — `rejected` terminal + `rejected_by_decision` — this spec's disposition linkage builds on); `catalog-normalizer-type-mapping-and-partition.md` (the `FIELD_TYPES` vocabulary type-change rules are expressed in); `specifications/master-crmbuilder-PRD.md` §8 (Phase 3 baseline triage, "Migration Mapping").

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 06-12-26 | ADO Area Specialist (storage) / Claude | Initial draft under WTK-104. Defines `migration_mapping` (`MIG-NNN`) as the methodology record carrying one keep/transform disposition's data-migration obligation: exactly one mandatory `migration_mapping_migrates_from_record` edge to the disposed baseline candidate (uniqueness on the source side encodes "one mapping per disposition"; the disposition Decision is reached *through* the source candidate, never duplicated), one-or-more `migration_mapping_migrates_to_record` edges to the confirmed target record(s), two-level scope (`entity` / `field` — the two data-bearing capture types), a closed-vocabulary JSON transform-rule list (`type_change`, `enum_value_map`, `merge`, `split`) with explicit no-silent-behavior policies, denormalized literal source-system coordinates for compile determinism, and the compile contract against `ImportManager.check/execute`. Verification criteria: six example queries (including the Phase 3 completion check "every keep and transform has a mapping") and twelve invariants. |

---

## Change Log

**Version 1.0 (06-12-26):** Initial creation. No code, vocab, or migration changes ship with this document — it is the design the implementing Work Tasks build from. §6 (compile contract) defines what the schema must guarantee so a future compiler can mechanically produce import batches; §10 enumerates the build surface.

---

## 1. Purpose and Position

Master CRMBuilder PRD v0.2 §8, "Migration Mapping":

> Every *keep* and *transform* creates a data-migration obligation, recorded at triage time while the knowledge is fresh and the stakeholder is present: source entity/field → target entity/field, plus transform rules for transforms (type changes, value mappings for enums, merges, splits). These mappings are the input to migration planning and eventually compile into executable migration via the data-import machinery. A keep/transform without a recorded mapping is incomplete triage.

The PRD flags the mechanics gap explicitly: until the record type lands, mappings are captured in prose sections of triage deliverables and backfilled later. This spec closes the gap at the design level. It defines `migration_mapping` as a v2 methodology entity type following the per-entity template (`methodology-entity-schema-spec-guide.md`) and the conventions inherited across the workstream lineage (`domain.md` → … → `field.md` → the PI-004 cohort):

- **Parent-prefix field naming** (DEC-046): all columns prefixed `migration_mapping_`.
- **`{source}_{verb}_{target}` relationship-kind naming** (DEC-048), with the generic-`record` target word per the `deposit_event_wrote_record` precedent, because the target side spans two entity types.
- **Soft-3-letter identifier prefix posture** (DEC-044): `MIG`.
- **Four-status propose-verify lifecycle** (DEC-047 + the WTK-088 `rejected` terminal, now live in `vocab.py`).
- **Engagement scoping** (PI-123): `EngagementScopedMixin`, row-level `engagement_id`.

Two prior designs frame what this record must link to:

1. **The disposition machinery (WTK-088 §3.6).** A *keep* is the status transition `candidate → confirmed` on the baseline record itself. A *transform* is a new confirmed record in the target shape, a variant/supersession edge from the new record to the baseline candidate (`entity_variant_of_entity` for entities, the same-type `supersedes` kind for fields), and closure of the baseline candidate at `rejected` with a mandatory `rejected_by_decision` edge to the transform Decision. The disposition is therefore *not itself a record type* — it is an observable state of the baseline candidate. This spec's "link to the originating disposition" is the mandatory edge to that candidate (§3.3.1), and the schema's keep/transform invariants are stated against the candidate's observable state (§5.2).
2. **The evidence and normalization layers (WTK-088 §4, WTK-096, WTK-102).** Utilization evidence (declared vs. used enum options, population rates) is what makes enum value maps *checkable*: a recorded `enum_value_map` can be verified against the observed value distribution (§5.1, Q4).

The compile target is the existing data-import machinery: `ImportManager` in `espo_impl/core/import_manager.py`, whose `check()` consumes a list of source records plus a `field_mapping: {source_key: espo_field_name}` dict and `fixed_values`, plans per-record CREATE/UPDATE/SKIP actions, and whose `execute()` applies the plan. The compiler itself is future work (§10); this spec's job is to make the mapping records carry everything that compiler needs, deterministically (§6).

---

## 2. Summary

A `migration_mapping` record carries one Phase 3 keep/transform disposition's data-migration obligation: *records and values from this source entity/field land in that target entity/field, transformed by these rules.* Each kept or transformed baseline candidate — `entity` or `field`, the two data-bearing capture types — gets exactly one mapping, recorded at triage time while the stakeholder is present. A *keep* produces a `direct` mapping whose source and target are the same record (the baseline candidate, now confirmed in place); a *transform* produces a mapping from the now-rejected baseline candidate to the new confirmed record, carrying zero or more transform rules. Rules come from a closed four-kind vocabulary matching the PRD's named set — `type_change`, `enum_value_map`, `merge`, `split` — each with explicit policies for the unmapped/unparseable case so that nothing about the migration is decided silently at compile time. Merges (N source candidates → one target) are N mappings sharing a `merge_group`; splits (one source → N targets) are one mapping with multiple target edges and per-target extraction rules — both shapes preserve the one-mapping-per-disposition unit. The mapping denormalizes the literal source-system coordinates (system label, entity name, attribute name) at triage time so compilation does not depend on later renames of methodology records.

Dispositions on the three non-data capture types (`persona`, `process`, `manual_config`) create no migration mapping: roles, workflows, and manual-config items are configuration carried forward by deployment, not record data carried forward by import.

---

## 3. Schema Specification

### 3.1 Identity

| Field | Value |
|-------|-------|
| Entity type name (storage) | `migration_mapping` |
| Display name (singular) | Migration Mapping |
| Display name (plural) | Migration Mappings |
| Identifier prefix | `MIG` |
| Identifier format | `MIG-NNN`, zero-padded to 3 digits (e.g., `MIG-001`, `MIG-042`) |
| Identifier auto-assignment | Server-side on POST omission per PI-002; helper at `GET /migration-mappings/next-identifier` per DEC-043 |

`MIG` is three letters under the soft-3-letter posture (DEC-044), reads unambiguously as "migration", and does not collide with the existing prefix space (DEC, SES, RSK, PI, TOP, REF, CHR, STA, DOM, ENT, PROC, CRM, PRJ, WSK, WTK, CONV, CNV, RB, WT, COP, DEP, CM, FND, LRN, REL, AGP, SKL, GVR, FLD, PER, REQ, MCF, TST, TERM, ENG).

### 3.2 Fields

All columns carry the `migration_mapping_` parent prefix (DEC-046). The table is `migration_mappings`, engagement-scoped via `EngagementScopedMixin` (row-level `engagement_id`, PI-123).

#### 3.2.1 Identity fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `migration_mapping_identifier` | TEXT | yes | server-assigned | `^MIG-\d{3}$`, unique per engagement | The methodology-entity identifier. Server-assigned when omitted from POST body per PI-002. |

**No name field — documented deviation.** Mappings are dense, mechanical-leaning records (a CBM-scale triage produces one per kept/transformed candidate — easily 100+), authored in batches with the stakeholder present. A mandatory free-text name would add authoring friction with no retrieval value: the natural label *is* the source → target pair, which the UI derives from the edges (§3.6.2). This mirrors the spirit of WTK-088 §4.2 (mechanical rows are cited through their subjects), while the record itself remains a full methodology entity because consultants author, edit, and verify it.

#### 3.2.2 Content fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `migration_mapping_source_system_label` | TEXT | yes | — | non-empty trimmed | Human-readable source-system identity, e.g. `espocrm @ crm.cbmentors.org`. Matches the `evidence_source_label` convention (WTK-088 §4.3) so mappings and evidence join on the same string. Disambiguates multi-source clients (one Phase 1.5 deposit per source). |
| `migration_mapping_source_entity_name` | TEXT | yes | — | non-empty trimmed | The *literal* entity name in the source system at snapshot time (e.g. `CSession`, `Contact`). Denormalized deliberately: the compiler extracts data by source-system names, and the methodology candidate's client-language `entity_name`/`field_name` may be edited after triage. See §6.2. |
| `migration_mapping_source_attribute_name` | TEXT | conditional | — | non-empty trimmed when `migration_mapping_level = field`; MUST be NULL when `level = entity` | The literal field/column name in the source system (e.g. `cContactType`). Field-level mappings only. |
| `migration_mapping_transform_rules` | JSON | no | `null` | list of rule objects per §4 when set; MUST be NULL/empty when `migration_mapping_disposition = keep` | The transform-rule list. NULL or `[]` is valid for a rename-only transform (the shape change is visible in the source ≠ target edge pair; no value transformation is needed). `JSONColumnNoneAsNull` per the PI-α dialect aliases. |
| `migration_mapping_notes` | TEXT | no | — | — | Internal consultant scratchpad: stakeholder context behind a value map, ordering rationale for a merge, etc. Not consumed by the compiler. |

#### 3.2.3 Classification fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `migration_mapping_level` | TEXT | yes | — | enum: `entity` \| `field` | Mapping scope. `entity`: records of the source entity land in the target entity (the extraction context field-level mappings compile inside). `field`: values of the source field land in the target field. Must agree with the types of both edge targets (§3.3.1, invariant I5). |
| `migration_mapping_disposition` | TEXT | yes | — | enum: `keep` \| `transform` | The originating Phase 3 disposition. `keep` ⇒ direct mapping: source record and target record are the same methodology record, `transform_rules` empty. `transform` ⇒ source ≠ target. Must agree with the source candidate's observable disposition state (§5.2, I7/I8). *Drop* dispositions never produce a mapping. |
| `migration_mapping_status` | TEXT | yes | `candidate` | enum: `candidate` \| `confirmed` \| `deferred` \| `rejected`; transitions per §3.4 | Lifecycle status. Mappings recorded live at triage with the stakeholder present are legitimately POSTed at `confirmed` directly (explicit non-starter status on POST is permitted, per the `field.md` §3.5.3 precedent). |

#### 3.2.4 Relationship fields

None. `migration_mapping` has no FK columns on its table; both linkages (source candidate, target record) are references-entity edges per the references-first discipline (DEC-006, reaffirmed for mandatory edges by DEC-249). See §3.3.

#### 3.2.5 Timestamp fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `migration_mapping_created_at` | DATETIME | yes | server-set on insert | ISO 8601 UTC | Inherited base behavior. |
| `migration_mapping_updated_at` | DATETIME | yes | server-set on insert and update | ISO 8601 UTC | Inherited base behavior. |
| `migration_mapping_deleted_at` | DATETIME | no | null until soft-delete | ISO 8601 UTC when set | Inherited base behavior. |

No storage-level length caps, mirroring the cohort posture.

### 3.3 Relationships

#### 3.3.1 Outgoing relationships

`migration_mapping` declares two outgoing relationship kinds:

| relationship_kind | source | target | mechanism | cardinality | semantics |
|-------------------|--------|--------|-----------|-------------|-----------|
| `migration_mapping_migrates_from_record` | `migration_mapping` | `entity` \| `field` | references-entity edge | exactly 1 per live mapping; **at most 1 live inbound per candidate** | The baseline candidate whose keep/transform disposition this mapping records. This edge *is* the link to the originating disposition. |
| `migration_mapping_migrates_to_record` | `migration_mapping` | `entity` \| `field` | references-entity edge | ≥ 1 per live mapping; > 1 only with a `split` rule (§4.5) | The confirmed methodology record(s) the source's data lands in. For a `keep`, the single target is the same record as the source. |

Naming: both kinds follow `{source}_{verb}_{target}` (DEC-048) with the generic `record` target word, per the `deposit_event_wrote_record` precedent — the target side spans two entity types, so no single target name applies, and per-target-type kind pairs (`…_from_entity` / `…_from_field`) would say nothing the pair constraint doesn't already say.

**The disposition linkage — through the source candidate, never duplicated.** The "originating Phase 3 disposition" is an observable state of the source candidate, not a record (WTK-088 §3.6):

- *keep*: the candidate is at `confirmed`, and this mapping's source and target edges point at the same record.
- *transform*: the candidate is at `rejected` with a live `rejected_by_decision` edge to the transform Decision, and the target record carries a variant/supersession edge to it (`entity_variant_of_entity` at entity level; same-type `supersedes` at field level, new record → baseline candidate).

The disposition Decision is therefore reachable as `mapping → migrates_from_record → candidate → rejected_by_decision → DEC-NNN`. No `migration_mapping_disposed_by_decision` edge and no decision column are added: they would duplicate a path the graph already carries, the same reasoning WTK-088 §3.4 used to reject `*_rejected_at`/`*_rejected_by` columns. The `migration_mapping_disposition` enum is retained as a *declared* value precisely so the schema can verify declared-vs-observable agreement (I7/I8) — a disagreement is a triage bookkeeping error worth surfacing, which a derived-only value could not catch.

**"One mapping per disposition" — uniqueness on the source side.** A candidate receives exactly one terminal disposition (PRD §8), so it can be the `migrates_from_record` target of **at most one live mapping**. The access layer enforces this at edge creation: a POST that would give a candidate a second live inbound `migrates_from_record` edge is refused 422 (`{"error": "duplicate_mapping_for_candidate", "candidate_identifier": "..."}`). Re-doing a mapping means soft-deleting (bookkeeping error) or rejecting (changed decision) the old one first.

**Merges are N mappings, not one.** A merge (e.g., `first_name` + `last_name` → `full_name`) involves N source candidates, hence N dispositions, hence N mappings — each `migrates_from_record` its own candidate, all `migrates_to_record` the same target, each carrying a `merge` rule sharing one `merge_group` key (§4.4). The one-mapping-per-disposition unit is preserved; cross-mapping coherence is a verification concern (I10, Q5).

**Splits are one mapping.** A split (one source field → N target fields; one source entity routed into N target entities) is one disposition, hence one mapping, with N `migrates_to_record` edges and one `split` rule assigning an extractor per target (§4.5).

**Cardinality and validation:**

- Exactly one live `migrates_from_record` edge per live mapping — mandatory, created atomically with the row (§3.5.4), the `field_belongs_to_entity` enforcement pattern (DEC-249/250).
- At least one live `migrates_to_record` edge per live mapping — same atomic-POST treatment; more than one admitted only when `transform_rules` contains a `split` rule covering every target (I6).
- Edge-target entity types must both equal `migration_mapping_level` (I5).
- The `migrates_from_record` target must be live and a baseline candidate of a data-bearing type; the `migrates_to_record` target must be live and at `confirmed` status (a mapping into an unconfirmed shape is premature by construction — the disposition that creates the mapping also confirms the target).
- Duplicate `(source_id, target_id, relationship_kind)` tuples rejected by the references-table uniqueness constraint.

**Lifecycle semantics:**

- Soft-deleting a mapping soft-deletes both outgoing edges atomically; restore restores them. Restore when an edge's target record is itself soft-deleted returns 422 naming the blocked side, per the `field.md` §3.4.6 pattern.
- Soft-deleting or rejecting a methodology record does NOT cascade to mappings referencing it; the dangling state is surfaced by compile pre-flight (Q6) rather than hidden by cascade, consistent with the PI-059 leniency posture.

**Mechanical additions per the CLAUDE.md vocab triad:**

1. Both kinds added to `REFERENCE_RELATIONSHIPS` in `access/vocab.py`.
2. `_kinds_for_pair` extended: `(migration_mapping, entity)` and `(migration_mapping, field)` each admit both kinds.
3. Alembic migration rebuilding the `refs.relationship_kind` CHECK — and the `change_log` entity-type CHECK for the new `migration_mapping` entity type (the known live-DB gotcha).

#### 3.3.2 Inbound relationships (anticipated)

A future migration-compile run (§6, §10) will want provenance from its output artifact back to the mappings it compiled — the natural shape is `deposit_event_wrote_record`-style edges from a compile/import deposit event, or a `compiled_from` kind declared by the compiler's own spec. Not declared here; noted for forward awareness.

#### 3.3.3 Hierarchy

None. Field-level mappings are *grouped under* entity-level mappings at compile time, but the grouping is derivable (source field → `field_belongs_to_entity` → source entity → that entity's mapping) and is deliberately not stored — storing it would create a second source of truth that re-parenting or re-triage could silently desynchronize. Compile pre-flight resolves and checks the grouping (Q6).

### 3.4 Lifecycle

#### 3.4.1 Status values

| Status value | Description | Valid predecessors | Valid successors |
|--------------|-------------|--------------------|------------------|
| `candidate` | Drafted (e.g., consultant pre-work before the triage session). **Default starter status.** | (none — starter) | `confirmed`, `deferred`, `rejected` |
| `confirmed` | Stakeholder-verified at triage; eligible for compilation. | `candidate`, `deferred` | `deferred` |
| `deferred` | Acknowledged but out of current migration scope (e.g., the data migrates in a later wave). | `candidate`, `confirmed` | `confirmed`, `rejected` |
| `rejected` | Permanently withdrawn (truly terminal). Requires the atomic `rejected_by_decision` edge per WTK-088 §3.4. | `candidate`, `deferred` | (none) |

This is the standard four-status methodology lifecycle exactly as live in `vocab.py` post WTK-088/PI-153 — `migration_mapping` joins as the next status-bearing methodology type with no per-type variation. Mappings recorded live at triage POST directly at `confirmed` (§3.2.3).

#### 3.4.2 Transition semantics

The one-way propose-verify gate (DEC-047) carries forward unchanged: no status lists `candidate` as a successor. `confirmed ⇄ deferred` supports migration-wave re-scoping. Note the interplay with re-triage: if a stakeholder reverses a disposition (a kept field is later dropped), the existing mapping must be moved to `rejected` (with the reversing Decision) — invariant I7's agreement check makes a stale mapping on a re-disposed candidate visible rather than silent.

#### 3.4.3 Status independence

`migration_mapping_status` is independent of the source and target records' statuses, per the cohort posture (`field.md` §3.4.3) — with the caveat that the *disposition agreement* invariants (I7/I8) tie the mapping's validity (not its status) to the source candidate's state. A mapping does not auto-reject when its candidate's disposition is reversed; the verification queries surface the mismatch for a human to resolve.

#### 3.4.4 Soft-delete semantics

Standard v2 behavior, plus the atomic two-edge handling in §3.3.1. Soft-delete remains the bookkeeping path (mis-recorded mapping); `rejected` is the governed-withdrawal path (changed stakeholder decision), per the WTK-088 §3.5 three-exit distinction.

### 3.5 API Surface

#### 3.5.1 Endpoints

| Method | Path | Body | Notes |
|--------|------|------|-------|
| GET | `/migration-mappings` | — | List. `?include_deleted=true`; filters per §3.5.5. |
| GET | `/migration-mappings/{identifier}` | — | Single fetch; 404 if not found. |
| POST | `/migration-mappings` | full record minus identifier, PLUS `migration_mapping_migrates_from_identifier` (one) and `migration_mapping_migrates_to_identifiers` (list, ≥ 1) for atomic edge creation | Create. 201 with assigned identifier. See §3.5.4. |
| PUT | `/migration-mappings/{identifier}` | full record | Full replace. Does NOT accept the edge body keys — re-pointing is explicit edge management. |
| PATCH | `/migration-mappings/{identifier}` | partial record | Status-transition validation; `rejected` requires the atomic `rejected_by_decision` key or a pre-existing edge (WTK-088 §3.4). Does NOT accept the edge body keys. |
| DELETE | `/migration-mappings/{identifier}` | — | Soft-delete; both outgoing edges soft-deleted atomically. Idempotent. |
| POST | `/migration-mappings/{identifier}/restore` | — | Restores row + both edges atomically; 422 if not soft-deleted or if an edge target is itself soft-deleted. |
| GET | `/migration-mappings/next-identifier` | — | `{"next": "MIG-NNN"}` per DEC-043. |

Standard `{data, meta, errors}` envelope throughout.

#### 3.5.2 Identifier auto-assignment

Server-assigned on POST omission per PI-002, via the SAVEPOINT-retry helper.

#### 3.5.3 Status-transition validation

Standard 422 `invalid_status_transition` shape; `rejected` transitions follow the WTK-088 atomic edge-or-pre-existing-edge rule.

#### 3.5.4 POST atomicity for the mandatory edges

POST `/migration-mappings` requires both edge body keys so the row and its edges land in one transaction (the DEC-250 pattern, extended to a two-kind edge set):

```
POST /migration-mappings
{
  "migration_mapping_level": "field",
  "migration_mapping_disposition": "transform",
  "migration_mapping_source_system_label": "espocrm @ crm.cbmentors.org",
  "migration_mapping_source_entity_name": "Contact",
  "migration_mapping_source_attribute_name": "cContactType",
  "migration_mapping_transform_rules": [
    {
      "rule_kind": "enum_value_map",
      "value_map": {"Mentor Candidate": "candidate", "Active Mentor": "active"},
      "unmapped_policy": "error"
    }
  ],
  "migration_mapping_notes": null,
  "migration_mapping_status": "confirmed",
  "migration_mapping_migrates_from_identifier": "FLD-041",
  "migration_mapping_migrates_to_identifiers": ["FLD-118"]
}
```

Validation at POST (all in the one transaction):

- `migration_mapping_migrates_from_identifier` missing/null → 422 `missing_source_candidate`.
- Source target not found / soft-deleted / wrong entity type for `level` → 422 `invalid_source_candidate` with reason.
- Source candidate already sourced by a live mapping → 422 `duplicate_mapping_for_candidate` (§3.3.1).
- `migration_mapping_migrates_to_identifiers` missing/empty → 422 `missing_target_record`; any target not found / soft-deleted / not `confirmed` / wrong type → 422 `invalid_target_record` with reason.
- Multiple targets without a `split` rule covering exactly the target set → 422 `split_rule_required`.
- `disposition = keep` with source ≠ target, or with non-empty `transform_rules` → 422 `invalid_keep_shape`.
- Rule-list schema validation per §4 (unknown `rule_kind`, missing required rule keys, level-inapplicable kind) → 422 `invalid_transform_rule` naming the offending rule index.

PUT/PATCH never accept the edge keys; re-pointing a mapping is explicit reference management (rare; normally a mapping is soft-deleted and re-created).

#### 3.5.5 List filters

`GET /migration-mappings` supports, beyond `?include_deleted=true`:

- `?level=entity|field`
- `?source_identifier=ENT-NNN|FLD-NNN` — mappings migrating from the named candidate (the disposition lookup)
- `?target_identifier=ENT-NNN|FLD-NNN` — mappings landing in the named record (merge-group assembly reads this)

Justified as the compile path's and triage UI's dominant access patterns, per the `?entity_identifier` precedent (`field.md` §3.5.5). Further filters (`?status=`, `?disposition=`) deferred to real-use signal.

### 3.6 UI Considerations

Default `ListDetailPanel` layout under the Methodology sidebar group, with one master-pane deviation.

#### 3.6.1 Sidebar

"Migration Mappings", appended to the Methodology group after the existing entries (Domains, Entities, Processes, CRM Candidates, Fields, Personas, Requirements, Manual Configs, Test Specs, …).

#### 3.6.2 Master pane

| Column | Source | Notes |
|--------|--------|-------|
| Identifier | `migration_mapping_identifier` | Default sort key, ascending |
| Level | `migration_mapping_level` | — |
| Source | derived | The `migrates_from_record` target's identifier + name |
| Target | derived | The `migrates_to_record` target identifier(s) + name(s); `A, B` for splits |
| Disposition | `migration_mapping_disposition` | — |
| Status | `migration_mapping_status` | — |
| Updated | `migration_mapping_updated_at` | Localized |

**Deviation: no Name column; Source/Target derived columns instead.** Rationale in §3.2.1 — the source → target pair *is* the record's natural label. Precedent: the `field` master pane's derived Entity column.

#### 3.6.3 Detail pane

Identifier (read-only); Source record (read-only label, edge-derived); Target record(s) (read-only labels, edge-derived); Level; Disposition; Source system label / source entity name / source attribute name; Transform rules (read-only pretty-printed JSON in v1 — a structured rule editor is a deferred follow-on, §8); Notes (collapsed); Status; `ReferencesSection` for any other edges.

#### 3.6.4 Create/Edit/Delete dialogs

`EntityCrudDialog` subclass per the standard pattern: create requires source-candidate and target-record pickers (filtered by the chosen level) and POSTs the atomic body per §3.5.4; transform rules entered as JSON text with client-side schema validation in v1. Edit leaves source/target read-only. Delete uses edge-text confirmation and soft-deletes row + edges atomically. Authoring at triage speed is expected to go through the API/MCP rather than the dialog; the dialog exists for corrections and monitoring parity.

### 3.7 Template section mapping

The remaining template sections are promoted to major sections for citability — the transform-rule model is this record type's substantive core and deserves top-level structure: Transform-Rule Model = §4, Verification Criteria (queries + invariants) = §5, Compile Contract = §6, Acceptance Criteria (template §3.7) = §7, Open Questions (template §3.8) = §8, Cross-References (template §3.9) = §9, Implementation Notes = §10.

---

## 4. Transform-Rule Model

### 4.1 Representation and posture

`migration_mapping_transform_rules` is a JSON **list of rule objects**, each with a `rule_kind` from the closed vocabulary `MIGRATION_TRANSFORM_RULE_KINDS = {type_change, enum_value_map, merge, split}` — exactly the PRD §8 named set. The list is ordered; at compile time rules apply in list order (relevant when a `type_change` and an `enum_value_map` coexist: map values first, then convert, unless the author ordered otherwise).

Posture, inherited from the normalizer (WTK-102 §3.10 "no silent widening"): **no rule has implicit behavior.** Every rule kind carries an explicit policy for the case its happy path doesn't cover (`unmapped_policy`, `on_error`), and the policy vocabulary makes "fail the record" (`error`) the recommended default. Anything the stakeholder didn't decide at triage surfaces at compile pre-flight or as a per-record import error — never as a silently coerced value.

Validation is access-layer JSON-schema validation at write time (§3.5.4); cross-mapping coherence (merge groups) is verified by query (Q5) and compile pre-flight, since it spans rows.

### 4.2 `type_change`

The field's value shape changes between source and target. Field-level only.

| Key | Required | Validation | Description |
|-----|----------|------------|-------------|
| `rule_kind` | yes | `"type_change"` | — |
| `from_type` | yes | member of `FIELD_TYPES` | The source field's methodology-level type (normally the baseline candidate's `field_type`, restated here so the rule is self-contained). |
| `to_type` | yes | member of `FIELD_TYPES`, ≠ `from_type` | The target field's methodology-level type. |
| `conversion` | no | object | How values convert: `{"strategy": "cast" \| "parse" \| "custom", "format": "<strptime-style or pattern, parse only>", "on_error": "error" \| "null" \| "skip_record"}`. Omitted ⇒ `cast` with `on_error: error`. `custom` carries a prose `description` the compiler refuses to auto-compile (it surfaces as a manual migration step). |

Both type endpoints are expressed in the engine-agnostic `FIELD_TYPES` vocabulary (`field.md` §3.2.3), not platform types — consistent with the normalizer having already mapped source natives into `FIELD_TYPES` at deposit. Platform-type realization happens downstream of the methodology layer.

### 4.3 `enum_value_map`

Source option values map to target option values. Field-level only; meaningful when either endpoint is `enum`/`multi_enum`.

| Key | Required | Validation | Description |
|-----|----------|------------|-------------|
| `rule_kind` | yes | `"enum_value_map"` | — |
| `value_map` | yes | non-empty object, string → string | `{source_value: target_value}`. Multiple source values may map to one target value (option consolidation). |
| `unmapped_policy` | yes | `"error"` \| `"passthrough"` \| `"null"` \| `"default"` | What happens to an observed source value absent from `value_map`. `error` (recommended): the record fails import and is reported. `passthrough`: value carried verbatim. `null`: field left empty. `default`: `default_value` used. |
| `default_value` | conditional | required iff `unmapped_policy = "default"` | — |

Completeness is *checkable, not enforced at write*: the observed source value distribution lives in utilization evidence (`evidence_detail` per-option distributions, WTK-088 §4.3), so Q4 reports any confirmed `enum_value_map` whose `value_map` keys don't cover the observed values — at triage time, while the stakeholder can still answer.

### 4.4 `merge`

N source candidates' values/records combine into one target. The rule appears on **each** participating mapping (one per disposition, §3.3.1).

| Key | Required | Validation | Description |
|-----|----------|------------|-------------|
| `rule_kind` | yes | `"merge"` | — |
| `merge_group` | yes | non-empty string | Shared key naming the merge across sibling mappings (e.g., `"contact-full-name"`). Scoped per engagement. |
| `combinator` | yes | `"concat"` \| `"coalesce"` \| `"sum"` \| `"custom"` | Field level: how sibling values combine. Entity level: `coalesce` is the meaningful value — records from N source entities land in one target entity, and per-field collisions resolve by the import machinery's never-overwrite-non-empty rule (§6.3); other combinators are field-level only. `custom` carries a prose `description`, manual-step semantics as in §4.2. |
| `merge_order` | yes | integer ≥ 1, unique within the group | This mapping's position (concat order; coalesce priority). |
| `separator` | conditional | required iff `combinator = "concat"` | E.g., `" "`. Stated explicitly on every member so any single mapping is self-contained. |

Cross-mapping invariants (I10, verified by Q5 and compile pre-flight): all live confirmed mappings sharing a `merge_group` target the same record, declare the same `combinator` (and `separator`), and carry distinct `merge_order` values.

### 4.5 `split`

One source's values/records distribute across N targets. One rule on the one mapping (one disposition), whose target edge set must exactly equal the rule's assignment targets (I6).

| Key | Required | Validation | Description |
|-----|----------|------------|-------------|
| `rule_kind` | yes | `"split"` | — |
| `assignments` | yes | non-empty list | One object per target: `{"target": "<FLD-NNN or ENT-NNN>", "extractor": {...}}`. The `target` set must exactly match the mapping's `migrates_to_record` edge targets. |
| `assignments[].extractor` | yes | object | Field level: `{"strategy": "delimiter", "delimiter": ", ", "index": 0}` or `{"strategy": "pattern", "pattern": "<regex with one capture group>"}` or `{"strategy": "custom", "description": "..."}`. Entity level (record routing, e.g. one Contact entity split into Mentor and Client): `{"strategy": "value_router", "router_attribute": "<source attribute name>", "router_values": ["Mentor", "Mentor Candidate"]}` — a source record routes to the target whose `router_values` contains its router-attribute value; the policy for a record matching no target is the rule-level `unrouted_policy`. |
| `unrouted_policy` | conditional | entity level only; `"error"` \| `"skip_record"` | What happens to a source record matching no assignment's `router_values`. Required at entity level. |

### 4.6 Level applicability

| rule_kind | `level = field` | `level = entity` |
|-----------|------------------|-------------------|
| `type_change` | yes | no |
| `enum_value_map` | yes | no |
| `merge` | yes (value combination) | yes (`coalesce` record-fold only) |
| `split` | yes (value extraction) | yes (`value_router` record routing) |

Level-inapplicable kinds are rejected at write (§3.5.4).

---

## 5. Verification Criteria

The schema is correct and complete when it answers the queries in §5.1 and the invariants in §5.2 hold under test.

### 5.1 Example queries the schema must answer

Sketched in portable SQL over the v2 store (`refs` columns per the live schema; engagement filter elided).

**Q1 — Phase 3 completion check: every keep and transform has a mapping** (PRD §8 completion criterion; must return zero rows before Phase 3 closes). A *keep* is a confirmed baseline candidate; a *transform* is a rejected baseline candidate that is the target of a variant/supersession edge. Shown for `field` (run the analogous arm for `entity` with `entity_variant_of_entity`):

```sql
-- kept fields (confirmed baseline candidates) lacking a mapping
SELECT f.field_identifier, 'keep' AS disposition
FROM fields f
JOIN refs prov ON prov.relationship_kind = 'deposit_event_wrote_record'
              AND prov.target_type = 'field'
              AND prov.target_id = f.field_identifier   -- baseline = deposited by an audit
WHERE f.field_deleted_at IS NULL
  AND f.field_status = 'confirmed'
  AND NOT EXISTS (
    SELECT 1 FROM refs m
    JOIN migration_mappings mm ON mm.migration_mapping_identifier = m.source_id
    WHERE m.relationship_kind = 'migration_mapping_migrates_from_record'
      AND m.target_type = 'field' AND m.target_id = f.field_identifier
      AND mm.migration_mapping_deleted_at IS NULL
      AND mm.migration_mapping_status IN ('confirmed', 'candidate', 'deferred'))
UNION ALL
-- transformed fields (rejected baseline candidates superseded by a new record) lacking a mapping
SELECT f.field_identifier, 'transform'
FROM fields f
JOIN refs v ON v.relationship_kind = 'supersedes'
           AND v.target_type = 'field' AND v.target_id = f.field_identifier
WHERE f.field_status = 'rejected'
  AND NOT EXISTS (
    SELECT 1 FROM refs m
    WHERE m.relationship_kind = 'migration_mapping_migrates_from_record'
      AND m.target_type = 'field' AND m.target_id = f.field_identifier);
```

**Q2 — the migration worksheet:** every confirmed mapping with its source coordinates, target record(s), disposition, and rules — the input to migration planning:

```sql
SELECT mm.migration_mapping_identifier, mm.migration_mapping_level,
       mm.migration_mapping_disposition,
       mm.migration_mapping_source_entity_name,
       mm.migration_mapping_source_attribute_name,
       frm.target_id AS source_record, tto.target_id AS target_record,
       mm.migration_mapping_transform_rules
FROM migration_mappings mm
JOIN refs frm ON frm.source_id = mm.migration_mapping_identifier
             AND frm.relationship_kind = 'migration_mapping_migrates_from_record'
JOIN refs tto ON tto.source_id = mm.migration_mapping_identifier
             AND tto.relationship_kind = 'migration_mapping_migrates_to_record'
WHERE mm.migration_mapping_deleted_at IS NULL
  AND mm.migration_mapping_status = 'confirmed'
ORDER BY mm.migration_mapping_level DESC, mm.migration_mapping_source_entity_name;
```

**Q3 — disposition audit for one candidate:** "where did this go?" — its mapping (if kept/transformed) and its rationale Decision (if transformed/dropped), in one walk: mapping via the inbound `migrates_from_record` edge; Decision via the candidate's outbound `rejected_by_decision` edge (WTK-088 Q5). The schema adds no new mechanism here — the point is that the existing walk *composes*.

**Q4 — enum-map coverage check:** every confirmed `enum_value_map` mapping whose source field's observed value distribution (latest utilization-evidence snapshot, `evidence_detail` per-option distribution) contains values absent from the rule's `value_map` keys and whose `unmapped_policy` is `error`. JSON-extraction over `migration_mapping_transform_rules` joined to `utilization_evidence` per the WTK-088 §5.1 latest-snapshot CTE; flagged rows are triage follow-ups, not schema errors.

**Q5 — merge-group coherence:** for each `merge_group` across live confirmed mappings, exactly one distinct target record, exactly one distinct `combinator` (+ `separator`), and no duplicate `merge_order`. Must return zero incoherent groups before compile.

**Q6 — compile pre-flight: field-level mappings without an entity-level context.** Every confirmed field-level mapping whose source field's parent entity (via `field_belongs_to_entity`) is not the `migrates_from_record` target of a confirmed entity-level mapping, or whose target field's parent entity is not that entity-level mapping's target. Must return zero rows before the affected entity's batch compiles (it is a pre-flight gate, not a write-time gate — triage records mappings incrementally, §3.3.3).

### 5.2 Invariants that must hold

| # | Invariant | Enforced at |
|---|-----------|-------------|
| I1 | Every live mapping has exactly one live `migrates_from_record` edge; POST without the source body key is refused 422. | repository layer, atomic POST (§3.5.4) |
| I2 | Every live mapping has ≥ 1 live `migrates_to_record` edge. | repository layer, atomic POST |
| I3 | A baseline candidate is the `migrates_from_record` target of at most one live mapping ("one mapping per disposition"). | repository layer (duplicate-mapping refusal, §3.3.1) |
| I4 | `migrates_from_record` targets a live record; `migrates_to_record` targets a live record at `confirmed` status (checked at edge creation). | repository layer |
| I5 | Both edges' target entity types equal `migration_mapping_level` (`entity` or `field`). | repository layer |
| I6 | More than one `migrates_to_record` edge ⇔ a `split` rule exists whose `assignments` target set exactly equals the edge-target set. | repository layer (write) + Q5-style pre-flight |
| I7 | `disposition = keep` ⇒ source edge target = target edge target (one target), `transform_rules` empty, and the record is at `confirmed`. | repository layer (write) + verification query (re-triage drift) |
| I8 | `disposition = transform` ⇒ source ≠ every target; the source candidate, once triage closes, is at `rejected` with a live `rejected_by_decision` edge, and each target carries a variant/supersession edge to the source. Write-time check is shape-only (source ≠ target); the disposition-state agreement is a verification query, because mapping and disposition may be recorded in either order within a triage session. | repository layer (shape) + Q1/Q3-family queries (state) |
| I9 | `transform_rules`, when set, is a list of objects each with `rule_kind ∈ MIGRATION_TRANSFORM_RULE_KINDS`, required keys present per §4, kinds level-applicable per §4.6, conditional keys consistent (`default_value` ⇔ `unmapped_policy = default`, etc.). | repository layer JSON-schema validation |
| I10 | All live confirmed mappings sharing a `merge_group`: same single target record, same `combinator`/`separator`, distinct `merge_order`. | verification query (Q5) + compile pre-flight (spans rows; not a write-time gate) |
| I11 | `level = field` ⇒ `source_attribute_name` non-empty; `level = entity` ⇒ `source_attribute_name` NULL. | table CHECK + repository layer |
| I12 | Soft-delete/restore round-trips the row and both edges atomically; restore with a soft-deleted edge target is refused 422; mappings for non-data capture types (`persona`/`process`/`manual_config`) are unrepresentable (edge pair rules admit only `entity`/`field` targets). | repository layer + vocab pair rules |

---

## 6. Compile Contract — from Mappings to the Data-Import Machinery

This section defines what the schema guarantees so that a future compiler can mechanically turn confirmed mappings into executable migration. The compiler itself is new work (§10); per the PRD, mappings "eventually compile into executable migration via the data-import machinery."

### 6.1 The target machinery

`espo_impl/core/import_manager.py` — `ImportManager.check(records, field_mapping, fixed_values)` plans per-record `CREATE`/`UPDATE`/`SKIP`/`ERROR` actions against a target instance, and `execute(plans)` applies them, with the established semantics: match by email, never overwrite existing non-empty fields, E.164 phone cleaning, name derivation. The compiler's job is to produce, **per confirmed entity-level mapping**, an import batch: a list of source records (already transformed) plus a `field_mapping: {source_key: target_platform_field_name}` dict.

### 6.2 The compile function (deterministic by construction)

```
compile(engagement, source snapshot) →
  for each confirmed entity-level mapping M_e:
    field maps = confirmed field-level mappings whose source field belongs to
                 M_e's source entity (derived grouping, §3.3.3; pre-flight Q6 green)
    extract source records by M_e.source_entity_name from the snapshot
      (M_e.source_system_label names which source)
    per record: apply each field map's rules in list order
      (enum_value_map → type_change conversion → merge combination /
       split extraction; merge groups assemble across sibling maps;
       entity-level split routes the record per value_router first)
    emit (records, field_mapping, fixed_values) per target entity
    hand to ImportManager.check → operator review → execute
```

The schema properties that make this deterministic:

- **Literal source coordinates on every mapping** (§3.2.2): extraction never depends on methodology-record names, which may have been edited after triage. The snapshot is addressed by the same names the audit observed.
- **Closed rule vocabulary with explicit policies** (§4): every non-happy-path case has a stakeholder-decided answer (`error`/`null`/`default`/`passthrough`/`skip_record`); `custom` strategies are by definition not auto-compilable and surface as manual migration steps in the compile report rather than guesses.
- **One mapping per disposition** (I3): no ambiguity about which rule set governs a candidate's data.
- **Pre-flight gates** (Q1, Q5, Q6): completeness (every keep/transform mapped), merge coherence, and entity-context coverage are all zero-row checks the compiler runs before emitting anything.

### 6.3 Resolution left to compile time (deliberately)

- **Target platform field names.** Mappings target methodology records (`FLD-NNN`); the import machinery needs platform names (`cContactType`). That resolution belongs to the deploy layer (the YAML generated from confirmed methodology records, per the `field.md` cognate-layer note) and happens at compile time against the generated program files or live target metadata — storing platform names on the mapping would duplicate the deploy layer's naming authority. Open question §8 tracks the exact resolution source.
- **Record matching/dedupe strategy.** `ImportManager` matches by email today. Entity-level `coalesce` merges lean on exactly its never-overwrite-non-empty semantics, which is why that combinator is the entity-level vocabulary (§4.4). Non-person entities will need a match-key story; that is an import-machinery extension, tracked as an open question, not a mapping-schema column — until it exists, non-person entity batches compile as create-only.
- **Source extraction.** Reading source records (the audit/profiler read path against the live source, or a persisted snapshot) is the compiler's input, out of scope for the record type.

---

## 7. Acceptance Criteria

What "this entity type is correctly implemented" looks like; build planning translates these into test cases.

1. **Schema migration applies cleanly, dual-head.** SQLite chain migration creates `migration_mappings` with all twelve columns (identifier, level, disposition, source_system_label, source_entity_name, source_attribute_name, transform_rules, notes, status, created_at, updated_at, deleted_at) plus `engagement_id`, the I11 CHECK, the status CHECK, and the identifier-format CHECK; rebuilds the `refs.relationship_kind` CHECK with both new kinds AND the `change_log` entity-type CHECK with `migration_mapping`; runs forward and backward. The Postgres chain gets the same deltas in `migrations/pg/`.
2. **Identifier format and auto-assignment.** `^MIG-\d{3}$` enforced; POST with identifier omitted server-assigns via the SAVEPOINT-retry helper; `GET /migration-mappings/next-identifier` agrees; concurrent POSTs do not collide.
3. **Vocab registration.** `REFERENCE_RELATIONSHIPS` contains both kinds; `_kinds_for_pair((migration_mapping, entity))` and `((migration_mapping, field))` return both kinds; `MIGRATION_TRANSFORM_RULE_KINDS` exported; `migration_mapping` in `ENTITY_TYPES`.
4. **Atomic POST.** The §3.5.4 body creates row + `migrates_from_record` edge + `migrates_to_record` edge(s) in one transaction; every §3.5.4 422 case returns its named error shape; a mid-transaction failure leaves no orphan row (the PI-153-era transaction-control posture).
5. **One-mapping-per-disposition uniqueness.** A second live mapping POSTed against an already-mapped candidate is refused 422 `duplicate_mapping_for_candidate`; after soft-deleting or rejecting the first, the POST succeeds.
6. **Level agreement.** A field-level POST naming an `ENT-NNN` source (or vice versa) is refused 422; `source_attribute_name` presence/absence enforced per I11.
7. **Keep shape.** `disposition = keep` with source ≠ target, two targets, or non-empty rules is refused 422 `invalid_keep_shape`; a valid keep POST (source = target, no rules) succeeds.
8. **Split shape.** Two `migrates_to_identifiers` without a `split` rule → 422 `split_rule_required`; a `split` rule whose assignment targets don't exactly equal the edge-target set → 422 `invalid_transform_rule`; a valid one-source-two-target split round-trips.
9. **Rule-list validation.** Unknown `rule_kind`, missing required keys, level-inapplicable kinds, and inconsistent conditional keys (`unmapped_policy = default` without `default_value`; `concat` without `separator`) are each refused 422 `invalid_transform_rule` naming the rule index; a valid example of each of the four kinds round-trips byte-identically through POST → GET.
10. **Status lifecycle.** Four-status transitions enforced with the standard 422 shape; POST at explicit `confirmed` accepted; `rejected` requires the atomic `rejected_by_decision` key or pre-existing edge and is terminal.
11. **Soft-delete/restore atomicity.** DELETE soft-deletes row + both edges; restore restores all three; restore with a soft-deleted edge target is refused 422 naming the blocked side.
12. **List filters.** `?level=`, `?source_identifier=`, `?target_identifier=`, `?include_deleted=true` each filter correctly; the source-identifier filter returns the unique live mapping for a disposed candidate.
13. **Verification queries run green on a seeded fixture.** A test fixture seeding one keep, one rename-only transform, one enum-map transform, one two-source merge, and one one-source-two-target split (plus one unmapped kept candidate and one incoherent merge group as negative rows) makes Q1 return exactly the unmapped candidate, Q5 exactly the incoherent group, and Q2 exactly the five mappings with correct joins.
14. **Change-log coverage.** Mapping writes emit `change_log` rows under entity type `migration_mapping` without 500s on a live (non-create_all) DB — the known CHECK-rebuild gotcha is regression-tested by the migration test, not only create_all.
15. **UI panel.** Migration Mappings appears in the Methodology sidebar group; master pane shows the §3.6.2 columns including derived Source/Target; detail pane renders rules read-only; CRUD dialogs round-trip a keep and a transform end to end.
16. **Sample CBM-scale triage batch.** Roughly 20 mappings spanning both levels and all four rule kinds can be authored via REST in triage order (mappings before some dispositions finalize, per I8's deferred state check), and Q1/Q5/Q6 converge to zero rows once the batch completes.

---

## 8. Open Questions and Deferred Decisions

(The template's §3.8, promoted to a major section alongside §4–§7; placed after the substantive sections it depends on.)

**[build] Target-platform-name resolution source (§6.3).** The compiler resolves `FLD-NNN` targets to platform field names via the generated YAML program files or live target-instance metadata. Which, and how conflicts surface, is the compiler's first design question — explicitly not a mapping column.

**[build] Rule-list JSON-schema location.** Whether §4's rule schemas live as a vocab-adjacent constant (`MIGRATION_TRANSFORM_RULE_SCHEMAS`) validated in the repository layer, or as pydantic models on the API boundary. Either satisfies I9; the build decides per the existing JSON-column validation precedents.

**[build] Compile-run provenance.** Whether a compile/import run deposits a `deposit_event` with `wrote_record`-style edges back to the mappings it compiled (§3.3.2), or a dedicated `compiled_from` kind. Belongs to the compiler's spec.

**[CBM redo] Structured rule editor.** v1 renders/edits rules as validated JSON text (§3.6.3). Whether triage volume justifies a structured per-kind editor is a real-use question.

**[CBM redo] Match-key strategy for non-person entities (§6.3).** `ImportManager` matches by email; entity-level merges of non-person entities need a match-key extension to the import machinery. Surfaced by the first CBM entity batch that needs UPDATE semantics; until then create-only.

**[CBM redo] Migration waves.** `deferred` carries "migrates in a later wave" (§3.4.1). If real engagements need named waves with ordering, a `migration_mapping_wave` column (or a grouping record) is a v-next migration; status alone is the v1 posture.

**[v-next] Default-value / constant-fill rules.** The PRD names four rule kinds; "fill the target with a constant the source never had" is a plausible fifth (`constant_fill`). Deliberately excluded until triage produces a real case — the closed vocabulary is cheap to extend and expensive to shrink.

---

## 9. Cross-References

**Decisions to be authored at build-closure** (descriptive, unnumbered — identifiers are claimed on `main` at apply time per the Model A branch protocol): (a) `migration_mapping` identity/prefix/lifecycle adoption; (b) the two-edge linkage model with source-side uniqueness encoding one-mapping-per-disposition and the through-the-candidate disposition-Decision posture; (c) the closed transform-rule vocabulary and no-silent-behavior policy posture; (d) the denormalized-source-coordinates compile-determinism posture; (e) the no-name-column UI deviation.

- `specifications/master-crmbuilder-PRD.md` §8 — the Migration Mapping requirement, dispositions table, and completion criteria this spec implements; §7 — the Phase 1.5 candidates and evidence it builds on.
- `candidate-lifecycle-rejected-and-utilization-evidence.md` (WTK-088) — the disposition lifecycle (`rejected`, `rejected_by_decision`, §3.6 triage mapping) and the utilization-evidence table Q4 joins; named this record type as its deferred §7 item.
- `field.md` / `entity.md` — the two subject entity types; `field_belongs_to_entity` (the Q6 grouping walk); `FIELD_TYPES` (§4.2's type vocabulary); the atomic-POST and mandatory-edge enforcement precedents (DEC-249/250).
- `catalog-normalizer-type-mapping-and-partition.md` (WTK-102) — the no-silent-behavior posture inherited by §4.1; the normalization that puts source types into `FIELD_TYPES` before mappings are authored.
- `espocrm-data-profiling-pass.md` (WTK-096) — the observed value distributions behind Q4.
- `espo_impl/core/import_manager.py` — the compile target (§6).
- `methodology-entity-schema-spec-guide.md` — the template; deviations documented: no name column (§3.2.1), derived master-pane columns (§3.6.2), section promotion per the §3.7 mapping.
- DEC-006 (references-first), DEC-043 (next-identifier helpers), DEC-044 (prefix posture), DEC-046 (parent-prefix naming), DEC-047 (lifecycle), DEC-048 (relationship-kind naming), DEC-249/250 (mandatory-edge atomic POST), DEC-291 (`entity_variant_of_entity`), PI-002 (identifier on POST optional), PI-123 (engagement scoping).

---

## 10. Implementation Notes (build surface for the implementing Work Tasks)

This spec ships no code. The build surface:

- **vocab.py:** `MIGRATION_MAPPING_STATUSES` / `_STATUS_TRANSITIONS` (standard four-status); `MIGRATION_MAPPING_LEVELS`; `MIGRATION_MAPPING_DISPOSITIONS`; `MIGRATION_TRANSFORM_RULE_KINDS`; both edge kinds in `REFERENCE_RELATIONSHIPS` + `_kinds_for_pair` clauses; `migration_mapping` in `ENTITY_TYPES`; extend the `rejected_by_decision` source set to include `migration_mapping` (§3.4.1).
- **models.py:** `MigrationMapping(EngagementScopedMixin, Base)` per §3.2, `JSONColumnNoneAsNull` for the rules column, CHECKs per I11 + status + identifier format.
- **Migrations, dual-head:** SQLite chain — create table, rebuild `ck_ref_relationship` AND the `change_log` entity-type CHECK (the live-DB gotcha); PG chain — same deltas in `migrations/pg/`; never replay the SQLite chain on PG.
- **Repository layer:** atomic POST (row + two edge kinds, §3.5.4); source-side uniqueness (I3); level/liveness/status edge validation (I4/I5); keep-shape and split-shape checks (I6/I7); rule-list validation (I9); soft-delete/restore edge atomicity; the three list filters.
- **API:** standard endpoint set + the §3.5.4 error shapes, `{data, meta, errors}` envelope.
- **Verification queries:** Q1/Q5/Q6 as repository helpers (they are the Phase 3 close and compile pre-flight gates, so they need a callable form, not just documentation).
- **UI (follow-on):** the §3.6 panel.
- **The compiler** (§6) is its own Planning Item, downstream of this record type and the spreadsheet/source-snapshot story.

---

*End of document.*

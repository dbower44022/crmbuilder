# Methodology Schema Design Spec — `rejected` Lifecycle State and Utilization-Evidence Storage

**Last Updated:** 06-11-26
**Status:** Draft v1.0 — produced under WTK-088 (Architecture deliverable for the audit-to-V2 deposit path)
**Position in workstream:** Cross-cutting design spec resolving the two Master CRMBuilder PRD v0.2 open schema decisions for the methodology candidate lifecycle (`specifications/master-crmbuilder-PRD.md`, "Gaps and questions added at v0.2"): (1) no rejected/terminal disposition exists in the methodology lifecycle; (2) where utilization evidence lives on candidate records. Both decisions gate the Phase 1.5 audit → V2 deposit path and the Phase 3 baseline-triage *drop* disposition.
**Companion documents:** `methodology-entity-schema-spec-guide.md` (template conventions); the per-entity specs this design amends when implemented (`domain.md`, `entity.md`, `field.md`, `persona.md`, `requirement.md`, `manual_config.md`, `test_spec.md`); `specifications/master-crmbuilder-PRD.md` §7 (Phase 1.5) and §8 (Phase 3 baseline triage).

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 06-11-26 | ADO Area Specialist (storage) / Claude | Initial draft under WTK-088. Decision 1: a fourth lifecycle status `rejected` — truly terminal, reachable from `candidate` and `deferred` only, never from `confirmed` — added uniformly to the seven status-bearing methodology entity types, with the drop rationale carried by a mandatory `rejected_by_decision` reference edge to a Decision record, applied atomically with the status flip (PI-030 `resolves` precedent). Decision 2: utilization evidence lives in a new append-only child table `utilization_evidence` with polymorphic subject columns (`change_log` precedent), typed triage-critical metric columns, and a JSON detail column — chosen over per-table JSON columns. Verification criteria: six example triage queries the schema must answer and ten lifecycle invariants that must hold. |

---

## Change Log

**Version 1.0 (06-11-26):** Initial creation. Resolves the two pending schema decisions named in Master CRMBuilder PRD v0.2 so the Phase 1.5 deposit path and Phase 3 triage *drop* disposition have a defined storage target. No code, vocab, or migration changes ship with this document — it is the design the implementing Planning Item builds from. §6 enumerates the implementation surface (vocab additions, CHECK rebuilds including the `change_log` CHECK, dual-head SQLite + Postgres migrations, repository enforcement points).

---

## 1. Purpose and Position

Master CRMBuilder PRD v0.2 drafted Phase 1.5 (Existing System Baseline) and the Phase 3 baseline-triage section, and left two schema decisions explicitly pending:

1. **No rejected/terminal disposition exists in the methodology lifecycle.** The current one-way gate is `candidate → confirmed ⇄ deferred`. Triage's *drop* disposition wants a true rejected terminal state with recorded rationale, distinct from `deferred`.
2. **Where evidence lives on candidate records** — a structured evidence column/child table vs. free-text notes — with the requirement that evidence be structured enough for triage queries such as "all fields under 5% population".

This spec resolves both. It is a design document in the lineage of the per-entity methodology schema specs (`domain.md` → `entity.md` → … → `test_spec.md`) but cross-cutting: Decision 1 amends the shared lifecycle those specs inherit from `domain.md` §3.4 / DEC-047, and Decision 2 introduces one new table serving five subject entity types. When implemented, each affected per-entity spec gains a short §3.4 amendment pointing here; this document remains the authoritative rationale.

Both decisions unblock the audit-to-V2 deposit path (Master PRD §7 Known Limitations): the deposit transform cannot write evidence until evidence has a home, and triage cannot run until *drop* has a storage semantic.

---

## 2. Summary of Decisions

| # | Decision | Resolution |
|---|----------|------------|
| D1 | Rejected terminal state | Add a fourth status `rejected` to every status-bearing methodology entity type. Truly terminal (empty successor set). Reachable from `candidate` and `deferred` only — never directly from `confirmed`. The drop rationale is a Decision record linked by a new mandatory `rejected_by_decision` reference edge, created atomically with the status flip. |
| D2 | Utilization evidence storage | A new append-only child table `utilization_evidence` with polymorphic subject columns (`evidence_subject_type` + `evidence_subject_identifier`, per the `change_log` precedent), typed columns for the triage-critical metrics, and a JSON `evidence_detail` column for source-specific depth. Chosen over a JSON column on each candidate table. |

---

## 3. Decision 1 — `rejected` Lifecycle State

### 3.1 Status value and scope

A new status value `rejected` is added to the methodology lifecycle vocabulary. It applies to the seven methodology entity types that carry a lifecycle status today:

| Entity type | Current statuses | With this spec |
|---|---|---|
| `domain` | `candidate` / `confirmed` / `deferred` | + `rejected` |
| `entity` | `candidate` / `confirmed` / `deferred` | + `rejected` |
| `field` | `candidate` / `confirmed` / `deferred` | + `rejected` |
| `persona` | `candidate` / `confirmed` / `deferred` | + `rejected` |
| `requirement` | `candidate` / `confirmed` / `deferred` | + `rejected` |
| `test_spec` | `candidate` / `confirmed` / `deferred` | + `rejected` |
| `manual_config` | `candidate` / `confirmed` / `deferred` / `completed` | + `rejected` |

The extension is uniform by design: the three-status lifecycle was established once (`domain.md` §3.4, DEC-047) and inherited unchanged across the cohort; the fourth status follows the same discipline so there is one rejection vocabulary across the methodology layer, not per-type variants.

Out of scope for D1:

- **`process`** carries no `status` field — the four-value `process_classification` enum stands in its place per `process.md` §3.4 / DEC-057. Phase 1.5 captures process candidates and Phase 3 must be able to drop them, so this is a real gap, but closing it means giving `process` a lifecycle status — a `process.md` amendment with its own decision, not a silent side effect of this spec. **Recommendation:** add `process_status` with the four-status lifecycle defined here in a follow-on decision; until it lands, a dropped process candidate is soft-deleted with the rationale Decision linked via the generic `references` kind. Tracked in §7.
- **`crm_candidate`** already has its own terminal `declined` (DEC-062) — unaffected.
- **`term`** uses the documentary `active` / `draft` / `retired` lifecycle — unaffected.

### 3.2 Transition model

The updated transition map, identical for the six three-status types (shown generically; each type's map substitutes its own prefix):

```
candidate: {confirmed, deferred, rejected}
confirmed: {deferred}
deferred:  {confirmed, rejected}
rejected:  {}            ← truly terminal
```

`manual_config` keeps its `completed` deviation and gains the same arcs:

```
candidate: {confirmed, deferred, rejected}
confirmed: {deferred, completed}
deferred:  {confirmed, rejected}
completed: {}
rejected:  {}
```

Transition semantics, in the form the existing specs use:

| From | To `rejected` permitted? | Rationale |
|---|---|---|
| `candidate` | **Yes** | The Phase 3 triage *drop* disposition: a baseline candidate deliberately not carried forward. Also available outside triage for any proposed-then-rejected record. |
| `deferred` | **Yes** | A deferral that hardens into a permanent drop. Deferred means "acknowledged, not now"; when "not now" becomes "never", the record moves to `rejected` rather than lingering ambiguously. |
| `confirmed` | **No** | A confirmed record was accepted into the inventory; removing it later is a scope change, not a triage drop. It must first be demoted `confirmed → deferred` (one visible decision) and then `deferred → rejected` (a second visible decision). The two-step demotion keeps "we un-accepted this" and "we permanently dropped this" as separate, individually auditable moves and preserves the propose-verify shape of the existing gate. |
| `completed` (`manual_config` only) | **No** | `completed` is already terminal; completed work is never retroactively rejected. Unchanged from `manual_config.md` §3.4. |

The one-way gate out of `candidate` is preserved: no status — including `rejected` — ever lists `candidate` as a successor.

### 3.3 Irreversibility rules

`rejected` is a **true terminal**, in the sense the v0.7 governance lifecycles use the word (no transitions out, no transitions between terminals):

- **Empty successor set.** The `*_STATUS_TRANSITIONS` map for every affected type lists `rejected: frozenset()`. The standard status-transition validation in the access layer therefore refuses every PATCH out of `rejected` with the existing invalid-transition error shape.
- **Soft-delete does not reopen it.** A rejected record may still be soft-deleted (DELETE) and restored (POST `/restore`); restore preserves status, so the record comes back at `rejected`. There is no soft-delete-and-restore path back into the live lifecycle — this is deliberately *stronger* than the `manual_config` `completed` posture ("soft-delete-and-restore-and-redo is the only path back"), because rejection records a stakeholder decision, not a work state.
- **Re-proposal is a new record, not a resurrection.** If a rejected item turns out to be needed after all, the consultant creates a *new* candidate record and links it to the rejected one with the existing same-type `supersedes` kind (new record → rejected record), or `entity_variant_of_entity` where the entity-variant semantic fits. The rejected record and its rationale Decision remain intact as the durable answer to "where did this go, and why?" — the new record carries the new context. No status machinery changes are needed for this; the vocabulary already admits both edges.

### 3.4 Drop rationale — the `rejected_by_decision` edge

**New reference kind:** `rejected_by_decision`.

| Property | Value |
|---|---|
| Kind name | `rejected_by_decision` |
| Source types | `domain`, `entity`, `field`, `persona`, `requirement`, `test_spec`, `manual_config` (the §3.1 scope) |
| Target type | `decision` |
| Mechanism | references-entity edge (`refs` table), like every methodology cross-edge per DEC-006 |
| Cardinality | A rejected record has **at least one** outbound `rejected_by_decision` edge (exactly one in the normal case; a later superseding Decision may add a second). A Decision may reject many records — Phase 3 triage batches by domain, and one triage Decision legitimately covers a coherent group of drops ("drop the seven dormant marketing-automation fields, rationale: …"). |

Naming note: the kind is a single generic name constrained by source/target pair rules, following the v0.8 precedent (`resolves`, `addresses`, `blocked_by`) rather than the per-type `{source}_{verb}_{target}` pattern (DEC-048). Seven per-type names (`field_rejected_by_decision`, `entity_rejected_by_decision`, …) would say nothing the pair constraint doesn't already say, and the newer generic precedent exists precisely for kinds whose semantic is uniform across source types.

**Enforcement — transition-requires-edge, applied atomically.** The pattern mirrors two existing mechanisms:

1. **Atomic edge + flip** (primary path, PI-030 `resolves` precedent): the status PATCH that moves a record to `rejected` carries the rejecting Decision's identifier — `{"field_status": "rejected", "rejected_by_decision": "DEC-NNN"}` — and the access layer creates the `rejected_by_decision` edge and flips the status in one transaction. A PATCH to `rejected` *without* the key and *without* a pre-existing live edge is refused (422) with an error naming this rule.
2. **Edge-first** (also valid): a client may POST the `rejected_by_decision` reference first and then PATCH the status to `rejected` without the key; the access layer finds the existing edge and admits the transition. This keeps the decomposed-reference handling style of the standard endpoint set usable.

Either way, the invariant at rest is the same: **no record is at `rejected` without a live `rejected_by_decision` edge** (invariant I3, §5.2). The supporting edge cannot be deleted while the record remains at `rejected` (the access layer refuses, mirroring the v0.7 consumed-requires-edge and supersession-requires-edge enforcement on `work_ticket` and governance supersession).

The Decision record itself is a standard `DEC-NNN` governance record — context, decision, rationale, executive summary — authored per the governance recording rules (TOP-013). This spec adds no columns to `decisions`. No `*_rejected_at` / `*_rejected_by` columns are added to the methodology tables either: the Decision carries the who/why, the `refs` row carries `created_at`, and `change_log` carries the transition timestamp — adding columns would duplicate all three.

### 3.5 `rejected` vs. `deferred` vs. soft-delete

The three exits now mean three different things, and the distinction is the point of D1:

| Mechanism | Meaning | Reversible? | Rationale required? | Visible in live lists? |
|---|---|---|---|---|
| `deferred` | Acknowledged, deliberately not now; may return | Yes — `deferred → confirmed` | No (notes optional) | Yes, filtered by status |
| `rejected` | Deliberately and permanently not carried forward | No — terminal; re-proposal is a new record | **Yes — linked Decision, enforced** | Yes, filtered by status |
| Soft-delete | Bookkeeping removal (mistake, duplicate, test data) | Yes — POST `/restore` | No | No |

Before this spec, "rejection via soft-delete" (`field.md` §3.4.4 and siblings) conflated the second and third rows. That guidance is **superseded for stakeholder-decided drops**: a triage drop is a governed removal that must stay queryable ("show me everything we dropped and why"), which soft-delete cannot provide. Soft-delete remains correct for the bookkeeping cases. The per-entity specs' §3.4.4 sections should be amended to say exactly this when D1 is implemented.

### 3.6 Phase 3 triage mapping

How the three triage dispositions (Master PRD §8) land on this model:

| Disposition | Storage effect |
|---|---|
| **Keep** | `candidate → confirmed` (unchanged by this spec) |
| **Transform** | New confirmed record + variant/supersession edge; the baseline candidate is *closed* by moving it to `rejected` with the transform Decision as its `rejected_by_decision` target — the Decision's rationale states the record was transformed, not discarded, and the variant edge preserves lineage |
| **Drop** | `candidate → rejected` + `rejected_by_decision` → the drop Decision |

This gives Phase 3's completion criterion "no baseline candidate remains at `candidate`" a precise queryable form (§5.1, Q6) and makes "every drop has a Decision record with rationale" structurally guaranteed rather than procedurally hoped-for.

---

## 4. Decision 2 — Utilization-Evidence Storage

### 4.1 Options considered

**Option A — JSON evidence column on each candidate table** (`entity_utilization_evidence`, `field_utilization_evidence`, …): evidence travels on the row; reads are trivial. Rejected because: (a) five tables × one migration each, and every future evidence-shape change is five more; (b) the headline triage queries become JSON-extraction queries (`json_extract` / `jsonb_*`) that differ in ergonomics across the SQLite/Postgres dual-dialect posture (PI-α) and cannot be straightforwardly indexed on SQLite; (c) re-profiling overwrites — a single column holds one snapshot, but Phase 1.5 re-runs and the planned post-deployment drift detection ("the baseline machinery's second pointing", Master PRD Part III) need history; (d) it bloats the candidate tables the per-entity specs deliberately keep small.

**Option B — child table with typed columns (chosen):** one table serves all subject types; the triage-critical metrics are real typed, indexable columns so the headline queries are plain portable SQL; repeated profiling appends snapshot rows naturally; candidate tables are untouched.

**Free-text notes** (the third option named in the PRD) fails the stated requirement outright — "all fields under 5% population" is not answerable from prose — and is not considered further.

### 4.2 Subject linkage — polymorphic columns, not `refs`

Evidence rows point at their subject via two plain columns, `evidence_subject_type` + `evidence_subject_identifier`, following the `change_log` precedent — **not** via the `refs` table. The references store is the uniform mechanism for *methodology judgment edges* (affiliations, coverage, lineage — things consultants create and reason over). Utilization evidence is *observational machine output*: high-volume (one row per discovered field per profile run — hundreds per audit), written mechanically by the deposit path, never authored or re-pointed by a person. `change_log` and `identifier_reservations` are the existing precedents for mechanical tables with integer surrogate PKs outside the refs discipline; evidence joins that family. This also means no prefixed identifier (`UTL-NNN`) and no per-row presence in conversation — evidence rows are cited through their subject ("FLD-042's population rate"), never directly.

The subject reference is soft (a string pair, not an FK), like `change_log.entity_identifier` and `principal_id`: evidence must outlive nothing — but the access layer validates at insert that the subject row exists, is live, and is of an evidence-bearing type (I9, §5.2).

### 4.3 Table definition — `utilization_evidence`

Engagement-scoped (`EngagementScopedMixin`), integer surrogate PK, column prefix `evidence_` per the parent-prefix convention (DEC-046).

| Column | Type | Required | Validation | Description |
|---|---|---|---|---|
| `id` | INTEGER | yes (PK) | autoincrement | Surrogate key. No prefixed identifier — mechanical table, §4.2. |
| `engagement_id` | TEXT | yes | mixin-standard | Row-level engagement scope (PI-123). |
| `evidence_subject_type` | TEXT | yes | enum: `entity` \| `field` \| `persona` \| `process` \| `manual_config` | The Phase 1.5 capture types (Master PRD §7 table). `process` carries evidence even though it has no lifecycle status (§3.1). |
| `evidence_subject_identifier` | TEXT | yes | non-empty; subject must exist, be live, and match `evidence_subject_type` (access layer) | `ENT-NNN`, `FLD-NNN`, etc. Soft reference, §4.2. |
| `evidence_profiled_at` | DATETIME | yes | ISO 8601 UTC | Snapshot timestamp of the *source data* — when the profiler read the source system, not when the row was written. The "as of when" half of provenance. |
| `evidence_source_label` | TEXT | yes | non-empty trimmed | Human-readable source identity, e.g. `espocrm @ crm.cbmentors.org`. The "where from" half, denormalized for direct query; the deposit event carries the full source identity in `apply_context`. |
| `evidence_deposit_event_identifier` | TEXT | no | `DEP-NNN` format when set | Soft reference to the depositing `deposit_event`. Nullable: a standalone re-profile (drift check) may run outside a deposit. |
| `evidence_catalog_class` | TEXT | no | enum: `standard` \| `custom`, or NULL | Standard-vs-custom catalog partition (Master PRD §7 Activity 3). NULL where the partition doesn't apply (e.g. persona evidence). |
| `evidence_record_count` | INTEGER | no | ≥ 0 | Entity-shaped: total live records of the discovered entity at snapshot time. NULL for non-entity subjects. |
| `evidence_last_record_created_at` | DATETIME | no | ISO 8601 UTC | Entity-shaped: most recent record creation in the source — the dormancy signal. |
| `evidence_populated_count` | INTEGER | no | ≥ 0 | Field-shaped: count of parent-entity records with this field non-empty. |
| `evidence_population_rate` | FLOAT | no | 0.0 – 1.0 | Field-shaped: `populated_count / parent record count`, stored (not derived at query time) so the headline triage query is a flat indexed comparison. |
| `evidence_last_populated_at` | DATETIME | no | ISO 8601 UTC | Field-shaped: most recent write of a non-empty value — "hasn't been filled in since 2024". |
| `evidence_distinct_value_count` | INTEGER | no | ≥ 0 | Field-shaped: distinct non-empty values observed. |
| `evidence_declared_option_count` | INTEGER | no | ≥ 0 | Enum-shaped: options declared in source configuration. |
| `evidence_used_option_count` | INTEGER | no | ≥ 0 | Enum-shaped: declared options actually present in data — `declared − used` is the ghost-option count. |
| `evidence_detail` | JSON | no | object when set | Source-specific depth that doesn't warrant typed columns: per-option value distributions, top-N values, dormancy notes, structural-oddity flags (workflow references a deleted field), profiler version. `JSONColumnNoneAsNull` per the PI-α dialect aliases. |
| `evidence_created_at` | DATETIME | yes | server-set on insert | Row write time. No `updated_at` / `deleted_at` — the table is append-only (§4.4). |

All metric columns are nullable because evidence is shape-heterogeneous: an entity row uses the record-count pair, a field row the population trio, an enum field additionally the option pair, a persona row possibly none of them (its evidence — role membership counts, last-login recency — lives in `evidence_detail` until a typed column earns its place). The typed set is exactly the metrics the Master PRD's triage rules query by name; everything else starts in `evidence_detail` and is promoted by migration when a triage query needs it indexed.

**Indexes:** `(evidence_subject_type, evidence_subject_identifier, evidence_profiled_at)` (the latest-snapshot lookup), `evidence_population_rate`, `evidence_deposit_event_identifier`, `engagement_id`.

### 4.4 Append-only semantics and snapshots

Evidence is observational: rows are written by the deposit path (or a standalone re-profile) and never edited. The API surface is **POST + GET only** — no PATCH, no DELETE — mirroring the born-terminal `deposit_event` posture. A re-profile appends a new row per subject; history accumulates by design and is the input to the planned drift detection.

**Latest-snapshot rule:** the current evidence for a subject is the row with the greatest `evidence_profiled_at` per `(evidence_subject_type, evidence_subject_identifier, evidence_source_label)`. Triage queries read the latest row per subject (across sources where a client has several — rare, and triage then sees one row per source, which is correct: the same candidate may be heavily used in one system and dormant in another).

### 4.5 API surface

| Endpoint | Behavior |
|---|---|
| `POST /utilization-evidence` | Insert one row. Validates subject existence/liveness/type-match, enum and range constraints. Batch form (`POST` with a list) is an implementation option for the deposit path; not required by this spec. |
| `GET /utilization-evidence` | Filtered list: `subject_type`, `subject_identifier`, `deposit_event`, `max_population_rate`, `latest=true` (apply the §4.4 latest-snapshot rule), standard pagination. This single endpoint, with `subject_type=field&max_population_rate=0.05&latest=true`, *is* the headline triage query over REST. |
| `GET /fields/{id}/utilization-evidence` (and sibling nested reads per subject type) | Convenience: evidence rows for one subject, newest first. |

Standard `{data, meta, errors}` envelope throughout. Evidence writes emit `change_log` rows like every mutating access-layer call, which requires the `change_log` CHECK rebuild noted in §6.

---

## 5. Verification Criteria

The implementation is correct when the schema answers the queries in §5.1 and the invariants in §5.2 hold under test.

### 5.1 Example triage queries the schema must answer

Written as portable SQL (SQLite ≥ 3.25 and Postgres; window functions used for latest-snapshot). `latest` below is the §4.4 rule:

```sql
WITH latest AS (
  SELECT ue.*,
         ROW_NUMBER() OVER (
           PARTITION BY ue.evidence_subject_type,
                        ue.evidence_subject_identifier,
                        ue.evidence_source_label
           ORDER BY ue.evidence_profiled_at DESC
         ) AS rn
  FROM utilization_evidence ue
)
```

**Q1 — all candidate fields under 5% population** (the PRD's named query):

```sql
SELECT f.field_identifier, f.field_name,
       l.evidence_population_rate, l.evidence_source_label
FROM fields f
JOIN latest l
  ON l.evidence_subject_type = 'field'
 AND l.evidence_subject_identifier = f.field_identifier
 AND l.rn = 1
WHERE f.field_deleted_at IS NULL
  AND f.field_status = 'candidate'
  AND l.evidence_population_rate < 0.05
ORDER BY l.evidence_population_rate;
```

**Q2 — dormant candidate entities** (gaps-and-ghosts: empty or no record created in 12 months):

```sql
SELECT e.entity_identifier, e.entity_name,
       l.evidence_record_count, l.evidence_last_record_created_at
FROM entities e
JOIN latest l
  ON l.evidence_subject_type = 'entity'
 AND l.evidence_subject_identifier = e.entity_identifier
 AND l.rn = 1
WHERE e.entity_deleted_at IS NULL
  AND e.entity_status = 'candidate'
  AND (l.evidence_record_count = 0
       OR l.evidence_last_record_created_at < :twelve_months_ago);
```

**Q3 — ghost enum options** (declared but unused options on candidate fields):

```sql
SELECT f.field_identifier, f.field_name,
       l.evidence_declared_option_count - l.evidence_used_option_count
         AS ghost_options
FROM fields f
JOIN latest l
  ON l.evidence_subject_type = 'field'
 AND l.evidence_subject_identifier = f.field_identifier
 AND l.rn = 1
WHERE f.field_deleted_at IS NULL
  AND l.evidence_declared_option_count IS NOT NULL
  AND l.evidence_used_option_count < l.evidence_declared_option_count
ORDER BY ghost_options DESC;
```

**Q4 — Phase 1.5 completion check: candidates missing evidence** (must return zero rows before the phase closes; shown for `field`, run per subject type):

```sql
SELECT f.field_identifier
FROM fields f
WHERE f.field_deleted_at IS NULL
  AND f.field_status = 'candidate'
  AND NOT EXISTS (
    SELECT 1 FROM utilization_evidence ue
    WHERE ue.evidence_subject_type = 'field'
      AND ue.evidence_subject_identifier = f.field_identifier);
```

**Q5 — drop audit: every rejected field with its rationale Decision** ("show me everything we dropped and why"):

```sql
SELECT f.field_identifier, f.field_name,
       r.target_id AS decision_identifier, d.title AS decision_title
FROM fields f
JOIN refs r
  ON r.source_type = 'field'
 AND r.source_id = f.field_identifier
 AND r.relationship_kind = 'rejected_by_decision'
JOIN decisions d ON d.identifier = r.target_id
WHERE f.field_status = 'rejected';
```

**Q6 — Phase 3 completion check: triage progress per deposit event** (candidates from one Phase 1.5 source still awaiting disposition; must reach zero):

```sql
SELECT r.target_type, r.target_id
FROM refs r
JOIN fields f
  ON r.target_type = 'field' AND r.target_id = f.field_identifier
WHERE r.source_type = 'deposit_event'
  AND r.source_id = :dep_identifier
  AND r.relationship_kind = 'deposit_event_wrote_record'
  AND f.field_status = 'candidate';
-- union the analogous arm per subject type (entities, personas, …)
```

### 5.2 Lifecycle invariants that must hold

| # | Invariant | Enforced at |
|---|---|---|
| I1 | `rejected` has an empty successor set — no PATCH out of `rejected` succeeds, for any affected entity type. | vocab transition map + standard status-transition validation |
| I2 | `rejected` is reachable only from `candidate` and `deferred`. `confirmed → rejected` and (`manual_config`) `completed → rejected` are refused. | vocab transition map |
| I3 | Every record at `rejected` has ≥ 1 live outbound `rejected_by_decision` edge to an existing Decision. A PATCH to `rejected` without the atomic `rejected_by_decision` key and without a pre-existing edge is refused (422). | repository layer (atomic edge + flip, PI-030 pattern) |
| I4 | A `rejected_by_decision` edge cannot be deleted while its source record's status is `rejected`. | repository layer (consumed-requires-edge pattern) |
| I5 | Soft-delete and restore preserve `rejected`; restore never re-opens the lifecycle. | existing restore semantics (status untouched) — covered by test, no new code |
| I6 | No status lists `candidate` as a successor (one-way gate preserved). | vocab transition map |
| I7 | The `rejected_by_decision` kind is admitted only for (§3.1 source type, `decision`) pairs — `RELATIONSHIP_RULES`, the refs CHECK, and the access layer agree. | vocab `_kinds_for_pair` + `ck_ref_relationship` rebuild |
| I8 | `utilization_evidence` is append-only: no UPDATE or DELETE path exists through the API or access layer. | API surface (POST + GET only) |
| I9 | Every evidence row's subject exists, is live (not soft-deleted), and its type matches `evidence_subject_type`, validated at insert; `evidence_subject_type` is CHECK-constrained to the five capture types. | repository layer + table CHECK |
| I10 | Evidence never participates in lifecycle enforcement: rejecting (or deleting) a candidate leaves its evidence rows intact and queryable, and a candidate with no evidence can still transition normally (Q4 is a *process* gate, not a schema gate). | by construction (no coupling) — covered by test |

---

## 6. Implementation Notes (for the building Planning Item)

This spec ships no code. The build surface it defines:

- **vocab.py:** add `rejected` to the seven `*_STATUSES` sets and their `*_STATUS_TRANSITIONS` maps (§3.2); add `rejected_by_decision` to `REFERENCE_RELATIONSHIPS`; add the pair clause to `_kinds_for_pair` (source in the §3.1 seven, target `decision`); add an `EVIDENCE_SUBJECT_TYPES` frozenset (`entity`, `field`, `persona`, `process`, `manual_config`).
- **models.py:** new `UtilizationEvidence(EngagementScopedMixin, Base)` per §4.3; widen the seven `ck_*_status` CHECKs.
- **Migrations, dual-head (PI-α):** SQLite chain — batch-rebuild the seven status CHECKs, rebuild `ck_ref_relationship` from current vocab, rebuild the `change_log` entity-type CHECK (the known gotcha: tests are `create_all`-based and miss it; the live DB 500s without it), create `utilization_evidence`. Postgres chain — the same deltas in `migrations/pg/`; never replay the SQLite chain on PG.
- **Repository layer:** atomic edge + flip on the status PATCH (§3.4, PI-030 pattern); edge-deletion guard (I4); evidence insert validation (I9); the `latest=true` list filter (§4.5).
- **API:** the two `utilization-evidence` endpoints + nested reads; 422 error shapes for I2/I3 refusals.
- **`change_log`:** evidence writes log under a new `utilization_evidence` entity type — include it in `ENTITY_TYPES` (or the change-log admitted set) and the CHECK rebuild above.
- **Per-entity spec amendments:** a §3.4 note in each affected spec pointing here; supersede the §3.4.4 "rejection via soft-delete" guidance per §3.5.
- **UI (deferred follow-on):** status filter values gain `rejected`; an evidence sub-panel on candidate detail panes is a monitoring nicety, not part of this scope.

## 7. Open Questions and Deferred Decisions

- **`process` lifecycle status** (§3.1): recommended follow-on decision — add `process_status` with this four-status lifecycle so process candidates triage uniformly. Until then, dropped process candidates are soft-deleted with a `references`-kind Decision link.
- **Persona/process typed metrics:** their evidence currently lives wholly in `evidence_detail`; promote typed columns (e.g. role member count, last-login recency) when a triage query needs them indexed.
- **Migration-mapping records** (Master PRD §8): out of scope here; the keep/transform mapping record type remains a pending schema decision and does not block D1/D2.
- **Batch POST for the deposit path** (§4.5): implementation option, decided at build time.
- **Evidence retention:** snapshots accumulate indefinitely by design; a pruning policy is deferred until drift detection defines what history it needs.

## 8. Cross-References

- Master CRMBuilder PRD v0.2 — §7 Phase 1.5, §8 Phase 3 baseline triage, and the two pending decisions this spec resolves (`specifications/master-crmbuilder-PRD.md`)
- DEC-047 (three-status propose-verify lifecycle), DEC-046 (parent-prefix naming), DEC-048 (relationship-kind naming), DEC-006 (references-first discipline)
- PI-030 slice A (atomic edge + status flip — the `resolves` precedent for §3.4)
- v0.7 governance enforcement patterns (supersession-requires-edge, consumed-requires-edge — the precedent for I3/I4)
- `change_log` / `identifier_reservations` models (the mechanical-table precedent for §4.2)
- PI-α dialect posture (`JSONColumnNoneAsNull`, dual-head migrations) — `pi-alpha-postgres-foundation-architecture.md`
- Per-entity specs amended by this design: `domain.md`, `entity.md`, `field.md`, `persona.md`, `requirement.md`, `manual_config.md`, `test_spec.md`, and (recommendation only) `process.md`

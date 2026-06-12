# Methodology Design Spec — EspoCRM Data-Profiling Pass

**Last Updated:** 06-11-26
**Status:** Draft v1.0 — produced under WTK-096 (Development-area spec deliverable for the Phase 1.5 data profiler)
**Position in workstream:** Third spec of the Phase 1.5 baseline family. `candidate-lifecycle-rejected-and-utilization-evidence.md` (WTK-088) defined *where* utilization evidence lives; `audit-report-to-candidate-deposit-transform.md` (WTK-090) defined *how candidates enter* and fixed the `utilization-profile.json` consumer contract (§2.2 there) while naming the profiler itself out of scope. This spec defines the profiler: the **second audit pass** that reads record data from an EspoCRM source over its REST search/count endpoints and produces that profile — per-entity record counts and creation recency, per-field population rates, actual enum value distribution versus declared options, and dormant-entity detection. Spec only — no code ships with this document.
**Companion documents:** `audit-report-to-candidate-deposit-transform.md` (WTK-090 — §2.2 output contract, §5 evidence mapping); `candidate-lifecycle-rejected-and-utilization-evidence.md` (WTK-088 — §4.3 metric columns, §4.6 triage queries Q1–Q3 that fix the thresholds); `specifications/master-crmbuilder-PRD.md` §7 (Phase 1.5 Activity 2: "Schema shows what was built; data shows what is used"); `PRDs/product/features/feat-audit.md` (the V1 Audit feature whose schema-discovery pass this sequences after).

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 06-11-26 | ADO Area Specialist (access) / Claude | Initial draft under WTK-096. Defines the profiler as a second pass over the schema-discovery work-list (the `AuditReport` / `audit-report.json` manifest), the precise metric formulas including the `last_populated_at` created-at proxy and the per-type populated predicate, the hybrid count-query/scan REST strategy with a per-field-type where-clause table and automatic count→scan fallback, deterministic pagination and the recency-biased sampling cap, dormancy thresholds aligned to the WTK-088 triage queries (365 days, 0.05), the serial-request retry/backoff error model with metric/entity/run failure tiers, the read-only invariant, and the additive extensions to the WTK-090 §2.2 profile contract. |

---

## Change Log

**Version 1.0 (06-11-26):** Initial creation. §10 enumerates the build surface for the implementing Work Tasks.

---

## 1. Purpose and Position

Master CRMBuilder PRD v0.2 §7 Activity 2:

> **Profile the data.** For each discovered entity and field: record counts, creation recency, per-field population rate, actual enum value usage, dormant entities. Schema shows what was built; data shows what is used.

Its Known Limitations name the gap: "The data profiler (population rates, recency, value distributions) is not yet built."

The profiler is the evidence half of Phase 1.5. The schema-discovery pass (the existing V1 Audit, `espo_impl/core/audit_manager.py`) answers *what was built*; this pass answers *what is used*, and its output is what makes Phase 3 triage decidable ("this field is on 87% of your contacts" / "this field hasn't been filled in since 2024" — Master PRD §8 conduct). Downstream, the WTK-090 transform copies the profile's metrics into the typed `utilization_evidence` columns (WTK-088 §4.3), and the WTK-088 §4.6 triage queries (Q1 low-population, Q2 dormant-entity, Q3 ghost-options) read them by name. Every metric this spec defines therefore traces to a typed evidence column or a named `evidence_detail` key — the profiler computes nothing the triage layer cannot consume.

Three properties are structural, not procedural:

- **Read-only.** The profiler issues `GET` requests exclusively — never `POST`, `PUT`, `PATCH`, or `DELETE`. The source is a witness (Master PRD §7); a profiler that writes to it has corrupted the witness. This matches the Audit feature's `role: source` posture.
- **Schema-driven.** The profiler never discovers schema. Its work-list — which entities, which fields, which declared enum options — comes entirely from the schema-discovery pass's output. A field the audit did not capture is not profiled.
- **Mechanical.** No keep/drop judgment. Dormancy flags (§5) are advisory derivations from raw metrics; the raw metrics always travel with them so triage can re-derive under different thresholds.

---

## 2. Sequencing After the Schema-Discovery Pass

### 2.1 The two-pass shape

A Phase 1.5 audit run against an EspoCRM source has two passes over the same connection:

1. **Pass 1 — schema discovery** (exists today): `AuditManager.run_audit()` produces the `AuditReport` aggregate and, per WTK-090 §2.1, serializes it as `audit-report.json` in the audit output directory.
2. **Pass 2 — data profiling** (this spec): consumes the pass-1 result as its work-list, queries the source's record search/count endpoints, and writes `utilization-profile.json` **alongside** `audit-report.json` in the same output directory.

Pass 2 runs strictly after pass 1 completes, in the same run, against the same `InstanceProfile`. The work-list handoff is in-memory when the passes share a process (the `AuditReport` object) and via the manifest file when they don't (§2.3 standalone mode) — the two are equivalent by construction since the manifest is a direct serialization of the aggregate.

**Work-list derivation from the report:**

- **Entities to profile:** every `EntityAuditResult` in the report, custom and native alike. The WTK-090 §3.1 skipped-native rule is a *transform* rule, not a profiler rule — a bare native entity's record count and recency still inform the Baseline Report even though no candidate is deposited for it. The wire name used in queries is `espo_name`.
- **Fields to profile per entity:** every `FieldAuditResult` on the entity (wire name: `api_name`). Native stock fields are not in the report unless `include_native_fields` was set, so the profiler inherits the audit's scope decision for free.
- **Relationship endpoints:** each `RelationshipAuditResult` side whose entity is profiled contributes one link-shaped profiling target (§4.3 attribute resolution), keyed by its `link` / `link_foreign` wire name. Deduplicated against `FieldAuditResult` entries by wire name within the entity, mirroring WTK-090 §3.3.
- **Declared enum options:** from each enum/multiEnum field's `properties["options"]`. `declared_option_count` is computed from the manifest, not queried — the schema pass already owns that fact.

### 2.2 Run integration

A new `AuditOptions.include_data_profile: bool = True` gates pass 2, default **on** — matching the DEC-180 precedent that the audit's identity is full-configuration capture; the first v1.x run with the profiler built produces utilization evidence without intervention. The entity restriction (`selected_entities`) applies to pass 2 transitively through the report. Pass-2 failure is **non-fatal to pass 1's output**: the YAML and `audit-report.json` stand; a profiler abort (§7.4) leaves either no `utilization-profile.json` or a partial one with `anomalies` recording the abort — the WTK-090 transform runs in schema-only mode either way (its §2.2: the profile is an *optional* second input).

### 2.3 Standalone re-profile mode

The profiler is also runnable on its own, taking an existing `audit-report.json` plus an instance profile, producing a fresh `utilization-profile.json` with a new `profiled_at`. This is the **drift check** WTK-088 §4.3 designed for (`evidence_deposit_event_identifier` is nullable: "a standalone re-profile may run outside a deposit") and what makes the WTK-090 §5 re-observation path ("we dropped this field in triage and the source shows it still being populated") operational without re-running schema discovery. Entities or fields in the manifest that no longer exist on the source at re-profile time produce per-target anomalies (§7.3) and are omitted from the profile — disappearance is itself the signal, and the evidence trail going stale is how triage reads it (WTK-090 §7 rule 4).

### 2.4 Snapshot semantics

The profile carries **one** top-level `profiled_at` (ISO 8601 UTC), captured when pass 2 starts. Per-entity queries execute over wall-clock minutes on a live system, so the profile is a *smeared* snapshot — per-entity counts are each internally consistent (one query) but not mutually transactional. This is accepted: triage thresholds operate at month granularity, and the alternative (freezing the source) violates read-only mechanics. The smear bound is recorded as `completed_at` at top level; consumers needing the precise read time of one entity find it in that entity's `detail.profiled_entity_at`.

---

## 3. Metric Definitions

All formulas below are exact definitions; §4 defines how each is obtained over REST. Names match the WTK-090 §2.2 contract keys, which in turn feed the WTK-088 §4.3 evidence columns of the same stem.

### 3.1 The populated predicate

`populated(field, record)` — the single predicate every field metric builds on — is **type-shaped**:

| Field shape (wire types) | `populated` iff |
|---|---|
| scalar string (`varchar`, `text`, `wysiwyg`, `email`, `phone`, `url`, `enum`, `date`, `datetime`, `datetimeOptional`) | value is non-NULL and non-empty after trim |
| numeric (`int`, `float`, `autoincrement`) | value is non-NULL (zero **is** populated — 0 is a real answer) |
| `currency`, `currencyConverted` | the amount attribute is non-NULL |
| `bool` | **always** — see below |
| array-shaped (`multiEnum`, `checklist`, `array`) | the array is non-NULL and non-empty |
| link (`link`, `linkOne`, `foreign`) | the foreign-id attribute is non-NULL |
| `linkParent` | the parent-id attribute is non-NULL |
| `linkMultiple` | at least one linked record exists |
| composite (`personName`, `address`) | **any** component attribute is populated under the scalar-string rule |

**Booleans are excluded from population-rate signal.** An EspoCRM bool column defaults to false and is never NULL in practice; `population_rate` would read 1.0 universally and pollute the Q1 low-population query with false negatives, or read as garbage if defined over trueness. Instead: `populated_count` = `record_count`, `population_rate` = `1.0` (definitionally), and the *useful* signal — the true-count — is recorded in `detail.value_distribution` as `{"true": n, "false": record_count − n}`. A bool field that is never true on any record is a dormancy candidate via the distribution, which is the honest framing of that fact.

The count-query strategy (§4.2) approximates the scalar-string predicate by non-NULL alone (EspoCRM's `isNotNull` cannot see empty strings). EspoCRM normalizes empty submissions to NULL in the common path, so the approximation is usually exact; where the scan path (§4.4) runs anyway, it computes the strict predicate and the stricter number wins, with `detail.empty_string_count` recording the delta when nonzero.

### 3.2 Entity-level metrics

| Metric | Definition |
|---|---|
| `record_count` | Total non-deleted records of the entity visible to the audit credential at snapshot time. (EspoCRM's REST layer excludes soft-deleted rows by construction; "visible to the credential" is restated in §7.2 — the audit credential must be admin-level or counts are silently partial.) |
| `last_record_created_at` | `max(createdAt)` over those records; absent (key omitted) when `record_count = 0`. |

### 3.3 Field-level metrics

For a field `f` on entity `E` with `record_count = N`:

| Metric | Definition |
|---|---|
| `populated_count` | `count(r ∈ E : populated(f, r))` |
| `population_rate` | `populated_count / N`, rounded to 3 decimal places; **omitted when `N = 0`** (no records means no evidence about the field either way — an empty entity must not read as "all fields 0% populated"; the entity-level dormancy flag carries the finding) |
| `last_populated_at` | `max(createdAt)` over records where `populated(f, r)`; omitted when `populated_count = 0` |
| `distinct_value_count` | count of distinct values among populated records. For enum: distinct declared-or-observed scalar values. For multiEnum/checklist/array: distinct *elements* across all arrays. For links: distinct foreign ids. For other types: distinct normalized scalar values (trimmed; case-preserved). |

**`last_populated_at` is a defined proxy, by design.** EspoCRM stores no per-field write timestamp; the true "most recent write of a non-empty value" (WTK-088 §4.3's gloss) is recoverable only from the audit/stream log, which is partial (only audited fields) and expensive. The profiler defines `last_populated_at := max(record createdAt | field populated)` — which reads as: *no record created after this date carries a value in this field*. That is precisely the triage question ("are new records still getting this field filled?") and is conservative in the right direction: a field back-filled onto old records after creation shows older than reality, prompting a triage probe rather than suppressing one. The proxy choice is recorded in `detail.last_populated_at_basis: "created_at"` so a future audit-log refinement (§11) can change basis without ambiguity. `modifiedAt` was considered and rejected as the basis: a record modified for any unrelated reason would refresh every populated field's timestamp, destroying the dormancy signal.

### 3.4 Enum-usage metrics

For enum/multiEnum/checklist fields, with declared options `O = {o₁ … oₖ}` from the manifest:

| Metric | Definition |
|---|---|
| `declared_option_count` | `k = |O|` (from the manifest — never queried) |
| `used_option_count` | `count(o ∈ O : option_count(o) > 0)` — declared options actually present in data. `declared − used` is the Q3 ghost-option count. |
| `detail.value_distribution` | `{option → count}` for every declared option, including zeros (a zero **is** the ghost-option evidence). For multiEnum, `option_count(o)` counts records whose array contains `o`, so the distribution sums to ≥ `populated_count`. |
| `detail.undeclared_values` | values observed in data but absent from `O` (stale data from removed options, or direct DB writes) — `{value → count}`, scan-derived (§4.4), capped at 50 entries by descending count. Undeclared values count toward `distinct_value_count` but **not** `used_option_count` (which is defined over declared options); their presence is a structural oddity for the gaps-and-ghosts list. |

### 3.5 Non-enum distributions

For non-enum fields the full distribution is unbounded; the profiler records `detail.top_values` — the top 10 values by count among populated records, scan-derived — for fields whose `distinct_value_count ≤ 100` (a de-facto enum living in a varchar is real triage signal: "this free-text field has 6 values — should it be a dropdown?"). Above 100 distinct, `top_values` is omitted as noise. Distinct tracking itself is capped at 1,000 per field; at the cap, `distinct_value_count` is reported as the cap value with `detail.distinct_overflow: true`.

---

## 4. REST Query Strategy

### 4.1 The list endpoint and the count idiom

Everything the profiler needs comes from one EspoCRM surface: the record list endpoint,

```
GET {api_url}/{Entity}?maxSize=…&offset=…&select=…&orderBy=…&order=…&where[0][type]=…&where[0][attribute]=…&where[0][value]=…
```

which returns `{"total": <int>, "list": [...]}`. Two derived idioms:

- **Count query:** `maxSize=0` — returns `total` with an empty list; no record payload crosses the wire. (Fallback: a server build that rejects `maxSize=0` gets `maxSize=1&select=id`; detected once per run on the first count query and remembered.)
- **Recency query:** `orderBy=createdAt&order=desc&maxSize=1&select=id,createdAt` (+ optional `where`) — returns the newest matching record's `createdAt` in one row.

The client surface is two new generic methods on `EspoAdminClient` (§10): `count_records(entity, where=None) → (status, total)` and `list_records(entity, select, where=None, order_by=None, order=None, offset=0, max_size=200) → (status, body)`, both routed through the existing `_request` (inheriting its sentinel-body error contract, §7).

### 4.2 Count mode — the default path

Per entity `E`, in order:

1. `record_count`: count query, no where.
2. `last_record_created_at`: recency query, no where. Skipped when `record_count = 0`.
3. Per field `f`: `populated_count`: count query with the **populated-where** from the table below.
4. Per field `f` with `populated_count > 0`: `last_populated_at`: recency query with the same populated-where.
5. Per enum/multiEnum field, per declared option `o`: `option_count(o)`: count query with the **option-where** below.

**Populated-where and option-where by wire type:**

| Wire type | Populated-where | Option-where |
|---|---|---|
| scalar string, `date`, `datetime`, `datetimeOptional` | `isNotNull` on `f` | — |
| `enum` | `isNotNull` on `f` | `equals` on `f`, value `o` |
| `int`, `float`, `autoincrement` | `isNotNull` on `f` | — |
| `currency`, `currencyConverted` | `isNotNull` on `f` (the amount attribute carries the field name) | — |
| `bool` | none — `populated_count := record_count` (§3.1); true-count via `isTrue` on `f` | — |
| `multiEnum`, `checklist`, `array` | `arrayIsNotEmpty` on `f` | `arrayAnyOf` on `f`, value `[o]` |
| `link`, `linkOne`, `foreign` | `isNotNull` on `{f}Id` | — |
| `linkParent` | `isNotNull` on `{f}Id` | — |
| `linkMultiple` | `isLinked` on `f` | — |
| `personName` | `isNotNull` on `lastName` (then scan refines per §3.1 any-component rule) | — |
| `address` | `isNotNull` on `{f}City` (then scan refines) | — |

Any count/recency query answering **400** (a where type unsupported for that attribute on that server build) triggers the **count→scan fallback** for that metric: the metric is computed from the scan pass instead, and a metric-level anomaly records the downgrade (§7.3). The table is a starting map, not a wall — the fallback means an entry being wrong on some EspoCRM version degrades one metric to scan-derived, never fails the field.

Count mode is preferred wherever it suffices because it is *exact at any scale* (the server counts; sampling never applies), transfers near-zero payload, and needs no value handling. Its limits are exactly two: it cannot see inside values (distinct counts, undeclared values, top values, empty-string refinement) and it costs one request per metric.

### 4.3 Request budget

Per entity: `2 + F + P + Σ option-counts`, where `F` = profiled fields (one populated-count each), `P` = fields with nonzero population (one recency each, ≤ F). Worked example — a CBM-scale entity with 40 fields, 5 enums × 7 options: `2 + 40 + ~35 + 35 ≈ 112` requests; a 20-entity source lands around 1,500–2,500 requests. At the serial-request default with a healthy local instance (~20–50 req/s observed against the deploy-validation instance) that is one to two minutes; against a slow remote, the throttle and the per-entity progress callback (§10) keep it observable. The budget is linear in schema size, **independent of record count** — count mode's defining property. The scan pass (next) is the only record-count-sensitive component, and it is capped.

### 4.4 Scan mode — the value-inspection pass

One paged read per entity supplies everything count mode cannot:

```
GET /{Entity}?select=id,createdAt,{profiled field attributes}&orderBy=createdAt&order=desc&maxSize=200&offset=…
```

- **Page size** 200 (the codebase's existing convention — `get_teams`/`get_roles`); the server may clamp lower, so the loop advances `offset` by `len(list)` (not by the requested size) and terminates when `offset ≥ total` or a page returns empty. `orderBy=createdAt&order=desc` makes pagination deterministic and puts the newest records first, which is what makes the sampling cap (§4.5) recency-biased by construction. Records created *during* the scan can shift the window by at most the insertion count — accepted under §2.4 smear semantics.
- **Computed from the scan:** `distinct_value_count`, `detail.undeclared_values`, `detail.top_values`, the §3.1 empty-string and any-component refinements, and any metric downgraded by count→scan fallback (including, when so downgraded, `populated_count`/`last_populated_at` recomputed under the strict predicate from the scanned rows).
- **Select-list discipline:** only profiled-field attributes are requested (component attributes for composites, `{f}Id` for links). `linkMultiple` fields are **excluded from the select** — EspoCRM materializes `{f}Ids` only on detail reads, not reliably on list reads, and per-record link expansion is an N×L request explosion; `linkMultiple` distinct-target counting is therefore out of scope v1 (its `populated_count` comes from the `isLinked` count query, which suffices for Q1).
- **Skip rule:** entities where no scan-derived metric is needed (no enum with undeclared-value interest, no non-enum field, no fallback triggered — rare but possible for tiny link-only entities) skip the scan entirely.

### 4.5 Sampling cap

The scan is exact up to `scan_cap` records per entity (default **10,000** = 50 pages at 200; configurable). Beyond the cap the scan stops and the scanned prefix — the **most recent `scan_cap` records by `createdAt`** — becomes the sample:

- Scan-derived *rates* (the strict-predicate refinements) are reported from the sample as-is.
- Scan-derived *counts* (`distinct_value_count`, undeclared/top-value counts) are reported as observed in the sample — never extrapolated; a sampled distinct count is a floor, and `detail` says so.
- Count-mode metrics are **unaffected** — they were never scan-derived, so `record_count`, `populated_count`, `population_rate`, `last_populated_at`, and all enum option counts stay exact at any scale. This split is why the hybrid exists: the WTK-088 typed columns (what triage queries by name) are exact; only the `evidence_detail` depth degrades to sampled.
- The entity's `detail` records `{"sampled": true, "scan_count": 10000, "sample_fraction": 0.21, "sample_basis": "most_recent_by_created_at"}`. The recency bias is deliberate: triage asks about *current* practice, and the newest records answer it; the bias is named so a reader of an 8-year-old archive entity's profile knows the early years went unscanned.

---

## 5. Dormancy and Triage Flags

Thresholds align with the WTK-088 §4.6 queries so the profiler's advisory flags and the evidence-layer queries can never disagree:

| Flag | Definition | Default threshold | WTK-088 anchor |
|---|---|---|---|
| `detail.dormant` (entity) | `record_count = 0` **or** `last_record_created_at < profiled_at − dormancy_window` | `dormancy_window` = 365 days | Q2 (`:twelve_months_ago`) |
| `detail.empty` (entity) | `record_count = 0` (subset of dormant, flagged separately — "never used" and "no longer used" are different triage conversations) | — | Q2 first disjunct |
| `detail.low_population` (field) | `population_rate < low_population_threshold` (only when `population_rate` is present, §3.3) | 0.05 | Q1 |
| `detail.stale` (field) | `populated_count > 0` and `last_populated_at < profiled_at − dormancy_window` — "hasn't been filled in since…" | 365 days | Master PRD §8 conduct line |
| `detail.ghost_options` (enum field) | `declared_option_count − used_option_count`, when > 0 | — | Q3 |

Both thresholds are profiler options (`dormancy_window_days: int = 365`, `low_population_threshold: float = 0.05`). Flags are **advisory and re-derivable**: every flag's inputs are typed metrics in the same profile, so triage (or a re-rendered Baseline Report) can re-derive under different thresholds without re-profiling. The profiler never suppresses a record or field on account of a flag — mechanical capture, no judgment (§1).

---

## 6. Output — the `utilization-profile.json` Contract

The output is the WTK-090 §2.2 contract, verbatim, with additive keys only. `manifest_version` stays `1`; additions are optional keys a version-1 consumer ignores (the transform reads named keys, never iterates exhaustively).

```json
{
  "manifest_version": 1,
  "profiled_at": "2026-06-11T18:00:00Z",
  "completed_at": "2026-06-11T18:03:41Z",
  "source_url": "https://crm.cbmentors.org",
  "source_label": "espocrm @ crm.cbmentors.org",
  "profiler_version": "<espo_impl distribution version>",
  "options": {"dormancy_window_days": 365, "low_population_threshold": 0.05, "scan_cap": 10000},
  "anomalies": [
    {"scope": "metric", "entity": "CEngagement", "field": "legacyCode",
     "metric": "populated_count", "status": 400,
     "note": "isNotNull rejected for attribute; metric scan-derived"}
  ],
  "entities": {
    "CEngagement": {
      "record_count": 412,
      "last_record_created_at": "2026-06-09T14:22:00Z",
      "detail": {"profiled_entity_at": "2026-06-11T18:00:04Z", "dormant": false, "empty": false,
                  "sampled": false, "request_count": 96},
      "fields": {
        "engagementStage": {
          "populated_count": 398, "population_rate": 0.966,
          "last_populated_at": "2026-06-09T14:22:00Z",
          "distinct_value_count": 5,
          "declared_option_count": 7, "used_option_count": 5,
          "detail": {"value_distribution": {"active": 211, "paused": 9, "...": 0},
                      "undeclared_values": {}, "ghost_options": 2,
                      "last_populated_at_basis": "created_at"}
        }
      }
    }
  }
}
```

Shape rules: top-level and per-entity/per-field `detail` objects hold everything not in the §2.2 typed key set, mirroring WTK-088's typed-columns-plus-`evidence_detail` split — a metric is promoted out of `detail` only when the consumer contract promotes it. Keys defined as "omitted" in §3 are absent, not null. Entity keys are EspoCRM wire names (`espo_name`); field keys are wire `api_name` — exactly the keys the transform joins on. Entities skipped by entity-level failure (§7.3) are absent from `entities` and present in `anomalies`. The file is written atomically (temp file + rename) at pass end; a partial run that aborts before the write leaves no profile (§2.2 non-fatality covers the consequence).

---

## 7. Error Handling, Rate Limits, and Failure Tiers

### 7.1 Transport and retry

All requests route through `EspoAdminClient._request`, inheriting the sentinel-body contract (status `-1` + `_request_failed` on transport failure; `_parse_failed` on non-JSON). On top of it the profiler adds one retry policy, applied per request:

- **Retryable:** transport sentinels (connection/timeout), HTTP 429, 502, 503, 504. Backoff 1 s, 2 s, 4 s, 8 s, 16 s (5 attempts total); a `Retry-After` header, when present and larger, wins over the computed delay. Stock EspoCRM does not rate-limit, but reverse proxies and hosting layers in front of real instances do — 429/`Retry-After` handling is for them.
- **Not retryable:** 400 (semantic — triggers count→scan fallback, §4.2), 401/403 (auth/ACL — tier rules below), 404 (target gone — §2.3 anomaly).
- **Pacing:** requests are strictly serial on one `requests.Session` (connection reuse for free), with an optional `throttle_seconds: float = 0.0` inter-request sleep for operator-imposed politeness against shared production instances. No concurrency in v1 — the budget (§4.3) doesn't need it, and serial is trivially within any proxy's comfort. Parallel per-entity profiling is a named deferral (§11).

### 7.2 Run preconditions

Before pass 2 starts: one probe count query against the first work-list entity. A 401 here aborts the pass (credentials died between passes); a 403 falls through to the entity tier below. The profiler also restates the audit's standing assumption: the credential must be admin-level — EspoCRM applies ACL to list/count results silently, so a scoped credential yields *wrong counts, not errors*. The probe cannot detect this; the precondition is documentation plus the instance-profile `role: source` admin convention, and `apply_context` already carries the credential identity for forensics.

### 7.3 Failure tiers

| Tier | Trigger | Behavior |
|---|---|---|
| **Metric** | 400 on a count/recency query; scan unable to compute (e.g. attribute absent from list payload); retries exhausted on a *non-first* query of a field | Metric omitted or scan-derived per §4.2 fallback; anomaly row `scope: "metric"`; field keeps its other metrics. |
| **Entity** | 403 on the entity; 404 (deleted since pass 1); retries exhausted on the entity's `record_count` query | Entity omitted from `entities`; anomaly row `scope: "entity"`; run continues with the next entity. |
| **Run** | 401 anywhere; retries exhausted on ≥ 3 consecutive entities (the instance is down, not flaky) | Pass aborts. If ≥ 1 entity completed, the partial profile **is** written, with `anomalies` carrying `scope: "run"` and the unprofiled remainder listed; otherwise no file. |

Anomalies are carried in the profile itself (§6) and surfaced by the caller into the audit's existing `warnings` stream, which the WTK-090 transform already folds into its per-run anomaly Planning Item (§3.6 there) — the profiler does not write Planning Items; it is upstream of the deposit path.

### 7.4 Idempotency

The profiler is trivially re-runnable: read-only against the source, and its output is a whole-file atomic write keyed by nothing. Two runs produce two profiles distinguished by `profiled_at`; the evidence layer's latest-snapshot rule (WTK-088 §4.4) makes the newer one current. There is no resume-within-a-run — at ~minutes of wall clock and full idempotency, re-running is the resume mechanism.

---

## 8. Where the Code Lives

The profiler is **espo_impl-side**, not crmbuilder_v2-side: it speaks the EspoCRM wire protocol, reuses `EspoAdminClient`/`InstanceProfile`, and is the natural pass 2 of the existing Audit feature. The WTK-090 §2.1 package boundary is preserved exactly — `espo_impl` produces `utilization-profile.json`; `crmbuilder_v2` consumes it; neither imports the other; the JSON file is the interface, and this spec plus WTK-090 §2.2 are its contract.

- **Module:** `espo_impl/core/data_profiler.py` — `ProfileOptions` (thresholds, `scan_cap`, `throttle_seconds`), `DataProfiler(client, report, options)` with `run() → UtilizationProfile`, and pure metric/predicate functions (`populated_where_for(field)`, the §3.1 predicate, flag derivations) kept free of HTTP so they unit-test without a client — mirroring the manager/pure-function split used across `espo_impl/core`.
- **Client additions:** `EspoAdminClient.count_records` and `list_records` (§4.1) — generic, profile-agnostic; `search_by_email` becomes expressible through `list_records` but is left untouched (no refactor rider on this work).
- **Audit integration:** `AuditManager.run_audit` invokes the profiler after report assembly when `include_data_profile`, writing the profile beside `audit-report.json`; profiler warnings merge into `AuditReport.warnings`. The audit UI exposes the flag as one checkbox ("Profile record data") in the existing audit options group.
- **Worker path:** pass 2 runs inside the existing `audit_worker.py` QThread; the per-entity progress callback drives the existing log-line convention (`Profiling CEngagement… 412 records, 41 fields`).

---

## 9. Verification Criteria

Metric/predicate functions verify offline (pure-unit); the REST strategy verifies against a mocked `EspoAdminClient` (the codebase's standing test idiom) with canned `{total, list}` bodies; end-to-end shape verifies by feeding the produced profile to the WTK-090 T6 fixture path. The implementation is correct when:

**P1 — Metric exactness on a small fixture.** A mocked entity (12 records; one varchar populated on 9, one enum with options A–G populated A×5/B×3/C×1, one multiEnum, one link, one bool true×4, one empty field) yields exactly: `record_count` 12, the §3.3 metrics per field, `used_option_count` 3, `ghost_options` 4, distribution including declared zeros, bool distribution `{true: 4, false: 8}` with `population_rate` 1.0.

**P2 — Populated predicate per type.** Each row of the §3.1 table holds, including: numeric zero populated; empty-string scan refinement decrementing the count-mode number with `empty_string_count` recorded; composite any-component; `population_rate` omitted (not 0, not null) for a zero-record entity.

**P3 — Recency proxy.** `last_populated_at` equals the max `createdAt` among populated records — not `modifiedAt`, not max over all records; omitted when `populated_count` 0; `last_populated_at_basis` present.

**P4 — Dormancy boundaries.** Entities/fields exactly at threshold edges (last creation `profiled_at − 365d ± 1s`; rate 0.05 exactly — not flagged; 0.049 — flagged) flag per §5; flags re-derivable from the typed metrics in the same profile.

**P5 — Pagination.** A 950-record scan at page size 200 issues pages at offsets 0/200/400/600/800, advances by returned length when the server clamps to 100, and terminates on short page; deterministic order asserted.

**P6 — Sampling cap.** 25,000 records with `scan_cap` 10,000: count-mode metrics exact (from mocked `total`s), scan-derived metrics from the newest 10,000 only, `sampled`/`sample_fraction`/`sample_basis` recorded, no extrapolation.

**P7 — Count→scan fallback.** A 400 on one field's populated-where downgrades exactly that metric to scan-derived, records a metric-scope anomaly, leaves sibling fields count-derived.

**P8 — Failure tiers.** 403 on one entity → entity omitted + anomaly + run continues; 401 mid-run → abort, partial profile written with run-scope anomaly when ≥ 1 entity completed; 429 with `Retry-After: 3` → honored; 3 consecutive entity-level retry exhaustions → run abort.

**P9 — Read-only invariant.** The full P1–P8 suite records every request method; all are GET. (Cheap to assert with the mocked client; the invariant worth a permanent regression tripwire.)

**P10 — Contract round-trip.** A produced profile validates against the WTK-090 §2.2 consumer expectations: the transform's T6 ("evidence with profile") consumes it unmodified; wire-name keys join against the manifest; a version-1 consumer ignoring the additive keys loses nothing typed.

---

## 10. Build Surface (for the implementing Work Tasks)

This spec ships no code. In dependency order:

1. **`EspoAdminClient.count_records` / `list_records`** (§4.1), with the `maxSize=0` fallback probe; unit tests against the mocked session.
2. **`espo_impl/core/data_profiler.py`** (§8): predicate/metric pure functions first (P1–P4 offline), then `DataProfiler.run()` with the §4 strategy and §7 tiers (P5–P9 mocked).
3. **Audit integration:** `AuditOptions.include_data_profile`, the `run_audit` hook, profile write beside `audit-report.json`, warning merge, UI checkbox, worker progress lines (§8). Sequenced with — but independent of — the WTK-090 build's `audit-report.json` writer (its build item 4); the two passes share the output directory, not code.
4. **Contract fixture:** one canonical produced profile checked in as the WTK-090 T6 input fixture (P10), so transform and profiler builds stay pinned to the same bytes.
5. **Out of scope here:** the Baseline Report renderer (consumes the profile downstream); the spreadsheet source adapter (Master PRD §7 Known Limitations — its profiler parity is §11); the transform's evidence mapping (WTK-090 §5 owns it); any audit-log-based recency refinement.

---

## 11. Open Questions and Deferred Decisions

- **Audit-log recency refinement** (§3.3): EspoCRM's stream/audit log could give true per-field write times for audited fields. Deferred — partial coverage, expensive reads, and the created-at proxy already asks the right triage question. The `last_populated_at_basis` key is the forward-compatibility hook.
- **Parallel per-entity profiling** (§7.1): serial is fine at the §4.3 budget; revisit only if multi-hundred-entity sources appear. Concurrency would need per-host politeness limits the serial design gets for free.
- **`linkMultiple` value depth** (§4.4): distinct-target counts and per-target distributions are excluded v1 (list-read materialization is unreliable). The `isLinked` populated-count suffices for Q1; revisit if triage wants relationship-fanout evidence.
- **Scoped-credential detection** (§7.2): a non-admin credential silently under-counts. A heuristic tripwire (compare one entity's count under two select shapes, or probe an admin-only endpoint) was considered and deferred — the instance-profile convention plus documentation covers the dogfood and CBM cases.
- **Spreadsheet adapter parity:** when the CSV/Sheets source adapter lands, its profiler should emit the same `utilization-profile.json` contract so the transform stays adapter-blind. The §3 metric definitions are already source-agnostic; only §4's query strategy is EspoCRM-specific. This spec's §3/§5/§6 should be lifted, not re-derived, when that adapter is specified.
- **Threshold provenance:** the 365-day window and 0.05 rate are inherited from WTK-088's queries, which inherited them from the Master PRD's narrative ("hasn't been filled in since 2024", "low population"). If triage practice tunes them, the WTK-088 queries and the §5 defaults must move together — they are one fact in two places, both tracing here.

---

## 12. Cross-References

- `audit-report-to-candidate-deposit-transform.md` (WTK-090) — §2.1 manifest boundary, §2.2 profile contract (the normative consumer), §3.6 anomaly PI, §5 evidence mapping, T6 fixture
- `candidate-lifecycle-rejected-and-utilization-evidence.md` (WTK-088) — §4.3 evidence columns, §4.4 latest-snapshot rule, §4.6 queries Q1–Q3 (threshold anchors)
- `specifications/master-crmbuilder-PRD.md` v0.2 — §7 Phase 1.5 (Activity 2, phase rules, Known Limitations this spec closes), §8 evidence-led triage conduct (commit `9681039`)
- `espo_impl/core/audit_manager.py` — `AuditOptions`, `AuditReport` and component dataclasses (the pass-1 work-list shape); `espo_impl/core/audit_utils.py` — `EntityClass` / `FieldClass`
- `espo_impl/core/api_client.py` — `EspoAdminClient._request` (sentinel-body error contract), `search_by_email` (the existing where-clause idiom §4.1 generalizes), `get_teams`/`get_roles` (the `maxSize=200` page-size convention)
- `PRDs/product/features/feat-audit.md` — the V1 Audit feature (pass 1; transitional reference per Master PRD §7 Inputs)

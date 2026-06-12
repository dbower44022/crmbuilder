# Methodology Design Spec — Utilization Evidence Inline on Baseline Candidates

**Last Updated:** 06-11-26
**Status:** Draft v1.0 — produced under WTK-097 (storage-area spec deliverable for the Phase 1.5 candidate-inline evidence contract)
**Position in workstream:** Fourth spec of the Phase 1.5 baseline family. `candidate-lifecycle-rejected-and-utilization-evidence.md` (WTK-088) defined *where* utilization evidence is stored (the `utilization_evidence` child table); `audit-report-to-candidate-deposit-transform.md` (WTK-090) defined *how the deposit path attaches it* to the candidates it writes; `espocrm-data-profiling-pass.md` (WTK-096) defined *how the metrics are computed*. This spec closes the remaining contract: the **candidate-inline shape** — the single normalized evidence object that travels with a candidate everywhere a candidate is read (deposit plan, API reads, Baseline Report, triage), the normative `evidence_detail` key schema per subject type that the three prior specs left informal, the consolidated versioning/idempotency rules when a profile is re-run, and the acceptance criteria that make Phase 3 keep/transform/drop triage decidable from this evidence alone. Spec only — no code ships with this document.
**Companion documents:** `candidate-lifecycle-rejected-and-utilization-evidence.md` (WTK-088 — §4 table, §4.4 latest-snapshot rule, §4.5 endpoints, §5.1 queries); `audit-report-to-candidate-deposit-transform.md` (WTK-090 — §5 evidence attachment, §7 re-run rules); `espocrm-data-profiling-pass.md` (WTK-096 — §3 metric definitions, §5 flags, §6 profile contract); `specifications/master-crmbuilder-PRD.md` §7 (Phase 1.5 Activity 2 and 4) and §8 (Phase 3 evidence-led triage conduct).

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 06-11-26 | ADO Area Specialist (storage) / Claude | Initial draft under WTK-097. Reconciles the Master PRD's "evidence inline" phrasing with the WTK-088 child-table storage decision (inline is a transport property, not a storage property — D2 is not reopened). Defines the canonical inline evidence object (typed metrics + advisory flags + detail) projected identically into the transform's dry-run plan, an `include_evidence=latest` API projection on the five candidate endpoint families, and the Baseline Report; fixes the normative `evidence_detail` key schema per subject type with an `evidence_schema_version` discriminator; consolidates re-run versioning (append-only snapshots, latest-per-(subject, source), exact-tie resolution by greatest `id`); and states the eight acceptance criteria (A1–A8) under which triage is decidable from the inline evidence alone. |

---

## Change Log

**Version 1.0 (06-11-26):** Initial creation. §9 enumerates the build surface for the implementing Work Tasks. No schema change to the WTK-088 table is required; the one API addition is the read projection in §6.

---

## 1. Purpose and Position

Master CRMBuilder PRD v0.2 §7 states the phase rule this spec serves:

> **Evidence travels with the candidate.** Each candidate carries the utilization evidence that makes triage decidable: field population rate, last-populated date, actual enum value distribution vs. declared options, record counts and recency for entities, standard-vs-custom catalog classification.

and Activity 4: "Write candidate methodology records *with evidence inline*."

The three prior specs built the supply side. What remains unspecified is the **consumption contract**: when a triage session, the Baseline Report renderer, or the desktop UI reads a candidate, what exact structure arrives with it, and what guarantees does that structure carry? Today the answer is scattered — the typed columns are normative (WTK-088 §4.3), but the `evidence_detail` JSON is described only by example in three places, the flags computed by the profiler (WTK-096 §5) have no defined home on the evidence row, and no read path delivers a candidate *with* its evidence in one request. Phase 3's conduct rule — "lead with evidence, not with the item" — needs the evidence in hand at the moment the candidate is in hand.

This spec defines that contract. Three boundaries are fixed up front:

- **WTK-088 D2 is not reopened.** Storage remains the `utilization_evidence` child table; per-candidate inline JSON columns stay rejected for the reasons recorded there (indexability, history, dual-dialect ergonomics). "Inline" in the Master PRD — and in this spec's title — is a **transport property**: evidence arrives with the candidate wherever the candidate is read. The child table is how that property is implemented without paying inline storage's costs.
- **No new metrics.** Every typed metric here is a WTK-088 §4.3 column; every flag is a WTK-096 §5 derivation. This spec arranges them; it does not extend them.
- **No transform changes.** The WTK-090 §5 attachment mapping stands. This spec makes its `evidence_detail` column's contents normative (§4) where WTK-090 listed them informally.

---

## 2. The Inline Principle — One Object, Every Surface

The unit of the contract is the **inline evidence object** (§3): a single normalized JSON shape assembled from one `utilization_evidence` row. The principle: every surface that presents a candidate presents this same object, so a consultant moving between the dry-run plan, the API, the Baseline Report, and the triage UI reads one vocabulary.

| Surface | When | How the object arrives |
|---|---|---|
| Transform plan (`--dry-run`) | Deposit time | Each planned candidate in the plan output carries its to-be-written evidence as an inline object — the operator previews exactly what triage will later read (WTK-090 §6) |
| Candidate API reads | Any time | `include_evidence=latest` projection on the five candidate endpoint families (§6) embeds the latest object(s) in the candidate's `data` payload |
| Evidence API reads | Any time | `GET /utilization-evidence` and the nested per-subject reads (WTK-088 §4.5) return full history; each row renders as one object |
| Baseline Report | Phase 1.5 close | The renderer groups candidates and prints each candidate's object(s); the gaps-and-ghosts list is computed from the flags (§3.3) |
| Triage session | Phase 3 | The consultant's working view per candidate is the object; the §8 criteria define when it suffices to decide a disposition |

The object is a *projection*, not a copy: there is exactly one storage row per snapshot, and every surface derives the object from it deterministically (§3.4). Nothing is denormalized onto the candidate tables.

---

## 3. The Inline Evidence Object

### 3.1 Shape

One object per `utilization_evidence` row:

```json
{
  "subject_type": "field",
  "subject_identifier": "FLD-042",
  "profiled_at": "2026-06-11T18:00:00Z",
  "source_label": "espocrm @ crm.cbmentors.org",
  "deposit_event": "DEP-012",
  "catalog_class": "custom",
  "metrics": {
    "populated_count": 398,
    "population_rate": 0.966,
    "last_populated_at": "2026-06-09T14:22:00Z",
    "distinct_value_count": 5,
    "declared_option_count": 7,
    "used_option_count": 5
  },
  "flags": {
    "low_population": false,
    "stale": false,
    "ghost_options": 2
  },
  "detail": { "…": "§4 normative key schema" }
}
```

- The envelope keys (`subject_type` … `catalog_class`) map 1:1 onto the WTK-088 §4.3 columns of the same stem (`evidence_` prefix dropped in projection). `deposit_event` is `null` for standalone re-profiles.
- **`metrics`** holds exactly the typed metric columns that are non-NULL on the row, key names matching the column stems. Absent metrics are **omitted, not null** — same rule as the WTK-096 profile contract, and for the same reason: "no evidence" and "evidence of zero" must not be confusable. An entity-subject object carries the `record_count` pair; a field-subject object the population trio plus distinct count; an enum field additionally the option pair; a persona/process/manual_config object may have an empty `metrics` (their depth lives in `detail` until WTK-088 §7 promotes typed columns).
- **`flags`** is the advisory triage layer, projected from `detail` (§3.3) — surfaced at top level because the gaps-and-ghosts list and the triage conversation key on them, but stored only once.
- **`detail`** is the row's `evidence_detail` verbatim, per the §4 key schema.

### 3.2 Entity-level vs field-level content

The Work Task's named dimensions land as follows, restating the prior specs' assignments in one table — entity and field are the two evidence-bearing levels with typed metrics; the other three subject types are detail-only in v1:

| Dimension (Master PRD §7) | Entity-subject object | Field-subject object |
|---|---|---|
| Counts | `metrics.record_count` | `metrics.populated_count`, `metrics.distinct_value_count` |
| Recency | `metrics.last_record_created_at` | `metrics.last_populated_at` (created-at proxy; basis named in `detail`) |
| Population rates | — | `metrics.population_rate` (omitted when parent `record_count` = 0) |
| Enum usage | — | `metrics.declared_option_count` / `used_option_count`; full distribution in `detail.value_distribution` |
| Dormancy flags | `flags.dormant`, `flags.empty` | `flags.low_population`, `flags.stale`, `flags.ghost_options` |
| Standard-vs-custom | `catalog_class` | `catalog_class` |

### 3.3 Flags — stored in detail, projected to the top

The WTK-096 §5 flags are computed by the profiler and travel in the profile's `detail` blocks. The transform copies them **verbatim** into `evidence_detail` (no recomputation — the profiler's thresholds, recorded in the profile's `options`, are the thresholds of record for that snapshot, and `detail.thresholds` carries them per §4.1). The projection lifts the flag keys (`dormant`, `empty`, `low_population`, `stale`, `ghost_options`) from `detail` into the object's `flags` block; they remain physically stored once.

Flags are advisory and re-derivable (WTK-096 §5): every flag's inputs are typed metrics on the same row. If a consumer re-derives under different thresholds and disagrees, **the typed metrics win** — a flag is a rendering of the metrics at recorded thresholds, never independent evidence. A schema-only deposit (no profile) has no flags; the `flags` block is then an empty object, which is itself signal (§8 A3).

### 3.4 Determinism

Object assembly is a pure function of one row: drop the `evidence_` prefix, partition non-NULL typed columns into the envelope and `metrics`, lift the five flag keys into `flags`, pass `detail` through. Two surfaces rendering the same row always produce byte-identical objects (modulo key ordering, which serializers fix canonically). This is what makes the §8 criteria testable.

---

## 4. Normative `evidence_detail` Key Schema

WTK-088 §4.3 defined `evidence_detail` as "source-specific depth that doesn't warrant typed columns"; WTK-090 §5 and WTK-096 §6 listed contents by example. This section fixes the keys. Producers (the transform; future source adapters) MUST use these names for these facts; unknown additional keys are permitted (consumers ignore them — the additive posture of the profile contract carries through); a fact listed here MUST NOT travel under a different name.

### 4.1 Common keys (all subject types)

| Key | Type | Presence | Content |
|---|---|---|---|
| `evidence_schema_version` | int | always | Version of this detail-key schema; starts at `1`. The discriminator that lets the detail shape evolve without guessing (§7.3). |
| `wire_name` | string | always | The source-system identity the candidate was derived from: entity `espo_name`, field `api_name`, role/team `name`, tab `id`. The join key back to the manifest and profile. |
| `wire_type` | string | field subjects | The EspoCRM metadata type before the WTK-090 §3.2 lossy map (`varchar`, `linkMultiple`, …). |
| `profiler_version` / `transform_version` | string | when applicable | Tool identities; `profiler_version` absent on schema-only deposits. |
| `thresholds` | object | when flags present | The profiler options the flags were derived under: `{"dormancy_window_days": 365, "low_population_threshold": 0.05}` (WTK-096 §5). Travels with the flags so re-derivation is always possible from the row alone. |
| `schema_only` | bool | when `true` | Present and `true` when the deposit ran without a profile (WTK-090 §2.2); the explicit marker for "data metrics absent because unprofiled", as opposed to absent-because-empty. |

### 4.2 Entity subjects

| Key | Type | Content |
|---|---|---|
| `dormant`, `empty` | bool | WTK-096 §5 entity flags (lifted into `flags` on projection) |
| `layouts_captured` | array | Layout names the audit captured — the "curated UI" signal (WTK-090 §3.1) |
| `sampled`, `scan_count`, `sample_fraction`, `sample_basis` | per WTK-096 §4.5 | Present when the scan was capped; qualifies the scan-derived depth below, never the typed metrics |
| `profiled_entity_at` | datetime | The precise read time of this entity within the smeared snapshot (WTK-096 §2.4) |

### 4.3 Field subjects

| Key | Type | Content |
|---|---|---|
| `low_population`, `stale`, `ghost_options` | bool / int | WTK-096 §5 field flags (lifted into `flags`) |
| `value_distribution` | object | Enum/multiEnum/bool: `{option → count}` including declared zeros (WTK-096 §3.4) |
| `undeclared_values` | object | Values in data absent from declared options, capped at 50 (WTK-096 §3.4) |
| `top_values` | object | Non-enum top-10 distribution when `distinct_value_count` ≤ 100 (WTK-096 §3.5) |
| `last_populated_at_basis` | string | `"created_at"` — the recency-proxy marker (WTK-096 §3.3) |
| `empty_string_count` | int | Scan refinement delta when nonzero (WTK-096 §3.1) |
| `distinct_overflow` | bool | Present when distinct tracking hit its cap (WTK-096 §3.5) |
| `relationship_pairing` | object | For `reference` fields from a `RelationshipAuditResult`: the opposite side's wire identity (WTK-090 §3.3) |

### 4.4 Persona, process, and manual_config subjects

All depth, no typed metrics in v1 (WTK-088 §4.3 note):

| Subject | Keys |
|---|---|
| `persona` | `kind` (`"role"` / `"team"`), `scope_access` (per-entity access levels, compact), `system_permissions` |
| `process` | `filter` (the structured condition AST, or `null` when unrecoverable), `scope`, `acl`, `nav_order` |
| `manual_config` | `origin` (`"unrecoverable_filter"` in v1), `tab_scope`, `tab_id` |

Promotion of any of these into typed columns follows the WTK-088 §7 rule: a key earns a column when a triage query needs it indexed, by migration, with the detail key retired in the same change.

---

## 5. How the Deposit Path Attaches It

Normative reference: WTK-090 §5 — unchanged. Restated as contract obligations the §8 criteria test:

1. **Every touched candidate, every run.** One evidence row per candidate the run created *or matched*, per run. Evidence is the only thing a re-run always writes.
2. **Detail conformance.** The row's `evidence_detail` follows §4 — this is the one place this spec tightens WTK-090, which listed the contents without fixing names.
3. **Plan-time preview.** The transform's plan object (WTK-090 §6) carries each candidate's evidence as a §3 object, and `--dry-run` prints it. The operator sees at deposit time exactly what triage sees later; a malformed detail block is caught before anything is written.
4. **Flags copied, not computed.** The transform never derives flags; it copies the profile's (§3.3). A transform computing its own flags would create a second threshold authority — the WTK-096 §11 "one fact in two places" warning made structural.

---

## 6. The Inline Read Projection — `include_evidence`

The missing read path: a candidate *with* its evidence in one request.

### 6.1 Surface

The five candidate endpoint families (`/entities`, `/fields`, `/personas`, `/processes`, `/manual-configs`) accept an optional query parameter on both single-record GET and list GET:

| Parameter | Behavior |
|---|---|
| `include_evidence=latest` | Embed the latest snapshot per source (§7.1) — one §3 object per `source_label` — as a `utilization_evidence` key in each record's `data` payload |
| `include_evidence=all` | Embed full history, newest first. Intended for detail views and drift inspection; list endpoints MAY refuse it (422) to bound payloads — single-record GET MUST honor it |
| omitted | Today's payload, byte-identical — the projection is strictly additive and costs nothing when not requested |

Embedded shape, inside the candidate's existing envelope `data`:

```json
"utilization_evidence": {
  "snapshots": [ { "…": "§3 object" } ],
  "snapshot_count": 7,
  "sources": ["espocrm @ crm.cbmentors.org"]
}
```

`snapshot_count` is the subject's total row count (so `latest` consumers see history exists without fetching it); `snapshots` is ordered by `profiled_at` descending. A candidate with no evidence rows gets `{"snapshots": [], "snapshot_count": 0, "sources": []}` — present, empty, and exactly the Q4 completion-gate signal (WTK-088 §5.1) made visible at read time.

### 6.2 Boundaries

- **Read-only and derived.** The projection adds no write path and no storage; WTK-088 I8 (append-only, POST + GET) is untouched.
- **Not a filter.** Triage-scale queries ("all fields under 5%") remain the evidence endpoint's job (`GET /utilization-evidence?subject_type=field&max_population_rate=0.05&latest=true`, WTK-088 §4.5). The projection answers "show me *this* candidate with its evidence", not "find candidates by evidence". Combining candidate-status filters with evidence filters in one query is deferred (§10).
- **Soft-reference semantics.** The join is by `(subject_type, subject_identifier)` per WTK-088 §4.2; a rejected or deferred candidate projects its evidence exactly as a live candidate does (I10 — evidence never participates in lifecycle).
- **Consumers.** The deferred WTK-088 UI evidence sub-panel, the Baseline Report renderer, and triage-session tooling all read this projection rather than assembling their own joins — one implementation of §3.4 determinism.

---

## 7. Versioning and Idempotency on Re-Profile

Consolidating the rules split across WTK-088 §4.4, WTK-090 §7, and WTK-096 §7.4 into the single statement consumers rely on:

### 7.1 Snapshot model

- **Append-only.** A re-profile (with or without a re-deposit) appends rows; nothing is updated or deleted (WTK-088 I8). Candidates are never mutated by re-observation (WTK-090 §7 rule 1).
- **Current = latest per (subject, source).** The current evidence for a subject is the greatest `evidence_profiled_at` per `(evidence_subject_type, evidence_subject_identifier, evidence_source_label)` (WTK-088 §4.4). Multi-source candidates have one current object per source, and the projection returns all of them under `latest` (§6.1) — triage legitimately sees "heavily used in system A, dormant in system B".
- **Exact-tie resolution.** WTK-090 §5 tolerates duplicate rows for one `(subject, source, profiled_at)` after a failure-and-rerun. The tie-break is **greatest `id` wins** — deterministic, and correct because an exact tie is by construction a re-append of the same observation. The projection and the `latest=true` list filter apply the same tie-break.

### 7.2 What a re-run changes and what it cannot

| Surface | Re-run effect |
|---|---|
| Candidate row | Never touched (name, description, status, edges all triage-owned after first deposit) |
| Evidence | One new row per touched subject; history accumulates |
| `flags` | May flip between snapshots (a field going stale *is* the drift signal); each snapshot's flags are frozen with their `thresholds` |
| Provenance | New rows carry the new run's `deposit_event` (or `null` standalone); prior rows keep theirs — provenance is per-snapshot, never rewritten |

### 7.3 Schema evolution

Three versioned layers, each already governed; this spec adds the third:

| Layer | Discriminator | Rule |
|---|---|---|
| Profile file | `manifest_version` (WTK-090 §2.2) | Additive keys only at version 1; consumers read named keys |
| Evidence typed columns | Alembic migrations (WTK-088 §6) | Column promotion is a migration; dual-head SQLite + PG |
| `evidence_detail` keys | `evidence_schema_version` (§4.1), starts at 1 | Additive keys bump nothing; a renamed/retyped/retired key bumps the version, and consumers branch on it. Old rows are never rewritten — history is heterogeneous by design, readable because each row names its own version |

---

## 8. Acceptance Criteria — Triage Decidability

The Work Task's closing requirement: the criteria under which Phase 3 keep/transform/drop is decidable from this evidence. "Decidable" means the consultant can conduct the Master PRD §8 evidence-led conversation for a candidate from its inline object(s) alone — no source-system access, no manifest spelunking, no second query. The implementation (and the Phase 1.5 run that uses it) is correct when:

**A1 — One-request sufficiency.** `GET /{family}/{id}?include_evidence=latest` returns the candidate and its current object(s) in one response; every §8 criterion below is checkable from that response alone.

**A2 — The five conduct probes are answerable** from a field-subject object on a profiled source: *"on 87% of your contacts"* (`metrics.population_rate`), *"hasn't been filled in since 2024"* (`metrics.last_populated_at` + `flags.stale`), *"7 declared options, 5 ever used"* (`metrics.declared_option_count` / `used_option_count` + `detail.value_distribution`), *"this entity has no records since 2024"* (entity object: `metrics.last_record_created_at` + `flags.dormant`), *"someone paid to add this"* (`catalog_class`). Each probe names its key path; a build is wrong if any probe needs a key outside the object.

**A3 — Schema-only deposits degrade decidably.** Without a profile, the object still arrives with: `catalog_class`, `detail.wire_name`/`wire_type`, `detail.schema_only: true`, `metrics.declared_option_count` for enums, and an empty `flags`. Triage can tell "unprofiled" from "profiled and empty" without ambiguity — the conversation falls back to schema-led, knowingly.

**A4 — Multi-source candidates render per source.** A candidate matched by two sources carries one current object per `source_label`; neither masks the other.

**A5 — Flags reconcile with metrics.** For every object, re-deriving each flag from the object's own `metrics` at `detail.thresholds` reproduces the stored flag. A mismatch is a build defect, not a data finding.

**A6 — The WTK-088 queries still govern scale.** Q1–Q3 (low-population, dormant, ghost-options) and the Q4/Q6 completion gates run unchanged against the typed columns; the projection adds no second query path for them and regresses none of them.

**A7 — Evidence survives disposition.** A rejected candidate (post-triage drop) still projects its full history, and a later standalone re-profile appends to it — the drift seed ("we dropped it and the source shows it still being populated", WTK-090 §5) is readable from the same inline view.

**A8 — Plan/read parity.** The object printed for a candidate by the transform's `--dry-run` and the object returned by §6 after the run are identical (§3.4 determinism), for both profiled and schema-only runs.

A1–A2 + A5 make *keep* and *drop* arguable from evidence; A3 bounds what triage can claim without data; A4 and A7 cover the multi-system and post-disposition edges; A8 is the determinism tripwire. Migration-mapping capture for keep/transform remains out of scope (Master PRD §8 mechanics gap — pending its own record type).

---

## 9. Build Surface (for the implementing Work Tasks)

This spec ships no code. In dependency order:

1. **WTK-088 build first** (its §6) — table, vocab, endpoints; prerequisite for everything here.
2. **Projection assembler:** one pure function row → §3 object in the access layer (e.g. alongside the evidence repository), used by every surface; unit-tested for §3.4 determinism and the §3.3 flag lift.
3. **API:** the `include_evidence` parameter on the five candidate families (§6.1), reusing the assembler and the §7.1 latest/tie-break selection shared with the `latest=true` list filter; 422 shape for refused `all` on lists.
4. **Transform conformance (WTK-090 build):** emit `evidence_detail` per §4 (including `evidence_schema_version`, `thresholds`, `schema_only`), copy flags verbatim, render plan-time objects via the same assembler shape (A8).
5. **Tests:** A1–A8 as the acceptance suite — A2/A3/A5 against the WTK-090 T6 fixtures (with/without profile), A4 against its rule-6 multi-source case, A7 against its T7, A8 across `--dry-run` and live read.
6. **Out of scope here:** the Baseline Report renderer (consumes §3/§6, specified separately); evidence-filtered candidate queries (§10); UI evidence sub-panel (WTK-088 deferred follow-on — now has its contract).

## 10. Open Questions and Deferred Decisions

- **Evidence-filtered candidate lists** (§6.2): `GET /fields?status=candidate&max_population_rate=0.05` (candidate filter × evidence filter in one query) would serve triage prep directly; deferred until the two-query pattern (evidence endpoint → candidate identifiers) proves annoying in practice.
- **Persona/process typed metrics** (inherited from WTK-088 §7): when promoted, their keys move from `detail` to `metrics` under the §7.3 versioning rule.
- **Evidence pruning** (inherited from WTK-088 §7): unbounded history is by design until drift detection defines retention; `snapshot_count` (§6.1) is the early visibility into accumulation.
- **Cross-engagement projection:** the registry's cross-engagement learning posture (DEC-373) does not extend to evidence — evidence is engagement-scoped observational data with no system-row variant; noted to foreclose the analogy.

## 11. Cross-References

- `candidate-lifecycle-rejected-and-utilization-evidence.md` (WTK-088) — §4.2 soft-reference linkage, §4.3 typed columns, §4.4 latest-snapshot rule, §4.5 endpoints, §5.1 Q1–Q6, §5.2 I8/I10, §6 build surface, §7 deferred promotions
- `audit-report-to-candidate-deposit-transform.md` (WTK-090) — §2.2 profile contract, §3 name derivation (the wire-identity survival rule §4.1 formalizes), §5 evidence attachment, §6 plan/execute split, §7 re-run rules, T6/T7 fixtures
- `espocrm-data-profiling-pass.md` (WTK-096) — §3 metric definitions, §4.5 sampling keys, §5 flags and thresholds, §6 profile shape rules (the omitted-not-null convention §3.1 inherits)
- `specifications/master-crmbuilder-PRD.md` v0.2 — §7 Phase 1.5 ("evidence travels with the candidate", Activity 2/4, completion criteria), §8 Phase 3 conduct (the probes A2 makes executable)
- `crmbuilder-v2/src/crmbuilder_v2/api/envelope.py` — the `{data, meta, errors}` envelope the §6 projection embeds into
- TOP-013 — governance recording rules (API-first; the projection is read-only and adds no recording path)

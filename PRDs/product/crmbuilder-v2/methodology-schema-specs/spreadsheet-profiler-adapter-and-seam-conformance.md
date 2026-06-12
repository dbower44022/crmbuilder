# Methodology Design Spec — Spreadsheet Profiler Adapter and Phase 1.5 Seam Conformance

**Last Updated:** 06-12-26
**Status:** Draft v1.0 — produced under WTK-110 (api-area spec deliverable, Design phase of PI-156 Spreadsheet source adapter)
**Position in workstream:** First spec of the second-source-adapter family. The EspoCRM Phase 1.5 path is proven end-to-end — schema discovery (V1 Audit), data profiling (WTK-096/098), catalog normalization (WTK-102/103), and the candidate deposit transform (WTK-090/092) — and PI-156 calls for the adapter seam to be drawn now that the deposit path has landed ("the adapter seam (each adapter emits the normalized inventory) should be drawn when the deposit path lands"). This spec does two things: it **pins the seam** — the normalized-inventory contract `plan_deposit` consumes, stated as the exact key set the landed consumer reads (§2) — and it **designs the spreadsheet adapter** that emits through it: supported input formats (§3), the profiling pipeline that proposes candidate entities and fields with evidence (§4), the evidence/confidence data model (§5), the per-key conformance mapping (§6), and golden-sample verification criteria (§7). The companion WTK-111 spec (storage) owns persistence for uploaded spreadsheets and profiling output; the boundary is drawn in §3.4.
**Companion documents:** `audit-report-to-candidate-deposit-transform.md` (WTK-090 — the deposit pipeline and the manifest pair this adapter emits into); `espocrm-data-profiling-pass.md` (WTK-096 — the profile contract and metric semantics this adapter's profile conforms to); `catalog-normalizer-type-mapping-and-partition.md` (WTK-102 — the two-stage type architecture the spreadsheet stage-1 table extends); `candidate-lifecycle-rejected-and-utilization-evidence.md` (WTK-088 — where evidence lands); `specifications/master-crmbuilder-PRD.md` §7 (Phase 1.5; its Known Limitations name this adapter as the planned second source).

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 06-12-26 | ADO Area Specialist (api) / Claude | Initial draft under WTK-110. Pins the Phase 1.5 adapter seam as the consumed-key contract of `plan_deposit` (manifest + profile, with generic readings of the EspoCRM-historical key names) and the four small consumer deltas a second adapter needs (`source_system` key, per-system composed map selection, file-source label rule, constant-custom partition). Designs the spreadsheet adapter: CSV-family inputs (the exports every spreadsheet product produces), the five-stage profiling pipeline (parse/header detection, column type inference by recognizer vote, enum/multi-value/auto-number/reference post-passes, sheet→entity proposal, utilization metrics), a pinned 17-type inferred-type vocabulary with its stage-1 table, the `type_inference` evidence/confidence block riding the WTK-096 detail passthrough, and the no-manifest-relationships-in-v1 decision (cross-sheet matches are reference-typed fields with containment evidence). Verification: three inline golden samples (typed coverage, cross-sheet reference, messy sheet) and conformance checks C1–C8 including a shared seam-contract checker both adapters must pass. |

---

## Change Log

**Version 1.0 (06-12-26):** Initial creation. No code ships with this document — it is the design the implementing Work Tasks build from. §9 enumerates the build surface.

---

## 1. Purpose and Position

Master CRMBuilder PRD v0.2 §7 Known Limitations:

> EspoCRM is the only source adapter. The spreadsheet adapter (CSV/Sheet profiler proposing entity/field candidates) is the planned second source, since for small organizations the "existing system" is most often a spreadsheet.

The spreadsheet adapter is the highest-reach second source: it makes Phase 1.5 runnable for every client whose operational system is a workbook rather than a CRM. Unlike the EspoCRM source, a spreadsheet has no declared schema — the adapter must *infer* one. That changes the character of the output, not its shape: the adapter still emits the normalized inventory (a manifest plus a utilization profile), but every structural fact in it is an inference carrying evidence and a confidence grade, where the EspoCRM adapter's facts were declarations read from metadata.

Phase-rule constraints inherited from Master PRD §7 bind this adapter exactly as they bind the EspoCRM path: the run is **mechanical** (no keep/drop judgment — oddities become anomalies and evidence, never silent corrections), **candidates never auto-confirm**, **provenance is mandatory** (one deposit event per source), and **evidence travels with the candidate**. The seam makes the last three free: the adapter emits the manifest pair, and the landed transform supplies candidate status, provenance, evidence attachment, and idempotency unchanged.

---

## 2. The Phase 1.5 Adapter Seam (verified against source)

### 2.1 What the seam is

The seam is the **serialized manifest pair** consumed by `plan_deposit` (`crmbuilder_v2/transform/audit_deposit.py`):

1. **`audit-report.json`** — the normalized inventory: entities with fields, plus relationships, roles, and teams, with source identity and run diagnostics. `manifest_version: 1`.
2. **`utilization-profile.json`** (optional) — the utilization metrics, keyed by the same wire names the manifest carries. `manifest_version: 1`.

An adapter is anything that produces this pair. Everything downstream of the pair — candidate mapping, scope rules, evidence attachment, deposit-event provenance, idempotent re-runs, the anomaly Planning Item — is the landed transform and is **shared, not per-adapter**. WTK-090 §2.1 defined the pair as a serialization of the V1 `AuditReport`; this spec restates it adapter-neutrally as the key set the consumer actually reads, which is the only thing a second adapter must conform to.

### 2.2 The pinned key contract

The keys below are every manifest key `plan_deposit`, `derive_source_label`, and the §7 idempotency path read, verified against `audit_deposit.py` at the commit this spec is authored on. Keys the EspoCRM serialization carries but no consumer reads (e.g. layout internals beyond `layout_type`) are *not* part of the seam; an adapter may omit them.

**Manifest top level:**

| Key | Required | Consumer use |
|---|---|---|
| `manifest_version` | yes (`1`) | version gate in `load_manifest` |
| `timestamp` | yes | snapshot timestamp; `evidence_profiled_at` fallback |
| `source_url` | yes | source label host; `apply_context.source_instance` |
| `source_name` | yes | `apply_context.source_name` |
| `source_system` | new, optional | see §2.4 delta D1; absent → `espocrm` |
| `errors`, `warnings` | optional lists | each line becomes an anomaly PI line |
| `entities` | yes | the entity/field mapping (§3.1–§3.2 of WTK-090) |
| `relationships` | optional | reference-field mapping (WTK-090 §3.3) |
| `roles`, `teams` | optional | persona mapping (WTK-090 §3.4) |

**Per entity** (one object per `entities[]` element):

| Key | Required | Consumer use |
|---|---|---|
| `yaml_name` | yes | name fallback (`_entity_name` raises without it); wire lookup |
| `espo_name` | yes | **profile join key**; wire lookup; notes `Source:` block |
| `label_singular` | optional | the candidate `entity_name` (falls back to `yaml_name`) |
| `label_plural` | optional | description suffix |
| `entity_type` | optional | `ENTITY_KIND_MAP` lookup; unknown/null → kind omitted |
| `entity_class` | yes | scope (`custom` always in scope; `native` conditional; `system` never) and `catalog_class` |
| `stream` | optional | notes block only |
| `layouts[].layout_type` | optional | `layouts_captured` evidence summary |
| `filtered_tabs` | optional | process/manual_config mapping; native-entity scope trigger |
| `fields[]` | yes | the field mapping |

**Per field** (one object per `fields[]` element):

| Key | Required | Consumer use |
|---|---|---|
| `yaml_name` | yes | name fallback; link-dedup key |
| `api_name` | yes | **profile join key** (first, then `yaml_name`); notes |
| `label` | optional | the candidate `field_name` (falls back to `yaml_name`) |
| `field_type` | yes | the **native type** fed to the composed type map |
| `field_class` | optional | scope: `None`/`custom` in scope, else skipped |
| `properties.options` | optional | enum declared options → notes, `declared_option_count` |
| `properties.default` | optional | notes block only |
| `properties.required` | optional | the candidate `required` flag |

**Per relationship / role / team:** the WTK-090 §3.3–§3.4 key sets (`name`/`link_type`/`entity`/`link`/`label`/`audited` and their `_foreign` twins; role/team `name` + `description`). The spreadsheet adapter emits none of these in v1 (§6.4), so they are listed for contract completeness only.

**Profile:** the WTK-096 §6 contract verbatim — top-level `manifest_version`, `profiled_at`, `profiler_version`, `options`, `anomalies`; `entities` keyed by the manifest's `espo_name` values, each with `record_count`, `last_record_created_at`, `detail`, and `fields` keyed by `api_name`, each with the typed metric keys (`populated_count`, `population_rate`, `last_populated_at`, `distinct_value_count`, `declared_option_count`, `used_option_count`) plus `detail`. Per-entity and per-field `detail` blocks are **passed through verbatim** into `evidence_detail` — that passthrough is the channel the spreadsheet adapter's inference evidence rides (§5.3).

### 2.3 Generic readings of the EspoCRM-historical key names

The key names are EspoCRM-flavored (`espo_name`, `yaml_name`, `api_name`) because the contract was first serialized from `AuditReport`. The seam pins them as **wire names with adapter-defined semantics** — renaming them would force a manifest-version bump and consumer churn for zero behavior. Generic readings:

| Wire key | Generic meaning | EspoCRM value | Spreadsheet value (§6) |
|---|---|---|---|
| `yaml_name` | canonical machine name (slug) | YAML entity/field name | normalized sheet/header slug |
| `espo_name` | source-native entity name; profile entity join key | EspoCRM scope name | literal sheet/file name |
| `api_name` | source-native field name; profile field join key | EspoCRM attribute name | literal header text |
| `field_type` | the source's native type vocabulary | metadata wire type | inferred type (§4.2 vocabulary) |

### 2.4 Consumer deltas required for a second adapter

Four small deltas in the landed code, all backward compatible (`manifest_version` stays `1`; every existing fixture is unaffected):

- **D1 — `source_system` manifest key.** `plan_deposit` currently hard-codes `SOURCE_SYSTEM = "espocrm"` and module-level `WIRE_TYPE_MAP = composed_type_map("espocrm")`; the `apply_context` it emits already carries a `source_system` key (WTK-089 §4.3 required), sourced from that constant. The manifest gains an optional top-level `source_system` (a `SYSTEM_TYPE_MAPS` key); absent → `"espocrm"`. `plan_deposit` selects `composed_type_map(source_system)` per run and feeds the manifest's value into the existing `apply_context` key.
- **D2 — file-source label.** `derive_source_label` is `{system} @ {netloc}`; a `file://` URI has an empty netloc and would label every spreadsheet source `spreadsheet @ unknown`. New rule: when the netloc is empty, use the URL path's basename — e.g. `spreadsheet @ cbm-mentor-tracking.xlsx`.
- **D3 — spreadsheet stage-1 registration.** `SYSTEM_TYPE_MAPS` gains the `"spreadsheet"` table (§6.3). `CATALOG_SYSTEMS` does **not** grow — that frozenset is the catalog-survey vocabulary, and a spreadsheet is not a surveyed product; only the stage-1 registry and the partition rule know the slug.
- **D4 — constant-custom partition.** A tier-1 rule in `transform/normalize.py`: `system == "spreadsheet"` → every item, entity and attribute, is `custom`. A spreadsheet has no stock schema and no catalog presence — tiers 2 and 3 are never consulted. (No `plan_deposit` change: the adapter emits `entity_class`/`field_class` `"custom"` everywhere, and the landed `catalog_class` derivation already reads those.)

Everything else — `ENTITY_KIND_MAP` (null `entity_type` → kind omitted, the designed deferral), `_LINK_WIRE_TYPES`, the scope rules, the idempotency diff — is untouched.

---

## 3. Supported Input Formats

### 3.1 CSV, as every spreadsheet product exports it

v1 ingests **delimited text files** — the export format shared by Excel, Google Sheets, LibreOffice Calc, Airtable, and every SaaS "download as CSV" button — using only the stdlib `csv` module (no new dependencies). The adapter must accept the dialect/encoding spread those products actually produce:

- **Encodings:** UTF-8 with BOM (Excel "CSV UTF-8"), UTF-8 without BOM (Google Sheets), UTF-16 LE/BE with BOM (Excel "Unicode Text", tab-delimited), and a `cp1252` fallback for legacy Excel exports. Detection order: BOM sniff → strict UTF-8 decode → `cp1252` fallback **with a warning** (the fallback never fails, so it must be visible).
- **Dialects:** delimiter from `csv.Sniffer` over the first 64 KiB, restricted to `,`, `;`, `\t`, `|`; on sniff failure, comma, with a warning. Quoting per RFC 4180 (`"` quote char, doubled-quote escape); CRLF and LF both accepted; embedded newlines inside quoted cells preserved.
- **Ragged rows:** rows shorter than the header are padded with empties; longer rows are truncated to the header width — both counted and reported as one per-sheet anomaly with the affected row count.

### 3.2 Native workbook formats — deferred

Native `.xlsx`/`.ods` ingestion requires a new dependency (`openpyxl`/`odfpy`) and brings formula cells, merged ranges, and multi-table sheets with it. Deferred as a named follow-on (§8); for v1 the operator exports each sheet to CSV — the path every spreadsheet product supports, and the path the upload UX (WTK-111's scope) can instruct. The pipeline (§4) is byte-agnostic past parsing, so native formats later slot in as an additional Stage A reader without touching inference or emission.

### 3.3 The source unit

One **source** = one workbook = one adapter run = one manifest pair = one deposit event (Master PRD §7: one deposit event per source system). On disk a source is a directory of CSV files, one per sheet (`{sheet}.csv`); the directory (or single file) is the run input. Files within one source are profiled together — cross-sheet reference detection (§4.5) only sees sheets of the same source. A client with three unrelated workbooks runs three times and gets three deposit events, keeping provenance unambiguous.

### 3.4 Boundary with WTK-111 (persistence)

This adapter is a **pure function of files**: paths in, manifest pair out (written beside the inputs, mirroring `programs/audit-YYYYMMDD-HHMMSS/`). Where uploaded workbooks live, how uploads become the per-sheet CSV layout, retention, and any REST upload surface are WTK-111's persistence scope. The interface between the two specs is exactly: a readable source directory in, `audit-report.json` + `utilization-profile.json` out.

---

## 4. The Profiling Pipeline

Five stages, all pure given the file bytes and options. Stages B–E are deterministic (same bytes + same options → same output, criterion C6); the populated predicate throughout is the WTK-096 §3.1 one: a cell is populated iff non-empty after trimming whitespace (whitespace-only cells count toward `empty_string_count`, not population).

### 4.1 Stage A — parse and header detection

Decode and parse per §3.1. Fully-blank rows are dropped from the data set and counted (`blank_row_count`, entity detail). Then decide whether row 1 is a header:

- **Header accepted** (the default expectation) when every column that has any populated body cell also has a populated row-1 cell, **and** row 1 diverges from the body's type profile — operationally: among columns whose body infers a non-text type (§4.2), ≥ 60% have a row-1 value that fails that type's recognizer. A sheet whose columns are all text-typed accepts row 1 as header when its values are unique.
- **Ambiguous** → assume header (the overwhelmingly common case for exported sheets) and record a `header_assumed` anomaly so triage knows the column names are load-bearing guesses.
- **Operator override:** `--no-header` (per sheet) names columns `column_1 … column_n`.

Header normalization: trim, collapse internal whitespace runs to one space (that trimmed text is the `api_name`/`label`); slugify to snake_case for `yaml_name`. Empty header → `column_{i}` + anomaly; duplicate headers → `_2`, `_3` suffixes on both forms + anomaly.

### 4.2 Stage B — column type inference

Per column, every populated cell is tested against the recognizer set; the inferred type is the **most specific recognizer whose match rate ≥ τ** (`inference_threshold`, default **0.95**) over populated cells, with specificity order:

`boolean` → `integer` → `decimal` → `currency` → `percent` → `date` → `datetime` → `time` → `email` → `url` → `phone` → `long_text` → `text`

Recognizer definitions (pinned; all case-insensitive where applicable):

| Native type | Recognizer |
|---|---|
| `boolean` | membership in `{true,false}`, `{yes,no}`, `{y,n}` — one pair per column. `{1,0}` is deliberately **not** boolean (integer wins; a 0/1 flag column surfaces via its 2-value distribution instead). |
| `integer` | optional sign; digits; optional US thousands-grouping (`1,234`). `--decimal-comma` swaps `.`/`,` roles for European exports. |
| `decimal` | integer grammar plus one decimal point. |
| `currency` | integer/decimal grammar with a leading or trailing currency symbol (`$`, `€`, `£`) and/or parenthesized negatives. |
| `percent` | integer/decimal grammar with trailing `%`. |
| `date` | pinned format list, tried in order: ISO `YYYY-MM-DD`; `M/D/YYYY` and `D/M/YYYY` (slash family); `M-D-YYYY`; `D-Mon-YYYY` / `Mon D, YYYY` (named month); two-digit years accepted in the slash family (pivot 1970). Slash-family day/month ambiguity is resolved **per column**: any value with first component > 12 fixes D/M, any with second component > 12 fixes M/D; an unresolvable column assumes M/D (US default) and records `date_order_assumed` in its inference evidence. |
| `datetime` | a `date` grammar plus a `time` grammar separated by space or `T`, optional zone suffix. |
| `time` | `HH:MM(:SS)`, optional `AM`/`PM`. |
| `email` | exactly one `@`; non-empty local part; domain containing a dot. |
| `url` | `http(s)://` prefix or `www.` prefix. |
| `phone` | after stripping spaces, `()-.`: optional `+`, 7–15 digits (the E.164 envelope; same cleaning family as the import pipeline's phone handling). |
| `long_text` | not a recognizer over cells but a text refinement: ≥ 5% of populated cells contain an embedded newline, or the 95th-percentile trimmed length > 200 characters. |
| `text` | the universal fallback; no threshold. |

Below-τ columns are `text` (or `long_text` per its refinement) — a 60/40 integer/text column is *text with a recorded runner-up*, never a forced number. The runner-up recognizer and its rate are always recorded (§5.1) so triage sees near-misses.

### 4.3 Stage B′ — post-passes (enum, multi-value, auto-number)

Applied after base inference, to columns in the stated base types:

- **`enum`** (base `text` only): `populated_count ≥ 10` (`enum_min_support`), `distinct_value_count ≥ 2`, `distinct_value_count < populated_count`, and `distinct_value_count ≤ min(24, max(6, ⌈0.5 × populated_count⌉))` (`enum_max_options` 24; the `max(6, …)` floor keeps small sheets eligible). Numeric/date-typed columns never promote — a column of status *codes* stays `integer` with its distribution as evidence.
- **`multi_enum`** (base `text` only): a single delimiter — precedence `;`, `|`, `,` — splits ≥ 20% of populated cells into > 1 trimmed token, and the **token** vocabulary passes the enum test above (computed over tokens). Comma is admitted as a multi-value delimiter only when the token test passes with ≤ 12 distinct tokens (commas inside prose otherwise flood it).
- **`auto_number`** (base `integer` only): all populated values unique and near-contiguous (`(max − min + 1) / populated_count ≤ 1.5`) — the exported-row-ID signature.
- **`empty`**: zero populated cells. Not an anomaly — an empty column is gaps-and-ghosts evidence, exactly what triage wants surfaced — but inference confidence is `none` (§5.2).

### 4.4 Stage C — candidate-entity proposal

**One sheet → one candidate entity**, mechanically: the entity is the sheet, its fields are the sheet's columns. The adapter performs **no splitting, merging, singularization, or renaming** — proposing that "the `Mentors` and `2024 Mentors` sheets are one entity" is judgment, and judgment belongs to Phase 3 triage (Master PRD §7: mechanical capture). Structural oddities that *suggest* a different entity shape are recorded as evidence, not acted on:

- **Repeated column groups** (`Child 1 Name, Child 1 DOB, Child 2 Name, Child 2 DOB …`, detected as ≥ 2 groups of headers equal up to a trailing/embedded index) → `repeated_group` entry in the entity's detail block: the de-normalized child-entity signature, triage's strongest decompose hint.
- **Near-duplicate sheets** (≥ 80% of normalized headers shared between two sheets of the source) → `similar_sheets` entry on both entities.

### 4.5 Stage D — cross-sheet reference detection

For each column and each *other* sheet's **candidate key column** (a column that is ≥ 95% populated with all-unique values), compute containment: the fraction of the column's populated distinct values present in the key column. A **reference inference** fires when containment ≥ 0.95 (`reference_containment_threshold`) over ≥ 10 matched distinct values. Header hints (`*id`/`*_id` suffix, header containing the other sheet's name) raise confidence (§5.2) but are never sufficient alone, and never required.

A fired reference re-types the column to native `reference` (overriding its base inference, which is preserved as evidence) and records the pairing in the column's `reference_inference` detail block (§5.1). **In v1 the adapter emits no manifest `relationships` entries** (§6.4 has the full rationale): the reference is a *field-level inference with evidence*, and the field path is the one that carries evidence through the seam.

### 4.6 Stage E — utilization metrics

The spreadsheet *is* its own data, so profiling is exact — no sampling, no request budget, no count/scan split. Per the WTK-096 metric definitions, with spreadsheet-specific postures:

- **Entity:** `record_count` = data rows (blank rows excluded and counted separately). `last_record_created_at` is **omitted by default** — a spreadsheet has no row-creation timestamp, and inventing one from an arbitrary date column would be judgment. Operator designation `--created-column SHEET=COLUMN` enables it (and per-field `last_populated_at` = max designated-column value over rows where the field is populated), with the basis recorded as `last_record_created_at_basis: {"column": …}` so the derivation is always visible. Entity `dormant` is derivable only under designation; `empty` (`record_count == 0`) always.
- **Field:** `populated_count`, `population_rate` per the §3.1 predicate; `distinct_value_count` (cap 1,000 → report cap + `distinct_overflow: true`); `empty_string_count` (whitespace-only cells). Booleans follow the WTK-096 rule: `population_rate` 1.0 definitionally? **No** — unlike a CRM bool column, a spreadsheet boolean cell can be genuinely blank, and blank-vs-false is real signal; `population_rate` is computed normally and the true/false distribution still lands in `value_distribution`.
- **Enum metrics:** for `enum`/`multi_enum` inferences, `declared_option_count` = `used_option_count` = the observed option count **by construction** — a spreadsheet declares nothing, so the option set *is* the observed set, and the ghost-option signal (declared − used) is structurally zero. The spec states this so the WTK-088 Q3 ghost-options query reading zeros over spreadsheet candidates is understood as honest, not broken. `value_distribution` carries the full per-option counts (tokens for `multi_enum`, so it sums ≥ `populated_count`).
- **Non-enum distributions:** `top_values` (top 10 by count) when `distinct_value_count ≤ 100`, per WTK-096 §3.5.

---

## 5. The Evidence/Confidence Data Model

Every structural fact the adapter asserts is an inference; this section pins where the supporting evidence lives and how confidence is graded. Design rule: **assertions go in the manifest, evidence goes in the profile `detail` blocks** — because the WTK-090 transform passes per-entity and per-field `detail` through verbatim into `evidence_detail`, which is exactly where triage reads evidence (WTK-088 §4).

### 5.1 The `type_inference` block

Every field's profile `detail` carries:

```json
"type_inference": {
  "inferred_type": "enum",
  "base_type": "text",
  "match_rate": 1.0,
  "non_empty_count": 412,
  "recognizer": "enum_post_pass",
  "runner_up": null,
  "runner_up_rate": null,
  "confidence": "high",
  "date_order_assumed": false,
  "sample_values": ["active", "paused", "closed"]
}
```

- `inferred_type` — the emitted native type; `base_type` — the pre-post-pass type when a post-pass re-typed the column (enum/multi_enum/auto_number/reference), else equal to `inferred_type`.
- `match_rate` / `non_empty_count` — the vote that won; `runner_up` / `runner_up_rate` — the best losing recognizer when its rate ≥ 0.30, else null (the 60/40 mixed-column signal).
- `sample_values` — up to 5 distinct example values, **redaction-aware**: omitted for `email`/`phone` inferences (PII; the recognizer name is evidence enough).
- Reference inferences add a sibling block: `"reference_inference": {"target_sheet": …, "target_column": …, "containment": 0.98, "matched_distinct": 41, "header_hint": true}`.
- Entity-level detail carries the §4.4 structure evidence (`repeated_group`, `similar_sheets`), `blank_row_count`, `ragged_row_count`, `source_file`, and `source_file_modified_at` (the file's mtime — the closest thing a spreadsheet has to a snapshot timestamp, recorded as evidence, never used as a metric basis).

### 5.2 Confidence grades

One ordinal vocabulary, pinned, attached to every inference:

| Grade | Type inference | Reference inference |
|---|---|---|
| `high` | `match_rate ≥ 0.99` and `non_empty_count ≥ 50` | containment ≥ 0.99 and matched_distinct ≥ 25 |
| `medium` | `match_rate ≥ τ` and `non_empty_count ≥ 10` | at threshold (≥ 0.95 / ≥ 10) |
| `low` | won the vote but `non_empty_count < 10` | — (below threshold never fires) |
| `none` | `empty` columns | — |

A header hint (§4.5) promotes a `medium` reference inference one grade; nothing else moves a grade — confidence is re-derivable from the recorded inputs, mirroring the WTK-096 advisory-flags principle (the grade travels *with* its inputs, so triage can re-grade under different thresholds without re-profiling).

### 5.3 Where evidence lands downstream

Through the landed transform, with **zero** consumer changes: the profile's typed metrics populate the typed `utilization_evidence` columns; the `detail` blocks (including `type_inference` and `reference_inference`) arrive verbatim inside `evidence_detail`, alongside the transform's own keys (`wire_name`, `wire_type` = the inferred native type, `catalog_attribute_type` from the normalizer). The manifest field's `notes` `Source:` block carries the wire identity (header text, slug, inferred native type, observed options) per the WTK-090 losslessness rule. The adapter's options block (§6.2) travels in the profile and is copied into evidence `thresholds` handling exactly as the EspoCRM profiler's options are today.

---

## 6. Seam Conformance — What the Adapter Emits

### 6.1 The manifest, key by key

| Seam key | Spreadsheet adapter emission |
|---|---|
| `manifest_version` | `1` |
| `source_system` | `"spreadsheet"` |
| `timestamp` | run timestamp, ISO 8601 UTC |
| `source_url` | `file://{absolute source path}` (workbook directory or single file) |
| `source_name` | operator-supplied source name (`--source-name`), default the basename |
| `errors` | unreadable/undecodable file failures (the run continues over remaining sheets) |
| `warnings` | encoding fallback, sniff fallback, header assumption, ragged rows |
| `entities[].yaml_name` | sheet-name slug (snake_case) |
| `entities[].espo_name` | literal sheet file name minus extension — the profile join key |
| `entities[].label_singular` | trimmed sheet name, verbatim (no singularization — §4.4) |
| `entities[].label_plural` | omitted |
| `entities[].entity_type` | `null` → entity kind omitted; classification is triage's (the designed DEC-292 deferral) |
| `entities[].entity_class` | `"custom"`, always |
| `entities[].stream` | `false` |
| `entities[].layouts` / `filtered_tabs` | `[]` — consequence: `layouts_captured` is empty and no process/manual_config candidates arise |
| `fields[].yaml_name` | header slug (snake_case) |
| `fields[].api_name` | trimmed header text, verbatim — the profile join key |
| `fields[].label` | trimmed header text |
| `fields[].field_type` | the inferred native type (§4.2/§4.3 vocabulary) |
| `fields[].field_class` | `"custom"`, always |
| `fields[].properties.options` | for `enum`/`multi_enum` only: the observed option list, ordered by descending count then alphabetically (deterministic) |
| `fields[].properties.required` | `false`, always — a spreadsheet declares no constraint; fill rate is evidence, not constraint |
| `fields[].properties.default` | never emitted |
| `relationships`, `roles`, `teams` | `[]` (§6.4) |

Scope consequence, for the record: every entity is `entity_class: "custom"` → always in scope; every field `field_class: "custom"` → always in scope. The EspoCRM skipped-native rule simply never fires for this adapter.

### 6.2 The profile

The WTK-096 §6 contract verbatim, with the spreadsheet postures of §4.6 and the §5 detail blocks. Top-level `options` pins every inference parameter so evidence is re-derivable:

```json
"options": {"inference_threshold": 0.95, "enum_min_support": 10, "enum_max_options": 24,
            "multi_value_delimiters": [";", "|", ","], "reference_containment_threshold": 0.95,
            "decimal_comma": false, "dormancy_window_days": 365, "low_population_threshold": 0.05}
```

`profiler_version` is the adapter's distribution version. Entity keys = manifest `espo_name` values; field keys = manifest `api_name` values — the join `plan_deposit` performs (criterion C7). Anomalies use the WTK-096 row shape (`scope`/`entity`/`field`/`note`).

### 6.3 The stage-1 spreadsheet type table

The adapter's native-type vocabulary is its **inferred-type** vocabulary — 17 values, closed. Registered as `_SPREADSHEET_TYPES` in `transform/normalize.py` under slug `"spreadsheet"` (delta D3), all bare-string keys (no pairs; the adapter owns its own vocabulary, so it never needs a subtype discriminator), no `calculated`/`multivalued` flags (formulas are invisible in CSV exports — §8; multi-valuedness is its own native type):

| Inferred native type | `CATALOG_ATTRIBUTE_TYPES` | Composed `FIELD_TYPES` |
|---|---|---|
| `text` | `string` | `text` |
| `long_text` | `text` | `long_text` |
| `integer` | `integer` | `number` |
| `decimal` | `decimal` | `number` |
| `currency` | `currency` | `money` |
| `percent` | `decimal` | `number` |
| `boolean` | `boolean` | `boolean` |
| `date` | `date` | `date` |
| `datetime` | `datetime` | `datetime` |
| `time` | `time` | `text` (stage-2 lossy rule, shared) |
| `email` | `email` | `text` (PI-054 refinement candidate, shared) |
| `phone` | `phone` | `text` |
| `url` | `url` | `text` |
| `enum` | `enum` | `enum` |
| `multi_enum` | `multienum` | `multi_enum` |
| `reference` | `reference` | `reference` |
| `auto_number` | `autonumber` | `number` |
| `empty` | `string` | `text` (with confidence `none`; not the anomaly fallback — an empty column is signal, not an error) |

The table is total over the closed vocabulary, so the §3.10 fallback chain is unreachable for a conforming adapter build — criterion C3 enforces totality, and the fallback still guards against adapter/normalizer version skew.

### 6.4 Why no manifest `relationships` in v1

The WTK-090 §3.3 relationships branch was built for *declared* relationships: it maps each side to a `reference` field whose evidence is the declared pairing — and it has **no slot for utilization metrics or confidence** (it performs no profile join). A spreadsheet cross-sheet match is the opposite case: an *inference* whose value is its evidence (containment, matched-distinct, fill rate). Emitting it through the relationships branch would discard exactly what makes it useful, and emitting the column both ways (relationship side + plain field) would double-map the candidate, since the landed link-dedup keys on `_LINK_WIRE_TYPES` — EspoCRM wire types the spreadsheet vocabulary deliberately does not reuse.

So v1 pins: a fired reference is emitted as a **plain field of native type `reference`** (→ `FIELD_TYPES` `reference` through §6.3), carrying full utilization metrics plus the `reference_inference` evidence block through the profile join. Triage sees a reference-typed candidate field with containment evidence and decides whether it becomes a modeled relationship — which is a Phase 3 outcome in any case. If a later schema pass gives relationship candidates first-class confidence carriage, the adapter can populate the relationships block additively (the key contract is already pinned in §2.2); nothing in v1's emission blocks that.

Roles and teams: a spreadsheet has none; `roles`/`teams` stay empty and no persona candidates arise from this adapter.

---

## 7. Verification Criteria

### 7.1 Golden samples

Three golden fixtures live with the test suite as literal CSV files plus expected-output JSON (the manifest-is-the-fixture-format property, WTK-090 §2.1). Pinned content:

**G-1 `contacts.csv` — typed coverage.** 12 data rows + header. Columns and expected inference:

| Header | Content sketch | Expected native type (confidence) |
|---|---|---|
| `ID` | 1…12 | `auto_number` (medium) |
| `Name` | 12 distinct names | `text` (medium) |
| `Email` | 12 well-formed addresses | `email` (medium; `sample_values` omitted) |
| `Phone` | 10 digits, mixed `(216) 555-…` / `216-555-…` formats | `phone` (medium) |
| `Active` | `Yes`/`No` | `boolean` (medium) |
| `Joined` | ISO dates | `date` (medium) |
| `Donation Total` | `$1,250.00`-style | `currency` (medium) |
| `Visits` | small integers | `integer` (medium) |
| `Score` | one-decimal values | `decimal` (medium) |
| `Website` | 9 URLs, 3 blank | `url` (medium; `population_rate` 0.75) |
| `Stage` | `active`×6, `paused`×4, `closed`×2 | `enum` (medium; options `["active","paused","closed"]`; `declared_option_count` = `used_option_count` = 3) |
| `Tags` | `mentor; donor`-style, `;`-delimited | `multi_enum` (medium; token distribution sums ≥ populated) |
| `Notes` | prose, two cells with embedded newlines | `long_text` (medium) |
| `Legacy Code` | all blank | `empty` (none; `population_rate` 0.0) |

Expected manifest: one entity (`espo_name` `contacts`, `label_singular` `contacts`, `entity_class` `custom`, `entity_type` null), 14 fields with the native types above; expected profile: `record_count` 12, the per-field metrics, `type_inference` on every field. All confidences are `medium` (12 < 50 rows) — deliberately, so the grade boundaries are exercised.

**G-2 `contacts.csv` + `donations.csv` — cross-sheet reference.** G-1's contacts plus a 15-row `donations.csv` (`Donation ID` auto_number; `Contact ID` referencing 10 distinct contact IDs, containment 1.0; `Amount` currency; `Date` date). Expected: `donations.Contact ID` native type `reference`, `reference_inference` block `{target_sheet: "contacts", target_column: "ID", containment: 1.0, matched_distinct: 10, header_hint: true}`, confidence `high` (hint-promoted from medium); **no** manifest `relationships` entries; `contacts.ID` unchanged from G-1.

**G-3 `messy.csv` — degradation honesty.** 25 data rows engineered to fire every guard: duplicate header (`Amount`, `Amount` → `Amount`, `Amount_2` + anomaly), one empty header (→ `column_3` + anomaly), a 60/40 integer/text column (→ `text`, `runner_up: "integer"`, `runner_up_rate: 0.6`), an ambiguous all-≤-12 slash-date column (→ `date` with `date_order_assumed: true`), whitespace-only cells (counted in `empty_string_count`, not population), two fully-blank rows (`record_count` 25, `blank_row_count` 2), one ragged row (padded + anomaly), and a cp1252-only byte (encoding-fallback warning). Expected output pins the exact anomaly/warning set.

### 7.2 Conformance checks

**C1 — Seam key-contract conformance, shared checker.** A single `assert_seam_conformant(manifest, profile)` checker encoding §2.2 (required keys present, types correct, profile keys joinable, `manifest_version` 1) that **both** the spreadsheet golden outputs **and** the landed EspoCRM transform fixtures pass. One checker, two adapters — the seam is a thing the suite owns, not prose.

**C2 — End-to-end through `plan_deposit`.** Feeding G-1's manifest + profile to the landed `plan_deposit` with empty `ExistingState` yields: 1 entity create + 14 field creates at `candidate`, zero persona/process/manual_config plans, every evidence row carrying its `type_inference` verbatim in `detail`, `catalog_class` `custom` throughout, and zero unmapped-type anomalies.

**C3 — Stage-1 totality and composition.** `_SPREADSHEET_TYPES` is total over the 17-value inferred vocabulary; `composed_type_map("spreadsheet")` matches the §6.3 third column entry-for-entry; every value is in `CATALOG_ATTRIBUTE_TYPES` (the WTK-102 N1/N2 criteria applied to the eighth table).

**C4 — Constant-custom partition.** `partition("spreadsheet", item)` returns `custom` for every entity and attribute item, including items whose names collide with catalog standard items of other systems (e.g. a sheet named `Contacts`).

**C5 — Idempotent re-run.** Planning G-1 a second time against an `ExistingState` seeded with the first plan's creates yields zero creates, 15 matches, 15 new evidence rows — the landed §7 rules, exercised over spreadsheet-born candidates.

**C6 — Determinism.** Byte-identical inputs + pinned options + pinned clock produce byte-identical manifest and profile (option ordering, option-list ordering, key ordering all pinned).

**C7 — Profile join completeness.** Every profile entity key matches a manifest `espo_name` and every profile field key matches an `api_name` of that entity — no orphan evidence (the silent-loss failure mode of a key mismatch).

**C8 — Messy-sheet expectations.** G-3's expected anomaly set, warning set, and degraded inferences match exactly — the guards are behavior, not best-effort.

---

## 8. Open Questions and Deferred Decisions

- **Native `.xlsx`/`.ods` ingestion** (§3.2): deferred pending the `openpyxl`/`odfpy` dependency decision; brings formula-cell visibility (a formula column is `derived`-type signal v1 cannot see — CSV exports bake formulas to values).
- **Relationship candidates with confidence carriage** (§6.4): if Phase 3 practice shows triage wants pre-modeled relationship candidates rather than reference-typed fields, the relationships block gains an evidence slot and the adapter populates it additively.
- **Locale breadth**: v1 pins US-default number/date conventions with one `--decimal-comma` switch; full locale inference (per-column, e.g. mixed-locale workbooks) is deferred until a real source demands it.
- **Header-row position**: v1 assumes row 1 (or `--no-header`); title rows above the header (common in hand-made sheets) are a parse-stage extension (`--skip-rows`) deferred to first contact with one.
- **Created-column auto-suggestion**: the profiler could *suggest* a created-at column (a near-100%-filled monotone-ish date column) as evidence while still requiring operator designation; deferred as polish.

---

## 9. Build Surface (for the implementing Work Tasks)

1. **Consumer deltas D1–D2** (`transform/audit_deposit.py`): optional `source_system` manifest key (default `espocrm`), per-run `composed_type_map(source_system)`, `apply_context.source_system`, file-source label rule in `derive_source_label`.
2. **Normalizer deltas D3–D4** (`transform/normalize.py`): `_SPREADSHEET_TYPES` per §6.3 registered in `SYSTEM_TYPE_MAPS`; constant-custom tier-1 partition rule for `"spreadsheet"`.
3. **The adapter** — new module `crmbuilder-v2/src/crmbuilder_v2/adapters/spreadsheet.py` (a new `adapters` subpackage; the seam keeps it import-free of both `espo_impl` and the transform internals): Stage A–E pipeline as pure functions over file bytes + an `AdapterOptions` dataclass (every §6.2 option), `profile_source(path, options) → (manifest, profile)`, atomic dual-file writer.
4. **CLI** — `crmbuilder-v2-spreadsheet-profile <source-dir-or-csv> [--source-name …] [--no-header SHEET] [--created-column SHEET=COLUMN] [--decimal-comma] [--output-dir …]`, mirroring the deposit CLI's argument idiom; output lands beside the input by default, ready for the existing deposit CLI.
5. **Shared seam checker** (C1) — `assert_seam_conformant` in the test support layer, applied to both adapters' fixtures.
6. **Fixtures + tests** per §7 (G-1/G-2/G-3 as literal files; C1–C8).
7. **Out of scope here:** upload persistence and any REST surface for it (WTK-111); native workbook formats (§8); the Baseline Report renderer.

---

## 10. Cross-References

- `crmbuilder-v2/src/crmbuilder_v2/transform/audit_deposit.py` — the seam's consumer: `load_manifest`/`load_profile`, `derive_source_label`, `plan_deposit` (the key reads §2.2 pins), `SOURCE_SYSTEM`/`WIRE_TYPE_MAP` (delta D1)
- `crmbuilder-v2/src/crmbuilder_v2/transform/normalize.py` — `SYSTEM_TYPE_MAPS`, `CATALOG_TO_FIELD_TYPE`, `resolve_type`, `partition` (deltas D3–D4)
- `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — `CATALOG_ATTRIBUTE_TYPES`, `FIELD_TYPES`, `CATALOG_SYSTEMS` (deliberately not grown)
- `audit-report-to-candidate-deposit-transform.md` (WTK-090) — §2 the manifest pair, §3 candidate mapping, §7 idempotency
- `espocrm-data-profiling-pass.md` (WTK-096) — §3 metric definitions, §5 flags, §6 the profile contract
- `catalog-normalizer-type-mapping-and-partition.md` (WTK-102) — §2 two-stage architecture, §3.10 fallback, §6 criteria N1–N9
- `espo_impl/core/data_profiler.py` — the EspoCRM profiler whose output contract this adapter's profile shares
- `specifications/master-crmbuilder-PRD.md` §7/§8 — Phase 1.5 rules and the triage consumer

# Methodology Design Spec — Spreadsheet Source Store and Profiling-Output Persistence

**Last Updated:** 06-12-26
**Status:** Draft v1.0 — produced under WTK-111 (storage-area spec deliverable, Design phase of PI-156 Spreadsheet source adapter)
**Position in workstream:** Companion to `spreadsheet-profiler-adapter-and-seam-conformance.md` (WTK-110), which designed the adapter as a pure function of files — paths in, manifest pair out — and drew the boundary at §3.4: "Where uploaded workbooks live, how uploads become the per-sheet CSV layout, retention, and any REST upload surface are WTK-111's persistence scope." This spec owns that scope on both sides of the adapter: the **source store** where client-supplied workbook files are held during and after profiling (location, layout, intake, size limits, retention, sensitive-data handling — §3) and the **output persistence** of the normalized inventory the adapter emits (where the manifest pair lands, how the resulting candidate records and evidence persist through the unchanged deposit path — §4). The Work Task's named verification criterion — schema review against the existing normalized-inventory storage used by the EspoCRM path — is §5, conducted against the landed code at the commit this spec is authored on.
**Companion documents:** `spreadsheet-profiler-adapter-and-seam-conformance.md` (WTK-110 — the adapter and the seam; this spec changes nothing it pinned); `audit-report-to-candidate-deposit-transform.md` (WTK-090 — the deposit path both adapters share); `candidate-lifecycle-rejected-and-utilization-evidence.md` (WTK-088 — the evidence table and its latest-snapshot rule); `governance-schema-specs/deposit-path-provenance-and-schema.md` (WTK-089 — the `deposit_event_kind` discriminator and `audit_deposit` apply_context contract); `migration_mapping.md` (WTK-104 — the downstream compile contract whose source-extraction step the retained snapshot serves); `specifications/master-crmbuilder-PRD.md` §7 (Phase 1.5 rules).

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 06-12-26 | ADO Area Specialist (storage) / Claude | Initial draft under WTK-111. Defines the gitignored, engagement-keyed, snapshot-immutable source store at `crmbuilder-v2/data/sources/` with a `source-manifest.json` content-identity record (names, bytes, SHA-256) per snapshot; intake as a small CLI that copies operator-supplied files into the canonical layout (REST/portal upload deferred); enforced-with-override size limits (100 MiB/file, 500 MiB/snapshot); a first-time-at-rest sensitive-data posture (client record data held by CRMBuilder for the first time — never under a git-tracked tree, never in the client repo, no cell values in any log, same at-rest class as the unified engagement DB); and engagement-lifetime retention justified by the snapshot's second life as the migration compiler's source-of-record (WTK-104 §6.3). Output side: the manifest pair lands in the snapshot directory (not the client repo — it carries record-data excerpts, unlike the EspoCRM audit's schema YAML), and DB persistence rides the landed deposit path unchanged. Pins the source-label stability invariant (all snapshots of one source produce one `evidence_source_label`, keeping the WTK-088 per-(subject, source) latest-snapshot rule working across re-uploads) and the registered-snapshot source-identity rule that delivers it. Schema review (§5) verdict: full interchangeability with **zero storage-layer schema or migration changes**; every storage delta is config helper + gitignore + intake utility. |

---

## Change Log

**Version 1.0 (06-12-26):** Initial creation. No code ships with this document — it is the design the implementing Work Tasks build from. §7 enumerates the build surface.

---

## 1. Purpose and Position

The EspoCRM Phase 1.5 path holds no client record data at rest: the audit and profiler read the live CRM over REST, the audit output directory (`programs/audit-YYYYMMDD-HHMMSS/` in the client repo) carries schema YAML plus the manifest pair, and the record data itself stays in the CRM, re-contactable at any time. The spreadsheet adapter inverts both properties. Its input **is** the client's record data — a workbook of real names, emails, donations — and once the client hands the file over there is no live system behind it to re-contact: the held file is the only copy CRMBuilder has, and (per WTK-104 §6.3) the only thing a future migration compile can extract records from.

That inversion creates the two storage problems this spec resolves:

1. **Input side (§3):** client-supplied workbook files must be *held* — somewhere deliberate, with content identity, size discipline, a retention rule that survives until migration, and a sensitive-data posture for the first time CRMBuilder keeps client record data at rest.
2. **Output side (§4):** the manifest pair and everything downstream of it must persist so that spreadsheet-born inventory records are **interchangeable** with EspoCRM-born ones — same tables, same constraints, same provenance chain, same triage and migration consumers — which §5 verifies structure-by-structure against the landed schema.

Phase-rule constraints inherited from Master PRD §7 bind unchanged: provenance is mandatory (one deposit event per source), candidates never auto-confirm, evidence travels with the candidate. The seam (WTK-110 §2) already guarantees the behavioral half of interchangeability; this spec supplies the persistence half and proves the storage layer needs nothing new to receive it.

---

## 2. Design Overview

```
crmbuilder-v2/data/sources/                          ← gitignored root (config.sources_dir())
└── {ENGAGEMENT}/                                    ← engagement code, e.g. CRMBUILDER
    └── {source-slug}/                               ← one workbook = one source (WTK-110 §3.3)
        ├── 20260612T081500Z/                        ← snapshot: immutable once registered
        │   ├── source-manifest.json                 ← content identity (names, bytes, sha256)
        │   ├── originals/                           ← as-received files, byte-preserved
        │   │   └── cbm-mentor-tracking.xlsx
        │   ├── mentors.csv                          ← per-sheet CSVs = the adapter input
        │   ├── donations.csv
        │   ├── audit-report.json                    ← adapter output (profiler run writes)
        │   └── utilization-profile.json
        └── 20260701T140000Z/                        ← re-upload = a new snapshot, never overwrite
            └── …
```

The flow: **intake** registers operator-supplied files into a new snapshot (§3.3) → the **profiler** (WTK-110) runs over the snapshot's CSVs and writes the manifest pair into the same snapshot directory (§4.1) → the **deposit CLI** (`crmbuilder-v2-deposit-audit`, landed) carries the pair into the V2 DB exactly as it does for an EspoCRM manifest (§4.2). Files stay put for the engagement's lifetime (§3.6); the DB rows are the inventory of record, and the snapshot is the data-of-record behind them.

---

## 3. The Source Store

### 3.1 Location

The store root is `crmbuilder-v2/data/sources/`, exposed as `config.sources_dir()` — a repo-rooted module-level helper following `api_log_path()` / `verify_log_dir()` exactly (same `_repo_root()` derivation, same docstring posture), with an optional `CRMBUILDER_V2_SOURCES_DIR` Settings override for tests and future production topology. Repo-rooted, not engagement-DB-adjacent, because the store is file storage, not database storage; one durable location regardless of which engagement is active.

The root is **gitignored** (a new `.gitignore` entry — `crmbuilder-v2/data/` is per-entry ignored, and `sources/` is not currently covered). This is load-bearing, not housekeeping: the store holds client record data, and §3.5's first rule is that such data never sits under a git-tracked path where a careless `git add -A` could publish it.

Within the root, the first level is the **engagement code** (the same value the `X-Engagement` header accepts, e.g. `CRMBUILDER`), matching the retired per-engagement-DB layout (`data/engagements/CRMBUILDER.db`) — human-navigable and unique. The second level is the **source slug**: lowercase `[a-z0-9-]+`, derived from the operator's `--source-name` (or the upload's basename) by the same trim/collapse/slugify family the adapter applies to headers (WTK-110 §4.1), kebab-cased for path use. One slug directory = one source = one workbook = one deposit-event stream, per WTK-110 §3.3.

### 3.2 Snapshots and `source-manifest.json`

The third level is the **snapshot**: a directory named by its UTC registration instant, `YYYYMMDDTHHMMSSZ` (the runtime-log timestamp idiom). A snapshot is **immutable once registered** — intake never writes into an existing snapshot; a corrected or refreshed upload is a *new* snapshot beside the old one. Immutability is what makes everything downstream trustworthy: the profiler's determinism criterion (WTK-110 C6) is meaningful only over frozen bytes; the deposit's provenance points at content that cannot have drifted; and the migration compiler (§3.6) extracts from exactly what was profiled.

Each snapshot carries a `source-manifest.json` written by intake — the content-identity record that lets any later consumer verify it is reading what was registered:

```json
{
  "source_manifest_version": 1,
  "engagement": "CRMBUILDER",
  "source_name": "CBM Mentor Tracking",
  "source_slug": "cbm-mentor-tracking",
  "registered_at": "2026-06-12T08:15:00Z",
  "registered_by": "doug",
  "originals": [
    {"name": "cbm-mentor-tracking.xlsx", "bytes": 412884, "sha256": "9f8a…"}
  ],
  "sheets": [
    {"file": "mentors.csv", "bytes": 88412, "sha256": "1c2d…",
     "original": "cbm-mentor-tracking.xlsx", "sheet_name": "Mentors"},
    {"file": "donations.csv", "bytes": 31755, "sha256": "7e0b…",
     "original": "cbm-mentor-tracking.xlsx", "sheet_name": "Donations"}
  ],
  "oversize_allowed": false,
  "notes": null
}
```

- `originals/` preserves the as-received files byte-for-byte (the `.xlsx` the client actually sent). v1 never reads them (WTK-110 §3.2 defers native ingestion); they are retained because they are the client's artifact of record — when a CSV export question arises ("did the export mangle that date column?"), the original answers it, and when native ingestion lands (§6) the original becomes directly profilable without asking the client again.
- `sheets[]` lists the per-sheet CSVs at the snapshot root — the adapter's input set. The `original`/`sheet_name` keys record which workbook sheet each CSV came from, when known (operator-supplied or filename-derived; both nullable for a CSV-only intake with no original).
- SHA-256 per file is the content identity the provenance chain terminates in (§4.2) and the migration pre-flight verifies (§3.6).

The adapter reads `*.csv` at the snapshot root (per WTK-110 §3.3, "a directory of CSV files"); `source-manifest.json`, the output JSONs, and the `originals/` subdirectory are not CSVs and are naturally outside its input glob.

### 3.3 Intake — how uploads become the layout

v1 intake is a small CLI, `crmbuilder-v2-register-source`:

```
crmbuilder-v2-register-source <file-or-dir>… --engagement <ENG> --source-name <name>
    [--sheet-name FILE=NAME]… [--allow-oversize]
```

It creates the next snapshot directory, copies the supplied files in (CSVs to the root, anything else to `originals/`), computes sizes and hashes, enforces the §3.4 limits, writes `source-manifest.json`, and prints the snapshot path — which is then the input to `crmbuilder-v2-spreadsheet-profile` (WTK-110 §9.4). Splitting a workbook into per-sheet CSVs remains the operator's export step in v1 (every spreadsheet product has it, per WTK-110 §3.2); intake registers the results, it does not convert.

**No REST upload surface in v1.** The V2 API is a localhost, single-operator service today; the operator has the filesystem, and a `multipart/form-data` endpoint would add an attack/PII surface with no current consumer. The deliberate future consumer is the stakeholder portal direction (API-driven web portal for stakeholder capture) — when a remote stakeholder needs to hand a workbook over without the operator in the loop, the portal's backend POSTs into this same store layout through a then-designed endpoint. Deferred with that shape in mind (§6); the store layout is the stable contract either path writes into.

The desktop UI equivalent (a file-picker dialog that shells the same registration function) is a follow-on convenience, not v1 scope — monitoring-first UI posture.

### 3.4 Size limits

Enforced at intake, per file and per snapshot:

| Limit | Default | On breach |
|---|---|---|
| Per file | 100 MiB | refuse with `source_file_too_large`, naming the file and both numbers |
| Per snapshot (sum incl. originals) | 500 MiB | refuse with `snapshot_too_large` |

`--allow-oversize` overrides both, recording `oversize_allowed: true` in the manifest so the exception is visible forever — the enforced-with-override posture (the governance-rule hybrid, applied to a file gate).

Rationale for the numbers: the adapter streams rows through the stdlib `csv` reader and bounds memory by the distinct-tracking cap (1,000 values/field) and option distributions, so the cap is not protecting profiler correctness — it is protecting the intake copy, the Dropbox-synced disk (§3.5), and the operator from registering something that is not a small-organization workbook at all. 100 MiB of CSV is roughly half a million to a million rows — past every real workbook in the adapter's target population (Master PRD §7: "for small organizations the existing system is most often a spreadsheet"). A genuine outlier passes with the override and its visible manifest flag.

### 3.5 Sensitive-data handling

The spreadsheet path is the **first time CRMBuilder holds client record data at rest**. Every prior surface kept it elsewhere: the EspoCRM adapter reads the live CRM and persists metrics; the import wizard reads files in place from operator-chosen paths and retains nothing; instance credentials go to the OS keyring. A held workbook is names, emails, phone numbers, donation amounts. Five rules:

1. **Never under a git-tracked tree.** The store root is gitignored (§3.1); nothing in the layout is ever a candidate for commit. In particular, the store is **not** in the client repo — unlike the EspoCRM audit output, which is schema-only YAML and belongs there. The same rule extends to the adapter's outputs (§4.1).
2. **No cell values in any log.** Intake logs names, byte counts, and hashes — never content. The profiler's run output and the deposit-event log (`deposit-event-logs/dep_NNN.log`, which **is** git-tracked) carry sheet names, header names, counts, and anomaly notes — never cell values. This is the `mask_secrets()` discipline applied to PII: the boundary is "structure and metrics may be logged; data may not." WTK-110 already embeds the same boundary in the persisted evidence (`sample_values` omitted for email/phone inferences, §5.1); this spec makes it a store-wide rule with a verification criterion (S7).
3. **Same at-rest class as the unified engagement DB.** The store lives beside `v2-unified.db`, which already persists client-derived value distributions and top-values. One protection class, one location, one answer to "where is client data on this machine." No application-layer encryption in v1 — the deployment-phase production topology (PI-α's deferred Deployment work) is where at-rest encryption gets decided for DB and store together, not piecemeal here (§6).
4. **Bounded excerpts only in the DB.** What crosses from the store into the database is the manifest pair's content: observed enum option lists, `top_values` (≤ 10 values, ≤ 100-distinct columns), `sample_values` (≤ 5, redacted for email/phone), value distributions. Bounded and triage-justified — but still client data, which is why the evidence rows inherit the DB's protection class rather than being treated as anonymous metrics. Whether redaction should widen (e.g. name-like text columns) is an open question for triage practice to answer (§6).
5. **Deletion is a procedure, not a hope.** A client's deletion request is satisfiable: snapshots are plain directories, enumerable per engagement, and removing them removes the record data. What survives in the DB after a file purge is the candidate records and evidence rows — counts, rates, and the bounded excerpts of rule 4. A purge CLI that also scrubs excerpt keys out of `evidence_detail` (an UPDATE against an append-only-by-convention table, so it needs its own design care) is deferred (§6); v1 documents the manual path: delete the snapshot directories, and if excerpt scrubbing is required, handle it as an operator procedure against the named evidence rows.

### 3.6 Retention

**Snapshots are retained for the life of the engagement.** This is not caution — it is the migration design. WTK-104's compile contract (§6.2–§6.3) extracts source records "from the snapshot," addressed by the literal source coordinates denormalized onto each `migration_mapping` (`source_entity_name`, `source_attribute_name`). For a spreadsheet source those coordinates are exactly the manifest's `espo_name` (sheet file name) and `api_name` (literal header text) — which resolve directly against the held snapshot's CSVs. The EspoCRM path can re-contact its live CRM at compile time; the spreadsheet path compiles from the snapshot **or not at all**. Deleting a deposited snapshot before migration completes severs every keep/transform mapping that points into it.

Concretely:

- A snapshot that has been deposited (a `deposit_event` references it, §4.2) is **locked**: the future purge surface refuses to remove it without an explicit force while the engagement has unresolved migration work. v1, with no purge CLI, states the rule for the operator.
- Superseded snapshots (older registrations of the same source) are retained too — they are the drift history behind the evidence trail, and they are cheap. Pruning policy is a real-use question (§6).
- Migration pre-flight (the WTK-104 compiler's first design task) verifies the referenced snapshot exists and its `source-manifest.json` hashes still match before extracting — the file-side analogue of WTK-104's Q6 gate, listed there as a cross-reference obligation.
- Post-engagement disposal (deployment validated, client confirms) is the §3.5 rule-5 deletion procedure, at the operator's initiative.

---

## 4. Output Persistence

### 4.1 The manifest pair lands in the snapshot

The profiler run writes `audit-report.json` and `utilization-profile.json` **into the snapshot directory it profiled** (the WTK-110 §9.4 CLI's default output-beside-input, made specific). They do not go to the client repo, deliberately breaking the EspoCRM symmetry (`programs/audit-…/` lives in the client repo): a spreadsheet manifest carries observed option values, and the profile carries `top_values`, `sample_values`, and full value distributions — record-data excerpts, governed by §3.5 rule 1. The EspoCRM manifest pair describes schema and metrics of data that lives elsewhere; the spreadsheet pair *contains* data excerpts of a file we hold. Different content class, different home.

Co-locating outputs with inputs also gives the pair the snapshot's properties for free: immutability convention (a re-profile of the same snapshot overwrites the pair, which is safe — C6 determinism means byte-identical regeneration; a *new upload* is a new snapshot with its own pair), the §3.6 retention rule, and one directory to point provenance at.

Writes are atomic (temp-file + rename), matching the landed profiler's `write()` idiom.

### 4.2 The provenance chain, file → database

DB persistence is the landed deposit path, unchanged: the operator runs `crmbuilder-v2-deposit-audit <snapshot>/audit-report.json --profile <snapshot>/utilization-profile.json --engagement <ENG>`, and `plan_deposit`/`execute_plan` produce entity and field candidates, evidence rows, the anomaly PI, and one `deposit_event` of kind `audit_deposit` — exactly as for an EspoCRM manifest, modulo WTK-110's consumer deltas D1–D4 (which are transform-layer, not storage-layer; §5.3 confirms the storage fit).

The chain that answers "where did this candidate's data come from, exactly":

```
field FLD-NNN
  ←(deposit_event_wrote_record)— DEP-NNN
      .deposit_event_apply_context.source_system   = "spreadsheet"        (D1)
      .deposit_event_apply_context.source_instance = "file:///…/sources/CRMBUILDER/cbm-mentor-tracking/20260612T081500Z"
      .deposit_event_apply_context.snapshot_at     = manifest timestamp
          → the snapshot directory
              → source-manifest.json → per-file SHA-256                   (content identity)
```

`source_instance` is the manifest's `source_url`, which the adapter sets to the `file://` URI of its input directory — the snapshot. The chain therefore terminates in hashed content: any consumer (triage audit, migration pre-flight, a dispute about what was profiled) can walk from a candidate to the exact bytes behind it. Evidence rows carry the per-file depth: WTK-110 §5.1 already pins `source_file` and `source_file_modified_at` in entity-level detail; this spec adds the optional **`source_file_sha256`** enrichment — when the input directory contains a `source-manifest.json`, the adapter copies each sheet's hash into its entity's detail block. (`source-manifest.json` is just another input file, so the adapter stays a pure function of files; an unregistered ad-hoc directory simply lacks the enrichment.)

### 4.3 Source identity and the label-stability invariant

One genuine interaction between this store and the landed evidence semantics, found by the §5 review:

`evidence_source_label` is the join key of the WTK-088 latest-snapshot rule — "latest evidence per *(subject, source)*" — and of the WTK-104 mapping join (`migration_mapping_source_system_label` matches it). It is derived by `derive_source_label` from the manifest's `source_url`; under WTK-110's delta D2, an empty-netloc `file://` URI labels by the URL path's basename. If the adapter's `source_url` were the literal snapshot path, the basename would be the timestamp component — **every re-upload would mint a new label**, each re-profile would look like a brand-new source, and the per-(subject, source) evidence history this store's snapshot model is supposed to feed would never accumulate.

**Invariant (pinned):** all snapshots of one source produce one `evidence_source_label`.

**Rule that delivers it:** when the adapter's input directory carries a `source-manifest.json`, the manifest's `source_url` is the `file://` URI of the **source directory** (the snapshot's parent — `…/sources/CRMBUILDER/cbm-mentor-tracking`), and `source_name` defaults from the registered `source_name`. D2's basename rule then yields the stable `spreadsheet @ cbm-mentor-tracking` across every snapshot. The snapshot's own identity is not lost — it travels in `apply_context.source_instance`? No: `source_instance` *is* `source_url` in the landed builder, so it is the source directory too, and the snapshot instant is carried by `snapshot_at` (= the manifest `timestamp`, the run over that snapshot) plus the per-file `source_file` / `source_file_sha256` evidence detail of §4.2, which resolve the exact snapshot content. For an unregistered ad-hoc input directory (no `source-manifest.json`), WTK-110's literal behavior stands unchanged — `source_url` = the input path, label from its basename — which is correct for the one-off case and self-inflicted for anyone re-profiling ad-hoc directories with varying names.

This is a refinement WTK-110's D2 absorbs without modification (D2's rule text is untouched; what changes is which path the adapter feeds it), and it is owned here because the store layout is what created — and resolves — the aliasing question.

### 4.4 Re-upload and re-profile semantics

The landed idempotency (WTK-090 §7) composes with snapshots as follows, no new mechanism:

- **Re-profile of the same snapshot** → byte-identical manifest pair (C6) → a re-deposit matches every candidate by name, creates nothing, appends one evidence row per subject with the same metrics under a new `profiled_at`, and emits its own deposit event. Harmless, useful as a repair path (WTK-090 T3).
- **New snapshot of the same source** (the client sent an updated workbook) → same source label (§4.3); sheets and headers that persist match by natural key and accumulate fresh evidence (drift signal); added sheets/columns create new candidates with `wrote_record` provenance from the new deposit event; vanished ones go evidence-stale, which *is* the dormancy signal (WTK-090 §7 rule 4). Sheet renames read as disappearance + new candidate — the known WTK-090 rename posture, unchanged.
- **A different workbook** is a different source: new slug, new label, one deposit event per source per run (Master PRD §7), candidates merging only on name collision per the WTK-088 multi-source posture.

---

## 5. Schema Review — Interchangeability with the EspoCRM-Path Inventory Storage

The Work Task's verification criterion: review the spreadsheet path's persistence against the normalized-inventory storage the EspoCRM path uses, structure by structure, against the landed code. **Verdict first: full interchangeability with zero schema or migration changes.** A spreadsheet-born candidate, evidence row, and deposit event are rows in the same tables under the same constraints as EspoCRM-born ones, distinguishable only by their values (`source_system`, label, catalog class) — which is the definition of interchangeable. Detail:

### 5.1 Candidate record tables (`entities`, `fields`)

| Aspect | EspoCRM path | Spreadsheet path | Fit |
|---|---|---|---|
| Types deposited | entity, field, persona, process, manual_config | entity, field only (WTK-110 §6.1: `roles`/`teams`/`filtered_tabs` empty) | ✓ subset |
| Status | `candidate`, always | identical (seam-supplied) | ✓ |
| `entity_kind` | mapped or omitted (null admitted per DEC-292) | always null (`entity_type: null`) | ✓ designed deferral |
| `field_type` | `FIELD_TYPES` via `composed_type_map("espocrm")` | `FIELD_TYPES` via `composed_type_map("spreadsheet")` (D1/D3); WTK-110 §6.3 table is total, every image ∈ `FIELD_TYPES` | ✓ same closed vocabulary |
| `field_belongs_to_entity` edge | atomic with row | identical (landed `create_field`) | ✓ |
| Natural keys / idempotency | `entity_name`, (parent, `field_name`) | identical; names derive deterministically from sheet/header labels (WTK-110 §4.1) | ✓ |
| `notes` `Source:` block | wire entity/field names + type | identical mechanism; wire identity = sheet name, header text, inferred type | ✓ losslessness rule holds |

No column, CHECK, or uniqueness constraint on either table reads a value the spreadsheet path cannot supply.

### 5.2 `utilization_evidence`

Reviewed against the model's constraints (`models.py`, `UtilizationEvidence`):

| Constraint / column | Spreadsheet value | Fit |
|---|---|---|
| `ck_evidence_subject_type` (∈ `BASELINE_CAPTURE_TYPES`) | `entity` / `field` only | ✓ |
| `ck_evidence_catalog_class` (∈ {standard, custom} or NULL) | `custom`, always (D4 constant partition) | ✓ — the `standard` arm simply never fires |
| `ck_evidence_population_rate_range` [0, 1] | computed rate; note the spreadsheet boolean posture (WTK-110 §4.6) computes it normally rather than pinning 1.0 — still in range | ✓ |
| Count nonneg CHECKs | exact counts (no sampling) | ✓ |
| `evidence_declared_option_count` / `used_option_count` | equal by construction (a spreadsheet declares nothing); ghost-option signal structurally zero, documented honest at WTK-110 §4.6 | ✓ — semantic note, not a constraint issue |
| `evidence_profiled_at` | profile `profiled_at` (run instant) — strictly increasing across re-profiles, so the latest-snapshot index ordering works | ✓ |
| `evidence_source_label` (TEXT, no format CHECK; the per-(subject, source) join key) | stable per §4.3's invariant | ✓ given §4.3; **without** §4.3 this is the one place interchangeability would silently degrade |
| `evidence_deposit_event_identifier` (`DEP-` format or NULL) | this run's DEP | ✓ |
| `evidence_detail` (JSON) | `type_inference` / `reference_inference` blocks ride the landed verbatim detail passthrough; `source_file_sha256` (§4.2) is an additive key in a schemaless column | ✓ |

### 5.3 `deposit_events`

| Aspect | Finding |
|---|---|
| `deposit_event_kind` | **Reuse `audit_deposit` — no new kind.** The WTK-089 discriminator distinguishes deposit *pathways* (close-out apply vs. source-baseline deposit), not adapters; adapter identity is `apply_context.source_system`, which D1 feeds from the manifest. `DEPOSIT_EVENT_KINDS` is untouched, so no vocab/CHECK migration. A `spreadsheet_deposit` kind would fork every kind-switched consumer for zero information the apply_context doesn't carry. |
| Required apply_context keys (`_require_audit_apply_context`) | `source_system = "spreadsheet"` (non-empty string — the validator checks shape, not membership, so D1 needs no storage change); `source_instance` = the `file://` source URI (non-empty ✓); `snapshot_at` = manifest timestamp (ISO 8601 ✓). |
| Close-out payload | `audit_deposit` forbids the payload parent edge (landed WTK-089 behavior) — fits; nothing file-side pretends to be a payload. |
| `records_summary` | entities + fields keys only — the landed sum-equals-edges rule holds. |
| `deposit_event_log_file_path` | unchanged convention (`deposit-event-logs/dep_NNN.log`, git-tracked, Model A `main`-only) — subject to §3.5 rule 2 (no cell values), which the landed plan output already satisfies (names and counts only). |

### 5.4 References vocabulary

`deposit_event_wrote_record` already admits `entity`, `field`, and `planning_item` targets (the WTK-090 build closed that gap for the EspoCRM path); the spreadsheet path emits no relationship/role/team structures, so no pair rule, no `REFERENCE_RELATIONSHIPS` change, no `ck_ref_relationship` rebuild, and therefore none of the standing migration gotchas (change_log CHECK, dual-head, mid-stream guard) are even in play.

### 5.5 Downstream consumers (read-side interchangeability)

- **Triage (WTK-088 queries):** Q1 low-population, dormancy, and ghost-option queries run unmodified over spreadsheet-born evidence; ghost options read zero by construction (§5.2), the documented-honest posture.
- **Migration mapping (WTK-104):** `migration_mapping_source_system_label` joins on the stable label (§4.3); `source_entity_name` / `source_attribute_name` hold the literal sheet name and header text, which resolve against the retained snapshot (§3.6) — the spreadsheet path is actually the *stronger* case for WTK-104's denormalized-coordinates posture, since there is no live system to consult instead.
- **Idempotency / `ExistingState`:** name-keyed, status-blind — adapter-agnostic by construction.

### 5.6 Storage deltas required

None to schema. The complete storage-area build surface is filesystem-and-config: `config.sources_dir()`, the gitignore entry, the intake utility, and the §4.3 source-identity rule inside the adapter's manifest assembly (a WTK-110-build touchpoint owned jointly). §7 enumerates.

---

## 6. Open Questions and Deferred Decisions

- **REST/portal upload** (§3.3): deferred until the stakeholder-portal backend exists; the store layout is the contract it will write into. Brings auth, quotas, and virus-scanning questions with it.
- **At-rest encryption** (§3.5): decided at the PI-α Deployment phase for DB and store together; v1 inherits the local-single-operator posture.
- **Evidence-excerpt redaction breadth** (§3.5): WTK-110 redacts `sample_values` for email/phone inferences; whether name-like text columns warrant the same (at the cost of triage signal) is a question for real triage practice.
- **Purge CLI** (§3.5, §3.6): snapshot deletion with deposit-reference guard (`--force` past the lock), plus optional `evidence_detail` excerpt scrubbing — the latter needs design care against the append-only evidence convention.
- **Snapshot pruning policy** (§3.6): superseded-snapshot retention is currently "keep everything"; revisit if store size becomes real.
- **Native-format originals as input** (§3.2): when WTK-110 §8's `.xlsx` ingestion lands, `originals/` becomes directly profilable and the intake's CSV-export instruction relaxes.
- **Intake-time sheet splitting**: intake registers operator-exported CSVs; auto-splitting an `.xlsx` into per-sheet CSVs at intake is the natural follow-on once a native reader exists (same dependency decision as above).

---

## 7. Build Surface (for the implementing Work Tasks)

This spec ships no code. In dependency order:

1. **`config.py`:** `sources_dir()` module helper (repo-rooted, `api_log_path()` idiom) + `CRMBUILDER_V2_SOURCES_DIR` Settings override.
2. **`.gitignore`:** add `crmbuilder-v2/data/sources/`.
3. **Intake** — `crmbuilder-v2/src/crmbuilder_v2/adapters/source_store.py` (the WTK-110 §9.3 `adapters` subpackage): `register_source(files, engagement, source_name, *, sheet_names=None, allow_oversize=False) → Path` implementing §3.2–§3.4 (layout, hashing, limits, manifest write, atomicity); CLI `crmbuilder-v2-register-source` in the root `pyproject.toml`.
4. **Adapter touchpoints** (built with WTK-110's adapter, designed here): the §4.3 registered-snapshot source-identity rule (`source-manifest.json` present → `source_url` = source-dir URI, `source_name` default) and the §4.2 `source_file_sha256` evidence-detail enrichment; output written into the snapshot via the existing `--output-dir` default, atomic writes.
5. **No migrations, no vocab changes, no model changes** (§5.6 — the review's central result; D1–D4 are WTK-110's transform-layer surface).
6. **Tests** per §8.

---

## 8. Verification Criteria

**S1 — Registration round-trip.** Registering one `.xlsx` original plus two CSVs yields the §2 layout: snapshot dir named by UTC instant, CSVs at root, original under `originals/`, `source-manifest.json` with correct names, byte counts, and SHA-256 values (independently recomputed by the test).

**S2 — Snapshot immutability.** A second registration for the same source creates a sibling snapshot; the first is byte-identical before and after. Intake exposes no path that writes into an existing snapshot.

**S3 — Size limits.** A file over 100 MiB → `source_file_too_large`; a snapshot summing over 500 MiB → `snapshot_too_large`; both pass with `--allow-oversize` and the manifest records `oversize_allowed: true`. (Sparse/truncated fixtures, not real 100 MiB files.)

**S4 — Gitignore coverage.** `git check-ignore` confirms a path under `crmbuilder-v2/data/sources/` is ignored.

**S5 — Label stability.** Two snapshots of one registered source, profiled and deposited in sequence: both deposits produce the same `evidence_source_label`; the WTK-088 latest-snapshot query returns the second run's rows; candidate counts unchanged on the re-deposit (WTK-090 T3 semantics over snapshots, §4.4).

**S6 — Schema fit, end to end.** The WTK-110 G-1 golden manifest pair, placed in a registered snapshot and driven through the landed `plan_deposit`/`execute_plan` against a live test DB (with D1–D4 in place): every row lands with zero constraint violations; `evidence_catalog_class = "custom"` throughout; the deposit event is kind `audit_deposit` with `apply_context.source_system = "spreadsheet"` and `source_instance` the source-dir `file://` URI; every evidence `detail` carries its `type_inference` and, for registered input, `source_file_sha256`. (This is §5 made executable — it subsumes WTK-110's C2 with the store in the loop.)

**S7 — No cell values in logs.** A fixture sheet seeded with a sentinel cell value: the sentinel appears in no intake output, no profiler run output, and no deposit-event log; it does appear (bounded) only where §3.5 rule 4 admits it — manifest options / profile distributions / DB evidence.

**S8 — Provenance chain walk.** From a deposited field candidate: `wrote_record` → deposit event → `apply_context.source_instance` → an existing directory whose `source-manifest.json` hashes match the held files — the §4.2 chain, asserted as a test, and the shape of the future migration pre-flight check (§3.6).

**S9 — Deposit-reference lock (rule-level, v1).** With no purge CLI in v1, S9 is the documented-rule check: the snapshot referenced by S6's deposit event is resolvable from the DB alone (S8), so any future purge surface can implement the §3.6 guard; the purge CLI's own tests land with it.

---

## 9. Cross-References

**Decisions to be authored at build-closure** (descriptive, unnumbered — identifiers claimed on `main` at apply time per Model A): (a) the gitignored engagement-keyed snapshot-immutable source store and its content-identity manifest; (b) engagement-lifetime retention with the deposited-snapshot lock (migration source-of-record); (c) the first-at-rest sensitive-data posture (no git-tracked client data, no cell values in logs, DB-class protection, deletion procedure); (d) the source-label stability invariant and registered-snapshot source-identity rule; (e) reuse of the `audit_deposit` deposit-event kind for spreadsheet deposits.

- `spreadsheet-profiler-adapter-and-seam-conformance.md` (WTK-110) — the adapter this store feeds; §3.3 the source unit, §3.4 the boundary this spec fills, §6.1 the emission table (§4.3 here refines which path feeds `source_url`), §9 the joint build surface.
- `audit-report-to-candidate-deposit-transform.md` (WTK-090) — the shared deposit path; §7 idempotency (composed with snapshots in §4.4).
- `candidate-lifecycle-rejected-and-utilization-evidence.md` (WTK-088) — the evidence table; §4.4 the per-(subject, source) latest-snapshot rule behind §4.3's invariant.
- `governance-schema-specs/deposit-path-provenance-and-schema.md` (WTK-089) — `deposit_event_kind`, the `audit_deposit` apply_context required keys (§5.3).
- `migration_mapping.md` (WTK-104) — §6.2/§6.3 the compile contract whose source-extraction step the retained snapshot serves (§3.6).
- `crmbuilder-v2/src/crmbuilder_v2/transform/audit_deposit.py` — `derive_source_label` (D2 interplay, §4.3), `plan_deposit` apply_context assembly, `RestDepositClient` write path.
- `crmbuilder-v2/src/crmbuilder_v2/access/models.py` — `UtilizationEvidence` (the §5.2 constraint review subject); `access/repositories/deposit_events.py` — `_require_audit_apply_context` (§5.3).
- `crmbuilder-v2/src/crmbuilder_v2/config.py` — `api_log_path()` / `verify_log_dir()`, the path-helper idiom §3.1 follows.
- `espo_impl/core/data_profiler.py` — the EspoCRM profiler's atomic `write()` idiom (§4.1).
- `specifications/master-crmbuilder-PRD.md` §7 — Phase 1.5 rules (one deposit per source, mechanical capture, provenance); §8 — the migration obligation behind §3.6.

---

*End of document.*

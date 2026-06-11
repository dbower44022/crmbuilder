# Methodology Design Spec — AuditReport-to-Candidate Deposit Transform

**Last Updated:** 06-11-26
**Status:** Draft v1.0 — produced under WTK-090 (Development-area spec deliverable for the audit-to-V2 deposit path)
**Position in workstream:** Companion to `candidate-lifecycle-rejected-and-utilization-evidence.md` (WTK-088), which defined *where* utilization evidence lives and *how* candidates terminate; this spec defines *how candidates enter* — the transform that turns a V1 `AuditReport` into candidate methodology records deposited into the V2 engagement DB with deposit-event provenance. Together they cover the Phase 1.5 storage path named open in Master CRMBuilder PRD v0.2 §7 Known Limitations ("the transform from `AuditReport` to candidate methodology records plus deposit-event provenance is new work", commit `9681039`).
**Companion documents:** `candidate-lifecycle-rejected-and-utilization-evidence.md` (evidence table §4, build surface §6); `specifications/master-crmbuilder-PRD.md` §7 (Phase 1.5) and §8 (Phase 3 triage); the per-entity specs of the five target record types (`entity.md`, `field.md`, `persona.md`, `process.md` / `process-v2.md`, `manual_config.md`); `PRDs/product/features/feat-audit.md` (the V1 Audit feature that produces the input).

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 06-11-26 | ADO Area Specialist (access) / Claude | Initial draft under WTK-090. Defines the serialized-AuditReport boundary (audit additionally writes `audit-report.json`; the transform is a crmbuilder-v2 CLI consuming it), the field mapping from `AuditReport` structures to the five candidate record types (entity, field — including relationships-as-reference-fields — persona, process, manual_config), one deposit_event per source system with `wrote_record` provenance and a defined `apply_context` shape, evidence attachment per the WTK-088 §4 `utilization_evidence` table, natural-key idempotency with never-touch-existing semantics, the REST write path mirroring `apply_close_out.py`, and fixture-based verification criteria. Names the two vocab gaps the build must close: `deposit_event_wrote_record` does not yet admit methodology target types, and `create_process` requires a live domain (resolved by a per-source baseline placeholder domain). |

---

## Change Log

**Version 1.0 (06-11-26):** Initial creation. No code ships with this document — it is the design the implementing Work Tasks build from. §9 enumerates the build surface.

---

## 1. Purpose and Position

Master CRMBuilder PRD v0.2 §7 defines Phase 1.5 (Existing System Baseline): capture each existing client system as **candidate** methodology records carrying provenance and utilization evidence, so Phase 3 triage can give every item a deliberate disposition. Its Known Limitations name the gap this spec closes:

> The audit → V2 deposit path is not yet built. The Audit function currently emits YAML program files and V1 client-database rows; the transform from `AuditReport` to candidate methodology records plus deposit-event provenance is new work.

The V1 Audit feature (`espo_impl/core/audit_manager.py`) already discovers the source system's configuration into an in-memory `AuditReport` aggregate (entities with fields, layouts, and filtered tabs; relationships; roles; teams). This spec defines the transform that carries that aggregate into the V2 requirements graph:

- five candidate record types written at `candidate` status — `entity` (`ENT-`), `field` (`FLD-`), `persona` (`PER-`), `process` (`PROC-`), `manual_config` (`MCF-`);
- one `deposit_event` (`DEP-`) per source system per run, with `deposit_event_wrote_record` edges to every record the run created and an `apply_context` carrying source identity and snapshot timestamp;
- `utilization_evidence` rows (WTK-088 §4) attached to every candidate the run touched, created or matched;
- idempotent re-run behavior so a second audit of the same source appends evidence rather than duplicating candidates.

Phase-rule constraints inherited from Master PRD §7 that the design must make structural, not procedural: **candidates never auto-confirm** (every record enters at `candidate`; the transform never writes any other status and never transitions an existing record), **provenance is mandatory** (every created record is reachable from its deposit event via `wrote_record`), and **one deposit event per source system** per run.

---

## 2. Inputs and the Serialization Boundary

### 2.1 The `audit-report.json` manifest

The transform does **not** import `espo_impl` (and `espo_impl` does not import `crmbuilder_v2`). The boundary is a serialized manifest: the audit run additionally writes its `AuditReport` dataclass tree as JSON to `audit-report.json` at the root of the audit output directory (`programs/audit-YYYYMMDD-HHMMSS/`), alongside the YAML it already emits. The serialization is a direct `dataclasses.asdict` of `AuditReport` plus a `manifest_version` key (starting at `1`), with two adjustments:

- `EntityAuditResult.entity_class` (and the per-field class where carried) serialize as their enum `.value` strings (`custom` / `native` / `system`);
- `FilteredTabAuditResult.filter` serializes via the existing `render_condition` structured form (`{all: [...]}`), or `null` when the audit could not recover the filter.

This boundary gives three properties at once: the two packages stay decoupled; an audit run is **replayable** into V2 without re-contacting the source system; and the manifest **is** the fixture format for the verification suite (§8) — test fixtures are literal `audit-report.json` files.

### 2.2 The optional utilization profile

The data profiler (Master PRD §7 Activity 2 — population rates, recency, value distributions) is separate, unbuilt work. The transform accepts its output as an **optional** second input, `utilization-profile.json`, keyed by EspoCRM wire names:

```json
{
  "manifest_version": 1,
  "profiled_at": "2026-06-11T18:00:00Z",
  "entities": {
    "CEngagement": {
      "record_count": 412,
      "last_record_created_at": "2026-06-09T14:22:00Z",
      "fields": {
        "engagementStage": {
          "populated_count": 398, "population_rate": 0.966,
          "last_populated_at": "2026-06-09T14:22:00Z",
          "distinct_value_count": 5,
          "declared_option_count": 7, "used_option_count": 5,
          "detail": {"value_distribution": {"active": 211, "...": 0}}
        }
      }
    }
  }
}
```

When the profile is supplied, its metrics populate the typed `utilization_evidence` columns (§5). When absent (a schema-only deposit), the transform still runs: evidence rows carry `evidence_catalog_class`, the structural facts derivable from the report alone (`evidence_declared_option_count` from enum `options`), and `evidence_detail`; all data-derived metric columns stay NULL. The profile's `profiled_at` wins over the report `timestamp` as `evidence_profiled_at` when both are present.

### 2.3 Source identity

The transform derives a stable **source label** used everywhere a human-readable source identity is needed (`evidence_source_label`, the placeholder domain name §4.4, the deposit event title): `{product} @ {host}` where product is `espocrm` (the only adapter today) and host is the netloc of `AuditReport.source_url` (e.g. `espocrm @ crm.cbmentors.org`). `AuditReport.source_name` (the instance profile name) and the full URL travel in `apply_context` (§6.3).

---

## 3. Field Mapping — AuditReport to the Five Candidate Types

General rules applying to every mapping below:

- **Status is always `candidate`.** The transform passes no other status and never PATCHes a status. (`manual_config` likewise enters at `candidate`, never `completed`.)
- **Names come from source labels** (Master PRD §7 capture table), falling back to wire names when no label exists. Names are trimmed; the V2 repositories enforce non-empty.
- **Descriptions are synthesized when the source has none.** Every create-required description field gets a deterministic sentence naming the source, e.g. `Discovered by audit of espocrm @ crm.cbmentors.org.` — appended after the source description when one exists, used alone when not. Determinism matters for idempotent fixtures (§8).
- **The original wire identity always survives** in the record's `notes` field as a `Source:` block (wire entity name, wire field name, wire type) *and* in the evidence row's `evidence_detail`. Triage and the eventual migration mapping (Master PRD §8) need the wire names; the V2 records deliberately carry business-language names.

### 3.1 `EntityAuditResult` → `entity` candidate

| `entity` field | Source | Notes |
|---|---|---|
| `entity_name` | `label_singular`, else `yaml_name` | Engagement-global uniqueness; collision handling per §7 |
| `entity_description` | synthesized (general rule), incorporating `label_plural` where present | |
| `entity_kind` | mapped from EspoCRM `entity_type`: `Person` → `person`; `Company` → `organization`; `Event` → `event`; `Base` / `BasePlus` / unknown / `None` → omitted (`null`) | `kind` is optional per `entity.md` v1.1 §3.2.3 / DEC-292 — classification deferral is the designed behavior for exactly this case. No source type maps to `transaction`; triage assigns it where it fits. |
| `entity_notes` | `Source:` block — `espo_name`, `yaml_name`, `entity_type`, `entity_class`, `stream` flag | |
| `entity_status` | `candidate` | |

Scope: entities of `entity_class` `custom` always map. Entities of class `native` map **only when the audit captured custom fields or filtered tabs on them** (a bare untouched native entity is product stock, not requirements signal — it would survive triage trivially and add noise). Class `system` never maps. The skipped-native rule is a transform rule, not an audit change: the manifest carries everything the audit captured.

Layouts (`EntityAuditResult.layouts`) do **not** map to candidate records — layout is presentation, not a requirement; the Master PRD §7 capture table deliberately omits them. The transform records only a per-entity layout summary (`{"layouts_captured": ["detail", "list", ...]}`) in the entity's evidence `evidence_detail`, preserving the signal "this entity had a curated UI" for triage.

### 3.2 `FieldAuditResult` → `field` candidate

| `field` field | Source | Notes |
|---|---|---|
| `field_belongs_to_entity_identifier` | the `ENT-NNN` of the parent `EntityAuditResult`'s candidate (created or matched this run) | `create_field` writes row + `field_belongs_to_entity` edge atomically |
| `field_name` | `label`, else `yaml_name` | Uniqueness scoped to the parent entity |
| `field_description` | synthesized (general rule) | |
| `field_type` | wire-type map below | |
| `field_required` | `properties.required` when present, else `false` | |
| `field_notes` | `Source:` block — `yaml_name`, `api_name`, wire `field_type`, retained `properties` of interest (`options`, `default`, audit flags) | |
| `field_status` | `candidate` | |

**Wire-type map** (EspoCRM metadata type → `FIELD_TYPES` vocab):

| EspoCRM wire type | `field_type` |
|---|---|
| `varchar`, `email`, `phone`, `url`, `personName`, `address` | `text` |
| `text`, `wysiwyg` | `long_text` |
| `enum` | `enum` |
| `multiEnum`, `checklist`, `array` | `multi_enum` |
| `date` | `date` |
| `datetime`, `datetimeOptional` | `datetime` |
| `currency`, `currencyConverted` | `money` |
| `bool` | `boolean` |
| `int`, `float`, `autoincrement` | `number` |
| `link`, `linkParent`, `linkMultiple`, `linkOne` | `reference` |
| `foreign` | `derived` |
| *anything else* | `text` fallback + anomaly (§3.6) |

The map is engine-side lossy by design — the V2 vocabulary is deliberately engine-agnostic (`field.md` §3.2.3) — and lossless in total because the wire type always survives in notes and evidence detail. Composite types (`address`, `personName`, `currency`) map as a single candidate field, not exploded into their storage columns; the explosion is an EspoCRM storage artifact, not a requirement. An unmapped wire type maps to `text` and raises an anomaly (§3.6); the map is extended, not silently widened.

Scope: fields of class `custom` always map (on both custom and native parents — `include_native_custom_fields`). `native` stock fields map **only when the utilization profile shows real use** (`population_rate` present and > 0)? **No** — resolved the other way: native stock fields are **not** transformed in v1. Master PRD §7 Activity 3 says standard items are "signal only where the data profile shows real use", but that judgment is exactly what Phase 3 triage performs; depositing hundreds of stock fields as candidates would bury the custom signal. Stock-field utilization arrives in the Baseline Report (rendered from the profile directly), and a used stock field the stakeholder confirms in triage is created as a new candidate there. Revisit if triage practice shows this loses signal. `SYSTEM_FIELDS` never map (the audit already excludes them).

### 3.3 `RelationshipAuditResult` → `field` candidates of type `reference`

There is no relationship methodology record; the V2 vocabulary models a relationship endpoint as a field of type `reference` (`field.md` v0.5 vocabulary, richer link typing deferred to v0.6+). Each `RelationshipAuditResult` maps to **one `reference`-type field candidate per audited side**:

- on the entity side (when `audited` is true and the entity has a candidate): `field_name` from `label`, else `link`; the `Source:` block records `link_type`, `link`, `entity_foreign`, `relation_name`;
- on the foreign side (when `audited_foreign` is true and the foreign entity has a candidate): symmetric, from `label_foreign` / `link_foreign`.

A side whose entity was not transformed (skipped native, §3.1) is itself skipped. The pairing (that the two field candidates are two ends of one source relationship) is recorded in both `Source:` blocks and both evidence details; a first-class cross-edge between the two field candidates is deferred until the field vocabulary grows richer link typing (no current `refs` kind expresses it, and inventing one is a schema decision out of this spec's scope).

Deduplication: a link captured both as a `FieldAuditResult` (wire type `link*`) and as a `RelationshipAuditResult` side maps **once**, keyed by the wire link name within the entity — the relationship mapping wins (it carries the foreign-entity context).

### 3.4 `RoleAuditResult` / `TeamAuditResult` → `persona` candidates

| `persona` field | Source | Notes |
|---|---|---|
| `persona_name` | role/team `name` | Engagement-global uniqueness; a role and a team sharing a name merge into one persona (§7) |
| `persona_role_summary` | role/team `description`, else synthesized: `Role discovered in espocrm @ {host}.` / `Team discovered in …` | required non-empty |
| `persona_responsibilities` | omitted (`null`) — the audit has no responsibility narrative | |
| `persona_notes` | `Source:` block — kind (`role` / `team`), and for roles a compact rendering of `scope_access` (per-entity access levels) and `system_permissions` | |
| `persona_status` | `candidate` | |

Per Master PRD §7: "Source roles and teams are persona *evidence*, not personas" — they enter as candidates precisely so triage can confirm them against, or merge them into, the Phase 1 interview personas. The role's permission payload (`scope_access`) rides in notes and evidence detail; it is **not** also emitted as a `role_permission` manual_config in v1 — roles are deployable through the v1.3 YAML schema, so they are not "manual config on the eventual target." The `role_permission` manual_config category is reserved for the genuinely undeployable §12.5 role-aware-visibility items, which the audit marks NOT_AUDITABLE and which surface as anomalies (§3.6), not records.

### 3.5 `FilteredTabAuditResult` → `process` candidate (+ `manual_config` when the filter was unrecoverable)

Per the Master PRD §7 capture table, automation and navigation structure are *process evidence*: "named for what it does, in business language where derivable."

| `process` field | Source | Notes |
|---|---|---|
| `process_name` | tab `label`, else `scope` | |
| `domain_identifier` | the per-source baseline placeholder domain — §4.4 | `create_process` requires a live domain |
| `process_purpose` | synthesized: `Filtered navigation tab over {entity} discovered in {source_label}; filter: {one-line render of the condition}.` | |
| `process_classification` | `unclassified` | per the capture table |
| `process_notes` | `Source:` block — `id`, `scope`, `acl`, `nav_order`, the structured filter AST | |

The six Phase 3 content fields (`steps`, `triggers`, …) are omitted — they are interview products, not audit products.

When `filter` is `null` (the audit hit an unknown where-item type and the operator must hand-write the filter), the transform **additionally** emits a `manual_config` candidate: category `saved_view`, `name` = `Recreate filter: {tab label}`, `description` synthesized, `instructions` = the audit warning text plus the tab's scope and id. This is the one manual_config source in today's `AuditReport`. Workflows, saved views (as such), and duplicate-check rules — the other Master PRD manual_config sources — are not yet captured by the audit; their mappings are defined when capture lands (`workflow` → `process` candidate + `manual_config` category `workflow`; saved view → `manual_config` category `saved_view`; duplicate rule → `manual_config` category `duplicate_check`), and the transform's mapping layer is structured so each is an added case, not a redesign.

### 3.6 Anomalies → Planning Items

Per Master PRD §7 ("anything unauditable is logged as a Planning Item, not silently dropped"), the transform accumulates anomalies and emits **one Planning Item per run per source** (not per anomaly) summarizing them: entries from `AuditReport.errors` and `warnings`, unmapped wire types (§3.2 fallback), skipped soft-deleted matches (§7), NOT_AUDITABLE advisories. Status `Draft`, body listing each anomaly with its source object. Zero anomalies → no PI. The PI is governance, not methodology — it gets a `wrote_record` edge like every other record the run created (the kind already admits `planning_item` targets).

---

## 4. Provenance — the Deposit Event

### 4.1 One deposit event per source system per run

Each transform run against one source manifest emits exactly one `deposit_event` as its **last** write (mirroring `apply_close_out.py`): every record POST has already succeeded, so the event can carry truthful `records_summary` and complete `wrote_record` edges. Multi-source clients run the transform once per source manifest, yielding one event per source (Master PRD §7 phase rule).

### 4.2 `wrote_record` edges and the vocab gap

The event carries a `deposit_event_wrote_record` edge to **every record the run created** — the five methodology types, the placeholder domain (first run only, §4.4), and the anomaly PI. `records_summary` counts by entity type and must sum to the number of `wrote_record` edges (enforced by `create_deposit_event`); **matched-but-not-created records get no edge and no count** — provenance edges state "this run wrote this record", and a re-run did not write the records it merely re-observed (re-observation provenance is the evidence row's `evidence_deposit_event_identifier`, §5).

**Vocab gap (build surface):** `_kinds_for_pair` currently admits `deposit_event_wrote_record` only for governance targets (`session`, `decision`, `planning_item`, `reference`, `conversation`, `work_ticket`, `commit`). The build adds the six methodology targets — `entity`, `field`, `persona`, `process`, `manual_config`, `domain` — to that clause, with the matching `ck_ref_relationship` CHECK rebuild (and the standing migration gotchas: dual-head SQLite + PG, mid-stream chain-entry guard).

### 4.3 `apply_context` and the close_out_payload parent

`apply_context` is the durable answer to "where did this come from, and as of when":

```json
{
  "kind": "audit_baseline_deposit",
  "source_system": "espocrm",
  "source_url": "https://crm.cbmentors.org",
  "source_name": "CBM Test",
  "source_label": "espocrm @ crm.cbmentors.org",
  "snapshot_timestamp": "<AuditReport.timestamp>",
  "profiled_at": "<profile.profiled_at | null>",
  "audit_manifest_path": "<repo-relative path to audit-report.json>",
  "manifest_version": 1,
  "transform_version": "<crmbuilder_v2.__version__>"
}
```

`create_deposit_event` requires exactly one `deposit_event_applies_close_out_payload` parent edge. An audit deposit has no session close-out, but the substrate's lazy-create path (PRD §3.5 forward-compatibility) covers it without schema change: the transform targets the next free `COP-NNN`, passing `target_file_path` = the manifest path, so the lazily created payload row *is* the registration of the manifest as the applied artifact. Its description marks it `audit_baseline_deposit`. Relaxing the parent-edge requirement was considered and rejected — minimal change, and the lazy payload preserves the uniform "every deposit applies a payload file" audit trail. `deposit_event_log_file_path` follows the existing convention: the transform tees its stdout to `deposit-event-logs/dep_NNN.log` (git-tracked; Model A — the transform, like `apply_close_out.py`, runs governance writes on `main` only).

Outcome semantics: `success` when every record POST and evidence POST succeeded; `failure` (with `error_info` carrying the failed POST's request summary, response body, and the progress count) when the run aborted partway — in which case the event's `wrote_record` edges cover exactly the records that did land, keeping provenance truthful, and the §7 idempotency makes the re-run resume cleanly.

### 4.4 The per-source baseline placeholder domain

`create_process` requires a live `domain`, but Phase 1.5 is mechanical — domain assignment is Phase 2/3 judgment, and the Master PRD capture table deliberately deposits no domains. The transform bridges this with **one placeholder domain per source**: name `Baseline: {source_label}`, status `candidate`, description stating it is a mechanical container for baseline process candidates pending triage re-homing. It is created on the first run that needs it (idempotent by name thereafter), receives a `wrote_record` edge on the run that created it, and is itself a triage item: Phase 3 re-homes its processes to real domains and rejects the placeholder (`rejected_by_decision`, per WTK-088 D1). If a run maps no processes, no placeholder is created. Alternative considered and rejected: relaxing `create_process` to admit domainless processes — a schema change rippling into `process.md` §3.5 and the UI for one mechanical caller's benefit.

---

## 5. Evidence Attachment

For **every candidate the run touched — created or matched —** the transform appends one `utilization_evidence` row per WTK-088 §4 (the PI-153 build surface, §6 of that spec). Evidence is the one thing a re-run always writes; it is how re-observation is recorded without mutating the candidate.

| Evidence column | Transform source |
|---|---|
| `evidence_subject_type` / `evidence_subject_identifier` | the candidate's type and `XXX-NNN` |
| `evidence_profiled_at` | profile `profiled_at` when supplied, else `AuditReport.timestamp` |
| `evidence_source_label` | §2.3 |
| `evidence_deposit_event_identifier` | this run's `DEP-NNN` (the event is POSTed last, so evidence rows are POSTed after it — see ordering note below) |
| `evidence_catalog_class` | entity/field class `custom` → `custom`, `native` → `standard`; NULL for persona/process/manual_config subjects |
| `evidence_record_count`, `evidence_last_record_created_at` | entity subjects, from the profile; NULL without profile |
| `evidence_populated_count`, `evidence_population_rate`, `evidence_last_populated_at`, `evidence_distinct_value_count` | field subjects, from the profile; NULL without profile |
| `evidence_declared_option_count` | enum/multi_enum field subjects, from the report's `options` property (no profile needed) |
| `evidence_used_option_count` | enum/multi_enum field subjects, from the profile |
| `evidence_detail` | the source-specific depth: wire names and type, value distributions, layout summary (§3.1), role `scope_access` payload, filter AST, relationship pairing (§3.3), profiler/transform versions |

**Write ordering.** The run's sequence is: candidate records (§7 order) → anomaly PI → deposit_event → evidence rows. Evidence references the deposit event by identifier, and the event's `records_summary` counts only candidate records, so the event must exist before evidence and evidence must not be counted by it. Evidence POSTs failing after a `success` event is the one partial state the design accepts (evidence is append-only and re-runnable; the §7 re-run repairs it by re-appending — duplicate evidence rows for one `(subject, source, profiled_at)` are tolerated by the WTK-088 latest-snapshot rule, which keys on `profiled_at`, making the re-appended row an exact-tie duplicate, not a corruption). If the build prefers strictness, the batch-POST option (WTK-088 §4.5) makes evidence atomic per run; this spec does not require it.

Subjects whose records were matched at `rejected` status still get evidence rows (WTK-088 I10: evidence never participates in lifecycle enforcement). That is the drift-detection seed: "we dropped this field in triage and the source shows it still being populated" is a real finding.

---

## 6. Repository Write Path

The transform is a **REST client of the live V2 API**, not a direct access-layer caller — per the TOP-013 core principle (record creation through API or MCP) and mirroring `apply_close_out.py`, the existing deposit-path precedent:

- **Module:** `crmbuilder_v2/transform/audit_deposit.py` — pure functions: `load_manifest(path)`, `load_profile(path)`, `plan_deposit(manifest, profile, existing)` (the mapping + idempotency diff, returning a deterministic plan object), `execute_plan(plan, client)` (the POSTs). The plan/execute split keeps the mapping logic unit-testable without an API (§8).
- **CLI:** `crmbuilder-v2-deposit-audit <audit-report.json> [--profile <utilization-profile.json>] --engagement <ENG> [--dry-run]`, registered alongside `crmbuilder-v2-api` in the root `pyproject.toml`. `--dry-run` prints the plan (records to create, matches, evidence count) and exits — the operator preview, given the deposit writes are not transactional end-to-end.
- **HTTP:** `BASE = http://127.0.0.1:8765`; every request sends `X-Engagement` (PI-β); every response unwraps the `{data, meta, errors}` envelope; error bodies may bypass the envelope (`api/errors.py`) — read body before unwrapping on non-2xx.
- **Endpoints used:** `GET /entities`, `/fields`, `/personas`, `/processes`, `/manual-configs`, `/domains` (the idempotency pre-read, §7); `POST` to the same plus `/planning-items`, `/deposit-events`, `/utilization-evidence`. No PATCH, PUT, or DELETE is issued by the transform, ever — structurally enforcing "the transform never mutates existing records."
- **Identifiers:** never supplied — server-assigned on every POST (PI-002 uniform surface), which is what makes parallel-safe re-keying a non-issue here.

Each POST is its own transaction; the run is **resumable, not atomic** (§4.3 failure semantics + §7 idempotency are the compensation). Per-record atomicity that matters is already inside the substrate: `create_field` writes row + parent edge in one transaction; `create_deposit_event` writes row + all edges + payload transition in one transaction.

---

## 7. Idempotency and Re-Run Behavior

The invariant: **running the transform N times against the same source produces the same candidate set as running it once**, plus N evidence snapshots and N deposit events. Concretely:

**Natural keys.** Matching is by the same name keys the repositories enforce uniqueness on — no new columns, no side-table:

| Type | Natural key |
|---|---|
| `entity` | `entity_name` (engagement-global) |
| `field` | (`field_belongs_to_entity` parent, `field_name`) |
| `persona` | `persona_name` |
| `process` | `process_name` |
| `manual_config` | `manual_config_name` |
| `domain` (placeholder) | `domain_name` |

The deterministic name derivation (§3) makes the key stable across runs. A name match against a record at **any live status** — `candidate`, `confirmed`, `deferred`, `rejected` — is a match.

**Re-run rules:**

1. **Matched → never touched.** No create, no field update, no status transition. The lifecycle belongs to triage (Master PRD §7: candidates never auto-confirm — and symmetrically, re-audit never un-confirms, un-rejects, or overwrites triage-era edits to names/descriptions). The run appends an evidence row (§5) and moves on.
2. **Missing → created** at `candidate`, with a `wrote_record` edge from this run's deposit event. This covers both first runs and source-side additions between runs ("the client added a field since the baseline").
3. **Soft-deleted match → skipped + anomaly.** A name match against a soft-deleted record creates nothing (re-creating would race the repositories' live-scoped uniqueness into a confusing twin) and writes no evidence; it is logged in the anomaly PI (§3.6) for an operator to resolve (restore the record, or rename/delete it so the next run creates fresh).
4. **Source-side disappearance → nothing.** A candidate whose source object vanished is not deleted or transitioned; it simply receives no new evidence row, and its evidence trail going stale *is* the dormancy signal. Triage and drift detection read it from there.
5. **Every run emits its own deposit event** with `wrote_record` edges covering only that run's creations (possibly zero — a pure re-observation run has `records_summary: {}` and no `wrote_record` edges, which `create_deposit_event` admits since the sum-equals-count rule holds at 0 = 0).
6. **Cross-source name collisions merge.** A second source whose entity name matches an existing candidate's matches it (rule 1) and appends evidence under its own `evidence_source_label` — exactly the WTK-088 §4.4 multi-source posture (latest snapshot is per `(subject, source)`); triage sees one candidate with per-source evidence.

**Write order within a run** (dependencies only, alphabetical within a tier): placeholder domain (if needed) → entities → fields (need parent `ENT-NNN`) → personas → processes (need the domain) → manual_configs → anomaly PI → deposit event → evidence rows. The plan object (§6) fixes this order deterministically so fixture assertions are stable.

---

## 8. Verification Criteria

The transform fixture format is the manifest itself (§2.1): each test feeds a literal `audit-report.json` (and optionally a `utilization-profile.json`) and asserts on the resulting rows and edges. The mapping layer (`plan_deposit`) is additionally unit-testable with no API. The implementation is correct when:

**T1 — Full small-report transform.** Fixture: one custom entity (2 custom fields, one of them enum with 7 options), one native entity carrying 1 custom field, one relationship between them (both sides audited), 1 role with description + scope_access, 1 team, 2 filtered tabs (one with a recovered filter, one with `filter: null`), 1 audit warning. Expected: 2 `entity` + (3 + 2 relationship-side) `field` + 2 `persona` + 2 `process` + 1 `manual_config` (the null-filter tab) + 1 placeholder `domain` + 1 anomaly PI; every methodology record at `candidate`; every `field` has its `field_belongs_to_entity` edge; both processes point at the placeholder domain; the enum field's notes and evidence carry the 7 declared options.

**T2 — Provenance completeness.** After T1: exactly one `deposit_event`, outcome `success`; `records_summary` sums to the `wrote_record` edge count; **every** created record (including the placeholder domain and the anomaly PI) is reachable via `wrote_record`; `apply_context` carries all §4.3 keys; the lazily created close_out_payload's file path is the manifest path. (This is Master PRD §7 completion criterion 2 made executable, and Q6 of WTK-088 §5.1 runs against it.)

**T3 — Idempotent re-run.** Run T1's fixture twice. Second run: zero candidate creations, a second `deposit_event` with `records_summary: {}` and no `wrote_record` edges, and exactly one new evidence row per touched subject. Total candidate counts unchanged; no record's `updated_at`-relevant fields changed.

**T4 — Incremental re-run.** T1's fixture plus one new custom field on the existing custom entity. Expected: exactly 1 creation (`field`), with a `wrote_record` edge from the new deposit event only; everything else matches rule 1.

**T5 — Wire-type map coverage.** A fixture entity carrying one field of every wire type in §3.2's table maps to the expected `FIELD_TYPES` values; an unknown wire type (`futureType`) maps to `text` and lands in the anomaly PI.

**T6 — Evidence with and without profile.** T1 with the profile supplied: field evidence rows carry the typed metrics (population_rate et al.), entity rows carry record_count/recency, the enum row carries used_option_count, `evidence_profiled_at` = profile timestamp. T1 without: same row count, all profile-derived columns NULL, `evidence_declared_option_count` still populated, `evidence_profiled_at` = report timestamp, `evidence_catalog_class` correct (`custom`/`standard`).

**T7 — Lifecycle non-interference.** Seed a candidate from T1, transition it `candidate → rejected` (with its `rejected_by_decision` edge) out-of-band, re-run. The record stays `rejected`, untouched; it still receives an evidence row (WTK-088 I10).

**T8 — Failure resumability.** Force a POST failure mid-run (e.g. kill the API after the entities tier). Expected: deposit event with outcome `failure`, `error_info` populated, `wrote_record` edges covering exactly the records that landed; a subsequent clean re-run completes the set with no duplicates (T4 semantics).

**T9 — Soft-deleted match.** Soft-delete one T1 candidate, re-run. No twin is created; the anomaly PI for the run names the skipped subject.

**T10 — Scope rules.** A fixture with a bare native entity (no custom fields, no tabs) and a stock native field on a captured entity: neither maps; a `system`-class entity never maps.

---

## 9. Build Surface (for the implementing Work Tasks)

This spec ships no code. In dependency order:

1. **WTK-088 build first** — the `utilization_evidence` table, vocab, migrations, and endpoints (that spec's §6) are a prerequisite for §5 here.
2. **vocab.py:** extend the `deposit_event_wrote_record` clause in `_kinds_for_pair` with the six methodology target types (§4.2); `REFERENCE_RELATIONSHIPS` is unchanged (the kind exists).
3. **Migrations:** rebuild `ck_ref_relationship` from current vocab, dual-head (SQLite chain + `migrations/pg/`), with the mid-stream chain-entry guard; no new tables (evidence is WTK-088's).
4. **espo_impl (audit side, one small change):** serialize `AuditReport` to `audit-report.json` in the output dir per §2.1 (a `to_manifest()` on the dataclass or a writer in `audit_manager.py`; covered by a round-trip test).
5. **crmbuilder_v2/transform/audit_deposit.py + CLI** per §6, with the §3 mapping table and §7 plan/diff logic.
6. **Fixtures + tests** per §8 (plan-level unit tests offline; T1–T10 against the API test harness).
7. **Out of scope here:** the data profiler (§2.2 consumer contract only), the Baseline Report renderer, the spreadsheet source adapter, a dedicated `observed_in` provenance kind (Master PRD §7 Known Limitations — `wrote_record` + evidence rows are the v1 trail).

## 10. Open Questions and Deferred Decisions

- **Relationship pairing edge** (§3.3): a first-class edge between the two `reference` field candidates of one source relationship awaits richer link typing in the field vocabulary (v0.6+ per `field.md`).
- **Native stock-field signal** (§3.2): revisit the no-deposit rule if triage practice shows the Baseline Report path loses confirmable stock fields.
- **Evidence batch POST** (§5): adopt WTK-088's batch option if the per-row tail-failure window proves annoying in practice.
- **`process` placeholder domain** (§4.4): superseded automatically if a follow-on decision relaxes `create_process`'s domain requirement; the transform then deposits domainless processes and the placeholder is retired.
- **Rename detection:** a source-side rename (label change) reads as disappearance + new candidate under name-key matching. Acceptable for v1 (the old candidate goes evidence-stale; triage reconciles); a wire-name side-key could tighten this later at the cost of a stored mapping.

## 11. Cross-References

- `candidate-lifecycle-rejected-and-utilization-evidence.md` (WTK-088) — evidence table §4, lifecycle D1, invariants §5.2, build surface §6
- `specifications/master-crmbuilder-PRD.md` v0.2 — §7 Phase 1.5 (phase rules, capture table, completion criteria, Known Limitations this spec closes), §8 Phase 3 triage (commit `9681039`)
- `espo_impl/core/audit_manager.py` — `AuditReport` and its component dataclasses (the input shape); `espo_impl/core/audit_utils.py` — `EntityClass` / `FieldClass`
- `crmbuilder_v2/access/repositories/` — `entity.py`, `field.py`, `persona.py`, `process.py`, `manual_config.py` (the create surfaces §3 maps onto), `deposit_events.py` (atomic POST, lazy payload, records_summary rule)
- `crmbuilder_v2/access/vocab.py` — `FIELD_TYPES`, `ENTITY_KINDS`, `MANUAL_CONFIG_CATEGORIES`, `PROCESS_CLASSIFICATIONS`, `_kinds_for_pair` (the `wrote_record` clause §4.2 extends)
- `crmbuilder-v2/scripts/apply_close_out.py` — the deposit-path precedent for the REST write path, envelope handling, deposit-event-log convention
- `PRDs/product/features/feat-audit.md` — the V1 Audit feature (transitional reference per Master PRD §7 Inputs)
- TOP-013 — governance recording rules (API-first record creation)

# Methodology Design Spec — Catalog Normalizer: Field.type Mapping and Standard-vs-Custom Partition

**Last Updated:** 06-12-26
**Status:** Draft v1.0 — produced under WTK-102 (storage-area spec deliverable for the Phase 1.5 normalization step)
**Position in workstream:** Companion to `audit-report-to-candidate-deposit-transform.md` (WTK-090), which defined the AuditReport → candidate deposit path and shipped the EspoCRM-only wire-type map as part of it (`transform/audit_deposit.py` `WIRE_TYPE_MAP`). This spec owns the normalization layer that map belongs to — Master CRMBuilder PRD v0.2 §7 Activity step 3 ("Normalize through the catalog") — and generalizes it to all seven catalog-surveyed source systems: the deterministic native-type → `FIELD_TYPES` mapping per system, the standard-vs-custom partition per system, the triage-priority derivation, and the verification criteria that keep the candidate graph engine-agnostic.
**Companion documents:** `audit-report-to-candidate-deposit-transform.md` (WTK-090 — the deposit pipeline this layer runs inside); `espocrm-data-profiling-pass.md` (WTK-096 — the utilization metrics priority derivation consumes); `candidate-lifecycle-rejected-and-utilization-evidence.md` (WTK-088 — the evidence rows that carry `evidence_catalog_class`); `field.md` §3.2.3 (the `FIELD_TYPES` target vocabulary); `catalog-ingestion-PRD-v0.1.md` §4 (the catalog tables that are the partition's reference oracle); `specifications/master-crmbuilder-PRD.md` §7 (Phase 1.5) and §8 (Phase 3 triage).

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 06-12-26 | ADO Area Specialist (storage) / Claude | Initial draft under WTK-102. Defines the two-stage type mapping (per-system native type → `CATALOG_ATTRIBUTE_TYPES`, then a fixed total projection `CATALOG_ATTRIBUTE_TYPES` → `FIELD_TYPES`), seven per-system stage-1 adapter tables with the EspoCRM table proven identical-by-composition to the landed `WIRE_TYPE_MAP`, fallback rules (unknown native type → `string` → `text` + anomaly), the three-tier partition oracle (source marker → catalog presence → conservative `custom` + anomaly) with per-system marker rules including the NPSP-namespace rule that distinguishes `salesforce_npsp` from `salesforce`, derived-not-stored triage priority bands aligned to the WTK-096 dormancy thresholds, and verification criteria N1–N9 (totality, composition identity, per-system fixtures, engine-agnostic invariants). |

---

## Change Log

**Version 1.0 (06-12-26):** Initial creation. No code ships with this document — it is the design the implementing Work Tasks build from. §7 enumerates the build surface.

---

## 1. Purpose and Position

Master CRMBuilder PRD v0.2 §7, Activity step 3:

> **Normalize through the catalog.** Map each discovered field to the engine-agnostic field type vocabulary and partition every item as *standard* (part of the source product's stock schema) or *custom* (added for this client). Custom items are concentrated requirements signal — someone paid to add them; standard items are signal only where the data profile shows real use.

The WTK-090 transform spec built the deposit pipeline and, inside it, the EspoCRM-only instance of this step (`WIRE_TYPE_MAP` in `transform/audit_deposit.py`, plus the `EntityClass`/`FieldClass` partition inherited from `espo_impl/core/audit_utils.py`). EspoCRM is the only source adapter today, but the base entity catalog already surveys **seven** systems (`CATALOG_SYSTEMS` in `access/vocab.py`: `salesforce`, `hubspot`, `attio`, `espocrm`, `civicrm`, `salesforce_npsp`, `bloomerang`), and the Master PRD names further source adapters as planned work. Without a pinned normalization contract, each future adapter would invent its own mapping and partition ad hoc, and the candidate vocabulary would drift per-adapter — the exact failure the engine-agnostic graph exists to prevent.

This spec pins that contract:

1. the deterministic mapping from each of the seven systems' native field types to the engine-agnostic `FIELD_TYPES` vocabulary, including fallback rules (§3);
2. the partition rules classifying every discovered item — entity and attribute — as `standard` vs `custom`, per system (§4);
3. how triage priority is derived from the partition class and the utilization profile (§5);
4. verification criteria: full coverage, per-system spot-check fixtures, and the invariants that keep the candidate graph engine-agnostic (§6).

The normalizer is a layer **inside** `plan_deposit` (WTK-090 §6) — it has no I/O of its own. Its inputs are the discovery manifest's native-typed items plus the catalog tables; its outputs are the `field_type` value on each planned `field` candidate, the `evidence_catalog_class` value on each planned evidence row, and (at render time, not deposit time) the triage priority bands the Baseline Report orders by.

---

## 2. The Two-Stage Mapping Architecture

### 2.1 Why two stages

A single flat table per system (native type → `FIELD_TYPES` directly, the WTK-090 v1 shape) works for one system but multiplies the lossy-collapse decisions by seven: every adapter author re-decides "what does an email type become?" independently. The catalog already carries a finer engine-agnostic vocabulary — `CATALOG_ATTRIBUTE_TYPES` (21 values, `access/vocab.py`) — that sits naturally between the native vocabularies and the 11-value `FIELD_TYPES`. The normalizer therefore maps in two stages:

- **Stage 1 (per system):** native type → `CATALOG_ATTRIBUTE_TYPES`. Seven tables, one per system slug (§3.3–§3.9). This is the only place per-system knowledge lives, and most rows are near-1:1 because the catalog vocabulary was designed from these systems' type systems.
- **Stage 2 (fixed, system-independent):** `CATALOG_ATTRIBUTE_TYPES` → `FIELD_TYPES`. One total projection (§3.2). This is the **only** place the lossy collapse onto the methodology vocabulary happens; when `FIELD_TYPES` grows (PI-054: `address`, `phone`, `url`, …), only this table changes and all seven systems inherit the refinement at once.

The composed map for EspoCRM reproduces the landed `WIRE_TYPE_MAP` exactly (verification criterion N3) — the two-stage design is a refactoring of the landed behavior, not a behavior change.

### 2.2 Losslessness in total

Stage 2 is lossy by design — `FIELD_TYPES` is deliberately shape-oriented, not rendering-oriented (`field.md` §3.2.3) — and lossless in total because of WTK-090's standing rules, which this spec inherits unchanged: the original native type always survives in the candidate's `notes` `Source:` block and in the evidence row's `evidence_detail`, and the stage-1 catalog attribute type is additionally recorded in `evidence_detail` (key `catalog_attribute_type`) so triage and the eventual migration mapping can recover the finer shape without re-consulting the source.

### 2.3 Authoring posture for the six unbuilt adapters

EspoCRM's stage-1 table is grounded in landed, deployment-proven code. The other six tables are **adapter contracts** authored from each product's public schema documentation as of this spec's date. They are pinned now so the vocabulary cannot drift per-adapter, with two guards: each future adapter build validates its table against a live-discovery fixture before first production use (criterion N4), and any correction is a versioned amendment to this spec — never a silent in-code divergence. The fallback rule (§3.10) makes a stale table degrade safely (unknown type → `text` + anomaly), never silently.

---

## 3. The Deterministic Type Mapping

### 3.1 General rules

- The mapping is a **pure function** `(system, native type[, native subtype/flags]) → FIELD_TYPES value` with no data-dependent branches: the same input always yields the same output, fixture-stable (WTK-090 §8's plan-determinism requirement extends to this layer).
- Some systems type fields with a **pair** (HubSpot `type` × `fieldType`; CiviCRM `data_type` × `html_type`; Attio `type` × `is_multiselect`). The stage-1 key for those systems is the pair; the tables below spell the pairs out. Lookup precedence within a system: computed-value flag first (anything the source marks calculated/formula/rollup → `formula` regardless of result type), then the exact pair, then the bare type, then fallback.
- Composite native types (EspoCRM `address`/`personName`/`currency`, Salesforce `Address`/`Name`, Attio `location`) map as **one** candidate field, never exploded into storage columns — the explosion is a storage artifact, not a requirement (WTK-090 §3.2 rule, generalized).
- System-plumbing fields are excluded **before** mapping (EspoCRM `SYSTEM_FIELDS` precedent; each adapter pins the equivalent exclusion set — Salesforce audit fields `CreatedById`/`SystemModstamp`/…, HubSpot `hs_object_id`/analytics internals, CiviCRM `id`/`hash`, etc.). Exclusion is an adapter-discovery concern; the normalizer only sees what discovery emits, and maps all of it.

### 3.2 Stage 2 — the fixed projection `CATALOG_ATTRIBUTE_TYPES` → `FIELD_TYPES`

Total over all 21 catalog attribute types. No fallback exists or is needed at this stage — a stage-1 output outside this table is a programming error, not an input condition.

| Catalog attribute type | `FIELD_TYPES` | Note |
|---|---|---|
| `string` | `text` | |
| `text` | `long_text` | Multi-line free text |
| `richtext` | `long_text` | Formatting is presentation, not shape |
| `integer` | `number` | |
| `decimal` | `number` | |
| `currency` | `money` | |
| `boolean` | `boolean` | |
| `date` | `date` | |
| `datetime` | `datetime` | |
| `time` | `text` | Lossy: `FIELD_TYPES` has no time-of-day. `datetime` would assert a date that does not exist; `text` preserves the value-shape honestly. Finer type recoverable from evidence detail. |
| `enum` | `enum` | |
| `multienum` | `multi_enum` | |
| `reference` | `reference` | |
| `multireference` | `reference` | Cardinality survives in evidence detail |
| `email` | `text` | PI-054 candidate: refine when `FIELD_TYPES` grows `phone`/`url`/`email` |
| `phone` | `text` | PI-054 candidate |
| `url` | `text` | PI-054 candidate |
| `address` | `text` | PI-054 candidate |
| `attachment` | `text` | Lossy: no file shape in `FIELD_TYPES`; the attachment-ness is triage-relevant and survives in notes + evidence detail |
| `autonumber` | `number` | |
| `formula` | `derived` | |

### 3.3 Stage 1 — `espocrm`

Grounded in the landed `WIRE_TYPE_MAP` (`transform/audit_deposit.py`); the composition of this table with §3.2 reproduces it value-for-value (criterion N3).

| EspoCRM wire type | Catalog type | Composed `FIELD_TYPES` |
|---|---|---|
| `varchar`, `personName` | `string` | `text` |
| `email` | `email` | `text` |
| `phone` | `phone` | `text` |
| `url` | `url` | `text` |
| `address` | `address` | `text` |
| `text` | `text` | `long_text` |
| `wysiwyg` | `richtext` | `long_text` |
| `enum` | `enum` | `enum` |
| `multiEnum`, `checklist`, `array` | `multienum` | `multi_enum` |
| `date` | `date` | `date` |
| `datetime`, `datetimeOptional` | `datetime` | `datetime` |
| `currency`, `currencyConverted` | `currency` | `money` |
| `bool` | `boolean` | `boolean` |
| `int` | `integer` | `number` |
| `float` | `decimal` | `number` |
| `autoincrement` | `autonumber` | `number` |
| `link`, `linkParent`, `linkOne` | `reference` | `reference` |
| `linkMultiple` | `multireference` | `reference` |
| `foreign` | `formula` | `derived` |

**Named extensions** (not in the landed map; today these wire types hit the fallback and raise anomalies — adopting the extension routes them to the same end value without the anomaly noise): `file` → `attachment`, `image` → `attachment`, `attachmentMultiple` → `attachment`, `barcode` → `string`. Adoption is a one-line-per-entry change to the implementation table plus a fixture update; per WTK-090 §3.2, "the map is extended, not silently widened" — this spec is the extension record.

### 3.4 Stage 1 — `salesforce`

Keyed on the Metadata/Describe API field type, with the calculated-flag precedence rule (§3.1): any field with `calculated: true` (formula and roll-up summary fields) maps to `formula` regardless of its declared result type.

| Salesforce field type | Catalog type |
|---|---|
| `Text`, `EncryptedText`, `Name` (compound) | `string` |
| `TextArea`, `LongTextArea` | `text` |
| `Html` (rich text area) | `richtext` |
| `Number` | `decimal` |
| `Percent` | `decimal` |
| `Currency` | `currency` |
| `AutoNumber` | `autonumber` |
| `Checkbox` | `boolean` |
| `Date` | `date` |
| `DateTime` | `datetime` |
| `Time` | `time` |
| `Email` | `email` |
| `Phone` | `phone` |
| `Url` | `url` |
| `Address` (compound) | `address` |
| `Geolocation` / `Location` | `string` (lat/long pair as text; no geo shape in either vocabulary) |
| `Picklist` | `enum` |
| `MultiselectPicklist` | `multienum` |
| `Lookup`, `MasterDetail`, `ExternalLookup`, `IndirectLookup`, `Hierarchy`, `MetadataRelationship` | `reference` |
| `Formula` / `Summary` (rollup) — i.e. `calculated: true` | `formula` |

### 3.5 Stage 1 — `salesforce_npsp`

Identical to §3.4 — NPSP is a managed package on the Salesforce platform and introduces no new field types. The system exists as a distinct catalog slug because its **partition** differs (§4.3): the NPSP package's namespaced fields are stock schema *for this system* even though the raw platform marks them custom.

### 3.6 Stage 1 — `hubspot`

Keyed on the property pair (`type`, `fieldType`); calculated properties (`calculated: true` or a `calculation_*` fieldType) map to `formula` first per §3.1.

| HubSpot (`type`, `fieldType`) | Catalog type |
|---|---|
| (`string`, `text`) | `string` |
| (`string`, `textarea`) | `text` |
| (`string`, `html`) | `richtext` |
| (`string`, `file`) | `attachment` |
| (`string`, `phonenumber`) and (`phone_number`, any) | `phone` |
| (`number`, any) | `decimal` |
| (`date`, any) | `date` |
| (`datetime`, any) | `datetime` |
| (`bool`, any) and (`enumeration`, `booleancheckbox`) | `boolean` |
| (`enumeration`, `select`) / (`enumeration`, `radio`) | `enum` |
| (`enumeration`, `checkbox`) | `multienum` |
| (`json`, any) | *fallback* (§3.10) |

HubSpot models cross-object links as **associations**, not properties; discovery emits them as relationship items, which map per WTK-090 §3.3 (reference-type field candidates per audited side, `reference`/`multireference` by association cardinality), not through this table.

### 3.7 Stage 1 — `attio`

Keyed on the attribute `type`, refined by the `is_multiselect` flag where Attio carries one.

| Attio attribute type | Catalog type |
|---|---|
| `text` | `string` |
| `personal-name` | `string` |
| `number` | `decimal` |
| `rating` | `integer` |
| `currency` | `currency` |
| `checkbox` | `boolean` |
| `date` | `date` |
| `timestamp` | `datetime` |
| `status` | `enum` |
| `select` (`is_multiselect: false`) | `enum` |
| `select` (`is_multiselect: true`) | `multienum` |
| `record-reference` (`is_multiselect: false` / `true`) | `reference` / `multireference` |
| `actor-reference` | `reference` (target is a workspace user; the pairing note in evidence detail flags it as persona-adjacent signal for triage) |
| `location` | `address` |
| `domain` | `url` |
| `email-address` | `email` |
| `phone-number` | `phone` |
| `interaction` | `datetime` (read-only system aggregate — usually excluded pre-mapping by the adapter's system set; mapped defensively if it leaks through) |

### 3.8 Stage 1 — `civicrm`

Keyed on the custom-field pair (`data_type`, `html_type`), with the `serialize` flag promoting single-valued kinds to multi-valued ones. Core (non-custom-group) fields map by the same data-shape rows.

| CiviCRM (`data_type`, `html_type`) | Catalog type |
|---|---|
| (`String`, `Text`) | `string` |
| (`String`, `Select` / `Radio` / `Autocomplete-Select`) | `enum` |
| (`String`, `CheckBox` / `Multi-Select`) or `serialize` set | `multienum` |
| (`Int`, any) | `integer` |
| (`Float`, any) | `decimal` |
| (`Money`, any) | `currency` |
| (`Memo`, `TextArea`) | `text` |
| (`Memo`, `RichTextEditor`) | `richtext` |
| (`Date`, any; `time_format` unset) | `date` |
| (`Date`, any; `time_format` set) | `datetime` |
| (`Boolean`, any) | `boolean` |
| (`StateProvince`, any) / (`Country`, any) | `enum` (`multienum` when `serialize` set) |
| (`File`, any) | `attachment` |
| (`Link`, any) | `url` |
| (`ContactReference`, any) / (`EntityReference`, any) | `reference` (`multireference` when `serialize` set) |

### 3.9 Stage 1 — `bloomerang`

Bloomerang custom fields carry a data type and a pick structure; the stock constituent/transaction schema's typed channels map by shape.

| Bloomerang shape | Catalog type |
|---|---|
| Text, free-form | `string` |
| Text, pick-one (predefined values) | `enum` |
| Text, pick-many (predefined values) | `multienum` |
| Date | `date` |
| Currency | `currency` |
| Number / Decimal | `decimal` |
| Boolean | `boolean` |
| Stock email channel | `email` |
| Stock phone channel | `phone` |
| Stock address block | `address` |
| Stock note / narrative fields | `text` |
| Stock links (household membership, soft-credit, tribute) | `reference` |

Bloomerang's public API vocabulary is the least settled of the seven; this table is the adapter contract per §2.3, and the N4 fixture gate is its enforcement.

### 3.10 Fallback rules

1. **Unknown native type** (not in the system's stage-1 table, after the precedence steps of §3.1): map to `string` (hence `text`) and raise an **anomaly** — one entry in the run's anomaly Planning Item (WTK-090 §3.6) naming the system, entity, field, and unmapped native type. Identical end-behavior to the landed `_FALLBACK_FIELD_TYPE` path, restated at the stage-1 level.
2. **Ambiguous pair** (a system emits a type/subtype combination the table does not pair — e.g. a new HubSpot `fieldType` under a known `type`): fall back to the bare-type row when one exists (anomaly-free, since the value-shape is still known), else rule 1.
3. **No silent widening.** The implementation never adds table entries at runtime or "guesses" by string similarity. New native types enter the table only through a versioned amendment to this spec (the §3.3 named-extensions pattern). The fallback keeps unattended runs safe; the anomaly keeps them honest.
4. Fallback-mapped items are otherwise full citizens: they are deposited, partitioned, and evidenced normally. The fallback affects only `field_type` fidelity, which the notes/evidence wire identity makes recoverable.

---

## 4. The Standard-vs-Custom Partition

### 4.1 Output and where it lands

Every discovered item — entity and attribute — receives exactly one partition class from `{standard, custom}`. The class lands in `evidence_catalog_class` on the item's `utilization_evidence` row (WTK-088 §4; WTK-090 §5 already writes it for EspoCRM as `custom` → `custom`, `native` → `standard` — this section generalizes the rule that produces it). The class is **evidence, not record state**: candidate records carry no partition column, so re-partitioning (a catalog correction, a marker fix) is a new evidence snapshot, never a record mutation — the same posture as every other normalizer output.

The partition vocabulary deliberately matches `CATALOG_PRESENCE_STATUSES` minus `absent` (`absent` describes a catalog concept missing from a system — meaningless for an item that was just discovered *in* that system).

### 4.2 The three-tier partition oracle

For each discovered item, evaluated in order; the first tier that yields a class wins:

1. **Source marker (authoritative).** The source system's own custom-vs-stock signal, read at discovery time. The live system is the witness; when it speaks, it wins. Per-system markers in §4.3.
2. **Catalog presence (reference oracle).** When the source exposes no marker for the item, look the item up in the catalog by `(system, api_name)` — `catalog_attribute_presence.api_name` for attributes, `catalog_entity_system.api_name` for entities. A hit with status `standard` → `standard`; a hit with status `custom` → `custom` (the catalog records that this concept is customarily client-added in this system). Synonym tables (`catalog_attribute_synonym`, `catalog_entity_synonym`) extend the match for label-discovered items; exact-api_name match always outranks a synonym match.
3. **Unresolvable → `custom` + anomaly.** No marker, no catalog row: classify `custom` and log an anomaly entry. The default is deliberately conservative in the direction that protects signal: misclassifying a standard item as custom costs one triage glance; misclassifying a custom item as standard buries paid-for requirements signal under the stock-schema noise floor — the asymmetric cost rules.

**Disagreement handling:** when tier 1 yields a class and the catalog disagrees (e.g. the marker says standard, the catalog has it `absent` for this system), the marker wins and the disagreement is recorded in `evidence_detail` (key `catalog_disagreement`) — it is catalog-correction input, not a runtime decision.

### 4.3 Per-system marker rules (tier 1)

| System | Entities | Attributes |
|---|---|---|
| `espocrm` | `classify_entity` (`espo_impl/core/audit_utils.py`): `isCustom` scope flag → custom; `NATIVE_ENTITIES` membership → standard; system scopes excluded pre-partition. Landed code; unchanged. | `classify_field`: `isCustom` field flag → custom; `c`-prefix-then-uppercase heuristic → custom; per-base-type native field sets → standard; `SYSTEM_FIELDS` excluded. Landed code; unchanged. |
| `salesforce` | API name ends `__c` → custom; no suffix → standard. Namespaced package objects (`ns__Name__c`) → standard, with the namespace recorded in notes (another vendor's stock schema, not this client's authoring — see §4.5). `__mdt` / `__e` / `__x` are excluded pre-partition (platform plumbing, not data entities). | Same suffix rule per field: un-namespaced `__c` → custom; namespaced `ns__field__c` → standard + namespace note; no suffix → standard. |
| `salesforce_npsp` | As `salesforce`, **except**: objects in the NPSP namespace set `{npsp, npe01, npe03, npe4, npe5, npo02}` → **standard** — they are the stock schema of the product this system slug names. Other namespaces → standard + note, as on raw Salesforce. | Same NPSP-namespace override per field. This is the discriminating rule between the two Salesforce slugs (criterion N6). |
| `hubspot` | Standard object type IDs (`0-1` contacts, `0-2` companies, `0-3` deals, `0-5` tickets, and the other `0-*` stock objects) → standard; `2-*` custom objects → custom. | Property `hubspotDefined: true` → standard; `false`/absent → custom. |
| `attio` | Attio's default workspace objects (people, companies, and the template-installed deals/users/workspaces) → standard; workspace-created objects → custom. | No per-attribute API flag is relied on: the adapter pins per-standard-object default-attribute slug sets (the `NATIVE_*_FIELDS` precedent from `audit_utils.py`, applied to Attio) → standard; everything else falls to tier 2. |
| `civicrm` | Structural: core entities → standard; there is no client mechanism for new top-level entities (custom *groups* attach fields to existing entities), so discovered entities are standard by construction; extension-provided entities → standard + extension note. | Structural and authoritative: any field from `civicrm_custom_field` (a custom group) → custom; core DAO fields → standard; extension-provided fields → standard + extension note. |
| `bloomerang` | Structural: the fixed product schema (Constituent, Transaction, Interaction, …) → standard; Bloomerang has no client-defined entities, so no discovered entity is custom. | Structural and authoritative: anything under the custom-fields API → custom; fixed-schema fields → standard. |

### 4.4 Entity partition and the `partial` value

`catalog_entity_system.is_standard` admits `{true, false, partial}` (`CATALOG_IS_STANDARD_VALUES`). `partial` marks an entity that is partly built-in and partly client-realized in a system (e.g. a concept stock-modeled as a record type on one object plus a client-added object elsewhere). When tier 2 resolves an **entity** to `partial`: the entity itself partitions `standard` (some stock footing exists), and its **attributes are partitioned individually** — which tiers 1–3 do anyway. `partial` never appears as an item's partition class; it only widens the per-attribute scrutiny on that entity.

### 4.5 What the partition does and does not gate

The partition class feeds two consumers: the deposit scope rules WTK-090 already fixed (custom items always deposit; bare standard items do not — `standard` signal travels through the Baseline Report and the profile, not through candidate records), and the triage priority derivation (§5). It does **not** gate evidence (every touched item gets its evidence row regardless of class, WTK-088 I10 posture) and it does not appear on candidate records (engine-agnostic invariant, §6 N7). Third-party-package items (Salesforce namespaced, CiviCRM extensions) partition `standard` under these rules — they are some vendor's stock schema, installed deliberately; the *installation* is the requirements signal, and it surfaces through the entity-level evidence and the Baseline Report narrative, not through a third partition class. If triage practice shows the binary partition losing package-vs-platform signal, a `package` class is the designed extension point (§8).

---

## 5. Triage Priority Derivation

### 5.1 Derived, not stored

Triage priority is a **projection computed at read/render time** from exactly two inputs — the item's partition class and its latest utilization-evidence snapshot — and is never stored on the candidate or the evidence row. This mirrors the established posture for derived rollups (the Workstream `needs_attention` → Planning Item rollup is derived at query time; WTK-096's dormancy flags are advisory and re-derivable): evidence accrues across runs, and a stored priority would go stale the moment a re-profile lands. Same inputs → same band, deterministically (criterion N8).

### 5.2 Use thresholds

Reused unchanged from WTK-096 (which aligned them to the WTK-088 triage queries) so every consumer agrees on what "real use" means:

- **Field in real use:** `evidence_population_rate` ≥ 0.05, and `evidence_last_populated_at` within the 365-day window.
- **Entity in real use:** `evidence_record_count` > 0 and `evidence_last_record_created_at` within the 365-day window.
- **Dormant:** fails either prong. Enum option-shrinkage (`evidence_used_option_count` < `evidence_declared_option_count`) does not change the band; it is a per-item triage note within the band.

### 5.3 The bands

| Band | Definition | Triage meaning | Surfaces as |
|---|---|---|---|
| **T1** | `custom` + real use | Concentrated requirements signal: someone paid to add it, and the organization still uses it. The strongest keep-probe candidates. | Top of the Baseline Report per domain group; first in the WTK-088 triage queue |
| **T2** | `custom` + dormant | Ghost signal: someone paid to add it and use stopped. Either a lapsed requirement or a process failure — both are Phase 2 probe material ("you built X, it's empty — tell me what happened"). | The **gaps-and-ghosts list** (Master PRD §7 Activity 5) |
| **T3** | `standard` + real use | The stock schema the organization actually leans on. Not deposited as candidates (WTK-090 §3.2 scope rule); prioritized **only** because the data proves use — exactly the Master PRD's "standard items are signal only where the data profile shows real use." | Baseline Report stock-usage section, ordered by population; confirmable into candidates at triage |
| **T4** | `standard` + dormant | Product noise floor. No triage attention. | Coverage appendix only (so completeness is auditable; criterion N5) |

**Schema-only runs** (no utilization profile supplied — WTK-090 §2.2's degraded mode): the use prong is unknown, so bands collapse to the partition axis — custom items render as a single `T1/T2 (use unprofiled)` band and standard items as `T3/T4 (use unprofiled)`; the report states that profiling is pending rather than silently presenting structure-only priority as use-verified priority.

### 5.4 Ordering within bands

Deterministic so renders are fixture-stable: within T1/T2, group by parent entity (entities ordered by `evidence_record_count` descending, then name ascending), fields by `evidence_population_rate` descending (T1) or `evidence_last_populated_at` descending (T2 — most-recently-abandoned first, the freshest ghost trail), ties by name ascending. T3 orders by population rate descending. Multi-source engagements derive bands per `(subject, source)` evidence pair (the WTK-088 §4.4 latest-snapshot key); an item custom-and-used in one source and dormant in another renders in both places, each under its source label.

---

## 6. Verification Criteria

The fixture format is the WTK-090 manifest (each test feeds a literal `audit-report.json` and optionally a `utilization-profile.json`); mapping- and partition-level checks run offline against the plan object, needing no API.

**N1 — Stage-1 totality per system.** For each of the seven systems: every native type (or keyed pair) in the system's §3 table maps to a member of `CATALOG_ATTRIBUTE_TYPES`; an input outside the table takes the §3.10 fallback chain and lands in the anomaly PI. Post-plan assertion: **no planned item is unmapped** — every planned `field` candidate carries a `field_type` ∈ `FIELD_TYPES`, with zero exceptions including fallback-mapped items.

**N2 — Stage-2 totality.** The §3.2 projection defines all 21 members of `CATALOG_ATTRIBUTE_TYPES` and emits only members of `FIELD_TYPES`. Enforced as a static test over the implementation tables (`set(CATALOG_TO_FIELD_TYPE) == CATALOG_ATTRIBUTE_TYPES` and `set(values) <= FIELD_TYPES`), so a vocab migration that widens the catalog vocabulary fails this test until the projection is extended deliberately.

**N3 — Composition identity for EspoCRM.** Stage 1 (`espocrm`) composed with stage 2 equals the landed `WIRE_TYPE_MAP` entry-for-entry (the §3.3 named extensions excepted, each asserted individually once adopted). This pins the refactoring as behavior-preserving.

**N4 — Per-system spot-check fixture.** One fixture per system (seven total), each carrying: one attribute of every native type (or pair) in that system's stage-1 table, one unknown native type, one standard and one custom item of each of entity and attribute per that system's §4.3 markers. Asserts: every mapped `field_type` matches the composed table; the unknown type maps `text` + one anomaly entry; every item's partition class matches expectation; no item lacks a class. A future adapter's first live discovery run must round-trip into its fixture before production use (§2.3).

**N5 — Partition coverage.** Post-plan: every discovered entity and attribute in the manifest carries exactly one class ∈ `{standard, custom}`; tier-3 classifications each have a matching anomaly entry; nothing is silently dropped between discovery and partition (count in == count partitioned + count excluded-by-named-system-set, with the exclusion list itself asserted).

**N6 — The NPSP discriminator.** A fixture field `npsp__Primary_Contact__c` partitions **custom** under system `salesforce` and **standard** under system `salesforce_npsp`; an un-namespaced `Mentoring_Stage__c` partitions custom under both; stock `Name` partitions standard under both.

**N7 — Engine-agnostic invariants on the candidate graph.** After a full deposit: (a) every `field` candidate's `field_type` ∈ `FIELD_TYPES` and every `entity` candidate's kind ∈ `ENTITY_KINDS` or omitted — no native vocabulary in any typed column; (b) product identity (system slugs, wire types, api_names, namespace prefixes) appears **only** in `notes` `Source:` blocks, `evidence_detail`, `evidence_source_label`/`evidence_catalog_class`, and the deposit event's `apply_context` — never in `field_name`/`entity_name`/descriptions' structured role (names come from source *labels*, which are client language); (c) no partition class is stored on any candidate record; (d) the same logical schema discovered from two different source systems produces candidate graphs that differ only in notes, evidence, and provenance — the graph itself (names, types, edges) is identical. (d) is the executable meaning of "engine-agnostic."

**N8 — Priority re-derivability.** Deriving bands twice from the same evidence snapshot yields identical band assignments and identical within-band order; deriving after a new evidence snapshot uses only the latest per `(subject, source)`; no candidate or evidence column stores a band.

**N9 — Fallback safety.** A manifest containing only unknown native types still completes: all fields deposit as `text`, all items partition (tier 3 at worst), the anomaly PI lists every fallback, and the run's deposit event reports `success` — degradation is loud but never blocking.

---

## 7. Build Surface (for the implementing Work Tasks)

This spec ships no code. In dependency order:

1. **`crmbuilder_v2/transform/normalize.py`** — the normalizer as a standalone module: `CATALOG_TO_FIELD_TYPE` (§3.2), `SYSTEM_TYPE_MAPS: dict[str, ...]` (§3.3–§3.9, keyed by `CATALOG_SYSTEMS` slug), `normalize_type(system, native, *, subtype=None, calculated=False) -> tuple[str, Anomaly | None]`, `partition(system, item, catalog_lookup) -> tuple[str, Anomaly | None]` (§4.2 tiers). Pure functions, no I/O — unit-testable offline like `plan_deposit`.
2. **Refactor `audit_deposit.py`** to consume the espocrm composed table from `normalize.py` in place of its inline `WIRE_TYPE_MAP`, guarded by the N3 composition test. The `EntityClass`/`FieldClass`-driven partition stays the espocrm tier-1 marker (it already runs at audit time); the normalizer reads it from the manifest.
3. **Catalog lookup read path** for tier 2: a `catalog_lookup(system, api_name, *, kind)` helper over the existing `access/repositories/catalog/read.py`, including synonym-extended matching. Note the deployment caveat: the catalog YAML source tree is gitignored — tier 2 degrades to tier 3 (with anomalies) on an unseeded database, which N9 makes safe.
4. **Evidence detail keys**: add `catalog_attribute_type` (§2.2) and `catalog_disagreement` (§4.2) to the transform's `evidence_detail` payload; bump `EVIDENCE_SCHEMA_VERSION` per its discriminator contract.
5. **Priority derivation** as a render/query-time helper (consumed by the Baseline Report renderer and the WTK-088 triage queries) — **not** a deposit-time write.
6. **Fixtures + tests** per §6 (N1–N3, N5–N9 offline against the plan; N4's seven fixtures, of which only espocrm exercises a real adapter today).
7. **Out of scope here:** the six non-EspoCRM source adapters themselves (each future adapter consumes its pinned table); the Baseline Report renderer; growing `FIELD_TYPES` (PI-054 — when it lands, only §3.2 changes).

---

## 8. Open Questions and Deferred Decisions

- **`time` and `attachment` lossiness** (§3.2): both collapse to `text` today. If triage practice shows the loss matters, the fix is PI-054 vocabulary growth, not per-system table changes — the two-stage design localizes it.
- **A third `package` partition class** (§4.5): namespaced-package and extension items partition `standard` in v1. If triage practice shows package-vs-platform provenance changing dispositions, `package` is added to the partition vocabulary (and `evidence_catalog_class`'s admitted values) as a deliberate widening.
- **Attio and Bloomerang table confirmation** (§2.3): the two least-documented adapters; their stage-1 tables harden when their adapters are built, through the N4 gate.
- **Synonym-match confidence** (§4.2 tier 2): synonym-extended catalog matching may want a confidence note in `evidence_detail` if false-positive matches surface in practice; exact-api_name-first ordering is the v1 guard.
- **Band thresholds as engagement configuration**: the 365-day / 0.05 thresholds are constants shared with WTK-096. A seasonal-cycle client (annual campaigns) may need a wider window; if so, the engagement-level override belongs in one shared place consumed by the profiler, the normalizer's priority projection, and the triage queries together.

---

## 9. Cross-References

- `specifications/master-crmbuilder-PRD.md` v0.2 — §7 Phase 1.5 Activity step 3 (the step this spec defines), phase rules, capture table; §8 Phase 3 triage (the consumer of the partition and priority)
- `audit-report-to-candidate-deposit-transform.md` (WTK-090) — the deposit pipeline hosting this layer; §3.2 (the landed espocrm map and scope rules), §3.6 (anomaly PI), §5 (evidence attachment), §8 (fixture format)
- `crmbuilder-v2/src/crmbuilder_v2/transform/audit_deposit.py` — `WIRE_TYPE_MAP`, `_FALLBACK_FIELD_TYPE`, `ENTITY_KIND_MAP`, `EVIDENCE_SCHEMA_VERSION` (the landed implementation §3.3 composes to and §7 refactors)
- `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — `CATALOG_SYSTEMS`, `CATALOG_ATTRIBUTE_TYPES`, `CATALOG_PRESENCE_STATUSES`, `CATALOG_IS_STANDARD_VALUES`, `FIELD_TYPES`, `ENTITY_KINDS`
- `catalog-ingestion-PRD-v0.1.md` §4 — `catalog_entity_system`, `catalog_attribute_presence`, the synonym tables (the tier-2 oracle)
- `crmbuilder-v2/src/crmbuilder_v2/access/repositories/catalog/read.py` — the catalog read path tier 2 builds on
- `espo_impl/core/audit_utils.py` — `classify_entity` / `classify_field` / `SYSTEM_FIELDS` / `NATIVE_*_FIELDS` (the espocrm tier-1 marker, and the pinned-native-sets precedent Attio's adapter mirrors)
- `espocrm-data-profiling-pass.md` (WTK-096) — the utilization metrics and dormancy thresholds §5 reuses
- `candidate-lifecycle-rejected-and-utilization-evidence.md` (WTK-088) — `evidence_catalog_class`, `evidence_detail`, the latest-snapshot-per-`(subject, source)` rule, triage queries
- `field.md` §3.2.3 — the `FIELD_TYPES` vocabulary and its shape-not-rendering rationale; PI-054 (vocabulary growth, the §3.2 refinement trigger)

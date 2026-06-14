# Engine-Neutral CRM Design Model & Pluggable Adapters — Phase 0 Design

**Project:** PRJ-025 · **Planning item:** PI-180 · **Topic:** TOP-089
**Status:** v0.1 (Phase 0 gate — design-model spec + dual-engine mapping)
**Implements:** REQ-142 (two-engine validation); grounds REQ-139, REQ-140, REQ-141, REQ-144, REQ-145.

---

## 1. Purpose

This document fixes the shape of the **engine-neutral CRM design model** before any schema
migration is written. It is the gate for PI-B (intrinsic field/entity intent) and PI-C (composite
constructs): those PIs implement exactly the columns, records, and edges this document specifies, and
no others.

The inversion (DEC of SES-173 / CNV-079): today the deployable CRM definition is hand-authored
EspoCRM-shaped YAML. We make the **V2 database the single, engine-neutral source of truth for CRM
design** — *what the CRM must do*, expressed independently of any product — and **generate** the
deployable artifact (EspoCRM YAML first, HubSpot and others later) on demand via a per-engine
**adapter**. This is the compiler model: the DB is an engine-neutral intermediate representation
(IR); each target CRM is a pluggable backend.

## 2. Architecture

```
   V2 design records (engine-neutral IR)            ── the source of truth
            │
            ▼
   ┌──────────────────────────┐
   │  engine adapter (backend) │   derive mechanics · apply defaults · resolve overrides
   └──────────────────────────┘
       │              │
       ▼              ▼
  EspoCRM YAML    HubSpot config        ── generated artifacts (never hand-authored, never the source)
```

- **Design records** hold neutral design intent only. No EspoCRM (or HubSpot) internal names, type
  enums, formula syntax, styling, or layout mechanics live on them.
- **An adapter** reads the design records and emits the engine artifact. It **derives** engine
  mechanics deterministically wherever possible, **applies engine defaults** where design
  under-specifies, and **resolves a sparse engine-scoped override** layer for the genuine choices it
  cannot derive.
- **The EspoCRM adapter** is the first backend; its output must pass
  `espo_impl/core/config_loader.py::validate_program()` (REQ-143).

## 3. The three dispositions

Every CRM design attribute has exactly one home. This is the core decision framework.

| Disposition | Definition | Stored where | Test |
|---|---|---|---|
| **Neutral design** | Business meaning of the thing; portable across CRMs | On the design record (column / child record / edge) | Maps onto **≥2 engines** with the same intent |
| **Derived** | An adapter can compute it deterministically from neutral intent | **Nowhere** — produced at generation time | A pure function of neutral fields + engine rules |
| **Engine override** | A genuine per-engine choice an adapter cannot derive | A **sparse, engine-scoped** override record | Maps cleanly to **only one** engine, or is pure presentation an adapter can't infer |

**The bias guard (REQ-142):** an attribute may be classified **neutral design only if it has a
documented mapping to both EspoCRM and HubSpot** carrying the same intent. An attribute that maps
cleanly to only one engine is *not* neutral — it is reshaped (to the shared intent both engines can
honor) or demoted to the engine-override layer. The dual-engine columns in §6–§8 are that proof.

**"Derive, don't store" (REQ-141):** if the EspoCRM adapter can compute it (internal `cFieldName`,
formula text, default label, default Base/Person/Event type), it is **not** a stored column. Storing
derivable mechanics couples the DB to EspoCRM and is forbidden.

## 4. Engine reference models (the two backends being mapped)

**EspoCRM** (downstream target, authoritative schema: `PRDs/product/app-yaml-schema.md` v1.3.x).
Entities have a `type` (Base/Person/Company/Event), `settings` (labelSingular/Plural, stream,
disabled, autoPlaceName), fields with a platform `type` enum + `cFieldName` internal naming +
`options`/styling + `formula`/`requiredWhen`/`visibleWhen` condition-expression ASTs, top-level
`relationships:` (link types + names), plus `duplicateChecks`/`savedViews`/`workflows`/`layout`.

**HubSpot** (paper second engine; Doug has an instance for the real adapter later). Objects (standard
+ custom) carry **properties**: internal `name` (snake_case), `label`, a `type` (`string`, `number`,
`date`, `datetime`, `enumeration`, `bool`) paired with a `fieldType` (`text`, `textarea`, `select`,
`radio`, `checkbox`, `booleancheckbox`, `number`, `date`, `file`, `calculation_equation`), a
`groupName` (property group ≈ panel/tab), `description` (shown as help text), `options` (for
enumerations), `displayOrder`, `hasUniqueValue`, `calculated` + `calculationFormula`. Relationships
are **associations** between objects (association type/label + cardinality). HubSpot has **no**
per-option color styling, **no** entity-level default sort (sort is per saved view), and **no**
EspoCRM-style required-when/visible-when on the property schema (those are form/workflow concerns).

The cells where HubSpot has no clean analog are exactly where an attribute is **not** neutral — see
the "→ override" rows.

## 5. The neutral design model — record shapes (feeds PI-B/PI-C)

Three layers of design records:

1. **Entity** (`ENT-`, exists) — extended with intrinsic neutral attributes (§6).
2. **Field** (`FLD-`, exists, `field_belongs_to_entity` parent) — extended with intrinsic neutral
   attributes (§7) + an **option-value** child collection for enum/multi-enum.
3. **Composite design records** (new, §8) — associations, validation/conditional rules,
   duplicate-detection rules, list/view/sort intent, automation intent, notification intent.

Plus a single **engine-override** record type (§9), keyed by `(target_engine, design_record)`.

Neutral-typing principle for fields: the methodology `field_type` stays a small **semantic** value
shape (text, long_text, enum, multi_enum, date, datetime, money, boolean, number, reference,
derived). It is *not* the platform enum. The `number` shape carries an optional neutral
`numeric_scale` (integer vs decimal) so adapters need not guess.

## 6. Entity-level attributes — dual-engine mapping

| Neutral attribute | Disposition | EspoCRM | HubSpot | Notes |
|---|---|---|---|---|
| name (business) | neutral (`entity_name`, have) | entity key (natural) | object label/name | — |
| description | neutral (`entity_description`, have) | `description` | object description | — |
| kind | neutral (`entity_kind`, have) | → derives `type` Base/Person/Company/Event | object class (standard vs custom) | derive engine type from kind |
| **singular/plural label** | **derived** (from name; override if irregular) | `settings.labelSingular/Plural` | object singular/plural label | pluralization irregular → override |
| **default sort** | **neutral** (`entity_default_sort`: field ref + asc/desc) | entityDefs `orderBy`/`order` | default list-view sort | both honor "default ordering" intent |
| **stream/activity feed** | **neutral** (`entity_track_activity` bool) | `settings.stream` | object timeline (always on) | intent = "track activity"; HubSpot always-on, adapter no-ops |
| disabled | override (engine) | `settings.disabled` | n/a | EspoCRM-only lifecycle flag |
| autoPlaceName | **derived** | `settings.autoPlaceName` | n/a | EspoCRM layout mechanic; adapter default |
| action (delete_and_create) | override (engine) | `action:` | n/a | EspoCRM deploy lifecycle only |
| domain affiliation | neutral (`entity_scopes_to_domain` edge, have) | program-file grouping | (organizational) | methodology scoping |
| variant-of | neutral (`entity_variant_of_entity` edge, have) | naming/comment only | (subtype note) | NOT a relationship; never emits a link |

## 7. Field-level attributes — dual-engine mapping

| Neutral attribute | Disposition | EspoCRM | HubSpot | Notes |
|---|---|---|---|---|
| name (business) | neutral (`field_name`, have) | → derives `cFieldName` (camelCase + c-prefix) | → derives property `name` (snake_case) | derive per engine; never store |
| **label** | **derived** (Title-case from name; override if irregular) | `label` | property `label` | both derive cleanly |
| description (rationale) | neutral (`field_description`, have) | `description` | property `description` (help) | see tooltip split |
| **tooltip / help** | **neutral** (`field_tooltip`) | `tooltipText` | property `description` (help) | distinct from rationale; HubSpot folds both into description (adapter prefers tooltip) |
| **usage summary** | **neutral** (`field_usage_summary`) | (doc only) | (doc only) | documentation intent; renders to PRD, not engine config |
| type (semantic) | neutral (`field_type`, have) + `numeric_scale` | platform type enum | `type`+`fieldType` | derive platform pair from semantic shape |
| **required (always)** | **neutral** (`field_required`, have) | `required` | property/form `required` | — |
| **conditional required** | **neutral** (validation rule record, §8) | `requiredWhen:` AST | conditional logic / workflow | neutral condition; adapter compiles to each engine |
| **default value** | **neutral** (`field_default_value`) | `default` | property default | — |
| **read-only** | **neutral** (`field_read_only` bool) | `readOnly`/`inlineEditDisabled` | property read-only | derived-fields imply true |
| **value format** | **neutral** (`field_format` token, e.g. date/date_time/percent/currency) | type-implied + display | property fieldType/number format | neutral token; adapter maps |
| **allowed values (enum)** | **neutral** (option-value child records) | `options:` | enumeration `options` | the business vocabulary; both consume it |
| max length / min / max | neutral (`field_max_length`, `field_min`, `field_max`) | `maxLength`/`min`/`max` | property validation | numeric/text bounds are business constraints |
| **unique** | **neutral** (`field_unique` bool) | fieldDefs `unique` | `hasUniqueValue` | both support a uniqueness constraint |
| formula (derived) | **neutral** structured expression (§8) → engine syntax derived | `formula:` text | `calculationFormula` | store neutral expr; derive each engine's syntax |
| externally populated | neutral (`field_externally_populated` bool) | `externallyPopulated` | (integration-sourced) | verification-spec + integration intent |
| category / layout tab | **derived** intent + adapter default | `category` → `layout` | `groupName` | neutral "grouping" hint optional; mechanics derived |
| enum color/style/sorted/displayAsLabel | **override (engine)** | `style`/`isSorted`/`displayAsLabel`/`translatedOptions` | n/a (no per-option color) | EspoCRM-only presentation |
| audited | override (engine) | `audited` | (always tracked) | EspoCRM-only flag |

## 8. Composite design constructs — dual-engine mapping (new records, PI-C)

Each is a **neutral** record (engine syntax derived by the adapter).

| Construct | Neutral record | EspoCRM | HubSpot |
|---|---|---|---|
| **Association** (entity↔entity link) | `association` (source, target, cardinality one-to-one/one-to-many/many-to-many, two role names, optional through) | top-level `relationships:` (linkType + link/linkForeign names *derived* from role names) | object **association** (type/label + cardinality) |
| **Validation / conditional rule** | `rule` (neutral condition AST + effect: required-when / visible-when / valid-when) | `requiredWhen`/`visibleWhen` cond-expr; dynamic logic | conditional property logic / form rules / workflow |
| **Enum option value** | `field_option` (value, label, display order) | `options:` (+ engine styling via override) | enumeration `options` |
| **Duplicate detection** | `dedup_rule` (match fields, normalize intent e.g. case-fold/e164, on-match block/warn, message) | `duplicateChecks:` | dedup settings / property `hasUniqueValue` |
| **List/view + sort** | `view` (columns, filter condition AST, sort) | `savedViews:` (+ `orderBy`) | saved list view |
| **Automation** | `automation` (trigger event, condition AST, ordered actions) | `workflows:` (Advanced Pack) | HubSpot workflow |
| **Notification / templated message** | `message_template` (subject, body intent, merge fields, audience) | `emailTemplates:` | marketing/transactional email + templates |

Neutral condition/expression ASTs reuse / mirror the already engine-neutral model in
`espo_impl/core/condition_expression.py` (parse / validate / render). The adapter renders the AST to
each engine's concrete syntax — it is **not** stored as EspoCRM text.

## 9. The engine-override layer (sparse, REQ-141)

One record type, `engine_override`, keyed by `(target_engine, design_record_identifier,
attribute)`, carrying a JSON value. It holds **only** the un-derivable per-engine residue:

- EspoCRM: enum `style`/`translatedOptions`, `audited`, `disabled`, `action`, an explicitly
  hand-tuned `cFieldName`/label/formula override, layout panel mechanics, `filteredTabs` ACL.
- HubSpot (future): property `groupName` override, specific `fieldType` choice (e.g. radio vs
  select), calculation overrides.

Invariants: overrides are **scoped to one engine**, **never** required for generation (absent →
adapter default + a loud deferral note), and **never** a parallel copy of neutral attributes.

## 10. The adapter contract (feeds PI-D)

```
class CrmAdapter(Protocol):
    engine: str                      # "espocrm", "hubspot", ...
    def generate(self, design: DesignModel, overrides: OverrideSet) -> Artifact: ...
```

Responsibilities, in order: **derive** mechanics (names, labels, platform types, formula/condition
syntax, default entity type) → **apply engine defaults** for under-specified intent → **merge**
engine-scoped overrides → **emit** the artifact → **emit loud deferral stubs** + a `MANUAL-CONFIG.md`
companion for anything not yet capturable (never silently drop). The EspoCRM adapter additionally
runs its output through `validate_program()` as a self-check.

Reuse the established renderer shape (`crmbuilder-v2/src/crmbuilder_v2/render/baseline_report.py`):
GET-only client (X-Engagement, `{data,meta,errors}` unwrap), `fetch (impure) → build_model (pure) →
emit (pure)`, injected `rendered_at`, total orderings, atomic write, `crmbuilder-v2-export-espocrm`
CLI. Emit YAML with `ruamel.yaml` (block scalars + deterministic key order), not `safe_dump`.

## 11. Schema implications for PI-B and PI-C

**PI-B (intrinsic intent):** add field columns `field_tooltip`, `field_usage_summary`,
`field_default_value`, `field_read_only`, `field_format`, `field_unique`, `field_max_length`,
`field_min`, `field_max`, `field_externally_populated`, `numeric_scale`; entity columns
`entity_default_sort` (field ref + direction), `entity_track_activity`; and the **`field_option`**
child collection. Migration must rebuild `change_log`/`refs` CHECKs from current vocab (known-gotcha);
guard every migration >0036 for mid-chain entry; validate on a copy of live `v2-unified.db`.

**PI-C (composite constructs):** new record types `association`, `rule`, `dedup_rule`, `view`,
`automation`, `message_template`, `engine_override`; new reference kinds wiring them to entities/
fields; access/REST/MCP/UI for each. Reuse the neutral condition AST.

Each new column/record/edge traces to a §6–§8 row that has **both** engine mappings — that is the
Phase-0 bias proof and the entry criterion for building it.

## 12. Open questions / deferred

- **Formula/condition AST sharing:** confirm `condition_expression.py`'s AST is rich enough for the
  neutral `rule`/formula model, or whether PI-C grows a dedicated neutral-expression module.
- **HubSpot association cardinality** nuances (labeled associations, primary) — finalized when the
  real HubSpot adapter is built against Doug's instance; the paper mapping above is the v0.1 guard.
- **Layout** stays "grouping intent + adapter default" in v0.1; richer neutral layout intent is a
  later PI if EspoCRM/HubSpot demand diverges.
- **Roles / field-level permissions** (EspoCRM §12) — out of scope for the design-model v0.1; revisit
  with a neutral access-intent model once two engines' RBAC shapes are compared.

# CRMBuilder v2 — Catalog Ingestion PRD

**Version:** 0.1 (draft)
**Last Updated:** 05-09-26 14:30
**Status:** Draft — pending approval

## Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.1 | 05-09-26 | Initial draft. Specifies the catalog database schema (9 tables), one-time Alembic data migration with two-pass loader, REST API + MCP tool surface, universal references integration, and JSON export hook behavior. Companion implementation plan to follow once this PRD is approved. |

---

## 1. Overview

### Purpose

This PRD specifies the requirements for CRMBuilder v2's catalog ingestion subsystem: the database schema, one-time migration, and API/MCP surface that bring the base entity catalog into V2 as authoritative data, retiring the YAML files that currently hold it. After ingestion, the catalog is editable through V2's UI and consumable by V2's methodology workflows, deployment renderers, and Claude-assisted operations via MCP.

The PRD specifies what a functioning catalog ingestion subsystem must do; how to build it is the companion implementation plan's concern.

### Background

The base entity catalog at `PRDs/product/crmbuilder-v2/research/base-entity-catalog/` is a structured research deliverable: 42 entries (34 universal + 8 subclass) across 5 tiers, with 414 attributes, 228 source citations, per-system mappings across seven surveyed CRM systems, common-synonym vocabulary, and full cross-system api_name resolution where authoritatively known. The catalog was authored in YAML during a research process; it is now reference data that V2 needs at runtime for three operational use cases (per `base-entity-catalog-research.md`):

1. **Reference library** — surfacing catalog entries during methodology entity drafting, so the interviewer sees what attributes most CRMs include for a concept
2. **Cross-system mapper** — at deployment configuration time, translating domain entities and attributes into the target backend's native names
3. **Gap checker** — comparing a draft entity-PRD's attribute list against the catalog's universal attribute set to flag omissions

The catalog is currently external to V2 (YAML files on disk). This PRD specifies its ingestion into V2's storage stack so V2's UI, API, and MCP server can serve the three use cases without external file dependencies.

### Source decisions

This PRD inherits the following decisions; they are not re-derived:

- **DEC-004 — Database as source of truth for all v2 artifacts.** Catalog content lives in the V2 database after ingestion; YAML files are decommissioned.
- **DEC-005 — Storage stack: SQLite + access layer + REST API + MCP server.** Catalog tables use the same four-layer pattern as the rest of V2.
- **DEC-006 — Universal references pattern with controlled relationship vocabulary.** Catalog rows are referenceable targets in the universal references table; the catalog's own inter-entity relationships use a dedicated `catalog_relationship` table (the two layers don't mix).
- **DEC-008 — Renders, not authored copies.** Catalog JSON exports are derived from the database; one file per entity, regenerated on every write to that entity.

In addition, eight design decisions specific to catalog ingestion were resolved during planning (see Open Questions section 10 for the resolved-decision summary).

---

## 2. Scope

### In Scope

The following are required deliverables for v0.1:

1. **Schema.** Nine SQLAlchemy 2.0 tables capturing the catalog data model (specified in section 4): `catalog_entity`, `catalog_entity_synonym`, `catalog_entity_system`, `catalog_source`, `catalog_attribute`, `catalog_attribute_enum_value`, `catalog_attribute_synonym`, `catalog_attribute_presence`, `catalog_relationship`, `catalog_relationship_presence`. (Ten counting `catalog_relationship_presence`, which is structurally a child of `catalog_relationship`.)

2. **One-time Alembic data migration.** Reads the 42 YAML files from `PRDs/product/crmbuilder-v2/research/base-entity-catalog/` and populates rows in dependency order with full fidelity. Idempotent via upsert-by-catalog_id semantics. Wrapped in a single transaction.

3. **Loader helper module.** Reusable Python module (`crmbuilder_v2/migrations/helpers/catalog_loader.py`) that the migration calls. Handles YAML parsing, two-pass entity insertion (universals first, subclasses second, relationships third), and validation. The data migration is a thin wrapper around this helper.

4. **Post-migration cleanup.** The migration commit removes `PRDs/product/crmbuilder-v2/research/base-entity-catalog/` (and its `subclasses/` subdirectory) from the working tree, along with the two cross-cutting deliverables `base-entity-catalog-research.md` and `entity-system-map.yaml`. Per V2's bootstrap-content pattern, these remain recoverable through git history but are no longer the source of truth.

5. **Catalog access layer.** Python module owning all reads and writes to catalog tables. Validates inputs, enforces controlled vocabularies (system enum, status enum, mechanism enum, data_model_role enum), manages transactions, and triggers JSON export generation on every catalog-entity write.

6. **REST API endpoints.** FastAPI routes for read (list, get, search, cross-system-map, gap-check) and write (create / update / delete entity, create / update / delete attribute on entity). Entity-level writes carry nested sub-row data as part of the parent payload; standalone sub-row endpoints are not exposed.

7. **MCP tools.** Four read-only tools exposed via V2's MCP server: `catalog_search`, `catalog_get_entity`, `catalog_get_cross_system_map`, `catalog_gap_check`. Write-side MCP tools are deferred.

8. **JSON export hook integration.** Per-entity exports under V2's exports directory at `catalog/entities/{catalog_id}.json`. Suppressed during the data migration; bulk-regenerated as a single step after migration completes. Per-entity regeneration fires on every catalog-entity write thereafter.

9. **Universal references integration.** Catalog entity and catalog attribute become valid `target_type` values in V2's universal references table. Other V2 entities (decisions, planning items, future methodology entities) can reference catalog rows. Catalog rows do not source universal references (catalog-internal relationships use the dedicated `catalog_relationship` table).

10. **Acceptance test suite.** Tests confirming: row counts after migration match expected (42 entities, 414 attributes, 2,898 presence cells, etc.); idempotency on re-run; soft-delete behavior; API contract; MCP tool contract; JSON export shape; suppression flag behavior during bulk operations.

### Out of Scope

The following are explicitly deferred to later versions or separate work:

1. **Methodology entity schema.** Personas, entities, fields, processes, process steps, requirements, manual-config items, test specifications. Catalog ingestion exposes the integration points (catalog rows are referenceable; the hybrid pattern from Decision 7 is sketched) but the methodology schema is a separate workstream.

2. **Catalog editing UI.** REST API endpoints for catalog editing are in scope; the V2 web UI that consumes them is a separate workstream (parallel to existing decisions / planning-items UIs).

3. **Write-side MCP tools.** Read-only MCP tools at v0.1; write-side tools (catalog_create_entity, catalog_update_entity) deferred until usage patterns surface.

4. **Pagination.** 42 entities and 414 attributes don't require pagination. Adding pagination is deferred until catalog scale demands it.

5. **Authentication and authorization.** Inherits the storage system PRD's deferral. Single-user, local at v0.1.

6. **Fresh-install seeding workflow.** Once the YAML files are decommissioned, a fresh V2 install cannot re-seed catalog from YAMLs in the user's working tree (the YAMLs are gone). Re-seeding from git history or a packaged dump is deferred to productization.

7. **Catalog versioning / time-travel.** No version-pinning of catalog state. Standard V2 audit columns (`created_at`, `updated_at`) provide history; full versioning is deferred.

8. **Reseeding from JSON exports.** The JSON exports produced by DEC-008 could conceptually be the seed source for fresh installs, but the loader doesn't read them at v0.1. Possible future enhancement.

---

## 3. Architecture and integration

### Position in V2's storage stack

Catalog ingestion sits inside V2's existing four-layer stack (DEC-005):

```
┌──────────────────────────────────────────────────────────────┐
│  MCP server (catalog_search, _get_entity, etc.)              │  Layer 4
├──────────────────────────────────────────────────────────────┤
│  REST API (GET/POST/PUT/DELETE /catalog/...)                 │  Layer 3
├──────────────────────────────────────────────────────────────┤
│  Catalog access layer (Python module)                        │  Layer 2
│    - Read methods (list_entities, get_entity, search, ...)   │
│    - Write methods (create_entity, update_entity, ...)       │
│    - JSON export hook trigger                                │
├──────────────────────────────────────────────────────────────┤
│  Storage (SQLite + SQLAlchemy 2.0 + Alembic)                 │  Layer 1
│    catalog_entity, catalog_attribute, catalog_*_presence,    │
│    catalog_*_synonym, catalog_*_system, catalog_source,      │
│    catalog_relationship, catalog_relationship_presence       │
└──────────────────────────────────────────────────────────────┘
```

The data migration runs once during the catalog-ingestion build commit. After that, V2 operates with the populated database; the YAML files are gone from the working tree.

### Integration with universal references (DEC-006)

V2's universal references table holds cross-entity references with a controlled relationship vocabulary. Catalog ingestion expands the controlled `target_type` vocabulary to include two new values:

- `catalog_entity` — references to a catalog entity row
- `catalog_attribute` — references to a catalog attribute row

The `target_id` is the catalog row's UUID. Source-side reference types are unchanged. Existing V2 entities (decisions, planning items, etc.) can immediately begin referencing catalog entries as targets; future methodology entities will rely on this same mechanism.

Catalog-internal relationships (e.g., "An Account has many Contacts") do not flow through universal references — they live in the dedicated `catalog_relationship` table and describe the data model rather than project artifacts. The two relationship layers do not mix.

### Integration with future methodology entity schema (Decision 7 sketch)

When the methodology entity schema is built, it will reference catalog entries using a hybrid pattern (per Decision 7 resolution):

- A future `methodology_entity` table will carry an optional `primary_catalog_entity_id` foreign key (the strongest "this entity is based on catalog X" claim, nullable for custom entities with no catalog parallel).
- Additional weak references (e.g., "this entity also borrows attributes from catalog `engagement`") use the universal references table with `target_type=catalog_entity` and a relationship vocabulary value like `derives_from` or `borrows_from`.
- The same pattern applies to attribute-level references.

This integration is not implemented in v0.1; catalog ingestion exposes the affordances (UUID primary keys, inclusion in universal references vocabulary, stable catalog_id text identifiers) and the methodology schema picks them up when it lands.

---

## 4. Schema specification

### Tables

The catalog comprises ten tables (one canonical entity table plus five entity-child tables plus one attribute table plus three attribute-child tables; the relationship layer adds two more):

#### 4.1 `catalog_entity`

One row per catalog entry. 42 rows after initial migration.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | UUID | PRIMARY KEY | V2 standard |
| `catalog_id` | TEXT | UNIQUE, NOT NULL | Stable string identifier (e.g., "account", "donation") |
| `name` | TEXT | NOT NULL | Display name (e.g., "Account") |
| `display_name` | TEXT | NOT NULL | Same as name for top-level entities; subclass-specific label for subclasses |
| `tier` | INTEGER | NOT NULL, CHECK 1-5 | Catalog tier |
| `entry_kind` | TEXT | NOT NULL, CHECK IN ('universal','subclass') | Entity kind |
| `parent_entity_id` | UUID | FK → catalog_entity.id, NULLABLE | Set only for subclasses |
| `discriminator_attribute` | TEXT | NULLABLE | Subclass discriminator field name |
| `discriminator_value` | TEXT | NULLABLE | Subclass discriminator value |
| `purpose` | TEXT | NOT NULL | Short purpose statement |
| `business_context` | TEXT | NOT NULL | Long-form context narrative |
| `data_model_role` | TEXT | NOT NULL, CHECK IN ('anchor','event','classifier','junction','log','document') | Role classifier |
| `typically_required` | BOOLEAN | NOT NULL, DEFAULT false | Whether entity is typically required |
| `is_deleted` | BOOLEAN | NOT NULL, DEFAULT false | V2 soft-delete pattern |
| `created_at`, `updated_at` | TIMESTAMP | V2 audit columns | |

Indexes: `catalog_id` (unique), `(tier, entry_kind)`, `parent_entity_id`, `is_deleted`.

#### 4.2 `catalog_entity_synonym`

Synonyms at entity level. ~200 rows.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `catalog_entity_id` | UUID | FK → catalog_entity.id ON DELETE CASCADE |
| `synonym` | TEXT | NOT NULL |
| `order_index` | INTEGER | NOT NULL, DEFAULT 0 |

Indexes: `catalog_entity_id`, `synonym` (for synonym-based search).

#### 4.3 `catalog_entity_system`

Per-system entity mapping. 294 rows (42 entities × 7 systems).

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `catalog_entity_id` | UUID | FK → catalog_entity.id ON DELETE CASCADE |
| `system` | TEXT | NOT NULL, CHECK IN (the 7 surveyed system slugs) |
| `system_name` | TEXT | NOT NULL | Display name in this system |
| `api_name` | TEXT | NULLABLE | API identifier in this system |
| `is_standard` | TEXT | NOT NULL, CHECK IN ('true','false','partial') | Stored as TEXT to accommodate 'partial' edge case from a few entries |
| `mechanism` | TEXT | NULLABLE, CHECK IN ('record_type','contact_subtype','type_discriminator','custom_property','separate_object','entity_inheritance') | Subclass mechanism; null for universals |
| `notes` | TEXT | NULLABLE |
| `docs_url` | TEXT | NULLABLE |

Indexes: `catalog_entity_id`, `(system, catalog_entity_id)` unique together.

#### 4.4 `catalog_source`

Citation URLs per entity. 228 rows.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `catalog_entity_id` | UUID | FK → catalog_entity.id ON DELETE CASCADE |
| `title` | TEXT | NOT NULL |
| `url` | TEXT | NOT NULL |
| `order_index` | INTEGER | NOT NULL, DEFAULT 0 |

#### 4.5 `catalog_attribute`

One row per catalog attribute. 414 rows.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `catalog_entity_id` | UUID | FK → catalog_entity.id ON DELETE CASCADE |
| `name` | TEXT | NOT NULL | Internal attribute name (e.g., "accountName") |
| `display_name` | TEXT | NOT NULL | Display label (e.g., "Account Name") |
| `type` | TEXT | NOT NULL, CHECK IN (the catalog's attribute-type vocabulary) | Attribute type |
| `required` | BOOLEAN | NOT NULL |
| `max_length` | INTEGER | NULLABLE |
| `reference_target` | TEXT | NULLABLE | catalog_id of the target entity for reference / multireference types |
| `description` | TEXT | NOT NULL |
| `usage` | TEXT | NOT NULL |
| `order_index` | INTEGER | NOT NULL, DEFAULT 0 |
| `is_deleted` | BOOLEAN | NOT NULL, DEFAULT false |
| `created_at`, `updated_at` | TIMESTAMP | |

Constraints: `UNIQUE(catalog_entity_id, name)`.
Indexes: `catalog_entity_id`, `name`, `is_deleted`.

#### 4.6 `catalog_attribute_enum_value`

Enum values for enum-typed attributes. ~150 rows.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `catalog_attribute_id` | UUID | FK → catalog_attribute.id ON DELETE CASCADE |
| `value` | TEXT | NOT NULL |
| `order_index` | INTEGER | NOT NULL, DEFAULT 0 |

#### 4.7 `catalog_attribute_synonym`

Synonyms at attribute level. ~280 rows.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `catalog_attribute_id` | UUID | FK → catalog_attribute.id ON DELETE CASCADE |
| `synonym` | TEXT | NOT NULL |
| `order_index` | INTEGER | NOT NULL, DEFAULT 0 |

Indexes: `catalog_attribute_id`, `synonym`.

#### 4.8 `catalog_attribute_presence`

Per-system attribute presence and api_name. 2,898 rows (414 attributes × 7 systems).

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `catalog_attribute_id` | UUID | FK → catalog_attribute.id ON DELETE CASCADE |
| `system` | TEXT | NOT NULL, CHECK IN (the 7 surveyed system slugs) |
| `status` | TEXT | NOT NULL, CHECK IN ('standard','custom','absent') |
| `api_name` | TEXT | NULLABLE | Populated when status is 'standard' and authoritative or convention-derived |

Constraints: `UNIQUE(catalog_attribute_id, system)`.

#### 4.9 `catalog_relationship`

Inter-entity relationships from the YAML `relationships[]` block. ~150 rows.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `source_entity_id` | UUID | FK → catalog_entity.id ON DELETE CASCADE |
| `target_entity_id` | UUID | FK → catalog_entity.id ON DELETE CASCADE |
| `cardinality` | TEXT | NOT NULL, CHECK IN ('one-to-one','one-to-many','many-to-one','many-to-many') |
| `role` | TEXT | NOT NULL, CHECK IN ('parent','child','peer') |
| `description` | TEXT | NOT NULL |

#### 4.10 `catalog_relationship_presence`

Per-system relationship presence. ~1,050 rows.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `catalog_relationship_id` | UUID | FK → catalog_relationship.id ON DELETE CASCADE |
| `system` | TEXT | NOT NULL |
| `status` | TEXT | NOT NULL, CHECK IN ('standard','custom','absent') |

### Row count summary

| Table | Rows after migration |
|---|---|
| catalog_entity | 42 |
| catalog_entity_synonym | ~200 |
| catalog_entity_system | 294 |
| catalog_source | 228 |
| catalog_attribute | 414 |
| catalog_attribute_enum_value | ~150 |
| catalog_attribute_synonym | ~280 |
| catalog_attribute_presence | 2,898 |
| catalog_relationship | ~150 |
| catalog_relationship_presence | ~1,050 |
| **Total** | **~5,700** |

---

## 5. Ingestion mechanics

### One-time Alembic data migration

Two Alembic revisions land together:

- `000X_catalog_schema` — creates all 10 catalog tables, indexes, and check constraints. Standard table-creation migration.
- `000X+1_catalog_seed` — invokes the loader helper module to read YAMLs from `PRDs/product/crmbuilder-v2/research/base-entity-catalog/` and populate rows. Wraps everything in a single transaction.

The migrations run automatically as part of V2's standard startup migration flow. Doug confirms successful migration via the acceptance criteria in section 9.

### Loader helper module

Located at `crmbuilder_v2/migrations/helpers/catalog_loader.py`. Public function:

```python
def load_catalog(session: Session, yaml_dir: Path, suppress_exports: bool = True) -> CatalogLoadReport:
    """Load all catalog YAMLs from yaml_dir into the database via the given session.
    
    Returns a CatalogLoadReport with: entities_inserted, attributes_inserted,
    presence_cells_inserted, relationships_inserted, validation_failures.
    
    Idempotent: re-running produces the same final state via upsert-by-catalog_id.
    """
```

Called by the data migration. Also callable directly for testing.

### Three-pass loader

Pass 1 — **Universal entities and their nested data**:
- For each universal-kind YAML file:
  - Upsert `catalog_entity` (keyed on catalog_id; UPDATE if exists)
  - Replace child rows (delete + reinsert): `catalog_entity_synonym`, `catalog_entity_system`, `catalog_source`
  - For each attribute: upsert `catalog_attribute` (keyed on catalog_entity_id + name); replace its child rows (`catalog_attribute_enum_value`, `catalog_attribute_synonym`, `catalog_attribute_presence`)

Pass 2 — **Subclass entities and their nested data**:
- Same as Pass 1, but parent_entity_id is resolved from the parent's catalog_id text → UUID (now available from Pass 1)

Pass 3 — **Relationships**:
- For each catalog_relationship YAML entry, look up source and target catalog_entity by catalog_id, insert relationship row, insert per-system presence

The three-pass ordering respects FK constraints: parent entities exist before subclasses reference them; both source and target entities exist before relationships reference them.

### Idempotency

Upsert-by-catalog_id (entities) and upsert-by-(entity_id, name) (attributes) make the loader idempotent. Dependent rows are delete-and-recreate per parent — a simple correctness strategy at the catalog's scale (5,700 rows total).

Re-running the migration after successful initial seed is a no-op at the Alembic level (revision already applied). Re-running the loader helper directly (e.g., during development to test a YAML change) produces a clean state.

### Validation step

After all three passes complete, the loader runs assertions:

- Row count of `catalog_entity` matches the expected (42 ± plan drift)
- Every subclass has `parent_entity_id` resolved to a real catalog_entity row
- Every `catalog_attribute_presence` row's status is in the allowed enum
- Every `catalog_relationship` row has both source and target resolved
- `catalog_id` values are unique across all entities

If any assertion fails, the transaction rolls back. The migration is atomic.

### Post-migration cleanup

The commit that lands the data migration also removes from the working tree (via `git rm`):

- `PRDs/product/crmbuilder-v2/research/base-entity-catalog/` (entire directory including `subclasses/`)
- `PRDs/product/crmbuilder-v2/research/base-entity-catalog-research.md`
- `PRDs/product/crmbuilder-v2/research/entity-system-map.yaml`

These files remain recoverable through git history but are no longer the source of truth. The `research/` directory continues to exist for other research deliverables.

---

## 6. API surface

### REST endpoints

All under `/catalog/`. FastAPI routes with Pydantic v2 request/response models.

#### Read endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/catalog/entities` | List entities. Query params: `tier`, `entry_kind`, `parent_entity`, `system`, `data_model_role`, `include_deleted` |
| GET | `/catalog/entities/{catalog_id}` | Get one entity with all nested data |
| GET | `/catalog/entities/{catalog_id}/attributes/{name}` | Get one attribute |
| GET | `/catalog/search` | Text search across entity names, attribute names, synonyms. Query params: `q`, `limit` (default 10, max 50), `include_attributes`, `include_synonyms` |
| GET | `/catalog/cross-system-map/{catalog_id}` | Per-system mapping for one entity. Query param: `system` to filter |
| POST | `/catalog/gap-check` | Body: `{ based_on_catalog_id, draft_attribute_names }`. Returns missing common attributes |

#### Write endpoints

Entity is the unit of edit. Sub-row data flows through the parent entity's payload.

| Method | Path | Purpose |
|---|---|---|
| POST | `/catalog/entities` | Create new entity |
| PUT | `/catalog/entities/{catalog_id}` | Replace entity (full payload incl. all nested data) |
| PATCH | `/catalog/entities/{catalog_id}` | Partial update of entity-level fields only |
| DELETE | `/catalog/entities/{catalog_id}` | Soft-delete |
| POST | `/catalog/entities/{catalog_id}/attributes` | Create new attribute on entity |
| PUT | `/catalog/entities/{catalog_id}/attributes/{name}` | Replace attribute (full payload incl. presence + synonyms) |
| PATCH | `/catalog/entities/{catalog_id}/attributes/{name}` | Partial update |
| DELETE | `/catalog/entities/{catalog_id}/attributes/{name}` | Soft-delete attribute |

#### Response patterns

- Standard V2 envelope (success/error/metadata) per existing convention
- Read responses for entities include nested attributes, systems, sources, synonyms, relationships
- List responses use a lightweight `CatalogEntitySummary` model (no nested data); detail responses use full `CatalogEntity`
- Soft-deleted rows excluded by default; `include_deleted=true` query param to include
- Inbound references (from universal references table) appear on entity / attribute detail responses

### MCP tools

Four read-only tools registered with V2's MCP server.

| Tool | Inputs | Output |
|---|---|---|
| `catalog_search` | `query: str`, `limit: int = 10` | Ranked list of catalog entries with brief context |
| `catalog_get_entity` | `catalog_id: str` | Full entity detail (matching the REST GET response) |
| `catalog_get_cross_system_map` | `catalog_id: str`, `target_system: str \| None = None` | Entity + all attributes mapped to the target system (or all systems if None) |
| `catalog_gap_check` | `based_on_catalog_id: str`, `draft_attribute_names: list[str]` | List of catalog universal attributes missing from the draft, with their cross-system standard counts |

Tool implementations are thin wrappers around the catalog access layer's read methods. No business logic at the MCP layer beyond protocol translation (per the V2 MCP architecture pattern).

Write-side MCP tools are not exposed at v0.1. Adding them is a future workstream once usage patterns surface a need.

---

## 7. JSON export hook behavior

Per DEC-008, V2 generates JSON exports on every write. For catalog ingestion:

### Per-entity export granularity

One JSON file per `catalog_entity` row, at `{V2_export_root}/catalog/entities/{catalog_id}.json` (subdirectory layout flat — subclasses live alongside universals in the same directory; the JSON's `entry_kind` and `parent_entity` fields capture the subclass relationship).

Each file contains the full entity payload: entity row + all its synonyms + systems + sources + attributes (with their enum_values, synonyms, presence) + relationships (source side only, to avoid duplication).

### Serialization details

- JSON structure mirrors the REST GET `/catalog/entities/{catalog_id}` response
- Sorted keys, 2-space indent (deterministic across runs)
- UUIDs excluded; `catalog_id` is the stable identifier in the JSON
- Relationships serialize on the source side only

### Bulk operation suppression

The data migration writes ~5,700 rows. Firing the export hook on every row write would regenerate the same set of JSON files dozens of times. The access layer exposes a `suppress_exports` context flag (callable as a context manager or constructor argument); the data migration sets it. When the flag is true, the export hook is a no-op.

After the data migration completes, a single explicit `regenerate_all_catalog_exports()` call writes all 42 JSON files once. This produces the initial state of the exports directory.

Future ad-hoc writes through the access layer use the hook normally (suppression off by default).

---

## 8. Acceptance criteria

The catalog ingestion subsystem is "functioning" when all of the following are true:

1. **Schema present**: All 10 catalog tables exist with the correct columns, constraints, and indexes per section 4. Alembic migration history shows the catalog schema and seed revisions applied.

2. **Catalog populated**: Row counts match section 4's expected totals within plan drift tolerance (±5 entities, ±50 attributes, ±100 sub-rows). All 42 catalog entries from the YAML files are represented with full fidelity (purpose, business_context, all attributes, all presence cells, all synonyms, all sources, all relationships).

3. **Subclass parents resolved**: Every row in `catalog_entity` with `entry_kind='subclass'` has a valid `parent_entity_id` pointing to a real `catalog_entity` row. The discriminator fields are populated.

4. **api_name coverage**: Every `catalog_attribute_presence` row with `status='standard'` has either a populated `api_name` or an explicit acknowledgment that none was captured in the source YAML (NULL is permitted for standard cells where the source YAML lacked an api_name).

5. **Idempotency**: Re-running the loader helper directly (e.g., via a CLI command or test fixture) produces the same final database state without errors. Re-running Alembic migrations after successful seed is a no-op.

6. **REST API contract**: All endpoints in section 6 return responses conforming to their Pydantic models. List endpoint supports the documented query filters. Search returns ranked hits. Cross-system-map returns the expected nested structure. Gap-check returns correct results against known input.

7. **MCP tool contract**: All four MCP tools registered with V2's MCP server, callable with their documented input schemas, return responses matching their documented output schemas.

8. **JSON exports written**: After the post-migration bulk regenerate runs, `{export_root}/catalog/entities/` contains 42 JSON files (one per catalog entity). Each file is valid JSON, sorted-key, 2-space indent, and round-trips via the same regeneration logic.

9. **Universal references integration**: The universal references table accepts `target_type='catalog_entity'` and `target_type='catalog_attribute'` without error. Inbound references from other V2 entities are exposed on catalog entity / attribute detail responses.

10. **YAML files decommissioned**: After the migration commit, `git ls-files PRDs/product/crmbuilder-v2/research/base-entity-catalog/` returns empty. The two cross-cutting deliverables (`base-entity-catalog-research.md`, `entity-system-map.yaml`) are also removed from the working tree.

11. **Acceptance test suite passes**: Pytest suite covers the above criteria with assertion-level coverage. All tests pass.

---

## 9. Out of scope

Repeated here for visibility (full list in section 2):

- Methodology entity schema (separate workstream; catalog integration points are exposed)
- Catalog editing UI in V2 (REST API is in scope; UI is a parallel workstream)
- Write-side MCP tools
- Pagination
- Authentication / authorization
- Fresh-install seeding workflow (assumes Doug's initial install)
- Catalog versioning / time-travel beyond standard audit columns
- Reseeding from JSON exports

---

## 10. Open questions and resolved-decision summary

### Resolved decisions (from planning conversation)

| # | Decision | Resolution |
|---|---|---|
| 1 | Catalog source of truth — YAML or DB? | DB (Option B). YAMLs decommissioned post-migration |
| 2 | Update strategy | One-time migration only; future edits via V2 |
| 3 | Schema layout | Ten tables per section 4 |
| 4 | Universal references integration | Catalog rows are referenceable targets; catalog-internal relationships in dedicated table |
| 5 | Ingestion mechanics | Alembic data migration with three-pass loader; upsert-by-catalog_id idempotency; YAMLs decommissioned in same commit |
| 6 | API/MCP surface | Full read + write REST; four read-only MCP tools; entity-level write granularity |
| 7 | Methodology entity integration | Hybrid pattern (primary FK + universal references for weak ties); sketched only, not implemented in v0.1 |
| 8 | JSON export hook | Per-entity exports; suppression flag during migration; bulk regenerate after |

### Open questions for implementation plan

These are questions the companion implementation plan must answer; they don't change the PRD's requirements:

- Exact Alembic revision number prefixes (depends on existing V2 migration history)
- Whether the catalog access layer is one module or split across multiple files (read methods vs write methods vs export hook)
- V2's existing JSON export directory location (the PRD assumes `{V2_export_root}/catalog/entities/` but the implementation plan should confirm against the storage system implementation)
- Naming conventions for Pydantic models (`CatalogEntity` vs `CatalogEntityRead` vs other patterns V2 uses)
- Test fixture strategy for catalog ingestion tests (in-memory SQLite? Test database? Shared with other V2 tests?)

### Pre-existing catalog issue not addressed by this PRD

The `donation-major-gift` subclass YAML has a discriminator referencing `parent.type`, but `donation.yaml` has no `type` attribute. This is a latent bug in the catalog content surfaced during the v0.9 naming rationalization. The fix requires adding a `donationType` attribute to `donation.yaml` with cross-system mapping. This is out of scope for catalog ingestion — fixed in a separate follow-up commit before ingestion runs. The ingestion loader should handle the broken discriminator gracefully (validation step flags it but doesn't block migration), or the catalog fix lands first.

---

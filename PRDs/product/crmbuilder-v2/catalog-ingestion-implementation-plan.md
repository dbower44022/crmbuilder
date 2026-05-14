# CRMBuilder v2 — Catalog Ingestion v0.1 Implementation Plan

**Version:** 0.1
**Last Updated:** 05-09-26 15:00
**Status:** Approved for execution
**Companion PRD:** `catalog-ingestion-PRD-v0.1.md` (v0.2, approved)
**Executing prompt:** `prompts/CLAUDE-CODE-PROMPT-v2-C-catalog-ingestion.md` (to follow)

---

## Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.1 | 05-09-26 | Initial implementation plan. Specifies build order across eight commits, code organization within V2's existing storage stack, Pydantic model inventory, test fixture strategy, and resolutions for the open questions left in PRD section 10. |

---

## 1. Overview

This plan implements the catalog ingestion subsystem specified in `catalog-ingestion-PRD-v0.1.md` (v0.2). The build is single-pass with incremental commits, each landing a coherent slice. The catalog ingestion adds ~10 database tables, ~15 Pydantic models, ~10 REST endpoints, 4 MCP tools, and a one-time data migration loading 42 catalog entries (~5,700 rows total).

The order below is dictated by dependency: schema must exist before the loader can populate rows; the loader must exist before the data migration can call it; the access layer must exist before the API; the API must exist before the MCP tools; everything must exist before the acceptance test suite can run end-to-end.

This plan does not re-state PRD requirements — it specifies the build sequence and the implementation-level choices needed to execute the PRD.

---

## 2. Implementation Choices

### 2.1 Language and runtime

**Python 3.12+** — inherited from V2's existing `pyproject.toml` constraint. No additional version pin.

### 2.2 ORM / query layer — SQLAlchemy 2.0 (inherited)

The catalog tables follow V2's existing SQLAlchemy 2.0 Declarative pattern. New model classes go in `crmbuilder_v2/storage/models/catalog.py` (or whatever path V2's models live at — the implementation should match the existing convention). Each table specified in PRD section 4 becomes a Declarative class with `@validates()` decorators for controlled-vocabulary fields (`system`, `status`, `mechanism`, `data_model_role`).

### 2.3 Migration tool — Alembic (inherited)

Two new Alembic revisions:
- `000X_catalog_schema.py` — `op.create_table()` calls for the 10 catalog tables plus indexes
- `000Y_catalog_seed.py` — invokes the loader helper module to populate rows from YAMLs

Alembic revision numbering depends on the current state of `crmbuilder_v2/migrations/versions/`. The implementation should `alembic history` to find the latest revision and increment from there.

### 2.4 Web framework — FastAPI (inherited)

New router module at `crmbuilder_v2/api/routes/catalog.py`. Registered in the FastAPI app alongside existing routers. Routes follow the patterns defined in PRD section 6 with `/catalog/` prefix.

### 2.5 MCP framework — official `mcp` Python SDK (inherited)

Tool definitions at `crmbuilder_v2/mcp/tools/catalog.py`. The four read-only tools (`catalog_search`, `catalog_get_entity`, `catalog_get_cross_system_map`, `catalog_gap_check`) register with V2's existing MCP server alongside any existing tools.

### 2.6 YAML parsing — PyYAML

For the one-time data migration's YAML reading, **PyYAML 6.0+** is sufficient. Format preservation is not needed (we read once, populate DB, decommission files); the catalog YAMLs use only standard YAML features (mappings, sequences, multi-line strings with `>` folding). PyYAML's `safe_load` handles them cleanly.

ruamel.yaml was used during catalog authoring for format-preserving edits, but the loader doesn't need that capability. PyYAML keeps the dependency surface smaller.

### 2.7 JSON export — Python stdlib `json` (inherited)

V2's existing JSON export infrastructure handles writing the per-entity files. The catalog access layer calls into that infrastructure on writes; the format (sorted keys, 2-space indent) is enforced by V2's existing export utilities.

### 2.8 New dependencies

**None.** All capabilities are covered by V2's existing dependency set (SQLAlchemy, Alembic, FastAPI, Pydantic v2, PyYAML, `mcp` SDK).

---

## 3. Code Organization

The following file paths are based on the V2 convention as observed in the storage system. The implementation should confirm against V2's actual repository layout; if paths differ, mirror the actual convention rather than these defaults.

### New files

| Path | Purpose |
|---|---|
| `crmbuilder_v2/migrations/versions/000X_catalog_schema.py` | Alembic schema migration (10 tables) |
| `crmbuilder_v2/migrations/versions/000Y_catalog_seed.py` | Alembic data migration (invokes loader) |
| `crmbuilder_v2/migrations/helpers/catalog_loader.py` | YAML→DB loader helper (reusable; called from data migration and tests) |
| `crmbuilder_v2/storage/models/catalog.py` | SQLAlchemy 2.0 models for the 10 catalog tables |
| `crmbuilder_v2/storage/schemas/catalog.py` | Pydantic v2 request/response models |
| `crmbuilder_v2/storage/access/catalog/__init__.py` | Access layer package — re-exports read + write methods |
| `crmbuilder_v2/storage/access/catalog/read.py` | Access layer read methods (`list_entities`, `get_entity`, `search`, `cross_system_map`, `gap_check`) |
| `crmbuilder_v2/storage/access/catalog/write.py` | Access layer write methods (`create_entity`, `update_entity`, `delete_entity`, etc.) — fires JSON export hook on each call |
| `crmbuilder_v2/storage/access/catalog/exports.py` | JSON export integration; bulk regenerate function |
| `crmbuilder_v2/api/routes/catalog.py` | FastAPI router for `/catalog/` endpoints |
| `crmbuilder_v2/mcp/tools/catalog.py` | MCP tool registration |
| `tests/storage/test_catalog_schema.py` | Schema-presence tests |
| `tests/storage/test_catalog_loader.py` | Loader unit tests + idempotency |
| `tests/storage/test_catalog_access.py` | Access layer read + write tests |
| `tests/api/test_catalog_routes.py` | REST API integration tests |
| `tests/mcp/test_catalog_tools.py` | MCP tool integration tests |
| `tests/storage/test_catalog_exports.py` | JSON export hook tests |
| `tests/fixtures/catalog/*.yaml` | Sample catalog YAMLs for unit testing the loader (3-5 entities, not the full 42) |

### Modified files

| Path | Change |
|---|---|
| `crmbuilder_v2/api/main.py` (or equivalent) | Register the new `catalog` router |
| `crmbuilder_v2/mcp/server.py` (or equivalent) | Register the new catalog tools |
| `crmbuilder_v2/storage/access/__init__.py` | Re-export catalog access methods |
| Universal references controlled vocabulary config | Add `catalog_entity` and `catalog_attribute` as valid `target_type` values (location depends on V2's existing reference-vocabulary definition) |

### Decommissioned files

Removed via `git rm` in the data-migration commit:

- `PRDs/product/crmbuilder-v2/research/base-entity-catalog/` (entire directory, including `subclasses/`)
- `PRDs/product/crmbuilder-v2/research/base-entity-catalog-research.md`
- `PRDs/product/crmbuilder-v2/research/entity-system-map.yaml`

The `research/` directory continues to exist for future research deliverables.

---

## 4. Pydantic Model Inventory

V2 convention assumed: `<EntityName>Read`, `<EntityName>Create`, `<EntityName>Update`, `<EntityName>Patch`. If V2 uses a different naming convention, mirror it; otherwise use the names below.

### Read models (response shapes)

| Model | Purpose |
|---|---|
| `CatalogEntityRead` | Full nested entity for GET responses — includes attributes, systems, sources, synonyms, relationships |
| `CatalogEntitySummary` | Lightweight entity for list responses (no nested data) |
| `CatalogAttributeRead` | Full attribute for nested inclusion in entity reads — includes presence, enum values, synonyms |
| `CatalogPresenceRead` | Per-system presence cell (status + optional api_name) |
| `CatalogSystemRead` | Per-system entity mapping (name, api_name, is_standard, mechanism, docs_url) |
| `CatalogSourceRead` | Source citation (title, url) |
| `CatalogRelationshipRead` | Inter-entity relationship with per-system presence |
| `CatalogSearchHit` | Search result entry — entity or attribute hit with rank and context |
| `CatalogCrossSystemMap` | Cross-system map response — entity + all attributes mapped to specified system(s) |
| `CatalogGapCheckResult` | Gap check response — list of missing catalog attributes with cross-system counts |

### Write models (request shapes)

| Model | Purpose |
|---|---|
| `CatalogEntityCreate` | POST /catalog/entities body — full nested |
| `CatalogEntityUpdate` | PUT /catalog/entities/{id} body — full nested replace |
| `CatalogEntityPatch` | PATCH body — partial, entity-level fields only |
| `CatalogAttributeCreate` | POST /catalog/entities/{id}/attributes body |
| `CatalogAttributeUpdate` | PUT body — full nested replace including presence and synonyms |
| `CatalogAttributePatch` | PATCH body — partial |
| `CatalogGapCheckRequest` | POST /catalog/gap-check body |

### Shared / utility models

| Model | Purpose |
|---|---|
| `CatalogSynonymWrite` | Used in entity and attribute write payloads for inserting synonyms |
| `CatalogPresenceWrite` | Used in attribute write payloads — same shape as `CatalogPresenceRead` but no id |
| `CatalogEnumValueWrite` | Used in attribute write payloads for enum_values |

Total: ~17 Pydantic models. Slightly more than the rough estimate; covers reads, writes, and shared shapes cleanly.

---

## 5. Commit Sequence

Eight commits. Each lands a coherent slice; system is buildable but feature-incomplete until commit H.

### Commit A — Schema migration

- Alembic revision `000X_catalog_schema.py` creating the 10 tables, indexes, and check constraints per PRD section 4
- SQLAlchemy models in `crmbuilder_v2/storage/models/catalog.py`
- Schema-presence test at `tests/storage/test_catalog_schema.py` (verifies tables exist, columns match, constraints fire)
- No data; no API; no business logic

### Commit B — Loader helper module

- `crmbuilder_v2/migrations/helpers/catalog_loader.py` with `load_catalog(session, yaml_dir, suppress_exports=True)` function
- Three-pass loading logic (universals → subclasses → relationships)
- Upsert-by-catalog_id and upsert-by-(entity_id, name) semantics
- Validation step (parent FK resolution, status enum check, etc.)
- Unit tests in `tests/storage/test_catalog_loader.py` using sample YAMLs from `tests/fixtures/catalog/`
- Tests for: insert from empty, idempotent re-run, validation failures roll back, subclass FK resolution

### Commit C — Data migration + YAML decommissioning

- Alembic revision `000Y_catalog_seed.py` that calls `load_catalog()` against `PRDs/product/crmbuilder-v2/research/base-entity-catalog/`
- `git rm` of the catalog YAML directory and two cross-cutting deliverables in the same commit
- Integration test that runs the migration against an in-memory database and asserts row counts match the PRD's expected totals

### Commit D — Pydantic models

- All ~17 models in `crmbuilder_v2/storage/schemas/catalog.py`
- Pydantic-level validation (enum values, required fields, max lengths)
- Unit tests confirming round-trips work (Pydantic ↔ SQLAlchemy ↔ JSON)

### Commit E — Access layer read methods + REST read endpoints

- `crmbuilder_v2/storage/access/catalog/read.py` with the read methods listed in section 3
- `crmbuilder_v2/api/routes/catalog.py` with the six read endpoints (GET endpoints + the POST gap-check) per PRD section 6
- Tests at `tests/api/test_catalog_routes.py` covering each endpoint against the migrated database
- Query parameter handling (filters, search ranking, include_deleted)

### Commit F — Access layer write methods + REST write endpoints

- `crmbuilder_v2/storage/access/catalog/write.py` with create/update/delete methods for entities and attributes
- Soft-delete pattern (`is_deleted` flag) matches V2's existing convention
- Entity-level write granularity: nested sub-row data flows through the parent payload
- Sub-row replacement strategy: delete + reinsert per parent on write
- Write endpoints in the same router (POST, PUT, PATCH, DELETE)
- Tests covering create, update, patch, delete, soft-delete behavior, and validation failures

### Commit G — MCP tools

- `crmbuilder_v2/mcp/tools/catalog.py` with the four read-only tools per PRD section 6
- Tools wrap access layer read methods directly (no logic at the MCP layer)
- Tests at `tests/mcp/test_catalog_tools.py` covering input schemas, output schemas, and behavior against the migrated database

### Commit H — JSON export hook integration + bulk regenerate + universal references integration

- `crmbuilder_v2/storage/access/catalog/exports.py` with per-entity export function and `regenerate_all_catalog_exports()` for the post-migration bulk run
- Access layer write methods fire the export hook on every entity-level write
- Suppression flag honored during the data migration
- Bulk regenerate invocation added to the data migration's post-load step
- Universal references controlled-vocabulary updated to include `catalog_entity` and `catalog_attribute` as `target_type` values
- Inbound references appear on read responses
- Tests at `tests/storage/test_catalog_exports.py` covering JSON file shape, sorted keys, suppression behavior, and bulk regenerate

After commit H, all PRD section 8 acceptance criteria are met. Acceptance test runs end-to-end.

---

## 6. Test Fixture Strategy

### Sample catalog YAMLs

Stored at `tests/fixtures/catalog/`. Subset of the full 42-entry catalog, sized for fast test execution:

- 3 universal entities covering different tiers (e.g., `account.yaml` from T1, `donation.yaml` from T4, `document.yaml` from T5)
- 2 subclass entities (e.g., `account-nonprofit.yaml`, `donation-major-gift.yaml`) — exercises subclass FK resolution
- Each fixture includes a representative mix of attribute types, presence statuses, enum values, synonyms, and at least one relationship

Total fixture rows: ~30 attributes, ~210 presence cells. Loader runs against fixtures finish in milliseconds.

### Database fixtures

- In-memory SQLite (`sqlite:///:memory:`) for unit tests — fast, isolated per test function
- Per-class fixture that creates schema and loads sample catalog once, reused across test methods
- Pytest fixture in `tests/conftest.py` providing a fresh session per test

### Mocked external integrations

- JSON export hook tests use a real temporary directory (via `tmp_path` fixture) to verify file shape; production tests use a mock to assert the hook was called the right number of times without doing actual I/O
- MCP server tests bypass the real MCP transport and call tools directly via the Python API

### Integration test using the real catalog

One integration test runs the full data migration against the real 42-entry catalog (against an in-memory database for speed) and asserts:

- 42 catalog_entity rows
- 415 catalog_attribute rows (post-v0.10 fix)
- 2,905 catalog_attribute_presence rows
- All subclass parent_entity_ids resolved
- All catalog_relationship rows have both source_entity_id and target_entity_id resolved
- No validation failures

This is the "full ingestion" test that mirrors PRD section 8's primary acceptance criterion.

---

## 7. Acceptance Criteria → Test File Mapping

PRD section 8 specifies 11 acceptance criteria. Each maps to one or more tests:

| Criterion | Test file(s) |
|---|---|
| 1. Schema present | `tests/storage/test_catalog_schema.py::test_all_tables_exist`, `test_column_types`, `test_check_constraints_enforce` |
| 2. Catalog populated | `tests/storage/test_catalog_loader.py::test_full_migration_row_counts`, `test_full_migration_fidelity` |
| 3. Subclass parents resolved | `tests/storage/test_catalog_loader.py::test_subclass_parent_resolution` |
| 4. api_name coverage | `tests/storage/test_catalog_loader.py::test_presence_status_api_name_correlation` |
| 5. Idempotency | `tests/storage/test_catalog_loader.py::test_idempotent_rerun` |
| 6. REST API contract | `tests/api/test_catalog_routes.py` (all test functions) |
| 7. MCP tool contract | `tests/mcp/test_catalog_tools.py` (all test functions) |
| 8. JSON exports written | `tests/storage/test_catalog_exports.py::test_bulk_regenerate_writes_42_files`, `test_json_shape_deterministic` |
| 9. Universal references | `tests/storage/test_catalog_access.py::test_catalog_as_reference_target`, `test_inbound_references_in_read_response` |
| 10. YAMLs decommissioned | Manual verification via `git ls-files PRDs/product/crmbuilder-v2/research/base-entity-catalog/` returning empty in CI |
| 11. Full acceptance suite passes | `pytest tests/storage/test_catalog_* tests/api/test_catalog_* tests/mcp/test_catalog_*` exits zero |

---

## 8. Resolved Open Questions

PRD section 10 left five implementation-level questions open. Resolutions:

| Question | Resolution |
|---|---|
| Alembic revision number prefixes | Determined at build time via `alembic history`. The two new revisions increment from the latest revision in `crmbuilder_v2/migrations/versions/`. The implementation does not hard-code revision numbers; they're whatever Alembic generates. |
| Catalog access layer one module or split | **Split into a package** `crmbuilder_v2/storage/access/catalog/` with `read.py`, `write.py`, `exports.py`, and `__init__.py` re-exporting the public API. Matches V2's existing pattern for moderate-complexity subsystems. |
| JSON export directory location | Default to `{V2_data_root}/exports/catalog/entities/{catalog_id}.json` following V2's existing pattern. If V2's actual export path differs, mirror the actual convention. The implementation should confirm against V2's existing export infrastructure. |
| Pydantic model naming convention | `CatalogEntityRead` / `CatalogEntityCreate` / `CatalogEntityUpdate` / `CatalogEntityPatch` family — assumes V2's convention. If V2 uses different suffixes (e.g., `In` / `Out` / `Patch`), mirror them. |
| Test fixture strategy | In-memory SQLite + sample YAMLs in `tests/fixtures/catalog/`, full-catalog integration test against real YAMLs. Documented in section 6 above. |

---

## 9. Build Validation Gate

After all eight commits land, run the following sequence to validate:

```bash
# 1. Schema and migration
alembic upgrade head
# Expect: no errors; both catalog_schema and catalog_seed revisions applied

# 2. Row counts
sqlite3 v2.db "SELECT COUNT(*) FROM catalog_entity"
# Expect: 42
sqlite3 v2.db "SELECT COUNT(*) FROM catalog_attribute"
# Expect: 415
sqlite3 v2.db "SELECT COUNT(*) FROM catalog_attribute_presence"
# Expect: 2,905

# 3. JSON exports
ls {V2_data_root}/exports/catalog/entities/ | wc -l
# Expect: 42

# 4. Acceptance test suite
pytest tests/storage/test_catalog_* tests/api/test_catalog_* tests/mcp/test_catalog_* -v
# Expect: all pass

# 5. Decommissioned YAMLs gone
test ! -d PRDs/product/crmbuilder-v2/research/base-entity-catalog/
echo "Exit code: $?"
# Expect: 0 (directory does not exist)

# 6. REST smoke test
curl -s http://localhost:8000/catalog/entities | jq '.[] | .catalog_id' | wc -l
# Expect: 42

# 7. MCP smoke test (run via V2's MCP harness)
mcp-test catalog_search '{"query": "donation"}'
# Expect: hits including donation, donation-major-gift, recurring-gift, etc.
```

If all seven validation steps pass, the build is complete and matches the PRD's "functioning" definition.

---

## 10. Out of Scope for This Build

Repeats PRD section 9 for visibility. Additionally, this implementation plan does not cover:

- **Catalog editing UI in V2** — REST endpoints exist; the UI that consumes them is a separate workstream paralleling the existing decisions / planning-items UI
- **Performance tuning** — at the catalog's scale (5,700 rows), no performance work is needed for v0.1. Indexes specified in PRD section 4 are sufficient
- **Fresh-install reseed flow** — once YAMLs are decommissioned from the working tree, re-seeding a fresh V2 install requires either git-history recovery of the YAMLs or future productization work to package seed data
- **Multi-version catalog support** — V2 carries one catalog at a time. Versioning is via standard audit columns
- **Cross-catalog merge / import** — third-party catalog imports are not supported

---

# CLAUDE-CODE-PROMPT: Delete Path A `automation/cbm_import/`

**Repo:** `dbower44022/crmbuilder`
**Date:** 04-15-26
**Goal:** All four Path A parsers have been migrated to Path B adapters. Delete the entire `automation/cbm_import/` directory and clean up test files that exclusively test Path A code.

## Context

Read `CLAUDE.md` at the repo root before starting.

The Path A → Path B migration is complete:

| Parser | Path A (tombstoned) | Path B (active) |
|---|---|---|
| Master PRD | `cbm_import/parsers/master_prd.py` | `importer/parsers/master_prd_docx.py` |
| Process Doc | `cbm_import/parsers/process_document.py` | `importer/parsers/process_doc_docx.py` |
| Entity PRD | `cbm_import/parsers/entity_prd.py` | `importer/parsers/entity_prd_docx.py` |
| Entity Inventory | `cbm_import/parsers/entity_inventory.py` | `importer/parsers/entity_inventory_docx.py` |
| Domain PRD | `cbm_import/parsers/domain_prd.py` | `importer/parsers/domain_prd_docx.py` |

All five Path A parsers are now tombstoned with `NotImplementedError`. No code outside of `automation/cbm_import/` and its dedicated test files should depend on live functionality from this directory.

## Deliverables

### 1. Delete `automation/cbm_import/`

Delete the entire directory tree:

```
automation/cbm_import/
├── __init__.py
├── __main__.py
├── cli.py
├── importer.py
├── parser_logic.py
├── docx_parser.py
├── reporter.py
└── parsers/
    ├── __init__.py
    ├── master_prd.py        (tombstoned)
    ├── entity_inventory.py  (tombstoned)
    ├── entity_prd.py        (tombstoned)
    ├── process_document.py  (tombstoned)
    └── domain_prd.py        (tombstoned)
```

### 2. Delete or archive test files that exclusively test Path A

**Delete these files entirely:**

- `automation/tests/test_cbm_importer.py` — unit tests for `parser_logic` functions and individual Path A parsers. All functionality has been re-implemented in Path B adapters.

**Delete these integration test files:**

- `automation/tests/integration/test_cbm_importer.py` — integration tests that run `CBMImporter` against fixture subset.
- `automation/tests/integration/conftest.py` — session-scoped fixtures that import `CBMImporter`.

**Check if `automation/tests/integration/` directory is now empty** after deleting the above files. If so, delete the directory itself.

### 3. Verify no remaining imports

Search the entire repo for any remaining imports from `automation.cbm_import`. Expected results:

- **Documentation/prompt files** (`.md`) — these are historical references, leave as-is
- **No `.py` files** should import from `automation.cbm_import` after the deletions

If any `.py` file still imports from `automation.cbm_import`, investigate:
- If it's a test file that exclusively tests Path A, delete it
- If it's production code, it's a missed dependency — flag it and do NOT delete `cbm_import` until resolved

### 4. Verify no test regressions

Existing Path B tests must continue to pass. The Path B test files are:

- `automation/tests/test_importer_parsers_master_prd_docx.py`
- `automation/tests/test_importer_parsers_process_doc_docx.py`
- `automation/tests/test_importer_parsers_entity_prd_docx.py`
- `automation/tests/test_importer_parsers_entity_inventory_docx.py`
- `automation/tests/test_importer_parsers_domain_prd_docx.py`

These should NOT import anything from `automation.cbm_import` — they import from `automation.importer.parsers`.

## Verification Steps

1. `uv run ruff check automation/` — clean (no import errors).
2. `uv run pytest automation/tests/ -v` — no regressions. Path B adapter tests all pass. No collection errors from missing `cbm_import` imports.
3. Confirm `automation/cbm_import/` no longer exists.
4. Confirm no `.py` files in the repo import from `automation.cbm_import`.

## Reporting

Return a plain-text summary covering:
- Files deleted (count and list)
- Any remaining references to `automation.cbm_import` found (should be docs only)
- Test suite counts (total / passed / skipped / failed)
- Ruff status

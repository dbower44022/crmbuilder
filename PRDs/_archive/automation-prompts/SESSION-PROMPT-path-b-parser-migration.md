# Session Prompt — Migrate Remaining Path A Parsers to Path B

**Repo:** `dbower44022/crmbuilder`
**Date:** 04-10-26
**Prerequisite:** Read `CLAUDE.md` in both `crmbuilder` and `ClevelandBusinessMentoring` repos.

---

## Context

On 04-10-26 we completed the migration of the Master PRD parser from Path A
(`automation/cbm_import/`) to Path B (`automation/importer/`). The work
included:

1. **Path B mapper fix** — `automation/importer/mappers/master_prd.py` now
   honors `is_service` from payload (commit `6400ec1`).
2. **CBM Master PRD v2.6** — added `MST-SVC-NNN` service codes to headings
   (commit `7ee9946` in `ClevelandBusinessMentoring`).
3. **New adapter** — `automation/importer/parsers/master_prd_docx.py` turns
   `.docx` → Path B envelope JSON. Supporting infrastructure in
   `automation/importer/parsers/__init__.py` (`ParseWarning`, `ParseReport`,
   `MasterPrdParseError`). 26 tests in
   `automation/tests/test_importer_parsers_master_prd_docx.py`. All pass.
4. **Path A tombstoned** — `automation/cbm_import/parsers/master_prd.py`
   raises `NotImplementedError`; `importer.py` catches it in `import_all()`.
5. **Test fixture** — `automation/tests/fixtures/cbm-master-prd-v2.6.docx`
   (commit `cb6ff20`).
6. **CBM database rebuilt** — fresh import through Path B adapter + legacy
   Phase 2–5. Result: 12 Domain rows (4 top-level + 4 sub-domains + 4
   services), 13 Personas, 15 Processes from Master PRD, 12 Entities,
   148 Fields, 111 FieldOptions, 24 BusinessObjects, 36 Decisions.
7. **Data Browser verified** — sub-domains render correctly in the tree when
   correct data is present.

---

## Known Legacy Parser Bugs (Path A)

These were discovered during the 04-10-26 session:

### Bug 4 — Process document parser: bad domain_code extraction
**File:** `automation/cbm_import/parsers/process_document.py` line 50
**Problem:** Stores the full header value `"Client Recruiting (CR)"` as
`domain_code` instead of extracting just `"CR"` from the parens.
**Impact:** Any process whose Process record doesn't already exist in the
database fails with "Could not resolve domain" because the lookup does
`Domain.code = "Client Recruiting (CR)"` which matches nothing.
**Note:** MN/MR processes didn't hit this because the Path B master PRD
import pre-created their Process records; the legacy importer found them by
code and just updated them without needing domain resolution.

### Bug 5 — Process document parser: no sub-domain assignment
**Problem:** Even with a clean domain code, the parser has no logic to assign
a sub-domain-level process (e.g., CR-PARTNER-MANAGE) to its sub-domain
Domain record (CR-PARTNER, id=5) rather than the parent domain (CR, id=4).
The document header says `Domain: Client Recruiting (CR)` — there's no
sub-domain field.
**Workaround used:** Manually pre-created Process records with correct
`domain_id` pointing to CR-PARTNER, then re-ran import to populate
steps/requirements.

### Bug 6 — Entity PRD parser: primary_domain_id never set
**File:** `automation/cbm_import/parsers/entity_prd.py`
**Problem:** All 12 imported entities have `primary_domain_id = NULL`.
Entities don't appear under any domain in the Data Browser tree.

### Bug 7 — Entity inventory parser: untested against new schema
**File:** `automation/cbm_import/parsers/entity_inventory.py`
**Status:** Unknown — not exercised during the rebuild session.

### Bug 8 — Domain PRD parser: untested against new schema
**File:** `automation/cbm_import/parsers/domain_prd.py`
**Status:** Unknown — not exercised during the rebuild session.

---

## Migration Plan

Migrate all four remaining Path A parsers to Path B using the same proven
pattern:

1. Inspect the source `.docx` structure for each document type
2. Inspect the corresponding Path B mapper in `automation/importer/mappers/`
   to understand the expected payload shape
3. Design the adapter (one decision at a time, confirm each)
4. Write a `CLAUDE-CODE-PROMPT-*.md` for Claude Code to implement
5. Test and verify against the real CBM documents
6. Tombstone the legacy parser with `NotImplementedError`

**Priority order:**

| Priority | Parser | Why |
|---|---|---|
| 1 | Process document | Fixes bugs 4+5, unblocks all future process imports including CR sub-domain processes |
| 2 | Entity PRD | Fixes bug 6, makes entities appear under domains in Data Browser |
| 3 | Entity inventory | Completeness |
| 4 | Domain PRD | Completeness |

When all four are migrated, delete `automation/cbm_import/` entirely.

---

## Established Infrastructure

The following infrastructure from the master PRD migration is reusable:

- **`automation/importer/parsers/__init__.py`** — `ParseWarning`,
  `ParseReport`, `MasterPrdParseError` (may need a generic
  `DocxParseError` base or per-parser error classes)
- **Envelope contract** — `{output_version, work_item_type, work_item_id,
  session_type, payload, decisions, open_issues}`
- **Pipeline wiring** — adapter produces envelope JSON string, feeds
  existing `ImportProcessor.run_full_import()` unchanged
- **Test pattern** — real-document tests + synthetic hard-failure tests +
  soft-warning tests + round-trip validation tests
- **Path A guard pattern** — replace parser body with `NotImplementedError`,
  guard `importer.py` entry points, skip legacy tests

---

## CBM File Locations

Doug's local clone of the CBM repo is at
`~/Dropbox/Projects/ClevelandBusinessMentors/`. This is the single
source of truth for CBM documents on his machine. Note the short name
(`Mentors`, not `Mentoring`) — the GitHub repo is named
`dbower44022/ClevelandBusinessMentoring`, but the local directory uses
the short form. A previous session incorrectly claimed two separate
directories existed (`ClevelandBusinessMentoring` and
`ClevelandBusinessMentors`); the long-named stale clone was deleted on
04-10-26 after it was discovered to be 42 commits behind and sparse-
checkout incomplete. Only the short-named directory exists now.

---

## Current Database State

After the 04-10-26 session, `automation/data/cbm-client.db` contains:

| Table | Count | Notes |
|---|---|---|
| Domain | 12 | 4 top-level + 4 sub-domains (CR) + 4 services |
| Persona | 13 | All from Path B master PRD import |
| Process | 17 | 15 from master PRD + 2 manually created (CR-PARTNER-MANAGE, CR-PARTNER-PROSPECT) |
| ProcessStep | 175 | 125 from initial import + 50 from CR-PARTNER re-import |
| Requirement | 110 | 92 from initial + 18 from CR-PARTNER re-import |
| Entity | 12 | All with primary_domain_id = NULL (bug 6) |
| Field | 148 | |
| FieldOption | 111 | |
| Relationship | 24 | 7 skipped (target entities not yet defined) |
| BusinessObject | 24 | |
| Decision | 36 | |

---

## Starting Point

Begin with Priority 1: **Process document parser migration**. Steps:

1. Read `CLAUDE.md` in both repos
2. Inspect `automation/cbm_import/parsers/process_document.py` (323 lines) —
   understand what it extracts
3. Inspect `automation/importer/mappers/process_definition.py` — understand
   the expected payload shape
4. Inspect a real process document (e.g., `PRDs/MN/MN-INTAKE.docx` and
   `PRDs/CR/PARTNER/CR-PARTNER-MANAGE.docx`) to understand the source
   structure and how sub-domain processes differ from top-level processes
5. Design the adapter one decision at a time
6. Author `CLAUDE-CODE-PROMPT-process-doc-adapter.md` in
   `PRDs/product/crmbuilder-automation-PRD/`

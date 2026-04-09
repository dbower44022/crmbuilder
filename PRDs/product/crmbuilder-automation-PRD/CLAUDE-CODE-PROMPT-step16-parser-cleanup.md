# Claude Code Follow-Up — Step 16 Parser Cleanup

## Context

Step 16 (CBM bootstrap importer) is committed and all 1067 tests pass. Doug ran a dry-run of the importer against the full CBM repository:

```
DRY RUN: Importing CBM PRDs...
=== CBM Import Report ===
Parsed:   634 records
Imported: 0 records
Skipped:  0 records
Warnings: 0
Errors:   0
Parsed by table:
  BusinessObject: 82 parsed
  Decision: 36 parsed
  Domain: 4 parsed
  Entity: 36 parsed
  Field: 245 parsed
  FieldOption: 111 parsed
  Persona: 13 parsed
  Process: 29 parsed
  ProcessStep: 46 parsed
  Relationship: 31 parsed
  Requirement: 1 parsed
```

Several counts are off relative to the real CBM repository. Review identified four concrete bugs in the parsers. All four must be fixed before the real (non-dry-run) import can proceed.

This is a **small, targeted follow-up**. Four bugs, four separate commits so they can be reviewed independently. All fixes are localized to `automation/cbm_import/parsers/` and `automation/cbm_import/parser_logic.py` — no changes to the importer orchestration, the database layer, the workflow engine, or the UI.

The CBM repository lives at `dbower44022/ClevelandBusinessMentoring`. Your development environment may or may not have it cloned. If it's not already available, Doug can share individual sample documents; otherwise use the CBM repo as a real-world verification source. Doug's local path is `/home/doug/Dropbox/Projects/ClevelandBusinessMentoring`.

**Before touching code**, read three sample CBM documents to understand the real structure:

- `PRDs/MN/MN-INTAKE.docx` — a standard process document (for Bug #1 and Bug #2)
- `PRDs/CBM-Entity-Inventory.docx` — the entity inventory document (for Bug #3)
- `PRDs/CBM-Master-PRD.docx` — the master PRD (for Bug #4)

## Bug #1 — Requirements are stored in tables, not paragraph text

### Problem

`automation/cbm_import/parsers/process_document.py` calls `parse_requirement_list()` from `parser_logic.py` on the paragraphs following the "System Requirements" heading. In real CBM documents, requirements are stored in a **two-column table** immediately after the heading:

```
| ID                 | Requirement                                          |
|--------------------|------------------------------------------------------|
| MN-INTAKE-REQ-001  | The system must accept client mentoring requests... |
| MN-INTAKE-REQ-002  | The submitting individual must be automatically...  |
| ...                | ...                                                  |
```

Each table has a header row followed by N requirement rows. The first cell is the identifier (format: `{DOMAIN}-{PROCESS}-REQ-NNN`, e.g., `MN-INTAKE-REQ-001`), the second cell is the description.

The paragraph-based parser finds nothing in these tables. The fallback `_extract_requirements_from_text()` uses a regex requiring `identifier: description` inline, which does not match any real CBM format. **Result: Requirement: 1** in the dry-run, where the real count should be ~130+ across all processes (each process has roughly 10-15 requirements).

Verify by opening any process .docx in python-docx and iterating `document.tables`. You will find a table whose header row is `['ID', 'Requirement']` (or equivalent) followed by rows with requirement identifiers.

### Fix

Modify `automation/cbm_import/parsers/process_document.py` to parse the requirements **table** instead of the requirements section paragraphs. The approach:

1. After extracting tables from the document (already done at line 35 via `extract_tables(doc)`), scan for the requirements table by looking for a header row where the first cell is `ID` (case-insensitive) and the second cell starts with `Requirement`.
2. For each data row in the matched table: extract the identifier from column 0 and the description from column 1. Skip empty rows.
3. Create requirement dicts with `identifier`, `description`, and `priority="must"` (the default from the existing code).
4. Record `report.record_parsed("Requirement", len(reqs))` once with the total.

Keep the existing section-heading detection for backward compatibility — if the table-based approach finds nothing, fall back to the paragraph-based parser. But the table-based approach should be tried **first**.

The existing `_extract_requirements_from_text()` fallback can be removed or kept. Your call. If you keep it, the order becomes: table → section paragraphs → inline text regex.

### Test

Add a test to `automation/tests/test_cbm_importer.py` that:

1. Constructs a minimal .docx file with a System Requirements section containing a two-column table with header `['ID', 'Requirement']` and 3 data rows
2. Passes it through the process document parser
3. Asserts the parser extracted 3 Requirement records with the correct identifiers and descriptions

Update the existing MN-INTAKE fixture at `automation/tests/fixtures/cbm_subset/MN/MN-INTAKE.docx` to include a requirements table if it doesn't already. Update the `create_fixtures.py` script accordingly. The integration test `test_cbm_importer.py::test_requirements_extracted` (or similar) should assert non-zero requirement count.

### Verify against real data

Before committing, run a dry-run against the full CBM repo and check the Requirement count in the report:

```bash
python -m automation.cbm_import \
    --cbm-repo /home/doug/Dropbox/Projects/ClevelandBusinessMentoring \
    --client-db /tmp/verify-cbm.db \
    --master-db /tmp/verify-master.db \
    --dry-run
```

Expected: **Requirement: ~130** (actual number will depend on how many requirements are in the CBM documents Doug has currently; anything in the range 80-200 is sensible; 1 is not).

### Commit 1 message

```
Fix CBM importer requirements parser to read ID/Requirement tables

Real CBM process documents store requirements in a two-column table
after the System Requirements heading, with header row ['ID',
'Requirement'] followed by N requirement rows. The existing parser
scanned paragraphs and found nothing in these tables.

Replace paragraph-based requirements extraction with a table-based
approach. Scan document tables for the ID/Requirement header pattern,
extract identifiers from column 0 and descriptions from column 1.

Before: Requirement: 1 parsed across all CBM processes.
After: Requirement: ~130 parsed.
```

## Bug #2 — Workflow steps are List Paragraph items without numeric prefixes

### Problem

`process_document.py:_extract_steps()` uses regex `^(?:Step\s+)?(\d+)[.):]\s*(.+)` to match numbered workflow steps. In real CBM process documents, workflow steps are Word "List Paragraph" style items where the number (1., 2., 3., ...) is rendered by Word's list numbering system and is **not stored in the paragraph text that python-docx returns**.

You can verify this by opening a process document and iterating paragraphs with their style:

```python
from docx import Document
d = Document('PRDs/MN/MN-INTAKE.docx')
for p in d.paragraphs:
    if p.style.name == 'List Paragraph':
        print(repr(p.text[:50]))
```

The output shows text like `'The prospective client completes and submits...'` — no `'1. '` prefix. The regex fails to match, so `_extract_steps()` falls through to its "continuation of previous step" branch which can never activate because no first step ever matches. Net effect: most processes produce zero ProcessStep records. The **ProcessStep: 46** count in the dry-run comes from a handful of processes that happen to have literal `"1."` or `"2."` in paragraph text (non-list-style numbering), plus fragments caught by the continuation branch.

### Fix

Rewrite `_extract_steps()` to handle List Paragraph style items. Two reasonable approaches — **pick whichever is simpler for you**:

**Option A — Inspect the underlying XML.** python-docx exposes each paragraph's XML via `paragraph._element` or `paragraph._p`. Numbered list paragraphs have a `<w:numPr>` child that references the numbering definition. You can inspect this to identify list items and optionally extract the rendered number. This is more precise but requires XML walking.

**Option B — Use style name plus positional ordering.** Scan paragraphs after the "Process Workflow" heading. Any paragraph with `style.name == 'List Paragraph'` (or similar — check what the CBM documents use) is a step. Assign sort_order by position in the sequence (first matching paragraph = 1, second = 2, etc.). Reset the counter if you encounter a non-list paragraph that clearly ends the workflow section. Stop at the next top-level section heading.

Option B is simpler and probably sufficient for CBM since step **ordering** is what matters, not the displayed number. Option A is more robust against mixed content. Both are acceptable — **your choice**, just document which in the commit message.

Additional considerations:

1. **Continuation text under a step.** Some workflow steps in CBM have sub-bullets or continuation paragraphs (also List Paragraph style but at a deeper indentation level). These should be appended to the description of the previous top-level step, not create new steps. The existing code attempts this on line 149-151 but may need adjusting for the new matching approach.

2. **Section boundary.** The existing code breaks on top-level section headings via the regex at line 133-138. That logic is still correct — keep it.

3. **Empty workflow section handling.** If no steps are found, still return an empty list (don't crash).

### Test

Add tests to `automation/tests/test_cbm_importer.py`:

1. Construct a minimal .docx with a Process Workflow section containing 5 List Paragraph items (use `python-docx`'s `add_paragraph(text, style='List Paragraph')` or equivalent)
2. Parse it through the process document parser
3. Assert 5 ProcessStep records are extracted with correct sort_order values

Update the MN-INTAKE fixture to use real List Paragraph style for its workflow steps. The existing fixture may be using a format that accidentally matches the old regex, so after this fix the fixture may need restructuring to match real CBM structure.

### Verify against real data

Dry-run against full CBM. Expected: **ProcessStep: ~150-250** (each of ~13-15 processes has 5-15 steps; sub-steps may or may not be counted separately depending on how you handle continuation).

### Commit 2 message

```
Fix CBM importer workflow step extraction for List Paragraph styles

Real CBM process documents store workflow steps as Word "List Paragraph"
style items where the number prefix is managed by Word's numbering
engine, not stored in the paragraph text. The existing regex-based
extractor never matched these paragraphs.

Replace regex-based step extraction with [approach-you-chose: XML
inspection / style-name detection]. Workflow steps are now identified
by their paragraph style and sort_order is assigned by position in the
section.

Before: ProcessStep: 46 parsed across all CBM processes.
After: ProcessStep: ~200 parsed.
```

## Bug #3 — Entity Inventory parser scrapes metadata and detail tables as business objects

### Problem

`automation/cbm_import/parsers/entity_inventory.py:parse()` iterates **every table** in `CBM-Entity-Inventory.docx` (line 37: `for table in tables:`). The real document has 12 tables:

- **Table 0** — document metadata header (6 rows: Document Type, Version, Status, etc.)
- **Table 1** — the actual entity inventory (28 rows × 7 columns: `PRD Entity Name | CRM Entity | Native/Custom | Entity Type | Discriminator | Disc. Value | Domain(s)`)
- **Tables 2-11** — per-entity detail tables (5 rows each with Entity Type info)

The parser treats every row of every table as a business object, producing **82 BusinessObjects** (28 real + 54 junk) and **36 Entities** (unique entity names scraped from metadata and detail tables). The real numbers should be **28 BusinessObjects** and **~16 Entities** (per the inventory document's own summary: "16 CRM Entities (2 native, 11 custom, 3 TBD), 28 Business Entity Concepts").

### Fix

Modify `automation/cbm_import/parsers/entity_inventory.py` to **identify and parse only the real inventory table**, not all tables in the document.

Approach: scan tables for one whose header row contains columns that look like the inventory structure. A reliable heuristic: the inventory table has a header row containing both `"PRD Entity Name"` (or similar — check the actual header text via python-docx) and `"CRM Entity"` (or `"Native / Custom"`, `"Entity Type"`). Match by column count (7) and by header cell text (case-insensitive, stripped).

Pseudocode:

```python
def _find_inventory_table(tables):
    for table in tables:
        if not table or len(table) < 2:
            continue
        header = [c.strip().lower() for c in table[0]]
        # Inventory table has a "crm entity" or "entity name" column
        # and a "native / custom" column in the header
        has_entity_col = any("entity" in h for h in header)
        has_native_col = any("native" in h for h in header)
        if has_entity_col and has_native_col and len(header) >= 5:
            return table
    return None
```

Then iterate only the data rows of that single table. All other tables in the document are ignored.

If the inventory table cannot be found, add a warning to the ImportReport and return empty lists rather than silently scraping every table.

### Test

Add a test to `automation/tests/test_cbm_importer.py`:

1. Construct a .docx with multiple tables — one that looks like the real inventory header, plus 2-3 decoy tables with other headers
2. Parse through the entity inventory parser
3. Assert only the real inventory table's rows were parsed (other tables ignored)

Update the fixture at `automation/tests/fixtures/cbm_subset/CBM-Entity-Inventory.docx` to include at least one decoy table so the test catches regression.

### Verify against real data

Dry-run against full CBM. Expected: **BusinessObject: 28** (or very close — depends on how many rows the current CBM document has in its inventory table) and **Entity: ~16** (unique entity names from the inventory table only).

### Commit 3 message

```
Fix CBM Entity Inventory parser to target only the inventory table

CBM-Entity-Inventory.docx contains 12 tables: a metadata header table,
the real inventory table, and 10 per-entity detail tables. The existing
parser iterated all 12 tables and treated every row as a BusinessObject
candidate, inflating counts with metadata and detail table junk.

Replace the "iterate all tables" loop with an inventory-table detector
that matches on header cell content (requires both "entity" and
"native" header columns). Other tables in the document are ignored.
Warning emitted if the inventory table cannot be found.

Before: BusinessObject: 82, Entity: 36 parsed.
After: BusinessObject: 28, Entity: ~16 parsed.
```

## Bug #4 — Process count is inflated by double-counting

### Problem

`record_parsed("Process", ...)` is called in two places:

- `automation/cbm_import/parsers/master_prd.py:70` — adds N where N is the number of processes listed in the Master PRD's process inventory section
- `automation/cbm_import/parsers/process_document.py:121` — adds 1 per individual process document parsed

This inflates the parse count. If the Master PRD has 15 processes in its inventory and there are 14 process .docx files, the report shows 29.

The issue is **only about the reported parse count** — the report's total doesn't reflect the number of unique processes. At **write time**, the CBMImporter may or may not dedupe; per Doug's instructions for this follow-up, verification of the write-time behavior is skipped in favor of adding an explicit dedupe step.

### Fix

Two-part fix:

**Part A — Remove the Master PRD parser's Process count.**

Modify `automation/cbm_import/parsers/master_prd.py` line 70 to NOT call `record_parsed("Process", ...)`. The Master PRD scan still extracts the process inventory data (it's used for the domain graph), but the count is not added to the report.

The authoritative Process count comes from individual process documents being parsed. The Master PRD's role is to provide the inventory metadata (domain associations, expected process codes), not to create Process records.

**Part B — Deduplicate at import time.**

In `automation/cbm_import/importer.py`, ensure that when the importer writes Process records to the database, it deduplicates by `code`. If a Process with the same code has already been written (e.g., from a prior call or from the Master PRD's inventory step if your importer still uses that data), the subsequent write should be a no-op (or an update that enriches the existing record with data from the detail document).

The simplest implementation: before each Process insert, run `SELECT id FROM Process WHERE code = ?` — if a row exists, skip the insert (or update specific columns like `name`, `description`, `triggers` with the more detailed data from the individual process document).

Make the same deduplication protection explicit for Entity writes, since Bug #3 also raised concerns there: if the Entity Inventory parser found an entity and the Entity PRD parser later finds the same entity, only insert once. This may already be happening implicitly through the current code, but make it explicit so there's no ambiguity.

### Test

Add a test to `automation/tests/test_cbm_importer.py`:

1. Mock or construct a scenario where the Master PRD parser yields a Process with code `MN-INTAKE` and the process document parser also yields a Process with code `MN-INTAKE`
2. Run the full import
3. Assert exactly one Process record with code `MN-INTAKE` exists in the database

### Verify against real data

Dry-run against full CBM. Expected: **Process: ~14-15** (matching the actual count of process .docx files in the CBM repo, which per memory item 4 is: MN has 5, MR has 5, CR has ~2, FU not started, plus services).

### Commit 4 message

```
Dedupe Process and Entity writes at import time; remove double-counting

The CBM import was double-counting Process records: master_prd.py
recorded the inventory count AND process_document.py recorded 1 per
individual process. The count is now authoritative from individual
process documents only.

Add explicit deduplication at import write time for Process and Entity
records. If a Process or Entity with a matching code already exists in
the database, the subsequent write updates the existing record rather
than creating a duplicate.

Before: Process: 29 parsed (inflated by master_prd inventory count).
After: Process: ~14 parsed.
```

## What I Want From You

### 1. Verify against a real CBM document before changing code

If the CBM repository is available in your environment, open `PRDs/MN/MN-INTAKE.docx` in python-docx and inspect:

- The requirements table (Bug #1) — confirm the header row is `['ID', 'Requirement']`
- The workflow steps (Bug #2) — confirm the style name (likely `'List Paragraph'`) and confirm python-docx returns the text without numeric prefixes
- The entity inventory tables (Bug #3) — open `PRDs/CBM-Entity-Inventory.docx` and confirm the table structure

If the repo is not available, ask Doug for samples via a comment in the conversation.

### 2. Apply the fixes in order

Commit 1 (requirements), Commit 2 (workflow steps), Commit 3 (entity inventory), Commit 4 (process dedupe). Four separate commits. Each independently reviewable.

### 3. Run verification after each commit

After each fix:

```bash
# Run the full test suite — must stay green
uv run pytest automation/tests/ -v

# Run the linter
uv run ruff check automation/
```

After all four commits are in, run a **dry-run against the full CBM repo** and paste the report. Expected numbers:

```
Parsed by table (approximate — actual values depend on current CBM content):
  BusinessObject: ~28
  Decision: ~36 (unchanged — this parser was not in scope)
  Domain: 4 (unchanged)
  Entity: ~16
  Field: ~245 (unchanged — this count already looked right)
  FieldOption: ~111 (unchanged)
  Persona: 13 (unchanged)
  Process: ~14
  ProcessStep: ~200
  Relationship: ~31 (unchanged)
  Requirement: ~130
```

If the post-fix dry-run shows anomalies not covered by these four bugs, stop and report them rather than trying to fix more. There may be more bugs this follow-up doesn't cover.

### 4. Report

In your response, confirm:

- Each bug's root cause was verified against a real CBM document before fixing
- All four fixes applied as described with commits in order
- Test count before and after each commit
- Post-fix dry-run output pasted verbatim
- Any deviations from the instructions and why
- Any ambiguities encountered during the fix
- Any additional anomalies noticed in the dry-run that weren't covered by this follow-up

Do not push — leave that for Doug.

## What Is Out of Scope

- Do not modify any code in `automation/db/`, `automation/workflow/`, `automation/prompts/`, `automation/importer/`, `automation/impact/`, `automation/docgen/`, `automation/ui/`, or `espo_impl/`
- Do not modify `automation/cbm_import/importer.py` except for the deduplication logic in Bug #4 Part B
- Do not refactor the parsers beyond the scope of the four bugs
- Do not "improve" other parser logic that looks suboptimal — report it separately in your final summary if you notice anything
- Do not add new top-level modules or new parser types
- Do not modify the schema or migrations
- Do not run the real import (non-dry-run) — Doug runs that manually after reviewing the fixes

## Reference Documents

Primary:
- `PRDs/product/crmbuilder-automation-PRD/CLAUDE-CODE-PROMPT-step16-cbm-integration.md` — the original Step 16 prompt
- The CBM repository at `dbower44022/ClevelandBusinessMentoring`, especially `PRDs/MN/MN-INTAKE.docx`, `PRDs/CBM-Entity-Inventory.docx`, and `PRDs/CBM-Master-PRD.docx` as real-world verification sources

Supporting:
- L2 PRD Section 13.3 — document type catalog (what each CBM document type contains)
- L2 PRD Section 11.12 — identifier management rules
- Memory item 7 — human-readable-first identifier convention
- Memory item 8 — field table format (already handled correctly in entity_prd.py, not in scope here)

## Summary of Changes

Files that will be modified:

```
automation/cbm_import/parsers/process_document.py    # Bugs #1 and #2
automation/cbm_import/parsers/entity_inventory.py    # Bug #3
automation/cbm_import/parsers/master_prd.py          # Bug #4 Part A
automation/cbm_import/importer.py                    # Bug #4 Part B (dedupe)
automation/cbm_import/parser_logic.py                # May need helper updates for Bug #1
automation/tests/test_cbm_importer.py                # New tests for each fix
automation/tests/fixtures/create_fixtures.py         # Fixture updates
automation/tests/fixtures/cbm_subset/*.docx          # Regenerated fixtures
```

Files that will NOT be modified:

- Anything in `automation/db/`, `automation/workflow/`, `automation/prompts/`, `automation/importer/`, `automation/impact/`, `automation/docgen/`, `automation/ui/`, `espo_impl/`
- Parsers for entity_prd, domain_prd — their counts look correct in the dry-run
- Integration tests in `automation/tests/integration/` — unchanged unless they need updates to track new expected counts

After these four commits land, Doug will re-run the dry-run against full CBM. If the numbers look right, he will run the real import. If more issues surface, they become a subsequent follow-up.

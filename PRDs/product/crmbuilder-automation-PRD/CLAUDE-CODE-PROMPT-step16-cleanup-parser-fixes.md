# Claude Code Implementation Prompt — Step 16 Cleanup: Parser Fixes

## Context

Step 16 is complete: the CBM importer, integration tests, and Part 0 project_folder wiring all landed. 1067 tests pass. The fixture subset integration tests work correctly.

Doug ran the CLI against the real CBM repository in dry-run mode and got this report:

```
=== CBM Import Report ===
Parsed:   634 records
Imported: 0 records
Skipped:  0 records
Warnings: 0
Errors:   0
Parsed by table:
  BusinessObject: 82 parsed, 0 imported
  Decision: 36 parsed, 0 imported
  Domain: 4 parsed, 0 imported
  Entity: 36 parsed, 0 imported
  Field: 245 parsed, 0 imported
  FieldOption: 111 parsed, 0 imported
  Persona: 13 parsed, 0 imported
  Process: 29 parsed, 0 imported
  ProcessStep: 46 parsed, 0 imported
  Relationship: 31 parsed, 0 imported
  Requirement: 1 parsed, 0 imported
```

Four of these numbers are wrong. Code review against the real CBM documents has identified four concrete parser bugs. This cleanup prompt fixes them.

**Do NOT modify any code outside `automation/cbm_import/` for this cleanup.** The engines and UI are locked. The only exceptions are tests in `automation/tests/`.

Make **four separate commits** so each fix can be reviewed independently.

## Before You Start

**Clone the CBM repo locally** so you have real documents to test against:

```bash
git clone https://github.com/dbower44022/ClevelandBusinessMentoring.git /tmp/cbm
```

You will need to read a handful of real CBM documents while you work:
- `/tmp/cbm/PRDs/MN/MN-INTAKE.docx` — standard process document with requirements table and workflow list
- `/tmp/cbm/PRDs/MN/MN-MATCH.docx` — another process document for cross-verification
- `/tmp/cbm/PRDs/CBM-Entity-Inventory.docx` — has 12 tables; only table index 1 is the real inventory
- `/tmp/cbm/PRDs/CBM-Master-PRD.docx` — the Master PRD with persona and domain sections

Use `python-docx` directly (`from docx import Document`) to inspect these. Do not rely on pandoc output — the bugs are about what python-docx exposes to the parser, and pandoc's plain-text rendering hides some of the details (particularly Word list-paragraph numbering, which pandoc renders but python-docx does not return in paragraph text).

After fixing each bug, run the dry-run CLI against the real CBM repo to verify the numbers improve:

```bash
python -m automation.cbm_import \
    --cbm-repo /tmp/cbm \
    --client-db /tmp/cbm-client.db \
    --master-db /tmp/cbm-master.db \
    --dry-run
```

Include a "before and after" number comparison for each bug in your final report.

---

## Bug #1: Requirements are in a table, not paragraphs

### The problem

`automation/cbm_import/parsers/process_document.py` calls `parse_requirement_list(paragraphs, req_idx, ...)` which scans paragraphs for requirements. The fallback `_extract_requirements_from_text()` uses a regex `([\w-]+-(?:REQ|SYS|DAT)-\d+)\s*[:\-–—]\s*(.+?)` that requires an inline `ID: description` format.

**Real CBM process documents store requirements in a two-column table** with headers `ID | Requirement`. The table sits between the "6. System Requirements" heading and the "7. Process Data" heading. Neither the paragraph scanner nor the regex fallback finds the table, so requirements are almost entirely missed.

Verified against `PRDs/MN/MN-INTAKE.docx`:
- The requirements section header is "6. System Requirements"
- The table is `d.tables[2]` (the third table in the document)
- 14 rows (1 header + 13 requirement rows)
- Header row: `['ID', 'Requirement']`
- Data rows: `['MN-INTAKE-REQ-001', 'The system must accept client mentoring requests...']`

### The fix

Add a **table-based requirements extractor** to `process_document.py` that:

1. Iterates all tables in the document
2. Detects requirement tables by checking if the header row contains the cells `ID` and `Requirement` (or close variants like `Identifier`/`Requirement Description`)
3. Extracts each data row as `{identifier: row[0], description: row[1], priority: "must"}`
4. Returns the combined list

Call this extractor **before** the paragraph-based fallback. Only fall back to the paragraph scanner if no requirement table is found (some documents may not follow the table convention).

**Do not remove the existing `parse_requirement_list()` and `_extract_requirements_from_text()` functions** — they may still work for documents that don't use the table format. Just add the table-based extractor as the primary path.

**Priority detection:** The real CBM tables don't have a priority column. Default to `"must"` for all table-extracted requirements. This matches the current fallback behavior.

### Test

Add a test in `automation/tests/test_cbm_importer.py` that:
- Loads a hand-crafted minimal process document .docx with a requirements table
- Asserts the correct number of requirements are parsed
- Asserts the identifier, description, and priority are correct

You can either add a new fixture .docx or update the existing `MN-INTAKE.docx` fixture in `automation/tests/fixtures/cbm_subset/` to include a requirements table. If you update the existing fixture, also update `automation/tests/fixtures/create_fixtures.py` (the script that generates the fixtures) so the fixture can be regenerated.

Update the existing integration test in `automation/tests/integration/test_cbm_importer.py` to assert `Requirement` count is non-zero after import.

### Expected dry-run improvement

Before: `Requirement: 1 parsed`
After: `Requirement: 100+ parsed` (roughly 10 requirements per process × ~13 processes = ~130)

### Commit 1 message

```
Fix CBM process document requirements parser to read tables

Requirements in real CBM process documents are stored in a two-column
table (ID | Requirement) between the "6. System Requirements" heading
and the "7. Process Data" heading. The existing paragraph scanner and
inline regex fallback could not find them, so only 1 of ~130
requirements was being parsed across the entire CBM repository.

Adds a table-based extractor as the primary path, retaining the
paragraph-based fallback for documents that don't follow the table
convention. Defaults extracted requirements to priority="must".
```

---

## Bug #2: ProcessStep regex fails on Word list paragraphs

### The problem

`automation/cbm_import/parsers/process_document.py:_extract_steps()` uses the regex:

```python
match = re.match(r"^(?:Step\s+)?(\d+)[.):]\s*(.+)", text, re.IGNORECASE)
```

This requires the step text to literally start with a digit-and-punctuation sequence like `"1. The prospective client..."`.

**Real CBM process documents use Word's List Paragraph style for numbered steps.** The list numbering is rendered by Word from the paragraph's `w:numPr` XML element — it is NOT part of the paragraph's text. When `python-docx` returns `paragraph.text`, it returns `"The prospective client completes..."` without any `"1. "` prefix. The regex fails on every list paragraph.

Verified against `PRDs/MN/MN-INTAKE.docx` "4. Process Workflow" section:
- Paragraph style is `"List Paragraph"`
- `paragraph.text` returns `"The prospective client completes and submits..."` with no numeric prefix
- The current regex never matches

The parser has a "continuation of previous step" branch that catches some fragments, but it only fires after at least one step has already matched — which never happens.

**Current result:** `ProcessStep: 46 parsed` across ~13 processes = ~3.5 steps per process on average. Expected: 10-15 steps per process.

### The fix

Your choice of approach — the two options are:

**Option A — Position-based numbering.** When you encounter a paragraph whose style name is `"List Paragraph"` in the workflow section, treat each list paragraph as a step and number them by their position (1, 2, 3, ...). Reset the counter when you leave the list (e.g., when you hit a non-list paragraph or a new section heading).

**Option B — Read the rendered list number from `w:numPr`.** python-docx exposes the paragraph's underlying XML via `paragraph._element`. You can walk it to find `w:numPr` and use `w:ilvl` (indent level) + `w:numId` (list definition) to reconstruct the displayed number. This is more fragile and requires understanding Word's numbering model.

**Pick whichever is cleaner.** Option A is simpler and is sufficient if the primary goal is to capture the text content and ordering of steps. Option B preserves the exact displayed numbering, which might matter if the source document uses sub-lists or restarted numbering that the administrator expects to see verbatim.

Either way, the fix needs to:

1. Pass `python-docx` paragraph objects (not just text strings) into `_extract_steps()` so the step extractor can check paragraph styles or XML
2. Detect List Paragraph style paragraphs in the workflow section
3. Produce one step per list paragraph with the full text as `description`
4. Preserve ordering via `sort_order` (1-based within the process)
5. Keep the existing literal-digit regex as a fallback for documents that don't use List Paragraph style

**The signature of `_extract_steps` will need to change** — it currently receives `list[str]`, and it will need to receive something that preserves style information. One approach: receive `list[(text: str, style: str)]` tuples. Another: receive the list of paragraph objects directly and extract text inside the function. Either is fine. Update the caller in `process_document.py` accordingly.

**Be careful not to break the existing fixture tests** in `automation/tests/test_cbm_importer.py` and `automation/tests/integration/test_cbm_importer.py`. The fixture .docx files may or may not use List Paragraph style; verify by inspecting `automation/tests/fixtures/cbm_subset/MN/MN-INTAKE.docx` with python-docx before committing.

### Test

Add a test in `automation/tests/test_cbm_importer.py` that:
- Loads a hand-crafted process document with a workflow section containing List Paragraph steps
- Asserts the correct number of steps are parsed
- Asserts sort_order is 1-based and monotonically increasing
- Asserts the step descriptions match the source text

If the existing fixture `MN-INTAKE.docx` doesn't have List Paragraph style workflow steps, update it (and `create_fixtures.py`) to include them.

Update the integration test to assert that the parsed ProcessStep count is at least, say, 5 per process on average for the fixture subset (or some sensible threshold).

### Expected dry-run improvement

Before: `ProcessStep: 46 parsed`
After: `ProcessStep: 150+ parsed` (roughly 10 steps × ~13 processes)

### Commit 2 message

```
Fix CBM process step extractor to handle Word List Paragraph style

The existing regex ^(\d+)[.):]  never matched real CBM process steps
because Word's List Paragraph numbering is rendered from the paragraph's
w:numPr element, not stored in the text. python-docx returns paragraph
text without the list number prefix, so the regex always failed.

Updates _extract_steps to accept paragraph objects (with style info)
instead of plain text strings, detects List Paragraph style in the
workflow section, and numbers steps by [position-in-list OR rendered
w:numPr — describe your choice in the commit body].

Retains the literal-digit regex as a fallback for documents that don't
use Word list paragraph styling.
```

---

## Bug #3: Entity Inventory parser reads all tables, not just the real inventory

### The problem

`automation/cbm_import/parsers/entity_inventory.py` iterates all tables in the document:

```python
for table in tables:
    for row in table[1:]:  # Skip header
        ...
```

**The real `CBM-Entity-Inventory.docx` has 12 tables**, not 1:
- Table index 0: Document metadata header (6 rows: Document Type, Implementation, etc.)
- **Table index 1: The real entity inventory (28 rows × 7 cols)**
- Tables 2-11: Per-entity detail tables (each 5 rows × 2 cols)

The parser treats every row of every table as a potential business object, so it scrapes 82 BusinessObjects (28 real + 54 junk from metadata and detail tables) and 36 Entity records (duplicated/junk entity names extracted from detail tables that describe single entities).

Verified against `PRDs/CBM-Entity-Inventory.docx`:
- Table 1 has header `['PRD Entity Name', 'CRM Entity', 'Native / Custom', 'Entity Type', 'Discriminator', 'Disc. Value', 'Domain(s)']`
- This is the canonical structure for the inventory

### The fix

Detect the real inventory table by its header signature. A table is the inventory if and only if its first row contains cells whose lowercased text matches a known inventory column set. At minimum, check that the header row contains **all of** the following:
- "entity" (matches "PRD Entity Name" or "CRM Entity")
- "native" or "type" (matches "Native / Custom" or "Entity Type")

Or more strictly, check for the exact string `"PRD Entity Name"` in the first cell (case-insensitive, whitespace-tolerant). Whichever detection heuristic you use, include a fallback warning if no inventory table is found so the administrator knows the parse failed.

Rewrite the iteration:

```python
inventory_table = _find_inventory_table(tables)
if inventory_table is None:
    report.add_warning("No entity inventory table found — expected table with 'PRD Entity Name' header")
    return data, report

for row in inventory_table[1:]:  # Skip header
    ...
```

The new inventory table has **7 columns**, not 2. Update the row-parsing logic to read each column by position:
- Column 0: PRD Entity Name → `business_object.name`
- Column 1: CRM Entity → `entity.name`
- Column 2: Native / Custom → `entity.is_native`
- Column 3: Entity Type → `entity.entity_type`
- Column 4: Discriminator (usually a field name)
- Column 5: Disc. Value (usually a value like "Client" or "Mentor")
- Column 6: Domain(s) → comma-separated domain codes

The current parser's column-by-column heuristic (iterating all cells trying to figure out which is which) should be replaced with direct positional access once the correct table is identified.

**Deduplication:** The new entity inventory table has multiple rows per CRM entity (e.g., "Client Contact" and "Mentor Contact" both map to "Contact"). Entity records must be deduplicated by CRM entity name (not by PRD entity name). Business objects are NOT deduplicated — each PRD entity name is its own business concept and gets its own BusinessObject row.

### Test

Add a test in `automation/tests/test_cbm_importer.py` that:
- Loads a hand-crafted Entity Inventory with multiple tables (metadata header + real inventory + detail tables)
- Asserts only the real inventory table is consumed
- Asserts the BusinessObject count matches the real inventory row count
- Asserts the Entity count is the deduplicated set of CRM Entity values

Update the existing fixture `automation/tests/fixtures/cbm_subset/CBM-Entity-Inventory.docx` to include multiple tables (at least one metadata table before the inventory table, and one detail table after) if it doesn't already. Update `create_fixtures.py` accordingly.

### Expected dry-run improvement

Before: `BusinessObject: 82 parsed, Entity: 36 parsed`
After: `BusinessObject: 28 parsed, Entity: ~16 parsed` (matches the Entity Inventory's own summary: "16 CRM entities, 28 business entity concepts")

### Commit 3 message

```
Fix CBM Entity Inventory parser to target the real inventory table

The existing parser iterated all 12 tables in CBM-Entity-Inventory.docx,
treating every row as a business object. This scraped document metadata,
summary statistics, and per-entity detail tables in addition to the
actual inventory, producing 82 BusinessObjects and 36 Entities instead
of the correct 28 and ~16.

Detects the real inventory table by its header signature (PRD Entity
Name + Native/Custom columns), then reads rows by column position from
the 7-column canonical structure. Deduplicates entities by CRM entity
name since multiple PRD concepts can map to the same entity.
```

---

## Bug #4: Process is counted twice in the parse report

### The problem

`automation/cbm_import/parsers/master_prd.py:70` calls `report.record_parsed("Process", len(processes))` when scanning the Master PRD's process inventory section.

`automation/cbm_import/parsers/process_document.py:121` calls `report.record_parsed("Process", 1)` for each individual process document.

**Both fire during a normal import.** The Master PRD contributes ~15 processes to the report, and each of the ~14 process .docx files adds 1 more. Result: `Process: 29 parsed` in the report even though the actual count should be ~14.

Note: Doug has instructed us to **skip verification of whether this causes duplicate rows at import time.** The fix below addresses both the report-count inflation and makes duplicate writes impossible, so either way the behavior is correct after this commit.

### The fix

Two changes:

**1. Remove the `record_parsed("Process", ...)` call from `master_prd.py`**. The Master PRD's process inventory is a source of metadata (process codes, names, domain assignments) but it is not a source of Process record creation. The individual process documents are the authoritative source. The Master PRD parser should still extract the process inventory data into `data["processes"]` so the importer has a list of expected processes, but it should not record them as parsed Process entities.

**2. Add deduplication at import time in `importer.py`**. When the importer writes Process records, it should dedupe by `process_code`. If the Master PRD's inventory mentions `MN-INTAKE` and the `MN-INTAKE.docx` process document is also parsed, only one Process row should be written. The process document's data takes precedence — it is the fuller source.

Read `importer.py` to find where Process records are written. Add a dedupe check: if a Process with the given code already exists in the database, update it instead of inserting a new row. (`save_record` or an `INSERT OR REPLACE` or a pre-check via `SELECT` — whichever matches the existing write patterns in `importer.py`.)

### Test

Add a test in `automation/tests/test_cbm_importer.py` that:
- Parses a minimal Master PRD containing a process inventory with process code `MN-INTAKE`
- Asserts the Master PRD parser does NOT record Process in the parsed counts
- Asserts the parsed data still contains the process inventory list (in `data["processes"]`)

Add a test in `automation/tests/integration/test_cbm_importer.py` or similar that:
- Imports a fixture subset where both the Master PRD and a process document reference the same process
- Asserts exactly one Process row exists in the database for that code

### Expected dry-run improvement

Before: `Process: 29 parsed`
After: `Process: ~14 parsed` (one per actual process document)

### Commit 4 message

```
Deduplicate Process records between Master PRD and process documents

The Master PRD parser was recording Process entries from its process
inventory section, and each individual process document was also
recording itself as a Process. This inflated the parse count to ~2x
the real number of processes.

Removes the Process record_parsed call from master_prd.py — the Master
PRD's process inventory is now metadata only, not a source of Process
records. Adds dedupe-by-code logic in importer.py so that if both
sources reference the same process, only one Process row is written.
The process document's data takes precedence over the Master PRD
inventory stub.
```

---

## Verification Before You Commit

After each commit, run:

```bash
# All tests pass
uv run pytest automation/tests/ -q

# Linter clean
uv run ruff check automation/

# Dry-run against real CBM repo to see the numbers improve
python -m automation.cbm_import \
    --cbm-repo /tmp/cbm \
    --client-db /tmp/cbm-client.db \
    --master-db /tmp/cbm-master.db \
    --dry-run
```

Record the "parsed by table" counts from each dry-run in your final report. Show the progression: initial numbers → after commit 1 → after commit 2 → after commit 3 → after commit 4.

Final expected state (approximate — exact numbers depend on the CBM repo's content):

```
BusinessObject: 28 (was 82)
Decision: 36 (unchanged)
Domain: 4 (unchanged)
Entity: ~16 (was 36)
Field: 245 (unchanged — no bug here)
FieldOption: 111 (unchanged)
Persona: 13 (unchanged)
Process: ~14 (was 29)
ProcessStep: 150+ (was 46)
Relationship: 31 (unchanged)
Requirement: 100+ (was 1)
```

If any number is significantly different from expected (e.g., Field count changes unexpectedly), investigate before committing. The four bugs above are the ones I've found — there may be others that only surface once the obvious bugs are fixed.

## Working Style

- **Read the real CBM documents before writing any fix.** The bugs come from assumptions about document structure that don't match reality. Inspect the real documents with python-docx directly.
- **Make four separate commits.** Each bug fix is independent. Don't combine them.
- **Keep changes scoped to `automation/cbm_import/` and `automation/tests/`.** Do not touch `automation/db/`, `automation/workflow/`, `automation/prompts/`, `automation/importer/`, `automation/impact/`, `automation/docgen/`, `automation/ui/`, or `espo_impl/`.
- **Do not run the real import (without `--dry-run`) at any point during this work.** Only dry-runs are safe until all four bugs are fixed and verified.
- **Surface new bugs, do not hide them.** If fixing one bug reveals a different bug in the same parser, flag it in your report rather than silently fixing it. Doug will review and decide whether to add it to this cleanup.
- **Do not refactor code that is not directly involved in the bug.** Surgical fixes only.
- **Do not push.** Doug pushes after reviewing the cleanup.

## What Is Out of Scope

- Fixing any bug not in the four listed above (flag them in the report instead)
- Refactoring the parser architecture
- Modifying code outside `automation/cbm_import/` and `automation/tests/`
- Running the real import
- Pushing commits

## Final Report Requirements

In your response, include:

1. **Before/after counts from the dry-run** after each commit
2. **Approach chosen for Bug #2** (position-based numbering or w:numPr reading) and why
3. **Any new bugs discovered** during the work (flagged, not fixed)
4. **Any tests that had to change** beyond new tests for the four bugs
5. **Final full test count** and linter status

Report format same as prior Step 16 report. This is the final cleanup before Doug runs the real CBM import.

# Claude Code Follow-Up #2 — Step 16 Parser Cleanup (Round 2)

## Context

Step 16 (CBM bootstrap importer) received a first round of parser fixes that addressed four bugs identified in the initial dry-run. Doug re-ran the dry-run against the full CBM repo and the numbers improved substantially — but three documents are still producing incomplete data, and post-hoc analysis identified three more bugs.

### First cleanup dry-run results

| Table | Original | After Round 1 | Target | Status |
|---|---|---|---|---|
| BusinessObject | 82 | 24 | ~28 | ✅ fixed |
| Entity | 36 | 12 | ~16 | ✅ fixed |
| Process | 29 | 10 | ~13 | ⚠️ short by 3 |
| ProcessStep | 46 | 69 | ~150 | ⚠️ short by ~80 |
| Requirement | 1 | 70 | ~100 | ⚠️ short by ~30 |
| Decision | 36 | 36 | — | ✓ unchanged |
| Domain | 4 | 4 | — | ✓ unchanged |
| Persona | 13 | 13 | — | ✓ unchanged |
| Field | 245 | 245 | — | ✓ unchanged |
| FieldOption | 111 | 111 | — | ✓ unchanged |
| Relationship | 31 | 31 | — | ✓ unchanged |

### What's causing the remaining gaps

Three bugs, each verified against the real CBM repository by parsing the actual documents:

1. **Bug #5 — `_extract_steps_from_doc` breaks on any Heading, including Heading 2 subsections.** Some CBM process documents (notably MR-DEPART.docx and NOTES-MANAGE.docx) organize their workflow section with `4. Process Workflow` as Heading 1 followed by `4.1 Voluntary Resignation`, `4.2 Administrative Departure`, etc. as Heading 2 subsections. The current code at `automation/cbm_import/parsers/process_document.py` (around line 143) has `if style_name and style_name.startswith("Heading"): break` which fires on the first Heading 2 and exits with zero steps. All the actual workflow steps are in paragraphs following the Heading 2 subsections and are never seen.

2. **Bug #6 — Requirements table detector requires a literal `['ID', 'Requirement']` header row.** Most CBM process documents have a proper header row, but MR-DEPART.docx's requirements table starts directly with a data row (no header at all):
   ```
   Row 0: ['MR-DEPART-REQ-001', 'The system must support transition...']
   Row 1: ['MR-DEPART-REQ-002', '...']
   ```
   The current detector checks `header[0].lower() == 'id'` and fails on MR-DEPART, causing all its requirements to be lost.

3. **Bug #8 — CR sub-domain processes are never discovered.** The CBM repo organizes the Client Recruiting domain with sub-directories:
   ```
   PRDs/CR/
   ├── CBM-Domain-Overview-ClientRecruiting.docx
   ├── PARTNER/
   │   ├── CR-PARTNER-PROSPECT.docx
   │   └── CR-PARTNER-MANAGE.docx
   ├── MARKETING/
   ├── EVENTS/
   └── REACTIVATE/
   ```
   The importer's Phase 4 loop at `automation/cbm_import/importer.py` around line 92 uses `domain_dir.glob("*.docx")` which does NOT recurse. The CR domain root contains only the Domain Overview (filtered out) and no process files, so both CR processes are silently skipped. The same issue affects any future domain with a similar nested structure.

(There is no "Bug #7" in this prompt — the numbering was assigned when the bugs were first catalogued.)

### Scope

This is a **small, targeted follow-up**. Three bugs, three commits, all localized to two files:

- `automation/cbm_import/parsers/process_document.py` — Bugs #5 and #6
- `automation/cbm_import/importer.py` — Bug #8

No changes to the database, no schema migrations, no workflow engine modifications, no UI changes, no other parsers.

**Verification against real CBM documents has already been done by reading files in `dbower44022/ClevelandBusinessMentoring`.** The claims above are factual, not hypothetical. You should still verify before applying the fixes by reading the specific documents mentioned, but you do not need to audit the entire CBM corpus.

## Bug #5 — Workflow step extractor breaks on Heading 2 subsections

### The problem

In `automation/cbm_import/parsers/process_document.py`, the `_extract_steps_from_doc()` function (around line 119) contains:

```python
# Stop at next Heading (section boundary)
if style_name and style_name.startswith("Heading"):
    if in_section or sort_order > 0:
        break
    continue
```

This breaks on **any** heading, including Heading 2 and Heading 3. For MR-DEPART.docx:

- Paragraph 32: `4. Process Workflow` (Heading 1) — this is the workflow_heading_idx
- Paragraph 34: `4.1 Voluntary Resignation` (Heading 2) — **parser breaks here**
- Paragraphs 35-39: 5 workflow steps (text paragraphs with style=None containing `"1. The mentor contacts..."`, `"2. The Mentor Administrator..."`, etc.)
- Paragraph 40: `4.2 Administrative Departure` (Heading 2) — 5 more steps follow
- Paragraph 46: `4.3 Reactivation from Departed` (Heading 2) — 3 more steps follow
- Paragraph 52: `5. Process Completion` (Heading 1) — true end of workflow section

The parser sees Heading 2 at paragraph 34 and exits with 0 steps. All 13 actual workflow steps across the three subsections are lost.

Same pattern affects NOTES-MANAGE.docx which has `4.1 Creating a Note`, `4.2 Viewing Notes`, `4.3 Editing a Note` as Heading 2 subsections.

### The fix

Only break on **Heading 1** (top-level section boundary), not on Heading 2 or deeper. Heading 2 and deeper are sub-section titles within the workflow section — they should be treated like any other non-step paragraph: skipped but not exiting the loop.

Replace the current break logic with something like:

```python
# Stop at next top-level section (Heading 1 only)
if style_name == "Heading 1":
    if in_section or sort_order > 0:
        break
    continue

# Skip sub-section headings (Heading 2, Heading 3) without breaking
if style_name and style_name.startswith("Heading"):
    continue
```

The existing text-pattern-based boundary detection (the regex at line 154-159 matching `"5. Process Completion"` etc.) is still valuable as a fallback — keep it. It's a defense-in-depth against documents where the Heading 1 style is missing or wrong.

Note: the sub-section step text (`"1. The mentor contacts..."`) has style=None in MR-DEPART and should match the existing regex fallback at line 165 (`r"^(?:Step\s+)?(\d+)[.):]\s*(.+)"`). Verify that the step numbering resets or continues correctly across subsections — for the purposes of this fix, continuous sort_order across subsections is acceptable (step 1 of 4.1 becomes sort_order=1, step 1 of 4.2 becomes sort_order=6 if 4.1 had 5 steps, etc.).

### Test

Add a test to `automation/tests/test_cbm_importer.py` that constructs a process document with:
- A Heading 1 `"4. Process Workflow"`
- A Heading 2 `"4.1 First Subsection"`
- Three paragraphs with text `"1. Step one"`, `"2. Step two"`, `"3. Step three"` (style=None or "Normal")
- A Heading 2 `"4.2 Second Subsection"`
- Two more paragraphs with text `"1. Step four"`, `"2. Step five"`
- A Heading 1 `"5. Process Completion"` (the real boundary)

Assert that `_extract_steps_from_doc()` returns 5 steps, not 0.

### Verify against real data

After the fix, re-parse MR-DEPART.docx and NOTES-MANAGE.docx:

```python
from automation.cbm_import.parsers.process_document import parse
data, report = parse('/home/doug/Dropbox/Projects/ClevelandBusinessMentors/PRDs/MR/MR-DEPART.docx')
print(f"MR-DEPART steps: {len(data['steps'])}")  # Expect 10-15
data, report = parse('/home/doug/Dropbox/Projects/ClevelandBusinessMentors/PRDs/services/NOTES/NOTES-MANAGE.docx')
print(f"NOTES-MANAGE steps: {len(data['steps'])}")  # Expect 8-15
```

Both should return non-zero step counts.

### Commit 1 message

```
Fix CBM workflow step extractor to not break on Heading 2 subsections

Some CBM process documents (MR-DEPART, NOTES-MANAGE, MR-MANAGE) use
Heading 2 subsections within the Process Workflow section to group
steps by sub-flow (e.g., "4.1 Voluntary Resignation", "4.2 Administrative
Departure"). The previous code broke on any heading, exiting the step
extraction loop at the first Heading 2 and losing all subsequent steps.

Change the break logic to only fire on Heading 1 (true section boundary).
Heading 2 and deeper are now treated as non-step paragraphs that are
skipped but do not end the workflow section.

Before: MR-DEPART 0 steps, NOTES-MANAGE 0 steps.
After: MR-DEPART ~13 steps, NOTES-MANAGE ~10 steps.
```

## Bug #6 — Requirements table without a header row is not recognized

### The problem

In `automation/cbm_import/parsers/process_document.py`, the requirements-table detector scans document tables for one whose first row is `['ID', 'Requirement']` (or similar case-insensitive variations). This works for most CBM documents but fails for MR-DEPART.docx, whose requirements table has **no header row** — the first row is already data:

```
Table 1 in MR-DEPART.docx:
  Row 0: ['MR-DEPART-REQ-001', 'The system must support transition of a mentor to Resigned or Departed status...']
  Row 1: ['MR-DEPART-REQ-002', 'The system must record a departure reason when status changes to Resigned or Departed.']
  Row 2: ['MR-DEPART-REQ-003', 'The system must record the departure date...']
```

Three requirements, none detected, because `row[0][0].lower() != 'id'`.

### The fix

Augment the requirements-table detector to **also match tables by content pattern**, not only by header row. The detection order should be:

1. **Header-based detection (existing):** Scan tables for one whose first row matches `['ID', 'Requirement']` (case-insensitive, stripped). If found, parse rows 1..N.
2. **Content-based detection (new):** If header-based detection found nothing, scan tables for one whose first data cell matches a requirement identifier pattern like `^[A-Z][A-Z0-9\-]*-REQ-\d+$`. If found, parse ALL rows of that table as requirements (no header row to skip).

Regex suggestion: `r"^[A-Z][A-Z0-9\-]+-REQ-\d+$"` — matches identifiers like `MR-DEPART-REQ-001`, `MN-INTAKE-REQ-013`, `NOTES-MANAGE-REQ-001`, etc.

Both detectors extract `(identifier, description)` from columns 0 and 1 of each data row. The output is the same list of requirement dicts.

Important: the content-based detector must be careful not to match field tables or other tables that happen to have identifier-shaped first cells. The `-REQ-` infix in the regex is the key discriminator — field tables use `-DAT-` and open-issue tables use `-ISS-`. As long as the regex requires `-REQ-` specifically, it will not match those other table types.

### Test

Add a test to `automation/tests/test_cbm_importer.py` that constructs a process document with:
- A System Requirements section
- A table with NO header row
- First row: `['XYZ-TEST-REQ-001', 'First requirement description']`
- Second row: `['XYZ-TEST-REQ-002', 'Second requirement description']`

Assert that the requirements parser extracts both requirements with the correct identifiers and descriptions.

Also add a negative test: construct a process document with a data table whose first cell is a `-DAT-` identifier (field table). Assert that the requirements parser does NOT extract it as a requirement.

### Verify against real data

After the fix, re-parse MR-DEPART.docx:

```python
from automation.cbm_import.parsers.process_document import parse
data, report = parse('/home/doug/Dropbox/Projects/ClevelandBusinessMentors/PRDs/MR/MR-DEPART.docx')
print(f"MR-DEPART requirements: {len(data['requirements'])}")  # Expect 3-5
for r in data['requirements']:
    print(f"  {r['identifier']}: {r['description'][:60]}")
```

Should return 3 or more requirements.

### Commit 2 message

```
Fix CBM requirements detector to match tables by content pattern

MR-DEPART.docx (and possibly other CBM process documents) has a
requirements table without a header row — the first row is already
data containing a requirement identifier. The previous header-based
detector missed these tables entirely.

Augment the detector with a content-based fallback: if no table
matches the ['ID', 'Requirement'] header pattern, scan for tables
whose first data cell matches a requirement identifier regex
(pattern: {PREFIX}-REQ-{NNN}). The -REQ- infix distinguishes
requirements tables from field (-DAT-) and issue (-ISS-) tables.

Before: MR-DEPART 0 requirements extracted.
After: MR-DEPART 3+ requirements extracted.
```

## Bug #8 — CR sub-domain processes are never discovered by the importer

### The problem

In `automation/cbm_import/importer.py`, the Phase 4 loop that discovers process documents walks the top level of each domain directory:

```python
# Phase 4: Import Process Documents
for domain_dir in sorted(self._prds.iterdir()):
    if not domain_dir.is_dir() or domain_dir.name in (
        "entities", "Archive", "WorkflowDiagrams", "services"
    ):
        continue
    for proc_file in sorted(domain_dir.glob("*.docx")):    # ← does not recurse
        if proc_file.name.startswith("~"):
            continue
        if any(kw in proc_file.name for kw in ("Domain-PRD", "Domain-Overview", "SubDomain")):
            continue
        r = self.import_process(proc_file.stem, proc_file)
        report.merge(r)
```

`domain_dir.glob("*.docx")` does not recurse into sub-directories. The CR domain's file layout is:

```
PRDs/CR/
├── CBM-Domain-Overview-ClientRecruiting.docx      ← filtered by "Domain-Overview"
├── PARTNER/
│   ├── CBM-SubDomain-Overview-Partner.docx        ← filtered by "SubDomain"
│   ├── CR-PARTNER-PROSPECT.docx                   ← never reached
│   └── CR-PARTNER-MANAGE.docx                     ← never reached
├── MARKETING/
│   └── (sub-domain overview + future processes)
├── EVENTS/
│   └── ...
└── REACTIVATE/
    └── ...
```

The CR domain root contains only the Domain Overview (which is correctly filtered out), so `glob("*.docx")` produces zero process files and both actual processes are silently skipped.

### The fix

Replace `domain_dir.glob("*.docx")` with `domain_dir.rglob("*.docx")` to recurse into sub-directories. The existing filename-based filters (`"Domain-PRD"`, `"Domain-Overview"`, `"SubDomain"`) will continue to correctly exclude sub-domain overview files like `CBM-SubDomain-Overview-Partner.docx`.

Also add `"Graphics"` to the top-level exclusion list alongside `"entities"`, `"Archive"`, `"WorkflowDiagrams"`, `"services"` — the CBM repo has a `PRDs/Graphics/` directory that may contain .docx files unrelated to processes.

```python
for domain_dir in sorted(self._prds.iterdir()):
    if not domain_dir.is_dir() or domain_dir.name in (
        "entities", "Archive", "WorkflowDiagrams", "services", "Graphics"
    ):
        continue
    for proc_file in sorted(domain_dir.rglob("*.docx")):    # ← now recurses
        if proc_file.name.startswith("~"):
            continue
        if any(kw in proc_file.name for kw in ("Domain-PRD", "Domain-Overview", "SubDomain")):
            continue
        r = self.import_process(proc_file.stem, proc_file)
        report.merge(r)
```

The `services/` branch is handled by the existing separate Phase 4 services loop at lines 100-108 — no change needed there.

Do NOT modify the Phase 5 Domain PRD loop at lines 112-120. Domain PRDs are only expected at the domain root, not in sub-directories.

### Test

Add a test to `automation/tests/test_cbm_importer.py` that constructs a fixture directory tree:
```
fixture_prds/
├── CBM-Master-PRD.docx
├── CBM-Entity-Inventory.docx
├── TD/                                    (test domain)
│   ├── CBM-Domain-PRD-TestDomain.docx     (filtered)
│   ├── TD-DIRECT.docx                     (top-level process)
│   └── SUB/
│       ├── CBM-SubDomain-Overview-Sub.docx  (filtered)
│       └── TD-SUB-NESTED.docx             (nested process)
```

Run the importer in dry-run mode. Assert that both `TD-DIRECT` and `TD-SUB-NESTED` are recorded as processes (2 process records total).

### Verify against real data

After the fix, run a dry-run against the full CBM repo and check the Process count:

```bash
python -m automation.cbm_import \
    --cbm-repo /home/doug/Dropbox/Projects/ClevelandBusinessMentors \
    --client-db /tmp/verify-cbm.db \
    --master-db /tmp/verify-master.db \
    --dry-run
```

Expected: **Process: ~13** (5 MN + 5 MR + 2 CR + 1 NOTES). Will be 12 or 13 depending on whether the importer currently correctly handles the services/NOTES-MANAGE case (which it does — verified).

### Commit 3 message

```
Fix CBM process discovery to recurse into sub-domain directories

The CR domain organizes processes in sub-directories (CR/PARTNER/,
CR/MARKETING/, etc.). The importer's Phase 4 glob pattern did not
recurse, so CR-PARTNER-PROSPECT and CR-PARTNER-MANAGE were silently
skipped. Any future sub-domain-organized processes would have the
same problem.

Change the domain-directory walk from glob() to rglob() so it
recurses. Existing filename-based filters (Domain-PRD, Domain-Overview,
SubDomain) continue to exclude overview documents correctly.

Also add Graphics/ to the top-level exclusion list to prevent
traversing unrelated .docx files in that directory.

Before: Process: 10 (CR processes missed).
After: Process: 12-13.
```

## What I Want From You

### 1. Verify each bug against a real CBM document before fixing

Open these documents with python-docx and confirm the symptoms:

- **Bug #5:** Open `PRDs/MR/MR-DEPART.docx` and `PRDs/services/NOTES/NOTES-MANAGE.docx`. Confirm they have Heading 2 subsections within the Process Workflow section.
- **Bug #6:** Open `PRDs/MR/MR-DEPART.docx`. List all tables with their first row. Confirm that the requirements table does not have a `['ID', 'Requirement']` header row.
- **Bug #8:** List `PRDs/CR/PARTNER/` contents. Confirm that `CR-PARTNER-PROSPECT.docx` and `CR-PARTNER-MANAGE.docx` exist.

If the CBM repo is not available in your environment, ask Doug. Doug's local path is `/home/doug/Dropbox/Projects/ClevelandBusinessMentors`.

### 2. Apply the fixes in order

Commit 1 (Bug #5 — workflow steps), Commit 2 (Bug #6 — requirements table), Commit 3 (Bug #8 — importer recursion). Three separate commits for independent review.

### 3. Run verification after each commit

```bash
# After each commit
uv run pytest automation/tests/ -v
uv run ruff check automation/
```

All existing tests must continue to pass. New tests added in each commit must pass.

### 4. Final dry-run against full CBM

After all three commits are in, run a dry-run against the full CBM repository:

```bash
python -m automation.cbm_import \
    --cbm-repo /home/doug/Dropbox/Projects/ClevelandBusinessMentors \
    --client-db /tmp/verify-cbm.db \
    --master-db /tmp/verify-master.db \
    --dry-run
```

Expected final numbers:
```
BusinessObject: 24        (unchanged from previous round)
Decision: 36              (unchanged)
Domain: 4                 (unchanged)
Entity: 12                (unchanged)
Field: 245                (unchanged)
FieldOption: 111          (unchanged)
Persona: 13               (unchanged)
Process: 12-13            ← up from 10 (Bug #8 fix)
ProcessStep: 100-160      ← up from 69 (Bug #5 fix)
Relationship: 31          (unchanged)
Requirement: 80-110       ← up from 70 (Bug #6 fix)
```

The ranges are wider than exact targets because the actual count depends on how steps and requirements are distributed across the CBM documents. The important thing is that all three previously-broken numbers move in the right direction.

### 5. Report

Confirm:
- Each bug verified against real CBM documents before fixing
- All three fixes applied in three separate commits
- Test count before and after each commit
- Post-fix dry-run output pasted verbatim
- Any deviations from the instructions and why
- Any additional anomalies noticed that this follow-up does not cover

Do not push — leave that for Doug.

## What Is Out of Scope

- Any code outside `automation/cbm_import/parsers/process_document.py` and `automation/cbm_import/importer.py` (and the test file + any fixture updates needed)
- Database schema changes
- Workflow engine modifications
- UI changes
- Modifying any other parser (entity_inventory, entity_prd, master_prd, domain_prd)
- Modifying the existing Master PRD or Entity Inventory parsers
- Running the real (non-dry-run) import
- Refactoring the parser beyond the scope of these three bugs
- Attempting to handle merged cells in python-docx tables (separate, known issue, not in scope here)

## Reference Documents

Primary:
- The CBM repository at `dbower44022/ClevelandBusinessMentoring`, specifically:
  - `PRDs/MR/MR-DEPART.docx` (for Bug #5 and Bug #6)
  - `PRDs/services/NOTES/NOTES-MANAGE.docx` (for Bug #5)
  - `PRDs/CR/PARTNER/CR-PARTNER-PROSPECT.docx` (for Bug #8)
  - `PRDs/CR/PARTNER/CR-PARTNER-MANAGE.docx` (for Bug #8)

Supporting:
- `automation/cbm_import/parsers/process_document.py` — the file containing Bugs #5 and #6
- `automation/cbm_import/importer.py` — the file containing Bug #8
- The first parser cleanup prompt at `PRDs/product/crmbuilder-automation-PRD/CLAUDE-CODE-PROMPT-step16-parser-cleanup.md` — for context on how the previous fixes were structured

## Summary of Changes

Files that will be modified:

```
automation/cbm_import/parsers/process_document.py    # Bugs #5 and #6
automation/cbm_import/importer.py                    # Bug #8
automation/tests/test_cbm_importer.py                # New tests for each fix
```

Files that will NOT be modified:

- Any other parser
- Any code outside `automation/cbm_import/`
- Database schema or migrations
- Workflow engine, prompts, importer (the production importer), impact engine, docgen, UI, espo_impl
- Fixture documents (the existing fixtures should still exercise the fixed parsers correctly; if they don't, update create_fixtures.py to reflect the real CBM structure)

After these three commits land, Doug will re-run the dry-run against full CBM. If the numbers look right, he will run the real import.

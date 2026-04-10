# Claude Code Follow-Up #4 — Step 16 Parser and Template Polish

## Context

Step 16's CBM bootstrap importer is functionally complete and document generation works end-to-end. Manual validation of the generated documents and database content revealed four data-quality issues — three in parsers and one in a docgen template. All four affect the quality of the imported data or generated output.

After these fixes land, Doug will delete the existing CBM client database and re-import from scratch to get a clean dataset.

## Bug P1 — Description rows parsed as separate Field records (HIGH PRIORITY)

### The problem

CBM Entity PRD field tables follow a two-row-per-field format (per the L2 PRD and Memory item 8):

```
Row 1: Field Name (bold) | Type | Required | Values | Default | ID
Row 2: Description spanning all columns (merged cell, gray font)
```

When python-docx reads a merged-cell row, it returns the **same text in every cell**. The `parse_field_table()` function in `automation/cbm_import/parser_logic.py` (around line 80) has description-row detection code at lines 124-135 that checks whether all cells except the first are empty (`all_others_empty`). Because merged cells repeat the description text in every cell, `all_others_empty` is False, and the parser treats the description row as a **regular field entry**.

This creates a junk Field record where `name`, `label`, `default_value`, and `description` all contain the same long description text.

Verified in the database. Contact entity has 100 Field rows, but the real count should be ~50. Every other row is a description-as-field entry:

```
Row 17: name='contactType'                                    ← real field
Row 18: name='The discriminator field for the Contact...'     ← DESCRIPTION of contactType
Row 19: name='preferredName'                                  ← real field
Row 20: name='The name the contact prefers to be called...'   ← DESCRIPTION of preferredName
```

The total 245 fields across all entities is ~120 real fields + ~125 junk.

### The fix

In `automation/cbm_import/parser_logic.py:parse_field_table()`, add a **merged-cell description row detector** that catches rows where python-docx repeats the same text in multiple cells. The detection heuristic:

**A row is a merged description row if the text in cell 0 is identical to the text in cell 1** (or cell 2, etc.). Real data rows never have the same text in the Field Name and Type columns. Merged rows always do because python-docx fills every cell with the merged content.

Pseudocode:

```python
# Before processing the row as a field, check for merged cells
first_cell = row[0].strip()
if len(row) >= 3:
    # Merged description rows repeat the same text across cells
    second_cell = row[1].strip() if len(row) > 1 else ""
    if first_cell and second_cell and first_cell == second_cell:
        # This is a merged description row — attach to previous field
        if fields:
            fields[-1].setdefault("description", "")
            if first_cell not in fields[-1].get("description", ""):
                fields[-1]["description"] = first_cell
        i += 1
        continue
```

This replaces the current `pass # Don't consume it` logic at line 135. Now the description row is **consumed and its text is attached to the previous field's description**.

Additionally, as a safety net, add a **length-based filter**: if `field_name` (column 0) is longer than 200 characters, it's almost certainly a description, not a field name. Real field names in CBM are camelCase identifiers (e.g., "contactType", "preferredName") — never more than ~40 characters.

### Test

Add a test to `automation/tests/test_cbm_importer.py` that:

1. Constructs a field table with 3 fields, each followed by a merged description row (simulate merged cells by putting the same text in every cell of the description row)
2. Parses it through `parse_field_table()`
3. Asserts exactly 3 fields are returned (not 6)
4. Asserts each field's `description` contains the description text from the merged row

### Commit 1 message

```
Fix parse_field_table to detect merged description rows

CBM Entity PRD field tables have two rows per field: a data row and a
description row where the description cell is merged across all columns.
python-docx returns merged cells with the same text in every cell. The
parser's previous description-row detection checked for empty cells,
which failed on merged rows, causing ~125 description entries to be
imported as junk Field records.

Add a merged-cell detector: if cells 0 and 1 have identical non-empty
text, the row is a description and its text is attached to the previous
field. Also add a length filter as a safety net.

Before: 245 Field records (half are descriptions).
After: ~120 Field records (descriptions attached to their fields).
```

## Bug P2 — Entity name duplication from header table parsing

### The problem

`automation/cbm_import/parsers/entity_prd.py` extracts the entity name from the Entity PRD's header table. CBM Entity PRDs have header entries like:

```
Entity: Account (Native — Company Type)
```

The parser stores the full text including the parenthetical type annotation as the entity name. This creates a duplicate Entity row alongside the clean one from the Entity Inventory parser.

Previously fixed manually in the database by repointing Field FKs and deleting junk entities. The parser still has the bug and will recreate duplicates on re-import.

### The fix

In `automation/cbm_import/parsers/entity_prd.py`, when extracting the entity name from the header table, strip everything from the first `(` onward and trim whitespace.

Find the line(s) where `entity_name` or `e_name` is set from the header table data. Apply:

```python
# Strip parenthetical type annotation: "Account (Native — Company Type)" → "Account"
if "(" in entity_name:
    entity_name = entity_name[:entity_name.index("(")].strip()
```

This should be applied in both places where the entity name is extracted from the header (around lines 73 and 84).

### Test

Add a test that constructs an Entity PRD with header entry `"Entity: Engagement (Custom — Base Type)"` and asserts the parser returns entity name `"Engagement"`, not the full string.

### Commit 2 message

```
Strip parenthetical type annotation from Entity PRD entity names

CBM Entity PRDs have header entries like "Account (Native — Company
Type)". The parser was storing the full text as the entity name,
creating duplicates alongside the clean entities from the Entity
Inventory. Strip everything after the first '(' and trim whitespace.
```

## Bug P3 — Persona descriptions empty in generated Master PRD

### The problem

The generated Master PRD shows persona headers (e.g., "System Administrator (MST-PER-001)") but no descriptive text below each header. The CBM Master PRD source document contains detailed descriptions for each persona (Responsibilities, What the CRM Provides, etc.).

Likely cause: the `automation/cbm_import/parsers/master_prd.py` parser extracts persona code and name but drops the description that follows in the source document.

### The fix

First, verify by reading the CBM Master PRD source document in python-docx. Each persona in the source has a heading like "MST-PER-001 — System Administrator" followed by paragraphs of descriptive text until the next persona heading.

The parser needs to:
1. Detect each persona heading (already working)
2. Capture all paragraphs between the current persona heading and the next one as the `description`
3. Store the description in the persona dict

Then verify the importer writes the description to the Persona table's `description` column (it may already do this if the parser provides it — check `importer.py` line 150-155).

### Test

Add a test that constructs a Master PRD with two personas, each followed by description paragraphs. Assert the parser returns descriptions for both personas.

### Commit 3 message

```
Extract persona descriptions from Master PRD

The Master PRD parser extracted persona codes and names but dropped
the descriptive text that follows each persona heading (Responsibilities,
What the CRM Provides). Capture all paragraphs between persona headings
as the persona description.

Before: Persona.description empty for all 13 personas.
After: Persona.description populated with source document content.
```

## Bug P4 — Domain PRD filename includes raw identifier text

### The problem

Generated Domain PRD files have filenames like:

```
CBM-Domain-PRD-3.5 MST-DOM-003 — Client Recruiting.docx
```

The expected filename should be something like `CBM-Domain-PRD-ClientRecruiting.docx` or `CBM-Domain-PRD-CR.docx`. The raw domain identifier (`3.5 MST-DOM-003 — Client Recruiting`) is leaking into the filename.

The bug is in the docgen pipeline or the Domain PRD template — it's using a raw domain description or identifier as part of the filename instead of a clean code or name.

### The fix

Search for the filename construction logic in `automation/docgen/`. It's likely in `automation/docgen/pipeline.py` or `automation/docgen/templates/domain_prd_template.py` or a shared helper. The filename should use the domain code (e.g., "CR") or a sanitized domain name (e.g., "ClientRecruiting"), not the raw description text.

Read the existing filename conventions for other document types (Master PRD produces `CBM-Master-PRD.docx`, Entity PRD produces `Contact-Entity-PRD.docx`) and match the pattern.

### Test

The easiest test: generate a Domain PRD document in a test fixture and assert the output filename does not contain identifier prefixes like "3.5 MST-DOM-003".

### Commit 4 message

```
Fix Domain PRD generated filename to use clean domain name

Generated Domain PRDs had filenames like "CBM-Domain-PRD-3.5 MST-DOM-003
— Client Recruiting.docx" because the raw domain identifier/description
was used in the filename. Use the domain code or sanitized name instead
to match the convention of other generated document types.
```

## Verification — Re-import from scratch

After all four commits, Doug will delete the existing CBM client database and re-import from scratch:

```bash
# Delete existing database
rm automation/data/cbm-client.db

# Re-import
python -m automation.cbm_import \
    --cbm-repo /home/doug/Dropbox/Projects/ClevelandBusinessMentoring \
    --client-db automation/data/cbm-client.db \
    --master-db automation/data/master.db
```

Then verify:

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('automation/data/cbm-client.db')
tables = ['Domain','Persona','Entity','Field','FieldOption','Relationship','BusinessObject','Process','ProcessStep','Requirement','Decision','WorkItem','AISession']
for t in tables:
    n = conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
    print(f'{t:<20} {n}')
print()
# Check no description-as-field entries remain
long_names = conn.execute('SELECT COUNT(*) FROM Field WHERE LENGTH(name) > 100').fetchone()[0]
print(f'Fields with name > 100 chars: {long_names}  (should be 0)')
# Check entity names are clean
for row in conn.execute('SELECT name FROM Entity WHERE name LIKE \"%(%)%\"'):
    print(f'BAD entity name: {row[0]!r}')
# Check persona descriptions
for row in conn.execute('SELECT code, LENGTH(description) FROM Persona ORDER BY code LIMIT 5'):
    print(f'Persona {row[0]}: desc length={row[1] or 0}')
"
```

Expected post-fix results:
- **Field: ~120** (down from 245 — the junk description entries are gone)
- **Entity: 12** (no duplicates)
- **Fields with name > 100 chars: 0**
- **No entity names containing parentheses**
- **Persona descriptions have non-zero length**

Also regenerate the Contact Entity PRD:

```bash
python3 -c "
import sqlite3
from automation.docgen.generator import DocumentGenerator
client_conn = sqlite3.connect('automation/data/cbm-client.db')
master_conn = sqlite3.connect('automation/data/master.db')
docgen = DocumentGenerator(client_conn, master_conn=master_conn, project_folder='/home/doug/cbm-generated')
wi = client_conn.execute(\"SELECT id FROM WorkItem WHERE item_type = 'master_prd' LIMIT 1\").fetchone()
if wi:
    result = docgen.generate(wi[0], mode='final')
    print(f'Master PRD: {result.file_path}  error={result.error}')
wi = client_conn.execute(\"SELECT id FROM WorkItem WHERE item_type = 'entity_prd' AND status = 'complete' LIMIT 1\").fetchone()
if wi:
    result = docgen.generate(wi[0], mode='final')
    print(f'Entity PRD: {result.file_path}  error={result.error}')
"
```

Then inspect the generated Entity PRD to confirm field names are real (e.g., "Contact Type", "Preferred Name") and not descriptions.

## What I Want From You

### 1. Apply the four fixes in order

Commit 1 (P1 — description rows), Commit 2 (P2 — entity name strip), Commit 3 (P3 — persona descriptions), Commit 4 (P4 — domain PRD filename). Four separate commits.

### 2. Run tests after each commit

```bash
uv run pytest automation/tests/ -v
uv run ruff check automation/
```

### 3. Report

Confirm:
- All four fixes applied
- Test count before and after
- Any deviations or ambiguities

Do not run the re-import or push — leave both for Doug.

## What Is Out of Scope

- Forward-reference relationships (deferred)
- Project_folder UI wiring (deferred)
- `_parse_dry_run()` services handling (minor)
- Modifying any Step 9-15 code except docgen templates
- Database schema changes
- Two-pass relationship resolution

## Files Modified

```
automation/cbm_import/parser_logic.py                # P1 — merged description row detection
automation/cbm_import/parsers/entity_prd.py          # P2 — entity name strip
automation/cbm_import/parsers/master_prd.py          # P3 — persona descriptions
automation/docgen/templates/domain_prd_template.py   # P4 — filename fix (or pipeline.py)
  OR automation/docgen/pipeline.py                   # P4 — whichever owns filename construction
automation/tests/test_cbm_importer.py                # New tests for P1, P2, P3
```

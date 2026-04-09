# Claude Code Follow-Up #3 — Step 16 Importer Cleanup (Round 3)

## Context

Step 16's CBM bootstrap importer has been through two rounds of parser cleanup. The third real (non-dry-run) import succeeded with 698 records parsed and 682 imported. Database verification confirmed two remaining issues that need fixes before the manual UI walkthrough:

### Real-import results (verbatim)

```
=== CBM Import Report ===
Parsed:   698 records
Imported: 682 records
Skipped:  1 records
Warnings: 0
Errors:   0
Parsed by table:
  BusinessObject: 24 parsed, 24 imported
  Decision: 36 parsed, 36 imported
  Domain: 4 parsed, 4 imported
  Entity: 12 parsed, 12 imported
  Field: 245 parsed, 245 imported
  FieldOption: 111 parsed, 111 imported
  Persona: 13 parsed, 13 imported
  Process: 11 parsed, 19 imported       ← 19 = 11 from .docx + 8 stubs from inventory
  ProcessStep: 119 parsed, 106 imported  ← gap = NOTES-MANAGE's 13 steps
  Relationship: 31 parsed, 0 imported   ← BUG: never written to DB
  Requirement: 92 parsed, 85 imported    ← gap = NOTES-MANAGE's 7 reqs
Skipped records:
  [Process] NOTES-MANAGE: Could not resolve domain (NOTES-MANAGE.docx)
```

### Database verification confirms

- `WorkItem` has 53 rows — workflow graph constructed correctly
- `AISession` has 20 rows — synthetic per-document sessions present
- `ChangeLog` has 0 rows — by design (bootstrap doesn't write ChangeLog noise; not a bug)
- **`Relationship` has 0 rows — entire table empty**
- `Process` has 19 rows but **NOTES-MANAGE is missing**

This follow-up addresses two bugs:

1. **Bug #9 — Relationships are parsed but never written to the database.** `import_entity_prd()` in `automation/cbm_import/importer.py` parses `data["relationships"]` from the Entity PRD but the function body has no code path that inserts into the Relationship table. The parser produces them, the report counts them as parsed, but they vanish at write time. Result: **0 relationships in the database, all 31 parsed records lost.**

2. **Bug #10 — Service documents (NOTES-MANAGE) cannot be imported because they have no domain.** Service .docx files like `PRDs/services/NOTES/NOTES-MANAGE.docx` have an empty `Domain:` field in their header table because services are structurally parallel to domains, not children of them. The current `import_process()` looks up Domain by code at line 309, gets nothing for an empty domain code, and returns a "Could not resolve domain" skip. The schema's `Domain.is_service` column exists specifically for this case: services should be Domain rows with `is_service=TRUE`.

This follow-up does NOT modify any parsers. Both fixes are localized to `automation/cbm_import/importer.py`.

### Scope

Two bugs, two commits, all changes in **one file**: `automation/cbm_import/importer.py`. Plus tests in `automation/tests/test_cbm_importer.py`.

No changes to:
- Any parser
- Database schema or migrations
- WorkflowEngine
- UI
- Any other automation package
- Any other Step 9–15 code

## Bug #9 — Relationships parsed but not written

### The problem

`automation/cbm_import/importer.py:import_entity_prd()` (around lines 222-287) parses an Entity PRD via `entity_prd.parse()`, which returns a dict with these keys: `entity`, `fields`, `field_options`, `relationships`, etc. The function imports the Entity, Fields, and FieldOptions but **never references `data.get("relationships", [])`**.

The parser correctly produces relationship dicts with these fields:
```python
{
    "name": "mentorAssignments",          # relationship name (camelCase from CBM)
    "link_type": "oneToMany",             # one of: oneToMany, manyToOne, manyToMany, oneToOne
    "entity_foreign": "Engagement",       # target entity name (string, needs lookup)
}
```

You can see the parser at `automation/cbm_import/parsers/entity_prd.py:_extract_relationships()` (around line 146). It pulls relationships from tables that contain link_type keywords like "onetomany" or "many-to-one".

### The fix

After the field/option import loop in `import_entity_prd()`, add a relationship import loop that:

1. Iterates `data.get("relationships", [])`
2. For each relationship dict:
   - Look up the target entity ID via `self._resolve("Entity", "name", rel["entity_foreign"])`
   - If the target entity is not found, record a skip with reason `"Target entity not found: {entity_foreign}"` and continue (do NOT fail the whole import)
   - INSERT into the Relationship table with the appropriate columns (see schema below)
   - Wrap in try/except `sqlite3.IntegrityError` to handle duplicates (already-existing relationships) the same way the field loop does
3. Call `report.record_imported("Relationship")` for each successful insert

### Relationship table schema

The Relationship table's columns (from `automation/db/client_schema.py`) are roughly:

```sql
CREATE TABLE Relationship (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL,                 -- source entity (FK to Entity)
    entity_foreign_id INTEGER NOT NULL,         -- target entity (FK to Entity)
    name TEXT NOT NULL,                         -- relationship name (e.g., "mentorAssignments")
    link_type TEXT NOT NULL,                    -- 'oneToMany' | 'manyToOne' | 'manyToMany' | 'oneToOne'
    label TEXT,                                 -- display label (optional)
    description TEXT,                           -- relationship description (optional)
    created_by_session_id INTEGER,              -- FK to AISession
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (entity_id) REFERENCES Entity(id),
    FOREIGN KEY (entity_foreign_id) REFERENCES Entity(id),
    FOREIGN KEY (created_by_session_id) REFERENCES AISession(id),
    UNIQUE(entity_id, name)
);
```

Read the actual schema in `automation/db/client_schema.py` before writing the INSERT — the columns above are illustrative but may not be exactly right. If the actual schema has additional NOT NULL columns or different naming, match them.

### Code structure

The new loop should appear in `import_entity_prd()` after the existing field loop ends (around line 284) and before the `except Exception` clause. Pattern:

```python
for rel in data.get("relationships", []):
    target_entity_name = rel.get("entity_foreign", "")
    if not target_entity_name:
        report.record_skipped(
            path.name, "Relationship", rel.get("name", "?"),
            "No target entity specified"
        )
        continue

    target_entity_id = self._resolve("Entity", "name", target_entity_name)
    if not target_entity_id:
        report.record_skipped(
            path.name, "Relationship", rel.get("name", "?"),
            f"Target entity not found: {target_entity_name}"
        )
        continue

    try:
        self._conn.execute(
            "INSERT INTO Relationship (entity_id, entity_foreign_id, name, link_type, "
            "description, created_by_session_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (entity_id, target_entity_id, rel["name"], rel.get("link_type", "oneToMany"),
             rel.get("description", ""), session_id),
        )
        self._conn.commit()
        report.record_imported("Relationship")
    except sqlite3.IntegrityError:
        self._conn.rollback()
        report.record_skipped(
            path.name, "Relationship", rel["name"], "Duplicate"
        )
```

Adjust the column list to match the actual schema. The `entity_id` variable is already in scope at that point in the function (line 242 sets it).

### Important consideration: forward references

Some entities reference entities that don't yet exist when their PRD is imported. For example, Contact-Entity-PRD might reference Engagement, but if Contact is imported first (alphabetical), Engagement doesn't exist yet and the FK lookup fails.

**For Round 3, accept this as a known limitation:** record the skip and continue. The administrator can add the missing relationships through the Data Browser after the import completes. Do not attempt a two-pass import or deferred resolution in this round — that's a larger architectural change.

If after the fix the verification dry-run shows many relationships skipped due to "target entity not found," that's a sign the import order matters and a future round may need to do entity creation in a first pass and relationship creation in a second pass. For now, let's see how bad it is.

### Test

Add a test to `automation/tests/test_cbm_importer.py` that:

1. Creates a temporary client database via `init_client_db()`
2. Inserts two Entity records: "Contact" and "Engagement"
3. Constructs a minimal Entity PRD .docx for Contact with one relationship: `{name: "engagements", link_type: "oneToMany", entity_foreign: "Engagement"}`
4. Calls `CBMImporter.import_entity_prd()` against it
5. Asserts a Relationship row exists in the database with the correct columns

Also add a test for the forward-reference case:
1. Insert only "Contact" (no Engagement)
2. Run the same import
3. Assert the Relationship was skipped (not inserted) and reported in the skip list with reason "Target entity not found: Engagement"

### Verify against real data

After the fix, re-run the real import against full CBM (or a backup copy if you don't want to overwrite the existing database):

```bash
# Optional: back up the existing database first
cp automation/data/cbm-client.db automation/data/cbm-client.db.before-round3

# Re-run the import (this will be additive on top of the existing DB)
python -m automation.cbm_import \
    --cbm-repo /home/doug/Dropbox/Projects/ClevelandBusinessMentoring \
    --client-db automation/data/cbm-client.db \
    --master-db automation/data/master.db
```

Then query:
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('automation/data/cbm-client.db')
print('Relationships:', conn.execute('SELECT COUNT(*) FROM Relationship').fetchone()[0])
print('Sample:')
for row in conn.execute('SELECT name, link_type, entity_id, entity_foreign_id FROM Relationship LIMIT 5'):
    print(' ', row)
"
```

Expected: 15-31 relationships imported (some may be skipped due to forward-reference issues, which is acceptable for this round).

### Commit 1 message

```
Import Relationship records in import_entity_prd

The Entity PRD parser produces relationship dicts in data["relationships"]
but import_entity_prd() never wrote them to the database. All 31 parsed
relationships in the CBM real-import were lost (parsed=31, imported=0).

Add a relationship import loop that resolves the target entity by name,
inserts a Relationship row with the appropriate FKs, and skips with a
clear reason when the target entity does not exist (forward reference).

Two-pass resolution for forward references is out of scope for this
round — the administrator can add unresolved relationships through the
Data Browser after import.

Before: Relationship 31 parsed, 0 imported.
After: Relationship 31 parsed, 15-31 imported (depending on forward refs).
```

## Bug #10 — Service documents skipped because they have no domain

### The problem

`automation/cbm_import/importer.py:import_process()` (around line 289) handles process documents by:

1. Parsing the .docx
2. Looking up the domain via `self._resolve("Domain", "code", proc_data.get("domain_code", ""))`
3. If no domain is found, recording a skip with reason "Could not resolve domain" and returning

For NOTES-MANAGE.docx (a service document at `PRDs/services/NOTES/NOTES-MANAGE.docx`), the parser sets `domain_code` to an empty string because services are structurally parallel to domains, not children of them. The Domain lookup fails, and the entire NOTES-MANAGE process is skipped along with its 13 ProcessSteps and 7 Requirements.

### The fix

The schema's `Domain` table has an `is_service` column (verified — see `automation/cbm_import/importer.py:159` where `is_service=False` is passed for regular domains during master_prd import). Services should be Domain rows with `is_service=TRUE`.

Modify `import_process()` to handle the missing-domain case by checking whether the process is being imported from the services branch:

**Approach:** Add a parameter to `import_process()` like `is_service: bool = False`. When the importer's services loop (around lines 100-108) calls `import_process()`, it passes `is_service=True`. Inside `import_process()`, when domain resolution fails AND `is_service` is True, auto-create or look up a "Services" Domain with `is_service=TRUE` and use that as the domain_id.

Example modifications:

**At lines 100-108 (services loop):**

```python
# Services
services_dir = self._prds / "services"
if services_dir.exists():
    for svc_dir in sorted(services_dir.iterdir()):
        if svc_dir.is_dir():
            for proc_file in sorted(svc_dir.glob("*.docx")):
                if not proc_file.name.startswith("~"):
                    r = self.import_process(proc_file.stem, proc_file, is_service=True)  # ← new arg
                    report.merge(r)
```

**In `import_process()` signature (line 289):**

```python
def import_process(
    self,
    process_code: str,
    path: Path | None = None,
    *,
    is_service: bool = False,
) -> ImportReport:
```

**In the domain resolution block (around line 309):**

```python
domain_id = self._resolve("Domain", "code", proc_data.get("domain_code", ""))
if not domain_id and is_service:
    # Auto-create or resolve a "Services" domain for service processes
    domain_id = self._ensure_services_domain(session_id)
```

**New helper method** `_ensure_services_domain()`:

```python
def _ensure_services_domain(self, session_id: int) -> int:
    """Get the ID of the Services domain, creating it if it doesn't exist.

    Service documents (e.g. NOTES-MANAGE) are structurally parallel to
    domain processes but live under a synthetic 'Services' domain row
    with is_service=TRUE.

    :param session_id: AISession ID for created_by_session_id.
    :returns: The Services domain ID.
    """
    if self._conn is None:
        return 0
    existing = self._resolve("Domain", "code", "SVC")
    if existing:
        return existing
    self._conn.execute(
        "INSERT INTO Domain (name, code, description, sort_order, is_service, "
        "created_by_session_id) VALUES (?, ?, ?, ?, ?, ?)",
        ("Services", "SVC", "Cross-domain services", 99, True, session_id),
    )
    self._conn.commit()
    return self._resolve("Domain", "code", "SVC") or 0
```

**Notes on the helper:**
- The domain code "SVC" is suggested but you can pick any short code that doesn't collide with existing domains. Avoid "S" (too generic) and avoid anything that might collide with future real domain codes. Document your choice in the commit message.
- `sort_order=99` puts the Services domain at the end of the list when displayed.
- The `is_service=True` flag is the key — the Step 15 UI uses this to render services in a separate sidebar branch per Section 14.8.1.

### Important consideration: process domain attribution

After this fix, NOTES-MANAGE will be imported as a Process under the synthetic "Services" domain (domain_id = whatever id "SVC" gets). The work item type for NOTES-MANAGE will still be `process_definition` (or `cross_domain_service` depending on what the WorkflowEngine uses for services — read `automation/workflow/phases.py` to confirm).

If the WorkflowEngine has a separate `cross_domain_service` work item type that needs to be used for services instead of `process_definition`, the importer should use that type. Read `phases.py` and `engine.py` to find out. If services use the same `process_definition` work item type as regular processes, no additional change is needed.

### Test

Add a test to `automation/tests/test_cbm_importer.py` that:

1. Creates a fixture .docx for a service process (header table has `Process Code` but empty/missing `Domain`)
2. Calls `CBMImporter.import_process(code, path, is_service=True)`
3. Asserts the Process row exists in the database
4. Asserts a Domain row with `code='SVC'`, `is_service=TRUE` exists
5. Asserts the Process row's `domain_id` references the Services domain

Also add a test for the regular case to confirm `is_service=False` still uses the existing domain resolution path:
1. Create a fixture .docx with `Domain: Mentoring (MN)`
2. Call `import_process(code, path, is_service=False)` (or just `import_process(code, path)`)
3. Assert the Process is associated with the MN Domain, not the SVC Domain

### Verify against real data

After the fix, re-run the real import against full CBM. The skip list should no longer contain NOTES-MANAGE, and the database should have a "Services" domain row plus a NOTES-MANAGE process row.

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('automation/data/cbm-client.db')
print('Services domain:')
for row in conn.execute(\"SELECT id, name, code, is_service FROM Domain WHERE is_service = 1\"):
    print(' ', row)
print('NOTES-MANAGE process:')
for row in conn.execute(\"SELECT code, name, domain_id FROM Process WHERE code = 'NOTES-MANAGE'\"):
    print(' ', row)
print('NOTES-MANAGE process steps:')
print(' ', conn.execute(\"SELECT COUNT(*) FROM ProcessStep ps JOIN Process p ON ps.process_id=p.id WHERE p.code='NOTES-MANAGE'\").fetchone()[0])
"
```

Expected:
- One Services domain row with `is_service=1`
- One NOTES-MANAGE process row referencing the Services domain
- ~10-15 NOTES-MANAGE process steps

### Commit 2 message

```
Auto-create Services domain for service process documents

Service documents like NOTES-MANAGE.docx live in PRDs/services/ and
have no parent domain — they are structurally parallel to domains, not
children of them. The Domain.is_service column exists for this case.

Add an is_service parameter to import_process() that, when set to True,
auto-creates a synthetic 'Services' domain (code='SVC', is_service=TRUE)
on first use and associates the process with it. The services loop in
import_all() now passes is_service=True for all service documents.

Before: NOTES-MANAGE skipped with "Could not resolve domain" — losing
the process plus 13 process steps and 7 requirements.
After: NOTES-MANAGE imported as a Services-domain process.
```

## What I Want From You

### 1. Verify the bugs against the database

Before changing code, run these queries against the existing `automation/data/cbm-client.db`:

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('automation/data/cbm-client.db')
print('Relationship rows:', conn.execute('SELECT COUNT(*) FROM Relationship').fetchone()[0])
print('NOTES-MANAGE process:', conn.execute(\"SELECT COUNT(*) FROM Process WHERE code='NOTES-MANAGE'\").fetchone()[0])
print('Services domain:', conn.execute('SELECT COUNT(*) FROM Domain WHERE is_service=1').fetchone()[0])
"
```

Expected (confirming the bugs are real):
- Relationship rows: 0
- NOTES-MANAGE process: 0
- Services domain: 0

### 2. Apply the fixes in order

Commit 1 (Bug #9 — relationships) first, then Commit 2 (Bug #10 — services). Two separate commits for independent review.

### 3. Run tests after each commit

```bash
uv run pytest automation/tests/ -v
uv run ruff check automation/
```

All existing tests must pass. New tests added in each commit must pass.

### 4. Re-run real import and verify

After both commits, do NOT modify the existing `cbm-client.db`. Instead:

```bash
# Move the existing DB aside
mv automation/data/cbm-client.db automation/data/cbm-client.db.round2

# Run a fresh import
python -m automation.cbm_import \
    --cbm-repo /home/doug/Dropbox/Projects/ClevelandBusinessMentoring \
    --client-db automation/data/cbm-client.db \
    --master-db automation/data/master.db
```

Note: The master DB should remain in place — only the client DB is being recreated.

Paste the full import report and the output of this verification query:

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('automation/data/cbm-client.db')
tables = ['Domain','Persona','Entity','Field','FieldOption','Relationship','BusinessObject','Process','ProcessStep','Requirement','Decision','WorkItem','AISession']
for t in tables:
    n = conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
    print(f'{t:<20} {n}')
print()
print('Services domain:', list(conn.execute('SELECT id, name, code FROM Domain WHERE is_service=1')))
print('NOTES-MANAGE:', list(conn.execute(\"SELECT code, name, domain_id FROM Process WHERE code='NOTES-MANAGE'\")))
"
```

### 5. Report

Confirm:
- Both bugs verified before fixing
- Both fixes applied in two separate commits
- Test count before and after each commit
- Final import report and verification query output pasted verbatim
- Any deviations from the instructions and why
- Any additional anomalies noticed in the post-fix database

Do not push — leave that for Doug.

## What Is Out of Scope

- Two-pass import (entity creation in pass 1, relationship creation in pass 2). If forward-reference issues are significant, that's a separate future round.
- Modifying any parser
- Changing the database schema or migrations
- Modifying the WorkflowEngine
- UI changes
- Modifying any other Step 9–15 code
- ChangeLog entries for bootstrap imports — accepted as not-a-bug per design decision

## Reference

Primary:
- `automation/cbm_import/importer.py` — the file being modified
- `automation/db/client_schema.py` — for the actual Relationship table column names
- `automation/cbm_import/parsers/entity_prd.py:_extract_relationships()` — to confirm the parser output structure
- `automation/workflow/phases.py` — to check if services use a different work item type than `process_definition`

Supporting:
- The previous Step 16 cleanup prompts for context on the established working style
- Memory item 13 — current state (CRM Builder Automation L2 PRD v1.13, all 16 steps complete)

## Summary of Changes

Files modified:
```
automation/cbm_import/importer.py            # Both bug fixes
automation/tests/test_cbm_importer.py        # New tests for both fixes
```

Files NOT modified:
- Any parser
- Any other automation package
- Database schema or migrations

After these two commits land, Doug will re-run the real import against fresh databases and verify the final state. If the numbers look right, the manual UI walkthrough begins.

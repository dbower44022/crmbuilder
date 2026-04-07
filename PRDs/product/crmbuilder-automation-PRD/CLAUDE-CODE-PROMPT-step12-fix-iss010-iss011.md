# Claude Code Follow-Up — Step 12: Fix cross-database ordering and add required field validation

## Context

You completed Step 12 (Import Processor) and the work was reviewed. The implementation is largely correct — 600 tests passing, all 16 modules + 16 test files present, linter clean, no regressions in Steps 9–11, AISession lifecycle correctly honored, and the trigger sequence properly delegates to the Workflow Engine.

Two issues were found that need to be corrected before Step 13 begins. Both are real but neither is severe enough to throw away the existing work — surgical fixes only.

## Issue 1: Cross-database transaction ordering (ISS-010)

### The problem

`automation/importer/commit.py` writes to two databases — the client database (most tables) and the master database (Client table only, used by master_prd imports). Per Section 11.6.2, all client database writes are wrapped in a single `transaction(conn)` for atomicity. The current implementation calls `_commit_client_update(master_conn, ...)` **inside** the client transaction loop, which means:

1. The client transaction begins.
2. Loop iteration 1: a Client ProposedRecord triggers `_commit_client_update` → `master_conn.commit()` happens immediately, writing to the master database.
3. Loop iterations 2..N: the loop processes other records (Domain, Persona, Process, etc.). If any of these fails (constraint violation, FK error, etc.), the client transaction rolls back.
4. Result: master.Client is updated, client.* is unchanged. The two databases are inconsistent.

SQLite does not support cross-database transactions, so the only safe pattern is to **defer the master write until the client transaction has successfully committed**.

### The fix

Restructure `commit_batch` in `automation/importer/commit.py` to separate Client records from other records and process them in two phases:

**Phase 1 — Client transaction (atomic, all-or-nothing):**
1. Separate the accepted records into two lists: `client_table_records` (those with `table_name == "Client"`) and `other_records` (everything else).
2. Open the client transaction.
3. Process `other_records` exactly as the current code does — INSERTs, UPDATEs, intra-batch FK resolution, ChangeLog entries.
4. Update the AISession row's `import_status` and `completed_at` inside this same transaction. This must happen before the transaction closes so that if anything fails, the AISession status is also rolled back.
5. The transaction commits at the end of the `with transaction(conn):` block.

**Phase 2 — Master write (after client transaction succeeds):**
1. After the `with transaction(conn):` block exits successfully, iterate over `client_table_records`.
2. For each one, call `_commit_client_update(master_conn, ...)` as before.
3. If any master write fails (extremely unlikely for a single-field UPDATE on an existing row), catch the exception and append a warning to a new field on `CommitResult` — `master_write_errors: list[str]`. Do not raise; the client commit is already complete.

The new ordering means: if a client database write fails, the master database is **never touched**. The only failure mode is if the master write fails after the client commit succeeds, which leaves the client in a consistent state and the master one field stale (the next master_prd import would overwrite it with the correct value anyway).

### What to update

- `automation/importer/commit.py` — restructure `commit_batch` per above. Add `master_write_errors: list[str]` field to the `CommitResult` dataclass with `default_factory=list`.
- `automation/importer/pipeline.py` — if `master_write_errors` is non-empty, propagate the warning through `ImportResult` so callers can see it. The pipeline should not raise — the client commit succeeded.
- `automation/tests/test_importer_commit.py` — add a test that simulates a client-db failure (e.g., unique constraint violation on a Domain code) when a Client record is also in the batch, and verifies that **master.Client was NOT modified**. Add a second test that verifies the happy path (client commit succeeds → master write happens after).

Do not change any other module's behavior. The trigger module, the mappers, and the conflict detection are all unaffected.

## Issue 2: Required field validation (ISS-011)

### The problem

The mapper modules use `payload.get("name", "")` patterns throughout, which means a missing required field becomes an empty string in the proposed record. The conflict detection module does not check for empty required fields, so an empty value passes Stage 4 (Detect) and reaches Stage 6 (Commit), where the database NOT NULL constraint catches it. The entire transaction rolls back, and the administrator is forced to retry the whole import after fixing the AI output.

This works correctly per spec but creates a bad user experience: the administrator only finds out about the problem at commit time, after going through the review stage. The required field check should happen at conflict detection time so the administrator sees it in Stage 5 and can fix or reject the record before commit.

### The fix

Add a new conflict type to `automation/importer/conflicts.py`: `required_field_check`.

**Step 1 — Add a per-table required column map.**

Add a module-level constant near the top of `conflicts.py`:

```python
# Required (NOT NULL) columns per table that must be non-empty in proposed records.
# Hand-maintained — see test_importer_conflicts.py for the drift-detection test.
REQUIRED_COLUMNS: dict[str, list[str]] = {
    "Domain": ["name", "code"],
    "Entity": ["name", "code"],
    "Field": ["name", "field_type", "entity_id"],
    "FieldOption": ["field_id", "value"],
    "Relationship": ["name", "from_entity_id", "to_entity_id", "relationship_type"],
    "Persona": ["name", "code"],
    "BusinessObject": ["name"],
    "Process": ["name", "code", "domain_id"],
    "ProcessStep": ["process_id", "step_number", "description"],
    "Requirement": ["identifier", "description"],
    "Decision": ["identifier", "title"],
    "OpenIssue": ["identifier", "title"],
    "ProcessEntity": ["process_id", "entity_id"],
    "ProcessField": ["process_id", "field_id"],
    "ProcessPersona": ["process_id", "persona_id"],
}
```

**Verify this list against `automation/db/client_schema.py`** before committing — every column with `NOT NULL` (other than `id`, `created_at`, `updated_at`, `created_by_session_id`) should appear here. The Client table is intentionally excluded since it lives in the master database and uses different validation.

**Step 2 — Add the check function.**

```python
def _check_required_fields(record: ProposedRecord) -> list[Conflict]:
    """Check that all required columns have non-empty values.

    Empty strings, None, and missing keys are all treated as missing.
    """
    if record.action == "update":
        # Updates only need to populate the fields they change;
        # required fields untouched by the update remain valid.
        return []

    required = REQUIRED_COLUMNS.get(record.table_name, [])
    conflicts: list[Conflict] = []
    for col in required:
        # Skip columns resolved by intra-batch references — they will
        # be populated at commit time
        if col in record.intra_batch_refs:
            continue
        value = record.values.get(col)
        if value is None or (isinstance(value, str) and value.strip() == ""):
            conflicts.append(Conflict(
                severity="error",
                conflict_type="required_field_missing",
                message=f"Required field '{col}' is missing or empty",
                field_name=col,
            ))
    return conflicts
```

**Step 3 — Wire it into `detect_conflicts`.**

In the main loop where each record is checked, add `record.conflicts.extend(_check_required_fields(record))` alongside the existing conflict checks.

### What to update

- `automation/importer/conflicts.py` — add the `REQUIRED_COLUMNS` map, the `_check_required_fields` function, and the call site in `detect_conflicts`.
- `automation/tests/test_importer_conflicts.py` — add tests:
  1. A proposed Domain with empty `name` produces an `error`-severity conflict
  2. A proposed Domain with empty `code` produces an `error`-severity conflict
  3. A proposed Domain with both `name` and `code` populated produces no required-field conflicts
  4. A proposed Field with `entity_id` set via `intra_batch_refs` (not in `values`) does NOT produce a required-field conflict for `entity_id`
  5. An update action does not produce required-field conflicts even if the values dict omits required fields
  6. **Drift detection test:** Read every CREATE TABLE statement in `automation/db/client_schema.py`, parse out the columns marked NOT NULL (excluding `id`, `created_at`, `updated_at`, `created_by_session_id`, `is_native`, `is_required`, `read_only`, `audited`, `is_full_width`, `is_service` and any other BOOLEAN-with-default columns), and assert that every one is listed in `REQUIRED_COLUMNS` for its table. This will fail loudly if anyone adds a NOT NULL column to the schema without updating the map. The Client table is excluded from this check.

The drift detection test is important — without it, this hand-maintained map will silently get out of sync with the schema. Implement it carefully so it correctly distinguishes between NOT NULL columns that need user-supplied values vs. columns with DEFAULT clauses that are auto-populated.

Do not change any other module's behavior.

## What I Want From You

### 1. Verify the issues are real before doing anything else

**Do not assume these fixes are already done.** Run these commands and report the output verbatim:

```bash
# Check that the cross-db ordering issue exists
grep -n "_commit_client_update" automation/importer/commit.py
```

Expected output: at least one call site **inside** the `with transaction(conn):` block (around lines 80–86 in the current version). If you see the call inside the transaction loop, the issue is real and you must continue with Issue 1.

```bash
# Check that the required field validation does not exist
grep -n "REQUIRED_COLUMNS\|_check_required_fields\|required_field" automation/importer/conflicts.py
```

Expected output: zero matches. If grep returns no matches, the issue is real and you must continue with Issue 2. If grep returns matches, stop and report what's already there.

If either issue is already fixed, report it and skip the corresponding section. Do not infer the state of the code from anything other than running these commands.

### 2. Apply the fixes

Apply both fixes per the instructions above. Make them in two separate commits so they can be reviewed independently.

Commit 1 message:
```
Fix cross-database transaction ordering (ISS-010)

Restructure commit_batch to commit client-db records in a single
transaction before writing to the master database. Prevents the
master.Client update from persisting when a subsequent client-db
write fails. Per L2 PRD Section 16.10.
```

Commit 2 message:
```
Add required field validation to conflict detection (ISS-011)

New REQUIRED_COLUMNS map and _check_required_fields conflict check
catch empty required fields at Stage 4 (Detect) instead of Stage 6
(Commit), letting administrators fix issues during review rather
than after a failed commit and rollback. Includes a drift-detection
test that scans the schema for unlisted NOT NULL columns. Per
L2 PRD Section 16.11.
```

### 3. Verify

Run these commands and confirm each:

```bash
# All tests must pass
uv run pytest automation/tests/ -v
```

Expected: all tests pass. Test count will be slightly higher than 600 because new conflict tests were added and at least one new commit test was added.

```bash
# Linter must be clean
uv run ruff check automation/
```

Expected: no errors.

```bash
# No regressions in earlier steps
grep -rn "phase TEXT" automation/db/
grep -rn "anthropic.com\|api\.anthropic" automation/importer/
```

Expected: zero matches for both.

```bash
# Verify the cross-db fix actually moved the call out of the transaction
grep -B2 -A2 "_commit_client_update" automation/importer/commit.py
```

Expected: the call site should be **outside** the `with transaction(conn):` block, in a separate loop after the transaction closes.

```bash
# Verify the required field check exists
grep -n "_check_required_fields\|REQUIRED_COLUMNS" automation/importer/conflicts.py
```

Expected: at least three matches (the constant definition, the function definition, and the call site inside `detect_conflicts`).

All checks must pass before you commit.

### 4. Report

In your response, confirm:

- Verification step ran and reported the expected output
- Both fixes applied as described
- Test count before and after
- Any deviations from the instructions and why
- Any ambiguities encountered

Do not push — leave that for Doug.

## What Is Out of Scope

- Do not modify any module other than `commit.py`, `conflicts.py`, `pipeline.py`, `test_importer_commit.py`, and `test_importer_conflicts.py`
- Do not change any mapper logic
- Do not touch `automation/db/`, `automation/workflow/`, `automation/prompts/`, or `espo_impl/`
- Do not refactor anything that isn't directly related to these two fixes
- Do not "improve" anything else you notice
- Do not add new modules or new top-level files
- Do not update the L2 PRD — Doug will add ISS-010 and ISS-011 to Section 16 separately

## Reference

Primary references for these fixes:

- `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`, Section 11.6.2 (Transaction Scope)
- `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`, Section 11.5 (Conflict Detection — severity model)
- `automation/db/client_schema.py` (source of truth for NOT NULL columns when building REQUIRED_COLUMNS)

The original Step 12 prompt is at:
`PRDs/product/crmbuilder-automation-PRD/CLAUDE-CODE-PROMPT-step12-import-processor.md`

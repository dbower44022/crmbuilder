# Claude Code Follow-Up — Step 9: Remove WorkItem.phase column

## Context

You completed Step 9 (database layer) and the work was reviewed. The implementation is largely correct — 168 tests passing, all 25 tables present, both v1.6 schema findings (Dependency UNIQUE, LayoutRow CHECK) correctly applied, DEC-053 tier column correctly added, and CHECK constraints on enumerated TEXT columns broadly applied per the Section 2.3 convention.

One issue was found that needs to be corrected before Step 10 begins.

## The Issue

`WorkItem` in `automation/db/client_schema.py` has a `phase` column with a NOT NULL CHECK constraint:

```sql
phase TEXT NOT NULL CHECK (phase IN (
    'Phase 1', 'Phase 2', 'Phase 3', 'Phase 4', 'Phase 5',
    'Phase 6', 'Phase 7', 'Phase 8', 'Phase 9', 'Phase 10', 'Phase 11'
)),
```

**This column should not exist.** The L2 PRD explicitly resolved this question in Section 14.2.3 (Full Project Inventory):

> "Below the work queue, a collapsible section labeled 'All Work Items' shows every work item in the project grouped by phase. **The application maintains a static mapping from item_type to phase number (for example, entity_prd maps to Phase 2, process_definition maps to Phase 5). This mapping is not stored in the database because it is defined by the methodology and does not vary per client.** Each phase group has a header showing the phase number, phase name, and a completion indicator..."

This was a design decision (Finding 7 from the v1.6 schema validation session). The reasoning: phase is fully derived from item_type via a static, one-to-one mapping that does not change per client. Storing it as a column creates redundant data and the possibility of inconsistency.

Additionally, even if the column were correct in principle, the CHECK constraint enumerates only 11 phases — but the Document Production Process has **12 phases** (see `CLAUDE.md` and `PRDs/process/CRM-Builder-Document-Production-Process.docx`). So the column was both wrong by design and also wrong in its enumeration.

## What I Want From You

### 1. Explain why you added the phase column

Before making the fix, please explain in your response:

- What in the L2 PRD or the Step 9 prompt led you to add this column?
- Did you read Section 14.2.3? If yes, how did you interpret it?
- If you did not read Section 14.2.3, what context drove the decision?
- Are there other places in the L2 PRD where phase appears that may have suggested it should be a column?

This is not a gotcha. The goal is to understand whether the PRD has ambiguous text that should be clarified, or whether the prompt was unclear, or whether something else happened. Future implementation steps will be better if we surface the root cause.

### 2. Remove the column

Make the following changes in `automation/db/client_schema.py`:

- Remove the `phase` column and its CHECK constraint from `WORK_ITEM_TABLE`
- Leave everything else in `WORK_ITEM_TABLE` exactly as it is

### 3. Update tests

In `automation/tests/test_client_schema.py`:

- Remove any test that exercises the `phase` column directly (creates a row with phase, tests the phase CHECK constraint, etc.)
- Update any test that creates a WorkItem row and currently passes a `phase` value — remove the `phase` column and value from the INSERT
- Do **not** delete tests for other WorkItem columns (item_type, status, FK constraints) — those are still required

### 4. Verify

Run:

```bash
uv run pytest automation/tests/ -v
uv run ruff check automation/
```

Both must pass before you commit.

### 5. Commit

Commit message:

```
Remove WorkItem.phase column per L2 PRD Section 14.2.3

Phase is application-level logic derived from item_type via a static
mapping; it should not be stored in the schema. Resolved by Finding 7
of the v1.6 schema validation session.
```

Do not push — leave that for Doug.

## What Is Out of Scope

- Do not modify any other table
- Do not modify the connection, migrations, or init_db modules
- Do not change any other tests beyond what is needed to remove phase references
- Do not add any new functionality
- Do not "improve" anything else you notice

## Reference

Primary reference for this fix:

`PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`, Section 14.2.3 (Full Project Inventory)

Also relevant:

`PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`, Section 6.3 (WorkItem) — confirms the WorkItem table definition and shows that phase is not listed as a column

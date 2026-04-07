# Claude Code Follow-Up — Step 9: Remove WorkItem.phase column

## Context

You completed Step 9 (database layer) and the work was reviewed. The implementation is largely correct — 168 tests passing, all 25 tables present, both v1.6 schema findings (Dependency UNIQUE, LayoutRow CHECK) correctly applied, DEC-053 tier column correctly added, and CHECK constraints on enumerated TEXT columns broadly applied per the Section 2.3 convention.

One issue was found that needs to be corrected before Step 10 begins. The L2 PRD has been updated to v1.7 to resolve the underlying doc-drift that caused the issue — Section 6.3 no longer shows phase as a column, and Section 14.2.3 now contains an explicit item_type-to-phase mapping table aligned to the 12-phase Document Production Process.

## The Issue

`WorkItem` in `automation/db/client_schema.py` has a `phase` column with a NOT NULL CHECK constraint:

```sql
phase TEXT NOT NULL CHECK (phase IN (
    'Phase 1', 'Phase 2', 'Phase 3', 'Phase 4', 'Phase 5',
    'Phase 6', 'Phase 7', 'Phase 8', 'Phase 9', 'Phase 10', 'Phase 11'
)),
```

**This column should not exist.** The L2 PRD v1.7 explicitly resolves this in Section 14.2.3 (Full Project Inventory):

> "The application maintains a static mapping from item_type to phase number, defined in the table below. This mapping is not stored in the database because it is defined by the methodology and does not vary per client. For three item_types (domain_overview, process_definition, domain_reconciliation), the phase number depends on whether the related Domain has is_service = TRUE — services consume Phase 4 (Cross-Domain Service Definition), while regular domains consume Phases 3, 5, and 6."

Section 14.2.3 then contains an explicit table mapping all item_types to their phases. This is application-level logic — not a schema column.

Section 6.3 (the WorkItem table definition) in v1.7 no longer shows phase as a column. The original Step 9 prompt was based on v1.6, which still had phase in Section 6.3 — that doc-drift is what led to the wrong implementation.

This was a design decision (Finding 7 from the v1.6 schema validation session). The reasoning: phase is fully derived from item_type via a static mapping that does not change per client. Storing it as a column creates redundant data and the possibility of inconsistency.

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

# Claude Code Implementation Prompt — Step 9: Database Layer

## Context

You are implementing **Step 9 of the CRM Builder Automation roadmap** — the database layer. The complete design for this work is in the Level 2 PRD at:

`PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`

**Read the L2 PRD first.** Sections 2 through 8 define the database architecture and the complete schema for both the master database and the client database. Section 15 contains the design decisions (DEC-001 through DEC-053) that explain why the schema is structured the way it is. Section 16 contains open issues you should be aware of but do not need to resolve in this step.

This is step 9 of a 16-step roadmap (see Section 17). All design steps (1–8) are complete. Subsequent implementation steps (10–16) will build on the database layer you produce.

## Repository Context

This work goes in the `dbower44022/crmbuilder` repository. Read `CLAUDE.md` at the repo root for general project conventions.

The existing `espo_impl/` package contains the EspoCRM deployment and configuration features (instance management, YAML application, deploy wizard). **Do not modify `espo_impl/`.** The Automation features are a separate concern that manages the requirements lifecycle that *produces* the YAML files.

## Where the Code Goes

Create a new top-level package:

```
automation/
├── __init__.py
├── db/
│   ├── __init__.py
│   ├── master_schema.py      # Master database schema (Section 3)
│   ├── client_schema.py      # Client database schema (Sections 4–8)
│   ├── connection.py         # Connection management, transactions
│   ├── migrations.py         # Versioned schema, upgrade path
│   └── init_db.py            # CLI: initialize a fresh client database
└── tests/
    ├── __init__.py
    ├── test_master_schema.py
    ├── test_client_schema.py
    ├── test_connection.py
    └── test_migrations.py
```

This is a deliberate top-level directory parallel to `espo_impl/`, not a subpackage of it. The `CLAUDE.md` rule against new top-level directories was written about deployment code; Automation is a distinct feature area with its own database, UI mode, and lifecycle.

## Definition of Done

This step is complete when **all** of the following are true:

1. **Master database schema implemented as SQLite**, matching Section 3 of the L2 PRD exactly. The single Client table with all columns, types, and constraints.

2. **Client database schema implemented as SQLite**, matching Sections 4–8 of the L2 PRD exactly. All 20 tables across the four layers (Requirements, Cross-Reference, Management, Audit) plus the Layout layer in Section 8.

3. **All constraints from v1.6 enforced at the database level:**
   - Every PRIMARY KEY, FOREIGN KEY, UNIQUE, and NOT NULL from the schema tables
   - The UNIQUE constraint on `Dependency(work_item_id, depends_on_id)` (Section 6.4)
   - The CHECK constraint on `LayoutRow` ensuring at least one cell is non-null (Section 8.2)
   - CHECK constraints on **every** TEXT column with enumerated values defined in the L2 PRD (Section 2.3 convention). This includes but is not limited to: `WorkItem.item_type`, `WorkItem.status`, `AISession.session_type`, `AISession.import_status`, `ChangeLog.change_type`, `Process.tier`, `GenerationLog.document_type`. **Read each table definition in Sections 4–8 and Section 13.11.1 carefully** — every column whose description enumerates valid values needs a CHECK constraint.

4. **Common conventions applied to every table** (Section 2.3): `id INTEGER PRIMARY KEY AUTOINCREMENT`, `created_at TIMESTAMP`, `updated_at TIMESTAMP`, plus `created_by_session_id` FK on tables created through AI sessions.

5. **Connection management module** with:
   - Open/close functions for both master and client databases
   - Context manager support (`with` statement)
   - Transaction support (begin, commit, rollback)
   - `PRAGMA foreign_keys = ON` set on every connection (SQLite does not enforce FKs by default)

6. **Migration support:**
   - A `schema_version` table in both master and client databases
   - A migration runner that applies versioned migrations in order
   - Initial migration (version 1) creates the full schema
   - The migration runner is idempotent — running it on an up-to-date database is a no-op

7. **CLI script** (`automation/db/init_db.py`) that:
   - Takes a path argument for where to create a new client database
   - Creates the file, runs migrations, and exits cleanly
   - Can be invoked as `uv run python -m automation.db.init_db /path/to/client.db`

8. **pytest test suite** with **tests written alongside each module as it is built**, not at the end. Coverage requirements:
   - Every table can be created and dropped cleanly
   - Every FK relationship rejects invalid references
   - Every UNIQUE constraint rejects duplicates
   - Every CHECK constraint rejects out-of-enumeration values
   - Every NOT NULL constraint rejects null inserts
   - The LayoutRow at-least-one-cell CHECK rejects fully-null rows
   - The Dependency UNIQUE constraint rejects duplicate dependency pairs
   - Connection context manager properly closes connections on exception
   - Transactions roll back on exception
   - Migration runner is idempotent
   - Tests use temporary database files (`tmp_path` fixture), never touch real data

9. **All tests pass**: `uv run pytest automation/tests/ -v`

10. **Linter clean**: `uv run ruff check automation/`

## Working Style

- **Read the L2 PRD before writing any code.** The schema is fully specified there. Do not improvise table structures, column names, or constraint names — match the PRD exactly.
- **Write tests alongside each module**, not at the end. When you implement `master_schema.py`, write `test_master_schema.py` in the same step. When you implement the connection module, write its tests immediately.
- **Implement in this order:** master schema → client schema → connection → migrations → init_db CLI. Each layer depends on the previous.
- **Surface ambiguities, do not invent answers.** If the L2 PRD is unclear about a column type, constraint, or behavior, stop and ask before proceeding. Do not guess.
- **No interaction with `espo_impl/`.** This package is fully independent.
- **No GUI code in this step.** The UI is step 15. This step is database only.
- **No AI integration in this step.** The Prompt Generator is step 11. This step is database only.

## Out of Scope for This Step

These are listed explicitly so you do not accidentally do them:

- Workflow Engine logic (status transitions, dependency graph construction) — that is step 10
- Prompt generation — step 11
- Import processing — step 12
- Impact analysis — step 13
- Document generation — step 14
- User interface — step 15
- Integration testing with CBM data — step 16
- Modifying `espo_impl/` in any way
- Creating any UI components
- Any business logic beyond what is needed to enforce the schema

## Reference Documents

Primary: `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`

Sections to read carefully before starting:
- Section 2: Database Architecture (two-database model, common conventions)
- Section 3: Master Database Schema
- Section 4: Client Database Schema — Requirements Layer (Domain, Entity, Field, FieldOption, Relationship, Persona, BusinessObject, Process, ProcessStep, Requirement)
- Section 5: Client Database Schema — Cross-Reference Layer (ProcessEntity, ProcessField, ProcessPersona)
- Section 6: Client Database Schema — Management Layer (Decision, OpenIssue, WorkItem, Dependency)
- Section 7: Client Database Schema — Audit Layer (AISession, ChangeLog, ChangeImpact)
- Section 8: Client Database Schema — Layout Layer (LayoutPanel, LayoutRow, LayoutTab, ListColumn)
- Section 13.11.1: GenerationLog (referenced for CHECK constraint)
- Section 15: Decisions (DEC-053 in particular for the tier column)

You may also find this useful for context on how the database will be used downstream, but **do not implement any of this functionality in step 9**:
- Section 9: Workflow Engine (explains how WorkItem status transitions work)
- Section 11.10.1: Import commit transaction (explains transaction patterns)

## Final Check

Before declaring this step complete, verify:

- [ ] Every table in Sections 3–8 exists in the code with the exact column names from the PRD
- [ ] Every constraint mentioned in the PRD is enforced in the schema
- [ ] Every enumerated TEXT column has a CHECK constraint
- [ ] All tests pass
- [ ] Linter is clean
- [ ] The init_db CLI successfully creates a fresh client database that can be inspected with `sqlite3 /path/to/client.db ".schema"`
- [ ] No code in `espo_impl/` was modified
- [ ] No work outside the step 9 scope was performed

When complete, commit with a descriptive message and report what was built. Do not push — leave that for Doug.

# Claude Code Implementation Prompt — Step 16: CBM Data Importer + Integration Tests

## Context

You are implementing **Step 16 of the CRM Builder Automation roadmap** — the **final step**. With Steps 9–15 complete, the application has all the production code it needs. Step 16 validates that the system actually works end-to-end with real data by importing the existing Cleveland Business Mentors (CBM) requirements documents into a client database and running integration tests against the populated state.

This is qualitatively different from Steps 9–15. It is **not** about building new production features. It has two phases:

- **Phase A — CBM Data Importer.** Build a one-time importer that reads the existing CBM `.docx` PRDs from the `dbower44022/ClevelandBusinessMentoring` repository and populates a CBM client database in the automation system. CBM is the proof-of-concept client; this importer is the bridge from "existing manual workflow" to "automation system." The importer is not part of the long-term application — it exists to bootstrap CBM's client database from its current paper trail.

- **Phase B — Integration Tests.** With CBM data loaded, write a small set of integration tests that exercise the full pipeline against the populated database. These tests validate that the eight engines (db, workflow, prompts, importer, impact, docgen, plus the UI logic helpers) work together correctly with realistic data, not just synthetic fixtures.

This is step 16 of 16. After this, the automation roadmap is complete.

## Repository Context

This work goes in the `dbower44022/crmbuilder` repository. Read `CLAUDE.md` at the repo root for general project conventions.

You will also need to read content from `dbower44022/ClevelandBusinessMentoring` (the CBM repo). The CBM repo contains the existing requirements documents in Word format. Read those documents to understand the structure, but do NOT modify them. The CBM repo is owned by Doug separately and is the source of truth for CBM's current requirements.

## Where the Code Goes

```
automation/
├── (existing packages — Steps 9-15 complete and locked)
└── cbm_importer/                       # NEW — Phase A
    ├── __init__.py
    ├── importer.py                     # CBMImporter class — public API
    ├── extractors/                     # One extractor per source document type
    │   ├── __init__.py
    │   ├── master_prd.py               # Reads CBM-Master-PRD.docx
    │   ├── entity_inventory.py         # Reads CBM-Entity-Inventory.docx
    │   ├── entity_prd.py               # Reads PRDs/entities/{Name}-Entity-PRD.docx
    │   ├── domain_overview.py          # Reads PRDs/{domain}/CBM-Domain-Overview-*.docx (and SubDomain variants)
    │   ├── process_document.py         # Reads PRDs/{domain}/{PROCESS-CODE}.docx
    │   └── domain_prd.py               # Reads PRDs/{domain}/CBM-Domain-PRD-*.docx
    ├── docx_helpers.py                 # Shared python-docx utilities for table/heading parsing
    ├── reconciliation.py               # Cross-document validation (e.g., entity references match across PRDs)
    └── cli.py                          # Command-line entry point: `python -m automation.cbm_importer.cli ...`

automation/tests/integration/           # NEW — Phase B
    ├── __init__.py
    ├── conftest.py                     # Fixture: populated CBM client database (cached for speed)
    ├── test_cbm_pipeline.py            # End-to-end pipeline tests against CBM data
    ├── test_cbm_workflow.py            # Workflow engine state transitions on CBM work items
    ├── test_cbm_impact.py              # Impact analysis on real CBM relationships
    ├── test_cbm_docgen.py              # Document generation against CBM data
    └── test_cbm_ui_logic.py            # UI logic modules (dashboard, work item, browser, documents) against CBM data
```

**Tests live in a new `automation/tests/integration/` subdirectory** to keep them separate from the unit tests in `automation/tests/`. Integration tests are slower (they import real .docx files and run multi-engine flows) and may be marked with a pytest marker so they can be run separately if desired.

## Foundation — Existing API Surface

You will not write any new engines. Phase A's importer reads .docx files and writes to the database via the existing schema. Phase B's tests call the existing engines.

### What you'll use

- **`automation.db.connection`** — `connect()`, `transaction()` for the importer's writes
- **`automation.db.client_schema`** — the target schema for the importer
- **`automation.db.migrations`** — `run_master_migrations()`, `run_client_migrations()` to set up the test databases
- **`automation.workflow.engine`** — `WorkflowEngine` for Phase B workflow tests
- **`automation.prompts.generator`** — `PromptGenerator` for Phase B prompt tests
- **`automation.importer.pipeline`** — `ImportProcessor` for Phase B (note: this is the AI-session import processor, not the CBM importer; they have different purposes)
- **`automation.impact.engine`** — `ImpactAnalysisEngine` for Phase B impact tests
- **`automation.docgen.generator`** — `DocumentGenerator` for Phase B docgen tests
- **`automation.ui.dashboard.dashboard_logic`** and other UI logic helpers — for Phase B UI logic tests

The terminology is unfortunately overloaded: there's the existing **`automation.importer`** (Step 12, the AI session output → database pipeline) and the new **`automation.cbm_importer`** (Step 16, the .docx → database bootstrapper). The names are deliberately distinct but it's worth keeping straight.

### What CBM data looks like

The CBM repo has this structure:

```
PRDs/
├── CBM-Master-PRD.docx                      # Master PRD (Phase 1 source)
├── CBM-Entity-Inventory.docx                # Entity Inventory (Phase 2a source)
├── entities/
│   ├── Contact-Entity-PRD.docx              # Entity PRDs (Phase 2b source)
│   ├── Account-Entity-PRD.docx
│   ├── Engagement-Entity-PRD.docx
│   ├── Session-Entity-PRD.docx
│   └── Dues-Entity-PRD.docx
├── MN/                                      # Mentoring domain
│   ├── CBM-Domain-PRD-Mentoring.docx        # Reconciled Domain PRD (Phase 6 source)
│   ├── MN-INTAKE.docx                       # Process docs (Phase 5 source)
│   ├── MN-MATCH.docx
│   ├── MN-ENGAGE.docx
│   ├── MN-CLOSE.docx
│   └── MN-INACTIVE.docx
├── MR/                                      # Mentor Recruitment domain
│   ├── CBM-Domain-PRD-MentorRecruitment.docx
│   ├── MR-RECRUIT.docx
│   ├── MR-APPLY.docx
│   ├── MR-ONBOARD.docx
│   ├── MR-MANAGE.docx
│   └── MR-DEPART.docx
└── CR/                                      # Client Recruiting domain
    ├── CBM-Domain-Overview-ClientRecruiting.docx
    ├── PARTNER/
    │   ├── CBM-SubDomain-Overview-Partner.docx
    │   ├── CR-PARTNER-PROSPECT.docx
    │   └── CR-PARTNER-MANAGE.docx
    ├── MARKETING/
    │   └── CBM-SubDomain-Overview-Marketing.docx
    └── EVENTS/, REACTIVATE/                 # In progress, may be empty
```

The CBM repo's domain structure is the **target shape** the automation database expects. The MN domain is the most complete (Domain PRD reconciled). The MR domain has a Domain PRD too. The CR domain is partial (has Domain Overview but no reconciled Domain PRD yet, and only the PARTNER sub-domain has process docs). The FU domain doesn't exist yet.

**Important for the importer:** these documents were generated by hand with the help of AI sessions. They follow consistent formatting (the existing Node.js generator templates establish the conventions), but they are not perfectly machine-readable. The importer must be tolerant of small variations and report parsing failures clearly rather than crashing.

### Reading the CBM repo

You do not have the CBM repo checked out locally. To read its files for the importer, you need to either:

1. **Clone it temporarily** during the integration test run (using the GitHub PAT from memory edit #3, or via `git clone https://github.com/dbower44022/ClevelandBusinessMentoring.git`)
2. **Have Doug check out a copy** to a known local path that the importer reads from

**Recommended approach:** the CBM importer takes a `cbm_repo_path` argument at construction. For development and testing, Doug clones the CBM repo to a known location (e.g., `~/repos/ClevelandBusinessMentoring`). The integration test fixture uses an environment variable `CBM_REPO_PATH` to find the repo, with a sensible default. If the variable is unset and the default doesn't exist, the integration tests are skipped with a clear message.

This avoids cloning during test runs (slow and network-dependent) while allowing the tests to work on Doug's machine and in any other environment with the CBM repo locally available.

## Phase A — CBM Data Importer

### Goal

Read the CBM `.docx` PRDs and produce a populated CBM client database that the rest of the automation system can operate against. The importer runs once per client (or once per re-import after major source changes); it is not part of the production application's runtime workflow.

### Definition of Done — Phase A

1. **CBMImporter class** (`importer.py`) is the public API:

```python
class CBMImporter:
    def __init__(
        self,
        cbm_repo_path: str | Path,
        client_db_path: str | Path,
        master_db_path: str | Path | None = None,
    ): ...
        # cbm_repo_path: root of the CBM repo (the directory containing PRDs/)
        # client_db_path: target client database; created if it doesn't exist
        # master_db_path: target master database; created if it doesn't exist;
        #   the CBM client record is inserted here on first import

    def run(self) -> ImportSummary:
        """Run the full import.

        Reads all CBM PRDs in dependency order, populates the client and
        master databases, and returns a summary of what was imported.

        Idempotent: re-running on an existing database updates records
        that have changed and reports counts.
        """

    def run_master_prd_only(self) -> ImportSummary:
        """Import just the Master PRD. Used for incremental imports."""
```

2. **Extractor modules** (`extractors/`) — one per source document type. Each extractor:
   - Takes a path to a .docx file
   - Returns a structured dataclass of extracted records (not yet written to the database)
   - Does not depend on other extractors (caller chains them)
   - Logs warnings for ambiguous content rather than raising

   The six extractors:
   - **master_prd.py** — extracts Personas, Domains, Sub-Domains, Process inventory from `CBM-Master-PRD.docx`
   - **entity_inventory.py** — extracts BusinessObjects (entities) and their classifications from `CBM-Entity-Inventory.docx`
   - **entity_prd.py** — extracts Entity, Field, FieldOption, Relationship, LayoutPanel/Row/Tab, ListColumn from `entities/{Name}-Entity-PRD.docx`
   - **domain_overview.py** — extracts Domain.domain_overview_text and any sub-domain references from `{domain}/CBM-Domain-Overview-*.docx` and `{domain}/{sub}/CBM-SubDomain-Overview-*.docx`
   - **process_document.py** — extracts Process, ProcessStep, Requirement, ProcessEntity, ProcessField, ProcessPersona from `{domain}/{PROCESS-CODE}.docx`
   - **domain_prd.py** — extracts Domain.domain_reconciliation_text plus any reconciliation Decision records from `{domain}/CBM-Domain-PRD-*.docx`

   The extractors should match the formatting conventions in the existing Node.js generator templates at `PRDs/process/templates/generate-process-doc-template.js` and `generate-entity-prd-template.js` in the crmbuilder repo. **Read those templates first** to understand the document structure they produce — the importer is essentially the inverse operation.

3. **docx_helpers.py** — shared utilities:
   - `read_docx(path) -> Document` — load a .docx file
   - `iter_tables(doc) -> Iterator[Table]` — iterate tables
   - `iter_paragraphs(doc) -> Iterator[Paragraph]` — iterate paragraphs
   - `find_section(doc, heading_text) -> tuple[int, int]` — locate paragraphs between two headings
   - `parse_table_to_dicts(table, headers) -> list[dict]` — parse a table into row dicts using header row keys
   - `extract_text(element) -> str` — get the plain text from a paragraph or cell, stripping formatting

   These helpers are reused across all extractors. They are pure-Python (no Qt) and can be tested independently.

4. **Reconciliation module** (`reconciliation.py`):
   - After all extractors run, validate cross-document references:
     - Every Entity referenced in a Process Document exists in the Entity Inventory
     - Every Field referenced in a Process Document exists in the relevant Entity PRD
     - Every Persona referenced in a Process Document exists in the Master PRD
     - Every Domain code referenced anywhere matches a Domain in the Master PRD
   - Reports inconsistencies as warnings without halting the import
   - The administrator (or Doug) can decide whether to fix the source documents or accept the warnings

5. **Idempotent writes** — running the importer twice on the same CBM repo with no changes should produce zero database changes the second time. This means:
   - Use `INSERT ... ON CONFLICT` or check-then-insert/update for every record type
   - Match by natural key (Domain.code, Entity.code, Process.code, Persona.code, Field.name within entity, etc.)
   - On update, only modify fields that actually changed
   - Track ChangeLog entries for updates so the audit trail records the re-import

6. **WorkItem creation** — after importing the source data, the importer must create the WorkItem records and Dependency edges that match the imported state. Use `WorkflowEngine.after_master_prd_import()` and `WorkflowEngine.after_business_object_discovery_import()` (Steps 10's existing methods) to wire up the work items. After both are called, the engine creates work items for all the entity_prd, domain_overview, process_definition, and domain_reconciliation records that were imported, with the correct dependencies.

   **Important:** the importer does NOT mark these work items as `complete`. They start as `not_started` or `ready` per the workflow engine's normal logic, even though their corresponding records already exist in the database. This is intentional — Step 16's tests will exercise transitioning them through the workflow.

   **However:** for any work item whose source document already exists in the CBM repo (and was imported), the importer MAY optionally mark them complete to reflect that the work was done outside the automation system. **Make this an importer option, off by default.** The default is to leave them in their natural workflow state so Phase B tests can exercise the transitions; the option exists for production use where the administrator wants to mirror the actual project state.

7. **CLI entry point** (`cli.py`):

   ```bash
   python -m automation.cbm_importer.cli \
     --cbm-repo /path/to/ClevelandBusinessMentoring \
     --client-db /path/to/cbm-client.db \
     --master-db /path/to/master.db
   ```

   Optional flags:
   - `--mark-complete` — mark work items complete for documents that exist in the CBM repo
   - `--master-prd-only` — incremental import of just the Master PRD
   - `--dry-run` — parse and validate without writing

   The CLI prints a summary report at the end: number of records imported by table, number of warnings from reconciliation, time elapsed.

8. **Tests for Phase A:**
   - **Unit tests for `docx_helpers.py`** — pure-Python tests against tiny synthetic .docx files (or the existing Node.js generator output if you can produce a small one for fixtures)
   - **Extractor tests** — for each extractor, a test that loads a small representative .docx fixture and asserts the right records come out. Use the actual CBM repo files as fixtures if available, otherwise build minimal fixtures.
   - **Importer end-to-end test** — uses a temp directory with a CBM repo clone (or skip if `CBM_REPO_PATH` env var is unset), runs `CBMImporter.run()`, and asserts the resulting database has the expected record counts for the MN domain (which is the most complete).
   - **Idempotency test** — run the importer twice and assert the second run produces zero ChangeLog entries.
   - **Reconciliation test** — feed in a known-inconsistent fixture (e.g., process doc references a field that doesn't exist in the entity PRD) and assert the warning is reported.

9. **Linter clean** and **all tests pass** for Phase A in isolation before moving to Phase B.

### Working style — Phase A

- **Read the CBM repo before writing extractor code.** Don't guess at the document structure. Open the actual .docx files (you can use python-docx in a scratch script) and inspect their tables and paragraphs.
- **Read the existing Node.js generator templates** (`PRDs/process/templates/generate-process-doc-template.js` and `generate-entity-prd-template.js`) — they document the structure your extractors must reverse-engineer.
- **Start with the easiest extractor first** — probably `master_prd.py` since it has flat structure (lists of personas, domains, processes). Then `entity_prd.py` (rich table-driven format). Then `process_document.py` (most complex, with steps, requirements, and cross-references).
- **Tolerate variation.** Real .docx files have inconsistencies — extra whitespace, slightly varied heading text, missing optional sections. Log warnings and continue rather than crashing.
- **Surface ambiguities, do not invent answers.** Examples to flag:
  - The CBM repo has both `MN-INTAKE.docx` and `Mentoring -MN-INTAKE-PRD.pdf`. Are the .docx files always authoritative, or do you need to handle a mix?
  - Some CBM directories contain `SESSION-PROMPT-*.md` files that pre-date the .docx files. Should the importer read those for any reason, or only the .docx?
  - The Node.js templates produce documents with specific table structures, but Doug may have manually edited some documents after generation. How do you detect and report a deviation that breaks parsing?
  - The CR domain has incomplete content (no reconciled Domain PRD, only some processes). Does the importer skip incomplete domains, import what's there, or fail?

## Phase B — Integration Tests

### Goal

Validate that all eight engines work together against real CBM data. These tests are not exhaustive — they are smoke tests that prove the pipeline isn't fundamentally broken when fed realistic input. Detailed unit tests are already covered in `automation/tests/`.

### Definition of Done — Phase B

10. **Integration test fixture** (`automation/tests/integration/conftest.py`):
    - A pytest fixture that returns a populated CBM client database connection
    - The fixture caches the database between tests in the same session for speed (e.g., as a temporary file that's reused)
    - If `CBM_REPO_PATH` env var is unset and the default path doesn't exist, the fixture marks all integration tests as skipped with a clear message
    - Cleanup runs after the test session, not after each test

11. **Pipeline test** (`test_cbm_pipeline.py`):
    - Loads the CBM client database via the fixture
    - Asserts the expected number of Domains (4 — MN, MR, CR, FU — note FU may have zero processes), Entities (5 — Contact, Account, Engagement, Session, Dues), Personas (whatever the CBM Master PRD lists)
    - Asserts at least one entity has fields, at least one process has steps, at least one process has requirements
    - Validates that the WorkItem table has been populated and the dependency graph is intact (at least one Dependency row per work item that has dependencies)

12. **Workflow test** (`test_cbm_workflow.py`):
    - For a known-complete work item (e.g., the master_prd work item), exercises `engine.start()` → `engine.complete()` and asserts the downstream work items transition correctly
    - For an entity_prd work item, simulates the full lifecycle: start → mark complete → revise → mark complete again
    - Asserts that revision cascades to downstream items per Section 9.7.2

13. **Impact test** (`test_cbm_impact.py`):
    - Picks a real CBM Field record (e.g., a field on the Contact entity)
    - Calls `impact.analyze_proposed_change("Field", field_id, "update", new_values={...})`
    - Asserts the impact set contains the expected downstream records (processes that use this field, layouts that display it)
    - Picks a real CBM Field and tests `change_type="delete"` — asserts transitive tracing surfaces dependent records

14. **Documentation generation test** (`test_cbm_docgen.py`):
    - **First, this test addresses the Step 15c project_folder gap.** The test fixture provides a temporary project folder that the DocumentGenerator can write to.
    - For a complete entity_prd work item, calls `docgen.generate(wi_id, mode="final")` and asserts:
      - The output file exists at the expected path (`{project_folder}/PRDs/entities/{EntityName}-Entity-PRD.docx`)
      - The file is a valid .docx that opens with python-docx
      - The file contains the entity's name and at least one field name from the database
    - For a process_definition work item, generates the process document and asserts the same
    - For yaml_generation, generates and asserts the YAML files exist in `{project_folder}/programs/`
    - **This test is the first end-to-end validation that document generation actually works** — Steps 14 and 15c built the components, but no test ran the full data → file flow with realistic data

15. **UI logic test** (`test_cbm_ui_logic.py`):
    - Calls `dashboard_logic.assemble_summary(conn)` and asserts the summary has the right work item counts by status
    - Calls `dashboard_logic.assemble_work_queue(conn)` and asserts the queue contains expected items
    - Calls `work_item_logic.get_dependencies(conn, wi_id)` for a known item and asserts upstream/downstream counts
    - Calls `browser_logic.build_tree(conn)` and asserts the tree has the expected structure (4 domains, 5 entities, etc.)
    - Calls `documents_logic.assemble_inventory(conn, master_conn=None)` and asserts the inventory groups match Section 13.2

16. **The integration tests are marked with `@pytest.mark.integration`** so they can be excluded from the default test run if desired. The default `pytest automation/tests/` should still run them; the marker is for selective filtering. Document the marker in `pyproject.toml` if necessary.

17. **Project folder wiring fix** — as part of Phase B, the Step 15c gap on `DocumentGenerator(project_folder=None)` must be addressed. The fix is small: the Documents view in `automation/ui/documents/` should accept a project folder from one of:
    - The client context (preferred — derived from the instance association in Section 14.9.3)
    - A configuration setting on the Client record (fallback)
    - An explicit user prompt the first time generation is attempted

    **Pick the simplest viable option.** The integration test bypasses the UI entirely and constructs DocumentGenerator with an explicit path, so the test does not depend on this fix. But the fix is necessary for the production application to actually generate documents through the UI. Implement it as a small modification to `automation/ui/documents/documents_view.py` reading from `automation.ui.client_context.ClientContext` (if that's where instance association lives) or from a similar source.

    **This is the only production code change in Step 16.** Everything else is the importer (Phase A) and tests (Phase B).

18. **All tests pass:** `uv run pytest automation/tests/ -v` with the integration tests included. Target: 1017 existing + new importer tests + new integration tests.

19. **Linter clean:** `uv run ruff check automation/`

### Working style — Phase B

- **Phase B depends on Phase A.** Don't write integration tests until the importer can actually populate a CBM database.
- **Run the importer manually first.** Before writing any integration test, run `python -m automation.cbm_importer.cli --cbm-repo ...` against a real CBM checkout and inspect the resulting database with sqlite3 CLI. Verify the data looks right before depending on it for tests.
- **Tests should be deterministic.** If the CBM repo changes, the tests may need updating. Make assertions tolerant where appropriate (e.g., "at least 4 domains" rather than "exactly 4 domains") so small CBM updates don't break the tests.
- **Document the integration test setup in `automation/tests/integration/conftest.py` docstring.** Include instructions for how to clone CBM, set the env var, and run the integration tests.

## Out of Scope for Step 16

- New production features (Steps 9-15 are complete)
- UI changes beyond the project_folder wiring fix
- Modifications to any existing engine module
- A general-purpose .docx parser (the importer is CBM-specific by design)
- A reverse importer (database → .docx) — that's the existing `automation.docgen` module
- Modifying the CBM repository itself
- HTTP / API calls

## Reference Documents

Primary: `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`

Sections to read:
- **Section 13** — Document Generator data model. The importer is the inverse operation; the table structure here tells you what records the extractors must produce.
- **Section 9** — Workflow Engine. The importer calls `after_master_prd_import()` and `after_business_object_discovery_import()` to wire up work items.
- **Section 11.3** — Payload-to-record mapping per work item type. The importer's extractors produce records analogous to what the AI session import processor (Step 12) produces from JSON, but sourced from .docx instead.
- **Section 17** — Next Steps. Step 16 is the last item.

External references:
- `dbower44022/ClevelandBusinessMentoring` — the CBM repo whose .docx files the importer reads
- `PRDs/process/templates/generate-process-doc-template.js` — Node.js generator template for process documents (the format your `process_document.py` extractor reverses)
- `PRDs/process/templates/generate-entity-prd-template.js` — Node.js generator template for Entity PRDs (the format your `entity_prd.py` extractor reverses)

## Final Check

Before declaring Step 16 complete, verify:

- [ ] **Phase A:**
  - [ ] CBMImporter class can run end-to-end against a real CBM repo checkout
  - [ ] The resulting client database contains records for at least the MN domain (Master PRD, Entity Inventory, Contact entity, MN processes, MN domain overview, MN domain PRD)
  - [ ] Re-running the importer produces zero ChangeLog entries (idempotency)
  - [ ] Reconciliation warnings are reported for inconsistencies
  - [ ] Unit tests for docx_helpers and each extractor pass
  - [ ] CLI entry point works

- [ ] **Phase B:**
  - [ ] Integration test fixture loads a populated CBM database
  - [ ] All five integration test files have at least one passing test
  - [ ] The docgen integration test produces actual .docx files in a temp directory
  - [ ] The project_folder wiring fix in `documents_view.py` works (Doug verifies manually)
  - [ ] Integration tests are marked with `@pytest.mark.integration`
  - [ ] Integration tests skip cleanly when `CBM_REPO_PATH` is unset

- [ ] **Standard checks:**
  - [ ] `grep -rn "phase TEXT" automation/db/` returns zero matches
  - [ ] `grep -rn "anthropic.com\|api\.anthropic" automation/cbm_importer/ automation/tests/integration/` returns zero matches
  - [ ] `grep -rn "PySide6" automation/cbm_importer/` returns zero matches (the importer is headless)
  - [ ] All tests pass: `uv run pytest automation/tests/ -v` (target: 1017 existing + new importer tests + new integration tests)
  - [ ] Linter is clean
  - [ ] No code in `automation/db/`, `automation/workflow/`, `automation/prompts/`, `automation/importer/`, `automation/impact/`, `automation/docgen/`, or `automation/ui/` was modified except for the project_folder wiring fix in `documents_view.py`
  - [ ] Any deviations from this prompt are documented in your final report
  - [ ] Any ambiguities encountered (especially around CBM document parsing) are documented in your final report

When complete, commit with a descriptive message. **Step 16 may be split into two commits**: one for Phase A (importer) and one for Phase B (integration tests + project_folder fix), so each can be reviewed independently. Do not push — leave that for Doug.

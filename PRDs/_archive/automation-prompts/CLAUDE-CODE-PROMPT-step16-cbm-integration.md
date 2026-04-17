# Claude Code Implementation Prompt — Step 16: CBM Integration

## Context

You are implementing **Step 16 of the CRM Builder Automation roadmap** — the final step. The full 16-step roadmap is in Section 17 of the L2 PRD, and this step closes it out.

The complete design is in the Level 2 PRD at `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`. Step 16 is loosely scoped in Section 17 as "Integration testing with CBM data — end-to-end validation using Cleveland Business Mentors as the proof-of-concept client." This prompt makes the scope concrete.

Steps 9 through 15c are complete: 1017 tests passing, the full Requirements mode UI works, the Document Generator produces all 8 document types, the Impact Analysis Engine traces changes, and the Import Processor handles the seven-stage pipeline. What's missing is **a populated CBM client database to actually test against**. The application has been built; nothing has run end-to-end with real data.

## What Step 16 Is

Step 16 has two parts that must happen in order:

**Part 1 — CBM PRD Importer.** The CBM project's existing Word documents in the `dbower44022/ClevelandBusinessMentoring` repository contain all the domain knowledge — Master PRD, Entity Inventory, Entity PRDs, Process documents, Domain PRDs. These documents need to be parsed and imported into a CBM client database in the format the Steps 9–15 system expects. Without this, the automation system has no data to operate on.

This is a **one-time importer**, not a general-purpose tool. It exists to bootstrap the CBM client database from the existing Word documents so the rest of the system can operate. After bootstrap, normal operation is administrator-driven through the UI.

**Part 2 — Integration Test Suite.** A small set of end-to-end tests that load the populated CBM database and exercise the full pipeline: Workflow Engine, Prompt Generator, Import Processor, Impact Analysis Engine, Document Generator. These are not unit tests — they validate that the components work together against real data.

There is also one **infrastructure fix** that must happen first: the Document Generator's `project_folder` is currently passed as `None` from the Documents view (deferred to Step 16 in the Step 15c review). This needs to be wired up so document generation actually works end-to-end.

## What Step 16 Is NOT

- **Not** a manual UI walkthrough. Doug will do that separately after this step lands. Your job is to make sure the system has data and the integration tests pass.
- **Not** a full CBM data import that handles every edge case. The CBM Word documents have been authored carefully but they will have inconsistencies. Importer is allowed to flag records it cannot map cleanly and skip them, as long as the skips are reported clearly.
- **Not** a refactor of any existing automation code. Steps 9 through 15c are locked. The only modification authorized in this step is the project_folder wiring fix.
- **Not** a replacement for the existing CBM Word documents. Those documents stay where they are. The importer reads from them and writes into the SQLite database.

## Repository Context

This work spans **two repositories**:

1. **`dbower44022/crmbuilder`** — where the importer code, tests, and project_folder fix live
2. **`dbower44022/ClevelandBusinessMentoring`** — the source repository containing the CBM Word documents to import

Read `CLAUDE.md` at the crmbuilder repo root for general project conventions. The CBM repo has its own CLAUDE.md describing the document organization — read it before parsing any files.

The CBM repo is structured as:

```
ClevelandBusinessMentoring/
├── PRDs/
│   ├── CBM-Master-PRD.docx                  # Master PRD (Section 13.3.1)
│   ├── CBM-Entity-Inventory.docx            # Entity Inventory (Section 13.3.2)
│   ├── entities/
│   │   ├── Contact-Entity-PRD.docx          # One per entity (Section 13.3.3)
│   │   ├── Account-Entity-PRD.docx
│   │   ├── Engagement-Entity-PRD.docx
│   │   ├── Session-Entity-PRD.docx
│   │   └── Dues-Entity-PRD.docx
│   ├── MN/                                  # Mentoring domain
│   │   ├── CBM-Domain-PRD-Mentoring.docx    # Domain Reconciliation (Section 13.3.6)
│   │   ├── MN-INTAKE.docx                   # Process Document (Section 13.3.5)
│   │   ├── MN-MATCH.docx
│   │   ├── MN-ENGAGE.docx
│   │   ├── MN-INACTIVE.docx
│   │   └── MN-CLOSE.docx
│   ├── MR/                                  # Mentor Recruitment domain
│   │   ├── CBM-Domain-PRD-MentorRecruitment.docx
│   │   ├── MR-RECRUIT.docx
│   │   ├── MR-APPLY.docx
│   │   ├── MR-ONBOARD.docx
│   │   ├── MR-MANAGE.docx
│   │   └── MR-DEPART.docx
│   ├── CR/                                  # Client Recruiting domain (partial)
│   │   ├── PARTNER/, MARKETING/, EVENTS/, REACTIVATE/  (sub-domains)
│   │   └── various .docx files
│   ├── services/                            # Cross-Domain Services
│   │   └── NOTES/
│   │       └── NOTES-MANAGE.docx
│   └── WorkflowDiagrams/                    # PNG files for process workflow embeds
└── CLAUDE.md
```

The Word documents share consistent structural conventions (header table, numbered sections, field tables with specific column widths). You can see the field table convention and other formatting details in the existing CBM documents — read 2-3 process documents and 1-2 entity PRDs to understand the structure before writing the parser.

## Where the Code Goes

### Part 0 — Infrastructure fix (commit 1)

```
automation/ui/documents/documents_view.py     # MODIFY: derive project_folder from instance association
automation/ui/mode_integration/instance_association.py   # MODIFY (if needed): add helper to look up project_folder by client
```

### Part 1 — CBM importer (commit 2)

```
automation/
└── cbm_import/                          # NEW package
    ├── __init__.py
    ├── importer.py                      # CBMImporter class — public API
    ├── docx_parser.py                   # Pure Python: extract structured data from .docx files
    ├── parser_logic.py                  # Pure Python: section detection, header table parsing, list extraction
    ├── parsers/
    │   ├── __init__.py
    │   ├── master_prd.py                # Parse CBM-Master-PRD.docx → Personas + Domains + processes inventory
    │   ├── entity_inventory.py          # Parse CBM-Entity-Inventory.docx → BusinessObjects + Entity stubs
    │   ├── entity_prd.py                # Parse entities/*.docx → Entity + Field + Relationship + Layout records
    │   ├── process_document.py          # Parse MN/MR/CR/*.docx → Process + ProcessStep + Requirement + cross-references
    │   └── domain_prd.py                # Parse domain reconciliation .docx → Domain narrative + Decision records
    ├── reporter.py                      # Generate import report (parsed, skipped, warnings)
    └── cli.py                           # Command-line entry point: python -m automation.cbm_import [path]
```

### Part 2 — Integration tests (commit 3)

```
automation/
└── tests/
    ├── integration/                     # NEW directory
    │   ├── __init__.py
    │   ├── conftest.py                  # Fixtures: imported CBM database, populated work items
    │   ├── test_cbm_importer.py         # Import a small CBM subset, assert records exist
    │   ├── test_cbm_workflow.py         # Walk through phases on CBM data
    │   ├── test_cbm_prompt_generation.py  # Generate prompts for CBM work items end-to-end
    │   ├── test_cbm_impact_analysis.py  # Make a change, verify impact tracing
    │   └── test_cbm_document_generation.py  # Generate docs from CBM data, verify output files
    └── fixtures/
        └── cbm_subset/                  # NEW: minimal CBM data subset for fast tests
            ├── Master-PRD-subset.docx   # A trimmed Master PRD with one domain
            ├── Entity-Inventory-subset.docx
            ├── entities/
            │   └── Contact-Entity-PRD-subset.docx
            └── MN/
                ├── MN-INTAKE-subset.docx
                └── CBM-Domain-PRD-Mentoring-subset.docx
```

The fixtures should be hand-crafted minimal versions, not full copies of CBM. Full CBM has hundreds of fields and dozens of processes; the integration tests need to run in seconds, not minutes. The full CBM import is exercised by the importer's CLI when Doug runs it manually.

## Foundation — Existing API Surface

You will use every engine from Steps 9–15. The importer writes through the engines where possible rather than directly to the database, because the engines enforce invariants (status transitions, AISession lifecycle, ChangeLog entries).

### Database — `automation.db.connection`

```python
from automation.db.connection import open_connection, connect, transaction
from automation.db.init_db import init_client_db, init_master_db
```

Use `init_client_db(path)` to create a fresh client database for CBM. Use `init_master_db(path)` for the master database. Both apply the schema migrations including the v2 ChangeImpact bump from Step 15a.

### Workflow Engine — `automation.workflow.engine`

```python
from automation.workflow.engine import WorkflowEngine

engine = WorkflowEngine(conn)

# Bootstrap project — call after master_prd records are populated
engine.create_project()
engine.after_master_prd_import()
engine.after_business_object_discovery_import()
```

The CBM importer's job is to populate Master PRD records and Business Object Discovery records, then call these methods to create the work item graph. Subsequent records (Entity PRDs, Process Documents) are imported by populating the corresponding work items as `complete` after their data is loaded.

### Import Processor — `automation.importer.pipeline`

The CBM importer does **not** use ImportProcessor. ImportProcessor is for AI session output. The CBM importer reads Word documents and writes records directly through the database connection. However, you should reuse the **mappers** from `automation.importer.mappers/` where possible — they know how to construct records correctly.

### Document Generator — `automation.docgen.generator`

```python
from automation.docgen.generator import DocumentGenerator

docgen = DocumentGenerator(conn, master_conn=master_conn, project_folder=project_folder)
result = docgen.generate(work_item_id, mode="final")
```

The integration test `test_cbm_document_generation.py` uses this. The test fixture sets up a temporary `project_folder` directory.

### Impact Analysis Engine — `automation.impact.engine`

```python
from automation.impact.engine import ImpactAnalysisEngine

impact = ImpactAnalysisEngine(conn)
proposed = impact.analyze_proposed_change(...)
```

Used by `test_cbm_impact_analysis.py`.

### Schema — `automation.db.client_schema`

Read this to confirm exact column names. The CBM importer writes to all the same tables the import processor does: Domain, Entity, Field, FieldOption, Relationship, Persona, BusinessObject, Process, ProcessStep, Requirement, ProcessEntity, ProcessField, ProcessPersona, Decision, OpenIssue, plus LayoutPanel/LayoutRow/LayoutTab/ListColumn for entity layouts.

### docx parsing

Use `python-docx` (already a project dependency from Step 14's Document Generator). For complex parsing (like the field tables with specific DXA column widths), you may need to walk the XML directly via `paragraph._element` or `table._tbl`. Match the parser to the structure of the existing CBM documents.

**Read 2-3 CBM documents end-to-end before writing any parser code.** Look at:

- `PRDs/CBM-Master-PRD.docx` — for personas list format and domain inventory
- `PRDs/MN/MN-INTAKE.docx` — for the standard process document structure
- `PRDs/entities/Contact-Entity-PRD.docx` — for the field table format

The documents follow consistent patterns. Identify them, then write parsers that target those patterns.

## Definition of Done

### Part 0 — project_folder wiring (commit 1)

1. **DocumentGenerator receives a real project_folder when invoked from the Documents view.**
   - The path is derived from the client context's selected client and the associated instance profile (Section 14.9.3 instance association)
   - If the client has no associated instance, the Documents view shows an explanatory message ("No project folder configured for this client. Associate an instance in Deployment mode.") rather than allowing generation with `None`
   - The `instance_association.py` module from Step 15c may need a new helper like `get_project_folder_for_client(client_id, instance_profiles)` — add it if needed
   - Buttons-never-disabled rule (Section 14.10.6) applies: the Generate Final / Generate Draft buttons remain visible but clicking them when no project_folder is configured shows the explanatory message
   - This is the **only modification to existing Step 15 code** authorized in this step

2. **A test verifies that DocumentGenerator instantiation in the Documents view fails fast on `None` project_folder** with a clear error message rather than silently producing invalid generation results. Add this to `automation/tests/test_ui_documents_view.py` or a new file if appropriate.

3. **Existing 1017 tests still pass** after the project_folder fix.

4. **Commit 1 message:**

```
Wire project_folder for DocumentGenerator from instance association

The Documents view previously passed project_folder=None when constructing
DocumentGenerator, deferring the wiring to Step 16 per the Step 15c review.
This commit derives project_folder from the client's associated instance
profile (Section 14.9.3) and shows an explanatory message when no
association exists. Generate Final and Generate Draft buttons remain
visible per Section 14.10.6 (buttons never disabled).

Required for Step 16 integration tests.
```

### Part 1 — CBM PRD importer (commit 2)

5. **CBMImporter class** (`cbm_import/importer.py`) is the public API:

```python
class CBMImporter:
    def __init__(
        self,
        client_db_path: Path | str,
        master_db_path: Path | str,
        cbm_repo_path: Path | str,
    ): ...

    def import_all(self, *, dry_run: bool = False) -> ImportReport:
        """Import all CBM PRDs into the client database.

        Order of operations:
          1. Initialize client and master databases (if not exists)
          2. Parse Master PRD → Personas, Domains, Processes inventory
          3. Create master_prd work item, mark complete with imported data
          4. Trigger workflow graph construction (after_master_prd_import)
          5. Parse Entity Inventory → BusinessObjects + Entity stubs
          6. Mark business_object_discovery work item complete
          7. Trigger second graph expansion (after_business_object_discovery_import)
          8. Parse each Entity PRD → populate Entity records, Fields, Relationships, Layouts
          9. Mark each entity_prd work item complete
          10. Parse each Process document → populate Process, ProcessStep, Requirement, cross-refs
          11. Mark each process_definition work item complete
          12. Parse each Domain PRD → populate Domain narrative + Decisions
          13. Mark each domain_reconciliation work item complete

        :param dry_run: If True, parse and validate but do not write to the database.
            Returns a report of what would have been imported.
        :returns: ImportReport with counts, warnings, and skipped records.
        """

    def import_master_prd(self) -> ImportReport: ...
    def import_entity_inventory(self) -> ImportReport: ...
    def import_entity_prd(self, entity_name: str) -> ImportReport: ...
    def import_process(self, process_code: str) -> ImportReport: ...
    def import_domain_prd(self, domain_code: str) -> ImportReport: ...
```

The granular methods (import_entity_prd, import_process, etc.) allow incremental imports for testing and re-runs.

6. **Each parser module** in `cbm_import/parsers/` implements one CBM document type:
   - **`master_prd.py`** — extracts Personas (with `MST-PER-NNN` codes from Section 2 of the Master PRD), Domains (from the domain inventory section), Processes (from the process inventory grouped by domain). Returns a structured dict that the importer translates into database records.
   - **`entity_inventory.py`** — extracts BusinessObjects (the business entity concepts) and the entity-to-business-object mapping. Each row in the inventory table becomes one BusinessObject record with a resolved Entity reference (if the entity exists) or a stub.
   - **`entity_prd.py`** — extracts the Entity record (overview metadata), all Field records (from the field tables), FieldOptions for enum/multiEnum fields, Relationship records (from the relationship section), Layout records (from layout sections if present). Honors the field table format documented in Memory item 8 (two rows per field, ID column).
   - **`process_document.py`** — extracts the Process record (purpose, triggers), ProcessStep records (from the workflow steps section, ordered), Requirement records (from the requirements section, with identifiers), ProcessPersona/ProcessEntity/ProcessField cross-references.
   - **`domain_prd.py`** — extracts the Domain narrative (`domain_overview_text`, `domain_reconciliation_text`) and any Decision records from the reconciliation document.

7. **Pure-logic separation**: `parser_logic.py` contains structure-detection helpers (find section by heading, parse a header table, extract a list under a heading) that have no dependency on python-docx. The actual python-docx access lives in `docx_parser.py`. This way the parser logic is testable with hand-built XML or fake document objects.

8. **Identifier preservation**: All identifiers in the source documents are preserved exactly. Persona codes (`MST-PER-001`), domain codes (`MN`, `MR`, `CR`, `FU`), process codes (`MN-INTAKE`), requirement identifiers, decision identifiers — all carried through verbatim. The Step 12 identifier management rules (Section 11.12) apply.

9. **Human-readable-first identifier rule**: When the importer logs progress or generates report messages, names are formatted as "Client Intake (MN-INTAKE)" not the reverse.

10. **Skip-and-report behavior**: When the parser encounters a record it cannot map cleanly (missing required field, inconsistent format, ambiguous reference), it skips the record, logs a warning to the ImportReport, and continues. The importer does not halt on parse errors. The administrator reviews the report after import and either accepts the gaps, edits the source documents, and re-imports, or fixes the records directly through the Data Browser.

11. **ImportReport** structure:

```python
@dataclasses.dataclass
class ImportReport:
    parsed: dict[str, int]      # table_name -> count of parsed records
    imported: dict[str, int]    # table_name -> count of records actually written
    skipped: list[SkippedRecord]  # records that could not be imported
    warnings: list[str]         # non-fatal issues
    errors: list[str]           # fatal errors that halted a sub-import

@dataclasses.dataclass
class SkippedRecord:
    source_file: str
    table_name: str
    identifier: str | None
    reason: str
```

12. **CLI entry point** (`cbm_import/cli.py`):

```bash
python -m automation.cbm_import \
    --cbm-repo /path/to/ClevelandBusinessMentoring \
    --client-db /path/to/cbm-client.db \
    --master-db /path/to/master.db \
    [--dry-run]
```

The CLI calls `CBMImporter.import_all()` and prints the report at the end. Doug runs this once after the implementation lands.

13. **Workflow integration**: After the importer populates the Master PRD records, it calls `engine.create_project()` and `engine.after_master_prd_import()` to create the initial work items. After Business Object Discovery records are populated, it calls `engine.after_business_object_discovery_import()` to expand the graph for entity_prd, process_definition, etc. The importer then marks each populated work item as `complete` (using either `engine.complete()` or by writing the status directly — your choice, document which).

14. **AISession records**: The importer creates one synthetic AISession per imported document with `session_type='initial'`, `import_status='imported'`, `generated_prompt='[CBM bootstrap import]'`, and timestamps reflecting the bootstrap. This satisfies the Step 9 schema's `created_by_session_id` foreign keys on Field, Persona, etc., and provides traceability — the administrator can see in the audit trail that records came from the CBM bootstrap rather than from a real AI session.

15. **The importer never modifies any code in `automation/db/`, `automation/workflow/`, `automation/prompts/`, `automation/importer/`, `automation/impact/`, `automation/docgen/`, or `automation/ui/`.** Steps 9–15 are locked. The only existing-file modification authorized in Step 16 is the Part 0 project_folder fix in commit 1.

16. **Importer tests** (`automation/tests/test_cbm_importer.py`): test individual parsers against the fixture subset documents. Verify that:
    - The Master PRD parser produces the right number of Personas and Domains
    - The Entity Inventory parser produces the right BusinessObjects
    - The Entity PRD parser correctly extracts fields with their metadata
    - The Process document parser correctly extracts steps and requirements
    - The Domain PRD parser correctly extracts the reconciliation narrative
    - Skipped records are reported clearly
    - Dry-run mode does not write to the database

17. **Commit 2 message:**

```
Implement Step 16 Part 1: CBM PRD importer (automation/cbm_import/)

One-time bootstrap importer that parses the existing CBM Word documents
in dbower44022/ClevelandBusinessMentoring and populates a CBM client
database with Personas, Domains, BusinessObjects, Entities, Fields,
Processes, ProcessSteps, Requirements, cross-references, and Decisions.

Reads source documents from PRDs/, calls the Workflow Engine to bootstrap
the project work items, marks each populated work item complete, and
creates synthetic AISession records for traceability per Step 9 schema.

Skip-and-report behavior for records the parser cannot map cleanly.
Dry-run mode supported. CLI entry point: python -m automation.cbm_import.

Section 17 of L2 PRD identifies this as Step 16's first part.
```

### Part 2 — Integration test suite (commit 3)

18. **`automation/tests/integration/conftest.py`** provides fixtures:
    - `cbm_db_subset` — a populated client database created by running the importer against the fixture subset documents
    - `cbm_master_db` — a populated master database with a single Client record for CBM
    - `temp_project_folder` — a temporary directory for document generation tests
    - These fixtures are session-scoped so the import only runs once per test session

19. **Importer integration test** (`test_cbm_importer.py`):
    - Run the full importer against the fixture subset
    - Assert: expected number of Domains, Personas, Entities, Processes, etc. are in the database
    - Assert: the work item graph was constructed correctly (master_prd, business_object_discovery, entity_prd for each entity, process_definition for each process)
    - Assert: every populated work item is in `complete` status with a non-null `completed_at`
    - Assert: synthetic AISession records exist with `import_status='imported'`

20. **Workflow integration test** (`test_cbm_workflow.py`):
    - Use the populated database
    - Verify `WorkflowEngine.get_available_work()` returns the correct items at the correct phases
    - Verify the dependency graph matches expectations (e.g., entity_prd depends on business_object_discovery)
    - Verify `get_phase_for()` returns the right phase number for each work item type

21. **Prompt generation integration test** (`test_cbm_prompt_generation.py`):
    - Pick a work item from the populated database (e.g., the entity_prd for Contact, which is already complete)
    - Reopen it for revision via `WorkflowEngine.revise()`
    - Generate a prompt via `PromptGenerator.generate(work_item_id, session_type='revision', revision_reason='test')`
    - Assert: the prompt is non-empty and contains expected sections (Session Header, Session Instructions placeholder, Context with the entity's data, Locked Decisions, Open Issues, Output Spec)
    - Assert: the AISession row was updated with the generated_prompt

22. **Impact analysis integration test** (`test_cbm_impact_analysis.py`):
    - Modify a Field record on the Contact entity (e.g., change `field_type` from varchar to text)
    - Call `ImpactAnalysisEngine.analyze_proposed_change()` for the proposed change
    - Assert: the impact set includes ProcessField references for processes that use the Contact entity
    - Assert: the impact set includes LayoutRow references if the field appears in layouts

23. **Document generation integration test** (`test_cbm_document_generation.py`):
    - Use the populated database and a temporary project_folder
    - Generate the Master PRD document via `DocumentGenerator.generate(master_prd_work_item_id, mode='final')`
    - Assert: the output .docx file exists at the expected path
    - Assert: a GenerationLog row was created
    - Assert: opening the .docx with python-docx succeeds and the document contains expected text (organization name, persona names, domain names)
    - Generate at least one Entity PRD and one Process Document the same way

24. **All integration tests pass against the fixture subset.** The full CBM import is not exercised by automated tests — it happens when Doug runs the CLI manually after the implementation lands.

25. **Test count**: at least 15 new integration tests across the 5 integration test files. The pure-logic importer tests in `test_cbm_importer.py` (separate from the integration test of the same name) add another 10-20 tests. Total target: ~30 new tests.

26. **All tests pass**: `uv run pytest automation/tests/ -v`. Target: 1017 existing + ~30 new + Part 0 tests, with no failures. Integration tests should run in under 60 seconds against the fixture subset.

27. **Linter clean**: `uv run ruff check automation/`

28. **Commit 3 message:**

```
Implement Step 16 Part 2: CBM integration test suite

End-to-end tests in automation/tests/integration/ that exercise the
full pipeline against a populated CBM database:
- test_cbm_importer.py: importer correctness against fixture subset
- test_cbm_workflow.py: WorkflowEngine queries on populated data
- test_cbm_prompt_generation.py: PromptGenerator end-to-end with
  revision session
- test_cbm_impact_analysis.py: ImpactAnalysisEngine traces field
  changes through cross-references
- test_cbm_document_generation.py: DocumentGenerator produces .docx
  files from populated CBM data

Fixtures in automation/tests/fixtures/cbm_subset/ provide minimal
hand-crafted CBM-style documents for fast test execution. Full CBM
import is exercised manually via the CLI.

Section 17 of L2 PRD identifies this as Step 16's second part.
Closes the 16-step roadmap.
```

## Working Style

- **Read the CBM CLAUDE.md and 2-3 sample documents before writing parser code.** The documents have consistent structure but it's not documented anywhere — you have to read them to understand the patterns. Suggested samples: `CBM-Master-PRD.docx`, `MN/MN-INTAKE.docx`, `entities/Contact-Entity-PRD.docx`.
- **Read the existing automation engine APIs** to understand what the importer is feeding into. Especially `automation/workflow/engine.py` (graph construction methods), `automation/db/client_schema.py` (target tables), and `automation/importer/mappers/` (existing record-construction logic you can reuse).
- **Implement in this order**:
  1. Part 0 (project_folder fix) — small, do it first to unblock the integration tests
  2. `cbm_import/parser_logic.py` and `docx_parser.py` (pure-Python parsing helpers, testable)
  3. Each parser module in `cbm_import/parsers/` one at a time, with tests
  4. `cbm_import/reporter.py` and `importer.py` (orchestration)
  5. `cbm_import/cli.py`
  6. Fixture documents in `automation/tests/fixtures/cbm_subset/` — hand-craft these as you write each parser
  7. Integration tests in `automation/tests/integration/`
- **Surface ambiguities, do not invent answers.** Examples to flag rather than guess:
  - Persona codes in the Master PRD use the format `MST-PER-NNN`. The L2 PRD doesn't constrain persona code format. Should the importer enforce the format, or accept whatever the document contains?
  - The CBM documents reference some entities that don't exist yet (placeholder names). Should the importer create stub Entity records or skip the references?
  - The Domain Reconciliation document may contain Decision records with rich formatting (lists, sub-decisions). What's the canonical mapping to the flat Decision table?
  - The CBM Process documents have a "Workflow Diagram" section that references a PNG file. The importer should extract the PNG path but not embed the binary. The PNG is referenced by the docgen step at generation time per Section 13.12.
  - Some CBM documents are at version 2.x and have evolved past their L2 PRD-described format. If a document doesn't match the expected structure, the parser should skip that document and report it clearly.
- **Do not modify Steps 9–15 except for the Part 0 project_folder fix.** All other existing automation code is locked.
- **Do not pull in pytest-qt.** Integration tests are headless.
- **No HTTP / API calls.** Option B integration is preserved.
- **The CBM repo is read-only from the importer's perspective.** The importer never writes to `dbower44022/ClevelandBusinessMentoring`. It only reads `.docx` files.

## Out of Scope for Step 16

- Modifying any Step 9–15 automation code beyond the Part 0 project_folder fix
- A general-purpose document importer for non-CBM clients (Step 16 is CBM-specific bootstrap)
- Manual UI walkthrough (Doug does that separately)
- HTTP / API calls
- Modifying the existing CBM Word documents
- Modifying the database schema
- Pulling in pytest-qt
- Any work after Step 16 — there is no Step 17

## Reference Documents

Primary references for this step:

- `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx` — sections to re-read:
  - **Section 17** — The 16-step roadmap including the Step 16 description
  - **Section 9.4** — Workflow graph construction (what the importer triggers via engine methods)
  - **Section 11.12** — Identifier management rules (the importer must follow these)
  - **Section 11.3** — Payload-to-record mapping (the existing import processor mappers you may reuse)
  - **Section 13.7.1** — Project folder structure (where DocumentGenerator writes files, relevant to Part 0)
- The CBM repository's `CLAUDE.md` and 2-3 sample documents
- Memory item 8 — Field table format (DXA column widths) for parsing entity PRD field tables
- Memory item 7 — Human-readable-first identifier rule
- Memory item 4 — Current CBM domain state (what's complete, what's deferred)

## Final Check

Before declaring this step complete, verify:

- [ ] **Commit 1 (Part 0):**
  - [ ] Documents view derives project_folder from instance association
  - [ ] Generate Final / Generate Draft buttons show explanatory message when no association exists
  - [ ] Existing 1017 tests still pass
- [ ] **Commit 2 (Part 1 importer):**
  - [ ] All 5 parsers + importer + CLI present
  - [ ] Pure-logic modules (`parser_logic.py`, `docx_parser.py` minus the python-docx imports themselves) are testable without a database
  - [ ] CBMImporter calls WorkflowEngine to construct the graph
  - [ ] Synthetic AISession records are created for traceability
  - [ ] Skip-and-report behavior works
  - [ ] CLI runs successfully against the fixture subset
- [ ] **Commit 3 (Part 2 integration tests):**
  - [ ] All 5 integration test files present with at least 15 total tests
  - [ ] Fixture subset documents exist in `automation/tests/fixtures/cbm_subset/`
  - [ ] Integration tests run in under 60 seconds
- [ ] `grep -rn "phase TEXT" automation/db/` returns zero matches
- [ ] `grep -rn "anthropic.com\|api\.anthropic" automation/cbm_import/ automation/tests/integration/` returns zero matches
- [ ] `grep -rn "PySide6" automation/cbm_import/` returns zero matches (importer is headless, not UI code)
- [ ] All tests pass: target ~1050+ tests, no failures
- [ ] Linter clean
- [ ] No code in `automation/db/`, `automation/workflow/`, `automation/prompts/`, `automation/importer/`, `automation/impact/`, `automation/docgen/`, `automation/ui/` (except Part 0), or `espo_impl/` was modified
- [ ] Any deviations from the API sketch above are documented in your final report
- [ ] Any ambiguities encountered in CBM document parsing and how you resolved them are documented in your final report
- [ ] Any source CBM documents that the parser could not handle are listed in the final report so Doug can fix them or accept the gap

When complete, commit with the descriptive messages above and report what was built. Do not push — leave that for Doug.

After Doug pushes and runs the CLI manually against the full CBM repo, the report from that run will identify any further gaps to fix as a small Step 16 follow-up.

This is the final step. After Step 16 lands and the full CBM import runs successfully, the 16-step automation roadmap is complete.

# Claude Code Implementation Prompt — Step 14: Document Generator

## Context

You are implementing **Step 14 of the CRM Builder Automation roadmap** — the Document Generator. The complete design for this work is in the Level 2 PRD at:

`PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`

**Read Section 13 of the L2 PRD before writing any code.** That section defines the entire Document Generator: the eight-document catalog, the data query layer (one query per document type), the template architecture, the seven-step rendering pipeline, staleness detection and presentation, output management, draft vs. final generation, generation tracking, workflow diagram integration, and schema changes.

This is step 14 of a 16-step roadmap (see Section 17). Steps 9 (database), 10 (workflow), 11 (prompts), 12 (importer), and 13 (impact analysis) are complete. The two remaining steps after this are Step 15 (UI) and Step 16 (CBM integration testing).

## Repository Context

This work goes in the `dbower44022/crmbuilder` repository. Read `CLAUDE.md` at the repo root for general project conventions. Read this prompt's "Foundation" section below carefully — it documents the API surface of Steps 9–13 your code must build on.

## Where the Code Goes

Create a new package parallel to the existing automation packages:

```
automation/
├── __init__.py              # exists
├── db/                      # exists — Step 9
├── workflow/                # exists — Step 10
├── prompts/                 # exists — Step 11
├── importer/                # exists — Step 12
├── impact/                  # exists — Step 13 (provides staleness)
├── docgen/                  # NEW — Step 14
│   ├── __init__.py
│   ├── generator.py         # DocumentGenerator class — public API
│   ├── pipeline.py          # 7-step rendering pipeline (Section 13.5)
│   ├── queries/             # Data query layer (Section 13.3)
│   │   ├── __init__.py
│   │   ├── master_prd.py
│   │   ├── entity_inventory.py
│   │   ├── entity_prd.py
│   │   ├── domain_overview.py
│   │   ├── process_document.py
│   │   ├── domain_prd.py
│   │   ├── yaml_program.py
│   │   └── crm_evaluation.py
│   ├── templates/           # Rendering templates (Section 13.4)
│   │   ├── __init__.py
│   │   ├── formatting.py    # Shared constants (Section 13.4)
│   │   ├── master_prd_template.py
│   │   ├── entity_inventory_template.py
│   │   ├── entity_prd_template.py
│   │   ├── domain_overview_template.py
│   │   ├── process_document_template.py
│   │   ├── domain_prd_template.py
│   │   ├── yaml_program_template.py
│   │   └── crm_evaluation_template.py
│   ├── paths.py             # Output path resolution (Section 13.7.1)
│   ├── validation.py        # Step 3 — data dictionary completeness check
│   ├── git_ops.py           # Local commit + optional push (Section 13.7.3)
│   ├── generation_log.py    # GenerationLog recording (Section 13.11)
│   ├── staleness.py         # Section 13.6 staleness presentation (consumes impact engine)
│   └── workflow_diagram.py  # PNG embedding (Section 13.12)
└── tests/
    ├── test_docgen_generator.py
    ├── test_docgen_pipeline.py
    ├── test_docgen_queries_master_prd.py
    ├── test_docgen_queries_entity_inventory.py
    ├── test_docgen_queries_entity_prd.py
    ├── test_docgen_queries_domain_overview.py
    ├── test_docgen_queries_process_document.py
    ├── test_docgen_queries_domain_prd.py
    ├── test_docgen_queries_yaml_program.py
    ├── test_docgen_queries_crm_evaluation.py
    ├── test_docgen_templates_master_prd.py
    ├── test_docgen_templates_entity_inventory.py
    ├── test_docgen_templates_entity_prd.py
    ├── test_docgen_templates_domain_overview.py
    ├── test_docgen_templates_process_document.py
    ├── test_docgen_templates_domain_prd.py
    ├── test_docgen_templates_yaml_program.py
    ├── test_docgen_templates_crm_evaluation.py
    ├── test_docgen_paths.py
    ├── test_docgen_validation.py
    ├── test_docgen_git_ops.py
    ├── test_docgen_generation_log.py
    ├── test_docgen_staleness.py
    ├── test_docgen_workflow_diagram.py
    └── test_docgen_formatting.py
```

**Tests live in the existing `automation/tests/` directory** — match the conventions established by Steps 9–13.

This is the largest module structure so far. The split between `queries/` and `templates/` is deliberate: queries read the database and produce data dictionaries, templates consume data dictionaries and produce files. They are independent — you can test queries against a populated database without touching template code, and you can test templates by feeding them hand-built data dictionaries without touching the database.

## Foundation — Existing API Surface

### Database — `automation.db.connection`

```python
from automation.db.connection import open_connection, connect, transaction

with connect(db_path) as conn:
    # ... read-only queries ...

# GenerationLog inserts use transaction()
with transaction(conn):
    conn.execute("INSERT INTO GenerationLog ...")
```

The Document Generator is **mostly read-only** against the requirements database. The only writes are GenerationLog insert rows for final generation. Wrap those in `transaction(conn)`.

### Workflow Engine — `automation.workflow.engine`

```python
from automation.workflow.engine import WorkflowEngine

engine = WorkflowEngine(conn)
status = engine.get_status(work_item_id)  # validate generatable state
```

The Document Generator queries work item status to validate generatable state per Section 13.5 step 1 (final → complete; draft → in_progress). It does not modify work items.

### Impact Analysis Engine — `automation.impact.engine`

```python
from automation.impact.engine import ImpactAnalysisEngine

impact = ImpactAnalysisEngine(conn)
stale = impact.get_stale_work_items()  # already implemented in Step 13
```

**Important:** Section 13.6.1 redefines staleness. Step 13's `get_stale_work_items()` calculates staleness using `WorkItem.completed_at` as the baseline. Section 13.6 says staleness should use `GenerationLog.generated_at` as the baseline instead — because regeneration without revision should clear staleness, but a work item can complete without being generated. This is a subtle but important distinction.

You should **not** modify `automation/impact/staleness.py`. Instead, the Document Generator's own `staleness.py` module computes its own staleness using GenerationLog as the baseline, per Section 13.6.1. The Impact Analysis Engine's staleness function remains as a different view (work item completion vs. data change), and the Document Generator's staleness function is the document-specific view (last generation vs. data change).

Document this distinction in your final report.

### Schema — `automation.db.client_schema`

The `GenerationLog` table **already exists** in the Step 9 schema with all required columns:

```sql
CREATE TABLE GenerationLog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_item_id INTEGER NOT NULL,
    document_type TEXT NOT NULL CHECK (document_type IN (
        'master_prd', 'entity_inventory', 'entity_prd', 'domain_overview',
        'process_document', 'domain_prd', 'yaml_program_files',
        'crm_evaluation_report'
    )),
    file_path TEXT NOT NULL,
    generated_at DATETIME NOT NULL,
    generation_mode TEXT NOT NULL CHECK (generation_mode IN ('final', 'draft')),
    git_commit_hash TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (work_item_id) REFERENCES WorkItem(id)
);
```

**No schema changes are required for Step 14.** Read `automation/db/client_schema.py` to confirm exact column names before writing INSERT/SELECT statements.

The `Client` table lives in the **master** database. Several document types (Master PRD, Entity Inventory, CRM Evaluation Report) need the client name and short name from Client. The DocumentGenerator accepts both connections at construction time, parallel to PromptGenerator and ImportProcessor.

## Definition of Done

This step is complete when **all** of the following are true:

1. **Formatting constants module** (`templates/formatting.py`) implements Section 13.4's shared formatting standards. All colors, fonts, sizes, page dimensions, table column widths, and any other constants are defined here, NOT inlined in template modules. Templates import from `formatting.py`. The constants are:
   - Header background: `#1F3864`
   - Header text: white
   - Title/heading color: `#1F3864`
   - Alternating row shading: `#F2F7FB`
   - Table borders: `#AAAAAA`
   - Gray text: `#888888`
   - Font: Arial throughout
   - Body 11pt, small 10pt, ID/description 8pt
   - Page: US Letter with 1" margins
   - Field table column widths (DXA): 2200+1100+800+2400+1000+1860=9360
   - Header: org name left, process name right
   - Footer: "Process Document — [Domain] Domain"

2. **Path resolution module** (`paths.py`) implements Section 13.7.1. Provides functions to compute the output path for each document type given the work item, the database connection (for entity/domain/process name lookups), and the project folder root. Paths follow:
   - Master PRD: `PRDs/{client}-Master-PRD.docx`
   - Entity Inventory: `PRDs/{client}-Entity-Inventory.docx`
   - Entity PRD: `PRDs/entities/{EntityName}-Entity-PRD.docx`
   - Domain Overview: `PRDs/{domain_code}/{client}-Domain-Overview-{DomainName}.docx`
   - Process Document: `PRDs/{domain_code}/{PROCESS-CODE}.docx`
   - Domain PRD: `PRDs/{domain_code}/{client}-Domain-PRD-{DomainName}.docx`
   - YAML: `programs/{entity_name}.yaml`
   - CRM Evaluation: `PRDs/{client}-CRM-Evaluation-Report.docx`
   - Sub-domains nest: `PRDs/{parent_code}/{subdomain_code}/{PROCESS-CODE}.docx`

   The `{client}` value is the client short name from the Client record (master database). If the short name is missing, use a sensible default like the lowercased client name.

3. **Data query modules** (`queries/`) implement Section 13.3 — one module per document type, each exposing a single function `query(conn, work_item_id, master_conn=None) -> dict` that returns the data dictionary for the template. The dictionary structure is whatever the corresponding template module needs; queries and templates are paired. The eight modules cover Section 13.3.1 through 13.3.8.

   For each query module, read the corresponding subsection of Section 13.3 and implement exactly the queries it specifies. Do not add queries the spec doesn't list. If you find that a section's data needs fields the spec doesn't mention, flag it as an ambiguity rather than guessing.

4. **Template modules** (`templates/`) implement Section 13.4 — one module per document type, each exposing a single function `generate(data_dict, output_path) -> None` that writes the formatted output file. Word document templates use `python-docx`. The YAML template uses a YAML serializer (PyYAML).

   **Important:** The existing Node.js generator templates at `PRDs/process/templates/generate-process-doc-template.js` and `PRDs/process/templates/generate-entity-prd-template.js` are the **reference implementations** for document formatting. Per Section 13.10.1, the Python templates produce **identical document structure and formatting**. Read those Node.js files before writing the corresponding Python templates. Do not "improve" the formatting — match it exactly.

   Use python-docx low-level APIs where needed. The existing entity PRD format (Memory item: 2 rows per field, alternating shading, gray description text) requires direct XML manipulation in some places. Match the existing format byte-for-byte where possible.

   The Word documents must observe the human-readable-first identifier rule everywhere. Headings, titles, body references, table contents — all use "Client Intake (MN-INTAKE)" format, never the reverse.

   **Product names:** Per Section 13.2, the CRM Evaluation Report is the **only** document type permitted to include product names. All other templates must never include product names (no EspoCRM, WordPress, etc.). This is a hard rule.

5. **Validation module** (`validation.py`) implements Section 13.5 step 3 — checks the data dictionary for completeness and produces warnings (not errors). For example, an Entity PRD where the entity has no fields produces a warning. The validator returns a list of warning objects; the pipeline presents them and the administrator can proceed or cancel. The validator does not block generation.

6. **Workflow diagram module** (`workflow_diagram.py`) implements Section 13.12. Provides a function that takes a process code and a project folder, looks up the diagram path (`PRDs/{domain_code}/{PROCESS-CODE}-workflow.png`), and returns the path if the PNG exists or `None` if it does not. The Process Document template calls this function and either embeds the image at 6.5" content width or inserts a placeholder.

7. **Git operations module** (`git_ops.py`) implements Section 13.7.3:
   - `commit(project_folder, file_paths, message) -> str | None` — runs `git add` and `git commit` in the project folder, returns the commit hash, or `None` if the commit fails (e.g., nothing to commit).
   - `push(project_folder) -> bool` — runs `git push`, returns `True` on success, `False` on failure. Per Section 13.7.3, push failures do not block — the generation is complete once the local commit succeeds.
   - Use `subprocess.run()` for git invocation. Capture stderr for error reporting.
   - Do not auto-push during normal generation. Push is offered as a separate optional action at the pipeline's Step 7.

8. **GenerationLog module** (`generation_log.py`) implements Section 13.11:
   - Function `record(conn, work_item_id, document_type, file_path, generation_mode, git_commit_hash) -> int` writes a GenerationLog row and returns the new id.
   - For final generation only — draft generation skips this step (Section 13.11.2).
   - Wrap the insert in `transaction(conn)`.
   - Function `get_latest_for_work_item(conn, work_item_id, mode='final') -> GenerationLog | None` returns the most recent log entry for a work item, used by staleness calculation.

9. **Staleness module** (`staleness.py`) implements Section 13.6.1:
   - Function `get_stale_documents(conn) -> list[StaleDocument]` returns all completed work items that have at least one final GenerationLog entry where any ChangeLog entry post-dates the most recent GenerationLog.generated_at AND affects records owned by the work item.
   - The "owns" relation uses the same mapping as `automation/impact/work_item_mapping.py` — read that module to reuse the ownership logic. Do not duplicate the mapping.
   - This is **different** from `automation/impact/staleness.py`, which uses `WorkItem.completed_at` as the baseline. The Document Generator's staleness uses `GenerationLog.generated_at` as the baseline. Document this distinction clearly in the module docstring.
   - Returns a list of dataclass instances with: work_item_id, item_type, last_generated_at, latest_change_at, change_count, change_summary (text drawn from the post-generation ChangeLog entries).

10. **Rendering pipeline** (`pipeline.py`) implements Section 13.5 — the seven-step pipeline:
    - Step 1 Select: validate work item is in generatable state (complete for final, in_progress for draft)
    - Step 2 Query: invoke the query module
    - Step 3 Validate: invoke the validator
    - Step 4 Render: invoke the template module
    - Step 5 Write: file is written by the template, then if final, run git commit
    - Step 6 Record: if final, write GenerationLog row
    - Step 7 Present: return a result object describing what happened

    The pipeline is synchronous — no threads, no async. Per Section 13.5, it completes in seconds.

11. **DocumentGenerator class** (`generator.py`) is the public API:

```python
class DocumentGenerator:
    def __init__(
        self,
        conn,
        master_conn=None,
        project_folder: str | Path | None = None,
    ): ...

    def generate(
        self,
        work_item_id: int,
        mode: str = "final",
    ) -> GenerationResult:
        """Run the full pipeline for a work item.
        Returns a GenerationResult with file_path, warnings, git_commit_hash,
        and any errors.
        Raises ValueError if mode is invalid or the work item is not in
        a generatable state.
        """

    def generate_batch(
        self,
        work_item_ids: list[int],
        mode: str = "final",
    ) -> list[GenerationResult]:
        """Per Section 13.7.4 — generate multiple documents.
        Each document is committed individually (one commit per document).
        A failure on one document does not block the others.
        """

    def get_stale_documents(self) -> list[StaleDocument]:
        """Convenience wrapper around staleness.get_stale_documents()."""

    def push(self) -> bool:
        """Optional follow-up after one or more generate() calls."""
```

12. **Document type catalog** is an enum or constant accessible from `__init__.py` listing the eight types per Section 13.2. The catalog maps each type to its work item type (e.g., entity_prd type → entity_prd work item type) and to its query module + template module.

13. **The generator never modifies work items, never reopens them, never marks them complete.** It only reads work items to validate state, and writes only to GenerationLog and the file system. Like the Impact Analysis Engine, it surfaces information; it does not change workflow state.

14. **All multi-row writes use `transaction(conn)`.** GenerationLog inserts must be wrapped.

15. **No code in `automation/db/`, `automation/workflow/`, `automation/prompts/`, `automation/importer/`, `automation/impact/`, or `espo_impl/` is modified.** Steps 9–13 are locked.

16. **pytest test suite** with **tests written alongside each module as it is built**. Coverage requirements:
    - `formatting.py`: constants are defined and importable
    - `paths.py`: each path pattern produces the correct output for representative inputs; sub-domain nesting works
    - Each query module: produces a correctly-shaped data dictionary against a populated test database; missing optional data is handled gracefully
    - Each template module: produces a valid .docx or .yaml file from a hand-built data dictionary; the file opens without errors; key content appears in the rendered text
    - `validation.py`: produces warnings for missing required content; does not block
    - `workflow_diagram.py`: returns the path when PNG exists, returns None when missing; the path resolution matches Section 13.12 convention
    - `git_ops.py`: commit returns a hash on success, None on failure; push failures do not raise
    - `generation_log.py`: records final generation; skips draft; latest-for-work-item query returns the most recent
    - `staleness.py`: detects work items where ChangeLog.changed_at > GenerationLog.generated_at; ignores work items with no final generation; uses the work item ownership mapping correctly
    - `pipeline.py`: end-to-end test that generates each document type for a work item in a populated test database, asserts the file exists at the expected path, and (for final mode) asserts a GenerationLog row exists
    - `generator.py`: end-to-end test of the public API including batch generation
    - All tests use real SQLite databases via `run_client_migrations()`, never mocks. Tests that involve git use a temporary directory initialized with `git init`.

17. **All tests pass**: `uv run pytest automation/tests/ -v`. Target: existing 708 + new docgen tests, no failures.

18. **Linter clean**: `uv run ruff check automation/`

## Working Style

- **Read Section 13 of the L2 PRD before writing any code.** Section 13 is long and the data query subsections are dense — read 13.3.1 through 13.3.8 carefully and verify every join column against `automation/db/client_schema.py`.
- **Read the existing Step 9–13 code** in `automation/db/`, `automation/workflow/`, `automation/prompts/`, `automation/importer/`, and `automation/impact/` so your code uses the real APIs.
- **Read the existing Node.js generator templates** at `PRDs/process/templates/generate-process-doc-template.js` and `PRDs/process/templates/generate-entity-prd-template.js` before writing the corresponding Python templates. Match their structure and formatting.
- **Read `automation/db/client_schema.py` for exact column names** before writing any queries.
- **Read `automation/impact/work_item_mapping.py`** to reuse the work item ownership logic for staleness — do not duplicate it.
- **Write tests alongside each module**, not at the end.
- **Implement in this order**: formatting → paths → workflow_diagram → validation → git_ops → generation_log → staleness → queries (8 modules) → templates (8 modules) → pipeline → generator. Each layer depends on earlier layers. Templates depend on queries via the data dictionary contract — but you can implement and test them independently by hand-building data dictionaries for the template tests.
- **Surface ambiguities, do not invent answers.** Examples of things to flag rather than guess:
  - Where exactly does the Process Document template embed the workflow diagram? What if the data dictionary contains a path but the file no longer exists at generation time?
  - The Domain PRD (Section 13.3.6) says "Decision (where domain_id matches or scoped to domain processes)" — what is the exact SQL for "scoped to domain processes"? Does it mean Decision.process_id IN (process IDs in this domain)?
  - The CRM Evaluation Report is the only document allowed to include product names. Where do those names come from in the data dictionary? Section 13.3.8 says `Client.crm_platform`, but is that a single value or does the data dictionary need additional context?
  - Section 13.7.3 says git commits include "only the generated file or files." What if the project folder repo has unrelated dirty changes? Should the generator stash them, refuse to commit, or just commit the generated file with an explicit `git add <file>` (which leaves dirty unrelated files alone)?
- **No GUI code.** UI is Step 15.
- **No HTTP / API calls.** Option B integration is preserved — this module never talks to anthropic.com.
- **Do not modify Steps 9–13.** Locked.
- **Do not modify `PRDs/process/templates/` Node.js files.** Reference only.
- **Do not create new files in `PRDs/`.** Output files go to a separate project folder, not the crmbuilder repo.

## Out of Scope for This Step

- Modifying any code in Steps 9–13
- Modifying or replacing the existing Node.js generator templates (they remain as references)
- Calling the Workflow Engine to revise, complete, or unblock work items
- UI code (Step 15)
- CBM-specific integration testing (Step 16)
- Any HTTP or API calls
- Modifying the database schema or migrations

## Reference Documents

Primary: `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`

Sections to read carefully before starting:
- **Section 13 (entire section)** — Document Generator. This is your spec.
- **Section 13.3** — Eight data query subsections.
- **Section 13.4** — Template architecture and shared formatting constants.
- **Section 13.5** — Seven-step rendering pipeline.
- **Section 13.6** — Staleness calculation (different from Section 12.10).
- **Section 13.7** — Output paths, file naming, git operations.
- **Section 13.10** — Relationship to existing Node.js templates.
- **Section 13.11** — GenerationLog table.
- **Section 13.12** — Workflow diagram embedding.

External references:
- `PRDs/process/templates/generate-process-doc-template.js` — Process Document reference implementation
- `PRDs/process/templates/generate-entity-prd-template.js` — Entity PRD reference implementation

You may also find this useful for context, but **do not implement any of it in step 14**:
- **Section 14** — User Interface. Step 15 will implement this. The UI is the primary caller of the Document Generator.

## Final Check

Before declaring this step complete, verify:

- [ ] `grep -rn "phase TEXT" automation/db/` returns zero matches (Step 9 fix verified, no regression)
- [ ] `grep -rn "anthropic.com\|api\.anthropic" automation/docgen/` returns zero matches (Option B integrity preserved)
- [ ] `grep -rn "engine\.revise\|engine\.complete\|engine\.start" automation/docgen/` returns zero matches outside tests (the docgen never modifies work items)
- [ ] `grep -rin "espocrm\|wordpress\|moodle\|constant contact\|digitalocean" automation/docgen/templates/ | grep -v "crm_evaluation"` returns zero matches (product names appear ONLY in the CRM Evaluation template)
- [ ] All items in the Definition of Done are met
- [ ] All tests pass (target: existing 708 + new docgen tests, no failures)
- [ ] Linter is clean
- [ ] No code in `automation/db/`, `automation/workflow/`, `automation/prompts/`, `automation/importer/`, `automation/impact/`, or `espo_impl/` was modified
- [ ] No work outside the Step 14 scope was performed
- [ ] The `DocumentGenerator` class can produce all eight document types end-to-end against a real SQLite database
- [ ] Staleness calculation correctly uses `GenerationLog.generated_at` as the baseline (not `WorkItem.completed_at`)
- [ ] Section 13.13's GenerationLog table requirement is satisfied by the existing Step 9 schema (no schema changes applied)
- [ ] Generated Word documents observe the human-readable-first identifier rule
- [ ] Generated Word documents (other than CRM Evaluation Report) contain no product names
- [ ] Any deviations from the API sketch above are documented in your final report
- [ ] Any ambiguities encountered in Section 13 and how you resolved them are documented in your final report

When complete, commit with a descriptive message and report what was built. Do not push — leave that for Doug.

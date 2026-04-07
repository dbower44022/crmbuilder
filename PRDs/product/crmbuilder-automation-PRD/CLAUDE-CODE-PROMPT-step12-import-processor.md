# Claude Code Implementation Prompt — Step 12: Import Processor

## Context

You are implementing **Step 12 of the CRM Builder Automation roadmap** — the Import Processor. The complete design for this work is in the Level 2 PRD at:

`PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`

**Read Section 11 of the L2 PRD before writing any code.** That section defines the entire Import Processor: the seven-stage pipeline (Receive → Parse → Map → Detect → Review → Commit → Trigger), payload-to-record mapping per work item type, conflict detection, partial import handling, session type variations, decision/issue handling, audit trail, downstream triggers, error recovery, and identifier management.

This is step 12 of a 16-step roadmap (see Section 17). Steps 9 (database), 10 (workflow), and 11 (prompts) are complete. Subsequent implementation steps (13–16) will build on top of the Import Processor.

## Repository Context

This work goes in the `dbower44022/crmbuilder` repository. Read `CLAUDE.md` at the repo root for general project conventions. Read this prompt's "Foundation" section below carefully — it documents the database, workflow, and prompts API surface your code must build on.

## Where the Code Goes

Create a new package parallel to the existing automation packages:

```
automation/
├── __init__.py              # exists
├── db/                      # exists — Step 9
├── workflow/                # exists — Step 10
├── prompts/                 # exists — Step 11
├── importer/                # NEW — Step 12
│   ├── __init__.py
│   ├── pipeline.py          # ImportProcessor class — public API
│   ├── parser.py            # JSON parsing and envelope validation (Section 11.2)
│   ├── mappers/             # Payload-to-record mapping (Section 11.3)
│   │   ├── __init__.py
│   │   ├── master_prd.py
│   │   ├── business_object_discovery.py
│   │   ├── entity_prd.py
│   │   ├── domain_overview.py
│   │   ├── process_definition.py
│   │   ├── domain_reconciliation.py
│   │   ├── yaml_generation.py
│   │   ├── crm_selection.py
│   │   └── crm_deployment.py
│   ├── proposed.py          # ProposedRecord and ProposedBatch dataclasses
│   ├── conflicts.py         # Conflict detection (Section 11.5)
│   ├── commit.py            # Stage 6 commit with ChangeLog (Section 11.9.2)
│   ├── triggers.py          # Stage 7 downstream triggers (Section 11.10)
│   └── identifiers.py       # Identifier validation (Section 11.12)
└── tests/
    ├── test_importer_parser.py
    ├── test_importer_mappers_master_prd.py
    ├── test_importer_mappers_business_object_discovery.py
    ├── test_importer_mappers_entity_prd.py
    ├── test_importer_mappers_domain_overview.py
    ├── test_importer_mappers_process_definition.py
    ├── test_importer_mappers_domain_reconciliation.py
    ├── test_importer_mappers_yaml_generation.py
    ├── test_importer_mappers_crm_selection.py
    ├── test_importer_mappers_crm_deployment.py
    ├── test_importer_proposed.py
    ├── test_importer_conflicts.py
    ├── test_importer_commit.py
    ├── test_importer_triggers.py
    ├── test_importer_identifiers.py
    └── test_importer_pipeline.py
```

**Tests live in the existing `automation/tests/` directory** — match the conventions established by Steps 9, 10, and 11.

## Foundation — Existing API Surface

The Import Processor is the most integrated module so far. It reads from the database, queries the workflow engine, mirrors the prompt generator's structure, and writes to multiple tables atomically. Use these existing APIs — do not bypass or duplicate them.

### Database — `automation.db.connection`

```python
from automation.db.connection import open_connection, connect, transaction

with connect(db_path) as conn:
    # ...

# All commits are wrapped in transactions
with transaction(conn):
    conn.execute("INSERT INTO ...")
    conn.execute("INSERT INTO ChangeLog ...")
```

The Import Processor's Stage 6 (Commit) writes to many tables in a single transaction. **Use `transaction(conn)` exclusively** — do not write raw `BEGIN`/`COMMIT` SQL.

### Workflow Engine — `automation.workflow.engine`

```python
from automation.workflow.engine import WorkflowEngine

engine = WorkflowEngine(conn)

# Stage 7 triggers call these:
engine.after_master_prd_import()                       # 11.10.1 step 1
engine.after_business_object_discovery_import()        # 11.10.1 step 1
engine.complete(work_item_id)                          # 11.10.1 step 2 + 3
# Note: complete() already triggers downstream recalculation per 9.7.1
```

The Workflow Engine's `complete()` method (Step 10) **already includes** the downstream recalculation logic from Section 9.7.1 and the automatic unblocking from Section 9.8.2. You do not need to re-implement these — call `engine.complete()` and it handles both. The Import Processor's job is to call the engine in the correct order, not to duplicate its logic.

The graph construction methods (`after_master_prd_import`, `after_business_object_discovery_import`) likewise already exist and handle the work item creation per Section 9.4.

### Schema — `automation.db.client_schema`

Read `automation/db/client_schema.py` to confirm exact column names before writing INSERT/UPDATE statements. Do not assume column names from the L2 PRD prose — verify against the schema.

Tables the Import Processor writes to during a commit (depending on payload):

- **Domain, Entity, Field, FieldOption, Relationship, Persona, BusinessObject, Process, ProcessStep, Requirement** — main records
- **ProcessEntity, ProcessField, ProcessPersona** — cross-reference records
- **Decision, OpenIssue** — from envelope top-level arrays
- **ChangeLog** — every committed record produces ChangeLog entries (Section 11.9.2)
- **AISession** — updates raw_output, structured_output, import_status, completed_at

The `Client` table lives in the **master** database. The Import Processor may need to update Client.organization_overview and Client.crm_platform from master_prd and crm_selection imports respectively. The pipeline accepts both connections at construction time, parallel to the PromptGenerator.

### AISession lifecycle (the contract between Steps 11 and 12)

Step 11 created the AISession row at prompt generation time with:
- `work_item_id` set
- `session_type` set
- `generated_prompt` set
- `import_status` = `'pending'`
- `started_at` set to CURRENT_TIMESTAMP
- `raw_output`, `structured_output`, `completed_at` = NULL

Step 12's job is to:
- **Stage 1 (Receive):** UPDATE the existing AISession row to set `raw_output`. Do not create a new row.
- **Stage 2 (Parse):** UPDATE `structured_output` after successful parse.
- **Stage 6 (Commit):** UPDATE `import_status` to one of `'imported'`, `'partial'`, or `'rejected'` and set `completed_at` to CURRENT_TIMESTAMP.

If multiple AISession rows exist for a work item (e.g., a previous attempt was abandoned), use the most recent one with `import_status = 'pending'`. If no pending session exists, raise an error — the administrator must generate a prompt first.

## Definition of Done

This step is complete when **all** of the following are true:

1. **Parser module** (`parser.py`) implements Section 11.2 — three layers of validation:
   - **Layer 1 — Syntax:** Strip markdown code fences and trailing non-JSON, then `json.loads()`. On failure, raise a parser error with the line and character position from the JSONDecodeError.
   - **Layer 2 — Envelope:** Validate `output_version`, `work_item_type`, `work_item_id`, `session_type`, `payload`, `decisions`, `open_issues` are all present and well-formed. The version uses major.minor semantics with major-version compatibility. Each field has explicit checks for missing/wrong-type with specific error messages.
   - **Layer 3 — Payload Structure:** Validate the payload object against the expected top-level keys for the declared `work_item_type`. The validator checks key presence and JSON type, not record completeness.

2. **Proposed records dataclass** (`proposed.py`) defines the in-memory representation of records after mapping but before commit. Two key types:
   - `ProposedRecord` — table_name, action ('create' or 'update'), target_id (None for create, existing id for update), values (dict of column→value), conflicts (list of Conflict objects), source_payload_path (for error messages)
   - `ProposedBatch` — list of ProposedRecord, plus references to the source AISession id, work_item_id, and session_type

3. **Mapper modules** (`mappers/` directory) implement Section 11.3 — one mapper per prompt-capable work item type. Each mapper has a single function `map_payload(conn, work_item, payload, session_type) -> ProposedBatch` that:
   - Reads the payload structure for that work item type per the L2 PRD section
   - Produces ProposedRecord entries for every record the payload should create or update
   - Includes intra-batch references (e.g., a proposed Field referencing a proposed Entity from the same batch — these are not flagged as missing FKs in conflict detection)
   - Tags each record's `source_payload_path` so conflict messages can point to the JSON location
   - For revision sessions: produces `update` actions matched against existing records by identifier

   The nine mappers cover: master_prd, business_object_discovery, entity_prd, domain_overview, process_definition, domain_reconciliation, yaml_generation, crm_selection, crm_deployment.

4. **Conflict detection module** (`conflicts.py`) implements Section 11.5:
   - **Severity levels:** `'error'`, `'warning'`, `'info'` (Section 11.5.1)
   - **Conflict types** (Section 11.5.2):
     - Identifier uniqueness — check proposed codes/identifiers against existing records and other records in the same batch (excluding the record being updated)
     - Type mismatches — Field updates that change field_type → info; Field creates with same name but different type → error
     - Referential integrity — every FK is checked against existing records and intra-batch records; missing → error; intra-batch reference → info
     - Duplicate detection — proposed records whose name closely matches an existing one in the same scope → warning
     - Orphaned updates — revision updates whose target no longer exists → error

   Conflicts are attached to ProposedRecord.conflicts. The function does not halt the pipeline.

5. **Commit module** (`commit.py`) implements Stage 6 (Section 11.1) and the audit trail (Section 11.9):
   - Wraps all writes in a single `transaction(conn)`
   - For each accepted ProposedRecord:
     - On create: INSERT the record and capture the new id; for FK references to other intra-batch records, resolve the target id (which now exists)
     - On update: UPDATE the existing record by id
     - Write ChangeLog entries (Section 11.9.2) capturing every field value (for creates) or every changed field (for updates), with `session_id` referencing the AISession row
   - On any failure, the transaction rolls back automatically and the function raises an error
   - On success, returns a CommitResult with counts and the list of newly-created record ids by table

6. **Identifier management module** (`identifiers.py`) implements Section 11.12:
   - **11.12.1 Preservation:** Identifiers from the AI session are used as-is, never auto-generated or renumbered
   - **11.12.2 Uniqueness validation:** Per-table uniqueness check, scoped correctly (Domain code unique across Domain, Requirement identifier unique across Requirement, etc.); revision updates exclude the record being updated
   - **11.12.3 Format validation:** Pattern checks for Domain codes, Entity codes, Process codes (including the Master PRD mapper's check that the prefix matches the parent domain code per Finding 5 from v1.6), Requirement identifiers, Decision identifiers, OpenIssue identifiers, Persona codes
   - Format violations are warnings, not errors (per the L2 PRD)
   - **11.12.4 Sequential gaps:** Do not enforce continuity — gaps are normal

7. **Triggers module** (`triggers.py`) implements Section 11.10 — the post-commit trigger sequence:
   - **Step 1:** For master_prd → call `engine.after_master_prd_import()`. For business_object_discovery → call `engine.after_business_object_discovery_import()`. For all others → no graph construction.
   - **Step 2 + 3:** If the import is full, call `engine.complete(work_item_id)`. The engine handles step 3 (downstream recalculation) automatically — do not duplicate it.
   - **Step 4:** Revision unblocking is also handled inside `engine.complete()` already — for revision imports, the engine's complete() method walks the blocked downstream items and restores them. Do not duplicate this either.
   - **Step 5:** Impact analysis is **deferred to Step 13**. For Step 12, the trigger module records that impact analysis is needed (e.g., by setting a flag on the AISession or logging a marker) but does not actually run impact analysis. Document the deferral clearly.

   Per Section 11.10.2, graph construction (step 1) **must complete before** work item completion (step 2). The trigger sequence is strictly ordered.

   Per Section 11.10.3, trigger failures do not roll back the commit. If a trigger fails, the data is still committed; the failure is reported to the caller for handling.

8. **ImportProcessor class** (`pipeline.py`) is the public API. Like the PromptGenerator, it accepts both the client connection and an optional master connection:

```python
class ImportProcessor:
    def __init__(self, conn, master_conn=None): ...

    def receive(self, work_item_id: int, raw_text: str) -> int:
        """Stage 1: Store raw_output on the pending AISession.
        Returns the AISession id.
        Raises if no pending session exists for this work item.
        """

    def parse(self, ai_session_id: int) -> dict:
        """Stage 2: Parse and validate envelope and payload structure.
        Stores structured_output on the AISession on success.
        Returns the parsed envelope dict.
        Raises ParserError on any layer 1/2/3 failure.
        """

    def map(self, ai_session_id: int) -> ProposedBatch:
        """Stage 3: Apply type-specific mapping rules.
        Returns a ProposedBatch with all proposed records.
        """

    def detect_conflicts(self, batch: ProposedBatch) -> ProposedBatch:
        """Stage 4: Detect conflicts and attach them to ProposedRecords.
        Returns the same batch with conflicts populated.
        Does not halt on conflicts — they are presented in Stage 5.
        """

    def commit(
        self,
        ai_session_id: int,
        batch: ProposedBatch,
        accepted_record_ids: set[str] | None = None,
    ) -> CommitResult:
        """Stage 6: Commit accepted records in a single transaction.

        accepted_record_ids: set of source_payload_path strings identifying
            which records the administrator accepted. None means accept all.

        Updates AISession.import_status based on outcome:
        - 'imported' if all proposed records accepted
        - 'partial' if some accepted, some rejected
        - 'rejected' if all rejected

        Sets AISession.completed_at on success.
        """

    def trigger(self, ai_session_id: int, commit_result: CommitResult) -> TriggerResult:
        """Stage 7: Run downstream triggers.
        Per 11.10.3, failures here do not roll back the commit.
        Returns a TriggerResult describing what happened.
        """

    def run_full_import(
        self,
        work_item_id: int,
        raw_text: str,
        accept_all: bool = True,
    ) -> ImportResult:
        """Convenience method that runs all 7 stages end-to-end.
        Used by tests and by callers that don't need interactive review.
        Will not be used by the UI (Step 15) which calls each stage
        individually for the interactive review.
        """
```

Method signatures may be refined as you implement, but the public API surface must support both the staged-interactive flow (for the UI) and the run-all flow (for tests and headless callers). Document any signature changes in your final report.

9. **AISession lifecycle is honored exactly:**
   - `receive()` updates the existing pending AISession (does not create a new one)
   - `parse()` updates `structured_output`
   - `commit()` updates `import_status` and `completed_at`
   - All AISession updates are wrapped in `transaction()`
   - If no pending AISession exists for the work item, `receive()` raises a clear error

10. **Stage 6 commit is atomic.** Either all accepted records and all ChangeLog entries are written, or none are. The transaction wraps everything. On failure, the database is unchanged.

11. **Per Section 11.10.3, trigger failures do not roll back commits.** If `engine.complete()` raises an exception during trigger execution, the data committed in Stage 6 stays committed. The TriggerResult reports the failure for the caller to handle.

12. **No direct calls to the schema or workflow engine internals.** Use the public APIs from `automation.db.connection`, `automation.workflow.engine`, and the schema definitions.

13. **pytest test suite** with **tests written alongside each module as it is built**. Coverage requirements:
    - `parser.py`: layer 1 (syntax errors with line/char info, markdown fence stripping), layer 2 (each envelope field validated independently), layer 3 (payload type checks per work item type)
    - `proposed.py`: dataclass construction, conflict attachment, intra-batch reference handling
    - Each mapper: produces correct ProposedRecord set for a representative payload; revision updates produce update actions matched to existing records; intra-batch references are tagged
    - `conflicts.py`: each of the five conflict types triggers correctly; severity assignment is correct; revision updates are excluded from uniqueness checks for the target record
    - `commit.py`: atomic commit succeeds; constraint violation rolls back everything; ChangeLog entries are created correctly for both creates and updates; intra-batch FK resolution works
    - `triggers.py`: each session type triggers the right Workflow Engine methods in the right order; trigger failure does not affect committed data
    - `identifiers.py`: each format pattern validates correctly; the Master PRD process code prefix check from Finding 5 works
    - `pipeline.py`: end-to-end test that creates a populated database via real fixtures, generates a prompt via the PromptGenerator, simulates AI output by writing JSON, runs the full pipeline, and asserts the database state after commit
    - All status validation paths: importing without a pending AISession raises; importing for a non-promptable work item type raises; importing with mismatched envelope fields raises
    - Real SQLite databases via `run_client_migrations()`, never mocks

14. **All tests pass**: `uv run pytest automation/tests/ -v`

15. **Linter clean**: `uv run ruff check automation/`

## Working Style

- **Read Section 11 of the L2 PRD before writing any code.** Section 11 is the longest section in the L2 PRD — read it carefully before starting. Pay special attention to 11.3 (the nine mappers — each subsection defines required vs. optional fields), 11.5 (conflict types), 11.9 (audit trail format), and 11.10 (trigger sequence and timing rules).
- **Read existing Steps 9, 10, and 11 code** in `automation/db/`, `automation/workflow/`, and `automation/prompts/` so your code uses the real APIs.
- **Read `automation/db/client_schema.py` for exact column names** before writing any INSERT/UPDATE statements. Do not infer column names from the L2 PRD prose.
- **Write tests alongside each module**, not at the end.
- **Implement in this order**: parser → proposed → identifiers → mappers (one at a time) → conflicts → commit → triggers → pipeline. Each layer depends on earlier layers.
- **Surface ambiguities, do not invent answers.** Examples of things to flag rather than guess:
  - How should a mapper handle a payload field that's listed as required in 11.3 but is missing from the actual JSON? Reject the import or default it?
  - What "scope" should the duplicate detection use for Persona name comparison — global, per-domain, or per-process?
  - For the master_prd mapper, when the payload includes `crm_platform` (which lives on the Client table in the master database), should the mapper update the Client record or just record it on the AISession for the administrator to manually transfer?
- **Step 13 is impact analysis.** Section 11.10.1 step 5 says the Import Processor "queues the changes for impact analysis." For Step 12, you implement the queueing (set a flag, write a marker, log the intent — your choice) but do not implement the impact analysis itself. Document the deferral clearly so Step 13 knows where to pick up.
- **Do not modify `espo_impl/`, `automation/db/`, `automation/workflow/`, or `automation/prompts/`.** Steps 9–11 are locked. If you find a bug, report it but do not fix it as part of Step 12.

## Out of Scope for This Step

- Calling the Claude API or any HTTP endpoint — this is Option B integration, the administrator pastes JSON
- Generating prompts (Step 11)
- Running impact analysis on committed changes (Step 13 — Step 12 only queues the intent)
- Generating documents (Step 14)
- UI code (Step 15)
- Modifying the database schema or migrations
- Modifying any code in `automation/db/`, `automation/workflow/`, or `automation/prompts/`

## Reference Documents

Primary: `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`

Sections to read carefully before starting:
- **Section 11 (entire section)** — Import Processor. This is your spec.
- **Section 11.3** — Nine mapper subsections (11.3.1 through 11.3.9). Each defines the payload-to-record rules for one work item type.
- **Section 11.5** — Conflict detection types and severity.
- **Section 11.9** — Audit trail (AISession lifecycle and ChangeLog format).
- **Section 11.10** — Downstream trigger sequence and timing rules. Critical because it couples to the Workflow Engine.
- **Section 11.12** — Identifier management rules.
- **Section 7.1** — AISession schema.
- **Section 7.2** — ChangeLog schema.
- **Section 6.3** — WorkItem schema (no phase column — phase is application logic, see Section 14.2.3).
- **Section 9.7** — Status transitions. The Workflow Engine already implements these; you just call them.

You may also find this useful for context, but **do not implement any of it in step 12**:
- **Section 12** — Impact Analysis Engine. Step 13 will implement this. Section 12.4 explains how impact analysis is triggered after import — that hook point is what Step 12 needs to leave for Step 13.

## Final Check

Before declaring this step complete, verify:

- [ ] `grep -rn "phase TEXT" automation/db/` returns zero matches (Step 9 fix verified, no regression)
- [ ] `grep -rn "anthropic.com\|api\.anthropic" automation/importer/` returns zero matches (Option B integrity preserved — no API calls)
- [ ] All items in the Definition of Done are met
- [ ] All tests pass (target: existing 417 + new importer tests, with no failures)
- [ ] Linter is clean
- [ ] No code in `automation/db/`, `automation/workflow/`, `automation/prompts/`, or `espo_impl/` was modified
- [ ] No work outside the Step 12 scope was performed
- [ ] The `ImportProcessor` class can run a full import end-to-end against a real SQLite database
- [ ] AISession lifecycle is correctly honored (one row per session, updated through stages, never duplicated)
- [ ] Stage 6 commit is atomic (test verifies rollback on constraint violation)
- [ ] Stage 7 triggers do not roll back committed data on failure (test verifies)
- [ ] Any deviations from the API sketch above are documented in your final report
- [ ] Any ambiguities encountered in Section 11 and how you resolved them are documented in your final report

When complete, commit with a descriptive message and report what was built. Do not push — leave that for Doug.

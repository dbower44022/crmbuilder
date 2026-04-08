# Claude Code Implementation Prompt — Step 13: Impact Analysis Engine

## Context

You are implementing **Step 13 of the CRM Builder Automation roadmap** — the Impact Analysis Engine. The complete design for this work is in the Level 2 PRD at:

`PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`

**Read Section 12 of the L2 PRD before writing any code.** That section defines the entire Impact Analysis Engine: change sources, the cross-reference query engine (with 10 query type subsections), ChangeImpact record creation, pre-commit and post-commit modes, batch processing, deduplication, work item mapping, revision eligibility, document staleness detection, and schema changes.

This is step 13 of a 16-step roadmap (see Section 17). Steps 9 (database), 10 (workflow), 11 (prompts), and 12 (importer) are complete. Subsequent implementation steps (14–16) will build on top of the Impact Analysis Engine.

## Repository Context

This work goes in the `dbower44022/crmbuilder` repository. Read `CLAUDE.md` at the repo root for general project conventions. Read this prompt's "Foundation" section below carefully — it documents the API surface of Steps 9–12 your code must build on, including the Step 12 marker that the Import Processor leaves for you to consume.

## Where the Code Goes

Create a new package parallel to the existing automation packages:

```
automation/
├── __init__.py              # exists
├── db/                      # exists — Step 9
├── workflow/                # exists — Step 10
├── prompts/                 # exists — Step 11
├── importer/                # exists — Step 12 (writes IMPACT_ANALYSIS_NEEDED marker)
├── impact/                  # NEW — Step 13
│   ├── __init__.py
│   ├── engine.py            # ImpactAnalysisEngine class — public API
│   ├── queries.py           # Cross-reference query paths (Section 12.3)
│   ├── changeimpact.py      # ChangeImpact record creation (Section 12.4)
│   ├── deduplication.py     # Batch deduplication (Section 12.4.3)
│   ├── work_item_mapping.py # Affected record → work item mapping (Section 12.8.1)
│   ├── staleness.py         # Document staleness detection (Section 12.10)
│   ├── batch.py             # Batch processing sequence (Section 12.9)
│   └── precommit.py         # Pre-commit edit/delete flow (Section 12.5)
└── tests/
    ├── test_impact_engine.py
    ├── test_impact_queries.py
    ├── test_impact_changeimpact.py
    ├── test_impact_deduplication.py
    ├── test_impact_work_item_mapping.py
    ├── test_impact_staleness.py
    ├── test_impact_batch.py
    └── test_impact_precommit.py
```

**Tests live in the existing `automation/tests/` directory** — match the conventions established by Steps 9–12.

## Foundation — Existing API Surface

The Impact Analysis Engine reads from the database, queries the workflow engine, and is triggered by the Import Processor (post-commit) and the future UI (pre-commit). Use these existing APIs — do not bypass or duplicate them.

### Database — `automation.db.connection`

```python
from automation.db.connection import open_connection, connect, transaction

with connect(db_path) as conn:
    # ...

# Writes to ChangeImpact use transaction()
with transaction(conn):
    conn.execute("INSERT INTO ChangeImpact ...")
```

The Impact Analysis Engine writes to `ChangeImpact` and reads from many tables. Wrap multi-row writes in `transaction(conn)`.

### Workflow Engine — `automation.workflow.engine`

```python
from automation.workflow.engine import WorkflowEngine

engine = WorkflowEngine(conn)
status = engine.get_status(work_item_id)  # to check revision eligibility per Section 12.8.2
```

The Impact Analysis Engine never modifies work items directly. It only queries their status to determine revision eligibility per Section 12.8.2. The engine **does not call** `engine.revise()` — that is the administrator's decision (Section 12.1: "the engine does not automatically modify any downstream records or reopen any work items").

### Schema — `automation.db.client_schema`

Read `automation/db/client_schema.py` to confirm exact column names before writing queries. The relevant tables for Impact Analysis are:

- **ChangeLog** — the input. Each ChangeLog row is a single field-level change. The engine reads these to know what changed.
- **ChangeImpact** — the output. The engine writes ChangeImpact rows linking each ChangeLog row to records that are downstream-affected.
- **Cross-reference tables**: ProcessEntity, ProcessField, ProcessPersona — these are the primary query targets for impact tracing.
- **Layout tables**: LayoutPanel, LayoutRow, LayoutTab, ListColumn — secondary query targets when fields/entities change.
- **Persona, Decision, OpenIssue** — also queried via FK back-references.
- **Requirement** — process_id FK enables back-tracing.
- **WorkItem** — used for revision eligibility checks and staleness calculation (compares `WorkItem.completed_at` to `ChangeLog.changed_at`).

Note: Section 12.11 specifies a schema change. **You should not implement this schema change in Step 13.** Instead, document what the schema change requires and add it as an open issue in your final report. The Step 9 schema is locked. If the schema change is essential to make Step 13 work, stop and ask Doug rather than modifying `automation/db/`.

### Step 12 contract — the IMPACT_ANALYSIS_NEEDED marker

The Import Processor (Step 12) writes a marker on the AISession.notes column when it commits a session that needs impact analysis. The marker is:

```python
_IMPACT_ANALYSIS_MARKER = "IMPACT_ANALYSIS_NEEDED"
```

Found in `automation/importer/triggers.py`. The Impact Analysis Engine should:

1. Provide a method `analyze_pending_sessions()` that finds all AISession rows whose `notes` column contains this marker, runs impact analysis on the ChangeLog entries from those sessions, writes ChangeImpact rows, and **clears the marker** by removing it from the notes column.
2. The marker is appended with a `' | '` separator, so removal needs to handle the case where the AISession has other notes that should be preserved.

This is the post-commit analysis flow per Section 12.1. The Import Processor leaves the marker; the Impact Analysis Engine consumes it.

For pre-commit analysis (Section 12.5), the engine accepts a list of proposed ChangeLog entries directly without going through the marker.

## Definition of Done

This step is complete when **all** of the following are true:

1. **Cross-reference query module** (`queries.py`) implements Section 12.3 — one query function per source record type. Each function takes the connection and the changed record id, returns a list of affected records (table_name, record_id, impact_description).
   - 12.3.1 Field Change → ProcessField, LayoutRow, ListColumn, Persona, Decision, OpenIssue
   - 12.3.2 Entity Change → Field (transitive on delete), ProcessEntity, LayoutPanel, ListColumn, Relationship, Persona, Decision, OpenIssue
   - 12.3.3 FieldOption Change → fields that reference this option (rare, but documented)
   - 12.3.4 Process Change → ProcessStep, ProcessEntity, ProcessField, ProcessPersona, Requirement, Decision, OpenIssue
   - 12.3.5 Persona Change → ProcessPersona, ProcessStep (performer_persona_id), Decision, OpenIssue
   - 12.3.6 Relationship Change → no downstream references in the schema (relationships are leaf nodes); document this
   - 12.3.7 Domain Change → Entity (primary_domain_id), Process, Decision, OpenIssue
   - 12.3.8 Requirement Change → Decision, OpenIssue
   - 12.3.9 ProcessStep Change → ProcessEntity, ProcessField, ProcessPersona (when these have process_step_id set)
   - 12.3.10 Decision and OpenIssue Changes → leaf nodes; no downstream references

   Each query function returns dataclass instances with consistent shape. Implement helper functions for repeated patterns (e.g., scoping queries by FK).

2. **Transitive tracing** (Section 12.3 prefatory text): Delete operations trace transitively. If deleting an Entity surfaces its Fields as affected, the engine **also** traces each Field's downstream references. Update operations trace one level only. The query module must distinguish update vs. delete and apply the correct depth.

3. **ChangeImpact record creation** (`changeimpact.py`) implements Section 12.4:
   - Builds impact descriptions from the query results per Section 12.4.1
   - Determines `requires_review` per Section 12.4.2 (some impacts are informational only and do not require review)
   - Creates `ChangeImpact` rows in the database (post-commit) or returns them as in-memory objects (pre-commit)

4. **Batch deduplication** (`deduplication.py`) implements Section 12.4.3 — when multiple ChangeLog entries in the same batch surface the same `(affected_table, affected_record_id)` pair, the engine merges them into one ChangeImpact record that references the first ChangeLog entry that surfaced it and combines the impact descriptions.

5. **Batch processing** (`batch.py`) implements Section 12.9:
   - Trace each ChangeLog entry independently
   - Deduplicate the candidate impact set
   - Write the deduplicated set to ChangeImpact (post-commit) or hold for presentation (pre-commit)
   - Per Section 12.9.3, consolidate queries where possible — if five Field updates target the same entity, batch the cross-reference queries rather than running them five times

6. **Work item mapping** (`work_item_mapping.py`) implements Section 12.8.1 — given a flagged ChangeImpact, return the work item id that "owns" the affected record:
   - Field, FieldOption → entity_prd work item with matching entity_id
   - Process, ProcessStep, Requirement, ProcessEntity, ProcessField, ProcessPersona → process_definition work item with matching process_id
   - Persona → master_prd work item
   - Layout tables → entity_prd work item with matching entity_id
   - Domain → domain_overview work item with matching domain_id
   - Relationship → entity_prd work items for **both** entities involved (returns a list, not a single id)

   When multiple flagged impacts map to the same work item, group them so the administrator sees one entry per affected work item with a count and summary.

7. **Document staleness detection** (`staleness.py`) implements Section 12.10:
   - A work item's document is stale when any ChangeLog entry affects a record owned by that work item AND the ChangeLog.changed_at timestamp is later than the WorkItem.completed_at timestamp
   - Provide a function `get_stale_work_items(conn) -> list[StaleWorkItem]` that returns all work items whose documents are stale
   - Use the same ownership mapping as Section 12.8.1
   - The function does not modify any data; it only queries

8. **Pre-commit flow** (`precommit.py`) implements Section 12.5 — the edit and delete flows for direct administrator edits:
   - `analyze_proposed_change(conn, table_name, record_id, change_type, new_values)` returns a list of in-memory ChangeImpact objects (not yet persisted) describing the downstream effects of a proposed change
   - Pre-commit analysis does NOT write ChangeImpact rows. The caller (future UI in Step 15) presents them to the administrator and either commits with the change or cancels.
   - Per Section 12.5.3, a rationale is required for direct edits — the function signature should accept it as a parameter even though the engine itself doesn't enforce it (that's the UI's job)

9. **ImpactAnalysisEngine class** (`engine.py`) is the public API. The class bundles the query, ChangeImpact, deduplication, batch, work item mapping, and staleness modules:

```python
class ImpactAnalysisEngine:
    def __init__(self, conn): ...

    # Post-commit analysis (called by Import Processor or by the AISession marker scan)
    def analyze_session(self, ai_session_id: int) -> AnalysisResult:
        """Analyze the ChangeLog entries from a single AISession.
        Writes ChangeImpact rows. Returns a summary of what was created.
        """

    def analyze_pending_sessions(self) -> list[AnalysisResult]:
        """Find all AISessions with the IMPACT_ANALYSIS_NEEDED marker,
        run analysis on each, and clear the marker after success.
        Returns a list of AnalysisResult, one per session.
        """

    # Pre-commit analysis (called by future UI for direct edits)
    def analyze_proposed_change(
        self,
        table_name: str,
        record_id: int,
        change_type: str,  # 'update' or 'delete'
        new_values: dict | None = None,
        rationale: str | None = None,
    ) -> list[ProposedImpact]:
        """Analyze a proposed direct edit before commit.
        Returns in-memory impact objects without writing them.
        """

    # Work item mapping
    def get_affected_work_items(self, change_impact_ids: list[int]) -> list[AffectedWorkItem]:
        """Group ChangeImpact records by their owning work item."""

    # Staleness detection
    def get_stale_work_items(self) -> list[StaleWorkItem]:
        """Return all work items whose documents are stale."""
```

Method signatures may be refined as you implement, but the public API surface must cover post-commit analysis, pending session scan, pre-commit analysis, work item grouping, and staleness queries. Document any signature changes in your final report.

10. **The engine never modifies work items.** Per Section 12.1, the engine "does not automatically modify any downstream records or reopen any work items." It surfaces information; the administrator decides. Do not call `engine.revise()` from the impact analysis code.

11. **Marker handling**: when `analyze_pending_sessions()` processes a session, it must clear the `IMPACT_ANALYSIS_NEEDED` marker from `AISession.notes` while preserving any other text in that column. The marker is appended with `' | '` as a separator.

12. **All multi-row writes use `transaction(conn)`**. The engine never commits partial state.

13. **pytest test suite** with **tests written alongside each module as it is built**. Coverage requirements:
    - `queries.py`: each of the 10 query types returns the correct affected records for a populated test database. Transitive tracing on delete is verified. Update tracing depth is one level only.
    - `changeimpact.py`: impact descriptions are correctly formatted; `requires_review` flag is set per the rules in Section 12.4.2.
    - `deduplication.py`: when two ChangeLog entries surface the same affected record, only one ChangeImpact row is created with merged descriptions.
    - `batch.py`: batch processing handles multi-entry batches correctly; query consolidation works (test by counting executed SQL queries with a wrapper).
    - `work_item_mapping.py`: each ownership rule maps correctly; Relationship maps to both entity_prd work items.
    - `staleness.py`: a work item with completed_at before a relevant ChangeLog.changed_at is reported stale; one with completed_at after is not; work items with no ChangeLog entries are not stale.
    - `precommit.py`: returns in-memory objects without writing; both update and delete change_types work; rationale parameter is accepted but not enforced.
    - `engine.py`: end-to-end test that creates a populated database via real fixtures, runs the Step 12 importer to create a session with the marker, runs `analyze_pending_sessions()`, asserts ChangeImpact rows were created and the marker was cleared.
    - All tests use real SQLite databases via `run_client_migrations()`, never mocks.

14. **All tests pass**: `uv run pytest automation/tests/ -v`

15. **Linter clean**: `uv run ruff check automation/`

## Working Style

- **Read Section 12 of the L2 PRD before writing any code.** Section 12 has 11 subsections and 10 query type definitions. The query module is the largest piece of work — read 12.3 carefully and verify every join column against `automation/db/client_schema.py`.
- **Read the existing Step 9–12 code** in `automation/db/`, `automation/workflow/`, `automation/prompts/`, and `automation/importer/` so your code uses the real APIs.
- **Read `automation/db/client_schema.py` for exact column names** before writing any SELECT/INSERT statements. Do not infer column names from the L2 PRD prose.
- **Write tests alongside each module**, not at the end.
- **Implement in this order**: queries → changeimpact → deduplication → batch → work_item_mapping → staleness → precommit → engine. Each layer depends on earlier layers.
- **Surface ambiguities, do not invent answers.** Examples of things to flag rather than guess:
  - Section 12.11 specifies a schema change. What does it require, and is it essential for Step 13? Stop and report rather than modifying `automation/db/`.
  - The `requires_review` determination in Section 12.4.2 — what specific rules distinguish an impact that requires review from one that does not?
  - For Section 12.3.6 (Relationship Change), the L2 PRD says relationships are leaf nodes. Confirm this matches the schema (i.e., no other table has a relationship_id FK).
  - For pre-commit analysis on a delete, how should the engine evaluate the impact when the record being deleted has cascading FK references that the schema does not declare ON DELETE CASCADE?
- **No bypassing the database API.** Use `automation.db.connection.transaction()` for all writes.
- **No GUI code.** UI is Step 15.
- **No document generation.** Step 14.
- **Do not modify `espo_impl/`, `automation/db/`, `automation/workflow/`, `automation/prompts/`, or `automation/importer/`.** Steps 9–12 are locked. If you find a bug, report it but do not fix it as part of Step 13. If Section 12.11's schema change is essential, stop and ask Doug.

## Out of Scope for This Step

- Modifying any code in Steps 9–12
- Implementing the Section 12.11 schema change (report it, don't apply it)
- Calling the Workflow Engine to revise or unblock work items (engine surfaces information only)
- Generating documents (Step 14)
- UI code (Step 15)
- Modifying the database schema or migrations

## Reference Documents

Primary: `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`

Sections to read carefully before starting:
- **Section 12 (entire section)** — Impact Analysis Engine. This is your spec.
- **Section 12.3** — Cross-reference query engine. Ten subsections, one per source record type.
- **Section 12.4** — ChangeImpact record creation, including the `requires_review` rules.
- **Section 12.8** — Interaction with revision workflow, including the work item mapping rules.
- **Section 12.9** — Batch processing.
- **Section 12.10** — Document staleness detection.
- **Section 12.11** — Schema changes (report, do not implement).
- **Section 7.2** — ChangeLog schema (your input).
- **Section 7.3** — ChangeImpact schema (your output).
- **Section 11.10.1** — Where Step 12 calls Step 13. The Import Processor leaves the `IMPACT_ANALYSIS_NEEDED` marker; you consume it.

You may also find this useful for context, but **do not implement any of it in step 13**:
- **Section 13** — Document Generator. Step 14 will implement this. Section 13.6 (staleness handling) consumes the staleness output from Step 13.

## Final Check

Before declaring this step complete, verify:

- [ ] `grep -rn "phase TEXT" automation/db/` returns zero matches (Step 9 fix verified, no regression)
- [ ] `grep -rn "anthropic.com\|api\.anthropic" automation/impact/` returns zero matches (Option B integrity preserved)
- [ ] `grep -rn "engine.revise\|engine.complete\|engine.start" automation/impact/` returns zero matches OR matches are only in tests (engine surfaces information, never modifies work items)
- [ ] All items in the Definition of Done are met
- [ ] All tests pass (target: existing 609 + new impact tests, with no failures)
- [ ] Linter is clean
- [ ] No code in `automation/db/`, `automation/workflow/`, `automation/prompts/`, `automation/importer/`, or `espo_impl/` was modified
- [ ] No work outside the Step 13 scope was performed
- [ ] The `ImpactAnalysisEngine` can run end-to-end against a real SQLite database, consuming an `IMPACT_ANALYSIS_NEEDED` marker left by Step 12 and writing ChangeImpact rows
- [ ] The IMPACT_ANALYSIS_NEEDED marker is correctly cleared after analysis without disturbing other notes content
- [ ] Section 12.11's schema change is reported in the final report, not applied
- [ ] Any deviations from the API sketch above are documented in your final report
- [ ] Any ambiguities encountered in Section 12 and how you resolved them are documented in your final report

When complete, commit with a descriptive message and report what was built. Do not push — leave that for Doug.

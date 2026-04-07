# Claude Code Implementation Prompt — Step 11: Prompt Generator

## Context

You are implementing **Step 11 of the CRM Builder Automation roadmap** — the Prompt Generator. The complete design for this work is in the Level 2 PRD at:

`PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`

**Read Section 10 of the L2 PRD before writing any code.** That section defines the entire Prompt Generator: prompt structure, context assembly rules per work item type, decision and issue inclusion rules, structured output format (common envelope and type-specific payloads), session type variations, interview guide selection, prompt templates, and context size management.

This is step 11 of a 16-step roadmap (see Section 17). Steps 9 (database layer) and 10 (workflow engine) are complete. Subsequent implementation steps (12–16) will build on top of the Prompt Generator.

## Repository Context

This work goes in the `dbower44022/crmbuilder` repository. Read `CLAUDE.md` at the repo root for general project conventions. Read this prompt's "Foundation" section below carefully — it documents the database and workflow API surface your code must build on.

## Where the Code Goes

Create a new package parallel to `automation/db/` and `automation/workflow/`:

```
automation/
├── __init__.py              # exists
├── db/                      # exists — Step 9
├── workflow/                # exists — Step 10
├── prompts/                 # NEW — Step 11
│   ├── __init__.py
│   ├── generator.py         # PromptGenerator class — public API
│   ├── structure.py         # 6-section prompt assembly (Section 10.2)
│   ├── context.py           # Context assembly per work item type (Section 10.3)
│   ├── decisions_issues.py  # Decision and OpenIssue inclusion rules (Section 10.4)
│   ├── output_format.py     # Structured output specification (Section 10.5)
│   ├── session_types.py     # Initial / revision / clarification variations (Section 10.6)
│   ├── guide_selection.py   # Interview guide selection (Section 10.7)
│   ├── templates.py         # Template rendering (Section 10.8)
│   └── context_size.py      # Priority tier management (Section 10.9)
└── tests/
    ├── test_prompts_generator.py
    ├── test_prompts_structure.py
    ├── test_prompts_context.py
    ├── test_prompts_decisions_issues.py
    ├── test_prompts_output_format.py
    ├── test_prompts_session_types.py
    ├── test_prompts_guide_selection.py
    ├── test_prompts_templates.py
    └── test_prompts_context_size.py
```

**Tests live in the existing `automation/tests/` directory** — match the Step 9 and Step 10 conventions.

## Foundation — Existing API Surface

The Prompt Generator reads from the database and queries the Workflow Engine. Use these existing APIs — do not bypass them and do not duplicate functionality.

### Database — `automation.db.connection`

```python
from automation.db.connection import open_connection, connect, transaction

# Context manager (preferred)
with connect(db_path) as conn:
    # ... use conn ...

# Transaction wrapping for any writes
with transaction(conn):
    conn.execute("INSERT INTO ...")
```

The Prompt Generator is **mostly read-only** against the requirements database. The only writes it performs are creating an `AISession` row when a prompt is generated (per Section 10.1 — "When the administrator selects a ready work item and initiates prompt generation"). All such writes must be wrapped in `transaction(conn)`.

### Workflow Engine — `automation.workflow.engine`

```python
from automation.workflow.engine import WorkflowEngine

engine = WorkflowEngine(conn)
status = engine.get_status(work_item_id)        # current status
phase = engine.get_phase_for(work_item_id)      # phase number 1–12
```

The Prompt Generator should call `WorkflowEngine.get_phase_for()` to populate the Session Header phase number — do not duplicate the phase mapping logic.

### Phase mapping — `automation.workflow.phases`

```python
from automation.workflow.phases import get_phase, get_phase_name

phase_num = get_phase("entity_prd")             # 2
phase_label = get_phase_name(2)                  # "Entity Definition"
```

Use these for any phase number → phase name conversion in the Session Header.

### Schema reference

Read `automation/db/client_schema.py` to confirm exact column names before writing queries. Do not assume column names from the L2 PRD prose — verify against the schema.

Key tables the Prompt Generator queries:

- **WorkItem** — to read item_type, item identifiers, status, and the related domain/entity/process
- **Domain, Entity, Process, Persona, Field, FieldOption, Relationship, BusinessObject, ProcessStep, Requirement** — for context assembly
- **ProcessEntity, ProcessField, ProcessPersona** — cross-reference tables for process scope
- **Decision, OpenIssue** — for Sections 4 and 5 of the prompt
- **AISession** — to write a new session row when a prompt is generated
- **Client** — for organization_overview and crm_platform fields used in some context payloads

The `Client` table lives in the **master** database, not the client database. The Prompt Generator may need both connections for some context assembly operations. Section 10.3 tells you which payloads need Client data.

## Definition of Done

This step is complete when **all** of the following are true:

1. **Prompt structure module** (`structure.py`) implements Section 10.2 — the 6-section fixed-order prompt: Session Header, Session Instructions, Context, Locked Decisions, Open Issues, Structured Output Specification. The module assembles these sections from inputs provided by other modules and returns the complete prompt as a single text string.

2. **Context assembly module** (`context.py`) implements Section 10.3 with one assembly function per work item type:
   - 10.3.1 master_prd
   - 10.3.2 business_object_discovery
   - 10.3.3 entity_prd
   - 10.3.4 domain_overview
   - 10.3.5 process_definition
   - 10.3.6 domain_reconciliation
   - 10.3.7 yaml_generation
   - 10.3.8 crm_selection
   - 10.3.9 crm_deployment

   Each function takes the connection and the work item id, queries the database for the data the L2 PRD specifies for that type, and returns a structured representation (dict or dataclass) that the structure module can format into the Context section.

   Three item_types do **not** need context assembly: stakeholder_review (conducted outside Claude), crm_configuration (tool-driven), verification (tool-generated). These are listed in Section 10.3 prefatory text — the Prompt Generator returns a clear "no prompt generated" indication for these item_types instead of producing a prompt.

3. **Decision and Issue inclusion module** (`decisions_issues.py`) implements Section 10.4 — the rules for which Decision and OpenIssue records appear in a generated prompt, scoped by work item type. The inclusion rules vary by work item type and are listed at line 1113 of the L2 PRD plain text (Section 10.4) — read those rules carefully and implement them as a per-type filter.

4. **Structured output format module** (`output_format.py`) implements Section 10.5:
   - **Common envelope** (10.5.1): output_version, work_item_type, work_item_id, session_type, payload, decisions[], open_issues[]
   - **Type-specific payloads** (10.5.2): one payload structure per prompt-capable work item type, defined in Section 10.5 paragraphs covering each type. The module produces the specification text that goes into Section 6 of the prompt — telling the AI what JSON structure to return at the end of the session.

5. **Session type variations module** (`session_types.py`) implements Section 10.6:
   - **Initial sessions** (10.6.1) — first time a work item is being worked
   - **Revision sessions** (10.6.2) — reopened work items, requires revision reason in the header and includes the prior structured_output for the AI to revise
   - **Clarification sessions** (10.6.3) — follow-up questions about completed work, requires a clarification topic in the header

   The session type affects the Session Header content and may affect what's included in Context. The module provides functions that take a session type and return the appropriate header text and any additional context blocks.

6. **Interview guide selection module** (`guide_selection.py`) implements Section 10.7. Each prompt-capable work item type maps to exactly one prompt-optimized interview guide file. The L2 PRD lists the mappings at line 1173 — for example, `master_prd` maps to `prompt-master-prd.md`, `entity_prd` maps to `prompt-entity-prd.md`, and so on. Read the file from `PRDs/process/interviews/prompt-templates/` (the path the L2 PRD specifies) and return its contents for inclusion in the prompt's Section 2 (Session Instructions).

   **Important**: Section 10.7 also notes that four work item types do not yet have source guides written: domain_overview, yaml_generation, crm_selection, and crm_deployment. For these, the module should return a clear placeholder that says "Guide not yet authored" rather than failing — the engine should still generate a prompt, just with the placeholder in Section 2. Surface the gap so it's visible.

7. **Template module** (`templates.py`) implements Section 10.8. Templates are stored at `PRDs/process/interviews/prompt-templates/template-{work_item_type}.md`. Each template contains static text, placeholder tokens that get replaced with database values, and session-type markers identifying content included only for initial/revision/clarification sessions. The template module reads a template file and renders it with a context dict, replacing tokens and stripping out blocks for non-matching session types.

   **Important**: Like the interview guides, these template files do not yet exist. The module should support reading them when present, and return a sensible default template (just the section markers) when not present, with a clear "template not yet authored" warning. Do not create template files as part of Step 11 — they are author-supplied content.

8. **Context size management module** (`context_size.py`) implements Section 10.9 — Priority Tier handling. Section 10.9.1 defines three priority tiers: Priority 1 (always included), Priority 2 (reduced last), Priority 3 (summarized if needed). The module accepts a context dict and a target token budget, then returns a possibly-reduced context dict. Use a simple word count as a proxy for tokens (1 word ≈ 1.3 tokens) — do not pull in tiktoken or any LLM tokenizer library.

9. **PromptGenerator class** (`generator.py`) is the public API. This is what the UI (Step 15) and possibly other components will call:

```python
class PromptGenerator:
    def __init__(self, conn, master_conn=None): ...
        # conn: open client database connection
        # master_conn: optional master database connection,
        #   required for work item types that need Client data

    def generate(
        self,
        work_item_id: int,
        session_type: str = "initial",
        revision_reason: str | None = None,
        clarification_topic: str | None = None,
    ) -> str:
        """Generate a complete prompt for the given work item.

        Returns the prompt as a single string ready for the administrator
        to copy into Claude.ai. Also creates an AISession row recording
        the generated prompt and session metadata.

        Raises ValueError if:
        - The work item is not found
        - The work item is not in status 'ready' or 'in_progress' (per 10.1)
        - The work item type does not require a prompt
          (stakeholder_review, crm_configuration, verification)
        - revision_reason is missing for session_type='revision'
        - clarification_topic is missing for session_type='clarification'
        """

    def is_promptable(self, item_type: str) -> bool:
        """Return True if this item_type produces a prompt."""
```

Method signatures may be refined as you implement, but the public API surface must cover prompt generation, session metadata recording, and the "is this type promptable" check. Document any signature changes in your final report.

10. **AISession recording**: When `generate()` is called successfully, write an AISession row with:
    - `work_item_id` set to the work item
    - `session_type` set to the session type
    - `generated_prompt` set to the full prompt text
    - `import_status` set to `'pending'`
    - `started_at` set to CURRENT_TIMESTAMP
    - `raw_output`, `structured_output`, `completed_at` left NULL (filled in by Step 12 Import Processor later)

    Wrap the insert in `transaction(conn)`.

11. **All multi-row queries are read-only and do not require transactions.** The single AISession insert is the only write.

12. **pytest test suite** with **tests written alongside each module as it is built**. Coverage requirements:
    - `structure.py`: prompt assembly produces all 6 sections in correct order; section content is correctly delimited
    - `context.py`: each of the 9 context assembly functions produces correct output for a populated test database; the 3 non-promptable item_types raise an appropriate error or return a marker
    - `decisions_issues.py`: each work item type's inclusion rule correctly filters Decision and OpenIssue records (test with a database containing global, domain-scoped, process-scoped, and entity-scoped records)
    - `output_format.py`: common envelope is correct for every type; type-specific payloads list the right fields
    - `session_types.py`: initial/revision/clarification headers are correct; revision sessions include the revision reason; clarification sessions include the clarification topic
    - `guide_selection.py`: known mappings return the correct file path; missing files return the placeholder message; do not test against real guide files (use temp files in test fixtures)
    - `templates.py`: token replacement works; session-type blocks are correctly included/excluded; missing template files return the default
    - `context_size.py`: priority tier reduction correctly trims Priority 3 first, then Priority 2, never Priority 1; trimming stops once under budget
    - `generator.py`: end-to-end test that creates a populated database, generates a prompt for a real work item, asserts the prompt contains expected sections, and verifies the AISession row was created correctly
    - All status validation tests: generate() raises ValueError for work items not in ready/in_progress; raises for non-promptable types; raises for missing session_type parameters

13. **All tests pass**: `uv run pytest automation/tests/ -v`

14. **Linter clean**: `uv run ruff check automation/`

## Working Style

- **Read Section 10 of the L2 PRD before writing any code.** Also read Section 10.5.2 carefully — the type-specific payload definitions are spread across paragraphs, not in a single table.
- **Read the existing Step 9 and Step 10 code** in `automation/db/` and `automation/workflow/` so your code uses the real APIs.
- **Read `automation/db/client_schema.py` for exact column names** before writing any queries. Do not infer column names from the L2 PRD prose.
- **Write tests alongside each module**, not at the end.
- **Implement in this order**: output_format → context → decisions_issues → session_types → guide_selection → templates → context_size → structure → generator. The dependencies flow from leaf modules up to the public API.
- **Surface ambiguities, do not invent answers.** Examples of things to flag rather than guess:
  - The L2 PRD says some interview guides "do not yet have source guides" — should the Prompt Generator refuse to generate prompts for those types, or generate with a placeholder? (My recommendation: generate with placeholder, but confirm with Doug.)
  - Whether AISession.started_at should be set when generate() is called or when the administrator actually starts the session in Claude.ai
  - Whether revision sessions should include the prior structured_output verbatim or in a summarized form
- **No bypassing the database API.** Use `automation.db.connection.connect()` and `transaction()` for any writes.
- **No GUI code.** UI is Step 15.
- **No actual API calls to Claude.** This is Option B integration — the Prompt Generator produces a text block the administrator copies into a Claude.ai session. There is no HTTP call to anthropic.com anywhere in this code.
- **No import processing.** Step 12.
- **Do not modify `espo_impl/`, `automation/db/`, or `automation/workflow/`.** Steps 9 and 10 are locked. If you find a bug, report it but do not fix it as part of Step 11.
- **Do not create interview guide files or template files.** Those are author-supplied content. Your code reads them when present and degrades gracefully when not.

## Out of Scope for This Step

- Calling the Claude API or any HTTP endpoint
- Parsing AI output (that is Step 12 — Import Processor)
- Storing AI output (Step 12)
- Running impact analysis (Step 13)
- Generating documents (Step 14)
- UI code (Step 15)
- Modifying the database schema or migrations
- Creating or editing interview guide content
- Creating or editing prompt template content

## Reference Documents

Primary: `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`

Sections to read carefully before starting:
- **Section 10 (entire section)** — Prompt Generator. This is your spec.
- **Section 10.3** — Context assembly rules per work item type. Note that each subsection (10.3.1 through 10.3.9) lists the specific data each prompt type needs.
- **Section 10.4** — Decision and Issue inclusion rules. The rules vary by work item type.
- **Section 10.5** — Structured output format. Common envelope plus 9 type-specific payloads.
- **Section 6.3** — WorkItem schema (item_type values and CHECK constraint)
- **Section 7.1** — AISession schema (the table you write to)
- **Section 6.1** — Decision schema (scope columns determine inclusion)
- **Section 6.2** — OpenIssue schema (scope columns determine inclusion)
- **Section 14.2.3** — item_type-to-phase mapping (already implemented in `automation/workflow/phases.py`)

You may also find this useful for context, but **do not implement any of it in step 11**:
- **Section 11** — Import Processor. Step 12 will implement this. Useful for understanding how the structured_output you specify in Section 6 of the prompt is later parsed and imported.

## Final Check

Before declaring this step complete, verify:

- [ ] `grep -rn "phase TEXT" automation/db/` returns zero matches (Step 9 fix verified, no regression)
- [ ] `grep -rn "import sqlite3" automation/prompts/` shows sqlite3 is only imported in modules that actually need raw SQL — most should use the connection helpers from `automation.db.connection`
- [ ] All items in the Definition of Done are met
- [ ] All tests pass (target: existing 306 + new prompt generator tests, with no failures)
- [ ] Linter is clean
- [ ] No code in `automation/db/`, `automation/workflow/`, or `espo_impl/` was modified
- [ ] No work outside the Step 11 scope was performed
- [ ] The `PromptGenerator` class can produce a complete prompt end-to-end against a real SQLite database, and the resulting AISession row is correctly recorded
- [ ] Any deviations from the API sketch above are documented in your final report
- [ ] Any ambiguities encountered in Section 10 and how you resolved them are documented in your final report

When complete, commit with a descriptive message and report what was built. Do not push — leave that for Doug.

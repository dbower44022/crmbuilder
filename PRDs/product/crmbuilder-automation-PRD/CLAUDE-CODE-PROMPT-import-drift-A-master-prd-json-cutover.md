# Claude Code Prompt — Import Drift A: Master PRD JSON Cutover

**Series:** import-drift (Prompt A of N)
**Repo:** crmbuilder
**Read first:** `CLAUDE.md`, then this prompt in full, then `SESSION-PROMPT-import-pipeline-drift.md` for the diagnostic context.
**Last Updated:** 04-11-26

## Background

The L2 PRD (Sections 10 and 11) specifies a JSON-based AI-session interchange: the Prompt Generator emits a prompt instructing Claude.ai to return a structured JSON envelope, the user pastes the JSON into the Import Processor, and the seven-stage pipeline parses, validates, maps, reviews, and commits the data.

**Section 11 is built and works.** `automation/importer/` implements the seven-stage pipeline and `automation/ui/importer/stage_receive.py` is a paste-JSON box exactly as §11.1 Stage 1 specifies.

**Section 10 is not built.** `automation/core/master_prd_prompt.py` is a hardcoded f-string that reads the source interview guide (`PRDs/process/interviews/interview-master-prd.md`) and instructs Claude.ai to *"Produce the Master PRD as a Word document"* — no JSON anywhere. As a workaround, `automation/importer/parsers/master_prd_docx.py` was written as an adapter that takes the resulting `.docx`, walks it with `python-docx`, and emits a Path B envelope JSON string to feed into the pipeline.

This prompt fixes the drift for the Master PRD work item type by building the missing Section 10 pieces (prompt-optimized guide, prompt template, and a real Prompt Generator) so Claude.ai is asked for JSON directly. The docx adapter is **kept alive in parallel** during transition for A/B validation; a later prompt in this series will retire it.

## Scope

**In scope:**
- Author the prompt-optimized Master PRD guide
- Author the Master PRD prompt template
- Define the concrete JSON schema for the master_prd payload
- Rewrite `automation/core/master_prd_prompt.py` to use the guide + template + database context
- Add unit tests for the new prompt generator
- Verify §11.2 Layer 3 payload validation accepts the schema

**Out of scope:**
- Other work item types (domain_overview, entity_prd, process_definition, domain_reconciliation, etc.) — those get their own prompts later in the series
- Deleting `automation/importer/parsers/master_prd_docx.py` — keep it alive for A/B validation
- §10.6 revision and clarification session variants — initial sessions only
- §10.9 context size management — Master PRD is the first phase, has no upstream context to manage
- Any UI changes to `stage_receive` or downstream stages — they already work

## Tasks

### Task 1 — Define the master_prd JSON payload schema

L2 PRD §10.5.2 describes the master_prd payload in prose but explicitly states *"Exact field-level JSON schemas are defined during implementation."* This task produces the concrete schema.

Create `automation/core/schemas/master_prd_payload.py` containing:

1. A Python `TypedDict` (or `pydantic` model — match whatever pattern the codebase already uses for the envelope) defining the master_prd payload structure with these top-level keys, derived from §10.5.2 line 1201:
   - `organization_overview` (string)
   - `personas` (array of objects with `name`, `code`, `description`, `responsibilities`, `crm_capabilities`)
   - `domains` (array of objects with `name`, `code`, `description`, `sort_order`, optional nested `sub_domains` with the same shape plus `is_service` boolean)
   - `processes` (array of objects with `name`, `code`, `description`, `sort_order`, `tier` ∈ {core, important, enhancement}, `business_value`, `key_capabilities` array, `domain_code` referencing the parent domain)
   - `cross_domain_services` (array of objects with `name`, `description`, `capabilities`, `consuming_domains`, `owned_entities`)
   - `system_scope` (object with `in_scope` array, `out_of_scope` array, `integrations` array)

2. A JSON Schema document (`automation/core/schemas/master_prd_payload.schema.json`) that the §11.2 Layer 3 validator can use. This is the source of truth — the Python TypedDict and the JSON Schema must agree.

3. A short module-level docstring explaining that this schema is consumed by both the Prompt Generator (rendered into the prompt-optimized guide as the output specification the AI must follow) and the Import Processor (validated in §11.2 Layer 3).

Before authoring the schema, **read** the `master_prd` mapping in §11.3.1 of the L2 PRD (`PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`) and confirm the schema field names align with what the existing mapper writes to `Client.organization_overview`, `Persona`, `Domain`, and `Process` records. If there is a mismatch, the schema follows the mapper, not the §10.5.2 prose — the mapper is the source of truth for what the database expects.

### Task 2 — Author the prompt-optimized Master PRD guide

Create `PRDs/process/interviews/prompt-optimized/` directory and inside it create `prompt-master-prd.md`.

This guide is **derived from** `PRDs/process/interviews/interview-master-prd.md` but is structured for AI consumption rather than human implementer consumption. Differences:

- Drop sections that are instructions to a human implementer about how to conduct the interview (turn-taking guidance, "ask the user," confirmation checkpoints between sections)
- Keep the substantive topic coverage and the interview question content
- Add a top-of-file header containing `source_version` referencing the version of `interview-master-prd.md` it was derived from (per §10.7 line 1247–1249)
- Add a final section titled **"Structured Output Specification"** that contains:
  - The §10.5.1 envelope structure with `output_version`, `work_item_type` (must be the literal string `"master_prd"`), `work_item_id` (placeholder `{work_item_id}` to be filled by the template), `session_type`, `payload`, `decisions`, `open_issues`
  - The full master_prd payload schema from Task 1, rendered as a JSON example with field-level comments explaining what goes where
  - Explicit instructions: *"At the end of this conversation, produce a single JSON code block containing the complete envelope. Do not include any other JSON code blocks earlier in the conversation. Do not wrap the JSON in additional prose after the code block."*
  - A note that the JSON must be syntactically valid and that the application's parser strips markdown code fences automatically (per §11.2 Layer 1)

### Task 3 — Author the Master PRD prompt template

Create `PRDs/process/interviews/prompt-templates/` directory and inside it create `template-master_prd.md`.

Per L2 PRD §10.8, the template defines the six-section prompt structure with placeholder tokens. The six sections per §10.2 (read this section from the L2 PRD before authoring) determine the layout. At minimum the template must include placeholder tokens for:

- `{client_name}` — read from the Client record
- `{client_code}` — read from the Client record
- `{work_item_id}` — read from the WorkItem record being processed
- `{session_type}` — `"initial"` for this prompt; other values are out of scope for this task
- `{generated_at}` — timestamp in `MM-DD-YY HH:MM` format
- `{prompt_optimized_guide_body}` — the full body of `prompt-master-prd.md`

The template includes static section headers, behavioral instructions to the AI, and the placeholder tokens. It does **not** include the JSON schema directly — that comes in via `{prompt_optimized_guide_body}`.

### Task 4 — Rewrite `automation/core/master_prd_prompt.py`

Replace the current 64-line hardcoded f-string implementation with a new implementation that:

1. Loads `PRDs/process/interviews/prompt-templates/template-master_prd.md`
2. Loads `PRDs/process/interviews/prompt-optimized/prompt-master-prd.md`
3. Reads the relevant context from the database (client name, client code, work item id) — if the existing function signature passes these in, accept them as arguments; if not, accept a database session and a work_item_id and look them up
4. Substitutes all placeholder tokens
5. Returns the assembled prompt text
6. Retains the existing `save_prompt()` companion that writes the assembled prompt to a `.md` file with the existing filename convention `master-prd-prompt-{client_code}-{YYYYMMDD-HHMMSS}.md`

The function signature change must be compatible with all existing call sites. Use grep to find every caller of `build_master_prd_prompt` before editing and update them in the same commit.

**Do not delete** `master_prd_prompt.py` — rewrite it in place. The module name and entry-point function name stay the same.

### Task 5 — Tests

Add or extend tests for `automation/core/master_prd_prompt.py`:

1. The assembled prompt contains the literal string `"master_prd"` as the `work_item_type` value in the envelope spec
2. The assembled prompt contains all six payload top-level keys from Task 1
3. Placeholder substitution works for `{client_name}`, `{client_code}`, `{work_item_id}`, `{generated_at}`
4. `save_prompt()` writes a file with the correct filename pattern
5. A round-trip test: assemble the prompt, extract the JSON example block from it, parse it with `json.loads`, and validate it against the JSON Schema from Task 1 — this proves the example in the prompt is valid against the schema we'll validate against in §11.2

Run the existing test suite with `uv run pytest tests/ -v` and confirm it still passes. Run `uv run ruff check automation/` and confirm clean.

### Task 6 — Wire payload validation in §11.2 Layer 3 (verification only)

This task is **verification, not implementation**. Open `automation/importer/` and find where §11.2 Layer 3 payload structure validation happens. Confirm it can load and apply the JSON Schema from Task 1 for the `master_prd` work item type. If wiring already exists for other types and just needs the new schema registered, register it. If no per-type schema validation exists yet, **stop and report** — do not invent it. That gap, if it exists, is its own follow-up prompt.

## Out of Scope (Reminders)

- Do not touch `automation/importer/parsers/master_prd_docx.py` — the adapter stays alive for A/B validation
- Do not touch any other phase's prompt generator, parser, or mapper
- Do not implement §10.6 revision or clarification flows
- Do not implement §10.9 context size management
- Do not add prompt-optimized guides for other phases — only `prompt-master-prd.md` in this prompt
- Do not delete or modify `interview-master-prd.md` — the prompt-optimized version is derived from it, not a replacement

## Acceptance Criteria

When this prompt is complete:

1. `PRDs/process/interviews/prompt-optimized/prompt-master-prd.md` exists with a structured output specification section containing the envelope and payload schema
2. `PRDs/process/interviews/prompt-templates/template-master_prd.md` exists with placeholder tokens
3. `automation/core/schemas/master_prd_payload.py` and `master_prd_payload.schema.json` exist and agree
4. `automation/core/master_prd_prompt.py` produces an assembled prompt that, when read by a human, clearly instructs Claude.ai to return a JSON envelope with a master_prd payload — no mention of "Word document" anywhere in the assembled prompt
5. All tests pass; ruff is clean
6. `automation/importer/parsers/master_prd_docx.py` is **untouched**
7. A short note in the commit message states whether Task 6's verification found the §11.2 Layer 3 wiring complete or identified a gap to follow up on

## Working Style

- Read all referenced PRD sections before authoring any file
- Make minimal edits to existing files; surgical str_replace where possible
- Ask before removing any existing functionality
- After completing all tasks, post a summary stating: (a) what was created, (b) what was modified, (c) what was verified in Task 6, and (d) the next required step (which will be Doug running an A/B test: generate a Master PRD prompt the new way, run it in Claude.ai, paste the resulting JSON into stage_receive, and confirm the import lands the same data the docx adapter would have produced).

## Filename Convention Note

This is Prompt A in the import-drift series. Subsequent prompts use:
- `CLAUDE-CODE-PROMPT-import-drift-B-{descriptor}.md`
- `CLAUDE-CODE-PROMPT-import-drift-C-{descriptor}.md`
- etc.

Likely B candidates (not committed yet, for planning context only): retire the master_prd_docx adapter once A/B validation passes; or extend the pattern to the next phase (probably `business_object_discovery` since §11.1 Stage 7 specifically wires it as the downstream of master_prd).

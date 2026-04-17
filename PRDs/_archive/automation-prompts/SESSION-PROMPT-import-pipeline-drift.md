# SESSION PROMPT — Interview Import Pipeline Drift

**Last Updated:** 04-11-26 (current session)
**Repo:** crmbuilder
**Read first:** crmbuilder `CLAUDE.md`, then this prompt in full.

## Purpose

In a prior session, Doug ran a Master PRD interview test and noticed no JSON file was produced. Investigation confirmed a **system-wide drift** between the L2 PRD design and the implemented Interview Import pipeline. This session resumes that investigation, completes the gap analysis, and produces a correction plan.

## Prior finding (do not re-derive — verify only)

**The L2 PRD specifies a JSON-based interchange. The code implements a .docx-based interchange. Neither references the other.**

### Evidence — L2 PRD design (intended)

`PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`, Section 10.5 line 1191 (in pandoc plain-text conversion):

> "AI sessions produce a JSON block at the end of each conversation for the Import Processor to parse. JSON is chosen for parsing reliability over human readability."

Section 10.5.1 specifies a **common envelope**: `output_version`, `work_item_type`, `work_item_id`, `session_type`, `payload`, `decisions`, `open_issues`.

Section 10.5.2 specifies **type-specific JSON payloads** for every work item type, including `master_prd`, `business_object_discovery`, `entity_prd`, `domain_overview`, `process_definition`, `domain_reconciliation`, `yaml_generation`, `crm_selection`, and `crm_deployment`.

Section 10.7 specifies **prompt-optimized guides** at `PRDs/process/interviews/prompt-optimized/` (e.g. `prompt-master-prd.md`), distinct from the source interview guides at `PRDs/process/interviews/`.

Section 10.8 specifies **prompt templates** at `PRDs/process/interviews/prompt-templates/template-{work_item_type}.md`.

Sections 10.6.2 and 10.6.3 specify that **revision** and **clarification** sessions reuse the same JSON envelope.

**Section 11 (Import Processor) was NOT read in the prior session.** Reading it in full is the first action of this session.

### Evidence — implementation (actual)

`automation/core/master_prd_prompt.py` is 64 lines. Lines 31–32 contain the entire format instruction the prompt sends to Claude.ai:

```
"Follow the interview guide below. Produce the Master PRD as "
"a Word document following CRM Builder document standards "
```

- No JSON. No envelope. No payload spec. No structured output instructions.
- It reads the **source** interview guide (`interview-master-prd.md`), not a prompt-optimized guide.
- It uses **no template** from `prompt-templates/` — it's a hardcoded f-string header.
- The companion `save_prompt()` writes the prompt itself to a `.md` file named `master-prd-prompt-{client_code}-{YYYYMMDD-HHMMSS}.md`. That `.md` file is the **prompt**, not Claude.ai's output.

The downstream importer parses **.docx files** via `automation/cbm_import/parsers/master_prd.py`, sitting next to `docx_parser.py`.

### Scope

The `automation/cbm_import/parsers/` directory contains parsers for **all five interview phases**: `master_prd.py`, `domain_prd.py`, `entity_inventory.py`, `entity_prd.py`, `process_document.py`. The drift is system-wide, not Master-PRD-only.

The L2 PRD describes a JSON pipeline that does not exist in code. The code implements a parallel .docx pipeline that is not described in the L2 PRD. This is an entire subsystem built against an unwritten spec while the written spec sits unimplemented.

## What this session must accomplish

Work through these steps **one at a time**, confirming with Doug before moving to the next. Do not bundle.

### Step 1 — Verify Section 11 (Import Processor)

Read L2 PRD Section 11 in full from `crmbuilder-automation-l2-PRD.docx`. Confirm whether it specifies JSON parsing (expected, given Section 10.5), and quote the relevant passages. Report findings to Doug. Wait for approval.

### Step 2 — Confirm scope across all five phases

Inspect each prompt generator and each parser to confirm the drift pattern is identical across all phases, or document any phase that differs:
- `automation/core/` — look for `*_prompt.py` files for each phase, or confirm `master_prd_prompt.py` is the only one
- `automation/cbm_import/parsers/` — read each parser's top-of-file docstring and main entry point to confirm .docx input
- `automation/ui/importer/` — read `import_view.py` and the stage_*.py files to confirm what file type the UI expects

Report the phase-by-phase status table to Doug. Wait for approval.

### Step 3 — Check for prompt-optimized guides and templates

Verify whether `PRDs/process/interviews/prompt-optimized/` and `PRDs/process/interviews/prompt-templates/` exist in the crmbuilder repo. If they exist, list contents. If they do not, that is additional drift to record. Report to Doug. Wait for approval.

### Step 4 — Present correction options with tradeoffs

Lay out the strategic choice for Doug:

**Option 1 — Restore the L2 PRD design.** Implement the JSON envelope/payload pipeline per Section 10.5, build prompt-optimized guides and templates per 10.7/10.8, build the JSON Import Processor per Section 11, retire `automation/cbm_import/` and `automation/core/master_prd_prompt.py`. Aligned with original intent. Schema validation, deterministic parsing, clean revision/clarification flows per 10.6.

**Option 2 — Formalize the .docx pipeline.** Rewrite L2 PRD Sections 10.5–10.8 and Section 11 to describe the .docx interchange as the design, document parser-based extraction, accept fragility tradeoffs. Cheaper now. Loses schema validation. Section 10.6 revision/clarification model becomes much harder. Discards the explicit "JSON for parsing reliability" rationale.

**Hybrid options should be discouraged** unless Doug specifically requests one — they tend to inherit the worst of both.

Wait for Doug's strategic decision. Do not proceed to implementation prompts until he chooses.

### Step 5 — Author Claude Code prompt(s)

Once Doug picks a direction, draft `CLAUDE-CODE-PROMPT-*.md` file(s) in `PRDs/product/crmbuilder-automation-PRD/`. Use the multi-prompt series naming convention if more than one prompt is needed: `CLAUDE-CODE-PROMPT-import-drift-{letter}-{descriptor}.md`.

Reminder: Claude does not edit application source directly. All code changes go through Claude Code prompts that Doug runs himself. PRD documents and one-off diagnostic scripts are the only exceptions.

## Working style reminders

- One issue at a time. Wait for explicit approval before moving on.
- After each completed step, state the next required step and ask Doug to confirm.
- Use plain text discussion, never the ask_user_input widget.
- All "Last Updated" timestamps in any document produced this session use `MM-DD-YY HH:MM` format.
- Never mention specific product names (EspoCRM, WordPress, etc.) in L1 or L2 PRD content.
- Reference all repo files by full repo-relative path and name the repo when ambiguous.

## Context budget note

In the prior session, a `<total_tokens>N tokens left</total_tokens>` signal was visible to Claude and dropped from a starting value to 10K within roughly a dozen turns of light tool use (one repo clone, one CLAUDE.md read, one file grep, one PRD pandoc conversion, one PRD section view). Doug instructed Claude to ignore the signal and proceed, treating any cutoff as data about what the limit actually does. This session should do the same: ignore the token signal, work normally, and if the conversation is cut off mid-step, that itself is the answer to whether the limit is real and binding.

# SESSION-PROMPT — Document Production Process v2.0 — Continuation (Part 3)

**Goal:** Complete the v2.0 rewrite of `PRDs/process/CRM-Builder-Document-Production-Process.docx` and the companion `CLAUDE.md` update. Step 1 is already committed from an earlier session. Step 2 was attempted in a prior session but failed and was discarded without commit. This session restarts at Step 2 using a corrected strategy, then continues through Step 10.

## Predecessor prompts (read both, in order)

1. `PRDs/process/SESSION-PROMPT-doc-production-process-v2.0-continuation.md` — contains all locked design decisions **D1–D9**. These remain final. Do not reopen.
2. `PRDs/process/SESSION-PROMPT-doc-production-process-v2.0-continuation-part2.md` — contains the 10-step execution plan (Steps 2–10). Step plan is still valid; only the **execution strategy for Step 2 (and Step 3)** changes, per the lessons learned below.

## State as of this handoff

- **Committed on `main`:** v1.7 of the docx with the Step-1 insertion already applied (new "mission-anchored" paragraph in Section 1 Purpose, with forward reference to Rule 2.1). Verify by grepping `mission-anchored` in the unpacked `word/document.xml` — should return 1 hit.
- **Nothing else committed.** Header still reads v1.7 / Last Updated `04-04-26 21:30`.
- **No dirty working tree from the prior session.** The prior Step 2 attempt was never saved to disk in the repo — it lived only in `/home/claude/unpacked/` and was discarded.

## What went wrong in the prior Step 2 attempt (do not repeat)

The prior attempt used a chain of first-occurrence `str.replace()` calls to remap the 12-row phase table into the new 13-row layout. Because several new cell values contained substrings that were also the *search target* of a later replacement in the chain (e.g. replacing "Process Definition" → "Entity PRDs" created a new "Entity PRDs" string that interacted badly with later edits; swapping "1 per domain" and "Outside Claude" across multiple rows via first-occurrence replace scrambled which row got which value), rows 4–8 of the resulting table were corrupted. Specifically, the broken output had:

- Row 4 Name: "Domain Overview + Entity PRDs" (wrong — should be "Domain Overview + Process Definition")
- Row 4 Output: "Domain Overview + Entity PRDs (Word)" (wrong)
- Row 4 Conv: "1 per service process + 1 per service + 1 per entity" (wrong)
- Row 5 Name: "Process Definition" (wrong — should be "Entity PRDs")
- Row 6 Conv: "Outside Claude" (wrong — should be "1 per service process + 1 per service")
- Row 8 Conv: "1 per domain" (wrong — should be "Outside Claude")

Narrative text, rows 1–3, and rows 9–13 were all correct. The sub-domain paragraph's `Phases 3–6 independently` → `Phases 4 and 7 independently` edit also landed correctly.

## Corrected strategy for Step 2

**Do not chain-replace cell text.** Instead:

1. Locate the phase table in `word/document.xml` by finding the `<w:tbl>` that contains the header row with "Phase" / "Name" / "Output" / "Conversations".
2. Capture one data row `<w:tr>...</w:tr>` verbatim as a **template** — the simplest is row 1 (Phase `1`, Master PRD, ...) because its cells already contain plain text runs.
3. Delete all existing data rows (keep the header row).
4. Build a Python list of 13 new row specs as 4-tuples `(phase, name, output, conv)` matching the approved D1 table:
   - `(1, "Master PRD", "Master PRD (Word)", "1")`
   - `(2, "Domain Discovery", "Domain Discovery Report (Word)", "1")`
   - `(3, "Inventory Reconciliation", "Entity Inventory + Persona Inventory (Word); Master PRD domain list updated in place", "1")`
   - `(4, "Domain Overview + Process Definition", "Domain Overview + Process documents (Word)", "1 per domain + 1 per business process")`
   - `(5, "Entity PRDs", "Entity PRDs (Word)", "1 per entity")`
   - `(6, "Cross-Domain Service Definition", "Service process documents + Service PRDs (Word)", "1 per service process + 1 per service")`
   - `(7, "Domain Reconciliation", "Domain PRDs (Word)", "1 per domain")`
   - `(8, "Stakeholder Review", "Approved Domain PRDs", "Outside Claude")`
   - `(9, "YAML Generation", "YAML program files", "1 per domain")`
   - `(10, "CRM Selection", "CRM Evaluation Report (Word)", "1")`
   - `(11, "CRM Deployment", "Deployed CRM instance", "None — administrator-driven")`
   - `(12, "CRM Configuration", "Configured CRM instance", "Tool-driven")`
   - `(13, "Verification", "Verification Spec", "Tool-generated")`
5. For each spec, clone the template row, extract its four `<w:t ...>...</w:t>` elements in order (use regex with an index counter, not string replace), and rewrite each `<w:t>`'s content atomically. This avoids any cross-contamination because each cell is set by position, not by matching old text.
6. Concatenate the 13 generated rows and splice them into the table after the header row.
7. **Also update the narrative** — these two edits are safe as plain-substring replacements because the old and new strings are unique:
   - `twelve phases, executed in strict sequence` → `thirteen phases, executed in strict sequence`
   - The full old "Phase 2 is performed once..." paragraph → the full new "Phases 1, 2, and 3 are performed once..." paragraph (verbatim per Part 2 Step 2). The apostrophe in `service's` must be written as `&#x2019;s` (entity form, followed by literal `s`).
   - The sub-domain paragraph: `Phases 3\u20136 independently` (literal en-dash) → `Phases 4 and 7 independently`.
8. Pack with `pack.py --original <original.docx>`, verify pandoc dump of Section 2 matches the approved table exactly, then pause for Doug's review before Step 3.

## Apply the same "rebuild, don't chain-replace" discipline to Step 3

Step 3 (Phase Details rewrite) is larger and touches more cross-referenced content. For each subsection whose numbering or content changes, prefer **replacing the whole subsection** (heading paragraph + body paragraphs through the next Heading2) with freshly authored XML, rather than chaining small edits. Cross-reference updates to phase numbers within unchanged prose *can* be done as plain-substring replacements, but audit them carefully with the D8 grep sweep in Step 4.

## Working style

- Confirm CLAUDE.md to read at session start: **crmbuilder root**.
- One step at a time, pause for Doug's approval between steps.
- Design is locked (D1–D9). Do not reopen.
- Single commit at the end across the full v2.0 rewrite plus CLAUDE.md update, message: `Update Document Production Process to v2.0`.
- Show Doug the exact CLAUDE.md replacement text before applying (per D9).

## Out of scope (unchanged)

Client-facing kickoff script; interview guides, templates, Automation L2 PRD; CBM repo changes.

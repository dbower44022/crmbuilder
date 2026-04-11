# CLAUDE-CODE-PROMPT — L2 PRD v1.17 and User Guide Updates for Master PRD Kickoff Button

**Repo:** `crmbuilder`
**Scope:** Documentation only. No code changes. Updates two Word documents to reflect the shipped Master PRD kickoff button feature (CLAUDE-CODE-PROMPT-master-prd-kickoff-button.md, commit f606a5b).

## Context

A new button "Start Master PRD Interview" was added to the Clients tab detail pane in `automation/ui/clients_tab.py`. It generates a ready-to-paste prompt from `PRDs/process/interviews/interview-master-prd.md`, copies it to the clipboard, and (if `project_folder` is set) saves it to `{project_folder}/prompts/master-prd-prompt-{code}-{YYYYMMDD-HHMMSS}.md`. The handler calls into a new pure-logic module `automation/core/master_prd_prompt.py` with two functions: `build_master_prd_prompt()` and `save_master_prd_prompt()`. Tests live in `tests/ui/test_master_prd_prompt.py` (10 tests). 233 → 243 tests, ruff clean, zero deviations from spec.

This change is a **deliberate Phase-1-only shortcut** that pre-dates the full Workflow Engine (Section 9) and Prompt Generator (Section 10) surfaces. It must not be presented as a piece of those subsystems — it is a small, surgical addition that will eventually be subsumed when those sections are implemented end-to-end.

## Files to Modify

1. `PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`
2. `docs/CRM-Builder-User-Guide.docx`

## Working Method for Both Documents

Use the standard docx unpack/edit/repack workflow:

```bash
python /mnt/skills/public/docx/scripts/office/unpack.py <file.docx> <unpack_dir>
# edit word/document.xml via Python string replacement (NOT str_replace tool for large blocks)
python /mnt/skills/public/docx/scripts/office/pack.py <unpack_dir> <file.docx> --original
python /mnt/skills/public/docx/scripts/office/validate.py <file.docx>
```

Always pull latest before unpacking. Smart quotes in XML are stored as `&#x2019;` — use the XML entity form when string-matching. After repacking, verify content with `pandoc <file.docx> -t plain --wrap=none | grep -nE "<pattern>"`.

## L2 PRD Edits (crmbuilder-automation-l2-PRD.docx)

### Edit 1 — Version metadata

In the title-page metadata table at the top:
- Change `Version` value from `1.16` to `1.17`
- Change `Last Updated` value from `04-10-26 14:00` to today's date in `MM-DD-YY HH:MM` format using the actual current local time when you run this

### Edit 2 — Section 9 (Workflow Engine) cross-reference

Section 9 begins around line 843 in plain-text dump. Find subsection **9.1 Overview**. At the end of 9.1's body text (before 9.2 begins), append a new paragraph:

> **Phase 1 kickoff shortcut.** Until the Workflow Engine UI is implemented end-to-end, the Clients tab provides a Phase-1-only shortcut for generating the Master PRD interview prompt. See Section 14.11.4 and DEC-060. This shortcut will be removed when the full workflow surface in Sections 14.2–14.4 is operational.

### Edit 3 — Section 10 (Prompt Generator) cross-reference

Section 10 begins around line 1111. Find subsection **10.1 Overview**. At the end of 10.1's body text, append a new paragraph:

> **Phase 1 kickoff shortcut.** A small, hardcoded prompt-generation path exists on the Clients tab for the Master PRD interview only. It bypasses the full Prompt Generator described in this section and reads directly from `PRDs/process/interviews/interview-master-prd.md`. See Section 14.11.4 and DEC-060. It will be removed when the Prompt Generator is wired into the Session Orchestration view (Section 14.4).

### Edit 4 — Section 14.11.2 (Client Detail Pane) addition

Section 14.11.2 starts around line 2983. At the end of its existing body text, append a new paragraph:

> The detail pane also includes a **Start Master PRD Interview** action button beneath the reachability indicator. This button is the entry point to the Phase 1 kickoff shortcut described in Section 14.11.4.

### Edit 5 — New Section 14.11.4 — Master PRD Kickoff

Insert a new subsection **14.11.4 Master PRD Kickoff** after the existing 14.11.3 (Create Client Form). Use the same heading style as 14.11.1, 14.11.2, 14.11.3. Body content:

> The Clients tab provides a single-click mechanism for beginning Phase 1 of the document production process: the Master PRD interview. This is a deliberate, scoped shortcut that exists because the full Workflow Engine (Section 9) and Prompt Generator (Section 10) surfaces are not yet implemented. When those surfaces are complete, this shortcut will be removed and Phase 1 will be initiated through the Requirements tab like all other phases. See DEC-060.
>
> **Trigger.** A button labeled "Start Master PRD Interview" appears in the Client Detail Pane (Section 14.11.2), positioned beneath the reachability indicator. The button is always enabled per the Buttons-Never-Disabled pattern (Section 14.10.6); if no client is selected, the click handler displays an explanatory message and takes no further action.
>
> **Behavior.** When clicked with a client selected, the application:
>
> 1. Reads the Master PRD interview guide from `PRDs/process/interviews/interview-master-prd.md`. If the guide is missing, a warning dialog is shown and no further action is taken.
> 2. Assembles a prompt consisting of a header (client name, client code, current date, and document-standards instructions) followed by the full interview guide body, separated by a horizontal rule.
> 3. Copies the assembled prompt to the system clipboard.
> 4. If the client's project folder is set and exists, writes the prompt to `{project_folder}/prompts/master-prd-prompt-{code}-{YYYYMMDD-HHMMSS}.md`. If the project folder is unset or unreachable, this step is skipped and the user is informed that only the clipboard copy was made.
> 5. Displays a confirmation dialog showing the saved file path (when applicable) and instructing the user to paste the prompt into a new Claude.ai conversation.
>
> **Header content.** The generated prompt header includes the client name, the client code, a timestamp in `MM-DD-YY HH:MM` format, and an explicit instruction to the downstream Claude session to follow CRM Builder document standards (Arial, #1F3864 headings, two-column requirement tables, alternating row shading #F2F7FB, body 11pt, US Letter, 1" margins) and to avoid mentioning specific product names in the resulting Master PRD.
>
> **Implementation note.** Prompt assembly and file writing live in `automation/core/master_prd_prompt.py` as Qt-free pure-logic functions. The Clients tab click handler is a thin wrapper that handles clipboard interaction, error dialogs, and the confirmation message. This separation preserves the pure-logic / Qt boundary established in Section 14.1.

### Edit 6 — New DEC-060 in Section 15

Section 15 contains the decision log; the most recent decision is **DEC-059** at line 3389 (15.59 App launch restores last active tab and last selected client). Insert a new entry **15.60 Phase 1 Master PRD kickoff shortcut on Clients tab (DEC-060)** immediately after 15.59. Body:

> **Decision.** A single-purpose "Start Master PRD Interview" button is added to the Clients tab detail pane to provide an in-application mechanism for initiating Phase 1 of the document production process. The button generates a ready-to-paste prompt from the canonical Master PRD interview guide and copies it to the clipboard, optionally also writing it to the active client's project folder.
>
> **Rationale.** Without this shortcut, a newly created client has no in-application path forward — the requirements discovery process must be initiated entirely outside the tool. This breaks the conceptual flow of the Clients tab as the application's entry point (Section 14.11) and creates a discoverability gap for new users. The Workflow Engine (Section 9) and Prompt Generator (Section 10) will eventually provide a comprehensive phase-aware UI surface that handles all eleven phases uniformly, but those subsystems are not yet implemented. The shortcut closes the gap with minimal surface area: one button, one pure-logic module, one click handler, and zero new database state.
>
> **Scope boundaries.** The shortcut is intentionally narrow. It does not track whether the Master PRD has been generated, imported, or completed; it does not appear for any other phase; it does not interact with the WorkflowEngine, PromptGenerator, AISession, or any other Section 9–10 component; it does not modify the Client schema. It reads the interview guide from disk at click time, treating that file as the single source of truth for Master PRD interview content.
>
> **Sunset.** When the Requirements tab is wired to the Workflow Engine and Prompt Generator end-to-end, this button and the `automation/core/master_prd_prompt.py` module will be removed. Phase 1 will then be initiated through the same Session Orchestration interface (Section 14.4) as all other phases. The removal should be tracked as a follow-up task at that time.
>
> **Alternatives considered.** A new "Requirements" or "Workflow" tab dedicated to phase status was rejected as scope creep that would prejudge the eventual Workflow Engine UI design. A modal dialog launched from the Clients tab was rejected as heavier than warranted for what is fundamentally "give me the prompt text." A clipboard-only implementation (no file save) was rejected because saving to the project folder provides an audit trail alongside other client artifacts.

## User Guide Edits (CRM-Builder-User-Guide.docx)

The current section structure of the User Guide is unknown. Begin by unpacking the file and reading its existing structure (use `pandoc CRM-Builder-User-Guide.docx -t plain --wrap=none` to dump and inspect headings).

### Required additions

1. **Locate the section that describes the Clients tab** (likely something like "Managing Clients", "The Clients Tab", "Getting Started with a Client", or similar). If no such section exists, add a new top-level section titled **"Starting Requirements Discovery"** at the appropriate location — probably immediately after whatever section describes creating a new client.

2. **Add a new subsection** within (or as) that section, titled **"Starting the Master PRD Interview"** (or "Starting Requirements Discovery" if a parent section like that already exists — use judgment to avoid title duplication). The body should contain user-facing instructions, not implementation details. Suggested content:

> Once you have created a client in the Clients tab, you can begin the Master PRD interview — the first phase of the document production process — directly from the application.
>
> **Steps.**
>
> 1. In the Clients tab, select the client you want to begin work on. The client detail pane will appear on the right.
> 2. Scroll to the bottom of the detail pane and click **Start Master PRD Interview**.
> 3. The application will assemble a complete interview prompt and copy it to your clipboard. If your client has a project folder set, a copy of the prompt will also be saved to `{project_folder}/prompts/` with a timestamped filename.
> 4. A confirmation dialog will appear showing the saved file path (when applicable). Click OK to dismiss it.
> 5. Open a new conversation in Claude.ai and paste the prompt into the message box. Send the message to begin the interview.
> 6. Work through the interview with Claude. When the interview is complete, Claude will produce the Master PRD as a Word document.
> 7. Save the resulting Word document into your client's project folder for use in subsequent phases.
>
> **Notes.**
>
> - The button is always available when a client is selected. If you click it without a selection, the application will prompt you to select a client first.
> - The interview content comes from the canonical Master PRD interview guide bundled with the application, so all clients receive a consistent interview experience.
> - The header of the generated prompt includes the client's name, code, and the current date, plus instructions for the downstream Claude session to follow CRM Builder document standards and to avoid naming specific CRM products in the Master PRD.
> - This is currently the only phase that can be started directly from the Clients tab. Future versions of CRM Builder will provide a unified workflow surface for all phases.

3. **Apply CRM Builder document standards to any new content:** Arial font, body 11pt, headings styled to match existing User Guide headings (do not introduce new heading styles). If the User Guide does not already follow these standards, do not retroactively change existing content — apply standards only to the new content being added.

4. **Update the User Guide's "Last Updated" date** if such a field exists in the document's metadata or front matter, using `MM-DD-YY HH:MM` format with the actual current local time. If no such field exists, do not invent one.

## Acceptance Criteria

1. L2 PRD version field reads `1.17`. Last Updated field reads today's date in `MM-DD-YY HH:MM` format.
2. New paragraphs appear at the end of Sections 9.1 and 10.1 referencing 14.11.4 and DEC-060.
3. New paragraph appears at the end of Section 14.11.2 referencing the Start Master PRD Interview button and Section 14.11.4.
4. New Section 14.11.4 exists with the heading "Master PRD Kickoff" and the body content above.
5. New entry 15.60 (DEC-060) exists in the decision log with the title "Phase 1 Master PRD kickoff shortcut on Clients tab (DEC-060)" and the body content above.
6. L2 PRD repacks cleanly with `--original` flag and passes validation.
7. User Guide contains a new section or subsection describing the Start Master PRD Interview button with the user-facing instructions above.
8. User Guide repacks cleanly and passes validation.
9. Both files are committed to `main` with a clear message and pushed.
10. Verify final content with pandoc dump + grep for the new strings ("DEC-060", "14.11.4", "Start Master PRD Interview") in both files where applicable.

## Out of Scope

- Do not change any code.
- Do not change any other sections of the L2 PRD.
- Do not retroactively reformat the User Guide.
- Do not add a new ISS-019 — there are no open issues for this change.
- Do not modify CLAUDE.md (its drift from current architecture is a separate cleanup task).

## Reporting Back

When finished, report:
- L2 PRD version and Last Updated date written
- Confirmation that all six L2 PRD edits landed (grep verification output)
- The exact section/subsection title used in the User Guide and where it was inserted
- Commit hash and message

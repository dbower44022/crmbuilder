# Claude Code Prompt E: Terminology Sweeps (L2 PRD v1.16 Alignment)

**Last Updated:** 04-11-26 02:11
**Series:** Fifth and final prompt in the A–E series implementing L2 PRD v1.16 design items. Prompts A–D are already merged.

## Context

Earlier prompts in the A–E series updated the L2 PRD document and made the functional/structural code changes needed to align the implementation with v1.16. A handful of purely cosmetic terminology updates in the codebase were deliberately deferred to a single sweep so earlier prompts could stay focused. This prompt is that sweep.

**Scope is strictly cosmetic/string-level.** No functional changes, no schema changes, no behavioral changes to tests. The only test changes permitted are updates to assertions that compare against user-facing strings being renamed here.

## Repository

`dbower44022/crmbuilder`

## Reference Material

Before starting, read:

- `CLAUDE.md` at the repository root
- Section 14 of the L2 PRD (`PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`) for the current canonical terminology

## Task 1: Replace "administrator" → "implementor"

The L2 PRD v1.16 standardized on **implementor** as the user role term. The docx has already been updated; the codebase has not.

Replace `administrator` (and `Administrator`, `ADMINISTRATOR`, preserving case) with `implementor` (and `Implementor`, `IMPLEMENTOR`) in:

- UI strings (button labels, menu items, tooltips, status messages, dialog text, placeholder text)
- Docstrings
- Code comments
- Test assertions that compare against any of the above user-facing strings
- Log messages emitted to the user-facing output panel

**Do NOT change:**

- The L2 PRD docx (already done)
- Variable names, function names, class names, module names, or file names
- Database column names, schema field names, YAML keys
- Any reference to the EspoCRM built-in "administrator" role or the EspoCRM system administrator account — that is a product term, not our role term
- Any reference to `sudo`, OS-level administrator, SSH user, or DigitalOcean account administrator

When in doubt about whether a use is "our role term" vs. "the platform's term," leave it and flag it in the commit message.

## Task 2: Replace "Dashboard" → "Requirements Dashboard"

`CLAUDE-CODE-PROMPT-user-guide-alignment.md` began this rename but covered only the most obvious sites. Finish the sweep.

Scope:

- Sidebar labels, window titles, breadcrumb segments, navigation labels, tab headers, and any other user-facing string that names the specific view as `"Dashboard"` → `"Requirements Dashboard"`
- Docstring and comment references that describe the view as "the Dashboard" → "the Requirements Dashboard"
- Test assertions comparing against the user-facing label

**Do NOT change:**

- Variable names, class names, method names, or file names — e.g., `DashboardView`, `dashboard_panel.py`, `self.dashboard` all stay. The goal is to keep diffs small and avoid churn.
- Generic uses of the word "dashboard" that do not refer to this specific sidebar view (e.g., "Deployment Dashboard" is a different view and stays as-is)
- Any remaining docx content (L2 PRD already updated)

## Task 3: Replace "mode" → "tab" in User-Facing Strings

The v1.16 UI restructure replaced the old "mode" concept with tabs. Some user-facing strings still say "mode" where "tab" is now correct.

Scope:

- Replace `"Requirements mode"` → `"Requirements tab"`, `"Deployment mode"` → `"Deployment tab"`, and any analogous user-facing string
- Status bar messages, tooltips, error dialogs, and log messages that tell the user to "switch modes" → "switch tabs"
- Docstrings and comments that describe the UI structure using "mode" where "tab" is now accurate
- Test assertions against any of the above strings

**Do NOT change:**

- Variable/attribute names such as `current_mode`, `mode_changed`, enum names like `AppMode`, or any internal state-machine terminology. These may be renamed in a future prompt; they are out of scope here.
- Uses of "mode" that are not about the Requirements/Deployment UI split (e.g., "edit mode," "read-only mode," "debug mode," "dark mode")
- The word "mode" when it appears inside a larger fixed term that has its own meaning

## Task 4: Finish "Run Import" → "Import Results"

`CLAUDE-CODE-PROMPT-user-guide-alignment.md` began this rename. Verify it is complete and finish any stragglers.

Scope:

- Grep the codebase for any remaining occurrences of `"Run Import"` in UI strings, docstrings, comments, or test assertions under `automation/ui/`, `automation/core/`, `automation/workers/`, and `tests/`
- Replace with `"Import Results"` where user-facing
- If no occurrences remain, state that explicitly in the commit message

## Out of Scope

The following are explicitly **not** part of Prompt E and must not be touched:

- Any functional change to UI, workers, core logic, or schema
- Any variable, class, method, function, file, or module rename
- Any database column, enum value, YAML key, or API field rename
- Any test that exercises behavior rather than string content
- Any change to the L2 PRD docx (already updated in earlier prompts)
- Any change to generated documentation templates in `tools/docgen/`

## Methodology

1. Create a working branch off `main`.
2. Use `rg` (ripgrep) to inventory each term before making changes. Save the inventory counts in the commit message so the scope of the sweep is visible in history.
3. Work one task at a time. Commit Tasks 1–4 as separate commits with clear messages.
4. After each task, run:
   - `uv run ruff check automation/ tools/ tests/`
   - `uv run pytest tests/ -q`
   Both must pass with zero new failures. If a test fails because it asserts against an old string, update the assertion — that is in scope. If a test fails for any other reason, stop and report.
5. Do NOT update version numbers in any docx or markdown file — this is a code-only sweep.

## Acceptance Criteria

- `rg -i 'administrator'` under `automation/` and `tests/` returns only platform/OS/EspoCRM references (documented in the commit message)
- `rg '"Dashboard"' automation/ui/` returns zero results for user-facing labels of the Requirements view (only variable/class name usages remain, if any)
- `rg -i '"Requirements mode"|"Deployment mode"' automation/` returns zero results
- `rg '"Run Import"'` returns zero results
- `uv run ruff check` clean
- `uv run pytest tests/ -q` passes at the same count as `main` (no new failures, no skipped tests)
- No diff outside of strings, docstrings, comments, and affected test assertions

## Deliverable

A PR titled `Prompt E: terminology sweeps (admin→implementor, Dashboard→Requirements Dashboard, mode→tab)` with per-task commits and a summary in the PR description that lists, for each task, the pre-sweep and post-sweep occurrence counts.

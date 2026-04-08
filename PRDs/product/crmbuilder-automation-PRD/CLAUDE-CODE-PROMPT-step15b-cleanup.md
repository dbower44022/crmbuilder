# Claude Code Implementation Prompt — Step 15b Cleanup

## Context

Step 15b (workflow screens: Session Orchestration, Import Review, Impact Analysis Display) is complete and committed. During the review, two small gaps were identified that need cleanup before Step 15c begins:

1. **`automation/ui/work_item/tab_sessions.py:89` retains a "coming in Step 15b" placeholder toast.** The original Step 15b prompt did not include `tab_sessions.py` in its modification allowlist, so Claude Code correctly left it alone and accurately reported the gap. This cleanup prompt authorizes the change.

2. **`automation/data/master.db` is tracked in git and `.gitignore` does not exclude database files.** The file was committed by accident when Doug ran the application to verify Step 15a. It is a development artifact and should not be in version control.

Both items are small, scoped, and independent of each other. This is a cleanup prompt modeled on the ISS-010/ISS-011 fix prompt from Step 12.

Current state: 953 tests passing, L2 PRD at v1.12, ISS-014 documented.

## Repository Context

This work goes in the `dbower44022/crmbuilder` repository. Read `CLAUDE.md` at the repo root for general project conventions. You should also briefly re-read `automation/ui/work_item/header_actions.py` — specifically the `_do_generate_prompt` handler — because the fix to `tab_sessions.py` follows the same pattern.

## Issue 1: Replace `tab_sessions.py:89` placeholder toast

### The problem

`automation/ui/work_item/tab_sessions.py` renders a session card for each AISession row on a work item. For clarification sessions that have not yet generated a prompt (`session_type == "clarification"` AND `import_status == "pending"`), the card shows a "Generate Prompt" button. In Step 15a this button was wired to a placeholder toast:

```python
gen_btn.clicked.connect(
    lambda: show_toast(self, "Prompt generation coming in Step 15b")
)
```

Step 15b built the Session Orchestration view (`automation/ui/session/session_view.py`) and the navigation push pattern in `automation/ui/work_item/header_actions.py`, but the `tab_sessions.py` button was never updated because the file was not in Step 15b's modification allowlist.

### The fix

Replace the placeholder toast at line 89 with a real navigation push to the Session Orchestration view, scoped to the clarification session whose card the button belongs to.

**Read `automation/ui/work_item/header_actions.py`** first to see how the `_do_generate_prompt` handler pushes the Session Orchestration view onto the drill-down stack. Use the same pattern.

Key considerations:
- The Session Orchestration view needs to know the work item id and the session id (so pre_generation.py can load the clarification topic from the existing AISession row)
- The navigation push should emit a signal the parent view handles, or call directly into the parent's drill-down stack — match whatever pattern `header_actions.py` uses
- The clarification session does not need a new AISession row created — the existing pending row is what the administrator is generating a prompt for
- The button's lambda closure captures the session object (`session` variable from the surrounding loop); use that to pass the session id

If the Session Orchestration view's constructor does not currently accept an existing `ai_session_id` parameter for the clarification case, and the session is created fresh by PromptGenerator.generate() each call, check how `session_view.py` handles clarification sessions today. Either:
- It already handles the "existing pending clarification session" case (likely, since Section 14.4.1 explicitly covers it) — in which case just pass the session id through
- Or it doesn't, in which case the minimum change is to add the session id parameter

Document which path you take in your final report.

### What to update

- `automation/ui/work_item/tab_sessions.py` — replace the `show_toast` lambda with a proper navigation push
- Possibly `automation/ui/session/session_view.py` — only if needed to accept an existing session id for clarification
- Possibly the parent drill-down navigation signal — only if needed to route the new push

Do not modify any other Step 15b files. Do not refactor anything not directly related to this fix.

### Verify

After the fix:
- Clicking "Generate Prompt" on a pending clarification session card navigates to Session Orchestration
- The Session Orchestration view loads with the clarification topic pre-populated from the existing AISession
- The breadcrumb updates correctly
- No placeholder toast appears

Test the behavior end-to-end via the pure-logic test files if applicable (the navigation push can be tested without Qt).

## Issue 2: Untrack `automation/data/master.db` and update .gitignore

### The problem

`automation/data/master.db` is a SQLite file auto-created by `automation/ui/client_context.py` when the application first launches. It contains no source-controlled content — it's a runtime artifact — but it was committed to git by accident during Step 15a verification.

### The fix

Two parts, in order:

1. **Add to `.gitignore`:** Open `.gitignore` at the repo root. Add an entry for SQLite database files. The safest pattern is to exclude the entire `automation/data/` directory since it is specifically for runtime databases and should never contain source-controlled files:

```
# Runtime databases (master.db, client databases)
automation/data/
```

Place this under the existing "# Python artifacts" or "# Testing" section — pick whichever section groups best. If neither fits well, add a new section header.

2. **Untrack the file without deleting it from disk:** Run `git rm --cached automation/data/master.db`. This removes the file from git's index but leaves it on the filesystem, so the running application continues to work. If `automation/data/` contains only `master.db`, the empty directory will also effectively disappear from git.

### Verify

After the fix:
- `git ls-files automation/data/` returns nothing (no tracked files in that directory)
- `git status --ignored` shows `automation/data/master.db` as ignored
- The file still exists on disk at `automation/data/master.db`
- `.gitignore` contains the new entry

## Verification Before Doing Anything Else

Before applying either fix, run these commands and report the output verbatim:

```bash
# Confirm issue 1 exists
grep -n "coming in Step 15b" automation/ui/work_item/tab_sessions.py
```

Expected: one match at line 89 or nearby. If zero matches, the fix was already applied — stop and report.

```bash
# Confirm issue 2 exists
git ls-files automation/data/master.db
cat .gitignore | grep -i "automation/data\|\.db"
```

Expected: `git ls-files` outputs `automation/data/master.db` (meaning it is tracked), and the grep on `.gitignore` returns nothing (meaning there is no existing exclusion). If either is not the expected state, the fix was already applied — stop and report.

## What to Commit

Make **two separate commits** so each fix can be reviewed independently.

**Commit 1 — tab_sessions fix:**

```
Wire tab_sessions.py clarification Generate Prompt to Session Orchestration

Replaces the Step 15a placeholder toast with a real navigation push
to the Session Orchestration view, scoped to the existing pending
clarification AISession. Uses the same pattern as header_actions.py
_do_generate_prompt. The Section 14.4 flow is now complete for
clarification sessions initiated from the work item Sessions tab.
```

**Commit 2 — gitignore cleanup:**

```
Untrack automation/data/master.db and add to .gitignore

The master database is a runtime artifact created by the application
on first launch. It was committed by accident during Step 15a
verification. Adds automation/data/ to .gitignore and removes the
file from git tracking (file remains on disk).
```

## Verification After the Fixes

Run these and confirm each:

```bash
# All tests still pass
uv run pytest automation/tests/ -q
```

Expected: 953 tests pass, zero failures. The logic tests should not be affected by either fix. If any test fails, investigate before committing.

```bash
# Linter clean
uv run ruff check automation/
```

Expected: no errors.

```bash
# Issue 1 fix verified
grep -n "coming in Step 15b" automation/ui/work_item/tab_sessions.py
```

Expected: zero matches.

```bash
# Issue 2 fix verified
git ls-files automation/data/master.db
git status --ignored | grep master.db
cat .gitignore | grep "automation/data"
```

Expected: `git ls-files` returns nothing; `git status --ignored` shows master.db as ignored; `.gitignore` contains the new entry.

## Report

In your response, confirm:

- Verification step ran and reported the expected output
- Both fixes applied as described
- Test count before and after (should remain 953 unless your fix adds logic tests)
- Any deviations from the instructions and why
- Any ambiguities encountered

Do not push — leave that for Doug.

## Out of Scope

- Modifying any file other than `automation/ui/work_item/tab_sessions.py`, `.gitignore`, and possibly `automation/ui/session/session_view.py` (only if needed for the session id parameter)
- Refactoring Step 15a or 15b code beyond the minimal change required
- Fixing the ISS-013 revision reason cache issue (the unbounded growth noted in the Step 15b review). That will be resolved when the permanent schema fix for ISS-013 lands.
- Anything related to Step 15c (Document Generation, Data Browser, Existing Panel Integration)

## Reference

- `automation/ui/work_item/header_actions.py` — pattern to match for the navigation push
- `automation/ui/session/session_view.py` — the target view for the navigation push
- `automation/ui/work_item/tab_sessions.py` — the file being modified
- Step 15b prompt: `PRDs/product/crmbuilder-automation-PRD/CLAUDE-CODE-PROMPT-step15b-workflow-screens.md`
- L2 PRD Section 14.4 — Session Orchestration

# CLAUDE-CODE-PROMPT-v2-ui-v0.5-E-closeout

**Last Updated:** 05-16-26 21:00
**Series:** v2-ui-v0.5
**Slice:** E (5 of 5)
**Status:** Ready to execute (after slice D passes)
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.5.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.5-implementation-plan.md`
**Predecessor slice:** v2-ui-v0.5-D (switching mechanism, top-strip, picker, single-gesture creation+activation)

## Purpose

This is the final slice of CRMBuilder v2 UI v0.5. This prompt builds slice **E — Closeout**.

Slice E is the mechanical closeout for the v0.5 release. Four categories of work:

1. **Version bump.** `__version__` in `crmbuilder-v2/src/crmbuilder_v2/__init__.py` set to `"0.5.0"`.

2. **README release note.** New entry in `crmbuilder-v2/README.md` matching v0.4's format.

3. **End-to-end integration smoke.** `tests/crmbuilder_v2/integration/test_v0_5_end_to_end.py` exercising the full lifecycle: dogfood migration → CBM single-gesture creation → cross-engagement scope verification → switch-back-and-forth.

4. **Final regression pass.** `uv run pytest tests/crmbuilder_v2/ -v` green across the full suite.

After this slice, v0.5 is shippable. The status-entity update from "v0.4 complete" to "v0.5 complete" is operator-authored after slice E lands (through the desktop versioned-replace dialog, against the post-migration CRMBUILDER engagement). The v0.5 build's session records and decision records are authored at the v0.5-Conversation-2 closeout (the build-planning conversation that produced this prompt), not inside slice E.

## Project context

Slices A–D delivered the engagement-management functionality:

- Slice A: foundation infrastructure + dogfood migration.
- Slice B: engagement schema + access layer + REST API.
- Slice C: engagement management panel + CRUD dialogs + forbid-active-delete behavior.
- Slice D: top-strip + picker + 12-step activation worker + single-gesture creation+activation.

Slice E adds no new functionality. It packages the release: version, release note, integration smoke, regression pass.

## Pre-flight

1. Confirm working directory.
2. Confirm `git status` clean.
3. Confirm git identity.
4. Pull latest.
5. **Verify slice D is in place.** Top-strip renders. Picker opens with ordering as specified. Activation worker executes the 12-step sequence end-to-end. Single-gesture creation+activation flow works. Slice D tests pass.
6. Confirm API operational.
7. Confirm slice D's test suite passes.

## Reading order

1. `crmbuilder/CLAUDE.md` — v2 version-source convention.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.5.md` §6 (cross-cutting concerns), §7 (acceptance criteria, especially the E1–E8 closeout criteria).
3. `PRDs/product/crmbuilder-v2/ui-v0.5-implementation-plan.md` Step E.
4. `crmbuilder-v2/README.md` — current state. Identify the v0.4 release note section as the format template.
5. `crmbuilder-v2/src/crmbuilder_v2/__init__.py` — current `__version__` value (should be `"0.4.0"`).
6. v0.4's closeout slice prompts (`CLAUDE-CODE-PROMPT-v2-ui-v0.4-F-closeout.md`) for format precedent on the README entry shape.

## Step 1 — Version bump

Modify `crmbuilder-v2/src/crmbuilder_v2/__init__.py`:

```python
# before
__version__ = "0.4.0"

# after
__version__ = "0.5.0"
```

No other file carries the version per the CLAUDE.md v2 version-source convention. The About dialog reads via `importlib.metadata` with `__version__` as fallback.

## Step 2 — README release note

Add a v0.5 release-note entry to `crmbuilder-v2/README.md`. Insert above the v0.4 entry (most-recent-first ordering). Format matches v0.4's: one-paragraph summary plus a bullet list.

Template:

```markdown
### v0.5 — Engagement Management (05-DD-26)

CRMBuilder v2 v0.5 closes the engagement-routing gap. v0.4's methodology
tables and v2's governance tables both lived in a single SQLite file at
`crmbuilder-v2/data/v2.db`, which mixed the v2 build's own dogfood content
with whatever methodology pilot was using v2 as system of record. v0.5
operationalises DEC-039's "one v2 instance per engagement, separate
SQLite, separate API port" finding into a designed feature: a bootstrap
meta DB at `crmbuilder-v2/data/engagements.db` hosting an engagements
registry table; per-engagement DB files at
`crmbuilder-v2/data/engagements/{engagement_code}.db`; an
`ActiveEngagementContext` desktop singleton; a two-database API server;
a 12-step kill-and-relaunch activation sequence; and a one-shot dogfood
migration that rehouses the existing `v2.db` into
`crmbuilder-v2/data/engagements/CRMBUILDER.db` with backup-first
verify-row-counts delete-original discipline.

- **Engagement entity type.** Single new methodology entity (`engagement`)
  with ten fields (`engagement_identifier`, `engagement_code`,
  `engagement_name`, `engagement_purpose`, `engagement_status`,
  `engagement_last_opened_at`, `engagement_export_dir`, plus audit
  timestamps). Code regex `^[A-Z][A-Z0-9]{1,9}$` mirrors v1's
  `Client.code` constraint. Status lifecycle `active`/`paused`/`archived`
  with free transitions.
- **Multi-engagement routing infrastructure.** Meta DB with its own
  Alembic chain; per-engagement DBs with the existing v0.4 chain applied
  lazily at engagement-open; two-database API server (meta DB for
  `/engagements/*`, active engagement DB for everything else); cross-
  restart active-state persistence via
  `crmbuilder-v2/data/current_engagement.json`.
- **Dogfood migration.** One-shot explicit migration at first launch.
  Backup `v2.db` to `v2.db.pre-v0.5-backup`; create meta DB; insert
  `CRMBUILDER` engagement row; copy `v2.db` to
  `engagements/CRMBUILDER.db`; verify all row counts match; delete
  original. Three install scenarios handled (existing v2 install,
  fresh install, rerun after successful migration). Idempotent on rerun.
- **Engagements sidebar group and management panel.** New "Engagements"
  sidebar group above Governance with one entry. Management panel
  (master/detail) lists engagements with sortable columns (Identifier,
  Code, Name, Status, Last Opened); right-click context menu; standard
  CRUD dialogs.
- **Top-strip switching affordance.** Always-visible top-strip above
  sidebar entries shows the active engagement's name + code with a
  chevron-down caret. Clicking opens the picker dropdown.
- **Picker dropdown.** Live engagements ordered by last-opened descending;
  paused and archived sorted to bottom in muted color; active engagement
  marked with a check icon; footer "Manage engagements..." item opens
  the management panel.
- **Single-gesture engagement creation.** New Engagement dialog runs
  POST + DB file creation + activation in one user click. Three-label
  progress indicator. Graceful inline failure recovery for activation
  failures with "Try switching now" / "Stay in <previous>" affordances.
- **12-step activation sequence.** Reachability check, pre-flight
  Alembic, kill API, kill MCP, write `current_engagement.json`, update
  in-memory context, launch new API, launch new MCP, PATCH
  `engagement_last_opened_at` via new API (deferred from the original
  spec's step 7 to after the new API is up per the question-6 amendment), emit
  signal, UI restore.
- **Forbid active-engagement soft-delete.** Delete dialog refuses with
  inline redirect to switch first; edge-case wording for last-engagement
  install case.
- **User Process Guide v0.2 deferred to v0.6.** The current Engagement
  Playbook at `PRDs/process/v2-user-process-guide.md` v0.1 describes the
  data layer as a single `v2.db` file, which is outdated after v0.5
  ships. A v0.2 update folding in the multi-engagement routing model is
  scheduled for v0.6.

Cumulative tests: v0.5 adds approximately 165-225 tests covering the meta
DB connection isolation, two-database API routing, the dogfood
migration's three install scenarios and row-count verification, the
ActiveEngagementContext lifecycle, the engagement repository methods and
REST endpoints, the management panel and CRUD dialogs including the
forbid-active-delete edge cases, the top-strip and picker rendering, the
12-step activation worker's happy path and each step's failure modes,
and the single-gesture creation flow with its three failure modes. All
v0.4 tests continue to pass against the migrated CRMBUILDER engagement.
```

Replace `05-DD-26` with the actual closeout date.

## Step 3 — End-to-end integration smoke test

Create `tests/crmbuilder_v2/integration/test_v0_5_end_to_end.py`. The test is one long integration scenario covering the full v0.5 user journey:

```python
def test_v0_5_full_lifecycle(qtbot, tmp_path):
    """
    Scenario: starting from a v0.4-state v2.db, run the v0.5 migration,
    verify CRMBUILDER is active and operable, create a CBM engagement via
    the New Engagement dialog with single-gesture creation+activation,
    verify CBM is active and operable with empty sessions, create a
    session in CBM and verify it gets SES-001 (per-engagement scope
    confirmed), switch back to CRMBUILDER via the picker, verify CRMBUILDER's
    sessions still contain SES-027+ (the dogfood sessions), switch to CBM
    again, verify CBM has its session at SES-001.
    """

    # 1. Setup: copy a v0.4-state v2.db fixture to the test workspace
    # 2. Trigger dogfood migration via run_dogfood_migration()
    # 3. Assert: v2.db gone; .pre-v0.5-backup present; engagements.db
    #    present with CRMBUILDER row; engagements/CRMBUILDER.db present;
    #    db-export/ refreshed; current_engagement.json points at CRMBUILDER
    # 4. Spawn the desktop application (or simulate via the API endpoints
    #    and direct UI invocations, depending on the integration framework
    #    chosen by v0.4's test patterns)
    # 5. Open the New Engagement dialog; submit with CBM/Cleveland Business
    #    Mentoring/CBM Phase 1 pilot
    # 6. Wait for activation completion (poll the ActiveEngagementContext
    #    state, or the activation worker's completed signal)
    # 7. Assert: top-strip shows CBM; engagements/CBM.db exists;
    #    current_engagement.json points at CBM; sessions table in CBM.db
    #    is empty
    # 8. Create a session in CBM via the Sessions panel (or via direct API
    #    against the CBM engagement DB)
    # 9. Assert: session identifier is SES-001 (per-engagement scope)
    # 10. Open the picker; click CRMBUILDER
    # 11. Wait for activation completion
    # 12. Assert: top-strip shows CRMBUILDER; current_engagement.json
    #     points at CRMBUILDER; Sessions panel shows the dogfood content
    #     (SES-027+)
    # 13. Open the picker; click CBM
    # 14. Wait for activation completion
    # 15. Assert: top-strip shows CBM; Sessions panel shows just the one
    #     session at SES-001
    # 16. Cleanup: delete the CBM engagement and its DB file, restore
    #     v2.db from .pre-v0.5-backup if needed for subsequent test runs
    #     (or just delete the test workspace; the actual production data
    #     is untouched in tests because tmp_path is used)
```

Implementation guidance: the integration test should use a temp-directory workspace (`tmp_path` from pytest) to isolate from the real data. The dogfood migration's input `v2.db` is a fixture: `tests/crmbuilder_v2/integration/fixtures/v0_4_state_v2.db` — committed to the repo as a small SQLite file representing a minimal v0.4-state dogfood with a handful of sessions and decisions. The fixture is created during slice E by snapshotting Doug's actual `v2.db.pre-v0.5-backup` after the dogfood migration runs, then trimming to a small reproducible set if the size is unwieldy.

Subprocess management in the integration test: this is the trickiest piece. The activation worker spawns API and MCP subprocesses. The integration test either (a) runs against real subprocesses with a test-only API port to avoid colliding with the running development API, or (b) injects a mock subprocess manager that simulates the API/MCP lifecycle without actually spawning processes. Option (b) is faster and more reproducible; option (a) is closer to real behavior. Slice E chooses (b) — the mock subprocess manager is part of the existing v0.4 test framework if present, or a small new helper introduced here. The mock spawns a thread that responds to `/health` with 200 after a configurable delay and serves the meta DB and active engagement DB connections directly.

## Step 4 — Final regression pass and manual smoke

### 4.1 Final regression pass

Run the full test suite: `uv run pytest tests/crmbuilder_v2/ -v`. All tests must pass. Note the final test count; record in the commit message.

### 4.2 Manual integration smoke

Beyond the automated test, run the following on Doug's actual machine (against the real `engagements.db` and the real CRMBUILDER engagement created by slice A):

1. **Open the desktop app.** Confirm the title bar reads "CRMBuilder v2 0.5.0" (or however the v0.4-shipped title-bar version display formats it). Open the About dialog; confirm v0.5.0.
2. **Engagements sidebar group renders.** Confirm the group is visible with one entry "Engagements".
3. **Top-strip renders.** Confirm "CRMBuilder v2 (CRMBUILDER) ▾" is shown at the top of the sidebar.
4. **Picker opens.** Click top-strip. Picker shows CRMBUILDER with check icon. Footer "Manage engagements..." present.
5. **Engagement panel opens.** Click "Engagements" sidebar entry OR click "Manage engagements..." in the picker. Confirm the panel renders with CRMBUILDER row at the top (active marker on it).
6. **Edit CRMBUILDER works.** Right-click → Edit. Change purpose. Submit. Confirm panel and JSON snapshot refresh.
7. **Create CBM via single-gesture.** Right-click → New (or top-strip → picker → "Manage engagements..." → engagement panel → New). Submit: code CBM, name "Cleveland Business Mentoring", purpose "CBM Phase 1 pilot per the v0.5 dogfood discipline", export_dir blank. Confirm progress indicator advances through three phases; confirm activation completes; confirm top-strip now shows CBM.
8. **CBM is isolated.** Open Sessions panel — empty. Open Decisions panel — empty. Open Planning Items — empty. Domains, Entities, Processes, CRM Candidates — empty. Charter — empty. Status — empty.
9. **Create a session in CBM.** Use the existing v0.3-shipped New Session dialog. Submit a session. Confirm it gets SES-001.
10. **Switch to CRMBUILDER via picker.** Click top-strip; click CRMBUILDER. Activation overlay shows; completes. Top-strip shows CRMBUILDER. Sessions panel shows SES-027+ (the dogfood content). Decisions panel shows DEC-086+ (the dogfood decisions plus the seven v0.5 decisions if they have been applied by the closeout pass).
11. **Switch to CBM again.** Confirm Sessions panel shows just SES-001.
12. **Forbid-active-delete with slice D wiring.** Right-click CBM → Delete (CBM is active). Confirm forbid-active message with "Switch engagement" button. Click — picker opens. Click CRMBUILDER. Activation completes. Right-click CBM (now inactive) → Delete; standard confirmation flow; soft-delete CBM. Confirm CBM disappears from picker.
13. **Restore CBM.** In the engagement panel with "Show soft-deleted" checked, right-click CBM → Restore. Confirm CBM reappears in the picker.
14. **Cross-restart persistence.** Switch to CBM. Close the desktop. Reopen. CBM is restored as active.

If any step fails, stop and report. The release is not shippable until all 14 manual smoke steps pass.

## Acceptance verification

Per PRD §7 closeout criteria E1–E8:

- E1. `__version__` is `"0.5.0"`; About dialog shows v0.5.0. ✓ from Step 1 + Step 4.2 step 1.
- E2. README has v0.5 release-note entry. ✓ from Step 2.
- E3. Full test suite green. ✓ from Step 4.1.
- E4. Engagements sidebar group renders with top-strip and picker. ✓ from Step 4.2 steps 2-5.
- E5. 12-step activation completes with q6 amendment. ✓ from Step 4.2 steps 7, 10, 11.
- E6. Dogfood migration completed cleanly on Doug's machine. ✓ from slice A acceptance verification (verified previously).
- E7. CBM engagement created via single-gesture; SES-001 in CBM starts fresh. ✓ from Step 4.2 steps 7-9.
- E8. Cumulative roll-up — all 13 architecture-level + 12 entity-level criteria pass in the running application. ✓ from Step 4.1's full regression pass plus Step 4.2's manual smoke covering the user-visible criteria.

## Commit

```bash
git add crmbuilder-v2/src/crmbuilder_v2/__init__.py \
        crmbuilder-v2/README.md \
        tests/crmbuilder_v2/integration/test_v0_5_end_to_end.py \
        tests/crmbuilder_v2/integration/fixtures/v0_4_state_v2.db
git commit -m "v2: v0.5 slice E — closeout (version 0.5.0, README release note, end-to-end integration smoke, full regression pass green)"
```

Doug pushes. Do NOT push.

## After commit

The release is shippable. Operator follow-up (not part of slice E):

1. **Status update.** Open the desktop UI; navigate to Status (now in the CRMBUILDER engagement); use the versioned-replace dialog to update phase from "v0.4 complete" to "v0.5 complete". Increment the version label appropriately.
2. **v0.5 build closeout records.** Author the session record for the v0.5-Conversation-2 build-planning conversation (the one that produced this slice E prompt) AND the seven DEC records (DEC-098 through DEC-104 per PRD §13's settled numbering). These are written via the close-out payload + apply prompt produced at the Conversation 2 closeout, NOT inside slice E.
3. **Optional cleanup.** After verifying v0.5 works for a reasonable period (a few days of normal use), Doug can delete `crmbuilder-v2/data/v2.db.pre-v0.5-backup` to reclaim disk space. The backup is preserved by the migration; deletion is operator-driven.

## What NOT to do

- Do NOT author any session, decision, planning_item, or reference records inside slice E. Those land via the Conversation 2 closeout payload + apply prompt.
- Do NOT modify the User Process Guide at `PRDs/process/v2-user-process-guide.md`. The v0.2 update is deferred to v0.6 per PRD §2 Out of Scope. Slice E's README mentions the deferral but does NOT rewrite the guide.
- Do NOT touch `__version__` to a value other than `"0.5.0"` (e.g., `"0.5.0-rc1"`, `"0.5"`, etc.).
- Do NOT modify any slice A–D deliverable. Slice E is strictly closeout; functional changes belong in earlier slices.
- Do NOT update the status entity inside Claude Code. Status updates are operator-authored through the desktop UI per the v0.3-shipped versioned-replace pattern.
- Do NOT remove `v2.db.pre-v0.5-backup` from `.gitignore` or attempt to clean it up. Operator-driven cleanup.

---

*End of prompt.*

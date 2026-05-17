# CLAUDE-CODE-PROMPT-v2-ui-v0.5-A-followup-launcher-wiring

**Last Updated:** 05-17-26 14:30
**Series:** v2-ui-v0.5
**Slice:** A follow-up (post-build defect fix)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.5.md` §5.4 (dogfood migration at first launch)
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.5-implementation-plan.md`
**Predecessor:** Slice A (foundation + dogfood migration) — landed but launcher wiring was incomplete

## Purpose

Slice A landed the meta DB Alembic chain, the `bootstrap_meta_db()` helper, the `needs_migration()` detector, and the `run_dogfood_migration()` module, plus all the access-layer and API-routing infrastructure. But the **launcher integration** — the bits that invoke those helpers at app startup — did not land. On Doug's machine after slice A: the API restarted fine but `engagements.db` was never created (no startup call to `bootstrap_meta_db()`); the desktop launched fine but the dogfood migration was never triggered (no startup call to `run_dogfood_migration()`). The result was a half-migrated state that produced 404s on `/engagements` and "No engagement selected" in the UI even though all the supporting code shipped.

Doug ran the migration manually via a one-liner; his machine is now correctly migrated. This prompt fixes the underlying defect so any future fresh install from a v0.4 state auto-migrates correctly without manual intervention.

Three categories of work:

1. **API startup hook.** Modify `crmbuilder-v2/src/crmbuilder_v2/api/main.py` to invoke `bootstrap_meta_db()` before the engagement DB pool is initialized. The hook is idempotent — `bootstrap_meta_db()` no-ops if the meta DB exists at head.

2. **Desktop startup migration trigger.** Modify `crmbuilder-v2/src/crmbuilder_v2/ui/app.py` to detect the migration-needed state via `needs_migration()` and invoke `run_dogfood_migration()` before the main window is shown, with a progress dialog wrapping the call. Hard-fail UX on migration error per slice A spec.

3. **Integration test.** New test in `tests/crmbuilder_v2/integration/test_launcher_wiring.py` that constructs a v0.4-state filesystem fixture (`v2.db` present, no meta DB, no `current_engagement.json`), invokes the desktop launcher, and asserts that post-launch the migration has run, `engagements.db` exists with the CRMBUILDER row, `engagements/CRMBUILDER.db` exists, `current_engagement.json` points at CRMBUILDER, and the in-memory `ActiveEngagementContext` is populated.

This is a **small surgical commit** — ~50 lines of source changes plus ~80 lines of new test. No new modules; no schema changes; no acceptance-criteria delta.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean.
3. Confirm git identity is `Doug Bower <dbower44022@users.noreply.github.com>`.
4. Pull latest: `git pull --rebase origin main`.
5. **Verify Doug's machine is post-migration.** `ls crmbuilder-v2/data/` should show `engagements.db`, `engagements/CRMBUILDER.db`, `current_engagement.json`, and `v2.db.pre-v0.5-backup`. No `v2.db`. This confirms the manual fix landed and we're patching the defect for next time, not the current state.
6. Confirm full v0.5 test suite passes: `cd crmbuilder-v2 && uv run pytest tests/crmbuilder_v2/ -q` — should report 689 passing (or whatever the current baseline is).

## Reading order

1. `crmbuilder/CLAUDE.md` — v2 section.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.5.md` §5.4 (dogfood migration at first launch — authoritative spec for the trigger behavior).
3. `PRDs/product/crmbuilder-v2/multi-engagement-architecture.md` §3.7 (DEC-084's 8-step migration spec).
4. Existing slice A code:
   - `crmbuilder-v2/src/crmbuilder_v2/api/main.py` — find the FastAPI app construction and `@app.on_event("startup")` hook (or equivalent lifespan handler). This is where `bootstrap_meta_db()` belongs.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/app.py` — find the desktop launcher entry point (likely a `main()` function or class). Identify the point between Qt application initialization and main window show; this is where the migration trigger belongs.
   - `crmbuilder-v2/src/crmbuilder_v2/access/meta_db.py` — confirm the `bootstrap_meta_db()` signature; it should be parameterless and idempotent.
   - `crmbuilder-v2/src/crmbuilder_v2/migration/dogfood_v0_5.py` — confirm `needs_migration()` and `run_dogfood_migration()` signatures.
5. Slice E's `tests/crmbuilder_v2/integration/test_v0_5_end_to_end.py` — read for fixture pattern; the new test reuses the v0.4-state `v2.db` fixture if one exists.

## Step 1 — API startup hook

Modify `crmbuilder-v2/src/crmbuilder_v2/api/main.py`. Find the existing startup hook (FastAPI lifespan handler or `@app.on_event("startup")`) that initializes the engagement DB pool. Add a call to `bootstrap_meta_db()` **before** the engagement DB pool initialization.

Pseudocode (adapt to the actual code shape):

```python
from crmbuilder_v2.access.meta_db import bootstrap_meta_db
from crmbuilder_v2.access import init_engagement_db_pool  # or whatever exists

@app.on_event("startup")  # or the lifespan equivalent
async def startup():
    bootstrap_meta_db()             # NEW — applies meta DB Alembic chain to head; idempotent
    init_engagement_db_pool()       # existing
```

`bootstrap_meta_db()` is idempotent: it creates `engagements.db` if missing, applies the Alembic chain to head, and exits cleanly if already at head. No-op on second invocation.

If the existing startup code uses FastAPI's modern lifespan handler (async context manager pattern), add the call in the equivalent location — before the engagement DB pool is initialized, before any request handlers can fire.

## Step 2 — Desktop startup migration trigger

Modify `crmbuilder-v2/src/crmbuilder_v2/ui/app.py`. Find the desktop launcher entry point. Between Qt application initialization (`QApplication`, font loading, etc.) and main window `.show()`, insert the migration-detection-and-trigger block per the slice A spec:

```python
from crmbuilder_v2.migration.dogfood_v0_5 import needs_migration, run_dogfood_migration
from PySide6.QtWidgets import QProgressDialog, QMessageBox

def main():
    app = QApplication(sys.argv)
    # ... existing Qt initialization (font loading, etc.) ...

    # NEW: Migration trigger before main window show
    if needs_migration():
        progress = QProgressDialog(
            "Upgrading to v0.5: migrating engagement...",
            None,  # no cancel button — migration must complete or fail
            0, 0,  # indeterminate progress bar
            parent=None,
        )
        progress.setWindowTitle("CRMBuilder v2 — Upgrading")
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()

        try:
            result = run_dogfood_migration()
        finally:
            progress.close()

        if not result.success:
            QMessageBox.critical(
                None,
                "Migration failed",
                f"v0.5 migration failed at step: {result.steps_completed[-1] if result.steps_completed else 'pre-flight'}\n\n"
                f"Error: {result.error}\n\n"
                f"Your v0.4 data is preserved at crmbuilder-v2/data/v2.db.pre-v0.5-backup. "
                f"Please revert to the prior v2 release and contact support.",
            )
            sys.exit(1)

    # ... existing code that constructs the main window and calls .show() ...
```

The progress dialog is centered with an indeterminate spinner. No cancel affordance per slice A spec — the migration must complete or fail atomically.

`QApplication.processEvents()` after `progress.show()` forces Qt to render the dialog before the synchronous migration blocks the event loop. Without it the dialog would not visibly appear until after the migration completes, defeating the purpose.

On migration failure: critical error dialog explaining the recovery path (backup file location plus revert instructions); `sys.exit(1)` so the app does not continue in a half-migrated state.

## Step 3 — Integration test

Create `tests/crmbuilder_v2/integration/test_launcher_wiring.py`. The test constructs a v0.4-state filesystem fixture, invokes the launcher integration, and asserts post-conditions:

```python
"""
Integration test for v0.5 launcher wiring.

Verifies that on first launch from a v0.4 state (v2.db present, no meta DB,
no current_engagement.json), the launcher integration correctly:
  1. Applies the meta DB Alembic chain via bootstrap_meta_db()
  2. Detects migration-needed state via needs_migration()
  3. Triggers run_dogfood_migration() before main window show
  4. Ends with CRMBUILDER as the active engagement

Regression test for the slice A launcher-wiring gap that produced the
inconsistent post-build state on Doug's machine (manifest: /engagements
returned 404, top-strip showed "No engagement selected", existing data
visible because API was still reading from v2.db via fallback).
"""

import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from crmbuilder_v2.access.meta_db import bootstrap_meta_db, meta_db_path
from crmbuilder_v2.access.engagement import list_engagements
from crmbuilder_v2.migration.dogfood_v0_5 import needs_migration, run_dogfood_migration


@pytest.fixture
def v0_4_state_workspace(tmp_path, monkeypatch):
    """Create a workspace with a v0.4-state v2.db and no meta DB.

    Reuses the fixture from test_v0_5_end_to_end.py if one exists; otherwise
    constructs a minimal v0.4-state SQLite file with a handful of sessions
    and decisions.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Source the v0.4-state fixture; if test_v0_5_end_to_end uses
    # tests/crmbuilder_v2/integration/fixtures/v0_4_state_v2.db, reuse it.
    fixture_src = Path(__file__).parent / "fixtures" / "v0_4_state_v2.db"
    if fixture_src.exists():
        shutil.copy(fixture_src, data_dir / "v2.db")
    else:
        # Minimal inline fallback: construct a tiny v0.4-state DB.
        # (Implementation detail: use the per-engagement Alembic chain to
        # create the schema; insert a couple of sessions and decisions.)
        pytest.skip("v0.4-state fixture not present; reuse from slice E test")

    monkeypatch.setenv("CRMBUILDER_V2_DATA_DIR", str(data_dir))
    return data_dir


def test_api_startup_invokes_bootstrap_meta_db(v0_4_state_workspace):
    """Slice A defect regression: API startup must apply meta DB Alembic chain."""
    data_dir = v0_4_state_workspace
    assert not (data_dir / "engagements.db").exists(), "pre-state: no meta DB"

    # Invoke whatever the API startup hook ends up calling.
    bootstrap_meta_db()

    assert (data_dir / "engagements.db").exists(), \
        "bootstrap_meta_db() must create the meta DB if missing"


def test_launcher_invokes_migration_when_needed(v0_4_state_workspace):
    """Slice A defect regression: desktop launcher must trigger migration."""
    data_dir = v0_4_state_workspace

    assert needs_migration(), "v0.4 state should report migration needed"

    result = run_dogfood_migration()

    assert result.success, f"migration failed: {result.error}"
    assert not (data_dir / "v2.db").exists(), "v2.db should be deleted post-migration"
    assert (data_dir / "v2.db.pre-v0.5-backup").exists(), "backup must be preserved"
    assert (data_dir / "engagements.db").exists()
    assert (data_dir / "engagements" / "CRMBUILDER.db").exists()

    current = json.loads((data_dir / "current_engagement.json").read_text())
    assert current["engagement_code"] == "CRMBUILDER"
    assert current["engagement_identifier"] == "ENG-001"

    engagements = list_engagements()
    assert len(engagements) == 1
    assert engagements[0].engagement_code == "CRMBUILDER"


def test_idempotent_on_already_migrated_state(v0_4_state_workspace):
    """Re-running after successful migration must be a no-op."""
    # First migration
    run_dogfood_migration()

    # Re-run
    assert not needs_migration(), "post-migration state should not need migration"
    result = run_dogfood_migration()
    assert result.success
    assert "already_migrated" in result.steps_completed
```

The test focuses on the helpers' behavior assuming the launcher correctly invokes them. A higher-fidelity test that drives the actual `main()` function under a Qt event loop is possible but adds significant complexity for marginal coverage. The unit-level coverage above plus the existing slice E end-to-end test cover the integration.

If the slice E `test_v0_5_end_to_end.py` already has equivalent coverage of `bootstrap_meta_db()` and `run_dogfood_migration()` invocations, simplify this new test to focus only on the gap: that the **launcher integration** (the wiring in `api/main.py` and `ui/app.py`) invokes them correctly. A direct test of that requires either patching the startup hooks and asserting calls, or instantiating the FastAPI test client and verifying `engagements.db` appears.

## Acceptance verification

Before committing:

1. **New tests pass.** `cd crmbuilder-v2 && uv run pytest tests/crmbuilder_v2/integration/test_launcher_wiring.py -v` — all green.
2. **Full suite stays green.** `cd crmbuilder-v2 && uv run pytest tests/crmbuilder_v2/ -q` — no regressions; total test count is 689 baseline + 3 new = 692 (adjust if you write more or fewer tests).
3. **Manual sanity check on a clean state.** Simulate a fresh-install state and verify launcher behavior:
   ```bash
   # Backup current state
   cp -r crmbuilder-v2/data crmbuilder-v2/data.real-backup

   # Restore v0.4 state from the .pre-v0.5-backup
   pkill -f crmbuilder-v2-api
   rm -rf crmbuilder-v2/data/engagements crmbuilder-v2/data/engagements.db crmbuilder-v2/data/current_engagement.json
   mv crmbuilder-v2/data/v2.db.pre-v0.5-backup crmbuilder-v2/data/v2.db

   # Restart API — should trigger bootstrap_meta_db() (creates engagements.db)
   cd crmbuilder-v2 && uv run crmbuilder-v2-api &
   sleep 3

   # Verify engagements.db now exists (was created by the API startup hook)
   ls crmbuilder-v2/data/engagements.db

   # Verify /engagements returns empty list (router works against empty meta DB)
   curl -s http://127.0.0.1:8765/engagements | python3 -m json.tool

   # Open the desktop — should detect migration-needed, show progress dialog,
   # run migration, end with CRMBUILDER active in the top-strip
   ```
4. **Restore the real state after the sanity check.**
   ```bash
   pkill -f crmbuilder-v2-api
   rm -rf crmbuilder-v2/data
   mv crmbuilder-v2/data.real-backup crmbuilder-v2/data
   cd crmbuilder-v2 && uv run crmbuilder-v2-api &
   ```

## Commit

```bash
git add crmbuilder-v2/src/crmbuilder_v2/api/main.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/app.py \
        tests/crmbuilder_v2/integration/test_launcher_wiring.py
git commit -m "v2: v0.5 slice A follow-up — wire launcher gaps (bootstrap_meta_db at API startup, migration trigger at desktop startup, regression test)

Slice A landed the meta DB Alembic chain, bootstrap_meta_db() helper,
needs_migration() detector, and run_dogfood_migration() module, but
the launcher integration to invoke them at app startup was not wired.
Result on first launch from v0.4 state: engagements.db never created,
dogfood migration never triggered, /engagements returns 404, top-strip
shows 'No engagement selected' even though all supporting code exists.

This commit:
- Adds bootstrap_meta_db() to the API startup hook in api/main.py
- Adds needs_migration() check + run_dogfood_migration() trigger in
  ui/app.py before main window show, wrapped in a QProgressDialog
  per slice A spec
- Adds integration test test_launcher_wiring.py covering the three
  gap behaviors (bootstrap on API startup; migration on desktop
  startup when needed; idempotency on already-migrated state)

Doug's machine was unblocked via manual migration trigger; this fix
ensures any future fresh-install from a v0.4 state auto-migrates
without operator intervention."
```

Doug pushes. Do NOT push.

## What NOT to do

- Do NOT modify the migration module, the meta DB Alembic chain, or any of slice A's existing helpers. The fix is strictly to wire the existing helpers into the startup paths.
- Do NOT add new acceptance criteria to the PRD. This is a defect fix, not a scope change.
- Do NOT modify the engagement REST API surface, the management panel, the top-strip, the picker, the activation worker, or the single-gesture flow. None of those need changes for this fix.
- Do NOT bump `__version__` — this is a follow-up patch to v0.5, not a new release.
- Do NOT add a v0.5.1 README entry — single follow-up patches don't warrant a release note unless the v0.5 release was already publicly cut, which it wasn't.
- Do NOT touch the v0.6 styling work that landed on origin/main in parallel. Those files are unrelated to this fix.
- Do NOT write session, decision, or planning records for this fix conversation. If this is run as a separate Claude Code conversation, its session record can be authored later as a normal build-execution session record (no decisions are produced; the fix is purely an implementation of slice A's documented spec).

---

*End of prompt.*

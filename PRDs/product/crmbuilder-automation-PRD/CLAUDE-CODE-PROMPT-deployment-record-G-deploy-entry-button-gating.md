# Claude Code Prompt — Deployment Record Series, Prompt G

**Series:** deployment-record (productize the Deployment Record artifact)
**Prompt ID:** G
**Descriptor:** deploy-entry-button-gating
**Filename:** `CLAUDE-CODE-PROMPT-deployment-record-G-deploy-entry-button-gating.md`
**Repository:** `crmbuilder`
**Depends on:** Prompts A, B, C, E, F merged (this prompt closes a gap left by F's execution)
**Related document:** `PRDs/product/crmbuilder-automation-PRD/cbm-test-instance-backfill-procedure.md` — the procedure that requires this fix to be reachable
**Last Updated:** 05-02-26 15:50
**Version:** 1.0

---

## Status

A small, narrow follow-up to Prompt F. F's specification stated that the "Generate Deployment Record" button (and Upgrade and Recovery & Reset) should be visible whenever the instance is self-hosted, regardless of whether `InstanceDeployConfig` exists yet — because the handlers now open the backfill dialog when config is missing. F's execution session correctly updated `_on_regenerate_record` to follow the backfill pattern, but the visibility gating in `refresh()` still hides the Generate Deployment Record button when no config exists, and the underlying `_instance_is_self_hosted()` helper returns `False` whenever there is neither a successful `DeploymentRun` nor an `InstanceDeployConfig` row — even for instances that *are* self-hosted but have no prior history (the exact case Prompt F was designed for).

Net effect on the live CBM Test instance: all three of Upgrade, Recovery & Reset, and Generate Deployment Record are hidden, so the user cannot trigger the backfill dialog through any path. The procedure document produced by Prompt F is therefore unrunnable as written. This prompt closes that gap.

After Prompt G: clicking on a self-hosted instance with no prior run / config history exposes all three action buttons. Clicking any of them opens the backfill dialog (existing behavior in `_on_upgrade`, `_on_recovery`, and `_on_regenerate_record` — already in place from F). This restores the path the procedure document describes.

---

## What this prompt accomplishes

1. **Fix `_instance_is_self_hosted()` in `automation/ui/deployment/deploy_entry.py`** to return `True` when there is no positive evidence the instance is cloud-hosted or bring-your-own. Specifically: keep the existing two queries that check `DeploymentRun.scenario` and `InstanceDeployConfig.scenario`, but change the return logic so that an absence of evidence defaults to `True` (self-hosted) rather than `False`. Only return `False` when there is positive evidence of a non-self-hosted scenario.

2. **Fix the visibility gating in `refresh()`** by removing the `_instance_has_deploy_config()` term from the Generate Deployment Record button's visibility check. The line currently reads:

   ```python
   has_config = is_sh and self._instance_has_deploy_config()
   self._regenerate_record_btn.setVisible(has_config)
   ```

   It should read:

   ```python
   self._regenerate_record_btn.setVisible(is_sh)
   ```

   The local variable `has_config` is no longer needed and its single use site goes away with this change. This matches the `setVisible(is_sh)` pattern already used for `_upgrade_btn` and `_recovery_btn` two lines above.

3. **Remove the now-unused `_instance_has_deploy_config()` helper method.** With the change in (2), the method has no remaining call sites in `deploy_entry.py`. Verify with a grep before deletion that nothing else in the codebase uses it.

4. **Update or extend tests** in `tests/test_deploy_entry.py` (or wherever the existing tests for `DeployEntry` live):
   - Add a test verifying that `_instance_is_self_hosted()` returns `True` when no `DeploymentRun` and no `InstanceDeployConfig` row exists for the instance (the CBM-Test-style case).
   - Add a test verifying that `_instance_is_self_hosted()` returns `False` when a `DeploymentRun` with `scenario='cloud_hosted'` exists (positive evidence of non-self-hosted).
   - Add a test verifying that the `_regenerate_record_btn` is visible after `refresh()` when the instance is self-hosted but has no `InstanceDeployConfig` row (the case Prompt F was designed for).
   - Existing tests added by F (`test_on_regenerate_record_opens_backfill_when_config_missing`, `test_on_regenerate_record_skips_when_user_cancels_backfill`) continue to pass without modification.

---

## What this prompt does NOT do

- **No changes to the handlers.** `_on_upgrade`, `_on_recovery`, and `_on_regenerate_record` are unchanged. They already handle the missing-config case via the backfill dialog (F's work).
- **No changes to `ConnectionConfigDialog`.** The backfill dialog itself is unchanged.
- **No changes to `regenerate_record_dialog.py` or `regenerate_record_worker.py`.** Prompt C's work is unchanged.
- **No schema changes.** No migration. No new tables or columns.
- **No changes to the wizard.** Prompt B's work is unchanged.
- **No changes to the procedure document** (`cbm-test-instance-backfill-procedure.md`). The procedure was written for the post-fix behavior; after this prompt lands, the procedure becomes runnable.
- **No changes to the JS generator in the CBM repo.** Out of scope.

---

## Constraints and conventions

- **Surgical scope.** Three small edits in one file (`deploy_entry.py`) plus tests. Total Python changes are well under 50 lines.
- **Match the existing style of `_instance_is_self_hosted()`.** The method already has try/except handling and reads cleanly; preserve that style.
- **The default-to-True logic must be conservative.** Only return `True` when (a) positive evidence of self-hosted, OR (b) absence of evidence. Return `False` only with positive evidence of cloud-hosted / bring-your-own. Do not, for example, return `True` when the SQL query raises an exception — preserve the existing `except Exception: return False` for the genuine error case.
- **Updated tests use the existing test scaffolding.** Use the same fixtures, the same patching patterns, and the same assertion style as the existing `test_on_regenerate_record_*` tests in `tests/test_deploy_entry.py`.
- **Python 3.11+, type hints, docstrings, pytest.** Same conventions as the rest of the codebase.

---

## Detailed implementation

### 1. Updated `_instance_is_self_hosted()`

Current implementation (lines 207–232 in `deploy_entry.py`, approximately):

```python
def _instance_is_self_hosted(self) -> bool:
    """Return True iff the active instance is self-hosted.

    Checks DeploymentRun rows first (the wizard's scenario record);
    falls back to InstanceDeployConfig if no DeploymentRun exists.
    Returns False when no instance is active.
    """
    if self._conn is None or self._instance is None:
        return False
    try:
        row = self._conn.execute(
            "SELECT scenario FROM DeploymentRun "
            "WHERE instance_id = ? AND outcome = 'success' "
            "ORDER BY completed_at DESC LIMIT 1",
            (self._instance.id,),
        ).fetchone()
        if row:
            return row[0] == "self_hosted"
        row = self._conn.execute(
            "SELECT scenario FROM InstanceDeployConfig "
            "WHERE instance_id = ?",
            (self._instance.id,),
        ).fetchone()
        return bool(row and row[0] == "self_hosted")
    except Exception:
        return False
```

The bug: the final `return bool(row and row[0] == "self_hosted")` returns `False` when `row` is `None` (no `InstanceDeployConfig` exists). For an instance with no successful `DeploymentRun` and no `InstanceDeployConfig`, this returns `False` even though the instance may well be self-hosted.

Replacement:

```python
def _instance_is_self_hosted(self) -> bool:
    """Return True unless the active instance is positively non-self-hosted.

    Checks DeploymentRun rows first (the wizard's scenario record),
    then InstanceDeployConfig. If either source provides a scenario,
    that scenario governs the answer. If neither source has a row,
    the instance has no recorded scenario yet — treat it as self-hosted
    so the backfill dialog can be reached. Cloud-hosted and
    bring-your-own scenarios are recognized only when explicitly
    recorded.

    Returns False when no instance is active or when a SQL error
    prevents reading the relevant tables.
    """
    if self._conn is None or self._instance is None:
        return False
    try:
        row = self._conn.execute(
            "SELECT scenario FROM DeploymentRun "
            "WHERE instance_id = ? AND outcome = 'success' "
            "ORDER BY completed_at DESC LIMIT 1",
            (self._instance.id,),
        ).fetchone()
        if row:
            return row[0] == "self_hosted"
        row = self._conn.execute(
            "SELECT scenario FROM InstanceDeployConfig "
            "WHERE instance_id = ?",
            (self._instance.id,),
        ).fetchone()
        if row:
            return row[0] == "self_hosted"
        # No recorded scenario — assume self-hosted so the user can
        # reach the backfill dialog. Cloud-hosted and BYO instances
        # carry positive evidence in one of the two tables above.
        return True
    except Exception:
        return False
```

Note the structural change: the second-fallback `return bool(row and row[0] == "self_hosted")` becomes a paired `if row: return row[0] == "self_hosted"` followed by an unconditional `return True` for the no-row case.

### 2. Updated `refresh()`

Current snippet (lines 156–164):

```python
# Show the Upgrade and Recovery buttons only for self-hosted
# instances. The presence of an InstanceDeployConfig with
# scenario=self_hosted is the gate; new self-hosted deployments
# use the backfill dialog if no config exists yet.
is_sh = self._instance_is_self_hosted()
self._upgrade_btn.setVisible(is_sh)
self._recovery_btn.setVisible(is_sh)
has_config = is_sh and self._instance_has_deploy_config()
self._regenerate_record_btn.setVisible(has_config)
```

Replacement:

```python
# Show the Upgrade, Recovery, and Generate Deployment Record
# buttons whenever the active instance is self-hosted. All three
# handlers use the backfill dialog if no InstanceDeployConfig
# exists yet, so the buttons no longer need to wait for a config
# row to appear.
is_sh = self._instance_is_self_hosted()
self._upgrade_btn.setVisible(is_sh)
self._recovery_btn.setVisible(is_sh)
self._regenerate_record_btn.setVisible(is_sh)
```

The local variable `has_config` is removed.

### 3. Remove `_instance_has_deploy_config()`

Verify nothing outside `deploy_entry.py` calls this method:

```
grep -rn "_instance_has_deploy_config" automation/ tests/
```

The expected output is exactly the one definition site in `deploy_entry.py` and the (now-removed) call site we just changed. If the grep returns any other call sites, stop and surface that finding rather than removing the method.

If the grep is clean, remove the method entirely.

### 4. Tests

Open `tests/test_deploy_entry.py` (added by Prompt F). Examine its existing fixtures and patching patterns. Add the following tests, using the same patterns:

- **`test_instance_is_self_hosted_when_no_run_and_no_config`** — construct a `DeployEntry`, set `_conn` to a connection with empty `DeploymentRun` and `InstanceDeployConfig` tables, set `_instance` to a populated `InstanceRow`, assert `_instance_is_self_hosted()` returns `True`.

- **`test_instance_is_self_hosted_false_for_cloud_hosted_run`** — same fixture, but insert a `DeploymentRun` row with `scenario='cloud_hosted'` and `outcome='success'`. Assert `_instance_is_self_hosted()` returns `False`.

- **`test_instance_is_self_hosted_true_for_self_hosted_run`** — insert a `DeploymentRun` row with `scenario='self_hosted'` and `outcome='success'`. Assert `_instance_is_self_hosted()` returns `True`.

- **`test_regenerate_record_button_visible_for_self_hosted_without_config`** — construct a `DeployEntry`, populate the database with a self-hosted `Instance` and zero `InstanceDeployConfig` rows, call `refresh()`, assert `_regenerate_record_btn.isVisible()` is `True`. (This is the regression test for the original bug.)

- **`test_regenerate_record_button_hidden_for_cloud_hosted`** — same setup but with a `DeploymentRun` row indicating cloud-hosted. Assert `_regenerate_record_btn.isVisible()` is `False`.

If the existing test file already covers some of these cases, do not duplicate; extend or skip as appropriate.

---

## Acceptance criteria

- `_instance_is_self_hosted()` returns `True` for an instance with no `DeploymentRun` and no `InstanceDeployConfig` row.
- `refresh()` makes all three buttons visible (Upgrade, Recovery & Reset, Generate Deployment Record) for a self-hosted instance with no prior config.
- The `_instance_has_deploy_config` helper is removed from `deploy_entry.py`.
- All existing tests in `tests/test_deploy_entry.py` continue to pass.
- The new tests added by this prompt pass.
- All other deployment-record-series tests continue to pass.
- `uv run ruff check automation/ui/deployment/deploy_entry.py tests/test_deploy_entry.py` passes.
- `grep -rn "_instance_has_deploy_config" automation/ tests/` returns zero matches after the change.
- `grep -n "has_config" automation/ui/deployment/deploy_entry.py` returns zero matches after the change.

---

## Notes for the implementer

- This prompt deliberately makes one unbalanced trade: it errs on the side of *showing* buttons rather than hiding them. The cost of showing an action button on a non-self-hosted instance is one wasted click — the user clicks Upgrade, sees the backfill dialog, recognizes the dialog is asking for SSH details that don't apply to their instance, and clicks Cancel. The cost of hiding the buttons (the current bug) is a complete deadlock with no path to recovery short of a developer fix. The asymmetry favors showing.
- Do not introduce any new "unknown scenario" tracking column or sentinel value. The current schema's silence on scenario for instances without a run / config row is sufficient; the application just needs to interpret that silence as "self-hosted by default" rather than "unknown, hide all features."
- The user is sitting at the application waiting for this fix. Keep the change tight and execute promptly. Do not refactor surrounding code, even if tempted.

# Claude Code Prompt — Error Handling Series, Prompt C

**Series:** error-handling (defensive error handling across the run pipeline)
**Prompt ID:** C
**Descriptor:** step-status-truthfulness
**Filename:** `CLAUDE-CODE-PROMPT-error-handling-C-step-status-truthfulness.md`
**Repository:** `crmbuilder`
**Depends on:** Prompts A and B merged (commit `5cd47d2 YAML Fixes`).
**Last Updated:** 05-02-26 16:00
**Version:** 1.0

---

## Status

The first live Configure run after Prompts A and B revealed a regression: **the STEP SUMMARY block lies.** A run with three failed relationships (HTTP 409 on every one) and a failed saved-views write (HTTP 405) showed:

```
=== SAVED VIEWS ===
[CHECK]   Contribution savedViews ...
[CREATE]  Contribution.savedViews[contribution-acknowledgment-pending] ... NOT FOUND ON CRM
[CREATE]  Contribution.savedViews[contribution-grant-deadlines] ... NOT FOUND ON CRM
[WRITE]   Contribution savedViews metadata ...
[ERROR]   Contribution savedViews metadata ... HTTP 405
          non-JSON response: <!doctype html>...
...
=== RELATIONSHIP OPERATIONS ===
[RELATIONSHIP]  Contribution → Contact (donorContact) ... ERROR (HTTP 409: ...)
[RELATIONSHIP]  Contribution → Account (donorAccount) ... ERROR (HTTP 409: ...)
[RELATIONSHIP]  Contribution → FundraisingCampaign (campaign) ... ERROR (HTTP 409: ...)
RELATIONSHIP SUMMARY
  Failed                      : 3
...
STEP SUMMARY
  Saved views               : OK         ← LIE
  Relationships             : OK         ← LIE
Run completed successfully               ← LIE
```

The bug is structural in `_run_step()`. Each manager handles per-item failures by emitting `[ERROR]` lines and recording `XxxStatus.ERROR` in its result list — none of them raise unless authentication fails. The body callable returns normally, `_run_step` sees success, and records `StepStatus.OK`. The aggregate STEP SUMMARY block is therefore actively misleading: it tells the user the deployment succeeded when it partially failed.

This is worse than no summary. The whole point of Prompt B was to give the operator reliable visibility into what worked and what didn't; Prompt C makes that visibility actually reliable.

After Prompt C: each step's reported status reflects whether the step actually accomplished its work. A step is `OK` only if every item processed succeeded. A step is `FAILED` if any item produced an error or verification failure. Drift (informational "exists on CRM, not in YAML") does not count as failure. The footer line correctly says "Run completed with N step failure(s)" when there are any.

---

## What this prompt accomplishes

1. **Add a result-inspection helper** to `espo_impl/workers/run_worker.py`:

   ```python
   def _check_results_for_errors(
       results: Iterable[Any] | None,
       error_statuses: set[Any],
       label: str,
   ) -> str | None:
       """Return a one-line failure summary, or None if no errors.

       :param results: Iterable of result records, each with a .status field.
       :param error_statuses: Statuses that count as failure (e.g. {SavedViewStatus.ERROR}).
       :param label: Human label for the result type (e.g. "saved view").
       :returns: f"{n} of {total} {label}(s) failed" if any errors, else None.
       """
   ```

   Module-level function. Defensive against `None`, missing `.status` attribute, empty iterables.

2. **Extend `_run_step` to accept an optional `failure_check` callable**:

   ```python
   def _run_step(
       self,
       step_name: str,
       has_work: bool,
       body: Callable[[], Any],
       failure_check: Callable[[Any], str | None] | None = None,
   ) -> tuple[StepResult, Any]:
   ```

   When the body returns normally AND `failure_check` is provided AND it returns a non-None string, downgrade the StepResult from `OK` to `FAILED` with that string as the error, emit a `[STEP FAILED]` line, and still return the body's return value (so callers can attach results to the report). When `failure_check` returns None (or is not provided), behavior is unchanged.

3. **Wire up failure checks for every step in `_run_full`** that can have per-item failures:

   - **entity_deletions** — track failure count via dict closure inside the body (since `_delete_entity` returns bool); failure check: `f"{n} entity deletion(s) failed"`.
   - **entity_creations** — same pattern as deletions, calling `_create_entity` and tracking the bool return.
   - **entity_settings** — body returns `list[SettingsResult]`; check `{SettingsStatus.ERROR}`.
   - **email_templates** — body returns `list[EmailTemplateResult]`; check `{EmailTemplateStatus.ERROR}`.
   - **duplicate_checks** — body returns `list[DuplicateCheckResult]`; check `{DuplicateCheckStatus.ERROR}`.
   - **saved_views** — body returns `list[SavedViewResult]`; check `{SavedViewStatus.ERROR}`.
   - **fields** — body returns `RunReport`; check `report.summary.errors > 0` and also `report.summary.verification_failed > 0`. Failure summary: `f"{errors} field(s) failed, {vfail} verification failure(s)"` with appropriate truncation when one is zero.
   - **layouts** — body has side effect on `report.layout_results`; failure check inspects the report after body completes; check `{EntityLayoutStatus.ERROR, EntityLayoutStatus.VERIFICATION_FAILED}`.
   - **relationships** — same shape; check `{RelationshipStatus.ERROR, RelationshipStatus.WARNING}` (matches existing `relationships_failed` summary count which already groups WARNING with failures).
   - **workflows** — same shape; check `{WorkflowStatus.ERROR}`.

4. **DRIFT statuses are informational, not failures.** Drift means "exists on CRM but not in YAML" — the YAML was applied successfully; the CRM has additional content. This is not a step failure. Do not include `DRIFT` in any error_statuses set.

5. **SKIPPED and SKIPPED_TYPE_CONFLICT do not count as failures** in this prompt. (`SKIPPED_TYPE_CONFLICT` arguably indicates a YAML/CRM disagreement that the user should know about — leave it for a future prompt to reclassify.)

6. **Update tests in `tests/test_run_worker.py`**:
   - New test: a step body returns a result list containing one ERROR record → step status is FAILED with the error summary string.
   - New test: a step body returns a result list with all SUCCESS records → step status is OK.
   - New test: a step body returns a list with only DRIFT records → step status is OK (drift is not failure).
   - New test: fields step where `report.summary.errors == 2` → step status is FAILED with `"2 field(s) failed"` substring.
   - New test: layouts step where the body sets `report.layout_results` to include one ERROR record → step status is FAILED.
   - New test: entity_creations step where `_create_entity` returns False once out of three calls → step status is FAILED with `"1 entity creation(s) failed"`.
   - **Update existing tests** that assumed body-returns-normally implies StepStatus.OK for cases where the returned results contain errors. Those tests must now either use all-success results or assert the FAILED outcome.
   - The existing test `test_run_full_saved_views_raises_manager_error` (or whatever it's called) is unaffected — raised exceptions still take the existing FAILED path through the `except` handler.

7. **Verify configure_progress.py UI behavior** is now correct: a run where a step is downgraded to FAILED via the new path should produce the same yellow "Completed with errors" outcome as a run where a step raised. Add or update one UI test to confirm this.

8. **No changes to managers**, no changes to the `XxxStatus` enums, no changes to `XxxResult` dataclasses. Pure changes are: `_run_step` signature widening, new helper, and per-step failure_check wiring.

---

## What this prompt does NOT do

- **Does not change manager raise/return contracts.** Managers still emit `[ERROR]` lines and record ERROR statuses without raising. Refactoring to raise on per-item failures would cascade through every manager and is a much larger architectural change.
- **Does not reclassify SKIPPED_TYPE_CONFLICT as failure.** That's a separate decision worth its own discussion.
- **Does not change DRIFT handling.** Drift remains informational.
- **Does not modify the per-manager summary blocks** (RUN SUMMARY for fields, LAYOUT SUMMARY, RELATIONSHIP SUMMARY). They already accurately report counts; the bug is only in STEP SUMMARY.
- **Does not introduce a "warning" StepStatus.** Some result types have WARNING (RelationshipStatus). For step-level rollup, treat WARNING as failure (matching the existing `relationships_failed` summary). A finer-grained step status is not in scope.
- **Does not add a "what failed and why" detail block** beyond the one-line `[STEP FAILED]` summary plus the existing per-item error lines emitted inside the step. The user has both: per-item detail in the step body, and step-level rollup in STEP SUMMARY.

---

## Constraints and conventions

- **`failure_check` is optional and additive.** Existing call sites that don't pass it behave exactly as before. No breaking changes to `_run_step` signature semantics.
- **`failure_check` is called only on the success path.** If the body raised, the step is already FAILED via the existing except handler — don't call `failure_check` after a raise.
- **`failure_check` is called with the body's return value.** For steps where the body doesn't return relevant data (layouts, relationships, workflows update `report.X_results` from inside), the closure can ignore the argument and inspect `report` directly. Use `_` as the parameter name.
- **For entity creations and deletions**, use a closure-captured dict to track failure counts:

  ```python
  fail_count = {"value": 0}

  def _body() -> None:
      for entity_def in creates:
          ok = entity_mgr._create_entity(entity_def)
          if not ok:
              fail_count["value"] += 1
      entity_mgr.rebuild_cache()

  def _failure_check(_: Any) -> str | None:
      n = fail_count["value"]
      return f"{n} entity creation(s) failed" if n > 0 else None
  ```

  Don't use a plain int because Python closures can't rebind enclosing scope without `nonlocal`, and dict mutation is the established pattern in this codebase (see `had_entity_ops_state["value"]` already in use).

- **The `[STEP FAILED]` line emitted from the failure_check downgrade** uses the same format as the `[STEP FAILED]` line emitted from the existing exception path, so the UI's tooltip-collection logic in configure_progress.py works without modification.
- **Plurality / grammar in failure summaries:** always emit "(s)" suffix, no special-casing for n=1. `"1 of 3 saved view(s) failed"`. Keeps the helper simple.
- **Python 3.11+, type hints, docstrings, pytest** — same conventions as the rest of the codebase.
- **No changes to PRD documents.** This prompt is purely code + tests.

---

## Detailed implementation

### Step 1 — Helper function

In `espo_impl/workers/run_worker.py`, near the top-of-module helpers (alongside `_format_error_detail` and `_is_authentication_message`):

```python
def _check_results_for_errors(
    results: Iterable[Any] | None,
    error_statuses: set[Any],
    label: str,
) -> str | None:
    """Inspect a result list and return a failure summary, or None if clean.

    :param results: Iterable of result records (may be None or empty).
    :param error_statuses: Set of status enum values that count as failure.
    :param label: Singular human label, e.g. "saved view", "field".
    :returns: ``"{n} of {total} {label}(s) failed"`` if any errors, else None.
    """
    if not results:
        return None
    items = list(results)
    error_count = sum(
        1 for r in items
        if getattr(r, "status", None) in error_statuses
    )
    if error_count == 0:
        return None
    return f"{error_count} of {len(items)} {label}(s) failed"
```

Add `from collections.abc import Iterable` to the imports if not already present.

### Step 2 — Extend `_run_step`

```python
def _run_step(
    self,
    step_name: str,
    has_work: bool,
    body: Callable[[], Any],
    failure_check: Callable[[Any], str | None] | None = None,
) -> tuple[StepResult, Any]:
    if not has_work:
        return (
            StepResult(step_name=step_name, status=StepStatus.SKIPPED),
            None,
        )

    try:
        return_value = body()
    except AuthenticationError:
        # ... existing handling ...
        raise
    except Exception as exc:
        # ... existing handling ...
        return (
            StepResult(
                step_name=step_name,
                status=StepStatus.FAILED,
                error=error_detail,
            ),
            None,
        )

    # New: post-success failure inspection
    if failure_check is not None:
        error_summary = failure_check(return_value)
        if error_summary:
            self.output_line.emit(
                f"[STEP FAILED] {step_name}: {error_summary}", "red"
            )
            return (
                StepResult(
                    step_name=step_name,
                    status=StepStatus.FAILED,
                    error=error_summary,
                ),
                return_value,
            )

    return (
        StepResult(step_name=step_name, status=StepStatus.OK),
        return_value,
    )
```

### Step 3 — Wire up each step

For result-list steps (settings, email_templates, duplicate_checks, saved_views), the failure_check is a one-liner:

```python
step_result, sv_results = self._run_step(
    "saved_views",
    has_saved_views,
    _saved_views_body,
    failure_check=lambda results: _check_results_for_errors(
        results, {SavedViewStatus.ERROR}, "saved view"
    ),
)
```

For layouts (results live on `report.layout_results`):

```python
def _layouts_failure_check(_: Any) -> str | None:
    return _check_results_for_errors(
        report.layout_results,
        {EntityLayoutStatus.ERROR, EntityLayoutStatus.VERIFICATION_FAILED},
        "layout",
    )

step_result, _ = self._run_step(
    "layouts", has_layouts, _layouts_body,
    failure_check=_layouts_failure_check,
)
```

For relationships and workflows: same pattern as layouts.

For fields (returns RunReport):

```python
def _fields_failure_check(fr: Any) -> str | None:
    if fr is None:
        return None
    errs = fr.summary.errors
    vfail = fr.summary.verification_failed
    if errs == 0 and vfail == 0:
        return None
    parts: list[str] = []
    if errs:
        parts.append(f"{errs} field(s) failed")
    if vfail:
        parts.append(f"{vfail} verification failure(s)")
    return ", ".join(parts)

step_result, fields_report = self._run_step(
    "fields", has_fields, _fields_body,
    failure_check=_fields_failure_check,
)
```

For entity_creations and entity_deletions (use closure-captured counter):

```python
create_fail_count = {"value": 0}

def _entity_creations_body() -> None:
    self.output_line.emit("", "white")
    self.output_line.emit("=== ENTITY CREATION ===", "white")
    for entity_def in creates:
        ok = entity_mgr._create_entity(entity_def)
        if not ok:
            create_fail_count["value"] += 1
    entity_mgr.rebuild_cache()
    had_entity_ops_state["value"] = True

def _entity_creations_failure_check(_: Any) -> str | None:
    n = create_fail_count["value"]
    return f"{n} entity creation(s) failed" if n > 0 else None

step_result, _ = self._run_step(
    "entity_creations", bool(creates), _entity_creations_body,
    failure_check=_entity_creations_failure_check,
)
```

Note: this also fixes a pre-existing latent bug — currently the worker calls `entity_mgr._create_entity()` and ignores the bool return. After this prompt, a False return is at least counted into the step's failure summary.

### Step 4 — Tests

Add to `tests/test_run_worker.py`:

```python
def test_saved_views_with_internal_errors_marks_step_failed():
    # Body returns a list with one ERROR record; expect StepStatus.FAILED.
    ...

def test_saved_views_all_clean_marks_step_ok():
    # Body returns list of all CREATED/UPDATED/SKIPPED; expect OK.
    ...

def test_saved_views_drift_only_marks_step_ok():
    # Body returns list of all DRIFT; expect OK (drift is not failure).
    ...

def test_fields_with_errors_marks_step_failed():
    # report.summary.errors == 2; expect FAILED with "2 field(s) failed" in message.
    ...

def test_fields_with_verification_failed_marks_step_failed():
    # report.summary.verification_failed == 1; expect FAILED.
    ...

def test_layouts_with_errors_marks_step_failed():
    # report.layout_results has one ERROR; expect FAILED.
    ...

def test_relationships_with_warning_marks_step_failed():
    # WARNING status counts as failure (matches existing summary semantics).
    ...

def test_entity_creations_partial_failure_marks_step_failed():
    # _create_entity returns False once; expect FAILED with "1 entity creation(s) failed".
    ...

def test_check_results_for_errors_helper():
    # Direct unit tests of the helper for None, empty, all-clean, mixed.
    ...
```

Update any existing tests that asserted StepStatus.OK in scenarios where a real result list contained errors. Find them by searching for `StepStatus.OK` and checking whether the test's mock returns include error statuses.

### Step 5 — Verification

```bash
pytest tests/ -x -v 2>&1 | tail -80
ruff check espo_impl/workers/run_worker.py tests/test_run_worker.py
mypy espo_impl/workers/run_worker.py
```

All existing tests must still pass (modulo the ones updated per Step 4). The 3 pre-existing test_entity_settings.py validation failures and other pre-existing failures noted in the Prompt A and B summaries remain pre-existing and out of scope.

Then a manual smoke test against any reachable instance:

1. Find or construct a YAML that will produce a per-item failure in some step (e.g., the FU-Contribution YAML still produces saved-view 405 and relationship 409s today).
2. Run Configure on it.
3. Confirm the STEP SUMMARY now shows `Saved views : FAILED (...)` and `Relationships : FAILED (...)` and the footer says `Run completed with 2 step failure(s)`.
4. Confirm the configure_progress UI shows the file in amber (Completed with errors) with a tooltip listing the failed steps.

---

## Acceptance criteria

- [ ] `_check_results_for_errors` helper exists in `run_worker.py`, with type hints and docstring.
- [ ] `_run_step` accepts optional `failure_check` parameter and downgrades to FAILED when it returns a non-None string.
- [ ] All 10 steps in `_run_full` have a `failure_check` wired up where applicable (entity_deletions, entity_creations, entity_settings, email_templates, duplicate_checks, saved_views, fields, layouts, relationships, workflows).
- [ ] DRIFT statuses do not trigger step FAILED.
- [ ] SKIPPED / SKIPPED_TYPE_CONFLICT do not trigger step FAILED.
- [ ] At least one new test per step type listed in Step 4.
- [ ] Existing tests updated where necessary; full test suite passes (modulo pre-existing failures).
- [ ] `ruff check` and `mypy` clean for modified files.
- [ ] Manual smoke test: a known-failing YAML now reports `STEP SUMMARY` with FAILED steps and amber UI outcome.

---

## Commit message

```
fix(run_worker): step status reflects per-item failures

After Prompts A and B, _run_step recorded StepStatus.OK whenever the
step body returned normally — but most managers handle per-item
failures by emitting [ERROR] lines and recording XxxStatus.ERROR in
their result list, not by raising. The result was a STEP SUMMARY block
that reported all-OK on runs where saved views, relationships, fields,
or other items had failed. Worse than no summary: an actively
misleading one.

This commit:
- Adds _check_results_for_errors helper for inspecting result lists
  and returning a one-line failure summary.
- Extends _run_step with an optional failure_check callable. When the
  body returns normally but the check returns a non-None string, the
  step is downgraded to FAILED with that string as the error and a
  [STEP FAILED] line is emitted.
- Wires up failure checks for every step that can have per-item
  failures: entity creations/deletions, settings, email templates,
  duplicate checks, saved views, fields, layouts, relationships,
  workflows.
- DRIFT statuses are NOT counted as failure (informational only).
- SKIPPED / SKIPPED_TYPE_CONFLICT not counted (preserve existing
  semantics; SKIPPED_TYPE_CONFLICT may merit reclassification later).
- Side fix: entity creations now count False returns from
  _create_entity, which were previously ignored.

After this commit, the FU-Contribution Configure run that previously
showed "Run completed successfully" with 3 failed relationships and a
failed saved-views write will correctly report:
  Saved views               : FAILED (1 of 1 saved view(s) failed)
  Relationships             : FAILED (3 of 3 relationship(s) failed)
  Run completed with 2 step failure(s)

This is Prompt C in the error-handling series.
```

# Claude Code Prompt — Error Handling Series, Prompt B

**Series:** error-handling (defensive error handling across the run pipeline)
**Prompt ID:** B
**Descriptor:** worker-step-isolation
**Filename:** `CLAUDE-CODE-PROMPT-error-handling-B-worker-step-isolation.md`
**Repository:** `crmbuilder`
**Depends on:** Prompt A merged. Prompt A's `_format_error_detail()` helper and sentinel body shapes are used by the new step-failure logging.
**Last Updated:** 05-02-26 14:30
**Version:** 1.0

---

## Status

`espo_impl/workers/run_worker.py` orchestrates a Configure run as a sequence of phases:

1. Entity deletions (optional)
2. Entity creations (optional)
3. Entity settings
4. Email templates
5. Duplicate-check rules
6. Saved views
7. Field operations
8. Layout operations
9. Relationship operations
10. Workflow operations

`RunWorker.run()` wraps the whole thing in a single `try/except Exception` that, on any unhandled exception, calls `self.finished_error.emit(str(exc))` and aborts. The progress dialog then shows the file as failed and stops processing further files.

This was the failure mode observed in the live FU-Contribution Configure run: a `JSONDecodeError` raised inside the saved-view writer escaped the `SavedViewManagerError` catch, hit the catch-all, and killed the run before fields, layouts, relationships, or workflows were processed. The user saw `Error: Expecting value: line 1 column 1 (char 0)` and nothing else.

Prompt A makes the parse-error case impossible (parse failures now return sentinel bodies, not exceptions), but the broader architectural problem remains: **the worker has no per-step isolation.** Any unanticipated exception in any manager kills the entire run. There's no shortage of ways this can happen — KeyError on a malformed YAML edge case, AttributeError on a None where a dict was expected, TypeError from a model mismatch, future bugs in any of the ten manager classes.

The right shape: each step runs in its own try block. An unhandled exception emits a clear `[ERROR]` line for that step, marks the step as failed in the report, and the run continues to the next step. The user gets a complete picture of what worked and what didn't, in one run, and downstream steps that don't depend on the failed one still execute.

After Prompt B: a manager raising any exception (its declared `*ManagerError`, an unexpected `KeyError`, anything) is contained to its own step. The run continues. The final summary clearly shows which steps failed. Auth errors (HTTP 401) remain a hard abort — those affect every step and there's no value in continuing.

---

## What this prompt accomplishes

1. **Refactor `RunWorker._run_full()`** in `espo_impl/workers/run_worker.py` to wrap each step (entity deletions, entity creations, entity settings, email templates, duplicate checks, saved views, fields, layouts, relationships, workflows) in its own protected block.

2. **Define a step-execution contract**:
   - Each step is a callable that returns `tuple[bool, list[Any]]` where the bool is success/failure and the list is the step's results (settings results, dup-check results, etc., as applicable).
   - The wrapper around each step catches `AuthenticationError` (re-raise — terminates the run), and `Exception` (logged, marked as failed, continues).
   - Each protected step emits `=== <STEP NAME> ===` header → step body → either `[STEP OK] <step name>` or `[STEP FAILED] <step name>: <error detail>` footer.

3. **Add a `StepStatus` and `StepResult` model** to `espo_impl/core/models.py`:
   - `StepStatus` enum with values `OK`, `FAILED`, `SKIPPED` (skipped means the step was a no-op because there was nothing to process).
   - `StepResult` dataclass with `step_name: str`, `status: StepStatus`, `error: str | None`, `details: dict[str, Any]`.
   - Add `step_results: list[StepResult]` to `RunReport`.

4. **Update the run summary emission** to include a per-step status block. After the existing field summary, emit:
   ```
   ===========================================
   STEP SUMMARY
   ===========================================
     Entity deletions          : OK / FAILED / SKIPPED (n)
     Entity creations          : ...
     ...
   ===========================================
   ```
   Plus a final terminal line: `Run completed with N step failures` or `Run completed successfully`.

5. **Hard-abort conditions** (these still terminate the run):
   - `AuthenticationError` from any layer — emit `[FATAL] Authentication failed — aborting run` and stop.
   - HTTP 401 returned by any API call routed through a manager — managers already raise `*ManagerError("Authentication failed (HTTP 401)")`; the worker now distinguishes these from other manager errors. If the message contains "401" or "Authentication", treat as fatal. (Long-term cleanup would be a dedicated `AuthenticationError` raised everywhere, but that's outside this prompt.)

6. **Soft-abort conditions** (these mark the step failed but continue):
   - `*ManagerError` (`EntityManagerError`, `SavedViewManagerError`, etc.) — emit `[STEP FAILED]` line with `_format_error_detail` of the message and continue.
   - Any other `Exception` — emit `[STEP FAILED]` with exception type and message, log the full traceback at `logger.exception(...)` level, and continue. Worker keeps running.

7. **Update `RunWorker.run()`** to:
   - Keep the outer `try/except Exception` as a final safety net (catches anything that escapes the per-step wrappers, which should be impossible after this refactor but is defensive).
   - On the final-safety-net catch, emit `[FATAL] Unexpected error — please file a bug: <type>: <msg>` with the full traceback at log level, then call `finished_error.emit`.

8. **Update `RunReport` model** in `espo_impl/core/models.py` to include `step_results: list[StepResult] = field(default_factory=list)`. Existing fields stay.

9. **Update `configure_progress.py`'s `_on_worker_ok` handler** to display the per-file outcome based on `report.step_results`: if any step has status `FAILED`, mark the file as `Completed with errors` (yellow) instead of `Completed successfully` (green). If all steps are `OK` or `SKIPPED`, keep the green outcome. Add a tooltip on the file row showing which steps failed.

10. **Tests**:
    - In `tests/workers/test_run_worker.py` (create or extend): tests that mock each manager to either succeed, raise its declared `*ManagerError`, or raise an unexpected `KeyError`/`RuntimeError`, and assert that:
      - Successful steps produce `StepStatus.OK`.
      - `*ManagerError` produces `StepStatus.FAILED` and the run continues.
      - Unexpected exceptions produce `StepStatus.FAILED` and the run continues.
      - `AuthenticationError` aborts the run and emits `[FATAL]`.
      - 401 in any manager error message aborts the run.
    - Test that `report.step_results` contains the expected entries in expected order.
    - Test that `configure_progress.py` shows yellow when a file has any failed step (UI-level test if the existing test infrastructure supports it; otherwise a unit test on the logic that determines the outcome color).

---

## What this prompt does NOT do

- **Does not introduce a `BaseManagerError`** or unify the manager exception hierarchy. That's a worthy refactor but bigger than this prompt. For now we just match on `*ManagerError` types via tuple isinstance check.
- **Does not change manager behavior.** Managers still raise the same exceptions, still emit the same output. The change is entirely at the worker layer.
- **Does not retry failed steps.** A failed step stays failed. Retry policy is a future feature.
- **Does not change how individual fields/views/etc. handle errors *within* a step.** `field_manager` already processes all fields even if some fail — that's intra-step resilience and stays as-is.
- **Does not introduce dependencies between steps.** Today, fields can be processed even if entity settings failed, layouts can be processed even if fields failed, etc. This is preserved. (In some real-world cases this means downstream steps will fail in cascading ways — e.g., if entity creation fails, the field step will then fail because the entity doesn't exist. That's fine — each failure is logged independently and the user sees the full picture.)
- **Does not modify the `verify` or `preview` paths in `RunWorker.run()`.** Those don't have multi-step orchestration; they're single-call paths through `field_mgr.verify()` or `field_mgr.preview()`. Wrapping is unnecessary and the existing `try/except` is sufficient.
- **Does not add a "fail fast" mode.** All steps always run. If the user wants to abort on first failure they can hit Cancel.

---

## Constraints and conventions

- **Step ordering is preserved exactly.** Don't reorder. The existing order has semantic meaning (entities before fields, settings before saved views, etc.).
- **Emit step headers (`=== <STEP NAME> ===`) only when the step has work to do.** The existing code already guards each step with `if has_settings:` / `if has_dup_checks:` etc. Preserve those guards. A step with no work emits no header and gets `StepStatus.SKIPPED` in the step summary.
- **Cache rebuild after entity ops** is part of the entity-create / entity-delete steps, not its own step. If rebuild fails, that's a failure of the parent step.
- **Don't lose the existing per-step result attachments.** The current code does `self._settings_results = settings_mgr.process_settings(...)` and later attaches to the report. Keep that — just route it through the protected wrapper.
- **`StepResult.step_name`** uses canonical strings: `"entity_deletions"`, `"entity_creations"`, `"entity_settings"`, `"email_templates"`, `"duplicate_checks"`, `"saved_views"`, `"fields"`, `"layouts"`, `"relationships"`, `"workflows"`. Snake_case, no display formatting. Display formatting happens at output time.
- **`StepResult.error`**: when status is `FAILED`, must be non-None and contain a useful description. Use `_format_error_detail` from Prompt A for `*ManagerError` messages where the error message itself looks like it came from an HTTP body. For unexpected exceptions, use `f"{type(exc).__name__}: {exc}"`.
- **Logger usage**: each unexpected exception path calls `logger.exception(...)` (which logs the full traceback). `*ManagerError` paths call `logger.warning(...)` (no traceback — it's a known failure mode).
- **No changes to PRD documents.** This prompt is purely code + tests.
- **Python 3.11+, type hints, docstrings, pytest** — same conventions as the rest of the codebase.

---

## Detailed implementation

### Step 1 — Models

In `espo_impl/core/models.py`, add:

```python
from enum import Enum


class StepStatus(str, Enum):
    OK = "ok"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    step_name: str
    status: StepStatus
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
```

Add to `RunReport`:

```python
step_results: list[StepResult] = field(default_factory=list)
```

### Step 2 — Worker refactor pattern

Introduce a private helper on `RunWorker`:

```python
def _run_step(
    self,
    step_name: str,
    has_work: bool,
    body: Callable[[], Any],
) -> tuple[StepResult, Any]:
    """Run one phase of the pipeline, isolating failures.

    :param step_name: Canonical snake_case step name.
    :param has_work: If False, the step is skipped (no-op, no header emitted).
    :param body: Zero-arg callable that runs the step. Returns step-specific
        results (or None). May raise *ManagerError or any Exception.
    :returns: Tuple of (StepResult, body return value or None on failure).
    :raises AuthenticationError: Re-raised so the caller can hard-abort.
    """
    if not has_work:
        return StepResult(step_name=step_name, status=StepStatus.SKIPPED), None

    try:
        return_value = body()
    except AuthenticationError:
        raise
    except Exception as exc:
        # Distinguish authentication-flavored manager errors
        msg = str(exc)
        if "401" in msg or "Authentication" in msg:
            self.output_line.emit(
                f"[FATAL]   Authentication failed during {step_name} — aborting run",
                "red",
            )
            raise AuthenticationError(msg) from exc

        is_known_manager_error = isinstance(exc, _MANAGER_ERROR_TYPES)
        if is_known_manager_error:
            logger.warning(
                "Step %s failed with manager error: %s", step_name, exc
            )
            error_detail = _format_error_detail({"message": msg})
        else:
            logger.exception("Step %s failed with unexpected exception", step_name)
            error_detail = f"{type(exc).__name__}: {msg}"

        self.output_line.emit(
            f"[STEP FAILED] {step_name}: {error_detail}", "red"
        )
        return (
            StepResult(
                step_name=step_name,
                status=StepStatus.FAILED,
                error=error_detail,
            ),
            None,
        )

    return StepResult(step_name=step_name, status=StepStatus.OK), return_value
```

`_MANAGER_ERROR_TYPES` is a module-level tuple imported at the top:

```python
_MANAGER_ERROR_TYPES = (
    EntityManagerError,
    EntitySettingsManagerError,
    EmailTemplateManagerError,
    DuplicateCheckManagerError,
    SavedViewManagerError,
    LayoutManagerError,
    RelationshipManagerError,
    WorkflowManagerError,
)
```

### Step 3 — Wire each step through `_run_step`

Convert each existing step block. Example for the saved-views step:

```python
has_saved_views = any(
    e.saved_views and e.action != EntityAction.DELETE
    for e in self.program.entities
)

def _saved_views_body() -> list[SavedViewStatus]:
    self.output_line.emit("", "white")
    self.output_line.emit("=== SAVED VIEWS ===", "white")
    sv_mgr = SavedViewManager(client, self.output_line.emit)
    return sv_mgr.process_saved_views(self.program)

step_result, sv_results = self._run_step(
    "saved_views", has_saved_views, _saved_views_body
)
all_step_results.append(step_result)
self._saved_view_results = sv_results or []
```

Apply the same conversion to entity_deletions, entity_creations, entity_settings, email_templates, duplicate_checks, fields, layouts, relationships, workflows.

The cache rebuild calls (`entity_mgr.rebuild_cache()`) stay inside the entity_creations and entity_deletions step bodies. If rebuild fails, the step's body raises and the wrapper marks the step failed.

### Step 4 — Step summary emission

After all steps complete (and after the existing field summary), emit:

```python
self.output_line.emit("", "white")
self.output_line.emit("===========================================", "white")
self.output_line.emit("STEP SUMMARY", "white")
self.output_line.emit("===========================================", "white")

failure_count = 0
for sr in all_step_results:
    display_name = _STEP_DISPLAY_NAMES.get(sr.step_name, sr.step_name)
    if sr.status == StepStatus.OK:
        self.output_line.emit(f"  {display_name:<26}: OK", "green")
    elif sr.status == StepStatus.SKIPPED:
        self.output_line.emit(f"  {display_name:<26}: SKIPPED", "gray")
    else:
        failure_count += 1
        self.output_line.emit(
            f"  {display_name:<26}: FAILED ({sr.error})", "red"
        )

self.output_line.emit("===========================================", "white")
if failure_count > 0:
    self.output_line.emit(
        f"Run completed with {failure_count} step failure(s)", "yellow"
    )
else:
    self.output_line.emit("Run completed successfully", "green")
```

Where `_STEP_DISPLAY_NAMES` is a module-level dict mapping snake_case to human-readable, e.g. `"entity_deletions": "Entity deletions"`.

Attach `step_results` to the report before emitting `finished_ok`:

```python
report.step_results = all_step_results
self.finished_ok.emit(report)
```

### Step 5 — Update `configure_progress.py`

In `_on_worker_ok`:

```python
if report and report.step_results:
    has_failures = any(
        sr.status == StepStatus.FAILED for sr in report.step_results
    )
    if has_failures:
        outcome = "Completed with errors"
        outcome_color = "yellow"
        failed = [
            sr.step_name for sr in report.step_results
            if sr.status == StepStatus.FAILED
        ]
        tooltip = "Failed steps: " + ", ".join(failed)
    else:
        outcome = "Completed successfully"
        outcome_color = "green"
        tooltip = ""
else:
    outcome = "Completed successfully"
    outcome_color = "green"
    tooltip = ""

# ... existing row update logic, applying outcome_color and tooltip
```

### Step 6 — Tests

Create or extend `tests/workers/test_run_worker.py`. Use `unittest.mock.patch` on each manager class to control its behavior. Reference existing test patterns in `tests/workers/` for fixture conventions.

Key tests:

- `test_run_full_all_steps_succeed`: every manager returns successfully; assert `step_results` has expected entries and all are `OK` or `SKIPPED`; assert `finished_ok` was emitted.
- `test_run_full_saved_views_raises_manager_error`: `SavedViewManager.process_saved_views` raises `SavedViewManagerError("Bad payload")`; assert that step is `FAILED` with error containing "Bad payload"; assert subsequent steps (fields, layouts, relationships, workflows) still ran and are `OK`; assert `finished_ok` (not `finished_error`) was emitted.
- `test_run_full_unexpected_exception`: a manager raises `KeyError("foo")`; assert step is `FAILED` with error `"KeyError: 'foo'"`; assert run continues; assert `logger.exception` was called.
- `test_run_full_authentication_error_aborts`: `EntityManager._create_entity` raises `EntityManagerError("Authentication failed (HTTP 401)")`; assert subsequent steps did NOT run; assert `[FATAL]` was emitted; assert `finished_error` was emitted.
- `test_run_full_authentication_error_class_aborts`: a manager raises `AuthenticationError()` directly; assert hard abort.
- `test_step_summary_emission`: verify the step summary block is emitted with correct format and counts.
- `test_configure_progress_yellow_on_step_failure`: a file with one failed step shows yellow outcome and tooltip lists the failed step.

### Step 7 — Verification

```bash
pytest tests/ -x -v 2>&1 | tail -80
ruff check espo_impl/workers/ espo_impl/core/models.py automation/ui/deployment/
mypy espo_impl/workers/run_worker.py
```

All existing tests pass. Then a manual smoke test:

1. Run Configure on a clean YAML against any reachable instance — confirm a successful run still shows the expected output and the new step summary.
2. Deliberately introduce a YAML error that will cause one specific step to fail (e.g., a saved view referencing a nonexistent field) and confirm the run completes with that step marked failed and other steps OK.

---

## Acceptance criteria

- [ ] `RunWorker._run_full()` is refactored: each step is wrapped in `_run_step`. No bare manager calls remain in `_run_full`.
- [ ] `_run_step` correctly distinguishes hard-abort (auth) vs soft-abort (everything else).
- [ ] `StepStatus` and `StepResult` exist in `models.py`. `RunReport.step_results` exists and is populated by `_run_full`.
- [ ] Step summary block is emitted after every full run with the documented format.
- [ ] `configure_progress.py` shows yellow outcome when any step fails, with a tooltip listing failed steps.
- [ ] All listed tests exist and pass.
- [ ] Manual smoke test: a YAML with one bad step still allows the rest of the run to complete; the user sees a clear summary of what worked and what didn't.
- [ ] All existing tests still pass.
- [ ] `ruff check` and `mypy` clean for modified files.

---

## Commit message

```
fix(run_worker): per-step exception isolation

Previously RunWorker.run() wrapped the entire 10-step Configure
pipeline in a single try/except, so any unhandled exception in
any manager (manager-declared error or otherwise) aborted the
entire run with a one-line Python error message and no per-step
visibility.

This commit refactors _run_full() to wrap each step in a protected
block via the new _run_step() helper. A failed step:
- Emits a clear [STEP FAILED] line with formatted error detail
- Records a StepResult(status=FAILED, error=...) in the report
- Does not block subsequent steps from running
- Logs full traceback at logger.exception level for unexpected
  exceptions (manager-declared errors get logger.warning)

Authentication failures (AuthenticationError, or "401" / "Authentication"
in any manager error message) remain a hard abort — there's no
value in continuing if auth is broken.

A new STEP SUMMARY block is emitted at the end of every run, listing
each step as OK / SKIPPED / FAILED with error detail. The progress
dialog shows a yellow "Completed with errors" outcome on files
that have any failed step, with a tooltip listing the failures.

Adds StepStatus enum and StepResult dataclass to models.py.
Adds step_results to RunReport.

This is Prompt B in the error-handling series. Together with Prompt
A (api_client hardening), the run pipeline is now resilient to
unexpected response formats and unexpected manager exceptions, with
clear diagnostic output at every step.
```

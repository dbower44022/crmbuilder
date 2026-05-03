# Claude Code Prompt — Error Handling Series, Prompt D

**Series:** error-handling (defensive error handling across the run pipeline)
**Prompt ID:** D
**Descriptor:** broken-manager-shortcircuit
**Filename:** `CLAUDE-CODE-PROMPT-error-handling-D-broken-manager-shortcircuit.md`
**Repository:** `crmbuilder`
**Depends on:** Prompts A, B, and C merged.
**Last Updated:** 05-02-26 17:30
**Version:** 1.0

---

## Status

The first live FU-Contribution Configure run plus subsequent investigation revealed a foundational issue that goes beyond error handling: **`EspoAdminClient.put_metadata()` calls a non-existent endpoint method.** EspoCRM's `routes.json` defines exactly one route for `/api/v1/Metadata`:

```json
{ "route": "/Metadata", "method": "get", "params": { "controller": "Metadata" } }
```

GET only. There is no PUT, POST, or PATCH. The 405 Method Not Allowed observed on `Contribution savedViews metadata` is EspoCRM's Slim framework correctly rejecting an unsupported method. This bug has existed since the yaml-v1.1 series introduced these managers (Prompts B/C/G); it never surfaced because no prior live Configure run exercised any of the three affected blocks.

Three managers depend on `put_metadata`:
- `saved_view_manager.py` — writes to `clientDefs.{Entity}.savedViews`
- `duplicate_check_manager.py` — writes to entity duplicate-check metadata
- `workflow_manager.py` — writes to workflow metadata

None of these EspoCRM features actually have a public REST API write path:
- **Saved views** (in CRM Builder's sense — list-view filters in `clientDefs`) require disk-level edits to `custom/Espo/Custom/Resources/metadata/clientDefs/{Entity}.json` plus a rebuild. No public API.
- **Duplicate-check rules** are configured via the `EntityManager` endpoint (different code path; not via metadata writes), but reimplementing requires research and a new manager design.
- **Workflows** in EspoCRM are records (CRUD via `/api/v1/Workflow`) and require the Advanced Pack extension. Reimplementing requires entity-record CRUD plus extension detection.

Per the architectural decision (Option C of the diagnosis), this prompt takes the **near-term unblock path**: short-circuit all three broken managers to recognize their YAML directives but acknowledge that the work cannot be performed via the API, then surface those items in a prominent "MANUAL CONFIGURATION REQUIRED" block at the end of the run. The YAML schema stays intact (these blocks remain valid input — they're now documentation that drives the manual-config block). Future prompts can reimplement against correct backends if and when that work is prioritized.

After Prompt D: a Configure run with `savedViews:`, `duplicateChecks:`, or `workflows:` blocks completes without errors, emits a clear note per item that it requires manual configuration, and ends with a consolidated MANUAL CONFIGURATION REQUIRED block listing all such items. The FU-Contribution run becomes a clean success modulo the relationship 409 issue (Issue 3, separate prompt).

---

## What this prompt accomplishes

1. **Add `NOT_SUPPORTED` status** to three enums in `espo_impl/core/models.py`:
   - `SavedViewStatus.NOT_SUPPORTED = "not_supported"`
   - `DuplicateCheckStatus.NOT_SUPPORTED = "not_supported"`
   - `WorkflowStatus.NOT_SUPPORTED = "not_supported"`

2. **Short-circuit `SavedViewManager.process_saved_views`** in `espo_impl/core/saved_view_manager.py`:
   - Replace the CHECK / `_process_view` / `_write_views` logic with a no-op pass: iterate every saved view in every non-deleted entity, emit one output line per view of the form `[NOT SUPPORTED] {entity}.savedViews[{view.id}] — manual config required`, and return a list of `SavedViewResult(entity=..., view_id=..., status=SavedViewStatus.NOT_SUPPORTED)`.
   - Do NOT delete the existing `_process_view`, `_write_views`, `_extract_existing_views`, `_view_to_dict`, `_views_match` private methods — leave them as dead code with a top-of-class TODO comment explaining they're retained for future REST-API or file-based reimplementation. Rationale: removing them creates a larger diff and makes resurrection harder when someone implements the real solution.
   - Mark the docstring of `process_saved_views` clearly: "EspoCRM has no public REST API for clientDefs metadata writes. This method short-circuits to NOT_SUPPORTED for every YAML-declared saved view; manual configuration is required via the EspoCRM admin UI or file-based metadata edits. See MANUAL-CONFIG.md generated per run."

3. **Short-circuit `DuplicateCheckManager.process_duplicate_checks`** the same way:
   - Iterate every duplicate-check rule, emit `[NOT SUPPORTED] {entity}.duplicateChecks[{rule.id}] — manual config required`, return list of `DuplicateCheckResult(...status=DuplicateCheckStatus.NOT_SUPPORTED)`.
   - Leave private methods in place as dead code with the same TODO rationale.
   - Clear docstring update.

4. **Short-circuit `WorkflowManager.process_workflows`** the same way:
   - Iterate workflows, emit `[NOT SUPPORTED] {entity}.workflows[{workflow.id}] — manual config required`, return `WorkflowResult(...status=WorkflowStatus.NOT_SUPPORTED)`.
   - Leave private methods in place. Clear docstring update.

5. **Update `_run_full` in `run_worker.py`** for these three steps:
   - The `failure_check` callable for `saved_views`, `duplicate_checks`, and `workflows` continues to use only `{ERROR}` as the failure-trigger set. `NOT_SUPPORTED` items do NOT cause step downgrade. Result: a step with all NOT_SUPPORTED items reports `StepStatus.OK`.
   - Conceptual rationale: the manager succeeded at what it can do given platform constraints (recognize directives and report them). The "you must do these manually" surfacing happens via the dedicated MANUAL CONFIGURATION REQUIRED block.

6. **New MANUAL CONFIGURATION REQUIRED block** in `run_worker.py`:
   - After `_emit_step_summary`, walk every `XxxResult` list attached to the report, collect entries where `status == NOT_SUPPORTED`, and emit:
     ```
     ===========================================
     MANUAL CONFIGURATION REQUIRED
     ===========================================
     The following items declared in the YAML cannot be applied via
     EspoCRM's REST API. Configure them manually via the admin UI:

     Saved views:
       Contribution.savedViews[contribution-acknowledgment-pending]
       Contribution.savedViews[contribution-grant-deadlines]

     Duplicate checks:
       (none)

     Workflows:
       (none)
     ===========================================
     ```
   - Entries grouped by feature type. Empty groups display "(none)" or are omitted (pick one — recommend showing all three with "(none)" for absent groups, so the operator always sees the full schema).
   - Block is suppressed entirely if there are zero NOT_SUPPORTED items across all three result types — no point emitting an empty advisory.
   - Block uses `output_line.emit(..., "yellow")` so it's visually distinct from the step summary (white) and doesn't read as an error (red).

7. **`configure_progress.py` UI behavior**:
   - File rows where the only "issue" is NOT_SUPPORTED items remain green ("Completed successfully") — this is not a failure.
   - However, attach a tooltip on such rows: `"Manual configuration required for N item(s) — see run log"`. This signals the operator that the run log has actionable content even though no error occurred.
   - Rows with both NOT_SUPPORTED items AND actual failures stay amber and the tooltip mentions both.

8. **Tests**:
   - `tests/test_saved_views.py`: replace or augment existing happy-path / API-call tests with new tests that assert `process_saved_views` does NOT call `client.put_metadata` or `client.get_client_defs`, and that every result is `SavedViewStatus.NOT_SUPPORTED`. Existing tests that exercised the API-path methods can be removed or marked `@pytest.mark.skip(reason="dead code retained for future reimplementation")`.
   - Same for `tests/test_duplicate_checks.py` and `tests/test_workflows.py`.
   - `tests/test_run_worker.py`: add a test that a YAML containing saved views and workflows produces `StepStatus.OK` for both steps and emits the MANUAL CONFIGURATION REQUIRED block. Verify block content via mock output capture.
   - `tests/test_run_worker.py`: add a test that confirms NOT_SUPPORTED items don't trigger step downgrade in the `failure_check`.
   - `configure_progress` UI tooltip test: a file with 2 NOT_SUPPORTED items but no failures shows green outcome with the manual-config tooltip text.

9. **No changes to YAML schema, no changes to YAML parser, no changes to YAML files in CBM**. The YAML directives remain valid and meaningful — they now drive the MANUAL CONFIGURATION REQUIRED block instead of API calls.

---

## What this prompt does NOT do

- **Does not remove `put_metadata` from `api_client.py`.** It's harmless dead code now (no caller invokes it after this prompt), but removing it creates churn for no functional benefit. A future cleanup prompt can excise it.
- **Does not modify `programs/FU/MANUAL-CONFIG.md` (or any per-domain MANUAL-CONFIG.md in CBM).** Those are hand-curated source-of-truth documents and stay outside this code change. Operators continue to read them. The MANUAL CONFIGURATION REQUIRED block in the run log is a complementary runtime signal, not a replacement.
- **Does not implement file-based or SSH-based metadata writes.** That's Option B from the diagnosis and is a separate, larger workstream.
- **Does not implement Workflow entity CRUD.** Same — separate workstream.
- **Does not implement EntityManager-based duplicate-check rule writes.** Same.
- **Does not gate on EspoCRM version or extension presence** (e.g. detecting Advanced Pack for workflows). All three managers behave identically: short-circuit to NOT_SUPPORTED. Future reimplementations can add detection.
- **Does not change `failure_check` semantics for the other 7 steps.** Only the three affected steps' checks need to ignore NOT_SUPPORTED — but since NOT_SUPPORTED only exists in the three relevant enums, this is automatic.
- **Does not affect entity creation, fields, layouts, or relationships.** Those steps are unchanged.

---

## Constraints and conventions

- **The string value `"not_supported"`** for the new enum values uses snake_case to match the existing convention (`"verification_failed"`, `"skipped_type_conflict"`, etc.).
- **Output line format**: `"[NOT SUPPORTED] {entity}.{block}[{id}] — manual config required"` — uppercase NOT SUPPORTED with single space, em-dash (Unicode `—`, not double-hyphen), exact phrasing for grep/test stability.
- **Output color**: `"yellow"` for the per-item NOT SUPPORTED lines and for the entire MANUAL CONFIGURATION REQUIRED block. Reserved colors: red = error, green = success, gray = skipped, yellow = needs attention but not failure.
- **The MANUAL CONFIGURATION REQUIRED block emits AFTER the STEP SUMMARY**, so the operator reads the run summary first, then the manual-config items as a follow-up advisory.
- **No new dependencies on EspoCRM internals** in this prompt. The short-circuit doesn't even talk to the CRM. This is the right move because we know the API doesn't support what we want — there's no point burning an API round-trip just to confirm.
- **Existing private methods left as dead code**: add `# TODO(error-handling-D): restore when Option B reimplementation lands` to the top of each retained private method. This makes them grep-able when someone returns to do the proper fix.
- **Python 3.11+, type hints, docstrings, pytest** — same conventions as the rest of the codebase.
- **No changes to PRD documents.** This prompt is purely code + tests.

---

## Detailed implementation

### Step 1 — Models

In `espo_impl/core/models.py`:

```python
class SavedViewStatus(Enum):
    """Outcome status for a saved-view operation."""
    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"
    DRIFT = "drift"
    ERROR = "error"
    NOT_SUPPORTED = "not_supported"  # NEW: platform doesn't expose REST write path


class DuplicateCheckStatus(Enum):
    """Outcome status for a duplicate-check rule operation."""
    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"
    DRIFT = "drift"
    ERROR = "error"
    NOT_SUPPORTED = "not_supported"  # NEW


class WorkflowStatus(Enum):
    """Outcome status for a workflow operation."""
    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"
    DRIFT = "drift"
    ERROR = "error"
    NOT_SUPPORTED = "not_supported"  # NEW
```

### Step 2 — Manager short-circuit (template — apply to all three)

For `SavedViewManager.process_saved_views`:

```python
def process_saved_views(
    self, program: ProgramFile
) -> list[SavedViewResult]:
    """Acknowledge saved views from the YAML; do not attempt API writes.

    EspoCRM has no public REST API for clientDefs metadata writes
    (``/api/v1/Metadata`` accepts GET only — there is no PUT, POST, or
    PATCH route). Saved views must be configured manually via the
    EspoCRM admin UI or by editing
    ``custom/Espo/Custom/Resources/metadata/clientDefs/{Entity}.json``
    on disk and rebuilding cache.

    This method iterates every saved view declared in the YAML, emits
    a NOT SUPPORTED line per item, and returns results all marked
    ``SavedViewStatus.NOT_SUPPORTED``. The MANUAL CONFIGURATION
    REQUIRED block at the end of the run aggregates these for
    operator action.

    The previous CHECK/WRITE implementation is retained as private
    methods (see ``_process_view`` etc.) for future reimplementation
    against a working backend. They are not currently called.

    :param program: Parsed and validated program file.
    :returns: List of per-view results, each with status NOT_SUPPORTED.
    """
    results: list[SavedViewResult] = []

    for entity_def in program.entities:
        if entity_def.action == EntityAction.DELETE:
            continue
        if not entity_def.saved_views:
            continue

        for view in entity_def.saved_views:
            self.output_fn(
                f"[NOT SUPPORTED] {entity_def.name}.savedViews"
                f"[{view.id}] — manual config required",
                "yellow",
            )
            results.append(
                SavedViewResult(
                    entity=entity_def.name,
                    view_id=view.id,
                    status=SavedViewStatus.NOT_SUPPORTED,
                )
            )

    return results
```

Apply analogous changes to `DuplicateCheckManager.process_duplicate_checks` and `WorkflowManager.process_workflows`. The result-construction details differ slightly per result class — match each one's existing field signature.

Add `# TODO(error-handling-D): restore when REST-capable reimplementation lands` to the top of every retained private method (`_process_view`, `_write_views`, etc. in each manager).

### Step 3 — `run_worker.py` MANUAL CONFIGURATION REQUIRED block

After `self._emit_step_summary(all_step_results)` and before `report.step_results = all_step_results`:

```python
self._emit_manual_config_block(report)
```

New private method on `RunWorker`:

```python
def _emit_manual_config_block(self, report: RunReport) -> None:
    """Emit a consolidated advisory listing items requiring manual config.

    Walks the saved-view, duplicate-check, and workflow result lists
    on the report and surfaces every entry whose status is
    ``NOT_SUPPORTED`` in a single advisory block. Suppressed entirely
    if no such entries exist.

    :param report: The run report after all steps have executed.
    """
    saved_view_items = [
        f"  {r.entity}.savedViews[{r.view_id}]"
        for r in report.saved_view_results
        if r.status == SavedViewStatus.NOT_SUPPORTED
    ]
    dup_check_items = [
        f"  {r.entity}.duplicateChecks[{r.rule_id}]"
        for r in report.duplicate_check_results
        if r.status == DuplicateCheckStatus.NOT_SUPPORTED
    ]
    workflow_items = [
        f"  {r.entity}.workflows[{r.workflow_id}]"
        for r in report.workflow_results
        if r.status == WorkflowStatus.NOT_SUPPORTED
    ]

    if not (saved_view_items or dup_check_items or workflow_items):
        return

    self.output_line.emit("", "white")
    self.output_line.emit(
        "===========================================", "yellow"
    )
    self.output_line.emit(
        "MANUAL CONFIGURATION REQUIRED", "yellow"
    )
    self.output_line.emit(
        "===========================================", "yellow"
    )
    self.output_line.emit(
        "The following items declared in the YAML cannot be applied",
        "yellow",
    )
    self.output_line.emit(
        "via EspoCRM's REST API. Configure them manually via the",
        "yellow",
    )
    self.output_line.emit(
        "admin UI or by editing metadata files on disk:", "yellow"
    )
    self.output_line.emit("", "yellow")

    self.output_line.emit("Saved views:", "yellow")
    for line in (saved_view_items or ["  (none)"]):
        self.output_line.emit(line, "yellow")
    self.output_line.emit("", "yellow")

    self.output_line.emit("Duplicate checks:", "yellow")
    for line in (dup_check_items or ["  (none)"]):
        self.output_line.emit(line, "yellow")
    self.output_line.emit("", "yellow")

    self.output_line.emit("Workflows:", "yellow")
    for line in (workflow_items or ["  (none)"]):
        self.output_line.emit(line, "yellow")

    self.output_line.emit(
        "===========================================", "yellow"
    )
```

### Step 4 — `configure_progress.py` tooltip enhancement

In `_on_worker_ok`, after the existing failed-steps tooltip logic:

```python
# Collect NOT_SUPPORTED counts for advisory tooltip
not_supported_count = 0
if report:
    not_supported_count += sum(
        1 for r in report.saved_view_results
        if r.status == SavedViewStatus.NOT_SUPPORTED
    )
    not_supported_count += sum(
        1 for r in report.duplicate_check_results
        if r.status == DuplicateCheckStatus.NOT_SUPPORTED
    )
    not_supported_count += sum(
        1 for r in report.workflow_results
        if r.status == WorkflowStatus.NOT_SUPPORTED
    )

if not_supported_count > 0:
    advisory = (
        f"Manual configuration required for {not_supported_count} "
        f"item(s) — see run log"
    )
    if tooltip:
        tooltip = f"{tooltip}\n{advisory}"
    else:
        tooltip = advisory
```

Outcome color logic stays the same — green when no failures (NOT_SUPPORTED is not failure), amber when any step failed.

### Step 5 — Tests

Replace `tests/test_saved_views.py` happy-path API tests with NOT_SUPPORTED tests. Suggested approach:

```python
def test_process_saved_views_returns_not_supported_for_all_views():
    program = _make_program_with_saved_views(...)
    mock_client = Mock(spec=EspoAdminClient)
    output_calls: list[tuple[str, str]] = []

    mgr = SavedViewManager(mock_client, lambda m, c: output_calls.append((m, c)))
    results = mgr.process_saved_views(program)

    # No API calls should have been made
    mock_client.put_metadata.assert_not_called()
    mock_client.get_client_defs.assert_not_called()

    # All results NOT_SUPPORTED
    assert all(r.status == SavedViewStatus.NOT_SUPPORTED for r in results)
    assert len(results) == expected_view_count

    # Output emitted in expected format
    assert any(
        "[NOT SUPPORTED]" in msg and "manual config required" in msg
        for msg, _ in output_calls
    )
    assert all(color == "yellow" for msg, color in output_calls)
```

Same shape for duplicate checks and workflows.

For `tests/test_run_worker.py`:

```python
def test_run_full_emits_manual_config_block_when_not_supported_items_present():
    # YAML with saved views; manager returns NOT_SUPPORTED for each
    # Assert step status OK, run output contains MANUAL CONFIGURATION REQUIRED
    ...

def test_run_full_no_manual_config_block_when_no_not_supported_items():
    # YAML without saved views/dup checks/workflows
    # Assert no MANUAL CONFIGURATION REQUIRED in output
    ...

def test_not_supported_items_do_not_trigger_step_failure():
    # All saved views NOT_SUPPORTED, no errors
    # Assert step_results['saved_views'].status == OK
    ...
```

Mark or remove existing tests that exercised the now-dead API-path methods. Removal is preferred for clarity, but `@pytest.mark.skip(reason=...)` is acceptable for tests that are non-trivial to delete.

### Step 6 — Verification

```bash
pytest tests/ -x -v 2>&1 | tail -80
ruff check espo_impl/core/saved_view_manager.py \
           espo_impl/core/duplicate_check_manager.py \
           espo_impl/core/workflow_manager.py \
           espo_impl/core/models.py \
           espo_impl/workers/run_worker.py \
           tests/test_saved_views.py \
           tests/test_duplicate_checks.py \
           tests/test_workflows.py \
           tests/test_run_worker.py
mypy espo_impl/core/saved_view_manager.py espo_impl/workers/run_worker.py
```

Then manual smoke test on FU-Contribution YAML against any reachable instance (CBM Test):

1. Delete `CContribution` if it exists.
2. Run Configure on `FU-Contribution.yaml`.
3. Confirm:
   - Entity creation succeeds.
   - `=== SAVED VIEWS ===` block emits two `[NOT SUPPORTED]` lines (yellow), no API calls, no errors.
   - `=== FIELD OPERATIONS ===` runs and creates 18 fields successfully.
   - Layouts run and update successfully.
   - Relationships still produce 3 × HTTP 409 errors (that's Issue 3, not in scope here) — the relationships step legitimately FAILS in step summary.
   - STEP SUMMARY shows: Saved views: OK, Fields: OK, Layouts: OK, Relationships: FAILED.
   - MANUAL CONFIGURATION REQUIRED block lists the two saved views, with "(none)" under Duplicate checks and Workflows.
   - File row in configure_progress is amber (because of relationship failure), with tooltip listing both the failed relationships step AND the manual-config advisory.

---

## Acceptance criteria

- [ ] `SavedViewStatus`, `DuplicateCheckStatus`, `WorkflowStatus` each have a `NOT_SUPPORTED = "not_supported"` value.
- [ ] `SavedViewManager.process_saved_views`, `DuplicateCheckManager.process_duplicate_checks`, `WorkflowManager.process_workflows` no longer call `put_metadata` or any API method; they iterate YAML items, emit `[NOT SUPPORTED]` lines (yellow), and return all-NOT_SUPPORTED result lists.
- [ ] Private API-path methods in each of those managers are retained with `TODO(error-handling-D)` comments at the top.
- [ ] `_run_full` failure_check sets for these three steps continue to be `{ERROR}` only — NOT_SUPPORTED does NOT trigger step downgrade.
- [ ] New `_emit_manual_config_block` method in `RunWorker` emits the consolidated yellow advisory block when any NOT_SUPPORTED items exist, and emits nothing when there are none.
- [ ] `configure_progress.py` `_on_worker_ok` adds a manual-config advisory to the tooltip when NOT_SUPPORTED items are present (regardless of overall outcome color).
- [ ] All listed tests exist and pass.
- [ ] Existing tests that exercised the dead API-path methods are removed or skip-marked.
- [ ] Manual smoke test on FU-Contribution: saved views show NOT SUPPORTED, fields/layouts succeed, MANUAL CONFIGURATION REQUIRED block appears, run completes with only relationship step failed (Issue 3 territory).
- [ ] `ruff check` clean for all modified files.
- [ ] `mypy` clean for the two main modified files where mypy is configured.

---

## Commit message

```
fix(managers): short-circuit broken metadata-write managers to NOT_SUPPORTED

Three managers — SavedView, DuplicateCheck, Workflow — call
EspoAdminClient.put_metadata(), which PUTs to /api/v1/Metadata.
EspoCRM defines exactly one route for that path: GET only. There is
no PUT, POST, or PATCH. The managers have been broken since the
yaml-v1.1 series introduced them; the bug surfaced on the first live
Configure run that exercised the saved-views path (FU-Contribution).

The underlying EspoCRM features for these three managers don't have
public REST API write paths in their current form:
- Saved views (clientDefs): require disk-level edits + rebuild
- Duplicate-check rules: configured via EntityManager, not metadata
- Workflows: are entity records (Advanced Pack), not metadata

Per architectural decision (diagnosis Option C), this commit takes
the unblock path: short-circuit all three managers to recognize
their YAML directives but emit a NOT SUPPORTED notice and a new
MANUAL CONFIGURATION REQUIRED advisory block at the end of the run.
The YAML schema stays intact so the directives continue to drive the
manual-config advisory; future prompts can reimplement against the
correct backends if and when prioritized.

Adds NOT_SUPPORTED status to SavedViewStatus, DuplicateCheckStatus,
and WorkflowStatus. RunWorker emits a yellow consolidated advisory
block grouping NOT_SUPPORTED items by feature type. configure_progress
adds a manual-config tooltip on file rows with NOT_SUPPORTED items.
NOT_SUPPORTED does NOT count as step failure — these are platform
constraints, not deployment errors.

Existing private API-path methods in the three managers are retained
as dead code with TODO(error-handling-D) markers for resurrection
when proper REST-API or file-based reimplementation lands.

This is Prompt D in the error-handling series. Unblocks the
FU-Contribution Configure run for everything except the still-open
relationship 409 issue (Issue 3, separate prompt).
```

# Claude Code Prompt — Error Handling Series, Prompt E

**Series:** error-handling (defensive error handling across the run pipeline)
**Prompt ID:** E
**Descriptor:** validation-wiring-hard-reject
**Filename:** `CLAUDE-CODE-PROMPT-error-handling-E-validation-wiring-hard-reject.md`
**Repository:** `crmbuilder`
**Depends on:** Prompts A, B, C, D merged. The CBM-side YAML fix (`FU-Contribution.yaml` v1.0.1, commit `b7d490a` in the ClevelandBusinessMentoring repo) must also be in place — without it, this prompt's hard-reject behavior would block FU-Contribution deployment until the YAML is fixed.
**Last Updated:** 05-02-26 18:00
**Version:** 1.0

---

## Status

Investigation of the FU-Contribution relationship 409 errors revealed that `ConfigLoader.validate_program()` exists (in `espo_impl/core/config_loader.py`) and contains substantial validation logic — including a check at line 638 that rejects any field whose `type` is not in `SUPPORTED_FIELD_TYPES` — but **the validator is never called from the Configure flow.** `configure_progress.py` calls `loader.load_program(Path(f.path))` only; the returned `ProgramFile` is then handed to `RunWorker` without any validation pass.

Consequence: FU-Contribution.yaml's `type: link` fields (which the validator would have flagged as "unsupported field type 'link'" — `link` is not in `SUPPORTED_FIELD_TYPES`) parsed and ran through to the field-creation API, where EspoCRM accepted the POST and created stub link fields without proper foreign-entity wiring, which subsequently caused the `EntityManager/action/createLink` calls in the relationships step to return HTTP 409 Conflict.

The CBM-side fix (commit `b7d490a` on `ClevelandBusinessMentoring/main`) removes the duplicate `type: link` field declarations from FU-Contribution.yaml. That unblocks the immediate deployment. This prompt prevents the same pattern from recurring by **wiring `validate_program()` into the Configure flow with hard-reject semantics**: validation errors block the file from running, the file row goes red with a "Validation failed" outcome, and the run log shows each error. Other files in the same batch are unaffected.

After Prompt E: every file the operator selects in the Deployment tab is validated before any API call is made. A YAML with `type: link` fields, missing required properties, invalid enum option references, malformed conditions, or any other validator-recognised problem is rejected before deployment begins. The validator was designed for this; it just hasn't been used.

---

## What this prompt accomplishes

1. **Wire `validate_program()` into `configure_progress.py`'s `_load_and_start`** in `automation/ui/deployment/configure_progress.py`:
   - After `loader.load_program(...)` succeeds for a file, call `loader.validate_program(program)`.
   - If the returned errors list is non-empty: emit each error to the run log as red `[VALIDATION ERROR]` lines, mark the file's outcome as `Validation failed` (red), record `(outcome="failed", timestamp=...)` in `self._file_results`, and **do not** append to `self._pending`. The file is excluded from the run.
   - If the errors list is empty: append to `self._pending` as today.
   - At the end of the file-loading loop, if every file failed validation, emit `"No valid YAML files to process."` and finish, same as the existing empty-pending path. If at least one file passed, proceed to `_run_next()` as today.

2. **Improve the error message for `type: link`** in `espo_impl/core/config_loader.py` `_validate_field`:
   - Currently emits: `f"{prefix}: unsupported field type '{field_def.type}'"`.
   - Change to: detect `field_def.type == "link"` specifically and emit: `f"{prefix}: 'link' is not a valid field type — link relationships must be declared in the top-level 'relationships:' block, not in the entity 'fields:' block. See the YAML schema spec for examples."`
   - For all other unsupported types, keep the existing generic message.
   - One-line addition; protects future operators from staring at "unsupported field type 'link'" wondering where else it should go.

3. **`configure_progress.py` UI behavior**:
   - Files that fail validation render in the file-status panel with the same red "Failed" treatment as a runtime failure, but with outcome text `"Validation failed (N error(s))"` and a tooltip listing the first 5 errors (truncated with `"... (M more)"` if more exist).
   - The progress bar accounts for these files: their portion of `_total_ops` is added to `_completed_ops` immediately so the bar advances correctly. (Today, `_total_ops` is incremented only for `_pending` entries via `_count_operations(program)` — for failed-validation files, no ops are counted, which keeps progress math accurate. Verify this is still consistent after the change; adjust if needed.)

4. **Surface validation errors prominently in the run log** before any per-file processing begins:
   - Emit a one-line header per failed file: `=== {filename}: VALIDATION FAILED ({N} error(s)) ===` in red.
   - Emit each error indented as `  - {error message}` in red.
   - Add a blank line after the last error of each file.
   - The header and errors precede the existing `=== Running: {filename} ===` blocks for the files that DID pass validation.

5. **Tests**:
   - **`tests/test_config_loader.py`** (extend or create): test that `_validate_field` emits the new specific message for `type: link` and the generic message for other unsupported types.
   - **`tests/test_configure_progress.py`** (extend or create — UI tests are typically lighter, follow the existing convention): test that:
     - A file with validation errors does NOT enter `_pending`.
     - `_file_results` records `("failed", ...)` for that file.
     - The run log contains `=== {filename}: VALIDATION FAILED` and the individual error lines.
     - A batch where one file is valid and one is invalid: only the valid one runs.
     - A batch where all files are invalid: emits "No valid YAML files to process." and does not call `_run_next`.
   - **`tests/test_run_worker.py`**: no changes needed — the worker is unaffected. (Validation happens before the worker is constructed.)

6. **No changes** to:
   - `RunWorker` or any manager.
   - `validate_program()`'s logic itself — only its caller and the one error-message tweak.
   - `load_program()`.
   - The `_run_full` pipeline.
   - YAML schema or any YAML files in the CBM repo (the CBM-side YAML fix for FU-Contribution is a separate commit).

---

## What this prompt does NOT do

- **Does not change `validate_program()`'s logic.** This prompt assumes the existing validator is correct as-is. If gaps are found later (e.g., it doesn't catch some other invalid pattern), those fixes are separate prompts.
- **Does not add a "skip validation" override.** Hard reject means hard reject. If an operator needs to bypass for an emergency, they edit the YAML to fix the validation errors. (B3 in the diagnosis options was explicitly declined.)
- **Does not validate at YAML upload / file-add time.** Validation runs at Configure-time only. Adding pre-flight validation to the program panel is a future UX improvement, not in scope here.
- **Does not retroactively validate any existing YAML in the CBM repo.** If other YAMLs have validation errors that have been latent until now, they will surface the next time someone runs Configure on them — and they'll need to be fixed individually as encountered. (Per CLAUDE.md, MR is the only domain with prior live work, and MR-Dues.yaml is known-clean per the manual review during this issue's diagnosis.)
- **Does not modify how individual validation errors are formatted by `_validate_*` methods other than the one `_validate_field` change for `type: link`.** All other error messages stay as-is.
- **Does not change the operations counter logic in `_count_operations`** or the progress bar math beyond the small adjustment described in section 3.

---

## Constraints and conventions

- **`validate_program()` returns `list[str]`.** An empty list means valid. Don't reinterpret as bool or change the signature.
- **Hard reject is per-file, not per-batch.** Each file is validated independently; one file's failures do not affect other files in the batch.
- **Error message for `type: link`** must include the phrase `"declared in the top-level 'relationships:' block"` exactly — this is what tests assert against and what operators will grep for in logs.
- **Output color**: validation errors emit in red, matching the convention for runtime errors. The `[VALIDATION ERROR]` prefix or the `=== ... VALIDATION FAILED` header is what distinguishes them from runtime errors in the log.
- **Tooltip truncation**: first 5 errors, then `"... (N more)"`. If there are exactly 5 errors, no "more" line. If 6+, the line reads `"... (1 more)"` for 6, `"... (2 more)"` for 7, etc.
- **Don't introduce a new exception type.** Validation errors are domain-level data, not Python exceptions. The existing pattern (returning a list of strings) is correct.
- **Python 3.11+, type hints, docstrings, pytest** — same conventions as the rest of the codebase.
- **No changes to PRD documents.** This prompt is purely code + tests.

---

## Detailed implementation

### Step 1 — `_validate_field` improvement

In `espo_impl/core/config_loader.py`, around line 638:

```python
if not field_def.type:
    errors.append(f"{prefix}: missing required property 'type'")
elif field_def.type == "link":
    errors.append(
        f"{prefix}: 'link' is not a valid field type — link "
        f"relationships must be declared in the top-level "
        f"'relationships:' block, not in the entity 'fields:' block. "
        f"See the YAML schema spec for examples."
    )
elif field_def.type not in SUPPORTED_FIELD_TYPES:
    errors.append(
        f"{prefix}: unsupported field type '{field_def.type}'"
    )
```

### Step 2 — Wire validation into `_load_and_start`

In `automation/ui/deployment/configure_progress.py`, replace the file-loading loop (around lines 203–215) with:

```python
loader = ConfigLoader()
validation_failures: list[tuple[YamlFileInfo, list[str]]] = []

for f in self._files:
    try:
        program = loader.load_program(Path(f.path))
    except Exception as exc:
        self._append_log(f"Failed to load {f.name}: {exc}", "error")
        self._record_validation_failure(f, [f"Parse error: {exc}"])
        continue

    errors = loader.validate_program(program)
    if errors:
        validation_failures.append((f, errors))
        continue

    self._pending.append((f, program))
    self._total_ops += _count_operations(program)

# Emit validation failure blocks before any per-file processing
for f, errors in validation_failures:
    self._append_log("", "white")
    self._append_log(
        f"=== {f.name}: VALIDATION FAILED ({len(errors)} error(s)) ===",
        "error",
    )
    for err in errors:
        self._append_log(f"  - {err}", "error")
    self._record_validation_failure(f, errors)

if not self._pending:
    if validation_failures:
        self._append_log(
            "No valid YAML files to process — all files failed validation.",
            "warning",
        )
    else:
        self._append_log("No valid YAML files to process.", "warning")
    self._finish()
    return

self._run_next()
```

Add a new private helper:

```python
def _record_validation_failure(
    self, file_info: YamlFileInfo, errors: list[str]
) -> None:
    """Record a validation-failed file in _file_results with a tooltip.

    :param file_info: The YAML file that failed validation.
    :param errors: List of validation error messages from validate_program.
    """
    timestamp = datetime.now(UTC).isoformat()
    outcome = f"Validation failed ({len(errors)} error(s))"
    self._file_results[file_info.path] = (outcome, timestamp)

    # Build tooltip: first 5 errors, then "... (N more)" if applicable
    shown = errors[:5]
    tooltip_lines = list(shown)
    if len(errors) > 5:
        tooltip_lines.append(f"... ({len(errors) - 5} more)")
    self.file_tooltips[file_info.path] = "\n".join(tooltip_lines)
```

(Adjust attribute names — `file_tooltips`, `_file_results`, `_append_log` — to match the actual attributes from Prompt B's implementation. They're referenced here against the structure described in the merged code.)

### Step 3 — Apply red treatment in the file-status panel

In whichever method renders the per-file outcome row (typically `_apply_run_results` or an analogous handler — find it by searching for `self._file_results` reads or for the existing amber/green/red branching from Prompt B), add a branch for `outcome.startswith("Validation failed")`:
- Color: red (`#D32F2F` or whatever the existing red constant is).
- Tooltip: from `self.file_tooltips[path]`.

### Step 4 — Tests

`tests/test_config_loader.py`:

```python
def test_validate_field_link_type_emits_specific_message():
    loader = ConfigLoader()
    program = ProgramFile(
        version="1.0",
        description="test",
        entities=[
            EntityDefinition(
                name="Foo",
                fields=[FieldDefinition(name="bar", type="link", label="Bar")],
                action=EntityAction.CREATE,
            )
        ],
    )
    errors = loader.validate_program(program)
    assert any("link" in e and "relationships:" in e for e in errors)


def test_validate_field_other_unsupported_type_emits_generic_message():
    loader = ConfigLoader()
    program = ProgramFile(
        version="1.0",
        description="test",
        entities=[
            EntityDefinition(
                name="Foo",
                fields=[FieldDefinition(name="bar", type="frobnicate", label="Bar")],
                action=EntityAction.CREATE,
            )
        ],
    )
    errors = loader.validate_program(program)
    assert any("unsupported field type 'frobnicate'" in e for e in errors)
```

`tests/test_configure_progress.py` (or wherever existing UI tests live):

```python
def test_validation_failure_excludes_file_from_pending():
    # Given a YAML file that has a type: link field
    # When _load_and_start runs
    # Then the file is NOT in _pending and IS in _file_results with "Validation failed"
    ...

def test_validation_failure_emits_log_block():
    # Given a YAML with validation errors
    # When _load_and_start runs
    # Then the log contains "=== {filename}: VALIDATION FAILED" and each error indented
    ...

def test_mixed_batch_only_valid_files_run():
    # Given two files, one valid, one invalid
    # When _load_and_start runs
    # Then _pending has exactly 1 entry (the valid file)
    # And the invalid file is in _file_results
    ...

def test_all_invalid_batch_finishes_without_running():
    # Given all files invalid
    # When _load_and_start runs
    # Then _pending is empty, "No valid YAML files" is logged, _run_next is NOT called
    ...

def test_validation_tooltip_truncation():
    # Given a file with 8 validation errors
    # When _load_and_start runs
    # Then the file's tooltip contains first 5 errors plus "... (3 more)"
    ...
```

### Step 5 — Verification

```bash
pytest tests/ -x -v 2>&1 | tail -80
ruff check espo_impl/core/config_loader.py \
           automation/ui/deployment/configure_progress.py \
           tests/test_config_loader.py \
           tests/test_configure_progress.py
mypy espo_impl/core/config_loader.py automation/ui/deployment/configure_progress.py
```

All existing tests pass. The 10 pre-existing failures noted in earlier prompt verifications remain pre-existing and unrelated.

Manual smoke test:

1. With FU-Contribution.yaml at v1.0.1 (already pushed), run Configure on it. Expect: passes validation, runs through all steps, relationships now succeed (no 409s), STEP SUMMARY shows all OK or SKIPPED, MANUAL CONFIGURATION REQUIRED block lists the two saved views (NOT_SUPPORTED).

2. Temporarily revert the YAML to its v1.0.0 form (or hand-edit a copy to add `type: link` field declarations) and run Configure on the reverted version. Expect: validation rejects the file before any API call. Run log contains `=== FU-Contribution.yaml: VALIDATION FAILED (3 error(s)) ===` with three lines each containing the phrase about declaring link relationships in the relationships block. File row red with "Validation failed (3 error(s))" outcome and a tooltip showing the three errors. No fields, no relationships, no API contact for that file.

3. Run Configure on a known-good YAML (any of the MR domain files) — expect identical behavior to before this change.

---

## Acceptance criteria

- [ ] `_validate_field` in `config_loader.py` emits a specific message for `type: link` containing the phrase `"declared in the top-level 'relationships:' block"`. Other unsupported types continue to emit the generic message.
- [ ] `configure_progress.py`'s `_load_and_start` calls `loader.validate_program(program)` after `load_program` succeeds. Files with validation errors do not enter `_pending`, are recorded in `_file_results` with outcome `"Validation failed (N error(s))"`, and have a tooltip listing up to 5 errors with "... (M more)" suffix when applicable.
- [ ] The run log shows a `=== {filename}: VALIDATION FAILED ({N} error(s)) ===` header in red for each failed file, followed by one indented red line per error.
- [ ] If all files in a batch fail validation, `_run_next` is NOT called and `"No valid YAML files to process — all files failed validation."` is logged.
- [ ] If only some files in a batch fail validation, the remaining files run as before. The progress bar math accounts correctly for the failed files.
- [ ] All listed tests exist and pass.
- [ ] All existing tests still pass.
- [ ] `ruff check` and `mypy` clean for modified files.
- [ ] Manual smoke test: a YAML with `type: link` fields is rejected with the expected message; a clean YAML runs as before.

---

## Commit message

```
fix(configure): hard-reject invalid YAML at deployment time

ConfigLoader.validate_program() has been dead code: configure_progress.py
called load_program() but never validate_program(). The validator
contains substantive checks — including rejection of unsupported field
types like 'link' — that have never run against real deploys. The
FU-Contribution Configure run hit this gap: 'type: link' fields were
accepted, EspoCRM created stub links without proper foreign-entity
wiring, and subsequent createLink calls returned HTTP 409.

This commit wires validate_program() into the Configure flow with
hard-reject semantics. Each YAML file is validated after parsing; on
any error, the file is excluded from _pending, the run log shows a
red VALIDATION FAILED block listing each error, and the file row
renders red with a 'Validation failed (N error(s))' outcome plus
tooltip showing the first 5 errors. Other files in the batch run
normally.

Also improves the _validate_field error message for 'type: link'
specifically: instead of the generic 'unsupported field type', the
operator now sees 'link is not a valid field type — link relationships
must be declared in the top-level relationships: block, not in the
entity fields: block.'

This is Prompt E in the error-handling series. Together with the
companion CBM-side YAML fix (FU-Contribution.yaml v1.0.1, commit
b7d490a in ClevelandBusinessMentoring), it both unblocks the
immediate FU-Contribution deployment AND prevents the same pattern
from recurring.
```

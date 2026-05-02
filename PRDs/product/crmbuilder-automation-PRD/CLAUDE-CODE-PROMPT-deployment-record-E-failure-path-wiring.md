# Claude Code Prompt — Deployment Record Series, Prompt E

**Series:** deployment-record (productize the Deployment Record artifact)
**Prompt ID:** E
**Descriptor:** failure-path-wiring
**Filename:** `CLAUDE-CODE-PROMPT-deployment-record-E-failure-path-wiring.md`
**Repository:** `crmbuilder`
**Depends on:** Prompts B and C merged (this prompt connects code introduced by both)
**Last Updated:** 05-02-26 13:30
**Version:** 1.0

---

## Status

Small follow-up prompt closing a gap left by Prompt C's execution. Prompts B and C were authored to interlock: Prompt B's Setup Wizard surfaces a "Generate Deployment Record manually" button when automatic generation fails during a successful deploy, and the button is supposed to call `launch_regeneration_dialog` from Prompt C. When Prompt C ran, however, Prompt B was not yet visible to the executing session as merged, and the cross-call was deferred — leaving Prompt B's `_on_generate_record_manually` handler as a temporary stub that displays a "not yet wired up" message.

This prompt completes the connection. It is intentionally narrow: one source file, two changes, one test extension.

After Prompt E: when automatic Record generation fails during a successful deploy, the user clicks the "Generate Deployment Record manually" button in the wizard's Result page and sees the regeneration dialog — the same one available from the Deployment tab.

---

## What this prompt accomplishes

1. Replace the stub `_on_generate_record_manually` handler in `automation/ui/deployment/deploy_wizard/wizard_dialog.py` with a real call to `launch_regeneration_dialog`.
2. Add the necessary import.
3. Add a test case to `tests/test_deploy_worker.py` (or a more appropriate existing test module — verify by reading the file's docstring) that asserts the wizard's failure-path button now invokes `launch_regeneration_dialog` rather than the placeholder QMessageBox.

---

## What this prompt does NOT do

- **No new functionality.** The dialog launched by `launch_regeneration_dialog` is unchanged. The wizard pages introduced by Prompt B are unchanged. The deploy worker is unchanged.
- **No signature changes to `launch_regeneration_dialog`.** Whatever C decided that signature should be, this prompt accepts and uses it as-is. If the existing wizard state does not already carry every argument the function requires, retrieve missing values from the per-client database via the wizard's existing `self._conn` connection rather than changing the function's signature.
- **No changes to the Deployment tab's "Generate Deployment Record" button** in `deploy_entry.py`. That button is already wired correctly.

---

## Constraints and conventions

- **Resolve every value from existing wizard state, the database, or constants** — do not require new constructor arguments to the wizard dialog. The wizard already has `self._conn` (sqlite3 connection), `self._instance_id` (set during deploy), and access to other state. If a value `launch_regeneration_dialog` needs is not directly available on `self`, derive it via a query against `self._conn` or read it from the relevant row.
- **Read the actual `launch_regeneration_dialog` signature in `automation/ui/deployment/regenerate_record_dialog.py` before writing the call.** Do not assume parameter names. Match the signature exactly.
- **Read the existing wizard handler before replacing it.** The current stub at `_on_generate_record_manually` documents itself as a Prompt-C placeholder; replace it cleanly with a docstring explaining the new behavior.
- **Defensive guard for missing prerequisites.** If `self._instance_id is None` (Record-generation failed before the Instance row was created — uncommon but possible), or any other required-state precondition is unmet, surface a clear `QMessageBox.warning` explaining the situation and directing the user to the Deployment tab instead. Do not crash.
- **Python 3.11+ syntax, type hints, docstrings, pytest.** Same conventions as the rest of the codebase.
- **No formatting changes outside the immediate edit area.** This is a surgical fix, not a refactor.

---

## Detailed implementation

### 1. Read the call signature first

Before writing any code, read these two files to verify exact names:

- `automation/ui/deployment/regenerate_record_dialog.py` — find the `launch_regeneration_dialog` function definition. Note its parameters (names, types, required vs. optional).
- `automation/ui/deployment/deploy_wizard/wizard_dialog.py` — find the existing `_on_generate_record_manually` method (currently stubbed) and the wizard's `self.*` attributes that hold deploy-related state (search for `self._instance_id`, `self._conn`, and any other state attributes that hold instance / project-folder / deploy-config information).

The values `launch_regeneration_dialog` requires that are present on `self` are direct passthroughs. Values that aren't on `self` must be looked up:

- **InstanceDeployConfig:** load via `automation.core.deployment.deploy_config_repo.load_deploy_config(self._conn, self._instance_id)`. The function already exists.
- **Instance row:** if needed beyond `instance_id`, load with a direct SQL query against `self._conn`: `SELECT * FROM Instance WHERE id = ?`.
- **Project folder:** the per-client SQLite database is one project folder per database, so resolve the folder from `self._conn`'s file path via `Path(self._conn.execute("PRAGMA database_list").fetchone()[2]).parent.parent` (the `.crmbuilder/` directory's parent is the project folder). If `deploy_entry.py`'s code reads project folder differently, match its pattern instead — consistency over speculation.

### 2. Add the import

Place `from automation.ui.deployment.regenerate_record_dialog import launch_regeneration_dialog` in the existing import block of `wizard_dialog.py`. Place it logically (near other `automation.ui.deployment.*` imports) and in a position that matches the file's existing import ordering convention.

### 3. Replace the stub handler

Replace the existing `_on_generate_record_manually` method body. The new method:

- Has a docstring explaining what it does (one paragraph).
- Validates prerequisites (`self._instance_id is not None`, project folder resolvable, deploy config loadable). On failure, shows a `QMessageBox.warning` with a clear message and returns without crashing.
- Calls `launch_regeneration_dialog` with `parent=self` plus whatever other arguments the function's actual signature requires.
- Does not return a value.

The replacement removes the existing `QMessageBox.information` placeholder entirely.

### 4. Test

Add or extend a test in `tests/test_deploy_worker.py` (or wherever wizard-handler tests live — verify by checking which existing tests touch `wizard_dialog.py`):

- `test_on_generate_record_manually_launches_regeneration_dialog` — patches `launch_regeneration_dialog` to a `MagicMock`. Constructs a wizard dialog instance with `_instance_id` set and `_conn` connected to an in-memory database that has an `Instance` row and an `InstanceDeployConfig` row. Calls `_on_generate_record_manually()`. Asserts the patched function was called exactly once and that `parent=` was the wizard instance.
- `test_on_generate_record_manually_warns_when_no_instance_id` — same setup but `_instance_id = None`. Asserts a `QMessageBox.warning` was shown (use `monkeypatch` on `QMessageBox.warning`) and `launch_regeneration_dialog` was NOT called.

If integration-style wizard testing is too heavy, the alternative is to test `_on_generate_record_manually` as a unit by constructing a partial fake (a `SimpleNamespace` or a tiny stub class with only the attributes the method reads). Either approach is acceptable; use whichever produces more reliable tests.

---

## Acceptance criteria

- The two existing failing-path test scenarios in `tests/test_regenerate_record_dialog.py` and `tests/test_regenerate_record_worker.py` (Prompt C's tests) continue to pass.
- The one-or-two new tests added in this prompt pass.
- Manual confirmation: from the wizard, when Record generation fails (which can be simulated by an inspector that always raises in tests, or harder-to-simulate without a deploy in production), the failure-path button invokes the regeneration dialog, not the placeholder QMessageBox.
- `uv run ruff check` passes on `automation/ui/deployment/deploy_wizard/wizard_dialog.py` and any test file touched.
- The grep `grep -rn "Manual regeneration is not yet wired up" automation/` returns zero matches (the placeholder string is gone).
- The grep `grep -rn "launch_regeneration_dialog" automation/ui/deployment/deploy_wizard/` returns at least one match (the new call).

---

## Notes for the implementer

- This is a small fix in a series whose larger prompts have already landed. Do not expand scope. If you find yourself wanting to refactor the result page, the regeneration dialog, or the deploy worker, stop — those changes belong in a separate prompt.
- If `launch_regeneration_dialog`'s signature requires arguments that genuinely are not derivable from existing wizard state plus the database, the correct response is **NOT** to add new constructor arguments to the wizard dialog (that broadens the change set unacceptably). The correct response is to add the necessary lookup helper inside the wizard module and document why. If even that is not possible without architectural changes, stop and surface the question to the user via a clear comment in the prompt's output.
- The "warning when no instance_id" case is intentionally non-fatal. The user has already seen a successful deploy result page; failing now would be confusing. A warning that points them to the Deployment tab is the correct UX.

# Claude Code Prompt — Deployment Record Series, Prompt C

**Series:** deployment-record (productize the Deployment Record artifact)
**Prompt ID:** C
**Descriptor:** manual-regeneration
**Filename:** `CLAUDE-CODE-PROMPT-deployment-record-C-manual-regeneration.md`
**Repository:** `crmbuilder`
**Depends on:** Prompts A and B merged
**Last Updated:** 05-02-26 06:30
**Version:** 1.0

---

## Status

Third and final prompt in the deployment-record series. Adds a manual "Generate Deployment Record" action to the Deployment tab so that:

- An existing instance with a working `InstanceDeployConfig` can have its Record regenerated on demand (e.g. when versions change after an upgrade, when the Proton Pass entry naming changes, when a migration adds new fields).
- An instance whose original deploy predated the auto-generation in Prompt B can have its Record produced for the first time.
- An instance whose Record-generation failed during deploy (the warning path from Prompt B) can be regenerated cleanly.

This prompt does not introduce new generator logic. It exposes the Prompt A function via a UI affordance, with a small dialog that collects (or re-collects) the administrator-supplied values that aren't auto-detectable.

After Prompt C: every instance the application manages can produce or refresh its Deployment Record on demand without re-running the deploy.

---

## What this prompt accomplishes

1. **"Generate Deployment Record" action** on the Deployment tab's instance picker. Disabled when the active instance has no `InstanceDeployConfig` row (cloud-hosted and BYO scenarios); enabled otherwise.
2. **Regeneration dialog** that opens on action invocation. Pre-fills its fields from the active `InstanceDeployConfig` row's persisted administrator-input columns (`domain_registrar`, `dns_provider`, `droplet_id`, `backups_enabled` — added by Prompt B's migration `_client_v10`). The Proton Pass entry-name fields are not persisted; they pre-fill from the templated defaults established in Prompt B and the administrator confirms or edits them.
3. **Live-system inspection** when the dialog is confirmed. Opens a fresh SSH connection using the persisted `InstanceDeployConfig` (host, port, username, credential), runs `inspect_server_for_record_values`, and generates the `.docx` to the same output path as Prompt B.
4. **Versioning awareness.** If a Record file already exists at the target path, the dialog shows the existing file's modification time and offers two paths: overwrite, or write to a versioned filename (`{code}-Instance-Deployment-Record-{YYYY-MM-DD-HHMMSS}.docx`). Default is overwrite for simplicity.
5. **Programmatic entry point** so the Prompt B Result page's "Generate manually" button can launch the same dialog without going through the Deployment tab.
6. **Tests** verifying: action enable / disable logic; dialog field defaults; SSH-connection-failure surfacing as an error message rather than a crash; successful regeneration produces a file at the expected path.

---

## What this prompt does NOT do

- **No retroactive automatic backfill** — the application does not scan all instances and generate Records for the ones that lack them. Each instance is regenerated only when the administrator triggers it.
- **No batch regeneration** — one instance at a time. A future enhancement could add "Regenerate Records for all instances in this client" but that's outside the v1.0 scope.
- **No comparison of old-vs-new Record content** — overwrite is unconditional. Git is the diff tool of record. (Prompt C does not commit anything; it just writes the file. Commit handling is administrator-driven.)
- **No CBM-Test-Instance backfill commit** — running the regeneration against the live CBM Test Instance produces a `.docx` that overwrites the existing hand-produced one. Whether to actually do that backfill, and whether to retire the hand-produced JS generator, is a discussion outside the scope of this prompt and will be a separate decision after Prompt C lands.

---

## Constraints and conventions

- **Reuse Prompt A's `inspect_server_for_record_values`.** Do not duplicate inspection logic.
- **Reuse the `AdministratorInputs` dataclass** introduced in Prompt A for dialog → generator handoff.
- **Match the existing Deployment-tab UI patterns.** The action lives alongside Upgrade and Recovery on the Deploy entry's button row; the dialog mirrors `recovery_dialog.py`'s structure for size, layout, and confirmation flow.
- **SSH credentials handling** — pull SSH credentials from the keyring via the existing `secrets` module; never read raw secrets into UI state. Use the same patterns as `recovery_dialog.py` and `upgrade_dialog.py`.
- **Threaded execution** — the SSH-and-generate step runs in a `QThread`, mirroring `RegenerateRecordWorker` (new) on the pattern of `UpgradeWorker` and `CredentialResetWorker`.
- **Python 3.11+, type hints, docstrings, pytest** — same conventions as the rest of the codebase.

---

## Detailed implementation

### 1. New module `automation/ui/deployment/regenerate_record_dialog.py`

A modal dialog that launches the regeneration. Layout, top to bottom:

- Header: "Regenerate Deployment Record" with a one-line subhead identifying the instance.
- Form section: the same fields as Prompt B's Documentation Inputs page (registrar, DNS provider, Droplet ID, backups enabled, three Proton Pass entry names). Pre-filled from the persisted `InstanceDeployConfig` columns and the templated Proton Pass entry defaults.
- Output-file section: shows the target file path. If a file already exists at that path, shows its modification time. Two radio buttons: Overwrite (default) / Write versioned copy.
- Progress section: a log area that streams the SSH inspection and generation steps (mirrors the wizard's progress page).
- Footer: Cancel and Generate buttons.

The dialog has two modes:
- "Setup mode" (form visible, log hidden, buttons = Cancel / Generate)
- "Running mode" (form hidden, log visible, buttons = Cancel only; Cancel attempts to abort the worker)
- "Done mode" (form hidden, log visible, buttons = Close / Reveal in file manager)

Transitions: Setup → Running on Generate click; Running → Done on worker finish (success or failure).

### 2. New worker `automation/ui/deployment/regenerate_record_worker.py`

```python
class RegenerateRecordWorker(QThread):
    """Background worker for manual Deployment Record regeneration.

    :param instance: The Instance row.
    :param deploy_config: The InstanceDeployConfig row (with persisted
        administrator-input columns from Prompt B).
    :param administrator_inputs: Updated administrator inputs from the
        dialog (may differ from the persisted values if the
        administrator edited them).
    :param output_path: Where to write the .docx.
    :param parent: Parent QObject.
    """

    log_line = Signal(str, str)
    completed = Signal(str)        # absolute path of generated file
    failed = Signal(str)           # error message

    def __init__(
        self,
        instance: Instance,
        deploy_config: InstanceDeployConfig,
        administrator_inputs: AdministratorInputs,
        output_path: Path,
        parent=None,
    ) -> None:
        ...

    def run(self) -> None:
        try:
            self._log("Connecting via SSH...")
            ssh = self._open_ssh()
            try:
                self._log("Inspecting server...")
                values = inspect_server_for_record_values(
                    ssh, self._instance, self._deploy_config,
                    self._administrator_inputs,
                )
                self._log("Generating Deployment Record...")
                generate_deployment_record(values, self._output_path)
                self._log("Done.")
                self.completed.emit(str(self._output_path))
            finally:
                ssh.close()
        except Exception as exc:
            self.failed.emit(str(exc))
```

`_open_ssh` builds a `SelfHostedConfig` from the `InstanceDeployConfig` row plus the keyring-resolved credential and calls the existing `connect_ssh` helper.

### 3. Deployment tab wiring

`automation/ui/deployment/deploy_entry.py` (or wherever the Deploy entry's button row lives) gains a "Generate Deployment Record" button alongside Upgrade and Recovery. Enable / disable matches Upgrade and Recovery: enabled when the active instance is self-hosted with a populated `InstanceDeployConfig`; disabled otherwise with an explanatory tooltip.

On click: instantiate `RegenerateRecordDialog` with the active instance and its config, show it modal, handle its result (none — the dialog manages its own lifecycle).

### 4. Programmatic launch

A module-level function `launch_regeneration_dialog(parent, instance, deploy_config) -> None` that the Prompt B Result page's "Generate manually" button can call. The function builds the dialog with the same arguments and `exec()`s it.

### 5. Output path and versioning

```python
def _resolve_output_path(
    project_folder: Path, instance_code: str, *, versioned: bool,
) -> Path:
    base_dir = project_folder / "PRDs" / "deployment"
    base_dir.mkdir(parents=True, exist_ok=True)
    if versioned:
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d-%H%M%S")
        return base_dir / f"{instance_code}-Instance-Deployment-Record-{timestamp}.docx"
    return base_dir / f"{instance_code}-Instance-Deployment-Record.docx"
```

### 6. Tests

`tests/test_regenerate_record_dialog.py` and `tests/test_regenerate_record_worker.py`:

- `test_dialog_disables_generate_with_no_inputs` — empty registrar field disables Generate; populating it enables Generate.
- `test_dialog_prefills_from_deploy_config` — deploy_config with persisted `domain_registrar="Porkbun"` produces a dialog whose Registrar field reads "Porkbun".
- `test_dialog_overwrite_vs_versioned_path_resolution` — overwrite returns the canonical path; versioned returns a path with a timestamp suffix.
- `test_worker_emits_completed_on_success` — patches SSH layer and generator to succeed; asserts `completed` signal is emitted with the expected path.
- `test_worker_emits_failed_on_inspection_error` — patches SSH inspection to raise; asserts `failed` signal is emitted with the exception message and `completed` is not emitted.
- `test_worker_emits_failed_on_generation_error` — patches generator to raise; asserts `failed` signal carries the message.

---

## Acceptance criteria

- The Generate Deployment Record action is visible on the Deployment tab when an active instance has a populated `InstanceDeployConfig`, hidden / disabled otherwise.
- The dialog pre-fills correctly from persisted columns and templated defaults.
- A successful run produces a file at the expected path that opens cleanly in Word / LibreOffice and matches the v1.2 visual standard.
- A failed run (SSH unreachable, generator error) produces an error message in the dialog without crashing the application.
- The Prompt B Result page's "Generate manually" button launches the same dialog correctly.
- All existing tests continue to pass; new tests pass.
- `uv run ruff check` passes on all touched files.

---

## Notes for the implementer

- The existing `recovery_dialog.py` and `upgrade_dialog.py` are the closest structural analogues. Skim them first; the Setup → Running → Done mode pattern is established there.
- The `AdministratorInputs` dataclass should be imported from `automation/core/deployment/record_generator.py` (Prompt A) and not redefined.
- When the dialog's administrator-input values differ from the persisted `InstanceDeployConfig` columns, the worker writes the new values back to the row before calling the generator. This keeps the persisted state aligned with the Record's claims. Use the existing `save_deploy_config` flow.
- Cancel during the Running phase is hard to make truly graceful (paramiko's blocking I/O is the limiting factor). It's acceptable for v1.0 to disable Cancel during Running and only allow Close from Done mode. Document this in a comment.
- The output filename uses `Instance.code` as the disambiguator. For CBM Test, that's `CBMTEST`, producing `CBMTEST-Instance-Deployment-Record.docx`. This intentionally diverges from the existing hand-produced filename `CBM-Test-Instance-Deployment-Record.docx` — the application's naming is more uniform across instances and the existing hand-produced filename can be renamed (or both can coexist) when the CBM Test backfill is performed as a separate manual step after Prompt C lands.

---

## After this prompt

The series is complete. Next steps after merging Prompt C, in the order they should happen:

1. Run the manual regeneration once against the CBM Test Instance (as a smoke test against a real, complex deployment).
2. Review the output. If it matches the existing hand-produced v1.2, retire the JS generator at `ClevelandBusinessMentoring/PRDs/deployment/generate-deployment-record.js`. If it diverges, open a bug and iterate.
3. Update the Deployment Runbook to reflect that Sections 11.1–11.3 (manual Record production) are now performed automatically by the wizard, with the manual flow available as a fallback. Bump the Runbook to v1.1.
4. (Optional, later) Decide whether to add a "Regenerate Records for all instances in this client" batch operation.

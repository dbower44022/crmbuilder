# Claude Code Prompt — Deployment Record Series, Prompt B

**Series:** deployment-record (productize the Deployment Record artifact)
**Prompt ID:** B
**Descriptor:** wizard-integration
**Filename:** `CLAUDE-CODE-PROMPT-deployment-record-B-wizard-integration.md`
**Repository:** `crmbuilder`
**Depends on:** Prompt A (deployment-record-A-python-generator-module) merged
**Reference document:** `crmbuilder/PRDs/product/crmbuilder-automation-PRD/deployment-runbook.docx` v1.0 §11 (the manual process this prompt automates)
**Last Updated:** 05-02-26 06:30
**Version:** 1.0

---

## Status

Second prompt in the deployment-record series. Wires the generator from Prompt A into the deploy wizard's success path, so every successful self-hosted deploy automatically produces a Deployment Record `.docx` in the client's project folder. The administrator's only post-deploy work for documentation becomes verifying the generated file looks right and capturing the MariaDB root password into the password manager.

This prompt does not touch the manual-regeneration path (that's Prompt C). The Setup Wizard is the only call site introduced here.

After Prompt B: a self-hosted deploy that succeeds produces both the EspoCRM instance and a `.docx` Deployment Record, with the file path surfaced to the administrator on the wizard's success page.

---

## What this prompt accomplishes

1. **Wizard final-page expansion** — the success page (the Result page in `wizard_dialog.py`) gains a "Deployment Record" section showing the generated file's path, with a "Reveal in file manager" button that opens the containing folder.
2. **Administrator-input collection** — three new wizard pages (or one combined page; see "Detailed implementation" below for the recommended split) collect the administrator-supplied values that cannot be auto-detected: domain registrar, DNS provider, Droplet ID, weekly-backups status, and the three Proton Pass entry names. These pages appear *after* the existing self-hosted progress page and *before* the Result page, only on the self-hosted scenario.
3. **Generator invocation in the deploy worker's success path** — after `persist_deploy_config_from_wizard` writes the `InstanceDeployConfig` row, the worker calls `inspect_server_for_record_values` (still over the existing SSH connection), then `generate_deployment_record`. The output path is `{project_folder}/PRDs/deployment/{instance_code}-Instance-Deployment-Record.docx`. The parent directory is created if missing.
4. **Failure isolation** — Record-generation failure is non-fatal. If generation raises, the deploy is still considered successful (the EspoCRM instance is operational), and the Result page surfaces the generation failure as a warning with the exception message and a "Generate Deployment Record" link that defers to Prompt C's manual flow.
5. **Tests** — extend `tests/test_deploy_worker.py` (or add a new test module if the existing one is hard to extend cleanly) with two integration-style tests: one for the success path producing a Record, one for the Record-generation-fails path producing a successful deploy with a warning.

---

## What this prompt does NOT do

- **No new generator code.** Prompt A produced the generator; this prompt only calls it.
- **No manual-regeneration UI.** That is Prompt C.
- **No retroactive Record generation for the existing CBM Test Instance.** That is also a Prompt C concern.
- **No changes to the cloud-hosted or bring-your-own scenarios.** Those scenarios have no SSH connection and no `InstanceDeployConfig` row; they cannot produce a Deployment Record. The new wizard pages introduced here are gated to the self-hosted path only.
- **No changes to the JS generator in the CBM repo.** It continues to exist; retiring it is a future cleanup.

---

## Constraints and conventions

- **Match existing wizard conventions.** Page-construction follows the pattern in `wizard_dialog.py`'s `_build_self_hosted_*_page` methods. Validation follows the pattern in `_validate_sh_*` methods.
- **Use the existing SSH connection.** The deploy worker has an open paramiko `SSHClient` from `connect_ssh(cfg)`. Pass it directly into `inspect_server_for_record_values`. Do not open a second connection.
- **Persist the administrator inputs in `InstanceDeployConfig` where they fit.** Specifically: `domain_registrar`, `dns_provider`, `droplet_id`, `backups_enabled` are useful enough for future re-runs (Prompt C) that they should be saved. This requires a tiny schema migration (`_client_v10`) adding four columns: `domain_registrar TEXT`, `dns_provider TEXT`, `droplet_id TEXT`, `backups_enabled INTEGER`. The Proton Pass entry names are *not* persisted to the database — they go into the generated `.docx` and nowhere else, since the database is not the appropriate place to track external password-manager entry naming.
- **Be defensive about the project folder.** If `Instance.project_folder` is unset or does not exist on disk, surface a clear message on the Result page and skip generation rather than crashing. The administrator can run the manual flow from Prompt C after setting up the project folder.
- **Python 3.11+ syntax, type hints, docstrings, pytest** — same conventions as Prompt A and the rest of the codebase.

---

## Detailed implementation

### 1. Schema migration `_client_v10`

`automation/db/migrations.py` (or wherever client migrations are sequenced — verify against the existing `_client_v9` pattern) gains an entry for `_client_v10`:

```sql
ALTER TABLE InstanceDeployConfig ADD COLUMN domain_registrar TEXT;
ALTER TABLE InstanceDeployConfig ADD COLUMN dns_provider TEXT;
ALTER TABLE InstanceDeployConfig ADD COLUMN droplet_id TEXT;
ALTER TABLE InstanceDeployConfig ADD COLUMN backups_enabled INTEGER;
```

`backups_enabled` is `INTEGER` in SQLite (0 / 1) with `NULL` permitted for "not yet captured" (existing rows from before this migration will be `NULL` until backfilled). The `automation/core/deployment/deploy_config_repo.py` `InstanceDeployConfig` dataclass and `_row_to_config` / `save_deploy_config` functions are extended to round-trip the new columns.

### 2. Wizard page additions

The recommended split is **one new page** added between the existing self-hosted progress page and the Result page. Reasoning: the administrator is in flight at that point and has just watched a deploy succeed; loading them with three separate pages of forms is friction. One page with five form fields (registrar, DNS provider, Droplet ID, backups checkbox, three Proton Pass entry names) is acceptable density.

Page name: "Documentation Inputs". Built in `wizard_dialog.py` as `_build_self_hosted_documentation_page`. Validation in `_validate_sh_documentation`.

Field details:

| Field | Widget | Default | Validation |
|---|---|---|---|
| Domain Registrar | QLineEdit | "Porkbun" | Required, non-empty |
| DNS Provider | QLineEdit | (auto-fills with registrar value if same) | Required |
| Droplet ID | QLineEdit | (parsed from clipboard URL if it matches the DigitalOcean droplet URL pattern) | Optional; if present, must be all-digits |
| Backups Enabled | QCheckBox | unchecked | none |
| Admin Password Proton Pass Entry | QLineEdit | (templated from instance_code, e.g. "{code}-ESPOCRM-{Env} Instance Admin") | Required |
| DB Root Password Proton Pass Entry | QLineEdit | (templated similarly) | Required |
| DigitalOcean Account Proton Pass Entry | QLineEdit | (templated) | Required |

Each field has a one-line hint label below it explaining what it's for. The page header explains: "These values are needed to generate the Deployment Record document. They are not used by the application itself; they document where each item is stored or who manages it."

The page's defaults make the typical case (a CBM-style deploy) one click ("Next") rather than seven fields of typing.

### 3. Deploy worker integration

`automation/ui/deployment/deploy_wizard/deploy_worker.py`'s `SelfHostedWorker._run_phases` method gains a final block after the verification phase succeeds:

```python
# Persist deploy config (existing behavior, unchanged)
# ... wizard_logic.persist_deploy_config_from_wizard call lives here ...

# Generate Deployment Record (new behavior)
self.step_started.emit("generate_record")
self._log("=== Generating Deployment Record ===")
try:
    record_path = _generate_deployment_record_from_deploy(
        ssh=ssh,
        instance=self._persisted_instance,
        deploy_config=self._persisted_deploy_config,
        administrator_inputs=self._administrator_inputs,
        project_folder=self._project_folder,
        log=self._log,
    )
    self.record_generated.emit(str(record_path))
    self.step_completed.emit("generate_record")
except Exception as exc:
    self._log(f"Deployment Record generation failed: {exc}", "warning")
    self.record_generation_failed.emit(str(exc))
    # Do NOT call step_failed — the deploy itself succeeded.
```

`_generate_deployment_record_from_deploy` is a small private orchestrator that bridges the worker's available state to the Prompt A function signatures. It builds the `AdministratorInputs` from `self._administrator_inputs`, calls `inspect_server_for_record_values`, builds the `DeploymentRecordValues` from the inspection result + the `Instance` and `InstanceDeployConfig` rows, and calls `generate_deployment_record(values, output_path)`.

Two new signals on `SelfHostedWorker`:
- `record_generated = Signal(str)` — emitted with the absolute path of the generated `.docx`.
- `record_generation_failed = Signal(str)` — emitted with the exception message.

The Result page subscribes to both. On `record_generated` it shows the path with a "Reveal in file manager" button (uses `QDesktopServices.openUrl(QUrl.fromLocalFile(parent_dir))`). On `record_generation_failed` it shows a yellow warning panel with the message and a "Generate manually" button that triggers Prompt C's regeneration dialog (Prompt C must implement that dialog as a callable from arbitrary code, not only from the Deployment tab UI).

### 4. Output path

```python
output_path = (
    Path(project_folder)
    / "PRDs"
    / "deployment"
    / f"{instance_code}-Instance-Deployment-Record.docx"
)
```

If `Path(project_folder)` does not exist or is not a directory, surface a non-fatal warning and skip generation. The Result page displays the missing-project-folder explanation in that case.

### 5. Tests

Two new tests in `tests/test_deploy_worker.py` (or a new module if the existing one is hard to extend):

- `test_self_hosted_worker_generates_record_on_success` — patches the SSH layer to simulate a successful deploy, patches the generator to a no-op that records the call. Asserts `record_generated` is emitted with the expected path and the generator was called with a `DeploymentRecordValues` derived from the (mocked) Instance / InstanceDeployConfig.
- `test_self_hosted_worker_emits_warning_on_record_failure` — same setup, but the patched generator raises. Asserts `record_generation_failed` is emitted with the exception message, `deployment_finished` is emitted with `True` (deploy succeeded), and no `step_failed` for `generate_record` is emitted.

If integration-test scaffolding is too heavy for these (paramiko mocking, etc.), it's acceptable to test `_generate_deployment_record_from_deploy` as a unit instead: exercise it with a real (in-memory) `Instance` and `InstanceDeployConfig`, mock the SSH inspection helper to return a fixture `DeploymentRecordValues`, and verify the generator is called with that exact values bag and the correct output path.

---

## Acceptance criteria

- A self-hosted deploy (run end to end against a clean Droplet, or simulated via a test harness) produces a `.docx` at `{project_folder}/PRDs/deployment/{code}-Instance-Deployment-Record.docx`.
- The Documentation Inputs wizard page validates correctly, has sensible defaults, and saves the four persistable fields to `InstanceDeployConfig`.
- The Result page surfaces either the success path (file path + Reveal button) or the failure path (warning + manual-generation button).
- Migration `_client_v10` applies cleanly to a database at `_client_v9` and is idempotent on re-application.
- All existing tests continue to pass; new tests pass.
- `uv run ruff check` passes on all touched files.
- The cloud-hosted and bring-your-own scenarios are unaffected — verified by exercising those paths in the wizard and confirming no Documentation Inputs page appears, no Record is generated, and no errors surface.

---

## Notes for the implementer

- The wizard's existing pattern uses index-based page navigation. Inserting a new page between progress and Result requires updating index constants and the `_on_next` / `_on_back` page-routing logic. Trace those carefully — the routing varies by scenario (self-hosted vs cloud vs BYO).
- The `AdministratorInputs` collected on the new page need to survive across the wizard's worker invocation. The existing pattern has `_self_hosted_config` as a `SelfHostedConfig` instance set during `_validate_sh_*` and consumed by `_start_self_hosted_deploy`. Add `_administrator_inputs` parallel to it.
- Persisting the administrator inputs to `InstanceDeployConfig` happens *before* the Record-generation call so that a Record-generation failure still leaves the inputs available for Prompt C's manual flow.
- The "Reveal in file manager" button should use `QDesktopServices` rather than shelling out — cross-platform behavior is better and the project doesn't otherwise shell out for file-manager operations.

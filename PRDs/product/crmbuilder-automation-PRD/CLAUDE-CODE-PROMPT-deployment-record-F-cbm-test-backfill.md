# Claude Code Prompt — Deployment Record Series, Prompt F

**Series:** deployment-record (productize the Deployment Record artifact)
**Prompt ID:** F
**Descriptor:** cbm-test-backfill
**Filename:** `CLAUDE-CODE-PROMPT-deployment-record-F-cbm-test-backfill.md`
**Repository:** `crmbuilder`
**Depends on:** Prompts A, B, C, E merged (A and B in commit `ab41c84`; C in `0bcfeea`; E in `b125afc`)
**Related artifact:** `tools/diagnostics/bridge_password_to_keyring.py` (committed in `c013185`) — the keyring-bridge helper this prompt's documentation references but does not invoke directly
**Last Updated:** 05-02-26 14:30
**Version:** 1.0

---

## Status

A one-time targeted operation, not a feature. This prompt produces the steps and supporting code (where necessary) to populate the missing `InstanceDeployConfig` row for the live CBM Test EspoCRM instance, so that:

- The Deployment tab's "Generate Deployment Record" action (added by Prompt C) becomes enabled for that instance.
- The Setup Wizard's "Documentation Inputs" page (added by Prompt B) is bypassed-by-existence for any future re-deploys / regenerations against this instance.
- The smoke test of the deployment-record series can run against a real, complex deployment.

The CBM Test instance was deployed on 2026-03-28, before migration `_client_v9` (which introduced the `InstanceDeployConfig` table) had been applied to the local database. The Instance row was created on 2026-04-13 via the application's manual "Add Instance" flow but no associated deploy-config row was ever written. Migration `_client_v9` and `_client_v10` (Prompt B) have since been applied; the table exists and is empty.

This prompt's deliverable is **not** application code changes. It is a structured backfill procedure that uses existing application infrastructure (the `ConnectionConfigDialog` flow already invoked by Upgrade and Recovery) to write the row correctly. The prompt also adds the small cross-reference needed so that Prompt C's "Generate Deployment Record" action invokes the same backfill flow when no config exists, mirroring the pattern in Upgrade and Recovery — closing a small gap in C and making this backfill operation reachable from the right entry point.

After Prompt F: the CBM Test instance has a populated `InstanceDeployConfig` row containing every captured value, and the user can then proceed with the smoke test by clicking "Generate Deployment Record" on the Deployment tab.

---

## What this prompt accomplishes

1. **Adds the missing backfill invocation to Prompt C's Deployment-tab action.** The new action's handler should follow the same `load_deploy_config → if None: ConnectionConfigDialog → check saved_config` pattern that `_on_upgrade` and `_on_recovery` use in `deploy_entry.py`. The handler today either disables the button when config is missing (per Prompt C's spec) or fails to launch the dialog. Whichever it does, change it to mirror the existing Upgrade / Recovery pattern: open the backfill dialog first if config is missing, proceed with regeneration after the dialog returns successfully.

2. **Authoring documentation only — no DB writes from this prompt.** The actual data entry happens interactively when the user clicks the new button or runs Upgrade / Recovery against an instance that lacks a config row. The prompt produces a Markdown procedural document (`PRDs/product/crmbuilder-automation-PRD/cbm-test-instance-backfill-procedure.md`) that records the exact values to enter into the `ConnectionConfigDialog` form when the user runs the backfill against the CBM Test instance, and the keyring-bridge step needed for the MariaDB root password.

3. **Small test addition.** A test verifying that `_on_generate_record_manually` in `deploy_entry.py` (the new Deployment-tab action handler) opens the backfill dialog when `load_deploy_config` returns `None`, and proceeds to the regeneration dialog after the user fills in and confirms the backfill.

---

## What this prompt does NOT do

- **No data writes.** The prompt does not modify any SQLite database, does not write to keyring, does not issue any SSH commands. The user runs the resulting procedure interactively after Prompt F is merged.
- **No new wizard or dialog code.** `ConnectionConfigDialog` (in `automation/ui/deployment/connection_config_dialog.py`) is reused as-is. Do not modify it for this prompt.
- **No changes to the keyring-bridge script.** It is committed at `tools/diagnostics/bridge_password_to_keyring.py` and used as-is by the operator running the backfill procedure.
- **No retroactive Record generation.** The Deployment Record `.docx` is produced after backfill via the regular "Generate Deployment Record" action, not by this prompt.
- **No CBM repository changes.** This prompt operates entirely in the crmbuilder repo. The CBM repo is unaffected until the operator later commits the regenerated `.docx`, which is a separate manual step performed during the smoke test.
- **No Prompt B changes.** Prompt B's wizard pages handle the deploy-time path; this prompt only touches the post-deploy / backfill path on the Deployment tab.

---

## Constraints and conventions

- **Mirror the Upgrade and Recovery patterns exactly.** The handler structure should be the same: import `load_deploy_config` and `ConnectionConfigDialog` lazily inside the handler; check for `_conn` and `_instance` non-None at the top; load config; if `None`, exec the dialog and read `dialog.saved_config`; bail on cancel; otherwise proceed.
- **Reuse existing `_db_path()` if applicable.** The handler may need the database path to launch the regeneration dialog; use the existing helper rather than recomputing.
- **No new constructor arguments to existing classes.** All values are obtainable from existing state.
- **Procedure document follows CBM PRD output standards** insofar as a Markdown file can — Last Updated date in MM-DD-YY HH:MM format, a Revision History section, and concrete actionable steps.
- **The procedure document includes the captured values verbatim.** The point of the document is to be a checklist the operator follows during the live backfill; if the values aren't there, the document fails its purpose.
- **Python 3.11+, type hints, docstrings, pytest** — same conventions as the rest of the codebase.

---

## Detailed implementation

### 1. Handler change in `deploy_entry.py`

Locate the existing `_on_generate_record_manually` handler (added by Prompt C). It currently handles the action-button click on the "Generate Deployment Record" button. Whatever its current implementation does when `load_deploy_config` returns `None`, replace that path with the same `ConnectionConfigDialog` invocation used by `_on_upgrade` and `_on_recovery`. After the dialog returns and `saved_config is not None`, the handler then proceeds to invoke `launch_regeneration_dialog` as it would have if config had existed at the start.

Cross-reference the file. Read these two existing handlers as the canonical pattern:
- `_on_upgrade` in `automation/ui/deployment/deploy_entry.py`
- `_on_recovery` in `automation/ui/deployment/deploy_entry.py`

The new control flow:

```
def _on_generate_record_manually(self) -> None:
    if self._conn is None or self._instance is None:
        return

    config = load_deploy_config(self._conn, self._instance.id)
    if config is None:
        # Same backfill pattern as Upgrade and Recovery.
        dialog = ConnectionConfigDialog(
            self._conn, self._instance.id, self._instance.name,
            parent=self,
        )
        dialog.exec()
        config = dialog.saved_config
        if config is None:
            return  # User cancelled.

    # At this point config is non-None. Proceed with regeneration.
    launch_regeneration_dialog(
        parent=self,
        instance_id=self._instance.id,
        connection=self._conn,
        # ...other arguments matching launch_regeneration_dialog's signature
    )
```

The exact arguments to `launch_regeneration_dialog` are whatever its signature requires. Read the signature in `automation/ui/deployment/regenerate_record_dialog.py`. Do not modify the signature.

If Prompt C's button-enable logic currently disables the button when config is missing, also update that gating: with this change, the button should be enabled whenever the instance is self-hosted, regardless of whether config exists yet — the handler now handles the missing-config case gracefully via the backfill dialog. The relevant gating code is likely in `set_client_context` or `_update_action_states` (or similar) on `DeployEntry`.

### 2. Procedure document

Create a new file:

```
PRDs/product/crmbuilder-automation-PRD/cbm-test-instance-backfill-procedure.md
```

Content structure (this is the spec; produce the document literally):

```markdown
# CBM Test Instance — InstanceDeployConfig Backfill Procedure

| Field | Value |
|---|---|
| Document Type | Procedural runbook (one-time operation) |
| Subject | CBM Test EspoCRM instance — backfilling deploy config |
| Status | Active — to be performed once, then archived |
| Version | 1.0 |
| Last Updated | (insert MM-DD-YY HH:MM at execution time) |

## Revision History

| Version | Date | Notes |
|---|---|---|
| 1.0 | (date) | Initial release. |

## Purpose

The CBM Test EspoCRM instance was deployed on 2026-03-28 before
the application's `InstanceDeployConfig` schema existed locally.
The Instance row was created later via the manual Add Instance
flow and no deploy-config row was ever written. Migration
`_client_v10` (Prompt B in the deployment-record series) has
since been applied; the table exists, is empty, and is now
populatable via the in-application backfill flow.

This procedure populates the row using the application's existing
`ConnectionConfigDialog` flow and the keyring-bridge helper.

## Prerequisites

1. The crmbuilder application is up to date with at least commit
   `b125afc` (Prompts A, B, C, E merged).
2. Proton Pass is open with the entry
   `ESPOCRM Root DB Password - Test Instance` accessible.
3. The SSH key file
   `~/Dropbox/Projects/ClevelandBusinessMentors/ssh` is in place.
4. The diagnostic helper `tools/diagnostics/bridge_password_to_keyring.py`
   is present (committed in `c013185`).

## Step 1 — Bridge the MariaDB root password into the OS keyring

From the crmbuilder repo root:

```
uv run python tools/diagnostics/bridge_password_to_keyring.py
```

When prompted, paste the MariaDB root password from Proton Pass
(twice, hidden input). On success, copy the printed
`crmbuilder:<uuid>` reference string. This goes into Step 2.

## Step 2 — Run the backfill via the application

Launch the application:

```
uv run crmbuilder
```

In the application:

1. Select the CBM client.
2. Open the Deployment tab.
3. Click on the CBM Test instance.
4. Click any of: Upgrade, Recovery & Reset, or
   Generate Deployment Record. (All three trigger the same
   backfill dialog when config is missing.)
5. The Connection Config dialog opens. Enter the values from
   the table below.
6. Click Save / OK.
7. After the dialog closes, click Cancel on the
   Upgrade / Recovery / Regenerate dialog that opens next.
   The backfill is complete; we don't need to perform the action
   that triggered it.

## Step 3 — Values to enter

| Field | Value |
|---|---|
| SSH Host | `104.131.45.208` |
| SSH Port | `22` |
| SSH Username | `root` |
| SSH Auth Type | `key` |
| SSH Credential | `~/Dropbox/Projects/ClevelandBusinessMentors/ssh` |
| Domain | `crm-test.clevelandbusinessmentors.org` |
| Let's Encrypt Email | `admin@cbmentors.org` |
| DB Root Password Reference | `crmbuilder:<uuid>` from Step 1 |
| Admin Email | `admin@cbmentors.org` |
| Current EspoCRM Version | `9.3.4` |
| Cert Expiry Date | `2026-06-26` |
| Domain Registrar (Prompt B field) | `Porkbun` |
| DNS Provider (Prompt B field) | `Porkbun` |
| Droplet ID (Prompt B field) | `561480073` |
| Backups Enabled (Prompt B field) | `false` (unchecked) |

If the dialog does not expose all of these fields directly,
note which it omits in the verification step below; remaining
columns can be reviewed via the diagnostic script
(`cbm_deployment_inspect.py`) and any gaps addressed in a
follow-up.

## Step 4 — Verify

Run the existing inspector:

```
python3 ~/crmbuilder-diagnostics/cbm_deployment_inspect.py
```

In the output, the section `InstanceDeployConfig rows` should
now show one row with all of the values from Step 3.

## Step 5 — Proceed with smoke test

The CBM Test instance is now ready for the deployment-record
series smoke test:

1. In the Deployment tab, click Generate Deployment Record.
2. A Documentation-Inputs-style dialog will appear pre-filled
   from the row written in Steps 1–3.
3. Confirm and let the regeneration run.
4. The output `.docx` lands at
   `~/Dropbox/Projects/ClevelandBusinessMentors/PRDs/deployment/CBMTEST-Instance-Deployment-Record.docx`.
5. Compare visually against the existing hand-produced
   `CBM-Test-Instance-Deployment-Record.docx` v1.3.

If the comparison passes, the smoke test is complete.
```

### 3. Test addition

In `tests/test_deploy_entry.py` (or whichever existing test module covers `DeployEntry` — verify by searching `tests/`), add or extend tests as follows:

- `test_on_generate_record_manually_opens_backfill_when_config_missing` — patches `load_deploy_config` to return `None`, patches `ConnectionConfigDialog` to a `MagicMock` whose `saved_config` returns a populated `InstanceDeployConfig`, patches `launch_regeneration_dialog` to a `MagicMock`. Calls `_on_generate_record_manually`. Asserts the dialog was constructed with the right arguments and that `launch_regeneration_dialog` was subsequently called.
- `test_on_generate_record_manually_skips_when_user_cancels_backfill` — same patches but the dialog's `saved_config` returns `None` (user cancelled). Asserts `launch_regeneration_dialog` was NOT called.

If `tests/test_deploy_entry.py` does not exist yet, create it. Use the established test scaffolding from `tests/test_deploy_worker.py` as the model.

---

## Acceptance criteria

- The handler in `deploy_entry.py` follows the exact pattern of `_on_upgrade` and `_on_recovery` for the missing-config case.
- The procedure document at `PRDs/product/crmbuilder-automation-PRD/cbm-test-instance-backfill-procedure.md` exists, contains the full table of values, and is internally consistent.
- The two new tests pass; existing tests continue to pass.
- `uv run ruff check` passes on touched files.
- `grep -rn "Generate Deployment Record" automation/ui/deployment/` shows the action is wired only in `deploy_entry.py`; no stray references elsewhere.

---

## Notes for the implementer

- The CBM repo (`dbower44022/ClevelandBusinessMentoring`) is not touched by this prompt. The procedure document lives in the crmbuilder repo because it is a procedure for using the crmbuilder application, not CBM-internal documentation.
- Treat the value table in the procedure document as authoritative. Do not modify or "improve" any value. Each was captured during a structured diagnostic pass on 2026-05-02 and tied back to specific evidence in the live system, the operator's recollection, or earlier deployment work.
- The procedure includes a "click Cancel on the action dialog that opens next" step in Step 2.7. This is intentional and correct: the easiest way to invoke the backfill without performing an actual upgrade or recovery is to launch the action that triggers the backfill, then cancel the resulting action dialog after the backfill itself has saved. This is a one-liner in the doc and should not be elaborated.
- After this prompt is merged and executed, the CBM Test backfill itself is the next action — and it is not part of this prompt's deliverable. The operator runs the procedure, then proceeds to the smoke test.

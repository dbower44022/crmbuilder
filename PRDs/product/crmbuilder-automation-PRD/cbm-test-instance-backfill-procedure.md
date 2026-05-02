# CBM Test Instance — InstanceDeployConfig Backfill Procedure

| Field | Value |
|---|---|
| Document Type | Procedural runbook (one-time operation) |
| Subject | CBM Test EspoCRM instance — backfilling deploy config |
| Status | Active — to be performed once, then archived |
| Version | 1.0 |
| Last Updated | 05-02-26 14:30 |

## Revision History

| Version | Date | Notes |
|---|---|---|
| 1.0 | 05-02-26 | Initial release. |

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

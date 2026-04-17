# Claude Code Prompt — Deploy Wizard Rewrite (Three Scenarios)

## Purpose

L2 PRD v1.16 replaces the legacy single-path Deploy Wizard with a
three-scenario wizard covering self-hosted, cloud-hosted, and
bring-your-own deployments. This prompt implements the wizard internals
behind the "Start Deploy Wizard" launch button that Prompt C wired up as
a stub. On completion, the Deploy entry's launch button must open the
real wizard and every wizard run must write a `DeploymentRun` row.

## Position in the Sequence

- Prompt A (merged): Schema migrations for `Instance` and
  `DeploymentRun` (`CLAUDE-CODE-PROMPT-schema-instance-deploymentrun.md`)
- Prompt B (merged): Tab restructure + Clients tab UI
  (`CLAUDE-CODE-PROMPT-tab-restructure-clients-tab.md`)
- Prompt C (merged): Deployment tab shell + legacy JSON migration
  (`CLAUDE-CODE-PROMPT-deployment-tab-shell-iss017.md`)
- **Prompt D (this file): Deploy Wizard internals (three scenarios)**
- Prompt E: Terminology sweeps (administrator → implementor,
  Dashboard → Requirements Dashboard)

Prompt C left a stub: the Deploy entry's "Start Deploy Wizard" button is
wired up but its click handler shows a "Not yet implemented — see
Prompt D" message box. This prompt replaces that stub with the real
wizard.

## Authoritative Source

Read the following sections of
`PRDs/product/crmbuilder-automation-PRD/crmbuilder-automation-l2-PRD.docx`
before implementing:

- **Section 3.1** — `Client.crm_platform` and `Client.deployment_model`
  columns (populated in Phase 9, read by the wizard for scenario
  pre-selection)
- **Section 6.5** — `Instance` table (what the wizard reads and writes)
- **Section 6.6** — `DeploymentRun` table (append-only history; written
  on every wizard execution)
- **Section 14.12.4** — Deploy entry (the history table the wizard
  appends to, and the launch button the wizard opens from)
- **Section 14.12.5** — Deploy Wizard overview (scenario confirmation,
  pre-selection, existing-instance matching)
- **Section 14.12.5.1** — Self-Hosted Path (seven-step sequence)
- **Section 14.12.5.2** — Cloud-Hosted and Bring-Your-Own Paths
  (four-step shared sequence)
- **Section 14.12.6** — Supported Deployment Targets (v1: EspoCRM only,
  in all three scenarios)
- **Section 15, DEC-070 through DEC-075** — the decisions driving this
  rewrite, especially DEC-071's statement that product names are
  permitted in deployment-phase content and DEC-072's explicit
  out-of-scope list for vendor provisioning APIs

## Legacy Code to Port From (Not Edit In Place)

The existing self-hosted wizard implementation lives under `espo_impl/`:

- `espo_impl/ui/deploy_wizard.py` — legacy PySide6 QWizard (single-path,
  self-hosted only)
- `espo_impl/core/deploy_manager.py` — SSH + installer orchestration
  logic (domain verification, EspoCRM installer invocation, Let's
  Encrypt provisioning, admin user creation, connectivity check)
- `espo_impl/workers/deploy_worker.py` — QThread worker that runs the
  long-running deploy steps without blocking the UI

These files are the **reference implementation** for the self-hosted
path, not the target location. Do not edit them in place. Port the
relevant logic into the new wizard under `automation/ui/deployment/`
(alongside Prompt C's deployment tab shell) and leave the legacy files
untouched for now — Prompt E or a later cleanup can remove them.

## Out of Scope for Prompt D

- **Additional CRM platforms.** Section 14.12.6 lists EspoCRM as the
  only v1 target. The wizard's data model and branching must be
  structured to accept new platforms in future releases (per DEC-075),
  but Prompt D only implements EspoCRM steps.
- **Vendor provisioning APIs.** Per DEC-072, the wizard does not create
  vendor accounts, configure billing, or call vendor REST APIs to
  provision instances. Cloud-hosted is always "register an existing
  instance the implementor already purchased."
- **Terminology sweeps.** Any "administrator" or "Dashboard" strings in
  the legacy code being ported should be carried over as-is (or with
  the wizard's own new copy written correctly from the start). The
  global sweep is Prompt E.
- **Encrypted credential storage (ISS-018).** Credentials written to
  `Instance` rows remain plaintext in v1, same as Prompt C.

## Required Implementation

### 1. Wizard shell and scenario selection (§14.12.5)

Create a new QWizard (or equivalent QDialog-with-stacked-pages) under
`automation/ui/deployment/deploy_wizard/` with the following behavior:

- **Step 1 — Scenario and Platform confirmation.** Radio buttons for
  the three scenarios (self-hosted, cloud-hosted, bring-your-own) and a
  CRM platform selector (v1: EspoCRM only, so the control is a single
  read-only value but structured to accept more in the future).
- **Pre-selection from `Client`.** On entry to Step 1, read
  `Client.crm_platform` and `Client.deployment_model` for the active
  client. When both are non-NULL, pre-select the matching radio and
  platform. The implementor may override. When either is NULL (Phase 9
  incomplete), no pre-selection — the implementor must pick explicitly.
- **Existing-instance matching.** After Step 1 is confirmed, query the
  per-client `Instance` table for rows matching the wizard's target
  (same platform and deployment model). If one or more matches exist,
  show a dialog with three options: **Update existing in place**
  (dropdown selector when multiple match), **Create new instance**, or
  **Cancel**. If no match exists, proceed directly to the
  scenario-specific steps.
- **DeploymentRun lifecycle.** Insert a `DeploymentRun` row when the
  wizard transitions past Step 1 into the scenario-specific steps,
  populated with `scenario`, `crm_platform`, `instance_id` (if
  updating) or NULL (if creating), and `started_at`. Update the same
  row with `completed_at`, `outcome` (success, failure, cancelled),
  and `failure_reason` when the wizard terminates. Never delete.

### 2. Self-hosted path (§14.12.5.1)

Implement seven steps, in order, porting logic from
`espo_impl/core/deploy_manager.py` and
`espo_impl/workers/deploy_worker.py`:

1. **Server target capture** — SSH host, port, username, credential
   (password or key path). No server provisioning.
2. **Domain capture and DNS verification** — domain name, then a
   verification check that DNS resolves to the supplied server. Retry
   every 30 seconds up to a 10-minute timeout. Show live progress.
3. **CRM platform installation** — run the official EspoCRM installer
   script non-interactively over SSH with configuration passed as
   command-line flags. Docker is installed by the installer script;
   the wizard does not install Nginx, PHP, or MySQL directly.
4. **TLS certificate provisioning** — Let's Encrypt for the configured
   domain. HTTP-only and custom-certificate modes are not offered in
   v1.
5. **Admin account creation** — capture initial admin username and
   password, create the EspoCRM admin user.
6. **Connectivity verification** — HTTPS reachability plus an
   authenticated EspoCRM REST API call.
7. **Instance row population** — write `url = https://{domain}`,
   `admin_username`, `admin_password` into the matched `Instance` row,
   or insert a new row. Finalize the `DeploymentRun` row.

All long-running network and SSH work must run in a worker thread so
the wizard UI stays responsive. Mirror the threading pattern already
used in `espo_impl/workers/deploy_worker.py`.

### 3. Cloud-hosted and bring-your-own paths (§14.12.5.2)

Both scenarios share an identical four-step sequence and differ only
in the help text on the first step. Implement once, parameterize the
help text by scenario:

1. **Instance details capture** — URL, admin username, admin password
   (or API token where applicable). Cloud-hosted help text directs the
   implementor to the vendor portal; bring-your-own help text directs
   them to their own configured credentials.
2. **Connectivity verification** — reach the supplied URL and call the
   CRM REST API with the supplied credentials.
3. **Compatibility check** — verify the connected instance is the
   selected CRM platform and that its version is supported by CRM
   Builder. Maintain a `SUPPORTED_VERSIONS` constant keyed by platform.
4. **Instance row population** — same write semantics as the
   self-hosted path's final step. Finalize the `DeploymentRun` row.

### 4. Wiring to the Deploy entry

Replace Prompt C's "Not yet implemented" handler on the Start Deploy
Wizard button with a handler that instantiates and runs the new
wizard. When the wizard finishes (success, failure, or cancel),
refresh the Deploy entry's history table so the just-inserted
`DeploymentRun` row appears.

### 5. Logic separation

Follow the established pattern from Steps 15a/15b/15c: keep Qt-free
pure-logic modules separate from the PySide6 view classes. Put
pre-selection resolution, existing-instance matching, DNS verification,
SSH invocation, HTTP probes, and version-compatibility checks in
`automation/core/deployment/` so they can be unit-tested without Qt.
The wizard pages under `automation/ui/deployment/deploy_wizard/` are
thin views that call into that core.

## Acceptance Criteria

- Start Deploy Wizard opens a real wizard (no "Not yet implemented"
  dialog remains).
- With `Client.crm_platform` and `Client.deployment_model` populated,
  Step 1 pre-selects and the implementor can override.
- With either column NULL, Step 1 requires explicit selection.
- Existing-instance matching presents update / create-new / cancel
  correctly.
- Self-hosted path runs all seven steps end-to-end against a test
  server (mock SSH in tests; live run verified manually).
- Cloud-hosted and bring-your-own paths run all four steps and differ
  only in help text.
- Every wizard execution — success, failure, or cancel — writes a
  `DeploymentRun` row with appropriate `outcome` and, on failure, a
  `failure_reason`.
- On success, the matched or newly created `Instance` row reflects the
  captured URL and credentials.
- Pure-logic modules under `automation/core/deployment/` are covered by
  unit tests; no Qt imports in that subtree.
- Full test suite passes; `ruff` clean.
- Legacy files under `espo_impl/ui/deploy_wizard.py`,
  `espo_impl/core/deploy_manager.py`, and
  `espo_impl/workers/deploy_worker.py` are **not** edited in this
  prompt.

## Commit Message

    Implement Deploy Wizard rewrite (three scenarios) — Prompt D

    Replaces Prompt C's stub launch handler with a real three-scenario
    Deploy Wizard covering self-hosted, cloud-hosted, and
    bring-your-own paths per L2 PRD v1.16 §14.12.5 and
    DEC-070–DEC-075. Scenario and platform pre-select from
    Client.crm_platform / Client.deployment_model. Every wizard run
    writes a DeploymentRun row. Self-hosted logic ported from
    espo_impl/ reference implementation into automation/core/deployment
    and automation/ui/deployment/deploy_wizard. Legacy espo_impl
    modules left in place for later cleanup.

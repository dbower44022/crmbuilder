# CRM Builder — Server Management Layer

**Version:** 1.0
**Status:** Plan — implementation pending
**Last Updated:** May 2026
**Depends On:** feat-crm-deployment.md, app-ui-patterns.md
**Maintained By:** Claude Code

---

## 1. Purpose

This document defines a persistent server-connection layer that enables
post-deploy operations against a self-hosted EspoCRM instance — Upgrade
EspoCRM, Recovery & Reset, and a future class of maintenance features
(backup/restore on demand, server health checks, log retrieval, cert
renewal monitoring). It also retires the orphaned `espo_impl/`
deployment cluster left behind by the move to the three-tab
architecture.

The need surfaced when the in-place EspoCRM Upgrade feature was
implemented against `espo_impl/core/deploy_manager.py` and discovered to
be unreachable from the live UI. The current production deploy path
(`automation/core/deployment/ssh_deploy.py`) intentionally does not
persist SSH credentials past a deploy run, which prevents *any*
post-deploy SSH operation from working without re-prompting the user.

---

## 2. Status

This is a forward-looking plan. The Upgrade feature was implemented but
not wired in — its phase logic, worker, dialog, and tests will be
ported into the new layer rather than rewritten from scratch.

---

## 3. Goals

- Provide a single durable place to store everything required to SSH
  back into a deployed Droplet for an `Instance`.
- Make Upgrade EspoCRM and Recovery & Reset reachable from the live
  Deployment tab without per-operation credential prompts.
- Establish the pattern for future server-side features so each one is
  a small additive change, not a re-litigation of the credential model.
- Retire the orphaned `espo_impl/` deploy/recovery cluster.

## 4. Non-goals

- No re-architecture of the deploy wizard itself.
- No change to how `Instance.url`/`username`/`password` are used by
  API-path code (Configure, Verify, Audit).
- No support for cloud-hosted or bring-your-own instances in this
  layer — those scenarios cannot be SSHed into by definition. The
  scenario gate is strict: post-deploy server operations are visible
  only when `InstanceDeployConfig.scenario = 'self_hosted'`.

---

## 5. Architecture

### 5.1 Data model — `InstanceDeployConfig` table

One-to-one with `Instance`. New table in the per-client SQLite
database, added by migration `_client_v9` (next after the existing
`_client_v8` in `automation/db/migrations.py`).

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PRIMARY KEY | |
| `instance_id` | INTEGER NOT NULL UNIQUE | FK → `Instance(id)` |
| `scenario` | TEXT NOT NULL CHECK | `'self_hosted'` only in v1 |
| `ssh_host` | TEXT NOT NULL | |
| `ssh_port` | INTEGER NOT NULL DEFAULT 22 | |
| `ssh_username` | TEXT NOT NULL | |
| `ssh_auth_type` | TEXT NOT NULL CHECK | `'key'` \| `'password'` |
| `ssh_credential_ref` | TEXT NOT NULL | keyring reference id (see §5.2) |
| `domain` | TEXT NOT NULL | full domain |
| `letsencrypt_email` | TEXT NOT NULL | |
| `db_root_password_ref` | TEXT NOT NULL | keyring reference id |
| `admin_email` | TEXT | |
| `current_espocrm_version` | TEXT | refreshed by `VersionCheckWorker` |
| `latest_espocrm_version` | TEXT | refreshed by `VersionCheckWorker` |
| `last_upgrade_at` | TIMESTAMP | |
| `last_backup_paths` | TEXT | JSON array of last-3 server paths |
| `cert_expiry_date` | TEXT | YYYY-MM-DD |
| `created_at` | TIMESTAMP DEFAULT CURRENT_TIMESTAMP | |
| `updated_at` | TIMESTAMP DEFAULT CURRENT_TIMESTAMP | |

The `Instance.username` and `Instance.password` columns continue to
hold the EspoCRM admin API credential — that's the API-path concern
and is unchanged. `InstanceDeployConfig` carries the SSH-path concern.

### 5.2 Secret storage — keyring from day one

All secret values live in the OS keyring via Python's `keyring`
package (uses macOS Keychain, Linux Secret Service, Windows Credential
Manager). The DB stores opaque reference IDs only.

A thin abstraction in `automation/core/secrets.py`:

```python
def put_secret(value: str) -> str   # returns reference id
def get_secret(ref: str) -> str
def delete_secret(ref: str) -> None
```

Reference IDs use the form `crmbuilder:{uuid4}`. Service name in the
keyring is `crmbuilder`. Removing an `InstanceDeployConfig` row also
calls `delete_secret` for both `ssh_credential_ref` and
`db_root_password_ref`.

For the SSH key-file case, `ssh_credential_ref` stores the **path**
(not the key contents) — paths are not sensitive in the same way and
this matches the existing wizard model. Only the `'password'` auth
type and `db_root_password` round-trip through keyring.

`keyring` is added to `pyproject.toml` dependencies.

### 5.3 Module layout

```
automation/
├── core/
│   ├── secrets.py                              # NEW — keyring abstraction
│   └── deployment/
│       ├── ssh_deploy.py                       # existing
│       ├── deploy_config_repo.py               # NEW — InstanceDeployConfig CRUD
│       ├── upgrade_ssh.py                      # NEW — phase logic, version helpers
│       └── recovery_ssh.py                     # NEW — admin reset, full DB reset
├── workers/
│   ├── upgrade_worker.py                       # NEW — UpgradeWorker + VersionCheckWorker
│   └── recovery_worker.py                      # NEW
├── ui/
│   └── deployment/
│       ├── connection_config_dialog.py         # NEW — backfill dialog
│       ├── upgrade_dialog.py                   # NEW
│       ├── recovery_dialog.py                  # NEW
│       ├── deploy_entry.py                     # EDIT — Upgrade / Recovery buttons
│       └── instance_picker.py                  # EDIT — version + cert badges
└── db/
    ├── client_schema.py                        # EDIT — InstanceDeployConfig DDL
    └── migrations.py                           # EDIT — _client_v9
```

---

## 6. Functional flows

### 6.1 Wizard persistence

In `automation/core/deployment/wizard_logic.py`, the existing function
that updates `Instance` on a successful deploy gains a sibling write of
`InstanceDeployConfig` from the same `SelfHostedConfig`. Both writes
run in the same transaction. Secrets are stored in keyring first; their
reference IDs go into the table.

No change to `wizard_dialog.py` — every field needed is already
collected on pages 1-3.

### 6.2 Backfill for already-deployed instances

When the user clicks **Upgrade EspoCRM** or **Recovery & Reset** on an
`Instance` that has no `InstanceDeployConfig` row, a
`ConnectionConfigDialog` opens with the same fields the wizard pages
1-3 collect. On save, secrets are written to keyring, the row is
created, and the original action proceeds.

Subsequent clicks skip the dialog. The dialog is also reachable later
from a small "Edit Connection" link in the upgrade and recovery
dialogs, in case credentials change.

### 6.3 Upgrade flow

The four phases (pre-flight, backup, upgrade, verify) and version
helpers from the implemented `espo_impl/core/upgrade_manager.py` port
verbatim into `automation/core/deployment/upgrade_ssh.py`, taking
`InstanceDeployConfig` instead of the legacy `DeployConfig`.

`VersionCheckWorker` fires on `instance_changed` from the picker, runs
in the background, and persists detected versions into
`InstanceDeployConfig`. The instance picker header shows
"EspoCRM 8.4.0 → 8.5.1 available" or "up to date" accordingly.

Major-version warning modal stays as designed.

Backups are retained at 3 most recent on the server.

### 6.4 Recovery flow

Two operations port from `espo_impl/ui/recovery_dialog.py`:

1. **Admin credentials reset** — SSH-driven SQL UPDATE on the
   `user` table inside the `espocrm-db` MariaDB container. Updates
   `Instance.username`/`password` after success.
2. **Full database reset** — `docker compose down --volumes`,
   `rm -rf /var/www/espocrm`, then re-runs Phase 2 (installer),
   Phase 3 (post-install), Phase 4 (verify). Re-provisions API user
   on the fresh instance.

Both operations require an `InstanceDeployConfig` row.

### 6.5 Scenario gating (strict)

`Upgrade EspoCRM` and `Recovery & Reset` buttons are visible only when
the active instance's `InstanceDeployConfig.scenario = 'self_hosted'`
(or no row exists yet — in which case the click triggers the backfill
dialog, which itself only allows `'self_hosted'`).

For cloud-hosted and bring-your-own instances the buttons are hidden,
not disabled. (Per project convention, buttons are never grayed —
they're either shown with a meaningful click action or absent.)

---

## 7. UI integration

### 7.1 Deploy entry — header row

```
[Start Deploy Wizard]   [Upgrade EspoCRM]   [Recovery & Reset]
```

Upgrade and Recovery buttons hidden when no instance is selected or
scenario is not `'self_hosted'`.

### 7.2 Instance picker — header

The `InstancePicker` widget gains a status row beneath the picker
itself, showing two badges sourced from `InstanceDeployConfig`:

```
EspoCRM 8.4.0 → 8.5.1 available     SSL valid (87 days)
```

`VersionCheckWorker` and `CertCheckWorker` both kicked off from
`_on_instance_changed` (`deployment_window.py`).

---

## 8. Legacy cleanup

After PR 3 lands, delete in PR 4:

- `espo_impl/core/deploy_manager.py`
- `espo_impl/core/upgrade_manager.py`
- `espo_impl/workers/deploy_worker.py`
- `espo_impl/workers/upgrade_worker.py`
- `espo_impl/ui/deploy_panel.py`
- `espo_impl/ui/deploy_dashboard.py`
- `espo_impl/ui/upgrade_dashboard.py`
- `espo_impl/ui/deploy_wizard.py`
- `espo_impl/ui/recovery_dialog.py`
- `tests/test_deploy_manager.py`
- The `data/instances/{slug}_deploy.json` JSON file convention is
  retired — covered by the new table and keyring.

The exploration confirmed nothing in `automation/`, `espo_impl/main.py`,
or `espo_impl/ui/main_window.py` imports any of these. Safe to remove
in one commit at the end of the cycle.

---

## 9. Testing

- **Schema migration**: apply `_client_v9` to a v8 DB; verify table,
  FK, UNIQUE on `instance_id`, CHECK constraints. Mirrors the style in
  `tests/db/test_client_migrations.py`.
- **Secrets store**: round-trip put/get/delete; keyring backend mocked
  via `keyring.set_keyring(InMemoryKeyring())`.
- **Wizard persistence**: given a successful `SelfHostedConfig` run,
  assert both `Instance` and `InstanceDeployConfig` rows exist in the
  same transaction; assert secrets in keyring; assert no plaintext
  secrets in the DB.
- **Backfill flow**: instance without deploy config → click Upgrade →
  dialog appears → save → table populated → second click skips.
- **Upgrade phases**: port the existing 24 tests from
  `tests/test_upgrade_manager.py` against the new module signatures.
- **Recovery operations**: mock SSH, assert correct command sequencing
  (admin reset SQL string, full-reset teardown commands), assert
  `Instance` updates after admin reset.
- **Scenario gating**: verify Upgrade/Recovery buttons hidden when
  scenario != 'self_hosted'.
- **Manual integration**: one end-to-end run against the CBM test
  Droplet covering deploy → version badge populates → upgrade →
  version increments → backup paths populate → cert badge still works
  → admin credential reset → full reset.

---

## 10. Sequencing

Each phase shippable on its own; no half-finished states.

| PR | Scope | Estimate |
|----|-------|----------|
| 1 | Foundation: migration `_client_v9`, `secrets.py` + keyring dependency, `deploy_config_repo.py`, schema + secrets tests | ~1 day |
| 2 | Wizard persistence: hook into `wizard_logic.py`, `ConnectionConfigDialog` for backfill, persistence + backfill tests | ~½ day |
| 3 | Upgrade port: `upgrade_ssh.py`, `upgrade_worker.py`, `upgrade_dialog.py`, button + version badge wiring, port the 24 phase tests | ~1 day |
| 4 | Recovery port: `recovery_ssh.py`, `recovery_worker.py`, `recovery_dialog.py`, button wiring, recovery tests | ~1 day |
| 5 | Legacy cleanup: delete the 9 orphaned files + legacy tests | ~½ day |

**Total: ~4 days work** to land Upgrade and Recovery end-to-end.

---

## 11. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Keyring unavailable in headless environments (CI, Docker without dbus) | Provide `KEYRING_DISABLE=1` env var that falls back to a clearly-marked plaintext store **for tests only**; production code paths require a real backend. CI uses the in-memory keyring shim. |
| `InstanceDeployConfig` row leaks if Instance is deleted | Add `ON DELETE CASCADE` on the FK; row deletion also calls `delete_secret` for both refs. |
| Wizard runs to completion but DB write fails midway | Wrap Instance + InstanceDeployConfig + secret writes so secrets are persisted *last*; if the DB fails, no orphan secrets. If keyring fails, abort before DB commit. |
| User changes SSH key / DB root password out-of-band | "Edit Connection" link in upgrade and recovery dialogs lets them re-enter and update the secrets and table row. |
| Dead-code references in archived prompts (`PRDs/_archive/`) | Leave as-is; they're archived for historical context and not run. |

---

## 12. Open items

None — keyring-from-v1, recovery-this-cycle, and strict self-hosted
gating are confirmed.

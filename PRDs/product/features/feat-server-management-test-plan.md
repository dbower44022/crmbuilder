# Server Management — Manual Integration Test Plan

**Companion to:** `feat-server-management.md`
**Purpose:** End-to-end validation of the deploy / upgrade / recovery
flows against a real DigitalOcean Droplet. Runs the code paths that
unit tests can only mock.
**Last Updated:** May 2026

---

## Pre-flight

| | Item |
|---|---|
| ☐ | A throwaway DigitalOcean Droplet exists (Ubuntu 22.04 LTS, 2 GB RAM minimum) |
| ☐ | A subdomain DNS A record points to the Droplet IP and has propagated |
| ☐ | SSH key pair is on disk; the public key is on the Droplet |
| ☐ | CRM Builder app launches via `uv run crmbuilder` and the Deployment tab opens |
| ☐ | An active client is selected (Clients tab) |
| ☐ | Master keyring is unlocked on your machine (Linux: gnome-keyring/kwallet running; macOS: Keychain unlocked; Windows: Credential Manager available) |

If you do not have a throwaway Droplet, **skip Section 4 (Full Reset)**
— it is destructive and must only run against an environment whose
data you can lose.

---

## 1. Deploy + persistence (~15 min)

The wizard already worked before this cycle. What's new is that
`InstanceDeployConfig` should be persisted on success.

| | Step | Expected |
|---|---|---|
| ☐ | Click **Deployment** tab → **Deploy** sidebar entry → **Start Deploy Wizard** | Wizard opens at Page 0 |
| ☐ | Walk pages 0-3 with the test Droplet's details | All form validation passes |
| ☐ | Click **Save & Deploy** → wait for all phases to complete | "Deployment completed successfully!" |
| ☐ | Open the per-client SQLite DB (path under `<project_folder>/.crmbuilder/`) and run `SELECT * FROM InstanceDeployConfig` | One row exists; `instance_id` matches the deployed instance |
| ☐ | Inspect that row's `ssh_credential_ref` and `db_root_password_ref` | Both are `crmbuilder:<uuid>` strings — **not** plaintext |
| ☐ | Confirm the actual secrets are in the keyring | Linux: `secret-tool search service crmbuilder`; macOS: search Keychain.app for "crmbuilder" |
| ☐ | Restart the app, reselect the instance | Deploy panel reopens without errors |

**Success criteria:** Row exists; secrets are keyring-resolved; no
plaintext credentials in the DB.

---

## 2. Version badge + upgrade (~10 min)

Pre-condition: a self-hosted instance with `InstanceDeployConfig` (from §1).

| | Step | Expected |
|---|---|---|
| ☐ | Select the deployed instance from the Active Instance picker | A version badge appears under the dropdown ("EspoCRM X.Y.Z — up to date" *or* "→ A.B.C available") |
| ☐ | Wait ~5 seconds for `VersionCheckWorker` to refresh | Badge text matches reality (compare to https://www.espocrm.com/downloads/) |
| ☐ | If "up to date": SSH to the Droplet and **manually downgrade** by editing `data/state.php` to a lower version (`docker compose exec espocrm sed -i ...`); reselect the instance. The detector probes `state.php` first, then `config-internal.php`, `Application.php`, and finally legacy `config.php` | Badge flips to "→ A.B.C available" |
| ☐ | Click **Deploy** sidebar → **Upgrade EspoCRM** button | Modal opens; phase cards visible; "Run Upgrade" enabled |
| ☐ | Click **Run Upgrade** | Phase 1: pre-flight checks pass; logs stream into the dialog |
| ☐ | Watch Phase 2: backup | `/var/backups/espocrm/<timestamp>/db.sql.gz` and `data.tar.gz` appear; SSH and `ls -la /var/backups/espocrm/` confirms |
| ☐ | Watch Phase 3: upgrade | Pre-upgrade chown of `/var/www/html` to `www-data:www-data` runs first; then `php command.php upgrade -y` runs to completion; new version reads back. Note: EspoCRM's CLI upgrades one minor/patch step per invocation — the routine deliberately doesn't loop to the latest |
| ☐ | Watch Phase 4: verification | All four checks PASS |
| ☐ | Close the dialog; check the picker badge | Badge updates to "up to date" with new version |
| ☐ | Re-open the SQLite DB | `current_espocrm_version`, `last_upgrade_at`, `last_backup_paths` are populated |

**Success criteria:** Backups land on disk; CLI upgrader exits 0; badge
refreshes; DB state matches what happened on the server.

**Failure modes to watch:**
- Backup fails because `/var/backups/espocrm` lacks permissions → `mkdir -p` should handle, but check
- `get_latest_version()` calls GitHub's `api.github.com/repos/espocrm/espocrm/releases/latest` and reads `tag_name`. If GitHub rate-limits the IP (60 req/hour unauthenticated), the worker falls back to the stored `latest_espocrm_version` — symptom is a stale "up to date" badge despite a newer release being out
- Phase 3's pre-upgrade chown needs root inside the espocrm container; if the container's root user is locked down, the chown step aborts before any destructive action
- Version detection probes `data/state.php` → `data/config-internal.php` → `application/Espo/Core/Application.php` → `data/config.php`; if all miss, Phase 1 dumps a directory listing to the log so the actual file layout is visible
- `mariadb-dump` may not exist if the image switched to plain `mysqldump` — check the espocrm-db container

---

## 3. Backup retention (~3 min)

| | Step | Expected |
|---|---|---|
| ☐ | Run upgrade flow 4 times in a row (the upgrade itself is idempotent — once it's at the latest version it'll cleanly say "no upgrade available" but you can stub a downgrade between runs) | After each run, `ls /var/backups/espocrm/` count grows |
| ☐ | After the 4th run, count the backup directories | Exactly **3** remain (oldest is gone) |
| ☐ | Inspect `last_backup_paths` in `InstanceDeployConfig` | Three paths matching the three remaining server directories |

**Success criteria:** Retention is exactly 3, oldest pruned.

---

## 4. Recovery — admin credential reset (~5 min)

| | Step | Expected |
|---|---|---|
| ☐ | Click **Deploy** sidebar → **Recovery && Reset** button | Modal opens with two cards |
| ☐ | In the **Reset Admin Credentials** card, enter a new username (e.g. `admin2`) and a new password | Both fields populated |
| ☐ | Click **Reset Admin Credentials** → confirm in the dialog | Worker runs; "Admin credentials reset successfully" |
| ☐ | Browse to `https://<your-domain>` and try logging in with the **old** admin password | Should fail |
| ☐ | Log in with the **new** username + password | Should succeed |
| ☐ | Inspect `Instance.username` and `Instance.password` in the SQLite DB | Both updated to new values |

**Success criteria:** Old credentials fail, new ones work, DB is in sync.

**Failure modes:**
- `mariadb` CLI not present in container — would fail; check container image
- MD5 password hash format may not match newer EspoCRM versions; if login still fails after the SQL UPDATE returns 0, check the `password` column directly to see if EspoCRM expects bcrypt now

---

## 5. ⚠️ Recovery — full database reset (~15 min, **DESTRUCTIVE**)

**STOP** if this is a production Droplet. This step nukes all data.

| | Step | Expected |
|---|---|---|
| ☐ | (Optional) Create a test record in EspoCRM you'll know to look for after | Record visible in EspoCRM UI |
| ☐ | Click **Deploy** sidebar → **Recovery && Reset** | Modal still open or reopen |
| ☐ | In the **Full Database Reset** card, enter new admin user/pass | Fields populated |
| ☐ | Type anything except `DELETE ALL DATA` in the confirm box | Run button stays disabled |
| ☐ | Type exactly `DELETE ALL DATA` | Run button enables (red) |
| ☐ | Click **Run Full Reset** → confirm in the warning dialog | All four phases run |
| ☐ | Phase 1: teardown | `/var/www/espocrm` is removed on the server (verify via `ls /var/www/`) |
| ☐ | Phase 2: install | New EspoCRM containers start up |
| ☐ | Phase 3: post-install | Cert read; cert_expiry_date persisted |
| ☐ | Phase 4: verification | All checks PASS |
| ☐ | Browse to the URL and log in with the new credentials | Login works |
| ☐ | Look for the test record you created earlier | Gone — confirms data was wiped |

**Success criteria:** Full teardown + reinstall succeeds; old data gone;
new admin works.

**Failure modes:**
- Let's Encrypt rate limit if you've redeployed too many times this week — wait or use a different subdomain
- `phase_install_espocrm` uses `--clean` which should be safe after teardown, but if it complains about leftover state, the rm -rf may not have caught everything

---

## 6. Self-hosted gate (~5 min)

| | Step | Expected |
|---|---|---|
| ☐ | Add a second instance via the wizard, this time selecting **Cloud-Hosted** scenario | Wizard finishes with a connectivity check, no SSH involved |
| ☐ | Select that instance in the picker | **No** version badge appears under the dropdown |
| ☐ | Look at the **Deploy** sidebar entry | **Upgrade EspoCRM** and **Recovery & Reset** buttons are hidden (only Start Deploy Wizard visible) |
| ☐ | Switch back to the self-hosted instance | Both buttons reappear |

**Success criteria:** Buttons truly absent for cloud-hosted, not just disabled.

---

## 7. Backfill flow (~5 min)

Simulates an instance that was deployed before this layer existed.

| | Step | Expected |
|---|---|---|
| ☐ | In SQLite, manually delete the InstanceDeployConfig row for one of your self-hosted instances: `DELETE FROM InstanceDeployConfig WHERE instance_id = ?` | Row gone |
| ☐ | Reselect that instance in the picker | Version badge is "EspoCRM version: unknown" |
| ☐ | Click **Upgrade EspoCRM** | `ConnectionConfigDialog` opens (NOT the upgrade dialog) |
| ☐ | Cancel the dialog | Upgrade flow aborts |
| ☐ | Click **Upgrade EspoCRM** again, fill in the form correctly, Save | Upgrade dialog opens with the new config |
| ☐ | Verify a row now exists in InstanceDeployConfig | Row present |
| ☐ | Click **Upgrade EspoCRM** a third time | Upgrade dialog opens immediately (no backfill) |

**Success criteria:** Backfill triggered, then bypassed once persisted.

---

## 8. Negative paths (~10 min)

| | Step | Expected |
|---|---|---|
| ☐ | Stop the EspoCRM container on the Droplet (`docker compose stop espocrm`), then click **Upgrade EspoCRM** → **Run Upgrade** | Phase 1 fails: "EspoCRM container is not running" |
| ☐ | Restart the container; fill the disk on the Droplet to >98% (`fallocate -l 95G /tmp/big`); click Upgrade | Phase 1 fails on disk-space check |
| ☐ | `rm /tmp/big`; with the container fully wedged, run admin credential reset | Should fail with a meaningful error, **not** a Python traceback |
| ☐ | Disconnect the Droplet's SSH (stop the SSH server) and click Upgrade | Worker shows "SSH connection failed: ..." in red |

**Success criteria:** All failures surface as user-readable errors, not stack traces.

---

## 9. Sign-off

| | Item |
|---|---|
| ☐ | All checks above passed (or any deviations are documented) |
| ☐ | No plaintext secrets observed in any log line, command echo, or DB column |
| ☐ | Deviations or follow-ups recorded as issues / TODOs in the repo |

If anything failed, file the failure mode in this checklist next to
the step that broke and either fix the code or downgrade the spec.

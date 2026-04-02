# Claude Code Prompt: Add Recovery Tools Screen to CRM Builder

## Context

Read `CLAUDE.md` and `espo_impl/ui/deploy_dashboard.py` before starting. This
prompt adds a Recovery Tools screen to the existing PySide6 deployment tool.
Do not modify any existing functionality — add only what is specified here.

Key files to understand before implementing:
- `espo_impl/core/models.py` — `DeployConfig` and `InstanceProfile` dataclasses
- `espo_impl/core/deploy_manager.py` — SSH execution, phase logic, credential masking
- `espo_impl/workers/deploy_worker.py` — QThread worker with `start_phase` parameter
- `espo_impl/ui/deploy_dashboard.py` — Dashboard layout, phase cards, action buttons

### Verified environment details

The following have been verified against the deployed test instance:

- **Docker compose path:** `/var/www/espocrm/docker-compose.yml` (confirmed)
- **Database engine:** MariaDB (`mariadb:latest`) — use `mariadb` as the
  CLI command, **not** `mysql`
- **User table:** `user` (singular, not `users`)
- **Admin identification:** There is **no `is_admin` column**. Admin status is
  determined by the `type` column with value `'admin'`.
- **User type values:** `admin`, `api`, `regular`, `system`
- **API users:** Have `type = 'api'`, `auth_method = 'ApiKey'`, and the key
  stored in the `api_key` column
- **Password column:** `password` (varchar 150, hashed)

**Database CLI pattern:**
```bash
docker compose -f /var/www/espocrm/docker-compose.yml exec -T espocrm-db \
  mariadb -u root -p'{db_root_password}' espocrm -e "SQL_STATEMENT"
```

---

## What to Build

Add a **Recovery Tools** screen to the Deployment Dashboard. This screen is accessed
via a clearly labeled "Recovery & Reset" button on the Deployment Dashboard. It
provides two recovery operations:

### Operation 1 — Reset Admin Credentials

Resets the EspoCRM admin username and password directly in the MySQL database
running inside the Docker container. Leaves all data, configuration, and
customizations completely intact.

**User flow:**
1. User clicks "Recovery & Reset" on the Dashboard
2. Recovery Tools screen opens
3. User selects "Reset Admin Credentials"
4. A form appears with three fields:
   - New admin username
   - New admin password
   - Confirm new admin password
5. Validation: password and confirm password must match before proceeding
6. User clicks "Reset Credentials"
7. A confirmation dialog appears: "This will reset the EspoCRM admin credentials.
   Are you sure?" with Cancel and Confirm buttons
8. On confirm: tool connects via SSH, executes the credential reset, reports
   success or failure in a log window on the screen
9. On success: displays the new credentials in a clearly labeled summary panel,
   updates `DeployConfig.admin_username` and `DeployConfig.admin_password`, saves
   the config, and prompts the user to log in and verify access

**Implementation notes:**
- Password fields must be masked
- Use the instance's `DeployConfig` (loaded from `{slug}_deploy.json`) for SSH
  connection details (`droplet_ip`, `ssh_key_path`, `ssh_user`) and database
  credentials (`db_root_password`)
- Connect via SSH using `connect_ssh()` from `deploy_manager.py`
- The MariaDB database runs inside the `espocrm-db` Docker container —
  execute SQL via `docker compose exec` using the `mariadb` client (not `mysql`):
  ```bash
  docker compose -f /var/www/espocrm/docker-compose.yml exec -T espocrm-db \
    mariadb -u root -p'{db_root_password}' espocrm -e "SQL_STATEMENT"
  ```
- EspoCRM stores passwords as MD5 hashes — use `MD5()` in the SQL UPDATE
  (this is EspoCRM's internal storage format, not a design choice)
- Target the admin user by `type = 'admin'` and `deleted = 0` (there is no
  `is_admin` column — admin status is determined by the `type` column)
- Example SQL:
  ```sql
  UPDATE user
  SET user_name = 'newusername',
      password = MD5('newpassword')
  WHERE type = 'admin'
    AND deleted = 0
  LIMIT 1;
  ```
- Mask all credential values before emitting to the log window — use the same
  `mask_credentials()` pattern from `deploy_manager.py`

---

### Operation 2 — Full Database Reset

Tears down the Docker EspoCRM installation and re-runs the installer to restore
a clean working instance. All data, contacts, custom fields, and configuration
are permanently destroyed.

**User flow:**
1. User selects "Full Database Reset" on the Recovery Tools screen
2. A warning panel appears in red with the text:
   "WARNING: This will permanently delete ALL data in the CRM including all
   entities, records, custom fields, and configuration. This cannot be undone."
3. Below the warning, a text input field with the label:
   "Type RESET to confirm"
4. The "Proceed with Full Reset" button is always enabled (per project
   convention: buttons are never disabled). If the user clicks it without
   typing "RESET" exactly (case-sensitive), show a message:
   "You must type RESET in the confirmation field to proceed."
5. On clicking "Proceed with Full Reset" with valid confirmation:
   a. A final confirmation dialog appears:
      "Are you absolutely sure? All CRM data will be permanently deleted."
      with Cancel and I Understand — Delete Everything buttons
   b. On confirm: the reset sequence begins
6. Reset sequence (shown step by step in the log window):
   a. Connect via SSH using the configured SSH user from `DeployConfig`
   b. Stop and remove all EspoCRM Docker containers and volumes:
      `docker compose -f /var/www/espocrm/docker-compose.yml down --volumes`
   c. Remove the installation directory: `rm -rf /var/www/espocrm`
   d. Automatically re-run Phase 2 (EspoCRM Installation) through Phase 4
      (Verification) using the existing `DeployWorker` with `start_phase=2`
      — reuse the exact same implementation, do not duplicate it
7. Display verification results on completion
8. On any step failure: log the error clearly, halt, do not attempt to continue

**Implementation notes:**
- Reuse the existing phase implementations in `deploy_manager.py`
  (`phase2_install_espocrm`, `phase3_post_install`, `phase4_verify`) via
  `DeployWorker` — do not duplicate deployment logic
- Use the instance's `DeployConfig` for all connection details and credentials
- The log window must stream output live as each step executes, same as
  the main Deployment Dashboard log window — connect to the same signals
  (`log_line`, `phase_started`, `phase_completed`, `phase_failed`)
- After successful completion, `DeployConfig.deployed_at` and
  `DeployConfig.cert_expiry_date` will be updated by the existing Phase 3 logic

**Post-reset API user provisioning:**
A Full Database Reset destroys all EspoCRM data including API user records.
The API key stored in the `InstanceProfile` will no longer be valid after
the reset. To avoid requiring manual setup after every reset, the tool must
automatically restore the CRM Builder connection.

After Phase 4 (Verification) completes successfully:

1. **Create an API user via the EspoCRM REST API.** Use Basic auth with the
   admin credentials from `DeployConfig` (`admin_username`, `admin_password`)
   against the instance URL (`https://{full_domain}`). Make a POST request to
   `/api/v1/User` with:
   ```json
   {
     "userName": "crmbuilder-api",
     "type": "api",
     "authMethod": "ApiKey",
     "apiKey": "<generated-key>",
     "isActive": true
   }
   ```
   Generate the API key using `secrets.token_urlsafe(32)`. An API user with
   `type: "api"` is verified to match the schema — existing API users in the
   test instance use this type with `authMethod: "ApiKey"` and the key stored
   in the `api_key` column.

2. **Update the `InstanceProfile`.** Set:
   - `auth_method` = `"api_key"`
   - `api_key` = the generated API key
   - Clear `secret_key` (not needed for API key auth)

   Save the updated profile using `_save_instance()` via the instance panel,
   or write directly to `{instances_dir}/{slug}.json` using the same JSON
   format as `InstancePanel._save_instance()`.

3. **Display a summary** in the log window:
   ```
   API user 'crmbuilder-api' created successfully.
   Instance profile updated with new API key.
   Ready to run program files.
   ```

4. **If API user creation fails** (e.g., EspoCRM is not yet fully
   initialized), fall back to updating the `InstanceProfile` to use Basic
   auth with the admin credentials from `DeployConfig`:
   - `auth_method` = `"basic"`
   - `api_key` = `DeployConfig.admin_username`
   - `secret_key` = `DeployConfig.admin_password`

   Display a notice:
   > "Could not create API user automatically. The instance profile has been
   > switched to Basic auth using admin credentials. You can create an API
   > user manually later through the EspoCRM administration panel."

This ensures the Full Database Reset is a one-click operation for test
environments — no manual credential setup is required afterwards.

---

## Operation Logging

Every recovery operation must write a detailed log file to `data/recovery_logs/`
in addition to streaming output to the UI log window.

**Log file naming:**
```
data/recovery_logs/recovery-YYYY-MM-DD-HH-MM-SS.log
```

**Log file content — required for every operation:**

```
CRM Builder — Recovery Log
===========================
Timestamp:   YYYY-MM-DD HH:MM:SS
Instance:    [instance name]
Operation:   Reset Admin Credentials | Full Database Reset
Server IP:   [droplet_ip from DeployConfig]
Domain:      [full_domain from DeployConfig]

--- Operation Steps ---
[HH:MM:SS] STARTED  <step description>
[HH:MM:SS] OK       <step description>
[HH:MM:SS] FAILED   <step description>
            Error:   <error message>
            Command: <command that failed, with credentials masked>

--- Result ---
COMPLETED | FAILED

[If Reset Admin Credentials — COMPLETED:]
New admin username: <username>
Note: Password not logged for security.

[If Full Database Reset — COMPLETED:]
Phase 2 reinstallation: COMPLETED
Phase 3 post-install:   COMPLETED
Phase 4 verification:   COMPLETED | FAILED
  [list each verification check and its result]

[If any operation — FAILED:]
Failed at step: <step description>
Error detail:   <full error output, with credentials masked>
```

**Logging requirements:**
- The `data/recovery_logs/` directory must be created automatically if it does
  not exist (use `pathlib.Path.mkdir(parents=True, exist_ok=True)`)
- Passwords must never appear in log files under any circumstances — apply
  `mask_credentials()` to all command strings and error output before writing
- Each step must be logged as it executes — do not buffer and write at the end
- The log file must be written even if the operation fails partway through
- On completion, display the log file path in the UI so the user can find it

---

## File Changes Required

- **New file:** `espo_impl/ui/recovery_dialog.py` — Recovery Tools screen (PySide6
  dialog, following the same pattern as `import_dialog.py` and `deploy_wizard.py`)
- **Modified file:** `espo_impl/ui/deploy_dashboard.py` — add "Recovery & Reset"
  button that opens the Recovery Tools dialog. Make minimal changes only — add the
  button and the handler, nothing else.
- **Modified file:** `.gitignore` — add `data/recovery_logs/` entry if not already
  present
- **No changes** to any phase files, deploy_manager.py, deploy_worker.py, models,
  config files, or other UI screens

---

## UI Style Requirements

Match the existing application style exactly:
- Same fonts, colors, spacing, and button styles as the rest of the application
- The "Recovery & Reset" button on the Dashboard must be visually distinct from
  the deployment action buttons — use a muted/secondary style so it does not
  look like a primary action
- The Full Database Reset warning panel must use a red background with white text
- The confirmation input field for "RESET" must be visually prominent
- Log window must use the same dark-background, monospace, color-coded style as
  the Dashboard log window (`LOG_COLORS` from `deploy_dashboard.py`)

---

## Constraints

- Make minimal changes to existing files — only modify `espo_impl/ui/deploy_dashboard.py`
- Do not refactor, reformat, or reorganize any existing code
- Do not change any existing functionality
- Ask for confirmation before removing any existing code
- All new code must follow the same patterns and style as existing code in the project
- Buttons are never disabled — use click handlers that show explanatory messages
  when preconditions are not met
- All credential values must be masked in log output — never log passwords
- Do not add new top-level directories — use `data/recovery_logs/` within the
  existing `data/` directory

# Claude Code Prompt: Add Recovery Tools Screen to CBM CRM Deployment Tool

## Context

Read `PRDs/CBM-PRD-CRM-Deploy.md` and `PRDs/CBM-PRD-CRM-Deploy-Context.md` before
starting. This prompt adds a Recovery Tools screen to the existing PySide6 deployment
tool. Do not modify any existing functionality — add only what is specified here.

---

## What to Build

Add a **Recovery Tools** screen to the Deployment Dashboard. This screen is accessed
via a clearly labeled "Recovery & Reset" button on the Deployment Dashboard. It
provides two recovery operations:

### Operation 1 — Reset Admin Credentials

Resets the EspoCRM admin username and password directly in the MySQL database.
Leaves all data, configuration, and customizations completely intact.

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
9. On success: displays the new credentials in a clearly labeled summary panel
   and prompts the user to log in and verify access

**Implementation notes:**
- Password fields must be masked
- Use the saved config (cbm-crm-dev.yml or cbm-crm-prod.yml) for SSH connection
  details and MySQL credentials
- The MySQL operation must update the `users` table in the EspoCRM database,
  setting `user_name` and `password` (EspoCRM stores passwords as MD5 hash of
  the password string — use MD5() in the SQL UPDATE statement)
- Target the record where `is_admin = 1` and `deleted = 0`
- Example SQL:
  ```sql
  UPDATE users
  SET user_name = 'newusername',
      password = MD5('newpassword')
  WHERE is_admin = 1
    AND deleted = 0
  LIMIT 1;
  ```

---

### Operation 2 — Full Database Reset

Drops and recreates the EspoCRM database, then automatically re-runs Phase 3
(EspoCRM Installation) to restore a clean working instance. All data, contacts,
engagements, custom fields, and configuration are permanently destroyed.

**User flow:**
1. User selects "Full Database Reset" on the Recovery Tools screen
2. A warning panel appears in red with the text:
   "WARNING: This will permanently delete ALL data in the CRM including contacts,
   engagements, mentors, and all configuration. This cannot be undone."
3. Below the warning, a text input field with the label:
   "Type RESET to confirm"
4. The "Proceed with Full Reset" button is disabled until the user has typed
   exactly "RESET" (case-sensitive) in the confirmation field
5. On clicking "Proceed with Full Reset":
   a. A final confirmation dialog appears:
      "Are you absolutely sure? All CRM data will be permanently deleted."
      with Cancel and I Understand — Delete Everything buttons
   b. On confirm: the reset sequence begins
6. Reset sequence (shown step by step in the log window):
   a. Connect via SSH as cbmadmin
   b. Drop the EspoCRM database
   c. Recreate the empty database with the same name
   d. Grant privileges to the EspoCRM database user
   e. Remove /var/www/espocrm directory
   f. Automatically trigger Phase 3 (EspoCRM Installation) from the existing
      phase runner — reuse the exact same Phase 3 implementation, do not
      duplicate it
   g. On Phase 3 completion: run Phase 5 (Verification) automatically
7. Display verification results on completion
8. On any step failure: log the error clearly, halt, do not attempt to continue

**Implementation notes:**
- Reuse the existing `phase3_espocrm.py` and `phase5_verify.py` — do not
  duplicate deployment logic
- Use the saved config for all connection details, database name, user,
  and passwords
- The log window must stream output live as each step executes, same as
  the main Deployment Dashboard log window

---

## File Changes Required

- **New file:** `ui/recovery.py` — Recovery Tools screen (PySide6)
- **Modified file:** `ui/dashboard.py` — add "Recovery & Reset" button that
  opens the Recovery Tools screen. Make minimal changes only — add the button
  and the navigation call, nothing else.
- **No changes** to any phase files, config files, or other UI screens

---

## UI Style Requirements

Match the existing application style exactly:
- Same fonts, colors, spacing, and button styles as the rest of the application
- The "Recovery & Reset" button on the Dashboard must be visually distinct from
  the deployment action buttons — use a muted/secondary style so it does not
  look like a primary action
- The Full Database Reset warning panel must use a red background with white text
- The confirmation input field for "RESET" must be visually prominent
- Disabled state of the "Proceed with Full Reset" button must be visually obvious

---

## Constraints

- Make minimal changes to existing files — only modify `ui/dashboard.py`
- Do not refactor, reformat, or reorganize any existing code
- Do not change any existing functionality
- Ask for confirmation before removing any existing code
- All new code must follow the same patterns and style as existing code in the project

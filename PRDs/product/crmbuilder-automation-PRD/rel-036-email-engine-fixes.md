# REL-036 — EspoCRM activity-parent & email-account engine fixes

**Release:** REL-036 (manual) · **Project:** PRJ-073 · **Date:** 2026-06-30
Follow-on engine fixes from the CBM email-send incident (06-27/28).

## PI-348 — Register entities as Email activity parents (REQ-388)

**Symptom:** composing an email from a custom entity's detail view was rejected by
backend parent validation, because the activity-panel deploy registered entities
as parents of Meeting/Call/Task only.

**Cause:** the registration + verification paths defaulted their `holders` to
`PANEL_HOLDERS = ("Meeting", "Call", "Task")` — the visible-panel holders, which
deliberately omit Email (Email isn't needed for the *panels* to render).

**Fix:** default the registration/verification `holders` to
`PARENT_HOLDERS = ("Meeting", "Call", "Task", "Email")` in
`deploy_activity_panels` and `register_activity_parents`, so the deploy adds each
entity to the **Email** parent list too — keeping the platform's standard parents
(`union_parent_list`). The panel-render manager defaults (`is_registered`,
`wait_until_registered`) stay on `PANEL_HOLDERS`, since the visible panels only
need Meeting/Call/Task; the deploy passes `PARENT_HOLDERS` explicitly for the
registration write and its post-rebuild verification.

**Verified:** unit tests assert the deploy registers against Email and that the
per-holder writer registers all four holders. Live acceptance (compose an email
from the entity's detail view; re-audit shows the entity in the Email parent list)
is an operator step against a deployed instance.

## PI-349 — Email-account setup with provider folder resolution (REQ-389)

**Requirement:** the Configure pipeline must be able to provision an outgoing email
account and set its Sent / Trash / Drafts folders to the mail provider's **real**
folder paths, discovered by listing the account's mailboxes — **never guessed** (a
wrong folder makes a delivered message fail to file with a folder-not-found error).

**Built (new capability):**
- `espo_impl/core/email_folders.py` — the pure, deterministic resolver. Parses IMAP
  `LIST` output and resolves each role by the RFC 6154 SPECIAL-USE attribute
  (`\Sent`/`\Trash`/`\Drafts`) first, then a fixed set of well-known folder names
  (matched case-insensitively on the mailbox's final path segment; covers Gmail,
  Outlook/Exchange, Dovecot/cPanel, generic IMAP). A role that matches neither
  resolves to **`None`** — the "never guess" guarantee.
- `automation/core/deployment/email_account_setup.py` — the I/O orchestrator.
  `discover_folders` connects over IMAP (client injectable for tests) and `LIST`s
  the mailboxes; `configure_email_account` discovers the folders and then
  **create-or-updates** the EspoCRM `EmailAccount` over REST with the resolved
  paths. If any of Sent/Trash/Drafts is unresolved it **refuses to write** and
  reports the unresolved roles rather than setting a guessed value. The EspoCRM
  folder attribute names live in one `_FOLDER_FIELDS` constant for easy correction
  across versions.

**Verified:** unit tests cover SPECIAL-USE resolution, the known-name fallback,
the never-guess `None` path, IMAP `LIST` parsing, idempotent create-vs-update, and
the refuse-to-write-when-unresolved behaviour (IMAP + REST faked).

**Scope boundary (explicit — not a silent cap):**
- The live acceptance step — a real test send files a copy to the Sent folder with
  no folder-selection error in the instance log — is an **operator verification**
  against a deployed instance (it needs real credentials + a live send), not a unit
  test.
- `configure_email_account` is a **standalone, pipeline-callable capability**
  (satisfying "the Configure pipeline must be able to provision…"). Wiring it to a
  specific desktop action / Configure worker is a follow-on, mirroring how the
  activity-panel deploy capability is invoked.

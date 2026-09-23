# Phase 2 kickoff — recovery

| Field | Value |
|---|---|
| Title | Phase 2 kickoff — recovery |
| Last Updated | 09-22-26 23:22 |
| Revision | 1.0 |
| Status | Ready to run. Capabilities 1 and 2 of phase 2 are merged and pushed (PI-556, PI-557). |
| Governs | One session's work: absorbing version 1's two recovery operations into version 2's deploy package |
| Source | `phase-2-server-lifecycle-kickoff.md` §3 item 3; the version 1 capability inventory, area 4a rows "Reset the administrator login" and "Wipe an instance and rebuild it from clean"; PRJ-125; TOP-119 |

## Opening answer

Paste this as the first line of the new session so the session-open hook
classifies it:

> Opening answer: Absorb version 1's recovery into version 2 — the administrator login reset and the clean rebuild — so version 2 can rescue an instance without calling version 1.

---

## 1. What this session delivers

Version 2 can rescue a self-hosted instance in two ways, without calling
version 1:

1. **Reset the administrator login.** The instance is healthy, but nobody can
   sign in as administrator. A new administrator username and password are
   written directly into the platform's database.
2. **Rebuild the instance from clean.** The containers and their data volumes
   are removed and the platform is installed again on the same server, with
   fresh application credentials. **This destroys every record on the
   instance.**

Both operations are written as code a caller drives. The screens that drive them
are area 4b work and are not part of this session. That matches what PI-557 did
for the upgrade.

"Done" means both operations are merged and pushed to `main`, and nothing in
version 2 imports `automation.core.deployment.recovery_ssh`.

## 2. Governance comes first

The inventory lists these as **two capabilities**. The phase rule is one
requirement per absorbed capability, so this session needs:

- **Two requirements**, each with provenance, each confirmed by an approving
  decision. A status edit is not an approval.
- **Two planning items** in PRJ-125, each implementing one requirement.
- One branch, `absorb/recovery`, and every code commit carrying
  `Governed-By: PI-NNN` for the planning item it implements.

Model them on REQ-639 and PI-557. REQ-639's acceptance summary names what the
running code proves and must keep. It also states that proving the code against
a real instance is the product owner's step. Both recovery requirements need the
same sentence.

**Push before resolving.** In the last session, both planning items were marked
Resolved before their commits were pushed. The push hook's governance gate then
flagged every code commit, because code cannot land against a Resolved planning
item. The gate is in warn mode today. In enforce mode, that order blocks the
push. The order is: merge, push, then mark the planning item Resolved, with a
resolution reference that says the commit is pushed.

## 3. What to read before writing anything

- **Version 1 code:** `automation/core/deployment/recovery_ssh.py` (164 lines),
  `automation/ui/deployment/recovery_worker.py` (261 lines, holding the order of
  the full rebuild and the credential writes afterwards), and
  `automation/ui/deployment/recovery_dialog.py` (348 lines, holding the
  typed-phrase gate).
- **Version 2 code the rebuild reuses:** `crmbuilder-v2/src/crmbuilder_v2/deploy/ssh.py`
  already owns `phase_install_espocrm`, `phase_post_install`, `phase_verify` and
  `mask_secrets`. **Do not port version 1's copies.** `deploy/upgrade.py` holds
  the pattern to follow: `_require_deploy_config`, `_connected`, the entry points
  that write to the store, and `phase2_backup`.
- **Where credentials live in version 2:** `segments/operate/models.py`, the
  record of each instance's server details. The columns are `admin_username`,
  `admin_password_ref`, `db_password_ref` and `db_root_password_ref`. Secrets
  are Fernet-encrypted in the shared store through `crmbuilder_v2/secrets.py`,
  not in the operating system's keyring.

## 4. What the version 1 code gets wrong, or may get wrong

Read the code before trusting the inventory, and read the instance before
trusting the code. Each item below states how strongly it is held.

**1. The password hash is probably wrong. Inferred, not checked.** Version 1
writes `password = MD5('<new password>')` and says MD5 is the platform's stored
format. Current releases of the platform are believed to hash with a salted
algorithm. If they do, an MD5 reset writes a password that never matches, the
command exits 0, and the log reports success. That is the "silence is the
defect" shape. **Before porting, read a real instance:** check the stored
format in the `user` table, and check whether the platform's own command-line
tool has a set-password command. If it has one, that command is the reset to
port, for the same reason the upgrade runs the platform's own upgrader.

**2. Values are pasted unquoted into the database statement and the shell
command. Verified in the code.** A username or password containing a quote
breaks the command. A crafted one changes it. The port must quote every value.

**3. The database administrator's password goes on the command line. Verified
in the code.** The reset passes it as `-p'<password>'`, so anyone on the host
who can list processes can read it. The upgrade already passes it in the
environment as `MYSQL_PWD` (`deploy/upgrade.py`, `phase2_backup`). Do the same
here.

**4. Which administrator is reset is decided silently. Verified in the code.**
`WHERE type = 'admin' AND deleted = 0 LIMIT 1` picks one administrator without
saying which. With two administrators, the one reset may not be the one locked
out. The port must name the account it will reset, or refuse when more than one
matches.

**5. The administrator password is also version 2's access credential.
Verified in the model's own comment.** The same password backs the instance's
basic-auth credential. A reset that updates the platform and not the store
leaves version 2 unable to reach the instance it just rescued. Version 1
updated its own instance row afterwards. The version 2 port must update both
`admin_password_ref` and the instance's stored credential, and a failure
between the two must be reported rather than left silent.

**6. The rebuild keeps no backup. Verified in the code.** Version 1 tears down
first and installs second. If the install fails, the data is already gone and
nothing can be restored. `phase2_backup` already exists, and running it before
the teardown is the natural fix. That changes version 1's behaviour, so it is
decision A below.

**7. The rebuild may ask for a new certificate. Inferred, not checked.** The
teardown removes `/var/www/espocrm`. The certificate files under
`/etc/letsencrypt` probably survive, but whether the installer reuses them or
requests again is not known. The certificate authority limits duplicate
requests per week. Read what the installer does before relying on either answer.

**8. After a rebuild, the store describes an instance that no longer exists.
Inferred from the design.** The recorded version, backup folders and upgrade
time, and everything version 2 has published onto the instance, describe the
instance before the wipe. The rebuild must refresh what it can read back. It
must also say plainly what it cannot know, rather than leave stale values
looking current.

## 5. Decisions to raise, not settle in passing

Each passes the two-part test. Present each one with the consequential decision
template, and wait for the product owner.

**A. Does a rebuild take a backup first?** The recommendation is yes, using
`phase2_backup`, and refusing to tear down if the backup fails. The cost: a
rebuild takes longer and needs free disk space, and it cannot rescue an instance
whose database is too broken to dump. An explicit override for that case is part
of the question.

**B. Where does the typed-phrase gate live when there is no screen?** Version 1
guards the rebuild with a typed `DELETE ALL DATA` phrase in its dialog. Version 2
has no dialog yet. The recommendation is that the entry point refuses unless the
caller passes the instance's own identifier as a confirmation argument, so the
guard exists in code before any screen does. The cost: every future caller has
to carry the confirmation through, and a screen still needs its own phrase on
top.

**Do not settle this one:** whether a rebuild is a recorded, resumable run like
a deploy run. DEC-1141 left the same question open for the upgrade, and it
belongs with the screens that drive both.

## 6. How to work

- Governance rules are in the store, not in a file. Read them at session start.
- Follow `deploy/upgrade.py`'s shape: steps that report what they learned and
  write nothing, then entry points that open the remote login, drive the steps
  and write through the repository that owns the columns.
- **Build test fixtures from what the server actually returns**, following
  lesson LRN-007. Where a fixture could not be read off a real instance, say so
  at the top of the test file, as `tests/crmbuilder_v2/deploy/test_upgrade.py`
  does.
- The full version 2 test suite runs longer than the ten-minute tool limit. Run
  the deploy tests, the Operate segment tests and
  `tests/crmbuilder_v2/test_version_one_imports.py` in the foreground. Run the
  full suite in the background.
- **Production deploys are human-only.** This session writes code that can wipe
  an instance. It does not wipe one.

## 7. What comes after

Capability 4 in the phase kickoff is version state. The upgrade entry points
already write the version fields, so check how much of capability 4 is still
missing before drafting anything for it. Then come capability 5, reachability,
and capability 6, server inspection.

## Change log

| Revision | Date | Description |
|---|---|---|
| 1.0 | 09-22-26 23:22 | Written at the close of the in-place upgrade session (PI-557, merged as `26d4d5e4` and pushed). Records eight findings from reading version 1's recovery code, two decisions to raise, and the push-before-resolve order. |

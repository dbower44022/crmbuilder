# PI-567 kickoff — wait for a new server's first-boot setup

| Field | Value |
|---|---|
| Title | PI-567 kickoff — wait for a new server's first-boot setup |
| Last Updated | 09-23-26 11:50 |
| Revision | 1.0 |
| Status | Ready to run. REQ-644 is confirmed (DEC-1147), and PI-567 is Draft in PRJ-125. |
| Governs | One session's work: building PI-567, which implements REQ-644 |
| Source | CNV-398, the 09-23-26 live server proof in SES-426; REQ-644; DEC-1147 |

## Opening answer

Paste this as the first line of the new session so the session-open hook
classifies it:

> Opening answer: Build PI-567 — version 2's server preparation waits for a new server's first-boot setup before it uses the package manager, so a fast deploy run never fails on a package lock.

---

## 1. What this session delivers

When version 2 prepares a newly created server, it waits for the server's own
first-boot setup to finish before running any package command. It says in the
log that it is waiting, and when the wait ended. If the wait passes its limit,
the step fails, and the failure names first-boot setup as the cause and Retry as
the remedy. It does not fail with a package-manager error.

"Done" means PI-567 is merged to `main` and pushed, and then marked Resolved.
The order matters, and section 6 explains why.

## 2. Governance is already in place

- **REQ-644** is confirmed, approved by **DEC-1147** on 09-23-26. Its acceptance
  summary is the definition of done. Read it from the store, not from this file.
- **PI-567** is Draft in **PRJ-125** and implements REQ-644. Move it to In
  Progress when the work starts. Every code commit carries
  `Governed-By: PI-567` and names an explicit pathspec.
- No new requirement is needed. If the work shows that REQ-644 is wrong or
  incomplete, stop and raise it with the product owner. Do not widen the work in
  passing.

## 3. The defect, as the live proof met it

Verified on 09-23-26. Run DEP-001 built `proof-5.acmeconstruction.us` on
Ubuntu 24.04, in DigitalOcean region nyc3. DNS resolved in about thirty
seconds, so server preparation reached the brand-new server while Ubuntu's
first-boot setup was still updating packages. The log read:

```
▸ server_prep
$ apt-get -o DPkg::Lock::Timeout=600 update && DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=600 upgrade -
Reading package lists...
E: Could not get lock /var/lib/apt/lists/lock. It is held by process 1230 (apt-get)
E: Unable to lock directory /var/lib/apt/lists/
✗ server_prep: server_prep: Command failed (exit 100): apt-get -o DPkg::Lock::Timeout=600 update && ...
```

Retry resumed at server preparation a few minutes later, and the run completed.

**Why the 08-30 fix did not hold.** On 08-30, `-o DPkg::Lock::Timeout=600` was
added to every `apt-get`. That option makes apt wait for the dpkg lock. It did
not make `apt-get update` wait for the package-list lock,
`/var/lib/apt/lists/lock`: the run above failed at once, not after ten minutes.
The runs before 09-23 were protected only by slower DNS waits.

**The test that should have caught this could not.**
`tests/crmbuilder_v2/deploy/test_ssh.py`,
`test_server_prep_waits_for_the_package_lock_rather_than_failing`, checks that
every package command carries the timeout option. It checks the code agrees
with itself, not that the server waits. That is lesson LRN-007's shape exactly.
Replace it with tests built from the real output above.

## 4. Where the change goes

- **Code:** `crmbuilder-v2/src/crmbuilder_v2/deploy/ssh.py`, function
  `phase_server_prep`. It is a list of commands run in order, stopping at the
  first failure.
- **Tests:** `tests/crmbuilder_v2/deploy/test_ssh.py`, section "Preparing the
  machine". The tests replace `run_remote` with a stand-in that records each
  command and returns an exit code and output.
- **Leave version 1 alone.** `automation/core/deployment/ssh_deploy.py` carries
  the same command. Version 1 is being retired by absorption, and nothing in
  version 2 calls it any more.

### What to check before choosing the wait

These points are inferred, not checked. Settle each one before relying on it.

- **`cloud-init status --wait` blocks until first-boot setup finishes.** Wrapped
  in `timeout`, it gives a bounded wait. Its exit codes differ between
  cloud-init releases. Recent releases are believed to return 2 when setup
  finished with recoverable errors. A non-zero exit therefore does not
  automatically mean "not finished", so read the documentation for the release
  Ubuntu 24.04 ships.
- **cloud-init may not be the only holder of the lock.** Ubuntu's scheduled
  package timers (`apt-daily` and `apt-daily-upgrade`) can start their own
  update in the first minutes. Waiting for cloud-init alone may not be enough.
  A bounded wait on the locks themselves, the package-list lock and the dpkg
  locks, covers both. Consider doing both waits.
- **Whether `DPkg::Lock::Timeout` should stay.** It still helps the commands
  that take the dpkg lock. Removing it is a separate choice. Make that choice
  deliberately, not by accident.

Choose the smallest change that meets REQ-644's acceptance summary. Put the
reason for it beside the code, the way the existing comments do.

## 5. How to work

- **Use a worktree off `main`.** The main folder is shared with other sessions.
  At the time of writing it is on `absorb/recovery`, and other worktrees are in
  use. A branch name such as `fix/first-boot-wait` fits.
- **Sequencing with the recovery branch.** `absorb/recovery` (PI-562 and PI-563,
  commit `3fe5c30e`) also changes `deploy/ssh.py`: `run_remote` gains a
  standard-input parameter, and the installer command quotes every value. It
  does not touch `phase_server_prep`. If recovery has merged when this session
  starts, branch from the updated `main`. If not, expect a small merge in the
  same file.
- **Tests:** run `tests/crmbuilder_v2/deploy/` and
  `tests/crmbuilder_v2/test_version_one_imports.py` in the foreground, and the
  linter on the changed files. The full version 2 suite runs longer than the
  ten-minute tool limit; run it in the background if it is wanted. Its known
  intermittent crash in the desktop tests is lesson LSN-073.
- **Production deploys are human-only.** This session writes the code. It does
  not deploy a server.

## 6. Closing the work

1. Commit on the branch with `Governed-By: PI-567`, then merge to `main` with no
   fast-forward, as PI-556 and PI-557 were.
2. **Push `main` before marking PI-567 Resolved.** The push hook's governance
   gate flags any commit whose planning item is already Resolved when the push
   runs. It warns today, and in enforce mode it would block. The last two
   sessions resolved first and were flagged.
3. Mark PI-567 Resolved with a resolution reference naming the branch commit,
   the merge commit, and that both are pushed.

## 7. Proving it on a real server

That is the product owner's step, and it is not part of this session. The
09-23-26 proof's method works and is recorded in CNV-398:

- a worktree pinned to the commit under test;
- a throwaway local store in its own Postgres container (the SQLite store is
  refused);
- fresh provider tokens, because the proof tokens were revoked afterwards;
- one deploy run on a zone the product owner controls.

The proof passes for REQ-644 when a brand-new server whose DNS resolves at once
gets through server preparation with no Retry, and the log shows the wait.

## 8. What comes after

**PI-568** implements REQ-645: email templates on EspoCRM 10, and audit areas
that report "not checked" instead of a false pass. It is a must, and it must
land before any CBM instance is upgraded to version 10. It begins with two
read-only reads: a version 10 instance, and CBM production.

## Change log

| Revision | Date | Description |
|---|---|---|
| 1.0 | 09-23-26 11:50 | Written in SES-426 after the live server proof (CNV-398) and the approval of REQ-644 by DEC-1147. |

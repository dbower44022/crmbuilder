# Phase 2 kickoff — version state and reachability

| Field | Value |
|---|---|
| Title | Phase 2 kickoff — version state and reachability |
| Last Updated | 09-23-26 10:41 |
| Revision | 1.0 |
| Status | Ready to run once the recovery absorption (PI-562, PI-563) is merged and pushed. |
| Governs | One session's work: confirming capability 4 of phase 2 is already covered, then absorbing capability 5 |
| Source | `phase-2-server-lifecycle-kickoff.md` §3 items 4 and 5; `phase-2-recovery-kickoff.md` §7; PRJ-125; TOP-119 |

## Opening answer

Paste this as the first line of the new session so the session-open hook
classifies it:

> Opening answer: Absorb version 1's reachability check into version 2, after confirming version state needs no new code, so version 2 can adopt an instance somebody else provisioned without calling version 1.

---

## 1. What this session delivers

1. **Version state, capability 4: a confirmation, probably not code.** Version 1
   has two writers for version state: one records the running and latest
   versions, the other records the result of an upgrade. Version 2 now writes
   every one of those values. The upgrade's check writes the running and latest
   versions. The upgrade itself writes the running version, the upgrade time and
   the backup folders. The provisioning run and the rebuild write the
   certificate expiry. Verify that against the code before recording anything.
   If it holds, record it in the store as covered, with no requirement, because
   no capability is being built. The one gap worth checking: nothing re-reads
   the certificate expiry on a running instance. Version 1 did not either, so it
   is new work, not absorption. Raise it as a question; do not build it.
2. **Reachability, capability 5.** Version 1's `automation/core/deployment/connectivity.py`
   (126 lines) proves that an instance somebody else provisioned is reachable,
   that its credentials sign in, that it is the expected platform, and that its
   version is supported. Absorb that check into version 2 as one requirement and
   one planning item, in the shape of the upgrade and recovery work.

"Done" means capability 4 is recorded as covered (or its gap is raised), and the
reachability check is merged and pushed to `main`, with nothing in version 2
importing `automation.core.deployment.connectivity`.

## 2. Governance comes first

Same shape as the last two sessions. For capability 5: one requirement with
provenance, confirmed by an approving decision; one planning item in PRJ-125;
branch `absorb/reachability`; every code commit carrying `Governed-By: PI-NNN`.
The acceptance summary ends with the sentence that proving the check against a
real instance is the product owner's step.

**Push before resolving.** Merge, push, and only then mark the planning item
Resolved, with a resolution reference that says the commit is pushed.

## 3. What is already known

- **The supported-version list is stale. Verified by reading the code.**
  Version 1's list stops at 8.5. The CBM test instance runs 9.3.6 and CBM
  production runs 9.3.8, so version 1's check calls both unsupported. Whether
  version 2 keeps a fixed list, reads the supported range from somewhere, or
  drops the check is a decision for the product owner, not a detail to settle
  in passing.
- **Version 2 already has a sign-in check.** `crmbuilder_v2/deploy/recovery.py`
  `check_sign_in` signs in and reports whether the account is an administrator,
  telling "refused" apart from "could not be checked". The introspection client
  (`crmbuilder_v2/introspect/espo_client.py`) has its own `test_connection`.
  Reuse one of them; do not add a third.
- **The CBM instances sign in with the administrator's e-mail address, not
  "admin".** "admin" is refused.

## 4. Findings from the recovery session that belong to later work

- **The upgrade's database dump puts the database password on the host's
  command line. Verified by reading the code.** It passes the password as
  `-e MYSQL_PWD=<value>` to the container command. That keeps it off the
  database client's command line inside the container, but the container
  command itself runs on the server, so a process listing on the server shows
  it. The reset in `recovery.py` avoids the problem by feeding its password on
  standard input. The dump can be fixed the same way. That is a small change to
  the upgrade, and it needs its own planning item.
- **The installer's copies of old installations are never removed.** A rebuild
  leaves one under `~/espocrm-backup/` on the server (DEC-1142). Pruning them is
  later work.

## 5. How to work

- Governance rules are in the store, not in a file. Read them at session start.
- Build test fixtures from what the server actually returns (lesson LRN-007),
  and say at the top of each test file which fixtures were not read off a real
  instance.
- The full version 2 suite runs longer than the ten-minute tool limit. Run the
  deploy tests, the Operate segment tests and
  `tests/crmbuilder_v2/test_version_one_imports.py` in the foreground, and the
  full suite in the background.

## 6. What comes after

Capability 6, server inspection: the inspection half of `record_generator.py`
(418 lines). Then capability 7, the deployment record document, and 8,
extensions.

## Change log

| Revision | Date | Description |
|---|---|---|
| 1.0 | 09-23-26 10:41 | Written at the close of the recovery session (PI-562, PI-563). Records that capability 4 appears covered, the stale supported-version list, and two findings for later work. |

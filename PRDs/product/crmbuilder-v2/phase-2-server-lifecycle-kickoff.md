# Phase 2 kickoff — the server lifecycle

| Field | Value |
|---|---|
| Title | Phase 2 kickoff — the server lifecycle |
| Last Updated | 09-21-26 |
| Revision | 1.0 |
| Status | Ready to run. Phase 1 closed 09-21-26 (DEC-1139). |
| Governs | One session's work: absorbing version 1's server lifecycle into version 2's Operate segment |
| Source | PI-514 / DEC-1093 / DEC-1094 (the version 1 capability inventory, areas 4a and 4b); DEC-1129 (removal programme); DEC-1139 (phase 1 close) |

## Opening answer

Paste this as the first line of the new session so the session-open hook
classifies it:

> Opening answer: Build the server lifecycle into version 2 — upgrade, recovery, server inspection and reachability — absorbing it from version 1 under the capability inventory.

---

## 1. Why this phase exists

The goal is to merge every capability of version 1 into version 2 so version 1
can be retired. One of version 1's nine functional areas has been migrated: the
configuration engine, finished the week of 09-15-26. Eight have not.

Phase 2 is the server lifecycle. It matters more than its size suggests for one
reason: **it removes the last version 1 import version 2 makes.** Until that
import is gone, none of version 1 can be deleted, because a dependency is a
deletion gate.

The frozen list is `tests/crmbuilder_v2/test_version_one_imports.py`. It holds
two entries. One is the emitter's self-check still reading a declaration back
with version 1's parser — small, and not this phase. The other is this:

```
("deploy/runner.py", "automation.core.deployment")
```

`crmbuilder-v2/src/crmbuilder_v2/deploy/runner.py` calls version 1's five SSH
provisioning phases directly, in `RunnerDeps.__post_init__`. Absorbing them is
the spine of this phase.

## 2. What is already covered — do not rebuild it

Read this before writing anything. The inventory marks nine capabilities in
area 4a and seven in area 4b as **already covered** by version 2. Among them:

- Waiting for a domain name to resolve before continuing.
- Masking a secret in the operation log.
- Recording the start and outcome of a deployment attempt.
- Registering a deployed instance and keeping its address and login.
- Storing and reading a server's connection, hosting and domain details.
- Keeping a secret out of the database and resolving it by reference.
- The instance register, the deployment-run history, and the rule that gates
  upgrade and recovery on a self-hosted deploy.

Version 2's deploy runner is already a resumable, checkpointed phase machine
with every external dependency injectable (`RunnerDeps`), which is why the SSH
phases can be absorbed behind the same seam they are called through today.

## 3. What this phase absorbs

Eight capabilities in area 4a, roughly 2,900 lines, and the screens above them
in area 4b. In the order I would take them:

**1. The five provisioning phases** (`ssh_deploy.py`, 385 lines). Prepare the
machine, install the platform, fix ownership, obtain the certificate, verify.
Absorbing these strikes the second frozen import. Everything else in the phase
is easier once the runner owns its own SSH path.

**2. Upgrade** (`upgrade_ssh`, 122 + 276 lines). Read whether the running
platform is behind the latest release, then upgrade in place: pre-flight,
back up the database and the data volume with retention, run the upgrade
inside the container, verify. Two cautions the version 1 code documents and a
port must keep — the platform upgrades one step at a time, so 9.3.4 to 9.3.6
is two invocations and the routine deliberately does not loop; and the
pre-upgrade ownership change is required because the image build ran as root.

**3. Recovery** (`recovery_ssh`, 45 + 60 lines). Reset the administrator login
when the administrator is locked out; wipe an instance and rebuild it clean.
The second is gated behind a typed phrase in version 1 and must stay gated.

**4. Version state** (`deploy_config_repo` writers, 54 lines). What version an
instance is on, when it was last upgraded, where its certificate expires.

**5. Reachability** (`connectivity.py`, 126 lines). Prove an instance somebody
else provisioned is reachable and its credentials work, before it is adopted.

**6. Server inspection** (`record_generator` inspection half, 418 lines). Read
an as-deployed server's facts — operating system, processors, memory, disk,
platform version, certificate expiry.

**7. The Deployment Record document** (`record_generator` document half, 1,151
lines). **Stop here and raise it rather than building it.** It produces a Word
document, and phase 4 is where document production is decided, including the
open question the inventory recorded: whether any customer-facing deliverable
must ship as a Word document. Building a Word renderer in phase 2 would decide
that question by accident.

**8. Extensions** (`extension_ssh.py`, `extension_repo.py`, 961 lines).
Install a licensed platform extension, with per-environment licence slots.
Largest single item in the phase and the most separable — it can be its own
piece of work after the rest lands.

## 4. What this phase must not decide

Three deferred planning items share one unanswered question, and phase 2 will
brush against it. **Do not settle it in passing.**

- **PI-552** — loading a list of people into an instance.
- **PI-553** — handing the operator the files a navigation tab needs.
- **PI-550** — comparing duplicate-detection rules against an instance.

The first two are deferred because version 1 wrote files to the operator's own
machine and read files the operator picked, and version 2 publishes from a
service with no operator filesystem. **Where a generated file goes, and where
an incoming file comes from, is an architectural decision.** The Deployment
Record document in item 7 above asks exactly the same question. If phase 2
reaches it, raise it as its own decision for the product owner — do not answer
it inside a deploy feature.

## 5. How to work

Read the governance rules at session start; they are the binding ones and they
are in the store, not in a file. The ones this phase leans on hardest:

- **Requirement-first.** A confirmed requirement and an implementing planning
  item exist before any code, even a one-line change. Each absorbed capability
  gets its own requirement, per the inventory's own rule.
- **Every commit carries `Governed-By: PI-NNN`**, and commits name an explicit
  pathspec.
- **Production deploys are human-only.** This phase writes code that deploys
  servers; it does not deploy one.

### The one discipline that mattered most

**Read the code before trusting the inventory, and read the instance before
trusting the code.**

The inventory is a good map and it was right about nearly every row checked.
It was also written on 09-17-26, before the engine work moved the code under
it, and in phase 1 it was stale three times: two capabilities it listed as
missing were already built, and a third was covered on both halves with a
live gap underneath that the inventory had not described.

Seven defects were found in the publish path the week of 09-15-26. Not one was
found by a test. Every one was found by running the real thing against a real
instance, and the lesson is recorded as **LRN-007**: a fixture written from one
side agrees with the code instead of checking it. When you write a test for an
absorbed capability, build its fixture from what the server actually returns —
read it off a real instance and paste it in, with the date and the host named.

The second recurring shape, met eight times: **a construct the design can
express that the code discards without a word.** When absorbing a capability,
ask what happens when the platform refuses it. Silence is the defect.

## 6. Where things are

- **Inventory:** `specifications/re-architecture/v1-capability-inventory.md`,
  areas 4a and 4b.
- **Version 2 deploy code:** `crmbuilder-v2/src/crmbuilder_v2/deploy/` (runner,
  spec, worker, providers, keys) and the Operate segment at
  `crmbuilder-v2/src/crmbuilder_v2/segments/operate/`.
- **Version 1 code to absorb:** `automation/core/deployment/` and
  `automation/ui/deployment/`.
- **The deletion gate:** `tests/crmbuilder_v2/test_version_one_imports.py`.
  Removing an import means deleting its line there. That is the point — the
  list is the gate made visible, and it may shrink but never grow.
- **Project:** PRJ-125. **Topic:** TOP-119.

## 7. What "done" looks like

The second entry is gone from the frozen import list, version 2 can provision,
upgrade, recover and inspect a server without calling version 1, and the
Deployment Record document and the extension installer are either built or
raised with their reasons. At that point — and not before — version 1's
deployment layer can be deleted, which is phase 2's real product.

## Change log

| Revision | Date | Description |
|---|---|---|
| 1.0 | 09-21-26 | Written at the close of phase 1, after three capabilities were absorbed (PI-548, PI-549, PI-551) and three deferred (PI-550, PI-552, PI-553). |

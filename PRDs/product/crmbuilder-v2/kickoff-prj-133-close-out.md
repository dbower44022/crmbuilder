# Kickoff — close out "Deploying another client's application" (PRJ-133)

| Field | Value |
|---|---|
| Title | Kickoff — close out "Deploying another client's application" (PRJ-133) |
| Last Updated | 09-30-26 15:05 |
| Revision | 1.0 |
| Status | Ready to run. The project's one planning item is resolved; the project is still in flight. |
| Governs | One session: decide whether the project's purpose is met, and either mark PRJ-133 complete or open the one planning item that still stands between it and completion. |
| Source | SES-444 on 09-28-26 to 09-30-26: PI-588 built, rolled out as commit `41f3b35b`, accepted in CNV-413; DEC-1196, DEC-1197. |

## Opening answer

Paste this as the first line of the new session:

> Opening answer: Close out PRJ-133 "Deploying another client's application" — confirm its purpose is met in production now that PI-588 is resolved, and mark the project complete or open the planning item that still stands in the way.

Operating mode: DETAIL.

---

## 1. What this session delivers

A ruling from Doug on whether the project has done what it was opened for, recorded as a decision. Then one of two outcomes:

- **Complete.** PRJ-133 is marked complete, which is terminal: a completed project is never reopened, and later work on deployment grants opens a new project.
- **One more planning item.** If Doug rules that the purpose is not yet proven, the session records the requirement or planning item for the missing piece, inside PRJ-133, and stops. The build is a later session.

## 2. Where the project stands (verified 09-30-26 15:03 through the production API)

The project was opened on 09-27-26 to let a client deploy a private application another client defines, through a deployment grant recorded per client, so that a chapter such as Rochester or Boston can install Cleveland's chapter CRM from the desktop.

- Its only planning item, PI-588, is Resolved through the acceptance conversation CNV-413. Re-enumerate the project's planning items at the live moment before closing; do not rely on this line.
- In production, Cleveland (CLI-001) defines the chapter CRM application ENG-002, which stays private. Rochester (CLI-003) and Boston (CLI-004) hold deployment grants for it. Their deployments DPL-003 and DPL-004 are now the rule, not the migration's exception.
- The deploy refusal accepts a deployment-grant holder. The desktop's Clients panel and the connector add and remove deployment grants one at a time, and the defining client can never move by accident (DEC-1196). A deployment grant does not show the application's demo/test deployment to its holder (DEC-1197).

## 3. The one question to put to Doug

Everything the project named has been built and accepted. What has **not** been done is the sentence the purpose ends with: no chapter has yet installed Cleveland's chapter CRM from the desktop under a deployment grant. The acceptance in CNV-413 proved the rule with the "Register an existing CRM" dialog, which records a CRM that already runs; it did not run the deploy wizard, which builds a new server. Boston's CRM at crm.bbmentors.org was finished by hand as a test system (DEC-1160) before the grant existed.

Put this to Doug as one decision, with both options and their costs:

- **A. The purpose is met.** The rule, the desktop and the connector are built and verified; a wizard run under a grant exercises the same refusal that was already accepted. Mark PRJ-133 complete. *Cost:* the first real chapter deploy under a grant happens in a client project, not here, so any surprise in the wizard's client step surfaces there.
- **B. Prove it end to end first.** Record one planning item in PRJ-133 for a deploy-wizard run of Cleveland's application for a deployment-grant holder, against a test server, and complete the project only after it. *Cost:* a server is built and torn down, which is money and an afternoon, and the project stays open until then.

Recommend A unless Doug wants the wizard run as the proof. Whatever he rules, record the decision in the store with the session and the project linked, before touching the project's status.

## 4. If the ruling is A — closing the project

1. Re-read the project's planning items from the store: `GET /references?target_id=PRJ-133`, then keep only `planning_item_belongs_to_project` rows and read each item's status. Every one must be Resolved. If any is not, stop: it is moved or resolved by a person, never by editing its status.
2. Record the decision that closes the project, linked to this session and to PRJ-133.
3. Mark PRJ-133 complete through the store. Completion is terminal.
4. Add one sentence to the "Client, application and deployment" paragraph of `CLAUDE.md` saying PRJ-133 is complete and when, as a documentation-only commit on `main`.

## 5. If the ruling is B — the planning item

Requirement-first applies even to a proof run: a confirmed requirement, then the planning item that implements it, both in PRJ-133, before any wizard run is scheduled. The requirement's acceptance should name the client, the application, the purpose (client's own), the expected labels in the wizard's client step, and that the server is removed afterwards. Do not run the wizard in this session.

## 6. Out of scope

- Anything about what a client's people see on the web surface. That is REQ-662 in PRJ-131, and whether a deployment-grant holder may see a design there needs its own decision.
- Making any application public.
- Any change to the deployment grant's meaning; the term is TERM-076 and is fixed.

## Change log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-30-26 15:05 | Claude (Claude Code) | First version, written at the close of SES-444 after PI-588 was accepted in production. |

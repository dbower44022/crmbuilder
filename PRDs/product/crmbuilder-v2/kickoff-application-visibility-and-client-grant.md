# Kickoff — who may deploy a private application: Cleveland's visibility and the per-client grant

| Field | Value |
|---|---|
| Title | Kickoff — who may deploy a private application: Cleveland's visibility and the per-client grant |
| Last Updated | 09-27-26 22:30 |
| Revision | 1.1 |
| Status | Run in SES-443 on 09-27-26. Option B chosen (DEC-1194); REQ-664 confirmed (DEC-1195); PI-588 Draft in PRJ-133; build prompt `kickoff-pi-588-deployment-grant-build.md`. |
| Governs | One session: the decision, its requirement and planning item, and, if Doug approves in the same session, the build. |
| Source | SES-437 (DEC-1177), SES-439 and the PRJ-128 acceptance walkthrough (test plan step 7), the PI-582 close-out on 09-27-26 |

## Opening answer

Paste this as the first line of the new session so the session-open hook classifies and files it:

> Opening answer: Decide how a client other than the defining client may deploy a private application — Cleveland's chapter CRM ENG-002 for Rochester and Boston — resolving the open point of DEC-1177, then record the requirement and planning item that follow.

Operating mode: DETAIL.

---

## 1. What this session delivers

A decision, recorded as DEC-NNN, on how a client that did not define an application may deploy it, applied first to Cleveland's chapter CRM (ENG-002). Today the rule in REQ-653 reads: a private application accepts a deployment only from its defining client. The migration created the Rochester and Boston deployments as a written-down exception to that rule (DEC-1181, DEC-1182). A third chapter cannot be added through the desktop or the REST API until this decision is made.

"Done" for the session is the decision recorded, the requirement that carries it confirmed by that decision, a planning item that implements it placed in a project, and a prompt for the build session if the build is not done in the same session. If Doug says build in the same session, "done" is the code merged to `main`, pushed, rolled out by Doug, and the planning item resolved through a conversation's `resolves` edge.

## 2. Governance already in place

- **REQ-653** "CRMBuilder records clients, applications and deployments" is confirmed. Its private-application rule is the sentence this decision changes or keeps. A change to the rule is a change of meaning, so it is a new requirement or an amendment confirmed by the new decision, never a status edit.
- **DEC-1177** made ENG-002 private and named making it public as a separate later decision. **DEC-1181** and **DEC-1182** created the Rochester and Boston deployments as a bounded exception. **DEC-1183** chose the `engagement_clients` holding, with `is_primary`, as the store of the defining client. **DEC-1155** defines client, application and deployment; terms TERM-005, TERM-070, TERM-071.
- **PRJ-128** is complete and terminal under the project-complete rule: the new planning item cannot join it. Open the item in a new project, or in PRJ-023 if Doug reads this as Master PRD dogfood work. Put the project choice to Doug with the decision.
- No new terminology without Doug's approval. "Grant" is not yet a glossary term; if option B is chosen, propose the term and its one-sentence definition for approval before using it in a record.

## 3. The store as it stands (verified 09-27-26 00:25 through the production API)

- Four clients: CLI-001 Cleveland Business Mentors, CLI-002 CRMBuilder, CLI-003 Rochester Business Mentors, CLI-004 Boston Business Mentors.
- ENG-002 is held by one client only, CLI-001, marked primary. Visibility private. No non-primary holder exists on any engagement.
- Four deployments, DPL-001 to DPL-004, all of ENG-002: two for CLI-001, one for CLI-003, one for CLI-004.
- The refusal is `_require_may_deploy` in `crmbuilder-v2/src/crmbuilder_v2/segments/operate/repositories/deployments.py` (line 117 at commit e9fd5418): private and client is not the defining client raises `application_private`. The desktop's Register deployment dialog shows the refusal inline (test plan step 7). The demo/test rule `demo_test_requires_defining_client` sits beside it and is unaffected.
- The holding is read and written through `segments/client_management/repositories/client.py` (`get_engagement_clients`, `set_engagement_clients`, `primary_client_for_engagement`) and the REST routes `GET` and `PUT /engagements/{id}/clients` (PI-512 / REQ-589). The desktop's Clients panel shows a client's applications and deployments; whether it can add a non-primary holder is to be verified at the session start, not assumed.

## 4. The decision to put to Doug first

Present in the consequential-decision form, one turn, before any other work.

**Question.** When Rochester wants a third chapter CRM from Cleveland's design, who has to have said yes, and where is that recorded?

**Option A, make ENG-002 public.** One PATCH of `engagement_visibility`, no code. Any client record in the store may then register a deployment of Cleveland's design. Today the four clients are all Doug's, so the exposure is theoretical, but the model was built for client people signing in and seeing only their own client (DEC-1159); public means every future client sees Cleveland's application as deployable.

**Option B, a per-client grant recorded as a non-primary holder (recommended).** A private application accepts a deployment from its defining client or from any client that holds it in `engagement_clients` without the primary mark. No new table and no new column: DEC-1183 already made the holding the record of who an application belongs to, and the migration's exception becomes regular by adding CLI-003 and CLI-004 as holders of ENG-002. Cost: a requirement amendment, a change to `_require_may_deploy` and its tests, a way in the desktop and the connector to add and remove a holder, and the glossary term for the grant. The `is_primary` reading of the holding becomes load-bearing in a second place, which the design must state.

**Option C, keep the rule and add chapters by hand.** No change; each new chapter deployment is written through the droplet access layer as the migration was. Cost: the desktop cannot do the one thing DEC-1154 was decided for, deploying a chapter, and every chapter is an operator step.

**Recommendation.** Option B. Its cost is one small build; its benefit is that the answer to "who may deploy this" is a row Doug can read, per client, and the two existing chapter deployments stop being an exception. Ask Doug to choose A, B or C, and to name the project the planning item goes in.

## 5. If Doug chooses B: what follows in the same session

1. Record the decision naming REQ-653 and DEC-1177; propose the glossary term.
2. Write the requirement amendment or the new requirement with provenance, and confirm it by the decision.
3. Create the planning item in the named project, implementing the requirement, Draft.
4. Regularise the two chapter deployments: add CLI-003 and CLI-004 as non-primary holders of ENG-002 through `PUT /engagements/ENG-002/clients`, recorded in the decision's consequences.
5. Build only if Doug says so in this session: `_require_may_deploy` reads the holding; tests in `tests/crmbuilder_v2/segments/operate/test_deployment.py` and `api/test_deployments_api.py`; the desktop and connector surface for holders; `Governed-By: PI-NNN`; a branch; push to `main`; Doug rolls out with `scripts/deploy-production.sh`.

## 6. Other open items, not for this session unless Doug raises them

- The Cleveland design session over the candidate corrections in `prj128-migration-rehearsal-report.md` §4 (DEC-1189).
- The doubled Maintainer sentence in the session-open confirmation line, seen in SES-441 on 09-27-26: not yet filed.
- A close-out procedure line that reviews PRJ-132 "Unfiled sessions" and files each session under its real project.
- Rotation of the production database credential that appeared in a pasted terminal line on 09-25-26: Doug's task, outside any session.

## Change log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.1 | 09-27-26 22:30 | Claude (Claude Code) | Status set to run: outcome of SES-443 recorded and the build prompt named. |
| 1.0 | 09-27-26 00:30 | Claude (Claude Code) | First version, written at the PI-582 close-out after the 09-27-26 rollout of e9fd5418. |

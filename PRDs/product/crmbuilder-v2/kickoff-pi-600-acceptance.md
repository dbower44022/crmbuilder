# Kickoff — accept PI-600 against production (the Business Mentors Association's deployment of ENG-002)

| Field | Value |
|---|---|
| Title | Kickoff — accept PI-600 against production (the Business Mentors Association's deployment of ENG-002) |
| Last Updated | 11-09-26 12:02 |
| Revision | 1.1 |
| Status | Run in SES-459 on 11-09-26, without a separate session: rollout of `def69cc6`, then the review runbook (artifact XVHN3wKnWvkoycjKubDQ5R). Every step passed; CNV-426 resolves PI-600. Do not run again. |
| Governs | One acceptance session: the check in section 5 of `kickoff-pi-600-deployment-credentials-build.md`, then PI-600 resolved through a conversation's `resolves` edge. |
| Source | SES-459 on 11-09-26: PI-600 built and pushed to `main` as `e155d670`; PI-600 is In Review. |

## Opening answer

Start the session by giving only this file's full path, on one line with nothing typed before it (PI-589; a word before the path defeats it, PI-597).

> Opening answer: Accept PI-600 in PRJ-129 against production — the Business Mentors Association's deployment of ENG-002 (REQ-668, REQ-669, REQ-670).

Operating mode: DETAIL. Stopping points: (1) before any write to production, to confirm the client and grant exist; (2) after the acceptance check, before PI-600 is resolved.

---

## 1. What was built (SES-459)

- The deploy wizard asks the deployment's name on step 1, beside Client and Purpose. Leaving step 1, or pressing **Set credentials…**, creates the deployment; later changes on step 1 update the same deployment.
- The credentials dialog opens only on that deployment. Its title reads "Hosting credentials for deployment DPL-NNN — name". The wizard never saves an application token.
- Step 1's token lines end "(the application's)" or "(this deployment's own)".
- The server lists and the Cloudflare zones are read through the deployment: `GET /deployments/{id}/digitalocean/options` and `GET /deployments/{id}/cloudflare/zones`.
- Each deployment carries `deployment_has_run`: true when a deploy run names it or it holds an instance. The Deployments panel shows "active — not yet run" for one that has never run.
- Remove in the Deployments panel removes a deployment that never ran and deletes its own tokens (`POST /deployments/{id}/remove-unrun`). For one that has run, it is refused with the reason (Doug, SES-459, option a).

## 2. The check

Run section 5 of `PRDs/product/crmbuilder-v2/kickoff-pi-600-deployment-credentials-build.md`, steps 1 to 6, with Doug. Two corrections to its wording, from the build:

- Step 2: the name is now asked on step 1, so fill in Client, Purpose (Client's own) and the deployment name before pressing **Set credentials…**.
- Step 6: "abandon a second wizard after step 1" means fill in step 1, click Next, then Cancel. The deployment then shows "active — not yet run" until removed.

Also confirm that DPL-001..DPL-004 show no "not yet run" mark, and that Remove on DPL-001 is refused.

## 3. At the end

- Record a conversation, and a `resolves` edge from it to PI-600, only after every step passes.
- Hand the screens and labels in SES-459's final report to a `cbm-client-intake` session for guide steps 5.8 and 9.3 and `OPEN-ITEMS.md` item 73. Make no change to that repository from here.

## Change log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.1 | 11-09-26 12:02 | Claude (Claude Code) | Marked run: the check was done in SES-459 itself; CNV-426 resolves PI-600. |
| 1.0 | 11-09-26 08:54 | Claude (Claude Code) | First version, written at the end of the PI-600 build in SES-459. |

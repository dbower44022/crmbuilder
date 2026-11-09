# Kickoff — build a new deployment's own provider credentials in the deploy wizard (PI-600, REQ-668..REQ-670)

| Field | Value |
|---|---|
| Title | Kickoff — build a new deployment's own provider credentials in the deploy wizard (PI-600, REQ-668..REQ-670) |
| Last Updated | 11-09-26 00:40 |
| Revision | 1.0 |
| Status | Ready to run. Requirements confirmed, planning item Ready. |
| Governs | One build session: PI-600 in PRJ-129, from branch to merged, pushed and ready for Doug's rollout. |
| Source | SES-458 on 11-09-26: DEC-1205 (shape A), CNV-425; from the kickoff `~/Dropbox/Projects/cbm-client-intake/prompts/crmbuilder-deployment-credentials-kickoff.md` v0.2 |

## Opening answer

Start the session by giving only this file's full path, on one line with nothing typed before it. The session-open rule then reads the line below (PI-589; a word before the path defeats it, PI-597).

> Opening answer: Build PI-600 in PRJ-129 — the deploy wizard creates the deployment early and gives it its own provider credentials (REQ-668, REQ-669, REQ-670).

Operating mode: DETAIL. Stopping points: (1) after the design check in section 4.1, before any code; (2) after the tests pass on the branch, before the merge to `main`; (3) after the push, for Doug's rollout.

---

## 1. What this session delivers

Code merged to `main` and pushed that satisfies the acceptance summaries of REQ-668, REQ-669 and REQ-670. Doug then runs the rollout with `scripts/deploy-production.sh`. PI-600 is resolved through a conversation's `resolves` edge once the acceptance check in section 5 has been run against production.

## 2. Governance already in place

- **DEC-1205** "The deploy wizard creates the deployment early and gives it its own provider credentials (shape A)". Rejected: B (create in the Deployments panel, then a **Build…** action) and C (hold the tokens in memory until Deploy).
- **REQ-668** (must): the wizard creates the deployment when step 1 is left or **Set credentials…** is pressed, works on that one deployment from then on, saves every provider credential at deployment scope, and never writes a provider credential at application scope.
- **REQ-669** (must): the wizard's DigitalOcean catalogue (regions, sizes, images, SSH keys) and its Cloudflare zone list use the deployment's credential, falling back to the application's.
- **REQ-670** (must): a deployment that has never run is marked as not yet run in the Deployments panel and can be removed there; removal soft-deletes the deployment and deletes its deployment-scope credentials; a deployment that has run is refused removal this way.
- **PI-600** is Ready in **PRJ-129** "Deployment inputs: settings, secrets and readiness". Move it to In Progress when the branch is cut. Every code commit carries `Governed-By: PI-600`.

Read each requirement's full acceptance summary from the store (`GET /requirements/REQ-668` and so on) before building. The store is the source; this file summarises.

## 3. The code as it stands (verified 11-09-26 in SES-458)

Under `crmbuilder-v2/src/crmbuilder_v2/segments/operate/`:

- `ui/dialogs/deploy_wizard_dialog.py`: `_deployment_identifier` starts as None (~165) and is set only in `_deploy()` (~985–1013), which also reuses it after a refused run. `_open_credentials` (~967) passes it to `ProviderCredentialsDialog` and then calls `_load_providers`. `_load_providers` (~855) already reads `list_deployment_provider_credentials` once a deployment exists. `_load_catalogs` (~888) calls `get_digitalocean_options` and `list_cloudflare_zones`, which take no deployment. `build_deployment_body` (~802) sends client and purpose (step 1) and the name from `instance_name` (step 4).
- `ui/dialogs/provider_credentials_dialog.py` `_save` (~203): with a deployment it calls `put_deployment_provider_credential`; without one it calls `put_provider_credential` (application scope). After this build the wizard must never reach the second branch.
- `routers/provider_credentials.py`: `digitalocean_options` and `cloudflare_zones` (~86, ~104) both call `_token(provider)`, which reads the application row only.
- `repositories/provider_credentials.py` `resolve_provider_credential(session, provider, deployment_identifier=...)` (~78): the deployment's credential, else the application's. The run already uses it (`deploy/runner.py` ~414). Reuse it for REQ-669.
- `routers/deployments.py`: `POST /deployments` (instance optional, `deployment_name` required), `PATCH /deployments/{id}` (name may change), `DELETE /deployments/{id}` (soft delete via `delete_deployment`), and `GET`/`PUT`/`DELETE /deployments/{id}/provider-credentials[/{provider}]`.
- `vocab.py`: `DEPLOYMENT_STATUSES` is `{"active", "retired"}`. Not yet run is derived from deploy-run history (`GET /deploy-runs?deployment=`), not a new status value (REQ-670 notes).
- `ui/panels/deployments.py`: no Remove action exists today; **Credentials…** (~644) already sets deployment-scope tokens.
- `GET /deploy-runs/dns-lookup` uses public resolvers and needs no change.

## 4. Scope

1. **Design check (stopping point 1).** The deployment needs a name when it is created, and the name is asked on step 4 today. Choose between moving the name field to step 1, or creating with a default name that step 4 writes back by `PATCH`. Also decide the deployment-scoped catalogue routes' shape (for example `GET /deployments/{id}/digitalocean/options` and `GET /deployments/{id}/cloudflare/zones`, or a `?deployment=` parameter on the existing routes). Present both choices to Doug before code; they are implementation choices following DEC-1205, so record his answers as decisions only if he says they pass the two-part test.
2. **Wizard (REQ-668).** Create the deployment on leaving step 1 or on **Set credentials…**, whichever is first; emit `deployment_created`; never create a second one. `_deploy` keeps reusing it. The credentials dialog, when opened from the wizard, always has a deployment and says which one. Remove the wizard's path to application-scope saves.
3. **Catalogues (REQ-669).** API routes, client methods and the wizard's `_load_catalogs` use the deployment-scoped forms. The application-scope routes stay for other callers.
4. **Deployments panel (REQ-670).** A not-yet-run mark, and a Remove action with confirmation for a not-yet-run deployment that soft-deletes it and deletes its two deployment-scope credentials. Remove is refused, with an explanation, for a deployment that has run. Buttons are never disabled (GVR-217).
5. **Tests.** `tests/crmbuilder_v2/segments/operate/test_provider_credentials.py`, `test_deployment.py`, the API tests, and under `ui/`: `test_deploy_dialogs.py`, `test_provider_credentials_dialog.py`, `test_deployments_panel.py`. Cover every numbered acceptance item that a test can reach.

## 5. Acceptance check against production after rollout

The test case is the Business Mentors Association's deployment of ENG-002. Do not write any of this without Doug.

1. Client **Business Mentors Association** exists and holds a deployment grant on ENG-002 (Clients panel, Deployment grants, Add application).
2. Open the deploy wizard for ENG-002, choose that client and purpose Client's own, press **Set credentials…**. Expected: a new deployment exists and the dialog names it.
3. Save the DigitalOcean token "crmbuilder-bma" and the Cloudflare token "crmbuilder-bma" (both in the Association's Proton Pass). Expected: `GET /deployments/{id}/provider-credentials` shows both; `GET /provider-credentials` for ENG-002 still shows `crmbuilder-eng002-readonly (cbm team, read-only)`.
4. Step 2 onwards lists the Association's SSH keys and its zones `mentorsassociation.org` and `businessmentorsassociation.org`, and the address `crm.businessmentorsassociation.org` is offered CRMBuilder-created DNS.
5. Whether the first run goes ahead now is Doug's call; the two paid add-ons are left out for now (Association ruling 74).
6. Abandon a second wizard after step 1 and remove that deployment from the Deployments panel. Expected: it is gone from the list and its credentials are deleted.

## 6. At the end

Report the exact screens and labels for `cbm-client-intake`'s deployment guide steps 5.8 and 9.3. Changes to that repository, including `OPEN-ITEMS.md` item 73, are made only through a session in that repository.

## 7. Out of scope

- Application-scope credentials set outside the wizard (the Credentials panel) stay as they are.
- A **Build…** action on an existing deployment (shape B, rejected by DEC-1205).
- New deployment status values.

## Change log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 11-09-26 00:40 | Claude (Claude Code) | First version, written in SES-458 after DEC-1205 and the confirmation of REQ-668, REQ-669 and REQ-670. |

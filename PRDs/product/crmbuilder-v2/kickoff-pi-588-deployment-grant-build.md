# Kickoff — build the deployment grant (PI-588, REQ-664)

| Field | Value |
|---|---|
| Title | Kickoff — build the deployment grant (PI-588, REQ-664) |
| Last Updated | 09-27-26 22:30 |
| Revision | 1.0 |
| Status | Ready to run. Requirement confirmed, planning item Draft, data already regularised. |
| Governs | One build session: PI-588 in PRJ-133, from branch to merged, pushed and ready for Doug's rollout. |
| Source | SES-443 on 09-27-26: DEC-1194 (the choice), DEC-1195 (approval of REQ-664), TERM-076, CNV-412 |

## Opening answer

Paste this as the first line of the new session:

> Opening answer: Build PI-588 in PRJ-133 — a client holding a deployment grant may deploy a private application, and the desktop and connector add and remove deployment grants (REQ-664).

Operating mode: DETAIL.

---

## 1. What this session delivers

Code merged to `main` and pushed that satisfies REQ-664's acceptance summary. After that, Doug runs the rollout with `scripts/deploy-production.sh`, and PI-588 is resolved through a conversation's `resolves` edge once the acceptance criteria are verified against production.

## 2. Governance already in place

- **REQ-664** "A private application may be deployed by its defining client or by a client holding a deployment grant". Confirmed by DEC-1195. It refines REQ-653, whose own text is deliberately unedited.
- **DEC-1194** chose the deployment grant, stored as a row in `engagement_clients` without the primary mark. There is no new table and no new column.
- **TERM-076** "Deployment grant": a client's recorded permission to deploy a private application it did not define. It permits deployment only, not seeing or changing the design. Use this term in code comments, the user interface and connector tool descriptions. Invent no other name for it.
- **PI-588** is Draft in **PRJ-133** "Deploying another client's application". Move it to In Progress when the branch is cut. Every code commit carries `Governed-By: PI-588`.

## 3. The store as it stands (verified 09-27-26 22:30 through the production API)

- ENG-002 is private. Its holders are CLI-001 (primary, the defining client), CLI-003 Rochester and CLI-004 Boston (both non-primary, so both hold deployment grants). These rows were written in SES-443 through `PUT /engagements/ENG-002/clients`.
- DPL-001 and DPL-002 belong to CLI-001, DPL-003 to CLI-003 and DPL-004 to CLI-004. None of the four is touched by this build.
- No other engagement has a non-primary holder.
- Nothing else in the code reads a non-primary holding as permission to see the design. The only readers of `engagement_clients` are `client_management/repositories/client.py`, `engagement.py` (primary only), the Clients panel and the PRJ-128 migration. Keep it that way.

## 4. Scope

1. **The refusal.** `_require_may_deploy` in `crmbuilder-v2/src/crmbuilder_v2/segments/operate/repositories/deployments.py` accepts a deployment from the defining client or from a client holding the application without the primary mark. Every other client of a private application is refused with `application_private`, whose message should now mention the deployment grant. `demo_test_requires_defining_client` stays as it is.
2. **The Clients panel** (`segments/client_management/ui/panels/clients.py`).
   - `_on_add_engagement` today passes `primary=client_identifier`, which would make the added client the defining client. When the application already has a defining client, the added client must become a deployment-grant holder and the primary mark must not move.
   - `_on_remove_engagement` must refuse to remove the defining client's holding as though it were a deployment grant.
   - Show a deployment grant as a deployment grant, not as an application the client defines.
3. **The connector.** Add tools to list, add and remove the deployment grants of an application in `crmbuilder-v2/src/crmbuilder_v2/mcp_server/tools.py`. `PUT /engagements/{id}/clients` replaces the whole set. If a read-modify-write through it is judged unsafe, add a narrow route instead, one that adds or removes a single deployment grant, and put that design choice to Doug before building it.
4. **The Register deployment dialog** offers the clients that hold a deployment grant, and the inline refusal text names the deployment grant.
5. **Tests.**
   - `tests/crmbuilder_v2/segments/operate/test_deployment.py` and `test_deployment_purpose.py`: a deployment-grant holder may register a client's-own deployment; a client with neither role is refused; a deployment-grant holder is still refused a demo/test deployment.
   - The deployments API tests under `tests/crmbuilder_v2/segments/operate/api/`.
   - The Clients panel tests under `tests/crmbuilder_v2/segments/client_management/ui/`: adding never moves the primary mark; removing the defining client is refused.
   - The connector tool tests.

## 5. Acceptance check against production after rollout

1. Read `GET /engagements/ENG-002/clients`. Expected: CLI-001 primary, CLI-003 and CLI-004 not primary.
2. In the desktop, open Register deployment for ENG-002 with a client that is not a holder. Expected: the inline `application_private` refusal naming the deployment grant.
3. Add a deployment grant for that client through the desktop. Expected: `GET /applications/ENG-002` still names CLI-001 as defining client.
4. Remove that deployment grant again, so production ends as it started.

## 6. Out of scope

- Making any application public.
- Letting a deployment-grant holder see or edit the design. That belongs to the client web surface (REQ-662) and would need its own decision.
- Editing REQ-653's text.

## Change log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-27-26 22:30 | Claude (Claude Code) | First version, written in SES-443 after DEC-1194, DEC-1195 and the regularisation of the Rochester and Boston holders. |

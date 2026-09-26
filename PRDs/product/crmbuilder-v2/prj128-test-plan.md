# PRJ-128 — rollout steps and comprehensive test plan

| Field | Value |
|---|---|
| Title | PRJ-128 — rollout steps and comprehensive test plan |
| Last Updated | 09-26-26 01:01 |
| Revision | 1.4 |
| Status | PROJECT COMPLETE (09-26-26, DEC-1191). ACCEPTED. The 35-step acceptance walkthrough (claude.ai/artifact/VhWW7sBMPPfGRnqTEnaELU) ran clean on 09-26-26 after one fix (PI-584, the Run history window loading on open) and one corrected expectation (the private-application refusal comes before the demo/test rule). All six items Resolved. |
| Source | Session SES-439 (delegation DEC-1184; decisions DEC-1185 to DEC-1188), on top of SES-437 (mapping, DEC-1176 to DEC-1182) and SES-438 (PI-575, DEC-1183). |
| Read by | Doug, to roll out and to test; the follow-up session that applies the migration run after the ruling. |

## 1. What is in production

Main carries, in this order after the PI-575 rollout of this morning (v0.7.0): PI-576 the deployment record, PI-577 the purpose, PI-579 the migration run (code and its non-applying Alembic revision), and PI-580 the desktop and connector rename. None of it is in production yet; the store head there is still `client_management_0003_application_attributes` on the client-management branch and `operate_0002_deploy_needs_action` on the operate branch. The rollout adds three operate revisions: `operate_0003_deployments`, `operate_0004_deployment_purpose` and `operate_0005_prj128_migration_run`. The third records itself as run without moving anything, because the Rochester comparison needs the ruling in section 3.

## 2. Rolling out

The deploy script is the usual one and takes no backup itself; take one first because the operate revisions change three tables.

### In the terminal, on the droplet

1. Open a terminal and type the line below, then press Enter:
   ```bash
   ssh -i ~/.ssh/id_ed25519 root@138.197.72.15
   ```
   You should see the droplet's prompt, ending in `#`. If it asks for a password or refuses the key, stop and tell me exactly what it says.

2. At the droplet prompt, type the line below and press Enter:
   ```bash
   cd /opt/crmbuilder && set -a && . crmbuilder-v2/data/crmbuilder.env && set +a && pg_dump -Fc --no-owner --no-acl "${CRMBUILDER_V2_DATABASE_URL/+psycopg/}" > backups/pre-operate0003-$(date +%Y%m%d-%H%M%S).dump && ls -la backups | tail -3
   ```
   You should see a new file named `pre-operate0003-<date>.dump` of roughly 10 MB in the listing. If the file is missing or under 1 MB, stop and tell me exactly what the listing shows.

3. Type `exit` and press Enter to leave the droplet. You should be back at your own prompt.

### In the terminal, in the repository

4. In a terminal whose current folder is `~/Dropbox/Projects/crmbuilder`, type the line below and press Enter:
   ```bash
   git checkout main && git pull --ff-only
   ```
   You should see `Already up to date.` or a fast-forward ending at commit `c890e24d`. If git reports a conflict or refuses, stop and tell me exactly what it says. (If main is checked out in the pi-566 worktree, run this there or remove that worktree first.)

5. In the same terminal, type the line below and press Enter:
   ```bash
   ./scripts/deploy-production.sh
   ```
   It asks you to type the phrase `deploy production`. You should see the preflight, the copy, the migrate step listing the three operate revisions, the migrate step printing every move of the migration run and ending `PRJ-128 migration run applied: {...}` (if it prints `NOT applied`, stop and paste me the line), the service restart, and finally `DEPLOY OK: commit ... | v0.7.x | alembic ...`. If the script stops before `DEPLOY OK`, stop and paste me its last twenty lines.

## 3. The ruling

Doug ruled on 09-25-26 (DEC-1189): the nine associations and the attribute differences are candidate corrections to Cleveland's design, the copy is archived and kept, and the run applies. Section 4 of the rehearsal report is the work order for a later Cleveland design session.

## 4. Test plan

Each item names where you are, what to do, what you should see. Anything else: stop and tell me exactly what you see.

### 4.1 Desktop, after the rollout (start the version 2 desktop from the main clone with `cd ~/Dropbox/Projects/crmbuilder && uv run crmbuilder-v2-ui`; plain `uv run crmbuilder` opens the old version 1 window)

1. **Top strip.** With the CRMBuilder application active, the strip reads `CRMBuilder v2 (CRMBUILDER) · defined by CRMBuilder`. Click it: the picker groups applications under their clients and its footer reads `Manage applications…`.
2. **Applications panel.** Sidebar entry `Applications` opens a list with columns Identifier, Code, Name, Defined by, Visibility, Status, Last Opened, Created. ENG-001, ENG-002, ENG-004 and ENG-005 show their client under Defined by and `private` under Visibility; ENG-003 shows CRMBuilder and `archived`; ENG-005, ENG-006 and ENG-007 show `archived`. No label on the panel says engagement.
3. **New application.** Click `New Application`: the dialog is titled `New application` and has a `Defined by` combo listing the two clients and a `Visibility` combo defaulting to `private`. Cancel it.
4. **Clients panel.** Columns Identifier, Name, Status, Applications, Deployments, Created. Select Cleveland Business Mentors: the detail shows `Applications defined` with ENG-002 and ENG-004 and a `Deployments` section listing DPL-001 and DPL-002.
5. **Deployments panel.** Sidebar entry `Deployments` (in place of Instances). Under the CBM application it lists DPL-001 to DPL-004; under any application, `New deployment…` opens the wizard and `Register existing…` opens the register dialog. No label says instance or engagement.
6. **Register existing.** In the CBM application, click `Register existing…`, choose client Cleveland Business Mentors, purpose `Client's own`, name `Test registration`, URL `https://crm-test.clevelandbusinessmentors.org`, any API key, Save. The list shows `DPL-005` with Client `Cleveland Business Mentors`, Purpose `client_own`; the detail shows the CRM connection, an empty deploy configuration and `Hosting credentials` with DigitalOcean `configured (application default)`. Then `Remove` it (and the demo/test one from step 7) and tick `Show retired`: they reappear struck through with `Restore`.
7. **Private application and demo/test.** Repeat step 6 choosing client Rochester Business Mentors and purpose `Demo/test`: the dialog refuses inline saying ENG-002 is private to CLI-001 and CLI-003 may not deploy it (the private-application rule of DEC-1177; Rochester's existing deployment came in through the migration). With client Cleveland Business Mentors and purpose `Demo/test` it succeeds, because the defining client may run the demo/test deployment. The `demo_test_requires_defining_client` refusal needs a public application and cannot be shown in production today.
8. **Deploy wizard.** `New deployment…`: the start page asks `Who is this deployment for?` with Client and Purpose; the server page asks `What should CRMBuilder call this deployment?`; the review lists Client and Purpose. Do not press Deploy unless you mean to create a server.
9. **Hosting credentials.** On a deployment's detail, `Credentials…` opens `Hosting credentials` listing DigitalOcean and Cloudflare with `(application default)` or `(this deployment)` after the label. Cancel.
10. **Deploy History.** The list has a `Deployment` column; the detail has a `Deployment` row and says `CRM connection` where it said Instance.
11. **Connection info** (Help or the status area, wherever it lives today): the row reads `Active application`.

### 4.2 Connector (claude.ai or Claude Code with the crmbuilder-v2 connector, after the MCP service restarts)

1. `list_applications` returns ENG-001, ENG-002, ENG-004 and ENG-005 with `engagement_defining_client` and `engagement_visibility`; `get_application("ENG-002")` returns CLI-001, private.
2. `list_deployments` returns the deployments you registered in 4.1 with `deployment_purpose` on every row; `list_deployments(for_client="CLI-002")` returns only the demo/test deployment of an application CRMBuilder may deploy (none, until one is public) plus CRMBuilder's own; `get_deployment("DPL-001")` returns the instance and credential flags, never a token.
3. `select_engagement("ENG-002")` still works and `get_active_engagement` names Cleveland Business Mentors as the defining client. No tool description says engagement except to explain the ENG identifier.

### 4.3 The API directly (optional)

1. `GET /deployments` and `POST /deployments` behave as the connector shows; a POST without `deployment_purpose` is a 422.
2. `POST /deploy-runs` with `deployment_identifier` refuses an unknown deployment (`deployment_not_found`) and one that already holds an instance.
3. `GET /instances` and `GET /instances/{id}/deploy-config` are unchanged.

### 4.4 The migration run's result (right after the rollout)

1. Clients panel lists four clients; Rochester Business Mentors and Boston Business Mentors each run one deployment; Cleveland runs two.
2. Deployments panel under CBM shows DPL-001 to DPL-004 with the right clients, INST-001 to INST-004, and purposes `client_own`; DPL-003's credentials show `(this deployment)` for DigitalOcean and Cloudflare; DPL-004's for DigitalOcean.
3. Applications panel shows ENG-003, ENG-005, ENG-006 and ENG-007 as `archived`; ENG-003 defined by CRMBuilder.
4. Deploy History under CBM lists DEP-001 (Rochester) to DEP-004 (Boston's needs-action run) with their deployments.
5. Under the archived ENG-006, the copied design records are soft-deleted (visible with Show soft-deleted) and each carries the archive note.

## 5. Open items for you, in one place

- Review of the wording DEC-1188 chose and of the retired glossary term Engagement (TERM-001).
- Review of the identifier prefix DPL and its note on TERM-071 (DEC-1185).
- PI-582, the session-filing defect, is Draft; the workaround `CRMBUILDER_V2_SESSION_PROJECT=PRJ-128` in the shell still applies to new sessions.
- Two deferred decisions from the mapping: making the Cleveland application public before a third chapter, and folding ENG-004 into it.

## Change log

| Revision | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.4 | 09-26-26 01:01 | Claude (Claude Code) | PRJ-128 marked complete at Doug's word. |
| 1.3 | 09-26-26 00:58 | Claude (Claude Code) | Acceptance walkthrough ran clean; status set to ACCEPTED. |
| 1.2 | 09-25-26 18:08 | Claude (Claude Code) | Rollout done and recorded (DEC-1190); section 2 is history, section 4 is the open work. |
| 1.1 | 09-25-26 15:52 | Claude (Claude Code) | The ruling is in the code, so the rollout applies the migration run; expectations updated accordingly. |
| 1.0 | 09-25-26 13:52 | Claude (Claude Code), for Doug Bower | First version at the close of the PRJ-128 build. |

# Engagement migration mapping — the seven engagements under the client, application and deployment model

| Field | Value |
|---|---|
| Title | Engagement migration mapping — the seven engagements under the client, application and deployment model |
| Last Updated | 09-24-26 23:20 |
| Revision | 1.0 |
| Status | APPROVED — all seven rows approved by Doug on 09-24-26 in SES-437, one at a time, and recorded as DEC-1176 to DEC-1182. Binding on PI-579. |
| Source | Planning item PI-578 in project PRJ-128. Decisions DEC-1155 (the three terms) and DEC-1175 (classification by hand, row by row). Requirement REQ-653. Written in session SES-437 on 09-24-26 from the production store as it stood that evening. |
| Read by | PI-579, the migration run, which carries out exactly what the approved rows say and nothing else. |
| Replaces | Nothing. Supersedes the intent of PI-447 (Rochester clean-up under DEC-978), whose end state DEC-1175 restated. |

## 1. Why this exists

Seven engagement records exist today. DEC-1155 replaced the words engagement and instance with client, application and deployment. DEC-1175 decided that the seven are classified by hand, once, in a written mapping Doug approves row by row, and that each approved row is recorded as a decision. This document is that mapping. Nothing moves until every row it needs is approved, and the migration run (PI-579) reads this document rather than deciding anything itself.

## 2. Terms used

**Client** (TERM-005): any organisation that uses CRMBuilder as a tool. **Application** (TERM-070): the complete definition of a piece of software, entered by one client, private to that client or public. **Deployment** (TERM-071): one installation of one application on one hosting provider for one client, holding that client's hosting credentials, setting values, secrets, built resources, run history, running release and update policy. **Purpose** of a deployment (REQ-654, PI-577): the client's own, or the defining client's demo/test deployment (TERM-072).

**Engagement** (TERM-001) and **instance** are the old words. Under PI-575 the engagement row becomes the application row and keeps its `ENG-` identifier internally. Under PI-576 one deployment row absorbs an instance, its deploy configuration and the provider credentials that today hang off the engagement. The deployment identifier prefix is put to Doug when PI-576 starts; this document calls each future deployment "the deployment made from INST-NNN of ENG-NNN" and never invents an identifier.

**Design records**: the record types that describe the software rather than an installation of it. In this store today: entities, fields, field options, associations, layouts, roles, teams, field permission rules, filtered tabs, message templates, views, transitions and rules. **Governance records**: requirements, decisions, planning items, projects, sessions, conversations, topics and the rest of the delivery model.

**Retain, not delete** (governance rule): an archived record changes status and stays in the store. No row is removed by this mapping.

## 3. The store as verified on 09-24-26

Read from the production database through the droplet access layer. Counts are live rows (soft-deleted rows excluded) unless stated.

| Engagement | Code and name | Client holding it today | Design records | Instances and deploy configurations | Provider credentials | Governance and other records |
|---|---|---|---|---|---|---|
| ENG-001 | CRMBUILDER — CRMBuilder v2 | CLI-002 CRMBuilder | 61 entities, 344 fields, 12 domains, 15 personas, 20 processes | none | none | 663 requirements, 1,161 decisions, 579 planning items, 131 projects, 407 sessions, 502 conversations, 119 topics, 80 releases, 209 commits, 204 workstreams, and the two role assignments |
| ENG-002 | CBM — Cleveland Business Mentoring | CLI-001 Cleveland Business Mentors | 29 entities (36 with 7 soft-deleted), 606 fields (813 with 207 soft-deleted), 693 field options, 111 associations, 257 layouts, 12 roles, 9 teams, 51 field permission rules, 1 filtered tab, 1 message template, 1 view, 13 transitions, 2 rules | INST-001 CBMTEST at crm-test.clevelandbusinessmentors.org, droplet 561480073; INST-002 CBM Production at crm.clevelandbusinessmentors.org, droplet 577428056; both self-hosted, DNS at Porkbun; both carry a deploy configuration; 1,582 instance membership rows | 1 DigitalOcean (read-only team token) | 16 requirements, 49 decisions, 14 planning items, 5 projects, 14 sessions, 17 personas, 19 mapping candidates, 4 publish runs, 6 reference pointers |
| ENG-003 | ADOTEST — ADO E2E Sandbox | none | none | none | none | 9 projects and 12 planning items, all orchestration test fixtures (marker-file proofs); 36 workstreams, 26 work tasks |
| ENG-004 | CBMMENTOR — CBM Mentoring Custom App | CLI-001 Cleveland Business Mentors | 5 entities (crm_engagement, meeting_note, next_step, progress_goal, session_log), 1 field, 4 associations | none | none | 110 requirements, 99 decisions, 15 planning items, 1 project, 5 sessions, 12 topics, 4 releases, 601 release demands, 445 artifact versions, 43 findings |
| ENG-005 | CRMB3 — CRMBuilderV3 Requirements Capture | CLI-002 CRMBuilder | none | none | none | none. The engagement row and its client link are the only rows. |
| ENG-006 | ROCHNY — Rochester NY Test Instance | none | 29 entities, 573 fields, 768 field options, 93 associations, 257 layouts, 12 roles, 9 teams — all status candidate, all written on 08-31-26 between 03:10 and 03:12 UTC by an audit capture of the instance below | INST-001 "Lakeside rehearsal" at crm-lakeside.acmeconstruction.us, droplet 596478056, DNS at Cloudflare, provisioned by deploy run DEP-001 (succeeded, 08-31-26); 1 deploy configuration; 973 instance membership rows; the server answers today | 1 DigitalOcean ("dougs account"), 1 Cloudflare ("Lakeside Cloudflare Token") | none |
| ENG-007 | BOSTON — Boston Business Mentors | none | none | INST-001 "Boston Business Mentors CRM" at crm.bbmentors.org, droplet 603193973, manual DNS, administrator teresa.lang@bbmentors.org; provisioned by deploy run DEP-003 (needs action; DEP-001 and DEP-002 failed earlier); 1 deploy configuration; the server answers today | 1 DigitalOcean ("boston-DO") | none |

**Access, as verified.** Two principals exist: PRN-001 Doug Bower and PRN-002 Michael Bower. Two role assignments exist, both on ENG-001: PRN-001 owner, PRN-002 editor. The owner role grants access to every engagement, which is how ENG-002 through ENG-007 are reached today. Four API tokens exist, all held by those two principals; a token is bound to a principal, not to an engagement. **No role assignment and no token is scoped to ENG-002, ENG-003, ENG-004, ENG-005, ENG-006 or ENG-007.**

## 4. The mapping

One row per engagement. Each row states what the engagement becomes, who its defining client or deploying client is, what happens to each instance, deploy configuration and provider credential, what happens to its design records, and what happens to access. Every row's Approval line names the decision record that binds it.

### Row 1 — ENG-001, CRMBuilder v2

- **Becomes:** the application CRMBuilder defines for itself. Visibility private.
- **Defining client:** CLI-002 CRMBuilder, the client that already holds it.
- **Instances, deploy configurations, credentials:** none exist; nothing to create.
- **Design records:** stay where they are. The 61 entities and 344 fields are CRMBuilder's own design, recorded under the dogfood.
- **Governance records:** every one stays where it is, under identifier ENG-001. No renumbering.
- **Access:** the two role assignments stay as they are. PRN-001 owner keeps access to every application; PRN-002 editor keeps editor rights on this application.
- **Approval:** approved by Doug on 09-24-26 in SES-437, recorded as DEC-1176.

### Row 2 — ENG-002, Cleveland Business Mentoring

- **Becomes:** the application Cleveland Business Mentors defines: the chapter CRM. Visibility private for now. Making it public, so that any client may deploy it, is a separate later decision; Rochester and Boston deploy it under this mapping because the mapping says so, not because the application is public.
- **Defining client:** CLI-001 Cleveland Business Mentors.
- **Instances:** INST-001 CBMTEST and INST-002 CBM Production each become one deployment of this application, client CLI-001, hosting provider DigitalOcean, purpose the client's own. The deploy configuration of each is folded into its deployment (server address, domain, certificate, administrator and database credential references, DNS provider Porkbun, droplet identifier, backup state). The instance membership rows follow their instance.
- **Provider credentials:** the one DigitalOcean credential (read-only team token) attaches to both of Cleveland's deployments. PI-576 decides whether a credential row is shared by reference or copied per deployment; this mapping requires only that both deployments can reach it.
- **Design records:** stay where they are, as the application's definition. The 7 soft-deleted entities and 207 soft-deleted fields stay soft-deleted.
- **Custom web applications:** the Cleveland application is the application the intake custom web applications built in the cbm-client-intake repository belong to under DEC-1155 (five public intake forms, eleven staff and mentor tools, about thirty-five settings, one hosted web application with its database). Their definition is not yet in the store; ENG-002 holds only the business definition of one process they run (the Mentor Application process, sixteen requirements, decisions DEC-030 to DEC-047, one view, one message template). This mapping does not bring the definition in; that is the separate work DEC-1152, DEC-1153 and DEC-1154 decided.
- **What the deployments carry:** the CRM server only. The three DigitalOcean App Platform applications that run the custom web applications today (production, the crm-test copy and the development copy) are recorded nowhere in the store, so the migration cannot fold them in. They join the deployment record when DEC-1154's hosted web application component is built.
- **Governance records:** stay where they are.
- **Access:** none scoped here today; nothing to move.
- **Approval:** approved by Doug on 09-24-26 in SES-437, with the two clauses above added at his question, recorded as DEC-1177.

### Row 3 — ENG-003, ADO E2E Sandbox

- **Becomes:** archived. The engagement row is marked archived and is not read as an application. Recommended over keeping it because nothing in it is a design and nothing in it has been opened since the orchestration end-to-end tests of June 2026.
- **Defining client:** CLI-002 CRMBuilder, assigned so the archived row satisfies PI-575's rule that an application names a client. No new client record.
- **Instances, deploy configurations, credentials:** none.
- **Design records:** none.
- **Governance records:** the 9 test projects, 12 test planning items, 36 workstreams and 26 work tasks are retained under ENG-003, archived with it, never deleted.
- **Access:** none scoped here.
- **Alternative considered and rejected:** keep it as a live CRMBuilder application named for orchestration testing. Cost: an application with no design appears in every application list.
- **Approval:** approved by Doug on 09-24-26 in SES-437 as archived, recorded as DEC-1178.

### Row 4 — ENG-004, CBM Mentoring Custom App

- **Becomes:** a second application Cleveland Business Mentors defines: the mentor web application. Visibility private.
- **Defining client:** CLI-001 Cleveland Business Mentors, the client that already holds it.
- **Instances, deploy configurations, credentials:** none.
- **Design records:** the 5 entities, 1 field and 4 associations stay where they are.
- **Governance records:** the 97 requirements (110 rows including soft-deleted) and 99 decisions stay where they are. Folding this application into the chapter CRM application (ENG-002), which would renumber them, is a separate later decision per DEC-1175 and is not made here. This is the mentor web application built in the cbm-mentoring-app repository, a different custom web application from the intake ones in cbm-client-intake (see row 2).
- **Access:** none scoped here.
- **Approval:** approved by Doug on 09-24-26 in SES-437, recorded as DEC-1179.

### Row 5 — ENG-005, CRMBuilderV3 Requirements Capture

- **Becomes:** archived. The engagement row is marked archived and is not read as an application. Recommended because the engagement holds no record of any kind beyond its own row and its client link, and the V3 requirements capture it was opened for has since been carried out under ENG-001 (the Master CRMBuilder PRD work and the client, application and deployment model itself).
- **Defining client:** CLI-002 CRMBuilder, already the holder.
- **Instances, deploy configurations, credentials, design records, governance records:** none.
- **Access:** none scoped here.
- **Alternative considered and rejected:** keep it as an empty CRMBuilder application for a future requirements capture. Cost: the same empty-application clutter as row 3, with the added risk that new work lands in it instead of ENG-001 and splits CRMBuilder's own definition across two applications.
- **Approval:** approved by Doug on 09-24-26 in SES-437 as archived, recorded as DEC-1180.

### Row 6 — ENG-006, Rochester NY Test Instance

- **Becomes:** a deployment of the Cleveland chapter CRM application (ENG-002) for a new client record, Rochester. The engagement row ENG-006 is marked archived once its deployment has moved; it is kept, not deleted, as the home of the archived design copy below.
- **Deploying client:** a new client record named Rochester Business Mentors, confirmed by Doug on approval.
- **Instance:** INST-001 "Lakeside rehearsal" becomes one deployment of application ENG-002, client Rochester, hosting provider DigitalOcean, purpose the client's own. Its deploy configuration (server 143.198.4.94, domain crm-lakeside.acmeconstruction.us, Cloudflare DNS, droplet 596478056) is folded in. Its 973 instance membership rows and its one deploy run DEP-001 follow it. The address is a rehearsal domain on Doug's own accounts, not a Rochester-owned domain; Doug chose to migrate it as DEC-1175 says rather than archive it as a rehearsal, because the record is easy to retire later and archiving would leave the credentials and run history homeless.
- **Provider credentials:** the DigitalOcean credential ("dougs account") and the Cloudflare credential ("Lakeside Cloudflare Token") move to the Rochester deployment. They are the deploying client's credentials under DEC-1155 even though the accounts behind them are Doug's today; replacing them with Rochester's own accounts is ordinary deployment maintenance afterwards.
- **Design records:** the copied design (29 entities, 573 fields, 768 field options, 93 associations, 257 layouts, 12 roles, 9 teams) is compared with Cleveland's design by the method in section 5. If the comparison passes, every copied record is archived: status set to an archived state, engagement identifier unchanged, retained under ENG-006. If the comparison fails, PI-579 stops before archiving and reports the differences; no other row is affected.
- **Governance records:** none.
- **Access:** no role assignment and no token is scoped to ENG-006 today, so nothing moves. See section 6 for the rule PI-579 applies if that changes before it runs.
- **Approval:** approved by Doug on 09-24-26 in SES-437 with all four rulings and the client name Rochester Business Mentors, recorded as DEC-1181.

### Row 7 — ENG-007, Boston Business Mentors

- **Becomes:** a deployment of the Cleveland chapter CRM application (ENG-002) for a new client record, Boston Business Mentors. The engagement row ENG-007 is marked archived once its deployment has moved.
- **Deploying client:** a new client record named Boston Business Mentors.
- **Instance:** INST-001 "Boston Business Mentors CRM" becomes one deployment of application ENG-002, client Boston Business Mentors, hosting provider DigitalOcean, purpose the client's own. Its deploy configuration (server 209.97.157.6, domain crm.bbmentors.org, manual DNS, administrator teresa.lang@bbmentors.org, droplet 603193973) is folded in, including any open items the deploy left on it. Its three deploy runs (DEP-001 failed, DEP-002 failed, DEP-003 needs action) follow it as its run history; the failed runs are history, not errors to be repaired by the migration.
- **Provider credentials:** the DigitalOcean credential ("boston-DO") moves to the Boston deployment.
- **Design records:** none. Boston has no copied design, so there is nothing to compare or archive. Boston's CRM was published from the Cleveland application's design and continues to be.
- **Governance records:** none.
- **Access:** none scoped here today; nothing moves. Section 6 applies.
- **Approval:** approved by Doug on 09-24-26 in SES-437, recorded as DEC-1182.

## 5. The Rochester comparison method

**What is being compared.** The design records under ENG-006 were written on 08-31-26 by an audit capture of the Lakeside server, which had itself been published from Cleveland's design. Cleveland's design under ENG-002 has been edited since: 274 of its 606 live fields were created after 08-31-26 and none were deleted after that date. So the two sets are not expected to be identical; the question DEC-1175 asks is whether the copy holds anything Cleveland's design does not, because that is the only thing that would be lost by archiving it.

**Direction.** The comparison is one-directional: every record in the copy must be accounted for in Cleveland's design. Records that exist only in Cleveland's design are not differences; they are the design having grown.

**Match keys.** An entity matches on its name, exact. A field matches on its entity's name plus its own name, compared without regard to letter case. Case-insensitive because the design's authored names for fourteen fields (Amount, Format, Category and their neighbours on Contribution, Event, Resource and Contact) were written capitalised on 06-12-26, while the audit records the engine's camel-case name for the same field; they are one field. A role matches on role name and a team on team name, exact. An association matches on source entity name, target entity name and association name. A layout matches on entity name plus layout type. A field option matches on its field's match plus option value.

**What is compared once matched, and by what rule.** The attributes and equality rules are those of the compared-set declaration (DEC-928, `compared-set-declaration.md`), which already says for every design attribute whether it is compared and how two values are judged equal. Field type is compared after mapping the engine's type name to the design's (the `mapped` rule). Field options are compared as a set. Layout content is compared as the declaration says for each layout type.

**Exclusions.** A copied field marked built-in (`field_built_in` true) that has no counterpart in Cleveland's design is excluded. These are engine-supplied fields the audit reads from every server (today three: Account.isLocked, Meeting.externalService, User.passwordVersion); Cleveland's design never listed them and loses nothing by their absence.

**What counts as a match.** The copy matches Cleveland's design when every non-excluded copied entity, field, role, team, association and layout has a matching record in Cleveland's live design, and every compared attribute on each matched pair is equal under its rule, or differs only in the way section 5.1 lists as accepted. Anything else is a difference and PI-579 stops.

### 5.1 The result measured today, and the one ruling this row needs

Measured on 09-24-26 against the live store, before any migration code exists:

| Set | Copied records | Matched in Cleveland | Not matched |
|---|---|---|---|
| Entities | 29 | 29 | 0 |
| Fields, by name (case-insensitive) | 573 | 570 | 3, all built-in, all excluded |
| Fields, by name and type | 573 | 565 | 5 type differences, listed below, plus the 3 excluded |
| Roles | 12 | 12 | 0 |
| Teams | 9 | 9 | 0 |
| Associations, layouts, field options | 93, 257, 768 | not yet measured at attribute level; entity-level counts agree for layouts (257 and 257) | to be measured by PI-579's rehearsal |

The five type differences are the same difference five times: the audit read `file` (or `money`, once) from the server where Cleveland's design says `text`. They are Account.annualPledgeAmountConverted (money against text), Event.eventGraphic, Event.sponsorGraphic, MentorProfile.profilePhoto and MentorProfile.resumeUpload (file against text). The server is more precise than the design here; the copy holds no information Cleveland's design would want to keep, it holds a correction Cleveland's design might want to make.

**Ruling for row 6 (approved, DEC-1181):** these five are accepted differences. They do not stop the archive. PI-579 records them in the comparison decision as five candidate corrections to Cleveland's design, for Doug to accept or reject in a design session later. Any other attribute difference the rehearsal finds is a stop.

## 6. Access rule PI-579 applies

Role assignments are per engagement and tokens are per principal. Today no principal holds a role on ENG-006 or ENG-007, so the migration moves nothing. The rule for the run, in case that changes before it executes: a role assignment on an engagement that becomes a deployment cannot be carried over mechanically, because the deployment lives under application ENG-002 and granting the same role there would give the principal Cleveland's whole design. PI-579 therefore stops and reports any such assignment instead of widening access silently, and Doug decides that case by hand. Tokens are unaffected because they bind to principals, not engagements.

## 7. Decisions recorded

One decision per row, all recorded in session SES-437 on 09-24-26 under engagement ENG-001.

| Row | Engagement | Decision |
|---|---|---|
| 1 | ENG-001 | DEC-1176 |
| 2 | ENG-002 | DEC-1177 |
| 3 | ENG-003 | DEC-1178 |
| 4 | ENG-004 | DEC-1179 |
| 5 | ENG-005 | DEC-1180 |
| 6 | ENG-006 | DEC-1181 |
| 7 | ENG-007 | DEC-1182 |

## 8. What PI-579 reads from this document

The seven rows of section 4 as approved, the two new client records they name (Rochester Business Mentors; Boston Business Mentors), the comparison method and the accepted differences of section 5, and the access rule of section 6. Nothing in this document is executed by writing it; PI-579 executes it after a backup and a rehearsal, as its own description requires.

## Change log

| Revision | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-24-26 23:20 | Claude (Claude Code) | Row 7 (ENG-007) approved and recorded as DEC-1182. All seven rows approved; status set to APPROVED. |
| 0.7 | 09-24-26 23:16 | Claude (Claude Code) | Row 6 (ENG-006) approved with its four rulings and the client name Rochester Business Mentors, recorded as DEC-1181; section 5.1 ruling marked approved. |
| 0.6 | 09-24-26 23:13 | Claude (Claude Code) | Row 5 (ENG-005) approved as archived and recorded as DEC-1180. |
| 0.5 | 09-24-26 23:06 | Claude (Claude Code) | Row 4 (ENG-004) approved and recorded as DEC-1179; requirement count corrected to 97 live. |
| 0.4 | 09-24-26 23:04 | Claude (Claude Code) | Row 3 (ENG-003) approved as archived and recorded as DEC-1178. |
| 0.3 | 09-24-26 22:58 | Claude (Claude Code) | Row 2 (ENG-002) amended at Doug's question with the custom web applications and what-the-deployments-carry clauses, approved and recorded as DEC-1177. |
| 0.2 | 09-24-26 21:36 | Claude (Claude Code) | Row 1 (ENG-001) approved by Doug and recorded as DEC-1176. |
| 0.1 | 09-24-26 21:26 | Claude (Claude Code), for Doug Bower | First draft. Store state verified from production; seven rows drafted per DEC-1175; comparison method and measured result; access rule. All rows pending approval. |

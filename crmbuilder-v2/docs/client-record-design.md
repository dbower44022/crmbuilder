# The client record above the engagement: design note

| Field | Value |
|---|---|
| Title | The client record above the engagement: design note |
| Last Updated | 09-16-26 00:08 |
| Revision | 1.0 |
| Status | Approved by the product owner, DEC-1092, all seven recommendations accepted |
| Source | PI-512 / REQ-589 / DEC-1077 (segments), DEC-1086 (ownership addendum), DEC-1090 (package shape) |

## 1. Purpose

The store files every record under an engagement, but a client organisation can hold several engagements and some engagements belong to no client. This note designs the client record that sits above the engagement, inside the Client Management package, so that one client holds many engagements and a chapter engagement serves several clients. It is the review gate before any code or migration is written.

## 2. The client record

**Where it lives.** `crmbuilder_v2/segments/client_management/`: the table class in `models.py`, the value sets in `vocab.py`, the request and response shapes in `schemas.py`, a repository `repositories/client.py`, a router `routers/clients.py`, two connector tools in `tools.py`, client methods on the `ClientManagementMethods` mixin, and a panel and two dialogs under `ui/`. The package's `__init__` docstring gains the client record in its ownership sentence.

**Fields.** Table `clients`.

| Column | Type | Notes |
|---|---|---|
| client_identifier | text, primary key | `CLI-NNN`, three digits minimum, assigned by the repository like `ENG-NNN` |
| client_name | text, required | unique, case-insensitive, like the engagement name |
| client_status | text, required | `active`, `inactive`; transitions active to inactive and back |
| client_notes | text, optional | free text |
| client_created_at, client_updated_at | timestamp with zone | as the engagement row |
| client_deleted_at | timestamp with zone, optional | soft delete, restore allowed, as the engagement row |

**Engagement scope.** The client carries no `engagement_id`. It is system-wide, like the principal: the scope filter acts only on tables that use the engagement-scoped mixin, and the client table does not use it, so the scope middleware and the row-level filter leave it alone with no change to either. A client is visible from every engagement, which is the point of a record that sits above engagements.

**Identifier prefix.** `CLI`. The registry of identifier prefixes is the set of format checks on the table classes; the prefixes in use today are ASN, AMP, ARN, AUT, COP, CM, CRM, DUP, DEP, DOM, ENG, ENT, FLD, FMP, FPR, FTB, FND, AGP, GVR, LRN, LSN, PRF, RFE, RFP, SKL, TERM, INST, LAY, MCF, MSG, MIG, OVR, PTC, PER, PRN, PROC, PRJ, PUB, RB, REL, RUN, REQ, ROL, RUL, SMG, SET, TXN, TM, TST, TOK, TRN, VEW, WSK, WTK and WT. `CLI` collides with none. The identifier reservation service covers only the six governance types and needs no change; the repository assigns the next identifier the way the engagement repository does.

**Change log.** The client repository does not emit change-log rows in this planning item. The change-log entity-type check is built from a shared vocabulary set and rebuilt by migrations on the Shared Core branch, so emitting rows for a new type would require a shared-file edit and a Shared Core revision. The engagement repository emits none today either, so the client record matches its parent. This is open question 4.

## 3. The client-to-engagement relationship

The glossary says an engagement serves one client, or a group of clients that share one product definition (a chapter each), and one client may hold many engagements over time. Two shapes fit.

**Shape A, recommended: one link table only.** Table `engagement_clients` with columns `engagement_id` (foreign key to engagements), `client_id` (foreign key to clients), `is_primary` (boolean), and a created timestamp; primary key on the pair; a partial unique index so an engagement has at most one primary client. An ordinary engagement has one row with `is_primary` true. A chapter engagement has one row per member client, one of them primary for display. An engagement with no client has no rows. Cost: every read of "the client of this engagement" is a join through the link table, and the engagement row itself does not name its client.

**Shape B: a nullable client column plus a link table for chapters.** `engagements.client_id` nullable, and `engagement_clients` for the chapter members. Cost: two places can disagree about who serves an engagement, the code must keep them consistent on every write, and the chapter case has one row shape for the primary and another for the members.

Shape A is recommended because it has one source of truth and the chapter case is the same shape as the ordinary case with more rows.

## 4. Scope selection

Today the desktop shell's engagement picker lists every engagement as one row, name and code, and activating a row sets the engagement on the client context and on the `X-Engagement` header. The connector's `select_engagement` tool takes an engagement identifier or code and sets the same header.

**Desktop.** The picker groups rows by client: a client heading, then its engagements indented beneath it, in name order. Engagements with no client sit under a final heading, "No client". Clicking an engagement row activates it as today; clicking a heading does nothing. The top strip shows "Client name, then engagement name (code)" when the engagement has a primary client, and only the engagement when it has none. A chapter engagement shows its primary client in the strip and appears once, under its primary client, in the picker.

**Connector.** `select_engagement` keeps its signature. A new read tool, `list_clients`, returns each client with its engagements, so a caller can find the engagement identifier by client name. `get_active_engagement` also returns the primary client of the active engagement, or none. The header stays an engagement identifier or code, so nothing in the scope middleware changes.

## 5. The migration on the client_management branch

Revision `client_management_0002_clients`, down revision `client_management_0001_branch`. It creates `clients` with its checks and unique index, and `engagement_clients` with its foreign keys, primary key and partial unique index. Downgrade drops both.

**The data step.** Recommended: inside the same revision, after the tables exist, an insert of the clients and link rows, guarded so it runs only when the engagements it names exist and the clients do not. The alternative, a one-time script, leaves a fresh database without the assignment and depends on someone remembering to run it. The assignment, for confirmation:

| Client | Engagements |
|---|---|
| Cleveland Business Mentors (CLI-001) | ENG-002 Cleveland Business Mentoring, ENG-004 CBM Mentoring Custom App |
| CRMBuilder (CLI-002) | ENG-001 CRMBuilder v2, ENG-005 CRMBuilderV3-Requirements Capture |
| none | ENG-003 ADO E2E Sandbox, ENG-006 Rochester NY Test Instance |

**Rehearsal.** As the standing lesson requires: dump the live store, restore into the dev container as a separate database, upgrade to all heads from the branch, confirm the two tables and the six link rows, run the bootstrap check and a brief API start, then drop the copy.

## 6. The API and connector surface

Endpoints under `/clients`: list, get, next-identifier, create, update, patch, delete, restore, and `/clients/{identifier}/engagements`. Under the existing engagements router, `/engagements/{identifier}/clients` (get) and `/engagements/{identifier}/clients` (put, replacing the set with one primary). Connector tools: `list_clients` and `get_client`. Client mixin methods: `list_clients`, `get_client`, `create_client`, `update_client`, `patch_client`, `delete_client`, `restore_client`, `next_client_identifier`, `list_client_engagements`, `get_engagement_clients`, `set_engagement_clients`. Panel "Clients" with a create-or-edit dialog and a delete dialog, and the engagement dialog gains a client chooser.

**Achievable inside the package.** The registry assembles routers, tools, client mixins, panels and entity-type labels from the package, so all of the above lands with no shared-file edit. Two shared edits are needed anyway, both already sanctioned: the sidebar order in `ui/navigation.py` gains "Clients" next to "Engagements" (DEC-1090 keeps that list shared by design), and the shell's picker and top strip (`ui/widgets/engagement_picker.py`, `ui/widgets/engagement_top_strip.py`, the picker call in `ui/main_window.py`) change to show client then engagement, because the picker is shell furniture, not a package screen. The acceptance line "no shared file changed" should read "no shared file changed except the sidebar list and the shell's scope picker". This is open question 3.

## 7. Access control

Principals, tokens and role assignments stay per engagement. No client-level right, role or token is added. A person who may act on two of a client's engagements holds two role assignments, as today. Out of scope by the planning item.

## 8. Risks and open questions

1. **The assignment list** in section 5. Recommendation: confirm as written, including that the two test engagements belong to no client. Cost of a wrong answer: a data migration to move rows later.
2. **Shape A or B** in section 3. Recommendation: A. Cost: a join on every engagement-to-client read.
3. **The acceptance wording** in section 6: two shell files and the sidebar list must change. Recommendation: accept the narrowed wording. Cost: the "no shared file" proof lists three named exceptions.
4. **Change-log rows** for the client record. Recommendation: none in this planning item, matching the engagement record; a later Shared Core revision can add the type for both. Cost: client edits are not in the change history until then.
5. **Client name uniqueness** across the whole store. Recommendation: unique, case-insensitive, like engagement names. Cost: two real organisations with the same name need a distinguishing suffix.
6. **Deleting a client that still has engagements.** Recommendation: refuse; unlink first. Cost: two steps to remove a client.
7. **The header stays an engagement.** Recommendation: yes; a client is never a scope. Cost: none now; a client-wide report later reads across its engagements explicitly.

## 9. Steps for the code phase

1. Migration `client_management_0002_clients` with the data step; rehearse on a clone of the live store. About 1 file plus 1 test.
2. Model, vocabulary, schemas, repository, router, tools, client methods. About 7 files plus 6 tests.
3. Panel, two dialogs, the engagement dialog's client chooser. About 4 files plus 3 tests.
4. The shell's picker and top strip grouped by client; the sidebar entry. About 3 shared files plus 2 tests.
5. Proof: `git diff --stat` showing package files, the migration, and only the three named shared files. About 1 document.

## Change log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 0.1 | 09-15-26 23:53 | Claude (Claude Code, PI-512 lane) | First draft for product-owner review: record shape, link-table recommendation, scope selection, migration and data step, surface, seven open questions. |
| 1.0 | 09-16-26 00:08 | Claude (Claude Code, PI-512 lane) | Approved by the product owner (DEC-1092) with all seven recommendations: the assignment list, shape A, the narrowed acceptance wording, no change-log rows, unique names, refuse-delete-with-engagements, the header stays an engagement. |

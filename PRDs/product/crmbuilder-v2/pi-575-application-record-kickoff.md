# PI-575 kickoff — the application record with a defining client and a visibility

| Field | Value |
|---|---|
| Title | PI-575 kickoff — the application record with a defining client and a visibility |
| Last Updated | 09-24-26 23:29 |
| Revision | 1.0 |
| Status | Ready to run. REQ-653 is confirmed; PI-575 is Draft in PRJ-128; the migration mapping PI-578 is approved (DEC-1176 to DEC-1182). |
| Governs | One session's work: building PI-575, the first of six items in PRJ-128 |
| Source | SES-437 close-out on 09-24-26; REQ-653; DEC-1155, DEC-1175; the mapping at `PRDs/product/crmbuilder-v2/engagement-migration-mapping.md` |

## Opening answer

Paste this as the first line of the new session so the session-open hook classifies it:

> Opening answer: Build PI-575 — the store's engagement row becomes the application record REQ-653 names, gaining a defining client and a visibility, with the access layer, the REST API and unit tests, and no desktop change.

Operating mode: DETAIL.

---

## 1. What this session delivers

The record that today is called an engagement becomes the application: the complete definition one client enters. It keeps its `ENG-` identifier and its scope role over the 77 scoped record types, and gains two facts the new model needs: the defining client, a link to a client record, and the visibility, private or public, defaulting to private. The access layer and the REST API read and write both. The store refuses to create an application that names a missing client. The four engagements a client already holds read as applications of that client; the three that no client holds are refused an application reading until the migration run (PI-579) assigns them as the approved mapping says.

"Done" means PI-575 is merged to `main`, pushed, rolled out to production by Doug, and then marked Resolved through a conversation's `resolves` edge, in that order.

## 2. Governance is already in place

- **REQ-653** "CRMBuilder records clients, applications and deployments" is confirmed. Its acceptance summary is the definition of done for the application part: an application record names its defining client and its visibility, and no application exists without the client it names. Read it from the store.
- **PI-575** is Draft in **PRJ-128** and implements REQ-653. Move it to In Progress when the work starts. Every code commit carries `Governed-By: PI-575` and names an explicit pathspec. Work on a branch (Model A); governance applies on `main`.
- **DEC-1155** defines the three terms; **DEC-1175** decided the migration is by hand; **DEC-1176 to DEC-1182** are the seven approved mapping rows. Read them before touching the schema: they say which engagement becomes which application and who defines it.
- No new requirement is needed for this item. If the work shows REQ-653 is wrong or incomplete, stop and raise it with Doug. Do not widen the work in passing: the deployment record is PI-576, the purpose is PI-577, the migration is PI-579, the desktop and connector rename is PI-580.
- Terms: Client TERM-005, Application TERM-070, Deployment TERM-071. No new term without Doug's approval. "Defining client" and "visibility" are the attribute names DEC-1155 and REQ-653 already use.

## 3. The store as it stands (verified 09-24-26)

- The `engagements` table (`crmbuilder-v2/src/crmbuilder_v2/segments/client_management/models.py`, class `EngagementRow`) has identifier, code, name, purpose, status (`active | paused | archived`), last-opened and the three timestamps. No client column, no visibility column.
- Clients live in `clients`, and the holding is `engagement_clients` (engagement, client, `is_primary`), created by migration `client_management_0002_clients` on the client-management Alembic branch, which is that branch's head. Four rows exist: ENG-002 and ENG-004 held by CLI-001 Cleveland Business Mentors; ENG-001 and ENG-005 held by CLI-002 CRMBuilder. ENG-003, ENG-006 and ENG-007 have no row.
- The access layer is `segments/client_management/repositories/engagement.py` (dataclass `Engagement` in `engagement_models.py`, functions `create_engagement`, `update_engagement`, `patch_engagement`, `list_engagements`, `get_engagement`) and `repositories/client.py` (`get_engagement_clients`, `primary_client_for_engagement`, `set_engagement_clients`).
- The REST surface is `segments/client_management/routers/engagements.py` (`/engagements`, plus `/engagements/{id}/clients` GET and PUT) with schemas in `segments/client_management/schemas.py` (`EngagementCreateIn`, `EngagementReplaceIn`, `EngagementPatchIn`, `EngagementClientsIn`).
- The connector tools for this segment are in `segments/client_management/tools.py` (`select_engagement`, `get_active_engagement`, `list_clients`, `get_client`).
- Tests: `tests/crmbuilder_v2/segments/client_management/test_engagement.py`, `test_client.py`, `test_client_tools.py`; migration tests under `tests/crmbuilder_v2/migration/`, pattern `test_client_management_0002_clients.py`.
- The approved mapping fixes the end state the migration run will produce: ENG-001 defined by CLI-002 (DEC-1176); ENG-002 and ENG-004 defined by CLI-001 (DEC-1177, DEC-1179); ENG-003 and ENG-005 archived under CLI-002 (DEC-1178, DEC-1180); ENG-006 and ENG-007 become deployments of ENG-002 and their rows are archived (DEC-1181, DEC-1182). All visibilities private. **PI-575 does not apply the mapping**; it builds the attributes and the refusals, and PI-579 moves the rows.

## 4. The one design choice to put to Doug first

Where the defining client is stored. Present this in the first turn, in the consequential-decision form, before writing the migration.

- **Option A, reuse the holding (recommended).** The `engagement_clients` row marked `is_primary` is the defining client. No new column for the client; one new column `engagement_visibility` on `engagements`. An engagement with no primary holding is refused an application reading. Cost: "required" is enforced by the read and create paths, not by a NOT NULL column, because three rows legitimately have no client until PI-579 runs. Benefit: no second place records the same fact, and the chapter-engagement shape (several holders, one primary) stays possible.
- **Option B, a new column.** `engagement_defining_client` on `engagements`, nullable until PI-579, with `engagement_clients` kept for other holders. Cost: two places can disagree about who defines an application, and the migration must keep them equal. Benefit: the defining client is one join away with no `is_primary` reasoning.

Whichever Doug picks, record it as a decision naming REQ-653 and PI-575 before the migration is written.

## 5. What to build, in order

1. **Migration** `client_management_0003_application_attributes` on the client-management branch (down revision `client_management_0002_clients`): the visibility column with a CHECK of `private | public` and a default of `private`, back-filled to `private` for every existing row; the defining-client storage per the decision in section 4. Inspector-guarded both ways, with a downgrade. Add the migration test beside `test_client_management_0002_clients.py`.
2. **Model and dataclass**: `EngagementRow` and `Engagement` gain `engagement_visibility` and expose the defining client (identifier and name) in `to_dict()`.
3. **Access layer**: `create_engagement` takes a defining client and a visibility; it refuses, before the row is written, a client identifier that does not exist or is soft-deleted (`client_not_found`, the same shape as the reference existence refusals of REQ-596). `update_engagement` and `patch_engagement` accept a visibility change and a defining-client change under the same refusal. `get_engagement` and `list_engagements` return both attributes. Add `application_of(client)` or equivalent listing so a client's applications can be read; keep the existing holding functions working.
4. **REST API**: the create, replace and patch bodies accept `engagement_defining_client` and `engagement_visibility`; the responses carry them. Add the name **application** alongside the engagement path: `/applications` routes that serve the same rows and schemas (list, get, create, replace, patch), so the connector and the desktop can move to the new word in PI-580 without a second change here. Keep `/engagements` unchanged for every existing caller. A refused client returns the `{data, meta, errors}` envelope with the `client_not_found` code and a 422.
5. **Connector**: no new tools in this item beyond what the application alias needs for PI-580 to build on; if a `list_applications` read tool is trivial, add it, otherwise leave it to PI-580.
6. **Unit tests** cover: the two attributes round-trip on create, replace and patch; the default visibility is private; creating with a missing or deleted client is refused before any row is written; an engagement with no defining client is refused an application reading and still lists as an engagement; the `/applications` alias returns the same records as `/engagements`.
7. **Rollout**: after merge to `main`, run the publish check, and ask Doug to roll out to production (GVR-240: production deploy is human-only). Record the store head after rollout in the PI's resolution and in `CLAUDE.md` only if the bootstrap section needs it.

## 6. Boundaries

- No desktop change, no rename of the `ENG` prefix, no change to the scope middleware or to the 77 scoped tables. Those are PI-580 and a later decision.
- No deployment record, no purpose, no credential move. PI-576 and PI-577.
- Do not assign clients to ENG-003, ENG-006 or ENG-007 and do not archive anything. PI-579 does that from the mapping.
- Keep the deployment identifier prefix question in view: PI-576 opens by putting a prefix and a glossary term to Doug, and PI-579 cannot be written until that is approved. Do not decide it here.
- Record governance in real time: session and conversation under PRJ-128, the section 4 decision when Doug makes it, PI-575 to In Progress at the start and Resolved through the conversation's `resolves` edge at the end, never by a status edit.

## Change log

| Revision | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-24-26 23:29 | Claude (Claude Code), for Doug Bower | First version, written at the close of SES-437 after the mapping was approved. |

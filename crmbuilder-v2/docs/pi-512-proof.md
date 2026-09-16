# PI-512 proof: the client record landed inside the package

| Field | Value |
|---|---|
| Title | PI-512 proof: the client record landed inside the package |
| Last Updated | 09-16-26 00:23 |
| Revision | 1.0 |
| Status | Recorded |
| Source | PI-512 / REQ-589 / DEC-1092, client-record-design.md §6 |

## What was proved

The client record above the engagement, its link table, repository, endpoints, connector tools, desktop client methods, panel and dialogs were built inside `crmbuilder_v2/segments/client_management/` and reached every shared surface through the segment registry. Outside the package, only the files DEC-1092 (question 3) sanctioned changed: the sidebar order, the shell's scope picker and top strip, and the picker call and lookup in the main window. The migration and its test are the other two files outside the package, as the planning item requires.

## The invariant: what changed outside the package

`git diff --stat 1479454b HEAD` (from the approved design note to the last code commit), excluding the package and its tests, verbatim:

```
 .../pg/versions/client_management_0002_clients.py  | 146 +++++++++++++++++++++
 crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py  |  21 ++-
 crmbuilder-v2/src/crmbuilder_v2/ui/navigation.py   |   1 +
 .../crmbuilder_v2/ui/widgets/engagement_picker.py  | 127 +++++++++++++++---
 .../ui/widgets/engagement_top_strip.py             |  22 ++++
 .../test_client_management_0002_clients.py         | 131 ++++++++++++++++++
 6 files changed, 430 insertions(+), 18 deletions(-)
```

Inside the package and its tests:  18 files changed, 2143 insertions(+), 10 deletions(-)

## Counts before and after

| Surface | Before | After |
|---|---|---|
| API routes | 671 | 682 |
| Tables on the metadata | 108 | 110 |
| Connector tools | 134 | 136 |
| Desktop panels | 44 | 45 |
| Alembic heads | 7 | 7 (client_management head is now client_management_0002_clients) |

The eleven new routes: list, next-identifier, get, a client's engagements, create, replace, patch, delete and restore under `/clients`, and get and put under `/engagements/{identifier}/clients`.

## The data step on a fresh database

The migration's assignment step is guarded: it inserts a client only where at least one of the engagements it names exists and the client does not. A fresh database, which has no engagements, gets the two tables and no rows. The migration test seeds the six engagements the live store holds and checks the assignment lands exactly as the design note states, that a second run changes nothing, and that one primary per engagement is enforced.

## Change log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-16-26 00:23 | Claude (Claude Code, PI-512 lane) | First record. |

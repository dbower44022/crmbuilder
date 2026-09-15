# PI-508 throwaway-type proof

| Field | Value |
|---|---|
| Title | PI-508 throwaway-type proof |
| Last Updated | 09-14-26 18:11 |
| Revision | 1.0 |
| Status | Recorded; the throwaway type was removed before the final commit |
| Source | PI-508 / REQ-591 / DEC-1090, segment-package-design.md §5 |

## What was proved

A sixth record type, ProofRow on table cm_proof, was added inside the Client Management segment package and reached every shared surface with no edit to any shared file. The type was then removed. The branch point for the proof was commit 5a39afd1, the last code-move commit.

## The invariant: only package files changed

`git diff --stat 5a39afd1` with the proof in place, verbatim:

```
 .../segments/client_management/client.py           |  7 +++++++
 .../segments/client_management/models.py           | 14 +++++++++++++
 .../client_management/repositories/proof.py        | 20 ++++++++++++++++++
 .../segments/client_management/routers/__init__.py |  3 ++-
 .../segments/client_management/routers/proof.py    | 24 ++++++++++++++++++++++
 .../segments/client_management/schemas.py          |  8 ++++++++
 .../segments/client_management/tools.py            |  8 ++++++--
 .../segments/client_management/ui/__init__.py      |  3 +++
 .../segments/client_management/ui/panels/proof.py  | 11 ++++++++++
 .../client_management/test_contribution.py         | 23 +++++++++++++++++++++
 10 files changed, 118 insertions(+), 3 deletions(-)
```

Every path is under crmbuilder-v2/src/crmbuilder_v2/segments/client_management/ or tests/crmbuilder_v2/segments/client_management/. The shared models module, the shared schemas module, the API application factory, the connector tool list, the desktop client and the panel registry were not touched.

## What each shared surface saw

Output of a Python check run against the tree with the proof in place, verbatim:

```
cm_proof in metadata: True | tables: 112
/proofs routes: ['/proofs GET', '/proofs POST'] | routes: 673
tool list_proofs: True
client list_proofs / create_proof: True True
panel Proofs: True | label proof -> Proofs
```

Before the proof: 111 tables, 671 routes, 134 tools, 44 panels. With the proof: 112 tables, 673 routes (GET and POST /proofs), 135 tools, 45 panels, and the entity type "proof" opens the Proofs panel. The test tests/crmbuilder_v2/segments/client_management/test_contribution.py asserted all five and passed (1 passed in 2.39s). No migration was written; the test builds its schema from the record definitions.

## Removal

The nine package files were restored to commit 5a39afd1 and the three new files plus the test were deleted. `git diff --stat 5a39afd1` afterwards is empty; `git status` shows only this document.

## Change log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-14-26 18:11 | Claude (Claude Code, PI-508 lane) | Proof run and recorded; throwaway type removed. |

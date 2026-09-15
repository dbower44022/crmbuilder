# PI-513 throwaway-type proof

| Field | Value |
|---|---|
| Title | PI-513 throwaway-type proof |
| Last Updated | 09-15-26 00:40 |
| Revision | 1.0 |
| Status | Recorded; the throwaway type was removed before the final commit |
| Source | PI-513 / REQ-591 / DEC-1090, segment-package-design.md §5 |

## What was proved

A fifth record type, OperateProofRow on table op_proof, was added inside the Operate segment package and reached every shared surface with no edit to any shared file. The type was then removed. This repeats the PI-508 proof on the second package, so the invariant holds for a package that was moved by copying the template rather than by designing it.

## The invariant: only package files changed

`git diff --stat 08fd452e` and `git status --short` with the proof in place, verbatim:

```
 .../src/crmbuilder_v2/segments/operate/client.py        |  9 +++++++++
 .../src/crmbuilder_v2/segments/operate/models.py        |  9 +++++++++
 .../crmbuilder_v2/segments/operate/routers/__init__.py  |  8 +++++++-
 .../src/crmbuilder_v2/segments/operate/schemas.py       |  4 ++++
 .../src/crmbuilder_v2/segments/operate/tools.py         | 17 ++++++++++-------
 .../src/crmbuilder_v2/segments/operate/ui/__init__.py   |  3 +++
 6 files changed, 42 insertions(+), 8 deletions(-)

 M crmbuilder-v2/src/crmbuilder_v2/segments/operate/client.py
 M crmbuilder-v2/src/crmbuilder_v2/segments/operate/models.py
 M crmbuilder-v2/src/crmbuilder_v2/segments/operate/routers/__init__.py
 M crmbuilder-v2/src/crmbuilder_v2/segments/operate/schemas.py
 M crmbuilder-v2/src/crmbuilder_v2/segments/operate/tools.py
 M crmbuilder-v2/src/crmbuilder_v2/segments/operate/ui/__init__.py
?? crmbuilder-v2/src/crmbuilder_v2/segments/operate/repositories/op_proof.py
?? crmbuilder-v2/src/crmbuilder_v2/segments/operate/routers/op_proof.py
?? crmbuilder-v2/src/crmbuilder_v2/segments/operate/ui/panels/op_proof.py
?? tests/crmbuilder_v2/segments/operate/api/test_op_proof.py
```

Every path is under crmbuilder-v2/src/crmbuilder_v2/segments/operate/ or tests/crmbuilder_v2/segments/operate/. The shared models module, the shared vocabulary, the shared schemas module, the API application factory, the connector tool list, the desktop client, the panel registry and the main window were not touched.

## What each shared surface saw

Output of a Python check run against the tree with the proof in place, verbatim:

```
op_proof in metadata: True | tables: 112
/op-proofs routes: ['/op-proofs GET', '/op-proofs POST'] | routes: 673
tool list_op_proofs: True | tools: 135
client list_op_proofs / create_op_proof: True True
panel Op Proofs: True | panels: 45 | label op_proof -> Op Proofs
```

A throwaway API test through the shared client fixture created a row with POST /op-proofs (201) and read it back with GET /op-proofs (200): 1 passed.

Before the proof: 111 tables, 671 routes, 134 tools, 44 panels. With the proof: 112 tables, 673 routes, 135 tools, 45 panels, and the entity type "op_proof" opens the Op Proofs panel.

## Removal

The six package files were restored to commit 08fd452e and the three new files plus the test were deleted. `git diff --stat 08fd452e` afterwards is empty; `git status` shows only this document. Counts after removal: routes, tables, tools, panels = 671 111 134 44.

## Deviations from the design note

Two shared types had to leave the shared files, because a package module cannot import a shared module that in turn re-exports the package (an import cycle). The JSON column types (JSONColumn, JSONColumnNoneAsNull) moved from access/models.py to access/base.py, and the request-schema base with the inline governance edge (_Base, GovernanceEdgeIn) moved from api/schemas.py to a new api/schema_base.py. Both are re-exported from their old modules, so no import path changed. The first package did not hit this because none of its five tables used a JSON column and none of its schemas carried an inline edge.

Three things stayed shared on purpose. The instances router moved whole although it also serves Build's operations on an instance (audit, publish, conformance, memberships, record export); those routes move to the Build package when Build moves, and splitting one router file across two packages now would cost more than it saves. The deploy worker package (crmbuilder_v2.deploy) stayed shared because Build's audit worker imports its worker identity helper. The instance membership table stayed in the shared models module because the mapping places it in Build. And api/main.py still names the deploy_runs router module for the worker registration hook; a package-declared startup hook is a follow-on for the registry.

Operate exposes no connector tool today, so its tool factory returns an empty list; the registry finds the segment the same way as every other.

## Change log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-15-26 00:40 | Claude (Claude Code, PI-513 lane) | Proof run and recorded; throwaway type removed. |

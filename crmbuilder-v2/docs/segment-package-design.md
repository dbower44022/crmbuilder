# Segment package design: Client Management first

| Field | Value |
|---|---|
| Title | Segment package design: Client Management first |
| Last Updated | 09-14-26 17:57 |
| Revision | 1.0 |
| Status | Approved by the product owner (DEC-1090), all seven recommendations accepted |
| Source | PI-508 / REQ-591 / DEC-1079 / DEC-1089 / DEC-1090 |

## 1. Purpose

Every new record type today edits six shared files, so two lanes adding two unrelated record types collide in the same places. This note states the shape of one segment package and the registry protocol that lets the shared files discover what packages declare, so a later record type is one new directory and nothing else. Client Management goes first because it is the smallest segment, five record types, and the pattern is cheapest to correct there.

## 2. Package layout

The five record types, from the approved mapping: the engagement registry row, the principal, the access token, the role assignment, and the participant. Their code today is spread over the shared models module, two access modules and one repository, three routers, the shared schemas module, the desktop client, two panels and their dialogs, and the panel registry.

Proposed source layout:

```
crmbuilder-v2/src/crmbuilder_v2/segments/
    __init__.py                 the segment registry (section 3)
    client_management/
        __init__.py             declares the package's contribution (section 3)
        models.py               EngagementRow, PrincipalRow, ApiTokenRow, RoleAssignmentRow, Participant
        schemas.py              EngagementCreateIn / ReplaceIn / PatchIn, ParticipantCreateIn / ReplaceIn / PatchIn,
                                PrincipalCreateIn, RoleAssignIn, TokenMintIn, AgentMintIn
        vocab.py                PARTICIPANT_STATUSES and transitions, PRINCIPAL_KINDS, RBAC_ROLES
        repositories/
            __init__.py
            engagement.py       today access/engagement.py
            principal.py        today access/principal.py
            participant.py      today access/repositories/participant.py
        routers/
            __init__.py         routers: list[APIRouter]
            engagements.py
            principals.py
            participant.py
        tools.py                the connector tools that belong to this segment (today: select_engagement, get_active_engagement)
        client.py               ClientManagementMethods: the desktop client methods for the five record types
        ui/
            __init__.py         panels: dict[label, factory]; entity_type_to_label: dict
            panels/
                engagements.py
                participant.py
            dialogs/
                engagement_crud.py, engagement_delete.py, new_engagement_dialog.py, _engagement_schema.py
                participant_crud.py, _participant_schema.py
```

Proposed test layout, mirroring the source:

```
tests/crmbuilder_v2/segments/client_management/
    test_engagement.py          today tests/crmbuilder_v2/access/test_engagement.py
    test_principal.py           today tests/crmbuilder_v2/access/test_principal.py
    test_participant.py         today tests/crmbuilder_v2/access/test_participant.py
    api/test_engagements_api.py, test_participants_api.py, test_principals_admin.py
    ui/test_engagements_panel.py, test_participants_panel.py, test_engagement_crud_dialogs.py
    test_contribution.py        new: the package declares exactly what section 3 requires
```

Two records stay where they are on purpose. The engagement-scope filter and write stamp (access/engagement_scope.py) and the principal middleware (api/principal_middleware.py, api/principal_deps.py) are Shared Core plumbing under the approved mapping; they read the package's tables but they are not moved. The engagement dataclass and status enumeration (access/engagement_models.py) move with the engagement repository, since only that repository and its callers use them.

## 3. The registry protocol

One rule governs every item below: a package declares, the shared file discovers. Nothing in a shared file names a package. The one place that lists packages is the segment registry, `crmbuilder_v2/segments/__init__.py`, which holds a tuple of package import paths. Adding a segment adds one line there; adding a record type inside an existing segment adds nothing there.

Each package's `__init__.py` exposes one object:

```python
CONTRIBUTION = SegmentContribution(
    name="client_management",
    models=(EngagementRow, PrincipalRow, ApiTokenRow, RoleAssignmentRow, Participant),
    routers=(engagements.router, principals.router, participant.router),
    tools=tool_definitions,            # callable(http) -> list[ToolDefinition]
    client_methods=ClientManagementMethods,
    panels=PANELS,                     # label -> factory
    entity_type_to_label={"engagement": "Engagements", "participant": "Participants"},
)
```

`SegmentContribution` is a small frozen dataclass in `segments/__init__.py`, and `iter_contributions()` imports every package in the tuple and yields its `CONTRIBUTION`.

### 3a. Table metadata

Current mechanism, as read: `access/models.py` defines `Base(DeclarativeBase)` and every table class in one module. The Alembic environment (`migrations/pg/env.py`) does `from crmbuilder_v2.access.models import Base` and sets `target_metadata = Base.metadata`. The bootstrap path and the test fixtures call `Base.metadata.create_all`. A table exists for Alembic and for create_all only if its class has been imported before those calls.

Proposed: `Base`, the two scoping mixins, the four check helpers, and `_utcnow` move to `access/base.py`; `access/models.py` re-exports them. Package model modules import `Base` from `access/base.py`. The shared `access/models.py` ends with one call, `segments.load_models()`, which imports every package's `models` module so their tables register on `Base.metadata`. The Alembic environment and every create_all caller keep importing `Base` from `access/models.py` and see the package tables because that import triggers the load.

Recommendation between the two discovery mechanisms named in the planning item: the import-side-effect registry, not Python entry points. Reason: entry points need a reinstall of the distribution to see a new package, so a worktree that adds a segment and runs the tests without `uv sync` would silently miss it; the registry tuple is read from source and fails loudly on a typo. The cost is one line per new segment in the registry tuple, which is the intended single point of change.

### 3b. Routers

Current mechanism, as read: `api/main.py` imports the routers package and calls `app.include_router(...)` 84 times by name, one line per router, including `principals.router`, `engagements.router` and `participant.router`.

Proposed: each package's `routers/__init__.py` exposes `routers: tuple[APIRouter, ...]`. `api/main.py` replaces the three lines for this segment with one loop over `iter_contributions()` that includes every router each contribution declares. The 81 remaining lines stay until their segments move. Route paths, prefixes, tags and dependencies are unchanged; only the file that holds the router moves.

### 3c. API schemas

Current mechanism, as read: `api/schemas.py` (3,358 lines) holds every request and response model; the engagement and participant schemas live there, while the principal schemas already live inside `api/routers/principals.py`. Sixty-seven source files and one test file import from `crmbuilder_v2.api.schemas`.

Proposed: the package's `schemas.py` defines its Pydantic models. `api/schemas.py` re-exports them by name (`from crmbuilder_v2.segments.client_management.schemas import EngagementCreateIn, ...`) so every existing import keeps resolving. No discovery is needed for schemas: a schema is only ever imported by the router that uses it, and that router now lives beside it. The re-export exists solely for backward compatibility and is removed with the shims in a later release.

### 3d. Connector tools

Current mechanism, as read: `mcp_server/tools.py` defines every tool as an inner coroutine of one function, `tool_definitions(http)`, collects them in a list, and wraps each as a `ToolDefinition`. `register_tools` iterates that list. The two tools that belong to this segment are `select_engagement` and `get_active_engagement`.

Proposed: each package's `tools.py` exposes `tool_definitions(http) -> list[ToolDefinition]` built with the same `ToolDefinition` and `_unwrap` helper, which move to `mcp_server/_tooling.py` so packages can import them without importing the big module. The shared `tool_definitions` becomes: its own remaining list, plus the concatenation of every contribution's `tools(http)`. Tool names stay identical, so the chat dispatcher and the connector see no change.

### 3e. Desktop client methods

Current mechanism, as read: `ui/client.py` is one class, `StorageClient`, with 382 methods; `list_engagements`, `get_engagement`, `create_engagement`, `list_participants` and `create_participant` are among them. Panels and dialogs take a `StorageClient` instance.

Proposed: mixin composition. Each package's `client.py` defines a plain class of methods that expect `self._get`, `self._post` and the other transport helpers `StorageClient` already has. `StorageClient` is declared as `class StorageClient(*segment_client_mixins(), _StorageClientBase)`, where `segment_client_mixins()` reads the contributions. Method names are unchanged, so every panel, dialog and test that calls `client.list_engagements()` keeps working. Registration at runtime (setattr on the class) was considered and rejected: mixins keep the methods visible to type checkers and to a reader of the class.

### 3f. Vocabulary and check constraints

Current mechanism, as read: `access/vocab.py` holds `PARTICIPANT_STATUSES` and its transitions, `PRINCIPAL_KINDS` and `RBAC_ROLES`. The five tables' CHECK constraints in `access/models.py` are written as literal SQL strings, not built from the vocabulary, so no migration rebuilds a constraint from these three sets. `access/models.py` imports `vocab` for other tables' checks, not these.

Proposed: the three sets move to the package's `vocab.py`; `access/vocab.py` re-exports them by name. No migration is needed because no constraint is rebuilt from them and no table changes. This is the one item where a later segment will differ: for a segment whose checks are built from the vocabulary (the field kinds, for example), the constraint-rebuilding migrations import the set by name, and the re-export keeps those migrations importing what they imported at their own revision (lesson LSN-062 applies).

## 4. Backward compatibility

Every existing import path keeps working for one release through re-export shims in the old modules. Counts are files that use the path, source then tests, from a search of the worktree:

| Import path that must keep working | Source files | Test files |
|---|---|---|
| `from crmbuilder_v2.access.models import ...` (any of the five classes) | 117 total importing the module; 13 name one of the five | 106 total; included in the 13 |
| `from crmbuilder_v2.access import engagement` | 5 | 17 |
| `from crmbuilder_v2.access.engagement import ...` | 0 | 1 |
| `from crmbuilder_v2.access import principal` | 2 | 6 |
| `from crmbuilder_v2.access.principal import ...` | 2 | 0 |
| `from crmbuilder_v2.access.repositories import participant` | 1 | 0 |
| `from crmbuilder_v2.access.engagement_models import ...` | 5 | 5 |
| `from crmbuilder_v2.api.routers import (... engagements, principals, participant ...)` | 1 | 8 |
| `from crmbuilder_v2.api.schemas import ...` (engagement and participant schemas) | 67 total importing the module | 1 |
| `from crmbuilder_v2.ui.panels.engagements import ...` | 2 | 3 |
| `from crmbuilder_v2.ui.panels.participant import ...` | 1 | 1 |

Name references to the five classes across source and tests: EngagementRow 51, Participant 29, PrincipalRow 21, ApiTokenRow 15, RoleAssignmentRow 13.

The shims: `access/models.py` re-exports the five classes; `access/engagement.py`, `access/principal.py` and `access/repositories/participant.py` become one-line modules that re-export everything from the package repositories; `api/routers/engagements.py`, `principals.py` and `participant.py` re-export `router`; `api/schemas.py` re-exports the schemas; `access/vocab.py` re-exports the three sets; `ui/panels/engagements.py` and `ui/panels/participant.py` re-export the panel classes. Each shim carries a one-line comment naming PI-508 and the release in which it is removed. The Alembic environment is not touched.

## 5. The throwaway-type proof

The acceptance test for the package shape. Done once, inside the package, and removed before merge; the steps and their result are recorded on the planning item.

1. In `segments/client_management/models.py`, add a sixth class, `ProofRow`, table `cm_proof`, with an identifier column and a name column, on `Base` from `access/base.py`.
2. In `segments/client_management/repositories/proof.py`, add `list_proofs` and `create_proof`.
3. In `segments/client_management/routers/proof.py`, add a router with `GET /proofs` and `POST /proofs`; append it to the package's `routers` tuple.
4. In `segments/client_management/schemas.py`, add `ProofCreateIn`.
5. In `segments/client_management/tools.py`, add `list_proofs`; in `client.py`, add `list_proofs` and `create_proof`.
6. In `segments/client_management/ui/`, add a minimal list panel and register it in the package's `panels` dictionary under the label "Proofs".
7. Run: `git diff --stat` against the branch point shows changes under `segments/client_management/` and `tests/crmbuilder_v2/segments/client_management/` only. That is the invariant.
8. Show it works: `Base.metadata.tables` contains `cm_proof`; the API serves `GET /proofs`; `tool_definitions(http)` contains `list_proofs`; `StorageClient` has `list_proofs`; `PANEL_REGISTRY` contains "Proofs". One test, `test_contribution.py::test_throwaway_type_is_discovered`, asserts all five and is deleted with the type.
9. Remove every file and line from steps 1 to 6 and the test from step 8. Confirm `git diff --stat` against the branch point no longer mentions "proof".

No migration is written for the proof table; the test builds the schema with create_all, and the proof never reaches a database that Alembic manages.

## 6. Risks and open questions

1. **The principal tables are system-wide, not engagement-scoped.** The engagement row is the tenant table every scoped table's foreign key points at; the principal, token and role-assignment rows carry no scope. Moving them into a segment package is a code move only and does not change that. Recommendation: proceed; record in the package's module docstring that these four tables are the scope root and are never filtered by engagement.

2. **The engagement-scope plumbing imports the engagement row.** `access/engagement_scope.py` and the principal middleware reference the engagements and principals tables. Under the mapping they are Shared Core and stay put, importing the classes from the package. This is the Shared Core reading a segment's table, which the ownership rule allows. Recommendation: accept; no alternative keeps the scope root in the Shared Core without duplicating the table.

3. **The panel registry and navigation order stay shared.** `ui/panel_registry.py` names every panel, and `ui/navigation.py` holds the per-phase sidebar order with "Engagements" and "Participants" in it. The panel registry becomes discovery-driven in this planning item; the sidebar order is product design, not code structure, and stays a shared list. Recommendation: leave navigation order shared and note it as the one intentional per-segment edit in the desktop shell.

4. **The three Alembic-sensitive re-exports must outlive the shims.** If a later segment's constraint-building migrations import a vocabulary set by its old path, that re-export cannot be removed with the other shims. Recommendation: for this segment none applies; for later segments, the shim removal step checks `migrations/pg` for imports before deleting a re-export.

5. **Test files that assert on the shared modules' contents.** `test_single_head.py` style tests that enumerate `Base.metadata` or the routers list keep working, because the registry loads packages before those objects are read. One risk is a test that imports `access/models.py` in a way that runs before `segments` is importable (a circular import). Recommendation: the load call sits at the very end of `access/models.py`, and `segments/__init__.py` imports nothing from `access/models.py` at module level.

6. **Open question for the product owner: does the package own its migrations directory now, or after PI-507?** PI-507 introduces one Alembic branch per owner. Recommendation: this planning item writes no migration and leaves the migration tree alone; when PI-507 merges, the client_management branch label is the package's migration home, and a later planning item moves the historical revisions' authorship into documentation only, never the files.

7. **Open question for the product owner: the name of the top-level directory.** `segments/` matches the decision vocabulary (functional segment). The alternative `apps/` is shorter but coins a term the glossary does not define. Recommendation: `segments/`.

## 7. Step list for the code phase

Steps 2 to 5 of PI-508, each a separate commit or small group of commits on branch pi-508.

| Step | Work | Files touched (estimate) |
|---|---|---|
| 2a | `access/base.py` extracted; `segments/__init__.py` with `SegmentContribution`, `iter_contributions`, `load_models`; `mcp_server/_tooling.py` extracted | 5 new or edited |
| 2b | Move the five model classes, three repositories, `engagement_models.py`, the three vocabulary sets, and the schemas into the package; write the shims | 12 moved, 8 shims |
| 2c | Move the three routers and the two connector tools; shims for the routers | 5 moved, 3 shims |
| 2d | Move the client methods into `ClientManagementMethods`; compose `StorageClient` | 2 edited, 1 new |
| 2e | Move the two panels and six dialogs; package `ui/__init__.py`; shims for the two panel modules | 8 moved, 2 shims, 1 new |
| 3 | Registry assembly in `access/models.py`, `api/main.py`, `mcp_server/tools.py`, `ui/client.py`, `ui/panel_registry.py`, `ui/main_window.py` (entity-type labels) | 6 edited |
| 4 | Move the eleven test files into `tests/crmbuilder_v2/segments/client_management/`; add `test_contribution.py` | 12 |
| 5 | The throwaway-type proof: add, verify, record, remove | 8 added then removed |

Acceptance for the whole item, from PI-508: all tests pass; the five classes are no longer defined in the shared models module; the throwaway-type proof is recorded on the planning item; this note is approved.

## Change log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 0.1 | 09-14-26 17:55 | Claude (Claude Code, PI-508 lane) | First draft from reading the five record types' code paths, the router inclusion, the Alembic environment, the connector tool list, the desktop client and panel registry, and the approved mapping. |
| 1.0 | 09-14-26 17:57 | Claude (Claude Code, PI-508 lane) | Approved by the product owner as DEC-1090 with all seven recommendations of section 6 accepted. Status set to Approved; the code phase (section 7) begins. |

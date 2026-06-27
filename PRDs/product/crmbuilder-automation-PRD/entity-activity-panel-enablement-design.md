# Entity Activity-Panel Enablement — Design (PI-338 / REQ-379)

**Engagement:** ENG-001 (CRMBuilder tool) · **Project:** PRJ-068 · **Release:** REL-028
**Requirement:** REQ-379 (confirmed, DEC-767) — *Configure pipeline can enable entity activity panels.*
**Downstream consumer:** ENG-002 PI-009 / REQ-003 (CBM entities expose role-appropriate activity panels).

## Problem

EspoCRM shows the **Activities**, **History**, and **Tasks** bottom panels on an
entity's detail view only when the entity is registered as a possible *parent*
of `Meeting` / `Call` / `Task` — i.e. it appears in
`entityDefs.{Meeting,Call,Task}.fields.parent.entityList` — and the panels are
not `disabled` in the entity's `bottomPanelsDetail` layout.

The Configure pipeline's `entity_manager.create_entity` writes only
`type`, `stream`, labels, and `disabled`. It never performs the parent-list
registration nor enables the panels, so a deployed activity-tracking entity has
no Activities/History/Tasks panels. (`Stream` is the one piece it does set.)

## Empirical findings (probed on the CBM test instance, EspoCRM 9.3.6; prod 9.3.8, same line)

1. **Fresh `createEntity(type=BasePlus)`** auto-registers the new entity in the
   `Meeting`/`Call`/`Task` `parent.entityList` and adds `meetings`/`calls`/
   `tasks`/`emails` links — **but** ships `clientDefs.bottomPanels` with
   `activities`/`history` set `disabled: true`.
2. **Enabling the panels** on an already-registered entity = PUT
   `/{Entity}/layout/bottomPanelsDetail` with
   `{activities:{disabled:false,index},history:{disabled:false,index},tasks:{disabled:false,index}}`
   then `Admin/rebuild`. **Confirmed working, REST-only.** (Note: `clientDefs`
   still reads `disabled:true` — that is the static template default; the layout
   override wins at render. Verify via `Layout/action/getOriginal`, not clientDefs.)
3. **`updateEntity` cannot change an entity's template type or re-register
   parent lists** — it returns `true` but no-ops on `type`. The template/type is
   **fixed at creation**.
4. **Existing entities that are `BasePlus` but absent from the parent lists**
   (the actual CBM-production state) therefore cannot be repaired through REST:
   there is no REST write path to `entityDefs.{Meeting,Call,Task}.fields.parent.entityList`
   (the dead-`put_metadata` constraint).

## Decided approach (DEC-767 program; prod-repair mechanism per Doug, 06-27)

Two deploy paths, chosen by the entity's current state:

### Path 1 — REST layout enable (entity already registered in parent lists)
For an entity already a valid activity parent (e.g. any freshly
`createEntity(BasePlus)` entity), enable the panels by deploying a
`bottomPanelsDetail` layout (Path-1 is pure REST, inside the existing layout
deploy capability). Idempotent.

### Path 2 — SSH metadata patch (entity NOT registered — repair path)
For an existing entity missing parent-list registration, patch the EspoCRM
container metadata over SSH (the server-management layer already owns SSH via
`InstanceDeployConfig`), then rebuild:

1. SSH to the instance (host/user/key from `InstanceDeployConfig`).
2. For each of `Meeting`, `Call`, `Task`: read
   `custom/Espo/Custom/Resources/metadata/entityDefs/{Holder}.json` inside the
   container (create the file/key if absent), add the target entity to
   `fields.parent.entityList` (and `parent.entityTypeList` where present),
   idempotently (no duplicate, preserve existing).
3. Ensure the entity's `meetings`/`calls`/`tasks` links exist (REST `createLink`
   where missing — or include in the same metadata patch).
4. `chown www-data` on touched files (same root-owned-COPY caveat as upgrade),
   `php command.php rebuild` (or `Admin/rebuild`).
5. Re-read metadata to confirm registration; deploy the Path-1 layout to surface
   the panels.

Safety: back up each touched JSON to `/var/backups/espocrm/metadata/{ts}/`
before writing; the patch is a pure-Python JSON merge (unit-testable in
isolation) shipped to the container, never an in-container `sed`.

## Build plan (PI-338)

- **Core (pure, unit-tested):** `merge_parent_entity_list(holder_json, entity)`
  and `build_bottom_panels_detail_layout(indexes)` — deterministic JSON
  transforms, no I/O.
- **REST:** `api_client` method for `bottomPanelsDetail` already exists via
  `save_layout(entity, "bottomPanelsDetail", payload)`; add a thin
  `enable_activity_panels(entity)` orchestration in a new
  `espo_impl/core/activity_panel_manager.py`.
- **SSH:** `automation/core/deployment/activity_metadata_ssh.py` — read/patch/
  write/backup/rebuild the holder metadata files in the container.
- **Validation + audit:** extend the audit round-trip so per-entity panel state
  (registered? panels enabled?) is captured and a re-audit confirms the
  acceptance criterion.
- **Tests:** unit tests for the JSON merges; an integration smoke against the
  test instance (gated/manual) replicating the proven probe.

## Acceptance (REQ-379)

Deploying an activity-type entity through the Configure pipeline registers it in
the Meeting/Call/Task parent lists, the Activities/History/Tasks panels render on
its detail view, and a re-audit reports the panels present.

## Branch / governance

Branch `pi-338-entity-activity-panels` (Model A — code/migration only; the
PI-338 build-closure governance lands on `main` after merge). PI-009 (ENG-002)
then applies Path 1/2 to the nine CBM entities + Stream on `CInformationRequest`
across prod and dev, and re-audits.

# PI-123 — Stage 4 Cutover Runbook (DESTRUCTIVE; Doug in the loop)

This is the **live cutover**: consolidate `CRMBUILDER.db` + `CBM.db` into one
unified DB at the strict schema, repoint the default DB, retire the meta engine,
enable scoping by default. **Run one step at a time at Doug's terminal**
(feedback: `feedback_one_step_at_a_time`). Stages 2 and 3 are done and on the
`pi-123` branch (strict ORM schema + central scoping + the consolidation script
`crmbuilder-v2/src/crmbuilder_v2/migration/unify_engagement_dbs.py` + the
leak/consolidation tests).

## What Stage 2/3 delivered (already on the branch)
- **Strict schema** in the ORM (`access/models.py`): composite
  `(engagement_id, identifier)` PKs/uniques + `engagement_id NOT NULL` FK, built
  by `Base.metadata.create_all`. This is the target the consolidation builds.
- **Process-wide scoping**: the read-filter/write-stamp are registered on the
  base ORM `Session` class (`access/engagement_scope.py::install_engagement_scope`),
  so every session carries them — no factory can write un-stamped rows.
- **Resolver reads the unified `engagements` table** (`engagement.list_engagements_unified`,
  wired into `api/scope_middleware.py`); the scope middleware is the outermost
  middleware so the ContextVar is set before the marker-guard BaseHTTPMiddleware.
- **Consolidation script** `migration/unify_engagement_dbs.py` (`consolidate(...)`):
  builds a fresh unified DB at the strict schema, seeds `engagements` from the
  meta DB, copies each source's scoped rows with `engagement_id` stamped
  (surrogate-`id` tables get a per-engagement offset; `decisions`/`topics`
  self-FKs offset with them), copies catalog once, then validates count +
  identifier parity, no NULL `engagement_id`, and `PRAGMA foreign_key_check`.
- **Tests**: `migration/test_engagement_leak_isolation.py` (the §7 acceptance
  backbone — cross-engagement isolation via the real access layer) and
  `migration/test_unify_engagement_dbs.py` (the consolidation harness against
  synthetic colliding-identifier sources).

## ⚠️ Critical pre-flight finding (discovered in Stage 3)
The live source DBs are **behind head and lack `engagement_id`**:
- `data/engagements/CRMBUILDER.db` — chain **`0036`**, no `engagement_id`.
- `data/engagements/CBM.db` — chain **`0010`** (far behind; missing the v0.4+
  methodology/governance tables and many NOT-NULL columns added since 0010).
- `data/engagements.db` (meta) — holds `ENG-001=CRMBUILDER`, `ENG-002=CBM`.

The consolidation copies **source∩unified columns** and always stamps
`engagement_id`, so a missing `engagement_id` column is fine. **But** a unified
column that is `NOT NULL` with no SQL default and is **absent from a stale
source** (e.g. `decisions.context`, `decisions.executive_summary`, columns added
after 0010) will fail the insert. Therefore:

**The sources MUST be migrated to the current head (`0036`) before consolidation**
(D9 step 1). The blocker: the base-entity-catalog YAMLs are gitignored/absent
(memory `project_v2_catalog_data_gitignored`), so `alembic upgrade head` cannot
run the catalog-seed migrations from scratch. Options to resolve before Stage 4:
1. Restore the catalog YAMLs locally and `alembic upgrade head` each source copy; or
2. Hand-migrate CBM 0010→0036 with the catalog-seed migrations stubbed/skipped
   (CBM may have no catalog rows to seed); or
3. Confirm CBM is acceptable to bring to head via the desktop UI's lazy
   activation migration (which is how it would normally advance).

Do this against **copies** first and re-run `test_unify_engagement_dbs.py`-style
parity checks on the real output before touching the live default DB.

## Cutover steps (each its own turn)
1. **Back up** `data/engagements/CRMBUILDER.db`, `CBM.db`, and `data/engagements.db`
   (`.pre-pi123-backup`).
2. **Pre-flight migrate** copies of both sources to head `0036` (see the finding
   above); refuse to proceed if either is behind.
3. **Consolidate** into `data/v2-unified.db`:
   `uv run python -m crmbuilder_v2.migration.unify_engagement_dbs \
     --unified crmbuilder-v2/data/v2-unified.db \
     --meta crmbuilder-v2/data/engagements.db \
     --source ENG-001=<migrated CRMBUILDER copy> \
     --source ENG-002=<migrated CBM copy> --catalog-source ENG-001`
   Confirm `CONSOLIDATION OK` + per-engagement row counts.
4. **Validate on the real output**: per-engagement count/identifier parity vs the
   migrated sources; re-export each engagement's snapshot from the unified DB and
   diff against `db-export/` on identifiers (not numeric PKs).
5. **Repoint the default DB** at `v2-unified.db`; **retire the meta engine** and
   its chain (`access/meta_db.py`, `migrations/meta/`, `meta_exporter`,
   `run_meta_migrations`, `meta_models.EngagementRow`); make the `/engagements`
   API serve the unified `engagements` table; **enable scoping + enforcement by
   default** (flip `Settings.engagement_scoping_enabled` default / set the env in
   `cli.run_api`). Remove `route_settings_to_engagement` / `CRMBUILDER_V2_DB_PATH`
   file-routing per D6.
6. **Smoke-test** the desktop app + API against the unified DB (switch engagement
   via the marker; confirm reads/writes are correctly scoped).
7. **Cleanup commit** removing the per-engagement source files + meta DB after
   validation in use. Bump `__version__`.

## Close-out (on `main`, after merge — Branch-work protocol)
Author the build-closure close-out payload (DEC-232 / SES-074 pattern): ingest
the branch's slice/cutover commits, mark WTK-026/027/028 + the cutover work tasks
Complete, complete WSK-009 (Development) + the Testing/Data-Migration/Deployment
workstreams, and `resolves_planning_items: [PI-123]`. Author a **DEC** for the
build-discovered refinements: the string-identifier discriminator, the
consolidation-coupled enforce, the **Session-class scope registration** (the fix
for the per-factory un-stamped-write hazard), and the **pre-flight source-migration
requirement** (CBM at 0010). Fold these into `pi-123-unified-db-architecture.md`
(annotate D1/D3/D5/D8/D9). Re-key identifiers to `main`'s heads at authoring.
Once PI-123 is Resolved, **PI-122** (Agent Profile Registry) is unblocked.

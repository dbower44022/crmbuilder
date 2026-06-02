# PI-123 — Unified Multi-Engagement DB: Architecture & Decomposition

**Status:** v0.1 — Architecture/design pass deliverable (produced by the PI-123 Architecture phase, 06-01-26); **annotated 06-02-26 with build-closure refinements (DEC-376)** — see the `Build note (DEC-376)` callouts under D1, D3, D5, D8, D9. The build (Slices 1–3) + cutover (Stages 1–4) shipped on the `pi-123` branch; the build-closure (`close-out-payloads/ses_153.json`) records DEC-376 and resolves PI-123 on `main`.
**Planning item:** PI-123 (Draft → this doc is its Architecture-phase output)
**Project:** PRJ-019 — Production Database Architecture
**Blocks:** PI-122 (Agent Profile Registry) — `PI-122 blocked_by PI-123` (DEC-374)
**Governing decisions:** DEC-373 (scope-aware registry + unified-DB direction), DEC-374 (PRJ-019 project home)
**Predecessor design:** `multi-engagement-architecture.md` v1.1 (the v0.5 per-engagement-DB model this supersedes; the migration it called "PI-017" is now scoped here as PI-123)
**Companion forward dependency:** `agent-profile-registry/agent-profile-registry-PRD-v0.1.md` v0.3 §13.5

---

## 1. Purpose

This document is the **Architecture-phase deliverable** for PI-123. It produces two things the build phases consume:

1. **A design** — the schema change, the access-layer routing rewrite, the data migration, the snapshot/export model, the Alembic-chain collapse, and the ops change, each settled with a decision and a rationale.
2. **A decomposition** — the work broken into ADO phase Workstreams and, within Development, concrete build slices with a serial dependency chain.

It is **not** migration code. No `engagement_id` column is added and no DB is consolidated by this document. The Development and Data-Migration phases do that, taking this design as their spec. Per the build order in registry PRD §14 (**PI-123 → PI-122 → runtime scheduler**), nothing in PI-122 starts until this lands.

---

## 2. The change in one paragraph

CRMBuilder v2 today keeps **one SQLite file per engagement** (`crmbuilder-v2/data/engagements/{CODE}.db`), each with its own Alembic chain, plus a small **meta DB** (`data/engagements.db`) holding the engagement registry. The running API binds to exactly one engagement's file at a time, selected by the `CRMBUILDER_V2_DB_PATH` env var and switched in place by re-pointing `Settings` and rebuilding the engine (`route_settings_to_engagement`, DEC-110/DEC-115). PI-123 replaces this with **a single multi-tenant database** in which every engagement-scoped row carries an `engagement_id` discriminator, the engagements registry becomes a table inside that one DB, and the access layer selects an engagement by **filtering rows** rather than by **selecting a file**. This is the standard multi-tenant model: it is the production-architecture baseline (one DB to back up, migrate, and operate) and the practical enabler of the Agent Profile Registry's cross-engagement learning (DEC-373) — in one DB, the registry's `system | engagement` scope collapses to row scope and cross-engagement learning becomes one `GROUP BY`.

---

## 3. Current state (precise)

Mapped from the live code so the rewrite scope is exact.

| Concern | Current mechanism | File |
|---|---|---|
| Engagement registry | A separate "meta DB" SQLite file with a single `engagements` table + its own Alembic chain (`migrations/meta/`) | `access/meta_db.py`, `access/meta_models.py`, `migration/meta_alembic.py` |
| Per-engagement content | ~38 tables (governance + methodology + catalog) in `data/engagements/{CODE}.db` | `access/models.py` (single `Base`) |
| DB selection | `Settings.db_path` from `CRMBUILDER_V2_DB_PATH`; `get_engine()` caches one engine keyed on `db_url`; re-route resets caches | `config.py`, `access/db.py`, `runtime/engagement_routing.py` |
| Active-engagement marker | `data/current_engagement.json` `{engagement_code, engagement_identifier, set_at}` | `runtime/engagement_routing.py` |
| Identifier assignment | Per-repo `select(Model.identifier)` over the active connection → `next_prefixed_identifier()`; concurrency via `identifier_reservations` + SAVEPOINT retry | `access/_helpers.py`, `access/repositories/*.py` |
| References (edges) | `refs` table; `source_id`/`target_id` are **identifier strings** (`SES-150`), not numeric FKs; all edges intra-engagement today by construction | `access/models.py` (`refs`) |
| Snapshot/export | `session_scope` flushes, `build_snapshot(session)` reads all tables, writes JSON to the active engagement's `engagement_export_dir` | `access/db.py`, `access/exporter.py` |
| Migrations | `alembic upgrade head` per engagement DB, lazy at activation; main chain head **0036**; meta chain separate | `migrations/`, `migration/lazy_migration.py` |

**Live engagements:** two — `CRMBUILDER` (`ENG-001`, the 27 MB dogfood) and `CBM` (`ENG-002`, ~400 KB). Both `active`. The migration consolidates exactly these two files; the design must not assume only two.

**Why identifiers collide under unification.** Identifier sequences are per-engagement today (DEC-082): CRMBUILDER is at `SES-150`, CBM at `SES-001`. Both files independently hold a `sessions` row whose `identifier = 'SES-001'`. The `sessions.identifier` column is `UNIQUE` within each file. Merge the two files naively and that uniqueness is violated — `SES-001` appears twice. This is the central crux the design must solve **without** renumbering history (CBM's `SES-001` must stay `SES-001`; CRMBUILDER's `SES-150` must stay `SES-150`).

---

## 4. Target state

```
                         crmbuilder-v2/data/v2-unified.db   (one file)
   ┌───────────────────────────────────────────────────────────────────────┐
   │  engagements                 ← tenant registry (was the meta DB)        │
   │    id, engagement_code, engagement_name, …, engagement_export_dir       │
   │                                                                          │
   │  ENGAGEMENT-SCOPED tables   (every row has engagement_id NOT NULL FK)    │
   │    sessions, conversations, decisions, planning_items, projects,         │
   │    workstreams, work_tasks, work_tickets, close_out_payloads,            │
   │    deposit_events, commits, reference_books, reference_book_versions,    │
   │    refs, change_log, charter, status, risks, topics,                     │
   │    domains, entities, fields, personas, processes, requirements,         │
   │    crm_candidates, test_specs, manual_configs, engagement_areas,         │
   │    identifier_reservations                                               │
   │      UNIQUE(engagement_id, identifier)   ← per-engagement sequences kept │
   │                                                                          │
   │  SYSTEM/SHARED tables       (no engagement_id — global reference data)   │
   │    catalog_entity, catalog_attribute, catalog_relationship, …(catalog_*) │
   │    alembic_version                                                        │
   └───────────────────────────────────────────────────────────────────────┘
```

The API holds **one engine** against this file. Which engagement a request operates on is resolved per request into a **`ContextVar`**; reads are filtered to that engagement and writes are stamped with it, centrally — not by re-pointing a file.

---

## 5. Design decisions

### D1 — Fold the meta DB into the unified DB; `engagements` becomes the tenant table

The separate meta DB existed to "separate routing metadata from methodology content" when each engagement was its own file (DEC-078). With one file, that separation is moot and a second file is pure overhead (a second engine, a second Alembic chain, the two-database API server of `multi-engagement-architecture.md` §3.10). The `engagements` table moves into the unified DB and becomes the tenant registry: `engagements.id` is the target of every `engagement_id` FK.

- The meta Alembic chain (`migrations/meta/`) is **retired**; its `engagements` table definition is folded into the main `Base` and reaches head via a new main-chain migration.
- `access/meta_db.py`'s separate engine/pool is removed; engagement-registry queries run on the one engine (and are the queries that are **not** engagement-filtered — see D5).
- `engagement_id` is the surrogate `engagements.id` (stable integer PK), **not** `engagement_code` — codes are user-facing and (in principle) renameable; the integer FK is the durable key.

> **Build note (DEC-376):** the discriminator that shipped is the stable **string** identifier `engagements.engagement_identifier` (`ENG-NNN`), **not** an integer surrogate. The identifier is never renamed either, so it *is* the durable key — with less churn and consistency with v2's identifier-keyed model (refs, etc.). The `EngagementScopedMixin.engagement_id` column is `String(32)` FK → `engagements.engagement_identifier`. (`engagement_code` remains user-facing/renameable, as above.)

### D2 — `engagement_id` discriminator on every engagement-scoped table

Every table holding engagement-specific content gets `engagement_id INTEGER NOT NULL REFERENCES engagements(id)`. Three-bucket classification:

- **Engagement-scoped** (get the column): all governance + methodology tables listed in §4. ~30 tables.
- **System/shared** (no column): the `catalog_*` base-entity-catalog tables. The catalog is CRM reference data identical across engagements; it is shared, not per-tenant. Keeping it un-scoped (a) avoids duplicating ~10 catalog tables × N engagements, and (b) is the **precedent the registry reuses** — `engagement_id NULL = system scope` (DEC-373). PI-122's registry tables join this bucket.
- **Tenant registry**: `engagements` itself (the FK target; no self-scoping).

`engagement_id` is `NOT NULL` for the scoped bucket — every governance/methodology row belongs to exactly one engagement. (System scope is expressed by living in the un-scoped bucket, not by a NULL `engagement_id` on a scoped table. The registry's `system | engagement` discriminator in PI-122 is a *nullable* `engagement_id` on the *registry* tables; that is a PI-122 schema choice, consistent with this one.)

Indexing: every scoped table gets `engagement_id` as the **leading column** of its hot indexes, because the active-engagement filter is on every query (§D5). New composite indexes replace single-column ones where the discriminator is now the high-selectivity prefix.

### D3 — Identifier collision → composite `(engagement_id, identifier)` uniqueness

This resolves the §3 crux. For every scoped table that carries a prefixed identifier:

- Replace `UNIQUE(identifier)` with `UNIQUE(engagement_id, identifier)`.
- Per-engagement sequences are **preserved exactly**: CRMBUILDER `SES-150` and CBM `SES-001` coexist; CBM's next session is still `SES-002`, CRMBUILDER's still `SES-151`. No history is renumbered.
- The identifier-assignment helper is unchanged in logic but its **input set narrows to the active engagement**: each repo's `select(Model.identifier)` must carry `WHERE engagement_id = :active`. Under D5's central filter this happens automatically (the select references a mapped class), so per-repo edits are near-zero — but every assignment site is on the **audit list** (§7) because a leak here silently mints a colliding identifier.
- `identifier_reservations` gains `engagement_id` and its lookup index becomes `(engagement_id, entity_type, expires_at)` so concurrent reservations don't cross engagements.
- `refs.reference_identifier` (`REF-NNNN`) similarly becomes `UNIQUE(engagement_id, reference_identifier)`.

> **Build note (DEC-376):** implemented in three constraint classes (see `pi-123-slice3-enforce-plan.md`): **Class A** (19 identifier-as-PK tables + `engagement_areas`) make `engagement_id` part of a **composite PK** `(<identifier>, engagement_id)` via an `EngagementScopedPKMixin`; **Class B** (decisions, planning_items, risks, topics, charter/status versions, reference_book_versions, refs) swap `UNIQUE(identifier)` → `UNIQUE(engagement_id, identifier)` (refs also gets the composite `uq_ref_full` + composite `reference_identifier` unique; `commits` also `UNIQUE(engagement_id, commit_sha)`; `reference_book_versions` gains a composite FK to its parent's composite PK); **Class C** (change_log, identifier_reservations) take NOT NULL + FK + an `engagement_id`-leading index. Coexistence + intra-engagement rejection are pinned by `test_engagement_id_collision_coexistence` and `test_engagement_leak_isolation`.

### D4 — References (`refs`) gain `engagement_id`; edges stay intra-engagement

`refs.source_id` / `target_id` are identifier **strings** scoped to an engagement, so an edge is only meaningful within one engagement. Add `engagement_id NOT NULL`; rewrite the constraints/indexes:

- `UNIQUE(source_type, source_id, target_type, target_id, relationship_kind)` → prefix with `engagement_id`.
- `ix_refs_source` / `ix_refs_target` → prefix with `engagement_id`.
- Edge creation stamps `engagement_id` from the active context (D5's `before_flush`), and both endpoints must resolve to rows in the **same** engagement — add an access-layer assertion (cheap; both endpoint lookups already scope by the active engagement).
- **Cross-engagement edges are explicitly out of scope for PI-123.** The registry's cross-engagement learning (PI-122) does not use `refs` edges across tenants; it uses `GROUP BY content` over `learning` rows. If a future need for a genuine cross-tenant edge arises, it is a separate, deliberate schema change — not a side effect of this migration.

### D5 — Access-layer rewrite: central filter + stamp, not threaded parameters

This is the largest and riskiest piece. The choice is between threading an `engagement_id` argument through ~35 repositories and every router (explicit, verbose, enormous blast radius) and a **centralized** mechanism. We choose centralized:

1. **Active engagement in a `ContextVar`.** A `contextvars.ContextVar[int | None]` holds the active `engagement_id` for the current request/operation. Set by FastAPI middleware (D6); set by the CLI at startup; set by tests via a context manager.
2. **Reads filtered centrally** via a SQLAlchemy `do_orm_execute` event that applies `with_loader_criteria(<scoped-entity>, lambda cls: cls.engagement_id == active, include_aliases=True)` for every mapped class in the engagement-scoped bucket, pulling `active` from the ContextVar. Any `select(Model …)` — including the identifier-assignment `select(Model.identifier)` and `func.max(...)` selects, which reference the mapped class — inherits the filter. The engagements table and catalog tables are **not** registered, so registry and catalog queries are unfiltered.
3. **Writes stamped centrally** via a `before_flush` (or `before_insert` per-mapper) event that sets `engagement_id` from the ContextVar on every new scoped row that doesn't already have it. So repositories keep constructing `SessionModel(...)` without passing `engagement_id`; the stamp is automatic.
4. **A hard guard.** If the ContextVar is unset when a scoped read or write executes, raise (no silent "all engagements" leak). The only code allowed to run scoped queries with no active engagement is explicitly-cross-engagement reporting (none in PI-123) and the data migration (which sets the ContextVar per source engagement).

**Why this over threaded parameters.** It confines the change to one event-registration module plus an audited exception list, instead of editing every repository signature and every router call. It makes the *default* correct (a forgotten filter still gets the central one) rather than the default dangerous. The tradeoff is "magic": the filter is invisible at the call site. We accept it because (a) it is the established SQLAlchemy multitenancy recipe, (b) the alternative's blast radius is far larger and equally error-prone, and (c) §7's leak-test pins the behavior.

**The audit list (raw SQL and bypass paths).** `with_loader_criteria` only covers ORM-entity statements. Anything that bypasses the ORM must be hand-scoped and is enumerated for the Development phase: raw `text()`/`exec_driver_sql` queries, `Core`-level `select(table.c.…)` not bound to a mapper, bulk operations, the exporter's snapshot reads (D7), the change-log emitter, and any `session.get()`/`session.merge()` by numeric PK (PK lookups must additionally assert the loaded row's `engagement_id` matches active, since a PK get is not filtered by loader criteria).

> **Build note (DEC-376):** the ContextVar holds the **string** identifier (`str | None`), matching D1's build-note. Crucially, the read-filter + write-stamp listeners are registered on the **base ORM `Session` class** (process-wide), **not per-sessionmaker** as Slice 2b first did: a session created from a factory that hadn't been (re)registered wrote un-stamped (NULL `engagement_id`) rows under the strict schema — an intermittent, high-rate correctness bug. `get_engine` also builds the factory **under a lock and installs scope before publishing it**. Audit-list outcomes: `engagement_areas`' single-value `session.get` was converted to a scoped `select`; the remaining `session.get` sites are Class B integer-`id` PKs (globally unique post-consolidation → safe), with the user-facing `references.py` id-gets flagged for an `engagement_id`-match guard in the leak-test pass.

### D6 — Request → engagement resolution; the marker-file default preserved

The unified DB *can* serve every engagement concurrently, so a request must say which one it targets. Resolution order, in middleware:

1. **`X-Engagement: <CODE>` header** (or, optionally, a `/engagements/{code}/…` path prefix) → look up `engagements.id`, set the ContextVar.
2. **Fallback: the `current_engagement.json` marker** → the existing single-active default. This keeps every current workflow working unchanged: `crmbuilder-v2-api &` + bare `curl http://127.0.0.1:8765/sessions` resolves to the marker's engagement exactly as today. The desktop UI's engagement switch keeps writing the marker; it no longer needs to re-point a DB file or call `route_settings_to_engagement`.
3. **Engagement-registry endpoints** (`/engagements/*`) and health/admin run **without** an active engagement (they query the un-scoped `engagements` table).

`route_settings_to_engagement` / `CRMBUILDER_V2_DB_PATH` / the two-database API server are removed. `current_engagement.json` survives as the default-engagement marker (not as a file-routing pointer). Backward-compat: an unset `X-Engagement` + a present marker behaves like today; the multi-tenant capability is purely additive (set the header to address any engagement without switching the marker).

> **Build note (DEC-376):** as shipped at cutover — the resolver reads the **unified `engagements` table** (`engagement.list_engagements_unified`), not the meta DB; the scope middleware is the **outermost** middleware so the ContextVar is set in the top-level request task before the marker-guard `BaseHTTPMiddleware` spawns its child task; `route_settings_to_engagement` was **repointed** (not yet removed) to bind the unified DB + enable scoping (the single chokepoint both `cli.run_api` and the desktop activation call). Two items are **deferred to the successor program** (`production-multitenant-api-architecture.md`): the `current_engagement.json` single-active **marker is retired** in favor of a per-request authenticated engagement (D5 there), and the **desktop activation worker is de-filed** — it still pre-flight-migrates + binds the per-engagement file (Steps 3/8), so switching to CBM currently fails at Step 3. `route_settings_to_engagement` / `engagement_db_path` / the meta layer are removed there too.

### D7 — Snapshot/export model: scope the snapshot, keep per-engagement export dirs

`build_snapshot(session)` currently dumps "all tables" — which, in the unified DB, is **all engagements**. It must produce a **per-engagement** snapshot:

- `build_snapshot` takes the active `engagement_id` and filters every scoped table to it (it already runs inside an active-engagement context after a write, so the ContextVar is available; it must be passed explicitly to be safe rather than relying on event filtering of its read queries — see the audit list).
- Output still lands in that engagement's `engagement_export_dir` (the column moves onto the `engagements` table in the unified DB; the `assert_export_dir_ready` gate is unchanged). CRMBUILDER's snapshots keep landing at `PRDs/product/crmbuilder-v2/db-export/`; CBM's at its configured dir.
- Catalog (system/shared) tables: exported once into a shared/system export location, or excluded from per-engagement exports and snapshotted separately. **Decision:** exclude `catalog_*` from per-engagement snapshots (they are reference data, already large and gitignored where they live); a system-snapshot is a deferred nicety, not part of PI-123.
- `session_scope`'s flush→snapshot→commit→promote ordering is unchanged; only the snapshot's row scope changes.

### D8 — Alembic: one chain; an additive forward migration

Collapse to a single chain on the unified DB:

- The main chain continues from head **0036**. New migrations `0037+`: (a) create/fold the `engagements` table into the main metadata; (b) add `engagement_id` to each scoped table; (c) swap the unique constraints/indexes to the composite shape (D3/D4); (d) add the cross-engagement guard indexes.
- SQLite has no real `ALTER … ADD CONSTRAINT`; constraint swaps use Alembic's **batch mode** (`batch_alter_table`, table-rebuild) per affected table. This is the bulk of the migration code — one batch block per scoped table, mechanical but voluminous.
- **Ordering vs. data:** the schema migration adds `engagement_id` as nullable first, the **data migration (D9) backfills it**, then a follow-up migration tightens it to `NOT NULL` and installs the composite constraints. Standard add-nullable → backfill → enforce three-step, so the enforce step can't fail on un-backfilled rows.
- The meta chain is retired; the unified DB's `alembic_version` is the single source of schema truth.

> **Build note (DEC-376):** the **enforce step is NOT an independently-mergeable chain head.** A `0039`-style head setting `NOT NULL` / composite uniqueness would fail on the live per-engagement DBs (whose `engagement_id` is NULL until the engagement-aware backfill, and which the desktop lazy-runs `upgrade head` against). So the strict (enforced) schema is reached by **building the unified DB fresh at the strict schema** (`Base.metadata.create_all` from the current models, which already express the composite keys + NOT NULL + FK) **and copying rows in** (D9) — not by ALTER-ing live tables. The chain ships only through `0038` (nullable `engagement_id`); `create_all` materialises the strict shape. See `pi-123-slice3-enforce-plan.md`.

### D9 — Data migration: consolidate per-engagement files, preserve identifiers

A one-shot, idempotent, **explicit** consolidation (mirrors the v0.5 dogfood migration's posture, §3.7 of the predecessor doc), run once at cutover:

1. **Pre-flight.** Verify every `data/engagements/{CODE}.db` is at main-chain head 0036 (lazy-migrate any that are behind first). Refuse to run if any source is behind or unreachable. Back up every source file (`.pre-pi123-backup`).
2. **Build the unified DB** at `data/v2-unified.db`: create schema at the new head with `engagement_id` nullable (post-D8 step a/b, pre-enforce).
3. **Seed `engagements`** from the existing meta DB (`engagements.db`) — preserving `ENG-NNN` identifiers and `engagements.id` values so existing FKs/markers stay valid.
4. **Per source engagement, in a ContextVar scope:** read every scoped table from `{CODE}.db` and insert into the unified DB with `engagement_id` stamped. **Numeric PKs are reassigned** by the unified DB's autoincrement; this is safe because nothing references rows by numeric PK across tables — `refs` joins by `(engagement_id, identifier)` strings, and the deposit_event/close_out back-references are by identifier too. (The audit list confirms no numeric-PK FK between scoped tables; any found is remapped via an old→new PK map per engagement.)
5. **Copy catalog once** from the dogfood DB (catalog is identical across engagements; pick the canonical source — CRMBUILDER) into the shared bucket; assert CBM's catalog matches (or is absent) before discarding it.
6. **Enforce.** Run the D8 enforce migration (NOT NULL + composite constraints). A constraint failure here means a collision the design didn't anticipate → abort, keep backups, report.
7. **Validate.** Per engagement and per table, assert `COUNT(*) WHERE engagement_id = X` in the unified DB equals `COUNT(*)` in `{CODE}.db`. Assert identifier sets match exactly per engagement. Assert ref edge counts match. Assert no scoped row has NULL `engagement_id`.
8. **Re-export** every engagement's snapshot from the unified DB and diff against the pre-migration `db-export/` to prove byte-equivalence of governance content (modulo intended numeric-PK changes — compare on identifiers, not PKs).
9. **Cutover.** Point the API default at the unified DB; leave source files + backups in place for a rollback window; remove them in a later cleanup commit once validated in use.

Idempotent: a re-run detects the unified DB already populated (engagements seeded + row counts match) and exits cleanly.

> **Build note (DEC-376):** implemented as `migration/unify_engagement_dbs.py` (`consolidate(...)`) and run at the live cutover. Differences from the plan above: (1) the consolidation builds the unified DB **fresh at the strict schema** (per D8's build-note) rather than nullable-then-enforce; (2) surrogate-`id` tables are reassigned by a **per-engagement offset** (with the only intra-scoped integer self-FKs — `decisions.supersedes_id/superseded_by_id`, `topics.parent_topic_id` — offset with them), not autoincrement-with-remap-map; (3) the source DBs **lacked `engagement_id`** and were behind head (CRMBUILDER@0036, CBM@0010), so the copy always stamps `engagement_id` from the source columns rather than reading it; (4) **CRMBUILDER (ENG-001) folded in with exact per-table count/identifier parity + FK-check clean**, but **CBM (ENG-002) was re-created fresh as an empty engagement** — its 16 stale chain-0010 rows predated the schema's NOT-NULL backfills (`executive_summary` etc.) and could not migrate cleanly, so they were discarded by decision; (5) validation = per-engagement count + identifier parity + no-NULL + `PRAGMA foreign_key_check`, plus the cross-engagement leak-test; (6) the byte-equivalence re-export diff (step 8) was satisfied by count/identifier parity since `db-export` itself is on the chopping block in the successor program. Pre-flight migrating stale sources to head is genuinely blocked by the gitignored catalog YAMLs (see `pi-123-stage4-cutover-runbook.md`).

### D10 — Ops: one file to operate

Backup becomes a single `v2-unified.db` copy (and the gitignored data dir shrinks from N files + a meta file + N Alembic chains to one file + one chain). Document the new backup target and the WAL/`busy_timeout` posture (unchanged from `access/db.py`'s `BEGIN IMMEDIATE` + 5 s busy-timeout, which now serializes writers across *all* engagements — acceptable at current scale; a connection-pool/WAL review is a deferred production-hardening item, §9).

### D11 — Registry readiness (forward hook, not built here)

PI-123 deliberately makes the unified DB the "natural home" for PI-122 but **builds no registry tables**. The hooks it leaves: (a) the system/shared bucket and the `do_orm_execute` registration list make "system scope = unfiltered / NULL `engagement_id`" a one-line addition for registry tables; (b) the ContextVar + central stamp/filter is exactly what the registry resolver will reuse; (c) the composite-identifier pattern is the template for any future per-engagement registry identifier. Nothing in PI-123 depends on PI-122; the dependency is one-directional.

---

## 6. Schema-change summary (for the Development phase)

| Table group | Change |
|---|---|
| `engagements` | Move into main `Base`; reached via main chain; FK target. No `engagement_id`. |
| Governance scoped (`sessions`, `conversations`, `decisions`, `planning_items`, `projects`, `workstreams`, `work_tasks`, `work_tickets`, `close_out_payloads`, `deposit_events`, `commits`, `reference_books`, `reference_book_versions`, `refs`, `change_log`, `charter`, `status`, `risks`, `topics`) | `+ engagement_id NOT NULL FK`; identifier uniqueness → composite; hot indexes prefixed with `engagement_id`. |
| Methodology scoped (`domains`, `entities`, `fields`, `personas`, `processes`, `requirements`, `crm_candidates`, `test_specs`, `manual_configs`, `engagement_areas`) | Same as above. |
| `identifier_reservations` | `+ engagement_id`; lookup index → `(engagement_id, entity_type, expires_at)`. |
| Catalog (`catalog_*`) | **No change** — system/shared bucket. |
| `alembic_version` | Single chain; meta chain retired. |

Charter/status are per-engagement singletons today (one row, version-incrementing); they become per-`(engagement_id)` singletons — the version-increment logic scopes to the active engagement (covered automatically by D5's filtered read of the current max version).

---

## 7. The leak-test and the audit list (acceptance backbone)

The single most important test the Testing phase owns: **cross-engagement isolation.** Seed the unified DB with ≥2 engagements that *intentionally share identifiers* (both have `SES-001`, overlapping decision IDs, overlapping ref edges). Then, for **every** repository read/list endpoint and every identifier-assignment path, assert under engagement A's context it returns only A's rows and assigns A's next identifier — never B's. This is the regression net for the D5 "magic."

The Development phase works through an **audit list** of ORM-bypass sites (from D5): raw `text()`/`exec_driver_sql`, Core selects, bulk ops, `session.get`/`merge` by PK, the exporter, the change-log emitter, the next-identifier helpers, and the `apply_close_out.py` script's direct queries. Each is either confirmed safe or hand-scoped, and each gets a line in the leak-test.

---

## 8. Decomposition

PI-123 decomposes into the six ADO phase Workstreams. Architecture is **this document** (complete). The serial chain and per-phase scope:

```
Architecture ─► Development ─► Testing ─► Data Migration ─► Documentation ─► Deployment
  (this doc)      (slices)     (leak)      (consolidate)      (CLAUDE.md)      (cutover)
```

(`blocked_by` chain is serial; Documentation can overlap Testing in practice but is sequenced after for a clean record.)

### Workstream: Architecture — ✅ complete (this document)
Schema design, routing-rewrite strategy, migration plan, decomposition. Output: this doc + the decomposition below.

### Workstream: Development — the schema + access rewrite (slices, serial)

- **Slice 1 — Fold the meta DB in (D1).** Move `engagements` into main `Base`; retire the meta engine/chain; registry endpoints run on the one engine; `/engagements/*` stays unfiltered. Schema-only, no `engagement_id` yet. Migration `0037`.
- **Slice 2 — Add `engagement_id` (nullable) + the central filter/stamp (D2, D5, D6).** Migration `0038` adds nullable `engagement_id` to the scoped bucket; implement the ContextVar, the `do_orm_execute` read filter, the `before_flush` stamp, the unset-guard, and the request middleware with marker-file fallback. Behind the nullable column the system still works single-engagement (marker default).
- **Slice 3 — Composite identifiers + refs scoping (D3, D4).** Migration `0039` (batch-mode constraint swaps) once data is backfilled — but the *constraint code* and the per-repo audit (identifier-assignment sites, refs endpoint same-engagement assertion) land here; the enforce migration is gated on Slice/Phase Data-Migration's backfill.
- **Slice 4 — Snapshot/export scoping (D7).** Scope `build_snapshot` to the active engagement; exclude catalog; keep per-engagement export dirs. Update `session_scope`/`force_export` call sites.
- **Slice 5 — Retire the old routing (D6 cleanup).** Remove `route_settings_to_engagement`, `CRMBUILDER_V2_DB_PATH` file-routing, the two-database server scaffolding; repoint defaults at `v2-unified.db`. Update the desktop switch to write-marker-only.

### Workstream: Testing — the isolation net (§7)
The cross-engagement leak-test across every read/list/assignment path; the audit-list checklist as tests; migration validation harness (§D9 step 7) as an automated test against a fixture pair of engagements with colliding identifiers.

### Workstream: Data Migration — consolidate the live files (D9)
The one-shot idempotent consolidation script + its pre-flight, backups, backfill, enforce, validate, re-export, cutover steps. Run against the live `CRMBUILDER.db` + `CBM.db`. This Workstream *produces the backfill* that gates Development Slice 3's enforce migration, so in execution order the backfill precedes the enforce step (the serial-chain note above).

### Workstream: Documentation — orientation surfaces
Update `CLAUDE.md` (the multi-engagement notes, the routing description, the backup target, the Branch-work/`CRMBUILDER_V2_DB_PATH` references), `multi-engagement-architecture.md` (annotate superseded), and the memory notes that name `data/engagements/CRMBUILDER.db` / `CRMBUILDER_V2_DB_PATH`.

### Workstream: Deployment — cutover + cleanup
Execute the cutover (D9 step 9), validate in use, then a cleanup commit removing the source per-engagement files, the meta DB, and the retired meta chain. Bump `__version__`.

**Resolution.** PI-123 resolves when the final delivering session's close-out includes it in `resolves_planning_items` — i.e., after Deployment cutover is validated. Intermediate slices/workstreams `addresses` PI-123.

---

## 9. Open questions & deferred

- **Concurrency/WAL posture (deferred to production hardening).** `BEGIN IMMEDIATE` + 5 s busy-timeout now serializes writers across all engagements in one file. Fine at current scale (single operator, occasional writes). If concurrent multi-engagement writes become real, evaluate WAL mode + a connection pool. Not in PI-123.
- **SQLite vs. a server DB (Postgres) — out of scope, noted.** The unified row-level-`engagement_id` model is exactly what ports to Postgres later if SaaS scale demands it. PI-123 stays on SQLite; the design choices (no SQLite-only tricks beyond batch-mode DDL) keep that door open.
- **Path-prefix vs. header for engagement addressing (D6).** Header chosen as primary for minimal router change; a `/engagements/{code}/…` prefix is an optional additive convenience the Development phase may or may not add.
- **System-snapshot of catalog/shared tables (D7).** Deferred; catalog is gitignored reference data today.
- **Registry tables (PI-122).** Explicitly downstream; PI-123 leaves the hooks (D11), builds nothing.

---

## 10. Cross-references

- `multi-engagement-architecture.md` v1.1 — the per-engagement-DB model this supersedes; its PI-017 ("multi-tenant API + MCP migration", anchored by DEC-081) is now realized as PI-123. DEC-081's "committed migration at prototype-to-production transition" is the commitment this design discharges.
- `agent-delivery-organization-evolution.md` v0.3 §9A / item 8 — the scope statement and the `system | engagement` registry direction (DEC-373).
- `agent-profile-registry/agent-profile-registry-PRD-v0.1.md` v0.3 §13.3/§13.5/§14 — the registry's dependence on this migration and the build order (PI-123 → PI-122 → runtime).
- `crmbuilder-v2/src/crmbuilder_v2/access/db.py`, `config.py`, `runtime/engagement_routing.py`, `access/meta_db.py`, `access/_helpers.py`, `access/models.py` (`refs`, `identifier_reservations`) — the rewrite surface.
- `specifications/governance-recording-rules.md` — governs this session's close-out.

---

*End of document — PI-123 Architecture phase complete. Next phase: Development (Slice 1).*

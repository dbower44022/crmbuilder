# PI-β — De-file the runtime + kill snapshots + API/MCP-only: Architecture & Scoping

**Status:** v0.1 — PI-β's Architecture/scoping pass (06-02-26). Refines the
program-level design (`production-multitenant-api-architecture.md` D5-partial /
D6 / D7 / D8) into a build-ready removal plan. Not implementation.
**Project:** PRJ-019 — Production Database Architecture.
**Planning item:** PI-β (de-file + kill snapshots + API/MCP-only) — created under
PRJ-019 at PI-α's close-out (`ses_154.json`, draft id **PI-126**).
**Branch:** `pi-beta-defile` (off `main`).
**Builds on:** PI-123 (the unified row-level `engagement_id` DB — the single
store everything now points at). Independent of PI-α's *Postgres* port (PI-β is
dialect-agnostic), but **shares edits** in `access/db.py`, `runtime/engagement_routing.py`,
and `tests/.../conftest.py` — see §7 sequencing.

---

## 0. Scope boundary (what PI-β is and is NOT)

PI-β finishes the runtime's transition out of the per-engagement-file world that
PI-123 made *data*-unnecessary. The data is already one DB; PI-β removes the
*apparatus* that still pretends there are many.

**In scope (PI-β):**
- **D6 — remove the per-engagement-file apparatus:** the meta DB layer, the
  per-engagement-file routing + `engagement_db_path`, the activation-worker
  subprocess swap, the single-active `current_engagement.json` marker, the
  one-shot migrators (`dogfood_v0_5`, `lazy_migration`).
- **D7 — remove the snapshot/export process:** the JSON exporter, the
  `session_scope` export hook, `force_export`, `assert_export_dir_ready`, the
  `meta_exporter`, and the git-tracked `db-export/` tree.
- **D8 — API/MCP-only orientation:** retire the static-JSON file-fallback tier;
  rewrite `CLAUDE.md`, `governance-recording-rules.md`, the orientation/conduct
  docs.
- **D5-partial — per-request engagement via the `X-Engagement` header**, with the
  marker fallback removed; engagement switching becomes a client-side context
  change (this dissolves the broken activation-worker Step 3/8). *Full per-request-
  from-the-authenticated-principal is PI-γ; PI-β just removes the marker and makes
  the header the resolution.*

**Explicitly OUT of scope:**
- **Identity / principals / RBAC** — PI-γ. PI-β leaves the `X-Engagement` header
  unauthenticated (as today); PI-γ adds the principal that constrains which
  engagements a request may select.
- **The Postgres port** — PI-α (already built). PI-β must not depend on a PG
  engine; everything here is dialect-agnostic.

**The governance trail does not disappear — it relocates.** Removing `db-export/`
does not lose history: the git-tracked audit trail becomes the **close-out
payloads** (`close-out-payloads/*.json`) plus the **deposit-event logs**
(`deposit-event-logs/dep_*.log`), both already committed per apply. The DB is the
source of truth; clients read it via API/MCP, never by reading committed JSON.

---

## 1. Current state — the removal surface (from the dependency survey)

Four clusters, each with the dependents that break when it goes (file:line in the
survey; summarized here).

### 1a. Meta DB layer (D6)
`access/meta_db.py`, `meta_models.py`, `migration/meta_alembic.py`,
`migrations/meta/` — a *second* SQLite DB (`data/engagements.db`) holding the
`engagements` registry, with its own engine pool + Alembic chain.
- **Served from:** `api/routers/engagements.py` (all 8 endpoints) via
  `api/deps.py::meta_session()`. `api/main.py` bootstraps + migrates it at startup.
- **Key fact:** PI-123 Slice 1 already folded an identical `engagements` table into
  the **unified** `Base` (`models.py`), and `scope_middleware`/`engagement.list_engagements_unified`
  already read it. So the unified DB *already has* the registry — the meta DB is
  now a redundant second copy. **PI-β deletes the meta copy and points
  `/engagements` at the unified table.**

### 1b. Snapshot / export machinery (D7)
`access/exporter.py` (`build_snapshot`/`write_staging`/`promote_staging`/
`cleanup_staging`), `access/meta_exporter.py`, the `session_scope(export=True)`
hook in `access/db.py`, `force_export`, `runtime.assert_export_dir_ready`.
- **Fires on:** every writable request (`api/deps.py::writable_session` →
  `session_scope(export=True)`), every engagement write
  (`engagement._refresh_snapshot`), `apply_close_out.py`.
- **Writes:** `PRDs/product/crmbuilder-v2/db-export/*.json` (+ `meta/engagements.json`),
  git-tracked.

### 1c. File-routing + activation (D6 / D5)
`runtime/engagement_routing.py` (`route_settings_to_engagement`,
`resolve_active_engagement`, `assert_export_dir_ready`), `migration/lazy_migration.py`
(`engagement_db_path` → `data/engagements/{code}.db`), `ui/activation_worker.py`
(the 12-step subprocess swap that writes `current_engagement.json` and relaunches
the API at the per-engagement file — the **broken "Switching failed at step 3"**),
`migration/dogfood_v0_5.py`.
- **Key fact:** PI-123's cutover already made `route_settings_to_engagement` point
  at the *single* unified file. So per-engagement *files* are already unused at
  runtime; PI-β removes the now-dead routing + the marker + the swap.

### 1d. Orientation file-fallback (D8)
`CLAUDE.md` Tier-2 file-fallback (read `db-export/*.json`),
`PRDs/process/v2-user-process-guide.md`, `specifications/governance-recording-rules.md`.

---

## 2. Design decisions

### D-β1 — `/engagements` serves the unified `engagements` table
Rewrite `api/routers/engagements.py` to use the normal access-layer session
(`writable_session`/`readonly_session`) against the unified DB's `engagements`
table (already in `Base`), and delete `api/deps.py::meta_session`. The endpoints'
shapes are unchanged; only the backing store changes. `engagement.list_engagements_unified`
is already the read path — extend it to cover create/update/delete/next-identifier.
Then delete `meta_db.py`, `meta_models.py`, `meta_alembic.py`, `migrations/meta/`,
and the `api/main.py` meta bootstrap/migration calls. *The transitional
`_IdentifierFormatCheck` import PI-α added to `meta_models.py` disappears with the
file.*

### D-β2 — Engagement is selected per request by the `X-Engagement` header; the marker is removed
`scope_middleware` keeps the `X-Engagement` resolution and **drops the
`current_engagement.json` fallback** (`resolve_active_engagement`). The desktop app
sends its currently-selected engagement as `X-Engagement` on **every** request (the
`StorageClient` already centralizes HTTP); **switching engagements becomes a
client-side context change** — set the header, refresh the panels — not a
subprocess teardown/rebuild. This **deletes `ui/activation_worker.py`** and
dissolves the Step 3/8 failure. CLI (`crmbuilder-v2-api`) no longer routes to a
per-engagement file or reads a marker; it serves the one DB and lets each request
name its engagement. *PI-γ later constrains the header to the principal's allowed
engagements; PI-β leaves it unauthenticated as today.*
- **Sub-decision — no active engagement on a request:** with the marker gone, a
  request that names no engagement and hits a scoped table is an error under
  enforcement (the existing `EngagementScopeNotSet`). The desktop always sends the
  header; MCP/Claude-Code sessions send it (or select via a tool). Document the
  header as required for scoped operations.

### D-β3 — `session_scope` collapses to flush→commit; `db-export/` is deleted
Remove the export hook from `session_scope` (drop the `export=` parameter),
delete `exporter.py`, `meta_exporter.py`, `force_export`, and
`runtime.assert_export_dir_ready` + the `Settings.export_dir`/`__UNCONFIGURED__`
sentinel. **`apply_close_out.py` stops regenerating snapshots** (it keeps writing
the deposit-event log). Delete the git-tracked `db-export/` tree in the same
commit that removes the writer — the close-out payloads + deposit-event logs are
the audit trail. The desktop UI and MCP read live state via the API; nothing reads
the JSON.
- **Sub-decision — the catalog exporter** (`repositories/catalog/exports.py`,
  gated by `assert_export_dir_ready`): determine at the Development phase whether
  it is (a) part of the same db-export snapshotting (remove with it) or (b) a
  separate operator-facing catalog→YAML/JSON dump (keep, but re-gate without
  `assert_export_dir_ready`). Lean (a) — it shares the export-dir gate.

### D-β4 — Retire the one-shot migrators
Delete `migration/dogfood_v0_5.py` (the v0.4→v0.5 meta-DB bootstrap) and the
per-engagement-file parts of `migration/lazy_migration.py` (`engagement_db_path`,
`run_engagement_migrations` if only the file path used it). These ran once at the
v0.5 / unified-DB transitions and have no role in the one-DB world. The
`new_engagement_dialog` create-flow stops computing a per-engagement file path —
creating an engagement is a row insert into the unified `engagements` table via
the API.

### D-β5 — API/MCP-only orientation (D8)
Remove `CLAUDE.md`'s Tier-2 **file-fallback** bullet (keep Tier-2 **MCP** and add
the REST API as the equal alternative); rewrite `governance-recording-rules.md`'s
snapshot-regeneration section to the "DB is source of truth; the git trail is
payloads + deposit logs" model; strip the file-fallback passages from
`v2-user-process-guide.md`. Orientation is **MCP or REST API only**.

---

## 3. Removal order (each step leaves the suite green)

The survey's dependency cascade dictates the order; do it as reviewable slices,
each green:

1. **`/engagements` onto the unified DB** (D-β1 read+write path) — the only
   *functional* change; everything else is deletion. Land this first so the meta
   DB has no readers.
2. **Delete the meta layer** — `meta_db`/`meta_models`/`meta_alembic`/`migrations/meta/`
   + `api/main.py` bootstrap/migration + `api/deps.meta_session`.
3. **Header-only engagement resolution** (D-β2) — drop the marker fallback in
   `scope_middleware`; make the desktop send `X-Engagement` everywhere; **delete
   `activation_worker.py`** + the marker writes; simplify `cli.run_api` + `ui/app`
   startup routing.
4. **Kill the export** (D-β3) — remove the `session_scope` hook + `exporter`/
   `meta_exporter`/`force_export`/`assert_export_dir_ready` + the `export_dir`
   setting; update `apply_close_out.py`; **delete `db-export/`**. (Biggest git
   diff — the tracked JSON tree.)
5. **Retire the one-shot migrators** (D-β4).
6. **Docs** (D-β5).

Tests: every broken caller in the survey is a test to update. The `conftest`
`v2_env` loses `force_export`/`export_dir` (it currently calls `force_export()` and
gates on the export dir) — it simplifies to bootstrap + seed + scope. Expect a
large but mechanical test-surface update (the export-assertion tests
`test_engagement_scope_middleware`, catalog-export tests, the two-database-routing
tests, the launcher-wiring tests all change or go).

---

## 4. Phase decomposition (PI-β Workstreams)

| Phase | Scope |
|---|---|
| **Architecture** | *This document.* |
| **Development** | Slices 1-6 of §3: `/engagements`→unified; delete meta layer; header-only resolution + delete activation worker; kill export + delete `db-export/`; retire migrators. |
| **Testing** | Update/remove the export/meta/two-database/launcher tests; suite green (on SQLite, and on PG once PI-α lands — the harness is shared). |
| **Documentation** | D-β5 doc rewrites (CLAUDE.md, governance-recording-rules, user-process-guide). |
| **Data Migration** | None (no schema change — pure removal). Mark **Not Applicable**. |
| **Deployment** | None beyond the merge. Mark **Not Applicable** (or fold the `db-export/` deletion note here). |

---

## 5. Open questions & deferred
- **Catalog exporter** (D-β3 sub-decision) — keep as an operator dump or remove
  with the snapshot machinery; decided at Development.
- **CLI engagement selection** — once the marker is gone, does `crmbuilder-v2-api`
  need a default/`--engagement` for convenience, or is the header always
  authoritative? Lean: header-only; the desktop/clients always send it. Confirm at
  Development.
- **MCP active-engagement** — the stdio MCP server (Claude Desktop) needs a way to
  name the engagement (a tool arg or a session-level setting) now that there is no
  marker. Likely a small MCP-side change; scope at Development.
- **`apply_close_out.py` snapshot removal vs. the branch-guard/db-export pre-commit
  hook** — the hook that rejects `db-export/` commits off `main` becomes moot once
  the tree is gone; remove it too.

---

## 6. The broken-switch fix (why this is also a bugfix)
The "Switching failed at step 3" dialog that surfaced during the PI-123 cutover is
the activation worker's per-engagement-file step (pre-flight Alembic on a per-file
DB that no longer exists post-cutover). PI-β's D-β2 **deletes the whole subprocess-
swap path** — switching is a header change — so the failure mode is removed by
construction, not patched. (PI-124, the make-dialogs-copyable item, is orthogonal
and stays.)

---

## 7. Sequencing with PI-α (important)
PI-β is *dialect-agnostic* and was scoped "parallel" to PI-α in the program design,
but the two **edit the same files** — `access/db.py` (`session_scope`),
`runtime/engagement_routing.py`, and `tests/.../conftest.py` (`v2_env`). PI-α's
test harness *uses* `force_export`/`export_dir`, which PI-β *deletes*. Cleanest
path: **land PI-α first** (it is done), then build PI-β off the post-PI-α `main` so
the conftest/db.py edits compose instead of conflict. This branch (`pi-beta-defile`)
is currently off the pre-PI-α `main`; rebase it onto `main` after PI-α merges
before the Development slices, or expect a `conftest.py`/`db.py` reconciliation at
merge (the DEC-232 build-closure pattern handles it either way).

---

## 8. Cross-references
- `production-multitenant-api-architecture.md` (D5/D6/D7/D8 this refines;
  D1/D9/D10 = PI-α, D2/D3/D4 = PI-γ).
- `pi-alpha-postgres-foundation-architecture.md` (the shared-file sequencing in §7).
- The PI-β dependency survey (this session) — the file:line removal inventory the
  Development slices consume.

*End of document — PI-β Architecture/scoping pass v0.1. Next: rebase onto post-PI-α
`main`, then Development slice 1 (`/engagements` onto the unified DB).*

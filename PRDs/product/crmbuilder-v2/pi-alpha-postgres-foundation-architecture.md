# PI-α — Postgres Foundation: Architecture & Scoping

**Status:** v0.1 — PI-α's own Architecture/scoping pass (06-02-26). Refines the
program-level design (`production-multitenant-api-architecture.md` §D1, D9, D10,
D11) into a build-ready plan for **just the Postgres foundation**. This is the
design the PI-α Development/Testing/Data-Migration/Deployment phases consume; it
is **not** implementation.
**Project:** PRJ-019 — Production Database Architecture.
**Planning item:** PI-α (Postgres foundation) — *to be created under PRJ-019 at
this session's close-out; identifier server-assigned.*
**Branch:** `pi-alpha-postgres`.
**Builds on:** the PI-123 unified row-level `engagement_id` schema, the central
ContextVar scope filter/stamp, and the Session-class listener registration — all
carried forward **unchanged**.

---

## 0. Scope boundary (what PI-α is and is NOT)

PI-α swaps the **store** under an otherwise-unchanged runtime. It is deliberately
the *narrowest* foundation slice so PI-β (de-file + kill snapshots) and PI-γ
(identity/RBAC) land on a stable Postgres base.

**In scope (PI-α):**
- Postgres as the store (D1): URL/driver/config, dialect-conditional engine build.
- `JSON` → `JSONB` (D1) on the ~12 JSON columns.
- Drop the SQLite transaction hacks; add a real connection pool (D10).
- A **fresh PG Alembic baseline** at the current strict models — the SQLite
  batch-mode chain (0001–0038) is **not** replayed on PG.
- The one-shot, validated `v2-unified.db` → Postgres data migration (D9),
  including the cross-engagement leak-test re-run on PG.
- The full test suite (2343 tests) green on Postgres in CI + locally.
- Hosting: local Docker PG for dev/test; the prod topology decision (D11) pinned
  at PI-α's Deployment phase.

**Explicitly OUT of scope (deferred to their PIs):**
- Removing the meta layer, per-engagement file routing, activation-worker swap,
  the single-active marker — **PI-β (D6)**. PI-α keeps them working on PG.
- Removing the snapshot/export process (`session_scope` export hook, `db-export/`)
  — **PI-β (D7)**. The export is DB-agnostic (it reads ORM state and writes JSON);
  it survives the PG port untouched. *This is a clean seam — see §6.*
- Identity, tokens, RBAC, principals — **PI-γ (D2/D3/D4)**.
- API/MCP-only orientation rewrite — **PI-β (D8)**.

**The seam that makes PI-α small:** every component PI-β/PI-γ will delete is
*dialect-agnostic*. The meta DB, the snapshot exporter, the activation worker, and
the file router all operate above SQLAlchemy's dialect layer or on their own
SQLite meta engine. PI-α changes only the *primary* engagement engine's dialect.
The meta engine (`meta_db.py`) **stays SQLite** through PI-α (it's a tiny local
registry PI-β deletes wholesale); porting it to PG would be wasted work.

---

## 1. Current state — the SQLite-specific surface (precise)

Everything dialect-specific is concentrated in five places. PI-α touches exactly
these and nothing else in the access layer.

| # | Location | SQLite-specific thing | PI-α action |
|---|---|---|---|
| 1 | `config.py:106` `db_url` | `f"sqlite:///{self.db_path}"` | URL construction becomes driver/dialect-aware (§2) |
| 2 | `access/db.py:29-47` `_enable_sqlite_pragmas` | `PRAGMA foreign_keys=ON`, `busy_timeout=5000`, `isolation_level=None` | dialect-guarded; no-op on PG (§3) |
| 3 | `access/db.py:50-61` `_sqlite_emit_begin` + `_build_engine` | `event.listen(..., "begin", BEGIN IMMEDIATE)` | dialect-guarded; PG uses standard SQLAlchemy `begin` (§3) |
| 4 | `access/db.py:57` `create_engine(url, future=True)` | no pool args (SQLite default `SingletonThreadPool`/`NullPool`) | add `QueuePool` config for PG (§4) |
| 5 | `migrations/env.py:28-79` | `render_as_batch=True`, sqlite connect pragmas, `BEGIN IMMEDIATE` | PG path: no batch, no pragmas, standard transaction (§5) |

**Dialect-agnostic — explicitly carried forward unchanged** (verified by read):
- `access/engagement_scope.py` — the `do_orm_execute` read-filter + `before_flush`
  write-stamp registered on the **base ORM `Session` class**. Pure ORM events; no
  SQL dialect dependence. **Unchanged.**
- `access/models.py` composite PKs / composite uniques / FKs / partial-unique
  indexes — all native to Postgres.
- `EngagementScopedPKMixin` and the Class A/B/C keying — native to PG.
- The snapshot exporter and `session_scope`'s export hook — read ORM state, write
  JSON files. **Unchanged in PI-α** (PI-β removes them).

**JSON columns (the JSONB targets), enumerated** from `access/models.py`:

| Line | Column | Notes |
|---|---|---|
| 156, 175 | `close_out_payload.payload`, `work_ticket.payload` | `dict`, NOT NULL |
| 282 | session medium metadata (`default=list`) | array |
| 285 | session medium metadata (`default=dict`) | object |
| 398 | work-area labels — **`JSON(none_as_null=True)`** | load-bearing: must preserve on PG (§3.1) |
| 1737, 1740, 1742 | deposit_event `records_summary` / `error_info` / `apply_context` | diagnostic JSON |
| 1807 | `commit.commit_parent_shas` (`default=list`) | 0/1/2 SHA array |
| 2225, 2226 | change_log `before_payload` / `after_payload` | nullable dict |
| 2262 | identifier-reservation `reserved_identifiers` | array; not exported |

All use SQLAlchemy's **generic `JSON`** type (no `dialects.sqlite.JSON`), so the
switch to JSONB is a single type-alias change applied across these columns.

---

## 2. D1 — Store: URL, driver, configuration

**Driver: psycopg 3 (`psycopg`), sync mode.** Rationale: psycopg3 is the current
SQLAlchemy-recommended PG driver, has first-class SQLAlchemy 2.0 support, ships
binary wheels (`psycopg[binary]`), and supports both sync and (later) async on the
same package — so a future async move (deferred, §9) needs a driver-mode change,
not a dependency swap. SQLAlchemy URL: `postgresql+psycopg://…`.

**Config (`config.py`).** Introduce a first-class database-URL setting that
*defaults to the SQLite path* (so PI-β-and-earlier code, and the meta DB, keep
working) but accepts a full PG URL:

```
CRMBUILDER_V2_DATABASE_URL   # e.g. postgresql+psycopg://crmb:…@localhost:5432/crmbuilder_v2
```

- If `CRMBUILDER_V2_DATABASE_URL` is set → `db_url` returns it verbatim; the engine
  is Postgres. `db_path` becomes meaningful only for the (still-SQLite) meta DB and
  the migration *source*.
- If unset → `db_url` returns the existing `sqlite:///{db_path}` (unchanged
  default; nothing breaks for anyone who hasn't provisioned PG).

`db_url` therefore becomes the single dialect switch the rest of the code reads.
`Settings` validates the URL scheme and surfaces a clear error on a malformed PG
URL.

**Decision — keep the SQLite default through PI-α.** PI-α makes PG *possible and
validated*, it does not make PG *mandatory*. The default install stays SQLite
until the whole suite is green on PG and the prod migration is rehearsed; flipping
the default to PG is the last step of PI-α's Deployment phase (or early PI-β).

---

## 3. D1 — JSON → JSONB; D10 — drop the SQLite transaction hacks

### 3.1 JSONB
Replace the generic `JSON` import usage with a **dialect-variant type** so SQLite
(meta DB, migration source, and any SQLite-default install) keeps `JSON` while
Postgres gets `JSONB`:

```python
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

# one module-level alias in models.py:
JSONColumn = JSON().with_variant(JSONB(), "postgresql")
```

- Every `mapped_column(JSON, …)` becomes `mapped_column(JSONColumn, …)`.
- **`none_as_null=True` (line 398) is load-bearing** and must be preserved: the
  variant for that column is
  `JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")`.
  A dedicated `JSONColumnNoneAsNull` alias covers it. Without it, Python `None`
  serializes to the JSON text `'null'` rather than SQL NULL — a behavior the
  work-area-labels query depends on.
- `default=list` / `default=dict` are dialect-agnostic and unchanged.
- **JSONB ordering caveat:** JSONB does not preserve object key order or duplicate
  keys. Audit the JSON columns for any reader that depends on key order or
  round-trip byte-identity. None are expected (they're all read back as `dict`/
  `list`), but the Testing phase asserts round-trip equality per column.

### 3.2 Drop the SQLite transaction hacks (PG path)
`_enable_sqlite_pragmas` and `_sqlite_emit_begin` exist solely to make SQLite behave
under concurrent writers and to fix pysqlite's autocommit-emulation SAVEPOINT bug.
**None of these apply to Postgres** — PG has MVCC, real transactions, and proper
SAVEPOINT semantics out of the box.

`_build_engine` becomes dialect-conditional:

```python
def _build_engine(url: str) -> Engine:
    engine = create_engine(url, future=True, **_pool_kwargs(url))
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _enable_sqlite_pragmas)
        event.listen(engine, "begin", _sqlite_emit_begin)
    return engine
```

On PG: no connect-pragma listener, no `BEGIN IMMEDIATE` — standard SQLAlchemy
transaction control. `expire_on_commit=False` on the sessionmaker stays (it is
dialect-agnostic and load-bearing for the API's detached-instance reads).

**The autocommit-emulation SAVEPOINT bug the SQLite hack fixed does not exist on
PG** (DEC, v0.7 governance note) — PG SAVEPOINTs roll back correctly. The
governance-entity post-insert edge-rule validation that motivated the SQLite fix
works correctly on PG with no special handling. The Testing phase re-runs the
governance orphan-row regression test on PG to confirm.

---

## 4. D10 — Connection pool

**Decision: sync SQLAlchemy + `QueuePool`.** Keep the API synchronous (FastAPI sync
endpoints on the threadpool — its current shape); do **not** move to async in PI-α
(§9 defers it). A sync `QueuePool` against psycopg3 gives concurrent readers *and*
writers via PG MVCC — the single-writer `BEGIN IMMEDIATE` serialization is gone.

`_pool_kwargs(url)`:
- **PG:** `poolclass=QueuePool, pool_size=…, max_overflow=…, pool_pre_ping=True,
  pool_recycle=…`. `pool_pre_ping=True` defends against managed-PG idle-connection
  drops; `pool_recycle` (e.g. 1800s) defends against server-side connection
  timeouts. Sizes are env-configurable with sane defaults; pinned against the
  prod topology at the Deployment phase, and validated against PI-100's
  concurrent-writer scale target during Testing.
- **SQLite:** unchanged (no pool kwargs; SQLAlchemy's default for `sqlite:///`).

The `_engine_lock` double-checked-locking factory build (db.py:64-97) and the
install-scope-before-publish ordering are **unchanged** — they are concurrency
correctness for the factory rebuild, orthogonal to the pool.

---

## 5. D1 — Alembic: a fresh Postgres baseline

**Decision: PG gets its own baseline revision, not the replayed batch chain.**
The 0001–0038 chain is SQLite-batch-mode (`render_as_batch=True`, table copy/drop
DDL) and encodes SQLite-shaped intermediate states. Replaying it on PG is both
unnecessary (PG does in-place `ALTER`) and risky (some batch ops have no clean PG
analogue). Mirrors PI-123's "build fresh + copy rows" posture.

Plan:
1. A **single PG baseline migration** materializes the *current* strict schema
   directly from `Base.metadata` (autogenerate against an empty PG, hand-reviewed),
   stamped as the PG head. PG starts there and grows its **own** forward chain.
2. `migrations/env.py` becomes dialect-aware: `render_as_batch=True` and the
   sqlite connect pragmas apply **only** when the URL is SQLite; on PG, batch mode
   is off and migrations run as standard transactions.
3. Two heads coexist by design: the SQLite chain (frozen at 0038 — only the
   still-SQLite meta DB and legacy SQLite installs touch it) and the PG baseline.
   They are not cross-applied. *Document this explicitly so a future contributor
   doesn't try to `alembic upgrade head` a PG DB through the batch chain.*
4. **Open sub-decision for the Development phase:** single Alembic environment with
   dialect branching, vs. a separate PG migration tree (like `migrations/meta/`).
   Lean toward dialect-branching in the existing `env.py` (one head to reason
   about); revisit if the branch logic gets unwieldy.

---

## 6. D9 — Data migration: `v2-unified.db` → Postgres

The payoff of PI-123: the source is already a single, validated, fully-stamped
unified DB. **A straight table-by-table copy — no offset gymnastics** (the
consolidation already reassigned surrogate ids and stamped `engagement_id`; the
data is internally consistent).

Reuse the posture (and much of the harness) of
`migration/unify_engagement_dbs.py::consolidate`:

1. **Stand up PG schema** at the strict models (the PG baseline migration / a
   guarded `create_all`). Empty target; refuse to run against a non-empty PG (the
   `consolidate`/`FileExistsError` analogue).
2. **Copy every engagement-scoped + system table** from `v2-unified.db` into PG,
   `engagement_id` preserved verbatim. Order tables so FK parents precede children;
   disable/defer FK checks during load (PG `SET CONSTRAINTS ALL DEFERRED` inside the
   txn, or load with session_replication_role, then re-validate). Self-FKs
   (`decisions.supersedes_id`, `topics.parent_topic_id`) copy as-is — no remapping,
   because the unified ids are already final.
3. **Copy `catalog_*`** (system/shared) once.
4. **Reset PG sequences** to `max(id)+1` per table with a surrogate `id` — critical:
   a bulk copy of explicit `id`s leaves PG's `SERIAL`/identity sequence at 1, so the
   next insert collides. (No SQLite analogue; this is the one genuinely new
   migration step vs. the SQLite consolidation.)
5. **Validate** (the PI-123 D9 acceptance set, on PG): per-engagement per-table row
   counts vs. source; identifier-set parity per engagement; FK integrity
   (`information_schema`/explicit FK validation in place of `PRAGMA
   foreign_key_check`); and a **cross-engagement isolation re-run of the PI-123
   leak-test against PG** (`test_engagement_leak_isolation.py` parametrized to run
   on the PG engine).
6. **Idempotent + re-runnable** into a fresh target; one-shot for the real cutover.

**Snapshot export during PI-α:** `session_scope` still runs its JSON export hook
(it reads ORM state — dialect-agnostic). It keeps working against PG with no
change. PI-β removes it. The migration script itself uses `export=False` (as the
bootstrap path already does).

---

## 7. D11 — Hosting / deployment

- **Dev/test:** local **Docker Postgres** — a `docker-compose` (or `compose.yaml`)
  service, ephemeral per-developer; **CI spins one up** (GitHub Actions
  `services: postgres:` or a compose step) and runs the suite against it. A
  `make`/`uv` target stands up PG + applies the baseline + (optionally) runs the
  migration from a checked-out `v2-unified.db` copy.
- **Prod:** **DigitalOcean Managed Postgres** (matches the existing droplet/DO
  deployment workflow; offloads backups/HA/patching — the ops that "going
  production" is meant to reduce). The API deploys as a service on a droplet/
  container pointing at the managed PG via `CRMBUILDER_V2_DATABASE_URL`.
- **Pinned at PI-α's Deployment phase:** exact prod topology (droplet-vs-container
  for the API, region, whether a pgBouncer/pooling sidecar is needed),
  managed-PG tier/size, connection-pool sizes (informed by PI-100 scale testing),
  TLS/`sslmode` for the DB connection, and secret handling for the DB URL
  (keyring locally / env+secret-store in prod — coordinates with PI-γ's token
  storage).

---

## 8. Phase decomposition (PI-α Workstreams)

Per ADO, PI-α decomposes into the six phase Workstreams. This document **is** the
Architecture phase output.

| Phase | Scope |
|---|---|
| **Architecture** | *This document.* Decisions D1/D9/D10/D11 refined for PI-α; the SQLite surface enumerated; the migration + baseline + pool + JSONB plans set. |
| **Development** | psycopg3 dep; `config.db_url`/`DATABASE_URL` setting; dialect-conditional `_build_engine` + `_pool_kwargs`; `JSONColumn`/`JSONColumnNoneAsNull` variants across models; dialect-aware `migrations/env.py`; the PG baseline migration. |
| **Data Migration** | The `v2-unified.db` → PG one-shot migration script (§6) + sequence reset + the validation/leak-test harness on PG. |
| **Testing** | Whole suite (2343) green on PG (parametrize/duplicate the engine fixture to run key suites on a Dockerized PG in CI); JSONB round-trip assertions; the governance orphan-row regression on PG; leak-test on PG; PI-100 concurrent-writer scale check against the pool. |
| **Deployment** | Pin prod topology (§7); stand up managed PG; rehearse the migration against a prod-shaped PG; decide when to flip the default off SQLite. |
| **Documentation** | Update CLAUDE.md's v2 store description; record the dual-head Alembic posture; dev quickstart (Docker PG); the migration runbook. (Note: the *orientation/API-MCP-only* doc rewrite is PI-β/D8, not here.) |

---

## 9. Open questions & explicitly deferred

- **Async API?** — **Deferred (decided: stay sync for PI-α).** Moving FastAPI to
  async + `asyncpg`/`psycopg` async is a larger, separable change with its own
  risk; sync + `QueuePool` + threadpool already delivers concurrent readers/writers
  on PG MVCC. Revisit post-PI-α if scale testing (PI-100) shows the threadpool is
  the bottleneck. psycopg3 keeps the async door open without a dependency change.
- **Single Alembic env with dialect branching vs. a separate PG tree** — §5 step 4;
  resolved at Development phase. Lean: dialect-branching in the existing `env.py`.
- **Pool sizes / `sslmode` / prod topology** — §7; pinned at Deployment phase,
  informed by PI-100.
- **Meta DB stays SQLite through PI-α** — confirmed (PI-β deletes it; porting is
  waste). If PI-β slips materially, revisit whether the meta DB should also move to
  PG in the interim (default: no).
- **Desktop direct-DB paths** — confirm the desktop app reaches the DB only via the
  API (`StorageClient`) so the PG switch is transparent to it. Any residual
  direct-DB path (e.g. a CLI utility) gets the dialect-aware engine for free, but
  enumerate them in the Development phase.
- **Flip-the-default timing** — when `CRMBUILDER_V2_DATABASE_URL`-unset should
  start defaulting to PG (vs. staying SQLite). Decided at Deployment phase; likely
  early PI-β.

---

## 10. Cross-references
- `production-multitenant-api-architecture.md` — the program design (D1/D9/D10/D11
  this refines; D6/D7/D8 are PI-β, D2/D3/D4 are PI-γ).
- `pi-123-unified-db-architecture.md` — the unified schema + scope mechanism PI-α
  ports to PG unchanged; `migration/unify_engagement_dbs.py` — the migration
  harness §6 reuses.
- `tests/crmbuilder_v2/migration/test_engagement_leak_isolation.py` — the
  cross-engagement leak-test §6 step 5 re-runs on PG.
- PI-100 (concurrent-writer scale validation) — informs pool sizing (§4) and the
  Testing-phase scale check.
- PI-γ — DB-URL secret handling coordinates with token storage (§7).

*End of document — PI-α Architecture/scoping pass v0.1. Next: review/refine, then
PI-α Development phase (psycopg3 + dialect-conditional engine + JSONB variants +
PG baseline) on `pi-alpha-postgres`. Governance records (PI-α/β/γ planning items
under PRJ-019 + this session's close-out) land on `main` per the branch-work
protocol.*

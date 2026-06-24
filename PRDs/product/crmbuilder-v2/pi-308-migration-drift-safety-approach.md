# PI-308 — Startup migration-drift check + Alembic-backed bootstrap-db command

**Implements:** REQ-343 (*Migration drift detection and an honest schema-apply command*) — **awaiting approval**, REL-011 / PRJ-059.
**Status of this doc:** design approach drafted pre-approval. No code is written until REQ-343 is confirmed via the approving-decision path.
**Area:** `access` (plus `cli`). **No migration, no schema change, no new governance entity types.**

---

## 1. Why (one paragraph)

The live unified DB silently ran 3 migrations behind head (0081 vs 0084) for ~28h until a read hit `pipeline_events` and 500'd. Root cause: **no runtime path applies migrations** (`cli.run_api`, the desktop UI, `scripts/apply_close_out.py` never run Alembic or even `create_all`), and the one manual command `crmbuilder-v2-bootstrap-db` is **mislabeled** — its docstring says "apply Alembic migrations" but it runs `Base.metadata.create_all`, which only creates absent tables and never `ALTER`s existing ones, so column-only and CHECK-only migrations stay invisible. The live DB had been bootstrapped via create_all and stamped to 0081 by the one-off `scripts/migrate_live_db_to_0081.py`, with no follow-up for 0082–0084.

## 2. Design principle: reuse, don't reinvent

`src/crmbuilder_v2/migration/version_info.py` **already** computes the answer:

```python
schema_version() -> SchemaVersion(current, head, is_up_to_date)   # already surfaced via /admin + UI connection-info dialog
```

PI-308 does **not** write a new version comparator. It (0) makes that existing helper dialect-aware, (1) makes `bootstrap_database` apply migrations, and (2) calls the helper as an **active gate** at API startup instead of leaving it as a passive dialog.

---

## 3. Part 0 — make `schema_version()` dialect-aware *(precondition for #1 and #3)*

**Problem.** `make_alembic_config()` hardcodes `script_location = migrations/` (the SQLite chain). On Postgres that computes the **wrong head** — the SQLite head (`0084…`) instead of the PG chain's own head under `migrations/pg/`. The two chains are separate Alembic environments (`migrations/alembic.ini` vs `migrations/pg/alembic.ini`), both stamping the same `alembic_version` table.

**Change** (`migration/version_info.py`):
- Detect dialect from the URL: `make_url(url).get_backend_name()`.
- Point `script_location` at `migrations/pg/` for `postgresql*`, `migrations/` for `sqlite`.
- `_current_revision(url)` is unchanged — reading `alembic_version` is dialect-agnostic.

```python
def make_alembic_config(url: str | None = None) -> Config:
    url = url or get_settings().db_url
    is_pg = make_url(url).get_backend_name().startswith("postgresql")
    base = _migrations_dir()                       # <repo>/crmbuilder-v2/migrations
    script = base / "pg" if is_pg else base
    ini = (base / "pg" / "alembic.ini") if is_pg else (base.parent / "alembic.ini")
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(script))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg
```

Head computation needs only the script directory (no live connection), so the PG branch is unit-testable offline with a synthetic `postgresql+psycopg://…` URL.

## 4. Part 1 (#1) — honest `bootstrap_database`

**Change** (`access/db.py`):
```python
def bootstrap_database(settings: Settings | None = None) -> None:
    from alembic import command
    from crmbuilder_v2.migration.version_info import make_alembic_config
    s = settings or get_settings()
    command.upgrade(make_alembic_config(s.db_url), "head")
```
- **Fresh DB** → full chain runs (SQLite baseline `0001` is itself `create_all`-based; PG baseline is `create_all`) → `create_all` is subsumed, no behavior loss for the new-DB case.
- **Behind DB** → applies only the delta, including column- and CHECK-only migrations (the gap create_all couldn't close).
- **At head** → no-op (idempotent).
- Fix `cli.py:7` docstring — it already *claims* "apply Alembic migrations"; now it's true.

**Caller audit (build step, not a risk):**
- `cli.bootstrap_db()` → wants a ready DB. ✅ improved.
- `scripts/demo_pi134_reconciliation_gate.py` → wants a ready DB. ✅ improved.
- **Test fixtures build schema via `Base.metadata.create_all` directly (conftest), NOT via `bootstrap_database`** — so the fast hermetic test path is unaffected. Confirm during build.

## 5. Part 2 (#3) — active startup drift gate in `run_api`

**New helper** (`migration/version_info.py`):
```python
def assert_schema_current() -> None:
    """Raise SchemaDriftError if the unified DB is behind / un-stamped."""
    sv = schema_version()
    if not sv.is_up_to_date:
        raise SchemaDriftError(sv.current, sv.head)
```

**Wire into `run_api()`** (`cli.py`), right after `settings = get_settings()`, covering the `--check-only` path too (cheap diagnostic):
```python
try:
    assert_schema_current()
except SchemaDriftError as e:
    _fail_loud(
        f"REFUSING TO START: database schema is behind the code.\n"
        f"  applied revision: {e.current or '(un-stamped / empty DB)'}\n"
        f"  code expects head: {e.head}\n"
        f"  remedy: run  crmbuilder-v2-bootstrap-db  to apply pending migrations,\n"
        f"          then relaunch."
    )
```

**Behavior chosen: refuse-to-serve** (per Doug's "check-and-halt, not auto-apply"). `_fail_loud` already prints to **both** stderr and stdout and exits 2 (DEC-108), so a UI-spawned API surfaces the reason in captured stdout + the rotating `api.log`.

**Why fail-loud doesn't cause a restart storm:** drift fails at **cold start, before first-ready**, so it routes to `app.py`'s **fatal startup dialog** (DEC-108 / PI-110), *not* the post-first-ready auto-restart loop (`MainWindow.had_first_ready()` gate). The desktop's 3× auto-restart only triggers on `connection_lost`/`crashed` *after* a healthy start — which drift never reaches. A small UI follow-up (surface the captured drift reason verbatim in that fatal dialog) is **optional polish**, not required for acceptance.

**Un-stamped/empty DB** (`current is None`) is treated as "behind" and names the remedy (`bootstrap-db`) — correct, since an empty DB would 500 on first query anyway.

## 6. Acceptance mapping (REQ-343)

| Acceptance criterion | Test |
|---|---|
| (1) API started against a behind DB emits a loud, specific drift warning naming current-vs-expected and does **not** silently serve | Stamp a temp SQLite DB at an earlier rev; invoke `run_api`/`assert_schema_current`; assert non-zero exit + message contains both revisions. |
| (2) schema-apply command brings a behind DB fully to head — columns **and** constraints, not just absent tables — leaving applied == head | `bootstrap_database` against a DB stamped behind a column-only migration; assert the column exists afterward **and** `schema_version().is_up_to_date`. |
| (dialect) head resolves per-dialect | Offline: `make_alembic_config("postgresql+psycopg://…")` head == PG chain head, not SQLite head. |
| (regression) | Existing `version_info` tests + `/admin` schema surface still pass. |

## 7. Files touched

- `src/crmbuilder_v2/migration/version_info.py` — dialect-aware `make_alembic_config`; `SchemaDriftError`; `assert_schema_current`.
- `src/crmbuilder_v2/access/db.py` — `bootstrap_database` runs `alembic upgrade head`.
- `src/crmbuilder_v2/cli.py` — startup gate in `run_api`; fix line-7 docstring.
- tests (v2 suite) per §6.
- **No** Alembic revision, **no** model change, **no** vocab/CHECK change.

## 8. Out of scope (explicit)

- **Auto-apply migrations on startup** — deliberately not chosen (would auto-mutate a shared governance DB on every spawn). Check-and-halt only.
- **Periodic `/health` heartbeat for an external API's death** — that's PI-111, separate.
- **Surfacing drift in a richer UI banner** — optional polish noted in §5; not required for acceptance.

## 9. Delivery (ADO / branch protocol)

Small, single-area (`access`/`cli`) code change. Likely workstreams: **Architecture** (this doc) → **Development** → **Testing**. Model A: code-only branch `pi-308`; no migration ships on the branch; build-closure (records governance, resolves PI-308) lands on `main` after merge. **Precondition: REQ-343 confirmed first.**

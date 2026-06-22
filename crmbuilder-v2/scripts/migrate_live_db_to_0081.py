#!/usr/bin/env python3
"""One-off: migrate the live ``v2-unified.db`` to alembic head ``0081`` (PI-255).

Adds the seven PI-255 source-mapping tables (``source_mappings``,
``source_mapping_targets``, ``source_mapping_joins``, ``field_mappings``,
``field_mapping_translations``, ``value_mappings``, ``mapping_candidates``) and
rebuilds the ``change_log`` / ``refs`` / ``instance_memberships``-state CHECKs to
admit the new entity types + membership states.

WHY NOT A PLAIN ``alembic upgrade head``
----------------------------------------
The live DB is ``create_all``-managed: its ``alembic_version`` is stuck at
``0074`` while its *schema* is actually current through ``0080`` (the
``cost_events`` / ``publish_runs`` tables already exist). A plain upgrade from
0074 would re-run 0075..0080 against objects that already exist. So this script
**STAMPs** the version to ``0080_pi_263_cost_events`` (the true schema level),
then **UPGRADEs head**, which runs *only* ``0081``.

SAFETY
------
- Refuses to run while the API/desktop app holds the DB (it auto-restarts and
  would race the schema rebuild). Close the desktop app first, or pass --force.
- Takes a timestamped backup (WAL-checkpointed) before touching anything.
- Idempotent: exits cleanly if the DB is already at 0081.
- All-or-nothing: on any failure the original DB is untouched/restorable from
  the backup; the path is printed.

REUSABLE BEYOND 0081 --- the ``--reconcile-only`` mode
------------------------------------------------------
The live DB is ``create_all``-managed, and ``create_all`` adds new *tables* but
never new *columns* on existing tables. So any migration that adds a column to
a pre-existing table (0078's ``releases.release_back_half`` was the first one to
bite) silently drifts. ``--reconcile-only`` diffs the live DB's columns against
the current ORM models and ``ADD COLUMN``s the gaps (online-backup first, safe
while the API runs). Run it after any parallel-session migration-number
divergence; don't trust ``alembic_version`` or table-presence alone. This part
is migration-version-agnostic and stays useful long after 0081.

HOME / HOW TO REACH IT
----------------------
Lives in the repo at ``crmbuilder-v2/scripts/migrate_live_db_to_0081.py`` (a
sibling of ``apply_close_out.py``). Run it from the repo root so its venv has
``crmbuilder_v2`` + ``alembic`` and the ``0081`` migration is on disk:

    cd ~/Dropbox/Projects/crmbuilder
    uv run python crmbuilder-v2/scripts/migrate_live_db_to_0081.py --dry-run
    uv run python crmbuilder-v2/scripts/migrate_live_db_to_0081.py --reconcile-only
    uv run python crmbuilder-v2/scripts/migrate_live_db_to_0081.py --yes   # full migrate

``--db`` overrides the target (defaults to the ``data/v2-unified.db`` beside the
crmbuilder-v2 the script lives in); ``--alembic-dir`` overrides the migration
source.
"""

from __future__ import annotations

import argparse
import socket
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

# This script lives at crmbuilder-v2/scripts/; the crmbuilder-v2 root is its
# grandparent, and the live unified DB sits at <crmbuilder-v2>/data/v2-unified.db
# (per CLAUDE.md PI-β: one unified DB; gitignored). Both are overridable via
# --db / --alembic-dir.
_CRMBUILDER_V2 = Path(__file__).resolve().parent.parent
DEFAULT_DB = _CRMBUILDER_V2 / "data" / "v2-unified.db"
# The true schema level of the live DB (cost_events/publish_runs present) — we
# stamp here, then upgrade head runs only 0081.
SCHEMA_LEVEL_REVISION = "0080_pi_263_cost_events"
TARGET_HEAD = "0081_pi_255_source_mapping_tables"
# Sentinel that proves the schema is at the expected 0080 level.
SCHEMA_LEVEL_TABLE = "cost_events"
NEW_TABLES = [
    "source_mappings",
    "source_mapping_targets",
    "source_mapping_joins",
    "field_mappings",
    "field_mapping_translations",
    "value_mappings",
    "mapping_candidates",
]
# Candidate alembic dirs (a crmbuilder-v2 whose migrations/versions has 0081).
# Default: the crmbuilder-v2 this script lives in. --alembic-dir overrides.
_ALEMBIC_CANDIDATES = [_CRMBUILDER_V2]


def _die(msg: str, code: int = 1) -> None:
    print(f"\n✗ {msg}", file=sys.stderr)
    sys.exit(code)


def find_alembic_dir(override: str | None) -> Path:
    if override:
        d = Path(override).resolve()
        candidates = [d]
    else:
        candidates = _ALEMBIC_CANDIDATES
    for d in candidates:
        if (d / "migrations" / "versions" / f"{TARGET_HEAD}.py").exists() and (
            d / "alembic.ini"
        ).exists():
            return d
    _die(
        "could not find a crmbuilder-v2 dir containing the 0081 migration.\n"
        "  Run from a checkout on `main` (where this script lives), or pass "
        "--alembic-dir <path-to-crmbuilder-v2>.\n"
        f"  Looked in: {', '.join(str(c) for c in candidates)}"
    )


def api_holding_db(host: str = "127.0.0.1", port: int = 8765) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def alembic_version(db: Path) -> str | None:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = list(con.execute("SELECT version_num FROM alembic_version"))
        return rows[0][0] if rows else None
    finally:
        con.close()


def table_names(db: Path) -> set[str]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return {
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    finally:
        con.close()


def changelog_admits_source_mapping(db: Path) -> bool:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        sql = list(
            con.execute(
                "SELECT sql FROM sqlite_master WHERE name='change_log'"
            )
        )[0][0]
        return "source_mapping" in sql
    finally:
        con.close()


def backup(db: Path) -> Path:
    # Use SQLite's online backup API — it produces a consistent snapshot even
    # while another process (e.g. the live API) is reading/writing the DB.
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    dest = db.with_name(f"{db.name}.bak-pre0081-{stamp}")
    src = sqlite3.connect(str(db), timeout=15)
    try:
        src.execute("PRAGMA busy_timeout=10000")
        dst = sqlite3.connect(str(dest))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return dest


def run_alembic(alembic_dir: Path, db: Path, args: list[str]) -> None:
    env = {
        **__import__("os").environ,
        "CRMBUILDER_V2_DB_PATH": str(db),
        # Make sure scoping/baseline env doesn't interfere with the migration.
    }
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(alembic_dir),
        env=env,
        capture_output=True,
        text=True,
    )
    label = " ".join(args)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        _die(f"alembic {label} failed (exit {proc.returncode}).")
    print(f"  alembic {label} → ok")


def missing_columns(db: Path) -> list[tuple[str, object]]:
    """Return (table, Column) pairs the models define but the live DB lacks.

    The live DB is ``create_all``-managed; ``create_all`` creates absent *tables*
    but never adds new *columns* to a pre-existing table. So a migration that
    added a column to an existing table (e.g. 0078's ``releases.release_back_half``)
    leaves a gap that stamping past it does not heal. This finds those gaps.
    """
    # Import here so the script can run its --help / preflight without the venv
    # models import cost, and so a fresh checkout imports the merged models.
    from crmbuilder_v2.access.models import Base

    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        db_tables = {
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        out: list[tuple[str, object]] = []
        for tname, table in Base.metadata.tables.items():
            if tname not in db_tables:
                continue
            db_cols = {r[1] for r in con.execute(f"PRAGMA table_info({tname})")}
            for col in table.columns:
                if col.name not in db_cols:
                    out.append((tname, col))
        return out
    finally:
        con.close()


def _add_column_ddl(table: str, col) -> str:
    """Build a SQLite ``ALTER TABLE ... ADD COLUMN`` clause for one model column.

    Honours NOT NULL only when a usable default exists (SQLite requires a
    default to add a NOT NULL column to a populated table); raises otherwise.
    """
    type_sql = str(col.type)  # e.g. 'VARCHAR(16)', 'TEXT', 'DATETIME'
    default_sql = None
    if col.server_default is not None:
        raw = getattr(col.server_default, "arg", None)
        raw = getattr(raw, "text", raw)
        default_sql = str(raw)
        if not str(default_sql).strip().lstrip("-").replace(".", "", 1).isdigit():
            default_sql = "'" + str(default_sql).strip().strip("'") + "'"
    elif getattr(col.default, "is_scalar", False):
        val = col.default.arg
        default_sql = f"'{val}'" if isinstance(val, str) else str(val)
    pieces = [f'ALTER TABLE {table} ADD COLUMN {col.name} {type_sql}']
    if not col.nullable:
        if default_sql is None:
            raise RuntimeError(
                f"{table}.{col.name} is NOT NULL with no default — cannot safely "
                "add to a populated table; needs a hand-written migration."
            )
        pieces.append(f"NOT NULL DEFAULT {default_sql}")
    elif default_sql is not None:
        pieces.append(f"DEFAULT {default_sql}")
    return " ".join(pieces)


def reconcile_columns(db: Path, *, dry_run: bool) -> int:
    """Add any model-defined columns missing from the live DB. Returns the count."""
    gaps = missing_columns(db)
    if not gaps:
        print("  no missing columns — schema columns already match the models.")
        return 0
    print(f"  {len(gaps)} missing column(s):")
    ddls = []
    for table, col in gaps:
        ddl = _add_column_ddl(table, col)
        ddls.append(ddl)
        print(f"    {ddl}")
    if dry_run:
        print("  (--dry-run) no changes made.")
        return 0
    con = sqlite3.connect(str(db), timeout=15)
    try:
        con.execute("PRAGMA busy_timeout=10000")
        for ddl in ddls:
            con.execute(ddl)
        con.commit()
    finally:
        con.close()
    print(f"  added {len(ddls)} column(s).")
    return len(ddls)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=str(DEFAULT_DB), help="live DB path")
    ap.add_argument(
        "--alembic-dir",
        default=None,
        help="crmbuilder-v2 dir containing the 0081 migration",
    )
    ap.add_argument("--yes", action="store_true", help="skip confirmation")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="show the plan and change nothing",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="proceed even if the API/app is up (NOT recommended)",
    )
    ap.add_argument(
        "--reconcile-only",
        action="store_true",
        help="skip stamp/upgrade; only add model-defined columns the live DB is "
        "missing (heals the create_all column-drift, e.g. releases.release_back_half)",
    )
    args = ap.parse_args()

    db = Path(args.db).resolve()
    if not db.exists():
        _die(f"DB not found: {db}")
    alembic_dir = find_alembic_dir(args.alembic_dir)

    print("Live DB source-mapping migration (PI-255 → alembic head 0081)")
    print(f"  DB           : {db}")
    print(f"  alembic dir  : {alembic_dir}")

    ver = alembic_version(db)
    tabs = table_names(db)
    print(f"  current ver  : {ver}")

    # --- column-reconcile-only mode (heals create_all column drift) -----------
    if args.reconcile_only:
        print("\nColumn-reconcile mode (add model columns the live DB lacks):")
        if api_holding_db() and not args.force and not args.dry_run:
            _die(
                "the API is reachable on 127.0.0.1:8765 — close the desktop app "
                "(and any standalone API) first so nothing writes mid-ALTER, then "
                "re-run. (ADD COLUMN is fast/additive; override with --force if "
                "you are certain nothing is writing.)"
            )
        if not args.dry_run:
            bak = backup(db)
            print(f"  backup: {bak}")
        n = reconcile_columns(db, dry_run=args.dry_run)
        if n and not args.dry_run:
            print("\n✓ Columns reconciled. Restart the app to pick up the schema.")
        elif not args.dry_run:
            print("\n✓ Nothing to do — columns already match.")
        return

    # Already migrated?
    if all(t in tabs for t in NEW_TABLES) and (ver or "").startswith("0081"):
        print("\n✓ Source-mapping tables present and version at 0081.")
        # Belt-and-suspenders: still heal any missing columns (create_all drift).
        print("Checking for missing model columns (create_all column drift):")
        reconcile_columns(db, dry_run=True)
        print("  (run with --reconcile-only to add any listed above.)")
        return

    # Preconditions: schema must be at the 0080 level, tables not yet present.
    if SCHEMA_LEVEL_TABLE not in tabs:
        _die(
            f"unexpected schema: '{SCHEMA_LEVEL_TABLE}' table is absent, so the "
            "DB is NOT at the 0080 level this script assumes. Stop and review "
            "manually (do not stamp blindly)."
        )
    already = [t for t in NEW_TABLES if t in tabs]
    if already:
        _die(
            "some source-mapping tables already exist "
            f"({already}); the DB is in a partial state. Review manually."
        )

    if api_holding_db() and not args.force and not args.dry_run:
        _die(
            "the API is reachable on 127.0.0.1:8765 — the desktop app likely "
            "owns it and will auto-restart it, racing the schema rebuild.\n"
            "  → Close the CRMBuilder desktop app (and any standalone "
            "`crmbuilder-v2-api`), then re-run.\n"
            "  (Override with --force only if you are certain nothing is "
            "writing to the DB.)"
        )

    print("\nPlan:")
    print(f"  1. backup {db.name} → {db.name}.bak-pre0081-<ts>")
    print(f"  2. alembic stamp {SCHEMA_LEVEL_REVISION}   (record the true level)")
    print("  3. alembic upgrade head            (runs ONLY 0081)")
    print(f"  4. verify: version=0081, {len(NEW_TABLES)} new tables, CHECKs updated")

    if args.dry_run:
        print("\n(--dry-run) No changes made.")
        return

    if not args.yes:
        resp = input("\nProceed? [y/N] ").strip().lower()
        if resp not in {"y", "yes"}:
            print("Aborted.")
            return

    print("\n→ backing up…")
    bak = backup(db)
    print(f"  backup: {bak}")

    print("→ stamping + upgrading…")
    run_alembic(alembic_dir, db, ["stamp", SCHEMA_LEVEL_REVISION])
    run_alembic(alembic_dir, db, ["upgrade", "head"])

    print("→ verifying…")
    ver2 = alembic_version(db)
    tabs2 = table_names(db)
    missing = [t for t in NEW_TABLES if t not in tabs2]
    ok_check = changelog_admits_source_mapping(db)
    problems = []
    if not (ver2 or "").startswith("0081"):
        problems.append(f"version is {ver2!r}, expected 0081")
    if missing:
        problems.append(f"missing tables: {missing}")
    if not ok_check:
        problems.append("change_log CHECK does not admit 'source_mapping'")
    if problems:
        _die(
            "verification FAILED:\n  - "
            + "\n  - ".join(problems)
            + f"\n  Restore from backup if needed: {bak}"
        )

    print(f"  version      : {ver2}")
    print(f"  new tables   : all {len(NEW_TABLES)} present")
    print("  CHECKs       : change_log/refs/membership admit the new types")
    print("\n✓ Migration complete.")
    print(f"  Backup kept at: {bak}")
    print("  → Restart the CRMBuilder desktop app / API to pick up the new schema.")


if __name__ == "__main__":
    main()

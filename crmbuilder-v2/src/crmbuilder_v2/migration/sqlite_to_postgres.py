"""PI-alpha (D9) — one-shot migration of the unified SQLite DB into Postgres.

Implements the data-migration phase of ``pi-alpha-postgres-foundation-architecture.md``
§6: the just-built, validated ``v2-unified.db`` is the **source**, and the target
is an empty Postgres database at the same strict ORM schema.

Because the source is already unified — every scoped row carries its final
``engagement_id`` and its final surrogate ``id`` (PI-123 did the stamping +
offset reassignment) — this is a **straight table-by-table copy**, no offset
gymnastics. The work here is the cross-dialect concerns the SQLite→SQLite
consolidation never had:

* **Type coercion.** SQLite stores JSON as ``TEXT``, booleans as ``0/1``, and
  ``timestamptz`` as ISO strings; Postgres wants ``JSONB``, ``boolean``, and
  ``timestamptz``. We copy **through SQLAlchemy Core bound to the shared
  ``Base.metadata``**, so each column's type round-trips: reading from SQLite
  decodes (JSON text → ``dict``, ``0/1`` → ``bool``, ISO → ``datetime``) and
  writing to Postgres re-encodes for the PG dialect. Using Core (not the ORM
  Session) also bypasses the engagement-scope filter/stamp listeners — they live
  on the ORM ``Session`` class — so the copy sees and writes **all** engagements'
  rows verbatim, which is exactly what a migration must do.
* **FK order.** Insert in ``Base.metadata.sorted_tables`` order (parents before
  children) with FK enforcement left **ON**, so Postgres validates referential
  integrity as the data lands — no superuser ``session_replication_role`` toggle
  and no managed-PG privilege dependency. The only intra-table integer FKs
  (``decisions.supersedes_id``/``superseded_by_id`` and ``topics.parent_topic_id``)
  are handled by a two-pass: insert the rows with those columns NULLed, then
  ``UPDATE`` them once every row of the table exists.
* **Sequence reset.** A bulk copy of explicit ``id`` values leaves Postgres'
  ``SERIAL`` sequence at 1, so the next ORM insert would collide. After the copy
  we ``setval`` each surrogate-``id`` table's sequence to ``MAX(id)``.

Validated (D9 acceptance, on Postgres): per-engagement per-table row-count parity
vs the source, identifier-set parity per identifier-PK table, no NULL
``engagement_id``, and a cross-engagement isolation check (the leak-test essence)
run through the scoped ORM against Postgres.

Run::

    uv run python -m crmbuilder_v2.migration.sqlite_to_postgres \\
        --sqlite crmbuilder-v2/data/v2-unified.db \\
        --postgres 'postgresql+psycopg://crmb:crmb@localhost:55432/crmbuilder_v2'
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import Engine, create_engine, func, insert, select, text, update
from sqlalchemy.engine import make_url

from crmbuilder_v2.access.models import Base
from crmbuilder_v2.migration.unify_engagement_dbs import (
    IDENTIFIER_PK_TABLES,
    SCOPED_TABLES,
    SELF_FK_COLUMNS,
)

_log = logging.getLogger("crmbuilder_v2.migration.sqlite_to_postgres")


@dataclass
class PgMigrationResult:
    ok: bool
    per_engagement_rows: dict[str, int] = field(default_factory=dict)
    count_mismatches: list[str] = field(default_factory=list)
    identifier_mismatches: list[str] = field(default_factory=list)
    null_engagement_rows: int = 0
    isolation_ok: bool | None = None
    sequences_reset: int = 0
    errors: list[str] = field(default_factory=list)


def _engagement_ids(sqlite_engine: Engine) -> list[str]:
    with sqlite_engine.connect() as c:
        return [
            r[0]
            for r in c.execute(
                text(
                    "SELECT engagement_identifier FROM engagements "
                    "ORDER BY engagement_identifier"
                )
            )
        ]


def _pg_is_empty(pg_engine: Engine) -> bool:
    """True if no scoped table holds any row (a fresh target)."""
    md = Base.metadata
    with pg_engine.connect() as c:
        for table in SCOPED_TABLES:
            if table not in md.tables:
                continue
            n = c.execute(select(func.count()).select_from(md.tables[table])).scalar()
            if n:
                return False
    return True


def _copy_table(src_conn, dst_conn, table, *, null_self_fks: tuple[str, ...]) -> int:
    """Copy one table src→dst through Core; NULL the named self-FK cols (pass 1)."""
    rows = [dict(m) for m in src_conn.execute(select(table)).mappings()]
    if not rows:
        return 0
    if null_self_fks:
        for r in rows:
            for col in null_self_fks:
                r[col] = None
    dst_conn.execute(insert(table), rows)
    return len(rows)


def _fix_self_fks(src_conn, dst_conn, table_name: str, fk_cols: tuple[str, ...]) -> None:
    """Pass 2: restore the self-FK columns now that every row exists."""
    table = Base.metadata.tables[table_name]
    pk = table.c.id
    src_rows = src_conn.execute(
        select(table.c.id, *[table.c[col] for col in fk_cols])
    ).all()
    for row in src_rows:
        values = {col: row[i + 1] for i, col in enumerate(fk_cols)}
        if all(v is None for v in values.values()):
            continue
        dst_conn.execute(update(table).where(pk == row[0]).values(**values))


def _id_pk_tables() -> list[str]:
    """Every model table with a surrogate ``id`` column, derived from metadata.

    Sequences are reset for these after the copy (REQ-438 / PI-377). Deriving the
    set from ``Base.metadata`` rather than a hand-maintained list is the durable
    fix: a hardcoded list silently drifts as tables are added, which is exactly
    how the live store ended up with 34 of 44 id-tables' sequences left behind.
    """
    return sorted(
        t.name for t in Base.metadata.tables.values() if "id" in t.columns
    )


def _reset_sequences(pg_engine: Engine) -> int:
    """setval each id-table's owning sequence to MAX(id) (or 1 if empty)."""
    n = 0
    with pg_engine.begin() as c:
        for table_name in _id_pk_tables():
            seq = c.execute(
                text("SELECT pg_get_serial_sequence(:t, 'id')"), {"t": table_name}
            ).scalar()
            if not seq:
                continue
            # ``is_called=false`` when empty so the first nextval yields 1.
            c.execute(
                text(
                    f"SELECT setval('{seq}', "
                    f"COALESCE((SELECT MAX(id) FROM {table_name}), 1), "
                    f"(SELECT COUNT(*) FROM {table_name}) > 0)"
                )
            )
            n += 1
    return n


def copy_all(sqlite_engine: Engine, pg_engine: Engine) -> None:
    """Copy every table SQLite→Postgres in FK-safe order, inside one PG txn."""
    md = Base.metadata
    ordered = list(md.sorted_tables)  # parents before children
    with sqlite_engine.connect() as src, pg_engine.begin() as dst:
        for table in ordered:
            self_fks = SELF_FK_COLUMNS.get(table.name, ())
            n = _copy_table(src, dst, table, null_self_fks=self_fks)
            if n:
                _log.info("copied %s rows into %s", n, table.name)
        # Pass 2 — restore self-FKs once all rows are present.
        for table_name, fk_cols in SELF_FK_COLUMNS.items():
            if table_name in md.tables:
                _fix_self_fks(src, dst, table_name, fk_cols)


def validate(sqlite_engine: Engine, pg_engine: Engine) -> PgMigrationResult:
    """D9 acceptance: count + identifier parity, no NULLs, isolation on PG."""
    result = PgMigrationResult(ok=True)
    md = Base.metadata
    engagements = _engagement_ids(sqlite_engine)

    with sqlite_engine.connect() as sc, pg_engine.connect() as pc:
        for table_name in SCOPED_TABLES:
            if table_name not in md.tables:
                continue
            table = md.tables[table_name]
            eid = table.c.engagement_id
            for eng in engagements:
                src_n = sc.execute(
                    select(func.count()).select_from(table).where(eid == eng)
                ).scalar()
                dst_n = pc.execute(
                    select(func.count()).select_from(table).where(eid == eng)
                ).scalar()
                result.per_engagement_rows[eng] = (
                    result.per_engagement_rows.get(eng, 0) + dst_n
                )
                if src_n != dst_n:
                    result.ok = False
                    result.count_mismatches.append(
                        f"{eng}.{table_name}: sqlite={src_n} pg={dst_n}"
                    )
            # No NULL engagement_id landed.
            nulls = pc.execute(
                select(func.count()).select_from(table).where(eid.is_(None))
            ).scalar()
            result.null_engagement_rows += nulls
            if nulls:
                result.ok = False
                result.errors.append(f"{nulls} NULL engagement_id in {table_name}")
            # Identifier-set parity (identifier-PK tables only). The identifier
            # column is the composite PK member other than engagement_id — its
            # name is table-specific (``session_identifier``, ``commit_identifier``,
            # …), so derive it rather than assume a generic ``identifier``.
            if table_name in IDENTIFIER_PK_TABLES:
                pk_others = [
                    c for c in table.primary_key.columns if c.name != "engagement_id"
                ]
                if len(pk_others) != 1:
                    continue
                ident = pk_others[0]
                for eng in engagements:
                    s = {
                        r[0]
                        for r in sc.execute(
                            select(ident).where(eid == eng)
                        )
                    }
                    d = {
                        r[0]
                        for r in pc.execute(
                            select(ident).where(eid == eng)
                        )
                    }
                    if s != d:
                        result.ok = False
                        result.identifier_mismatches.append(
                            f"{eng}.{table_name}: "
                            f"missing={sorted(s - d)[:5]} extra={sorted(d - s)[:5]}"
                        )

    # Cross-engagement isolation on Postgres (the leak-test essence): a scoped
    # ORM read under one active engagement must never see another's rows.
    if len(engagements) >= 2:
        result.isolation_ok = _check_isolation(pg_engine, engagements)
        if not result.isolation_ok:
            result.ok = False
            result.errors.append("cross-engagement isolation failed on Postgres")

    return result


def _check_isolation(pg_engine: Engine, engagements: list[str]) -> bool:
    """Under each active engagement, a scoped ORM count == that engagement's rows."""
    from sqlalchemy.orm import sessionmaker

    from crmbuilder_v2.access import engagement_scope
    from crmbuilder_v2.access.models import PlanningItem

    # Install the scope listeners on a factory bound to PG, mirroring the app.
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False, future=True)
    engagement_scope.install_engagement_scope(factory)
    table = Base.metadata.tables["planning_items"]
    with pg_engine.connect() as c:
        truth = {
            eng: c.execute(
                select(func.count())
                .select_from(table)
                .where(table.c.engagement_id == eng)
            ).scalar()
            for eng in engagements
        }
    prev = engagement_scope.set_enforcement(True)
    try:
        for eng in engagements:
            tok = engagement_scope.set_active_engagement(eng)
            try:
                s = factory()
                seen = s.query(PlanningItem).count()
                s.close()
            finally:
                engagement_scope.reset_active_engagement(tok)
            if seen != truth[eng]:
                _log.error(
                    "isolation: active=%s saw %s planning_items, expected %s",
                    eng, seen, truth[eng],
                )
                return False
    finally:
        engagement_scope.set_enforcement(prev)
    return True


def migrate(
    sqlite_path: str | Path,
    pg_url: str,
    *,
    create_schema: bool = True,
) -> PgMigrationResult:
    """Stand up the PG schema, copy from SQLite, reset sequences, validate."""
    sqlite_path = Path(sqlite_path)
    if not sqlite_path.exists():
        raise FileNotFoundError(f"source SQLite DB not found: {sqlite_path}")
    if make_url(pg_url).get_backend_name() == "sqlite":
        raise ValueError("--postgres must be a Postgres URL, not SQLite")

    sqlite_engine = create_engine(f"sqlite:///{sqlite_path}")
    pg_engine = create_engine(pg_url, future=True)
    try:
        if create_schema:
            _log.info("creating schema on Postgres target")
            Base.metadata.create_all(pg_engine)
        if not _pg_is_empty(pg_engine):
            raise RuntimeError(
                "refusing to migrate into a non-empty Postgres target "
                "(scoped tables already hold rows); drop/recreate the schema first"
            )
        _log.info("copying %s -> Postgres", sqlite_path)
        copy_all(sqlite_engine, pg_engine)
        result = PgMigrationResult(ok=True)
        result.sequences_reset = _reset_sequences(pg_engine)
        _log.info("reset %d sequences", result.sequences_reset)
        v = validate(sqlite_engine, pg_engine)
        # Fold the validation into the result (keep the sequence count).
        seqs = result.sequences_reset
        result = v
        result.sequences_reset = seqs
        if result.ok:
            _log.info("migration validation OK")
        else:
            for err in (
                result.count_mismatches
                + result.identifier_mismatches
                + result.errors
            ):
                _log.error("validation: %s", err)
        return result
    finally:
        sqlite_engine.dispose()
        pg_engine.dispose()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description="Migrate the unified SQLite DB into Postgres (PI-alpha D9)."
    )
    parser.add_argument("--sqlite", required=True, type=Path)
    parser.add_argument("--postgres", required=True)
    parser.add_argument(
        "--no-create-schema",
        action="store_true",
        help="assume the PG schema already exists (e.g. applied via Alembic)",
    )
    args = parser.parse_args(argv)

    result = migrate(
        args.sqlite, args.postgres, create_schema=not args.no_create_schema
    )
    if not result.ok:
        print("MIGRATION FAILED:")
        for err in (
            result.count_mismatches + result.identifier_mismatches + result.errors
        ):
            print(f"  - {err}")
        return 1
    print("MIGRATION OK")
    for eng, n in sorted(result.per_engagement_rows.items()):
        print(f"  {eng}: {n} scoped rows")
    print(f"  sequences reset: {result.sequences_reset}")
    print(f"  isolation on PG: {result.isolation_ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

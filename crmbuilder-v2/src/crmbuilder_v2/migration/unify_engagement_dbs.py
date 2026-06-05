"""PI-123 Stage 3/4 — consolidate per-engagement DB files into one unified DB.

Implements D9 of ``pi-123-unified-db-architecture.md``: build a fresh unified
database at the **strict** target schema (``Base.metadata.create_all`` — composite
``(engagement_id, identifier)`` keys, ``engagement_id NOT NULL`` + FK), then copy
every scoped row from each per-engagement source DB into it with ``engagement_id``
stamped. The engagements registry is seeded from the meta DB; the ``catalog_*``
reference data is copied once (it is identical across engagements and lives in the
shared/un-scoped bucket).

The headline crux — preserve per-engagement identifier sequences (CBM ``SES-001``
*and* CRMBUILDER ``SES-150`` coexist) — is handled for free by the composite
``(engagement_id, identifier)`` keys: identifier-PK tables keep their string
identifier and just gain ``engagement_id``. Surrogate-``id`` tables (decisions,
refs, …) have their integer PK **reassigned** by a per-engagement offset so the
two files' ``id`` spaces never collide; the only intra-scoped integer FKs
(``decisions.supersedes_id`` / ``superseded_by_id`` → ``decisions.id`` and
``topics.parent_topic_id`` → ``topics.id``) get the same offset so referential
integrity is preserved. ``refs`` joins endpoints by identifier **string**, not by
numeric id, so its reassignment is invisible to the edge graph.

Non-destructive: the source files are opened read-only and never modified. The
caller chooses the unified-DB path; the live cutover (Stage 4) points the default
DB at it only after the validation below passes.

Run as a module for a dry consolidation against copies::

    uv run python -m crmbuilder_v2.migration.unify_engagement_dbs \\
        --unified /tmp/v2-unified.db \\
        --meta crmbuilder-v2/data/engagements.db \\
        --source ENG-001=/tmp/CRMBUILDER.copy.db \\
        --source ENG-002=/tmp/CBM.copy.db \\
        --catalog-source ENG-001
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import create_engine

from crmbuilder_v2.access.models import Base

_log = logging.getLogger("crmbuilder_v2.migration.unify")

# --------------------------------------------------------------------------
# Table classification (mirrors pi-123-slice3-enforce-plan.md §1).
# --------------------------------------------------------------------------
# Class A + engagement_areas — the prefixed identifier (or name) IS the PK;
# under the strict schema the PK is composite ``(engagement_id, <identifier>)``.
# No surrogate ``id`` column → nothing to reassign; the row keeps its identifier.
IDENTIFIER_PK_TABLES: tuple[str, ...] = (
    "sessions", "domains", "entities", "fields", "personas", "processes",
    "projects", "workstreams", "work_tasks", "work_tickets", "conversations",
    "reference_books", "crm_candidates", "manual_configs", "test_specs",
    "requirements", "deposit_events", "close_out_payloads", "commits",
    "engagement_areas",
    # PI-134 reconciliation gate (DEC-400) — identifier-PK scoped table.
    "findings",
)

# Class B + C — surrogate autoincrement ``id`` PK. The integer id is reassigned
# by a per-engagement offset so the two source files' id spaces never collide.
SURROGATE_ID_PK_TABLES: tuple[str, ...] = (
    "decisions", "planning_items", "risks", "topics", "refs", "charter",
    "status", "reference_book_versions", "change_log", "identifier_reservations",
)

SCOPED_TABLES: tuple[str, ...] = IDENTIFIER_PK_TABLES + SURROGATE_ID_PK_TABLES

# The only intra-scoped integer FK columns (→ another scoped row's ``id``).
# They take the same per-engagement offset as the id they reference so the
# self-references stay valid after reassignment. (reference_book_versions →
# reference_books is a *string* composite FK and needs no remap.)
SELF_FK_COLUMNS: dict[str, tuple[str, ...]] = {
    "decisions": ("supersedes_id", "superseded_by_id"),
    "topics": ("parent_topic_id",),
}

# System/shared reference data — copied once, no engagement_id.
CATALOG_TABLES: tuple[str, ...] = (
    "catalog_entity", "catalog_entity_synonym", "catalog_entity_system",
    "catalog_source", "catalog_attribute", "catalog_attribute_enum_value",
    "catalog_attribute_synonym", "catalog_attribute_presence",
    "catalog_relationship", "catalog_relationship_presence",
)

# Per-engagement id offset. Far larger than any engagement's row count, so the
# reassigned id spaces are disjoint. Engagement i (1-based) uses offset i*STEP.
ID_OFFSET_STEP = 1_000_000_000


@dataclass
class SourceEngagement:
    """One source per-engagement DB to fold into the unified store."""

    identifier: str  # ENG-NNN
    db_path: Path


@dataclass
class ValidationResult:
    ok: bool
    per_table_counts: dict[str, dict[str, int]] = field(default_factory=dict)
    identifier_parity: dict[str, bool] = field(default_factory=dict)
    null_engagement_rows: int = 0
    fk_violations: list = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Schema + low-level helpers
# --------------------------------------------------------------------------
def build_unified_schema(unified_path: Path) -> None:
    """Create the unified DB at the strict (target) schema via ``create_all``."""
    engine = create_engine(f"sqlite:///{unified_path}")
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


# --------------------------------------------------------------------------
# Copy steps
# --------------------------------------------------------------------------
def seed_engagements(unified_conn: sqlite3.Connection, meta_db_path: Path) -> int:
    """Copy the engagements registry from the meta DB into the unified table."""
    meta = sqlite3.connect(f"file:{meta_db_path}?mode=ro", uri=True)
    try:
        src_cols = _columns(meta, "engagements")
        dst_cols = _columns(unified_conn, "engagements")
        cols = [c for c in src_cols if c in dst_cols]
        rows = meta.execute(
            f"SELECT {','.join(cols)} FROM engagements"
        ).fetchall()
        placeholders = ",".join("?" for _ in cols)
        unified_conn.executemany(
            f"INSERT INTO engagements ({','.join(cols)}) VALUES ({placeholders})",
            rows,
        )
        return len(rows)
    finally:
        meta.close()


def copy_engagement(
    unified_conn: sqlite3.Connection, src: SourceEngagement, offset: int
) -> dict[str, int]:
    """Copy one source DB's scoped rows into the unified DB, stamped + reassigned.

    Returns a per-table source row count for the validation step.
    """
    counts: dict[str, int] = {}
    source = sqlite3.connect(f"file:{src.db_path}?mode=ro", uri=True)
    try:
        for table in SCOPED_TABLES:
            if not _table_exists(source, table):
                counts[table] = 0
                continue
            src_cols = _columns(source, table)
            dst_cols = set(_columns(unified_conn, table))
            # Copy the source∩unified columns EXCEPT engagement_id — which we
            # always stamp ourselves (the source predates the discriminator:
            # CRMBUILDER is at chain 0036, CBM at 0010, neither has the column).
            copy_cols = [
                c for c in src_cols if c in dst_cols and c != "engagement_id"
            ]
            rows = source.execute(
                f"SELECT {','.join(copy_cols)} FROM {table}"
            ).fetchall()
            counts[table] = len(rows)
            if not rows:
                continue

            surrogate = table in SURROGATE_ID_PK_TABLES
            self_fks = SELF_FK_COLUMNS.get(table, ())
            id_idx = copy_cols.index("id") if "id" in copy_cols and surrogate else None
            fk_idxs = [copy_cols.index(c) for c in self_fks if c in copy_cols]

            out_rows = []
            for row in rows:
                values = list(row)
                if id_idx is not None and values[id_idx] is not None:
                    values[id_idx] = values[id_idx] + offset
                for fk_i in fk_idxs:
                    if values[fk_i] is not None:
                        values[fk_i] = values[fk_i] + offset
                values.append(src.identifier)  # stamp the discriminator
                out_rows.append(tuple(values))

            insert_cols = [*copy_cols, "engagement_id"]
            placeholders = ",".join("?" for _ in insert_cols)
            unified_conn.executemany(
                f"INSERT INTO {table} ({','.join(insert_cols)}) VALUES ({placeholders})",
                out_rows,
            )
        return counts
    finally:
        source.close()


def copy_catalog(unified_conn: sqlite3.Connection, catalog_src_path: Path) -> dict[str, int]:
    """Copy the shared catalog tables once from the canonical source DB."""
    counts: dict[str, int] = {}
    source = sqlite3.connect(f"file:{catalog_src_path}?mode=ro", uri=True)
    try:
        for table in CATALOG_TABLES:
            if not _table_exists(source, table):
                counts[table] = 0
                continue
            src_cols = _columns(source, table)
            dst_cols = set(_columns(unified_conn, table))
            cols = [c for c in src_cols if c in dst_cols]
            rows = source.execute(f"SELECT {','.join(cols)} FROM {table}").fetchall()
            counts[table] = len(rows)
            if rows:
                placeholders = ",".join("?" for _ in cols)
                unified_conn.executemany(
                    f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})",
                    rows,
                )
        return counts
    finally:
        source.close()


# --------------------------------------------------------------------------
# Validation (D9 step 7)
# --------------------------------------------------------------------------
def validate(
    unified_path: Path,
    sources: list[SourceEngagement],
    source_counts: dict[str, dict[str, int]],
) -> ValidationResult:
    """Assert per-engagement count + identifier parity, no NULLs, no FK breaks."""
    result = ValidationResult(ok=True)
    conn = sqlite3.connect(f"file:{unified_path}?mode=ro", uri=True)
    try:
        # Per-engagement per-table COUNT parity vs source.
        for src in sources:
            result.per_table_counts[src.identifier] = {}
            for table in SCOPED_TABLES:
                unified_n = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE engagement_id=?",
                    (src.identifier,),
                ).fetchone()[0]
                src_n = source_counts[src.identifier].get(table, 0)
                result.per_table_counts[src.identifier][table] = unified_n
                if unified_n != src_n:
                    result.ok = False
                    result.errors.append(
                        f"count mismatch {src.identifier}.{table}: "
                        f"unified={unified_n} source={src_n}"
                    )

        # No scoped row with a NULL engagement_id.
        for table in SCOPED_TABLES:
            n = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE engagement_id IS NULL"
            ).fetchone()[0]
            result.null_engagement_rows += n
            if n:
                result.ok = False
                result.errors.append(f"{n} NULL engagement_id rows in {table}")

        # FK integrity across the whole DB.
        result.fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if result.fk_violations:
            result.ok = False
            result.errors.append(
                f"{len(result.fk_violations)} foreign-key violations"
            )
    finally:
        conn.close()
    return result


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------
def consolidate(
    unified_path: Path,
    sources: list[SourceEngagement],
    meta_db_path: Path,
    *,
    catalog_source_identifier: str,
) -> ValidationResult:
    """Build the unified DB and copy every source in; return the validation."""
    unified_path = Path(unified_path)
    if unified_path.exists():
        raise FileExistsError(
            f"refusing to overwrite existing unified DB at {unified_path}; "
            "remove it first (the cutover writes a fresh file)"
        )

    _log.info("building unified schema at %s", unified_path)
    build_unified_schema(unified_path)

    catalog_src = next(
        (s for s in sources if s.identifier == catalog_source_identifier), None
    )
    if catalog_src is None:
        raise ValueError(
            f"catalog source {catalog_source_identifier!r} not among the sources"
        )

    conn = sqlite3.connect(unified_path)
    source_counts: dict[str, dict[str, int]] = {}
    try:
        conn.execute("PRAGMA foreign_keys=OFF")  # bulk load; checked at the end
        seeded = seed_engagements(conn, meta_db_path)
        _log.info("seeded %d engagements", seeded)
        for i, src in enumerate(sources, start=1):
            offset = i * ID_OFFSET_STEP
            counts = copy_engagement(conn, src, offset)
            source_counts[src.identifier] = counts
            _log.info(
                "copied %s (%d scoped rows, id offset %d)",
                src.identifier, sum(counts.values()), offset,
            )
        cat_counts = copy_catalog(conn, catalog_src.db_path)
        _log.info("copied catalog (%d rows)", sum(cat_counts.values()))
        conn.commit()
    finally:
        conn.close()

    result = validate(unified_path, sources, source_counts)
    if result.ok:
        _log.info("validation OK")
    else:
        for err in result.errors:
            _log.error("validation: %s", err)
    return result


def _parse_source(spec: str) -> SourceEngagement:
    ident, _, path = spec.partition("=")
    if not ident or not path:
        raise argparse.ArgumentTypeError(
            f"--source must be ENG-NNN=/path/to.db, got {spec!r}"
        )
    return SourceEngagement(identifier=ident, db_path=Path(path))


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Consolidate per-engagement DBs.")
    parser.add_argument("--unified", required=True, type=Path)
    parser.add_argument("--meta", required=True, type=Path)
    parser.add_argument(
        "--source", required=True, action="append", type=_parse_source,
        dest="sources", help="ENG-NNN=/path/to/engagement.db (repeatable)",
    )
    parser.add_argument("--catalog-source", required=True)
    args = parser.parse_args(argv)

    result = consolidate(
        args.unified, args.sources, args.meta,
        catalog_source_identifier=args.catalog_source,
    )
    if not result.ok:
        print("CONSOLIDATION FAILED:")
        for err in result.errors:
            print(f"  - {err}")
        return 1
    print("CONSOLIDATION OK")
    for eng, tables in result.per_table_counts.items():
        print(f"  {eng}: {sum(tables.values())} scoped rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

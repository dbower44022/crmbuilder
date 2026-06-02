"""PI-123 Stage 3 — consolidation harness test (against synthetic source DBs).

Builds two per-engagement source DBs with **intentionally colliding identifiers**
(both hold ``DEC-001``, ``TOP-001``, a ``refs`` edge, and a ``topics`` self-FK
parent chain), runs :func:`unify_engagement_dbs.consolidate`, and asserts the
unified DB: preserves both engagements' rows (count + identifier parity),
re-stamps ``engagement_id`` per source, reassigns surrogate ``id``s without
collision while keeping the ``topics.parent_topic_id`` self-FK valid, and passes
``PRAGMA foreign_key_check``. This validates the copy mechanics; the live
consolidation (Stage 4, against ``CRMBUILDER.db`` + ``CBM.db``) reuses the same
function after the pre-flight chain-migration of each source to head.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from crmbuilder_v2.access.models import Base
from crmbuilder_v2.migration.unify_engagement_dbs import (
    SourceEngagement,
    consolidate,
)
from sqlalchemy import create_engine

_NOW = datetime(2026, 6, 2, tzinfo=UTC).isoformat()
_EXEC = "x" * 200


def _build_source(path: Path, engagement_id: str) -> None:
    """Create a source DB at the unified schema and seed colliding rows.

    The consolidation re-stamps ``engagement_id`` from its own columns, so a
    source built at the strict schema (engagement_id present) exercises the same
    copy path as a real pre-unified source (engagement_id absent).
    """
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute(
        "INSERT INTO engagements "
        "(engagement_identifier, engagement_code, engagement_name, "
        "engagement_purpose, engagement_status, engagement_created_at, "
        "engagement_updated_at) VALUES (?,?,?,?,?,?,?)",
        (engagement_id, engagement_id, engagement_id, "p", "active", _NOW, _NOW),
    )
    # topics — Class B (surrogate id PK + UNIQUE(engagement_id, identifier))
    # with a self-FK parent chain (TOP-002 → TOP-001 via id).
    conn.execute(
        "INSERT INTO topics (id, identifier, name, description, parent_topic_id, "
        "created_at, engagement_id) VALUES (1, 'TOP-001', 'root', '', NULL, ?, ?)",
        (_NOW, engagement_id),
    )
    conn.execute(
        "INSERT INTO topics (id, identifier, name, description, parent_topic_id, "
        "created_at, engagement_id) VALUES (2, 'TOP-002', 'child', '', 1, ?, ?)",
        (_NOW, engagement_id),
    )
    # refs — the D4 edge (composite uniques); both engagements share the edge.
    conn.execute(
        "INSERT INTO refs (id, reference_identifier, source_type, source_id, "
        "target_type, target_id, relationship_kind, created_at, engagement_id) "
        "VALUES (1, 'REF-0001', 'decision', 'DEC-001', 'topic', 'TOP-001', "
        "'references', ?, ?)",
        (_NOW, engagement_id),
    )
    conn.commit()
    conn.close()


def test_consolidate_preserves_engagements_and_self_fks(tmp_path: Path) -> None:
    src_a = tmp_path / "ENG-001.db"
    src_b = tmp_path / "ENG-002.db"
    _build_source(src_a, "ENG-001")
    _build_source(src_b, "ENG-002")

    # Seed a meta DB with both engagements.
    meta = tmp_path / "engagements.db"
    mconn = sqlite3.connect(meta)
    mconn.execute(
        "CREATE TABLE engagements (engagement_identifier TEXT, engagement_code "
        "TEXT, engagement_name TEXT, engagement_purpose TEXT, engagement_status "
        "TEXT, engagement_created_at TEXT, engagement_updated_at TEXT, "
        "engagement_deleted_at TEXT)"
    )
    for eng in ("ENG-001", "ENG-002"):
        mconn.execute(
            "INSERT INTO engagements (engagement_identifier, engagement_code, "
            "engagement_name, engagement_purpose, engagement_status, "
            "engagement_created_at, engagement_updated_at) VALUES (?,?,?,?,?,?,?)",
            (eng, eng, eng, "p", "active", _NOW, _NOW),
        )
    mconn.commit()
    mconn.close()

    unified = tmp_path / "v2-unified.db"
    result = consolidate(
        unified,
        [SourceEngagement("ENG-001", src_a), SourceEngagement("ENG-002", src_b)],
        meta,
        catalog_source_identifier="ENG-001",
    )

    assert result.ok, result.errors
    assert result.null_engagement_rows == 0
    assert result.fk_violations == []

    conn = sqlite3.connect(unified)
    # Both engagements' TOP-001 coexist (composite-identifier coexistence).
    assert conn.execute(
        "SELECT COUNT(*) FROM topics WHERE identifier='TOP-001'"
    ).fetchone()[0] == 2
    # Per-engagement counts preserved.
    for eng in ("ENG-001", "ENG-002"):
        assert conn.execute(
            "SELECT COUNT(*) FROM topics WHERE engagement_id=?", (eng,)
        ).fetchone()[0] == 2
        assert conn.execute(
            "SELECT COUNT(*) FROM refs WHERE engagement_id=?", (eng,)
        ).fetchone()[0] == 1
    # The topics self-FK survived id reassignment: TOP-002's parent is TOP-001
    # *within the same engagement*, never the other engagement's TOP-001.
    for eng in ("ENG-001", "ENG-002"):
        child_parent_id, = conn.execute(
            "SELECT parent_topic_id FROM topics WHERE identifier='TOP-002' "
            "AND engagement_id=?", (eng,)
        ).fetchone()
        parent_eng, parent_ident = conn.execute(
            "SELECT engagement_id, identifier FROM topics WHERE id=?",
            (child_parent_id,),
        ).fetchone()
        assert parent_eng == eng
        assert parent_ident == "TOP-001"
    conn.close()


def test_consolidate_refuses_existing_unified_db(tmp_path: Path) -> None:
    import pytest

    unified = tmp_path / "v2-unified.db"
    unified.write_text("")
    with pytest.raises(FileExistsError):
        consolidate(unified, [], tmp_path / "m.db", catalog_source_identifier="ENG-001")

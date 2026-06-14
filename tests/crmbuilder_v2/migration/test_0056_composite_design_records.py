"""PI-189 slice 1 — migration 0054 creates associations + engine_overrides
and rebuilds the entity-type CHECKs.

Mirrors the test_0052 pattern: create_all, drop the two new tables to
simulate the pre-0054 state, stamp at 0053, upgrade to 0054 (explicit
revision so later chain growth doesn't perturb the single-step downgrade),
assert the tables are back, the change_log/refs CHECKs admit the two new
``association`` / ``engine_override`` types, the ``engine_overrides``
uniqueness constraint bites, and the pre-existing plain ``refs`` indexes
(``ix_refs_source`` / ``ix_refs_target``) survive the batch recreate, then
downgrade to 0053.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_DIR = _REPO_ROOT / "crmbuilder-v2"
_MIGRATION_DOWN = "0055_pi_182_field_entity_intrinsic"
_MIGRATION_UP = "0056_pi_189_composite_design_records"
_TABLES = ("associations", "engine_overrides")


def _alembic(args: list[str], db_path: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CRMBUILDER_V2_DB_PATH"] = str(db_path)
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(_ALEMBIC_DIR),
        env=env,
        capture_output=True,
        text=True,
    )


def test_0054_creates_and_drops_composite_design_tables(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))
        for table in _TABLES:
            c.execute(text(f"DROP TABLE IF EXISTS {table}"))
    engine.dispose()

    stamp = _alembic(["stamp", _MIGRATION_DOWN], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    up = _alembic(["upgrade", _MIGRATION_UP], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    eng = create_engine(f"sqlite:///{db}")
    insp = inspect(eng)
    names = set(insp.get_table_names())
    for table in _TABLES:
        assert table in names, f"{table} missing after 0054"

    # The pre-existing plain refs indexes survive the batch recreate (the
    # 0040 expression-index hazard does not apply — refs carries no
    # expression indexes, only these two plain column indexes).
    refs_indexes = {ix["name"] for ix in insp.get_indexes("refs")}
    assert "ix_refs_source" in refs_indexes
    assert "ix_refs_target" in refs_indexes

    with eng.begin() as c:
        # The recreated tables accept valid rows (CHECKs carried over).
        c.execute(
            text(
                "INSERT INTO associations "
                "(engagement_id, association_identifier, association_name, "
                "association_source_entity, association_target_entity, "
                "association_cardinality, association_status, "
                "association_created_at, association_updated_at) "
                "VALUES ('ENG-001', 'ASN-001', 'Mentor assignment', "
                "'ENT-001', 'ENT-002', 'many_to_many', 'candidate', "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        c.execute(
            text(
                "INSERT INTO engine_overrides "
                "(engagement_id, override_identifier, override_target_engine, "
                "override_subject_type, override_subject_identifier, "
                "override_attribute, override_created_at, override_updated_at) "
                "VALUES ('ENG-001', 'OVR-001', 'espocrm', 'association', "
                "'ASN-001', 'internal_name', CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP)"
            )
        )
        # The rebuilt change_log CHECK admits both new entity types.
        c.execute(
            text(
                "INSERT INTO change_log "
                "(timestamp, entity_type, entity_identifier, operation, actor, "
                "engagement_id) "
                "VALUES (CURRENT_TIMESTAMP, 'association', 'ASN-001', 'insert', "
                "'claude_session', 'ENG-001')"
            )
        )
        c.execute(
            text(
                "INSERT INTO change_log "
                "(timestamp, entity_type, entity_identifier, operation, actor, "
                "engagement_id) "
                "VALUES (CURRENT_TIMESTAMP, 'engine_override', 'OVR-001', "
                "'insert', 'claude_session', 'ENG-001')"
            )
        )
        # The rebuilt refs CHECKs admit the new types as source/target.
        c.execute(
            text(
                "INSERT INTO refs "
                "(reference_identifier, source_type, source_id, target_type, "
                "target_id, relationship_kind, created_at, engagement_id) "
                "VALUES ('REF-9201', 'engine_override', 'OVR-001', "
                "'association', 'ASN-001', 'references', CURRENT_TIMESTAMP, "
                "'ENG-001')"
            )
        )

    # The engine_overrides uniqueness tuple bites (same engine + subject +
    # attribute).
    with pytest.raises(IntegrityError):
        with eng.begin() as c:
            c.execute(
                text(
                    "INSERT INTO engine_overrides "
                    "(engagement_id, override_identifier, override_target_engine, "
                    "override_subject_type, override_subject_identifier, "
                    "override_attribute, override_created_at, override_updated_at) "
                    "VALUES ('ENG-001', 'OVR-002', 'espocrm', 'association', "
                    "'ASN-001', 'internal_name', CURRENT_TIMESTAMP, "
                    "CURRENT_TIMESTAMP)"
                )
            )
    eng.dispose()

    down = _alembic(["downgrade", _MIGRATION_DOWN], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    insp2 = inspect(create_engine(f"sqlite:///{db}"))
    names2 = set(insp2.get_table_names())
    for table in _TABLES:
        assert table not in names2, f"{table} present after downgrade"

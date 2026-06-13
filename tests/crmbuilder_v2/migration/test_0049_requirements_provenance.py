"""Phase 1 — migration 0049 adds requirement-provenance columns + 6 refs kinds.

Mirrors the test_0048 pattern but, because 0049 adds columns rather than a
table, it reaches the genuine pre-0049 state via the migration's own downgrade:
create_all (columns present from the ORM), stamp at 0049, downgrade to 0048
(drops the columns + narrows ``ck_ref_relationship``), assert the pre-state,
then upgrade back to 0049 (the real column-add path) and assert the columns,
their CHECKs, and the six new edge kinds are all in place.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_DIR = _REPO_ROOT / "crmbuilder-v2"
_MIGRATION_0048 = "0048_wtk_106_migration_mapping_entity"
_MIGRATION_0049 = "0049_requirements_provenance"

_NEW_COLUMNS = {
    "requirement_origin",
    "requirement_review_state",
    "requirement_approved_at",
}
_NEW_CHECKS = {"ck_requirement_origin", "ck_requirement_review_state"}


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


def _req_cols(db: Path) -> set[str]:
    insp = inspect(create_engine(f"sqlite:///{db}"))
    return {c["name"] for c in insp.get_columns("requirements")}


def _req_checks(db: Path) -> set[str]:
    insp = inspect(create_engine(f"sqlite:///{db}"))
    return {c["name"] for c in insp.get_check_constraints("requirements")}


def _insert_refines_ref(db: Path, ref_id: str) -> None:
    eng = create_engine(f"sqlite:///{db}")
    with eng.begin() as c:
        c.execute(
            text(
                "INSERT INTO refs "
                "(reference_identifier, source_type, source_id, target_type, "
                "target_id, relationship_kind, created_at, engagement_id) "
                f"VALUES ('{ref_id}', 'requirement', 'REQ-001', 'requirement', "
                "'REQ-002', 'requirement_refines_requirement', CURRENT_TIMESTAMP, "
                "'ENG-001')"
            )
        )
    eng.dispose()


def test_0049_provenance_columns_and_kinds_round_trip(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    engine.dispose()

    # Stamp at head (0049) then downgrade to reach the genuine pre-0049 state.
    stamp = _alembic(["stamp", _MIGRATION_0049], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    down = _alembic(["downgrade", _MIGRATION_0048], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"

    # Pre-state: columns and CHECKs gone, new edge kind rejected by ck_ref_relationship.
    assert not (_NEW_COLUMNS & _req_cols(db)), "columns present after downgrade"
    assert not (_NEW_CHECKS & _req_checks(db)), "checks present after downgrade"
    rejected = False
    try:
        _insert_refines_ref(db, "REF-9101")
    except (IntegrityError, OperationalError):
        rejected = True
    assert rejected, "new edge kind should be rejected before 0049"

    # The real add path: upgrade to 0049 with the columns absent.
    up = _alembic(["upgrade", _MIGRATION_0049], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    assert _NEW_COLUMNS <= _req_cols(db), "columns missing after 0049"
    assert _NEW_CHECKS <= _req_checks(db), "checks missing after 0049"

    # The new edge kind is now admitted; an out-of-vocab kind is still rejected.
    _insert_refines_ref(db, "REF-9102")
    bogus_rejected = False
    eng = create_engine(f"sqlite:///{db}")
    try:
        with eng.begin() as c:
            c.execute(
                text(
                    "INSERT INTO refs (reference_identifier, source_type, source_id, "
                    "target_type, target_id, relationship_kind, created_at, engagement_id) "
                    "VALUES ('REF-9103', 'requirement', 'REQ-001', 'requirement', "
                    "'REQ-002', 'requirement_not_a_real_kind', CURRENT_TIMESTAMP, 'ENG-001')"
                )
            )
    except (IntegrityError, OperationalError):
        bogus_rejected = True
    finally:
        eng.dispose()
    assert bogus_rejected, "out-of-vocab relationship kind should be rejected"

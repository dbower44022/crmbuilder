"""PI-471 — migration 0140: the ``transitions`` table and the four reference
kinds that name an individual move (REQ-577, REQ-583).

create_all (post-change schema), stamp 0140, run the real downgrade to 0139
(the table is gone, a pre-existing edge naming a transition is removed, and a
new one is refused by the narrowed CHECKs), then upgrade 0140 again (the table
is back and a transition row and a ``view_offers_transition`` edge are
accepted). The suite otherwise only stamps this revision, so without this test
the migration's own code would never run.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, exc, inspect, text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_DIR = _REPO_ROOT / "crmbuilder-v2"
_DOWN = "0139_pi_488_session_opening_fields"
_MIGRATION = "0140_pi_471_transitions"

_TRANSITION_COLS = (
    "engagement_id, transition_identifier, transition_process, "
    "transition_field, transition_from_kind, transition_from_values, "
    "transition_to_value, transition_actor_kind, transition_required_fields, "
    "transition_consequences, transition_order, transition_status, "
    "transition_created_at, transition_updated_at"
)


def _alembic(args: list[str], db_path: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CRMBUILDER_V2_DB_PATH"] = str(db_path)
    # The migration rebuilds the CHECKs from ``crmbuilder_v2.access.vocab``, so
    # the subprocess must import the checkout under test, not the venv's
    # editable install (lesson LSN-080).
    env["PYTHONPATH"] = os.pathsep.join(
        [str(_ALEMBIC_DIR / "src"), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(_ALEMBIC_DIR), env=env, capture_output=True, text=True,
    )


def _insert_transition(c, identifier: str) -> None:
    c.execute(
        text(
            f"INSERT INTO transitions ({_TRANSITION_COLS}) VALUES ('ENG-001', "
            f"'{identifier}', 'PROC-001', 'FLD-001', 'values', '[\"Candidate\"]', "
            "'Under Review', 'system', '[]', '[]', 0, 'candidate', "
            "'2026-01-01', '2026-01-01')"
        )
    )


def _insert_edge(c, kind: str, source_type: str, source_id: str) -> None:
    c.execute(
        text(
            "INSERT INTO refs (engagement_id, source_type, source_id, target_type, "
            "target_id, relationship_kind, created_at) VALUES ('ENG-001', "
            f"'{source_type}', '{source_id}', 'transition', 'TRN-001', '{kind}', "
            "'2026-01-01')"
        )
    )


def test_0140_round_trips_the_table_and_the_checks(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))
        c.execute(
            text(
                "INSERT INTO engagements (engagement_identifier, engagement_code, "
                "engagement_name, engagement_purpose, engagement_status, "
                "engagement_created_at, engagement_updated_at) VALUES ('ENG-001', "
                "'CRMBUILDER', 'CRMBuilder', 'dogfood', 'active', '2026-01-01', "
                "'2026-01-01')"
            )
        )
        _insert_transition(c, "TRN-001")
        _insert_edge(c, "view_offers_transition", "view", "VEW-001")
        _insert_edge(c, "is_about", "decision", "DEC-001")
    engine.dispose()
    assert _alembic(["stamp", _MIGRATION], db).returncode == 0

    down = _alembic(["downgrade", _DOWN], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    engine = create_engine(f"sqlite:///{db}")
    assert "transitions" not in inspect(engine).get_table_names()
    with engine.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))
        # Every edge touching a transition is removed, the generic one included,
        # because the narrowed target-type CHECK no longer admits the type.
        assert c.execute(text("SELECT COUNT(*) FROM refs")).scalar() == 0
    with engine.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))
        with pytest.raises(exc.IntegrityError):
            _insert_edge(c, "view_offers_transition", "view", "VEW-002")
    engine.dispose()

    up = _alembic(["upgrade", _MIGRATION], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    engine = create_engine(f"sqlite:///{db}")
    assert "transitions" in inspect(engine).get_table_names()
    with engine.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))
        _insert_transition(c, "TRN-001")
        _insert_edge(c, "view_offers_transition", "view", "VEW-002")
        _insert_edge(c, "automation_triggered_by_transition", "automation", "AUT-001")
        kinds = set(c.execute(text("SELECT relationship_kind FROM refs")).scalars())
    engine.dispose()
    assert kinds == {"view_offers_transition", "automation_triggered_by_transition"}

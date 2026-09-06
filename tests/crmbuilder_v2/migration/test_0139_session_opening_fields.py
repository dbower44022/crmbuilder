"""PI-488 — migration 0139: the session fields that record the opening answer
and what followed from it (REQ-568).

create_all (post-change schema), stamp 0139, run the real downgrade to 0138
(the four columns are gone), upgrade 0139 again (the columns are back with a
NULL answer and an empty segment list on the pre-existing row).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect, text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_DIR = _REPO_ROOT / "crmbuilder-v2"
_DOWN = "0138_pi_462_withdraws_and_claude_code"
_MIGRATION = "0139_pi_488_session_opening_fields"
_NEW = {
    "session_opening_answer",
    "session_kind_of_work",
    "session_confirmation_line",
    "session_phase_segments",
}
_SUMMARY = "s" * 200


def _alembic(args: list[str], db_path: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CRMBUILDER_V2_DB_PATH"] = str(db_path)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(_ALEMBIC_DIR / "src"), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(_ALEMBIC_DIR), env=env, capture_output=True, text=True,
    )


def _session_columns(db: Path) -> set[str]:
    engine = create_engine(f"sqlite:///{db}")
    try:
        return {c["name"] for c in inspect(engine).get_columns("sessions")}
    finally:
        engine.dispose()


def test_0139_round_trips_the_four_columns(tmp_path: Path) -> None:
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
        c.execute(
            text(
                "INSERT INTO sessions (engagement_id, session_identifier, "
                "session_title, session_description, session_medium, session_status, "
                "session_executive_summary, session_participants, "
                "session_medium_metadata, session_opening_answer, "
                "session_kind_of_work, session_confirmation_line, "
                "session_phase_segments, session_created_at, session_updated_at) "
                "VALUES ('ENG-001', 'SES-001', 't', 'd', 'claude_code', 'in_flight', "
                f"'{_SUMMARY}', '[]', '{{}}', 'define new business processes', "
                "'PROC-020', 'It sounds like you want to define new business "
                "processes.', '[{\"position\": 1}]', '2026-01-01', '2026-01-01')"
            )
        )
    engine.dispose()
    assert _NEW <= _session_columns(db)
    assert _alembic(["stamp", _MIGRATION], db).returncode == 0

    down = _alembic(["downgrade", _DOWN], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    assert not (_NEW & _session_columns(db))

    up = _alembic(["upgrade", _MIGRATION], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    assert _NEW <= _session_columns(db)
    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as c:
        row = c.execute(
            text(
                "SELECT session_opening_answer, session_kind_of_work, "
                "session_confirmation_line, session_phase_segments FROM sessions"
            )
        ).one()
    engine.dispose()
    # The pre-existing row reads NULL / the empty list after the round trip.
    assert row[0] is None and row[1] is None and row[2] is None
    assert row[3] in ("[]", [])

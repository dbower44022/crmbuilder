"""PI-462 — migration 0138: the ``withdraws`` reference kind and the
``claude_code`` session medium (REQ-560 / REQ-561).

create_all (post-change schema), stamp 0138, run the real downgrade to 0137
(a ``withdraws`` edge and a ``claude_code`` session are refused by the narrowed
CHECKs; a pre-existing ``withdraws`` row is gone and a ``claude_code`` session
reads ``chat``), upgrade 0138 again: both values are accepted.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, exc, text

from tests.crmbuilder_v2.migration._pg_chain import alembic as _alembic
from tests.crmbuilder_v2.migration._pg_chain import fresh_db, requires_postgres

pytestmark = requires_postgres

_DOWN = "0094_pi_418_portal_layout_types"
_MIGRATION = "0095_pi_462_withdraws_and_claude_code"

_SESSION_COLS = (
    "engagement_id, session_identifier, session_title, session_description, "
    "session_medium, session_status, session_executive_summary, "
    "session_participants, session_medium_metadata, "
    "session_created_at, session_updated_at"
)
_SUMMARY = "s" * 200




def _insert_ref(c, kind: str, source_id: str) -> None:
    c.execute(
        text(
            "INSERT INTO refs (engagement_id, source_type, source_id, target_type, "
            "target_id, relationship_kind, created_at) VALUES ('ENG-001', "
            f"'decision', '{source_id}', 'requirement', 'REQ-001', '{kind}', "
            "'2026-01-01')"
        )
    )


def _insert_session(c, medium: str, identifier: str) -> None:
    c.execute(
        text(
            f"INSERT INTO sessions ({_SESSION_COLS}) VALUES ('ENG-001', "
            f"'{identifier}', 't', 'd', '{medium}', 'planned', '{_SUMMARY}', "
            "'[]', '{}', '2026-01-01', '2026-01-01')"
        )
    )


def test_0138_round_trips_both_checks() -> None:
    db = fresh_db()
    engine = create_engine(db)
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("SET session_replication_role = replica"))
        c.execute(
            text(
                "INSERT INTO engagements (engagement_identifier, engagement_code, "
                "engagement_name, engagement_purpose, engagement_status, "
                "engagement_created_at, engagement_updated_at) VALUES ('ENG-001', "
                "'CRMBUILDER', 'CRMBuilder', 'dogfood', 'active', '2026-01-01', "
                "'2026-01-01')"
            )
        )
        # Rows the post-change schema admits: they must survive the downgrade
        # in the narrowed shape (edge removed, medium mapped back to chat).
        _insert_ref(c, "withdraws", "DEC-001")
        _insert_ref(c, "is_about", "DEC-002")
        _insert_session(c, "claude_code", "SES-001")
        _insert_session(c, "chat", "SES-002")
    engine.dispose()
    assert _alembic(["stamp", _MIGRATION], db).returncode == 0

    down = _alembic(["downgrade", _DOWN], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    engine = create_engine(db)
    with engine.begin() as c:
        c.execute(text("SET session_replication_role = replica"))
        kinds = c.execute(text("SELECT relationship_kind FROM refs")).scalars().all()
        assert kinds == ["is_about"]
        mediums = dict(
            c.execute(
                text("SELECT session_identifier, session_medium FROM sessions")
            ).all()
        )
        assert mediums == {"SES-001": "chat", "SES-002": "chat"}
        with pytest.raises(exc.IntegrityError):
            _insert_ref(c, "withdraws", "DEC-003")
    with engine.begin() as c:
        c.execute(text("SET session_replication_role = replica"))
        with pytest.raises(exc.IntegrityError):
            _insert_session(c, "claude_code", "SES-003")
    engine.dispose()

    up = _alembic(["upgrade", _MIGRATION], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    engine = create_engine(db)
    with engine.begin() as c:
        c.execute(text("SET session_replication_role = replica"))
        _insert_ref(c, "withdraws", "DEC-003")
        _insert_session(c, "claude_code", "SES-003")
        kinds = set(c.execute(text("SELECT relationship_kind FROM refs")).scalars())
        mediums = set(c.execute(text("SELECT session_medium FROM sessions")).scalars())
    engine.dispose()
    assert kinds == {"is_about", "withdraws"}
    assert mediums == {"chat", "claude_code"}

"""PI-512 — ``client_management_0002_clients`` creates ``clients`` and
``engagement_clients`` on the client_management branch, its guarded data step
assigns the six known engagements only where they exist, one primary per
engagement is enforced, and the downgrade drops both tables."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from tests.crmbuilder_v2.migration._pg_chain import alembic as _alembic
from tests.crmbuilder_v2.migration._pg_chain import (
    fresh_db,
    requires_postgres,
    stamp_heads,
)

pytestmark = requires_postgres

_FORK = "client_management_0001_branch"
_NEW = {"clients", "engagement_clients"}


def _tables(db: str) -> set[str]:
    eng = create_engine(db)
    try:
        return set(inspect(eng).get_table_names())
    finally:
        eng.dispose()


def _seed_engagements(db: str, identifiers: list[str]) -> None:
    eng = create_engine(db)
    try:
        with eng.begin() as c:
            for ident in identifiers:
                c.execute(
                    text(
                        "INSERT INTO engagements (engagement_identifier, engagement_code, "
                        "engagement_name, engagement_purpose, engagement_status, "
                        "engagement_created_at, engagement_updated_at) VALUES "
                        "(:i, :c, :n, 'p', 'active', NOW(), NOW())"
                    ),
                    {"i": ident, "c": ident.replace("-", ""), "n": f"Engagement {ident}"},
                )
    finally:
        eng.dispose()


def _rows(db: str, sql: str) -> list:
    eng = create_engine(db)
    try:
        with eng.begin() as c:
            return list(c.execute(text(sql)).all())
    finally:
        eng.dispose()


def test_create_assign_enforce_and_drop() -> None:
    db = fresh_db()
    engine = create_engine(db)
    Base.metadata.create_all(engine)
    engine.dispose()
    assert _NEW <= _tables(db)
    assert stamp_heads(db).returncode == 0

    # Downgrade the branch one step: both tables go.
    down = _alembic(["downgrade", f"client_management@{_FORK}"], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    assert not (_NEW & _tables(db))

    # Upgrade on an empty store: tables back, data step does nothing.
    up = _alembic(["upgrade", "heads"], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    assert _NEW <= _tables(db)
    assert _rows(db, "SELECT count(*) FROM clients")[0][0] == 0

    # Downgrade again, seed the live store's engagements, upgrade: assigned.
    assert _alembic(["downgrade", f"client_management@{_FORK}"], db).returncode == 0
    _seed_engagements(db, ["ENG-001", "ENG-002", "ENG-003", "ENG-004", "ENG-005", "ENG-006"])
    up = _alembic(["upgrade", "heads"], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    clients = _rows(db, "SELECT client_identifier, client_name FROM clients ORDER BY 1")
    assert clients == [("CLI-001", "Cleveland Business Mentors"), ("CLI-002", "CRMBuilder")]
    links = _rows(
        db,
        "SELECT engagement_id, client_id, is_primary FROM engagement_clients ORDER BY 1",
    )
    assert links == [
        ("ENG-001", "CLI-002", True),
        ("ENG-002", "CLI-001", True),
        ("ENG-004", "CLI-001", True),
        ("ENG-005", "CLI-002", True),
    ]

    # Re-running the data step is a no-op (the clients already exist).
    assert _alembic(["upgrade", "heads"], db).returncode == 0
    assert _rows(db, "SELECT count(*) FROM clients")[0][0] == 2

    # One primary per engagement is enforced by the partial unique index.
    eng = create_engine(db)
    try:
        with eng.begin() as c:
            c.execute(
                text(
                    "INSERT INTO clients (client_identifier, client_name, client_status, "
                    "client_created_at, client_updated_at) VALUES ('CLI-003', 'C', 'active', NOW(), NOW())"
                )
            )
        with pytest.raises(IntegrityError), eng.begin() as c:
            c.execute(
                text(
                    "INSERT INTO engagement_clients (engagement_id, client_id, is_primary, created_at) "
                    "VALUES ('ENG-002', 'CLI-003', true, NOW())"
                )
            )
        with eng.begin() as c:  # a second, non-primary client is fine (a chapter)
            c.execute(
                text(
                    "INSERT INTO engagement_clients (engagement_id, client_id, is_primary, created_at) "
                    "VALUES ('ENG-002', 'CLI-003', false, NOW())"
                )
            )
    finally:
        eng.dispose()

    # Heads: one per branch, and this revision sits on the client_management
    # branch (it stopped being that branch's head at
    # client_management_0003_application_attributes, PI-575).
    heads = _alembic(["heads"], db)
    assert sum(line.startswith("client_management_") for line in heads.stdout.splitlines()) == 1
    history = _alembic(["history", "-r", "client_management_0001_branch:client_management@head"], db)
    assert "client_management_0002_clients" in history.stdout

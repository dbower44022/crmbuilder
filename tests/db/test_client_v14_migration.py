"""Tests for the _client_v14 migration.

Widens the ConfigurationRun.outcome CHECK constraint from the original
('success', 'error') to ('success', 'partial', 'error', 'cancelled').
"""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from automation.db.migrations import run_client_migrations


def _insert_run(conn: sqlite3.Connection, outcome: str) -> None:
    """Insert one ConfigurationRun row with the given outcome.

    Cleans up after itself so each call starts from an empty Instance
    table (Instance.code has a UNIQUE constraint).
    """
    now = datetime.now(UTC).isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO Instance (name, code, environment) "
        "VALUES (?, ?, ?)",
        ("test-instance", "TST", "test"),
    )
    inst_id = conn.execute(
        "SELECT id FROM Instance WHERE name = 'test-instance'"
    ).fetchone()[0]
    try:
        conn.execute(
            "INSERT INTO ConfigurationRun "
            "(instance_id, file_name, operation, outcome, started_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (inst_id, "x.yaml", "run", outcome, now),
        )
    finally:
        conn.execute("DELETE FROM ConfigurationRun")
        conn.execute("DELETE FROM Instance")


@pytest.fixture()
def db(tmp_path: Path) -> sqlite3.Connection:
    conn = run_client_migrations(str(tmp_path / "client.db"))
    yield conn
    conn.close()


def test_outcome_accepts_success(db: sqlite3.Connection) -> None:
    _insert_run(db, "success")


def test_outcome_accepts_partial(db: sqlite3.Connection) -> None:
    _insert_run(db, "partial")


def test_outcome_accepts_error(db: sqlite3.Connection) -> None:
    _insert_run(db, "error")


def test_outcome_accepts_cancelled(db: sqlite3.Connection) -> None:
    _insert_run(db, "cancelled")


def test_outcome_rejects_unknown(db: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        _insert_run(db, "frobnicated")

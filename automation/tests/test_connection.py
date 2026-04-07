"""Tests for database connection management."""

import sqlite3

import pytest

from automation.db.connection import (
    close_connection,
    connect,
    open_connection,
    transaction,
)


class TestOpenClose:
    def test_open_returns_connection(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = open_connection(db_path)
        assert isinstance(conn, sqlite3.Connection)
        conn.close()

    def test_foreign_keys_enabled(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = open_connection(db_path)
        result = conn.execute("PRAGMA foreign_keys").fetchone()
        assert result[0] == 1
        conn.close()

    def test_close_connection(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = open_connection(db_path)
        close_connection(conn)
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")


class TestConnectContextManager:
    def test_yields_connection(self, tmp_path):
        db_path = tmp_path / "test.db"
        with connect(db_path) as conn:
            assert isinstance(conn, sqlite3.Connection)

    def test_foreign_keys_enabled(self, tmp_path):
        db_path = tmp_path / "test.db"
        with connect(db_path) as conn:
            result = conn.execute("PRAGMA foreign_keys").fetchone()
            assert result[0] == 1

    def test_closes_on_normal_exit(self, tmp_path):
        db_path = tmp_path / "test.db"
        with connect(db_path) as conn:
            pass
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_closes_on_exception(self, tmp_path):
        db_path = tmp_path / "test.db"
        with pytest.raises(ValueError, match="test error"):
            with connect(db_path) as conn:
                raise ValueError("test error")
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")


class TestTransaction:
    def test_commit_on_success(self, tmp_path):
        db_path = tmp_path / "test.db"
        with connect(db_path) as conn:
            conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
            conn.commit()
            with transaction(conn):
                conn.execute("INSERT INTO t (val) VALUES ('hello')")
            row = conn.execute("SELECT val FROM t").fetchone()
            assert row[0] == "hello"

    def test_rollback_on_exception(self, tmp_path):
        db_path = tmp_path / "test.db"
        with connect(db_path) as conn:
            conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
            conn.commit()
            with pytest.raises(RuntimeError, match="fail"):
                with transaction(conn):
                    conn.execute("INSERT INTO t (val) VALUES ('should_not_persist')")
                    raise RuntimeError("fail")
            row = conn.execute("SELECT COUNT(*) FROM t").fetchone()
            assert row[0] == 0

    def test_data_persists_after_commit(self, tmp_path):
        db_path = tmp_path / "test.db"
        with connect(db_path) as conn:
            conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
            conn.commit()
            with transaction(conn):
                conn.execute("INSERT INTO t (val) VALUES ('persist')")

        with connect(db_path) as conn2:
            row = conn2.execute("SELECT val FROM t").fetchone()
            assert row[0] == "persist"

    def test_multiple_operations_in_transaction(self, tmp_path):
        db_path = tmp_path / "test.db"
        with connect(db_path) as conn:
            conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
            conn.commit()
            with transaction(conn):
                conn.execute("INSERT INTO t (val) VALUES ('a')")
                conn.execute("INSERT INTO t (val) VALUES ('b')")
                conn.execute("INSERT INTO t (val) VALUES ('c')")
            rows = conn.execute("SELECT COUNT(*) FROM t").fetchone()
            assert rows[0] == 3

    def test_all_rolled_back_on_partial_failure(self, tmp_path):
        db_path = tmp_path / "test.db"
        with connect(db_path) as conn:
            conn.execute(
                "CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT UNIQUE)"
            )
            conn.commit()
            with pytest.raises(sqlite3.IntegrityError):
                with transaction(conn):
                    conn.execute("INSERT INTO t (val) VALUES ('a')")
                    conn.execute("INSERT INTO t (val) VALUES ('b')")
                    conn.execute("INSERT INTO t (val) VALUES ('a')")  # duplicate
            rows = conn.execute("SELECT COUNT(*) FROM t").fetchone()
            assert rows[0] == 0

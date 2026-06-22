"""SQLite engine pragma tests — REQ-296 / PI-253.

The access layer opens every SQLite connection in WAL journal mode so a read
never blocks while another connection is writing (and vice versa). In the old
rollback-journal (delete) mode a single writer blocked all readers, which froze
the desktop UI's periodic refresh and cascaded into a reconnect loop.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import get_engine


def test_sqlite_engine_uses_wal_journal_mode(v2_env):
    engine = get_engine()
    if engine.dialect.name != "sqlite":
        pytest.skip("WAL journal mode is SQLite-specific")
    with engine.connect() as conn:
        mode = conn.exec_driver_sql("PRAGMA journal_mode").scalar()
    assert (mode or "").lower() == "wal"

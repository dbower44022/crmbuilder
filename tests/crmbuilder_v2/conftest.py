"""Shared pytest fixtures for crmbuilder_v2.

Each test gets a fresh SQLite database file and an isolated JSON-export
directory. Settings and engine caches are reset so that environment
variables set by the fixture propagate.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from crmbuilder_v2.access.db import (
    bootstrap_database,
    force_export,
    reset_engine_cache,
)
from crmbuilder_v2.config import get_settings, reset_settings_cache


@pytest.fixture
def v2_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    db = tmp_path / "v2.db"
    export = tmp_path / "db-export"
    monkeypatch.setenv("CRMBUILDER_V2_DB_PATH", str(db))
    monkeypatch.setenv("CRMBUILDER_V2_EXPORT_DIR", str(export))
    reset_settings_cache()
    reset_engine_cache()
    bootstrap_database()
    force_export()
    yield tmp_path
    reset_engine_cache()
    reset_settings_cache()


@pytest.fixture
def settings(v2_env):
    return get_settings()


@pytest.fixture
def export_dir(v2_env: Path) -> Path:
    return v2_env / "db-export"

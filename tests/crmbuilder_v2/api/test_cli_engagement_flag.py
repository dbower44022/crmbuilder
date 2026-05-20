"""Multi-tenancy routing fix slice A — CLI ``--engagement`` integration tests.

These spawn the actual ``crmbuilder-v2-api`` entry point as a subprocess
(via ``python -c``) and assert exit code / stdout / stderr. ``--check-only``
is used to exercise resolve+route without binding uvicorn.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from crmbuilder_v2.access.db import reset_engine_cache
from crmbuilder_v2.access.engagement import create_engagement
from crmbuilder_v2.access.meta_db import (
    bootstrap_meta_db,
    meta_session_scope,
    reset_meta_engine_cache,
)
from crmbuilder_v2.config import reset_settings_cache


@pytest.fixture
def cli_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A temp data dir whose meta DB has CRMBUILDER + CBM engagements.

    ``data_dir()`` resolves to ``tmp_path`` (db_path = tmp_path/v2.db).
    The v2.db file is deliberately NOT created, so ``needs_migration()``
    is False in the spawned subprocess.
    """
    monkeypatch.setenv("CRMBUILDER_V2_DB_PATH", str(tmp_path / "v2.db"))
    monkeypatch.delenv("CRMBUILDER_V2_EXPORT_DIR", raising=False)

    from crmbuilder_v2.access import meta_exporter

    monkeypatch.setattr(
        meta_exporter, "meta_export_dir", lambda: tmp_path / "meta-export"
    )
    reset_settings_cache()
    reset_engine_cache()
    reset_meta_engine_cache()
    bootstrap_meta_db()
    with meta_session_scope() as s:
        create_engagement(
            s,
            engagement_code="CRMBUILDER",
            engagement_name="Dogfood",
            engagement_purpose="p",
        )
        create_engagement(
            s,
            engagement_code="CBM",
            engagement_name="Cleveland",
            engagement_purpose="p",
        )
    yield tmp_path
    reset_meta_engine_cache()
    reset_engine_cache()
    reset_settings_cache()


def _write_marker(data_dir: Path, code: str) -> None:
    (data_dir / "current_engagement.json").write_text(
        json.dumps({"engagement_identifier": "ENG-001", "engagement_code": code}),
        encoding="utf-8",
    )


def _run_cli(data_dir: Path, args: list[str]) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "CRMBUILDER_V2_EXPORT_DIR"}
    env["CRMBUILDER_V2_DB_PATH"] = str(data_dir / "v2.db")
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "from crmbuilder_v2.cli import run_api; run_api()",
            *args,
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_no_marker_no_flag_fails_loud_exit_2(cli_workspace):
    result = _run_cli(cli_workspace, [])
    assert result.returncode == 2
    assert "No active engagement" in (result.stdout + result.stderr)


def test_marker_only_starts_normally(cli_workspace):
    _write_marker(cli_workspace, "CRMBUILDER")
    result = _run_cli(cli_workspace, ["--check-only"])
    assert result.returncode == 0, result.stderr
    assert "active engagement CRMBUILDER" in result.stdout


def test_flag_overrides_marker_with_log_line(cli_workspace):
    _write_marker(cli_workspace, "CRMBUILDER")
    result = _run_cli(cli_workspace, ["--check-only", "--engagement", "CBM"])
    assert result.returncode == 0, result.stderr
    assert "overrides current_engagement.json (CRMBUILDER)" in result.stderr
    assert "active engagement CBM" in result.stdout


def test_flag_matches_marker_no_log_line(cli_workspace):
    _write_marker(cli_workspace, "CBM")
    result = _run_cli(cli_workspace, ["--check-only", "--engagement", "CBM"])
    assert result.returncode == 0, result.stderr
    assert "overrides" not in result.stderr
    assert "active engagement CBM" in result.stdout


def test_bogus_flag_fails_loud_exit_2_with_available_codes(cli_workspace):
    result = _run_cli(cli_workspace, ["--engagement", "BOGUS"])
    assert result.returncode == 2
    out = result.stdout + result.stderr
    assert "Unknown engagement 'BOGUS'" in out
    assert "CRMBUILDER" in out and "CBM" in out


def test_bogus_marker_fails_loud_exit_2(cli_workspace):
    _write_marker(cli_workspace, "BOGUS")
    result = _run_cli(cli_workspace, [])
    assert result.returncode == 2
    assert "Active engagement 'BOGUS' not found in meta DB" in (
        result.stdout + result.stderr
    )

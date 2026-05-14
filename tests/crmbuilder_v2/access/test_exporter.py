"""JSON export hook tests — atomicity and schema fidelity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import decisions


def test_bootstrap_creates_all_export_files(v2_env, export_dir: Path):
    expected = {
        "charter.json",
        "status.json",
        "decisions.json",
        "sessions.json",
        "risks.json",
        "planning_items.json",
        "topics.json",
        # Methodology entity snapshot — landed in UI v0.4 slice B.
        "domains.json",
        "references.json",
        "change_log.json",
    }
    actual = {p.name for p in export_dir.iterdir() if p.suffix == ".json"}
    assert expected == actual


def test_export_reflects_writes(v2_env, export_dir: Path):
    with session_scope() as s:
        decisions.create(
            s,
            identifier="DEC-042",
            title="The Answer",
            decision_date="05-07-26",
            status="Active",
        )
    rows = json.loads((export_dir / "decisions.json").read_text())
    assert len(rows) == 1
    assert rows[0]["identifier"] == "DEC-042"


def test_failed_write_does_not_affect_exports(
    v2_env, export_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    """If the body raises after some writes, both DB and exports roll back."""
    before = (export_dir / "decisions.json").read_text()
    with pytest.raises(RuntimeError):
        with session_scope() as s:
            decisions.create(
                s,
                identifier="DEC-001",
                title="t",
                decision_date="05-07-26",
                status="Active",
            )
            raise RuntimeError("simulated failure")
    after = (export_dir / "decisions.json").read_text()
    assert before == after  # rolled back; export unchanged


def test_no_temp_files_remain_after_success(v2_env, export_dir: Path):
    with session_scope() as s:
        decisions.create(
            s,
            identifier="DEC-001",
            title="t",
            decision_date="05-07-26",
            status="Active",
        )
    leftovers = list(export_dir.glob("*.tmp"))
    assert leftovers == []


def test_no_temp_files_remain_after_rollback(
    v2_env, export_dir: Path
):
    with pytest.raises(RuntimeError):
        with session_scope() as s:
            decisions.create(
                s,
                identifier="DEC-001",
                title="t",
                decision_date="05-07-26",
                status="Active",
            )
            raise RuntimeError("boom")
    leftovers = list(export_dir.glob("*.tmp"))
    assert leftovers == []


def test_export_failure_rolls_back_db(
    v2_env, export_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    """If the JSON export step raises, the DB write rolls back too."""
    from crmbuilder_v2.access import exporter

    def boom(*_args, **_kwargs):
        raise OSError("export disk failure simulated")

    monkeypatch.setattr(exporter, "write_staging", boom)

    with pytest.raises(OSError):
        with session_scope() as s:
            decisions.create(
                s,
                identifier="DEC-EXPLODE",
                title="t",
                decision_date="05-07-26",
                status="Active",
            )

    # DB transaction should have rolled back: no DEC-EXPLODE row.
    with session_scope(export=False) as s:
        rows = decisions.list_all(s)
    assert all(r["identifier"] != "DEC-EXPLODE" for r in rows)

"""JSON export hook tests — atomicity and schema fidelity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import decisions

_VALID_EXEC_SUMMARY = "PI-102 test executive summary. " * 7


def test_bootstrap_creates_all_export_files(v2_env, export_dir: Path):
    expected = {
        "charter.json",
        "status.json",
        "decisions.json",
        "sessions.json",
        "risks.json",
        "planning_items.json",
            "engagement_areas.json",
        "topics.json",
        # Methodology entity snapshots — domains landed in UI v0.4
        # slice B, entities in slice C, processes in slice D,
        # crm_candidates in slice E, personas in v0.5+ (PI-003),
        # fields in v0.5+ (PI-004 first slice; exporter registration
        # added retroactively in the PI-004 cohort manual_config
        # build's in-scope cleanup), requirements in v0.5+ (PI-004
        # cohort), and manual_configs in v0.5+ (PI-004 cohort).
        "domains.json",
        "entities.json",
        "processes.json",
        "crm_candidates.json",
        "personas.json",
        "fields.json",
        "requirements.json",
        "manual_configs.json",
        # PI-004 cohort closer — test_specs (resolves PI-004).
        "test_specs.json",
        # Governance entity snapshots (UI v0.7).
        "projects.json",
        "workstreams.json",
        "conversations.json",
        "reference_books.json",
        "reference_book_versions.json",
        "work_tickets.json",
        "close_out_payloads.json",
        "deposit_events.json",
        # v0.8 governance entity (PI-029, commit.md) — registered in
        # exporter._EXPORT_TABLES by PI-053 so commits.json regenerates
        # alongside the other governance snapshots.
        "commits.json",
        "references.json",
        "change_log.json",
    }
    actual = {p.name for p in export_dir.iterdir() if p.suffix == ".json"}
    assert expected == actual


def test_commit_model_in_export_tables():
    """PI-053 — Commit must be registered in _EXPORT_TABLES so commits.json
    regenerates when snapshots regenerate."""
    from crmbuilder_v2.access.exporter import _EXPORT_TABLES
    from crmbuilder_v2.access.models import Commit

    names = [name for name, _ in _EXPORT_TABLES]
    models = [model for _, model in _EXPORT_TABLES]
    assert "commits" in names
    assert Commit in models
    # And the (filename, model) pairing is correct.
    assert ("commits", Commit) in _EXPORT_TABLES


def test_export_reflects_writes(v2_env, export_dir: Path):
    with session_scope() as s:
        decisions.create(
            s,
            identifier="DEC-042",
            title="The Answer",
            decision_date="05-07-26",
            status="Active",
            executive_summary=_VALID_EXEC_SUMMARY,
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
                executive_summary=_VALID_EXEC_SUMMARY,
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
            executive_summary=_VALID_EXEC_SUMMARY,
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
                executive_summary=_VALID_EXEC_SUMMARY,
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
                identifier="DEC-999",
                title="t",
                decision_date="05-07-26",
                status="Active",
                executive_summary=_VALID_EXEC_SUMMARY,
            )

    # DB transaction should have rolled back: no DEC-999 row.
    with session_scope(export=False) as s:
        rows = decisions.list_all(s)
    assert all(r["identifier"] != "DEC-999" for r in rows)

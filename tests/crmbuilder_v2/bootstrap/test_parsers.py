"""Bootstrap parser unit tests, exercised against fixture markdown files."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def fixtures_dir() -> Path:
    return FIXTURES


def test_parse_decisions(fixtures_dir):
    from crmbuilder_v2.bootstrap.parsers.decisions import parse_decisions

    rows = parse_decisions(fixtures_dir / "decisions.md")
    assert {r["identifier"] for r in rows} == {"DEC-001", "DEC-002"}
    d1 = next(r for r in rows if r["identifier"] == "DEC-001")
    assert d1["title"].startswith("First decision")
    assert d1["status"] == "Active"
    assert d1["context"].startswith("This is the context")
    assert d1["alternatives_considered"].startswith("- Option A")


def test_parse_sessions_with_decision_references(fixtures_dir):
    from crmbuilder_v2.bootstrap.parsers.sessions import parse_sessions

    rows = parse_sessions(fixtures_dir / "sessions.md")
    assert len(rows) == 1
    ses = rows[0]
    assert ses["identifier"] == "SES-001"
    # "DEC-001 through DEC-002" plus a stray "DEC-002" mention should resolve
    # to a sorted unique list.
    assert ses["decisions_made"] == ["DEC-001", "DEC-002"]


def test_parse_charter_with_changelog(fixtures_dir):
    from crmbuilder_v2.bootstrap.parsers.charter import parse_charter

    rows = parse_charter(fixtures_dir / "charter.md")
    # Two change-log entries → two version rows.
    assert [r["version"] for r in rows] == [1, 2]
    assert rows[-1]["is_current"] is True
    # Current row carries the full payload structure.
    assert "sections" in rows[-1]["payload"]
    assert "Scope" in rows[-1]["payload"]["sections"]


def test_parse_status_without_changelog(fixtures_dir):
    from crmbuilder_v2.bootstrap.parsers.status import parse_status

    rows = parse_status(fixtures_dir / "status_no_changelog.md")
    assert len(rows) == 1
    assert rows[0]["version"] == 1
    assert rows[0]["is_current"] is True

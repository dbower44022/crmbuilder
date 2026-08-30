"""PI-433 / REQ-527 — Status payload generated from stored records."""

from __future__ import annotations

from datetime import UTC, datetime

from crmbuilder_v2 import __version__
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import planning_items, projects, status
from crmbuilder_v2.access.status_snapshot import build_status_payload

_EXEC = "Executive summary for a generated-status test planning item. " * 4


def _pi(s, ident, pi_status):
    return planning_items.create(
        s,
        identifier=ident,
        title=f"PI {ident}",
        item_type="pending_work",
        status=pi_status,
        executive_summary=_EXEC,
    )


def test_payload_without_prior_version(v2_env):
    with session_scope() as s:
        projects.create_project(
            s,
            identifier="PRJ-900",
            name="Generated status",
            purpose="p",
            description="d",
            status="in_flight",
        )
        _pi(s, "PI-900", "In Progress")
        _pi(s, "PI-901", "Draft")
        _pi(s, "PI-902", "Resolved")
        payload = build_status_payload(
            s, narrative="hello", now=datetime(2026, 8, 30, tzinfo=UTC)
        )
    assert payload["version_label"] == __version__
    assert payload["active_work"] == "hello"
    assert payload["phase"] == "Generated status"
    assert payload["metadata"]["Last Updated"] == "08-30-26"
    assert payload["metadata"]["Previous Version"] is None
    gen = payload["generated"]
    assert [p["identifier"] for p in gen["in_flight_projects"]] == ["PRJ-900"]
    # No previous version: every Resolved item counts as "since".
    assert [p["identifier"] for p in gen["resolved_since_previous"]] == ["PI-902"]
    assert gen["open_planning_items"]["counts"]["In Progress"] == 1
    assert gen["open_planning_items"]["counts"]["Draft"] == 1
    # Draft is counted, not listed.
    assert [p["identifier"] for p in gen["open_planning_items"]["items"]] == ["PI-900"]


def test_generate_writes_version_and_uses_previous_as_cutoff(v2_env):
    with session_scope() as s:
        _pi(s, "PI-910", "Resolved")
        first = status.generate(s, narrative=None)
    assert first["version"] == 1
    assert first["is_current"] is True
    assert first["payload"]["phase"] == "No project in flight"
    assert first["payload"]["generated"]["resolved_since_previous"][0]["identifier"] == "PI-910"

    with session_scope() as s:
        _pi(s, "PI-911", "Resolved")
        second = status.generate(s, narrative="second")
    assert second["version"] == 2
    gen = second["payload"]["generated"]
    assert second["payload"]["metadata"]["Previous Version"] == 1
    # Only the item resolved after version 1 was created.
    assert [p["identifier"] for p in gen["resolved_since_previous"]] == ["PI-911"]
    with session_scope() as s:
        assert status.get_current(s)["version"] == 2
        assert [v["version"] for v in status.list_versions(s)] == [2, 1]

"""Release-run repository tests — PI-326 (PRJ-065), REQ-262 / DEC-742.

The born-terminal run-outcome satellite: record round-trips, multiple runs per
release, outcome CHECK, findings edges, append-only (no update/delete verb), and
``list_for_release`` ordering. See preserve-failed-run-history-design.md §3.3.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import NotFoundError, UnprocessableError
from crmbuilder_v2.access.repositories import (
    findings,
    references,
    release_runs,
    releases,
)


def _release(s, title="R"):
    return releases.create_release(s, title=title, description="d")[
        "release_identifier"
    ]


def _scope():
    return {"projects": ["PRJ-037"], "planning_items": ["PI-229", "PI-230"]}


def _phases():
    return [
        {"workstream": "WSK-144", "phase_type": "Design", "terminal_status": "Complete"},
        {"workstream": "WSK-145", "phase_type": "Develop", "terminal_status": "Ready"},
    ]


def test_record_round_trips_all_fields(v2_env):
    with session_scope() as s:
        rel = _release(s)
        run = release_runs.record(
            s,
            release_identifier=rel,
            outcome="abandoned",
            scope=_scope(),
            phases_run=_phases(),
            halt_point="development",
            cause="malformed duplicate-phase decomposition",
            cause_code="malformed_decomposition",
        )
        assert run["release_run_identifier"].startswith("RUN-")
        assert run["release_identifier"] == rel
        assert run["release_run_outcome"] == "abandoned"
        assert run["release_run_scope"] == _scope()
        assert run["release_run_phases_run"] == _phases()
        assert run["release_run_halt_point"] == "development"
        assert run["release_run_cause_code"] == "malformed_decomposition"

        fetched = release_runs.get(s, run["release_run_identifier"])
        assert fetched["release_run_identifier"] == run["release_run_identifier"]
        assert fetched["release_run_scope"] == run["release_run_scope"]
        assert fetched["release_run_phases_run"] == run["release_run_phases_run"]
        assert fetched["release_run_outcome"] == run["release_run_outcome"]
        assert fetched["release_run_cause"] == run["release_run_cause"]
        # Born-terminal — no mutation timestamps on the persisted record.
        assert "release_run_updated_at" not in run
        assert "release_run_deleted_at" not in run


def test_shipped_run_has_no_halt_or_cause(v2_env):
    with session_scope() as s:
        rel = _release(s)
        run = release_runs.record(
            s,
            release_identifier=rel,
            outcome="shipped",
            scope=_scope(),
            phases_run=_phases(),
        )
        assert run["release_run_outcome"] == "shipped"
        assert run["release_run_halt_point"] is None
        assert run["release_run_cause"] is None
        assert run["release_run_cause_code"] is None


def test_multiple_runs_per_one_release(v2_env):
    # A release can run the lane more than once — NOT 1:1.
    with session_scope() as s:
        rel = _release(s)
        first = release_runs.record(
            s, release_identifier=rel, outcome="abandoned",
            scope=_scope(), phases_run=_phases(), halt_point="development",
        )
        second = release_runs.record(
            s, release_identifier=rel, outcome="shipped",
            scope=_scope(), phases_run=_phases(),
        )
        assert first["release_run_identifier"] != second["release_run_identifier"]
        runs = release_runs.list_for_release(s, rel)
        assert len(runs) == 2
        assert {r["release_run_outcome"] for r in runs} == {"abandoned", "shipped"}


def test_list_for_release_orders_newest_first(v2_env):
    from datetime import UTC, datetime

    with session_scope() as s:
        rel = _release(s)
        older = release_runs.record(
            s, release_identifier=rel, outcome="abandoned",
            scope=_scope(), phases_run=_phases(), halt_point="development",
            created_at=datetime(2026, 6, 1, tzinfo=UTC),
        )
        newer = release_runs.record(
            s, release_identifier=rel, outcome="shipped",
            scope=_scope(), phases_run=_phases(),
            created_at=datetime(2026, 6, 20, tzinfo=UTC),
        )
        runs = release_runs.list_for_release(s, rel)
        assert [r["release_run_identifier"] for r in runs] == [
            newer["release_run_identifier"],
            older["release_run_identifier"],
        ]


def test_outcome_check_rejects_bad_value(v2_env):
    with session_scope() as s:
        rel = _release(s)
        with pytest.raises(UnprocessableError):
            release_runs.record(
                s, release_identifier=rel, outcome="exploded",
                scope=_scope(), phases_run=_phases(),
            )


def test_invalid_json_shapes_rejected(v2_env):
    with session_scope() as s:
        rel = _release(s)
        with pytest.raises(UnprocessableError):
            release_runs.record(
                s, release_identifier=rel, outcome="shipped",
                scope=["not", "an", "object"], phases_run=_phases(),
            )
        with pytest.raises(UnprocessableError):
            release_runs.record(
                s, release_identifier=rel, outcome="shipped",
                scope=_scope(), phases_run={"not": "a list"},
            )


def test_unknown_release_raises(v2_env):
    with session_scope() as s:
        with pytest.raises(NotFoundError):
            release_runs.record(
                s, release_identifier="REL-999", outcome="abandoned",
                scope=_scope(), phases_run=_phases(),
            )
        with pytest.raises(NotFoundError):
            release_runs.list_for_release(s, "REL-999")


def test_findings_edges_created_and_queryable(v2_env):
    with session_scope() as s:
        rel = _release(s)
        f1 = findings.create_finding(
            s, type="conflict", severity="blocking", summary="dup phase",
        )["finding_identifier"]
        f2 = findings.create_finding(
            s, type="gap", severity="advisory", summary="missing design",
        )["finding_identifier"]
        run = release_runs.record(
            s, release_identifier=rel, outcome="abandoned",
            scope=_scope(), phases_run=_phases(), halt_point="development",
            finding_identifiers=[f1, f2, f1],  # dup is de-duplicated
        )
        run_id = run["release_run_identifier"]
        edges = references.list_references(
            s, source_id=run_id,
            relationship_kind="release_run_relates_to_finding",
        )
        assert {e["target_id"] for e in edges} == {f1, f2}
        assert all(e["target_type"] == "finding" for e in edges)


def test_repository_has_no_update_or_delete_verb(v2_env):
    # Append-only by construction: the module exposes only record + reads.
    assert not hasattr(release_runs, "update")
    assert not hasattr(release_runs, "delete")
    assert not hasattr(release_runs, "patch")


def test_explicit_identifier_and_collision(v2_env):
    from crmbuilder_v2.access.exceptions import ConflictError

    with session_scope() as s:
        rel = _release(s)
        run = release_runs.record(
            s, release_identifier=rel, outcome="shipped",
            scope=_scope(), phases_run=_phases(), identifier="RUN-050",
        )
        assert run["release_run_identifier"] == "RUN-050"
        with pytest.raises(ConflictError):
            release_runs.record(
                s, release_identifier=rel, outcome="shipped",
                scope=_scope(), phases_run=_phases(), identifier="RUN-050",
            )

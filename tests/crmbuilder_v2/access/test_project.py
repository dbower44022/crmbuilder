"""Project repository tests — UI v0.7 Slice A.

Covers ``workstream.md`` section 3.7: schema shape, identifier format,
case-insensitive name uniqueness, status enum + transition validation,
truly-terminal terminals, supersession-requires-edge, server-set lifecycle
timestamps, the eight repository methods, identifier auto-assignment, and
the soft-delete / restore round-trip.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import projects as ws
from sqlalchemy import inspect

_EXPECTED_COLUMNS = {
    "project_identifier",
    "project_name",
    "project_status",
    "project_purpose",
    "project_description",
    "project_notes",
    "project_created_at",
    "project_updated_at",
    "project_deleted_at",
    "project_started_at",
    "project_completed_at",
    "project_cancelled_at",
    "project_superseded_at",
    "engagement_id",
}


def _make(s, name="Project A"):
    return ws.create_project(s, name=name, purpose="p", description="d")


def _supersedes(src, dst):
    return [
        {
            "source_type": "project",
            "source_id": src,
            "target_type": "project",
            "target_id": dst,
            "relationship": "supersedes",
        }
    ]


def test_table_shape(v2_env):
    inspector = inspect(get_engine())
    assert "projects" in inspector.get_table_names()
    cols = {c["name"] for c in inspector.get_columns("projects")}
    assert cols == _EXPECTED_COLUMNS
    pk = inspector.get_pk_constraint("projects")
    assert pk["constrained_columns"] == ["project_identifier"]


def test_identifier_autoassign_and_format(v2_env):
    with session_scope() as s:
        r = _make(s)
        assert r["project_identifier"] == "PRJ-001"
        assert r["project_status"] == "planned"
    with session_scope() as s, pytest.raises(UnprocessableError):
        ws.create_project(
            s, name="Bad", purpose="p", description="d", identifier="WS-1"
        )
    with session_scope() as s:
        assert ws.next_project_identifier(s) == "PRJ-002"


def test_explicit_identifier_collision(v2_env):
    with session_scope() as s:
        _make(s, "A")
        with pytest.raises(ConflictError):
            ws.create_project(
                s, name="B", purpose="p", description="d", identifier="PRJ-001"
            )


def test_name_uniqueness_case_insensitive(v2_env):
    with session_scope() as s:
        _make(s, "Governance")
    with session_scope() as s, pytest.raises(UnprocessableError):
        _make(s, "governance")


def test_status_enum_and_transitions(v2_env):
    with session_scope() as s:
        _make(s)
    with session_scope() as s, pytest.raises(UnprocessableError):
        ws.patch_project(s, "PRJ-001", status="bogus")
    with session_scope() as s:
        ws.patch_project(s, "PRJ-001", status="in_flight")
        assert ws.get_project(s, "PRJ-001")["project_started_at"] is not None
    with session_scope() as s, pytest.raises(StatusTransitionError):
        ws.patch_project(s, "PRJ-001", status="planned")  # regression


def test_terminal_states_truly_terminal(v2_env):
    with session_scope() as s:
        _make(s)
        ws.patch_project(s, "PRJ-001", status="in_flight")
        ws.patch_project(s, "PRJ-001", status="complete")
        assert ws.get_project(s, "PRJ-001")["project_completed_at"]
    with session_scope() as s, pytest.raises(StatusTransitionError):
        ws.patch_project(s, "PRJ-001", status="cancelled")


def test_supersession_requires_edge(v2_env):
    with session_scope() as s:
        _make(s, "Source")
        _make(s, "Successor")  # PRJ-002
    # Missing edge -> 422.
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        ws.patch_project(s, "PRJ-001", status="superseded")
    assert exc.value.errors[0].code == "supersession_requires_successor_edge"
    # Edge supplied in the same payload -> ok.
    with session_scope() as s:
        r = ws.patch_project(
            s, "PRJ-001", status="superseded", references=_supersedes("PRJ-001", "PRJ-002")
        )
        assert r["project_status"] == "superseded"
        assert r["project_superseded_at"]


def test_create_with_terminal_status_backfill(v2_env):
    with session_scope() as s:
        r = ws.create_project(
            s,
            name="Backfilled",
            purpose="p",
            description="d",
            status="complete",
            timestamps={
                "project_started_at": "2026-05-20T00:00:00",
                "project_completed_at": "2026-05-22T00:00:00",
            },
        )
        assert r["project_status"] == "complete"
        assert r["project_started_at"].startswith("2026-05-20")
        assert r["project_completed_at"].startswith("2026-05-22")


def test_crud_methods_and_errors(v2_env):
    with session_scope() as s:
        _make(s)
        # PUT full replace
        r = ws.update_project(
            s, "PRJ-001", name="Renamed", purpose="p2", description="d2"
        )
        assert r["project_name"] == "Renamed"
        # PUT identifier mismatch
        with pytest.raises(UnprocessableError):
            ws.update_project(
                s, "PRJ-001", project_identifier="PRJ-999",
                name="x", purpose="p", description="d",
            )
        # patch unknown field
        with pytest.raises(UnprocessableError):
            ws.patch_project(s, "PRJ-001", bogus="x")
    with session_scope() as s, pytest.raises(NotFoundError):
        ws.update_project(s, "PRJ-404", name="x", purpose="p", description="d")


def test_soft_delete_restore_roundtrip(v2_env):
    with session_scope() as s:
        _make(s)
        ws.delete_project(s, "PRJ-001")
        assert ws.get_project(s, "PRJ-001") is None
        assert ws.get_project(s, "PRJ-001", include_deleted=True) is not None
        assert ws.list_projects(s) == []
        assert len(ws.list_projects(s, include_deleted=True)) == 1
        ws.restore_project(s, "PRJ-001")
        assert ws.get_project(s, "PRJ-001") is not None
    with session_scope() as s, pytest.raises(UnprocessableError):
        ws.restore_project(s, "PRJ-001")  # not deleted


def test_list_status_filter(v2_env):
    with session_scope() as s:
        _make(s, "A")
        _make(s, "B")
        ws.patch_project(s, "PRJ-001", status="in_flight")
        assert len(ws.list_projects(s, status="in_flight")) == 1
        assert len(ws.list_projects(s, status="planned")) == 1

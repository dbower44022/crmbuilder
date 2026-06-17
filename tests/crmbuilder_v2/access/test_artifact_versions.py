"""Artifact-version repository tests — PI-208 (PRJ-031), the change spine.

Covers pi-208-versioning-spine-architecture.md §7: per-artifact monotonic
numbering, the live = latest-shipped rule (in-flight versions are frozen drafts),
the artifact_type CHECK, release provenance, and the table shape.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import UnprocessableError
from crmbuilder_v2.access.repositories import artifact_versions as av
from crmbuilder_v2.access.repositories import releases
from sqlalchemy import inspect


def _release(s, title="R", status="preliminary_planning"):
    return releases.create_release(
        s, title=title, description="d", status=status
    )["release_identifier"]


def _ship(s, rel):
    """Drive a release straight to shipped via direct status writes (bypassing
    the gates, which are exercised in test_release; here we only need the
    terminal state for the live rule)."""
    from crmbuilder_v2.access._helpers import get_by_identifier
    from crmbuilder_v2.access.models import Release

    row = get_by_identifier(s, Release, Release.release_identifier, rel)
    row.release_status = "shipped"
    s.flush()


def test_table_shape(v2_env):
    inspector = inspect(get_engine())
    assert "artifact_versions" in inspector.get_table_names()
    cols = {c["name"] for c in inspector.get_columns("artifact_versions")}
    assert cols == {
        "id",
        "engagement_id",
        "artifact_type",
        "artifact_identifier",
        "version_number",
        "release_identifier",
        "snapshot",
        "created_at",
    }


def test_monotonic_numbering_per_artifact(v2_env):
    with session_scope() as s:
        rel = _release(s)
        v1 = av.snapshot(
            s, artifact_type="entity", artifact_identifier="ENT-001",
            release_identifier=rel, snapshot={"fields": []},
        )
        v2 = av.snapshot(
            s, artifact_type="entity", artifact_identifier="ENT-001",
            release_identifier=rel, snapshot={"fields": ["a"]},
        )
        # A different artifact numbers independently from 1.
        other = av.snapshot(
            s, artifact_type="entity", artifact_identifier="ENT-002",
            release_identifier=rel, snapshot={},
        )
        assert v1["version_number"] == 1
        assert v2["version_number"] == 2
        assert other["version_number"] == 1


def test_artifact_type_check_rejects_requirement(v2_env):
    with session_scope() as s:
        rel = _release(s)
        with pytest.raises(UnprocessableError):
            av.snapshot(
                s, artifact_type="requirement", artifact_identifier="REQ-001",
                release_identifier=rel, snapshot={},
            )


def test_live_is_none_until_release_ships(v2_env):
    with session_scope() as s:
        rel = _release(s)
        av.snapshot(
            s, artifact_type="field", artifact_identifier="FLD-001",
            release_identifier=rel, snapshot={"type": "varchar"},
        )
        # In-flight release → the version is a frozen draft, not live.
        assert av.live(
            s, artifact_type="field", artifact_identifier="FLD-001"
        ) is None
        _ship(s, rel)
        out = av.live(s, artifact_type="field", artifact_identifier="FLD-001")
        assert out is not None
        assert out["version_number"] == 1


def test_live_is_latest_shipped(v2_env):
    with session_scope() as s:
        r1 = _release(s, title="R1")
        av.snapshot(
            s, artifact_type="entity", artifact_identifier="ENT-009",
            release_identifier=r1, snapshot={"v": 1},
        )
        _ship(s, r1)
        # A second, in-flight release adds v2 — a frozen draft.
        r2 = _release(s, title="R2")
        av.snapshot(
            s, artifact_type="entity", artifact_identifier="ENT-009",
            release_identifier=r2, snapshot={"v": 2},
        )
        live = av.live(s, artifact_type="entity", artifact_identifier="ENT-009")
        assert live["version_number"] == 1  # v2's release hasn't shipped
        _ship(s, r2)
        live = av.live(s, artifact_type="entity", artifact_identifier="ENT-009")
        assert live["version_number"] == 2


def test_versions_for_release_provenance(v2_env):
    with session_scope() as s:
        rel = _release(s)
        av.snapshot(
            s, artifact_type="entity", artifact_identifier="ENT-A",
            release_identifier=rel, snapshot={},
        )
        av.snapshot(
            s, artifact_type="process", artifact_identifier="PROC-A",
            release_identifier=rel, snapshot={},
        )
        rows = av.versions_for_release(s, rel)
        assert len(rows) == 2
        assert {r["artifact_type"] for r in rows} == {"entity", "process"}


def test_list_versions_ascending(v2_env):
    with session_scope() as s:
        rel = _release(s)
        for _ in range(3):
            av.snapshot(
                s, artifact_type="persona", artifact_identifier="PER-1",
                release_identifier=rel, snapshot={},
            )
        rows = av.list_versions(
            s, artifact_type="persona", artifact_identifier="PER-1"
        )
        assert [r["version_number"] for r in rows] == [1, 2, 3]

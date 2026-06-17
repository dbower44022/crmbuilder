"""Planning-orchestration substrate tests — PI-209 (PRJ-033), Option A.

Covers pi-209-planning-org-architecture.md §6: author_designs (stage gate, vN+1
snapshot, idempotent re-run) and planning_readiness (frozen / designs /
decomposition / sequencing).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from crmbuilder_v2.access import planning
from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError
from crmbuilder_v2.access.models import Release
from crmbuilder_v2.access.repositories import (
    artifact_versions,
    planning_items,
    projects,
    references,
    releases,
    workstreams,
)


def _link(s, st, sid, tt, tid, rel):
    references.create(
        s, source_type=st, source_id=sid, target_type=tt, target_id=tid,
        relationship=rel,
    )


def _release(s, *, status="architecture_planning", frozen=True, title="R"):
    """A release with membership added while open, then promoted to ``status``."""
    return releases.create_release(s, title=title, description="d")[
        "release_identifier"
    ]


def _promote(s, rel, *, status="architecture_planning", frozen=True):
    row = get_by_identifier(s, Release, Release.release_identifier, rel)
    if frozen:
        row.release_frozen_at = datetime.now(UTC)
    row.release_status = status
    s.flush()


def _scope(s, rel, *, decomposed=True):
    """Attach a project + PI (optionally with a workstream) to the release."""
    prj = projects.create_project(s, name="P", purpose="p", description="d")[
        "project_identifier"
    ]
    _link(s, "project", prj, "release", rel, "project_belongs_to_release")
    pi = planning_items.create(
        s, title="PI", item_type="pending_work",
        executive_summary="x" * 250, area=["storage"],
    )["identifier"]
    _link(s, "planning_item", pi, "project", prj, "planning_item_belongs_to_project")
    if decomposed:
        ws = workstreams.create_workstream(s, phase_type="Develop", title="WS")[
            "workstream_identifier"
        ]
        _link(s, "workstream", ws, "planning_item", pi,
              "workstream_belongs_to_planning_item")
    return prj, pi


_DELTA_SETS = [
    {"artifact_type": "entity", "artifact_identifier": "ENT-1",
     "merged": {"fields": {"email": {"required": True}}, "attributes": {}}},
    {"artifact_type": "persona", "artifact_identifier": "PER-1",
     "merged": {"fields": {}, "attributes": {"label": "Mentor"}}},
]


def test_author_designs_requires_architecture_planning(v2_env):
    with session_scope() as s:
        rel = _release(s)
        _promote(s, rel, status="reconciliation")
        with pytest.raises(ConflictError, match="architecture_planning"):
            planning.author_designs(s, rel, _DELTA_SETS)


def test_author_designs_snapshots_vN1(v2_env):
    with session_scope() as s:
        rel = _release(s)
        _promote(s, rel)
        authored = planning.author_designs(s, rel, _DELTA_SETS)
        assert len(authored) == 2
        assert all(v["version_number"] == 1 for v in authored)
        # tied to the release, readable as live once shipped — here just provenance
        rows = artifact_versions.versions_for_release(s, rel)
        assert {(r["artifact_type"], r["artifact_identifier"]) for r in rows} == {
            ("entity", "ENT-1"), ("persona", "PER-1")
        }


def test_author_designs_idempotent(v2_env):
    with session_scope() as s:
        rel = _release(s)
        _promote(s, rel)
        planning.author_designs(s, rel, _DELTA_SETS)
        again = planning.author_designs(s, rel, _DELTA_SETS)
        assert again == []  # already versioned for this release
        assert len(artifact_versions.versions_for_release(s, rel)) == 2


def test_readiness_reports_missing(v2_env):
    with session_scope() as s:
        # undecomposed PI + not frozen (release left open, scope added while open)
        rel = _release(s)
        _scope(s, rel, decomposed=False)
        r = planning.planning_readiness(s, rel)
        assert r["ready"] is False
        assert r["frozen"] is False
        assert r["undecomposed_planning_items"]  # the PI lacks workstreams
        assert any("not frozen" in m for m in r["missing"])


def test_readiness_ready_when_complete(v2_env):
    with session_scope() as s:
        rel = _release(s)
        _scope(s, rel, decomposed=True)  # while open
        _promote(s, rel)  # frozen, architecture_planning
        r = planning.planning_readiness(s, rel)
        assert r["ready"] is True
        assert r["undecomposed_planning_items"] == []
        assert r["sequencing_ok"] is True


def test_plan_release_authors_then_reports(v2_env):
    with session_scope() as s:
        rel = _release(s)
        _scope(s, rel, decomposed=True)  # while open
        _promote(s, rel)
        out = planning.plan_release(s, rel, _DELTA_SETS)
        assert len(out["authored_designs"]) == 2
        assert out["readiness"]["ready"] is True
        assert out["readiness"]["designs_authored"] == 2

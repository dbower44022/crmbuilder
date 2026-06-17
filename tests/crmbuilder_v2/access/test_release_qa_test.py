"""Release-level QA/test gate tests — PI-206 (PRJ-031), §8.

Covers pi-206-qa-test-levels-architecture.md §4: the qa_pass/test_pass actions,
the qa→testing and testing→deployment gates, and rework-bounce-back invalidation.
Area-level REQ-192/193 are delivered + tested by the ADO Lead substrate
(test_lead.py); not re-tested here.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError
from crmbuilder_v2.access.models import (
    Requirement,
)
from crmbuilder_v2.access.repositories import (
    planning_items,
    projects,
    references,
    releases,
    requirement,
)


def _link(s, st, sid, tt, tid, rel):
    references.create(
        s, source_type=st, source_id=sid, target_type=tt, target_id=tid,
        relationship=rel,
    )


def _confirm(s, req):
    row = get_by_identifier(s, Requirement, Requirement.requirement_identifier, req)
    row.requirement_status = "confirmed"
    s.flush()


def _in_development(s, title="R"):
    """Build a scoped release and drive it (through the real gates) to development."""
    rel = releases.create_release(s, title=title, description="d")["release_identifier"]
    prj = projects.create_project(
        s, name=f"P{title}", purpose="p", description="d"
    )["project_identifier"]
    pi = planning_items.create(
        s, title=f"PI{title}", item_type="pending_work",
        executive_summary="x" * 250, area=["storage"],
    )["identifier"]
    req = requirement.create_requirement(
        s, name=f"REQ{title}", description="d", acceptance_summary="a"
    )["requirement_identifier"]
    _link(s, "project", prj, "release", rel, "project_belongs_to_release")
    _link(s, "planning_item", pi, "project", prj, "planning_item_belongs_to_project")
    _link(s, "planning_item", pi, "requirement", req,
          "planning_item_implements_requirement")
    _confirm(s, req)
    from crmbuilder_v2.access.repositories import workstreams
    ws = workstreams.create_workstream(s, phase_type="Develop", title=f"WS{title}")[
        "workstream_identifier"
    ]
    _link(s, "workstream", ws, "planning_item", pi,
          "workstream_belongs_to_planning_item")
    releases.transition(s, rel, "development_planning")
    releases.transition(s, rel, "reconciliation")
    releases.transition(s, rel, "architecture_planning")
    releases.transition(s, rel, "ready")
    releases.transition(s, rel, "development")
    releases.transition(s, rel, "qa")
    return rel


def test_qa_pass_requires_qa_status(v2_env):
    with session_scope() as s:
        rel = releases.create_release(s, title="A", description="d")[
            "release_identifier"
        ]
        with pytest.raises(ConflictError, match="not 'qa'"):
            releases.qa_pass(s, rel)


def test_qa_gate_blocks_until_passed(v2_env):
    with session_scope() as s:
        rel = _in_development(s)
        with pytest.raises(ConflictError, match="QA has not passed"):
            releases.transition(s, rel, "testing")
        out = releases.qa_pass(s, rel)
        assert out["release_qa_passed_at"] is not None
        assert releases.transition(s, rel, "testing")["release_status"] == "testing"


def test_test_gate_blocks_until_passed(v2_env):
    with session_scope() as s:
        rel = _in_development(s)
        releases.qa_pass(s, rel)
        releases.transition(s, rel, "testing")
        with pytest.raises(ConflictError, match="testing has not passed"):
            releases.transition(s, rel, "deployment")
        releases.test_pass(s, rel)
        assert (
            releases.transition(s, rel, "deployment")["release_status"]
            == "deployment"
        )


def test_rework_bounceback_clears_passes(v2_env):
    with session_scope() as s:
        rel = _in_development(s)
        releases.qa_pass(s, rel)
        releases.transition(s, rel, "testing")
        # bounce back to development — both passes must be invalidated.
        out = releases.transition(s, rel, "development")
        assert out["release_qa_passed_at"] is None
        assert out["release_test_passed_at"] is None
        # re-entering qa requires a fresh QA pass.
        releases.transition(s, rel, "qa")
        with pytest.raises(ConflictError, match="QA has not passed"):
            releases.transition(s, rel, "testing")

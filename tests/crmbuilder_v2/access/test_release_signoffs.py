"""Release front-half review sign-offs — PI-238 (PRJ-041 / REQ-285).

The human-review gate: reconciliation and architecture-planning each conclude on
a recorded, freshness-checked sign-off, and the release transitions gate on it.
Covers the repository (create/list/append-only, fingerprint freshness) and the
two gate predicates (blocked without a sign-off, blocked when the sign-off is
stale, passes with a fresh one).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from crmbuilder_v2.access import release_orchestration as orch
from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import Release
from crmbuilder_v2.access.repositories import (
    planning_items,
    projects,
    references,
    release_demands,
    release_signoffs,
    releases,
    workstreams,
)

_SUMMARY = (
    "A planning item exercised by the release sign-off gate tests; it carries "
    "enough audience-facing text to satisfy the 200-800 character executive "
    "summary requirement the planning_items repository enforces on create, so the "
    "scaffolding builds a valid in-scope item the planned-completely gate accepts."
)


def _set_status(s, rel, status, *, frozen=False):
    row = get_by_identifier(s, Release, Release.release_identifier, rel)
    row.release_status = status
    if frozen:
        row.release_frozen_at = datetime.now(UTC)
    s.flush()


def _demand(req, aid, facet, value):
    return {
        "requirement_identifier": req, "artifact_type": "entity",
        "artifact_identifier": aid, "field": "email", "facet": facet,
        "op": "set", "value": value,
    }


# --- repository: create / list / append-only -------------------------------


def test_create_and_list_signoff(v2_env):
    with session_scope() as s:
        rel = releases.create_release(s, title="R", description="d")[
            "release_identifier"
        ]
        row = release_signoffs.create_signoff(
            s, rel, stage="reconciliation", reviewer="ann",
            attestation="looks right", decision_identifier="DEC-9",
        )
        assert row["signoff_stage"] == "reconciliation"
        assert row["signoff_reviewer"] == "ann"
        assert row["signoff_fingerprint"]  # captured
        assert row["signoff_decision_identifier"] == "DEC-9"
        listed = release_signoffs.list_signoffs(s, rel)
        assert len(listed) == 1
        assert release_signoffs.list_signoffs(s, rel, stage="architecture_planning") == []


def test_invalid_stage_rejected(v2_env):
    with session_scope() as s:
        rel = releases.create_release(s, title="R", description="d")[
            "release_identifier"
        ]
        with pytest.raises(UnprocessableError):
            release_signoffs.create_signoff(
                s, rel, stage="bogus", reviewer="a", attestation="x")


def test_unknown_release_rejected(v2_env):
    with session_scope() as s:
        with pytest.raises(NotFoundError):
            release_signoffs.create_signoff(
                s, "REL-999", stage="reconciliation", reviewer="a", attestation="x")


# --- freshness: a sign-off goes stale when its reviewed output changes ------


def test_signoff_fresh_then_stale_after_change_set_changes(v2_env):
    with session_scope() as s:
        rel = releases.create_release(s, title="R", description="d")[
            "release_identifier"
        ]
        _set_status(s, rel, "reconciliation")
        release_demands.add_demands(
            s, rel, [_demand("REQ-1", "ENT-1", "required", True)],
            authored_by="AGP-recon")
        orch.run_reconciliation(s, rel)  # persists the change-set
        release_signoffs.create_signoff(
            s, rel, stage="reconciliation", reviewer="a", attestation="ok")
        # fresh right after signing
        assert release_signoffs.fresh_signoff(s, rel, "reconciliation") is not None
        assert release_signoffs.signoff_status(
            s, rel, "reconciliation")["is_signed_fresh"] is True
        # the change-set changes → the prior sign-off is now stale
        release_demands.add_demands(
            s, rel, [_demand("REQ-2", "ENT-1", "maxLength", 255)],
            authored_by="AGP-recon")
        orch.run_reconciliation(s, rel)
        assert release_signoffs.fresh_signoff(s, rel, "reconciliation") is None
        assert release_signoffs.signoff_status(
            s, rel, "reconciliation")["is_signed_fresh"] is False


# --- gate: reconciliation → architecture_planning ---------------------------


def test_reconciliation_gate_requires_fresh_signoff(v2_env):
    with session_scope() as s:
        rel = releases.create_release(s, title="R", description="d")[
            "release_identifier"
        ]
        _set_status(s, rel, "reconciliation")
        release_demands.add_demands(
            s, rel, [_demand("REQ-1", "ENT-1", "required", True)],
            authored_by="AGP-recon")
        orch.run_reconciliation(s, rel)  # no conflicts, change-set persisted
        # blocked without a sign-off ...
        with pytest.raises(ConflictError, match="human review sign-off"):
            releases.transition(s, rel, "architecture_planning")
        # ... allowed with one
        release_signoffs.create_signoff(
            s, rel, stage="reconciliation", reviewer="a", attestation="ok")
        assert releases.transition(s, rel, "architecture_planning")[
            "release_status"] == "architecture_planning"


def test_reconciliation_gate_blocks_stale_signoff(v2_env):
    with session_scope() as s:
        rel = releases.create_release(s, title="R", description="d")[
            "release_identifier"
        ]
        _set_status(s, rel, "reconciliation")
        release_demands.add_demands(
            s, rel, [_demand("REQ-1", "ENT-1", "required", True)],
            authored_by="AGP-recon")
        orch.run_reconciliation(s, rel)
        release_signoffs.create_signoff(
            s, rel, stage="reconciliation", reviewer="a", attestation="ok")
        # change the reviewed change-set → the sign-off no longer counts
        release_demands.add_demands(
            s, rel, [_demand("REQ-2", "ENT-1", "maxLength", 255)],
            authored_by="AGP-recon")
        orch.run_reconciliation(s, rel)
        with pytest.raises(ConflictError, match="human review sign-off"):
            releases.transition(s, rel, "architecture_planning")


# --- gate: architecture_planning → ready ------------------------------------


def _scaffold_architecture_planning(s):
    """A frozen, planned-completely release sitting in architecture_planning."""
    prj = projects.create_project(s, name="P", purpose="p", description="d")[
        "project_identifier"
    ]
    pi = planning_items.create(
        s, title="T", item_type="pending_work", executive_summary=_SUMMARY,
        execution_mode="interactive")["identifier"]
    rel = releases.create_release(s, title="R", description="d")[
        "release_identifier"
    ]
    references.create(s, source_type="project", source_id=prj,
                      target_type="release", target_id=rel,
                      relationship="project_belongs_to_release")
    references.create(s, source_type="planning_item", source_id=pi,
                      target_type="project", target_id=prj,
                      relationship="planning_item_belongs_to_project")
    ws = workstreams.create_workstream(
        s, phase_type="Develop", title="Build")["workstream_identifier"]
    references.create(s, source_type="workstream", source_id=ws,
                      target_type="planning_item", target_id=pi,
                      relationship="workstream_belongs_to_planning_item")
    _set_status(s, rel, "architecture_planning", frozen=True)
    return rel, pi


def test_architecture_planning_gate_requires_signoff(v2_env):
    with session_scope() as s:
        rel, pi = _scaffold_architecture_planning(s)
        # planned-completely passes, but no design review sign-off yet → blocked
        with pytest.raises(ConflictError, match="human review sign-off"):
            releases.transition(s, rel, "ready")
        release_signoffs.create_signoff(
            s, rel, stage="architecture_planning", reviewer="a", attestation="ok")
        assert releases.transition(s, rel, "ready")["release_status"] == "ready"

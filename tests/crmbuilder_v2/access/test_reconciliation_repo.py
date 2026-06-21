"""Reconciliation orchestration tests — PI-215 (PRJ-031), §5.4/§16.5.

Covers reconcile_release (status gate, base-from-live, conflict persistence,
re-run upsert), the RC-1 reconciliation gate on the release transition, and
governed conflict resolution. Release statuses set via ORM to isolate from the
upstream transition gates.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError
from crmbuilder_v2.access.models import Release
from crmbuilder_v2.access.repositories import (
    artifact_versions,
    release_signoffs,
    releases,
)
from crmbuilder_v2.access.repositories import reconciliation as recon


def _release(s, status="reconciliation", title="R"):
    rel = releases.create_release(s, title=title, description="d")[
        "release_identifier"
    ]
    if status != "preliminary_planning":
        row = get_by_identifier(s, Release, Release.release_identifier, rel)
        row.release_status = status
        s.flush()
    return rel


def _demand(req, atype, aid, field, facet, op, value=None):
    return {
        "requirement_identifier": req, "artifact_type": atype,
        "artifact_identifier": aid, "field": field, "facet": facet,
        "op": op, "value": value,
    }


def test_reconcile_requires_reconciliation_status(v2_env):
    with session_scope() as s:
        rel = _release(s, status="development_planning")
        with pytest.raises(ConflictError, match="not 'reconciliation'"):
            recon.reconcile_release(s, rel, [])


def test_conflict_persists_and_gates_transition(v2_env):
    with session_scope() as s:
        rel = _release(s)
        demands = [
            _demand("REQ-1", "entity", "ENT-1", "email", "required", "set", True),
            _demand("REQ-2", "entity", "ENT-1", "email", "required", "set", False),
        ]
        out = recon.reconcile_release(s, rel, demands)
        assert out["has_open_conflicts"] is True
        open_conflicts = recon.list_conflicts(s, rel, status="open")
        assert len(open_conflicts) == 1
        # RC-1: cannot leave reconciliation with an open conflict.
        with pytest.raises(ConflictError, match="open model conflict"):
            releases.transition(s, rel, "architecture_planning")
        # resolve via a governed decision, then the gate opens.
        recon.resolve_conflict(
            s, open_conflicts[0]["id"], decision_identifier="DEC-001",
            resolved_value={"required": True},
        )
        assert recon.has_open_conflicts(s, rel) is False
        # PI-238: the gate also needs a human review sign-off of the change-set.
        release_signoffs.create_signoff(
            s, rel, stage="reconciliation", reviewer="t", attestation="ok")
        out2 = releases.transition(s, rel, "architecture_planning")
        assert out2["release_status"] == "architecture_planning"


def test_clean_reconcile_allows_transition(v2_env):
    with session_scope() as s:
        rel = _release(s)
        demands = [
            _demand("REQ-1", "entity", "ENT-2", "email", "required", "set", True),
            _demand("REQ-2", "entity", "ENT-2", "email", "maxLength", "set", 255),
        ]
        out = recon.reconcile_release(s, rel, demands)
        assert out["has_open_conflicts"] is False
        # PI-238: the gate also needs a human review sign-off of the change-set.
        release_signoffs.create_signoff(
            s, rel, stage="reconciliation", reviewer="t", attestation="ok")
        assert (
            releases.transition(s, rel, "architecture_planning")["release_status"]
            == "architecture_planning"
        )


def test_base_comes_from_live_shipped_version(v2_env):
    with session_scope() as s:
        # a shipped release introduces ENT-9 v1 with email.required=False.
        shipped = _release(s, status="preliminary_planning", title="Shipped")
        artifact_versions.snapshot(
            s, artifact_type="entity", artifact_identifier="ENT-9",
            release_identifier=shipped,
            snapshot={"fields": {"email": {"required": False}}, "attributes": {}},
        )
        row = get_by_identifier(s, Release, Release.release_identifier, shipped)
        row.release_status = "shipped"
        s.flush()
        # an in-reconciliation release adds maxLength; base must carry required.
        rel = _release(s, title="Active")
        out = recon.reconcile_release(
            s, rel,
            [_demand("REQ-1", "entity", "ENT-9", "email", "maxLength", "set", 255)],
        )
        merged = out["delta_sets"][0]["merged"]["fields"]["email"]
        assert merged == {"required": False, "maxLength": 255}


def test_resolution_sticks_on_rerun(v2_env):
    with session_scope() as s:
        rel = _release(s)
        demands = [
            _demand("REQ-1", "entity", "ENT-3", "email", "required", "set", True),
            _demand("REQ-2", "entity", "ENT-3", "email", "required", "set", False),
        ]
        recon.reconcile_release(s, rel, demands)
        cid = recon.list_conflicts(s, rel, status="open")[0]["id"]
        recon.resolve_conflict(s, cid, decision_identifier="DEC-002")
        # re-run with the same demands — the resolution must not re-open.
        recon.reconcile_release(s, rel, demands)
        assert recon.has_open_conflicts(s, rel) is False
        assert len(recon.list_conflicts(s, rel, status="resolved")) == 1


def test_resolved_value_folded_into_delta_set(v2_env):
    """RC-5 seam fix: a resolved conflict's value is folded back into the
    reconciled delta-set, so the authored design is complete."""
    with session_scope() as s:
        rel = _release(s)
        demands = [
            _demand("REQ-1", "entity", "ENT-7", "email", "required", "set", True),
            _demand("REQ-2", "entity", "ENT-7", "email", "required", "set", False),
            _demand("REQ-2", "entity", "ENT-7", "email", "maxLength", "set", 255),
        ]
        out = recon.reconcile_release(s, rel, demands)
        # the contradicted facet is excluded until resolved; the clean one merges.
        assert out["delta_sets"][0]["merged"]["fields"]["email"] == {"maxLength": 255}
        cid = recon.list_conflicts(s, rel, status="open")[0]["id"]
        recon.resolve_conflict(
            s, cid, decision_identifier="DEC-1", resolved_value={"value": True}
        )
        # re-reconcile: the resolved value is now folded into the design.
        out2 = recon.reconcile_release(s, rel, demands)
        assert out2["delta_sets"][0]["merged"]["fields"]["email"] == {
            "maxLength": 255, "required": True
        }
        assert out2["has_open_conflicts"] is False

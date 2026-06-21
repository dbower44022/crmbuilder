"""Persisted reconciled change-set tests — PI-237 (PRJ-041 / REQ-285).

The front-half completion artifact: the reconciliation stage's merged result is
persisted (``release_change_sets``) alongside the demand-set and conflicts so a
human can review it. Covers the repository (persist/list/clear, wholesale
refresh, ordering), the orchestration driver (``persist_reconciled_change_set``,
resolution fold), and that ``run_reconciliation`` persists as a side effect.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from crmbuilder_v2.access import release_orchestration as orch
from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.models import Release
from crmbuilder_v2.access.repositories import (
    release_change_sets,
    release_demands,
    releases,
)
from crmbuilder_v2.access.repositories import reconciliation as recon


def _set_status(s, rel, status):
    row = get_by_identifier(s, Release, Release.release_identifier, rel)
    row.release_status = status
    s.flush()


def _demand(req, atype, aid, field, facet, op, value=None):
    return {
        "requirement_identifier": req, "artifact_type": atype,
        "artifact_identifier": aid, "field": field, "facet": facet,
        "op": op, "value": value,
    }


# --- repository: persist / list / clear ------------------------------------


def test_persist_then_list_round_trips_and_orders(v2_env):
    with session_scope() as s:
        rel = releases.create_release(s, title="R", description="d")[
            "release_identifier"
        ]
        # Supply out of dependency order; list must return entity before field.
        delta_sets = [
            {"artifact_type": "field", "artifact_identifier": "FLD-1",
             "merged": {"attributes": {"type": "varchar"}}, "provenance": [{"x": 1}]},
            {"artifact_type": "entity", "artifact_identifier": "ENT-1",
             "merged": {"fields": {"email": {"required": True}}}, "provenance": []},
        ]
        persisted = release_change_sets.persist_change_set(s, rel, delta_sets)
        assert len(persisted) == 2
        got = release_change_sets.list_change_set(s, rel)
        assert [(d["artifact_type"], d["artifact_identifier"]) for d in got] == [
            ("entity", "ENT-1"), ("field", "FLD-1")
        ]
        assert got[0]["merged"] == {"fields": {"email": {"required": True}}}
        assert got[1]["provenance"] == [{"x": 1}]


def test_persist_is_wholesale_refresh(v2_env):
    """Re-persisting replaces the prior snapshot — no stale rows linger."""
    with session_scope() as s:
        rel = releases.create_release(s, title="R", description="d")[
            "release_identifier"
        ]
        release_change_sets.persist_change_set(s, rel, [
            {"artifact_type": "entity", "artifact_identifier": "ENT-1",
             "merged": {}, "provenance": []},
            {"artifact_type": "entity", "artifact_identifier": "ENT-2",
             "merged": {}, "provenance": []},
        ])
        # second run drops ENT-2
        release_change_sets.persist_change_set(s, rel, [
            {"artifact_type": "entity", "artifact_identifier": "ENT-1",
             "merged": {"fields": {"x": {"required": True}}}, "provenance": []},
        ])
        got = release_change_sets.list_change_set(s, rel)
        assert [d["artifact_identifier"] for d in got] == ["ENT-1"]
        assert got[0]["merged"] == {"fields": {"x": {"required": True}}}


def test_clear_change_set(v2_env):
    with session_scope() as s:
        rel = releases.create_release(s, title="R", description="d")[
            "release_identifier"
        ]
        release_change_sets.persist_change_set(s, rel, [
            {"artifact_type": "entity", "artifact_identifier": "ENT-1",
             "merged": {}, "provenance": []},
        ])
        assert release_change_sets.clear_change_set(s, rel) == 1
        assert release_change_sets.list_change_set(s, rel) == []


def test_unknown_release_raises(v2_env):
    with session_scope() as s:
        with pytest.raises(NotFoundError):
            release_change_sets.list_change_set(s, "REL-999")
        with pytest.raises(NotFoundError):
            release_change_sets.persist_change_set(s, "REL-999", [])


# --- orchestration: persist_reconciled_change_set + run_reconciliation ------


def test_run_reconciliation_persists_change_set(v2_env):
    with session_scope() as s:
        rel = releases.create_release(s, title="R", description="d")[
            "release_identifier"
        ]
        _set_status(s, rel, "reconciliation")
        release_demands.add_demands(s, rel, [
            _demand("REQ-1", "entity", "ENT-1", "email", "required", "set", True),
            _demand("REQ-2", "entity", "ENT-1", "email", "maxLength", "set", 255),
        ], authored_by="AGP-recon")
        out = orch.run_reconciliation(s, rel)
        # the run returns the persisted change-set ...
        assert out["change_set"][0]["merged"]["fields"]["email"] == {
            "required": True, "maxLength": 255
        }
        # ... and it is durably stored for later review.
        stored = release_change_sets.list_change_set(s, rel)
        assert stored[0]["artifact_identifier"] == "ENT-1"
        assert stored[0]["merged"]["fields"]["email"] == {
            "required": True, "maxLength": 255
        }


def test_persisted_change_set_folds_conflict_resolution(v2_env):
    """After a conflict is resolved and reconciliation re-runs, the persisted
    change-set reflects the resolved value (it tracks the latest reconciliation)."""
    with session_scope() as s:
        rel = releases.create_release(s, title="R", description="d")[
            "release_identifier"
        ]
        _set_status(s, rel, "reconciliation")
        release_demands.add_demands(s, rel, [
            _demand("REQ-1", "entity", "ENT-1", "email", "required", "set", True),
            _demand("REQ-2", "entity", "ENT-1", "email", "required", "set", False),
        ], authored_by="AGP-recon")
        out = orch.run_reconciliation(s, rel)
        assert out["has_open_conflicts"] is True
        cid = recon.list_conflicts(s, rel, status="open")[0]["id"]
        recon.resolve_conflict(
            s, cid, decision_identifier="DEC-1", resolved_value={"value": True}
        )
        # re-run reconciliation → persisted set now folds the resolution
        orch.run_reconciliation(s, rel)
        stored = release_change_sets.list_change_set(s, rel)
        assert stored[0]["merged"]["fields"]["email"] == {"required": True}


def test_persist_reconciled_change_set_matches_delta_sets(v2_env):
    """The standalone driver persists exactly what reconciled_delta_sets computes."""
    with session_scope() as s:
        rel = releases.create_release(s, title="R", description="d")[
            "release_identifier"
        ]
        _set_status(s, rel, "reconciliation")
        release_demands.add_demands(s, rel, [
            _demand("REQ-1", "entity", "ENT-1", "name", "required", "set", True),
        ], authored_by="AGP-recon")
        _set_status(s, rel, "architecture_planning")
        derived = orch.reconciled_delta_sets(s, rel)
        persisted = orch.persist_reconciled_change_set(s, rel)
        assert [(d["artifact_type"], d["artifact_identifier"], d["merged"])
                for d in persisted] == [
            (d["artifact_type"], d["artifact_identifier"], d["merged"])
            for d in derived
        ]

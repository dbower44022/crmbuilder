"""Release demand-set store tests — PI-217 (PRJ-033), AL-1.

The agent-layer's persisted, replayable reconciliation input: add / list / clear /
as_reconcile_input + validation. See release-pipeline-agent-layer-architecture.md §3.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import NotFoundError, UnprocessableError
from crmbuilder_v2.access.repositories import release_demands, releases


def _release(s, title="R"):
    return releases.create_release(s, title=title, description="d")[
        "release_identifier"
    ]


def _demand(req, atype, aid, field, facet, op, value=None):
    return {
        "requirement_identifier": req, "artifact_type": atype,
        "artifact_identifier": aid, "field": field, "facet": facet,
        "op": op, "value": value,
    }


def test_add_and_list_demands(v2_env):
    with session_scope() as s:
        rel = _release(s)
        added = release_demands.add_demands(
            s, rel,
            [
                _demand("REQ-1", "entity", "ENT-1", "email", "required", "set", True),
                _demand("REQ-2", "entity", "ENT-1", "email", "maxLength", "set", 255),
            ],
            authored_by="AGP-recon",
        )
        assert len(added) == 2
        listed = release_demands.list_demands(s, rel)
        assert {d["facet"] for d in listed} == {"required", "maxLength"}
        assert all(d["authored_by"] == "AGP-recon" for d in listed)


def test_as_reconcile_input_shape(v2_env):
    with session_scope() as s:
        rel = _release(s)
        release_demands.add_demands(
            s, rel,
            [_demand("REQ-1", "entity", "ENT-1", "", "label", "set", "Email")],
            authored_by="AGP-recon",
        )
        demand = release_demands.as_reconcile_input(s, rel)[0]
        assert set(demand) == {
            "requirement_identifier", "artifact_type", "artifact_identifier",
            "field", "facet", "op", "value",
        }
        assert demand["field"] == "" and demand["facet"] == "label"


def test_clear_demands_all_and_by_requirement(v2_env):
    with session_scope() as s:
        rel = _release(s)
        release_demands.add_demands(
            s, rel,
            [
                _demand("REQ-1", "entity", "ENT-1", "email", "required", "set", True),
                _demand("REQ-2", "entity", "ENT-1", "name", "required", "set", True),
            ],
            authored_by="AGP-recon",
        )
        assert release_demands.clear_demands(
            s, rel, requirement_identifier="REQ-1"
        ) == 1
        assert {d["requirement_identifier"] for d in
                release_demands.list_demands(s, rel)} == {"REQ-2"}
        assert release_demands.clear_demands(s, rel) == 1
        assert release_demands.list_demands(s, rel) == []


def test_add_demands_validates(v2_env):
    with session_scope() as s:
        rel = _release(s)
        with pytest.raises(UnprocessableError):
            release_demands.add_demands(
                s, rel,
                [_demand("REQ-1", "not_a_type", "X-1", "f", "g", "set", 1)],
                authored_by="AGP-recon",
            )
        with pytest.raises(UnprocessableError):
            release_demands.add_demands(
                s, rel,
                [_demand("REQ-1", "entity", "ENT-1", "f", "g", "bogus_op", 1)],
                authored_by="AGP-recon",
            )


def test_unknown_release_raises(v2_env):
    with session_scope() as s:
        with pytest.raises(NotFoundError):
            release_demands.list_demands(s, "REL-999")

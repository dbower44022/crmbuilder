"""The workflow audit area — PI-413 (REQ-499 / DEC-926).

Detection only: a workflow the design describes records membership on its
automation; one the design does not describe is recorded keyed by its own id
and surfaces in conformance as drift naming it; a described automation the
instance lacks sweeps to absent; an unreadable result is unknown, never
none-present; and a missing Workflow scope (no Advanced Pack) is the positive
observation that the instance carries none.
"""

from __future__ import annotations

from crmbuilder_v2.access import conformance
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import automation as automation_repo
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import (
    instance_membership as membership_repo,
)
from crmbuilder_v2.access.repositories import instances as instances_repo
from crmbuilder_v2.introspect.reconcile import reconcile_workflows


class _WorkflowClient:
    def __init__(self, status=200, records=None):
        self._status = status
        self._records = records or []

    def get_records(self, entity, **kwargs):
        assert entity == "Workflow"
        if self._status != 200:
            return self._status, None
        return 200, {"total": len(self._records), "list": self._records}


def _setup(s, *, describe=True):
    iid = instances_repo.create_instance(
        s, name="chapter", url="https://x.example.org", role="both"
    )["instance_identifier"]
    eid = entity_repo.create_entity(
        s, name="Session", description="x", status="confirmed"
    )["entity_identifier"]
    aid = None
    if describe:
        aid = automation_repo.create_automation(
            s, name="EngagementTotalSessionCount", entity=eid,
            trigger="on_create",
            actions=[{"type": "set_field", "field": "total", "value": 1}],
            status="confirmed",
        )["automation_identifier"]
    return iid, aid


def _membership(s, iid, member_id):
    rows = membership_repo.list_memberships(
        s, instance_identifier=iid, member_type="workflow",
        member_identifier=member_id,
    )
    return rows[0] if rows else None


_LIVE = {
    "id": "6a10878b377565a5f",
    "name": "EngagementTotalSessionCount",
    "entityType": "CSession",
    "type": "afterRecordCreated",
    "isActive": True,
}


def test_a_described_matching_workflow_is_present(v2_env):
    with session_scope() as s:
        iid, aid = _setup(s)
        summary = reconcile_workflows(
            s, instance_identifier=iid, client=_WorkflowClient(records=[_LIVE]),
        )
        assert summary["present"] == 1
        assert summary["undescribed"] == []
        row = _membership(s, iid, aid)
        assert row["state"] == "present"
        assert row["override"] is None


def test_a_trigger_difference_is_drift_with_the_observed_value(v2_env):
    with session_scope() as s:
        iid, aid = _setup(s)
        live = dict(_LIVE, type="scheduled")
        reconcile_workflows(
            s, instance_identifier=iid, client=_WorkflowClient(records=[live]),
        )
        row = _membership(s, iid, aid)
        assert row["state"] == "drifted"
        assert row["override"] == {"automation_trigger": "scheduled"}


def test_an_unmappable_trigger_is_carried_raw_not_approximated(v2_env):
    with session_scope() as s:
        iid, aid = _setup(s)
        live = dict(_LIVE, type="signal")
        reconcile_workflows(
            s, instance_identifier=iid, client=_WorkflowClient(records=[live]),
        )
        row = _membership(s, iid, aid)
        assert row["override"] == {"automation_trigger": "unmapped:signal"}


def test_an_undescribed_workflow_is_recorded_and_reported_as_drift(v2_env):
    """REQ-499's core sentence, end to end through conformance."""
    with session_scope() as s:
        iid, _ = _setup(s, describe=False)
        summary = reconcile_workflows(
            s, instance_identifier=iid, client=_WorkflowClient(records=[_LIVE]),
        )
        assert summary["undescribed"] == ["EngagementTotalSessionCount"]
        row = _membership(s, iid, _LIVE["id"])
        assert row["state"] == "present"
        assert row["override"]["workflow_name"] == "EngagementTotalSessionCount"

        result = conformance.evaluate_instance(s, iid)
        entry = next(
            e for e in result["entries"]
            if e["member_type"] == "workflow" and e["outcome"] == "drift"
        )
        assert "EngagementTotalSessionCount" in entry["reason"]
        assert entry["writable"] is False  # no write path — DEC-926 deferral


def test_a_described_automation_the_instance_lacks_sweeps_absent(v2_env):
    with session_scope() as s:
        iid, aid = _setup(s)
        summary = reconcile_workflows(
            s, instance_identifier=iid, client=_WorkflowClient(records=[]),
        )
        assert summary["absent"] == 0  # no prior row existed to sweep
        # After a first present audit, a disappearance sweeps.
        reconcile_workflows(
            s, instance_identifier=iid, client=_WorkflowClient(records=[_LIVE]),
        )
        summary = reconcile_workflows(
            s, instance_identifier=iid, client=_WorkflowClient(records=[]),
        )
        assert summary["absent"] == 1
        assert _membership(s, iid, aid)["state"] == "absent"


def test_a_missing_workflow_scope_is_none_present(v2_env):
    """404 = no Advanced Pack: a positive observation, not an unknown."""
    with session_scope() as s:
        iid, aid = _setup(s)
        reconcile_workflows(
            s, instance_identifier=iid, client=_WorkflowClient(records=[_LIVE]),
        )
        summary = reconcile_workflows(
            s, instance_identifier=iid, client=_WorkflowClient(status=404),
        )
        assert "reason" not in summary
        assert summary["absent"] == 1


def test_an_unreadable_result_is_unknown_never_none_present(v2_env):
    with session_scope() as s:
        iid, aid = _setup(s)
        reconcile_workflows(
            s, instance_identifier=iid, client=_WorkflowClient(records=[_LIVE]),
        )
        summary = reconcile_workflows(
            s, instance_identifier=iid, client=_WorkflowClient(status=500),
        )
        assert "unknown" in summary["reason"]
        assert summary["absent"] == 0
        assert _membership(s, iid, aid)["state"] == "present"

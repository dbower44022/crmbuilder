"""Reconcile apply engine tests — PI-317 / PI-318 (REL-024)."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access import reconcile_apply
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.access.repositories import instance_membership as mb
from crmbuilder_v2.access.repositories import instances as inst_repo
from crmbuilder_v2.access.repositories import reconcile_transactions as txn_repo


def _setup(s):
    iid = inst_repo.create_instance(
        s, name="src", url="https://src.example.org", role="source"
    )["instance_identifier"]
    eid = entity_repo.create_entity(s, name="Account", description="x")[
        "entity_identifier"
    ]
    fid = field_repo.create_field(
        s, field_belongs_to_entity_identifier=eid, name="code",
        description="x", type="text", required=False,
    )["field_identifier"]
    return iid, fid


def test_capture_writes_design_and_logs_and_clears_override(v2_env):
    with session_scope() as s:
        iid, fid = _setup(s)
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="field", member_identifier=fid,
            state="drifted", override={"field_max_length": 100},
        )
        out = reconcile_apply.capture_field_attribute(
            s, instance=iid, field_identifier=fid,
            attribute="field_max_length", actor="Doug",
        )
        # canonical design now carries the captured value
        assert out["field"]["field_max_length"] == 100
        # transaction recorded
        t = out["transaction"]
        assert t["direction"] == "capture"
        assert t["after_value"] == 100
        assert t["target_ref"] == "design"
        # the instance no longer reads as drift on that attribute
        m = mb.list_memberships(s, instance_identifier=iid, member_type="field",
                                member_identifier=fid)[0]
        assert m["state"] == "present"
        assert m["override"] is None


def test_capture_without_deviation_is_conflict(v2_env):
    with session_scope() as s:
        iid, fid = _setup(s)
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="field", member_identifier=fid,
            state="present",
        )
        with pytest.raises(ConflictError):
            reconcile_apply.capture_field_attribute(
                s, instance=iid, field_identifier=fid,
                attribute="field_max_length", actor="Doug",
            )


def test_rollback_restores_prior_design_value(v2_env):
    with session_scope() as s:
        iid, fid = _setup(s)
        before = field_repo.get_field(s, fid)["field_max_length"]  # None
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="field", member_identifier=fid,
            state="drifted", override={"field_max_length": 100},
        )
        cap = reconcile_apply.capture_field_attribute(
            s, instance=iid, field_identifier=fid,
            attribute="field_max_length", actor="Doug",
        )
        assert field_repo.get_field(s, fid)["field_max_length"] == 100

        res = reconcile_apply.rollback(s, cap["transaction"]["id"], actor="Doug")
        # design restored
        assert field_repo.get_field(s, fid)["field_max_length"] == before
        # original marked rolled_back, compensating recorded
        assert res["rolled_back"]["status"] == "rolled_back"
        assert res["compensating"]["after_value"] == before
        # double rollback rejected
        with pytest.raises(ConflictError):
            reconcile_apply.rollback(s, cap["transaction"]["id"], actor="Doug")


def test_rollback_rejects_non_design_target(v2_env):
    with session_scope() as s:
        iid, fid = _setup(s)
        t = txn_repo.record(
            s, direction="publish", source_ref="design", target_ref=iid,
            member_type="field", member_identifier=fid, attribute="field_type",
            before_value="varchar", after_value="text", actor="Doug",
        )
        with pytest.raises(ConflictError):
            reconcile_apply.rollback(s, t["id"], actor="Doug")

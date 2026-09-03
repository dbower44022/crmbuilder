"""Conformance evaluation and one-deploy overrides — PI-410 (REQ-492/493/494).

Pins the mechanical evaluation: statuses derive from the declared compared
set with no discretion, apply-then-check yields conformant, repeatability is
a property of the store state, unknowns block, unwritable-only differences
get their own status, and an override is spent once without ever touching a
verdict.
"""

from __future__ import annotations

from crmbuilder_v2.access import conformance
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import automation as automation_repo
from crmbuilder_v2.access.repositories import (
    conformance_overrides,
)
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.access.repositories import (
    instance_membership as membership_repo,
)
from crmbuilder_v2.access.repositories import (
    instances as instances_repo,
)
from crmbuilder_v2.access.repositories import teams as team_repo


def _instance(s, name="chapter"):
    return instances_repo.create_instance(
        s, name=name, url=f"https://{name}.example.org", role="both"
    )["instance_identifier"]


def _confirmed_entity(s, name="Contact"):
    return entity_repo.create_entity(
        s, name=name, description="x", status="confirmed",
        track_activity=False,
    )["entity_identifier"]


def _present(s, iid, member_type, member_id, override=None, state="present"):
    membership_repo.upsert_membership(
        s, instance_identifier=iid, member_type=member_type,
        member_identifier=member_id, state=state, override=override,
    )


def test_an_audited_matching_design_is_conformant(v2_env):
    """REQ-492: applying the design and then checking yields conformant."""
    with session_scope() as s:
        iid = _instance(s)
        eid = _confirmed_entity(s)
        _present(s, iid, "entity", eid)
        result = conformance.evaluate_instance(s, iid)
        assert result["status"] == "conformant"
        assert result["counts"]["drift"] == 0
        assert result["counts"]["unknown"] == 0


def test_checking_twice_yields_an_identical_verdict(v2_env):
    """REQ-492's repeatability, as a tested property."""
    with session_scope() as s:
        iid = _instance(s)
        eid = _confirmed_entity(s)
        _present(s, iid, "entity", eid,
                 override={"entity_icon": "different"}, state="drifted")
        first = conformance.evaluate_instance(s, iid)
        second = conformance.evaluate_instance(s, iid)
        assert first == second
        assert first["status"] == "drifted"


def test_a_difference_in_a_compared_attribute_is_drift_with_an_entry(v2_env):
    """REQ-493: one entry per compared attribute with construct, attribute,
    outcome and reason."""
    with session_scope() as s:
        iid = _instance(s)
        eid = _confirmed_entity(s)
        _present(s, iid, "entity", eid,
                 override={"entity_icon": "fas fa-star"}, state="drifted")
        result = conformance.evaluate_instance(s, iid)
        assert result["status"] == "drifted"
        entry = next(
            e for e in result["entries"]
            if e["attribute"] == "entity_icon" and e["outcome"] == "drift"
        )
        assert entry["construct"] == "entity Contact"
        assert entry["reason"]
        assert entry["writable"] is True


def test_a_never_audited_construct_makes_the_instance_uncheckable(v2_env):
    """REQ-491: unknown is never omitted and never conformant."""
    with session_scope() as s:
        iid = _instance(s)
        _confirmed_entity(s)  # design defines it; no membership exists
        result = conformance.evaluate_instance(s, iid)
        assert result["status"] == "unable_to_be_checked"
        assert result["counts"]["unknown"] > 0
        entry = next(e for e in result["entries"] if e["outcome"] == "unknown")
        assert "never audited" in entry["reason"]


def test_a_candidate_design_record_is_not_conformance(v2_env):
    with session_scope() as s:
        iid = _instance(s)
        entity_repo.create_entity(s, name="Draft", description="x")  # candidate
        result = conformance.evaluate_instance(s, iid)
        assert result["entries"] == []
        assert result["status"] == "conformant"


def _confirmed_workflow(s, eid, name="Nightly sweep"):
    """A workflow is the one member type still without a write path
    (DEC-997): the audit reads it, no deploy writes it."""
    return automation_repo.create_automation(
        s, name=name, entity=eid, trigger="on_update",
        actions=[{"type": "set_field", "field": "x", "value": "y"}],
        status="confirmed",
    )["automation_identifier"]


def test_unwritable_only_differences_get_their_own_status(v2_env):
    """DEC-923's narrow refinement: the ONLY differences have no write path."""
    with session_scope() as s:
        iid = _instance(s)
        eid = _confirmed_entity(s)
        _present(s, iid, "entity", eid)
        wid = _confirmed_workflow(s, eid)
        _present(s, iid, "workflow", wid, state="absent")
        result = conformance.evaluate_instance(s, iid)
        assert result["status"] == "named_but_unwritable"
        assert result["counts"]["unwritable_drift"] == 1
        assert result["counts"]["drift"] == 0


def test_a_team_difference_is_writable_drift_now(v2_env):
    """PI-417 / REQ-519: a team the instance lacks used to be named-but-
    unwritable because no deploy could create it. The security program
    (DEC-998) can, so the same absence is drift a publish fixes — and the
    check's exit code moves from 3 to 1 with it."""
    with session_scope() as s:
        iid = _instance(s)
        tid = team_repo.create_team(
            s, name="Mentors", status="confirmed"
        )["team_identifier"]
        _present(s, iid, "team", tid, state="absent")
        result = conformance.evaluate_instance(s, iid)
        assert result["status"] == "drifted"
        assert result["counts"]["drift"] == 1
        assert result["counts"]["unwritable_drift"] == 0


def test_writable_drift_outranks_unwritable_and_unknown(v2_env):
    with session_scope() as s:
        iid = _instance(s)
        eid = _confirmed_entity(s)
        _present(s, iid, "entity", eid,
                 override={"entity_icon": "x"}, state="drifted")
        wid = _confirmed_workflow(s, eid)
        _present(s, iid, "workflow", wid, state="absent")
        result = conformance.evaluate_instance(s, iid)
        assert result["status"] == "drifted"


def test_a_declared_formula_is_unknown_not_falsely_matched(v2_env):
    with session_scope() as s:
        iid = _instance(s)
        eid = _confirmed_entity(s)
        fid = field_repo.create_field(
            s, field_belongs_to_entity_identifier=eid, name="total",
            description="x", type="derived", status="confirmed",
            derived_result_type="number",
            formula={"kind": "arithmetic", "expression": {
                "op": "+", "left": {"field": "a"}, "right": {"field": "b"}}},
        )["field_identifier"]
        _present(s, iid, "entity", eid)
        _present(s, iid, "field", fid)
        result = conformance.evaluate_instance(s, iid)
        entry = next(
            e for e in result["entries"] if e["attribute"] == "field_formula"
        )
        assert entry["outcome"] == "unknown"
        assert "formula scripts" in entry["reason"]


def test_every_entry_states_when_its_reading_was_taken(v2_env):
    """REQ-500: the result states when the reading behind it was taken."""
    with session_scope() as s:
        iid = _instance(s)
        eid = _confirmed_entity(s)
        _present(s, iid, "entity", eid)
        result = conformance.evaluate_instance(s, iid)
        entry = next(e for e in result["entries"] if e["outcome"] == "match")
        assert entry["read_at"]
        assert result["oldest_reading_at"]
        assert result["newest_reading_at"]


# --- one-deploy overrides (REQ-494) ------------------------------------------


def test_an_override_is_recorded_and_spent_exactly_once(v2_env):
    with session_scope() as s:
        iid = _instance(s)
        row = conformance_overrides.create_override(
            s, instance_identifier=iid, authorized_by="Doug",
            reason="known drift accepted for the hotfix deploy",
        )
        assert row["consumed_at"] is None
        spent = conformance_overrides.consume_override(
            s, instance_identifier=iid
        )
        assert spent["id"] == row["id"]
        assert spent["consumed_at"] is not None
        assert conformance_overrides.consume_override(
            s, instance_identifier=iid
        ) is None


def test_an_override_never_changes_the_verdict(v2_env):
    with session_scope() as s:
        iid = _instance(s)
        eid = _confirmed_entity(s)
        _present(s, iid, "entity", eid,
                 override={"entity_icon": "x"}, state="drifted")
        conformance_overrides.create_override(
            s, instance_identifier=iid, authorized_by="Doug", reason="hotfix",
        )
        before = conformance.evaluate_instance(s, iid)
        conformance_overrides.consume_override(s, instance_identifier=iid)
        after = conformance.evaluate_instance(s, iid)
        assert before["status"] == after["status"] == "drifted"


# --- the fleet view (PI-412 / REQ-498) ---------------------------------------


def test_the_fleet_view_rolls_up_every_instance_without_folding_unknowns(
    v2_env,
):
    """One row per instance; an instance whose conformance could not be
    established is its own outcome, never counted with either side."""
    with session_scope() as s:
        eid = _confirmed_entity(s)
        ok_i = _instance(s, "aligned")
        _present(s, ok_i, "entity", eid)
        bad_i = _instance(s, "strayed")
        _present(s, bad_i, "entity", eid,
                 override={"entity_icon": "x"}, state="drifted")
        dark_i = _instance(s, "unreached")  # never audited

        from crmbuilder_v2.access.conformance import fleet_view

        fleet = fleet_view(s)
        by_id = {r["instance"]: r for r in fleet["instances"]}
        assert by_id[ok_i]["status"] == "conformant"
        assert by_id[bad_i]["status"] == "drifted"
        assert by_id[dark_i]["status"] == "unable_to_be_checked"
        assert fleet["summary"]["conformant"] == 1
        assert fleet["summary"]["drifted"] == 1
        assert fleet["summary"]["unable_to_be_checked"] == 1
        # What currently differs is named, not just counted.
        assert any(
            d["attribute"] == "entity_icon" for d in by_id[bad_i]["differing"]
        )
        assert by_id[ok_i]["differing"] == []


def test_the_fleet_row_carries_the_stamp_reading(v2_env):
    from datetime import UTC, datetime

    from crmbuilder_v2.access.conformance import fleet_view
    from crmbuilder_v2.access.repositories import instances as inst_repo2

    with session_scope() as s:
        iid = _instance(s, "stamped")
        inst_repo2.record_stamp_reading(
            s, iid,
            standard_version="REL-045",
            plan_fingerprint="f" * 64,
            read_at=datetime.now(UTC),
        )
        fleet = fleet_view(s)
        row = next(r for r in fleet["instances"] if r["instance"] == iid)
        assert row["standard_version"] == "REL-045"
        assert row["plan_fingerprint"] == "f" * 64
        assert row["stamp_read_at"]

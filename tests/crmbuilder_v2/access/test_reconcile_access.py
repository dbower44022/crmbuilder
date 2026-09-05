"""The access-change gate on a security publish — PI-417 (REQ-519 / REQ-521)."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access import reconcile_access, reconcile_apply, reconcile_compare
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError, NotFoundError
from crmbuilder_v2.access.repositories import instance_membership as mb
from crmbuilder_v2.access.repositories import instances as inst_repo
from crmbuilder_v2.access.repositories import roles as role_repo
from crmbuilder_v2.access.repositories import teams as team_repo


def _instance(s):
    return inst_repo.create_instance(
        s, name="target", url="https://t.example.org", role="target"
    )["instance_identifier"]


def _role(s, scope_access=None, permissions=None):
    return role_repo.create_role(
        s, name="Mentor Role", scope_access=scope_access,
        system_permissions=permissions, status="confirmed",
    )["role_identifier"]


# --- publish scope: a role has no parent entity ------------------------------


def test_a_role_scopes_to_the_security_program_not_an_entity(v2_env):
    with session_scope() as s:
        rid = _role(s)
        scope = reconcile_apply.publish_scope_for_member(s, "role", rid)
    assert scope["filename"] == "security.yaml"
    # the entity fields come back empty rather than filled with a fiction
    assert scope["entity_identifier"] is None
    assert scope["entity_name"] is None


def test_a_team_scopes_to_the_security_program(v2_env):
    with session_scope() as s:
        tid = team_repo.create_team(s, name="Mentor Team", status="confirmed")[
            "team_identifier"
        ]
        scope = reconcile_apply.publish_scope_for_member(s, "team", tid)
    assert scope["filename"] == "security.yaml"


def test_a_filtered_tab_scopes_to_its_entity_s_program(v2_env):
    """A filtered tab is entity-bound (DEC-998 names it as the case that files
    normally), so it publishes with its entity — not the security program."""
    from crmbuilder_v2.access.repositories import entity as entity_repo
    from crmbuilder_v2.access.repositories import filtered_tabs as tab_repo

    with session_scope() as s:
        eid = entity_repo.create_entity(
            s, name="Mentor Application", description="x", status="confirmed",
            track_activity=False,
        )["entity_identifier"]
        fid = tab_repo.create_filtered_tab(
            s, entity_identifier=eid, label="Approved", status="confirmed",
        )["filtered_tab_identifier"]
        scope = reconcile_apply.publish_scope_for_member(s, "filtered_tab", fid)
    assert scope == {
        "entity_identifier": eid,
        "entity_name": "Mentor Application",
        "filename": "Mentor-Application.yaml",
    }


def test_an_unknown_filtered_tab_is_not_found_rather_than_refused(v2_env):
    with session_scope() as s:
        with pytest.raises(NotFoundError):
            reconcile_apply.publish_scope_for_member(s, "filtered_tab", "FTB-999")


# --- the capability table ----------------------------------------------------


def test_role_team_and_filtered_tab_are_all_publishable_now():
    for member, attribute in (
        ("role", "role_scope_access"),
        ("team", "team_description"),
        ("filtered_tab", "filtered_tab_label"),
    ):
        capturable, publishable = reconcile_compare._attribute_capabilities(
            member, attribute
        )
        assert (capturable, publishable) == (True, True), member


def test_only_the_entity_less_members_route_to_the_security_program():
    assert reconcile_compare.SECURITY_PROGRAM_MEMBERS == {"role", "team"}
    assert "filtered_tab" in reconcile_compare.PUBLISHABLE_GLOBAL_MEMBERS


# --- the assessment ----------------------------------------------------------


def test_a_narrowed_scope_level_reads_as_a_removal(v2_env):
    with session_scope() as s:
        iid = _instance(s)
        rid = _role(s, scope_access={"Account": {"read": "team", "create": "yes"}})
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="role", member_identifier=rid,
            state="drifted",
            override={"role_scope_access": {"Account": {"read": "all",
                                                        "create": "yes"}}},
        )
        out = reconcile_access.assess_access_publish(
            s, instance=iid, member_type="role", member_identifier=rid
        )
    assert out["removes_access"] is True
    assert [(c["scope"], c["action"], c["before"], c["after"])
            for c in out["removals"]] == [("Account", "read", "all", "team")]
    # the unchanged action is not reported as a change at all
    assert len(out["changes"]) == 1


def test_a_widened_scope_level_is_a_change_but_not_a_removal(v2_env):
    with session_scope() as s:
        iid = _instance(s)
        rid = _role(s, scope_access={"Account": {"read": "all"}})
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="role", member_identifier=rid,
            state="drifted",
            override={"role_scope_access": {"Account": {"read": "own"}}},
        )
        out = reconcile_access.assess_access_publish(
            s, instance=iid, member_type="role", member_identifier=rid
        )
    assert out["removes_access"] is False
    assert len(out["changes"]) == 1
    assert out["requires_confirmation"] is True


def test_a_scope_the_design_does_not_mention_is_left_alone(v2_env):
    """The security program declares what it declares; silence is not removal."""
    with session_scope() as s:
        iid = _instance(s)
        rid = _role(s, scope_access={"Account": {"read": "all"}})
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="role", member_identifier=rid,
            state="drifted",
            override={"role_scope_access": {"Account": {"read": "all"},
                                            "Contact": {"read": "all"}}},
        )
        out = reconcile_access.assess_access_publish(
            s, instance=iid, member_type="role", member_identifier=rid
        )
    assert out["changes"] == []
    assert out["removes_access"] is False


def test_a_system_permission_drop_reads_as_a_removal(v2_env):
    with session_scope() as s:
        iid = _instance(s)
        rid = _role(s, permissions={"assignmentPermission": "team"})
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="role", member_identifier=rid,
            state="drifted",
            override={"role_system_permissions": {"assignmentPermission": "all"}},
        )
        out = reconcile_access.assess_access_publish(
            s, instance=iid, member_type="role", member_identifier=rid
        )
    assert out["removes_access"] is True
    assert out["removals"][0]["permission"] == "assignmentPermission"


def test_not_set_on_either_side_is_never_claimed_as_a_removal(v2_env):
    """``not-set`` means "inherit the default" — its weight is unknown, and the
    gate does not assert a removal it cannot prove."""
    with session_scope() as s:
        iid = _instance(s)
        rid = _role(s, permissions={"exportPermission": "not-set"})
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="role", member_identifier=rid,
            state="drifted",
            override={"role_system_permissions": {"exportPermission": "yes"}},
        )
        out = reconcile_access.assess_access_publish(
            s, instance=iid, member_type="role", member_identifier=rid
        )
    assert len(out["changes"]) == 1
    assert out["removes_access"] is False


def test_an_unranked_level_is_reported_but_not_called_a_removal(v2_env):
    with session_scope() as s:
        iid = _instance(s)
        rid = _role(s, scope_access={"Account": {"read": "somethingNew"}})
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="role", member_identifier=rid,
            state="drifted",
            override={"role_scope_access": {"Account": {"read": "all"}}},
        )
        out = reconcile_access.assess_access_publish(
            s, instance=iid, member_type="role", member_identifier=rid
        )
    assert len(out["changes"]) == 1
    assert out["removes_access"] is False


def test_a_team_publish_is_confirmed_but_never_a_removal(v2_env):
    with session_scope() as s:
        iid = _instance(s)
        tid = team_repo.create_team(s, name="Mentor Team", status="confirmed")[
            "team_identifier"
        ]
        out = reconcile_access.assess_access_publish(
            s, instance=iid, member_type="team", member_identifier=tid
        )
    assert out["requires_confirmation"] is True
    assert out["removes_access"] is False
    assert "Mentor Team" in out["summary"]


def test_a_member_type_that_does_not_change_access_is_refused(v2_env):
    with session_scope() as s:
        iid = _instance(s)
        with pytest.raises(ConflictError):
            reconcile_access.assess_access_publish(
                s, instance=iid, member_type="field", member_identifier="FLD-001"
            )


def test_a_missing_role_is_not_found(v2_env):
    with session_scope() as s:
        iid = _instance(s)
        with pytest.raises(NotFoundError):
            reconcile_access.assess_access_publish(
                s, instance=iid, member_type="role", member_identifier="ROL-999"
            )


# --- the store-free core the whole-design route reuses (PI-466) --------------


def test_the_core_assessment_takes_both_sides_as_values():
    """The whole-design publish hands the target's live role in here; the
    words and the verdict are the reconcile route's, not a second judgement."""
    out = reconcile_access.assess_member_access(
        instance="INST-009", member_type="role", member_identifier="ROL-001",
        member_name="Mentor",
        design_scope_access={"Contact": {"read": "all", "delete": "no"}},
        design_system_permissions={"exportPermission": "no"},
        instance_scope_access={"Contact": {"read": "all", "delete": "all"}},
        instance_system_permissions={"exportPermission": "yes"},
    )
    assert out["removes_access"] is True
    assert [c["description"] for c in out["removals"]] == [
        "Mentor: Contact.delete all → no",
        "Mentor: exportPermission yes → no",
    ]
    assert out["target"] == {
        "instance": "INST-009", "member_type": "role",
        "member_identifier": "ROL-001", "member_name": "Mentor",
    }
    assert "2 of which take access away" in out["summary"]


def test_an_instance_holding_nothing_makes_every_setting_new_not_a_removal():
    out = reconcile_access.assess_member_access(
        instance="INST-009", member_type="role", member_identifier="ROL-001",
        member_name="Mentor",
        design_scope_access={"Contact": {"read": "all", "delete": "no"}},
    )
    assert out["removes_access"] is False
    assert [c["before"] for c in out["changes"]] == [None, None]
    assert out["changes"][0]["description"] == "Mentor: Contact.delete unset → no"


def test_the_core_refuses_a_member_type_that_does_not_change_access():
    with pytest.raises(ConflictError):
        reconcile_access.assess_member_access(
            instance="INST-009", member_type="field",
            member_identifier="FLD-001", member_name="x",
        )

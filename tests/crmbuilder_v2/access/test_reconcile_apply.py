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
from crmbuilder_v2.access.repositories import source_mapping as sm_repo


def _setup(s, *, role="source"):
    iid = inst_repo.create_instance(
        s, name="src", url="https://src.example.org", role=role
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


# --- PI-332: entity-settings capture --------------------------------------


def test_capture_entity_setting_writes_design_logs_clears(v2_env):
    """Capturing an entity-collection setting mirrors field capture: it writes
    the design, logs a capture, and clears the instance drift (REQ-375)."""
    with session_scope() as s:
        iid, _fid = _setup(s)
        eid = entity_repo.create_entity(s, name="Widget", description="x")[
            "entity_identifier"
        ]
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="entity", member_identifier=eid,
            state="drifted", override={"entity_default_sort_field": "name"},
        )
        out = reconcile_apply.capture_entity_setting(
            s, instance=iid, entity_identifier=eid,
            attribute="entity_default_sort_field", actor="Doug",
        )
        assert out["entity"]["entity_default_sort_field"] == "name"
        t = out["transaction"]
        assert t["direction"] == "capture"
        assert t["member_type"] == "entity"
        assert t["target_ref"] == "design"
        m = mb.list_memberships(s, instance_identifier=iid, member_type="entity",
                                member_identifier=eid)[0]
        assert m["state"] == "present"
        assert m["override"] is None


def test_capture_entity_setting_without_deviation_is_conflict(v2_env):
    with session_scope() as s:
        iid, _fid = _setup(s)
        eid = entity_repo.create_entity(s, name="Gadget", description="x")[
            "entity_identifier"
        ]
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="entity", member_identifier=eid,
            state="present",
        )
        with pytest.raises(ConflictError):
            reconcile_apply.capture_entity_setting(
                s, instance=iid, entity_identifier=eid,
                attribute="entity_default_sort_field", actor="Doug",
            )


# --- PI-332: publish scope + record ---------------------------------------


def test_entity_for_member_resolves_parents(v2_env):
    with session_scope() as s:
        eid = entity_repo.create_entity(s, name="Account", description="x")[
            "entity_identifier"
        ]
        fid = field_repo.create_field(
            s, field_belongs_to_entity_identifier=eid, name="code",
            description="x", type="text", required=False,
        )["field_identifier"]
        # field -> parent entity
        assert reconcile_apply.entity_for_member(s, "field", fid)[
            "entity_identifier"
        ] == eid
        # entity -> itself
        assert reconcile_apply.entity_for_member(s, "entity", eid)[
            "entity_identifier"
        ] == eid


def test_publish_scope_filename(v2_env):
    with session_scope() as s:
        eid = entity_repo.create_entity(s, name="Mentor Profile", description="x")[
            "entity_identifier"
        ]
        scope = reconcile_apply.publish_scope_for_member(s, "entity", eid)
        assert scope["entity_identifier"] == eid
        assert scope["filename"] == "Mentor-Profile.yaml"


def test_record_publish_logs_and_reconciles_membership(v2_env):
    """A successful publish logs a publish transaction and clears the published
    attribute's drift on the target instance (REQ-376)."""
    with session_scope() as s:
        iid, fid = _setup(s)
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="field", member_identifier=fid,
            state="drifted",
            override={"field_max_length": 50, "field_type": "varchar"},
        )
        rc = reconcile_apply.record_publish(
            s, instance=iid, member_type="field", member_identifier=fid,
            attribute="field_max_length", actor="Doug",
            before_value=50, after_value=255,
        )
        t = rc["transaction"]
        assert t["direction"] == "publish"
        assert t["source_ref"] == "design"
        assert t["target_ref"] == iid
        m = mb.list_memberships(s, instance_identifier=iid, member_type="field",
                                member_identifier=fid)[0]
        # only the published attribute is reconciled; the other drift remains
        assert m["override"] == {"field_type": "varchar"}
        assert m["state"] == "drifted"


def test_record_publish_whole_member_clears_all_drift(v2_env):
    """A whole-member promote (no attribute) marks the member present and clears
    its override entirely (REQ-369)."""
    with session_scope() as s:
        iid, fid = _setup(s)
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="field", member_identifier=fid,
            state="drifted", override={"field_max_length": 50},
        )
        reconcile_apply.record_publish(
            s, instance=iid, member_type="field", member_identifier=fid,
            actor="Doug",
        )
        m = mb.list_memberships(s, instance_identifier=iid, member_type="field",
                                member_identifier=fid)[0]
        assert m["state"] == "present"
        assert m["override"] is None


# --- WTK-257 (REL-038 / WTK-252 design): capture-back stays available for a
#     both-role instance. Capture is role-agnostic — eligibility is decided by a
#     recorded deviation, never by instance_role — and must succeed with zero
#     source_mapping rows present (the external-migration mapping path is never
#     on the both-role capture path). These tests lock that guarantee so the
#     WTK-251 audit-routing fix cannot be over-applied into the capture path.


def test_capture_field_available_for_both_role_instance(v2_env):
    """A both-role instance captures a live field-attribute value into the design
    on the same terms as any other instance (WTK-252 §3.1, acceptance 1)."""
    with session_scope() as s:
        iid, fid = _setup(s, role="both")
        # precondition: no resolved (or any) source mappings exist (acceptance 3)
        assert sm_repo.list_source_mappings(s, instance_identifier=iid) == []
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="field", member_identifier=fid,
            state="drifted", override={"field_max_length": 100},
        )
        out = reconcile_apply.capture_field_attribute(
            s, instance=iid, field_identifier=fid,
            attribute="field_max_length", actor="Doug",
        )
        # captured value lands on the canonical field
        assert out["field"]["field_max_length"] == 100
        # a capture transaction is logged from the both-role instance
        t = out["transaction"]
        assert t["direction"] == "capture"
        assert t["source_ref"] == iid
        assert t["target_ref"] == "design"
        # the attribute's drift clears on the instance
        m = mb.list_memberships(s, instance_identifier=iid, member_type="field",
                                member_identifier=fid)[0]
        assert m["state"] == "present"
        assert m["override"] is None
        # no source mappings were created or required by the capture
        assert sm_repo.list_source_mappings(s, instance_identifier=iid) == []


def test_capture_entity_setting_available_for_both_role_instance(v2_env):
    """A both-role instance captures a live entity-collection setting into the
    design on the same terms (WTK-252 §3.1, acceptance 2 + 3)."""
    with session_scope() as s:
        iid, _fid = _setup(s, role="both")
        eid = entity_repo.create_entity(s, name="Mentor", description="x")[
            "entity_identifier"
        ]
        assert sm_repo.list_source_mappings(s, instance_identifier=iid) == []
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="entity", member_identifier=eid,
            state="drifted", override={"entity_default_sort_field": "name"},
        )
        out = reconcile_apply.capture_entity_setting(
            s, instance=iid, entity_identifier=eid,
            attribute="entity_default_sort_field", actor="Doug",
        )
        assert out["entity"]["entity_default_sort_field"] == "name"
        t = out["transaction"]
        assert t["direction"] == "capture"
        assert t["member_type"] == "entity"
        assert t["source_ref"] == iid
        assert t["target_ref"] == "design"
        m = mb.list_memberships(s, instance_identifier=iid, member_type="entity",
                                member_identifier=eid)[0]
        assert m["state"] == "present"
        assert m["override"] is None
        assert sm_repo.list_source_mappings(s, instance_identifier=iid) == []


def test_capture_for_both_role_without_deviation_is_conflict_not_role_gate(v2_env):
    """Capture eligibility for a both-role instance is decided solely by a
    recorded deviation, never by the role: with no drift it raises the same
    ``ConflictError`` as any other role — not a role-based rejection
    (WTK-252 §3.2, acceptance 4)."""
    with session_scope() as s:
        iid, fid = _setup(s, role="both")
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="field", member_identifier=fid,
            state="present",
        )
        with pytest.raises(ConflictError) as exc:
            reconcile_apply.capture_field_attribute(
                s, instance=iid, field_identifier=fid,
                attribute="field_max_length", actor="Doug",
            )
        # the rejection is the nothing-to-capture conflict, not a role gate
        assert "nothing to capture" in str(exc.value)


# --- REQ-442: enum option set captures back through the generic path ----------

def test_capture_field_options_round_trips_into_design(v2_env):
    """An instance's enum option set captures back into the canonical field via
    the existing generic capture path (override attribute -> patch_field options=),
    proving the child-collection attribute rides the same rails as scalar attrs."""
    with session_scope() as s:
        iid = inst_repo.create_instance(
            s, name="src", url="https://src.example.org", role="source"
        )["instance_identifier"]
        eid = entity_repo.create_entity(s, name="Account", description="x")[
            "entity_identifier"
        ]
        fid = field_repo.create_field(
            s, field_belongs_to_entity_identifier=eid, name="status",
            description="x", type="enum", required=False,
            options=[{"option_value": "open", "option_label": "Open"}],
        )["field_identifier"]
        audited = [
            {"option_value": "open", "option_label": "Open"},
            {"option_value": "closed", "option_label": "Closed out"},
        ]
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="field", member_identifier=fid,
            state="drifted", override={"field_options": audited},
        )
        out = reconcile_apply.capture_field_attribute(
            s, instance=iid, field_identifier=fid,
            attribute="field_options", actor="Doug",
        )
        captured = {o["option_value"] for o in out["field"]["field_options"]}
        assert captured == {"open", "closed"}
        # the labels round-trip too
        labels = {o["option_value"]: o["option_label"] for o in out["field"]["field_options"]}
        assert labels["closed"] == "Closed out"
        # drift cleared on the instance
        m = mb.list_memberships(s, instance_identifier=iid, member_type="field",
                                member_identifier=fid)[0]
        assert m["state"] == "present"
        assert m["override"] is None


# --- REQ-443: capture & rollback an association attribute (cardinality) -------

from crmbuilder_v2.access.repositories import association as assoc_repo  # noqa: E402


def _assoc(s):
    """Two entities + a one_to_many association between them."""
    src = entity_repo.create_entity(s, name="Client", description="x")["entity_identifier"]
    tgt = entity_repo.create_entity(s, name="Contact", description="x")["entity_identifier"]
    a = assoc_repo.create_association(
        s, name="clientContact", source_entity=src, target_entity=tgt,
        cardinality="one_to_many",
    )
    return a["association_identifier"]


def test_capture_association_cardinality_into_design(v2_env):
    with session_scope() as s:
        iid = inst_repo.create_instance(
            s, name="t", url="https://t.example.org", role="both"
        )["instance_identifier"]
        aid = _assoc(s)
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="association", member_identifier=aid,
            state="drifted", override={"association_cardinality": "many_to_many"},
        )
        out = reconcile_apply.capture_association_attribute(
            s, instance=iid, association_identifier=aid,
            attribute="association_cardinality", actor="Doug",
        )
        assert out["association"]["association_cardinality"] == "many_to_many"
        t = out["transaction"]
        assert t["direction"] == "capture" and t["before_value"] == "one_to_many"
        m = mb.list_memberships(s, instance_identifier=iid, member_type="association",
                                member_identifier=aid)[0]
        assert m["state"] == "present" and m["override"] is None


def test_capture_association_without_deviation_is_conflict(v2_env):
    with session_scope() as s:
        iid = inst_repo.create_instance(
            s, name="t", url="https://t.example.org", role="both"
        )["instance_identifier"]
        aid = _assoc(s)
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="association", member_identifier=aid,
            state="present", override=None,
        )
        with pytest.raises(ConflictError):
            reconcile_apply.capture_association_attribute(
                s, instance=iid, association_identifier=aid,
                attribute="association_cardinality", actor="Doug",
            )


def test_rollback_association_capture_restores_cardinality(v2_env):
    with session_scope() as s:
        iid = inst_repo.create_instance(
            s, name="t", url="https://t.example.org", role="both"
        )["instance_identifier"]
        aid = _assoc(s)
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="association", member_identifier=aid,
            state="drifted", override={"association_cardinality": "many_to_many"},
        )
        cap = reconcile_apply.capture_association_attribute(
            s, instance=iid, association_identifier=aid,
            attribute="association_cardinality", actor="Doug",
        )
        txn_id = cap["transaction"]["id"]
        reconcile_apply.rollback(s, txn_id, actor="Doug")
        assert assoc_repo.get_association(s, aid)["association_cardinality"] == "one_to_many"


# --- REQ-445: per-value (merge) capture of enum option values ----------------

def test_merge_option_values_add_relabel_remove_and_leave_others():
    design = [{"option_value": "A", "option_label": "A"},
              {"option_value": "X", "option_label": "Keep"}]
    source = [{"option_value": "A", "option_label": "A"},
              {"option_value": "B", "option_label": "Bee"},
              {"option_value": "C", "option_label": "Wrong"}]
    # select B (add), X (remove — not in source), A relabel n/a (same). Leave C alone.
    out = reconcile_apply.merge_option_values(design, source, ["B", "X"])
    vals = {o["option_value"]: o["option_label"] for o in out}
    assert "B" in vals and vals["B"] == "Bee"   # added with source label
    assert "X" not in vals                       # removed (source lacks it)
    assert "A" in vals                           # unselected, untouched
    assert "C" not in vals                       # never selected, not pulled
    # order is resequenced
    assert [o["option_order"] for o in out] == list(range(len(out)))


def test_merge_option_values_relabels_selected_value():
    design = [{"option_value": "a", "option_label": "Apple"}]
    source = [{"option_value": "a", "option_label": "Apricot"}]
    out = reconcile_apply.merge_option_values(design, source, ["a"])
    assert out == [{"option_value": "a", "option_label": "Apricot", "option_order": 0}]


def _enum_field(s, options):
    eid = entity_repo.create_entity(s, name="Acct", description="x")["entity_identifier"]
    return field_repo.create_field(
        s, field_belongs_to_entity_identifier=eid, name="status",
        description="x", type="enum", required=False, options=options,
    )["field_identifier"]


def test_capture_field_option_values_merges_only_selected(v2_env):
    with session_scope() as s:
        iid = inst_repo.create_instance(
            s, name="t", url="https://t.example.org", role="both"
        )["instance_identifier"]
        fid = _enum_field(s, [{"option_value": "A", "option_label": "A"}])
        # instance audited set has A,B,C(wrong),D
        source = [{"option_value": v} for v in ("A", "B", "C", "D")]
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="field", member_identifier=fid,
            state="drifted", override={"field_options": source},
        )
        out = reconcile_apply.capture_field_option_values(
            s, instance=iid, field_identifier=fid, option_values=["B", "D"], actor="Doug",
        )
        vals = {o["option_value"] for o in out["field"]["field_options"]}
        assert vals == {"A", "B", "D"}          # C left behind
        # still drifts (design != instance set), override kept
        m = mb.list_memberships(s, instance_identifier=iid, member_type="field",
                                member_identifier=fid)[0]
        assert m["state"] == "drifted" and m["override"] is not None


def test_capture_field_option_values_clears_override_when_fully_matched(v2_env):
    with session_scope() as s:
        iid = inst_repo.create_instance(
            s, name="t", url="https://t.example.org", role="both"
        )["instance_identifier"]
        fid = _enum_field(s, [{"option_value": "A", "option_label": "A"}])
        source = [{"option_value": "A"}, {"option_value": "B"}]
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="field", member_identifier=fid,
            state="drifted", override={"field_options": source},
        )
        reconcile_apply.capture_field_option_values(
            s, instance=iid, field_identifier=fid, option_values=["B"], actor="Doug",
        )
        m = mb.list_memberships(s, instance_identifier=iid, member_type="field",
                                member_identifier=fid)[0]
        assert m["state"] == "present" and m["override"] is None


def test_capture_field_option_values_rollback_restores(v2_env):
    with session_scope() as s:
        iid = inst_repo.create_instance(
            s, name="t", url="https://t.example.org", role="both"
        )["instance_identifier"]
        fid = _enum_field(s, [{"option_value": "A", "option_label": "A"}])
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="field", member_identifier=fid,
            state="drifted", override={"field_options": [{"option_value": "A"}, {"option_value": "B"}]},
        )
        cap = reconcile_apply.capture_field_option_values(
            s, instance=iid, field_identifier=fid, option_values=["B"], actor="Doug",
        )
        reconcile_apply.rollback(s, cap["transaction"]["id"], actor="Doug")
        vals = {o["option_value"] for o in field_repo.get_field(s, fid)["field_options"]}
        assert vals == {"A"}   # B removed again


def test_capture_field_option_values_conflict_without_deviation(v2_env):
    with session_scope() as s:
        iid = inst_repo.create_instance(
            s, name="t", url="https://t.example.org", role="both"
        )["instance_identifier"]
        fid = _enum_field(s, [{"option_value": "A"}])
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="field", member_identifier=fid,
            state="present", override=None,
        )
        with pytest.raises(ConflictError):
            reconcile_apply.capture_field_option_values(
                s, instance=iid, field_identifier=fid, option_values=["A"], actor="Doug",
            )

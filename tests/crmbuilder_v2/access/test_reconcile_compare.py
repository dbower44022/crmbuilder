"""Unit tests for the three-way comparison core — PI-316 (REL-024)."""

from __future__ import annotations

from crmbuilder_v2.access.reconcile_compare import (
    ABSENT,
    PRESENT,
    UNKNOWN,
    _override_attrs,
    compute_member_rows,
)


def _mem(state="present", override=None):
    return {"state": state, "override": override}


def test_no_difference_emits_nothing():
    """Member present on both instances with no override: zero rows."""
    rows = compute_member_rows(
        member_type="field",
        member_identifier="FLD-1",
        member_name="phone",
        design_obj={"field_type": "varchar", "field_required": False},
        attributes=[],
        membership_a=_mem(),
        membership_b=_mem(),
    )
    assert rows == []


def test_attribute_drift_on_one_instance():
    """A drifts field_type; B matches design -> one attribute row, design vs A."""
    a = _mem(state="drifted", override={"field_type": "text"})
    rows = compute_member_rows(
        member_type="field",
        member_identifier="FLD-1",
        member_name="notes",
        design_obj={"field_type": "varchar"},
        attributes=_override_attrs(a, _mem()),
        membership_a=a,
        membership_b=_mem(),
    )
    assert len(rows) == 1
    r = rows[0]
    assert r["kind"] == "attribute"
    assert r["attribute"] == "field_type"
    assert r["design"] == "varchar"
    assert r["instance_a"] == "text"
    assert r["instance_b"] == "varchar"  # no override -> design value
    assert r["differs"] is True


def test_both_instances_agree_but_differ_from_design():
    """A and B both drift to the same value -> still flagged vs the design."""
    a = _mem(state="drifted", override={"field_max_length": 100})
    b = _mem(state="drifted", override={"field_max_length": 100})
    rows = compute_member_rows(
        member_type="field",
        member_identifier="FLD-1",
        member_name="code",
        design_obj={"field_max_length": 255},
        attributes=_override_attrs(a, b),
        membership_a=a,
        membership_b=b,
    )
    assert len(rows) == 1
    assert rows[0]["design"] == 255
    assert rows[0]["instance_a"] == 100
    assert rows[0]["instance_b"] == 100


def test_presence_difference_absent_on_b():
    """Design defines the member; B is absent -> a presence row."""
    rows = compute_member_rows(
        member_type="field",
        member_identifier="FLD-1",
        member_name="region",
        design_obj={"field_type": "enum"},
        attributes=[],
        membership_a=_mem(),
        membership_b=_mem(state="absent"),
    )
    assert len(rows) == 1
    r = rows[0]
    assert r["kind"] == "presence"
    assert r["design"] == PRESENT
    assert r["instance_a"] == PRESENT
    assert r["instance_b"] == ABSENT


def test_never_audited_is_unknown_presence():
    """No membership row on B -> unknown presence (distinct from absent)."""
    rows = compute_member_rows(
        member_type="entity",
        member_identifier="ENT-1",
        member_name="Account",
        design_obj={},
        attributes=[],
        membership_a=_mem(),
        membership_b=None,
    )
    assert rows[0]["instance_b"] == UNKNOWN


def test_absent_instance_does_not_drive_attribute_diff():
    """When B is absent, its attribute cell shows the presence token, and the
    diff is decided by design vs the present instance only."""
    a = _mem(state="drifted", override={"field_required": True})
    b = _mem(state="absent")
    rows = compute_member_rows(
        member_type="field",
        member_identifier="FLD-1",
        member_name="owner",
        design_obj={"field_required": False},
        attributes=_override_attrs(a, b),
        membership_a=a,
        membership_b=b,
    )
    kinds = {r["kind"] for r in rows}
    assert kinds == {"presence", "attribute"}
    attr_row = next(r for r in rows if r["kind"] == "attribute")
    assert attr_row["attribute"] == "field_required"
    assert attr_row["design"] is False
    assert attr_row["instance_a"] is True
    assert attr_row["instance_b"] == ABSENT  # presence token, not a value


def test_override_attrs_unions_and_sorts():
    a = _mem(override={"field_type": "text", "field_required": True})
    b = _mem(override={"field_max_length": 50})
    assert _override_attrs(a, b, None) == [
        "field_max_length",
        "field_required",
        "field_type",
    ]


# --- DB integration ---------------------------------------------------------

from crmbuilder_v2.access.db import session_scope  # noqa: E402
from crmbuilder_v2.access.reconcile_compare import three_way_compare  # noqa: E402
from crmbuilder_v2.access.repositories import entity as entity_repo  # noqa: E402
from crmbuilder_v2.access.repositories import field as field_repo  # noqa: E402
from crmbuilder_v2.access.repositories import instance_membership as mb  # noqa: E402
from crmbuilder_v2.access.repositories import instances as inst_repo  # noqa: E402


def _inst(s, name, role):
    return inst_repo.create_instance(
        s, name=name, url=f"https://{name}.example.org", role=role
    )["instance_identifier"]


def test_three_way_compare_groups_presence_and_attribute(v2_env):
    """End-to-end: a field drifted on A and absent on B yields both a presence
    and an attribute row under the parent entity's group; the entity (present on
    both) yields no row."""
    with session_scope() as s:
        a = _inst(s, "alpha", "source")
        b = _inst(s, "beta", "target")
        eid = entity_repo.create_entity(s, name="Account", description="x")[
            "entity_identifier"
        ]
        fid = field_repo.create_field(
            s, field_belongs_to_entity_identifier=eid, name="phone",
            description="x", type="text", required=False,
        )["field_identifier"]

        mb.upsert_membership(
            s, instance_identifier=a, member_type="field", member_identifier=fid,
            state="drifted", override={"field_type": "varchar"},
        )
        mb.upsert_membership(
            s, instance_identifier=b, member_type="field", member_identifier=fid,
            state="absent",
        )
        for inst in (a, b):
            mb.upsert_membership(
                s, instance_identifier=inst, member_type="entity",
                member_identifier=eid, state="present",
            )

        result = three_way_compare(s, instance_a=a, instance_b=b)
        grp = next(g for g in result["groups"] if g["entity_identifier"] == eid)
        kinds = {(r["member_type"], r["kind"]) for r in grp["rows"]}
        assert ("field", "presence") in kinds
        assert ("field", "attribute") in kinds
        # entity present on both -> no entity row
        assert not any(r["member_type"] == "entity" for r in grp["rows"])

        drill = three_way_compare(
            s, instance_a=a, instance_b=b, entity_identifier=eid
        )
        assert drill["scope"] == eid
        assert all(g["entity_identifier"] == eid for g in drill["groups"])

"""Unit tests for the three-way comparison core — PI-316 (REL-024)."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.reconcile_compare import (
    ABSENT,
    PRESENT,
    UNKNOWN,
    _override_attrs,
    compute_member_properties,
    compute_member_rows,
    option_sets_equal,
    summarize_option_diff,
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


def test_include_unchanged_emits_presence_anchor_plus_every_property():
    """REQ-478: with include_unchanged, an in-sync member yields a presence anchor
    row *and* one row per comparable property, so show-all shows values and not
    merely membership. Matching properties are non-differing and non-actionable."""
    rows = compute_member_rows(
        member_type="field",
        member_identifier="FLD-1",
        member_name="phone",
        design_obj={"field_type": "varchar", "field_required": False},
        attributes=[],
        membership_a=_mem(),
        membership_b=_mem(),
        include_unchanged=True,
    )
    anchor = rows[0]
    assert anchor["kind"] == "presence"
    assert anchor["differs"] is False
    assert anchor["actionable"] is False
    assert anchor["design"] == PRESENT
    assert anchor["instance_a"] == PRESENT
    assert anchor["instance_b"] == PRESENT

    by_attr = {r["attribute"]: r for r in rows[1:]}
    assert set(by_attr) == {"field_type", "field_required"}
    for r in by_attr.values():
        assert r["kind"] == "attribute"
        assert r["differs"] is False
        assert r["actionable"] is False
    # the value itself is carried in every location, not a presence token
    assert by_attr["field_type"]["design"] == "varchar"
    assert by_attr["field_type"]["instance_a"] == "varchar"
    assert by_attr["field_type"]["instance_b"] == "varchar"


def test_include_unchanged_covers_properties_no_instance_overrides():
    """The show-all attribute set comes from the design object, not from the
    override keys — the REQ-432 defect was that a property nothing deviates on was
    never even a comparison candidate, so it could never be shown."""
    rows = compute_member_rows(
        member_type="field",
        member_identifier="FLD-1",
        member_name="phone",
        design_obj={"field_type": "varchar", "field_label": "Phone"},
        attributes=_override_attrs(_mem(), _mem()),  # empty: nothing is overridden
        membership_a=_mem(),
        membership_b=_mem(),
        include_unchanged=True,
    )
    assert {r["attribute"] for r in rows if r["kind"] == "attribute"} == {
        "field_type", "field_label"
    }


def test_include_unchanged_keeps_properties_empty_in_every_location():
    """A COMPARED property unset in the design and both instances still gets a
    row: show-all must not quietly drop a property just because nothing has set
    it. An EXCLUDED property (field_tooltip, DEC-928) is dropped by ruling —
    never examined, never shown as a comparison row (REQ-490 / PI-409)."""
    rows = compute_member_rows(
        member_type="field",
        member_identifier="FLD-1",
        member_name="phone",
        design_obj={"field_type": "varchar", "field_format": None,
                    "field_tooltip": None},
        attributes=[],
        membership_a=_mem(),
        membership_b=_mem(),
        include_unchanged=True,
    )
    fmt = next(r for r in rows if r["attribute"] == "field_format")
    assert fmt["design"] is None
    assert fmt["differs"] is False
    assert not any(r.get("attribute") == "field_tooltip" for r in rows)


def test_include_unchanged_keeps_a_differing_member_actionable():
    """A member that differs keeps its difference flagged and actionable while its
    agreeing properties come along as verification-only rows."""
    a = _mem(state="drifted", override={"field_type": "text"})
    rows = compute_member_rows(
        member_type="field",
        member_identifier="FLD-1",
        member_name="notes",
        design_obj={"field_type": "varchar", "field_label": "Notes"},
        attributes=_override_attrs(a, _mem()),
        membership_a=a,
        membership_b=_mem(),
        include_unchanged=True,
    )
    by_attr = {r["attribute"]: r for r in rows}
    assert by_attr["field_type"]["differs"] is True
    assert by_attr["field_type"]["actionable"] is True
    assert by_attr["field_label"]["differs"] is False
    assert by_attr["field_label"]["actionable"] is False


def test_differences_only_ignores_non_overridden_properties():
    """The default path is untouched: an in-sync member yields no rows at all, and
    the widened attribute set never leaks into differences-only mode."""
    a = _mem(state="drifted", override={"field_type": "text"})
    rows = compute_member_rows(
        member_type="field",
        member_identifier="FLD-1",
        member_name="notes",
        design_obj={"field_type": "varchar", "field_label": "Notes"},
        attributes=_override_attrs(a, _mem()),
        membership_a=a,
        membership_b=_mem(),
    )
    assert [r["attribute"] for r in rows] == ["field_type"]


def test_member_properties_lists_every_property_with_differs_flags():
    """REQ-433: the per-field property view emits one row per property — matching
    and differing alike — with each location's value and a differs flag, dropping
    only identity/bookkeeping keys."""
    design = {
        "field_identifier": "FLD-1",   # bookkeeping -> excluded
        "field_name": "phone",
        "field_type": "varchar",
        "field_required": False,
        "field_max_length": 255,
        "created_at": "x",             # bookkeeping -> excluded
    }
    a = _mem(state="drifted", override={"field_max_length": 100})
    res = compute_member_properties(
        member_type="field",
        member_identifier="FLD-1",
        member_name="phone",
        design_obj=design,
        membership_a=a,
        membership_b=_mem(),
    )
    by_attr = {r["attribute"]: r for r in res["rows"]}
    # identity/bookkeeping keys are dropped; real properties are all present
    assert "field_identifier" not in by_attr
    assert "created_at" not in by_attr
    assert set(by_attr) == {"field_name", "field_type", "field_required", "field_max_length"}
    # in-sync property: same everywhere, not flagged
    assert by_attr["field_type"]["design"] == "varchar"
    assert by_attr["field_type"]["differs"] is False
    # drifted property: A overrides 255 -> 100, flagged
    ml = by_attr["field_max_length"]
    assert ml["design"] == 255 and ml["instance_a"] == 100 and ml["instance_b"] == 255
    assert ml["differs"] is True
    assert res["presence"] == {"design": PRESENT, "instance_a": PRESENT, "instance_b": PRESENT}


def test_member_properties_absent_instance_shows_presence_token():
    """A property on an instance that does not carry the member shows its presence
    token in place of a value (B absent here)."""
    res = compute_member_properties(
        member_type="field",
        member_identifier="FLD-1",
        member_name="notes",
        design_obj={"field_type": "varchar"},
        membership_a=_mem(),
        membership_b=None,  # never audited on B
    )
    row = res["rows"][0]
    assert row["instance_b"] == UNKNOWN
    assert res["presence"]["instance_b"] == UNKNOWN


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


def test_object_type_for_buckets():
    """Each member type maps to its detail-tree bucket (REQ-370)."""
    from crmbuilder_v2.access.reconcile_compare import object_type_for

    assert object_type_for("field", "field_type") == "fields"
    assert object_type_for("field", "field_formula") == "formulas"
    assert object_type_for("field", "field_derived_result_type") == "formulas"
    assert object_type_for("association", None) == "relations"
    assert object_type_for("layout", None) == "layouts"
    assert object_type_for("entity", "entity_default_sort_field") == "settings"
    assert object_type_for("role", None) == "other"
    assert object_type_for("team", None) == "other"
    assert object_type_for("filtered_tab", None) == "other"


def test_compare_emits_object_groups(v2_env):
    """A group's rows are partitioned into ordered object-type buckets (REQ-370)."""
    with session_scope() as s:
        a = _inst(s, "og_a", "source")
        b = _inst(s, "og_b", "target")
        eid = entity_repo.create_entity(s, name="Widget", description="x")[
            "entity_identifier"
        ]
        fid = field_repo.create_field(
            s, field_belongs_to_entity_identifier=eid, name="size",
            description="x", type="text", required=False,
        )["field_identifier"]
        mb.upsert_membership(
            s, instance_identifier=a, member_type="field", member_identifier=fid,
            state="drifted", override={"field_type": "varchar"},
        )
        for inst in (a, b):
            mb.upsert_membership(
                s, instance_identifier=inst, member_type="entity",
                member_identifier=eid, state="present",
            )
        res = three_way_compare(s, instance_a=a, instance_b=b)
        grp = next(g for g in res["groups"] if g["entity_identifier"] == eid)
        assert "object_groups" in grp
        buckets = {og["object_type"] for og in grp["object_groups"]}
        assert "fields" in buckets
        fields_og = next(og for og in grp["object_groups"] if og["object_type"] == "fields")
        assert fields_og["differing_count"] == len(fields_og["rows"]) >= 1
        # buckets appear in canonical order
        from crmbuilder_v2.access.reconcile_compare import OBJECT_TYPE_ORDER
        order = [OBJECT_TYPE_ORDER.index(og["object_type"]) for og in grp["object_groups"]]
        assert order == sorted(order)


def test_entity_settings_rows_are_actionable():
    """Entity-collection-setting attribute rows are actionable; a non-setting
    entity attribute is shown but not actionable (REQ-375 / REQ-358)."""
    a = _mem(state="drifted", override={"entity_default_sort_field": "name"})
    rows = compute_member_rows(
        member_type="entity", member_identifier="ENT-1", member_name="Account",
        design_obj={"entity_default_sort_field": "createdAt"},
        attributes=_override_attrs(a, _mem()),
        membership_a=a, membership_b=_mem(),
    )
    settings_row = next(r for r in rows if r["attribute"] == "entity_default_sort_field")
    assert settings_row["actionable"] is True

    other = _mem(state="drifted", override={"entity_label": "Acct"})
    rows2 = compute_member_rows(
        member_type="entity", member_identifier="ENT-1", member_name="Account",
        design_obj={"entity_label": "Account"},
        attributes=_override_attrs(other, _mem()),
        membership_a=other, membership_b=_mem(),
    )
    label_row = next(r for r in rows2 if r["attribute"] == "entity_label")
    assert label_row["actionable"] is False


def test_compare_existence_rollup(v2_env):
    """The payload carries one existence row per entity for the landing grid
    (REQ-368): design always present, instances reflect their membership."""
    with session_scope() as s:
        a = _inst(s, "ex_a", "source")
        b = _inst(s, "ex_b", "target")
        present_eid = entity_repo.create_entity(s, name="Here", description="x")[
            "entity_identifier"
        ]
        missing_eid = entity_repo.create_entity(s, name="Gone", description="x")[
            "entity_identifier"
        ]
        # present on A, absent on B; never audited (unknown) elsewhere
        mb.upsert_membership(s, instance_identifier=a, member_type="entity",
                             member_identifier=present_eid, state="present")
        mb.upsert_membership(s, instance_identifier=b, member_type="entity",
                             member_identifier=missing_eid, state="absent")

        res = three_way_compare(s, instance_a=a, instance_b=b)
        ex = {row["entity_identifier"]: row for row in res["existence"]}
        assert ex[present_eid]["design"] == PRESENT
        assert ex[present_eid]["instance_a"] == PRESENT
        assert ex[present_eid]["instance_b"] == UNKNOWN  # never audited on B
        assert ex[missing_eid]["instance_a"] == UNKNOWN
        assert ex[missing_eid]["instance_b"] == ABSENT

        # scoped drill restricts existence to the one entity
        drill = three_way_compare(s, instance_a=a, instance_b=b,
                                  entity_identifier=present_eid)
        assert [r["entity_identifier"] for r in drill["existence"]] == [present_eid]


def test_compare_group_carries_entity_label(v2_env):
    """REL-025 / REQ-365: a group surfaces the entity's captured display label."""
    from crmbuilder_v2.access.repositories import entity as entity_repo
    with session_scope() as s:
        a = _inst(s, "alpha2", "source")
        b = _inst(s, "beta2", "target")
        eid = entity_repo.create_entity(s, name="MentorProfile", description="x")[
            "entity_identifier"
        ]
        entity_repo.patch_entity(s, eid, label="CBM Member")
        fid = field_repo.create_field(
            s, field_belongs_to_entity_identifier=eid, name="code",
            description="x", type="text", required=False,
        )["field_identifier"]
        mb.upsert_membership(s, instance_identifier=a, member_type="field",
                             member_identifier=fid, state="drifted",
                             override={"field_type": "varchar"})
        res = three_way_compare(s, instance_a=a, instance_b=b)
        grp = next(g for g in res["groups"] if g["entity_identifier"] == eid)
        assert grp["entity"] == "MentorProfile"
        assert grp["entity_label"] == "CBM Member"


# --- REQ-442: choice-field option-value reconciliation -----------------------


def _opts(*items):
    """Build a field_options list. Each item is a value str or (value, label)."""
    out = []
    for it in items:
        if isinstance(it, tuple):
            out.append({"option_value": it[0], "option_label": it[1]})
        else:
            out.append({"option_value": it, "option_label": None})
    return out


def test_option_set_equality_order_insensitive_and_label_default():
    """Sets match regardless of order; a None label defaults to its value, so a
    None-vs-value-as-label pair is not drift (Decision 2)."""
    assert option_sets_equal(_opts("a", "b"), _opts("b", "a"))
    # design has no label; instance labels it with the value itself -> still equal
    assert option_sets_equal(_opts("a"), [{"option_value": "a", "option_label": "a"}])
    # a genuine relabel is NOT equal
    assert not option_sets_equal(_opts(("a", "Apple")), _opts(("a", "Apricot")))


def test_summarize_option_diff_added_removed_relabeled():
    diff = summarize_option_diff(
        _opts(("a", "Apple"), "gone"),
        _opts(("a", "Apricot"), "new"),
    )
    assert diff["added"] == ["new"]
    assert diff["removed"] == ["gone"]
    assert diff["relabeled"] == [("a", "Apple", "Apricot")]


def test_compute_rows_flags_instance_only_option():
    """An instance whose override adds an option surfaces a differing field_options
    attribute row; the design value is the canonical option list."""
    design = {"field_type": "enum", "field_options": _opts("a", "b")}
    a = _mem(state="drifted", override={"field_options": _opts("a", "b", "c")})
    rows = compute_member_rows(
        member_type="field", member_identifier="FLD-1", member_name="status",
        design_obj=design, attributes=["field_options"],
        membership_a=a, membership_b=_mem(),
    )
    attr_rows = [r for r in rows if r["kind"] == "attribute"]
    assert len(attr_rows) == 1
    r = attr_rows[0]
    assert r["attribute"] == "field_options"
    assert r["differs"] is True
    assert r["actionable"] is True  # field attribute — capture/publish (REQ-442)


def test_compute_rows_label_only_drift_surfaces():
    design = {"field_type": "enum", "field_options": _opts(("a", "Apple"))}
    a = _mem(state="drifted", override={"field_options": _opts(("a", "Apricot"))})
    rows = compute_member_rows(
        member_type="field", member_identifier="FLD-1", member_name="fruit",
        design_obj=design, attributes=["field_options"],
        membership_a=a, membership_b=_mem(),
    )
    assert any(r["attribute"] == "field_options" and r["differs"] for r in rows)


def test_compute_rows_order_only_difference_is_not_drift():
    """An override that merely reorders the same options is not a difference."""
    design = {
        "field_type": "enum",
        "field_holds": "several",
        "field_options": _opts("a", "b", "c"),
    }
    a = _mem(state="present", override={"field_options": _opts("c", "a", "b")})
    rows = compute_member_rows(
        member_type="field", member_identifier="FLD-1", member_name="tags",
        design_obj=design, attributes=["field_options"],
        membership_a=a, membership_b=_mem(),
    )
    assert [r for r in rows if r["kind"] == "attribute"] == []


def test_compute_properties_includes_option_set_and_flags_difference():
    """The per-field properties view (REQ-433) shows field_options and marks it
    differing only on a real set difference."""
    design = {"field_type": "enum", "field_options": _opts("a", "b")}
    a = _mem(state="drifted", override={"field_options": _opts("a")})  # removed b
    out = compute_member_properties(
        member_type="field", member_identifier="FLD-1", member_name="status",
        design_obj=design, membership_a=a, membership_b=_mem(),
    )
    opt_row = next(r for r in out["rows"] if r["attribute"] == "field_options")
    assert opt_row["differs"] is True
    # a field with matching options elsewhere reads as not differing
    design2 = {"field_type": "enum", "field_options": _opts("a", "b")}
    out2 = compute_member_properties(
        member_type="field", member_identifier="FLD-2", member_name="kind",
        design_obj=design2, membership_a=_mem(), membership_b=_mem(),
    )
    opt_row2 = next(r for r in out2["rows"] if r["attribute"] == "field_options")
    assert opt_row2["differs"] is False


# --- REQ-443: relationship (association) actionability -----------------------

def test_association_presence_row_is_actionable():
    """A relationship the design defines but an instance lacks yields a presence
    row that is actionable (publishable), unlike other member types."""
    rows = compute_member_rows(
        member_type="association", member_identifier="ASN-1", member_name="clientContact",
        design_obj={"association_cardinality": "many_to_one"},
        attributes=[], membership_a=_mem(), membership_b=_mem(state="absent"),
    )
    pres = [r for r in rows if r["kind"] == "presence"]
    assert len(pres) == 1
    assert pres[0]["actionable"] is True


def test_field_presence_row_stays_non_actionable():
    """Only relationships get targeted presence-push; a missing field's presence
    row remains view-only (brought over by the whole-entity promote)."""
    rows = compute_member_rows(
        member_type="field", member_identifier="FLD-1", member_name="phone",
        design_obj={"field_type": "varchar"},
        attributes=[], membership_a=_mem(), membership_b=_mem(state="absent"),
    )
    assert rows[0]["kind"] == "presence"
    assert rows[0]["actionable"] is False


def test_association_cardinality_attribute_is_actionable():
    a = _mem(state="drifted", override={"association_cardinality": "many_to_many"})
    rows = compute_member_rows(
        member_type="association", member_identifier="ASN-1", member_name="mentorProfile",
        design_obj={"association_cardinality": "many_to_one"},
        attributes=["association_cardinality"], membership_a=a, membership_b=_mem(),
    )
    attr = [r for r in rows if r["kind"] == "attribute"]
    assert len(attr) == 1
    assert attr[0]["attribute"] == "association_cardinality"
    assert attr[0]["actionable"] is True


# --- REQ-447: view a matching enum field's option values ----------------------

def test_matching_enum_shows_expandable_options_with_show_all():
    """An in-sync enum field, in show-all mode, still yields exactly one expandable
    (non-differing, not-actionable) field_options row (REQ-447) — now emitted by the
    general property sweep rather than the differences-only carve-out. Under REQ-478
    it sits alongside the member's presence anchor instead of replacing it."""
    design = {"field_type": "enum", "field_options": _opts("a", "b")}
    rows = compute_member_rows(
        member_type="field", member_identifier="FLD-1", member_name="status",
        design_obj=design, attributes=[],
        membership_a=_mem(), membership_b=_mem(), include_unchanged=True,
    )
    opt = [r for r in rows if r["attribute"] == "field_options"]
    assert len(opt) == 1
    assert opt[0]["differs"] is False
    assert opt[0]["actionable"] is False
    assert opt[0]["design"] == design["field_options"]
    assert [r["kind"] for r in rows].count("presence") == 1


def test_matching_enum_hidden_without_show_all():
    """Differences-only view stays clean: a fully in-sync enum field yields no rows."""
    design = {"field_type": "enum", "field_options": _opts("a", "b")}
    rows = compute_member_rows(
        member_type="field", member_identifier="FLD-1", member_name="status",
        design_obj=design, attributes=[], membership_a=_mem(), membership_b=_mem(),
    )
    assert rows == []


def test_enum_field_with_other_diff_also_exposes_options():
    """An enum field shown for a non-option difference also gets an expandable
    options view row so its values can be confirmed."""
    design = {"field_type": "enum", "field_options": _opts("a", "b"), "field_required": False}
    a = _mem(state="drifted", override={"field_required": True})
    rows = compute_member_rows(
        member_type="field", member_identifier="FLD-1", member_name="status",
        design_obj=design, attributes=["field_required"], membership_a=a, membership_b=_mem(),
    )
    attrs = {r["attribute"] for r in rows}
    assert "field_required" in attrs
    opt = next(r for r in rows if r["attribute"] == "field_options")
    assert opt["differs"] is False and opt["actionable"] is False


def test_enum_with_option_diff_not_double_rowed():
    """A real option difference still produces exactly one field_options row (the
    diff row), not an extra view row."""
    design = {"field_type": "enum", "field_options": _opts("a", "b")}
    a = _mem(state="drifted", override={"field_options": _opts("a", "b", "c")})
    rows = compute_member_rows(
        member_type="field", member_identifier="FLD-1", member_name="status",
        design_obj=design, attributes=["field_options"],
        membership_a=a, membership_b=_mem(), include_unchanged=True,
    )
    opt = [r for r in rows if r["attribute"] == "field_options"]
    assert len(opt) == 1 and opt[0]["differs"] is True


def test_non_enum_field_gets_presence_anchor_and_its_values_in_show_all():
    """A non-enum in-sync field keeps its present-everywhere anchor row and, under
    REQ-478, carries its property values behind it — no option children, since it
    has no option set."""
    rows = compute_member_rows(
        member_type="field", member_identifier="FLD-1", member_name="phone",
        design_obj={"field_type": "varchar"}, attributes=[],
        membership_a=_mem(), membership_b=_mem(), include_unchanged=True,
    )
    assert rows[0]["kind"] == "presence"
    assert [r["attribute"] for r in rows[1:]] == ["field_type"]
    assert not any(r["attribute"] == "field_options" for r in rows)


# --- REQ-478: show-all shows values in every section --------------------------

def test_show_all_settings_section_carries_entity_setting_values(v2_env):
    """The reported defect, end to end: with show-all on, the 'settings' section
    must carry the entity's actual setting values, not just a presence row.

    Entity-level settings are almost never overridden per instance, so under the
    old override-keyed attribute set this section rendered one bare
    present/present/present row per entity and no values at all.
    """
    with session_scope() as s:
        a = _inst(s, "alpha", "source")
        b = _inst(s, "beta", "target")
        eid = entity_repo.create_entity(s, name="Account", description="x")[
            "entity_identifier"
        ]
        # in sync everywhere, nothing overridden — the case that used to show nothing
        for inst in (a, b):
            mb.upsert_membership(
                s, instance_identifier=inst, member_type="entity",
                member_identifier=eid, state="present",
            )

        plain = three_way_compare(s, instance_a=a, instance_b=b)
        assert not any(g["entity_identifier"] == eid for g in plain["groups"]), (
            "differences-only must stay clean for an in-sync entity"
        )

        result = three_way_compare(
            s, instance_a=a, instance_b=b, include_unchanged=True
        )
        grp = next(g for g in result["groups"] if g["entity_identifier"] == eid)
        settings = next(
            og for og in grp["object_groups"] if og["object_type"] == "settings"
        )
        attrs = {r["attribute"] for r in settings["rows"] if r["kind"] == "attribute"}
        # Compared attributes carry through with their values; identity and
        # excluded attributes are ruled out of the comparison surface
        # (REQ-490 / PI-409 — DEC-928 rows govern).
        assert "entity_track_activity" in attrs
        assert "entity_default_sort_field" in attrs
        assert "entity_name" not in attrs and "entity_description" not in attrs
        assert settings["differing_count"] == 0
        # values, not presence tokens
        flag_row = next(
            r for r in settings["rows"]
            if r["attribute"] == "entity_track_activity"
        )
        assert flag_row["design"] is False
        assert flag_row["instance_a"] is False
        assert flag_row["instance_b"] is False
        assert flag_row["differs"] is False


def test_show_all_fields_section_carries_field_values(v2_env):
    """Same guarantee for the fields section: every field's properties come
    through with their values, not a single membership row."""
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
        for inst in (a, b):
            for mtype, mid in (("entity", eid), ("field", fid)):
                mb.upsert_membership(
                    s, instance_identifier=inst, member_type=mtype,
                    member_identifier=mid, state="present",
                )

        result = three_way_compare(
            s, instance_a=a, instance_b=b, include_unchanged=True
        )
        grp = next(g for g in result["groups"] if g["entity_identifier"] == eid)
        fields = next(
            og for og in grp["object_groups"] if og["object_type"] == "fields"
        )
        type_row = next(r for r in fields["rows"] if r["attribute"] == "field_type")
        assert type_row["design"] == "text"
        assert type_row["instance_a"] == "text"
        assert type_row["instance_b"] == "text"
        assert fields["differing_count"] == 0
        # the presence anchor is still there, so the member is listed as existing
        assert any(r["kind"] == "presence" for r in fields["rows"])


# --- REQ-479: per-direction capability ----------------------------------------

def test_activity_tracking_entity_settings_are_reconcilable():
    """The reported defect: capturing PartnerProfile's tracks-activities setting
    from an instance into the design was refused, though patch_entity accepts
    tracks_activities and the EspoCRM adapter consumes it for the BasePlus base
    type. Both activity-tracking flags are reconcilable in both directions."""
    for attr in ("entity_track_activity", "entity_tracks_activities"):
        a = _mem(state="drifted", override={attr: True})
        rows = compute_member_rows(
            member_type="entity", member_identifier="ENT-1",
            member_name="PartnerProfile", design_obj={attr: False},
            attributes=[attr], membership_a=a, membership_b=_mem(),
        )
        row = next(r for r in rows if r["attribute"] == attr)
        assert row["capturable"] is True, attr
        assert row["publishable"] is True, attr
        assert row["actionable"] is True, attr


def test_an_excluded_entity_attribute_yields_no_row_at_all():
    """PI-409 / REQ-490: an attribute the declaration excludes (entity_notes is
    authoring prose, DEC-928) is never examined — however it got into the
    candidate list, it produces no comparison row and can never be drift."""
    a = _mem(state="drifted", override={"entity_notes": "x"})
    rows = compute_member_rows(
        member_type="entity", member_identifier="ENT-1", member_name="PartnerProfile",
        design_obj={"entity_notes": "y"}, attributes=["entity_notes"],
        membership_a=a, membership_b=_mem(),
    )
    assert [r for r in rows if r["kind"] == "attribute"] == []


def test_association_cardinality_is_capture_only():
    """REQ-443 direction limit, now expressed on the row rather than only inside
    the apply router: the deploy engine cannot alter an existing link's
    cardinality, so it can be captured but never published."""
    a = _mem(state="drifted", override={"association_cardinality": "many_to_many"})
    rows = compute_member_rows(
        member_type="association", member_identifier="ASN-1", member_name="clientContact",
        design_obj={"association_cardinality": "one_to_many"},
        attributes=["association_cardinality"], membership_a=a, membership_b=_mem(),
    )
    row = next(r for r in rows if r["attribute"] == "association_cardinality")
    assert row["capturable"] is True
    assert row["publishable"] is False
    assert row["actionable"] is True


def test_association_presence_is_publish_only():
    """A relationship the design defines but an instance lacks is published to
    create the link; there is nothing to capture back."""
    rows = compute_member_rows(
        member_type="association", member_identifier="ASN-1", member_name="clientContact",
        design_obj={}, attributes=[],
        membership_a=_mem(state="absent"), membership_b=_mem(),
    )
    row = next(r for r in rows if r["kind"] == "presence")
    assert row["capturable"] is False
    assert row["publishable"] is True


def test_agreeing_property_is_actionable_in_neither_direction():
    """A show-all verification row offers no action either way (REQ-478)."""
    rows = compute_member_rows(
        member_type="field", member_identifier="FLD-1", member_name="phone",
        design_obj={"field_type": "varchar"}, attributes=[],
        membership_a=_mem(), membership_b=_mem(), include_unchanged=True,
    )
    for row in rows:
        assert row["capturable"] is False and row["publishable"] is False


# --- non-entity members become actionable (PI-416 / PI-417 — REQ-519) -------

def _global_member_row(member_type, attribute, instance_value, design_value):
    a = _mem(state="drifted", override={attribute: instance_value})
    rows = compute_member_rows(
        member_type=member_type, member_identifier="X-1", member_name="Thing",
        design_obj={attribute: design_value}, attributes=[attribute],
        membership_a=a, membership_b=_mem(),
    )
    return next(r for r in rows if r["attribute"] == attribute)


def test_a_filtered_tab_attribute_is_writable_both_ways():
    """REQ-519 / PI-417: what kept publish closed for a filtered tab was the
    emitter rendering no ``filteredTabs:`` block, never the engine. The block
    now emits with the tab's entity, so the row publishes like a field's."""
    row = _global_member_row(
        "filtered_tab", "filtered_tab_label", "My Clients", "Clients"
    )
    assert row["capturable"] is True
    assert row["publishable"] is True
    assert row["actionable"] is True


def test_a_missing_filtered_tab_is_brought_over_by_its_entity_not_pushed_alone():
    """A filtered tab belongs to an entity, so a whole-entity promote reaches
    it — the presence row stays view-only like a field's, unlike a role or
    team, which no promote would ever carry."""
    from crmbuilder_v2.access import reconcile_compare

    assert reconcile_compare._presence_capabilities("filtered_tab") == (
        False, False,
    )
    assert reconcile_compare._presence_capabilities("role") == (False, True)


def test_a_role_attribute_publishes_now_that_the_security_program_exists():
    """PI-417 / DEC-998: what closed the publish direction was the emitter, not
    the engine — one generated program was one entity, and a role belongs to
    none. The entity-less security program gives roles and teams somewhere to be
    written, so both directions open."""
    row = _global_member_row(
        "role", "role_system_permissions",
        {"exportPermission": "no"}, {"exportPermission": "not-set"},
    )
    assert row["capturable"] is True
    assert row["publishable"] is True
    assert row["actionable"] is True


@pytest.mark.parametrize("member_type", ["role", "team"])
def test_a_role_or_team_the_instance_lacks_can_be_pushed(member_type):
    """A team carries no compared attribute of its own — DEC-928 excluded its
    description and its name is the match key — so presence is the only
    difference it can have. No whole-entity promote reaches it either, since it
    belongs to no entity; the security program is the only way it gets there."""
    rows = compute_member_rows(
        member_type=member_type, member_identifier="X-1", member_name="Thing",
        design_obj={}, attributes=[],
        membership_a=_mem(state="absent"), membership_b=_mem(),
    )
    row = next(r for r in rows if r["kind"] == "presence")
    assert row["capturable"] is False
    assert row["publishable"] is True


def test_layout_attributes_stay_view_only():
    """REQ-520: a layout is not in the capturable set — its variants bound to a
    portal or a role have no mechanism to set, and the whole type stays
    non-actionable until that subset can be told apart."""
    a = _mem(state="drifted", override={"layout_rows": ["name"]})
    rows = compute_member_rows(
        member_type="layout", member_identifier="LAY-1", member_name="detailLayout",
        design_obj={"layout_rows": ["name", "phone"]}, attributes=["layout_rows"],
        membership_a=a, membership_b=_mem(),
    )
    row = rows[0]
    assert row["capturable"] is False and row["publishable"] is False


# --- undeclared vs drifted (PI-414 — REQ-513 / DEC-938 / DEC-940) -----------

def _one_attr(design_obj, attribute, instance_value, member_type="entity"):
    rows = compute_member_rows(
        member_type=member_type, member_identifier="X-1", member_name="Contact",
        design_obj=design_obj, attributes=[attribute],
        membership_a=_mem(state="drifted", override={attribute: instance_value}),
        membership_b=_mem(),
    )
    return next(r for r in rows if r["kind"] == "attribute")


def test_attribute_the_design_never_declared_is_unknown_naming_the_design():
    """REQ-513: the design says nothing and the CRM returns its own default. That
    is not the instance disagreeing — it is the design being unfinished, and the
    reason must say so, because the remedies are opposite."""
    row = _one_attr({"entity_default_sort_field": None},
                    "entity_default_sort_field", "createdAt")
    assert row["outcome"] == "unknown"
    assert row["reason"] == "undeclared_in_design"


def test_undeclared_attribute_still_counts_against_conformance():
    """REQ-513: unknown is not clean. The row is emitted and still differs, so an
    instance carrying an undeclared compared attribute is never reported
    conformant — it is only reported for a different reason."""
    row = _one_attr({"entity_default_sort_field": None},
                    "entity_default_sort_field", "createdAt")
    assert row["differs"] is True


def test_declared_attribute_that_disagrees_is_drift_with_no_reason():
    """The design states a value and the instance holds another: a real
    disagreement, and nothing to explain."""
    row = _one_attr({"entity_default_sort_field": "name"},
                    "entity_default_sort_field", "createdAt")
    assert row["outcome"] == "drift"
    assert row["reason"] is None


def test_fixed_values_field_listing_no_options_is_drift_not_unknown():
    """DEC-940 amends DEC-938 for exactly this case: a field declared to hold
    fixed values while listing none is a declared attribute in an invalid state,
    not an undeclared one. An unknown would say nobody can tell; drift says
    something is wrong."""
    row = _one_attr(
        {"field_values": "fixed", "field_options": []},
        "field_options", [{"option_value": "a", "option_label": "A"}],
        member_type="field",
    )
    assert row["outcome"] == "drift"


def test_fixed_values_listing_none_is_drift_even_when_the_instance_agrees():
    """REQ-516: the field is unusable on either side, so agreement on emptiness
    is not conformance. The row must be emitted in differences-only mode, not
    swallowed by the everything-agrees short-circuit."""
    rows = compute_member_rows(
        member_type="field", member_identifier="FLD-1", member_name="stage",
        design_obj={"field_values": "fixed", "field_options": []},
        attributes=["field_options"],
        membership_a=_mem(), membership_b=_mem(),
    )
    row = next(r for r in rows if r["kind"] == "attribute")
    assert row["outcome"] == "drift"
    assert row["differs"] is True


def test_the_both_sides_empty_fixed_set_offers_no_action():
    """Nothing exists to capture or publish — the remedy is finishing the
    design's option list, so batch apply must not be offered a no-op."""
    rows = compute_member_rows(
        member_type="field", member_identifier="FLD-1", member_name="stage",
        design_obj={"field_values": "fixed", "field_options": []},
        attributes=["field_options"],
        membership_a=_mem(), membership_b=_mem(),
    )
    row = next(r for r in rows if r["kind"] == "attribute")
    assert row["capturable"] is False
    assert row["publishable"] is False
    assert row["actionable"] is False


def test_an_open_values_field_listing_none_is_not_drift():
    """The empty-fixed rule keys on ``fixed`` — an open field with no listed
    options is a perfectly usable free-value field and stays a match."""
    rows = compute_member_rows(
        member_type="field", member_identifier="FLD-1", member_name="tags",
        design_obj={"field_values": "open", "field_options": []},
        attributes=["field_options"],
        membership_a=_mem(), membership_b=_mem(), include_unchanged=True,
    )
    row = next(r for r in rows if r["kind"] == "attribute")
    assert row["outcome"] == "match"


def test_a_declared_false_is_a_declaration_not_an_absence():
    """``False``, ``0`` and ``""`` are things the design says. Testing
    truthiness rather than ``is None`` would sweep them into unknown and hide
    real drift behind an unfinished-design label."""
    row = _one_attr({"field_required": False}, "field_required", True,
                    member_type="field")
    assert row["outcome"] == "drift"


def test_agreeing_attribute_is_a_match_when_shown():
    """Under show-all an in-sync property is a match, distinct from both drift
    and unknown."""
    rows = compute_member_rows(
        member_type="entity", member_identifier="ENT-1", member_name="Contact",
        design_obj={"entity_default_sort_field": "name"},
        attributes=["entity_default_sort_field"],
        membership_a=_mem(), membership_b=_mem(), include_unchanged=True,
    )
    row = next(r for r in rows if r["kind"] == "attribute")
    assert row["outcome"] == "match"
    assert row["differs"] is False


# --- Governed system settings (PI-406 / REQ-485) -----------------------------

from crmbuilder_v2.access.reconcile_compare import (  # noqa: E402
    member_property_compare,
)
from crmbuilder_v2.access.repositories import (  # noqa: E402
    system_settings as settings_repo,
)


def _setting(s, *, key="orgName", name="Organization name"):
    return settings_repo.create_system_setting(
        s, key=key, name=name, value_type="text", status="confirmed"
    )["system_setting_identifier"]


def _declare(s, sid, iid, value):
    settings_repo.set_value(
        s, system_setting_identifier=sid, instance_identifier=iid, value=value
    )


def _setting_rows(result):
    grp = next(
        (g for g in result["groups"] if g["entity_identifier"] is None), None
    )
    if grp is None:
        return []
    return [r for r in grp["rows"] if r["member_type"] == "system_setting"]


def test_a_setting_drifting_from_its_own_declared_value_is_drift(v2_env):
    """Each instance compares against ITS declared value: A holds its value,
    B holds something else — the row is drift even though A matches."""
    with session_scope() as s:
        a = _inst(s, "alpha2", "both")
        b = _inst(s, "beta2", "both")
        sid = _setting(s)
        _declare(s, sid, a, "Cleveland")
        _declare(s, sid, b, "Akron")
        mb.upsert_membership(
            s, instance_identifier=a, member_type="system_setting",
            member_identifier=sid, state="present",
        )
        mb.upsert_membership(
            s, instance_identifier=b, member_type="system_setting",
            member_identifier=sid, state="drifted",
            override={"value": "Canton"},
        )
        rows = _setting_rows(three_way_compare(s, instance_a=a, instance_b=b))
        row = next(r for r in rows if r["kind"] == "attribute")
        assert row["outcome"] == "drift"
        assert row["differs"] is True
        assert row["instance_a"] == "Cleveland"
        assert row["instance_b"] == "Canton"
        # Per-instance declared values render keyed by instance.
        assert row["design"] == {a: "Cleveland", b: "Akron"}
        assert row["actionable"] is False


def test_an_undeclared_value_is_not_captured_never_conformant(v2_env):
    """REQ-485: the design declares nothing for this instance, and whatever the
    instance holds must not read as conformant."""
    with session_scope() as s:
        a = _inst(s, "alpha3", "both")
        b = _inst(s, "beta3", "both")
        sid = _setting(s)
        mb.upsert_membership(
            s, instance_identifier=a, member_type="system_setting",
            member_identifier=sid, state="present",
            override={"value": "Cleveland"},
        )
        rows = _setting_rows(three_way_compare(s, instance_a=a, instance_b=b))
        row = next(r for r in rows if r["kind"] == "attribute")
        assert row["outcome"] == "unknown"
        assert row["reason"] == "undeclared_in_design"
        assert row["differs"] is True


def test_a_setting_held_at_its_declared_value_everywhere_is_quiet(v2_env):
    with session_scope() as s:
        a = _inst(s, "alpha4", "both")
        b = _inst(s, "beta4", "both")
        sid = _setting(s)
        _declare(s, sid, a, "Cleveland")
        _declare(s, sid, b, "Akron")
        for iid in (a, b):
            mb.upsert_membership(
                s, instance_identifier=iid, member_type="system_setting",
                member_identifier=sid, state="present",
            )
        rows = _setting_rows(three_way_compare(s, instance_a=a, instance_b=b))
        assert rows == []


def test_a_declared_value_the_instance_lacks_is_drift(v2_env):
    with session_scope() as s:
        a = _inst(s, "alpha5", "both")
        b = _inst(s, "beta5", "both")
        sid = _setting(s)
        _declare(s, sid, a, "Cleveland")
        mb.upsert_membership(
            s, instance_identifier=a, member_type="system_setting",
            member_identifier=sid, state="absent",
        )
        rows = _setting_rows(three_way_compare(s, instance_a=a, instance_b=b))
        row = next(r for r in rows if r["kind"] == "attribute")
        assert row["outcome"] == "drift"


def test_setting_rows_bucket_under_settings_in_the_global_group(v2_env):
    with session_scope() as s:
        a = _inst(s, "alpha6", "both")
        b = _inst(s, "beta6", "both")
        sid = _setting(s)
        _declare(s, sid, a, "Cleveland")
        mb.upsert_membership(
            s, instance_identifier=a, member_type="system_setting",
            member_identifier=sid, state="drifted", override={"value": "X"},
        )
        result = three_way_compare(s, instance_a=a, instance_b=b)
        grp = next(g for g in result["groups"] if g["entity_identifier"] is None)
        og = next(o for o in grp["object_groups"] if o["object_type"] == "settings")
        assert any(r["member_type"] == "system_setting" for r in og["rows"])


def test_setting_member_drill_compares_per_instance(v2_env):
    with session_scope() as s:
        a = _inst(s, "alpha7", "both")
        b = _inst(s, "beta7", "both")
        sid = _setting(s)
        _declare(s, sid, a, "Cleveland")
        mb.upsert_membership(
            s, instance_identifier=a, member_type="system_setting",
            member_identifier=sid, state="present",
        )
        drill = member_property_compare(
            s, instance_a=a, instance_b=b,
            member_type="system_setting", member_identifier=sid,
        )
        assert drill is not None
        assert drill["presence"]["design"] == "present"
        assert drill["presence"]["instance_a"] == "present"
        assert drill["presence"]["instance_b"] == "unknown"
        assert [r["attribute"] for r in drill["rows"]] == ["value"]


def test_settings_stay_out_of_an_entity_drill(v2_env):
    with session_scope() as s:
        a = _inst(s, "alpha8", "both")
        b = _inst(s, "beta8", "both")
        eid = entity_repo.create_entity(s, name="Widget", description="x")[
            "entity_identifier"
        ]
        sid = _setting(s)
        _declare(s, sid, a, "Cleveland")
        mb.upsert_membership(
            s, instance_identifier=a, member_type="system_setting",
            member_identifier=sid, state="drifted", override={"value": "X"},
        )
        drill = three_way_compare(
            s, instance_a=a, instance_b=b, entity_identifier=eid
        )
        assert _setting_rows(drill) == []


# --- Declared compared set through the surface (PI-409 / REQ-490) ------------


def test_an_excluded_attribute_never_produces_drift(v2_env):
    """DEC-928 excludes team_description; an old audit override on it must
    stop reading as drift — never examined, never drift."""
    with session_scope() as s:
        from crmbuilder_v2.access.repositories import teams as team_repo
        a = _inst(s, "alpha9", "both")
        b = _inst(s, "beta9", "both")
        tid = team_repo.create_team(
            s, name="Mentors", description="The mentors."
        )["team_identifier"]
        mb.upsert_membership(
            s, instance_identifier=a, member_type="team", member_identifier=tid,
            state="drifted", override={"team_description": "Something else."},
        )
        mb.upsert_membership(
            s, instance_identifier=b, member_type="team", member_identifier=tid,
            state="present",
        )
        result = three_way_compare(s, instance_a=a, instance_b=b)
        team_rows = [
            r for g in result["groups"] for r in g["rows"]
            if r["member_type"] == "team" and r["kind"] == "attribute"
        ]
        assert team_rows == []


def test_a_label_differing_only_by_edge_whitespace_is_not_drift():
    """DEC-928: labels compare str-trim."""
    row_present = compute_member_rows(
        member_type="entity", member_identifier="ENT-1", member_name="Mentor",
        design_obj={"entity_label": "Mentor"},
        attributes=["entity_label"],
        membership_a=_mem(state="drifted", override={"entity_label": " Mentor "}),
        membership_b=_mem(),
    )
    assert [r for r in row_present if r["kind"] == "attribute"] == []


def test_text_filter_fields_compare_as_an_unordered_set():
    rows = compute_member_rows(
        member_type="entity", member_identifier="ENT-1", member_name="Mentor",
        design_obj={"entity_text_filter_fields": ["name", "email"]},
        attributes=["entity_text_filter_fields"],
        membership_a=_mem(
            state="drifted",
            override={"entity_text_filter_fields": ["email", "name"]},
        ),
        membership_b=_mem(),
    )
    assert [r for r in rows if r["kind"] == "attribute"] == []


def test_layout_content_order_is_drift():
    rows = compute_member_rows(
        member_type="layout", member_identifier="LAY-1", member_name="list",
        design_obj={"layout_content": ["name", "email"]},
        attributes=["layout_content"],
        membership_a=_mem(
            state="drifted", override={"layout_content": ["email", "name"]}
        ),
        membership_b=_mem(),
    )
    row = next(r for r in rows if r["kind"] == "attribute")
    assert row["outcome"] == "drift"

"""Unit tests for the three-way comparison core — PI-316 (REL-024)."""

from __future__ import annotations

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


def test_include_unchanged_emits_present_everywhere_row():
    """REQ-432: with include_unchanged, an in-sync member yields one
    present-everywhere confirmation row (differs=False) so it can be verified."""
    rows = compute_member_rows(
        member_type="field",
        member_identifier="FLD-1",
        member_name="phone",
        design_obj={"field_type": "varchar"},
        attributes=[],
        membership_a=_mem(),
        membership_b=_mem(),
        include_unchanged=True,
    )
    assert len(rows) == 1
    r = rows[0]
    assert r["kind"] == "presence"
    assert r["differs"] is False
    assert r["actionable"] is False
    assert r["design"] == PRESENT
    assert r["instance_a"] == PRESENT
    assert r["instance_b"] == PRESENT


def test_include_unchanged_does_not_add_row_when_member_differs():
    """A member that already differs keeps only its diff rows — no extra in-sync
    row is appended even when include_unchanged is set."""
    a = _mem(state="drifted", override={"field_type": "text"})
    rows = compute_member_rows(
        member_type="field",
        member_identifier="FLD-1",
        member_name="notes",
        design_obj={"field_type": "varchar"},
        attributes=_override_attrs(a, _mem()),
        membership_a=a,
        membership_b=_mem(),
        include_unchanged=True,
    )
    assert len(rows) == 1
    assert rows[0]["differs"] is True


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


# --- REQ-442: enum / multi_enum field option-value reconciliation -------------


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
    design = {"field_type": "multi_enum", "field_options": _opts("a", "b", "c")}
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

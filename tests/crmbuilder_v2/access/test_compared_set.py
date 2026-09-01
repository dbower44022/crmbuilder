"""The compared-set declaration and its rule engine — PI-409 (REQ-490, DEC-928/989).

Pins the declaration's shape against the approved table, the mechanical rule
engine, and the coverage guarantee that every attribute the audit writes into
an override is declared — an undeclared audited attribute would silently fall
back to exact comparison, which is the run-time inference REQ-490 retires.
"""

from __future__ import annotations

from crmbuilder_v2.access import compared_set as cs


# --- declaration shape -------------------------------------------------------


def test_the_dec_928_tally_holds_for_the_original_constructs():
    """DEC-928: 30 compared, 9 identity, 34 excluded across the seven original
    member types. Post-DEC-928 constructs are additive and counted apart."""
    original = (
        "entity", "field", "association", "layout", "role", "team",
        "filtered_tab",
    )
    post_928 = {
        # entity: PI-422 / PI-424
        "entity_base_type", "entity_icon", "entity_color",
        "entity_status_field", "entity_kanban_view", "entity_count_disabled",
        "entity_optimistic_concurrency", "entity_multiple_assigned_users",
        "entity_formula_scripts",
        # field: PI-414 qualifiers, PI-425, the REQ-442 options collection
        "field_display", "field_values", "field_holds", "field_supplied_by",
        "field_built_in", "field_options",
    }
    tally = {"compared": 0, "identity": 0, "excluded": 0}
    for member_type in original:
        for attribute, decl in cs.COMPARED_SET[member_type].items():
            if attribute in post_928:
                continue
            tally[decl.disposition] += 1
    # The counts pin the approved TABLE ROWS, which are the decision's
    # substance (the document's summary tally box disagrees with its own
    # rows and was arithmetic garnish, not a ruling). One excluded row —
    # field_externally_populated — left the table when its column was
    # retired (PI-414 subtractive half).
    assert tally == {"compared": 33, "identity": 8, "excluded": 31}


def test_every_rule_token_is_vocabulary():
    for member_type, attributes in cs.COMPARED_SET.items():
        for attribute, decl in attributes.items():
            if decl.disposition == cs.COMPARED:
                assert decl.rule in cs.EQUALITY_RULES, (member_type, attribute)
            if decl.disposition == cs.IDENTITY:
                assert decl.rule == cs.JOIN_KEY


def test_every_audited_override_attribute_is_declared():
    """The audit's writable attribute inventory must be covered — an audited
    attribute without a declaration would compare by inference (REQ-490)."""
    from crmbuilder_v2.introspect import reconcile as introspect

    audited = {
        "entity": set(introspect._audited_entity_attrs({}).keys()),
        "field": (
            set(introspect._FIELD_BOOL_ATTRS)
            | set(introspect._FIELD_VALUE_ATTR_KEYS)
            | set(introspect._FIELD_QUALIFIER_ATTRS)
            | {"field_type", "field_options"}
        ),
        "association": {"association_cardinality"},
        "layout": {"layout_content"},
        "role": {"role_scope_access", "role_system_permissions"},
        "team": {"team_description"},
        "filtered_tab": {"filtered_tab_filter", "filtered_tab_label"},
        "message_template": {
            f"message_template_{k}"
            for k in introspect._MESSAGE_TEMPLATE_COMPARED
        },
        "rule": {"rule_condition"},
        "system_setting": {"value"},
    }
    for member_type, attributes in audited.items():
        for attribute in attributes:
            assert cs.declaration_for(member_type, attribute) is not None, (
                member_type, attribute,
            )


def test_the_serialized_form_mirrors_the_engine():
    served = cs.serialized()
    assert set(served) == set(cs.COMPARED_SET)
    row = next(
        r for r in served["entity"] if r["attribute"] == "entity_label"
    )
    assert row["disposition"] == "compared"
    assert row["rule"] == "str-trim"


# --- the rule engine ---------------------------------------------------------


def test_absent_and_empty_are_different_everywhere():
    """DEC-928's global null policy."""
    for rule in sorted(cs.EQUALITY_RULES):
        assert cs.values_equal(rule, None, None) is True
        assert cs.values_equal(rule, None, "") is False, rule
        assert cs.values_equal(rule, None, 0) is False, rule


def test_str_trim_ignores_edges_and_keeps_case():
    assert cs.values_equal(cs.STR_TRIM, "  Mentor ", "Mentor")
    assert not cs.values_equal(cs.STR_TRIM, "mentor", "Mentor")


def test_int_absent_is_not_zero():
    assert cs.values_equal(cs.INT, 4, "4")
    assert not cs.values_equal(cs.INT, None, 0)


def test_set_ignores_order_and_seq_does_not():
    assert cs.values_equal(cs.SET, ["a", "b"], ["b", "a"])
    assert not cs.values_equal(cs.SEQ, ["a", "b"], ["b", "a"])
    assert cs.values_equal(cs.SEQ, ["a", "b"], ["a", "b"])


def test_canonical_ignores_key_order_but_not_meaning():
    a = {"all": [{"field": "x", "op": "eq", "value": 1}]}
    b = {"all": [{"value": 1, "op": "eq", "field": "x"}]}
    c = {"all": [{"field": "x", "op": "eq", "value": 2}]}
    assert cs.values_equal(cs.CANONICAL, a, b)
    assert not cs.values_equal(cs.CANONICAL, a, c)


def test_map_compares_key_wise():
    assert cs.values_equal(cs.MAP, {"a": 1, "b": 2}, {"b": 2, "a": 1})
    assert not cs.values_equal(cs.MAP, {"a": 1}, {"a": 2})


def test_attr_equal_applies_the_declared_rule():
    assert cs.attr_equal("entity", "entity_label", " Mentors ", "Mentors")
    assert cs.attr_equal(
        "entity", "entity_text_filter_fields", ["name", "email"],
        ["email", "name"],
    )
    assert not cs.attr_equal(
        "layout", "layout_content", ["name", "email"], ["email", "name"]
    )


def test_an_undeclared_attribute_falls_back_to_exact():
    assert cs.attr_equal("entity", "entity_never_heard_of", 1, 1)
    assert not cs.attr_equal("entity", "entity_never_heard_of", 1, 2)

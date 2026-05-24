"""Tests for the condition-expression parser, validator, evaluator, and renderer."""

import datetime

import pytest

from espo_impl.core.condition_expression import (
    _MISSING,
    ROLE_OPERATORS,
    AllNode,
    AnyNode,
    LeafClause,
    RoleClause,
    collect_unknown_fields,
    collect_unknown_roles,
    evaluate_condition,
    parse_condition,
    render_condition,
    validate_condition,
)

# ---------------------------------------------------------------------------
# Parsing — shorthand form
# ---------------------------------------------------------------------------


class TestParseShorthand:
    """Shorthand (flat list) parsing tests."""

    def test_single_clause(self):
        raw = [{"field": "status", "op": "equals", "value": "Active"}]
        result = parse_condition(raw)
        assert isinstance(result, AllNode)
        assert len(result.children) == 1
        leaf = result.children[0]
        assert isinstance(leaf, LeafClause)
        assert leaf.field == "status"
        assert leaf.op == "equals"
        assert leaf.value == "Active"

    def test_multi_clause(self):
        raw = [
            {"field": "contactType", "op": "contains", "value": "Mentor"},
            {"field": "mentorStatus", "op": "equals", "value": "Active"},
        ]
        result = parse_condition(raw)
        assert isinstance(result, AllNode)
        assert len(result.children) == 2

    def test_empty_list_rejected(self):
        with pytest.raises(ValueError, match="must not be empty"):
            parse_condition([])

    def test_non_dict_item_rejected(self):
        with pytest.raises(ValueError, match="must be a dict"):
            parse_condition(["not a dict"])


# ---------------------------------------------------------------------------
# Parsing — structured form
# ---------------------------------------------------------------------------


class TestParseStructured:
    """Structured (all/any) parsing tests."""

    def test_all_only(self):
        raw = {
            "all": [
                {"field": "a", "op": "equals", "value": 1},
                {"field": "b", "op": "equals", "value": 2},
            ]
        }
        result = parse_condition(raw)
        assert isinstance(result, AllNode)
        assert len(result.children) == 2

    def test_any_only(self):
        raw = {
            "any": [
                {"field": "a", "op": "equals", "value": 1},
                {"field": "b", "op": "equals", "value": 2},
            ]
        }
        result = parse_condition(raw)
        assert isinstance(result, AnyNode)
        assert len(result.children) == 2

    def test_nested_any_in_all(self):
        raw = {
            "all": [
                {"field": "a", "op": "equals", "value": 1},
                {
                    "any": [
                        {"field": "b", "op": "equals", "value": 2},
                        {"field": "b", "op": "equals", "value": 3},
                    ]
                },
            ]
        }
        result = parse_condition(raw)
        assert isinstance(result, AllNode)
        assert len(result.children) == 2
        assert isinstance(result.children[1], AnyNode)
        assert len(result.children[1].children) == 2

    def test_nested_all_in_any(self):
        raw = {
            "any": [
                {
                    "all": [
                        {"field": "a", "op": "equals", "value": 1},
                        {"field": "b", "op": "equals", "value": 2},
                    ]
                },
                {"field": "c", "op": "equals", "value": 3},
            ]
        }
        result = parse_condition(raw)
        assert isinstance(result, AnyNode)
        assert isinstance(result.children[0], AllNode)

    def test_deeply_nested(self):
        raw = {
            "all": [
                {
                    "any": [
                        {
                            "all": [
                                {"field": "x", "op": "equals", "value": 1},
                                {"field": "y", "op": "equals", "value": 2},
                            ]
                        },
                        {"field": "z", "op": "isNull"},
                    ]
                },
            ]
        }
        result = parse_condition(raw)
        assert isinstance(result, AllNode)
        inner_any = result.children[0]
        assert isinstance(inner_any, AnyNode)
        assert isinstance(inner_any.children[0], AllNode)

    def test_both_all_and_any_rejected(self):
        raw = {
            "all": [{"field": "a", "op": "equals", "value": 1}],
            "any": [{"field": "b", "op": "equals", "value": 2}],
        }
        with pytest.raises(ValueError, match="both 'all' and 'any'"):
            parse_condition(raw)

    def test_empty_all_rejected(self):
        with pytest.raises(ValueError, match="non-empty list"):
            parse_condition({"all": []})

    def test_empty_any_rejected(self):
        with pytest.raises(ValueError, match="non-empty list"):
            parse_condition({"any": []})

    def test_unknown_dict_keys_rejected(self):
        with pytest.raises(ValueError, match="'all', 'any', 'field', or 'role'"):
            parse_condition({"bogus": True})


# ---------------------------------------------------------------------------
# Parsing — leaf clause details
# ---------------------------------------------------------------------------


class TestParseLeaf:
    """Leaf clause parsing tests."""

    def test_missing_field_rejected(self):
        with pytest.raises(ValueError, match="'all', 'any', 'field', or 'role'"):
            parse_condition([{"op": "equals", "value": 1}])

    def test_missing_op_rejected(self):
        with pytest.raises(ValueError, match="non-empty string 'op'"):
            parse_condition([{"field": "a"}])

    def test_no_value_clause(self):
        """isNull/isNotNull parsed without value."""
        raw = [{"field": "a", "op": "isNull"}]
        result = parse_condition(raw)
        leaf = result.children[0]
        assert leaf.value is _MISSING

    def test_value_false_is_preserved(self):
        raw = [{"field": "active", "op": "equals", "value": False}]
        result = parse_condition(raw)
        assert result.children[0].value is False

    def test_value_none_is_preserved(self):
        raw = [{"field": "x", "op": "equals", "value": None}]
        result = parse_condition(raw)
        assert result.children[0].value is None

    def test_non_list_non_dict_input_rejected(self):
        with pytest.raises(ValueError, match="list.*or dict"):
            parse_condition("not valid")


# ---------------------------------------------------------------------------
# Validation — operator checks
# ---------------------------------------------------------------------------


class TestValidateOperators:
    """Operator validation tests."""

    FIELDS = {"status", "score", "contactType", "tags", "startDate", "notes"}

    def test_unknown_operator(self):
        parsed = parse_condition([{"field": "status", "op": "regex", "value": ".*"}])
        errors = validate_condition(parsed, self.FIELDS)
        assert any("Unknown operator 'regex'" in e for e in errors)

    def test_all_valid_operators_accepted(self):
        from espo_impl.core.condition_expression import OPERATORS

        for op in OPERATORS:
            if op in {"isNull", "isNotNull"}:
                raw = [{"field": "status", "op": op}]
            elif op in {"in", "notIn"}:
                raw = [{"field": "status", "op": op, "value": ["A"]}]
            elif op in {"lessThan", "greaterThan", "lessThanOrEqual",
                        "greaterThanOrEqual"}:
                raw = [{"field": "score", "op": op, "value": 10}]
            else:
                raw = [{"field": "status", "op": op, "value": "A"}]
            parsed = parse_condition(raw)
            errors = validate_condition(parsed, self.FIELDS)
            assert not errors, f"Operator '{op}' unexpectedly invalid: {errors}"


# ---------------------------------------------------------------------------
# Validation — value shape
# ---------------------------------------------------------------------------


class TestValidateValueShape:
    """Value shape validation per operator type."""

    FIELDS = {"status", "score", "startDate", "tags"}

    def test_in_requires_list(self):
        parsed = parse_condition([
            {"field": "status", "op": "in", "value": "Active"},
        ])
        errors = validate_condition(parsed, self.FIELDS)
        assert any("list" in e for e in errors)

    def test_not_in_requires_list(self):
        parsed = parse_condition([
            {"field": "status", "op": "notIn", "value": "Active"},
        ])
        errors = validate_condition(parsed, self.FIELDS)
        assert any("list" in e for e in errors)

    def test_in_with_list_valid(self):
        parsed = parse_condition([
            {"field": "status", "op": "in", "value": ["A", "B"]},
        ])
        errors = validate_condition(parsed, self.FIELDS)
        assert not errors

    def test_is_null_rejects_value(self):
        parsed = parse_condition([
            {"field": "status", "op": "isNull", "value": True},
        ])
        errors = validate_condition(parsed, self.FIELDS)
        assert any("must not include a 'value'" in e for e in errors)

    def test_is_not_null_rejects_value(self):
        parsed = parse_condition([
            {"field": "status", "op": "isNotNull", "value": True},
        ])
        errors = validate_condition(parsed, self.FIELDS)
        assert any("must not include a 'value'" in e for e in errors)

    def test_comparison_accepts_numeric(self):
        parsed = parse_condition([
            {"field": "score", "op": "greaterThan", "value": 10},
        ])
        errors = validate_condition(parsed, self.FIELDS)
        assert not errors

    def test_comparison_accepts_date_string(self):
        parsed = parse_condition([
            {"field": "startDate", "op": "lessThan", "value": "2026-01-01"},
        ])
        errors = validate_condition(parsed, self.FIELDS)
        assert not errors

    def test_comparison_accepts_relative_date(self):
        parsed = parse_condition([
            {"field": "startDate", "op": "greaterThanOrEqual", "value": "today"},
        ])
        errors = validate_condition(parsed, self.FIELDS)
        assert not errors

    def test_comparison_rejects_non_numeric_string(self):
        parsed = parse_condition([
            {"field": "score", "op": "lessThan", "value": "banana"},
        ])
        errors = validate_condition(parsed, self.FIELDS)
        assert any("numeric" in e for e in errors)

    def test_equals_requires_value(self):
        parsed = parse_condition([{"field": "status", "op": "equals"}])
        errors = validate_condition(parsed, self.FIELDS)
        assert any("requires a 'value'" in e for e in errors)

    def test_contains_requires_value(self):
        parsed = parse_condition([{"field": "tags", "op": "contains"}])
        errors = validate_condition(parsed, self.FIELDS)
        assert any("requires a 'value'" in e for e in errors)

    def test_comparison_requires_value(self):
        parsed = parse_condition([{"field": "score", "op": "greaterThan"}])
        errors = validate_condition(parsed, self.FIELDS)
        assert any("requires a 'value'" in e for e in errors)


# ---------------------------------------------------------------------------
# Validation — field references
# ---------------------------------------------------------------------------


class TestValidateFieldReferences:
    """Field-reference checking."""

    def test_known_field_passes(self):
        parsed = parse_condition([
            {"field": "status", "op": "equals", "value": "A"},
        ])
        errors = validate_condition(parsed, {"status"})
        assert not errors

    def test_unknown_field_fails(self):
        parsed = parse_condition([
            {"field": "bogus", "op": "equals", "value": "A"},
        ])
        errors = validate_condition(parsed, {"status"})
        assert any("'bogus' not found" in e for e in errors)

    def test_related_entity_field_scope(self):
        parsed = parse_condition([
            {"field": "relField", "op": "equals", "value": "X"},
        ])
        # relField not in entity fields, but in related fields
        errors = validate_condition(
            parsed,
            entity_field_names={"status"},
            related_entity_field_names={"relField"},
        )
        assert not errors

    def test_related_entity_field_missing(self):
        parsed = parse_condition([
            {"field": "unknown", "op": "equals", "value": "X"},
        ])
        errors = validate_condition(
            parsed,
            entity_field_names={"status"},
            related_entity_field_names={"relField"},
        )
        assert any("'unknown' not found in related entity" in e for e in errors)


# ---------------------------------------------------------------------------
# Evaluation — all operators
# ---------------------------------------------------------------------------


class TestEvaluateOperators:
    """Evaluation tests — at least one positive and one negative per operator."""

    def test_equals_true(self):
        p = parse_condition([{"field": "s", "op": "equals", "value": "A"}])
        assert evaluate_condition(p, {"s": "A"}) is True

    def test_equals_false(self):
        p = parse_condition([{"field": "s", "op": "equals", "value": "A"}])
        assert evaluate_condition(p, {"s": "B"}) is False

    def test_not_equals_true(self):
        p = parse_condition([{"field": "s", "op": "notEquals", "value": "A"}])
        assert evaluate_condition(p, {"s": "B"}) is True

    def test_not_equals_false(self):
        p = parse_condition([{"field": "s", "op": "notEquals", "value": "A"}])
        assert evaluate_condition(p, {"s": "A"}) is False

    def test_contains_list_true(self):
        p = parse_condition([{"field": "tags", "op": "contains", "value": "X"}])
        assert evaluate_condition(p, {"tags": ["X", "Y"]}) is True

    def test_contains_list_false(self):
        p = parse_condition([{"field": "tags", "op": "contains", "value": "Z"}])
        assert evaluate_condition(p, {"tags": ["X", "Y"]}) is False

    def test_contains_non_list_false(self):
        p = parse_condition([{"field": "tags", "op": "contains", "value": "X"}])
        assert evaluate_condition(p, {"tags": "X"}) is False

    def test_in_true(self):
        p = parse_condition([{"field": "s", "op": "in", "value": ["A", "B"]}])
        assert evaluate_condition(p, {"s": "A"}) is True

    def test_in_false(self):
        p = parse_condition([{"field": "s", "op": "in", "value": ["A", "B"]}])
        assert evaluate_condition(p, {"s": "C"}) is False

    def test_not_in_true(self):
        p = parse_condition([{"field": "s", "op": "notIn", "value": ["A", "B"]}])
        assert evaluate_condition(p, {"s": "C"}) is True

    def test_not_in_false(self):
        p = parse_condition([{"field": "s", "op": "notIn", "value": ["A", "B"]}])
        assert evaluate_condition(p, {"s": "A"}) is False

    def test_less_than_true(self):
        p = parse_condition([{"field": "n", "op": "lessThan", "value": 10}])
        assert evaluate_condition(p, {"n": 5}) is True

    def test_less_than_false(self):
        p = parse_condition([{"field": "n", "op": "lessThan", "value": 10}])
        assert evaluate_condition(p, {"n": 10}) is False

    def test_greater_than_true(self):
        p = parse_condition([{"field": "n", "op": "greaterThan", "value": 10}])
        assert evaluate_condition(p, {"n": 15}) is True

    def test_greater_than_false(self):
        p = parse_condition([{"field": "n", "op": "greaterThan", "value": 10}])
        assert evaluate_condition(p, {"n": 10}) is False

    def test_less_than_or_equal_true(self):
        p = parse_condition([{"field": "n", "op": "lessThanOrEqual", "value": 10}])
        assert evaluate_condition(p, {"n": 10}) is True

    def test_less_than_or_equal_false(self):
        p = parse_condition([{"field": "n", "op": "lessThanOrEqual", "value": 10}])
        assert evaluate_condition(p, {"n": 11}) is False

    def test_greater_than_or_equal_true(self):
        p = parse_condition([{"field": "n", "op": "greaterThanOrEqual", "value": 10}])
        assert evaluate_condition(p, {"n": 10}) is True

    def test_greater_than_or_equal_false(self):
        p = parse_condition([{"field": "n", "op": "greaterThanOrEqual", "value": 10}])
        assert evaluate_condition(p, {"n": 9}) is False

    def test_is_null_true(self):
        p = parse_condition([{"field": "x", "op": "isNull"}])
        assert evaluate_condition(p, {"x": None}) is True

    def test_is_null_false(self):
        p = parse_condition([{"field": "x", "op": "isNull"}])
        assert evaluate_condition(p, {"x": "something"}) is False

    def test_is_null_missing_field(self):
        p = parse_condition([{"field": "x", "op": "isNull"}])
        assert evaluate_condition(p, {}) is True

    def test_is_not_null_true(self):
        p = parse_condition([{"field": "x", "op": "isNotNull"}])
        assert evaluate_condition(p, {"x": "val"}) is True

    def test_is_not_null_false(self):
        p = parse_condition([{"field": "x", "op": "isNotNull"}])
        assert evaluate_condition(p, {"x": None}) is False

    def test_comparison_null_field_returns_false(self):
        p = parse_condition([{"field": "n", "op": "greaterThan", "value": 0}])
        assert evaluate_condition(p, {"n": None}) is False


# ---------------------------------------------------------------------------
# Evaluation — structural forms
# ---------------------------------------------------------------------------


class TestEvaluateStructural:
    """Evaluation of AllNode / AnyNode combinations."""

    def test_all_true(self):
        p = parse_condition({
            "all": [
                {"field": "a", "op": "equals", "value": 1},
                {"field": "b", "op": "equals", "value": 2},
            ]
        })
        assert evaluate_condition(p, {"a": 1, "b": 2}) is True

    def test_all_false(self):
        p = parse_condition({
            "all": [
                {"field": "a", "op": "equals", "value": 1},
                {"field": "b", "op": "equals", "value": 2},
            ]
        })
        assert evaluate_condition(p, {"a": 1, "b": 99}) is False

    def test_any_true(self):
        p = parse_condition({
            "any": [
                {"field": "a", "op": "equals", "value": 1},
                {"field": "b", "op": "equals", "value": 2},
            ]
        })
        assert evaluate_condition(p, {"a": 99, "b": 2}) is True

    def test_any_false(self):
        p = parse_condition({
            "any": [
                {"field": "a", "op": "equals", "value": 1},
                {"field": "b", "op": "equals", "value": 2},
            ]
        })
        assert evaluate_condition(p, {"a": 99, "b": 99}) is False

    def test_nested_any_in_all(self):
        p = parse_condition({
            "all": [
                {"field": "a", "op": "equals", "value": 1},
                {
                    "any": [
                        {"field": "b", "op": "equals", "value": 2},
                        {"field": "b", "op": "equals", "value": 3},
                    ]
                },
            ]
        })
        assert evaluate_condition(p, {"a": 1, "b": 3}) is True
        assert evaluate_condition(p, {"a": 1, "b": 99}) is False


# ---------------------------------------------------------------------------
# Evaluation — relative dates
# ---------------------------------------------------------------------------


class TestEvaluateRelativeDates:
    """Relative-date values are resolved at evaluation time."""

    def test_today_comparison(self):
        today = datetime.date(2026, 4, 14)
        p = parse_condition([
            {"field": "d", "op": "equals", "value": "today"},
        ])
        assert evaluate_condition(p, {"d": today}, today=today) is True
        assert evaluate_condition(
            p, {"d": datetime.date(2026, 4, 13)}, today=today
        ) is False

    def test_last_n_days(self):
        today = datetime.date(2026, 4, 14)
        p = parse_condition([
            {"field": "d", "op": "greaterThanOrEqual", "value": "lastNDays:7"},
        ])
        # 7 days ago = April 7
        assert evaluate_condition(
            p, {"d": datetime.date(2026, 4, 10)}, today=today
        ) is True
        assert evaluate_condition(
            p, {"d": datetime.date(2026, 4, 1)}, today=today
        ) is False


# ---------------------------------------------------------------------------
# Render — round-trip
# ---------------------------------------------------------------------------


class TestRender:
    """Render and round-trip tests."""

    def test_shorthand_round_trip(self):
        raw = [
            {"field": "a", "op": "equals", "value": 1},
            {"field": "b", "op": "isNull"},
        ]
        parsed = parse_condition(raw)
        rendered = render_condition(parsed)
        # Shorthand parses to AllNode, renders as {"all": [...]}
        assert isinstance(rendered, dict)
        assert "all" in rendered
        reparsed = parse_condition(rendered)
        assert isinstance(reparsed, AllNode)
        assert len(reparsed.children) == len(parsed.children)
        # Verify leaf equivalence
        for orig, reparse in zip(parsed.children, reparsed.children, strict=True):
            assert isinstance(orig, LeafClause)
            assert isinstance(reparse, LeafClause)
            assert orig.field == reparse.field
            assert orig.op == reparse.op
            assert orig.value == reparse.value or (
                orig.value is _MISSING and reparse.value is _MISSING
            )

    def test_structured_round_trip(self):
        raw = {
            "any": [
                {"field": "a", "op": "in", "value": [1, 2]},
                {
                    "all": [
                        {"field": "b", "op": "equals", "value": "X"},
                        {"field": "c", "op": "isNotNull"},
                    ]
                },
            ]
        }
        parsed = parse_condition(raw)
        rendered = render_condition(parsed)
        assert rendered["any"][0]["field"] == "a"
        assert rendered["any"][1]["all"][0]["field"] == "b"
        assert "value" not in rendered["any"][1]["all"][1]

    def test_leaf_render(self):
        p = parse_condition([{"field": "x", "op": "equals", "value": 42}])
        rendered = render_condition(p)
        assert rendered == {"all": [{"field": "x", "op": "equals", "value": 42}]}

    def test_no_value_not_rendered(self):
        p = parse_condition([{"field": "x", "op": "isNull"}])
        rendered = render_condition(p)
        leaf_dict = rendered["all"][0]
        assert "value" not in leaf_dict


# ---------------------------------------------------------------------------
# Role clauses (Section 12.5.1) — Prompt F
# ---------------------------------------------------------------------------


class TestParseRoleClause:
    """Parser tests for the role-clause variant."""

    def test_parse_role_clause_equals(self):
        result = parse_condition({"role": "equals", "value": "Mentor"})
        assert isinstance(result, RoleClause)
        assert result.op == "equals"
        assert result.value == "Mentor"

    def test_parse_role_clause_in(self):
        result = parse_condition(
            {"role": "in", "value": ["Mentor", "Admin"]}
        )
        assert isinstance(result, RoleClause)
        assert result.op == "in"
        assert result.value == ["Mentor", "Admin"]

    def test_parse_role_clause_in_shorthand_list(self):
        result = parse_condition(
            [{"role": "equals", "value": "Mentor"}]
        )
        assert isinstance(result, AllNode)
        assert len(result.children) == 1
        assert isinstance(result.children[0], RoleClause)
        assert result.children[0].op == "equals"

    def test_parse_role_clause_in_any_block(self):
        result = parse_condition(
            {
                "any": [
                    {"role": "in", "value": ["Mentor", "Admin"]},
                    {"role": "equals", "value": "Staff"},
                ]
            }
        )
        assert isinstance(result, AnyNode)
        assert len(result.children) == 2
        assert all(isinstance(c, RoleClause) for c in result.children)

    def test_parse_compound_field_and_role(self):
        result = parse_condition(
            {
                "any": [
                    {"field": "x", "op": "equals", "value": "y"},
                    {"role": "in", "value": ["A"]},
                ]
            }
        )
        assert isinstance(result, AnyNode)
        assert isinstance(result.children[0], LeafClause)
        assert isinstance(result.children[1], RoleClause)

    def test_parse_role_clause_missing_value(self):
        with pytest.raises(ValueError, match="must include a 'value' key"):
            parse_condition({"role": "equals"})

    def test_parse_role_clause_missing_role_key(self):
        with pytest.raises(
            ValueError, match="'all', 'any', 'field', or 'role'",
        ):
            parse_condition({"value": "Mentor"})

    def test_parse_role_clause_empty_role_value(self):
        with pytest.raises(
            ValueError, match="non-empty string 'role' key",
        ):
            parse_condition({"role": "", "value": "Mentor"})

    def test_parse_role_clause_non_string_role(self):
        with pytest.raises(
            ValueError, match="non-empty string 'role' key",
        ):
            parse_condition({"role": 42, "value": "Mentor"})

    def test_parse_role_clause_with_extra_op_key(self):
        with pytest.raises(
            ValueError, match="unexpected key",
        ):
            parse_condition(
                {"role": "equals", "op": "equals", "value": "Mentor"}
            )

    def test_parse_role_clause_with_field_key_conflict(self):
        with pytest.raises(
            ValueError, match="both 'field' and 'role'",
        ):
            parse_condition(
                {"role": "equals", "field": "x", "value": "y"}
            )


class TestValidateRoleClauseContext:
    """Context-restriction tests (allow_role_clauses flag)."""

    def test_rejected_by_default(self):
        ast = parse_condition({"role": "equals", "value": "Mentor"})
        errors = validate_condition(ast, entity_field_names=set())
        assert len(errors) == 1
        assert "not permitted in this context" in errors[0]

    def test_accepted_when_allowed(self):
        ast = parse_condition({"role": "equals", "value": "Mentor"})
        errors = validate_condition(
            ast, entity_field_names=set(), allow_role_clauses=True,
        )
        assert errors == []

    def test_rejected_inside_compound_when_disallowed(self):
        ast = parse_condition(
            {
                "any": [
                    {"field": "x", "op": "equals", "value": "y"},
                    {"role": "in", "value": ["A"]},
                ]
            }
        )
        errors = validate_condition(
            ast, entity_field_names={"x"}, allow_role_clauses=False,
        )
        assert len(errors) == 1
        assert "not permitted in this context" in errors[0]

    def test_rejected_inside_nested_all_any(self):
        ast = parse_condition(
            {
                "all": [
                    {"field": "x", "op": "equals", "value": "y"},
                    {
                        "any": [
                            {"role": "equals", "value": "Mentor"},
                        ]
                    },
                ]
            }
        )
        errors = validate_condition(
            ast, entity_field_names={"x"}, allow_role_clauses=False,
        )
        assert len(errors) == 1
        assert "not permitted in this context" in errors[0]


class TestValidateRoleClauseOperator:
    """Operator-restriction tests (only 4 ops allowed)."""

    @pytest.mark.parametrize(
        "bad_op",
        ["lessThan", "greaterThan", "lessThanOrEqual",
         "greaterThanOrEqual", "contains", "isNull", "isNotNull"],
    )
    def test_disallowed_operator_rejected(self, bad_op):
        ast = parse_condition({"role": bad_op, "value": "x"})
        errors = validate_condition(
            ast, entity_field_names=set(), allow_role_clauses=True,
        )
        assert len(errors) == 1
        assert "Unknown role-clause operator" in errors[0]

    def test_lessthan_rejected(self):
        ast = parse_condition({"role": "lessThan", "value": "X"})
        errors = validate_condition(
            ast, entity_field_names=set(), allow_role_clauses=True,
        )
        assert any("Unknown role-clause operator" in e for e in errors)

    def test_isnull_rejected(self):
        ast = parse_condition({"role": "isNull", "value": "X"})
        errors = validate_condition(
            ast, entity_field_names=set(), allow_role_clauses=True,
        )
        assert any("Unknown role-clause operator" in e for e in errors)

    def test_contains_rejected(self):
        ast = parse_condition({"role": "contains", "value": "X"})
        errors = validate_condition(
            ast, entity_field_names=set(), allow_role_clauses=True,
        )
        assert any("Unknown role-clause operator" in e for e in errors)

    @pytest.mark.parametrize("good_op", sorted(ROLE_OPERATORS))
    def test_allowed_operator_passes_operator_check(self, good_op):
        if good_op in {"in", "notIn"}:
            value: object = ["Mentor"]
        else:
            value = "Mentor"
        ast = parse_condition({"role": good_op, "value": value})
        errors = validate_condition(
            ast, entity_field_names=set(), allow_role_clauses=True,
        )
        assert not any("Unknown role-clause operator" in e for e in errors)


class TestValidateRoleClauseValueShape:
    """Value-shape checks per operator."""

    def test_equals_with_list_value_rejected(self):
        ast = parse_condition({"role": "equals", "value": ["A"]})
        errors = validate_condition(
            ast, entity_field_names=set(), allow_role_clauses=True,
        )
        assert any(
            "non-empty string role name" in e for e in errors
        )

    def test_equals_with_empty_string_rejected(self):
        ast = parse_condition({"role": "equals", "value": ""})
        errors = validate_condition(
            ast, entity_field_names=set(), allow_role_clauses=True,
        )
        assert any(
            "non-empty string role name" in e for e in errors
        )

    def test_in_with_string_value_rejected(self):
        ast = parse_condition({"role": "in", "value": "A"})
        errors = validate_condition(
            ast, entity_field_names=set(), allow_role_clauses=True,
        )
        assert any(
            "requires 'value' to be a list" in e for e in errors
        )

    def test_in_with_empty_string_in_list_rejected(self):
        ast = parse_condition({"role": "in", "value": ["A", ""]})
        errors = validate_condition(
            ast, entity_field_names=set(), allow_role_clauses=True,
        )
        assert any(
            "non-empty string role name" in e for e in errors
        )

    def test_in_with_non_string_in_list_rejected(self):
        ast = parse_condition({"role": "in", "value": ["A", 42]})
        errors = validate_condition(
            ast, entity_field_names=set(), allow_role_clauses=True,
        )
        assert any(
            "non-empty string role name" in e for e in errors
        )


class TestValidateRoleClauseKnownRoles:
    """known_roles cross-check tests."""

    def test_known_roles_match(self):
        ast = parse_condition({"role": "equals", "value": "Mentor"})
        errors = validate_condition(
            ast,
            entity_field_names=set(),
            allow_role_clauses=True,
            known_roles={"Mentor", "Admin"},
        )
        assert errors == []

    def test_known_roles_missing_equals(self):
        ast = parse_condition({"role": "equals", "value": "GhostRole"})
        errors = validate_condition(
            ast,
            entity_field_names=set(),
            allow_role_clauses=True,
            known_roles={"Mentor"},
        )
        assert len(errors) == 1
        assert "GhostRole" in errors[0]

    def test_known_roles_missing_in_list(self):
        ast = parse_condition(
            {"role": "in", "value": ["Mentor", "GhostRole"]}
        )
        errors = validate_condition(
            ast,
            entity_field_names=set(),
            allow_role_clauses=True,
            known_roles={"Mentor"},
        )
        assert len(errors) == 1
        assert "GhostRole" in errors[0]
        assert "Mentor" not in errors[0].replace(
            "GhostRole", ""
        ).replace("declared in this batch", "")

    def test_known_roles_none_skips_check(self):
        ast = parse_condition({"role": "equals", "value": "Anything"})
        errors = validate_condition(
            ast,
            entity_field_names=set(),
            allow_role_clauses=True,
            known_roles=None,
        )
        assert errors == []

    def test_known_roles_in_with_all_known(self):
        ast = parse_condition(
            {"role": "in", "value": ["Mentor", "Admin"]}
        )
        errors = validate_condition(
            ast,
            entity_field_names=set(),
            allow_role_clauses=True,
            known_roles={"Mentor", "Admin", "Staff"},
        )
        assert errors == []


class TestCollectUnknownRoles:
    """collect_unknown_roles walker tests."""

    def test_empty_for_field_only_ast(self):
        ast = parse_condition([{"field": "x", "op": "equals", "value": "y"}])
        assert collect_unknown_roles(ast, set()) == set()

    def test_single_equals(self):
        ast = parse_condition({"role": "equals", "value": "Mentor"})
        assert collect_unknown_roles(ast, {"Admin"}) == {"Mentor"}

    def test_single_equals_known(self):
        ast = parse_condition({"role": "equals", "value": "Mentor"})
        assert collect_unknown_roles(ast, {"Mentor"}) == set()

    def test_in_list_partial(self):
        ast = parse_condition(
            {"role": "in", "value": ["Mentor", "Admin"]}
        )
        assert collect_unknown_roles(ast, {"Admin"}) == {"Mentor"}

    def test_in_list_all_known(self):
        ast = parse_condition(
            {"role": "in", "value": ["Mentor", "Admin"]}
        )
        assert collect_unknown_roles(ast, {"Mentor", "Admin"}) == set()

    def test_nested_compound(self):
        ast = parse_condition(
            {
                "all": [
                    {"field": "x", "op": "equals", "value": "y"},
                    {
                        "any": [
                            {"role": "equals", "value": "Ghost"},
                            {"field": "z", "op": "equals", "value": 1},
                        ]
                    },
                ]
            }
        )
        assert collect_unknown_roles(ast, {"Mentor"}) == {"Ghost"}


class TestRenderRoleClause:
    """Renderer tests for role clauses."""

    def test_render_role_clause_equals(self):
        rc = RoleClause(op="equals", value="Mentor")
        assert render_condition(rc) == {
            "role": "equals", "value": "Mentor",
        }

    def test_render_role_clause_in(self):
        rc = RoleClause(op="in", value=["A", "B"])
        assert render_condition(rc) == {"role": "in", "value": ["A", "B"]}

    def test_render_round_trip_role_only(self):
        original = {"role": "in", "value": ["Mentor", "Admin"]}
        ast = parse_condition(original)
        assert render_condition(ast) == original

    def test_render_round_trip_compound_field_and_role(self):
        original = {
            "any": [
                {"field": "x", "op": "equals", "value": "y"},
                {"role": "in", "value": ["A", "B"]},
            ]
        }
        ast = parse_condition(original)
        assert render_condition(ast) == original

    def test_render_round_trip_nested(self):
        original = {
            "all": [
                {"field": "x", "op": "equals", "value": "y"},
                {
                    "any": [
                        {"role": "equals", "value": "Mentor"},
                        {"field": "z", "op": "isNull"},
                    ]
                },
            ]
        }
        ast = parse_condition(original)
        assert render_condition(ast) == original


class TestCollectUnknownFieldsIgnoresRoleClauses:
    """Regression: role-clause value strings are not mistaken for field
    references."""

    def test_role_value_string_not_collected_as_field(self):
        ast = parse_condition({"role": "equals", "value": "Mentor"})
        assert collect_unknown_fields(ast, {"some_field"}) == set()

    def test_role_value_list_not_collected_as_fields(self):
        ast = parse_condition(
            {"role": "in", "value": ["Mentor", "Admin"]}
        )
        assert collect_unknown_fields(ast, {"some_field"}) == set()

    def test_compound_returns_only_field_unknowns(self):
        ast = parse_condition(
            {
                "any": [
                    {"field": "missingField", "op": "equals", "value": "y"},
                    {"role": "equals", "value": "Mentor"},
                ]
            }
        )
        assert (
            collect_unknown_fields(ast, set())
            == {"missingField"}
        )

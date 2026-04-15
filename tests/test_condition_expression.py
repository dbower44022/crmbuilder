"""Tests for the condition-expression parser, validator, evaluator, and renderer."""

import datetime

import pytest

from espo_impl.core.condition_expression import (
    _MISSING,
    AllNode,
    AnyNode,
    LeafClause,
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
        with pytest.raises(ValueError, match="'all', 'any', or 'field'"):
            parse_condition({"bogus": True})


# ---------------------------------------------------------------------------
# Parsing — leaf clause details
# ---------------------------------------------------------------------------


class TestParseLeaf:
    """Leaf clause parsing tests."""

    def test_missing_field_rejected(self):
        with pytest.raises(ValueError, match="'all', 'any', or 'field'"):
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

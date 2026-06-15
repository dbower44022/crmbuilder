"""Neutral structured-formula validator tests — PRJ-025 PI-197 (DEC-438).

Covers the concat / arithmetic / aggregate happy paths and the
malformation surfaces (bad kind, empty concat, bad part, bad expression
node, bad op, bad aggregate function, count-with-field, non-count without
field, missing association, unknown keys, non-dict).
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.formulas import FormulaError, validate_formula

# --- concat -----------------------------------------------------------------


def test_valid_concat_passes():
    validate_formula(
        {
            "kind": "concat",
            "parts": [
                {"field": "first_name"},
                {"literal": " "},
                {"field": "last_name"},
            ],
        }
    )


def test_concat_empty_parts_raises():
    with pytest.raises(FormulaError, match="non-empty"):
        validate_formula({"kind": "concat", "parts": []})


def test_concat_parts_not_a_list_raises():
    with pytest.raises(FormulaError, match="parts: must be a list"):
        validate_formula({"kind": "concat", "parts": {"field": "x"}})


def test_concat_part_with_both_keys_raises():
    with pytest.raises(FormulaError, match="exactly one"):
        validate_formula(
            {"kind": "concat", "parts": [{"field": "x", "literal": "y"}]}
        )


def test_concat_literal_must_be_string():
    with pytest.raises(FormulaError, match="literal: must be a string"):
        validate_formula({"kind": "concat", "parts": [{"literal": 5}]})


def test_concat_field_must_be_nonempty_ref():
    with pytest.raises(FormulaError, match="non-empty string reference"):
        validate_formula({"kind": "concat", "parts": [{"field": "  "}]})


def test_concat_unexpected_key_raises():
    with pytest.raises(FormulaError, match="unexpected keys"):
        validate_formula(
            {"kind": "concat", "parts": [{"literal": "x"}], "extra": 1}
        )


# --- arithmetic -------------------------------------------------------------


def test_valid_arithmetic_passes():
    validate_formula(
        {
            "kind": "arithmetic",
            "expression": {
                "op": "-",
                "left": {"field": "capacity"},
                "right": {"number": 1},
            },
        }
    )


def test_valid_arithmetic_nested_passes():
    validate_formula(
        {
            "kind": "arithmetic",
            "expression": {
                "op": "*",
                "left": {
                    "op": "+",
                    "left": {"field": "a"},
                    "right": {"number": 2.5},
                },
                "right": {"field": "b"},
            },
        }
    )


def test_arithmetic_bad_op_raises():
    with pytest.raises(FormulaError, match="op: must be one of"):
        validate_formula(
            {
                "kind": "arithmetic",
                "expression": {
                    "op": "%",
                    "left": {"field": "a"},
                    "right": {"number": 2},
                },
            }
        )


def test_arithmetic_bad_number_raises():
    with pytest.raises(FormulaError, match="number: must be an int or float"):
        validate_formula(
            {"kind": "arithmetic", "expression": {"number": "5"}}
        )


def test_arithmetic_bool_is_not_a_number():
    with pytest.raises(FormulaError, match="number: must be an int or float"):
        validate_formula(
            {"kind": "arithmetic", "expression": {"number": True}}
        )


def test_arithmetic_unknown_expr_shape_raises():
    with pytest.raises(FormulaError, match="must be a field ref"):
        validate_formula(
            {"kind": "arithmetic", "expression": {"field": "a", "op": "+"}}
        )


def test_arithmetic_missing_expression_raises():
    with pytest.raises(FormulaError, match="requires an 'expression'"):
        validate_formula({"kind": "arithmetic"})


# --- aggregate --------------------------------------------------------------


def test_valid_aggregate_count_passes():
    validate_formula(
        {"kind": "aggregate", "function": "count", "association": "ASN-001"}
    )


def test_valid_aggregate_count_explicit_null_field_passes():
    validate_formula(
        {
            "kind": "aggregate",
            "function": "count",
            "association": "ASN-001",
            "field": None,
        }
    )


def test_valid_aggregate_sum_passes():
    validate_formula(
        {
            "kind": "aggregate",
            "function": "sum",
            "association": "ASN-002",
            "field": "hours",
        }
    )


def test_aggregate_bad_function_raises():
    with pytest.raises(FormulaError, match="function: must be one of"):
        validate_formula(
            {"kind": "aggregate", "function": "median", "association": "ASN-1"}
        )


def test_aggregate_count_with_field_raises():
    with pytest.raises(FormulaError, match="must be null/absent for function"):
        validate_formula(
            {
                "kind": "aggregate",
                "function": "count",
                "association": "ASN-001",
                "field": "hours",
            }
        )


def test_aggregate_non_count_without_field_raises():
    with pytest.raises(FormulaError, match="field: must be a non-empty"):
        validate_formula(
            {"kind": "aggregate", "function": "avg", "association": "ASN-001"}
        )


def test_aggregate_missing_association_raises():
    with pytest.raises(FormulaError, match="association: must be a non-empty"):
        validate_formula({"kind": "aggregate", "function": "count"})


# --- top-level --------------------------------------------------------------


def test_bad_kind_raises():
    with pytest.raises(FormulaError, match="kind: must be one of"):
        validate_formula({"kind": "lookup", "parts": []})


def test_non_dict_raises():
    with pytest.raises(FormulaError, match="must be a JSON object"):
        validate_formula(["not", "a", "dict"])

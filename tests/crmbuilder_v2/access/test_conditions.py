"""Neutral condition-AST validator tests — PRJ-025 PI-189 slice 2.

Covers the leaf / all / any happy paths and the malformation surfaces
(bad op, empty group, non-list group, missing field, mixed keys, value
required / forbidden, unknown keys).
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.conditions import ConditionError, validate_condition


def test_valid_leaf_passes():
    validate_condition({"field": "stage", "op": "eq", "value": "won"})


def test_valid_leaf_valueless_op_passes():
    validate_condition({"field": "closed_at", "op": "is_empty"})
    validate_condition({"field": "closed_at", "op": "is_not_empty"})


def test_valid_leaf_fld_reference_passes():
    validate_condition({"field": "FLD-007", "op": "in", "value": [1, 2, 3]})


def test_valid_all_group_passes():
    validate_condition(
        {
            "all": [
                {"field": "stage", "op": "eq", "value": "won"},
                {"field": "amount", "op": "gte", "value": 100},
            ]
        }
    )


def test_valid_any_group_passes():
    validate_condition(
        {
            "any": [
                {"field": "a", "op": "is_empty"},
                {"field": "b", "op": "ne", "value": 0},
            ]
        }
    )


def test_valid_nested_group_passes():
    validate_condition(
        {
            "all": [
                {"field": "a", "op": "eq", "value": 1},
                {"any": [{"field": "b", "op": "eq", "value": 2}]},
            ]
        }
    )


def test_bad_op_raises():
    with pytest.raises(ConditionError):
        validate_condition({"field": "x", "op": "matches", "value": 1})


def test_empty_group_raises():
    with pytest.raises(ConditionError):
        validate_condition({"all": []})


def test_non_list_group_raises():
    with pytest.raises(ConditionError):
        validate_condition({"any": {"field": "x", "op": "eq", "value": 1}})


def test_missing_field_raises():
    with pytest.raises(ConditionError):
        validate_condition({"op": "eq", "value": 1})


def test_missing_op_raises():
    with pytest.raises(ConditionError):
        validate_condition({"field": "x", "value": 1})


def test_value_required_op_without_value_raises():
    with pytest.raises(ConditionError):
        validate_condition({"field": "x", "op": "eq"})


def test_mixed_group_and_leaf_keys_raises():
    with pytest.raises(ConditionError):
        validate_condition(
            {"all": [{"field": "x", "op": "eq", "value": 1}], "field": "y"}
        )


def test_both_all_and_any_raises():
    with pytest.raises(ConditionError):
        validate_condition(
            {
                "all": [{"field": "x", "op": "eq", "value": 1}],
                "any": [{"field": "y", "op": "eq", "value": 2}],
            }
        )


def test_unknown_key_on_leaf_raises():
    with pytest.raises(ConditionError):
        validate_condition(
            {"field": "x", "op": "eq", "value": 1, "bogus": True}
        )


def test_unknown_key_on_group_raises():
    with pytest.raises(ConditionError):
        validate_condition(
            {"all": [{"field": "x", "op": "eq", "value": 1}], "bogus": True}
        )


def test_non_dict_raises():
    with pytest.raises(ConditionError):
        validate_condition("not a condition")


def test_empty_field_raises():
    with pytest.raises(ConditionError):
        validate_condition({"field": "  ", "op": "eq", "value": 1})


def test_nested_malformed_child_raises():
    with pytest.raises(ConditionError):
        validate_condition({"all": [{"field": "x", "op": "bad", "value": 1}]})

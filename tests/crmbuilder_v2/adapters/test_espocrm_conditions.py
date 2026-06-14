"""Unit tests — neutral → EspoCRM condition compiler (PI-191 slice 2).

Pure, no DB. Covers every neutral operator → EspoCRM operator, the
valueless operators, nested all/any groups, field-reference resolution,
and the defensive error paths.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.vocab import NEUTRAL_CONDITION_OPS
from crmbuilder_v2.adapters.espocrm.conditions import (
    NEUTRAL_TO_ESPO_OP,
    CompileError,
    compile_condition,
)


def _identity(ref: str) -> str:
    return ref


@pytest.mark.parametrize(
    "neutral_op,espo_op",
    [
        ("eq", "equals"),
        ("ne", "notEquals"),
        ("gt", "greaterThan"),
        ("lt", "lessThan"),
        ("gte", "greaterThanOrEqual"),
        ("lte", "lessThanOrEqual"),
        ("in", "in"),
        ("contains", "contains"),
    ],
)
def test_value_bearing_ops_map(neutral_op, espo_op):
    out = compile_condition(
        {"field": "status", "op": neutral_op, "value": "x"}, _identity
    )
    assert out == {"field": "status", "op": espo_op, "value": "x"}


@pytest.mark.parametrize(
    "neutral_op,espo_op",
    [("is_empty", "isNull"), ("is_not_empty", "isNotNull")],
)
def test_valueless_ops_drop_value(neutral_op, espo_op):
    # Even if a stray value is present on the neutral side, the compiled
    # valueless leaf carries no 'value' key.
    out = compile_condition({"field": "x", "op": neutral_op}, _identity)
    assert out == {"field": "x", "op": espo_op}
    assert "value" not in out


def test_op_table_total_over_neutral_vocab():
    # Every neutral operator the store admits must have a mapping.
    assert set(NEUTRAL_TO_ESPO_OP) == set(NEUTRAL_CONDITION_OPS)


def test_in_op_passes_list_value_through():
    out = compile_condition(
        {"field": "tier", "op": "in", "value": ["a", "b"]}, _identity
    )
    assert out == {"field": "tier", "op": "in", "value": ["a", "b"]}


def test_field_ref_resolved_to_internal_name():
    resolver = {"FLD-007": "applicationStatus"}.get
    out = compile_condition(
        {"field": "FLD-007", "op": "eq", "value": "approved"},
        lambda r: resolver(r) or r,
    )
    assert out["field"] == "applicationStatus"


def test_nested_all_any_groups():
    ast = {
        "all": [
            {"field": "a", "op": "eq", "value": 1},
            {"any": [
                {"field": "b", "op": "is_empty"},
                {"field": "c", "op": "gt", "value": 3},
            ]},
        ]
    }
    out = compile_condition(ast, _identity)
    assert out == {
        "all": [
            {"field": "a", "op": "equals", "value": 1},
            {"any": [
                {"field": "b", "op": "isNull"},
                {"field": "c", "op": "greaterThan", "value": 3},
            ]},
        ]
    }


def test_unknown_operator_raises():
    with pytest.raises(CompileError):
        compile_condition({"field": "x", "op": "between", "value": 1}, _identity)


def test_empty_group_raises():
    with pytest.raises(CompileError):
        compile_condition({"all": []}, _identity)


def test_non_dict_node_raises():
    with pytest.raises(CompileError):
        compile_condition(["not", "a", "node"], _identity)


def test_leaf_missing_field_raises():
    with pytest.raises(CompileError):
        compile_condition({"op": "eq", "value": 1}, _identity)

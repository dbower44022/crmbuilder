"""Condition-expression parser, validator, evaluator, and renderer.

Implements the shared condition-expression construct described in
app-yaml-schema.md Section 11. All functions are pure logic with no GUI
dependencies.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any, Final

from espo_impl.core.relative_date import is_relative_date, resolve_relative_date

OPERATORS: Final[set[str]] = {
    "equals",
    "notEquals",
    "contains",
    "in",
    "notIn",
    "lessThan",
    "greaterThan",
    "lessThanOrEqual",
    "greaterThanOrEqual",
    "isNull",
    "isNotNull",
}

OPERATORS_REQUIRING_LIST: Final[set[str]] = {"in", "notIn"}
OPERATORS_NO_VALUE: Final[set[str]] = {"isNull", "isNotNull"}
OPERATORS_COMPARISON: Final[set[str]] = {
    "lessThan",
    "greaterThan",
    "lessThanOrEqual",
    "greaterThanOrEqual",
}

# Sentinel to distinguish "value not provided" from "value is None"
_MISSING: Final[object] = object()


# ---------------------------------------------------------------------------
# AST nodes
# ---------------------------------------------------------------------------

@dataclass
class LeafClause:
    """A single field-op-value comparison."""

    field: str
    op: str
    value: Any = field(default=_MISSING)


@dataclass
class AllNode:
    """Conjunction: all children must be true."""

    children: list[LeafClause | AllNode | AnyNode]


@dataclass
class AnyNode:
    """Disjunction: at least one child must be true."""

    children: list[LeafClause | AllNode | AnyNode]


# Union type for parsed condition nodes
ConditionNode = LeafClause | AllNode | AnyNode


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_condition(raw: Any) -> ConditionNode:
    """Parse a raw YAML condition into an AST.

    :param raw: A flat list (shorthand) or a dict with ``all:`` / ``any:``
        (structured form).
    :returns: Parsed AST root node.
    :raises ValueError: On malformed input.
    """
    if isinstance(raw, list):
        return _parse_shorthand(raw)
    if isinstance(raw, dict):
        return _parse_dict(raw)
    raise ValueError(
        f"Condition must be a list (shorthand) or dict (structured), "
        f"got {type(raw).__name__}"
    )


def _parse_shorthand(items: list) -> AllNode:
    """Parse shorthand form: flat list of leaf clauses → AllNode."""
    if not items:
        raise ValueError("Shorthand condition list must not be empty")
    children = [_parse_node(item) for item in items]
    return AllNode(children=children)


def _parse_dict(d: dict) -> ConditionNode:
    """Parse a dict that is either a leaf, an all-block, or an any-block."""
    has_all = "all" in d
    has_any = "any" in d
    has_field = "field" in d

    if has_all and has_any:
        raise ValueError(
            "Condition dict must not contain both 'all' and 'any' at the "
            "same level"
        )

    if has_all:
        return _parse_all(d["all"])
    if has_any:
        return _parse_any(d["any"])
    if has_field:
        return _parse_leaf(d)

    raise ValueError(
        f"Condition dict must contain 'all', 'any', or 'field'; "
        f"got keys: {sorted(d.keys())}"
    )


def _parse_all(items: Any) -> AllNode:
    """Parse an ``all:`` block."""
    if not isinstance(items, list) or not items:
        raise ValueError("'all' must be a non-empty list")
    return AllNode(children=[_parse_node(item) for item in items])


def _parse_any(items: Any) -> AnyNode:
    """Parse an ``any:`` block."""
    if not isinstance(items, list) or not items:
        raise ValueError("'any' must be a non-empty list")
    return AnyNode(children=[_parse_node(item) for item in items])


def _parse_node(item: Any) -> ConditionNode:
    """Parse a single node (leaf or nested all/any)."""
    if isinstance(item, dict):
        return _parse_dict(item)
    raise ValueError(
        f"Each condition clause must be a dict, got {type(item).__name__}"
    )


def _parse_leaf(d: dict) -> LeafClause:
    """Parse a leaf clause dict into a LeafClause."""
    field_name = d.get("field")
    if not field_name or not isinstance(field_name, str):
        raise ValueError("Leaf clause must have a non-empty string 'field'")

    op = d.get("op")
    if not op or not isinstance(op, str):
        raise ValueError(
            f"Leaf clause for field '{field_name}' must have a non-empty "
            f"string 'op'"
        )

    if "value" in d:
        return LeafClause(field=field_name, op=op, value=d["value"])
    return LeafClause(field=field_name, op=op)


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def validate_condition(
    parsed: ConditionNode,
    entity_field_names: set[str],
    related_entity_field_names: set[str] | None = None,
) -> list[str]:
    """Validate a parsed condition AST.

    :param parsed: Root of the parsed AST.
    :param entity_field_names: Valid field names on the primary entity.
    :param related_entity_field_names: Valid field names on a related entity
        (for aggregate ``where:`` clauses). If provided, leaf field references
        are checked against this set instead.
    :returns: List of error messages; empty means valid.
    """
    errors: list[str] = []
    _validate_node(parsed, entity_field_names, related_entity_field_names, errors)
    return errors


def _validate_node(
    node: ConditionNode,
    entity_fields: set[str],
    related_fields: set[str] | None,
    errors: list[str],
) -> None:
    """Recursively validate a node."""
    if isinstance(node, LeafClause):
        _validate_leaf(node, entity_fields, related_fields, errors)
    elif isinstance(node, (AllNode, AnyNode)):
        for child in node.children:
            _validate_node(child, entity_fields, related_fields, errors)


def _validate_leaf(
    leaf: LeafClause,
    entity_fields: set[str],
    related_fields: set[str] | None,
    errors: list[str],
) -> None:
    """Validate a single leaf clause."""
    # Check field reference
    check_fields = related_fields if related_fields is not None else entity_fields
    if leaf.field not in check_fields:
        errors.append(
            f"Field '{leaf.field}' not found in "
            f"{'related entity' if related_fields is not None else 'entity'} "
            f"fields"
        )

    # Check operator
    if leaf.op not in OPERATORS:
        errors.append(
            f"Unknown operator '{leaf.op}' on field '{leaf.field}'. "
            f"Valid operators: {sorted(OPERATORS)}"
        )
        return  # skip value checks if operator is unknown

    # Check value presence/shape
    has_value = leaf.value is not _MISSING

    if leaf.op in OPERATORS_NO_VALUE:
        if has_value:
            errors.append(
                f"Operator '{leaf.op}' on field '{leaf.field}' must not "
                f"include a 'value' clause"
            )
    elif leaf.op in OPERATORS_REQUIRING_LIST:
        if not has_value:
            errors.append(
                f"Operator '{leaf.op}' on field '{leaf.field}' requires "
                f"a 'value' list"
            )
        elif not isinstance(leaf.value, list):
            errors.append(
                f"Operator '{leaf.op}' on field '{leaf.field}' requires "
                f"'value' to be a list, got {type(leaf.value).__name__}"
            )
    elif leaf.op in OPERATORS_COMPARISON:
        if not has_value:
            errors.append(
                f"Operator '{leaf.op}' on field '{leaf.field}' requires "
                f"a 'value'"
            )
        elif has_value and not _is_valid_comparison_value(leaf.value):
            errors.append(
                f"Operator '{leaf.op}' on field '{leaf.field}' requires "
                f"'value' to be numeric, a date string, or a relative-date "
                f"string, got {leaf.value!r}"
            )
    else:
        # equals, notEquals, contains — value required
        if not has_value:
            errors.append(
                f"Operator '{leaf.op}' on field '{leaf.field}' requires "
                f"a 'value'"
            )


def _is_valid_comparison_value(value: Any) -> bool:
    """Return True if *value* is valid for a comparison operator."""
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        # Accept ISO date strings and relative-date strings
        if is_relative_date(value):
            return True
        try:
            datetime.date.fromisoformat(value)
            return True
        except ValueError:
            pass
        try:
            datetime.datetime.fromisoformat(value)
            return True
        except ValueError:
            pass
    if isinstance(value, (datetime.date, datetime.datetime)):
        return True
    return False


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

def evaluate_condition(
    parsed: ConditionNode,
    record: dict[str, Any],
    today: datetime.date | None = None,
) -> bool:
    """Evaluate a parsed condition against a record dict.

    :param parsed: Root of the parsed AST.
    :param record: Record to evaluate against (field name → value).
    :param today: Override for the current date (for testability).
    :returns: True if the condition holds.
    """
    if isinstance(parsed, AllNode):
        return all(
            evaluate_condition(child, record, today)
            for child in parsed.children
        )
    if isinstance(parsed, AnyNode):
        return any(
            evaluate_condition(child, record, today)
            for child in parsed.children
        )
    if isinstance(parsed, LeafClause):
        return _evaluate_leaf(parsed, record, today)
    raise TypeError(f"Unexpected node type: {type(parsed)}")  # pragma: no cover


def _evaluate_leaf(
    leaf: LeafClause,
    record: dict[str, Any],
    today: datetime.date | None,
) -> bool:
    """Evaluate a single leaf clause against a record."""
    field_value = record.get(leaf.field)
    op = leaf.op

    if op == "isNull":
        return field_value is None
    if op == "isNotNull":
        return field_value is not None

    # Resolve the comparison value (handle relative dates)
    compare_value = leaf.value
    if isinstance(compare_value, str) and is_relative_date(compare_value):
        compare_value = resolve_relative_date(compare_value, today)

    if op == "equals":
        return field_value == compare_value
    if op == "notEquals":
        return field_value != compare_value
    if op == "contains":
        # value is a member of the field's list
        if isinstance(field_value, list):
            return compare_value in field_value
        return False
    if op == "in":
        return field_value in compare_value
    if op == "notIn":
        return field_value not in compare_value
    if op == "lessThan":
        if field_value is None:
            return False
        return field_value < compare_value
    if op == "greaterThan":
        if field_value is None:
            return False
        return field_value > compare_value
    if op == "lessThanOrEqual":
        if field_value is None:
            return False
        return field_value <= compare_value
    if op == "greaterThanOrEqual":
        if field_value is None:
            return False
        return field_value >= compare_value

    return False  # pragma: no cover


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

def render_condition(parsed: ConditionNode) -> list | dict:
    """Render a parsed AST back to YAML-ready dict/list form.

    :param parsed: Root of the parsed AST.
    :returns: A list (shorthand form) or dict (structured form).
    """
    if isinstance(parsed, AllNode):
        # If all children are leaves, could render as shorthand list,
        # but to round-trip faithfully we always render structured.
        return {"all": [_render_node(child) for child in parsed.children]}
    if isinstance(parsed, AnyNode):
        return {"any": [_render_node(child) for child in parsed.children]}
    if isinstance(parsed, LeafClause):
        return _render_leaf(parsed)
    raise TypeError(f"Unexpected node type: {type(parsed)}")  # pragma: no cover


def _render_node(node: ConditionNode) -> dict:
    """Render a single node to a dict."""
    if isinstance(node, LeafClause):
        return _render_leaf(node)
    if isinstance(node, AllNode):
        return {"all": [_render_node(child) for child in node.children]}
    if isinstance(node, AnyNode):
        return {"any": [_render_node(child) for child in node.children]}
    raise TypeError(f"Unexpected node type: {type(node)}")  # pragma: no cover


def _render_leaf(leaf: LeafClause) -> dict:
    """Render a leaf clause to a dict."""
    result: dict[str, Any] = {"field": leaf.field, "op": leaf.op}
    if leaf.value is not _MISSING:
        result["value"] = leaf.value
    return result

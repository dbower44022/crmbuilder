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

# Role-clause operators (Section 12.5.1). Role identity does not
# support comparison / membership / nullity operators — those are
# rejected at validation time.
ROLE_OPERATORS: Final[set[str]] = {"equals", "notEquals", "in", "notIn"}
ROLE_OPERATORS_REQUIRING_LIST: Final[set[str]] = {"in", "notIn"}

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
class RoleClause:
    """A single role-identity check (Section 12.5.1).

    Distinct from ``LeafClause`` (which is field-based): a role
    clause checks the viewing user's role identity, not a value
    on the record being evaluated.

    :param op: One of ``equals``, ``notEquals``, ``in``, ``notIn``.
        Other operators are rejected at validation time per
        Section 12.5.1's operator restriction.
    :param value: Role name (string) for ``equals``/``notEquals``;
        list of role names for ``in``/``notIn``.
    """

    op: str
    value: Any


@dataclass
class AllNode:
    """Conjunction: all children must be true."""

    children: list[LeafClause | RoleClause | AllNode | AnyNode]


@dataclass
class AnyNode:
    """Disjunction: at least one child must be true."""

    children: list[LeafClause | RoleClause | AllNode | AnyNode]


# Union type for parsed condition nodes
ConditionNode = LeafClause | RoleClause | AllNode | AnyNode


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
    """Parse a dict that is either a leaf, a role clause, an all-block, or
    an any-block."""
    has_all = "all" in d
    has_any = "any" in d
    has_field = "field" in d
    has_role = "role" in d

    if has_all and has_any:
        raise ValueError(
            "Condition dict must not contain both 'all' and 'any' at the "
            "same level"
        )
    if has_field and has_role:
        raise ValueError(
            "Condition dict must not contain both 'field' and 'role' "
            "at the same level — a clause is either a field check or a "
            "role check, not both"
        )

    if has_all:
        return _parse_all(d["all"])
    if has_any:
        return _parse_any(d["any"])
    if has_field:
        return _parse_leaf(d)
    if has_role:
        return _parse_role_leaf(d)

    raise ValueError(
        f"Condition dict must contain 'all', 'any', 'field', or 'role'; "
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


def _parse_role_leaf(d: dict) -> RoleClause:
    """Parse a role-clause dict into a RoleClause.

    Per Section 12.5.1, the ``role:`` key carries the operator
    (one of ``equals``, ``notEquals``, ``in``, ``notIn``) and the
    ``value:`` key carries the role name(s). There is no separate
    ``op:`` key — the ``role:`` key carries that role.

    Structural validation (op must be a non-empty string; value
    must be present) is performed here; operator-vocabulary and
    value-shape validation are performed in
    :func:`_validate_role_leaf`.
    """
    op = d.get("role")
    if not op or not isinstance(op, str):
        raise ValueError(
            "Role clause must have a non-empty string 'role' key "
            "(the operator)"
        )
    if "value" not in d:
        raise ValueError(
            f"Role clause with role='{op}' must include a 'value' key"
        )
    extra_keys = set(d.keys()) - {"role", "value"}
    if extra_keys:
        raise ValueError(
            f"Role clause has unexpected key(s) {sorted(extra_keys)!r}; "
            f"role clauses use only 'role' and 'value'"
        )
    return RoleClause(op=op, value=d["value"])


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def validate_condition(
    parsed: ConditionNode,
    entity_field_names: set[str],
    related_entity_field_names: set[str] | None = None,
    *,
    allow_role_clauses: bool = False,
    known_roles: set[str] | None = None,
) -> list[str]:
    """Validate a parsed condition AST.

    :param parsed: Root of the parsed AST.
    :param entity_field_names: Valid field names on the primary entity.
    :param related_entity_field_names: Valid field names on a related entity
        (for aggregate ``where:`` clauses). If provided, leaf field references
        are checked against this set instead.
    :param allow_role_clauses: When True, role clauses are permitted in
        the AST. When False (default), any role clause is rejected with a
        "not allowed in this context" error. Per Section 12.5.1, only
        ``visibleWhen:`` consumers should set this to True.
    :param known_roles: When provided, every role-clause name must appear
        in this set. When None, role-clause names are not cross-checked
        (structural validation only).
    :returns: List of error messages; empty means valid.
    """
    errors: list[str] = []
    _validate_node(
        parsed,
        entity_field_names,
        related_entity_field_names,
        errors,
        allow_role_clauses=allow_role_clauses,
        known_roles=known_roles,
    )
    return errors


def collect_unknown_fields(
    parsed: ConditionNode,
    known_field_names: set[str],
) -> set[str]:
    """Return the set of leaf field references not in ``known_field_names``.

    Used by callers that want to distinguish "references a not-yet-created
    field" from structural errors (bad operator, missing value, etc.). When
    the only issues with a condition are unknown field references, the
    caller can choose to defer applying the condition rather than rejecting
    the whole program file.

    Role clauses do not contribute field references and are silently
    skipped by the walker.

    :param parsed: Root of the parsed AST.
    :param known_field_names: Field names known to exist (entity-local
        union, native fields, cross-batch fields).
    :returns: Set of field names referenced by the condition but not in
        ``known_field_names``. Empty set means every reference resolves.
    """
    unknowns: set[str] = set()
    _collect_unknown(parsed, known_field_names, unknowns)
    return unknowns


def _collect_unknown(
    node: ConditionNode,
    known: set[str],
    unknowns: set[str],
) -> None:
    """Recursively collect unknown field references."""
    if isinstance(node, LeafClause):
        if node.field not in known:
            unknowns.add(node.field)
    elif isinstance(node, (AllNode, AnyNode)):
        for child in node.children:
            _collect_unknown(child, known, unknowns)
    # RoleClause: no field references, nothing to collect.


def collect_unknown_roles(
    parsed: ConditionNode,
    known_role_names: set[str],
) -> set[str]:
    """Return the set of role-clause references not in ``known_role_names``.

    Mirrors :func:`collect_unknown_fields` for role references. Used by
    callers that want to defer applying a condition with unknown role
    references rather than rejecting the whole program file.

    :param parsed: Root of the parsed AST.
    :param known_role_names: Role names known to exist (typically from
        ``ProgramContext.role_names``).
    :returns: Set of role names referenced by the condition but not in
        ``known_role_names``. Empty set means every role reference
        resolves.
    """
    unknowns: set[str] = set()
    _collect_unknown_roles(parsed, known_role_names, unknowns)
    return unknowns


def _collect_unknown_roles(
    node: ConditionNode,
    known: set[str],
    unknowns: set[str],
) -> None:
    """Recursively collect unknown role references."""
    if isinstance(node, RoleClause):
        if isinstance(node.value, list):
            for v in node.value:
                if isinstance(v, str) and v not in known:
                    unknowns.add(v)
        elif isinstance(node.value, str):
            if node.value not in known:
                unknowns.add(node.value)
    elif isinstance(node, (AllNode, AnyNode)):
        for child in node.children:
            _collect_unknown_roles(child, known, unknowns)


def _validate_node(
    node: ConditionNode,
    entity_fields: set[str],
    related_fields: set[str] | None,
    errors: list[str],
    *,
    allow_role_clauses: bool,
    known_roles: set[str] | None,
) -> None:
    """Recursively validate a node."""
    if isinstance(node, LeafClause):
        _validate_leaf(node, entity_fields, related_fields, errors)
    elif isinstance(node, RoleClause):
        _validate_role_leaf(node, errors, allow_role_clauses, known_roles)
    elif isinstance(node, (AllNode, AnyNode)):
        for child in node.children:
            _validate_node(
                child,
                entity_fields,
                related_fields,
                errors,
                allow_role_clauses=allow_role_clauses,
                known_roles=known_roles,
            )


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


def _validate_role_leaf(
    role_clause: RoleClause,
    errors: list[str],
    allow_role_clauses: bool,
    known_roles: set[str] | None,
) -> None:
    """Validate a single role clause."""
    if not allow_role_clauses:
        errors.append(
            f"Role clauses (role='{role_clause.op}') are not permitted "
            f"in this context. Section 12.5.1 restricts role clauses to "
            f"viewing-context consumers (field-level and panel-level "
            f"visibleWhen:)."
        )
        return

    if role_clause.op not in ROLE_OPERATORS:
        errors.append(
            f"Unknown role-clause operator '{role_clause.op}'. "
            f"Role clauses are restricted to {sorted(ROLE_OPERATORS)}."
        )
        return

    if role_clause.op in ROLE_OPERATORS_REQUIRING_LIST:
        if not isinstance(role_clause.value, list):
            errors.append(
                f"Role-clause operator '{role_clause.op}' requires "
                f"'value' to be a list of role names, got "
                f"{type(role_clause.value).__name__}"
            )
            return
        if not all(isinstance(v, str) and v for v in role_clause.value):
            errors.append(
                f"Role-clause operator '{role_clause.op}' requires every "
                f"'value' list entry to be a non-empty string role name"
            )
            return
        if known_roles is not None:
            unknown = sorted(set(role_clause.value) - known_roles)
            if unknown:
                errors.append(
                    f"Role-clause operator '{role_clause.op}' references "
                    f"role(s) not declared in this batch: {unknown}"
                )
    else:
        if not isinstance(role_clause.value, str) or not role_clause.value:
            errors.append(
                f"Role-clause operator '{role_clause.op}' requires "
                f"'value' to be a non-empty string role name, got "
                f"{role_clause.value!r}"
            )
            return
        if known_roles is not None and role_clause.value not in known_roles:
            errors.append(
                f"Role-clause operator '{role_clause.op}' references "
                f"role '{role_clause.value}' not declared in this batch"
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
    if isinstance(parsed, RoleClause):
        return _render_role_leaf(parsed)
    raise TypeError(f"Unexpected node type: {type(parsed)}")  # pragma: no cover


def _render_node(node: ConditionNode) -> dict:
    """Render a single node to a dict."""
    if isinstance(node, LeafClause):
        return _render_leaf(node)
    if isinstance(node, RoleClause):
        return _render_role_leaf(node)
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


def _render_role_leaf(role_clause: RoleClause) -> dict:
    """Render a role clause to a dict in the canonical Section 12.5.1
    structured form: ``{"role": <op>, "value": <value>}``."""
    return {"role": role_clause.op, "value": role_clause.value}

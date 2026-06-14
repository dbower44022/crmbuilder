"""Neutral condition AST → EspoCRM condition-expression compiler (slice 2).

The engine-neutral ``rule`` record carries a neutral condition AST
(``crmbuilder_v2.access.conditions``: leaf ``{"field", "op", "value"}`` /
group ``{"all": [...]}`` / ``{"any": [...]}``). This module compiles that
shape into the EspoCRM condition-expression structure the V1 deploy
engine accepts (``espo_impl.core.condition_expression``: the same leaf /
``all`` / ``any`` shape, but with EspoCRM operator names and the field
reference derived to a lowerCamelCase EspoCRM field name).

Pure and deterministic: a fixed AST + a fixed reference resolver compile
to a byte-stable structure. The compiled output is attached to a field's
``requiredWhen:`` / ``visibleWhen:`` block (design §8, schema §6.1.1 /
§11) and must pass ``validate_program`` unchanged.
"""

from __future__ import annotations

from collections.abc import Callable

# Neutral leaf operator → EspoCRM ``where``/condition operator. The neutral
# vocabulary (``crmbuilder_v2.access.vocab.NEUTRAL_CONDITION_OPS``) maps
# one-to-one onto the EspoCRM operator set
# (``espo_impl.core.condition_expression.OPERATORS``). ``is_empty`` /
# ``is_not_empty`` carry no value; everything else does. The neutral model
# has no ``notIn`` — only ``in`` — so the table is total over the neutral ops.
NEUTRAL_TO_ESPO_OP: dict[str, str] = {
    "eq": "equals",
    "ne": "notEquals",
    "gt": "greaterThan",
    "lt": "lessThan",
    "gte": "greaterThanOrEqual",
    "lte": "lessThanOrEqual",
    "in": "in",
    "contains": "contains",
    "is_empty": "isNull",
    "is_not_empty": "isNotNull",
}

# EspoCRM operators that take no ``value`` key (mirrors
# ``condition_expression.OPERATORS_NO_VALUE``).
_ESPO_NO_VALUE = frozenset({"isNull", "isNotNull"})


class CompileError(ValueError):
    """Raised when a neutral condition cannot be compiled to EspoCRM form.

    The neutral AST is already validated at write time
    (``access.conditions.validate_condition``), so this is a defensive
    guard: an unknown operator or a structurally-unexpected node routes
    the owning rule to a deferral rather than emitting invalid YAML.
    """


def compile_condition(
    node: object,
    resolve_ref: Callable[[str], str],
) -> dict:
    """Compile one neutral condition node to its EspoCRM structure.

    :param node: a neutral condition AST node (leaf or ``all``/``any``
        group), already validated by ``access.conditions``.
    :param resolve_ref: maps a neutral field reference (a field name or a
        ``FLD-NNN`` identifier) to its emitted lowerCamelCase EspoCRM
        field name.
    :returns: the EspoCRM condition structure — a leaf
        ``{"field", "op"[, "value"]}`` or a group ``{"all"/"any": [...]}``.
    :raises CompileError: on an unexpected node shape or operator.
    """
    if not isinstance(node, dict):
        raise CompileError(
            f"condition node must be an object, got {type(node).__name__}"
        )

    if "all" in node or "any" in node:
        return _compile_group(node, resolve_ref)
    return _compile_leaf(node, resolve_ref)


def _compile_group(node: dict, resolve_ref: Callable[[str], str]) -> dict:
    key = "all" if "all" in node else "any"
    children = node[key]
    if not isinstance(children, list) or not children:
        raise CompileError(f"group {key!r} must be a non-empty list")
    return {key: [compile_condition(child, resolve_ref) for child in children]}


def _compile_leaf(node: dict, resolve_ref: Callable[[str], str]) -> dict:
    raw_field = node.get("field")
    if not isinstance(raw_field, str) or not raw_field.strip():
        raise CompileError("leaf clause requires a non-empty 'field'")
    op = node.get("op")
    espo_op = NEUTRAL_TO_ESPO_OP.get(op)
    if espo_op is None:
        raise CompileError(f"unsupported neutral operator {op!r}")

    leaf: dict = {"field": resolve_ref(raw_field), "op": espo_op}
    if espo_op not in _ESPO_NO_VALUE:
        # The neutral AST guarantees a 'value' for every value-bearing op.
        leaf["value"] = node.get("value")
    return leaf

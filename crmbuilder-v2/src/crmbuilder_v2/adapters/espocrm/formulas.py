"""Neutral structured-formula AST → EspoCRM ``formula:`` block compiler.

PRJ-025 PI-197 (design §7/§9, DEC-438). The engine-neutral ``derived``
field carries a structured formula AST (``crmbuilder_v2.access.formulas``:
``concat`` / ``arithmetic`` / ``aggregate``). This module compiles that
shape into the EspoCRM ``formula:`` block the V1 deploy engine accepts and
``validate_program`` validates — the three forms documented in
``PRDs/product/app-yaml-schema.md`` §6.1.3:

* **concat** → ``{type: concat, parts: [{literal: "..."} | {field: name}]}``.
* **arithmetic** → ``{type: arithmetic, expression: "<infix string>"}``
  (the V1 schema's arithmetic expression is a parsed infix string of field
  references, numeric literals, ``+ - * /`` and parentheses).
* **aggregate** → ``{type: aggregate, function: <fn>, relatedEntity: <Entity>,
  via: <link>[, field: <name>][, where: [...]]}``. ``count`` carries no
  ``field``; the other functions carry the aggregated field.

Pure and deterministic: a fixed AST + a fixed reference resolver + a fixed
association resolver compile to a byte-stable structure. Field references
derive to lowerCamelCase via the injected ``resolve_ref`` (the same
resolver the condition compiler uses). The compiled block is attached to a
derived field's ``formula:`` key and must pass ``validate_program``
unchanged.
"""

from __future__ import annotations

from collections.abc import Callable

from crmbuilder_v2.access.vocab import ARITHMETIC_OPS

# EspoCRM precedence: ``* /`` bind tighter than ``+ -``. Used to decide where
# parentheses are required when flattening the arithmetic tree to infix.
_PRECEDENCE: dict[str, int] = {"+": 1, "-": 1, "*": 2, "/": 2}


class FormulaCompileError(ValueError):
    """Raised when a neutral formula cannot be compiled to an EspoCRM block.

    The neutral AST is validated at write time
    (``access.formulas.validate_formula``), so this is a defensive guard:
    a dangling association reference or a structurally-unexpected node
    routes the owning derived field's formula to a deferral rather than
    emitting invalid YAML.
    """


def compile_formula(
    formula: object,
    resolve_ref: Callable[[str], str],
    resolve_association: Callable[[str], tuple[str, str]],
    resolve_related_ref: Callable[[str], str],
) -> dict:
    """Compile one neutral formula AST to its EspoCRM ``formula:`` block.

    :param formula: a neutral formula AST (``concat`` / ``arithmetic`` /
        ``aggregate``), already validated by ``access.formulas``.
    :param resolve_ref: maps a neutral *same-entity* field reference (a
        field name or ``FLD-NNN``) to its emitted lowerCamelCase EspoCRM
        field name — used by ``concat`` parts and ``arithmetic`` operands,
        which reference fields on the derived field's own entity.
    :param resolve_association: maps a neutral ``association`` reference
        (an ``ASN-NNN`` identifier) to the ``(relatedEntity, via)`` pair
        an aggregate roll-up needs — the related entity's business name and
        the lowerCamelCase link name back to this entity.
    :param resolve_related_ref: maps an aggregate's aggregated ``field`` to
        its lowerCamelCase name — that field lives on the *related* entity,
        not this one, so it derives leniently (no same-entity emitted check).
    :returns: the EspoCRM ``formula:`` block dict.
    :raises FormulaCompileError: on an unexpected node shape or an
        unresolvable association.
    """
    if not isinstance(formula, dict):
        raise FormulaCompileError(
            f"formula must be an object, got {type(formula).__name__}"
        )
    kind = formula.get("kind")
    if kind == "concat":
        return _compile_concat(formula, resolve_ref)
    if kind == "arithmetic":
        return _compile_arithmetic(formula, resolve_ref)
    if kind == "aggregate":
        return _compile_aggregate(
            formula, resolve_related_ref, resolve_association
        )
    raise FormulaCompileError(f"unsupported formula kind {kind!r}")


def _compile_concat(
    formula: dict, resolve_ref: Callable[[str], str]
) -> dict:
    parts: list[dict] = []
    for part in formula.get("parts", []):
        if "literal" in part:
            parts.append({"literal": part["literal"]})
        elif "field" in part:
            parts.append({"field": resolve_ref(part["field"])})
        else:  # pragma: no cover — validator guarantees one of the two
            raise FormulaCompileError("concat part must be literal or field")
    return {"type": "concat", "parts": parts}


def _compile_arithmetic(
    formula: dict, resolve_ref: Callable[[str], str]
) -> dict:
    expression = _expr_to_infix(
        formula.get("expression"), resolve_ref, parent_precedence=0
    )
    return {"type": "arithmetic", "expression": expression}


def _expr_to_infix(
    expr: object,
    resolve_ref: Callable[[str], str],
    *,
    parent_precedence: int,
) -> str:
    """Flatten an arithmetic expression node to an infix string.

    Parenthesises a binary sub-expression only when its operator binds more
    loosely than the parent's (so ``a*(b+c)`` keeps its parens but ``a+b*c``
    does not), keeping the emitted string minimal yet correct.
    """
    if not isinstance(expr, dict):  # pragma: no cover — validator guards
        raise FormulaCompileError("arithmetic expression node must be an object")
    if "field" in expr:
        return resolve_ref(expr["field"])
    if "number" in expr:
        value = expr["number"]
        # Render an integral float as an int (``5.0`` → ``5``) for a clean
        # deterministic expression; keep genuine decimals as-is.
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)
    op = expr.get("op")
    if op not in ARITHMETIC_OPS:  # pragma: no cover — validator guards
        raise FormulaCompileError(f"unsupported arithmetic operator {op!r}")
    precedence = _PRECEDENCE[op]
    left = _expr_to_infix(expr["left"], resolve_ref, parent_precedence=precedence)
    right = _expr_to_infix(
        expr["right"], resolve_ref, parent_precedence=precedence
    )
    rendered = f"{left} {op} {right}"
    if precedence < parent_precedence:
        return f"({rendered})"
    return rendered


def _compile_aggregate(
    formula: dict,
    resolve_ref: Callable[[str], str],
    resolve_association: Callable[[str], tuple[str, str]],
) -> dict:
    function = formula["function"]
    related_entity, via = resolve_association(formula["association"])
    block: dict = {
        "type": "aggregate",
        "function": function,
        "relatedEntity": related_entity,
        "via": via,
    }
    if function != "count":
        block["field"] = resolve_ref(formula["field"])
    return block

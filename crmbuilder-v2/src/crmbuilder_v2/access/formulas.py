"""Neutral structured-formula validator (PRJ-025 PI-197, DEC-438).

A ``derived`` field carries an engine-neutral structured formula AST in its
``field_formula`` column. This module is the self-contained, dependency-free
validator for that shape — the access layer runs an incoming formula object
through :func:`validate_formula` before it is persisted, exactly as
``access.conditions.validate_condition`` guards the neutral condition AST.

The AST has three kinds (``crmbuilder_v2.access.vocab.FORMULA_KINDS``):

* **concat** — ``{"kind": "concat", "parts": [<part>, ...]}`` with a
  non-empty list of parts. Each part is either ``{"field": <ref str>}``
  (a same-record or looked-up field reference) or ``{"literal": <str>}``
  (a literal string). The parts are concatenated in order.
* **arithmetic** — ``{"kind": "arithmetic", "expression": <expr>}`` where
  ``expr`` is recursively one of: ``{"field": <ref>}`` (a numeric field
  reference), ``{"number": <int|float>}`` (a numeric literal), or
  ``{"op": <one of ARITHMETIC_OPS>, "left": <expr>, "right": <expr>}``
  (a binary operation).
* **aggregate** — ``{"kind": "aggregate", "function": <one of
  FORMULA_AGGREGATE_FUNCTIONS>, "association": <ASN ref str>, "field":
  <ref str>}``. ``field`` is ``null`` (or absent) for ``count`` and a
  non-empty reference string for every other function. ``association``
  names the neutral ``association`` the roll-up traverses.

A malformed object raises :class:`FormulaError` (a ``ValueError``). The
access layer catches it and re-raises as the field-scoped
``UnprocessableError`` (HTTP 422) so the wire surface stays uniform.
"""

from __future__ import annotations

from crmbuilder_v2.access.vocab import (
    ARITHMETIC_OPS,
    FORMULA_AGGREGATE_FUNCTIONS,
    FORMULA_KINDS,
)


class FormulaError(ValueError):
    """Raised when a neutral structured-formula object is malformed."""


def validate_formula(obj: object, *, _path: str = "formula") -> None:
    """Validate a neutral structured-formula object, raising on malformation.

    :param obj: the candidate formula AST (concat / arithmetic / aggregate).
    :raises FormulaError: when ``obj`` is not a well-formed neutral formula
        AST. The message names the offending sub-path.
    """
    if not isinstance(obj, dict):
        raise FormulaError(
            f"{_path}: must be a JSON object, got {type(obj).__name__}"
        )
    kind = obj.get("kind")
    if kind not in FORMULA_KINDS:
        raise FormulaError(
            f"{_path}.kind: must be one of {sorted(FORMULA_KINDS)}"
        )
    if kind == "concat":
        _validate_concat(obj, _path=_path)
    elif kind == "arithmetic":
        _validate_arithmetic(obj, _path=_path)
    else:
        _validate_aggregate(obj, _path=_path)


def _require_ref(value: object, *, path: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise FormulaError(f"{path}: must be a non-empty string reference")


def _validate_concat(obj: dict, *, _path: str) -> None:
    extra = set(obj) - {"kind", "parts"}
    if extra:
        raise FormulaError(f"{_path}: unexpected keys: {sorted(extra)}")
    parts = obj.get("parts")
    if not isinstance(parts, list):
        raise FormulaError(f"{_path}.parts: must be a list")
    if not parts:
        raise FormulaError(f"{_path}.parts: must be a non-empty list")
    for index, part in enumerate(parts):
        ppath = f"{_path}.parts[{index}]"
        if not isinstance(part, dict):
            raise FormulaError(f"{ppath}: must be an object")
        keys = set(part)
        if keys == {"field"}:
            _require_ref(part["field"], path=f"{ppath}.field")
        elif keys == {"literal"}:
            if not isinstance(part["literal"], str):
                raise FormulaError(f"{ppath}.literal: must be a string")
        else:
            raise FormulaError(
                f"{ppath}: must carry exactly one of 'field' or 'literal'"
            )


def _validate_arithmetic(obj: dict, *, _path: str) -> None:
    extra = set(obj) - {"kind", "expression"}
    if extra:
        raise FormulaError(f"{_path}: unexpected keys: {sorted(extra)}")
    if "expression" not in obj:
        raise FormulaError(f"{_path}: requires an 'expression'")
    _validate_expr(obj["expression"], _path=f"{_path}.expression")


def _validate_expr(expr: object, *, _path: str) -> None:
    if not isinstance(expr, dict):
        raise FormulaError(f"{_path}: must be an object")
    keys = set(expr)
    if keys == {"field"}:
        _require_ref(expr["field"], path=f"{_path}.field")
        return
    if keys == {"number"}:
        value = expr["number"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise FormulaError(f"{_path}.number: must be an int or float")
        return
    if keys == {"op", "left", "right"}:
        op = expr["op"]
        if op not in ARITHMETIC_OPS:
            raise FormulaError(
                f"{_path}.op: must be one of {sorted(ARITHMETIC_OPS)}"
            )
        _validate_expr(expr["left"], _path=f"{_path}.left")
        _validate_expr(expr["right"], _path=f"{_path}.right")
        return
    raise FormulaError(
        f"{_path}: must be a field ref, a number literal, or a binary op "
        "(op/left/right)"
    )


def _validate_aggregate(obj: dict, *, _path: str) -> None:
    extra = set(obj) - {"kind", "function", "association", "field"}
    if extra:
        raise FormulaError(f"{_path}: unexpected keys: {sorted(extra)}")
    function = obj.get("function")
    if function not in FORMULA_AGGREGATE_FUNCTIONS:
        raise FormulaError(
            f"{_path}.function: must be one of "
            f"{sorted(FORMULA_AGGREGATE_FUNCTIONS)}"
        )
    _require_ref(obj.get("association"), path=f"{_path}.association")
    field_ref = obj.get("field")
    if function == "count":
        if field_ref is not None:
            raise FormulaError(
                f"{_path}.field: must be null/absent for function 'count'"
            )
    else:
        _require_ref(field_ref, path=f"{_path}.field")

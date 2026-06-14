"""Neutral condition-AST validator (PRJ-025 PI-189 slice 2).

The engine-neutral design model carries field/visibility/validity gates,
list filters, and automation conditions as a single recursive JSON shape —
the *neutral condition AST*. It mirrors the V1 application's
``espo_impl/core/condition_expression.py`` (``LeafClause`` / ``AllNode`` /
``AnyNode``) but is a self-contained, dependency-free validator for the V2
store: the ``rule``, ``view``, and ``automation`` records all run an incoming
condition object through :func:`validate_condition` before it is persisted.

Shape (recursive):

* **Leaf** — ``{"field": <field name or FLD-NNN>, "op": <op>, "value": <any>}``
  where ``op`` is one of :data:`~crmbuilder_v2.access.vocab.NEUTRAL_CONDITION_OPS`.
  ``value`` is required for every op except ``is_empty`` / ``is_not_empty``
  (those carry no value).
* **Group** — ``{"all": [<node>, ...]}`` or ``{"any": [<node>, ...]}`` with a
  non-empty list of child nodes; ``all`` is a conjunction, ``any`` a
  disjunction. A group object carries exactly one of ``all`` / ``any`` and no
  other keys.

A malformed object raises :class:`ConditionError` (a ``ValueError``). The
access layer catches it and re-raises as the field-scoped
``UnprocessableError`` (HTTP 422) so the wire surface stays uniform.
"""

from __future__ import annotations

from crmbuilder_v2.access.vocab import NEUTRAL_CONDITION_OPS

# Leaf operators that assert presence/absence and therefore carry no value.
_VALUELESS_OPS = frozenset({"is_empty", "is_not_empty"})

_LEAF_KEYS = frozenset({"field", "op", "value"})
_GROUP_KEYS = frozenset({"all", "any"})


class ConditionError(ValueError):
    """Raised when a neutral condition object is malformed."""


def validate_condition(obj: object, *, _path: str = "condition") -> None:
    """Validate a neutral condition object, raising on any malformation.

    :param obj: the candidate condition (a leaf or a group, recursively).
    :raises ConditionError: when ``obj`` is not a well-formed neutral
        condition AST. The message names the offending sub-path.
    """
    if not isinstance(obj, dict):
        raise ConditionError(
            f"{_path}: must be a JSON object, got {type(obj).__name__}"
        )

    has_group_key = bool(_GROUP_KEYS & obj.keys())
    has_leaf_key = bool({"field", "op"} & obj.keys())

    if has_group_key and has_leaf_key:
        raise ConditionError(
            f"{_path}: object mixes group keys (all/any) with leaf keys "
            "(field/op)"
        )

    if has_group_key:
        _validate_group(obj, _path=_path)
        return

    _validate_leaf(obj, _path=_path)


def _validate_group(obj: dict, *, _path: str) -> None:
    if "all" in obj and "any" in obj:
        raise ConditionError(
            f"{_path}: a group carries exactly one of 'all' or 'any', not both"
        )
    key = "all" if "all" in obj else "any"
    extra = set(obj) - {key}
    if extra:
        raise ConditionError(
            f"{_path}: unexpected keys on a group: {sorted(extra)}"
        )
    children = obj[key]
    if not isinstance(children, list):
        raise ConditionError(f"{_path}.{key}: must be a list of conditions")
    if not children:
        raise ConditionError(f"{_path}.{key}: must be a non-empty list")
    for index, child in enumerate(children):
        validate_condition(child, _path=f"{_path}.{key}[{index}]")


def _validate_leaf(obj: dict, *, _path: str) -> None:
    if "field" not in obj:
        raise ConditionError(f"{_path}: a leaf clause requires a 'field'")
    field = obj["field"]
    if not isinstance(field, str) or not field.strip():
        raise ConditionError(f"{_path}.field: must be a non-empty string")

    if "op" not in obj:
        raise ConditionError(f"{_path}: a leaf clause requires an 'op'")
    op = obj["op"]
    if op not in NEUTRAL_CONDITION_OPS:
        raise ConditionError(
            f"{_path}.op: must be one of {sorted(NEUTRAL_CONDITION_OPS)}"
        )

    if op not in _VALUELESS_OPS and "value" not in obj:
        raise ConditionError(f"{_path}: op {op!r} requires a 'value'")

    extra = set(obj) - _LEAF_KEYS
    if extra:
        raise ConditionError(
            f"{_path}: unexpected keys on a leaf clause: {sorted(extra)}"
        )

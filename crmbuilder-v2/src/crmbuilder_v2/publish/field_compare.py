"""Comparing a declared field against the one on the instance
(REQ-609 / PI-522).

Two questions, and they are not the same question:

*Does anything need writing?* — what the publish path asks before it acts.
*Is this instance still what we declared?* — what a person asks afterwards.

One comparison answers both, but only because it keeps a third answer
separate: **the properties it could not check**. A property the design does
not declare, or one the platform did not return, is not a match and not a
difference — it is unknown, and a report that silently counted it as
matching would let an instance be called conformant on evidence nobody has.
:attr:`FieldComparison.conclusive` is that distinction.

The version 2 drift comparison in ``introspect`` answers a different
question again — stored design records against stored audit records — and
cannot stand in for this one, which compares a declaration against live
metadata at the moment of writing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

#: Field kinds that carry a list of allowed values.
ENUM_KINDS = frozenset({"enum", "multiEnum"})

#: The kind that mirrors a value from a linked object type.
MIRROR_KIND = "foreign"

#: Compared for every field kind.
COMMON_PROPERTIES: tuple[str, ...] = (
    "label",
    "required",
    "default",
    "readOnly",
    "audited",
    "min",
    "max",
    "maxLength",
)

#: Compared as well for a field with a list of allowed values.
ENUM_PROPERTIES: tuple[str, ...] = ("options", "translatedOptions", "style")

#: Compared as well for a mirrored field: the link it follows and the field
#: it mirrors.
MIRROR_PROPERTIES: tuple[str, ...] = ("link", "field")

#: Properties whose values are lists of allowed values, and so deserve a
#: missing-and-extra breakdown rather than two opaque lists.
_VALUE_LIST_PROPERTIES = frozenset({"options"})

_NOT_DECLARED = "the design does not declare it"
_NOT_RETURNED = "the instance did not report it"


def _render(value: Any) -> str:
    """Render a value for a sentence a person reads."""
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(str(item) for item in value) + "]"
    return repr(value)


@dataclass(frozen=True)
class FieldDifference:
    """One property that differs, or one that could not be checked.

    :ivar property: The property's name.
    :ivar declared: What the design says.
    :ivar live: What the instance says.
    :ivar message: The difference in words — this is what a person reads,
        so it names the values rather than saying that they differ.
    """

    property: str
    declared: Any
    live: Any
    message: str


@dataclass
class FieldComparison:
    """What comparing one declared field against the instance found.

    :ivar matches: Whether anything the design declares differs. This is the
        publish path's question: false means there is something to write.
    :ivar differences: The names of the properties that differ.
    :ivar kind_conflict: Whether the field exists with a different kind,
        which is not something to overwrite — changing a field's kind on a
        live instance discards its data, so the publish path leaves it and
        reports it.
    :ivar detailed: The differences in full.
    :ivar unknowns: The properties this comparison could not answer.
    """

    matches: bool
    differences: list[str] = field(default_factory=list)
    kind_conflict: bool = False
    detailed: list[FieldDifference] = field(default_factory=list)
    unknowns: list[FieldDifference] = field(default_factory=list)

    @property
    def conclusive(self) -> bool:
        """Whether every property compared could actually be answered.

        A conformance statement may not rest on an unanswered property.
        ``matches and not conclusive`` means "nothing seen to differ, and
        some things could not be seen" — which is neither conformant nor
        drifted, and must be reported as its own thing.
        """
        return not self.unknowns

    @property
    def detail_text(self) -> str:
        """Every difference, in one sentence a person can read."""
        return "; ".join(difference.message for difference in self.detailed)


def _compared_properties(kind: str) -> tuple[str, ...]:
    """The properties worth comparing for a field of this kind."""
    properties = COMMON_PROPERTIES
    if kind in ENUM_KINDS:
        properties += ENUM_PROPERTIES
    if kind == MIRROR_KIND:
        properties += MIRROR_PROPERTIES
    return properties


def _describe_value_lists(prop: str, declared: Any, live: Any) -> str:
    """Describe how two lists of allowed values differ.

    Naming the values that are missing and the ones that are extra is the
    difference between a message an operator can act on and two lists they
    have to diff by eye.
    """
    if not isinstance(declared, (list, tuple)) or not isinstance(
        live, (list, tuple)
    ):
        return (
            f"{prop} differs — the design has {_render(declared)} and the "
            f"instance has {_render(live)}"
        )
    missing = [value for value in declared if value not in live]
    extra = [value for value in live if value not in declared]
    parts: list[str] = []
    if missing:
        parts.append(f"missing from the instance: {_render(missing)}")
    if extra:
        parts.append(f"on the instance but not declared: {_render(extra)}")
    if not parts:
        # Same values, different order. The platform preserves the order, so
        # this is a real difference, but saying "missing: []" would be absurd.
        parts.append(
            f"same values in a different order — the design has "
            f"{_render(declared)}"
        )
    return f"{prop} differs — " + "; ".join(parts)


def compare_field(
    declared: Mapping[str, Any], live: Mapping[str, Any]
) -> FieldComparison:
    """Compare one declared field against the field on the instance.

    :param declared: The field as the design declares it, in the platform's
        own property names, as the publish path would send it. A property
        the design does not declare is absent or ``None``.
    :param live: The field as the instance reports it.
    :returns: What differs, and what could not be checked.
    """
    declared_kind = declared.get("type")
    live_kind = live.get("type")

    if declared_kind != live_kind:
        return FieldComparison(
            matches=False,
            kind_conflict=True,
            differences=["type"],
            detailed=[
                FieldDifference(
                    "type",
                    declared_kind,
                    live_kind,
                    f"type differs — the design declares "
                    f"{_render(declared_kind)} but the instance has "
                    f"{_render(live_kind)}. Changing a field's type on a live "
                    f"instance discards its data, so this one is left alone.",
                )
            ],
        )

    differences: list[str] = []
    detailed: list[FieldDifference] = []
    unknowns: list[FieldDifference] = []

    for prop in _compared_properties(declared_kind or ""):
        declared_value = declared.get(prop)
        if declared_value is None:
            unknowns.append(
                FieldDifference(
                    prop, None, live.get(prop), f"{prop} — {_NOT_DECLARED}"
                )
            )
            continue
        if prop not in live:
            unknowns.append(
                FieldDifference(
                    prop, declared_value, None, f"{prop} — {_NOT_RETURNED}"
                )
            )
            continue

        live_value = live.get(prop)
        if declared_value == live_value:
            continue

        if prop in _VALUE_LIST_PROPERTIES:
            message = _describe_value_lists(prop, declared_value, live_value)
        else:
            message = (
                f"{prop} differs — the design declares "
                f"{_render(declared_value)} and the instance has "
                f"{_render(live_value)}"
            )
        differences.append(prop)
        detailed.append(
            FieldDifference(prop, declared_value, live_value, message)
        )

    return FieldComparison(
        matches=not differences,
        differences=differences,
        detailed=detailed,
        unknowns=unknowns,
    )

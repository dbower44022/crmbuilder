"""Duplicate-detection rules a publish cannot write — REQ-635 (PI-549).

A duplicate-detection rule says which records count as the same person or the
same organisation. The design holds them, the emitter writes them into a
declaration, and the parser accepts the block — and then nothing happened to
it at all. No write, no refusal, no word to the operator. A design could say
"treat two contacts with the same electronic-mail address as one" and the
publish would carry it to the instance and drop it in silence.

There is no write path to build. The platform serves its definition metadata
for reading only, which is the same wall the saved-view and automation writers
hit, and version 1's three managers each stopped at the same place. What
version 1 did do — and version 2 did not — was say so, once per rule.

So this reports rather than applies: every declared rule comes back
:data:`UNAVAILABLE`, carrying the sentence a person needs to configure it by
hand. Comparing a declared rule against the instance is a separate thing,
approved in DEC-921 and DEC-927 and deliberately not built here: no design
carries a rule today, so the comparison would be written against a shape of
live metadata nobody has read. DEC-926 set that precedent for automations.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any

#: The platform will not take this one; a person must.
UNAVAILABLE = "unavailable"

#: Why, in the words the operator needs. Named once so the reason a rule was
#: not written reads the same wherever it is reported.
_NO_WRITE_PATH = (
    "the platform serves its definition metadata for reading only, so a "
    "duplicate-detection rule cannot be written by a publish. Configure it on "
    "the instance by hand."
)


@dataclass(frozen=True)
class DuplicateCheckIntent:
    """One duplicate-detection rule, as the design declares it.

    :ivar entity: The design's name for the object type it guards.
    :ivar identifier: The rule's own name in the declaration, where it has
        one — a rule without one is still reported, by its object type.
    :ivar fields: The field names the rule compares, for the operator to
        reproduce by hand.
    """

    entity: str
    identifier: str | None = None
    fields: tuple[str, ...] = ()

    @property
    def description(self) -> str:
        """The rule as a person would say it."""
        named = f"{self.entity}.{self.identifier}" if self.identifier else self.entity
        if self.fields:
            return f"{named} (matching on {', '.join(self.fields)})"
        return named


@dataclass
class DuplicateCheckOutcome:
    """What happened to one declared rule.

    :ivar name: The rule, as a person would say it. Called ``name`` because
        that is where the report looks for what an outcome is about — an
        outcome that invents its own word for it comes out as a question
        mark, which is how this was caught.
    :ivar status: Always :data:`UNAVAILABLE` — there is nothing else it can be
        until a write path exists.
    :ivar detail: Why.
    :ivar manual_config: What somebody must do by hand.
    """

    name: str
    status: str = UNAVAILABLE
    detail: str = _NO_WRITE_PATH
    manual_config: list[str] = dataclass_field(default_factory=list)

    @property
    def failed(self) -> bool:
        """Never. A platform limit is not a failure of the run."""
        return False


def intents_for(entity: str, block: Any) -> list[DuplicateCheckIntent]:
    """The rules one object type's declaration asks for.

    Tolerant of how a rule is written, because the point is to report it, not
    to validate it: a rule may be a mapping with a name and the fields it
    matches on, or a bare name. Anything else is still reported, under its
    object type, rather than dropped for being an unfamiliar shape — dropping
    it quietly is the defect this exists to end.
    """
    declared = (block or {}).get("duplicateChecks") if hasattr(block, "get") else None
    if not isinstance(declared, (list, tuple)):
        return []
    out: list[DuplicateCheckIntent] = []
    for rule in declared:
        if isinstance(rule, dict):
            fields = rule.get("fields")
            out.append(
                DuplicateCheckIntent(
                    entity=entity,
                    identifier=_text(rule.get("id") or rule.get("name")),
                    fields=tuple(
                        str(name)
                        for name in (fields if isinstance(fields, (list, tuple)) else ())
                    ),
                )
            )
        else:
            out.append(
                DuplicateCheckIntent(entity=entity, identifier=_text(rule))
            )
    return out


def _text(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None


def report_duplicate_checks(
    intents: Iterable[DuplicateCheckIntent],
) -> Sequence[DuplicateCheckOutcome]:
    """Report every declared rule as one a person must configure.

    Takes no client: there is nothing to ask the instance, because there is
    nothing this can write and nothing it yet knows how to read back.
    """
    return [
        DuplicateCheckOutcome(
            name=intent.description,
            manual_config=[f"{intent.description}: {_NO_WRITE_PATH}"],
        )
        for intent in intents
    ]

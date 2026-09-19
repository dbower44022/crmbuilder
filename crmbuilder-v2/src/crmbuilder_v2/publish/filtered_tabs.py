"""Applying declared navigation tabs and their filters (REQ-614 / PI-528).

A filtered tab is a pre-filtered list of records in the navigation, and it is
two things on the instance: a stored filter, which this module writes, and
the registration that puts the tab in the navigation, which lives in the
platform's own definition files and is handed to the operator instead.

The stored filter belongs to a paid extension. When the extension is absent
the platform answers "no such thing" — which is not a failure of the publish,
it is an instance that cannot hold this part of the design, and saying so
plainly is more useful than an error.

**A filter written in words keeps meaning those words.** A design that says
"the last thirty days" must mean thirty days from whenever the filter runs,
not thirty days from the day it was written, so the words are resolved as
the filter is applied. Version 2 could not do this at all: it emitted the
word and the instance received a word where it expected a date.
"""

from __future__ import annotations

import datetime
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any

from crmbuilder_v2.introspect.espo_client import format_error_detail
from crmbuilder_v2.publish.entities import AuthenticationRejected
from crmbuilder_v2.publish.espo_write_client import EspoWriteClient

#: What happened to a tab.
CREATED = "created"
SKIPPED = "skipped"
UNAVAILABLE = "unavailable"
FAILED = "failed"
PREVIEWED = "previewed"

#: The record the stored filter is kept as.
FILTER_RECORD = "ReportFilter"

#: Dates a design can write as words.
RELATIVE_DATES = frozenset({"today", "yesterday", "thisMonth", "lastMonth"})

_LAST_N_DAYS = re.compile(r"^lastNDays:(\d+)$")
_NEXT_N_DAYS = re.compile(r"^nextNDays:(\d+)$")

_NO_EXTENSION = (
    "this instance has no stored filters — the extension that provides them "
    "is not installed, so the tab cannot be created. Install it, or put the "
    "filter on the list view by hand."
)
_REGISTRATION = (
    "the tab itself is registered in the platform's own definition files, "
    "which its interface does not expose. Add the scope, the label and the "
    "tab list entry on the server, then rebuild."
)


def is_relative_date(value: Any) -> bool:
    """Whether a value is a date written as words."""
    if not isinstance(value, str):
        return False
    return (
        value in RELATIVE_DATES
        or bool(_LAST_N_DAYS.match(value))
        or bool(_NEXT_N_DAYS.match(value))
    )


def resolve_relative_date(
    value: str, today: datetime.date | None = None
) -> datetime.date:
    """Turn a date written as words into the date it means today.

    :param value: One of the words, or ``lastNDays:N`` / ``nextNDays:N``.
    :param today: The day to resolve against; the real one by default.
    :raises ValueError: If the value is not a date this system understands.
    """
    reference = today if today is not None else datetime.date.today()

    if value == "today":
        return reference
    if value == "yesterday":
        return reference - datetime.timedelta(days=1)
    if value == "thisMonth":
        return reference.replace(day=1)
    if value == "lastMonth":
        first_of_this_month = reference.replace(day=1)
        return (first_of_this_month - datetime.timedelta(days=1)).replace(day=1)

    match = _LAST_N_DAYS.match(value)
    if match:
        return reference - datetime.timedelta(days=int(match.group(1)))
    match = _NEXT_N_DAYS.match(value)
    if match:
        return reference + datetime.timedelta(days=int(match.group(1)))

    raise ValueError(
        f"{value!r} is not a date this system understands. It knows "
        f"{', '.join(sorted(RELATIVE_DATES))}, lastNDays:N and nextNDays:N."
    )


def resolve_dates(value: Any, today: datetime.date | None = None) -> Any:
    """Resolve every date written as words, at any depth in a filter."""
    if isinstance(value, Mapping):
        return {key: resolve_dates(item, today) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [resolve_dates(item, today) for item in value]
    if is_relative_date(value):
        return resolve_relative_date(value, today).isoformat()
    return value


@dataclass(frozen=True)
class TabIntent:
    """One navigation tab, as the design declares it.

    :ivar label: The tab's name, which is how the design refers to it and
        how the stored filter is named.
    :ivar entity: The platform's name for the object type it lists.
    :ivar where: The filter, in the platform's own shape.
    """

    label: str
    entity: str
    where: Sequence[Mapping[str, Any]] = ()


@dataclass
class TabOutcome:
    """What happened to one tab.

    :ivar label: The tab's name.
    :ivar entity: The object type it lists.
    :ivar status: One of :data:`CREATED`, :data:`SKIPPED`,
        :data:`UNAVAILABLE`, :data:`FAILED`, :data:`PREVIEWED`.
    :ivar detail: What a person needs to read about it.
    :ivar manual_config: What somebody must do by hand — always at least the
        registration that puts the tab in the navigation.
    """

    label: str
    entity: str
    status: str
    detail: str = ""
    manual_config: list[str] = dataclass_field(default_factory=list)

    @property
    def failed(self) -> bool:
        return self.status == FAILED


def _raise_if_unauthenticated(status: int) -> None:
    if status == 401:
        raise AuthenticationRejected(
            "the instance rejected the credential (401); nothing further "
            "can be applied"
        )


def _existing_filters(client: EspoWriteClient, entity: str) -> tuple[int, set[str]]:
    status, body = client.list_report_filters(entity)
    _raise_if_unauthenticated(status)
    names: set[str] = set()
    if status == 200:
        rows = body.get("list") if isinstance(body, Mapping) else body
        if isinstance(rows, Sequence):
            names = {
                str(row["name"])
                for row in rows
                if isinstance(row, Mapping) and row.get("name")
            }
    return status, names


def apply_tabs(
    client: EspoWriteClient,
    intents: Iterable[TabIntent],
    *,
    preview: bool = False,
    today: datetime.date | None = None,
) -> list[TabOutcome]:
    """Apply every declared navigation tab.

    :param client: A write-capable client for the target instance.
    :param intents: The tabs as declared.
    :param preview: When true, report what would happen and write nothing.
    :param today: The day dates written as words resolve against.
    :returns: One outcome per tab, each carrying the manual step the
        platform's interface cannot perform.
    :raises AuthenticationRejected: If the instance rejects the credential.
    """
    outcomes: list[TabOutcome] = []
    extension_absent = False
    listed: dict[str, set[str]] = {}

    for intent in intents:
        registration = [f"{intent.entity} — {intent.label}: {_REGISTRATION}"]

        if extension_absent:
            outcomes.append(
                TabOutcome(
                    intent.label,
                    intent.entity,
                    UNAVAILABLE,
                    _NO_EXTENSION,
                    manual_config=[f"{intent.label}: {_NO_EXTENSION}"],
                )
            )
            continue

        if intent.entity not in listed:
            status, names = _existing_filters(client, intent.entity)
            if status == 404:
                # The extension is not installed. Every later tab will meet
                # the same answer, so stop asking.
                extension_absent = True
                outcomes.append(
                    TabOutcome(
                        intent.label,
                        intent.entity,
                        UNAVAILABLE,
                        _NO_EXTENSION,
                        manual_config=[f"{intent.label}: {_NO_EXTENSION}"],
                    )
                )
                continue
            if status != 200:
                outcomes.append(
                    TabOutcome(
                        intent.label,
                        intent.entity,
                        FAILED,
                        f"the instance did not report its stored filters "
                        f"({status})",
                    )
                )
                continue
            listed[intent.entity] = names

        if intent.label in listed[intent.entity]:
            outcomes.append(
                TabOutcome(
                    intent.label,
                    intent.entity,
                    SKIPPED,
                    "the filter already exists",
                    manual_config=registration,
                )
            )
            continue

        if preview:
            outcomes.append(
                TabOutcome(
                    intent.label,
                    intent.entity,
                    PREVIEWED,
                    "the filter would be created",
                    manual_config=registration,
                )
            )
            continue

        payload = {
            "name": intent.label,
            "entityType": intent.entity,
            "data": {"where": resolve_dates(list(intent.where), today)},
        }
        status, body = client.create_report_filter(payload)
        _raise_if_unauthenticated(status)
        if status == 404:
            extension_absent = True
            outcomes.append(
                TabOutcome(
                    intent.label,
                    intent.entity,
                    UNAVAILABLE,
                    _NO_EXTENSION,
                    manual_config=[f"{intent.label}: {_NO_EXTENSION}"],
                )
            )
            continue
        if status != 200:
            outcomes.append(
                TabOutcome(
                    intent.label,
                    intent.entity,
                    FAILED,
                    f"the instance refused the filter ({status}): "
                    f"{format_error_detail(body)}",
                )
            )
            continue

        listed[intent.entity].add(intent.label)
        outcomes.append(
            TabOutcome(
                intent.label,
                intent.entity,
                CREATED,
                manual_config=registration,
            )
        )
    return outcomes

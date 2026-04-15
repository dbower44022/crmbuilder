"""Relative-date vocabulary for condition expressions.

Implements the relative-date resolution described in app-yaml-schema.md
Section 11.4. All functions are pure logic with no GUI dependencies.
"""

import datetime
import re
from typing import Final

RELATIVE_DATE_TOKENS: Final[set[str]] = {
    "today",
    "yesterday",
    "thisMonth",
    "lastMonth",
}

_LAST_N_DAYS_RE: Final[re.Pattern[str]] = re.compile(r"^lastNDays:(\d+)$")
_NEXT_N_DAYS_RE: Final[re.Pattern[str]] = re.compile(r"^nextNDays:(\d+)$")


def is_relative_date(value: str) -> bool:
    """Return True if *value* is a valid relative-date string.

    :param value: Candidate string to check.
    :returns: True when the string matches one of the bare tokens or
        the ``lastNDays:N`` / ``nextNDays:N`` patterns.
    """
    if value in RELATIVE_DATE_TOKENS:
        return True
    if _LAST_N_DAYS_RE.match(value) or _NEXT_N_DAYS_RE.match(value):
        return True
    return False


def resolve_relative_date(
    value: str,
    today: datetime.date | None = None,
) -> datetime.date:
    """Resolve a relative-date string to a concrete date.

    :param value: A valid relative-date string.
    :param today: Override for the current date (for testability).
    :returns: The resolved ``datetime.date``.
    :raises ValueError: If *value* is not a valid relative-date string.
    """
    ref = today if today is not None else datetime.date.today()

    if value == "today":
        return ref
    if value == "yesterday":
        return ref - datetime.timedelta(days=1)
    if value == "thisMonth":
        return ref.replace(day=1)
    if value == "lastMonth":
        first_of_this = ref.replace(day=1)
        last_month = first_of_this - datetime.timedelta(days=1)
        return last_month.replace(day=1)

    m = _LAST_N_DAYS_RE.match(value)
    if m:
        n = int(m.group(1))
        return ref - datetime.timedelta(days=n)

    m = _NEXT_N_DAYS_RE.match(value)
    if m:
        n = int(m.group(1))
        return ref + datetime.timedelta(days=n)

    raise ValueError(
        f"Invalid relative-date string: '{value}'. "
        f"Valid forms: {sorted(RELATIVE_DATE_TOKENS)}, lastNDays:N, nextNDays:N"
    )

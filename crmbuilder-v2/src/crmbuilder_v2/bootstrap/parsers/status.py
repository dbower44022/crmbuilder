"""Parse ``status.md`` into a list of status version rows.

Same shape as the charter parser — the markdown's ``## Change Log`` table
becomes the version history; the most recent row carries the full payload.
"""

from __future__ import annotations

from pathlib import Path

from crmbuilder_v2.bootstrap.parsers.charter import parse_charter


def parse_status(path: Path) -> list[dict]:
    """Parse ``status.md``. Returns the same shape as ``parse_charter`` —
    a list of version-row dicts.

    ``status.md`` did not historically include a ``## Change Log`` table
    when first bootstrapped, so the parser falls through to the
    "no changelog → single version 1" path. The current update added a
    Change Log table; both shapes are handled.
    """
    return parse_charter(path)

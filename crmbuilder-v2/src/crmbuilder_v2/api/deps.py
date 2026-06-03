"""Shared FastAPI dependencies and helpers.

Every endpoint opens a session against the single unified DB via
``writable_session`` / ``readonly_session``; the active engagement is
resolved per request by the scope middleware (the ``X-Engagement``
header) and applied as a row-level filter/stamp. (PI-β removed the
separate meta DB and its ``meta_session`` dependency — the engagement
registry now lives in the unified DB's ``engagements`` table.)
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from crmbuilder_v2.access.db import session_scope


@contextmanager
def writable_session() -> Iterator[Session]:
    """Open a unified-DB session that runs the JSON export hook on commit."""
    with session_scope(export=True) as s:
        yield s


@contextmanager
def readonly_session() -> Iterator[Session]:
    """Open a unified-DB read-only session (skips the JSON export hook)."""
    with session_scope(export=False) as s:
        yield s

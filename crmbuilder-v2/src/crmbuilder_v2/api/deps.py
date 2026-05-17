"""Shared FastAPI dependencies and helpers.

v0.5 slice A adds the meta-DB dependency alongside the per-engagement
DB dependencies. The existing ``writable_session`` /
``readonly_session`` continue to route to the active engagement's DB
(env-var-pointed via ``CRMBUILDER_V2_DB_PATH``); new ``meta_session``
routes to the meta DB at ``crmbuilder-v2/data/engagements.db``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.meta_db import meta_session_scope


@contextmanager
def writable_session() -> Iterator[Session]:
    """Open a per-engagement DB session that runs the JSON export hook on commit."""
    with session_scope(export=True) as s:
        yield s


@contextmanager
def readonly_session() -> Iterator[Session]:
    """Open a per-engagement DB read-only session (skips the JSON export hook)."""
    with session_scope(export=False) as s:
        yield s


@contextmanager
def meta_session() -> Iterator[Session]:
    """Open a meta DB session (engagement-registry CRUD).

    v0.5 slice A wiring. Engagement endpoints route here; all other
    endpoints continue to use ``writable_session`` /
    ``readonly_session``. See ``multi-engagement-architecture.md`` §3.10.
    """
    with meta_session_scope() as s:
        yield s

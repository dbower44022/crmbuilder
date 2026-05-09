"""Shared FastAPI dependencies and helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from crmbuilder_v2.access.db import session_scope


@contextmanager
def writable_session() -> Iterator[Session]:
    """Open a session that runs the JSON export hook on commit."""
    with session_scope(export=True) as s:
        yield s


@contextmanager
def readonly_session() -> Iterator[Session]:
    """Open a read-only session (skips the JSON export hook)."""
    with session_scope(export=False) as s:
        yield s

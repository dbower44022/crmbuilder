"""Change-log emission helpers.

Every mutating repository call invokes :func:`emit` to record the change.
The actor is taken from a context variable, default ``claude_session``;
callers can override via :func:`set_actor` before opening a session scope.
"""

from __future__ import annotations

from contextvars import ContextVar

from sqlalchemy.orm import Session

from crmbuilder_v2.access.models import ChangeLog
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ACTORS,
    CHANGE_LOG_OPERATIONS,
    ENTITY_TYPES,
)

_actor: ContextVar[str] = ContextVar(
    "crmbuilder_v2_actor", default="claude_session"
)


def set_actor(actor: str) -> None:
    if actor not in CHANGE_LOG_ACTORS:
        raise ValueError(
            f"actor must be one of {sorted(CHANGE_LOG_ACTORS)}, got {actor!r}"
        )
    _actor.set(actor)


def current_actor() -> str:
    return _actor.get()


def emit(
    session: Session,
    *,
    entity_type: str,
    entity_identifier: str,
    operation: str,
    before: dict | None,
    after: dict | None,
) -> ChangeLog:
    if entity_type not in ENTITY_TYPES | {"reference"}:
        raise ValueError(f"unknown entity_type {entity_type!r}")
    if operation not in CHANGE_LOG_OPERATIONS:
        raise ValueError(f"unknown operation {operation!r}")
    entry = ChangeLog(
        entity_type=entity_type,
        entity_identifier=entity_identifier,
        operation=operation,
        actor=current_actor(),
        before_payload=before,
        after_payload=after,
    )
    session.add(entry)
    return entry

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
    CHANGE_LOG_ENTITY_TYPES,
    CHANGE_LOG_OPERATIONS,
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


# PI-γ: map an authenticated principal's kind to the change_log actor *kind*.
_KIND_TO_ACTOR = {"human": "user", "service_agent": "service_agent"}


def _resolve_actor_and_principal() -> tuple[str, str | None]:
    """Return ``(actor, principal_id)`` for the current context.

    When an authenticated principal is active (PI-γ), the actor reflects its
    kind (``user`` / ``service_agent``) and ``principal_id`` records *which*
    principal. With no active principal (auth off / non-request callers), falls
    back to the explicit actor ContextVar (default ``claude_session``) and a
    ``None`` principal. The synthetic default-owner (``PRN-000``, auth-off) is
    treated as "no real principal" so attribution stays ``claude_session`` and
    the audit log is unchanged when auth is disabled.
    """
    # Imported lazily to avoid an access-layer import cycle at module load.
    from crmbuilder_v2.access.principal_scope import (
        DEFAULT_OWNER,
        get_active_principal,
    )

    principal = get_active_principal()
    if principal is None or principal.principal_id == DEFAULT_OWNER.principal_id:
        return current_actor(), None
    return _KIND_TO_ACTOR.get(principal.kind, "user"), principal.principal_id


def emit(
    session: Session,
    *,
    entity_type: str,
    entity_identifier: str,
    operation: str,
    before: dict | None,
    after: dict | None,
) -> ChangeLog:
    # CHANGE_LOG_ENTITY_TYPES = ENTITY_TYPES + the log-only types
    # (`reference`, `utilization_evidence`) — the same derived set the
    # `ck_changelog_entity_type` CHECK is rebuilt from, so this guard
    # cannot drift from the schema (WTK-091).
    if entity_type not in CHANGE_LOG_ENTITY_TYPES:
        raise ValueError(f"unknown entity_type {entity_type!r}")
    if operation not in CHANGE_LOG_OPERATIONS:
        raise ValueError(f"unknown operation {operation!r}")
    actor, principal_id = _resolve_actor_and_principal()
    entry = ChangeLog(
        entity_type=entity_type,
        entity_identifier=entity_identifier,
        operation=operation,
        actor=actor,
        principal_id=principal_id,
        before_payload=before,
        after_payload=after,
    )
    session.add(entry)
    return entry

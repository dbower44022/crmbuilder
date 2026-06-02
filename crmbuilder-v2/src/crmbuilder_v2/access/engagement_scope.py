"""Central row-level engagement scoping for the unified multi-engagement DB.

PI-123 Slice 2b (DEC-375 / D5). This is the mechanism that makes a single
multi-tenant database behave per-engagement: instead of selecting a *file*, the
access layer filters *rows* by ``engagement_id``. Three pieces, registered
centrally on a sessionmaker by :func:`install_engagement_scope`:

* **read filter** — a ``do_orm_execute`` listener that injects
  ``with_loader_criteria(EngagementScopedMixin, engagement_id == active)`` into
  every ORM SELECT, so a query under engagement A's context sees only A's rows.
  Crucially this also filters bare column selects (``select(Model.identifier)``),
  so the per-engagement identifier-assignment helpers stay correct with no
  per-repository change.
* **write stamp** — a ``before_flush`` listener that stamps ``engagement_id`` on
  every new scoped row from the active context, so repositories keep
  constructing ``SessionModel(...)`` without passing ``engagement_id``.
* **unset guard** — optional enforcement: when enabled, a scoped read or write
  with *no* active engagement raises rather than silently spanning all
  engagements. Off by default so the mechanism is inert until the unified-DB
  runtime turns it on.

**Dormant by default.** With no active engagement set, the filter and stamp are
no-ops, so installing this on the current single-engagement-per-file runtime
changes nothing — every query still returns the file's rows. It only does work
once a caller sets an active engagement (the request middleware in Slice 2c /
the unified-DB cutover). Until then it is safe but inert.

The active engagement is the engagement's **identifier** (``ENG-NNN``), held in a
:class:`contextvars.ContextVar` so it is correct under threads and asyncio
without leaking across requests.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token

from sqlalchemy import event
from sqlalchemy.orm import with_loader_criteria

from crmbuilder_v2.access.models import EngagementScopedMixin

# The active engagement identifier (``ENG-NNN``) for the current context, or
# ``None`` meaning "no active engagement" (dormant / legacy single-file mode).
_active_engagement: ContextVar[str | None] = ContextVar(
    "crmbuilder_active_engagement", default=None
)

# Enforcement is a process-wide runtime mode (not per-context): the unified-DB
# runtime turns it on so an un-scoped scoped-query/write fails loud. A plain
# module flag, toggled at app startup; tests flip it around a block.
_enforce: bool = False


class EngagementScopeNotSet(RuntimeError):
    """Raised when enforcement is on and a scoped op runs with no active engagement."""


# --------------------------------------------------------------------------
# Active-engagement context
# --------------------------------------------------------------------------
def get_active_engagement() -> str | None:
    """Return the active engagement identifier (``ENG-NNN``) or ``None``."""
    return _active_engagement.get()


def set_active_engagement(engagement_id: str | None) -> Token:
    """Set the active engagement; returns a token for :func:`reset_active_engagement`."""
    return _active_engagement.set(engagement_id)


def reset_active_engagement(token: Token) -> None:
    """Restore the active engagement to its value before ``token`` was issued."""
    _active_engagement.reset(token)


@contextmanager
def active_engagement(engagement_id: str | None) -> Iterator[None]:
    """Scope a block to ``engagement_id`` (``None`` clears scoping for the block)."""
    token = _active_engagement.set(engagement_id)
    try:
        yield
    finally:
        _active_engagement.reset(token)


# --------------------------------------------------------------------------
# Enforcement mode
# --------------------------------------------------------------------------
def set_enforcement(enabled: bool) -> bool:
    """Enable/disable the unset guard; returns the previous value."""
    global _enforce
    previous = _enforce
    _enforce = bool(enabled)
    return previous


def is_enforcing() -> bool:
    return _enforce


@contextmanager
def enforcement(enabled: bool = True) -> Iterator[None]:
    """Temporarily set enforcement (restores the prior value on exit)."""
    previous = set_enforcement(enabled)
    try:
        yield
    finally:
        set_enforcement(previous)


# --------------------------------------------------------------------------
# Event handlers
# --------------------------------------------------------------------------
def _statement_touches_scoped(execute_state) -> bool:
    """Whether the ORM statement targets an engagement-scoped entity."""
    try:
        descriptions = execute_state.statement.column_descriptions
    except Exception:  # pragma: no cover - non-ORM / unusual statements
        return False
    for desc in descriptions:
        entity = desc.get("entity")
        if (
            entity is not None
            and isinstance(entity, type)
            and issubclass(entity, EngagementScopedMixin)
        ):
            return True
    return False


def _do_orm_execute(execute_state) -> None:
    # Only plain ORM SELECTs — never relationship lazy-loads or column
    # refreshes, which must not be re-filtered (SQLAlchemy multitenancy recipe).
    if (
        not execute_state.is_select
        or execute_state.is_column_load
        or execute_state.is_relationship_load
    ):
        return
    active = _active_engagement.get()
    if active is None:
        if _enforce and _statement_touches_scoped(execute_state):
            raise EngagementScopeNotSet(
                "a scoped query ran with no active engagement while enforcement "
                "is on; set an active engagement (X-Engagement / the request "
                "middleware) before querying engagement-scoped tables."
            )
        return
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            EngagementScopedMixin,
            lambda cls: cls.engagement_id == active,
            include_aliases=True,
        )
    )


def _before_flush(session, flush_context, instances) -> None:
    active = _active_engagement.get()
    for obj in session.new:
        if not isinstance(obj, EngagementScopedMixin):
            continue
        if getattr(obj, "engagement_id", None) is not None:
            continue  # explicit value wins (e.g. the data-migration backfill)
        if active is not None:
            obj.engagement_id = active
        elif _enforce:
            raise EngagementScopeNotSet(
                f"new {type(obj).__name__} has no engagement_id and no active "
                "engagement is set while enforcement is on; un-scoped writes are "
                "refused in multi-tenant mode."
            )


# --------------------------------------------------------------------------
# Installation
# --------------------------------------------------------------------------
def install_engagement_scope(session_factory) -> None:
    """Register the read filter + write stamp on ``session_factory``.

    Idempotent. ``session_factory`` is a :class:`~sqlalchemy.orm.sessionmaker`
    (or Session class); sessions it produces inherit the scoping. Registering
    is harmless while dormant — the handlers no-op until an active engagement is
    set, so this can be wired into the live runtime ahead of the cutover.
    """
    if not event.contains(session_factory, "do_orm_execute", _do_orm_execute):
        event.listen(session_factory, "do_orm_execute", _do_orm_execute)
    if not event.contains(session_factory, "before_flush", _before_flush):
        event.listen(session_factory, "before_flush", _before_flush)


def uninstall_engagement_scope(session_factory) -> None:
    """Remove the handlers from ``session_factory`` (idempotent; for tests)."""
    if event.contains(session_factory, "do_orm_execute", _do_orm_execute):
        event.remove(session_factory, "do_orm_execute", _do_orm_execute)
    if event.contains(session_factory, "before_flush", _before_flush):
        event.remove(session_factory, "before_flush", _before_flush)

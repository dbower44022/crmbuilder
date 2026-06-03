"""Active-principal context for the multi-user API (PI-γ — PRJ-019 / PI-127).

Mirrors :mod:`crmbuilder_v2.access.engagement_scope`: a ``ContextVar`` holds the
authenticated principal for the current request, set by the principal-resolution
middleware (the outermost middleware) and read by the RBAC guard and the
change-log attribution.

**Auth off by default.** When ``Settings.principal_auth_enabled`` is False (the
single-operator localhost default), the resolver yields :data:`DEFAULT_OWNER` —
a synthetic ``owner`` principal allowed on every engagement — so today's
zero-token flow is preserved and the whole suite stays green. Auth becomes
load-bearing only when the service is deployed and the flag is turned on.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Principal:
    """The authenticated actor for a request.

    ``roles`` is the set of role names the principal holds *anywhere*;
    ``roles_by_engagement`` maps an engagement identifier to the roles held on
    that engagement (the per-engagement rights that RBAC composes with the
    row-level scope). ``allowed_engagements`` is the set of engagements the
    principal may select. ``is_owner`` short-circuits the system/shared-table
    and token-admin gates.
    """

    principal_id: str
    kind: str
    roles: frozenset[str] = frozenset()
    roles_by_engagement: dict[str, frozenset[str]] = field(default_factory=dict)
    allowed_engagements: frozenset[str] = frozenset()
    # An owner is allowed on every engagement regardless of explicit
    # assignments (the default-owner localhost principal, and any human granted
    # the ``owner`` role on the catalog/system tables).
    all_engagements: bool = False

    @property
    def is_owner(self) -> bool:
        return "owner" in self.roles

    def is_engagement_allowed(self, engagement_id: str | None) -> bool:
        """True if this principal may act on ``engagement_id``.

        ``None`` (an unscoped request) is always allowed — scoping enforcement
        is a separate concern. An ``all_engagements`` principal is allowed
        everywhere; otherwise the engagement must be in ``allowed_engagements``.
        """
        if engagement_id is None:
            return True
        if self.all_engagements:
            return True
        return engagement_id in self.allowed_engagements


# The synthetic principal used when auth is disabled: a localhost owner with
# rights on every engagement and no backing DB row. ``principal_id`` is a
# reserved sentinel that never collides with a minted ``PRN-NNN``.
DEFAULT_OWNER = Principal(
    principal_id="PRN-000",
    kind="human",
    roles=frozenset({"owner"}),
    roles_by_engagement={},
    allowed_engagements=frozenset(),
    all_engagements=True,
)


_active_principal: ContextVar[Principal | None] = ContextVar(
    "crmbuilder_active_principal", default=None
)


def get_active_principal() -> Principal | None:
    """Return the active principal for the current context, or ``None``."""
    return _active_principal.get()


def set_active_principal(principal: Principal | None) -> Token:
    """Set the active principal; returns a token for :func:`reset_active_principal`."""
    return _active_principal.set(principal)


def reset_active_principal(token: Token) -> None:
    """Restore the active principal to its value before ``token`` was issued."""
    _active_principal.reset(token)

"""RBAC permission checks (PI-γ — PRJ-019 / PI-127).

A thin guard composed with the row-level engagement scope: given the active
principal and active engagement, decide whether an operation's required
permission is granted. The role → permission map lives in
:data:`crmbuilder_v2.access.vocab.ROLE_PERMISSIONS`.

**Auth off ⇒ open.** All checks are gated by ``Settings.principal_auth_enabled``;
when off, every check passes (the default-owner localhost flow). When on, the
permission must be granted by some role the principal holds on the active
engagement (or any ``owner`` role, which is total and engagement-spanning).
"""

from __future__ import annotations

from crmbuilder_v2.access.principal_scope import (
    Principal,
    get_active_principal,
)
from crmbuilder_v2.access.vocab import ROLE_PERMISSIONS
from crmbuilder_v2.config import get_settings


class PermissionDenied(Exception):
    """Raised when the active principal lacks a required permission."""

    http_status = 403
    code = "permission_denied"

    def __init__(self, permission: str, detail: str | None = None) -> None:
        self.permission = permission
        super().__init__(
            detail or f"principal lacks the {permission!r} permission"
        )


def principal_permissions(
    principal: Principal, engagement_id: str | None
) -> frozenset[str]:
    """Return the permissions ``principal`` has on ``engagement_id``.

    An ``owner`` (system owner) has every permission everywhere. Otherwise the
    permissions are the union over the roles held on the active engagement.
    """
    if principal.is_owner:
        return ROLE_PERMISSIONS["owner"]
    roles = principal.roles_by_engagement.get(engagement_id or "", frozenset())
    perms: set[str] = set()
    for role in roles:
        perms |= ROLE_PERMISSIONS.get(role, frozenset())
    return frozenset(perms)


def has_permission(
    principal: Principal | None,
    engagement_id: str | None,
    permission: str,
) -> bool:
    """True if ``principal`` is granted ``permission`` on ``engagement_id``.

    A ``None`` principal (no active principal at all, auth on) is denied.
    """
    if principal is None:
        return False
    return permission in principal_permissions(principal, engagement_id)


def check(
    permission: str,
    *,
    engagement_id: str | None,
    principal: Principal | None = None,
) -> None:
    """Raise :class:`PermissionDenied` if the active principal lacks ``permission``.

    A no-op when ``principal_auth_enabled`` is off. Reads the active principal
    from the context when ``principal`` is not supplied.
    """
    if not get_settings().principal_auth_enabled:
        return
    actor = principal if principal is not None else get_active_principal()
    if not has_permission(actor, engagement_id, permission):
        who = actor.principal_id if actor is not None else "<anonymous>"
        raise PermissionDenied(
            permission,
            detail=(
                f"principal {who} lacks {permission!r} on engagement "
                f"{engagement_id or '<none>'}"
            ),
        )

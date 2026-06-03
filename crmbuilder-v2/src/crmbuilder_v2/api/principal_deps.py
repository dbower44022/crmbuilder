"""FastAPI RBAC dependencies (PI-γ — PRJ-019 / PI-127).

``require_permission(perm)`` is the route-level guard that composes the RBAC
check with the already-active engagement scope: it reads the active engagement
(set by the engagement middleware) and the active principal (set by the
principal middleware) and raises :class:`PermissionDenied` (→ 403) when the
permission is not granted. A no-op when ``principal_auth_enabled`` is off.

Usage::

    @router.post("", dependencies=[Depends(require_permission("admin"))])
    def mint(...):
        ...
"""

from __future__ import annotations

from collections.abc import Callable

from crmbuilder_v2.access import rbac
from crmbuilder_v2.access.engagement_scope import get_active_engagement
from crmbuilder_v2.access.principal_scope import (
    Principal,
    get_active_principal,
)


def require_permission(permission: str) -> Callable[[], None]:
    """Return a dependency that enforces ``permission`` on the active engagement."""

    def _dependency() -> None:
        rbac.check(permission, engagement_id=get_active_engagement())

    return _dependency


def active_principal_dep() -> Principal | None:
    """Dependency that returns the request's active principal (or ``None``)."""
    return get_active_principal()

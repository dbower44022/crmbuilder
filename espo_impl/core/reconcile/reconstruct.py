"""Reconstruct a live CRM-only item into the YAML dict to insert into source.

Used for whole-item capture (the CRM_ONLY case): a role/team that exists in the
live CRM but in no program file is rebuilt into its ``roles:``/``teams:`` mapping
so it can be appended to source. Reuses the Audit feature's serializers (the
single source of truth for the YAML shape, incl. the five-action scope blocks and
the schema-managed permission keys) via an ``AuditManager(client=None)`` — the
``_*_to_yaml_dict`` methods are pure.
"""
from __future__ import annotations

from typing import Any

from espo_impl.core.audit_manager import AuditManager

_AUDIT = AuditManager(client=None)

#: Permission/scope values the YAML role schema can represent. EspoCRM also uses
#: 'not-set' (no explicit restriction), which is NOT in this set — a role using it
#: cannot be faithfully captured until the schema is extended (see
#: :func:`role_representability_issue`).
_VALID_SCOPE = {"all", "team", "own", "no"}


def role_to_yaml(role_view) -> dict[str, Any]:
    """A live role (``RoleAuditResult``) -> its ``roles:`` list-item mapping."""
    return _AUDIT._role_to_yaml_dict(role_view)


def role_representability_issue(role_yaml: dict[str, Any]) -> str | None:
    """Return a reason if ``role_yaml`` holds a value the schema can't represent.

    Guards whole-role capture from writing YAML that won't re-parse: EspoCRM
    permission/scope values like ``not-set`` are outside the schema vocabulary.
    Returns the first offending ``path=value`` string, or ``None`` if clean.
    """
    perms = role_yaml.get("system_permissions") or {}
    for key in ("assignment_permission", "user_permission"):
        val = perms.get(key)
        if val is not None and val not in _VALID_SCOPE:
            return f"system_permissions.{key}={val!r}"
    for entity, access in (role_yaml.get("scope_access") or {}).items():
        for key in ("read", "edit", "delete", "stream"):
            val = access.get(key)
            if val is not None and val not in _VALID_SCOPE:
                return f"scope_access.{entity}.{key}={val!r}"
    return None


def team_to_yaml(team_view) -> dict[str, Any]:
    """A live team (``TeamAuditResult``) -> its ``teams:`` list-item mapping."""
    return _AUDIT._team_to_yaml_dict(team_view)

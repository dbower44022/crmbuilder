"""Compute role and team differences between live CRM and source YAML.

No equivalent of FieldComparator existed for security, so this builds the
comparison, mirroring :func:`diff_fields` / :func:`diff_layouts`: pure functions
over pre-normalized inputs, with per-property CHANGED records and whole-item
CRM_ONLY / YAML_ONLY records.

Both sides expose the same typed sub-objects, so the live side can be either a
``RoleDefinition``/``TeamDefinition`` or the Audit feature's
``RoleAuditResult``/``TeamAuditResult`` (the live-capture glue builds these via
the audit reverse-mappers). Inputs are keyed by name:

* roles — ``{role_name: role_view}`` where ``role_view`` has ``.description``,
  ``.scope_access`` (``dict[str, ScopeAccess]``), ``.system_permissions``
  (``SystemPermissions | None``).
* teams — ``{team_name: team_view}`` with ``.description``.

``Difference.entity`` carries the role/team name for these config types (the
role/team is the container); the locator holds the precise sub-address.

Forward-asymmetry (matching FieldComparator): scope_access is compared only for
entities the YAML declares — live-only entity scopes (mostly EspoCRM system
scopes) are not flagged — and system_permissions only when the YAML manages them
(``system_permissions`` is not ``None``). This is a v1 boundary, surfaced in the
report rather than silently widening scope.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from espo_impl.core.models import ScopeAccess, SystemPermissions
from espo_impl.core.reconcile.locators import RoleLocator, TeamLocator
from espo_impl.core.reconcile.models import ConfigType, DiffCategory, Difference

_SCOPE_DIMS = ("create", "read", "edit", "delete", "stream")
_SYS_PERMS = (
    "assignment_permission",
    "user_permission",
    "export",
    "mass_update",
    "portal",
)
_DEFAULT_ACCESS = ScopeAccess()  # all-deny: the effective scope when live omits an entity


def _norm_desc(value: str | None) -> str | None:
    """Normalise a description so ``None`` and ``""`` compare equal (team rule)."""
    return value or None


def _role_changes(name, desired, live, src: Path | None) -> list[Difference]:
    out: list[Difference] = []

    if _norm_desc(desired.description) != _norm_desc(getattr(live, "description", None)):
        out.append(
            Difference(
                config_type=ConfigType.ROLE,
                category=DiffCategory.CHANGED,
                entity=name,
                locator=RoleLocator(name, part="description"),
                property="description",
                yaml_value=desired.description,
                crm_value=getattr(live, "description", None),
                source_file=src,
            )
        )

    live_scope = getattr(live, "scope_access", None) or {}
    for ent, d_access in (desired.scope_access or {}).items():
        # An entity the YAML grants but the live role omits is effectively denied.
        l_access = live_scope.get(ent) or _DEFAULT_ACCESS
        for dim in _SCOPE_DIMS:
            d_val = getattr(d_access, dim)
            l_val = getattr(l_access, dim)
            if d_val != l_val:
                out.append(
                    Difference(
                        config_type=ConfigType.ROLE,
                        category=DiffCategory.CHANGED,
                        entity=name,
                        locator=RoleLocator(name, part="scope_access", entity=ent, key=dim),
                        property=f"scope_access.{ent}.{dim}",
                        yaml_value=d_val,
                        crm_value=l_val,
                        source_file=src,
                    )
                )

    if desired.system_permissions is not None:
        l_perms = getattr(live, "system_permissions", None) or SystemPermissions()
        for key in _SYS_PERMS:
            d_val = getattr(desired.system_permissions, key)
            l_val = getattr(l_perms, key)
            if d_val != l_val:
                out.append(
                    Difference(
                        config_type=ConfigType.ROLE,
                        category=DiffCategory.CHANGED,
                        entity=name,
                        locator=RoleLocator(name, part="system_permissions", key=key),
                        property=f"system_permissions.{key}",
                        yaml_value=d_val,
                        crm_value=l_val,
                        source_file=src,
                    )
                )

    return out


def diff_roles(
    desired: dict[str, Any],
    live: dict[str, Any],
    *,
    source_files: dict[str, Path] | None = None,
) -> list[Difference]:
    """Compute role differences. CHANGED per differing property; whole-role
    CRM_ONLY / YAML_ONLY for roles present on only one side."""
    source_files = source_files or {}
    diffs: list[Difference] = []

    for name in sorted(set(desired) | set(live)):
        in_yaml = name in desired
        in_crm = name in live
        src = source_files.get(name)

        if in_yaml and in_crm:
            diffs.extend(_role_changes(name, desired[name], live[name], src))
        elif in_crm:
            diffs.append(
                Difference(
                    config_type=ConfigType.ROLE,
                    category=DiffCategory.CRM_ONLY,
                    entity=name,
                    locator=RoleLocator(name),
                    crm_value=live[name],
                    full_crm_block=live[name],
                )
            )
        else:
            diffs.append(
                Difference(
                    config_type=ConfigType.ROLE,
                    category=DiffCategory.YAML_ONLY,
                    entity=name,
                    locator=RoleLocator(name),
                    yaml_value=desired[name],
                    source_file=src,
                )
            )

    return diffs


def diff_teams(
    desired: dict[str, Any],
    live: dict[str, Any],
    *,
    source_files: dict[str, Path] | None = None,
) -> list[Difference]:
    """Compute team differences (description only; teams carry nothing else in
    YAML). CHANGED description; whole-team CRM_ONLY / YAML_ONLY otherwise."""
    source_files = source_files or {}
    diffs: list[Difference] = []

    for name in sorted(set(desired) | set(live)):
        in_yaml = name in desired
        in_crm = name in live
        src = source_files.get(name)

        if in_yaml and in_crm:
            d, l = desired[name], live[name]
            if _norm_desc(d.description) != _norm_desc(getattr(l, "description", None)):
                diffs.append(
                    Difference(
                        config_type=ConfigType.TEAM,
                        category=DiffCategory.CHANGED,
                        entity=name,
                        locator=TeamLocator(name, part="description"),
                        property="description",
                        yaml_value=d.description,
                        crm_value=getattr(l, "description", None),
                        source_file=src,
                    )
                )
        elif in_crm:
            diffs.append(
                Difference(
                    config_type=ConfigType.TEAM,
                    category=DiffCategory.CRM_ONLY,
                    entity=name,
                    locator=TeamLocator(name),
                    crm_value=live[name],
                    full_crm_block=live[name],
                )
            )
        else:
            diffs.append(
                Difference(
                    config_type=ConfigType.TEAM,
                    category=DiffCategory.YAML_ONLY,
                    entity=name,
                    locator=TeamLocator(name),
                    yaml_value=desired[name],
                    source_file=src,
                )
            )

    return diffs

"""Security (role/team) diff tests — offline, using RoleDefinition both sides.

RoleDefinition/TeamDefinition satisfy the duck-typed 'view' the comparator
expects (so does the audit RoleAuditResult), so they double as live-side stand-ins
here. Covers description, per-scope-dimension, system-permission, the
YAML-grants-but-live-denies case, the forward-asymmetry (unmanaged sections not
flagged), and whole-role/team CRM_ONLY / YAML_ONLY.
"""
from __future__ import annotations

from pathlib import Path

from espo_impl.core.models import (
    RoleDefinition,
    ScopeAccess,
    SystemPermissions,
    TeamDefinition,
)
from espo_impl.core.reconcile.locators import RoleLocator, TeamLocator
from espo_impl.core.reconcile.models import ConfigType, DiffCategory
from espo_impl.core.reconcile.security_diff import diff_roles, diff_teams

SRC = Path("security/security.yaml")


def _role(name, **kw):
    return RoleDefinition(name=name, **kw)


def test_role_description_change():
    desired = {"Mentor": _role("Mentor", description="Old")}
    live = {"Mentor": _role("Mentor", description="New")}

    diffs = diff_roles(desired, live, source_files={"Mentor": SRC})

    assert len(diffs) == 1
    d = diffs[0]
    assert d.config_type is ConfigType.ROLE and d.category is DiffCategory.CHANGED
    assert d.property == "description"
    assert (d.yaml_value, d.crm_value) == ("Old", "New")
    assert d.locator == RoleLocator("Mentor", part="description")
    assert d.source_file == SRC


def test_scope_dimension_change():
    desired = {"Mentor": _role("Mentor", scope_access={"Contact": ScopeAccess(read="team")})}
    live = {"Mentor": _role("Mentor", scope_access={"Contact": ScopeAccess(read="all")})}

    diffs = diff_roles(desired, live)

    assert len(diffs) == 1
    assert diffs[0].property == "scope_access.Contact.read"
    assert (diffs[0].yaml_value, diffs[0].crm_value) == ("team", "all")
    assert diffs[0].locator == RoleLocator("Mentor", part="scope_access", entity="Contact", key="read")


def test_yaml_grants_but_live_denies_entity():
    # YAML grants Contact.read=team; live role has no Contact scope at all -> deny.
    desired = {"Mentor": _role("Mentor", scope_access={"Contact": ScopeAccess(read="team", edit="team")})}
    live = {"Mentor": _role("Mentor", scope_access={})}

    diffs = diff_roles(desired, live)

    props = {d.property for d in diffs}
    assert "scope_access.Contact.read" in props   # team vs default "no"
    assert "scope_access.Contact.edit" in props


def test_system_permission_change():
    desired = {"Mentor": _role("Mentor", system_permissions=SystemPermissions(export=True))}
    live = {"Mentor": _role("Mentor", system_permissions=SystemPermissions(export=False))}

    diffs = diff_roles(desired, live)

    assert len(diffs) == 1
    assert diffs[0].property == "system_permissions.export"
    assert (diffs[0].yaml_value, diffs[0].crm_value) == (True, False)


def test_unmanaged_sections_not_flagged():
    # YAML declares no scope_access and no system_permissions; live has both set.
    desired = {"Mentor": _role("Mentor")}
    live = {"Mentor": _role("Mentor", scope_access={"Contact": ScopeAccess(read="all")},
                           system_permissions=SystemPermissions(export=True))}

    assert diff_roles(desired, live) == []


def test_matching_role_no_diffs():
    role = lambda: _role("Mentor", description="x",
                         scope_access={"Contact": ScopeAccess(read="team", create=True)},
                         system_permissions=SystemPermissions(export=True, assignment_permission="team"))
    assert diff_roles({"Mentor": role()}, {"Mentor": role()}) == []


def test_role_crm_only_and_yaml_only():
    desired = {"OldRole": _role("OldRole")}
    live = {"NewRole": _role("NewRole")}

    diffs = diff_roles(desired, live, source_files={"OldRole": SRC})
    by_cat = {d.category: d for d in diffs}

    assert by_cat[DiffCategory.YAML_ONLY].entity == "OldRole"
    assert by_cat[DiffCategory.YAML_ONLY].source_file == SRC
    assert by_cat[DiffCategory.CRM_ONLY].entity == "NewRole"
    assert by_cat[DiffCategory.CRM_ONLY].source_file is None


def test_team_description_change_and_normalization():
    # "" vs None must be treated as equal (no diff); a real change is flagged.
    same = diff_teams({"T": TeamDefinition("T", description="")},
                      {"T": TeamDefinition("T", description=None)})
    assert same == []

    changed = diff_teams({"T": TeamDefinition("T", description="A")},
                         {"T": TeamDefinition("T", description="B")})
    assert len(changed) == 1
    assert changed[0].config_type is ConfigType.TEAM
    assert changed[0].locator == TeamLocator("T", part="description")


def test_team_crm_only_and_yaml_only():
    diffs = diff_teams({"Gone": TeamDefinition("Gone")}, {"Added": TeamDefinition("Added")})
    cats = {d.category for d in diffs}
    assert cats == {DiffCategory.YAML_ONLY, DiffCategory.CRM_ONLY}

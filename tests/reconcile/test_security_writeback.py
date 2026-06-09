"""Role/team write-back: surgical sets at depth + boolean spelling preservation.

The key concern is that role booleans are authored yes/no in YAML; writing a
Python bool back must keep that spelling (not emit true/false), while a block
that authored true/false keeps that.
"""
from __future__ import annotations

from ruamel.yaml import YAML

from espo_impl.core.reconcile.document import YamlDocument
from espo_impl.core.reconcile.locators import RoleLocator, TeamLocator
from espo_impl.core.reconcile.patcher import apply_role_change, apply_team_change

FIXTURE = '''\
roles:
  - name: "Mentor"
    description: "Mentor role"   # rationale kept
    scope_access:
      Contact:
        create: yes
        read: team
        edit: team
    system_permissions:
      assignment_permission: team
      export: yes
      portal: no
  - name: "Admin"
    scope_access:
      Account:
        create: true
        read: all
teams:
  - name: "Mentors"
    description: "The mentors team"
'''


def _changed(before, after):
    b, a = before.splitlines(), after.splitlines()
    assert len(b) == len(a)
    return [i for i, (x, y) in enumerate(zip(b, a)) if x != y]


def test_scope_string_change():
    doc = YamlDocument(FIXTURE)
    apply_role_change(doc, RoleLocator("Mentor", part="scope_access", entity="Contact", key="read"), "all")
    out = doc.render()
    changed = _changed(FIXTURE, out)
    assert len(changed) == 1
    assert out.splitlines()[changed[0]] == "        read: all"


def test_yesno_boolean_spelling_preserved():
    doc = YamlDocument(FIXTURE)
    # create: yes -> False must render as 'no', not 'false'.
    apply_role_change(doc, RoleLocator("Mentor", part="scope_access", entity="Contact", key="create"), False)
    out = doc.render()
    assert "        create: no" in out
    assert "create: false" not in out


def test_true_false_boolean_spelling_preserved():
    doc = YamlDocument(FIXTURE)
    # Admin authored create: true -> False must stay true/false family.
    apply_role_change(doc, RoleLocator("Admin", part="scope_access", entity="Account", key="create"), False)
    out = doc.render()
    assert "        create: false" in out


def test_system_permission_yesno():
    doc = YamlDocument(FIXTURE)
    apply_role_change(doc, RoleLocator("Mentor", part="system_permissions", key="export"), False)
    out = doc.render()
    assert "      export: no" in out


def test_description_change_keeps_comment():
    doc = YamlDocument(FIXTURE)
    apply_role_change(doc, RoleLocator("Mentor", part="description"), "Updated rationale")
    out = doc.render()
    assert 'description: "Updated rationale"   # rationale kept' in out


def test_team_description_change():
    doc = YamlDocument(FIXTURE)
    apply_team_change(doc, TeamLocator("Mentors", part="description"), "Mentor squad")
    out = doc.render()
    changed = _changed(FIXTURE, out)
    assert len(changed) == 1
    assert 'description: "Mentor squad"' in out


def test_result_reparses_correctly():
    doc = YamlDocument(FIXTURE)
    apply_role_change(doc, RoleLocator("Mentor", part="scope_access", entity="Contact", key="create"), False)
    apply_role_change(doc, RoleLocator("Mentor", part="system_permissions", key="export"), False)
    data = YAML().load(doc.render())
    contact = data["roles"][0]["scope_access"]["Contact"]
    assert contact["create"] == "no"        # ruamel loads yes/no as strings
    assert data["roles"][0]["system_permissions"]["export"] == "no"


def test_absent_key_rejected():
    doc = YamlDocument(FIXTURE)
    try:
        # Mentor's Contact scope has no 'delete' key authored.
        apply_role_change(doc, RoleLocator("Mentor", part="scope_access", entity="Contact", key="delete"), "all")
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError for absent key")

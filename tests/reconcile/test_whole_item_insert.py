"""Whole-item capture: insert CRM-only roles/teams into source YAML.

Covers the document primitive (create-block-at-EOF and append-to-existing) and
the reconciler's batched insertion (all items in one splice, content_version
bumped, result re-parses).
"""
from __future__ import annotations

from ruamel.yaml import YAML

from espo_impl.core.reconcile.document import YamlDocument
from espo_impl.core.reconcile.locators import RoleLocator, TeamLocator
from espo_impl.core.reconcile.models import ConfigType, DiffCategory, Difference
from espo_impl.core.reconcile.reconciler import apply_reconciliation

_NO_SECURITY = '''\
content_version: "1.0.0"
entities:
  Contact:
    fields:
      - name: x
        type: varchar
        label: "X"
'''

_WITH_TEAMS = '''\
content_version: "1.0.0"
teams:
  - name: "Existing Team"
    description: "already here"
'''


def _reparse(t):
    return YAML().load(t)


def _role_crm_only(name, src, block):
    return Difference(
        config_type=ConfigType.ROLE, category=DiffCategory.CRM_ONLY, entity=name,
        locator=RoleLocator(name), full_crm_block=block, source_file=src,
    )


def _team_crm_only(name, src, block):
    return Difference(
        config_type=ConfigType.TEAM, category=DiffCategory.CRM_ONLY, entity=name,
        locator=TeamLocator(name), full_crm_block=block, source_file=src,
    )


def test_primitive_creates_block_at_eof():
    doc = YamlDocument(_NO_SECURITY)
    doc.insert_or_create_top_level_block("teams", [
        {"name": "Mentor Team", "description": "Mentors"},
        {"name": "Sponsor Team"},
    ])
    data = _reparse(doc.render())
    assert [t["name"] for t in data["teams"]] == ["Mentor Team", "Sponsor Team"]
    # The original entities block is untouched.
    assert "x" == data["entities"]["Contact"]["fields"][0]["name"]


def test_primitive_appends_to_existing_block():
    doc = YamlDocument(_WITH_TEAMS)
    doc.insert_or_create_top_level_block("teams", [{"name": "New Team"}])
    names = [t["name"] for t in _reparse(doc.render())["teams"]]
    assert names == ["Existing Team", "New Team"]


def test_reconciler_captures_roles_and_teams_into_new_blocks(tmp_path):
    f = tmp_path / "security.yaml"
    f.write_text(_NO_SECURITY)
    role_block = {
        "name": "Mentor Role",
        "description": "Mentors",
        "scope_access": {"Contact": {"create": True, "read": "team", "edit": "team",
                                     "delete": "no", "stream": "team"}},
        "system_permissions": {"assignment_permission": "team", "user_permission": "team",
                               "export": True, "mass_update": False, "portal": False},
    }
    diffs = [
        _role_crm_only("Mentor Role", f, role_block),
        _role_crm_only("Admin Role", f, {"name": "Admin Role"}),
        _team_crm_only("Mentor Team", f, {"name": "Mentor Team", "description": "Mentors"}),
    ]

    result = apply_reconciliation(diffs)
    fr = result.files[0]
    assert len(fr.applied) == 3
    assert fr.new_version == "1.1.0"

    data = _reparse(f.read_text())
    assert [r["name"] for r in data["roles"]] == ["Mentor Role", "Admin Role"]
    assert [t["name"] for t in data["teams"]] == ["Mentor Team"]
    # Reconstructed structure survives the round-trip.
    mentor = data["roles"][0]
    assert mentor["scope_access"]["Contact"]["read"] == "team"
    assert mentor["system_permissions"]["export"] is True


def test_not_set_permission_is_representable_and_round_trips(tmp_path):
    # EspoCRM 'not-set' is admitted by the schema (SCOPE_ACCESS_VALUES) so a role
    # using it captures and re-parses faithfully (no semantic remap).
    from espo_impl.core.config_loader import ConfigLoader
    from espo_impl.core.reconcile.reconstruct import role_representability_issue

    block = {
        "name": "Standard User",
        "scope_access": {"Account": {"create": False, "read": "not-set",
                                     "edit": "no", "delete": "no", "stream": "not-set"}},
        "system_permissions": {"assignment_permission": "not-set",
                               "user_permission": "not-set", "export": False,
                               "mass_update": False, "portal": False},
    }
    assert role_representability_issue(block) is None  # no longer flagged

    f = tmp_path / "security.yaml"
    f.write_text(_NO_SECURITY)
    apply_reconciliation([_role_crm_only("Standard User", f, block)])

    role = next(r for r in ConfigLoader().load_program(f).roles if r.name == "Standard User")
    assert role.system_permissions.user_permission == "not-set"
    assert role.scope_access["Account"].read == "not-set"


def test_captured_role_reparses_via_config_loader(tmp_path):
    # The inserted role must load through the real ConfigLoader as a RoleDefinition.
    from espo_impl.core.config_loader import ConfigLoader

    f = tmp_path / "security.yaml"
    f.write_text(_NO_SECURITY)
    block = {
        "name": "Reviewer",
        "scope_access": {"Account": {"create": False, "read": "all", "edit": "no",
                                     "delete": "no", "stream": "all"}},
    }
    apply_reconciliation([_role_crm_only("Reviewer", f, block)])

    program = ConfigLoader().load_program(f)
    names = [r.name for r in program.roles]
    assert "Reviewer" in names
    role = next(r for r in program.roles if r.name == "Reviewer")
    assert role.scope_access["Account"].read == "all"


_WITH_ENTITY = '''\
content_version: "1.0.0"
entities:
  Session:
    fields:
      - name: x
        type: varchar
        label: "X"
'''


def _rel_crm_only(link, entity, src, block):
    from espo_impl.core.reconcile.locators import RelationshipLocator
    return Difference(
        config_type=ConfigType.RELATIONSHIP, category=DiffCategory.CRM_ONLY, entity=entity,
        locator=RelationshipLocator(entity, link), full_crm_block=block, source_file=src,
    )


def _layout_crm_only(ltype, entity, src, body):
    from espo_impl.core.reconcile.locators import LayoutLocator
    return Difference(
        config_type=ConfigType.LAYOUT, category=DiffCategory.CRM_ONLY, entity=entity,
        locator=LayoutLocator(entity, ltype), full_crm_block=body, source_file=src,
    )


def test_relationship_crm_only_creates_block(tmp_path):
    f = tmp_path / "MN-Session.yaml"
    f.write_text(_NO_SECURITY)
    block = {"name": "sessionMentors", "entity": "Session", "entityForeign": "Contact",
             "linkType": "manyToMany", "link": "mentors", "linkForeign": "sessions",
             "label": "Mentors", "labelForeign": "Sessions"}
    result = apply_reconciliation([_rel_crm_only("mentors", "Session", f, block)])
    assert len(result.files[0].applied) == 1
    data = _reparse(f.read_text())
    assert data["relationships"][0]["link"] == "mentors"
    assert data["relationships"][0]["linkType"] == "manyToMany"


def test_layout_crm_only_creates_layout_map(tmp_path):
    f = tmp_path / "MN-Session.yaml"
    f.write_text(_WITH_ENTITY)  # entity exists, no layout: block
    body = {"columns": [{"field": "name", "width": 30}, {"field": "x"}]}
    result = apply_reconciliation([_layout_crm_only("list", "Session", f, body)])
    assert len(result.files[0].applied) == 1
    data = _reparse(f.read_text())
    cols = data["entities"]["Session"]["layout"]["list"]["columns"]
    assert cols == [{"field": "name", "width": 30}, {"field": "x"}]
    # the original fields block is intact
    assert data["entities"]["Session"]["fields"][0]["name"] == "x"


def test_layout_crm_only_appends_to_existing_layout(tmp_path):
    body_src = _WITH_ENTITY.rstrip() + "\n    layout:\n      detail:\n        panels:\n          - label: \"Main\"\n"
    f = tmp_path / "MN-Session.yaml"
    f.write_text(body_src)
    body = {"columns": [{"field": "name"}]}
    apply_reconciliation([_layout_crm_only("list", "Session", f, body)])
    layout = _reparse(f.read_text())["entities"]["Session"]["layout"]
    assert "detail" in layout and "list" in layout  # both present


def test_layout_crm_only_missing_entity_errors(tmp_path):
    f = tmp_path / "MN-Session.yaml"
    f.write_text(_WITH_ENTITY)
    body = {"columns": [{"field": "name"}]}
    result = apply_reconciliation([_layout_crm_only("list", "Ghost", f, body)])
    fr = result.files[0]
    assert fr.applied == [] and "error:" in fr.not_applied[0][1]

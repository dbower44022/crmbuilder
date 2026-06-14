"""Tests for ``espo_impl.core.audit_manager``.

Focus on the audit-v1.2 Prompt H additions: team / role discovery,
reverse-translation of EspoCRM Role wire shape to Schema §12.3 /
§12.4 structured form, and ``security/security.yaml`` emission per
DEC-182.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import yaml

from espo_impl.core.audit_manager import (
    AuditManager,
    AuditOptions,
    AuditReport,
    EntityAuditResult,
    FilteredTabAuditResult,
    RoleAuditResult,
    TeamAuditResult,
)
from espo_impl.core.audit_utils import EntityClass
from espo_impl.core.condition_expression import (
    AllNode,
    AnyNode,
    LeafClause,
)
from espo_impl.core.models import ScopeAccess, SystemPermissions

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(**method_returns: Any) -> MagicMock:
    """Build a MagicMock EspoAdminClient with the given method returns."""
    client = MagicMock()
    profile = MagicMock()
    profile.url = "https://example.test"
    profile.name = "audit-test"
    client.profile = profile
    # Default any unset client method to a 200/empty-list response so
    # discovery loops don't hang on AttributeError.
    for name, value in method_returns.items():
        getattr(client, name).return_value = value
    # Entity formula-script capture (REQ-122) runs by default inside
    # run_audit; default it to "no formula" unless the test overrides it.
    if "get_entity_formula" not in method_returns:
        client.get_entity_formula.return_value = (200, {})
    return client


def _make_manager(
    client: MagicMock | None = None,
    options: AuditOptions | None = None,
) -> tuple[AuditManager, list[tuple[str, str]]]:
    """Construct an AuditManager bound to ``client`` with a capture log."""
    if client is None:
        client = _make_client()
    log: list[tuple[str, str]] = []
    manager = AuditManager(
        client=client,
        options=options or AuditOptions(),
        callback=lambda msg, color: log.append((msg, color)),
    )
    return manager, log


def _empty_report() -> AuditReport:
    return AuditReport(
        source_url="https://example.test",
        source_name="audit-test",
        timestamp="2026-05-24T07:30:00Z",
        output_dir="",
    )


# ---------------------------------------------------------------------------
# _discover_teams
# ---------------------------------------------------------------------------


def test_discover_teams_empty():
    client = _make_client(get_teams=(200, {"total": 0, "list": []}))
    manager, _log = _make_manager(client)
    report = _empty_report()

    result = manager._discover_teams(report)

    assert result == []
    assert report.errors == []


def test_discover_teams_two_teams():
    client = _make_client(
        get_teams=(200, {"total": 2, "list": [
            {"name": "Admins", "description": "Site administrators"},
            {"name": "Mentors", "description": ""},
        ]}),
    )
    manager, _log = _make_manager(client)
    report = _empty_report()

    result = manager._discover_teams(report)

    assert len(result) == 2
    assert result[0].name == "Admins"
    assert result[0].description == "Site administrators"
    # Empty description normalized to None.
    assert result[1].name == "Mentors"
    assert result[1].description is None


def test_discover_teams_http_error():
    client = _make_client(get_teams=(500, None))
    manager, _log = _make_manager(client)
    report = _empty_report()

    result = manager._discover_teams(report)

    assert result == []
    assert len(report.errors) == 1
    assert "Failed to fetch teams" in report.errors[0]


def test_discover_teams_skips_records_without_name():
    client = _make_client(
        get_teams=(200, {"total": 2, "list": [
            {"name": "Real Team"},
            {"description": "no name field"},
            "not even a dict",
            {"name": ""},
        ]}),
    )
    manager, _log = _make_manager(client)
    report = _empty_report()

    result = manager._discover_teams(report)

    assert len(result) == 1
    assert result[0].name == "Real Team"


# ---------------------------------------------------------------------------
# _discover_roles
# ---------------------------------------------------------------------------


def test_discover_roles_empty():
    client = _make_client(get_roles=(200, {"total": 0, "list": []}))
    manager, _log = _make_manager(client)
    report = _empty_report()

    result = manager._discover_roles(report)

    assert result == []
    assert report.errors == []


def test_discover_roles_with_scope_access():
    role_record = {
        "name": "Mentor",
        "description": "Mentor role",
        "data": {
            "CEngagement": {
                "create": "yes",
                "read": "team",
                "edit": "own",
                "delete": "no",
                "stream": "team",
            },
            "Contact": {
                "create": "no",
                "read": "all",
                "edit": "team",
                "delete": "no",
                "stream": "all",
            },
        },
    }
    client = _make_client(
        get_roles=(200, {"total": 1, "list": [role_record]}),
    )
    manager, _log = _make_manager(client)
    report = _empty_report()

    result = manager._discover_roles(report)

    assert len(result) == 1
    role = result[0]
    assert role.name == "Mentor"
    assert role.description == "Mentor role"
    # Custom entity wire-name → natural name
    assert "Engagement" in role.scope_access
    assert "Contact" in role.scope_access
    assert "CEngagement" not in role.scope_access

    engagement_scope = role.scope_access["Engagement"]
    assert engagement_scope.create is True
    assert engagement_scope.read == "team"
    assert engagement_scope.edit == "own"
    assert engagement_scope.delete == "no"
    assert engagement_scope.stream == "team"


def test_discover_roles_with_system_permissions():
    role_record = {
        "name": "Admin",
        "data": {},
        "assignmentPermission": "all",
        "userPermission": "team",
        "exportPermission": "yes",
        "massUpdatePermission": "yes",
        "portalPermission": "no",
    }
    client = _make_client(
        get_roles=(200, {"total": 1, "list": [role_record]}),
    )
    manager, _log = _make_manager(client)
    report = _empty_report()

    result = manager._discover_roles(report)

    assert len(result) == 1
    perms = result[0].system_permissions
    assert perms is not None
    assert perms.assignment_permission == "all"
    assert perms.user_permission == "team"
    assert perms.export is True
    assert perms.mass_update is True
    assert perms.portal is False


def test_discover_roles_partial_system_permissions():
    role_record = {
        "name": "Sparse",
        "data": {},
        "assignmentPermission": "team",
    }
    client = _make_client(
        get_roles=(200, {"total": 1, "list": [role_record]}),
    )
    manager, _log = _make_manager(client)
    report = _empty_report()

    result = manager._discover_roles(report)

    perms = result[0].system_permissions
    assert perms is not None
    assert perms.assignment_permission == "team"
    # Missing columns default to most-restrictive
    assert perms.user_permission == "no"
    assert perms.export is False
    assert perms.mass_update is False
    assert perms.portal is False


def test_discover_roles_no_system_permissions():
    role_record = {"name": "NoPerms", "data": {}}
    client = _make_client(
        get_roles=(200, {"total": 1, "list": [role_record]}),
    )
    manager, _log = _make_manager(client)
    report = _empty_report()

    result = manager._discover_roles(report)

    assert result[0].system_permissions is None


def test_discover_roles_empty_scope_access_warning():
    role_record = {"name": "Toothless", "data": {}}
    client = _make_client(
        get_roles=(200, {"total": 1, "list": [role_record]}),
    )
    manager, _log = _make_manager(client)
    report = _empty_report()

    result = manager._discover_roles(report)

    assert len(result) == 1
    assert result[0].name == "Toothless"
    assert any(
        "empty scope_access" in w and "Toothless" in w
        for w in report.warnings
    )


def test_discover_roles_boolean_scope_skipped():
    role_record = {
        "name": "Mixed",
        "data": {
            "CEngagement": {
                "create": "yes",
                "read": "team",
                "edit": "own",
                "delete": "no",
                "stream": "team",
            },
            "MyScope1": True,
        },
    }
    client = _make_client(
        get_roles=(200, {"total": 1, "list": [role_record]}),
    )
    manager, _log = _make_manager(client)
    report = _empty_report()

    result = manager._discover_roles(report)

    role = result[0]
    assert "Engagement" in role.scope_access
    assert "MyScope1" not in role.scope_access
    assert any(
        "MyScope1" in w and "non-mapping" in w
        for w in report.warnings
    )


def test_discover_roles_create_yes_translation():
    role_record = {
        "name": "Toggle",
        "data": {
            "Contact": {
                "create": "yes",
                "read": "all",
                "edit": "all",
                "delete": "all",
                "stream": "all",
            },
            "Account": {
                "create": "no",
                "read": "all",
                "edit": "no",
                "delete": "no",
                "stream": "all",
            },
        },
    }
    client = _make_client(
        get_roles=(200, {"total": 1, "list": [role_record]}),
    )
    manager, _log = _make_manager(client)
    report = _empty_report()

    result = manager._discover_roles(report)

    role = result[0]
    assert role.scope_access["Contact"].create is True
    assert role.scope_access["Account"].create is False


def test_discover_roles_persona_always_none():
    role_record = {
        "name": "Whatever",
        "description": "test",
        "data": {},
        # If the source somehow carried persona it would still be
        # ignored per DEC-178.
        "persona": "MST-PER-005",
    }
    client = _make_client(
        get_roles=(200, {"total": 1, "list": [role_record]}),
    )
    manager, _log = _make_manager(client)
    report = _empty_report()

    result = manager._discover_roles(report)

    assert result[0].persona is None


def test_discover_roles_http_error():
    client = _make_client(get_roles=(500, None))
    manager, _log = _make_manager(client)
    report = _empty_report()

    result = manager._discover_roles(report)

    assert result == []
    assert any("Failed to fetch roles" in e for e in report.errors)


# ---------------------------------------------------------------------------
# YAML emission
# ---------------------------------------------------------------------------


def test_build_security_yaml_includes_both_blocks():
    manager, _log = _make_manager()
    teams = [TeamAuditResult(name="Admins", description="Site administrators")]
    roles = [
        RoleAuditResult(
            name="Mentor",
            description="Mentor role",
            scope_access={
                "Engagement": ScopeAccess(
                    create=True, read="team", edit="own",
                    delete="no", stream="team",
                ),
            },
            system_permissions=SystemPermissions(
                assignment_permission="team",
                user_permission="team",
                export=True,
                mass_update=False,
                portal=False,
            ),
        ),
    ]

    result = manager._build_security_yaml(roles, teams)

    assert "teams" in result
    assert "roles" in result
    assert result["teams"][0]["name"] == "Admins"
    assert result["roles"][0]["name"] == "Mentor"
    scope = result["roles"][0]["scope_access"]["Engagement"]
    assert scope == {
        "create": True, "read": "team", "edit": "own",
        "delete": "no", "stream": "team",
    }
    perms = result["roles"][0]["system_permissions"]
    assert perms["assignment_permission"] == "team"
    assert perms["export"] is True


def test_build_security_yaml_omits_system_permissions_when_none():
    manager, _log = _make_manager()
    roles = [RoleAuditResult(name="Bare", scope_access={})]

    result = manager._build_security_yaml(roles, [])

    assert "system_permissions" not in result["roles"][0]
    assert "scope_access" not in result["roles"][0]


def test_run_audit_emits_security_yaml(tmp_path: Path):
    client = _make_client(
        get_all_scopes=(200, {}),
        get_i18n=(200, {}),
        get_teams=(200, {"total": 1, "list": [
            {"name": "Admins", "description": "Site administrators"},
        ]}),
        get_roles=(200, {"total": 1, "list": [
            {
                "name": "Admin",
                "data": {
                    "Contact": {
                        "create": "yes", "read": "all",
                        "edit": "all", "delete": "all", "stream": "all",
                    },
                },
                "assignmentPermission": "all",
                "userPermission": "all",
                "exportPermission": "yes",
                "massUpdatePermission": "yes",
                "portalPermission": "no",
            },
        ]}),
    )
    manager, log = _make_manager(client)

    report = manager.run_audit(tmp_path)

    security_yaml = tmp_path / "security" / "security.yaml"
    assert security_yaml.exists()
    data = yaml.safe_load(security_yaml.read_text())
    assert data["teams"][0]["name"] == "Admins"
    assert data["roles"][0]["name"] == "Admin"
    assert data["roles"][0]["scope_access"]["Contact"]["create"] is True
    assert data["roles"][0]["system_permissions"]["export"] is True
    # And the NOT_AUDITABLE advisory should have surfaced in the log.
    assert any(
        "NOT_AUDITABLE" in msg and "DEC-6" in msg
        for msg, _ in log
    )
    assert report.files_written >= 1


def test_run_audit_no_security_yaml_when_disabled(tmp_path: Path):
    options = AuditOptions(include_security=False)
    client = _make_client(
        get_all_scopes=(200, {}),
        get_i18n=(200, {}),
    )
    manager, _log = _make_manager(client, options)

    manager.run_audit(tmp_path)

    assert not (tmp_path / "security" / "security.yaml").exists()
    # No role/team discovery API calls should have been made
    client.get_teams.assert_not_called()
    client.get_roles.assert_not_called()


def test_run_audit_no_security_yaml_when_empty(tmp_path: Path):
    """``include_security=True`` but server returns no teams or roles —
    no placeholder file should be written."""
    client = _make_client(
        get_all_scopes=(200, {}),
        get_i18n=(200, {}),
        get_teams=(200, {"total": 0, "list": []}),
        get_roles=(200, {"total": 0, "list": []}),
    )
    manager, _log = _make_manager(client)

    manager.run_audit(tmp_path)

    assert not (tmp_path / "security" / "security.yaml").exists()


def test_run_audit_emits_not_auditable_advisory(tmp_path: Path):
    client = _make_client(
        get_all_scopes=(200, {}),
        get_i18n=(200, {}),
        get_teams=(200, {"total": 0, "list": []}),
        get_roles=(200, {"total": 0, "list": []}),
    )
    manager, log = _make_manager(client)

    manager.run_audit(tmp_path)

    advisory_lines = [
        msg for msg, color in log
        if "NOT_AUDITABLE" in msg and "DEC-6" in msg
    ]
    assert advisory_lines, "expected the §12.5 NOT_AUDITABLE advisory"


# ---------------------------------------------------------------------------
# AuditOptions default
# ---------------------------------------------------------------------------


def test_audit_options_include_security_defaults_true():
    assert AuditOptions().include_security is True


# ---------------------------------------------------------------------------
# Filtered-tab discovery (audit-v1.2 Prompt I)
# ---------------------------------------------------------------------------


def _engagement_entity() -> EntityAuditResult:
    """A canonical custom entity used by the filtered-tab tests."""
    return EntityAuditResult(
        yaml_name="Engagement",
        espo_name="CEngagement",
        entity_class=EntityClass.CUSTOM,
        entity_type="Base",
        label_singular="Engagement",
        label_plural="Engagements",
    )


def test_audit_options_include_filtered_tabs_defaults_true():
    assert AuditOptions().include_filtered_tabs is True


def test_discover_filtered_tabs_no_tab_scopes():
    """When no custom tab scopes exist, no clientDefs / ReportFilter
    calls are made and no tabs are attached to any entity."""
    client = _make_client(get_all_scopes=(200, {}))
    manager, _log = _make_manager(client)
    report = _empty_report()
    entity = _engagement_entity()

    manager._discover_filtered_tabs([entity], report)

    assert entity.filtered_tabs == []
    client.get_client_defs.assert_not_called()
    client.list_report_filters.assert_not_called()


def test_discover_filtered_tabs_one_tab_one_entity():
    """A single tab scope binding to Engagement reverses into a
    FilteredTabAuditResult with id, scope, label, and a filter AST."""
    client = _make_client(
        get_all_scopes=(200, {
            "MyEngagements": {
                "entity": False, "tab": True, "isCustom": True,
                "acl": "boolean",
            },
        }),
        get_client_defs=(200, {
            "controller": "record",
            "entity": "CEngagement",
            "defaultFilter": "reportFilterABC123",
        }),
        list_report_filters=(200, {"total": 1, "list": [
            {
                "id": "ABC123",
                "name": "My Engagements",
                "entityType": "CEngagement",
                "data": {
                    "where": [
                        {
                            "type": "currentUser",
                            "attribute": "assignedUser",
                        },
                    ],
                },
            },
        ]}),
    )
    manager, _log = _make_manager(client)
    report = _empty_report()
    entity = _engagement_entity()

    manager._discover_filtered_tabs([entity], report)

    assert len(entity.filtered_tabs) == 1
    tab = entity.filtered_tabs[0]
    assert tab.id == "myEngagements"
    assert tab.scope == "MyEngagements"
    assert tab.label == "My Engagements"
    assert tab.acl == "boolean"
    # currentUser → LeafClause(field=assignedUser, op=equals, value=$user)
    assert isinstance(tab.filter, LeafClause)
    assert tab.filter.field == "assignedUser"
    assert tab.filter.op == "equals"
    assert tab.filter.value == "$user"


def test_discover_filtered_tabs_advanced_pack_absent():
    """list_report_filters returns 404 → informational log line, no
    error recorded, no tabs attached."""
    client = _make_client(
        get_all_scopes=(200, {
            "MyEngagements": {
                "entity": False, "tab": True, "isCustom": True,
            },
        }),
        get_client_defs=(200, {
            "entity": "CEngagement",
            "defaultFilter": "reportFilterABC123",
        }),
        list_report_filters=(404, None),
    )
    manager, log = _make_manager(client)
    report = _empty_report()
    entity = _engagement_entity()

    manager._discover_filtered_tabs([entity], report)

    assert entity.filtered_tabs == []
    assert report.errors == []
    assert any(
        "Advanced Pack not installed" in msg
        for msg, _color in log
    )


def test_discover_filtered_tabs_report_filter_missing():
    """Binding exists in clientDefs but the Report Filter ID isn't
    in the list response — warning recorded, tab not captured."""
    client = _make_client(
        get_all_scopes=(200, {
            "MyEngagements": {
                "entity": False, "tab": True, "isCustom": True,
            },
        }),
        get_client_defs=(200, {
            "entity": "CEngagement",
            "defaultFilter": "reportFilterDOES_NOT_EXIST",
        }),
        list_report_filters=(200, {"total": 1, "list": [
            {"id": "SOMETHING_ELSE", "name": "Other"},
        ]}),
    )
    manager, _log = _make_manager(client)
    report = _empty_report()
    entity = _engagement_entity()

    manager._discover_filtered_tabs([entity], report)

    assert entity.filtered_tabs == []
    assert any(
        "MyEngagements" in w and "not found" in w
        for w in report.warnings
    )


def test_discover_filtered_tabs_unknown_where_type():
    """A where-item with an unknown type (e.g. ``currentQuarter``)
    poisons the whole filter — the tab IS captured (label + scope)
    but the filter is None, and a warning is recorded."""
    client = _make_client(
        get_all_scopes=(200, {
            "QuarterlyOpen": {
                "entity": False, "tab": True, "isCustom": True,
                "acl": "boolean",
            },
        }),
        get_client_defs=(200, {
            "entity": "CEngagement",
            "defaultFilter": "reportFilterXYZ",
        }),
        list_report_filters=(200, {"total": 1, "list": [
            {
                "id": "XYZ",
                "name": "Quarterly Open",
                "data": {
                    "where": [
                        {"type": "currentQuarter", "attribute": "createdAt"},
                    ],
                },
            },
        ]}),
    )
    manager, _log = _make_manager(client)
    report = _empty_report()
    entity = _engagement_entity()

    manager._discover_filtered_tabs([entity], report)

    assert len(entity.filtered_tabs) == 1
    tab = entity.filtered_tabs[0]
    assert tab.scope == "QuarterlyOpen"
    assert tab.label == "Quarterly Open"
    assert tab.filter is None
    assert any(
        "QuarterlyOpen" in w and "currentQuarter" in w
        for w in report.warnings
    )
    assert any(
        "QuarterlyOpen" in w and "unknown where-item types" in w
        for w in report.warnings
    )


def test_reverse_where_item_current_user():
    manager, _log = _make_manager()
    report = _empty_report()

    node = manager._reverse_where_item(
        {"type": "currentUser", "attribute": "assignedUser"},
        report, "Test",
    )

    assert isinstance(node, LeafClause)
    assert node.field == "assignedUser"
    assert node.op == "equals"
    assert node.value == "$user"


def test_reverse_where_item_not_current_user():
    manager, _log = _make_manager()
    report = _empty_report()

    node = manager._reverse_where_item(
        {"type": "notCurrentUser", "attribute": "createdBy"},
        report, "Test",
    )

    assert isinstance(node, LeafClause)
    assert node.field == "createdBy"
    assert node.op == "notEquals"
    assert node.value == "$user"


def test_reverse_where_item_is_null():
    manager, _log = _make_manager()
    report = _empty_report()

    node = manager._reverse_where_item(
        {"type": "isNull", "attribute": "closedAt"},
        report, "Test",
    )

    assert isinstance(node, LeafClause)
    assert node.field == "closedAt"
    assert node.op == "isNull"
    # isNull leaves the LeafClause value as the sentinel MISSING; no
    # 'value' should round-trip through render_condition.
    from espo_impl.core.condition_expression import render_condition
    assert "value" not in render_condition(node)


def test_reverse_where_item_and_compound():
    manager, _log = _make_manager()
    report = _empty_report()

    node = manager._reverse_where_item(
        {
            "type": "and",
            "value": [
                {"type": "equals", "attribute": "status", "value": "Open"},
                {"type": "currentUser", "attribute": "assignedUser"},
            ],
        },
        report, "Test",
    )

    assert isinstance(node, AllNode)
    assert len(node.children) == 2
    assert isinstance(node.children[0], LeafClause)
    assert node.children[0].op == "equals"
    assert isinstance(node.children[1], LeafClause)
    assert node.children[1].value == "$user"


def test_reverse_where_item_or_compound():
    manager, _log = _make_manager()
    report = _empty_report()

    node = manager._reverse_where_item(
        {
            "type": "or",
            "value": [
                {"type": "equals", "attribute": "status", "value": "Open"},
                {"type": "equals", "attribute": "status", "value": "Pending"},
            ],
        },
        report, "Test",
    )

    assert isinstance(node, AnyNode)
    assert len(node.children) == 2


def test_reverse_where_item_nested_compound():
    manager, _log = _make_manager()
    report = _empty_report()

    node = manager._reverse_where_item(
        {
            "type": "and",
            "value": [
                {"type": "currentUser", "attribute": "assignedUser"},
                {
                    "type": "or",
                    "value": [
                        {"type": "equals", "attribute": "status",
                         "value": "Open"},
                        {"type": "equals", "attribute": "status",
                         "value": "Pending"},
                    ],
                },
            ],
        },
        report, "Test",
    )

    assert isinstance(node, AllNode)
    assert isinstance(node.children[1], AnyNode)
    assert len(node.children[1].children) == 2


def test_reverse_where_items_single_leaf_top_level():
    """A single-item list unwraps to the bare LeafClause (matches the
    deploy half's single-leaf wrap behavior in reverse)."""
    manager, _log = _make_manager()
    report = _empty_report()

    node = manager._reverse_where_items(
        [{"type": "equals", "attribute": "status", "value": "Open"}],
        report, "Test",
    )

    assert isinstance(node, LeafClause)
    assert node.field == "status"
    assert node.value == "Open"


def test_reverse_where_items_multi_leaf_top_level():
    """A multi-item top-level list wraps in an implicit AllNode
    (the schema's shorthand-list form)."""
    manager, _log = _make_manager()
    report = _empty_report()

    node = manager._reverse_where_items(
        [
            {"type": "equals", "attribute": "status", "value": "Open"},
            {"type": "currentUser", "attribute": "assignedUser"},
        ],
        report, "Test",
    )

    assert isinstance(node, AllNode)
    assert len(node.children) == 2


def test_reverse_where_items_empty_returns_none():
    manager, _log = _make_manager()
    report = _empty_report()

    assert manager._reverse_where_items(None, report, "T") is None
    assert manager._reverse_where_items([], report, "T") is None


def test_run_audit_writes_filteredTabs_block_in_entity_yaml(tmp_path: Path):
    """Full run with a filtered tab — per-entity YAML output contains
    a ``filteredTabs:`` block with the captured tab."""
    client = _make_client(
        get_all_scopes=(200, {
            "CEngagement": {
                "entity": True, "isCustom": True, "customizable": True,
                "type": "Base", "stream": False,
            },
            "MyEngagements": {
                "entity": False, "tab": True, "isCustom": True,
                "acl": "boolean",
            },
        }),
        get_i18n=(200, {
            "Global": {
                "scopeNames": {
                    "CEngagement": "Engagement",
                    "MyEngagements": "My Engagements",
                },
                "scopeNamesPlural": {"CEngagement": "Engagements"},
            },
        }),
        get_entity_field_list=(200, {
            "name": {"type": "varchar"},
        }),
        get_layout=(200, []),
        get_all_links=(200, {}),
        get_client_defs=(200, {
            "entity": "CEngagement",
            "defaultFilter": "reportFilterABC123",
        }),
        list_report_filters=(200, {"total": 1, "list": [
            {
                "id": "ABC123",
                "name": "My Engagements",
                "entityType": "CEngagement",
                "data": {
                    "where": [
                        {"type": "currentUser", "attribute": "assignedUser"},
                    ],
                },
            },
        ]}),
        get_teams=(200, {"total": 0, "list": []}),
        get_roles=(200, {"total": 0, "list": []}),
    )
    manager, _log = _make_manager(client)

    manager.run_audit(tmp_path)

    yaml_path = tmp_path / "Engagement.yaml"
    assert yaml_path.exists()
    data = yaml.safe_load(yaml_path.read_text())
    entity_block = data["entities"]["Engagement"]
    assert "filteredTabs" in entity_block
    assert len(entity_block["filteredTabs"]) == 1
    tab_dict = entity_block["filteredTabs"][0]
    assert tab_dict["id"] == "myEngagements"
    assert tab_dict["scope"] == "MyEngagements"
    assert tab_dict["label"] == "My Engagements"
    assert tab_dict["acl"] == "boolean"
    # render_condition emits a leaf as {"field": ..., "op": ..., "value": ...}
    assert tab_dict["filter"] == {
        "field": "assignedUser",
        "op": "equals",
        "value": "$user",
    }


def test_run_audit_no_filtered_tab_discovery_when_disabled(tmp_path: Path):
    """include_filtered_tabs=False — no clientDefs / ReportFilter
    API calls and no filteredTabs block in any YAML."""
    options = AuditOptions(include_filtered_tabs=False)
    client = _make_client(
        get_all_scopes=(200, {
            "CEngagement": {
                "entity": True, "isCustom": True, "customizable": True,
                "type": "Base", "stream": False,
            },
        }),
        get_i18n=(200, {}),
        get_entity_field_list=(200, {"name": {"type": "varchar"}}),
        get_layout=(200, []),
        get_all_links=(200, {}),
        get_teams=(200, {"total": 0, "list": []}),
        get_roles=(200, {"total": 0, "list": []}),
    )
    manager, _log = _make_manager(client, options)

    manager.run_audit(tmp_path)

    client.get_client_defs.assert_not_called()
    client.list_report_filters.assert_not_called()
    yaml_path = tmp_path / "Engagement.yaml"
    if yaml_path.exists():
        data = yaml.safe_load(yaml_path.read_text())
        assert "filteredTabs" not in data["entities"]["Engagement"]


def test_filtered_tab_to_yaml_dict_omits_filter_when_none():
    """When the filter couldn't be recovered, the YAML block has no
    ``filter:`` key (operator hand-writes it post-import)."""
    manager, _log = _make_manager()
    tab = FilteredTabAuditResult(
        id="quarterlyOpen",
        scope="QuarterlyOpen",
        label="Quarterly Open",
        filter=None,
        acl="boolean",
    )

    result = manager._filtered_tab_to_yaml_dict(tab)

    assert result == {
        "id": "quarterlyOpen",
        "scope": "QuarterlyOpen",
        "label": "Quarterly Open",
        "acl": "boolean",
    }


def test_filtered_tab_to_yaml_dict_includes_nav_order_when_set():
    manager, _log = _make_manager()
    tab = FilteredTabAuditResult(
        id="myEngagements",
        scope="MyEngagements",
        label="My Engagements",
        nav_order=3,
        filter=LeafClause(
            field="assignedUser", op="equals", value="$user",
        ),
    )

    result = manager._filtered_tab_to_yaml_dict(tab)

    assert result["navOrder"] == 3
    assert result["filter"] == {
        "field": "assignedUser", "op": "equals", "value": "$user",
    }


# ---------------------------------------------------------------------------
# selected_entities filtering (audit-v1.2 Prompt J — DEC-181)
# ---------------------------------------------------------------------------


def _three_entity_scopes() -> dict[str, dict[str, Any]]:
    """Fixture returning the all-scopes dict used by the selected-
    entities filter tests: one native (Contact), one native (Account),
    and one custom (CEngagement)."""
    return {
        "Contact": {
            "entity": True, "isCustom": False, "customizable": True,
            "type": "Person", "stream": False,
        },
        "Account": {
            "entity": True, "isCustom": False, "customizable": True,
            "type": "Company", "stream": False,
        },
        "CEngagement": {
            "entity": True, "isCustom": True, "customizable": True,
            "type": "Base", "stream": False,
        },
    }


def test_audit_options_selected_entities_defaults_none():
    """The new field default preserves the existing audit-everything
    behavior for any code path that doesn't opt in to picker filtering."""
    assert AuditOptions().selected_entities is None


def test_discover_entities_with_selected_entities_filters():
    """A non-None selected_entities set restricts the discovery output
    to the named subset; other classification rules still apply."""
    options = AuditOptions(selected_entities={"Contact"})
    client = _make_client(
        get_all_scopes=(200, _three_entity_scopes()),
        get_i18n=(200, {}),
    )
    manager, _log = _make_manager(client, options)
    report = _empty_report()

    entities = manager._discover_entities(report)

    assert {e.espo_name for e in entities} == {"Contact"}


def test_discover_entities_with_none_selected_entities_audits_all():
    """selected_entities=None (default) preserves the legacy behavior:
    every classified entity is included."""
    client = _make_client(
        get_all_scopes=(200, _three_entity_scopes()),
        get_i18n=(200, {}),
    )
    manager, _log = _make_manager(client)
    report = _empty_report()

    entities = manager._discover_entities(report)

    assert {e.espo_name for e in entities} == {
        "Contact", "Account", "CEngagement",
    }


def test_discover_entities_with_empty_set_audits_nothing():
    """selected_entities=set() (a deliberately empty selection)
    excludes every entity. The picker UI prevents an operator from
    starting an audit in this state, but the audit_manager itself
    honors the empty-set semantic — it is NOT the same as None."""
    options = AuditOptions(selected_entities=set())
    client = _make_client(
        get_all_scopes=(200, _three_entity_scopes()),
        get_i18n=(200, {}),
    )
    manager, _log = _make_manager(client, options)
    report = _empty_report()

    entities = manager._discover_entities(report)

    assert entities == []


# ---------------------------------------------------------------------------
# run_audit — pass-2 data-profiling hook (WTK-096 §2.2)
# ---------------------------------------------------------------------------


def _profiling_client() -> MagicMock:
    """Client mock satisfying a minimal layouts-off, security-off run."""
    return _make_client(
        get_all_scopes=(200, {
            "CEngagement": {"entity": True, "customizable": True,
                            "isCustom": True, "type": "Base"},
        }),
        get_i18n=(200, {}),
        get_entity_field_list=(200, {
            "cStage": {"type": "enum", "isCustom": True,
                       "options": ["a", "b"]},
        }),
    )


def _profile_off_options(**overrides) -> AuditOptions:
    kwargs = {
        "include_detail_layouts": False, "include_list_layouts": False,
        "include_edit_layout": False, "include_small_layouts": False,
        "include_detail_convert": False, "include_kanban": False,
        "include_search_massupdate": False, "include_relationships_layout": False,
        "include_side_bottom_panels": False, "include_relationships": False,
        "include_security": False, "include_filtered_tabs": False,
    }
    kwargs.update(overrides)
    return AuditOptions(**kwargs)


def test_run_audit_invokes_profiler_and_writes_profile(tmp_path, monkeypatch):
    import espo_impl.core.data_profiler as dp

    invoked = {}

    class FakeProfiler:
        def __init__(self, client, report, options=None, callback=None):
            invoked["report"] = report

        def run(self):
            return dp.UtilizationProfile(data={
                "manifest_version": 1, "anomalies": [], "entities": {"CEngagement": {}},
            })

    monkeypatch.setattr(dp, "DataProfiler", FakeProfiler)
    manager, log = _make_manager(_profiling_client(), _profile_off_options())

    report = manager.run_audit(tmp_path)

    assert invoked["report"] is report
    assert (tmp_path / "utilization-profile.json").exists()
    assert any("pass 2" in msg for msg, _ in log)


def test_run_audit_profiler_failure_is_non_fatal(tmp_path, monkeypatch):
    import espo_impl.core.data_profiler as dp

    class ExplodingProfiler:
        def __init__(self, *args, **kwargs):
            pass

        def run(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(dp, "DataProfiler", ExplodingProfiler)
    manager, _log = _make_manager(_profiling_client(), _profile_off_options())

    report = manager.run_audit(tmp_path)

    # Pass 1's output stands; the failure lands in warnings only.
    assert report.files_written >= 1
    assert any("Data profiling failed: boom" in w for w in report.warnings)
    assert not (tmp_path / "utilization-profile.json").exists()


def test_run_audit_profiler_sequences_after_assembly_and_merges_warnings(
    tmp_path, monkeypatch
):
    """WTK-100 — pass 2 runs strictly after pass-1 assembly (WTK-096
    §2.1): the profiler is constructed with the populated work-list and
    the YAML already written; its anomalies surface in the audit's
    warnings stream (§7.3)."""
    import espo_impl.core.data_profiler as dp

    observed = {}

    class FakeProfiler:
        def __init__(self, client, report, options=None, callback=None):
            observed["entities_at_init"] = len(report.entities)
            observed["files_written_at_init"] = report.files_written

        def run(self):
            return dp.UtilizationProfile(data={
                "manifest_version": 1,
                "anomalies": [{"scope": "entity", "entity": "CEngagement",
                               "status": 403,
                               "note": "HTTP 403 on record count"}],
                "entities": {},
            })

    monkeypatch.setattr(dp, "DataProfiler", FakeProfiler)
    manager, _log = _make_manager(_profiling_client(), _profile_off_options())

    report = manager.run_audit(tmp_path)

    assert observed["entities_at_init"] == 1
    assert observed["files_written_at_init"] >= 1
    assert any(
        "profiler [entity] CEngagement" in w for w in report.warnings
    )


def test_run_audit_profile_opt_out(tmp_path, monkeypatch):
    import espo_impl.core.data_profiler as dp

    def _fail(*args, **kwargs):
        raise AssertionError("profiler must not be constructed when opted out")

    monkeypatch.setattr(dp, "DataProfiler", _fail)
    manager, _log = _make_manager(
        _profiling_client(), _profile_off_options(include_data_profile=False),
    )

    report = manager.run_audit(tmp_path)
    assert report.errors == []
    assert not (tmp_path / "utilization-profile.json").exists()

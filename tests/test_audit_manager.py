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
    RoleAuditResult,
    TeamAuditResult,
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

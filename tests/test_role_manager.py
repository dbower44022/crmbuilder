"""Tests for the role manager orchestration logic + translation layer."""

from unittest.mock import MagicMock

import pytest

from espo_impl.core.models import (
    RoleDefinition,
    RoleStatus,
    ScopeAccess,
    SystemPermissions,
)
from espo_impl.core.role_manager import RoleManager, RoleManagerError


def server_response(roles: list[dict]) -> tuple[int, dict]:
    return (200, {"total": len(roles), "list": roles})


def scope_response(*entity_names: str) -> tuple[int, dict[str, dict]]:
    """Build a (status, body) response for ``client.get_all_scopes``.

    Returns the server-shape ``{scopeName: {entity, isCustom, ...}}``
    dict — the manager only inspects the keys, so the values can be
    minimal stubs.
    """
    return (
        200,
        {name: {"entity": True, "isCustom": False} for name in entity_names},
    )


def install_default_scopes(client: MagicMock) -> None:
    """Default the client's ``get_all_scopes`` to a permissive set.

    Includes every entity name that any pre-existing test in this
    module references on the YAML side. Keeps the existing
    CHECK→ACT tests passing once pre-flight is wired in.
    """
    client.get_all_scopes.return_value = scope_response(
        "Contact",
        "Account",
        "CEngagement",
    )


def make_manager(client=None) -> tuple[RoleManager, list]:
    if client is None:
        client = MagicMock()
    # Default get_all_scopes to a permissive set so existing tests
    # don't have to set it explicitly. Tests exercising the pre-flight
    # path itself override this with a more restrictive scope set.
    if not isinstance(client.get_all_scopes.return_value, tuple):
        install_default_scopes(client)
    output_log: list[tuple[str, str]] = []
    manager = RoleManager(
        client, lambda msg, color: output_log.append((msg, color)),
    )
    return manager, output_log


# =================================================================
# Translation-layer tests (pure logic; no manager involvement)
# =================================================================


# --- _translate_data_block ---


def test_translate_data_block_empty_returns_empty_dict():
    manager, _ = make_manager()
    assert manager._translate_data_block({}) == {}


def test_translate_data_block_custom_entity_gets_c_prefix():
    manager, _ = make_manager()
    scope_access = {
        "Engagement": ScopeAccess(
            create=True, read="own", edit="own", delete="no", stream="own",
        ),
    }
    result = manager._translate_data_block(scope_access)
    assert "CEngagement" in result
    assert "Engagement" not in result


def test_translate_data_block_native_entity_unchanged():
    manager, _ = make_manager()
    scope_access = {
        "Contact": ScopeAccess(
            create=False, read="team", edit="no", delete="no", stream="team",
        ),
    }
    result = manager._translate_data_block(scope_access)
    assert "Contact" in result
    assert "CContact" not in result


def test_translate_data_block_create_bool_to_yes_no_string():
    manager, _ = make_manager()
    scope_access = {
        "Contact": ScopeAccess(
            create=True, read="all", edit="all", delete="all", stream="all",
        ),
        "Account": ScopeAccess(
            create=False, read="all", edit="all", delete="all", stream="all",
        ),
    }
    result = manager._translate_data_block(scope_access)
    assert result["Contact"]["create"] == "yes"
    assert result["Account"]["create"] == "no"


def test_translate_data_block_scope_strings_passthrough():
    manager, _ = make_manager()
    scope_access = {
        "Contact": ScopeAccess(
            create=True, read="all", edit="team", delete="own", stream="no",
        ),
    }
    result = manager._translate_data_block(scope_access)
    assert result["Contact"] == {
        "create": "yes",
        "read": "all",
        "edit": "team",
        "delete": "own",
        "stream": "no",
    }


def test_translate_data_block_multiple_entities_mixed():
    manager, _ = make_manager()
    scope_access = {
        "Contact": ScopeAccess(
            create=False, read="team", edit="no", delete="no", stream="team",
        ),
        "Engagement": ScopeAccess(
            create=True, read="own", edit="own", delete="no", stream="own",
        ),
    }
    result = manager._translate_data_block(scope_access)
    assert set(result.keys()) == {"Contact", "CEngagement"}
    assert result["Contact"]["create"] == "no"
    assert result["CEngagement"]["create"] == "yes"


# --- _translate_system_permissions ---


def test_translate_system_permissions_none_all_denied():
    manager, _ = make_manager()
    result = manager._translate_system_permissions(None)
    assert set(result.keys()) == {
        "assignmentPermission",
        "userPermission",
        "exportPermission",
        "massUpdatePermission",
        "portalPermission",
    }
    assert result["assignmentPermission"] == "no"
    assert result["userPermission"] == "no"
    assert result["exportPermission"] == "no"
    assert result["massUpdatePermission"] == "no"
    assert result["portalPermission"] == "no"


def test_translate_system_permissions_partial_one_key_set():
    manager, _ = make_manager()
    perms = SystemPermissions(export=True)
    result = manager._translate_system_permissions(perms)
    assert result["exportPermission"] == "yes"
    assert result["assignmentPermission"] == "no"
    assert result["userPermission"] == "no"
    assert result["massUpdatePermission"] == "no"
    assert result["portalPermission"] == "no"


def test_translate_system_permissions_scope_keys_preserved():
    manager, _ = make_manager()
    perms = SystemPermissions(
        assignment_permission="own",
        user_permission="team",
    )
    result = manager._translate_system_permissions(perms)
    assert result["assignmentPermission"] == "own"
    assert result["userPermission"] == "team"


def test_translate_system_permissions_all_set():
    manager, _ = make_manager()
    perms = SystemPermissions(
        assignment_permission="all",
        user_permission="all",
        export=True,
        mass_update=True,
        portal=True,
    )
    result = manager._translate_system_permissions(perms)
    assert result == {
        "assignmentPermission": "all",
        "userPermission": "all",
        "exportPermission": "yes",
        "massUpdatePermission": "yes",
        "portalPermission": "yes",
    }


# --- _translate_to_payload ---


def test_translate_to_payload_include_name_true_has_name():
    manager, _ = make_manager()
    role_def = RoleDefinition(name="Mentor", description="The mentor role")
    payload = manager._translate_to_payload(role_def, include_name=True)
    assert payload["name"] == "Mentor"
    assert payload["description"] == "The mentor role"
    assert "data" in payload


def test_translate_to_payload_include_name_false_omits_name():
    manager, _ = make_manager()
    role_def = RoleDefinition(name="Mentor")
    payload = manager._translate_to_payload(role_def, include_name=False)
    assert "name" not in payload


def test_translate_to_payload_no_description_omitted():
    manager, _ = make_manager()
    role_def = RoleDefinition(name="Mentor")
    payload = manager._translate_to_payload(role_def, include_name=True)
    assert "description" not in payload


def test_translate_to_payload_full_payload_shape():
    manager, _ = make_manager()
    role_def = RoleDefinition(
        name="Mentor",
        description="x",
        scope_access={
            "Engagement": ScopeAccess(
                create=True, read="own", edit="own", delete="no", stream="own",
            ),
            "Contact": ScopeAccess(
                create=False, read="team", edit="no", delete="no",
                stream="team",
            ),
        },
        system_permissions=SystemPermissions(
            assignment_permission="own",
            user_permission="team",
            export=False,
            mass_update=False,
            portal=False,
        ),
    )
    payload = manager._translate_to_payload(role_def, include_name=True)
    assert payload["name"] == "Mentor"
    assert payload["description"] == "x"
    assert payload["data"] == {
        "CEngagement": {
            "create": "yes",
            "read": "own",
            "edit": "own",
            "delete": "no",
            "stream": "own",
        },
        "Contact": {
            "create": "no",
            "read": "team",
            "edit": "no",
            "delete": "no",
            "stream": "team",
        },
    }
    assert payload["assignmentPermission"] == "own"
    assert payload["userPermission"] == "team"
    assert payload["exportPermission"] == "no"
    assert payload["massUpdatePermission"] == "no"
    assert payload["portalPermission"] == "no"


def test_translate_to_payload_excludes_unmanaged_permissions():
    """DEC-2: never include the three EspoCRM-only permissions."""
    manager, _ = make_manager()
    role_def = RoleDefinition(
        name="Mentor",
        description="x",
        system_permissions=SystemPermissions(
            assignment_permission="all", user_permission="all",
            export=True, mass_update=True, portal=True,
        ),
    )
    payload = manager._translate_to_payload(role_def, include_name=True)
    assert "followerManagementPermission" not in payload
    assert "groupEmailAccountPermission" not in payload
    assert "dataPrivacyPermission" not in payload


def test_translate_to_payload_none_system_permissions_all_denied():
    manager, _ = make_manager()
    role_def = RoleDefinition(name="Mentor", system_permissions=None)
    payload = manager._translate_to_payload(role_def, include_name=True)
    assert payload["assignmentPermission"] == "no"
    assert payload["userPermission"] == "no"
    assert payload["exportPermission"] == "no"
    assert payload["massUpdatePermission"] == "no"
    assert payload["portalPermission"] == "no"


# =================================================================
# CHECK→ACT manager tests
# =================================================================


def role_record(
    name: str,
    role_id: str = "role-1",
    description: str | None = None,
    data: dict | None = None,
    assignment: str = "no",
    user_perm: str = "no",
    export: str = "no",
    mass_update: str = "no",
    portal: str = "no",
) -> dict:
    """Build a minimal server-side Role record for tests."""
    return {
        "id": role_id,
        "name": name,
        "description": description,
        "data": data or {},
        "assignmentPermission": assignment,
        "userPermission": user_perm,
        "exportPermission": export,
        "massUpdatePermission": mass_update,
        "portalPermission": portal,
    }


# --- Empty input ---


def test_empty_roles_returns_empty_list_no_api_call():
    client = MagicMock()
    manager, _ = make_manager(client)
    results = manager.process_roles([], dry_run=False)
    assert results == []
    assert client.get_roles.call_count == 0
    assert client.create_role.call_count == 0
    assert client.update_role.call_count == 0


# --- Create path ---


def test_create_when_server_has_no_roles():
    client = MagicMock()
    client.get_roles.return_value = server_response([])
    client.create_role.return_value = (
        201, {"id": "role-new", "name": "Mentor"},
    )
    manager, _ = make_manager(client)
    roles = [RoleDefinition(name="Mentor", description="x")]
    results = manager.process_roles(roles)
    assert len(results) == 1
    assert results[0].status == RoleStatus.CREATED
    assert results[0].role_id == "role-new"
    assert results[0].error is None


def test_create_payload_shape():
    client = MagicMock()
    client.get_roles.return_value = server_response([])
    client.create_role.return_value = (201, {"id": "role-new"})
    manager, _ = make_manager(client)
    role_def = RoleDefinition(
        name="Mentor",
        description="x",
        scope_access={
            "Engagement": ScopeAccess(
                create=True, read="own", edit="own", delete="no", stream="own",
            ),
        },
        system_permissions=SystemPermissions(
            assignment_permission="own", user_permission="team",
        ),
    )
    manager.process_roles([role_def])
    args, _ = client.create_role.call_args
    payload = args[0]
    assert payload["name"] == "Mentor"
    assert payload["description"] == "x"
    assert "CEngagement" in payload["data"]
    assert payload["assignmentPermission"] == "own"
    assert payload["userPermission"] == "team"
    assert payload["exportPermission"] == "no"
    assert payload["massUpdatePermission"] == "no"
    assert payload["portalPermission"] == "no"


def test_create_status_200_also_accepted():
    client = MagicMock()
    client.get_roles.return_value = server_response([])
    client.create_role.return_value = (200, {"id": "role-200"})
    manager, _ = make_manager(client)
    roles = [RoleDefinition(name="Mentor")]
    results = manager.process_roles(roles)
    assert results[0].status == RoleStatus.CREATED
    assert results[0].role_id == "role-200"


def test_create_dry_run_does_not_call_api():
    client = MagicMock()
    client.get_roles.return_value = server_response([])
    manager, _ = make_manager(client)
    roles = [RoleDefinition(name="Mentor")]
    results = manager.process_roles(roles, dry_run=True)
    assert results[0].status == RoleStatus.CREATED
    assert results[0].role_id is None
    assert client.create_role.call_count == 0


# --- Skip path ---


def test_skip_when_data_and_permissions_match():
    client = MagicMock()
    client.get_roles.return_value = server_response([
        role_record(
            name="Mentor",
            data={
                "CEngagement": {
                    "create": "yes", "read": "own", "edit": "own",
                    "delete": "no", "stream": "own",
                },
            },
            assignment="own", user_perm="team",
        ),
    ])
    manager, _ = make_manager(client)
    role_def = RoleDefinition(
        name="Mentor",
        scope_access={
            "Engagement": ScopeAccess(
                create=True, read="own", edit="own", delete="no",
                stream="own",
            ),
        },
        system_permissions=SystemPermissions(
            assignment_permission="own", user_permission="team",
        ),
    )
    results = manager.process_roles([role_def])
    assert results[0].status == RoleStatus.SKIPPED
    assert results[0].role_id == "role-1"
    assert client.update_role.call_count == 0


def test_skip_server_none_permission_coerces_to_no():
    """Server stores None for a permission column; YAML default → SKIP."""
    client = MagicMock()
    existing = role_record(name="Mentor")
    existing["exportPermission"] = None
    existing["massUpdatePermission"] = None
    client.get_roles.return_value = server_response([existing])
    manager, _ = make_manager(client)
    role_def = RoleDefinition(
        name="Mentor",
        system_permissions=SystemPermissions(),
    )
    results = manager.process_roles([role_def])
    assert results[0].status == RoleStatus.SKIPPED
    assert client.update_role.call_count == 0


# --- Update path ---


def test_update_when_description_differs():
    client = MagicMock()
    client.get_roles.return_value = server_response([
        role_record(name="Mentor", description="old"),
    ])
    client.update_role.return_value = (200, {})
    manager, _ = make_manager(client)
    role_def = RoleDefinition(name="Mentor", description="new")
    results = manager.process_roles([role_def])
    assert results[0].status == RoleStatus.UPDATED
    args, _ = client.update_role.call_args
    role_id, payload = args
    assert role_id == "role-1"
    assert payload["description"] == "new"
    assert "name" not in payload


def test_update_when_scope_access_differs():
    client = MagicMock()
    client.get_roles.return_value = server_response([
        role_record(
            name="Mentor",
            data={
                "CEngagement": {
                    "create": "no", "read": "no", "edit": "no",
                    "delete": "no", "stream": "no",
                },
            },
        ),
    ])
    client.update_role.return_value = (200, {})
    manager, _ = make_manager(client)
    role_def = RoleDefinition(
        name="Mentor",
        scope_access={
            "Engagement": ScopeAccess(
                create=True, read="own", edit="own", delete="no",
                stream="own",
            ),
        },
    )
    results = manager.process_roles([role_def])
    assert results[0].status == RoleStatus.UPDATED
    args, _ = client.update_role.call_args
    role_id, payload = args
    assert role_id == "role-1"
    assert "data" in payload
    assert payload["data"]["CEngagement"]["create"] == "yes"
    assert "assignmentPermission" in payload
    assert "name" not in payload


def test_update_when_system_permission_differs():
    client = MagicMock()
    client.get_roles.return_value = server_response([
        role_record(name="Mentor", export="no"),
    ])
    client.update_role.return_value = (200, {})
    manager, _ = make_manager(client)
    role_def = RoleDefinition(
        name="Mentor",
        system_permissions=SystemPermissions(export=True),
    )
    results = manager.process_roles([role_def])
    assert results[0].status == RoleStatus.UPDATED
    args, _ = client.update_role.call_args
    _, payload = args
    assert payload["exportPermission"] == "yes"


def test_update_combines_multiple_changes_into_one_patch():
    client = MagicMock()
    client.get_roles.return_value = server_response([
        role_record(
            name="Mentor",
            description="old",
            data={
                "Contact": {
                    "create": "no", "read": "no", "edit": "no",
                    "delete": "no", "stream": "no",
                },
            },
            export="no",
        ),
    ])
    client.update_role.return_value = (200, {})
    manager, _ = make_manager(client)
    role_def = RoleDefinition(
        name="Mentor",
        description="new",
        scope_access={
            "Contact": ScopeAccess(
                create=True, read="team", edit="team", delete="no",
                stream="team",
            ),
        },
        system_permissions=SystemPermissions(export=True),
    )
    results = manager.process_roles([role_def])
    assert results[0].status == RoleStatus.UPDATED
    assert client.update_role.call_count == 1
    args, _ = client.update_role.call_args
    _, payload = args
    assert payload["description"] == "new"
    assert payload["data"]["Contact"]["create"] == "yes"
    assert payload["exportPermission"] == "yes"


def test_update_dry_run_does_not_call_api():
    client = MagicMock()
    client.get_roles.return_value = server_response([
        role_record(name="Mentor", description="old"),
    ])
    manager, _ = make_manager(client)
    role_def = RoleDefinition(name="Mentor", description="new")
    results = manager.process_roles([role_def], dry_run=True)
    assert results[0].status == RoleStatus.UPDATED
    assert results[0].role_id == "role-1"
    assert client.update_role.call_count == 0


def test_update_omits_unmanaged_permissions():
    """DEC-2: PATCH must NOT include the three EspoCRM-only permissions."""
    client = MagicMock()
    client.get_roles.return_value = server_response([
        role_record(name="Mentor", description="old"),
    ])
    client.update_role.return_value = (200, {})
    manager, _ = make_manager(client)
    role_def = RoleDefinition(name="Mentor", description="new")
    manager.process_roles([role_def])
    _, payload = client.update_role.call_args.args
    assert "followerManagementPermission" not in payload
    assert "groupEmailAccountPermission" not in payload
    assert "dataPrivacyPermission" not in payload


# --- Error paths ---


def test_get_roles_401_raises():
    client = MagicMock()
    client.get_roles.return_value = (401, None)
    manager, _ = make_manager(client)
    with pytest.raises(RoleManagerError):
        manager.process_roles([RoleDefinition(name="Mentor")])


def test_get_roles_500_raises():
    client = MagicMock()
    client.get_roles.return_value = (500, {"message": "boom"})
    manager, _ = make_manager(client)
    with pytest.raises(RoleManagerError):
        manager.process_roles([RoleDefinition(name="Mentor")])


def test_server_duplicate_names_produce_per_role_error():
    client = MagicMock()
    client.get_roles.return_value = server_response([
        role_record(name="Mentor", role_id="role-a"),
        role_record(name="Mentor", role_id="role-b"),
        role_record(name="Staff", role_id="role-c"),
    ])
    manager, _ = make_manager(client)
    roles = [
        RoleDefinition(name="Mentor"),
        RoleDefinition(name="Staff"),
    ]
    results = manager.process_roles(roles)
    assert results[0].status == RoleStatus.ERROR
    assert "multiple server roles" in results[0].error
    assert results[1].status == RoleStatus.SKIPPED


def test_create_401_raises_halts_batch():
    client = MagicMock()
    client.get_roles.return_value = server_response([])
    client.create_role.return_value = (401, None)
    manager, _ = make_manager(client)
    roles = [RoleDefinition(name="A"), RoleDefinition(name="B")]
    with pytest.raises(RoleManagerError):
        manager.process_roles(roles)


def test_update_401_raises_halts_batch():
    client = MagicMock()
    client.get_roles.return_value = server_response([
        role_record(name="A", description="old"),
    ])
    client.update_role.return_value = (401, None)
    manager, _ = make_manager(client)
    roles = [RoleDefinition(name="A", description="new")]
    with pytest.raises(RoleManagerError):
        manager.process_roles(roles)


def test_create_500_produces_per_role_error_batch_continues():
    client = MagicMock()
    client.get_roles.return_value = server_response([])
    client.create_role.side_effect = [
        (500, {"message": "boom"}),
        (201, {"id": "role-ok"}),
    ]
    manager, _ = make_manager(client)
    roles = [
        RoleDefinition(name="Fails"),
        RoleDefinition(name="Works"),
    ]
    results = manager.process_roles(roles)
    assert results[0].status == RoleStatus.ERROR
    assert "500" in results[0].error
    assert results[1].status == RoleStatus.CREATED
    assert results[1].role_id == "role-ok"


def test_update_500_produces_per_role_error_batch_continues():
    client = MagicMock()
    client.get_roles.return_value = server_response([
        role_record(name="Fails", role_id="role-f", description="old"),
        role_record(name="Works", role_id="role-w", description="old"),
    ])
    client.update_role.side_effect = [
        (500, {"message": "boom"}),
        (200, {}),
    ]
    manager, _ = make_manager(client)
    roles = [
        RoleDefinition(name="Fails", description="new"),
        RoleDefinition(name="Works", description="new"),
    ]
    results = manager.process_roles(roles)
    assert results[0].status == RoleStatus.ERROR
    assert "500" in results[0].error
    assert results[1].status == RoleStatus.UPDATED


# --- Mixed batch ---


def test_mixed_batch_create_skip_update():
    client = MagicMock()
    client.get_roles.return_value = server_response([
        role_record(
            name="Skipper",
            role_id="role-skip",
            description="same",
        ),
        role_record(
            name="Updater",
            role_id="role-upd",
            description="old",
        ),
    ])
    client.create_role.return_value = (201, {"id": "role-new"})
    client.update_role.return_value = (200, {})
    manager, _ = make_manager(client)
    roles = [
        RoleDefinition(name="Creator", description="fresh"),
        RoleDefinition(name="Skipper", description="same"),
        RoleDefinition(name="Updater", description="new"),
    ]
    results = manager.process_roles(roles)
    assert len(results) == 3
    assert results[0].status == RoleStatus.CREATED
    assert results[0].role_id == "role-new"
    assert results[1].status == RoleStatus.SKIPPED
    assert results[1].role_id == "role-skip"
    assert results[2].status == RoleStatus.UPDATED
    assert results[2].role_id == "role-upd"
    assert client.create_role.call_count == 1
    assert client.update_role.call_count == 1


# =================================================================
# Pre-flight server-state validation tests (Prompt E)
# =================================================================


def test_preflight_all_resolve():
    """Every YAML scope_access entity exists on the server — pre-flight
    is a no-op and every role proceeds to CHECK→ACT."""
    client = MagicMock()
    client.get_all_scopes.return_value = scope_response(
        "Contact", "CEngagement",
    )
    client.get_roles.return_value = server_response([])
    client.create_role.return_value = (201, {"id": "role-new"})
    manager, _ = make_manager(client)
    role_def = RoleDefinition(
        name="Mentor",
        scope_access={
            "Contact": ScopeAccess(
                create=True, read="all", edit="all", delete="all", stream="all",
            ),
            "Engagement": ScopeAccess(
                create=True, read="own", edit="own", delete="no", stream="own",
            ),
        },
    )
    results = manager.process_roles([role_def])
    assert len(results) == 1
    assert results[0].status == RoleStatus.CREATED
    assert client.get_all_scopes.call_count == 1
    assert client.get_roles.call_count == 1


def test_preflight_one_role_unresolvable():
    """Server lacks one entity referenced by one role; that role
    ERRORs; sibling role still proceeds to CHECK→ACT."""
    client = MagicMock()
    client.get_all_scopes.return_value = scope_response("Contact")  # no CEngagement
    client.get_roles.return_value = server_response([])
    client.create_role.return_value = (201, {"id": "role-new"})
    manager, _ = make_manager(client)
    bad_role = RoleDefinition(
        name="Mentor",
        scope_access={
            "Engagement": ScopeAccess(
                create=True, read="own", edit="own", delete="no", stream="own",
            ),
        },
    )
    good_role = RoleDefinition(
        name="Staff",
        scope_access={
            "Contact": ScopeAccess(
                create=False, read="team", edit="no", delete="no", stream="team",
            ),
        },
    )
    results = manager.process_roles([bad_role, good_role])
    assert len(results) == 2
    assert results[0].name == "Mentor"
    assert results[0].status == RoleStatus.ERROR
    assert "Engagement" in (results[0].error or "")
    assert "not on target" in (results[0].error or "")
    assert results[1].name == "Staff"
    assert results[1].status == RoleStatus.CREATED
    # The bad role's payload was never POSTed.
    assert client.create_role.call_count == 1


def test_preflight_role_with_no_scope_access():
    """A role with empty scope_access trivially passes pre-flight."""
    client = MagicMock()
    client.get_all_scopes.return_value = scope_response()  # empty server
    client.get_roles.return_value = server_response([])
    client.create_role.return_value = (201, {"id": "role-new"})
    manager, _ = make_manager(client)
    role_def = RoleDefinition(name="Admin")  # no scope_access
    results = manager.process_roles([role_def])
    assert results[0].status == RoleStatus.CREATED


def test_preflight_get_all_scopes_401_raises():
    """A 401 from get_all_scopes raises RoleManagerError."""
    client = MagicMock()
    client.get_all_scopes.return_value = (401, None)
    manager, _ = make_manager(client)
    with pytest.raises(RoleManagerError) as exc_info:
        manager.process_roles([RoleDefinition(name="Mentor")])
    assert "401" in str(exc_info.value)


def test_preflight_get_all_scopes_500_raises():
    """A 500 from get_all_scopes raises RoleManagerError; pre-flight
    cannot proceed without server-state context."""
    client = MagicMock()
    client.get_all_scopes.return_value = (500, {"message": "boom"})
    manager, _ = make_manager(client)
    with pytest.raises(RoleManagerError) as exc_info:
        manager.process_roles([RoleDefinition(name="Mentor")])
    assert "pre-flight" in str(exc_info.value)


def test_preflight_natural_to_wire_translation():
    """YAML uses 'Engagement' (natural); server has 'CEngagement'
    (wire) — pre-flight identifies the match via translation."""
    client = MagicMock()
    client.get_all_scopes.return_value = scope_response("CEngagement")
    client.get_roles.return_value = server_response([])
    client.create_role.return_value = (201, {"id": "role-new"})
    manager, _ = make_manager(client)
    role_def = RoleDefinition(
        name="Mentor",
        scope_access={
            "Engagement": ScopeAccess(
                create=True, read="own", edit="own", delete="no", stream="own",
            ),
        },
    )
    results = manager.process_roles([role_def])
    assert results[0].status == RoleStatus.CREATED


def test_preflight_native_entity_match():
    """YAML uses 'Contact' (native, unchanged) — pre-flight matches."""
    client = MagicMock()
    client.get_all_scopes.return_value = scope_response("Contact")
    client.get_roles.return_value = server_response([])
    client.create_role.return_value = (201, {"id": "role-new"})
    manager, _ = make_manager(client)
    role_def = RoleDefinition(
        name="Mentor",
        scope_access={
            "Contact": ScopeAccess(
                create=True, read="all", edit="all", delete="all", stream="all",
            ),
        },
    )
    results = manager.process_roles([role_def])
    assert results[0].status == RoleStatus.CREATED


def test_preflight_mixed_batch_partial_failure():
    """Three roles, one with unresolvable scope_access; result list
    preserves YAML declaration order."""
    client = MagicMock()
    client.get_all_scopes.return_value = scope_response("Contact")
    client.get_roles.return_value = server_response([])
    client.create_role.return_value = (201, {"id": "role-new"})
    manager, _ = make_manager(client)
    roles = [
        RoleDefinition(
            name="A",
            scope_access={
                "Contact": ScopeAccess(
                    create=True, read="all", edit="all", delete="all",
                    stream="all",
                ),
            },
        ),
        RoleDefinition(
            name="B",
            scope_access={
                "Engagement": ScopeAccess(
                    create=True, read="own", edit="own", delete="no",
                    stream="own",
                ),
            },
        ),
        RoleDefinition(
            name="C",
            scope_access={
                "Contact": ScopeAccess(
                    create=False, read="team", edit="no", delete="no",
                    stream="team",
                ),
            },
        ),
    ]
    results = manager.process_roles(roles)
    assert [r.name for r in results] == ["A", "B", "C"]
    assert results[0].status == RoleStatus.CREATED
    assert results[1].status == RoleStatus.ERROR
    assert "Engagement" in (results[1].error or "")
    assert results[2].status == RoleStatus.CREATED


def test_preflight_all_unresolvable_skips_get_roles():
    """If every role fails pre-flight, ``get_roles`` is not called —
    the manager short-circuits to ERROR results."""
    client = MagicMock()
    client.get_all_scopes.return_value = scope_response("Contact")
    manager, _ = make_manager(client)
    roles = [
        RoleDefinition(
            name="A",
            scope_access={
                "Engagement": ScopeAccess(
                    create=True, read="own", edit="own", delete="no",
                    stream="own",
                ),
            },
        ),
        RoleDefinition(
            name="B",
            scope_access={
                "Workshop": ScopeAccess(
                    create=True, read="own", edit="own", delete="no",
                    stream="own",
                ),
            },
        ),
    ]
    results = manager.process_roles(roles)
    assert all(r.status == RoleStatus.ERROR for r in results)
    assert client.get_roles.call_count == 0


def test_preflight_error_lists_all_unresolvable_entities():
    """A single role with multiple unresolvable scope_access entities
    surfaces every one in the error message (alphabetically sorted)."""
    client = MagicMock()
    client.get_all_scopes.return_value = scope_response("Contact")
    manager, _ = make_manager(client)
    role_def = RoleDefinition(
        name="Mentor",
        scope_access={
            "Engagement": ScopeAccess(
                create=True, read="own", edit="own", delete="no", stream="own",
            ),
            "Workshop": ScopeAccess(
                create=True, read="own", edit="own", delete="no", stream="own",
            ),
        },
    )
    results = manager.process_roles([role_def])
    assert results[0].status == RoleStatus.ERROR
    error = results[0].error or ""
    assert "Engagement" in error
    assert "Workshop" in error
    # Alphabetical order in the message.
    assert error.index("Engagement") < error.index("Workshop")

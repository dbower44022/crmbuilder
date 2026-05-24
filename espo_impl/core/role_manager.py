"""Role check/create/update orchestration logic.

The deploy-side counterpart to Section 12.1 / 12.3 / 12.4 of the
v1.3 schema. Reads ``program.roles`` (populated by the loader in
Prompt A and structurally typed by Prompt B) and reconciles
against the target EspoCRM instance's Role records.

Translation layer:
- ``scope_access:`` per-entity blocks → EspoCRM Role ``data`` JSON
  field, keyed by wire-name (``C{Name}`` for custom entities,
  natural name for natives)
- ``system_permissions:`` five-key block → five top-level
  camelCase columns on the Role record:
  ``assignmentPermission``, ``userPermission``, ``exportPermission``,
  ``massUpdatePermission``, ``portalPermission``

PATCH semantics: only the schema-known fields are sent. EspoCRM
columns the v1.3 schema does not cover
(``followerManagementPermission``, ``groupEmailAccountPermission``,
``dataPrivacyPermission``) are preserved as operator-set values
(DEC-2). Entities not declared in a role's ``scope_access:``
block are omitted from ``data`` (matching the schema's whitelist
semantics — omission denies).

Out of scope (handled elsewhere):
- Pipeline ordering ensuring entities exist before roles deploy
  — Prompt E in ``run_worker.py``
- Field-level permissions (``fieldData``) — v1.4 deferred
- Audit-side reverse-engineering of role records — Prompt H
"""

import logging
from collections.abc import Callable
from typing import Any

from espo_impl.core.api_client import EspoAdminClient, _format_error_detail
from espo_impl.core.models import (
    RoleDefinition,
    RoleResult,
    RoleStatus,
    ScopeAccess,
    SystemPermissions,
)
from espo_impl.ui.confirm_delete_dialog import get_espo_entity_name

logger = logging.getLogger(__name__)

OutputCallback = Callable[[str, str], None]


class RoleManagerError(Exception):
    """Raised on fatal errors during role deploy (e.g., HTTP 401)."""


# Mapping from schema snake_case keys to EspoCRM camelCase columns.
# Scope-style keys (all/team/own/no vocabulary).
_SCOPE_PERMISSION_FIELD_MAP: dict[str, str] = {
    "assignment_permission": "assignmentPermission",
    "user_permission": "userPermission",
}
# Flag-style keys (yes/no boolean coerced to string).
_FLAG_PERMISSION_FIELD_MAP: dict[str, str] = {
    "export": "exportPermission",
    "mass_update": "massUpdatePermission",
    "portal": "portalPermission",
}


class RoleManager:
    """Orchestrates reading and writing Role records on EspoCRM.

    :param client: EspoCRM admin API client.
    :param output_fn: Callback for emitting output messages
        (message, color). Same convention as ``team_manager`` and
        ``tooltip_manager``.
    """

    def __init__(
        self,
        client: EspoAdminClient,
        output_fn: OutputCallback,
    ) -> None:
        self.client = client
        self.output_fn = output_fn
        self._server_duplicate_names: set[str] = set()

    # --- Translation layer (pure logic; testable in isolation) ---

    def _translate_data_block(
        self,
        scope_access: dict[str, ScopeAccess],
    ) -> dict[str, dict[str, str]]:
        """Translate a role's ``scope_access`` to the EspoCRM ``data`` field.

        - Entity natural names → wire-names via
          ``get_espo_entity_name``
        - Per-action values: ``create`` bool → ``"yes"`` / ``"no"``
          string; ``read`` / ``edit`` / ``delete`` / ``stream``
          strings passed through verbatim
        - Entities omitted from ``scope_access`` are omitted from
          the result (whitelist semantics)

        :param scope_access: From ``RoleDefinition.scope_access``.
        :returns: The ``data`` field payload dict ready for the
            EspoCRM Role record.
        """
        data: dict[str, dict[str, str]] = {}
        for entity_name, scope in scope_access.items():
            wire_name = get_espo_entity_name(entity_name)
            data[wire_name] = {
                "create": "yes" if scope.create else "no",
                "read": scope.read,
                "edit": scope.edit,
                "delete": scope.delete,
                "stream": scope.stream,
            }
        return data

    def _translate_system_permissions(
        self,
        perms: SystemPermissions | None,
    ) -> dict[str, str]:
        """Translate ``system_permissions`` to EspoCRM Role columns.

        Returns a dict keyed by EspoCRM column name (camelCase),
        containing only the five schema-managed keys. None input
        produces an all-denied result (each value is the
        most-restrictive setting for its key).

        :param perms: From ``RoleDefinition.system_permissions``.
        :returns: Dict ready for inclusion in the Role record
            payload alongside ``data``.
        """
        result: dict[str, str] = {}
        if perms is None:
            perms = SystemPermissions()
        for snake_key, camel_key in _SCOPE_PERMISSION_FIELD_MAP.items():
            result[camel_key] = getattr(perms, snake_key)
        for snake_key, camel_key in _FLAG_PERMISSION_FIELD_MAP.items():
            value = getattr(perms, snake_key)
            result[camel_key] = "yes" if value else "no"
        return result

    def _translate_to_payload(
        self,
        role_def: RoleDefinition,
        *,
        include_name: bool,
    ) -> dict[str, Any]:
        """Build the full EspoCRM Role record payload.

        :param role_def: Role definition from YAML.
        :param include_name: True for CREATE (POST); False for
            UPDATE (PATCH) since name is identity and shouldn't
            be re-sent. The manager treats name divergence as a
            CHECK match failure (different role), not as a rename.
        :returns: Payload dict for ``create_role`` or
            ``update_role``.
        """
        payload: dict[str, Any] = {}
        if include_name:
            payload["name"] = role_def.name
        if role_def.description is not None:
            payload["description"] = role_def.description
        payload["data"] = self._translate_data_block(role_def.scope_access)
        payload.update(
            self._translate_system_permissions(role_def.system_permissions)
        )
        return payload

    # --- Pre-flight server-state validation ---

    def _fetch_server_scope_set(self) -> frozenset[str]:
        """Fetch the server's scope list as a wire-name set.

        Used by ``_preflight_scope_access`` to validate that every
        ``scope_access:`` entity in a YAML role exists on the
        target.

        :returns: Frozenset of wire-form scope names (e.g.,
            ``"CEngagement"``, ``"Contact"``) from
            ``client.get_all_scopes()``.
        :raises RoleManagerError: On HTTP 401 (authentication) or
            any other non-200 status that prevents pre-flight from
            completing. The role-deploy step cannot proceed without
            server-state context.
        """
        status, body = self.client.get_all_scopes()
        if status == 401:
            raise RoleManagerError("Authentication failed (HTTP 401)")
        if status != 200 or body is None:
            error_msg = (
                f"HTTP {status}: {_format_error_detail(body)}"
                if status > 0 else "connection error"
            )
            raise RoleManagerError(
                f"Failed to fetch server scopes for pre-flight: {error_msg}"
            )
        return frozenset(body.keys())

    def _preflight_scope_access(
        self,
        roles: list[RoleDefinition],
        server_scope_set: frozenset[str],
    ) -> dict[str, set[str]]:
        """Identify scope_access entities that do not resolve on the server.

        Translates each role's ``scope_access`` keys to wire-form via
        ``get_espo_entity_name`` (so the comparison is apples-to-apples
        against the server's wire-form scope keys) and identifies any
        that aren't on the target.

        :param roles: YAML role definitions to check.
        :param server_scope_set: From ``_fetch_server_scope_set``.
        :returns: Mapping of role.name to the set of unresolvable
            entity names (in their natural / YAML form, for the
            operator's error message). Roles with empty
            ``scope_access`` or fully-resolving ``scope_access`` are
            absent from the returned dict.
        """
        unresolvable_by_role: dict[str, set[str]] = {}
        for role_def in roles:
            unresolvable: set[str] = set()
            for natural_name in role_def.scope_access.keys():
                wire_name = get_espo_entity_name(natural_name)
                if wire_name not in server_scope_set:
                    unresolvable.add(natural_name)
            if unresolvable:
                unresolvable_by_role[role_def.name] = unresolvable
        return unresolvable_by_role

    # --- CHECK→ACT orchestration ---

    def _fetch_server_roles(self) -> dict[str, dict[str, Any]]:
        """Fetch all roles from the server and index them by name.

        :returns: Mapping of role name to the full server record.
            Empty dict if the server has no roles.
        :raises RoleManagerError: On HTTP 401 (authentication
            failure) or any other non-200 status that prevents
            the CHECK phase from completing.
        """
        status, body = self.client.get_roles()
        if status == 401:
            raise RoleManagerError("Authentication failed (HTTP 401)")
        if status != 200 or body is None:
            error_msg = (
                f"HTTP {status}: {_format_error_detail(body)}"
                if status > 0 else "connection error"
            )
            raise RoleManagerError(
                f"Failed to fetch roles from server: {error_msg}"
            )

        server_list = body.get("list") or []
        by_name: dict[str, dict[str, Any]] = {}
        duplicates: set[str] = set()
        for record in server_list:
            name = record.get("name")
            if not isinstance(name, str):
                continue
            if name in by_name:
                duplicates.add(name)
            by_name[name] = record

        self._server_duplicate_names = duplicates
        return by_name

    def process_roles(
        self,
        roles: list[RoleDefinition],
        dry_run: bool = False,
    ) -> list[RoleResult]:
        """Process every role in the YAML batch against the server.

        Pre-flight runs before CHECK→ACT: every role's
        ``scope_access`` entity references are validated against the
        server's scope list (per DEC for Prompt E). Roles with
        unresolvable entities are ERRORed and skipped; remaining
        roles continue to CHECK→ACT.

        :param roles: ``program.roles``. Empty list yields empty
            result with no API calls.
        :param dry_run: If True, CHECK is performed and intended
            status is recorded, but no POST or PATCH is issued.
        :returns: List of RoleResult, one per input role. Pre-flight
            rejections appear in the result list with
            ``RoleStatus.ERROR`` and a descriptive ``error`` message.
        :raises RoleManagerError: On HTTP 401 from pre-flight or
            CHECK→ACT, or HTTP error on pre-flight scope-list fetch.
        """
        if not roles:
            return []

        # --- Pre-flight ----------------------------------------------
        self.output_fn(
            "[ROLE]  Fetching server scopes for pre-flight ...", "white",
        )
        server_scope_set = self._fetch_server_scope_set()
        unresolvable_by_role = self._preflight_scope_access(
            roles, server_scope_set,
        )

        # CHECK is fetched lazily — only when at least one role passes
        # pre-flight — so a batch in which every role's scope_access is
        # unresolvable does not pay the extra GET /Role round-trip.
        server_roles: dict[str, dict[str, Any]] | None = None

        results: list[RoleResult] = []
        for role_def in roles:
            unresolvable = unresolvable_by_role.get(role_def.name)
            if unresolvable:
                entity_list = ", ".join(sorted(unresolvable))
                error_msg = (
                    f"scope_access references entity not on target: "
                    f"{entity_list}; entity may have been declared in "
                    f"this batch but failed to deploy, or is not "
                    f"declared anywhere"
                )
                self.output_fn(
                    f"[ROLE]  {role_def.name} ... ERROR — {error_msg}",
                    "red",
                )
                results.append(RoleResult(
                    name=role_def.name,
                    status=RoleStatus.ERROR,
                    error=error_msg,
                ))
                continue

            if server_roles is None:
                self.output_fn(
                    "[ROLE]  Fetching server roles ...", "white",
                )
                server_roles = self._fetch_server_roles()
            results.append(
                self._process_one(role_def, server_roles, dry_run),
            )
        return results

    def _process_one(
        self,
        role_def: RoleDefinition,
        server_roles: dict[str, dict[str, Any]],
        dry_run: bool,
    ) -> RoleResult:
        """Process a single role. See process_roles for semantics."""
        name = role_def.name
        prefix = f"[ROLE]  {name}"

        if name in self._server_duplicate_names:
            error_msg = (
                "multiple server roles share this name; cannot "
                "determine which to update"
            )
            self.output_fn(f"{prefix} ... ERROR — {error_msg}", "red")
            return RoleResult(
                name=name, status=RoleStatus.ERROR, error=error_msg,
            )

        existing = server_roles.get(name)

        if existing is None:
            return self._create_role(role_def, prefix, dry_run)

        return self._update_or_skip_role(role_def, existing, prefix, dry_run)

    def _create_role(
        self,
        role_def: RoleDefinition,
        prefix: str,
        dry_run: bool,
    ) -> RoleResult:
        """Create a new role record on the server."""
        name = role_def.name
        self.output_fn(f"{prefix} ... CREATING", "white")
        if dry_run:
            return RoleResult(name=name, status=RoleStatus.CREATED)
        payload = self._translate_to_payload(role_def, include_name=True)
        status, body = self.client.create_role(payload)
        if status == 401:
            raise RoleManagerError("Authentication failed (HTTP 401)")
        if status in (200, 201) and body is not None:
            role_id = body.get("id")
            self.output_fn(f"{prefix} ... CREATED OK", "green")
            return RoleResult(
                name=name,
                status=RoleStatus.CREATED,
                role_id=role_id,
            )
        error_msg = (
            f"HTTP {status}: {_format_error_detail(body)}"
            if status > 0 else "connection error"
        )
        self.output_fn(f"{prefix} ... ERROR — {error_msg}", "red")
        return RoleResult(
            name=name, status=RoleStatus.ERROR, error=error_msg,
        )

    def _update_or_skip_role(
        self,
        role_def: RoleDefinition,
        existing: dict[str, Any],
        prefix: str,
        dry_run: bool,
    ) -> RoleResult:
        """Diff desired against existing; SKIP or PATCH accordingly."""
        name = role_def.name
        role_id = existing.get("id")

        desired_payload = self._translate_to_payload(
            role_def, include_name=False,
        )

        desired_data = desired_payload["data"]
        server_data = existing.get("data") or {}
        data_differs = desired_data != server_data

        perms_differ = False
        for camel_key in (
            list(_SCOPE_PERMISSION_FIELD_MAP.values())
            + list(_FLAG_PERMISSION_FIELD_MAP.values())
        ):
            desired_value = desired_payload[camel_key]
            server_value = existing.get(camel_key)
            if server_value is None:
                # Most-restrictive default for the missing column.
                server_value = "no"
            if desired_value != server_value:
                perms_differ = True
                break

        desired_description = role_def.description or None
        current_description = existing.get("description") or None
        description_differs = desired_description != current_description

        if not (data_differs or perms_differ or description_differs):
            self.output_fn(f"{prefix} ... NO CHANGE", "gray")
            return RoleResult(
                name=name, status=RoleStatus.SKIPPED, role_id=role_id,
            )

        # Only include description in PATCH if it differs; otherwise
        # leave it alone (the translator added it conditionally).
        if description_differs:
            desired_payload["description"] = desired_description
        else:
            desired_payload.pop("description", None)

        self.output_fn(f"{prefix} ... UPDATING", "white")
        if dry_run:
            return RoleResult(
                name=name, status=RoleStatus.UPDATED, role_id=role_id,
            )
        if role_id is None:
            error_msg = "server record missing 'id' field"
            self.output_fn(f"{prefix} ... ERROR — {error_msg}", "red")
            return RoleResult(
                name=name, status=RoleStatus.ERROR, error=error_msg,
            )
        status, body = self.client.update_role(role_id, desired_payload)
        if status == 401:
            raise RoleManagerError("Authentication failed (HTTP 401)")
        if status == 200:
            self.output_fn(f"{prefix} ... UPDATED OK", "green")
            return RoleResult(
                name=name, status=RoleStatus.UPDATED, role_id=role_id,
            )
        error_msg = (
            f"HTTP {status}: {_format_error_detail(body)}"
            if status > 0 else "connection error"
        )
        self.output_fn(f"{prefix} ... ERROR — {error_msg}", "red")
        return RoleResult(
            name=name,
            status=RoleStatus.ERROR,
            role_id=role_id,
            error=error_msg,
        )

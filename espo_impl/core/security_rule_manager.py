"""Field-level security rule CHECK→ACT→VERIFY orchestration logic.

The deploy-side counterpart to Section 12.7 (field-level permissions) and
the field-level half of Section 12.5 (role-aware visibility). Reads the
top-level ``program.field_permissions`` and ``program.field_visibility``
lists and reconciles them against the target EspoCRM instance.

Two surfaces, two outcomes:

- **Field permissions** (``fieldPermissions:``) are fully deployable. They
  live on the EspoCRM Role record's ``fieldData`` JSON column — a dict shaped
  ``{entity: {field: {"read": "...", "edit": "..."}}}`` parallel to the
  entity-scope ``data`` column the :class:`RoleManager` writes. This manager
  CHECKs the role's current ``fieldData``, MERGEs the declared cells in
  (whitelist semantics — unrelated cells are preserved), PATCHes the Role via
  the same REST path RoleManager uses, then VERIFIEs by re-reading the role.

- **Field visibility** (``fieldVisibility:``) has no EspoCRM 9.x deploy path —
  Dynamic Logic carries no role-condition type (DEC-243). Every rule is
  recorded ``NOT_SUPPORTED`` and surfaced in the MANUAL CONFIGURATION REQUIRED
  block; nothing is written.

Role I/O is not duplicated here: the CHECK and VERIFY re-reads reuse
``RoleManager._fetch_server_roles`` and the ACT path reuses
``EspoAdminClient.update_role`` (Role PATCH), so the wire shape stays the
single source of truth in ``role_manager`` / ``api_client``.
"""

import copy
import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from espo_impl.core.api_client import EspoAdminClient, _format_error_detail
from espo_impl.core.models import (
    FieldPermissionSpec,
    FieldVisibilitySpec,
    SecurityRuleResult,
    SecurityRuleStatus,
)
from espo_impl.core.role_manager import RoleManager

logger = logging.getLogger(__name__)

OutputCallback = Callable[[str, str], None]


class SecurityRuleManagerError(Exception):
    """Raised on fatal errors during security-rule deploy (e.g., HTTP 401)."""


# Section 12.7 permission level → EspoCRM fieldData read/edit cell.
_LEVEL_TO_CELL: dict[str, dict[str, str]] = {
    "read_write": {"read": "yes", "edit": "yes"},
    "read_only": {"read": "yes", "edit": "no"},
    "no_access": {"read": "no", "edit": "no"},
}


class SecurityRuleManager:
    """Orchestrates field-level permission and visibility rules.

    :param client: EspoCRM admin API client.
    :param output_fn: Callback for emitting output messages
        (message, color). Same convention as ``role_manager`` and
        ``team_manager``.
    """

    def __init__(
        self,
        client: EspoAdminClient,
        output_fn: OutputCallback,
    ) -> None:
        self.client = client
        self.output_fn = output_fn
        self._role_mgr = RoleManager(client, output_fn)

    def process_security_rules(
        self,
        field_permissions: list[FieldPermissionSpec],
        field_visibility: list[FieldVisibilitySpec],
        dry_run: bool = False,
    ) -> list[SecurityRuleResult]:
        """Process all field-level security rules against the server.

        Visibility rules are emitted as NOT_SUPPORTED first (no server
        round-trip). Permission rules are grouped by role; each role is
        CHECKed, MERGEd, PATCHed (skipped when ``dry_run``), and VERIFIEd.

        :param field_permissions: ``program.field_permissions``.
        :param field_visibility: ``program.field_visibility``.
        :param dry_run: If True, CHECK is performed and intended status
            recorded, but no PATCH is issued and no VERIFY re-read runs.
        :returns: One :class:`SecurityRuleResult` per input rule.
        :raises SecurityRuleManagerError: On HTTP 401 from the CHECK
            role fetch or the ACT PATCH.
        """
        results: list[SecurityRuleResult] = []

        # --- Field visibility: always NOT_SUPPORTED (DEC-243) ---------
        for vis in field_visibility:
            self.output_fn(
                f"[NOT SUPPORTED] {vis.entity}.{vis.field} "
                f"role={vis.role} — role-aware visibility has no "
                f"EspoCRM 9.x deploy path (DEC-243); configure manually",
                "yellow",
            )
            results.append(SecurityRuleResult(
                role=vis.role,
                entity=vis.entity,
                field=vis.field,
                status=SecurityRuleStatus.NOT_SUPPORTED,
            ))

        if not field_permissions:
            return results

        # --- CHECK: fetch server roles once, group rules by role ------
        self.output_fn(
            "[SECURITY] Fetching server roles for field permissions ...",
            "white",
        )
        server_roles = self._role_mgr._fetch_server_roles()

        by_role: dict[str, list[FieldPermissionSpec]] = defaultdict(list)
        for fp in field_permissions:
            by_role[fp.role].append(fp)

        for role_name, rules in by_role.items():
            results.extend(
                self._process_role(role_name, rules, server_roles, dry_run)
            )

        return results

    def _process_role(
        self,
        role_name: str,
        rules: list[FieldPermissionSpec],
        server_roles: dict[str, dict[str, Any]],
        dry_run: bool,
    ) -> list[SecurityRuleResult]:
        """CHECK→ACT→VERIFY all field-permission rules for one role.

        :param role_name: EspoCRM Role name.
        :param rules: The role's field-permission rules.
        :param server_roles: Name→record map from ``_fetch_server_roles``.
        :param dry_run: When True, no PATCH is issued.
        :returns: One result per rule.
        :raises SecurityRuleManagerError: On HTTP 401 during PATCH.
        """
        prefix = f"[SECURITY] {role_name}"
        existing = server_roles.get(role_name)

        if existing is None:
            error_msg = f"role '{role_name}' not found on target"
            self.output_fn(f"{prefix} ... ERROR — {error_msg}", "red")
            return [
                SecurityRuleResult(
                    role=role_name,
                    entity=r.entity,
                    field=r.field,
                    status=SecurityRuleStatus.ERROR,
                    error=error_msg,
                )
                for r in rules
            ]

        role_id = existing.get("id")
        current = existing.get("fieldData") or {}

        self.output_fn(
            f"{prefix} ... CHECK ({len(rules)} field permission(s))",
            "white",
        )

        # Build the merged fieldData (whitelist merge — only named cells
        # change) and the per-rule intended status against current state.
        merged: dict[str, Any] = copy.deepcopy(current)
        intended: list[tuple[FieldPermissionSpec, dict[str, str], SecurityRuleStatus]] = []
        for r in rules:
            cell = dict(_LEVEL_TO_CELL[r.level])
            current_cell = current.get(r.entity, {}).get(r.field)
            if current_cell == cell:
                status = SecurityRuleStatus.MATCHES
            elif current_cell is None:
                status = SecurityRuleStatus.CREATED
            else:
                status = SecurityRuleStatus.UPDATED
            merged.setdefault(r.entity, {})[r.field] = cell
            intended.append((r, cell, status))

        needs_patch = any(
            s is not SecurityRuleStatus.MATCHES for _, _, s in intended
        )

        if not needs_patch:
            self.output_fn(f"{prefix} ... MATCHES (no change)", "gray")
            return [
                SecurityRuleResult(
                    role=role_name, entity=r.entity, field=r.field,
                    status=s, role_id=role_id,
                )
                for r, _, s in intended
            ]

        if dry_run:
            self.output_fn(f"{prefix} ... WOULD APPLY", "yellow")
            return [
                SecurityRuleResult(
                    role=role_name, entity=r.entity, field=r.field,
                    status=s, role_id=role_id,
                )
                for r, _, s in intended
            ]

        # --- ACT: PATCH the merged fieldData --------------------------
        if role_id is None:
            error_msg = "server role record missing 'id' field"
            self.output_fn(f"{prefix} ... ERROR — {error_msg}", "red")
            return [
                SecurityRuleResult(
                    role=role_name, entity=r.entity, field=r.field,
                    status=SecurityRuleStatus.ERROR, error=error_msg,
                )
                for r in rules
            ]

        self.output_fn(f"{prefix} ... APPLYING", "white")
        status_code, body = self.client.update_role(
            role_id, {"fieldData": merged}
        )
        if status_code == 401:
            raise SecurityRuleManagerError("Authentication failed (HTTP 401)")
        if status_code != 200:
            error_msg = (
                f"HTTP {status_code}: {_format_error_detail(body)}"
                if status_code > 0 else "connection error"
            )
            self.output_fn(f"{prefix} ... ERROR — {error_msg}", "red")
            return [
                SecurityRuleResult(
                    role=role_name, entity=r.entity, field=r.field,
                    status=SecurityRuleStatus.ERROR, error=error_msg,
                    role_id=role_id,
                )
                for r in rules
            ]

        # --- VERIFY: single re-read of the role's fieldData -----------
        # First slice uses a single re-read rather than a poll loop: the
        # Role PATCH is a synchronous record write (no async cache rebuild
        # like field/layout deploys), so the read-back is reliable.
        verify_field_data = self._read_back_field_data(role_name)
        return [
            self._verify_rule(role_name, role_id, r, cell, status, verify_field_data)
            for r, cell, status in intended
        ]

    def _read_back_field_data(self, role_name: str) -> dict[str, Any] | None:
        """Re-read a role's ``fieldData`` for post-PATCH verification.

        Uses ``RoleManager._fetch_server_roles`` so the read shape stays
        consistent with the CHECK phase. Returns ``None`` if the role
        vanished between PATCH and re-read (treated as a verify miss).

        :param role_name: EspoCRM Role name.
        :returns: The role's ``fieldData`` dict, or None.
        """
        try:
            roles = self._role_mgr._fetch_server_roles()
        except Exception as exc:  # noqa: BLE001 — verify miss, not fatal
            logger.warning(
                "Verify re-read failed for role %s: %s", role_name, exc
            )
            return None
        record = roles.get(role_name)
        if record is None:
            return None
        return record.get("fieldData") or {}

    def _verify_rule(
        self,
        role_name: str,
        role_id: str | None,
        rule: FieldPermissionSpec,
        cell: dict[str, str],
        status: SecurityRuleStatus,
        verify_field_data: dict[str, Any] | None,
    ) -> SecurityRuleResult:
        """Compare one intended cell against the read-back fieldData.

        :param role_name: EspoCRM Role name.
        :param role_id: Server-assigned Role record ID.
        :param rule: The field-permission rule being verified.
        :param cell: The intended ``{"read": ..., "edit": ...}`` cell.
        :param status: The CHECK-phase intended status (CREATED/UPDATED).
        :param verify_field_data: The role's re-read ``fieldData``.
        :returns: The rule's result — ``status`` on match, ERROR on miss.
        """
        prefix = f"[SECURITY] {role_name} {rule.entity}.{rule.field}"
        read_cell = (verify_field_data or {}).get(rule.entity, {}).get(rule.field)
        if read_cell == cell:
            self.output_fn(f"{prefix} ... VERIFIED", "green")
            return SecurityRuleResult(
                role=role_name, entity=rule.entity, field=rule.field,
                status=status, role_id=role_id,
            )
        error_msg = (
            f"verification mismatch: expected {cell}, read {read_cell}"
        )
        self.output_fn(f"{prefix} ... VERIFY FAILED — {error_msg}", "red")
        return SecurityRuleResult(
            role=role_name, entity=rule.entity, field=rule.field,
            status=SecurityRuleStatus.ERROR, error=error_msg, role_id=role_id,
        )

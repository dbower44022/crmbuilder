# CLAUDE-CODE-PROMPT — audit-v1.2-D — Role Manager (Deploy-Side) with Translation Layer

**Repo:** `crmbuilder`
**Series:** `audit-v1.2` (eleven-prompt sequence implementing the v1.2
expansion of the Audit feature per
`PRDs/product/crmbuilder-automation-PRD/audit-v1.2-planning.md` v1.3)
**Last Updated:** 05-24-26 03:30
**Spec:** `PRDs/product/app-yaml-schema.md` Sections 12.1 (Roles),
12.3 (Scope-Level Entity Access), 12.4 (System Permissions).
**Planning:** `PRDs/product/crmbuilder-automation-PRD/audit-v1.2-planning.md`
§5 Prompt D.
**Depends on:** Prompt A (commit `84b55c2`), Prompt B (commit
`d1bccac`), Prompt C (commit `974e580`).
**Governance:** Two new decisions to author in this conversation's
close-out payload. Both resolved during Prompt D kickoff and recorded
in §1 below.

## Position in the Series

This is **Prompt D — the substantive deploy-side manager.** The
translation layer that maps YAML's clean per-entity permission model
to EspoCRM's `data` JSON field shape is the work that makes the
security half of the audit-v1.2 workstream actually deploy. Teams
landed in Prompt C; roles land here.

After this prompt:

- **Prompt E** adds the security pipeline step in `run_worker.py`,
  ordering team and role deploy before entity / layout / field deploy
- **Prompts F / G** add the role-aware visibility surfaces
- **Prompt H** adds audit-side discovery
- **Prompts I–K** complete filtered-tab audit, UI, and documentation

**This prompt does NOT implement:**

- Pipeline integration in `run_worker.py._run_full()` — Prompt E
- Cross-batch role-name uniqueness validation — Prompt B already
  did this via `ProgramContext.role_count_by_name`
- The `role:` leaf clause variant in `condition_expression.py` —
  Prompt F
- Role-aware `requiredWhen` / `visibleWhen` / `forRoles:` wiring
  — Prompt G
- Audit-side discovery (`_discover_roles`, `_discover_teams`) —
  Prompt H
- Server-state-aware entity resolution for `scope_access:` keys —
  the planning doc §5 Prompt B and §5 Prompt E place this concern
  on Prompt E's pipeline ordering, which guarantees entities are
  deployed before roles. Prompt D's manager translates YAML to
  EspoCRM payload and writes; if the server rejects, the error is
  surfaced per-role rather than blocked by a pre-flight server
  check.
- Field-level permissions and permission presets — deferred to v1.4
  per planning doc §7

## 1. Two New Governance Decisions

Both resolved in the planning conversation immediately preceding
this prompt. Implementation prompts cite by DEC number; fresh DECs
should be authored in this conversation's close-out payload.

### Decision 1 — `audit_log` removed from schema §12.4

The schema spec §12.4 lists `audit_log: yes / no` as one of six
system permissions. EspoCRM 9.x does not expose an audit-log Role
permission in its `valuePermissionList`
(`assignmentPermission`, `userPermission`, `portalPermission`,
`groupEmailAccountPermission`, `exportPermission`,
`massUpdatePermission`, `followerManagementPermission`,
`dataPrivacyPermission` — verified via
`docs.espocrm.com/development/metadata/app-acl/`). Keeping
`audit_log` in the schema would force a NOT_SUPPORTED translation
that the operator could never make succeed.

**Resolution: drop `audit_log` from §12.4.** The remaining v1.3
system permissions are five: `assignment_permission`,
`user_permission`, `export`, `mass_update`, `portal`.

**Rationale.** Schema describes what the deploy engine can
deliver. Operators wanting audit-log access control on EspoCRM 9.x
use the standard `scope_access.AuditLog` mechanism (the AuditLog
entity supports the regular per-action scope vocabulary).

**Consequence for the workstream.** This prompt includes
(a) a schema-doc patch removing `audit_log` from the §12.4 table,
example, and flag-style-keys sentence, and (b) backing out the
`audit_log` field on `SystemPermissions` in `models.py` and the
matching entry in `SYSTEM_PERMISSION_FLAG_KEYS` (both added by
Prompt B).

### Decision 2 — EspoCRM-only permissions preserved on PATCH

EspoCRM has three Role-level permissions the schema does not
cover: `followerManagementPermission`, `groupEmailAccountPermission`,
`dataPrivacyPermission`. When the role manager PATCHes an existing
role, only the fields the schema knows about are sent. EspoCRM's
PATCH semantics leave unsent fields alone, so operator-set values
on these three permissions (made via the EspoCRM admin UI) are
preserved across redeploys.

**Resolution: PATCH only schema-known fields. Preserve unmanaged
fields.**

**Rationale.** Matches the conservative-deletion / conservative-
modification convention shared across every existing manager in
the codebase ("don't touch what you don't manage"). The
alternative (reset to platform defaults on every PATCH) would
silently clobber operator settings; surprising failure mode.

**Consequence for the workstream.** The PATCH payload includes
exactly the five system_permissions camelCase fields plus the
recomputed `data` JSON blob. Never includes `followerManagementPermission`,
`groupEmailAccountPermission`, or `dataPrivacyPermission`.

## 2. EspoCRM Role Record Shape — Translation Target

Documented here so the translator code can reference a single
authoritative specification. Sourced from
`docs.espocrm.com/development/metadata/app-acl/`,
`docs.espocrm.com/development/metadata/scopes/`, and the
EspoCRM 9.x deploy that CBM targets.

**Top-level Role fields the v1.3 schema manages (five):**

| YAML key | EspoCRM column | Value form |
| --- | --- | --- |
| `assignment_permission` | `assignmentPermission` | string: `all` / `team` / `own` / `no` |
| `user_permission` | `userPermission` | string: `all` / `team` / `own` / `no` |
| `export` | `exportPermission` | string: `yes` / `no` (boolean expressed as string) |
| `mass_update` | `massUpdatePermission` | string: `yes` / `no` |
| `portal` | `portalPermission` | string: `yes` / `no` |

**Top-level Role fields EspoCRM exposes that the schema does NOT
manage (three; preserved on PATCH per DEC-2):**
`followerManagementPermission`, `groupEmailAccountPermission`,
`dataPrivacyPermission`.

**`data` field — per-entity scope access.** A JSON object on the
Role record keyed by entity wire-name. Per-entity shape:

```json
{
  "CEngagement": {
    "create": "yes",
    "read":   "own",
    "edit":   "own",
    "delete": "no",
    "stream": "own"
  },
  "Contact": {
    "create": "no",
    "read":   "team",
    "edit":   "no",
    "delete": "no",
    "stream": "team"
  }
}
```

Each value in the per-entity object is a STRING (no booleans for
`create`; the value is the literal string `"yes"` or `"no"`).
Entities omitted from `data` default to denied for that role —
matching the schema's whitelist semantics in §12.3.

**Entity wire-name conversion.** Custom entities declared in YAML
with natural form (`Engagement`) become wire-form (`CEngagement`)
in the `data` field. The convention is `C{Name}` — capital `C`
prefix, no dash, no other transformation. Native entities use
their natural form unchanged (`Contact`, `Account`, `Meeting`).
The translator MUST use the existing
`espo_impl.ui.confirm_delete_dialog.get_espo_entity_name` helper
(used by `tooltip_manager.py`) so the convention stays in one
place across managers.

## Scope

In scope:

1. `PRDs/product/app-yaml-schema.md` §12.4 — three-edit schema-doc
   correction implementing DEC-1: remove `audit_log` from the
   example block, the table, and the flag-style-keys sentence.
2. `espo_impl/core/models.py` — back out the `audit_log` field on
   `SystemPermissions` and the matching entry in
   `SYSTEM_PERMISSION_FLAG_KEYS` (both from Prompt B); add
   `RoleStatus` enum and `RoleResult` dataclass.
3. `espo_impl/core/api_client.py` — add `get_roles()`,
   `create_role(payload)`, `update_role(role_id, payload)`
   methods. Mirrors Prompt C's `get_teams` / `create_team` /
   `update_team` pattern; `create_role` and `update_role` take
   the full payload dict rather than named fields because the
   payload contains the variable-shape `data` JSON blob.
4. `espo_impl/core/role_manager.py` — new module implementing
   `RoleManager` with the translation layer (`_translate_to_payload`,
   `_translate_data_block`, `_translate_system_permissions`) and
   the CHECK→ACT orchestration (`process_roles`).
5. `tests/test_role_manager.py` — new test module covering the
   translation layer in isolation plus the manager paths
   (create / skip / update / error / dry-run / mixed batch).
6. `tests/test_config_loader.py` — update the affected Prompt B
   tests that assert `audit_log` is parsed (back-out: tests need
   to use the five remaining keys and reject `audit_log` as an
   unknown key).

Out of scope:

- Pipeline integration, role-aware visibility, audit-side
  discovery, filtered-tab audit, UI work, documentation — Prompts
  E through K
- Field-level permissions (`fieldData`) and permission presets —
  v1.4 deferred per planning doc §7
- Server-state validation of scope_access entity names — Prompt E
  via pipeline ordering

## Working Method

Standard CRM Builder Python conventions:

```bash
uv run ruff check espo_impl/ tests/
uv run pytest tests/ -v
```

**Precedent.** `espo_impl/core/team_manager.py` (Prompt C) is the
closest structural analog for the CHECK→ACT orchestration —
mirror its shape (bulk-fetch, by-name index, server-duplicate-name
detection, dry-run path, per-team error isolation). The role
manager is more substantive only in the translation layer, which
is new pure-logic code.

## Files to Modify

### 1. `PRDs/product/app-yaml-schema.md` §12.4 — schema-doc correction (DEC-1)

Three surgical edits:

**Edit 1 — Example block, line 2498.** Remove the line:
```
      audit_log:             no
```

**Edit 2 — Table, line 2510.** Remove the row:
```
| `audit_log` | `yes` / `no` | Whether the role may view the platform audit log |
```

**Edit 3 — Flag-style keys sentence, line 2515.** Change:
```
Flag-style keys (`export`, `mass_update`, `audit_log`, `portal`)
```
to:
```
Flag-style keys (`export`, `mass_update`, `portal`)
```

No other §12.4 edits. The revision-history table at the top of the
doc does not need an entry — this is a definitional correction, not
a semantic change to a still-evolving schema area.

### 2. `espo_impl/core/models.py` — back out `audit_log`; add Role types

**Back out `audit_log` from Prompt B's work.** In the existing
`SystemPermissions` dataclass, remove the line:
```python
audit_log: bool = False
```

In the existing module-level constant:
```python
SYSTEM_PERMISSION_FLAG_KEYS: frozenset[str] = frozenset({
    "export",
    "mass_update",
    "audit_log",   # ← remove this line
    "portal",
})
```
becomes:
```python
SYSTEM_PERMISSION_FLAG_KEYS: frozenset[str] = frozenset({
    "export",
    "mass_update",
    "portal",
})
```

**Add `RoleStatus` enum.** Place immediately after the existing
`TeamStatus` block (added in Prompt C) so role-side dataclasses are
grouped with their team-side counterparts:

```python
class RoleStatus(Enum):
    """Outcome status for a role operation.

    Uses the 5-value variant: CREATED / UPDATED / SKIPPED / ERROR /
    NOT_SUPPORTED. No DRIFT because the role manager always
    reconciles via PATCH; NOT_SUPPORTED reserved for any role whose
    declarations cannot be translated to EspoCRM (e.g., references
    to features not implemented in this workstream — currently
    none, but the slot leaves room for future schema additions).
    """

    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"
    ERROR = "error"
    NOT_SUPPORTED = "not_supported"


@dataclass
class RoleResult:
    """Result of processing a single role.

    :param name: Role name from YAML (also the match key).
    :param status: Outcome status.
    :param role_id: Server-assigned record ID. Populated after
        a successful CREATE; available from CHECK on
        SKIPPED / UPDATED for already-existing roles.
    :param error: Error message if status is ERROR.
    """

    name: str
    status: RoleStatus
    role_id: str | None = None
    error: str | None = None
```

### 3. `espo_impl/core/api_client.py` — three new methods

Place in the existing "record CRUD" cluster (after Prompt C's
`update_team` at the new line range, before `test_connection`):

```python
def get_roles(
    self,
) -> tuple[int, dict[str, Any] | None]:
    """List all Role records on the target instance.

    Bulk-fetches up to 200 roles in a single GET. Pagination
    beyond this is not implemented; documented as a future
    scaling concern matching ``get_teams``.

    :returns: Tuple of (status_code, response_json or None).
        Standard EspoCRM list shape ``{"total": N, "list": [...]}``
        on success.
    """
    url = f"{self.profile.api_url}/Role?maxSize=200"
    return self._request("GET", url)


def create_role(
    self, payload: dict[str, Any],
) -> tuple[int, dict[str, Any] | None]:
    """Create a new Role record.

    Unlike ``create_team``, the payload is variable-shape (it
    carries the ``data`` JSON blob and the five system-permission
    columns), so this method takes the full payload dict directly
    rather than named parameters.

    :param payload: Full Role creation payload. Required keys
        depend on EspoCRM 9.x's Role record schema; the manager
        layer is responsible for constructing a valid payload.
    :returns: Tuple of (status_code, created record or None).
    """
    return self.create_record("Role", payload)


def update_role(
    self, role_id: str, payload: dict[str, Any],
) -> tuple[int, dict[str, Any] | None]:
    """PATCH an existing Role record.

    Only the fields present in ``payload`` are updated; other
    fields are preserved. This is the semantic that lets the
    manager omit EspoCRM-only permissions (DEC-2) from the
    update path.

    :param role_id: Server-assigned Role record ID.
    :param payload: Partial Role update payload.
    :returns: Tuple of (status_code, response or None).
    """
    return self.patch_record("Role", role_id, payload)
```

### 4. `espo_impl/core/role_manager.py` — new module

Create the file. Module structure mirrors `team_manager.py`. The
substantive additions are the three translation methods.

**Module docstring** — establish the out-of-scope items and the
translation-target authority:

```python
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
# Scope-style keys (read/edit/delete/stream-style vocabulary).
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
```

**The `RoleManager` class.** Mirror `TeamManager` structure with
the three new translation methods.

```python
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
          string; ``read``/``edit``/``delete``/``stream`` strings
          passed through verbatim
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
            perms = SystemPermissions()  # all defaults (denied)
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

    # --- CHECK→ACT orchestration ---

    def _fetch_server_roles(self) -> dict[str, dict[str, Any]]:
        """Fetch all roles from the server, indexed by name.

        Same shape and error contract as ``TeamManager._fetch_server_teams``.
        """
        # (Mirror TeamManager's implementation; set
        # self._server_duplicate_names for name-collision detection.)
        ...

    def process_roles(
        self,
        roles: list[RoleDefinition],
        dry_run: bool = False,
    ) -> list[RoleResult]:
        """Process every role in the YAML batch against the server.

        :param roles: ``program.roles``. Empty list yields empty
            result with no API calls.
        :param dry_run: If True, CHECK is performed and intended
            status is recorded, but no POST or PATCH is issued.
        :returns: List of RoleResult, one per input role.
        :raises RoleManagerError: On HTTP 401 or other fatal CHECK
            errors.
        """
        if not roles:
            return []
        self.output_fn("[ROLE]  Fetching server roles ...", "white")
        server_roles = self._fetch_server_roles()
        results: list[RoleResult] = []
        for role_def in roles:
            results.append(self._process_one(role_def, server_roles, dry_run))
        return results

    def _process_one(
        self,
        role_def: RoleDefinition,
        server_roles: dict[str, dict[str, Any]],
        dry_run: bool,
    ) -> RoleResult:
        """Process a single role. See process_roles for semantics."""
        # ... mirror TeamManager._process_one structure ...
        # CHECK: match by name; flag duplicates
        # CREATE path: build CREATE payload (include_name=True),
        #              call create_role
        # SKIP path: server data + permissions all match desired
        # UPDATE path: any divergence → PATCH with UPDATE payload
        #              (include_name=False)
        # ERROR paths: server duplicate names, HTTP errors, etc.
```

**Diff logic for update detection.** The SKIP-vs-UPDATE decision
compares the translated desired payload against the existing
server record:

- For the `data` field: deep-compare the translated dict against
  the server's `data` value (both are dicts of dicts). Unordered
  comparison — dict equality handles this correctly.
- For each of the five managed permissions: compare the translated
  string value against the server's column value. Server may store
  these as `None` (uninitialized) or as a string; coerce `None` →
  the most-restrictive value for the diff (so `None` server vs
  `"no"` translation registers as a match, not divergence).
- ANY divergence → UPDATE. Diffing is at-fault-or-clean granularity;
  no per-field PATCH selectivity beyond "the five permissions and
  data". `description` is included in the PATCH payload only if it
  differs from the server's current value.

### 5. Tests — `tests/test_role_manager.py`

Mirror `tests/test_team_manager.py` shape. MagicMock the client;
small `make_manager()` helper.

**Translation-layer tests (no manager involvement):**

- `_translate_data_block`: empty scope_access → empty dict;
  custom entity → wire-name with `C` prefix; native entity →
  natural name unchanged; create=True/False → string "yes"/"no";
  scope strings passed through verbatim.
- `_translate_system_permissions`: None → all-denied dict with
  all five camelCase keys; partial SystemPermissions with one key
  set → result has all five keys with that one carrying the set
  value and the others at defaults.
- `_translate_to_payload`: include_name=True path produces a
  payload with `name`, `description` (if set), `data`, and all
  five system-permission keys; include_name=False path omits
  `name`. Verify EspoCRM-only permissions
  (followerManagementPermission, etc.) are NEVER in the payload.

**CHECK→ACT manager tests:**

Mirror the team_manager test coverage scaled to roles:

- Empty input → empty result, no API calls
- Create path: server empty, YAML one role → CREATED with role_id
- Create with full payload: verify create_role called with `name`,
  `description`, `data` containing correct wire-name keys, and the
  five permissions
- Dry-run create: CREATED but no create_role call
- Skip path: server role's data + permissions match translated
  desired
- Skip with description differing: still triggers UPDATE (description
  is part of the diff)
- Update path — scope_access change: server data differs in one
  entity's permissions → UPDATED, PATCH called with `data` and the
  five permissions but NOT `name`
- Update path — system_permissions change: server permission column
  differs → UPDATED
- Update path — multiple kinds of change in one role → single
  UPDATE call with the full payload
- Dry-run update: UPDATED but no update_role call
- Server stores `None` for a permission column; YAML/translation
  produces "no" → SKIP (None ≡ most-restrictive default)
- Server-side duplicate role names: duplicated-name YAML role
  ERRORs; others process normally
- get_roles 401 → RoleManagerError
- get_roles 500 → RoleManagerError
- create_role 401 → RoleManagerError
- update_role 401 → RoleManagerError
- create_role 500 → ERROR result for that role; batch continues
- update_role 500 → ERROR result for that role; batch continues
- Mixed batch: new + skip + update in one process_roles call

### 6. Tests — `tests/test_config_loader.py` — back out `audit_log`

Locate the Prompt B tests that include `audit_log` in their
`system_permissions:` fixture YAML. Update them so:

- Tests that previously included `audit_log: yes/no` no longer do.
- Add at least one new test asserting that `audit_log` is now
  rejected as an unknown system-permission key (verifies DEC-1 is
  enforced at the loader level).

## Acceptance Criteria

1. Schema-doc patch lands per §1 above; `audit_log` no longer
   appears in `app-yaml-schema.md` §12.4.
2. `models.py`'s `SystemPermissions` no longer has an `audit_log`
   field; `SYSTEM_PERMISSION_FLAG_KEYS` no longer includes
   `audit_log`.
3. `models.py` carries `RoleStatus` (CREATED / UPDATED / SKIPPED /
   ERROR / NOT_SUPPORTED) and `RoleResult` per §2 above.
4. `api_client.py` carries `get_roles`, `create_role`,
   `update_role` per §3 above.
5. `role_manager.py` exists with the `RoleManager` class
   implementing CHECK→ACT and the three translation methods
   (`_translate_data_block`, `_translate_system_permissions`,
   `_translate_to_payload`).
6. The translation layer correctly maps:
   - Custom entity natural names → wire-names via
     `get_espo_entity_name`
   - Native entity names → unchanged
   - Per-action `create` boolean → `"yes"` / `"no"` strings; the
     four scope actions → strings passed through verbatim
   - Five schema system-permission keys → five EspoCRM camelCase
     columns; values normalized appropriately
   - EspoCRM-only permissions
     (`followerManagementPermission`, `groupEmailAccountPermission`,
     `dataPrivacyPermission`) are NEVER in the create or update
     payload (DEC-2 enforcement)
7. CHECK→ACT manager correctly handles all paths: empty input,
   create, skip-no-change, update-on-divergence, server-duplicate-
   name error, per-role HTTP errors, authentication failure
   (raises `RoleManagerError`).
8. Diff logic treats server `None` permission column as equivalent
   to the most-restrictive translated value (no spurious updates
   on round-trip).
9. `dry_run=True` records intended status without invoking
   `create_role` or `update_role`.
10. Prompt B tests for `audit_log` updated; new test asserts
    `audit_log` is now rejected as an unknown key.
11. New tests cover every translation-layer and manager path
    enumerated in §5.
12. All other existing tests continue to pass.
13. `uv run ruff check espo_impl/ tests/` passes clean on touched
    files.
14. `uv run pytest tests/ -v` passes.
15. Commit and push to `main` with a clear message referencing
    this prompt, the planning doc, and the two new DECs to be
    formalized in this conversation's close-out.

## Out of Scope

- Pipeline integration in `run_worker.py._run_full()` — Prompt E
- Server-state validation of `scope_access` entity names — Prompt
  E via pipeline ordering
- Role-aware visibility — Prompts F / G
- Audit-side role discovery and emission — Prompt H
- Field-level permissions (`fieldData`) — v1.4 deferred
- Permission presets — v1.4 deferred
- Filtered-tab audit — Prompt I
- UI work — Prompt J
- Documentation — Prompt K

## Reporting Back

When finished, report:

- Modified file paths and line counts
- New tests added (count and brief coverage summary)
- Updated Prompt B tests (count and what changed)
- Total test count before → after, ruff status
- Commit hash and message
- Any deviations from this prompt's specification (and why)
- Any open questions or follow-ups for Prompt E

The expected next step after Prompt D is green is **Prompt E**:
security pipeline step in `run_worker.py._run_full()`, ordering
team and role deploy before the existing entity/field/layout work.
With Prompt D's manager landed, Prompt E is a smaller integration
prompt — wire the manager into the pipeline, add the security
step's progress indicator and error handling.

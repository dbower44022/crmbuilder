# CLAUDE-CODE-PROMPT — audit-v1.2-H — Audit-Side Discovery (Roles, Teams, security.yaml)

**Repo:** `crmbuilder`
**Series:** `audit-v1.2` (eleven-prompt sequence implementing the v1.2
expansion of the Audit feature per
`PRDs/product/crmbuilder-automation-PRD/audit-v1.2-planning.md` v1.3)
**Last Updated:** 05-24-26 07:30
**Spec:** `PRDs/product/app-yaml-schema.md` Sections 12.1 (Roles),
12.2 (Teams), 12.3 (Scope-Level Entity Access), 12.4 (System
Permissions). Section 12.5 is documented as NOT_AUDITABLE in v1.3
per DEC-6 — see §1 below.
**Planning:** `PRDs/product/crmbuilder-automation-PRD/audit-v1.2-planning.md`
§5 Prompt H — with scope reduction per DEC-6.
**Depends on:** Prompt C (commit `974e580` — `get_teams()`), Prompt D
(commit `4e82b686` — `get_roles()` and translation reference),
Prompt G (commit pending — DEC-6 / DEC-7 §12.5 NOT_SUPPORTED
treatment).
**Governance:** No new decisions in this prompt. Carries forward
the seven DECs already accumulated for this conversation's
close-out.

## Position in the Series

This is **Prompt H — the audit-side counterpart to Prompts C–G.**
What Prompts C and D deployed (teams and roles with scope_access
and system_permissions), Prompt H discovers and emits as
`security.yaml`. What Prompts F and G left as NOT_SUPPORTED
(§12.5 role-aware visibility) is also NOT_AUDITABLE in v1.3 — no
target wire surface exists to reverse-engineer from.

After this prompt:

- **Prompt I** adds filtered-tab audit capture
- **Prompts J / K** complete UI work and documentation

**This prompt does NOT implement:**

- Audit-side reverse-engineering of `role:` leaf clauses in
  visibleWhen — EspoCRM 9.x Dynamic Logic has no role-condition
  type to reverse from. The audit log emits a NOT_AUDITABLE
  advisory citing DEC-6.
- Audit-side reverse-engineering of `forRoles:` layout variants —
  Layout Sets bind to Teams, not Roles; no per-role layout records
  exist to walk. Same NOT_AUDITABLE advisory.
- Filtered-tab audit — Prompt I (separate concern; routine to
  sequence after H)
- UI changes — Prompt J
- Documentation updates — Prompt K

## 1. Reduced Scope per DEC-6 — §12.5 Is NOT_AUDITABLE in v1.3

The planning doc §5 Prompt H originally specified that the audit
manager's `_reverse_dynamic_logic()` would be extended to
recognize and emit `role:` leaf clauses when it sees EspoCRM's
role-aware dynamic-logic JSON. That extension was contingent on
EspoCRM 9.x having a role-condition type in dynamic-logic JSON.
Prompt G's research established that no such type exists; DEC-6
finalized §12.5 as NOT_SUPPORTED for deploy on EspoCRM 9.x.

**Consequence for the audit half.** There is nothing on the
target instance to reverse-engineer for §12.5. Dynamic Logic
metadata has no role-condition type to read. Layout Sets bind to
Teams not Roles; no per-role layout records exist. Manually-
configured role-aware visibility (via Dynamic Handler JavaScript)
is operator-written code that cannot be reverse-engineered into
structured YAML.

**The audit's behavior in v1.3:**

1. Discover and emit what IS deployable: roles, teams,
   `scope_access`, `system_permissions` (the parts Prompt D
   deploys)
2. Emit a NOT_AUDITABLE log entry at the end of the security
   step indicating that any role-aware visibility configured
   manually on the target was not captured. Operators are
   directed to maintain `visibleWhen: role:` and `forRoles:`
   YAML by hand for documentation purposes; audit will not
   round-trip them in v1.3
3. The emitted `security.yaml` carries the deployable surface
   only

This reduction shrinks Prompt H roughly 30% from the planning
doc's original scope. The dropped surface (`_reverse_dynamic_logic`
role-clause handling, forRoles layout reverse-engineering) is
re-added in v1.4 alongside the real implementation of §12.5
deploy.

## 2. Migration Numbering — `_client_v15`, Not `_client_v4`

The planning doc §5 Prompt H names "_client_v4" as the migration
adding role and team tables. The actual client schema has
progressed past that — the current head migration in
`automation/db/migrations.py` is `_client_v14`. The next
available version for Prompt H's tables is **`_client_v15`**.

This is purely a numbering update from the planning doc; no
design change. The migration adds the same tables the planning
doc described.

Future readers note: when Prompt I (filtered-tab audit) lands, it
will need its own next-available migration (likely `_client_v16`)
or extend `_client_v15` if both prompts are still in flight.
Since H lands first under the current sequencing, Prompt I gets
v16.

## 3. Reverse-Translation Specification

The deploy side (Prompt D `role_manager.py`) translates YAML →
EspoCRM Role record. Prompt H needs the inverse: EspoCRM Role
record → YAML.

### 3.1 Entity wire-name → natural-name

Prompt D uses
`espo_impl.ui.confirm_delete_dialog.get_espo_entity_name` for
natural → wire (`Engagement` → `CEngagement`). The reverse is
already implemented in
`espo_impl.core.audit_utils.strip_entity_c_prefix`
(`CEngagement` → `Engagement`; native entity names pass
through unchanged). Reuse it.

### 3.2 `Role.data` → `scope_access:`

Inverse of Prompt D's `_translate_data_block`:

- Source: EspoCRM Role record's `data` JSON field (per-entity
  permission matrix keyed by wire-name)
- Target: `RoleAuditResult.scope_access: dict[str, ScopeAccess]`
  keyed by natural name, then emitted into YAML

Wire shape per entity:
```json
{"create": "yes", "read": "all", "edit": "team", "delete": "no", "stream": "own"}
```

YAML target shape per entity:
```yaml
create: yes
read:   all
edit:   team
delete: no
stream: own
```

The `create` value is a STRING `"yes"` / `"no"` in EspoCRM but a
`bool` in the schema's `ScopeAccess` dataclass. Coerce string
`"yes"`/`"no"` to `True`/`False`. The other four actions pass
through as-is (vocabulary is identical: `all` / `team` / `own` /
`no`).

Entities present in `Role.data` but with no schema-valid actions
(e.g., `"MyScope1": true` — a boolean rather than an action dict)
are skipped with an audit-log warning. The schema doesn't have a
representation for boolean-scope access, and these are usually
non-entity scopes anyway.

### 3.3 Role columns → `system_permissions:`

Inverse of Prompt D's `_translate_system_permissions`. Reads the
five camelCase columns from the Role record and maps to the five
snake_case schema keys:

| EspoCRM column | YAML key | Coercion |
| --- | --- | --- |
| `assignmentPermission` | `assignment_permission` | string passthrough |
| `userPermission` | `user_permission` | string passthrough |
| `exportPermission` | `export` | `"yes"` → `True`, `"no"` → `False` |
| `massUpdatePermission` | `mass_update` | same |
| `portalPermission` | `portal` | same |

The three EspoCRM-only permissions (DEC-2 preservation list)
are NOT read into the audit output; the YAML schema doesn't
carry them.

### 3.4 Role-level fields

The Role record's other fields:
- `name` → YAML `name:` (identity match)
- `description` → YAML `description:` (None for missing, otherwise
  string)
- `data` → split into `scope_access:` per §3.2
- top-level permission columns → `system_permissions:` per §3.3

Audit captures whatever the source instance carries; no
cross-validation against any source-of-truth list (per DEC-178).
Persona metadata that originated in YAML and was lost during
deploy (no EspoCRM column for it) cannot be recovered; audit
emits `persona: null` or omits the key.

### 3.5 Team fields

Simpler:
- `name` → YAML `name:`
- `description` → YAML `description:` (None for missing)

## Scope

In scope:

1. `espo_impl/core/audit_manager.py`:
   - Extend `AuditOptions` with `include_security: bool = True` per
     DEC-180
   - Add `RoleAuditResult` and `TeamAuditResult` dataclasses
   - Extend `AuditReport` with `roles: list[RoleAuditResult]` and
     `teams: list[TeamAuditResult]` collections
   - Add `_discover_roles()` method using `client.get_roles()` —
     fetches all roles, translates each per §3
   - Add `_discover_teams()` method using `client.get_teams()` —
     fetches all teams, translates each per §3.5
   - Add `_reverse_scope_access()` helper
   - Add `_reverse_system_permissions()` helper
   - Extend `run_audit()` orchestration to invoke security
     discovery when `options.include_security` is True
   - Extend `_write_yaml_files()` to emit
     `<output_dir>/security/security.yaml` containing `roles:`
     and `teams:` blocks when security captured anything (per
     DEC-182 placement)
   - Emit informational warning for any captured role with empty
     `scope_access:` per DEC-179
   - Emit NOT_AUDITABLE advisory at end of security step per DEC-6
2. `automation/db/migrations.py`:
   - Add `_client_v15(conn)` migration creating `Role` and `Team`
     client-DB tables
   - Append `(15, _client_v15)` to `CLIENT_MIGRATIONS` list
3. `espo_impl/core/audit_db.py`:
   - Add `_insert_role()` and `_insert_team()` helpers
   - Wire both into `insert_audit_records()` ordering (teams
     before roles is fine; no FK dependency in the audit DB)
4. Tests:
   - `tests/test_audit_manager.py` — discovery, reverse-translation,
     write-yaml-files emit `security/security.yaml`
   - `tests/test_audit_db.py` — role and team insertion
   - `tests/db/test_client_migrations.py` — `_client_v15`
     idempotency and schema shape

Out of scope:

- Audit-side reverse engineering of `role:` clauses, `forRoles:`
  variants — NOT_AUDITABLE per DEC-6
- Filtered-tab audit — Prompt I
- UI work — Prompt J
- Documentation — Prompt K
- Cross-instance validation of audited roles against any source-of-
  truth list

## Working Method

Standard CRM Builder Python conventions:

```bash
uv run ruff check espo_impl/ automation/db/ tests/
uv run pytest tests/ -v
```

**Precedent.** `_discover_relationships` (audit_manager.py line
747) is the closest structural analog for `_discover_roles` /
`_discover_teams` — it queries a server resource, walks each
record, builds dataclass results, returns a list, and is invoked
by `run_audit` gated on an `AuditOptions` boolean. Mirror its
shape.

For the reverse-translation helpers, the closest analog is the
inverse-direction work in `_reverse_field_name` (line 605) and
`_reverse_dynamic_logic` (line 717). The new helpers are pure
functions on the captured wire data.

For `_client_v15`, mirror the idempotent pattern of `_client_v13`
or `_client_v14`: probe `sqlite_master` for existing tables, use
`CREATE TABLE IF NOT EXISTS`, skip silently if prerequisites are
absent.

## Files to Modify

### 1. `espo_impl/core/audit_manager.py` — dataclasses and discovery

**Extend `AuditOptions`** (add new boolean):

```python
@dataclass
class AuditOptions:
    """Options controlling what the audit captures."""

    include_custom_fields: bool = True
    include_native_custom_fields: bool = True
    include_detail_layouts: bool = True
    include_list_layouts: bool = True
    include_relationships: bool = True
    include_native_fields: bool = False
    include_security: bool = True  # NEW per DEC-180
```

**Add `RoleAuditResult` and `TeamAuditResult` dataclasses.** Place
after the existing `RelationshipAuditResult` (around line 92):

```python
@dataclass
class RoleAuditResult:
    """Result of auditing a single role.

    Captures only the surface the v1.3 schema defines and Prompt D
    deploys. Fields the schema doesn't carry (e.g., the three
    EspoCRM-only permissions per DEC-2) are not captured.

    :param name: Role identity (server-assigned name).
    :param description: Role description text (None if not set).
    :param persona: Always None on capture — the source instance
        doesn't carry persona metadata (it's documentation in YAML
        only per DEC-178). Operators reattach personas manually
        when curating audited YAML.
    :param scope_access: Per-entity access scope, keyed by natural
        entity name (Engagement, Contact, etc.).
    :param system_permissions: The five schema-managed system
        permissions per Section 12.4.
    """

    name: str
    description: str | None = None
    persona: str | None = None
    scope_access: dict[str, "ScopeAccess"] = field(default_factory=dict)
    system_permissions: "SystemPermissions | None" = None


@dataclass
class TeamAuditResult:
    """Result of auditing a single team."""

    name: str
    description: str | None = None
```

The forward references on `ScopeAccess` and `SystemPermissions`
let the dataclasses import from `models.py` without circular
issues; mirror however other audit dataclasses handle this.

**Extend `AuditReport`** with the two new collections:

```python
@dataclass
class AuditReport:
    # ... existing fields ...
    roles: list[RoleAuditResult] = field(default_factory=list)
    teams: list[TeamAuditResult] = field(default_factory=list)
```

**Add discovery methods.** Place after `_discover_relationships`
(after line 870 or similar):

```python
def _discover_teams(
    self, report: AuditReport,
) -> list[TeamAuditResult]:
    """Discover all teams on the source instance.

    Each team becomes a TeamAuditResult with name and description.
    Per DEC-1 (audit_log removed) and DEC-2 (EspoCRM-only
    permissions preserved), team_to_user membership is not
    captured — it's runtime data per Schema §12.2.

    :param report: Audit report for error/warning accumulation.
    :returns: List of TeamAuditResult. Empty list on no teams or
        on API failure (with the failure logged to the audit
        report).
    """
    status, body = self._client.get_teams()
    if status != 200 or not isinstance(body, dict):
        report.errors.append(
            f"Failed to fetch teams (HTTP {status})"
        )
        return []
    server_teams = body.get("list", []) if isinstance(body, dict) else []
    results: list[TeamAuditResult] = []
    for record in server_teams:
        if not isinstance(record, dict):
            continue
        name = record.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        description = record.get("description")
        if description is not None and not isinstance(description, str):
            description = None
        results.append(TeamAuditResult(
            name=name,
            description=description if description else None,
        ))
    return results


def _discover_roles(
    self, report: AuditReport,
) -> list[RoleAuditResult]:
    """Discover all roles on the source instance.

    Translates each Role record's wire shape to the schema's
    structured form via :meth:`_reverse_scope_access` and
    :meth:`_reverse_system_permissions`.

    Per DEC-179, captures with empty scope_access produce an
    informational warning in the audit log; the YAML output is
    unaffected.

    :param report: Audit report for error/warning accumulation.
    :returns: List of RoleAuditResult.
    """
    status, body = self._client.get_roles()
    if status != 200 or not isinstance(body, dict):
        report.errors.append(
            f"Failed to fetch roles (HTTP {status})"
        )
        return []
    server_roles = body.get("list", []) if isinstance(body, dict) else []
    results: list[RoleAuditResult] = []
    for record in server_roles:
        if not isinstance(record, dict):
            continue
        name = record.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        description = record.get("description")
        if description is not None and not isinstance(description, str):
            description = None
        scope_access = self._reverse_scope_access(
            record.get("data") or {}, report, role_name=name,
        )
        system_permissions = self._reverse_system_permissions(record)

        if not scope_access:
            report.warnings.append(
                f"Role '{name}' has empty scope_access; this role "
                f"grants no entity access on the source instance"
            )

        results.append(RoleAuditResult(
            name=name,
            description=description if description else None,
            persona=None,  # per DEC-178; source doesn't carry persona
            scope_access=scope_access,
            system_permissions=system_permissions,
        ))
    return results
```

**Add reverse-translation helpers.** Place near
`_reverse_dynamic_logic` (around line 720):

```python
def _reverse_scope_access(
    self,
    data: dict,
    report: AuditReport,
    role_name: str,
) -> dict[str, "ScopeAccess"]:
    """Reverse-translate EspoCRM Role.data to schema scope_access.

    Inverse of ``role_manager._translate_data_block``.

    :param data: Raw ``data`` field from the Role record (dict of
        per-scope permission objects).
    :param report: Audit report for warnings on skipped scopes.
    :param role_name: Role name for warning attribution.
    :returns: Mapping of natural entity name to ScopeAccess.
    """
    from espo_impl.core.audit_utils import strip_entity_c_prefix
    from espo_impl.core.models import ScopeAccess

    result: dict[str, ScopeAccess] = {}
    for wire_name, value in data.items():
        if not isinstance(wire_name, str):
            continue
        natural_name = strip_entity_c_prefix(wire_name)
        if not isinstance(value, dict):
            # Boolean scope (e.g., {"MyScope": true}) — schema has
            # no representation; skip with warning
            report.warnings.append(
                f"Role '{role_name}': scope '{natural_name}' has "
                f"non-mapping value {value!r}; skipped (not "
                f"representable in v1.3 schema)"
            )
            continue
        try:
            scope = ScopeAccess(
                create=value.get("create") == "yes",
                read=str(value.get("read") or "no"),
                edit=str(value.get("edit") or "no"),
                delete=str(value.get("delete") or "no"),
                stream=str(value.get("stream") or "no"),
            )
            result[natural_name] = scope
        except (ValueError, TypeError) as exc:
            report.warnings.append(
                f"Role '{role_name}': scope '{natural_name}' "
                f"failed to translate ({exc}); skipped"
            )
    return result


def _reverse_system_permissions(
    self,
    record: dict,
) -> "SystemPermissions | None":
    """Reverse-translate EspoCRM Role columns to SystemPermissions.

    Inverse of ``role_manager._translate_system_permissions``.
    Reads only the five schema-managed camelCase columns; the
    three EspoCRM-only permissions (DEC-2 preservation list) are
    not captured.

    :param record: Full Role record from the EspoCRM API.
    :returns: SystemPermissions instance, or None if none of the
        five managed columns are present on the record.
    """
    from espo_impl.core.models import SystemPermissions

    has_any = any(
        record.get(col) is not None
        for col in (
            "assignmentPermission", "userPermission",
            "exportPermission", "massUpdatePermission",
            "portalPermission",
        )
    )
    if not has_any:
        return None

    return SystemPermissions(
        assignment_permission=str(
            record.get("assignmentPermission") or "no"
        ),
        user_permission=str(
            record.get("userPermission") or "no"
        ),
        export=record.get("exportPermission") == "yes",
        mass_update=record.get("massUpdatePermission") == "yes",
        portal=record.get("portalPermission") == "yes",
    )
```

**Wire into `run_audit`.** After Step 3 (relationships) and
before Step 4 (write YAML files):

```python
# Step 3.5: Discover security (per DEC-180 default True)
teams: list[TeamAuditResult] = []
roles: list[RoleAuditResult] = []
if self._options.include_security:
    self._cb("[AUDIT]    Discovering teams ...", "cyan")
    teams = self._discover_teams(report)
    self._cb(
        f"[AUDIT]    Found {len(teams)} teams",
        "cyan",
    )
    self._cb("[AUDIT]    Discovering roles ...", "cyan")
    roles = self._discover_roles(report)
    self._cb(
        f"[AUDIT]    Found {len(roles)} roles",
        "cyan",
    )
    # Per DEC-6: §12.5 role-aware visibility is NOT_AUDITABLE
    self._cb(
        "[AUDIT]    NOTE: Section 12.5 role-aware visibility is "
        "NOT_AUDITABLE on EspoCRM 9.x (DEC-6). Any manually-"
        "configured role-aware visibility on the target is "
        "not captured by this audit.",
        "yellow",
    )

report.teams = teams
report.roles = roles
```

**Extend `_write_yaml_files`** to emit `security/security.yaml`
when `report.roles` or `report.teams` is non-empty:

```python
# Per DEC-182: security YAMLs live in a security/ subdirectory
if report.roles or report.teams:
    security_dir = output_dir / "security"
    security_dir.mkdir(parents=True, exist_ok=True)
    security_yaml: dict[str, Any] = {}
    if report.teams:
        security_yaml["teams"] = [
            self._team_to_yaml_dict(t) for t in report.teams
        ]
    if report.roles:
        security_yaml["roles"] = [
            self._role_to_yaml_dict(r) for r in report.roles
        ]
    self._write_yaml_file(
        security_dir / "security.yaml", security_yaml,
    )
    files_written += 1
```

Add the per-record YAML helpers `_team_to_yaml_dict` and
`_role_to_yaml_dict` near the existing `_write_yaml_file` (around
line 1011). For roles, emit `scope_access` keyed by natural
entity name with the five-action shape, and `system_permissions`
with the five schema-managed keys when present.

### 2. `automation/db/migrations.py` — `_client_v15`

Add the migration function and register it. Place
`_client_v15` after `_client_v14` (around line 763):

```python
def _client_v15(conn: sqlite3.Connection) -> None:
    """Add Role and Team tables for audit-v1.2 security capture.

    Tables hold the audited role and team records for instances
    where the audit feature has been run against a source CRM
    that includes a security configuration.

    Idempotent via ``CREATE TABLE IF NOT EXISTS``. Skips silently
    if the Instance table does not yet exist (a fresh database
    created via ``_client_v1`` already includes the new tables).

    See PRDs/product/crmbuilder-automation-PRD/CLAUDE-CODE-PROMPT-audit-v1.2-H-audit-side-discovery.md.
    """
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    if "Instance" not in tables:
        return

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS Role (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instance_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            scope_access_json TEXT,
            system_permissions_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (instance_id) REFERENCES Instance(id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_role_instance "
        "ON Role(instance_id)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS Team (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instance_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (instance_id) REFERENCES Instance(id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_team_instance "
        "ON Team(instance_id)"
    )
```

Append to `CLIENT_MIGRATIONS`:

```python
CLIENT_MIGRATIONS: list[tuple[int, Migration]] = [
    # ... existing entries through (14, _client_v14) ...
    (15, _client_v15),
]
```

### 3. `espo_impl/core/audit_db.py` — role and team insertion

Add `_insert_team` and `_insert_role` helpers mirroring the shape
of the existing `_insert_entity` / `_insert_relationship`
helpers. The Role insert serializes the scope_access dict and
system_permissions dataclass to JSON for storage (the audit DB
keeps the typed surface as opaque JSON; downstream consumers
parse it back when needed).

Wire both into `insert_audit_records` after the existing entity
and relationship inserts. Suggested order: teams, then roles
(no FK dependency between them, but the conventional ordering
matches the Configure pipeline's team-before-role sequence
established in Prompts C / D / E).

Return the per-record insert count so the caller's
`db_records` total reflects the new inserts.

### 4. Tests

**`tests/test_audit_manager.py`:**

- `test_discover_teams_empty` — server returns empty list; result
  is empty list; no errors recorded
- `test_discover_teams_two_teams` — server returns two teams;
  results carry name and description; description normalized to
  None for empty/missing
- `test_discover_teams_http_error` — server returns 500;
  empty result; error recorded in report
- `test_discover_roles_empty` — server returns empty list
- `test_discover_roles_with_scope_access` — server returns one
  role with scope_access on a custom entity (CEngagement) and a
  native entity (Contact); result has scope_access keyed by
  natural names (Engagement, Contact); each ScopeAccess has the
  correct typed values
- `test_discover_roles_with_system_permissions` — server returns
  role with all five permissions set; result has SystemPermissions
  with correct typed values
- `test_discover_roles_partial_system_permissions` — server has
  only assignmentPermission set; SystemPermissions present with
  that one populated and others at defaults
- `test_discover_roles_no_system_permissions` — server has none of
  the five columns; system_permissions is None
- `test_discover_roles_empty_scope_access_warning` — role with
  empty scope_access generates an informational warning in
  report.warnings; YAML output still includes the role
- `test_discover_roles_boolean_scope_skipped` — role's data has a
  boolean-value scope (e.g., `{"MyScope": true}`); skipped with
  warning
- `test_discover_roles_create_yes_translation` — scope_access entry
  with `create: "yes"` becomes ScopeAccess.create=True; `create:
  "no"` → False
- `test_discover_roles_persona_always_none` — captured role has
  persona=None even if record carries some other field; persona
  isn't captured per DEC-178
- `test_run_audit_emits_security_yaml` — full run with security
  enabled and teams/roles present writes `<output_dir>/security/
  security.yaml`; file contains `teams:` and `roles:` blocks
- `test_run_audit_no_security_yaml_when_disabled` —
  `include_security=False`; no security.yaml written; no role/team
  discovery API calls
- `test_run_audit_no_security_yaml_when_empty` —
  `include_security=True` but server has no teams or roles; no
  security.yaml written (placeholder file would be pointless)
- `test_run_audit_emits_not_auditable_advisory` — security
  discovery completes; audit log includes the §12.5 NOT_AUDITABLE
  advisory line

**`tests/test_audit_db.py`:**

- `test_insert_team_creates_row` — TeamAuditResult inserted; row
  visible in Team table with correct name and description
- `test_insert_role_creates_row_with_json_blobs` — RoleAuditResult
  inserted; row's scope_access_json and system_permissions_json
  columns hold the serialized payload
- `test_insert_audit_records_includes_role_and_team_counts` — full
  flow with roles and teams; return count includes the new
  inserts

**`tests/db/test_client_migrations.py`:**

- `test_client_v15_creates_role_table` — fresh DB through v15;
  Role table exists with expected columns and FK
- `test_client_v15_creates_team_table` — same for Team
- `test_client_v15_idempotent` — running v15 twice doesn't error
  (CREATE IF NOT EXISTS protection)
- `test_client_v15_no_instance_table_skips` — DB without Instance
  table; v15 runs without creating Role/Team (preserves the
  skip-silently pattern from neighboring migrations)

## Acceptance Criteria

1. `AuditOptions.include_security` exists and defaults to True per
   DEC-180.
2. `RoleAuditResult` and `TeamAuditResult` dataclasses carry the
   field shapes specified in §3.
3. `AuditReport.roles` and `AuditReport.teams` collections exist
   and populate during `run_audit`.
4. `_discover_teams` and `_discover_roles` correctly translate the
   EspoCRM wire shape to the schema's structured form, applying
   the natural-name conversion via `strip_entity_c_prefix`.
5. `_reverse_scope_access` correctly handles all five per-action
   fields with `create` boolean coercion and the other four
   action vocabulary passthrough.
6. `_reverse_system_permissions` reads only the five
   schema-managed camelCase columns; the three EspoCRM-only
   permissions are not captured.
7. Empty `scope_access` produces an informational warning per
   DEC-179; the role is still emitted in YAML.
8. Boolean-value scopes in Role.data (e.g., `{"MyScope": true}`)
   are skipped with a warning per §3.2.
9. `_write_yaml_files` emits `<output_dir>/security/security.yaml`
   per DEC-182 when security captured anything; skipped when
   nothing was captured.
10. `run_audit` emits the §12.5 NOT_AUDITABLE advisory in the
    audit log per DEC-6.
11. `_client_v15` migration creates Role and Team tables
    idempotently; skips silently when the Instance prerequisite
    table is absent; registered in `CLIENT_MIGRATIONS`.
12. `audit_db._insert_role` and `_insert_team` insert correctly
    and contribute to the `insert_audit_records` total count.
13. All existing tests continue to pass.
14. New tests cover every path enumerated in §4 above.
15. `uv run ruff check espo_impl/ automation/db/ tests/` passes
    clean on touched files.
16. `uv run pytest tests/ -v` passes.
17. Commit and push to `main` with a clear message referencing
    this prompt and the DEC-6 / DEC-178..182 governance.

## Out of Scope

- Audit-side reverse engineering of `role:` clauses or `forRoles:`
  variants — NOT_AUDITABLE per DEC-6
- Filtered-tab audit — Prompt I
- UI work (entity picker, security checkbox in the audit dialog,
  overwrite-confirmation dialog) — Prompt J
- Documentation updates — Prompt K
- v1.4 implementation of any §12.5 surface — future workstream

## Reporting Back

When finished, report:

- Modified file paths and line counts
- New tests added (count and brief coverage summary)
- Total test count before → after, ruff status
- Commit hash and message
- Any deviations from this prompt's specification (and why)
- Any open questions or follow-ups for Prompt I

The expected next step after Prompt H is green is **Prompt I** —
filtered-tab audit capture (`_discover_filtered_tabs`), the
`FilteredTabAuditResult` dataclass, and extending the
`_client_v15` migration (or adding `_client_v16`) for the
filtered-tab table. Prompt I is structurally similar to this
prompt — bulk-fetch from server, reverse-translate, emit into
the existing per-entity YAML files.

# CLAUDE-CODE-PROMPT — audit-v1.2-B — Structured `scope_access` and `system_permissions` Parsing

**Repo:** `crmbuilder`
**Series:** `audit-v1.2` (eleven-prompt sequence implementing the v1.2
expansion of the Audit feature per
`PRDs/product/crmbuilder-automation-PRD/audit-v1.2-planning.md` v1.3)
**Last Updated:** 05-23-26 17:15
**Spec:** `PRDs/product/app-yaml-schema.md` Sections 12.3 (Scope-Level
Entity Access) and 12.4 (System Permissions) — authoritative for
the YAML shape and vocabulary this prompt implements.
**Planning:** `PRDs/product/crmbuilder-automation-PRD/audit-v1.2-planning.md`
§5 Prompt B.
**Depends on:** Prompt A (commit `4c7f06f`) — the raw-passthrough
seams `scope_access_raw` and `system_permissions_raw` on
`RoleDefinition` are now populated by the loader and ready for
structured parsing alongside them.
**Governance:** SES-060 / DEC-178..182 covers the audit-v1.2 design
decisions; one in-session decision from the Prompt B kickoff
(natural-form scope_access keys) is recorded under §1 below and
should be captured as a fresh DEC in this conversation's close-out
payload.

## Position in the Series

This is **Prompt B — the second of the security-foundation pair.**
Prompt A added loader recognition of `roles:` and `teams:` as
top-level keys with minimal typed fields and raw passthrough.
Prompt B turns the raw passthroughs into typed dataclasses and
adds validator coverage for the vocabulary and entity-name
resolution rules. Together, Prompts A and B complete the
loader/validator half of the security workstream.

After this prompt:

- **Prompts C / D** add the deploy-side managers
  (`team_manager.py`, `role_manager.py`) that consume the
  structured fields this prompt populates
- **Prompt E** adds the security pipeline step and security-file
  deploy ordering
- **Prompts F / G** add role-aware visibility (the `role:` leaf
  clause in `condition_expression.py` and the layout-level
  `forRoles:` wiring)
- **Prompt H** adds audit-side discovery, the `_client_v4`
  migration for role/team/filtered-tab tables, and `security.yaml`
  emission

**This prompt does NOT implement:**

- Any deploy-side managers, API client methods, or pipeline
  ordering — Prompts C–E
- The `role:` leaf clause variant in `condition_expression.py` —
  Prompt F
- Role-aware `requiredWhen` / `visibleWhen` / `forRoles:` wiring —
  Prompt G
- Audit-side discovery or `security.yaml` emission — Prompt H
- Server-state-aware entity resolution for `scope_access:` keys —
  deferred per planning doc §5 Prompt B; the validator resolves
  against the batch context only (`entity_names` plus the native
  entity registry), matching the deferred-validation pattern
  already used for cross-batch field references

## 1. In-Session Decision — Natural-Form `scope_access` Keys

The planning conversation for this prompt resolved a schema
inconsistency between §12.3's example block (which used
`c-Engagement:` as a `scope_access` key) and the rest of the
schema's natural-form convention (every other YAML construct that
references an entity uses the same string as the `entities:`
block's key, with no prefix).

**Resolution: natural form.** `scope_access:` keys use the same
string as `entities:` block keys (`Engagement`, `Contact`,
`Account`) — never the c-prefixed wire form. The `C` prefix that
appears in EspoCRM's wire metadata is applied by the deploy
engine at deploy time; it is not visible at the YAML layer.

**Rationale.** Consistency with `relationships:` blocks,
cross-entity `requiredWhen` field references, `filteredTabs:`
scope binding, and every other entity reference in the schema.
A single divergent convention in `scope_access:` would force
operators to remember two forms for the same entity and would
weaken validator error messages.

**Consequence for the workstream.** This prompt includes a
two-line correction to `PRDs/product/app-yaml-schema.md` §12.3
(see Files to Modify §1 below). The validator resolves entity
names against `program.entities[i].name` (natural form, already
how `EntityDefinition.name` is populated by the loader) unioned
with the `native_entity_types.NATIVE_ENTITY_BASE_TYPE` registry.
No schema-version bump warranted — this is a documentation fix
to a single example block, not a vocabulary change.

This decision is governed by a fresh DEC to be authored in this
conversation's close-out payload.

## 2. Note — Planning Doc vs Schema Spec Field Enumeration

The planning doc §5 Prompt B lists the `ScopeAccess` dataclass as
having `entity_name`, `read`, `edit`, `delete`, `stream`,
`assignmentPermission`, and `recordAccessControl` fields. The
schema spec §12.3 is narrower: only `create`, `read`, `edit`,
`delete`, `stream` per-entity, with `assignment_permission`
moved to the system-permissions block (§12.4) and
`recordAccessControl` not present at the YAML layer at all (it's
an EspoCRM Role-data field handled at deploy time by the
forthcoming `role_manager.py`).

**The schema spec is authoritative** per the planning doc's own
framing in §3 Decision 2.5 ("all five parts of Section 12 in
scope, including role-aware visibility") and §1 ("This section
is the authoritative specification"). This prompt implements the
schema spec's narrower per-entity field set; the planning doc's
broader enumeration was an early draft anchored in EspoCRM's
wire shape and is superseded by the schema's per-entity vs
per-role partition.

## Scope

In scope:

1. `PRDs/product/app-yaml-schema.md` §12.3 — two-line correction:
   replace `c-Engagement:` with `Engagement:` in the example
   block; rewrite the line-2455 parenthetical to match the
   natural-form convention.
2. `espo_impl/core/models.py` — add `ScopeAccess` and
   `SystemPermissions` dataclasses with typed fields per the
   schema vocabulary; extend `RoleDefinition` with structured
   `scope_access` and `system_permissions` fields (alongside the
   existing `*_raw` passthroughs from Prompt A); add module-level
   vocabulary constants.
3. `espo_impl/core/models.py` — extend `ProgramContext` with
   `entity_names`, `role_names`, `team_names` frozensets and
   `role_count_by_name` / `team_count_by_name` count maps for
   cross-batch resolution and uniqueness detection. Update
   `from_programs` to populate the new fields.
4. `espo_impl/core/config_loader.py` — add `_parse_scope_access`
   and `_parse_system_permissions` parser methods; wire them into
   the existing `_parse_roles` so structured fields populate
   alongside the raw passthroughs; preserve the raw passthroughs
   verbatim (regression-safe for Prompt A's behavior).
5. `espo_impl/core/config_loader.py` — add `_validate_roles` and
   `_validate_teams` validator methods covering vocabulary,
   entity-name resolution, system-permissions key enumeration,
   within-file uniqueness, and cross-batch uniqueness via
   `ProgramContext`. Wire both into `validate_program()`.
6. Tests for parsing, validation, vocabulary normalization,
   entity resolution, system-permissions enumeration, and
   cross-batch uniqueness.

Out of scope:

- Schema-version bump — the spec §12.3 already defines the
  vocabulary; the correction in §1 above is a doc-error fix to
  a single example, not a vocabulary change
- Server-state-aware entity resolution for `scope_access` keys
  (an entity declared in the batch but not yet on the target
  server should validate cleanly; entity-on-server-but-not-in-batch
  resolution is deferred to Prompt E with the security pipeline
  step)
- Cross-batch role-name uniqueness with origin-file reporting
  in the error message — this prompt's validator emits
  uniqueness errors per-file (operator sees one error per file
  involved in the duplicate); origin-file tracking can be a
  follow-on polish if the multi-error noise becomes a problem
  in practice
- All Prompts C–K deliverables — see "Position in the Series"
  above for the per-prompt mapping

## Working Method

Standard CRM Builder Python conventions:

```bash
# After changes:
uv run ruff check espo_impl/ tests/
uv run pytest tests/ -v
```

All new code: no GUI dependencies, fully testable pure logic.
Edits limited to the files enumerated below.

## Files to Modify

### 1. `PRDs/product/app-yaml-schema.md` — §12.3 schema-doc correction

Two small edits, both within Section 12.3:

**Edit 1 — Example block (around line 2398–2426).** In the
`scope_access:` example, replace `c-Engagement:` (line 2400) and
`c-Session:` (line 2407) with their natural forms. The corrected
block reads:

```yaml
roles:
  - name: "Mentor"
    scope_access:
      Engagement:
        create: no
        read:   own
        edit:   own
        delete: no
        stream: own

      Session:
        create: yes
        read:   own
        edit:   own
        delete: no
        stream: own

      Contact:
        create: no
        read:   team
        edit:   no
        delete: no
        stream: team

      Account:
        create: no
        read:   team
        edit:   no
        delete: no
        stream: no
```

**Edit 2 — Parenthetical (line 2453–2456).** Rewrite the
sentence about custom-entity name form to match the natural-form
convention. From:

> Unresolved entity names are a hard-reject error. Custom-entity
> names use their natural form (e.g., `c-Engagement`, matching
> the key under `entities:` in the domain YAML); platform-specific
> prefixing is applied at deploy time.

To:

> Unresolved entity names are a hard-reject error. Custom-entity
> names use their natural form — the same string used as the key
> under the domain YAML's `entities:` block (e.g., `Engagement`,
> not `c-Engagement` or `CEngagement`). The platform-specific
> `C` prefix that appears in EspoCRM's wire metadata is applied
> by the deploy engine at deploy time and is not visible at the
> YAML layer.

No other schema-doc edits. The revision-history table at the top
of the doc does not need an entry — this is an example fix, not
a semantic schema change.

### 2. `espo_impl/core/models.py` — new dataclasses, extended models, constants

**New module-level constants** (place near the existing
`SUPPORTED_ENTITY_TYPES` / `VALID_NORMALIZE_VALUES` cluster at
the top of the file, in alphabetical order):

```python
# Scope-style action vocabulary used by scope_access read/edit/delete/stream
# (Section 12.3) and by system_permissions assignment_permission /
# user_permission (Section 12.4).
SCOPE_ACCESS_VALUES: frozenset[str] = frozenset({"all", "team", "own", "no"})

# v1.3 system-permissions key enumeration (Section 12.4). Two scope-style
# keys take SCOPE_ACCESS_VALUES; four flag-style keys take bool.
SYSTEM_PERMISSION_SCOPE_KEYS: frozenset[str] = frozenset({
    "assignment_permission",
    "user_permission",
})
SYSTEM_PERMISSION_FLAG_KEYS: frozenset[str] = frozenset({
    "export",
    "mass_update",
    "audit_log",
    "portal",
})
VALID_SYSTEM_PERMISSION_KEYS: frozenset[str] = (
    SYSTEM_PERMISSION_SCOPE_KEYS | SYSTEM_PERMISSION_FLAG_KEYS
)
```

**New `ScopeAccess` dataclass** (place immediately before
`RoleDefinition` so the per-entity structure precedes its parent
role definition):

```python
@dataclass
class ScopeAccess:
    """Per-entity access scope for a role (Section 12.3).

    All fields default to the most-restrictive value (denied) so
    that an entity entry with omitted actions defaults to "no
    access for that action". The whitelist-semantics rule —
    entities not listed are denied entirely — is enforced at the
    role level, not in this dataclass.

    :param create: Whether the role may create new records of this
        entity. ``yes`` and ``no`` only (the record does not exist
        at create time, so ``team`` / ``own`` have no meaning).
    :param read: Which records the role may view. One of ``all``,
        ``team``, ``own``, ``no``.
    :param edit: Same vocabulary as ``read``, applied to record
        modification.
    :param delete: Same vocabulary as ``read``, applied to record
        deletion.
    :param stream: Same vocabulary as ``read``, applied to the
        record's activity stream.
    """

    create: bool = False
    read: str = "no"
    edit: str = "no"
    delete: str = "no"
    stream: str = "no"
```

**New `SystemPermissions` dataclass** (place immediately after
`ScopeAccess`):

```python
@dataclass
class SystemPermissions:
    """System-level (non-entity) permissions for a role (Section 12.4).

    All fields default to the most-restrictive value (denied) per
    Section 12.4's "Omission defaults to deny" rule.

    :param assignment_permission: Whom the role may assign records
        to. One of ``all``, ``team``, ``own``, ``no``.
    :param user_permission: Which other users the role may view in
        the user directory. Same vocabulary as
        ``assignment_permission``.
    :param export: Whether the role may export records.
    :param mass_update: Whether the role may perform bulk updates.
    :param audit_log: Whether the role may view the platform audit
        log.
    :param portal: Whether the role may log in via the customer
        portal interface.
    """

    assignment_permission: str = "no"
    user_permission: str = "no"
    export: bool = False
    mass_update: bool = False
    audit_log: bool = False
    portal: bool = False
```

**Extend `RoleDefinition`** (currently in models.py after Prompt
A's commit). Add two structured fields alongside the existing
raw passthroughs:

```python
@dataclass
class RoleDefinition:
    # ... existing fields from Prompt A: name, description, persona ...
    scope_access: dict[str, ScopeAccess] = field(default_factory=dict)
    system_permissions: SystemPermissions | None = None
    # ... existing raw fields from Prompt A: scope_access_raw,
    #     system_permissions_raw ...
```

`scope_access` defaults to an empty dict (matching the schema's
"role with no `scope_access:` has no entity access" rule).
`system_permissions` defaults to `None` so the validator can
distinguish "operator omitted the block" from "operator wrote
the block with all defaults" — both are valid YAML, and the
deploy-side manager (Prompt D) consumes `None` as
"every-flag-denied" via `SystemPermissions()`. The raw fields
are preserved exactly as Prompt A established them.

**Extend `ProgramContext`** (currently `fields_by_entity` only).
Add five new fields:

```python
@dataclass(frozen=True)
class ProgramContext:
    fields_by_entity: dict[str, frozenset[str]]
    entity_names: frozenset[str] = frozenset()
    role_names: frozenset[str] = frozenset()
    team_names: frozenset[str] = frozenset()
    role_count_by_name: dict[str, int] = field(default_factory=dict)
    team_count_by_name: dict[str, int] = field(default_factory=dict)
```

(Note: `dataclass(frozen=True)` with a `dict` field needs
`field(default_factory=...)`. Verify the existing dataclass
mutability constraints — if the frozen decorator rejects
mutable defaults even via `field`, fall back to immutable
representations like `tuple[tuple[str, int], ...]` and a
helper property. The existing `fields_by_entity` dict on the
frozen class is the precedent — follow whatever pattern it
actually uses.)

Update `ProgramContext.from_programs` to populate all five new
fields. For uniqueness checking, both `role_count_by_name` and
`team_count_by_name` accumulate counts (so a name appearing in
N files maps to N), giving the validator clean cross-batch
duplicate detection.

### 3. `espo_impl/core/config_loader.py` — parser additions

Add imports for the new model classes (`ScopeAccess`,
`SystemPermissions`) and constants
(`SCOPE_ACCESS_VALUES`, `VALID_SYSTEM_PERMISSION_KEYS`,
`SYSTEM_PERMISSION_SCOPE_KEYS`, `SYSTEM_PERMISSION_FLAG_KEYS`)
to the existing `from espo_impl.core.models import (...)` block
in alphabetical order.

**New parser helpers.** Add two small helpers at the top of the
loader class for YAML 1.1 boolean coercion. These centralize the
normalization rules from schema §12.3 "YAML boolean coercion"
(line 2466–2471):

```python
def _coerce_yesno(self, value: Any, *, prefix: str, key: str) -> bool:
    """Normalize a YAML yes/no scalar to ``bool``.

    Accepts: ``True`` (bare ``yes``), ``False`` (bare ``no``),
    string ``"yes"`` (quoted), string ``"no"`` (quoted). All
    other values raise ``ValueError`` with a clear message.

    :param value: Raw value from YAML.
    :param prefix: Error-message prefix locating the source of
        the value (e.g. ``"roles[0] ('Mentor').scope_access.
        Engagement"``).
    :param key: The property name being normalized
        (e.g. ``"create"``).
    """
    if value is True or value == "yes":
        return True
    if value is False or value == "no":
        return False
    raise ValueError(
        f"{prefix}.{key}: must be 'yes' or 'no' (got {value!r})"
    )


def _coerce_scope(self, value: Any, *, prefix: str, key: str) -> str:
    """Normalize a YAML scope-vocabulary scalar to a canonical string.

    Accepts: strings ``"all"``, ``"team"``, ``"own"``, ``"no"``;
    the boolean ``False`` (from bare ``no``) normalizes to
    ``"no"``. Bare ``yes`` / ``True`` / quoted ``"yes"`` are
    rejected — ``yes`` is not in the scope vocabulary.

    :param value: Raw value from YAML.
    :param prefix: Error-message prefix.
    :param key: The property name being normalized.
    """
    if value is False:
        return "no"
    if isinstance(value, str) and value in SCOPE_ACCESS_VALUES:
        return value
    raise ValueError(
        f"{prefix}.{key}: must be one of 'all', 'team', 'own', "
        f"'no' (got {value!r})"
    )
```

**New `_parse_scope_access` method.** Converts a raw
`scope_access:` dict to `dict[str, ScopeAccess]`:

```python
def _parse_scope_access(
    self, raw: dict | None, *, role_name: str,
) -> dict[str, ScopeAccess]:
    """Parse a role's ``scope_access:`` block into typed values.

    :param raw: Raw scope_access dict (or None for absent block).
    :param role_name: Role name for error-message attribution.
    :returns: Mapping of entity natural name to ScopeAccess.
    :raises ValueError: On malformed structure or vocabulary
        violation.
    """
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(
            f"roles ('{role_name}'): 'scope_access' must be a mapping"
        )

    result: dict[str, ScopeAccess] = {}
    for entity_name, entity_block in raw.items():
        if not isinstance(entity_name, str) or not entity_name.strip():
            raise ValueError(
                f"roles ('{role_name}').scope_access: entity-name key "
                f"must be a non-empty string"
            )
        prefix = f"roles ('{role_name}').scope_access.{entity_name}"
        if not isinstance(entity_block, dict):
            raise ValueError(
                f"{prefix}: must be a mapping of per-action settings"
            )

        # Detect unknown action keys (anything outside the v1.3 set)
        unknown_keys = (
            set(entity_block.keys())
            - {"create", "read", "edit", "delete", "stream"}
        )
        if unknown_keys:
            raise ValueError(
                f"{prefix}: unknown action(s) "
                f"{sorted(unknown_keys)!r}; valid actions are "
                f"create, read, edit, delete, stream"
            )

        scope = ScopeAccess()
        if "create" in entity_block:
            scope.create = self._coerce_yesno(
                entity_block["create"], prefix=prefix, key="create",
            )
        for action_key in ("read", "edit", "delete", "stream"):
            if action_key in entity_block:
                setattr(
                    scope, action_key,
                    self._coerce_scope(
                        entity_block[action_key],
                        prefix=prefix, key=action_key,
                    ),
                )
        result[entity_name] = scope

    return result
```

**New `_parse_system_permissions` method.** Converts a raw
`system_permissions:` dict to a `SystemPermissions` instance:

```python
def _parse_system_permissions(
    self, raw: dict | None, *, role_name: str,
) -> SystemPermissions | None:
    """Parse a role's ``system_permissions:`` block into typed values.

    Returns ``None`` if the block is absent in YAML. Returns a
    fully-populated ``SystemPermissions`` (with per-key defaults
    for any omitted keys) if the block is present, even if
    empty.

    :param raw: Raw system_permissions dict (or None for absent
        block).
    :param role_name: Role name for error-message attribution.
    :returns: SystemPermissions instance or None.
    :raises ValueError: On unknown key or vocabulary violation.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(
            f"roles ('{role_name}'): 'system_permissions' must be a "
            f"mapping"
        )

    prefix = f"roles ('{role_name}').system_permissions"
    unknown_keys = set(raw.keys()) - VALID_SYSTEM_PERMISSION_KEYS
    if unknown_keys:
        raise ValueError(
            f"{prefix}: unknown key(s) {sorted(unknown_keys)!r}; "
            f"valid keys are {sorted(VALID_SYSTEM_PERMISSION_KEYS)!r}"
        )

    perms = SystemPermissions()
    for key in SYSTEM_PERMISSION_SCOPE_KEYS:
        if key in raw:
            setattr(perms, key, self._coerce_scope(
                raw[key], prefix=prefix, key=key,
            ))
    for key in SYSTEM_PERMISSION_FLAG_KEYS:
        if key in raw:
            setattr(perms, key, self._coerce_yesno(
                raw[key], prefix=prefix, key=key,
            ))
    return perms
```

**Wire into `_parse_roles`** (added in Prompt A). After the
existing block that constructs `RoleDefinition`, populate the
new structured fields:

```python
roles.append(RoleDefinition(
    name=name,
    description=description,
    persona=persona,
    scope_access=self._parse_scope_access(
        scope_access_raw, role_name=name,
    ),
    system_permissions=self._parse_system_permissions(
        system_permissions_raw, role_name=name,
    ),
    scope_access_raw=scope_access_raw,
    system_permissions_raw=system_permissions_raw,
))
```

The raw fields stay populated exactly as Prompt A established —
they remain the source of truth for round-tripping and for
audit-side reverse-engineering in Prompt H.

### 4. `espo_impl/core/config_loader.py` — validator additions

**New `_validate_roles` method.** Place in the existing
`_validate_*` cluster (after `_validate_filtered_tab_scopes`).
Performs four checks:

1. **Within-file role-name uniqueness.** Walk `program.roles`
   building a `seen_names: set[str]`; emit an error on
   re-declaration within the file.
2. **Cross-batch role-name uniqueness via ProgramContext.** For
   each role declared in this file, check
   `self._active_context.role_count_by_name.get(role.name, 0)`.
   If > 1, emit an error: "Role 'X' is declared in N files in
   the batch; role names must be unique across the batch."
3. **Entity-name resolution for `scope_access` keys.** For each
   role's `scope_access` mapping, every key must resolve to
   either an entity in
   `self._active_context.entity_names` OR a native entity in
   `NATIVE_ENTITY_BASE_TYPE`. Emit one error per unresolved
   entity name, naming the role and the entity:
   "Role 'X'.scope_access['Y']: entity 'Y' is not declared in
   this batch and is not a recognized native entity."
4. **(Vocabulary is already enforced at parse time** by the
   parser helpers; no duplicate validation here.)

The validator returns `list[str]`; the within-file pass and
cross-batch pass append to the same list.

**New `_validate_teams` method.** Same shape, simpler scope:
within-file team-name uniqueness, cross-batch team-name
uniqueness via `_active_context.team_count_by_name`. No
vocabulary or entity-resolution work.

**Wire into `validate_program`.** Insert calls in the existing
sequence at line 292–307, after the entity loop and after the
existing cross-block validators, before the relationship loop:

```python
for entity in program.entities:
    errors.extend(self._validate_entity(entity))

errors.extend(self._validate_alert_template_refs(program))
errors.extend(self._validate_workflow_template_refs(program))
errors.extend(self._validate_filtered_tab_scopes(program))
errors.extend(self._validate_roles(program))    # NEW
errors.extend(self._validate_teams(program))    # NEW

for rel in program.relationships:
    errors.extend(self._validate_relationship(rel))
```

### 5. Tests — `tests/test_config_loader.py`

Add new test cases. Follow the existing dedent/inline-YAML
fixture style. Coverage areas:

**Parsing — `scope_access` (structured fields populated):**

- A role with `scope_access:` containing two entities (one native
  like Contact, one custom like Engagement, both declared in the
  same file's `entities:` block) parses cleanly; the resulting
  `RoleDefinition.scope_access` is a dict with two `ScopeAccess`
  instances carrying the expected typed values; `scope_access_raw`
  is also populated with the original dict (regression coverage
  for Prompt A's behavior).
- A role with `scope_access:` omitting some actions (e.g., only
  `read` and `edit` specified, no `create`/`delete`/`stream`)
  populates the omitted actions with their dataclass defaults
  (denied).
- A role with an empty `scope_access:` block (`scope_access: {}`)
  parses to an empty dict.
- A role with no `scope_access:` block at all parses to an empty
  dict.

**Parsing — `scope_access` (YAML 1.1 boolean coercion):**

- Bare `create: yes` and bare `create: no` produce
  `ScopeAccess.create == True` / `False`.
- Quoted `create: "yes"` / `create: "no"` produce the same
  values (operator may write either form).
- Bare `read: no` (which YAML coerces to `False`) normalizes to
  `ScopeAccess.read == "no"`.
- Quoted `read: "no"` normalizes to `ScopeAccess.read == "no"`.
- Both forms yield identical parsed results — parametrized test
  enumerating bare-vs-quoted equivalence across all five actions.

**Parsing — `scope_access` (rejection):**

- `create: maybe` rejected (not in yes/no vocabulary).
- `read: yes` rejected (yes is not in the scope vocabulary).
- `read: somewhere` rejected (not in scope vocabulary).
- Unknown action key (e.g., `archive: yes`) rejected with a
  message listing the valid actions.
- `scope_access:` value that is not a mapping (e.g., a list)
  rejected.
- Per-entity block value that is not a mapping rejected.

**Parsing — `system_permissions` (structured field populated):**

- A role with a full `system_permissions:` block (all six keys
  set) parses to a `SystemPermissions` carrying the expected
  values.
- A role with a partial `system_permissions:` block (e.g., only
  `export: yes`) populates the named key and leaves omitted keys
  at their dataclass defaults (denied).
- A role with no `system_permissions:` block parses
  `system_permissions` to `None`.
- A role with `system_permissions: {}` parses to a
  fully-populated `SystemPermissions` with all defaults.

**Parsing — `system_permissions` (rejection):**

- Unknown system-permission key (e.g., `foobar: yes`) rejected
  with a message listing the valid keys.
- Scope-style key with non-scope value (e.g.,
  `assignment_permission: yes`) rejected.
- Flag-style key with scope-style value (e.g., `export: team`)
  rejected.

**Validation — `_validate_roles`:**

- Within-file uniqueness: a file with two roles both named
  "Mentor" produces a uniqueness error.
- Cross-batch uniqueness: two files each declaring a "Mentor"
  role, validated via `ProgramContext.from_programs([file1, file2])`,
  produce a duplicate error on each file's validation pass.
- Entity resolution — native: `scope_access:` keyed on
  `Contact` validates cleanly (native entity in registry).
- Entity resolution — custom in batch: `scope_access:` keyed on
  `Engagement` validates cleanly when `Engagement` is declared
  under another file's `entities:` block in the same
  `ProgramContext`.
- Entity resolution — unknown: `scope_access:` keyed on
  `NonexistentEntity` produces a clear error message.

**Validation — `_validate_teams`:**

- Within-file team-name uniqueness check.
- Cross-batch team-name uniqueness check via `ProgramContext`.

**Regression — Prompt A behaviors preserved:**

- All Prompt A tests pass unchanged (verified by running the
  full test suite); raw passthroughs remain populated alongside
  the new structured fields.

## Acceptance Criteria

1. `PRDs/product/app-yaml-schema.md` §12.3 example block uses
   natural-form entity names (no `c-` prefix); the line-2455
   parenthetical is rewritten per §1 above.
2. `espo_impl/core/models.py` contains `ScopeAccess` and
   `SystemPermissions` dataclasses with the field shapes
   specified in §2 above.
3. `RoleDefinition` carries structured `scope_access` and
   `system_permissions` fields alongside the raw passthroughs
   established by Prompt A; both pairs populate correctly from
   the loader.
4. `ProgramContext` carries `entity_names`, `role_names`,
   `team_names`, `role_count_by_name`, `team_count_by_name`
   fields; `from_programs` populates all five.
5. `_parse_scope_access` and `_parse_system_permissions` accept
   all valid YAML 1.1 boolean and quoted-string forms per the
   schema §12.3 normalization rule; both reject any value
   outside the per-key vocabulary with a clear error message
   identifying the role, entity (for scope_access), action, and
   the rejected value.
6. `validate_program()` calls `_validate_roles` and
   `_validate_teams` after the existing filtered-tab-scope
   check; both new validators contribute their errors to the
   returned list.
7. Entity-name resolution for `scope_access:` keys succeeds for
   natural-form names of (a) custom entities declared anywhere
   in the active `ProgramContext` and (b) native entities in
   `NATIVE_ENTITY_BASE_TYPE`. Unresolved names produce a clear
   per-role / per-entity error.
8. Within-file and cross-batch role-name and team-name
   uniqueness violations produce clear errors.
9. All existing tests continue to pass with no regression.
10. New tests cover every case enumerated in §5 above.
11. `uv run ruff check espo_impl/ tests/` passes clean.
12. `uv run pytest tests/ -v` passes.
13. Commit and push to `main` with a clear message referencing
    this prompt, the planning doc, and the spec sections
    implemented.

## Out of Scope

- All deploy-side work (`team_manager.py`, `role_manager.py`,
  pipeline ordering) — Prompts C / D / E
- `role:` leaf clause variant in `condition_expression.py` —
  Prompt F
- Role-aware `requiredWhen` / `visibleWhen` / `forRoles:`
  wiring — Prompt G
- Audit-side discovery and `security.yaml` emission — Prompt H
- `_client_v4` migration for role/team/filtered-tab tables —
  Prompt H
- Filtered-tab audit capture — Prompt I
- Audit dialog UI work — Prompt J
- `feat-audit.md` and user-guide documentation — Prompt K
- Server-state-aware entity resolution for `scope_access:` keys
  (entities on target but not in batch) — Prompt E
- Origin-file annotation in cross-batch uniqueness error
  messages — follow-on polish if needed

## Reporting Back

When finished, report:

- Modified file paths and line counts
- New tests added (count and brief coverage summary)
- Total test count before → after, ruff status
- Commit hash and message
- Any deviations from this prompt's specification (and why)
- Any open questions or follow-ups for Prompt C

The expected next step after Prompt B is green is **Prompt C**:
`team_manager.py` deploy-side, with the `api_client.py` extensions
needed to read and write Team records on the target instance.
Teams have no dependencies on roles or entities, so Prompt C lands
cleanly before the more substantive `role_manager.py` work in
Prompt D.

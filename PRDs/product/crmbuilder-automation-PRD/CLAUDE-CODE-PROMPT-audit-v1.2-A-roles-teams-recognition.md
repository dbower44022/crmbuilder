# CLAUDE-CODE-PROMPT — audit-v1.2-A — Roles and Teams Recognition

**Repo:** `crmbuilder`
**Series:** `audit-v1.2` (eleven-prompt sequence implementing the v1.2
expansion of the Audit feature per
`PRDs/product/crmbuilder-automation-PRD/audit-v1.2-planning.md` v1.3)
**Last Updated:** 05-23-26 16:30
**Spec:** `PRDs/product/app-yaml-schema.md` Sections 12.1 (Roles) and
12.2 (Teams) — authoritative for the YAML shape this prompt
implements.
**Planning:** `PRDs/product/crmbuilder-automation-PRD/audit-v1.2-planning.md`
§5 Prompt A.
**Governance:** SES-060 / DEC-178..182 are the audit-v1.2 design
decisions; **DEC-178** (persona is documentation metadata only,
no loader validation) and **DEC-182** (security YAMLs live in a
`security/` subdirectory of the program directory) are the two
that bite at Prompt A. DEC-179..181 guide later prompts in the
series.

## Position in the Series

This is **Prompt A — the foundation** for the audit-v1.2 expansion.
It establishes loader recognition for the two new top-level YAML keys
(`roles:` and `teams:`) and the dataclasses that subsequent prompts
populate with structured parsing and deploy logic.

The seven later prompts that depend on this work:

- **Prompt B** adds structured parsing for `scope_access:` and
  `system_permissions:` (Section 12.3 / 12.4)
- **Prompts C / D** add `team_manager.py` and `role_manager.py`
  deploy-side
- **Prompt E** adds the security pipeline step and deploy ordering
- **Prompt F** adds the `role:` leaf clause in `condition_expression.py`
- **Prompt G** wires role-aware field/panel/layout visibility
  (Section 12.5)
- **Prompt H** adds audit-side discovery and `security.yaml` emission

Prompts I (filtered-tab audit), J (entity picker UI), and K
(documentation) are sequenced after the core schema/deploy work and
do not depend on this prompt directly.

**This prompt does NOT implement:**

- Structured parsing of `scope_access:` or `system_permissions:`
  (Prompt B)
- Any deploy-side execution (Prompts C–G)
- Any audit-side discovery (Prompt H)
- The `role:` leaf clause variant in `condition_expression.py`
  (Prompt F)
- Cross-batch uniqueness validation of role/team names (Prompt B
  with `ProgramContext`)
- Any UI changes (Prompt J)

This prompt builds only the loader plumbing and dataclass shells.

## Scope

In scope:

1. `espo_impl/core/models.py` — add `RoleDefinition` and
   `TeamDefinition` dataclasses with minimal typed fields (`name`,
   `description`, `persona`) plus raw-passthrough fields
   (`scope_access_raw`, `system_permissions_raw`) following the
   established `EntityDefinition.*_raw` pattern.
2. `espo_impl/core/models.py` — extend `ProgramFile` with `roles`
   and `teams` collections (both default-empty lists).
3. `espo_impl/core/config_loader.py` — extend `load_program` to
   recognize `roles:` and `teams:` as valid top-level keys; parse
   each entry into the new dataclasses; hard-reject malformed
   structures (missing `name:`, wrong types) at parse time via
   `ValueError`, matching the existing `_parse_field` /
   `_parse_relationship` pattern.
4. Tests covering the above.

Out of scope (deferred to later prompts in the series; see the
"Position in the Series" list above for which prompt covers each):

- Structured parsing or validation of `scope_access:` /
  `system_permissions:` internals — Prompt B
- `validate_program()` changes for role/team rules — Prompt B
- Cross-batch role/team name-uniqueness enforcement via
  `ProgramContext` — Prompt B
- Any deploy-side managers, API client methods, or pipeline
  ordering — Prompts C–G
- Schema-doc edits — the spec in `app-yaml-schema.md` §§12.1–12.2
  is already authoritative; no changes needed for this prompt

## Working Method

Standard CRM Builder Python conventions:

```bash
# After changes:
uv run ruff check espo_impl/ tests/
uv run pytest tests/ -v
```

All new code: no GUI dependencies, fully testable pure logic. No
edits to any file beyond what is enumerated below — this is a
surgical addition mirroring the precedent established by Prompt A
of the v1.1 series (archived at
`PRDs/_archive/yaml-schema-prompts/CLAUDE-CODE-PROMPT-yaml-v1.1-A-condition-expressions-and-loader.md`).

**Note on the program-directory scan.** The planning doc §5 Prompt
A describes the scan as needing to be "extended to also scan
`<program_dir>/security/*.yaml` in addition to root `*.yaml`." On
inspection, the existing scanner in
`automation/ui/deployment/deployment_logic.py:354–386` uses
`programs_dir.rglob("*.yaml")` and is already recursive — files
under `programs/security/` are picked up by the existing walk with
no code change required. This prompt therefore does not modify the
scanner. It adds a test (see Files to Modify §3 below) that loads
the same role/team content from both root and `security/`
placements and asserts identical parsed results, locking in the
convention.

## Files to Modify

### 1. `espo_impl/core/models.py`

Add two new dataclasses, placed immediately after the
`RelationshipDefinition` block (around line 528, before the
`TooltipStatus` enum) to keep program-wide definitions grouped:

```python
@dataclass
class RoleDefinition:
    """A role declared in the top-level ``roles:`` list.

    Roles declare entity-level scope access (Section 12.3) and
    system-level permissions (Section 12.4). This dataclass holds
    only the minimal typed fields; ``scope_access:`` and
    ``system_permissions:`` are stashed as raw values for
    structured parsing in a later prompt.

    :param name: Role identity. Unique across the program batch
        (uniqueness enforced by a later prompt via
        ``ProgramContext``).
    :param description: Business rationale for the role. Optional
        block-scalar prose; no schema interpretation.
    :param persona: Master PRD persona identifier (e.g.,
        ``MST-PER-005``). Documentation metadata only — the loader
        does not cross-check the identifier against any source
        (per DEC-178 / planning doc §9.1).
    :param scope_access_raw: Raw per-entity access scope block.
        Parsed into a typed structure in a later prompt.
    :param system_permissions_raw: Raw system-level permissions
        block. Parsed into a typed structure in a later prompt.
    """

    name: str
    description: str | None = None
    persona: str | None = None
    scope_access_raw: dict | None = None
    system_permissions_raw: dict | None = None


@dataclass
class TeamDefinition:
    """A team declared in the top-level ``teams:`` list.

    Teams group users for the purpose of team-level access scope
    on records (the ``team`` value in ``scope_access:``).
    Team-to-user assignment is runtime data managed in the target
    CRM admin UI, not in YAML.

    :param name: Team identity. Unique across the program batch
        (uniqueness enforced by a later prompt via
        ``ProgramContext``).
    :param description: Business rationale for the team. Optional
        block-scalar prose; no schema interpretation.
    """

    name: str
    description: str | None = None
```

Then extend `ProgramFile` (around line 588) with two new
collections:

```python
roles: list[RoleDefinition] = field(default_factory=list)
teams: list[TeamDefinition] = field(default_factory=list)
```

Place these after the existing `relationships` field and before
`deprecation_warnings`, keeping content collections grouped.

**Imports.** The new dataclasses sit alongside the existing
`@dataclass` definitions in this module; they use `field` from
`dataclasses` which is already imported.

### 2. `espo_impl/core/config_loader.py`

Add imports for the two new model classes at the top of the file,
inserted in alphabetical order in the existing
`from espo_impl.core.models import (...)` block:

```python
from espo_impl.core.models import (
    # ... existing imports ...
    RoleDefinition,
    # ... existing imports ...
    TeamDefinition,
    # ... existing imports ...
)
```

Add two new parser methods on the loader class. Place them
together at the end of the `_parse_*` cluster (after
`_parse_filtered_tabs`, which is the most recent precedent for a
top-level / entity-level raw-passthrough parser):

```python
def _parse_roles(self, raw_roles: Any) -> list[RoleDefinition]:
    """Parse the top-level ``roles:`` list.

    Hard-rejects malformed entries (non-list at root, non-dict
    entry, missing or non-string ``name:``) by raising
    ``ValueError`` matching the existing parser conventions.
    Stashes ``scope_access`` and ``system_permissions`` as raw
    dicts for a later prompt to parse structurally.

    :param raw_roles: Raw value from ``raw.get("roles")``.
        ``None`` and missing key return an empty list (the YAML
        omits the block); a non-list value raises.
    :returns: Parsed role definitions (possibly empty).
    :raises ValueError: On malformed structure.
    """
    if raw_roles is None:
        return []
    if not isinstance(raw_roles, list):
        raise ValueError(
            "Top-level 'roles' must be a list of role definitions"
        )

    roles: list[RoleDefinition] = []
    for idx, role_data in enumerate(raw_roles):
        if not isinstance(role_data, dict):
            raise ValueError(
                f"roles[{idx}] must be a mapping, got "
                f"{type(role_data).__name__}"
            )
        name = role_data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                f"roles[{idx}] is missing a non-empty string 'name'"
            )

        description = role_data.get("description")
        if description is not None and not isinstance(description, str):
            raise ValueError(
                f"roles[{idx}] ('{name}'): 'description' must be a "
                f"string when present"
            )

        persona = role_data.get("persona")
        if persona is not None and not isinstance(persona, str):
            raise ValueError(
                f"roles[{idx}] ('{name}'): 'persona' must be a "
                f"string when present"
            )

        scope_access_raw = role_data.get("scope_access")
        if scope_access_raw is not None and not isinstance(
            scope_access_raw, dict
        ):
            raise ValueError(
                f"roles[{idx}] ('{name}'): 'scope_access' must be a "
                f"mapping when present"
            )

        system_permissions_raw = role_data.get("system_permissions")
        if system_permissions_raw is not None and not isinstance(
            system_permissions_raw, dict
        ):
            raise ValueError(
                f"roles[{idx}] ('{name}'): 'system_permissions' must "
                f"be a mapping when present"
            )

        roles.append(RoleDefinition(
            name=name,
            description=description,
            persona=persona,
            scope_access_raw=scope_access_raw,
            system_permissions_raw=system_permissions_raw,
        ))

    return roles


def _parse_teams(self, raw_teams: Any) -> list[TeamDefinition]:
    """Parse the top-level ``teams:`` list.

    Hard-rejects malformed entries by raising ``ValueError``.

    :param raw_teams: Raw value from ``raw.get("teams")``.
    :returns: Parsed team definitions (possibly empty).
    :raises ValueError: On malformed structure.
    """
    if raw_teams is None:
        return []
    if not isinstance(raw_teams, list):
        raise ValueError(
            "Top-level 'teams' must be a list of team definitions"
        )

    teams: list[TeamDefinition] = []
    for idx, team_data in enumerate(raw_teams):
        if not isinstance(team_data, dict):
            raise ValueError(
                f"teams[{idx}] must be a mapping, got "
                f"{type(team_data).__name__}"
            )
        name = team_data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                f"teams[{idx}] is missing a non-empty string 'name'"
            )

        description = team_data.get("description")
        if description is not None and not isinstance(description, str):
            raise ValueError(
                f"teams[{idx}] ('{name}'): 'description' must be a "
                f"string when present"
            )

        teams.append(TeamDefinition(
            name=name,
            description=description,
        ))

    return teams
```

Wire the parsers into `load_program`. After the existing
relationships parsing block (around line 243, immediately before
the `return ProgramFile(...)` call):

```python
# Parse top-level roles and teams (Section 12.1, 12.2)
roles = self._parse_roles(raw.get("roles"))
teams = self._parse_teams(raw.get("teams"))
```

Pass them to the `ProgramFile` constructor:

```python
return ProgramFile(
    version=str(raw.get("version", "")),
    description=str(raw.get("description", "")),
    content_version=str(raw.get("content_version", "1.0.0")),
    entities=entities,
    source_path=path,
    relationships=relationships,
    roles=roles,
    teams=teams,
    deprecation_warnings=deprecation_warnings,
)
```

### 3. Tests — `tests/test_config_loader.py`

Add new test fixtures and cases. Follow the existing dedent/yaml
fixture style in the file. Cover:

**Acceptance cases:**

- A program file with a valid `roles:` block (two roles, with and
  without `description`, with and without `persona`) loads cleanly;
  `ProgramFile.roles` is populated with `RoleDefinition` instances
  carrying the expected field values; `scope_access_raw` and
  `system_permissions_raw` are `None` when absent in YAML.
- A program file with a valid `teams:` block (two teams, with and
  without `description`) loads cleanly; `ProgramFile.teams` is
  populated as expected.
- A program file with both `roles:` and `teams:` plus an
  `entities:` block loads cleanly with all three populated; the
  presence of role/team blocks does not perturb entity parsing.
- A program file with neither `roles:` nor `teams:` continues to
  load cleanly with empty `roles` and `teams` lists on
  `ProgramFile` (regression coverage — existing YAML behavior is
  preserved).
- A role with `scope_access:` and `system_permissions:` mapping
  blocks (any internal shape — the values are stashed raw and not
  inspected at this stage) loads cleanly with both raw fields
  populated as the original dicts.
- A YAML file located at `programs/security/security.yaml`
  containing `roles:` and `teams:` blocks loads via
  `loader.load_program(path)` and produces a `ProgramFile`
  identical (modulo `source_path`) to the same content placed at
  `programs/security.yaml`. **This locks in the subdirectory
  convention per DEC-182 / planning doc v1.2 change log.**

**Rejection cases (each asserts a clear, role/team-specific
`ValueError`):**

- Top-level `roles:` set to a non-list value (e.g., a mapping)
- A role entry that is not a mapping (e.g., a bare string)
- A role missing its `name:` key
- A role with `name:` set to an empty string
- A role with `name:` set to a non-string type (e.g., integer)
- A role with `description:` set to a non-string type
- A role with `persona:` set to a non-string type
- A role with `scope_access:` set to a non-mapping value
- A role with `system_permissions:` set to a non-mapping value
- Top-level `teams:` set to a non-list value
- A team entry that is not a mapping
- A team missing its `name:` key
- A team with `name:` set to an empty string
- A team with `description:` set to a non-string type

**Test data convention.** Use small inline YAML strings via
`textwrap.dedent` mirroring the existing test file's style. Do not
add fixture files under `tests/fixtures/` for this prompt — the
existing test file inlines its YAML, and following that convention
keeps the diff readable.

## Acceptance Criteria

1. `espo_impl/core/models.py` contains `RoleDefinition` and
   `TeamDefinition` dataclasses with the exact field shapes
   specified in §1 above.
2. `espo_impl/core/models.py` `ProgramFile` carries
   `roles: list[RoleDefinition]` and `teams: list[TeamDefinition]`
   collections, both defaulting to empty lists.
3. `espo_impl/core/config_loader.py` `load_program` accepts
   programs containing top-level `roles:` and/or `teams:` blocks
   without error, populating the new `ProgramFile` collections.
4. Malformed `roles:` / `teams:` structures (missing `name:`,
   wrong types) produce a `ValueError` at parse time with a clear
   message identifying which role/team entry and which property
   is at fault.
5. A `security.yaml` placed under
   `programs/security/<filename>.yaml` is picked up by the
   existing recursive directory scan and loads via the same
   parser, producing identical content to a root-level placement.
   Locked in by a parametrized test.
6. All existing tests continue to pass with no regressions.
7. New tests cover every case enumerated in §3 above.
8. `uv run ruff check espo_impl/ tests/` passes clean.
9. `uv run pytest tests/ -v` passes.
10. Commit and push to `main` with a clear message referencing
    this prompt, the planning doc, and the spec sections
    implemented.

## Out of Scope

- `scope_access` / `system_permissions` value validation
  (vocabulary checks against `all`/`team`/`own`/`no` etc.) —
  Prompt B
- Entity-name resolution for `scope_access` keys against
  `ProgramContext` — Prompt B
- Cross-batch role/team name-uniqueness enforcement — Prompt B
- Role/team manager modules, API client methods — Prompts C / D
- Pipeline ordering for the security step — Prompt E
- `role:` leaf clause variant in `condition_expression.py` —
  Prompt F
- Role-aware `requiredWhen` / `visibleWhen` / `forRoles:` wiring
  — Prompt G
- Audit-side discovery, dataclasses, or `security.yaml` emission
  — Prompt H
- `_client_v4` migration adding role/team/filtered-tab tables to
  the client schema — Prompt H (also covers the filtered-tab
  table needed by Prompt I)
- Filtered-tab audit capture — Prompt I
- Audit-dialog UI work (entity picker, security checkbox,
  overwrite-confirmation dialog) — Prompt J
- `feat-audit.md` / user-guide documentation — Prompt K

## Reporting Back

When finished, report:

- Modified file paths and line counts
- New tests added (count and brief coverage summary)
- Total test count before → after, ruff status
- Commit hash and message
- Any deviations from this prompt's specification (and why)
- Any open questions or follow-ups for Prompt B

The expected next step after Prompt A is green is **Prompt B**:
structured `scope_access:` and `system_permissions:` parsing per
Section 12.3 / 12.4, building on the raw-passthrough seams this
prompt establishes.

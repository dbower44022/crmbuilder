# CLAUDE-CODE-PROMPT — audit-v1.2-C — Team Manager (Deploy-Side)

**Repo:** `crmbuilder`
**Series:** `audit-v1.2` (eleven-prompt sequence implementing the v1.2
expansion of the Audit feature per
`PRDs/product/crmbuilder-automation-PRD/audit-v1.2-planning.md` v1.3)
**Last Updated:** 05-24-26 02:30
**Spec:** `PRDs/product/app-yaml-schema.md` Section 12.2 (Teams) —
authoritative for the YAML shape this prompt's deploy-side consumes.
**Planning:** `PRDs/product/crmbuilder-automation-PRD/audit-v1.2-planning.md`
§5 Prompt C.
**Depends on:** Prompt A (commit `84b55c2` / local `4c7f06f`) for the
`TeamDefinition` dataclass and `program.teams` collection. Prompt B
(commit `d1bccac`) is not a hard dependency — the team-side model
work was already complete in Prompt A — but Prompt B should be
landed first for sequencing.
**Governance:** No new decisions in this prompt. Existing
audit-v1.2 governance (SES-060 / DEC-178..182) covers the design
authority.

## Position in the Series

This is **Prompt C — first of the deploy-side managers.** Teams are
the simpler of the two security-side managers (no dependencies, no
scope_access translation, no cross-batch entity resolution). Prompt
C ships the team half so Prompt D's role manager can land as a
self-contained unit without bundling team work.

After this prompt:

- **Prompt D** adds `role_manager.py` with the substantive
  scope_access translation work
- **Prompt E** adds the security pipeline step in `run_worker.py`,
  ordering team deploy before role deploy
- **Prompts F–H** complete the role-aware-visibility and audit-side
  work
- **Prompts I–K** complete filtered-tab audit, UI, and
  documentation

**This prompt does NOT implement:**

- Pipeline integration — the team manager is built but not yet
  invoked from `run_worker.py._run_full()`. That's Prompt E.
- Role manager — Prompt D.
- Team deletion. Per planning doc §5 Prompt C ("Team deletion is
  out of scope per the existing managers' conservative-deletion
  convention; document this"), teams declared on the server but
  not in YAML are left alone. Deletion is not a feature of this
  workstream. The team manager processes only the additive and
  modifying paths.
- Team rename. EspoCRM Team records are identified server-side by
  an opaque ID and matched from YAML by `name`. A rename in YAML
  is indistinguishable from "delete the old team, add a new team"
  to the CHECK→ACT pattern; since deletion is out of scope, a
  rename produces a new team and leaves the old one dangling. The
  manager documents this in its module docstring; operators are
  responsible for cleaning up renamed teams via the EspoCRM admin
  UI.
- User-to-team membership. Per Schema §12.2, "Team-to-user
  assignment is runtime data managed in the target CRM admin UI,
  not in YAML." The manager only handles Team records themselves.
- Pagination beyond `maxSize=200`. Single-bulk-fetch is sufficient
  for the dogfood and CBM use cases; documented as a future
  scaling concern.

## Scope

In scope:

1. `espo_impl/core/models.py` — add `TeamStatus` enum and
   `TeamResult` dataclass following the canonical 4-value Status
   precedent (CREATED / UPDATED / SKIPPED / ERROR; no DRIFT or
   NOT_SUPPORTED needed for teams).
2. `espo_impl/core/api_client.py` — add `get_teams()`,
   `create_team()`, and `update_team()` methods. `create_team()`
   and `update_team()` are thin wrappers around the existing
   `create_record()` / `patch_record()` generic methods with
   Team-specific payload construction; `get_teams()` performs a
   bulk-list GET against `/Team?maxSize=200`.
3. `espo_impl/core/team_manager.py` — new module implementing the
   `TeamManager` class with CHECK→ACT orchestration mirroring
   `tooltip_manager.py`. The `process_teams(teams, dry_run=False)`
   method takes the list of `TeamDefinition` from
   `program.teams` and returns a list of `TeamResult` records.
4. `tests/test_team_manager.py` — new test module mirroring
   `tests/test_tooltip_manager.py` patterns (MagicMock-based
   client mocking, no live HTTP).

Out of scope:

- Pipeline integration in `run_worker.py` — Prompt E
- Role-side anything (`role_manager.py`, `ScopeAccess` /
  `SystemPermissions` translation, role-aware visibility) —
  Prompts D / F / G
- Audit-side discovery of teams (`audit_manager._discover_teams`)
  — Prompt H
- Team deletion, team rename, user-team membership — see
  "Position in the Series" above
- Pagination beyond `maxSize=200` — documented as a future
  scaling concern

## Working Method

Standard CRM Builder Python conventions:

```bash
# After changes:
uv run ruff check espo_impl/ tests/
uv run pytest tests/ -v
```

All new code: no GUI dependencies; testable via MagicMock client
following the `test_tooltip_manager.py` pattern.

**Precedent.** `espo_impl/core/tooltip_manager.py` is the closest
analog in shape: single-record-type manager, simple CHECK→ACT
loop, 401 raises a manager-specific exception, dry-run path
records intended action without writing. Mirror its structure
where reasonable. The team manager is slightly simpler because
team records are top-level (no nested-under-entity iteration).

## Files to Modify

### 1. `espo_impl/core/models.py` — TeamStatus + TeamResult

Place immediately after the existing `TeamDefinition` block (added
in Prompt A) so team-side dataclasses are grouped:

```python
class TeamStatus(Enum):
    """Outcome status for a team operation.

    Values mirror the canonical Status enum precedent. Team
    operations do not need ``DRIFT`` (there is only one mutable
    field — ``description`` — so a CHECK that detects difference
    is always reconcilable via PATCH) or ``NOT_SUPPORTED`` (Team
    is a native EspoCRM record type with full REST support).
    """

    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TeamResult:
    """Result of processing a single team.

    :param name: Team name from YAML (also the match key).
    :param status: Outcome status.
    :param team_id: Server-assigned record ID. Populated after
        a successful CREATE; available from CHECK on
        SKIPPED / UPDATED for already-existing teams.
    :param error: Error message if status is ERROR.
    """

    name: str
    status: TeamStatus
    team_id: str | None = None
    error: str | None = None
```

`Enum` is already imported at the top of the module; verify
imports are alphabetically ordered if any changes are made.

### 2. `espo_impl/core/api_client.py` — new methods

Add three methods. Place them in the existing "record CRUD"
cluster (after `patch_record` at line 590, before
`test_connection` at line 594):

```python
def get_teams(
    self,
) -> tuple[int, dict[str, Any] | None]:
    """List all Team records on the target instance.

    Bulk-fetches up to 200 teams in a single GET. This is
    sufficient for the dogfood and pilot-client use cases; an
    instance with more than 200 teams would require pagination,
    which is not implemented in this workstream.

    :returns: Tuple of (status_code, response_json or None).
        The standard EspoCRM list response shape
        ``{"total": N, "list": [...]}`` is returned on success.
    """
    url = f"{self.profile.api_url}/Team?maxSize=200"
    return self._request("GET", url)


def create_team(
    self, name: str, description: str | None = None,
) -> tuple[int, dict[str, Any] | None]:
    """Create a new Team record.

    :param name: Team name (operator-chosen identifier).
    :param description: Optional description text.
    :returns: Tuple of (status_code, created record or None).
    """
    payload: dict[str, Any] = {"name": name}
    if description is not None:
        payload["description"] = description
    return self.create_record("Team", payload)


def update_team(
    self, team_id: str, description: str | None = None,
) -> tuple[int, dict[str, Any] | None]:
    """Update an existing Team record's description.

    Name is the team-identity key from YAML's perspective; this
    method intentionally does not accept a ``name`` parameter
    so the manager cannot accidentally trigger a server-side
    rename. The description is the only mutable field this
    workstream manages.

    :param team_id: Server-assigned Team record ID.
    :param description: New description text (or None to clear).
    :returns: Tuple of (status_code, response or None).
    """
    payload: dict[str, Any] = {"description": description}
    return self.patch_record("Team", team_id, payload)
```

### 3. `espo_impl/core/team_manager.py` — new module

Create the file. Module docstring should explicitly note the
out-of-scope items from "Position in the Series" above so future
readers understand the manager's boundaries.

```python
"""Team check/create/update orchestration logic.

This manager implements the deploy-side of the v1.2 audit
workstream's security half (paired with ``role_manager.py``).
It handles only Team records themselves; the following are out
of scope and handled elsewhere:

- Team deletion. Teams on the target server but not in YAML are
  left alone (conservative-deletion convention shared with every
  other manager in the codebase).
- Team rename. A YAML team whose name differs from any server
  team is treated as a new team; the old name remains on the
  server. Operators clean up renamed teams via the EspoCRM admin
  UI.
- User-to-team membership. Per Schema §12.2, team membership is
  runtime data managed in the target CRM admin UI, not in YAML.

The CHECK→ACT pattern mirrors ``tooltip_manager.py``:

1. CHECK: fetch all teams from the server in a single GET
2. For each YAML team, match by name against the server list
3. ACT: POST a new Team for unmatched YAML teams; PATCH
   description on matched-but-divergent teams; SKIP exact
   matches
"""

import logging
from collections.abc import Callable
from typing import Any

from espo_impl.core.api_client import EspoAdminClient, _format_error_detail
from espo_impl.core.models import (
    TeamDefinition,
    TeamResult,
    TeamStatus,
)

logger = logging.getLogger(__name__)

OutputCallback = Callable[[str, str], None]


class TeamManagerError(Exception):
    """Raised on fatal errors during team deploy (e.g., HTTP 401)."""


class TeamManager:
    """Orchestrates reading and writing Team records on EspoCRM.

    :param client: EspoCRM admin API client.
    :param output_fn: Callback for emitting output messages
        (message, color). The color string follows the existing
        managers' convention (``white`` for in-progress, ``gray``
        for skipped, ``green`` for success, ``red`` for errors).
    """

    def __init__(
        self,
        client: EspoAdminClient,
        output_fn: OutputCallback,
    ) -> None:
        self.client = client
        self.output_fn = output_fn

    def _fetch_server_teams(self) -> dict[str, dict[str, Any]]:
        """Fetch all teams from the server and index them by name.

        :returns: Mapping of team name to the full server record.
            Empty dict if the server has no teams.
        :raises TeamManagerError: On HTTP 401 (authentication
            failure) or any other non-200 status that prevents
            the CHECK phase from completing.
        """
        status, body = self.client.get_teams()
        if status == 401:
            raise TeamManagerError("Authentication failed (HTTP 401)")
        if status != 200 or body is None:
            error_msg = (
                f"HTTP {status}: {_format_error_detail(body)}"
                if status > 0 else "connection error"
            )
            raise TeamManagerError(
                f"Failed to fetch teams from server: {error_msg}"
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

        # The manager surfaces server-side duplicate-name conflicts
        # as per-team ERRORs in process_teams. Stash for caller.
        self._server_duplicate_names = duplicates
        return by_name

    def process_teams(
        self,
        teams: list[TeamDefinition],
        dry_run: bool = False,
    ) -> list[TeamResult]:
        """Process every team in the YAML batch against the server.

        :param teams: List of TeamDefinition from
            ``program.teams``. An empty list yields an empty
            result with no API calls.
        :param dry_run: If True, CHECK is performed and the
            intended status is recorded, but no POST or PATCH is
            issued.
        :returns: List of TeamResult, one per input team.
        :raises TeamManagerError: On HTTP 401 or other fatal CHECK
            errors. Per-team write failures are recorded as ERROR
            results, not raised.
        """
        if not teams:
            return []

        # CHECK — one bulk fetch
        self.output_fn("[TEAM]  Fetching server teams ...", "white")
        try:
            server_teams = self._fetch_server_teams()
        except TeamManagerError:
            # Propagate so the pipeline can surface it; do not
            # swallow auth or connectivity errors as per-team
            # results.
            raise

        results: list[TeamResult] = []
        for team_def in teams:
            results.append(self._process_one(team_def, server_teams, dry_run))
        return results

    def _process_one(
        self,
        team_def: TeamDefinition,
        server_teams: dict[str, dict[str, Any]],
        dry_run: bool,
    ) -> TeamResult:
        """Process a single team. See process_teams for semantics."""
        name = team_def.name
        prefix = f"[TEAM]  {name}"

        # Server-side duplicate-name ambiguity: refuse to act
        if name in self._server_duplicate_names:
            error_msg = (
                "multiple server teams share this name; cannot "
                "determine which to update"
            )
            self.output_fn(f"{prefix} ... ERROR — {error_msg}", "red")
            return TeamResult(
                name=name, status=TeamStatus.ERROR, error=error_msg,
            )

        existing = server_teams.get(name)
        desired_description = team_def.description  # may be None

        if existing is None:
            # CREATE path
            self.output_fn(f"{prefix} ... CREATING", "white")
            if dry_run:
                return TeamResult(name=name, status=TeamStatus.CREATED)
            status, body = self.client.create_team(name, desired_description)
            if status == 401:
                raise TeamManagerError("Authentication failed (HTTP 401)")
            if status in (200, 201) and body is not None:
                team_id = body.get("id")
                self.output_fn(f"{prefix} ... CREATED OK", "green")
                return TeamResult(
                    name=name,
                    status=TeamStatus.CREATED,
                    team_id=team_id,
                )
            error_msg = (
                f"HTTP {status}: {_format_error_detail(body)}"
                if status > 0 else "connection error"
            )
            self.output_fn(f"{prefix} ... ERROR — {error_msg}", "red")
            return TeamResult(
                name=name, status=TeamStatus.ERROR, error=error_msg,
            )

        # Existing record found — diff description
        team_id = existing.get("id")
        current_description = existing.get("description") or None
        desired_normalized = desired_description or None

        if current_description == desired_normalized:
            self.output_fn(f"{prefix} ... NO CHANGE", "gray")
            return TeamResult(
                name=name, status=TeamStatus.SKIPPED, team_id=team_id,
            )

        # UPDATE path
        self.output_fn(f"{prefix} ... UPDATING description", "white")
        if dry_run:
            return TeamResult(
                name=name, status=TeamStatus.UPDATED, team_id=team_id,
            )
        if team_id is None:
            # Defensive: should never happen with a valid server record
            error_msg = "server record missing 'id' field"
            self.output_fn(f"{prefix} ... ERROR — {error_msg}", "red")
            return TeamResult(
                name=name, status=TeamStatus.ERROR, error=error_msg,
            )
        status, body = self.client.update_team(team_id, desired_normalized)
        if status == 401:
            raise TeamManagerError("Authentication failed (HTTP 401)")
        if status == 200:
            self.output_fn(f"{prefix} ... UPDATED OK", "green")
            return TeamResult(
                name=name, status=TeamStatus.UPDATED, team_id=team_id,
            )
        error_msg = (
            f"HTTP {status}: {_format_error_detail(body)}"
            if status > 0 else "connection error"
        )
        self.output_fn(f"{prefix} ... ERROR — {error_msg}", "red")
        return TeamResult(
            name=name,
            status=TeamStatus.ERROR,
            team_id=team_id,
            error=error_msg,
        )
```

**Implementation notes:**

- `_server_duplicate_names` is set as an instance attribute by
  `_fetch_server_teams` and consumed by `_process_one`. This is
  the simplest signaling path between the two methods; if a
  future refactor wants pure functions, the duplicate set can be
  returned alongside the by-name map. For now, instance-attribute
  signaling matches the simplicity of the manager's overall
  shape.
- Description normalization treats empty string and `None` as
  equivalent (`""` from EspoCRM's serialized payload is
  semantically empty and should not trigger a spurious UPDATE).
  The `or None` coercion handles this on both sides of the diff.
- The output-callback color convention is borrowed from
  `tooltip_manager.py` and should match what `run_worker.py`
  expects when Prompt E wires the manager into the pipeline.

### 4. `tests/test_team_manager.py` — new test module

Follow `tests/test_tooltip_manager.py` patterns. Inline
`MagicMock` client; small `make_manager()` helper; one test
function per behavior.

Coverage areas:

**Empty input:**

- `process_teams([], dry_run=False)` returns an empty list and
  makes no API calls. Verified by asserting
  `client.get_teams.call_count == 0`.

**Create path:**

- Server returns empty list; YAML declares one team. Result:
  one `CREATED` with `team_id` populated from the create
  response. Verified that `create_team` was called with the
  expected name and description.
- Same scenario with `dry_run=True`: result is `CREATED` but
  `create_team` was not called.
- YAML team has no description: `create_team` is called with
  `description=None`.

**Skip path:**

- Server has a team with matching name and matching
  description. Result: `SKIPPED`, `team_id` from server,
  `update_team` not called.
- Server description is empty string, YAML description is None:
  normalized to equal; result is `SKIPPED`.
- Server description is None, YAML description is empty string:
  normalized to equal; result is `SKIPPED`.

**Update path:**

- Server has a team with matching name but divergent
  description. Result: `UPDATED`, `team_id` from server.
  Verified that `update_team` was called with the
  YAML description, not with the name.
- Same scenario with `dry_run=True`: result is `UPDATED` but
  `update_team` was not called.

**Error paths:**

- `get_teams` returns 401 → `TeamManagerError` is raised. No
  per-team results.
- `get_teams` returns 500 → `TeamManagerError` is raised.
- `get_teams` returns 200 but body has duplicate names. The
  duplicated-name YAML team produces `ERROR`; non-duplicated
  YAML teams in the same batch process normally.
- `create_team` returns 500 for a specific team → that team
  produces `ERROR` with `error` populated; subsequent YAML teams
  in the batch process normally.
- `update_team` returns 500 → `ERROR` result; subsequent teams
  process normally.
- `create_team` returns 401 → `TeamManagerError` raised
  (security-fatal, halts the batch).
- `update_team` returns 401 → `TeamManagerError` raised.

**Mixed batch:**

- Batch of three teams: one new, one matching, one divergent.
  Verifies the three different paths in a single
  `process_teams` call produce the three expected results in
  order.

Test helper sketch:

```python
"""Tests for the team manager orchestration logic."""

from unittest.mock import MagicMock

import pytest

from espo_impl.core.models import (
    TeamDefinition,
    TeamStatus,
)
from espo_impl.core.team_manager import TeamManager, TeamManagerError


def make_manager(client=None) -> tuple[TeamManager, list]:
    if client is None:
        client = MagicMock()
    output_log: list[tuple[str, str]] = []
    manager = TeamManager(
        client, lambda msg, color: output_log.append((msg, color)),
    )
    return manager, output_log


def server_response(teams: list[dict]) -> tuple[int, dict]:
    return (200, {"total": len(teams), "list": teams})


# ... test functions ...
```

## Acceptance Criteria

1. `models.py` carries `TeamStatus` (CREATED / UPDATED / SKIPPED /
   ERROR) and `TeamResult` dataclasses with the field shapes
   specified in §1 above.
2. `api_client.py` carries `get_teams()`, `create_team(name,
   description=None)`, `update_team(team_id, description=None)`
   methods. `update_team` accepts no `name` parameter (preventing
   accidental server-side rename).
3. `team_manager.py` exists at the path specified above with
   `TeamManager` class implementing `process_teams(teams,
   dry_run=False) -> list[TeamResult]`. The CHECK→ACT pattern is
   implemented as a single bulk-fetch followed by per-team
   matching against the by-name index.
4. The manager correctly handles all paths: empty input, create,
   skip-no-change, update-description-only, server-duplicate-name
   error, per-team HTTP errors, authentication failure
   (raises `TeamManagerError`).
5. Description normalization treats empty string and None as
   equivalent on both sides of the diff (no spurious updates).
6. `dry_run=True` records intended status without invoking any
   write API methods.
7. New tests cover every path enumerated in §4 above.
8. All existing tests continue to pass.
9. `uv run ruff check espo_impl/ tests/` passes clean on touched
   files.
10. `uv run pytest tests/ -v` passes.
11. Commit and push to `main` with a clear message referencing
    this prompt and the planning doc.

## Out of Scope

- Pipeline integration in `run_worker.py._run_full()` — Prompt E
  (adds the security pipeline step, ordering teams before roles)
- Team deletion — out of scope per planning doc; the manager
  documents the conservative-deletion convention
- Team rename — out of scope; a rename produces a new team plus
  a dangling old team requiring manual cleanup
- User-to-team membership — runtime data per Schema §12.2
- Pagination beyond `maxSize=200` — future scaling concern, not
  needed for dogfood or pilot use cases
- `role_manager.py` and all role-side concerns — Prompt D
- Role-aware visibility — Prompts F / G
- Audit-side team discovery (`_discover_teams`) — Prompt H

## Reporting Back

When finished, report:

- Modified file paths and line counts
- New tests added (count and brief coverage summary)
- Total test count before → after, ruff status
- Commit hash and message
- Any deviations from this prompt's specification (and why)
- Any open questions or follow-ups for Prompt D

The expected next step after Prompt C is green is **Prompt D**:
`role_manager.py` with the substantive scope_access translation
work that maps YAML `scope_access:` blocks to EspoCRM's Role
record `data` field shape, plus system_permissions translation to
the role-level permission columns. Prompt D is the most
substantive of the deploy-side managers.

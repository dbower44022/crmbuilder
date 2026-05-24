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
        self._server_duplicate_names: set[str] = set()

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

        self.output_fn("[TEAM]  Fetching server teams ...", "white")
        server_teams = self._fetch_server_teams()

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
        desired_description = team_def.description

        if existing is None:
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

        team_id = existing.get("id")
        current_description = existing.get("description") or None
        desired_normalized = desired_description or None

        if current_description == desired_normalized:
            self.output_fn(f"{prefix} ... NO CHANGE", "gray")
            return TeamResult(
                name=name, status=TeamStatus.SKIPPED, team_id=team_id,
            )

        self.output_fn(f"{prefix} ... UPDATING description", "white")
        if dry_run:
            return TeamResult(
                name=name, status=TeamStatus.UPDATED, team_id=team_id,
            )
        if team_id is None:
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

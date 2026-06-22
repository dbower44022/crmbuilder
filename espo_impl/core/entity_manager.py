"""Custom entity create/delete orchestration logic.

Confirmed API endpoints (discovered via browser dev tools 2026-03-21):
  Create: POST /api/v1/EntityManager/action/createEntity
          Payload: {"name":"Engagement","labelSingular":"Engagement",
                    "labelPlural":"Engagements","type":"Base",
                    "stream":false,"disabled":false}
          EspoCRM adds a C prefix: Engagement → CEngagement

  Delete: POST /api/v1/EntityManager/action/removeEntity
          Payload: {"name":"CEngagement"}
          Uses the C-prefixed internal name.

  Rebuild: POST /api/v1/Admin/rebuild
"""

import logging
import time
from collections.abc import Callable
from typing import Any

from espo_impl.core.api_client import EspoAdminClient, _format_error_detail
from espo_impl.core.models import EntityAction, EntityDefinition
from espo_impl.ui.confirm_delete_dialog import get_espo_entity_name

logger = logging.getLogger(__name__)

OutputCallback = Callable[[str, str], None]


class EntityManagerError(Exception):
    """Raised when the API returns 401 Unauthorized."""


class EntityManager:
    """Orchestrates custom entity create/delete operations.

    :param client: EspoCRM admin API client.
    :param output_fn: Callback for emitting output messages (message, color).
    """

    def __init__(
        self,
        client: EspoAdminClient,
        output_fn: OutputCallback,
    ) -> None:
        self.client = client
        self.output_fn = output_fn

    def process_entity(self, entity_def: EntityDefinition) -> bool:
        """Process a single entity definition.

        :param entity_def: Entity definition with an action.
        :returns: True if successful, False if an error occurred.
        """
        if entity_def.action == EntityAction.DELETE:
            return self._delete_entity(entity_def)
        elif entity_def.action == EntityAction.CREATE:
            return self._create_entity(entity_def)
        elif entity_def.action == EntityAction.DELETE_AND_CREATE:
            deleted = self._delete_entity(entity_def)
            if not deleted:
                # Delete failed for a reason other than "not found" — abort
                return False
            return self._create_entity(entity_def)
        return True

    def rebuild_cache(self) -> bool:
        """Trigger a cache rebuild on the instance.

        :returns: True if successful.
        """
        self.output_fn("[REBUILD] Triggering cache rebuild ...", "white")
        status_code, body = self.client.rebuild()

        if status_code == 401:
            self.output_fn(
                "[ERROR]   Authentication failed (HTTP 401)", "red"
            )
            raise EntityManagerError("Authentication failed (HTTP 401)")

        if status_code == 200:
            self.output_fn("[REBUILD] Cache rebuild complete", "green")
            return True

        self.output_fn(
            f"[REBUILD] Cache rebuild failed (HTTP {status_code})", "red"
        )
        if body:
            self.output_fn(f"          {body}", "red")
        return False

    def wait_for_metadata_ready(
        self,
        entity_def_names: list[str],
        timeout_seconds: float = 30.0,
    ) -> bool:
        """Poll EspoCRM's metadata API until every named entity's
        entityDefs are materialized in the cache, or the timeout
        elapses.

        Called after rebuild_cache() to close the async race window
        between rebuild completion and downstream operations. The
        underlying issue is that POST /Admin/rebuild returns 200 to
        acknowledge the request, but the rebuild itself runs
        asynchronously on the EspoCRM PHP process. Subsequent
        operations against newly-created entities can fail with
        HTTP 500 / 403 errors if the metadata for that entity isn't
        yet in the cache.

        :param entity_def_names: List of YAML-natural entity names
            (e.g. ["Engagement", "Session"]). Each is resolved to its
            EspoCRM internal name via get_espo_entity_name() before
            polling.
        :param timeout_seconds: Hard upper bound on how long to wait
            across all entities. Default 30 seconds.
        :returns: True if every entity's metadata was materialized
            before timeout; False if at least one timed out. On False
            return, callers should still proceed but should expect
            downstream operations to potentially fail and log
            accordingly.
        """
        if not entity_def_names:
            return True

        self.output_fn(
            "[WAIT]    Waiting for metadata cache to materialize "
            "new entities ...",
            "white",
        )

        backoff_pattern = [0.5, 0.5, 1.0, 1.0] + [2.0] * 30

        pending = list(entity_def_names)
        deadline = time.monotonic() + timeout_seconds
        attempt = 0
        timed_out_any = False

        while pending and time.monotonic() < deadline:
            delay = backoff_pattern[
                min(attempt, len(backoff_pattern) - 1)
            ]
            time.sleep(delay)
            attempt += 1

            still_pending: list[str] = []
            for yaml_name in pending:
                espo_name = get_espo_entity_name(yaml_name)
                status_code, meta = self.client.get_entity_full_metadata(
                    espo_name
                )
                if (
                    status_code == 200
                    and isinstance(meta, dict)
                    and meta
                ):
                    self.output_fn(
                        f"[WAIT]    {yaml_name} ({espo_name}) ... ready",
                        "gray",
                    )
                else:
                    still_pending.append(yaml_name)
            pending = still_pending

        if pending:
            timed_out_any = True
            for yaml_name in pending:
                espo_name = get_espo_entity_name(yaml_name)
                self.output_fn(
                    f"[WAIT]    {yaml_name} ({espo_name}) ... "
                    f"TIMED OUT after {timeout_seconds:.0f}s",
                    "yellow",
                )

        if timed_out_any:
            self.output_fn(
                f"[WAIT]    Metadata wait timed out after "
                f"{timeout_seconds:.0f}s — proceeding anyway",
                "yellow",
            )
            return False

        self.output_fn("[WAIT]    Metadata cache ready", "green")
        return True

    def _delete_entity(
        self, entity_def: EntityDefinition, dry_run: bool = False
    ) -> bool:
        """Delete a custom entity from the instance.

        :param entity_def: Entity definition to delete.
        :param dry_run: If True, log the planned delete and return
            without issuing the API write.
        :returns: True if deleted or didn't exist, False on error.
        """
        espo_name = get_espo_entity_name(entity_def.name)

        # Check if entity exists
        self.output_fn(
            f"[CHECK]   Entity {entity_def.name} ({espo_name}) ...", "white"
        )
        status_code, exists = self.client.check_entity_exists(espo_name)

        if status_code == 401:
            self.output_fn(
                "[ERROR]   Authentication failed (HTTP 401)", "red"
            )
            raise EntityManagerError("Authentication failed (HTTP 401)")

        if not exists:
            self.output_fn(
                f"[DELETE]  {espo_name} ... NOT FOUND (skipping)", "gray"
            )
            return True

        # Delete the entity
        self.output_fn(f"[DELETE]  {espo_name} ...", "white")
        if dry_run:
            self.output_fn(
                f"[DELETE]  {espo_name} ... would delete (preview)", "gray"
            )
            return True
        status_code, body = self.client.remove_entity(espo_name)

        if status_code == 401:
            raise EntityManagerError("Authentication failed (HTTP 401)")

        if status_code == 200:
            self.output_fn(f"[DELETE]  {espo_name} ... OK", "green")
            return True

        self.output_fn(
            f"[DELETE]  {espo_name} ... ERROR (HTTP {status_code})", "red"
        )
        self.output_fn(f"          {_format_error_detail(body)}", "red")
        return False

    def _create_entity(
        self, entity_def: EntityDefinition, dry_run: bool = False
    ) -> bool:
        """Create a custom entity on the instance.

        :param entity_def: Entity definition to create.
        :param dry_run: If True, log the planned create and return
            without issuing the API write.
        :returns: True if created or already exists, False on error.
        """
        espo_name = get_espo_entity_name(entity_def.name)

        # Check if entity already exists
        self.output_fn(
            f"[CHECK]   Entity {entity_def.name} ({espo_name}) ...", "white"
        )
        status_code, exists = self.client.check_entity_exists(espo_name)

        if status_code == 401:
            raise EntityManagerError("Authentication failed (HTTP 401)")

        if exists:
            self.output_fn(
                f"[CREATE]  {espo_name} ... ALREADY EXISTS (skipping)", "gray"
            )
            return True

        # Build the payload using natural name (EspoCRM adds C prefix)
        payload: dict[str, Any] = {
            "name": entity_def.name,
            "type": entity_def.type or "Base",
            "labelSingular": entity_def.labelSingular or entity_def.name,
            "labelPlural": entity_def.labelPlural or f"{entity_def.name}s",
            "stream": entity_def.stream,
            "disabled": entity_def.disabled,
        }

        self.output_fn(f"[CREATE]  {espo_name} ...", "white")
        if dry_run:
            self.output_fn(
                f"[CREATE]  {espo_name} ... would create (preview)", "gray"
            )
            return True
        status_code, body = self.client.create_entity(payload)

        if status_code == 401:
            raise EntityManagerError("Authentication failed (HTTP 401)")

        if status_code == 200:
            self.output_fn(f"[CREATE]  {espo_name} ... OK", "green")
            return True

        self.output_fn(
            f"[CREATE]  {espo_name} ... ERROR (HTTP {status_code})", "red"
        )
        self.output_fn(f"          {_format_error_detail(body)}", "red")
        return False

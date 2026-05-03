"""Saved-view CHECK->ACT orchestration logic."""

import logging
from collections.abc import Callable
from typing import Any

from espo_impl.core.api_client import EspoAdminClient, _format_error_detail
from espo_impl.core.condition_expression import render_condition
from espo_impl.core.models import (
    EntityAction,
    EntityDefinition,
    ProgramFile,
    SavedView,
    SavedViewResult,
    SavedViewStatus,
)
from espo_impl.ui.confirm_delete_dialog import get_espo_entity_name

logger = logging.getLogger(__name__)

OutputCallback = Callable[[str, str], None]


class SavedViewManagerError(Exception):
    """Raised when the API returns 401 Unauthorized."""


class SavedViewManager:
    """Orchestrates saved-view recognition and reporting.

    Saved views (clientDefs.{Entity}.savedViews) cannot be written via
    EspoCRM's REST API — ``/api/v1/Metadata`` exposes GET only. This
    manager recognizes YAML-declared saved views, emits a NOT SUPPORTED
    line for each, and returns ``NOT_SUPPORTED`` results so the run
    worker can surface them in its MANUAL CONFIGURATION REQUIRED block.

    The legacy CHECK/WRITE private helpers below are retained as dead
    code so a future REST-capable or file-based reimplementation can
    resurrect them with a smaller diff.

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

    def process_saved_views(
        self, program: ProgramFile
    ) -> list[SavedViewResult]:
        """Acknowledge saved views from the YAML; do not attempt API writes.

        EspoCRM has no public REST API for clientDefs metadata writes
        (``/api/v1/Metadata`` accepts GET only — there is no PUT, POST,
        or PATCH route). Saved views must be configured manually via
        the EspoCRM admin UI or by editing
        ``custom/Espo/Custom/Resources/metadata/clientDefs/{Entity}.json``
        on disk and rebuilding the cache.

        This method iterates every saved view declared in the YAML,
        emits a NOT SUPPORTED line per item, and returns results all
        marked ``SavedViewStatus.NOT_SUPPORTED``. The MANUAL
        CONFIGURATION REQUIRED block at the end of the run aggregates
        these for operator action.

        :param program: Parsed and validated program file.
        :returns: List of per-view results, each with status NOT_SUPPORTED.
        """
        results: list[SavedViewResult] = []

        for entity_def in program.entities:
            if entity_def.action == EntityAction.DELETE:
                continue
            if not entity_def.saved_views:
                continue

            for view in entity_def.saved_views:
                self.output_fn(
                    f"[NOT SUPPORTED] {entity_def.name}.savedViews"
                    f"[{view.id}] — manual config required",
                    "yellow",
                )
                results.append(
                    SavedViewResult(
                        entity=entity_def.name,
                        view_id=view.id,
                        status=SavedViewStatus.NOT_SUPPORTED,
                    )
                )

        return results

    def _process_entity_views(
        self, entity_def: EntityDefinition
    ) -> list[SavedViewResult]:
        # TODO(error-handling-D): restore when REST-capable reimplementation lands
        """CHECK->ACT for all saved views on one entity.

        :param entity_def: Entity definition with saved views.
        :returns: List of results for each view.
        :raises SavedViewManagerError: On authentication failure.
        """
        espo_name = get_espo_entity_name(entity_def.name)
        prefix = entity_def.name

        # Phase 1: CHECK — read current clientDefs metadata
        self.output_fn(
            f"[CHECK]   {prefix} savedViews ...", "white"
        )
        status_code, client_defs = self.client.get_client_defs(espo_name)

        if status_code == 401:
            raise SavedViewManagerError(
                "Authentication failed (HTTP 401)"
            )

        if status_code < 0:
            self.output_fn(
                f"[ERROR]   {prefix} savedViews ... CONNECTION ERROR",
                "red",
            )
            return [
                SavedViewResult(
                    entity=entity_def.name,
                    view_id=view.id,
                    status=SavedViewStatus.ERROR,
                    error="Connection error",
                )
                for view in entity_def.saved_views
            ]

        if client_defs is None:
            client_defs = {}

        # Extract existing saved views from metadata
        existing_views = self._extract_existing_views(client_defs)
        results: list[SavedViewResult] = []
        desired_ids: set[str] = set()

        for view in entity_def.saved_views:
            desired_ids.add(view.id)
            result = self._process_view(
                entity_def.name, espo_name, view, existing_views
            )
            results.append(result)

        # Drift detection: views on CRM not in YAML
        for existing in existing_views:
            eid = existing.get("id", "")
            if eid and eid not in desired_ids:
                self.output_fn(
                    f"[DRIFT]   {prefix}.savedViews[{eid}] "
                    f"exists on CRM but not in YAML",
                    "yellow",
                )
                results.append(SavedViewResult(
                    entity=entity_def.name,
                    view_id=eid,
                    status=SavedViewStatus.DRIFT,
                ))

        # Phase 2: ACT — write updated views to metadata
        if any(
            r.status in (SavedViewStatus.CREATED, SavedViewStatus.UPDATED)
            for r in results
        ):
            write_ok = self._write_views(
                entity_def.name, espo_name, entity_def.saved_views,
                existing_views, desired_ids,
            )
            if not write_ok:
                for r in results:
                    if r.status in (
                        SavedViewStatus.CREATED,
                        SavedViewStatus.UPDATED,
                    ):
                        r.status = SavedViewStatus.ERROR
                        r.error = "Failed to write metadata"

        return results

    def _process_view(
        self,
        entity_name: str,
        espo_name: str,
        view: SavedView,
        existing_views: list[dict],
    ) -> SavedViewResult:
        # TODO(error-handling-D): restore when REST-capable reimplementation lands
        """Compare a single saved view against existing CRM state.

        :param entity_name: Natural entity name.
        :param espo_name: EspoCRM entity name (C-prefixed).
        :param view: Desired saved view.
        :param existing_views: Current views from the CRM.
        :returns: Result indicating create/update/skip.
        """
        prefix = f"{entity_name}.savedViews[{view.id}]"

        # Find existing view by id
        existing = None
        for ev in existing_views:
            if ev.get("id") == view.id:
                existing = ev
                break

        desired = self._view_to_dict(view)

        if existing is None:
            self.output_fn(
                f"[CREATE]  {prefix} ... NOT FOUND ON CRM", "white"
            )
            return SavedViewResult(
                entity=entity_name,
                view_id=view.id,
                status=SavedViewStatus.CREATED,
            )

        # Compare
        if self._views_match(desired, existing):
            self.output_fn(
                f"[SKIP]    {prefix} ... MATCHES", "gray"
            )
            return SavedViewResult(
                entity=entity_name,
                view_id=view.id,
                status=SavedViewStatus.SKIPPED,
            )

        self.output_fn(
            f"[UPDATE]  {prefix} ... DIFFERS", "yellow"
        )
        return SavedViewResult(
            entity=entity_name,
            view_id=view.id,
            status=SavedViewStatus.UPDATED,
        )

    def _write_views(
        self,
        entity_name: str,
        espo_name: str,
        desired_views: list[SavedView],
        existing_views: list[dict],
        desired_ids: set[str],
    ) -> bool:
        # TODO(error-handling-D): restore when REST-capable reimplementation lands
        """Write the full set of saved views to CRM metadata.

        Preserves existing views that are not in the YAML (drift views
        are reported but not deleted).

        :param entity_name: Natural entity name.
        :param espo_name: EspoCRM entity name.
        :param desired_views: Desired views from YAML.
        :param existing_views: Current views from CRM.
        :param desired_ids: Set of desired view IDs.
        :returns: True if write succeeded.
        """
        merged: list[dict] = [self._view_to_dict(v) for v in desired_views]
        for ev in existing_views:
            eid = ev.get("id", "")
            if eid and eid not in desired_ids:
                merged.append(ev)

        payload: dict[str, Any] = {
            "clientDefs": {
                espo_name: {
                    "savedViews": merged,
                },
            },
        }

        self.output_fn(
            f"[WRITE]   {entity_name} savedViews metadata ...",
            "white",
        )
        status_code, body = self.client.put_metadata(payload)

        if status_code == 401:
            raise SavedViewManagerError(
                "Authentication failed (HTTP 401)"
            )

        if status_code < 0 or status_code >= 400:
            self.output_fn(
                f"[ERROR]   {entity_name} savedViews metadata ... "
                f"HTTP {status_code}",
                "red",
            )
            self.output_fn(f"          {_format_error_detail(body)}", "red")
            return False

        self.output_fn(
            f"[WRITE]   {entity_name} savedViews metadata ... OK",
            "green",
        )
        return True

    @staticmethod
    def _extract_existing_views(client_defs: dict) -> list[dict]:
        # TODO(error-handling-D): restore when REST-capable reimplementation lands
        """Extract saved views from clientDefs metadata.

        :param client_defs: clientDefs dict from the API.
        :returns: List of view dicts.
        """
        views = client_defs.get("savedViews", [])
        if not isinstance(views, list):
            return []
        return views

    @staticmethod
    def _view_to_dict(view: SavedView) -> dict:
        # TODO(error-handling-D): restore when REST-capable reimplementation lands
        """Convert a SavedView model to a metadata dict.

        :param view: SavedView instance.
        :returns: Dict suitable for CRM metadata.
        """
        d: dict[str, Any] = {
            "id": view.id,
            "name": view.name,
        }
        if view.description is not None:
            d["description"] = view.description
        if view.columns is not None:
            d["columns"] = view.columns
        if view.filter is not None:
            d["filter"] = render_condition(view.filter)
        if view.order_by:
            order_list = [
                {"field": ob.field, "direction": ob.direction}
                for ob in view.order_by
            ]
            d["orderBy"] = order_list[0] if len(order_list) == 1 else order_list
        return d

    @staticmethod
    def _views_match(desired: dict, existing: dict) -> bool:
        # TODO(error-handling-D): restore when REST-capable reimplementation lands
        """Compare a desired view dict against an existing one.

        :param desired: View dict from YAML.
        :param existing: View dict from CRM metadata.
        :returns: True if they match on all meaningful keys.
        """
        keys = {"id", "name", "description", "columns", "filter", "orderBy"}
        for key in keys:
            d_val = desired.get(key)
            e_val = existing.get(key)
            if d_val != e_val:
                return False
        return True

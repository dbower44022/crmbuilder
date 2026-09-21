"""Saved-view CHECK->ACT orchestration logic."""

import logging
from collections.abc import Callable

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.models import (
    EntityAction,
    ProgramFile,
    SavedViewResult,
    SavedViewStatus,
)

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


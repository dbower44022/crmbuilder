"""Workflow CHECK->ACT orchestration logic."""

import logging
from collections.abc import Callable

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.models import (
    EntityAction,
    ProgramFile,
    WorkflowResult,
    WorkflowStatus,
)

logger = logging.getLogger(__name__)

OutputCallback = Callable[[str, str], None]


class WorkflowManagerError(Exception):
    """Raised when the API returns 401 Unauthorized."""


class WorkflowManager:
    """Orchestrates workflow recognition and reporting.

    Workflows in EspoCRM are entity records exposed via
    ``/api/v1/Workflow`` (and require the Advanced Pack extension), not
    metadata writes. This manager recognizes YAML-declared workflows,
    emits a NOT SUPPORTED line for each, and returns ``NOT_SUPPORTED``
    results so the run worker can surface them in its MANUAL
    CONFIGURATION REQUIRED block.

    The legacy CHECK/WRITE private helpers below are retained as dead
    code so a future Workflow-record-CRUD reimplementation can
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

    def process_workflows(
        self, program: ProgramFile
    ) -> list[WorkflowResult]:
        """Acknowledge workflows from the YAML; do not attempt API writes.

        EspoCRM has no public REST API for clientDefs metadata writes,
        and workflows are not metadata in the first place — they are
        entity records that require the Advanced Pack extension.
        Workflows must be configured manually via the EspoCRM admin UI.

        This method iterates every workflow declared in the YAML, emits
        a NOT SUPPORTED line per item, and returns results all marked
        ``WorkflowStatus.NOT_SUPPORTED``. The MANUAL CONFIGURATION
        REQUIRED block at the end of the run aggregates these for
        operator action.

        :param program: Parsed and validated program file.
        :returns: List of per-workflow results, each with status NOT_SUPPORTED.
        """
        results: list[WorkflowResult] = []

        for entity_def in program.entities:
            if entity_def.action == EntityAction.DELETE:
                continue
            if not entity_def.workflows:
                continue

            for wf in entity_def.workflows:
                self.output_fn(
                    f"[NOT SUPPORTED] {entity_def.name}.workflows"
                    f"[{wf.id}] — manual config required",
                    "yellow",
                )
                results.append(
                    WorkflowResult(
                        entity=entity_def.name,
                        workflow_id=wf.id,
                        status=WorkflowStatus.NOT_SUPPORTED,
                    )
                )

        return results


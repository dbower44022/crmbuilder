"""Duplicate-check rule CHECK->ACT orchestration logic."""

import logging
from collections.abc import Callable

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.models import (
    DuplicateCheckResult,
    DuplicateCheckStatus,
    EntityAction,
    ProgramFile,
)

logger = logging.getLogger(__name__)

OutputCallback = Callable[[str, str], None]


class DuplicateCheckManagerError(Exception):
    """Raised when the API returns 401 Unauthorized."""


class DuplicateCheckManager:
    """Orchestrates duplicate-check rule recognition and reporting.

    Duplicate-check rules cannot be written via the metadata write path
    used here — ``/api/v1/Metadata`` exposes GET only, and the proper
    EspoCRM mechanism (the EntityManager endpoint) requires a different
    code path. This manager recognizes YAML-declared rules, emits a
    NOT SUPPORTED line for each, and returns ``NOT_SUPPORTED`` results
    so the run worker can surface them in its MANUAL CONFIGURATION
    REQUIRED block.

    The legacy CHECK/WRITE private helpers below are retained as dead
    code so a future reimplementation against EntityManager (or another
    working backend) can resurrect them with a smaller diff.

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

    def process_duplicate_checks(
        self, program: ProgramFile
    ) -> list[DuplicateCheckResult]:
        """Acknowledge duplicate checks from the YAML; do not attempt API writes.

        EspoCRM has no public REST API for clientDefs metadata writes
        and the existing EntityManager-based path is not implemented
        here. Duplicate-check rules must be configured manually via the
        EspoCRM admin UI.

        This method iterates every duplicate-check rule declared in the
        YAML, emits a NOT SUPPORTED line per item, and returns results
        all marked ``DuplicateCheckStatus.NOT_SUPPORTED``. The MANUAL
        CONFIGURATION REQUIRED block at the end of the run aggregates
        these for operator action.

        :param program: Parsed and validated program file.
        :returns: List of per-rule results, each with status NOT_SUPPORTED.
        """
        results: list[DuplicateCheckResult] = []

        for entity_def in program.entities:
            if entity_def.action == EntityAction.DELETE:
                continue
            if not entity_def.duplicate_checks:
                continue

            for rule in entity_def.duplicate_checks:
                self.output_fn(
                    f"[NOT SUPPORTED] {entity_def.name}.duplicateChecks"
                    f"[{rule.id}] — manual config required",
                    "yellow",
                )
                results.append(
                    DuplicateCheckResult(
                        entity=entity_def.name,
                        rule_id=rule.id,
                        status=DuplicateCheckStatus.NOT_SUPPORTED,
                    )
                )

        return results


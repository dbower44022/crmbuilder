"""Background worker thread for run/verify operations.

The deploy orchestration (the 12-step CHECK→ACT pipeline) lives in the Qt-free
:mod:`espo_impl.core.deploy_pipeline` module (PRJ-042, DEC-572) so it can be
reused headless by V2 publish. This worker is the Qt adapter: it runs the
pipeline off the main thread and translates its result into Qt signals.

The manager classes are imported here so they remain patchable at
``espo_impl.workers.run_worker.<Manager>`` (the V1 test seam); :meth:`_run_full`
passes them into the pipeline through a :class:`DeployManagers` set. The
``_run_step`` / ``_emit_step_summary`` / ``_emit_manual_config_block`` methods
and the module-level ``_check_results_for_errors`` are thin delegators kept for
the existing unit tests.
"""

import logging
from typing import Any

from PySide6.QtCore import QThread, Signal

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.comparator import FieldComparator
from espo_impl.core.deploy_pipeline import (
    DeployManagers,
    check_results_for_errors,
    deploy_pipeline,
    emit_manual_config_block,
    emit_step_summary,
    run_step,
)
from espo_impl.core.duplicate_check_manager import DuplicateCheckManager
from espo_impl.core.email_template_manager import EmailTemplateManager
from espo_impl.core.entity_manager import EntityManager
from espo_impl.core.entity_settings_manager import EntitySettingsManager
from espo_impl.core.field_manager import AuthenticationError, FieldManager
from espo_impl.core.filtered_tab_manager import FilteredTabManager
from espo_impl.core.layout_manager import LayoutManager
from espo_impl.core.models import (
    InstanceProfile,
    ProgramFile,
    RunReport,
    StepResult,
)
from espo_impl.core.relationship_manager import RelationshipManager
from espo_impl.core.role_manager import RoleManager
from espo_impl.core.saved_view_manager import SavedViewManager
from espo_impl.core.team_manager import TeamManager
from espo_impl.core.workflow_manager import WorkflowManager

logger = logging.getLogger(__name__)

# Re-exported for the existing unit tests that import it from this module.
_check_results_for_errors = check_results_for_errors


class RunWorker(QThread):
    """Background worker that runs entity and field operations off the main thread.

    :param profile: Instance connection profile.
    :param program: Validated program file to process.
    :param operation: Either "run", "preview", or "verify".
    :param skip_deletes: If True, skip all entity delete operations.
    :param parent: Parent QObject.
    """

    output_line = Signal(str, str)
    finished_ok = Signal(object)
    finished_error = Signal(str)

    def __init__(
        self,
        profile: InstanceProfile,
        program: ProgramFile,
        operation: str,
        skip_deletes: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.profile = profile
        self.program = program
        self.operation = operation
        self.skip_deletes = skip_deletes

    def run(self) -> None:
        """Execute the operation in a background thread."""
        try:
            client = EspoAdminClient(self.profile)
            comparator = FieldComparator()
            field_mgr = FieldManager(client, comparator, self.output_line.emit)

            if self.operation == "preview":
                report = field_mgr.preview(self.program)
                self.finished_ok.emit(report)
                return

            if self.operation == "verify":
                report = field_mgr.verify(self.program)
                self.finished_ok.emit(report)
                return

            # --- Full run ---
            self._run_full(client, field_mgr)

        except AuthenticationError:
            # Hard-abort: auth was promoted from a step to fatal.
            self.finished_error.emit("Authentication failed (HTTP 401)")
        except Exception as exc:
            # Final safety net — the pipeline should contain everything else,
            # but a defect there shouldn't crash the worker.
            logger.exception("Unexpected error escaped run pipeline")
            self.output_line.emit(
                f"[FATAL]   Unexpected error — please file a bug: "
                f"{type(exc).__name__}: {exc}",
                "red",
            )
            self.finished_error.emit(str(exc))

    # ── Main pipeline (delegates to the Qt-free orchestration) ─────────

    def _run_full(
        self, client: EspoAdminClient, field_mgr: FieldManager
    ) -> None:
        """Run the 12-step deploy pipeline and translate it into Qt signals.

        Delegates to :func:`espo_impl.core.deploy_pipeline.deploy_pipeline`,
        passing the manager classes from this module's namespace so the test
        patches at ``espo_impl.workers.run_worker.<Manager>`` take effect. On
        success the report is emitted via ``finished_ok``; an authentication
        failure is translated into ``finished_error`` exactly as before.

        :param client: API client.
        :param field_mgr: Field manager for field operations.
        """
        managers = DeployManagers(
            entity=EntityManager,
            entity_settings=EntitySettingsManager,
            email_template=EmailTemplateManager,
            duplicate_check=DuplicateCheckManager,
            saved_view=SavedViewManager,
            layout=LayoutManager,
            relationship=RelationshipManager,
            role=RoleManager,
            team=TeamManager,
            workflow=WorkflowManager,
            filtered_tab=FilteredTabManager,
        )

        try:
            outcome = deploy_pipeline(
                self.program,
                client,
                field_mgr,
                self.output_line.emit,
                skip_deletes=self.skip_deletes,
                managers=managers,
            )
        except AuthenticationError as exc:
            self.finished_error.emit(
                f"Authentication failed (HTTP 401): {exc}"
            )
            return

        # Stash the security results for downstream consumers (Prompt H).
        self._security_team_results = outcome.security_team_results
        self._security_role_results = outcome.security_role_results

        self.finished_ok.emit(outcome.report)

    # ── Thin delegators kept for the existing unit tests ──────────────

    def _run_step(
        self,
        step_name: str,
        has_work: bool,
        body,
        failure_check=None,
    ) -> tuple[StepResult, Any]:
        """Delegate to :func:`deploy_pipeline.run_step` with this worker's
        output callback. Retained for the ``_run_step`` unit tests."""
        return run_step(
            step_name,
            has_work,
            body,
            self.output_line.emit,
            failure_check,
        )

    def _emit_step_summary(self, step_results: list[StepResult]) -> None:
        """Delegate to :func:`deploy_pipeline.emit_step_summary`. Retained for
        the ``_emit_step_summary`` unit tests."""
        emit_step_summary(self.output_line.emit, step_results)

    def _emit_manual_config_block(self, report: RunReport) -> None:
        """Delegate to :func:`deploy_pipeline.emit_manual_config_block`.
        Retained for the ``_emit_manual_config_block`` unit tests."""
        emit_manual_config_block(self.output_line.emit, report)


__all__ = ["RunWorker"]

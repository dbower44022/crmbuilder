"""Background worker thread for run/verify operations."""

import logging
from collections.abc import Callable, Iterable
from typing import Any

from PySide6.QtCore import QThread, Signal

from espo_impl.core.api_client import EspoAdminClient, _format_error_detail
from espo_impl.core.comparator import FieldComparator
from espo_impl.core.duplicate_check_manager import (
    DuplicateCheckManager,
    DuplicateCheckManagerError,
)
from espo_impl.core.email_template_manager import (
    EmailTemplateManager,
    EmailTemplateManagerError,
)
from espo_impl.core.entity_manager import EntityManager, EntityManagerError
from espo_impl.core.entity_settings_manager import (
    EntitySettingsManager,
    EntitySettingsManagerError,
)
from espo_impl.core.field_manager import AuthenticationError, FieldManager
from espo_impl.core.filtered_tab_manager import (
    FilteredTabManager,
    FilteredTabManagerError,
)
from espo_impl.core.layout_manager import LayoutManager, LayoutManagerError
from espo_impl.core.models import (
    DuplicateCheckStatus,
    EmailTemplateStatus,
    EntityAction,
    EntityLayoutStatus,
    FilteredTabStatus,
    InstanceProfile,
    ProgramFile,
    RelationshipStatus,
    RunReport,
    SavedViewStatus,
    SettingsStatus,
    StepResult,
    StepStatus,
    WorkflowStatus,
)
from espo_impl.core.relationship_manager import (
    RelationshipManager,
    RelationshipManagerError,
)
from espo_impl.core.saved_view_manager import (
    SavedViewManager,
    SavedViewManagerError,
)
from espo_impl.core.workflow_manager import (
    WorkflowManager,
    WorkflowManagerError,
)

logger = logging.getLogger(__name__)


_MANAGER_ERROR_TYPES: tuple[type[Exception], ...] = (
    EntityManagerError,
    EntitySettingsManagerError,
    EmailTemplateManagerError,
    DuplicateCheckManagerError,
    SavedViewManagerError,
    LayoutManagerError,
    RelationshipManagerError,
    WorkflowManagerError,
    FilteredTabManagerError,
)


_STEP_DISPLAY_NAMES: dict[str, str] = {
    "entity_deletions": "Entity deletions",
    "entity_creations": "Entity creations",
    "entity_settings": "Entity settings",
    "email_templates": "Email templates",
    "duplicate_checks": "Duplicate checks",
    "saved_views": "Saved views",
    "fields": "Fields",
    "layouts": "Layouts",
    "relationships": "Relationships",
    "workflows": "Workflows",
    "filtered_tabs": "Filtered tabs",
}


def _is_authentication_message(message: str) -> bool:
    """Detect auth-flavored error messages so they can be promoted to fatal.

    :param message: Exception text from a manager.
    :returns: True if the message looks like an authentication failure.
    """
    return "401" in message or "Authentication" in message


def _check_results_for_errors(
    results: Iterable[Any] | None,
    error_statuses: set[Any],
    label: str,
) -> str | None:
    """Inspect a result list and return a failure summary, or None if clean.

    :param results: Iterable of result records (may be None or empty).
    :param error_statuses: Set of status enum values that count as failure.
    :param label: Singular human label, e.g. "saved view", "field".
    :returns: ``"{n} of {total} {label}(s) failed"`` if any errors, else None.
    """
    if not results:
        return None
    items = list(results)
    error_count = sum(
        1 for r in items
        if getattr(r, "status", None) in error_statuses
    )
    if error_count == 0:
        return None
    return f"{error_count} of {len(items)} {label}(s) failed"


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
            # Final safety net — _run_step should contain everything else,
            # but a defect there shouldn't crash the worker.
            logger.exception("Unexpected error escaped run pipeline")
            self.output_line.emit(
                f"[FATAL]   Unexpected error — please file a bug: "
                f"{type(exc).__name__}: {exc}",
                "red",
            )
            self.finished_error.emit(str(exc))

    # ── Per-step isolation ────────────────────────────────────────────

    def _run_step(
        self,
        step_name: str,
        has_work: bool,
        body: Callable[[], Any],
        failure_check: Callable[[Any], str | None] | None = None,
    ) -> tuple[StepResult, Any]:
        """Run one phase of the pipeline, isolating failures.

        :param step_name: Canonical snake_case step name.
        :param has_work: If False, the step is skipped (no-op, no header
            emitted).
        :param body: Zero-arg callable that runs the step. Returns
            step-specific results (or None). May raise *ManagerError or
            any Exception.
        :param failure_check: Optional callable invoked only on the success
            path with the body's return value. If it returns a non-None
            string, the step is downgraded from OK to FAILED with that
            string as the error and a ``[STEP FAILED]`` line is emitted.
            The body's return value is still returned to the caller so it
            can be attached to the report.
        :returns: Tuple of (StepResult, body return value or None on failure).
        :raises AuthenticationError: Re-raised so the caller can hard-abort.
        """
        if not has_work:
            return (
                StepResult(step_name=step_name, status=StepStatus.SKIPPED),
                None,
            )

        try:
            return_value = body()
        except AuthenticationError:
            self.output_line.emit(
                f"[FATAL]   Authentication failed during {step_name} "
                f"— aborting run",
                "red",
            )
            raise
        except Exception as exc:
            msg = str(exc)
            if _is_authentication_message(msg):
                self.output_line.emit(
                    f"[FATAL]   Authentication failed during {step_name} "
                    f"— aborting run",
                    "red",
                )
                raise AuthenticationError(msg) from exc

            if isinstance(exc, _MANAGER_ERROR_TYPES):
                logger.warning(
                    "Step %s failed with manager error: %s", step_name, exc
                )
                error_detail = _format_error_detail({"message": msg})
            else:
                logger.exception(
                    "Step %s failed with unexpected exception", step_name
                )
                error_detail = f"{type(exc).__name__}: {msg}"

            self.output_line.emit(
                f"[STEP FAILED] {step_name}: {error_detail}", "red"
            )
            return (
                StepResult(
                    step_name=step_name,
                    status=StepStatus.FAILED,
                    error=error_detail,
                ),
                None,
            )

        if failure_check is not None:
            error_summary = failure_check(return_value)
            if error_summary:
                self.output_line.emit(
                    f"[STEP FAILED] {step_name}: {error_summary}", "red"
                )
                return (
                    StepResult(
                        step_name=step_name,
                        status=StepStatus.FAILED,
                        error=error_summary,
                    ),
                    return_value,
                )

        return (
            StepResult(step_name=step_name, status=StepStatus.OK),
            return_value,
        )

    # ── Main pipeline ─────────────────────────────────────────────────

    def _run_full(
        self, client: EspoAdminClient, field_mgr: FieldManager
    ) -> None:
        """Execute entity operations then field operations.

        Each step runs inside :meth:`_run_step` so that a failure in any
        single phase does not abort the entire run. Only authentication
        failures are promoted to a hard abort.

        :param client: API client.
        :param field_mgr: Field manager for field operations.
        """
        entity_mgr = EntityManager(client, self.output_line.emit)
        all_step_results: list[StepResult] = []
        report: RunReport | None = None

        try:
            had_entity_ops_state = {"value": False}

            # --- Step 1: Entity deletions ------------------------------------
            if self.skip_deletes:
                self.output_line.emit("", "white")
                self.output_line.emit(
                    "[INFO]    Delete operations skipped "
                    "— running in field-update mode",
                    "yellow",
                )
                all_step_results.append(
                    StepResult(
                        step_name="entity_deletions",
                        status=StepStatus.SKIPPED,
                    )
                )
            else:
                delete_actions = {
                    EntityAction.DELETE,
                    EntityAction.DELETE_AND_CREATE,
                }
                deletes = [
                    e for e in self.program.entities
                    if e.action in delete_actions
                ]
                delete_fail_count = {"value": 0}

                def _entity_deletions_body() -> None:
                    self.output_line.emit("", "white")
                    self.output_line.emit("=== ENTITY DELETIONS ===", "white")
                    for entity_def in deletes:
                        ok = entity_mgr._delete_entity(entity_def)
                        if not ok:
                            delete_fail_count["value"] += 1
                    entity_mgr.rebuild_cache()
                    had_entity_ops_state["value"] = True

                def _entity_deletions_failure_check(_: Any) -> str | None:
                    n = delete_fail_count["value"]
                    return (
                        f"{n} entity deletion(s) failed" if n > 0 else None
                    )

                step_result, _ = self._run_step(
                    "entity_deletions",
                    bool(deletes),
                    _entity_deletions_body,
                    failure_check=_entity_deletions_failure_check,
                )
                all_step_results.append(step_result)

            # --- Step 2: Entity creations ------------------------------------
            create_actions = {
                EntityAction.CREATE,
                EntityAction.DELETE_AND_CREATE,
            }
            creates = [
                e for e in self.program.entities
                if e.action in create_actions
            ]
            create_fail_count = {"value": 0}

            def _entity_creations_body() -> None:
                self.output_line.emit("", "white")
                self.output_line.emit("=== ENTITY CREATION ===", "white")
                for entity_def in creates:
                    ok = entity_mgr._create_entity(entity_def)
                    if not ok:
                        create_fail_count["value"] += 1
                entity_mgr.rebuild_cache()
                had_entity_ops_state["value"] = True

            def _entity_creations_failure_check(_: Any) -> str | None:
                n = create_fail_count["value"]
                return (
                    f"{n} entity creation(s) failed" if n > 0 else None
                )

            step_result, _ = self._run_step(
                "entity_creations",
                bool(creates),
                _entity_creations_body,
                failure_check=_entity_creations_failure_check,
            )
            all_step_results.append(step_result)
            had_entity_ops = had_entity_ops_state["value"]

            # --- Step 3: Entity settings -------------------------------------
            has_settings = any(
                e.settings is not None and e.action != EntityAction.DELETE
                for e in self.program.entities
            )

            def _entity_settings_body() -> list[Any]:
                self.output_line.emit("", "white")
                self.output_line.emit("=== ENTITY SETTINGS ===", "white")
                settings_mgr = EntitySettingsManager(
                    client, self.output_line.emit
                )
                return settings_mgr.process_settings(self.program)

            step_result, settings_results = self._run_step(
                "entity_settings",
                has_settings,
                _entity_settings_body,
                failure_check=lambda results: _check_results_for_errors(
                    results, {SettingsStatus.ERROR}, "entity setting"
                ),
            )
            all_step_results.append(step_result)
            self._settings_results = settings_results or []

            # --- Step 4: Email templates -------------------------------------
            has_email_templates = any(
                e.email_templates and e.action != EntityAction.DELETE
                for e in self.program.entities
            )

            def _email_templates_body() -> list[Any]:
                self.output_line.emit("", "white")
                self.output_line.emit("=== EMAIL TEMPLATES ===", "white")
                et_mgr = EmailTemplateManager(client, self.output_line.emit)
                return et_mgr.process_email_templates(self.program)

            step_result, et_results = self._run_step(
                "email_templates",
                has_email_templates,
                _email_templates_body,
                failure_check=lambda results: _check_results_for_errors(
                    results, {EmailTemplateStatus.ERROR}, "email template"
                ),
            )
            all_step_results.append(step_result)
            self._email_template_results = et_results or []

            # --- Step 5: Duplicate checks ------------------------------------
            has_dup_checks = any(
                e.duplicate_checks and e.action != EntityAction.DELETE
                for e in self.program.entities
            )

            def _duplicate_checks_body() -> list[Any]:
                self.output_line.emit("", "white")
                self.output_line.emit(
                    "=== DUPLICATE CHECK RULES ===", "white"
                )
                dup_mgr = DuplicateCheckManager(
                    client, self.output_line.emit
                )
                return dup_mgr.process_duplicate_checks(self.program)

            step_result, dup_results = self._run_step(
                "duplicate_checks",
                has_dup_checks,
                _duplicate_checks_body,
                failure_check=lambda results: _check_results_for_errors(
                    results, {DuplicateCheckStatus.ERROR}, "duplicate check"
                ),
            )
            all_step_results.append(step_result)
            self._duplicate_check_results = dup_results or []

            # --- Step 6: Saved views -----------------------------------------
            has_saved_views = any(
                e.saved_views and e.action != EntityAction.DELETE
                for e in self.program.entities
            )

            def _saved_views_body() -> list[Any]:
                self.output_line.emit("", "white")
                self.output_line.emit("=== SAVED VIEWS ===", "white")
                sv_mgr = SavedViewManager(client, self.output_line.emit)
                return sv_mgr.process_saved_views(self.program)

            step_result, sv_results = self._run_step(
                "saved_views",
                has_saved_views,
                _saved_views_body,
                failure_check=lambda results: _check_results_for_errors(
                    results, {SavedViewStatus.ERROR}, "saved view"
                ),
            )
            all_step_results.append(step_result)
            self._saved_view_results = sv_results or []

            # --- Step 7: Fields ----------------------------------------------
            has_fields = any(
                e.fields and e.action != EntityAction.DELETE
                for e in self.program.entities
            )

            def _fields_body() -> RunReport:
                if had_entity_ops:
                    self.output_line.emit("", "white")
                    self.output_line.emit(
                        "=== FIELD OPERATIONS ===", "white"
                    )
                return field_mgr.run(self.program)

            def _fields_failure_check(fr: Any) -> str | None:
                if fr is None:
                    return None
                errs = fr.summary.errors
                vfail = fr.summary.verification_failed
                if errs == 0 and vfail == 0:
                    return None
                parts: list[str] = []
                if errs:
                    parts.append(f"{errs} field(s) failed")
                if vfail:
                    parts.append(f"{vfail} verification failure(s)")
                return ", ".join(parts)

            step_result, fields_report = self._run_step(
                "fields",
                has_fields,
                _fields_body,
                failure_check=_fields_failure_check,
            )
            all_step_results.append(step_result)

            if fields_report is not None:
                report = fields_report
            else:
                # Either fields were skipped (no work) or fields failed.
                # Either way we still need a valid report to attach the
                # remaining results and step summary to.
                report = field_mgr._build_report(self.program, "run", [])

            # Attach pre-field results to the report
            self._attach_settings_results(report)
            self._attach_duplicate_check_results(report)
            self._attach_saved_view_results(report)
            self._attach_email_template_results(report)

            # --- Step 8: Layouts ---------------------------------------------
            has_layouts = any(
                e.layouts and e.action != EntityAction.DELETE
                for e in self.program.entities
            )

            def _layouts_body() -> None:
                self.output_line.emit("", "white")
                self.output_line.emit("=== LAYOUT OPERATIONS ===", "white")
                layout_mgr = LayoutManager(client, self.output_line.emit)

                for entity_def in self.program.entities:
                    if entity_def.action == EntityAction.DELETE:
                        continue
                    if not entity_def.layouts:
                        continue
                    layout_results = layout_mgr.process_layouts(
                        entity_def, entity_def.fields
                    )
                    report.layout_results.extend(layout_results)

                # Update summary
                for lr in report.layout_results:
                    if lr.status == EntityLayoutStatus.UPDATED:
                        report.summary.layouts_updated += 1
                    elif lr.status == EntityLayoutStatus.SKIPPED:
                        report.summary.layouts_skipped += 1
                    elif lr.status in (
                        EntityLayoutStatus.ERROR,
                        EntityLayoutStatus.VERIFICATION_FAILED,
                    ):
                        report.summary.layouts_failed += 1

                # Emit layout summary
                self.output_line.emit("", "white")
                self.output_line.emit(
                    "===========================================", "white"
                )
                self.output_line.emit("LAYOUT SUMMARY", "white")
                self.output_line.emit(
                    "===========================================", "white"
                )
                total_layouts = len(report.layout_results)
                self.output_line.emit(
                    f"Total layouts processed : {total_layouts}", "white"
                )
                self.output_line.emit(
                    f"  Updated              : "
                    f"{report.summary.layouts_updated}",
                    "green" if report.summary.layouts_updated else "white",
                )
                self.output_line.emit(
                    f"  Skipped (no change)  : "
                    f"{report.summary.layouts_skipped}",
                    "gray",
                )
                self.output_line.emit(
                    f"  Failed               : "
                    f"{report.summary.layouts_failed}",
                    "red" if report.summary.layouts_failed else "white",
                )
                self.output_line.emit(
                    "===========================================", "white"
                )

            def _layouts_failure_check(_: Any) -> str | None:
                return _check_results_for_errors(
                    report.layout_results,
                    {
                        EntityLayoutStatus.ERROR,
                        EntityLayoutStatus.VERIFICATION_FAILED,
                    },
                    "layout",
                )

            step_result, _ = self._run_step(
                "layouts",
                has_layouts,
                _layouts_body,
                failure_check=_layouts_failure_check,
            )
            all_step_results.append(step_result)

            # --- Step 9: Relationships ---------------------------------------
            has_relationships = bool(self.program.relationships)

            def _relationships_body() -> None:
                self.output_line.emit("", "white")
                self.output_line.emit(
                    "=== RELATIONSHIP OPERATIONS ===", "white"
                )
                rel_mgr = RelationshipManager(client, self.output_line.emit)
                rel_results = rel_mgr.process_relationships(
                    self.program.relationships
                )
                report.relationship_results.extend(rel_results)

                for rr in rel_results:
                    if rr.status == RelationshipStatus.CREATED:
                        report.summary.relationships_created += 1
                    elif rr.status == RelationshipStatus.SKIPPED:
                        report.summary.relationships_skipped += 1
                    elif rr.status in (
                        RelationshipStatus.ERROR,
                        RelationshipStatus.WARNING,
                    ):
                        report.summary.relationships_failed += 1

                self.output_line.emit("", "white")
                self.output_line.emit(
                    "===========================================", "white"
                )
                self.output_line.emit("RELATIONSHIP SUMMARY", "white")
                self.output_line.emit(
                    "===========================================", "white"
                )
                total_rels = len(rel_results)
                self.output_line.emit(
                    f"Total relationships processed : {total_rels}", "white"
                )
                self.output_line.emit(
                    f"  Created                     : "
                    f"{report.summary.relationships_created}",
                    "green"
                    if report.summary.relationships_created
                    else "white",
                )
                self.output_line.emit(
                    f"  Skipped (already exists)    : "
                    f"{report.summary.relationships_skipped}",
                    "gray",
                )
                self.output_line.emit(
                    f"  Failed                      : "
                    f"{report.summary.relationships_failed}",
                    "red"
                    if report.summary.relationships_failed
                    else "white",
                )
                self.output_line.emit(
                    "===========================================", "white"
                )

            def _relationships_failure_check(_: Any) -> str | None:
                return _check_results_for_errors(
                    report.relationship_results,
                    {
                        RelationshipStatus.ERROR,
                        RelationshipStatus.WARNING,
                    },
                    "relationship",
                )

            step_result, _ = self._run_step(
                "relationships",
                has_relationships,
                _relationships_body,
                failure_check=_relationships_failure_check,
            )
            all_step_results.append(step_result)

            # --- Step 10: Workflows ------------------------------------------
            has_workflows = any(
                e.workflows and e.action != EntityAction.DELETE
                for e in self.program.entities
            )

            def _workflows_body() -> None:
                self.output_line.emit("", "white")
                self.output_line.emit(
                    "=== WORKFLOW OPERATIONS ===", "white"
                )
                wf_mgr = WorkflowManager(client, self.output_line.emit)
                wf_results = wf_mgr.process_workflows(self.program)

                report.workflow_results.extend(wf_results)
                for wr in wf_results:
                    if wr.status == WorkflowStatus.CREATED:
                        report.summary.workflows_created += 1
                    elif wr.status == WorkflowStatus.UPDATED:
                        report.summary.workflows_updated += 1
                    elif wr.status == WorkflowStatus.SKIPPED:
                        report.summary.workflows_skipped += 1
                    elif wr.status == WorkflowStatus.DRIFT:
                        report.summary.workflows_drift += 1
                    elif wr.status == WorkflowStatus.ERROR:
                        report.summary.workflows_failed += 1

            def _workflows_failure_check(_: Any) -> str | None:
                return _check_results_for_errors(
                    report.workflow_results,
                    {WorkflowStatus.ERROR},
                    "workflow",
                )

            step_result, _ = self._run_step(
                "workflows",
                has_workflows,
                _workflows_body,
                failure_check=_workflows_failure_check,
            )
            all_step_results.append(step_result)

            # --- Step 11: Filtered tabs --------------------------------------
            has_filtered_tabs = any(
                e.filtered_tabs and e.action != EntityAction.DELETE
                for e in self.program.entities
            )

            def _filtered_tabs_body() -> list[Any]:
                self.output_line.emit("", "white")
                self.output_line.emit("=== FILTERED TABS ===", "white")
                ft_mgr = FilteredTabManager(client, self.output_line.emit)
                return ft_mgr.process_filtered_tabs(self.program)

            step_result, ft_results = self._run_step(
                "filtered_tabs",
                has_filtered_tabs,
                _filtered_tabs_body,
                failure_check=lambda results: _check_results_for_errors(
                    results, {FilteredTabStatus.ERROR}, "filtered tab"
                ),
            )
            all_step_results.append(step_result)
            self._filtered_tab_results = ft_results or []
            self._attach_filtered_tab_results(report)

        except AuthenticationError as exc:
            # Hard-abort path. Attach what we have so far for diagnostics.
            if report is None:
                report = field_mgr._build_report(self.program, "run", [])
            report.step_results = all_step_results
            self.finished_error.emit(
                f"Authentication failed (HTTP 401): {exc}"
            )
            return

        # --- Emit step summary ----------------------------------------------
        self._emit_step_summary(all_step_results)

        # Attach step results to the report
        if report is None:
            report = field_mgr._build_report(self.program, "run", [])
        report.step_results = all_step_results

        # --- Emit manual-configuration advisory -----------------------------
        self._emit_manual_config_block(report)

        self.finished_ok.emit(report)

    # ── Result attachment helpers ─────────────────────────────────────

    def _attach_settings_results(self, report: RunReport) -> None:
        if not self._settings_results:
            return
        report.settings_results.extend(self._settings_results)
        for sr in self._settings_results:
            if sr.status == SettingsStatus.UPDATED:
                report.summary.settings_updated += 1
            elif sr.status == SettingsStatus.SKIPPED:
                report.summary.settings_skipped += 1
            elif sr.status == SettingsStatus.ERROR:
                report.summary.settings_failed += 1

    def _attach_duplicate_check_results(self, report: RunReport) -> None:
        if not self._duplicate_check_results:
            return
        report.duplicate_check_results.extend(self._duplicate_check_results)
        for dr in self._duplicate_check_results:
            if dr.status == DuplicateCheckStatus.CREATED:
                report.summary.duplicate_checks_created += 1
            elif dr.status == DuplicateCheckStatus.UPDATED:
                report.summary.duplicate_checks_updated += 1
            elif dr.status == DuplicateCheckStatus.SKIPPED:
                report.summary.duplicate_checks_skipped += 1
            elif dr.status == DuplicateCheckStatus.DRIFT:
                report.summary.duplicate_checks_drift += 1
            elif dr.status == DuplicateCheckStatus.ERROR:
                report.summary.duplicate_checks_failed += 1

    def _attach_saved_view_results(self, report: RunReport) -> None:
        if not self._saved_view_results:
            return
        report.saved_view_results.extend(self._saved_view_results)
        for svr in self._saved_view_results:
            if svr.status == SavedViewStatus.CREATED:
                report.summary.saved_views_created += 1
            elif svr.status == SavedViewStatus.UPDATED:
                report.summary.saved_views_updated += 1
            elif svr.status == SavedViewStatus.SKIPPED:
                report.summary.saved_views_skipped += 1
            elif svr.status == SavedViewStatus.DRIFT:
                report.summary.saved_views_drift += 1
            elif svr.status == SavedViewStatus.ERROR:
                report.summary.saved_views_failed += 1

    def _attach_email_template_results(self, report: RunReport) -> None:
        if not self._email_template_results:
            return
        report.email_template_results.extend(self._email_template_results)
        for etr in self._email_template_results:
            if etr.status == EmailTemplateStatus.CREATED:
                report.summary.email_templates_created += 1
            elif etr.status == EmailTemplateStatus.UPDATED:
                report.summary.email_templates_updated += 1
            elif etr.status == EmailTemplateStatus.SKIPPED:
                report.summary.email_templates_skipped += 1
            elif etr.status == EmailTemplateStatus.DRIFT:
                report.summary.email_templates_drift += 1
            elif etr.status == EmailTemplateStatus.ERROR:
                report.summary.email_templates_failed += 1

    def _attach_filtered_tab_results(self, report: RunReport) -> None:
        results = getattr(self, "_filtered_tab_results", None)
        if not results:
            return
        report.filtered_tab_results.extend(results)
        for ft in results:
            if ft.status == FilteredTabStatus.CREATED:
                report.summary.filtered_tabs_created += 1
            elif ft.status == FilteredTabStatus.SKIPPED:
                report.summary.filtered_tabs_skipped += 1
            elif ft.status == FilteredTabStatus.DRIFT:
                report.summary.filtered_tabs_drift += 1
            elif ft.status == FilteredTabStatus.ERROR:
                report.summary.filtered_tabs_failed += 1
            elif ft.status == FilteredTabStatus.NOT_SUPPORTED:
                report.summary.filtered_tabs_not_supported += 1

    # ── Step summary emission ────────────────────────────────────────

    def _emit_step_summary(self, step_results: list[StepResult]) -> None:
        """Emit the STEP SUMMARY block at the end of a full run.

        :param step_results: Per-step outcomes in pipeline order.
        """
        self.output_line.emit("", "white")
        self.output_line.emit(
            "===========================================", "white"
        )
        self.output_line.emit("STEP SUMMARY", "white")
        self.output_line.emit(
            "===========================================", "white"
        )

        failure_count = 0
        for sr in step_results:
            display_name = _STEP_DISPLAY_NAMES.get(sr.step_name, sr.step_name)
            if sr.status == StepStatus.OK:
                self.output_line.emit(
                    f"  {display_name:<26}: OK", "green"
                )
            elif sr.status == StepStatus.SKIPPED:
                self.output_line.emit(
                    f"  {display_name:<26}: SKIPPED", "gray"
                )
            else:
                failure_count += 1
                self.output_line.emit(
                    f"  {display_name:<26}: FAILED ({sr.error})", "red"
                )

        self.output_line.emit(
            "===========================================", "white"
        )
        if failure_count > 0:
            self.output_line.emit(
                f"Run completed with {failure_count} step failure(s)",
                "yellow",
            )
        else:
            self.output_line.emit("Run completed successfully", "green")

    # ── Manual-configuration advisory ────────────────────────────────

    def _emit_manual_config_block(self, report: RunReport) -> None:
        """Emit a consolidated advisory listing items requiring manual config.

        Walks the saved-view, duplicate-check, and workflow result lists
        on the report and surfaces every entry whose status is
        ``NOT_SUPPORTED`` in a single advisory block. Suppressed
        entirely if no such entries exist.

        :param report: The run report after all steps have executed.
        """
        saved_view_items = [
            f"  {r.entity}.savedViews[{r.view_id}]"
            for r in report.saved_view_results
            if r.status == SavedViewStatus.NOT_SUPPORTED
        ]
        dup_check_items = [
            f"  {r.entity}.duplicateChecks[{r.rule_id}]"
            for r in report.duplicate_check_results
            if r.status == DuplicateCheckStatus.NOT_SUPPORTED
        ]
        workflow_items = [
            f"  {r.entity}.workflows[{r.workflow_id}]"
            for r in report.workflow_results
            if r.status == WorkflowStatus.NOT_SUPPORTED
        ]
        filtered_tab_items = [
            f"  {r.entity}.filteredTabs[{r.tab_id}] (scope: {r.scope})"
            for r in report.filtered_tab_results
            if r.status == FilteredTabStatus.NOT_SUPPORTED
        ]

        # Filtered tabs always need a manual rebuild + Tab List add even
        # on the success path; surface every entry that was processed
        # (CREATED or SKIPPED), not just NOT_SUPPORTED, so the operator
        # does not miss the post-deploy step.
        filtered_tab_post_install = [
            f"  {r.entity}.filteredTabs[{r.tab_id}] (scope: {r.scope})"
            for r in report.filtered_tab_results
            if r.status in (
                FilteredTabStatus.CREATED,
                FilteredTabStatus.SKIPPED,
            )
        ]

        if not (
            saved_view_items
            or dup_check_items
            or workflow_items
            or filtered_tab_items
            or filtered_tab_post_install
        ):
            return

        self.output_line.emit("", "white")
        self.output_line.emit(
            "===========================================", "yellow"
        )
        self.output_line.emit(
            "MANUAL CONFIGURATION REQUIRED", "yellow"
        )
        self.output_line.emit(
            "===========================================", "yellow"
        )
        self.output_line.emit(
            "The following items declared in the YAML cannot be applied",
            "yellow",
        )
        self.output_line.emit(
            "via EspoCRM's REST API. Configure them manually via the",
            "yellow",
        )
        self.output_line.emit(
            "admin UI or by editing metadata files on disk:", "yellow"
        )
        self.output_line.emit("", "yellow")

        self.output_line.emit("Saved views:", "yellow")
        for line in (saved_view_items or ["  (none)"]):
            self.output_line.emit(line, "yellow")
        self.output_line.emit("", "yellow")

        self.output_line.emit("Duplicate checks:", "yellow")
        for line in (dup_check_items or ["  (none)"]):
            self.output_line.emit(line, "yellow")
        self.output_line.emit("", "yellow")

        self.output_line.emit("Workflows:", "yellow")
        for line in (workflow_items or ["  (none)"]):
            self.output_line.emit(line, "yellow")
        self.output_line.emit("", "yellow")

        self.output_line.emit("Filtered tabs (Report Filter unavailable):", "yellow")
        for line in (filtered_tab_items or ["  (none)"]):
            self.output_line.emit(line, "yellow")
        self.output_line.emit("", "yellow")

        self.output_line.emit(
            "Filtered tabs — copy bundle, rebuild, add to Tab List:", "yellow",
        )
        for line in (filtered_tab_post_install or ["  (none)"]):
            self.output_line.emit(line, "yellow")
        self.output_line.emit(
            "  See reports/filtered_tabs/<run_ts>/README.txt for steps.",
            "yellow",
        )

        self.output_line.emit(
            "===========================================", "yellow"
        )


__all__ = ["RunWorker"]

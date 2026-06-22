"""Qt-free deploy orchestration — the 12-step CHECK→ACT pipeline.

Extracted from ``espo_impl.workers.run_worker.RunWorker._run_full`` (PRJ-042,
DEC-572) so the deploy orchestration is a single source of truth callable from
both V1 (the Qt ``RunWorker``, which delegates here) and V2 publish (which calls
:func:`deploy_pipeline` directly, headless). Nothing in this module imports Qt.

The pipeline drives a sequence of managers (entity, fields, layouts,
relationships, security, etc.). The manager classes are injected through
:class:`DeployManagers` so a caller can substitute them — ``RunWorker`` passes
the classes from its own module namespace, which keeps the V1 test suite's
``patch("espo_impl.workers.run_worker.<Manager>")`` seams working unchanged.
Output is emitted through an ``output_fn(message, color)`` callback rather than a
Qt signal.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from espo_impl.core.api_client import EspoAdminClient, _format_error_detail
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
    ProgramFile,
    RelationshipStatus,
    RoleStatus,
    RunReport,
    SavedViewStatus,
    SettingsStatus,
    StepResult,
    StepStatus,
    TeamStatus,
    WorkflowStatus,
)
from espo_impl.core.relationship_manager import (
    RelationshipManager,
    RelationshipManagerError,
)
from espo_impl.core.role_manager import RoleManager, RoleManagerError
from espo_impl.core.saved_view_manager import (
    SavedViewManager,
    SavedViewManagerError,
)
from espo_impl.core.team_manager import TeamManager, TeamManagerError
from espo_impl.core.workflow_manager import (
    WorkflowManager,
    WorkflowManagerError,
)

logger = logging.getLogger(__name__)

# An ``output_fn(message, color)`` callback — the Qt-free seam for log output.
OutputFn = Callable[[str, str], None]


MANAGER_ERROR_TYPES: tuple[type[Exception], ...] = (
    EntityManagerError,
    EntitySettingsManagerError,
    EmailTemplateManagerError,
    DuplicateCheckManagerError,
    SavedViewManagerError,
    LayoutManagerError,
    RelationshipManagerError,
    RoleManagerError,
    TeamManagerError,
    WorkflowManagerError,
    FilteredTabManagerError,
)


STEP_DISPLAY_NAMES: dict[str, str] = {
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
    "security": "Security (teams and roles)",
    "filtered_tabs": "Filtered tabs",
}


@dataclass(frozen=True)
class DeployManagers:
    """The manager classes the pipeline instantiates.

    Defaults are the real managers. ``RunWorker`` passes the classes from its
    own namespace so the V1 test patches (``patch("...run_worker.X")``) reach
    the pipeline; V2 callers use the defaults.
    """

    entity: type = EntityManager
    entity_settings: type = EntitySettingsManager
    email_template: type = EmailTemplateManager
    duplicate_check: type = DuplicateCheckManager
    saved_view: type = SavedViewManager
    layout: type = LayoutManager
    relationship: type = RelationshipManager
    role: type = RoleManager
    team: type = TeamManager
    workflow: type = WorkflowManager
    filtered_tab: type = FilteredTabManager


@dataclass
class DeployOutcome:
    """The result of a full deploy run.

    :ivar report: The assembled :class:`RunReport` (all results attached).
    :ivar security_team_results: Team results from the Security step.
    :ivar security_role_results: Role results from the Security step.
    """

    report: RunReport
    security_team_results: list[Any] = field(default_factory=list)
    security_role_results: list[Any] = field(default_factory=list)


def is_authentication_message(message: str) -> bool:
    """Detect auth-flavored error messages so they can be promoted to fatal.

    :param message: Exception text from a manager.
    :returns: True if the message looks like an authentication failure.
    """
    return "401" in message or "Authentication" in message


def check_results_for_errors(
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


def run_step(
    step_name: str,
    has_work: bool,
    body: Callable[[], Any],
    output_fn: OutputFn,
    failure_check: Callable[[Any], str | None] | None = None,
) -> tuple[StepResult, Any]:
    """Run one phase of the pipeline, isolating failures.

    :param step_name: Canonical snake_case step name.
    :param has_work: If False, the step is skipped (no-op, no header emitted).
    :param body: Zero-arg callable that runs the step. Returns step-specific
        results (or None). May raise *ManagerError or any Exception.
    :param output_fn: ``(message, color)`` log callback.
    :param failure_check: Optional callable invoked only on the success path
        with the body's return value. If it returns a non-None string, the
        step is downgraded from OK to FAILED with that string as the error and
        a ``[STEP FAILED]`` line is emitted. The body's return value is still
        returned to the caller so it can be attached to the report.
    :returns: Tuple of (StepResult, body return value or None on failure).
    :raises AuthenticationError: Re-raised so the caller can hard-abort.
    """
    if not has_work:
        return (
            StepResult(step_name=step_name, status=StepStatus.NO_WORK),
            None,
        )

    try:
        return_value = body()
    except AuthenticationError:
        output_fn(
            f"[FATAL]   Authentication failed during {step_name} "
            f"— aborting run",
            "red",
        )
        raise
    except Exception as exc:
        msg = str(exc)
        if is_authentication_message(msg):
            output_fn(
                f"[FATAL]   Authentication failed during {step_name} "
                f"— aborting run",
                "red",
            )
            raise AuthenticationError(msg) from exc

        if isinstance(exc, MANAGER_ERROR_TYPES):
            logger.warning(
                "Step %s failed with manager error: %s", step_name, exc
            )
            error_detail = _format_error_detail({"message": msg})
        else:
            logger.exception(
                "Step %s failed with unexpected exception", step_name
            )
            error_detail = f"{type(exc).__name__}: {msg}"

        output_fn(f"[STEP FAILED] {step_name}: {error_detail}", "red")
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
            output_fn(f"[STEP FAILED] {step_name}: {error_summary}", "red")
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


# ── Result attachment helpers ────────────────────────────────────────────


def attach_settings_results(report: RunReport, results: list[Any]) -> None:
    if not results:
        return
    report.settings_results.extend(results)
    for sr in results:
        if sr.status == SettingsStatus.UPDATED:
            report.summary.settings_updated += 1
        elif sr.status == SettingsStatus.SKIPPED:
            report.summary.settings_skipped += 1
        elif sr.status == SettingsStatus.ERROR:
            report.summary.settings_failed += 1


def attach_duplicate_check_results(report: RunReport, results: list[Any]) -> None:
    if not results:
        return
    report.duplicate_check_results.extend(results)
    for dr in results:
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


def attach_saved_view_results(report: RunReport, results: list[Any]) -> None:
    if not results:
        return
    report.saved_view_results.extend(results)
    for svr in results:
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


def attach_email_template_results(report: RunReport, results: list[Any]) -> None:
    if not results:
        return
    report.email_template_results.extend(results)
    for etr in results:
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


def attach_filtered_tab_results(report: RunReport, results: list[Any]) -> None:
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


# ── Step summary emission ────────────────────────────────────────────────


def emit_step_summary(output_fn: OutputFn, step_results: list[StepResult]) -> None:
    """Emit the STEP SUMMARY block at the end of a full run.

    :param output_fn: ``(message, color)`` log callback.
    :param step_results: Per-step outcomes in pipeline order.
    """
    output_fn("", "white")
    output_fn("===========================================", "white")
    output_fn("STEP SUMMARY", "white")
    output_fn("===========================================", "white")

    failure_count = 0
    for sr in step_results:
        display_name = STEP_DISPLAY_NAMES.get(sr.step_name, sr.step_name)
        if sr.status == StepStatus.OK:
            output_fn(f"  {display_name:<26}: OK", "green")
        elif sr.status == StepStatus.NO_WORK:
            output_fn(f"  {display_name:<26}: NO WORK SPECIFIED", "gray")
        elif sr.status == StepStatus.SKIPPED:
            output_fn(f"  {display_name:<26}: SKIPPED", "gray")
        else:
            failure_count += 1
            output_fn(
                f"  {display_name:<26}: FAILED ({sr.error})", "red"
            )

    output_fn("===========================================", "white")
    if failure_count > 0:
        output_fn(
            f"Run completed with {failure_count} step failure(s)", "yellow"
        )
    else:
        output_fn("Run completed successfully", "green")


# ── Manual-configuration advisory ────────────────────────────────────────


def emit_manual_config_block(output_fn: OutputFn, report: RunReport) -> None:
    """Emit a consolidated advisory listing items requiring manual config.

    Walks the saved-view, duplicate-check, and workflow result lists on the
    report and surfaces every entry whose status is ``NOT_SUPPORTED`` in a
    single advisory block. Suppressed entirely if no such entries exist.

    :param output_fn: ``(message, color)`` log callback.
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

    # Filtered tabs always need a manual rebuild + Tab List add even on the
    # success path; surface every entry that was processed (CREATED or
    # SKIPPED), not just NOT_SUPPORTED, so the operator does not miss the
    # post-deploy step.
    filtered_tab_post_install = [
        f"  {r.entity}.filteredTabs[{r.tab_id}] (scope: {r.scope})"
        for r in report.filtered_tab_results
        if r.status in (
            FilteredTabStatus.CREATED,
            FilteredTabStatus.SKIPPED,
        )
    ]

    # Section 12.5 NOT_SUPPORTED items (DEC-6):
    # - Field-level visibleWhen with role clauses
    # - Panel-level visibleWhen with role clauses
    # - Variant-form layouts (`forRoles:`) — surfaced as
    #   LayoutResult NOT_SUPPORTED
    role_field_items = [
        f"  {r.entity_name}.{r.field_name} (field visibleWhen)"
        for r in report.not_supported_role_clauses
        if not r.is_panel
    ]
    role_panel_items = [
        f"  {r.entity_name}.panel[{r.field_name}] visibleWhen"
        for r in report.not_supported_role_clauses
        if r.is_panel
    ]
    variant_layout_items = [
        f"  {r.entity}.layout.{r.layout_type} (forRoles variant)"
        for r in report.layout_results
        if r.status == EntityLayoutStatus.NOT_SUPPORTED
    ]

    if not (
        saved_view_items
        or dup_check_items
        or workflow_items
        or filtered_tab_items
        or filtered_tab_post_install
        or role_field_items
        or role_panel_items
        or variant_layout_items
    ):
        return

    output_fn("", "white")
    output_fn("===========================================", "yellow")
    output_fn("MANUAL CONFIGURATION REQUIRED", "yellow")
    output_fn("===========================================", "yellow")
    output_fn(
        "The following items declared in the YAML cannot be applied", "yellow"
    )
    output_fn(
        "via EspoCRM's REST API. Configure them manually via the", "yellow"
    )
    output_fn(
        "admin UI or by editing metadata files on disk:", "yellow"
    )
    output_fn("", "yellow")

    output_fn("Saved views:", "yellow")
    for line in (saved_view_items or ["  (none)"]):
        output_fn(line, "yellow")
    output_fn("", "yellow")

    output_fn("Duplicate checks:", "yellow")
    for line in (dup_check_items or ["  (none)"]):
        output_fn(line, "yellow")
    output_fn("", "yellow")

    output_fn("Workflows:", "yellow")
    for line in (workflow_items or ["  (none)"]):
        output_fn(line, "yellow")
    output_fn("", "yellow")

    output_fn("Filtered tabs (Report Filter unavailable):", "yellow")
    for line in (filtered_tab_items or ["  (none)"]):
        output_fn(line, "yellow")
    output_fn("", "yellow")

    output_fn(
        "Filtered tabs — copy bundle, rebuild, add to Tab List:", "yellow"
    )
    for line in (filtered_tab_post_install or ["  (none)"]):
        output_fn(line, "yellow")
    output_fn(
        "  See reports/filtered_tabs/<run_ts>/README.txt for steps.", "yellow"
    )
    output_fn("", "yellow")

    # Section 12.5 — Role-aware visibility (NOT_SUPPORTED on EspoCRM 9.x per
    # DEC-6; deferred to v1.4).
    output_fn(
        "Section 12.5 role-aware visibility "
        "(NOT_SUPPORTED on EspoCRM 9.x):",
        "yellow",
    )
    output_fn("  Fields with role-clause visibleWhen:", "yellow")
    for line in (role_field_items or ["    (none)"]):
        output_fn(line, "yellow")
    output_fn("  Panels with role-clause visibleWhen:", "yellow")
    for line in (role_panel_items or ["    (none)"]):
        output_fn(line, "yellow")
    output_fn("  Layouts with forRoles variants:", "yellow")
    for line in (variant_layout_items or ["    (none)"]):
        output_fn(line, "yellow")
    output_fn(
        "  Configure manually via Dynamic Handler JS modules or "
        "Layout Sets + Teams (see schema §12.5 Deploy Support).",
        "yellow",
    )

    output_fn("===========================================", "yellow")


# ── Main pipeline ─────────────────────────────────────────────────────────


def deploy_pipeline(
    program: ProgramFile,
    client: EspoAdminClient,
    field_mgr: FieldManager,
    output_fn: OutputFn,
    *,
    skip_deletes: bool = False,
    managers: DeployManagers | None = None,
) -> DeployOutcome:
    """Execute entity operations then field operations — the 12-step pipeline.

    Each step runs inside :func:`run_step` so that a failure in any single
    phase does not abort the entire run. Only authentication failures are
    promoted to a hard abort: an :class:`AuthenticationError` propagates out of
    this function (after the ``[FATAL]`` line is emitted), and the caller is
    expected to handle it (V1 emits ``finished_error``).

    :param program: The validated program file to deploy.
    :param client: API client.
    :param field_mgr: Field manager for field operations and report building.
    :param output_fn: ``(message, color)`` log callback.
    :param skip_deletes: If True, skip all entity delete operations.
    :param managers: Manager classes to instantiate (defaults to the real set).
    :returns: A :class:`DeployOutcome` with the report and security results.
    :raises AuthenticationError: On any authentication failure during a step.
    """
    managers = managers or DeployManagers()
    entity_mgr = managers.entity(client, output_fn)
    all_step_results: list[StepResult] = []
    report: RunReport | None = None

    settings_results: list[Any] = []
    email_template_results: list[Any] = []
    duplicate_check_results: list[Any] = []
    saved_view_results: list[Any] = []
    filtered_tab_results: list[Any] = []
    team_results: list[Any] = []
    role_results: list[Any] = []

    had_entity_ops_state = {"value": False}

    # --- Step 1: Entity deletions ------------------------------------
    if skip_deletes:
        output_fn("", "white")
        output_fn(
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
            e for e in program.entities
            if e.action in delete_actions
        ]
        delete_fail_count = {"value": 0}

        def _entity_deletions_body() -> None:
            output_fn("", "white")
            output_fn("=== ENTITY DELETIONS ===", "white")
            for entity_def in deletes:
                ok = entity_mgr._delete_entity(entity_def)
                if not ok:
                    delete_fail_count["value"] += 1
            entity_mgr.rebuild_cache()
            had_entity_ops_state["value"] = True

        def _entity_deletions_failure_check(_: Any) -> str | None:
            n = delete_fail_count["value"]
            return f"{n} entity deletion(s) failed" if n > 0 else None

        step_result, _ = run_step(
            "entity_deletions",
            bool(deletes),
            _entity_deletions_body,
            output_fn,
            failure_check=_entity_deletions_failure_check,
        )
        all_step_results.append(step_result)

    # --- Step 2: Entity creations ------------------------------------
    create_actions = {
        EntityAction.CREATE,
        EntityAction.DELETE_AND_CREATE,
    }
    creates = [
        e for e in program.entities
        if e.action in create_actions
    ]
    create_fail_count = {"value": 0}

    def _entity_creations_body() -> None:
        output_fn("", "white")
        output_fn("=== ENTITY CREATION ===", "white")
        successful_creates: list[str] = []
        for entity_def in creates:
            ok = entity_mgr._create_entity(entity_def)
            if not ok:
                create_fail_count["value"] += 1
            else:
                # _create_entity returns True both for "created now" and for
                # "already exists." We only need to wait for entities created
                # in this run, but we don't have an easy boolean for that —
                # wait for all that succeeded and let wait_for_metadata_ready
                # short-circuit when an entity is already cached. The poll is
                # a single GET /Metadata, which is cheap.
                successful_creates.append(entity_def.name)
        entity_mgr.rebuild_cache()
        if successful_creates:
            entity_mgr.wait_for_metadata_ready(successful_creates)
        had_entity_ops_state["value"] = True

    def _entity_creations_failure_check(_: Any) -> str | None:
        n = create_fail_count["value"]
        return f"{n} entity creation(s) failed" if n > 0 else None

    step_result, _ = run_step(
        "entity_creations",
        bool(creates),
        _entity_creations_body,
        output_fn,
        failure_check=_entity_creations_failure_check,
    )
    all_step_results.append(step_result)
    had_entity_ops = had_entity_ops_state["value"]

    # --- Step 3: Entity settings -------------------------------------
    has_settings = any(
        e.settings is not None and e.action != EntityAction.DELETE
        for e in program.entities
    )

    def _entity_settings_body() -> list[Any]:
        output_fn("", "white")
        output_fn("=== ENTITY SETTINGS ===", "white")
        settings_mgr = managers.entity_settings(client, output_fn)
        return settings_mgr.process_settings(program)

    step_result, settings_out = run_step(
        "entity_settings",
        has_settings,
        _entity_settings_body,
        output_fn,
        failure_check=lambda results: check_results_for_errors(
            results, {SettingsStatus.ERROR}, "entity setting"
        ),
    )
    all_step_results.append(step_result)
    settings_results = settings_out or []

    # --- Step 4: Email templates -------------------------------------
    has_email_templates = any(
        e.email_templates and e.action != EntityAction.DELETE
        for e in program.entities
    )

    def _email_templates_body() -> list[Any]:
        output_fn("", "white")
        output_fn("=== EMAIL TEMPLATES ===", "white")
        et_mgr = managers.email_template(client, output_fn)
        return et_mgr.process_email_templates(program)

    step_result, et_out = run_step(
        "email_templates",
        has_email_templates,
        _email_templates_body,
        output_fn,
        failure_check=lambda results: check_results_for_errors(
            results, {EmailTemplateStatus.ERROR}, "email template"
        ),
    )
    all_step_results.append(step_result)
    email_template_results = et_out or []

    # --- Step 5: Duplicate checks ------------------------------------
    has_dup_checks = any(
        e.duplicate_checks and e.action != EntityAction.DELETE
        for e in program.entities
    )

    def _duplicate_checks_body() -> list[Any]:
        output_fn("", "white")
        output_fn("=== DUPLICATE CHECK RULES ===", "white")
        dup_mgr = managers.duplicate_check(client, output_fn)
        return dup_mgr.process_duplicate_checks(program)

    step_result, dup_out = run_step(
        "duplicate_checks",
        has_dup_checks,
        _duplicate_checks_body,
        output_fn,
        failure_check=lambda results: check_results_for_errors(
            results, {DuplicateCheckStatus.ERROR}, "duplicate check"
        ),
    )
    all_step_results.append(step_result)
    duplicate_check_results = dup_out or []

    # --- Step 6: Saved views -----------------------------------------
    has_saved_views = any(
        e.saved_views and e.action != EntityAction.DELETE
        for e in program.entities
    )

    def _saved_views_body() -> list[Any]:
        output_fn("", "white")
        output_fn("=== SAVED VIEWS ===", "white")
        sv_mgr = managers.saved_view(client, output_fn)
        return sv_mgr.process_saved_views(program)

    step_result, sv_out = run_step(
        "saved_views",
        has_saved_views,
        _saved_views_body,
        output_fn,
        failure_check=lambda results: check_results_for_errors(
            results, {SavedViewStatus.ERROR}, "saved view"
        ),
    )
    all_step_results.append(step_result)
    saved_view_results = sv_out or []

    # --- Step 7: Fields ----------------------------------------------
    has_fields = any(
        e.fields and e.action != EntityAction.DELETE
        for e in program.entities
    )

    def _fields_body() -> RunReport:
        if had_entity_ops:
            output_fn("", "white")
            output_fn("=== FIELD OPERATIONS ===", "white")
        return field_mgr.run(program)

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

    step_result, fields_report = run_step(
        "fields",
        has_fields,
        _fields_body,
        output_fn,
        failure_check=_fields_failure_check,
    )
    all_step_results.append(step_result)

    if fields_report is not None:
        report = fields_report
    else:
        # Either fields were skipped (no work) or fields failed. Either way we
        # still need a valid report to attach the remaining results and step
        # summary to.
        report = field_mgr._build_report(program, "run", [])

    # Attach pre-field results to the report
    attach_settings_results(report, settings_results)
    attach_duplicate_check_results(report, duplicate_check_results)
    attach_saved_view_results(report, saved_view_results)
    attach_email_template_results(report, email_template_results)

    # --- Step 8: Layouts ---------------------------------------------
    has_layouts = any(
        e.layouts and e.action != EntityAction.DELETE
        for e in program.entities
    )

    def _layouts_body() -> None:
        output_fn("", "white")
        output_fn("=== LAYOUT OPERATIONS ===", "white")
        layout_mgr = managers.layout(client, output_fn)

        for entity_def in program.entities:
            if entity_def.action == EntityAction.DELETE:
                continue
            if not entity_def.layouts:
                continue
            layout_results = layout_mgr.process_layouts(
                entity_def, entity_def.fields
            )
            report.layout_results.extend(layout_results)

        # Merge panel-level role-aware-visibility NOT_SUPPORTED records into
        # the run report (DEC-6). Field-level records were already attached by
        # field_mgr's report builder in Step 7.
        report.not_supported_role_clauses.extend(
            layout_mgr._not_supported_role_clauses
        )

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
        output_fn("", "white")
        output_fn("===========================================", "white")
        output_fn("LAYOUT SUMMARY", "white")
        output_fn("===========================================", "white")
        total_layouts = len(report.layout_results)
        output_fn(f"Total layouts processed : {total_layouts}", "white")
        output_fn(
            f"  Updated              : {report.summary.layouts_updated}",
            "green" if report.summary.layouts_updated else "white",
        )
        output_fn(
            f"  Skipped (no change)  : {report.summary.layouts_skipped}",
            "gray",
        )
        output_fn(
            f"  Failed               : {report.summary.layouts_failed}",
            "red" if report.summary.layouts_failed else "white",
        )
        output_fn("===========================================", "white")

    def _layouts_failure_check(_: Any) -> str | None:
        return check_results_for_errors(
            report.layout_results,
            {
                EntityLayoutStatus.ERROR,
                EntityLayoutStatus.VERIFICATION_FAILED,
            },
            "layout",
        )

    step_result, _ = run_step(
        "layouts",
        has_layouts,
        _layouts_body,
        output_fn,
        failure_check=_layouts_failure_check,
    )
    all_step_results.append(step_result)

    # --- Step 9: Relationships ---------------------------------------
    has_relationships = bool(program.relationships)

    def _relationships_body() -> None:
        output_fn("", "white")
        output_fn("=== RELATIONSHIP OPERATIONS ===", "white")
        rel_mgr = managers.relationship(client, output_fn)
        rel_results = rel_mgr.process_relationships(program.relationships)
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

        output_fn("", "white")
        output_fn("===========================================", "white")
        output_fn("RELATIONSHIP SUMMARY", "white")
        output_fn("===========================================", "white")
        total_rels = len(rel_results)
        output_fn(
            f"Total relationships processed : {total_rels}", "white"
        )
        output_fn(
            f"  Created                     : "
            f"{report.summary.relationships_created}",
            "green" if report.summary.relationships_created else "white",
        )
        output_fn(
            f"  Skipped (already exists)    : "
            f"{report.summary.relationships_skipped}",
            "gray",
        )
        output_fn(
            f"  Failed                      : "
            f"{report.summary.relationships_failed}",
            "red" if report.summary.relationships_failed else "white",
        )
        output_fn("===========================================", "white")

    def _relationships_failure_check(_: Any) -> str | None:
        return check_results_for_errors(
            report.relationship_results,
            {
                RelationshipStatus.ERROR,
                RelationshipStatus.WARNING,
            },
            "relationship",
        )

    step_result, _ = run_step(
        "relationships",
        has_relationships,
        _relationships_body,
        output_fn,
        failure_check=_relationships_failure_check,
    )
    all_step_results.append(step_result)

    # --- Step 10: Workflows ------------------------------------------
    has_workflows = any(
        e.workflows and e.action != EntityAction.DELETE
        for e in program.entities
    )

    def _workflows_body() -> None:
        output_fn("", "white")
        output_fn("=== WORKFLOW OPERATIONS ===", "white")
        wf_mgr = managers.workflow(client, output_fn)
        wf_results = wf_mgr.process_workflows(program)

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
        return check_results_for_errors(
            report.workflow_results,
            {WorkflowStatus.ERROR},
            "workflow",
        )

    step_result, _ = run_step(
        "workflows",
        has_workflows,
        _workflows_body,
        output_fn,
        failure_check=_workflows_failure_check,
    )
    all_step_results.append(step_result)

    # --- Step 11: Security ------------------------------------------
    has_security = bool(program.roles or program.teams)

    def _security_body() -> None:
        output_fn("", "white")
        output_fn("=== SECURITY (teams and roles) ===", "white")
        # Teams first — no dependencies on entities or roles.
        if program.teams:
            team_mgr = managers.team(client, output_fn)
            team_results.extend(team_mgr.process_teams(program.teams))
        # Roles second — pre-flight runs inside process_roles and validates
        # scope_access against server state.
        if program.roles:
            role_mgr = managers.role(client, output_fn)
            role_results.extend(role_mgr.process_roles(program.roles))

    def _security_failure_check(_: Any) -> str | None:
        team_errors = sum(
            1 for r in team_results if r.status == TeamStatus.ERROR
        )
        role_errors = sum(
            1 for r in role_results if r.status == RoleStatus.ERROR
        )
        total = team_errors + role_errors
        if total == 0:
            return None
        parts: list[str] = []
        if team_errors:
            parts.append(f"{team_errors} team error(s)")
        if role_errors:
            parts.append(f"{role_errors} role error(s)")
        return ", ".join(parts)

    step_result, _ = run_step(
        "security",
        has_security,
        _security_body,
        output_fn,
        failure_check=_security_failure_check,
    )
    all_step_results.append(step_result)

    # --- Step 12: Filtered tabs --------------------------------------
    has_filtered_tabs = any(
        e.filtered_tabs and e.action != EntityAction.DELETE
        for e in program.entities
    )

    def _filtered_tabs_body() -> list[Any]:
        output_fn("", "white")
        output_fn("=== FILTERED TABS ===", "white")
        ft_mgr = managers.filtered_tab(client, output_fn)
        return ft_mgr.process_filtered_tabs(program)

    step_result, ft_out = run_step(
        "filtered_tabs",
        has_filtered_tabs,
        _filtered_tabs_body,
        output_fn,
        failure_check=lambda results: check_results_for_errors(
            results, {FilteredTabStatus.ERROR}, "filtered tab"
        ),
    )
    all_step_results.append(step_result)
    filtered_tab_results = ft_out or []
    attach_filtered_tab_results(report, filtered_tab_results)

    # --- Emit step summary ----------------------------------------------
    emit_step_summary(output_fn, all_step_results)

    # Attach step results to the report
    if report is None:
        report = field_mgr._build_report(program, "run", [])
    report.step_results = all_step_results

    # --- Emit manual-configuration advisory -----------------------------
    emit_manual_config_block(output_fn, report)

    return DeployOutcome(
        report=report,
        security_team_results=team_results,
        security_role_results=role_results,
    )


__all__ = [
    "DeployManagers",
    "DeployOutcome",
    "OutputFn",
    "check_results_for_errors",
    "deploy_pipeline",
    "emit_manual_config_block",
    "emit_step_summary",
    "is_authentication_message",
    "run_step",
]

"""Background worker thread for run/verify operations."""

from PySide6.QtCore import QThread, Signal

from espo_impl.core.api_client import EspoAdminClient
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
from espo_impl.core.field_manager import FieldManager
from espo_impl.core.layout_manager import LayoutManager, LayoutManagerError
from espo_impl.core.models import (
    DuplicateCheckStatus,
    EmailTemplateStatus,
    EntityAction,
    EntityLayoutStatus,
    InstanceProfile,
    ProgramFile,
    RelationshipStatus,
    SavedViewStatus,
    SettingsStatus,
)
from espo_impl.core.relationship_manager import (
    RelationshipManager,
    RelationshipManagerError,
)
from espo_impl.core.saved_view_manager import (
    SavedViewManager,
    SavedViewManagerError,
)


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

        except Exception as exc:
            self.finished_error.emit(str(exc))

    def _run_full(
        self, client: EspoAdminClient, field_mgr: FieldManager
    ) -> None:
        """Execute entity operations then field operations.

        :param client: API client.
        :param field_mgr: Field manager for field operations.
        """
        entity_mgr = EntityManager(client, self.output_line.emit)
        had_entity_ops = False

        if self.skip_deletes:
            self.output_line.emit("", "white")
            self.output_line.emit(
                "[INFO]    Delete operations skipped "
                "\u2014 running in field-update mode",
                "yellow",
            )
        else:
            # Step 1: Delete entities
            delete_actions = {
                EntityAction.DELETE, EntityAction.DELETE_AND_CREATE
            }
            deletes = [
                e for e in self.program.entities
                if e.action in delete_actions
            ]
            if deletes:
                self.output_line.emit("", "white")
                self.output_line.emit(
                    "=== ENTITY DELETIONS ===", "white"
                )
                for entity_def in deletes:
                    try:
                        entity_mgr._delete_entity(entity_def)
                    except EntityManagerError as exc:
                        self.finished_error.emit(str(exc))
                        return
                had_entity_ops = True
                try:
                    entity_mgr.rebuild_cache()
                except EntityManagerError as exc:
                    self.finished_error.emit(str(exc))
                    return

        # Step 2: Create entities (for both create and delete_and_create)
        # In skip_deletes mode, delete_and_create is treated as create-if-not-exists
        create_actions = {EntityAction.CREATE, EntityAction.DELETE_AND_CREATE}
        creates = [
            e for e in self.program.entities if e.action in create_actions
        ]
        if creates:
            self.output_line.emit("", "white")
            self.output_line.emit("=== ENTITY CREATION ===", "white")
            for entity_def in creates:
                try:
                    entity_mgr._create_entity(entity_def)
                except EntityManagerError as exc:
                    self.finished_error.emit(str(exc))
                    return
            had_entity_ops = True
            try:
                entity_mgr.rebuild_cache()
            except EntityManagerError as exc:
                self.finished_error.emit(str(exc))
                return

        # Step 3: Apply entity settings
        has_settings = any(
            e.settings is not None and e.action != EntityAction.DELETE
            for e in self.program.entities
        )
        if has_settings:
            self.output_line.emit("", "white")
            self.output_line.emit(
                "=== ENTITY SETTINGS ===", "white"
            )
            settings_mgr = EntitySettingsManager(
                client, self.output_line.emit
            )
            try:
                settings_results = settings_mgr.process_settings(
                    self.program
                )
            except EntitySettingsManagerError as exc:
                self.finished_error.emit(str(exc))
                return

            # Stash results on report later (report not built yet)
            self._settings_results = settings_results
        else:
            self._settings_results = []

        # Step 3b: Apply email templates (before duplicate checks)
        has_email_templates = any(
            e.email_templates and e.action != EntityAction.DELETE
            for e in self.program.entities
        )
        if has_email_templates:
            self.output_line.emit("", "white")
            self.output_line.emit(
                "=== EMAIL TEMPLATES ===", "white"
            )
            et_mgr = EmailTemplateManager(
                client, self.output_line.emit
            )
            try:
                et_results = et_mgr.process_email_templates(
                    self.program
                )
            except EmailTemplateManagerError as exc:
                self.finished_error.emit(str(exc))
                return

            self._email_template_results = et_results
        else:
            self._email_template_results = []

        # Step 4: Apply duplicate-check rules
        has_dup_checks = any(
            e.duplicate_checks and e.action != EntityAction.DELETE
            for e in self.program.entities
        )
        if has_dup_checks:
            self.output_line.emit("", "white")
            self.output_line.emit(
                "=== DUPLICATE CHECK RULES ===", "white"
            )
            dup_mgr = DuplicateCheckManager(
                client, self.output_line.emit
            )
            try:
                dup_results = dup_mgr.process_duplicate_checks(
                    self.program
                )
            except DuplicateCheckManagerError as exc:
                self.finished_error.emit(str(exc))
                return

            self._duplicate_check_results = dup_results
        else:
            self._duplicate_check_results = []

        # Step 4b: Apply saved views
        has_saved_views = any(
            e.saved_views and e.action != EntityAction.DELETE
            for e in self.program.entities
        )
        if has_saved_views:
            self.output_line.emit("", "white")
            self.output_line.emit(
                "=== SAVED VIEWS ===", "white"
            )
            sv_mgr = SavedViewManager(
                client, self.output_line.emit
            )
            try:
                sv_results = sv_mgr.process_saved_views(
                    self.program
                )
            except SavedViewManagerError as exc:
                self.finished_error.emit(str(exc))
                return

            self._saved_view_results = sv_results
        else:
            self._saved_view_results = []

        # Step 5: Process fields
        has_fields = any(
            e.fields and e.action != EntityAction.DELETE
            for e in self.program.entities
        )
        if has_fields:
            if had_entity_ops:
                self.output_line.emit("", "white")
                self.output_line.emit(
                    "=== FIELD OPERATIONS ===", "white"
                )
            report = field_mgr.run(self.program)
        else:
            report = field_mgr._build_report(self.program, "run", [])

        # Attach settings and duplicate-check results to the report
        if self._settings_results:
            report.settings_results.extend(self._settings_results)
            for sr in self._settings_results:
                if sr.status == SettingsStatus.UPDATED:
                    report.summary.settings_updated += 1
                elif sr.status == SettingsStatus.SKIPPED:
                    report.summary.settings_skipped += 1
                elif sr.status == SettingsStatus.ERROR:
                    report.summary.settings_failed += 1

        if self._duplicate_check_results:
            report.duplicate_check_results.extend(
                self._duplicate_check_results
            )
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

        if self._saved_view_results:
            report.saved_view_results.extend(
                self._saved_view_results
            )
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

        if self._email_template_results:
            report.email_template_results.extend(
                self._email_template_results
            )
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

        # Step 6: Process layouts
        has_layouts = any(
            e.layouts and e.action != EntityAction.DELETE
            for e in self.program.entities
        )
        if has_layouts:
            self.output_line.emit("", "white")
            self.output_line.emit("=== LAYOUT OPERATIONS ===", "white")
            layout_mgr = LayoutManager(client, self.output_line.emit)

            for entity_def in self.program.entities:
                if entity_def.action == EntityAction.DELETE:
                    continue
                if not entity_def.layouts:
                    continue
                try:
                    layout_results = layout_mgr.process_layouts(
                        entity_def, entity_def.fields
                    )
                except LayoutManagerError as exc:
                    self.finished_error.emit(str(exc))
                    return
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
                f"  Updated              : {report.summary.layouts_updated}",
                "green" if report.summary.layouts_updated else "white",
            )
            self.output_line.emit(
                f"  Skipped (no change)  : {report.summary.layouts_skipped}",
                "gray",
            )
            self.output_line.emit(
                f"  Failed               : {report.summary.layouts_failed}",
                "red" if report.summary.layouts_failed else "white",
            )
            self.output_line.emit(
                "===========================================", "white"
            )

        # Step 7: Process relationships
        if self.program.relationships:
            self.output_line.emit("", "white")
            self.output_line.emit(
                "=== RELATIONSHIP OPERATIONS ===", "white"
            )
            rel_mgr = RelationshipManager(client, self.output_line.emit)

            try:
                rel_results = rel_mgr.process_relationships(
                    self.program.relationships
                )
            except RelationshipManagerError as exc:
                self.finished_error.emit(str(exc))
                return

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
                "green" if report.summary.relationships_created else "white",
            )
            self.output_line.emit(
                f"  Skipped (already exists)    : "
                f"{report.summary.relationships_skipped}",
                "gray",
            )
            self.output_line.emit(
                f"  Failed                      : "
                f"{report.summary.relationships_failed}",
                "red" if report.summary.relationships_failed else "white",
            )
            self.output_line.emit(
                "===========================================", "white"
            )

        self.finished_ok.emit(report)

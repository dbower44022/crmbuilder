"""Background worker thread for run/verify operations."""

from PySide6.QtCore import QThread, Signal

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.comparator import FieldComparator
from espo_impl.core.entity_manager import EntityManager, EntityManagerError
from espo_impl.core.field_manager import FieldManager
from espo_impl.core.models import EntityAction, InstanceProfile, ProgramFile


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

        # Step 3: Process fields
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

        self.finished_ok.emit(report)

"""Background worker thread for run/verify operations."""

from PySide6.QtCore import QThread, Signal

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.comparator import FieldComparator
from espo_impl.core.field_manager import FieldManager
from espo_impl.core.models import InstanceProfile, ProgramFile


class RunWorker(QThread):
    """Background worker that runs field operations off the main thread.

    :param profile: Instance connection profile.
    :param program: Validated program file to process.
    :param operation: Either "run" or "verify".
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
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.profile = profile
        self.program = program
        self.operation = operation

    def run(self) -> None:
        """Execute the operation in a background thread."""
        try:
            client = EspoAdminClient(self.profile)
            comparator = FieldComparator()
            manager = FieldManager(client, comparator, self.output_line.emit)

            if self.operation == "run":
                report = manager.run(self.program)
            elif self.operation == "preview":
                report = manager.preview(self.program)
            else:
                report = manager.verify(self.program)

            self.finished_ok.emit(report)
        except Exception as exc:
            self.finished_error.emit(str(exc))

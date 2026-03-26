"""Background worker thread for data import operations."""

from PySide6.QtCore import QThread, Signal

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.import_manager import ImportManager, RecordPlan


class ImportWorker(QThread):
    """Background worker that executes import ACT off the main thread.

    :param client: Authenticated API client.
    :param entity: EspoCRM entity name.
    :param plans: Pre-computed RecordPlans from CHECK step.
    :param parent: Parent QObject.
    """

    output_line = Signal(str, str)
    finished_ok = Signal(object)
    finished_error = Signal(str)

    def __init__(
        self,
        client: EspoAdminClient,
        entity: str,
        plans: list[RecordPlan],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.client = client
        self.entity = entity
        self.plans = plans

    def run(self) -> None:
        """Execute the import in a background thread."""
        try:
            manager = ImportManager(
                self.client, emit_line=self.output_line.emit
            )
            report = manager.execute(self.entity, self.plans)
            self.finished_ok.emit(report)
        except Exception as exc:
            self.finished_error.emit(str(exc))

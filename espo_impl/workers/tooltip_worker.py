"""Background worker thread for tooltip import operations."""

from PySide6.QtCore import QThread, Signal

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.models import (
    EntityAction,
    InstanceProfile,
    ProgramFile,
    RunReport,
    RunSummary,
    TooltipStatus,
)
from espo_impl.core.tooltip_manager import TooltipManager, TooltipManagerError


class TooltipWorker(QThread):
    """Background worker that imports tooltips off the main thread.

    :param profile: Instance connection profile.
    :param program: Validated program file to process.
    :param parent: Parent QObject.
    """

    output_line = Signal(str, str)
    finished_ok = Signal(object)
    finished_error = Signal(str)

    def __init__(
        self,
        profile: InstanceProfile,
        program: ProgramFile,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.profile = profile
        self.program = program

    def run(self) -> None:
        """Execute the tooltip import in a background thread."""
        try:
            from datetime import UTC, datetime

            client = EspoAdminClient(self.profile)
            tooltip_mgr = TooltipManager(client, self.output_line.emit)

            report = RunReport(
                timestamp=datetime.now(UTC).isoformat(),
                instance_name=self.profile.name,
                espocrm_url=self.profile.url,
                program_file=(
                    self.program.source_path.name
                    if self.program.source_path
                    else "unknown"
                ),
                operation="tooltips",
                content_version=self.program.content_version,
                summary=RunSummary(),
            )

            for entity_def in self.program.entities:
                if entity_def.action == EntityAction.DELETE:
                    continue
                if not entity_def.fields:
                    continue

                results = tooltip_mgr.process_tooltips(entity_def)
                report.tooltip_results.extend(results)

                for r in results:
                    if r.status == TooltipStatus.UPDATED:
                        report.summary.tooltips_updated += 1
                    elif r.status in (TooltipStatus.SKIPPED, TooltipStatus.NO_CHANGE):
                        report.summary.tooltips_skipped += 1
                    elif r.status == TooltipStatus.ERROR:
                        report.summary.tooltips_failed += 1

            # Emit summary
            total = len(report.tooltip_results)
            self.output_line.emit("", "white")
            self.output_line.emit(
                "===========================================", "white"
            )
            self.output_line.emit("TOOLTIP IMPORT SUMMARY", "white")
            self.output_line.emit(
                "===========================================", "white"
            )
            self.output_line.emit(
                f"Total fields processed  : {total}", "white"
            )
            self.output_line.emit(
                f"  Updated               : {report.summary.tooltips_updated}",
                "green" if report.summary.tooltips_updated else "white",
            )
            self.output_line.emit(
                f"  No change / skipped   : {report.summary.tooltips_skipped}",
                "gray",
            )
            self.output_line.emit(
                f"  Failed                : {report.summary.tooltips_failed}",
                "red" if report.summary.tooltips_failed else "white",
            )
            self.output_line.emit(
                "===========================================", "white"
            )

            self.finished_ok.emit(report)

        except TooltipManagerError as exc:
            self.finished_error.emit(str(exc))
        except Exception as exc:
            self.finished_error.emit(str(exc))

"""Background worker thread for CRM audit operations."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.audit_manager import AuditManager, AuditOptions, AuditReport
from espo_impl.core.models import InstanceProfile


class AuditWorker(QThread):
    """Background worker that runs a CRM audit off the main thread.

    :param profile: Source instance connection profile.
    :param output_dir: Directory to write YAML files into.
    :param options: Audit options controlling scope.
    :param db_path: Optional client DB path for record insertion.
    :param instance_id: Optional Instance table row ID for ConfigurationRun.
    :param parent: Parent QObject.
    """

    output_line = Signal(str, str)
    progress = Signal(int, int)
    finished_ok = Signal(object)
    finished_error = Signal(str)

    def __init__(
        self,
        profile: InstanceProfile,
        output_dir: Path,
        options: AuditOptions | None = None,
        db_path: str | None = None,
        instance_id: int | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.profile = profile
        self.output_dir = output_dir
        self.options = options or AuditOptions()
        self.db_path = db_path
        self.instance_id = instance_id

    def run(self) -> None:
        """Execute the audit in a background thread."""
        try:
            # Test connection first
            self.output_line.emit(
                f"[AUDIT]    Connecting to {self.profile.url} ...", "cyan"
            )
            client = EspoAdminClient(self.profile)
            success, message = client.test_connection()
            if not success:
                self.finished_error.emit(f"Connection failed: {message}")
                return

            self.output_line.emit(
                "[AUDIT]    Connection successful.", "green"
            )

            # Open DB connection if path provided
            db_conn = None
            if self.db_path:
                try:
                    db_conn = sqlite3.connect(self.db_path)
                    db_conn.execute("PRAGMA foreign_keys = ON")
                except sqlite3.Error as exc:
                    self.output_line.emit(
                        f"[AUDIT]    WARNING: Could not open database: {exc}",
                        "yellow",
                    )
                    db_conn = None

            # Run the audit
            manager = AuditManager(
                client=client,
                options=self.options,
                callback=self.output_line.emit,
            )

            report = manager.run_audit(
                output_dir=self.output_dir,
                db_conn=db_conn,
                instance_id=self.instance_id,
            )

            if db_conn is not None:
                db_conn.close()

            # Emit summary
            self._emit_summary(report)
            self.finished_ok.emit(report)

        except Exception as exc:
            self.finished_error.emit(str(exc))

    def _emit_summary(self, report: AuditReport) -> None:
        """Emit the audit summary block.

        :param report: Completed audit report.
        """
        custom = sum(
            1 for e in report.entities
            if e.entity_class.value == "custom"
        )
        native = sum(
            1 for e in report.entities
            if e.entity_class.value == "native"
        )
        total_fields = sum(len(e.fields) for e in report.entities)
        detail_layouts = sum(
            1 for e in report.entities
            for l in e.layouts if l.layout_type == "detail"
        )
        list_layouts = sum(
            1 for e in report.entities
            for l in e.layouts if l.layout_type == "list"
        )

        self.output_line.emit("", "white")
        self.output_line.emit(
            "===========================================", "white"
        )
        self.output_line.emit("AUDIT SUMMARY", "white")
        self.output_line.emit(
            "===========================================", "white"
        )
        self.output_line.emit(
            f"Source instance         : {report.source_name}", "white"
        )
        self.output_line.emit(
            f"Source URL              : {report.source_url}", "white"
        )
        self.output_line.emit(
            f"Audit timestamp         : {report.timestamp}", "white"
        )
        self.output_line.emit("", "white")
        self.output_line.emit(
            f"Entities discovered     : {len(report.entities)}", "white"
        )
        self.output_line.emit(
            f"  Custom entities       : {custom:>3}",
            "green" if custom else "white",
        )
        self.output_line.emit(
            f"  Native with customs   : {native:>3}",
            "cyan" if native else "white",
        )
        self.output_line.emit(
            f"Custom fields extracted : {total_fields:>3}",
            "green" if total_fields else "white",
        )
        self.output_line.emit(
            f"Detail layouts captured : {detail_layouts:>3}", "white"
        )
        self.output_line.emit(
            f"List layouts captured   : {list_layouts:>3}", "white"
        )
        self.output_line.emit(
            f"Relationships found     : {len(report.relationships):>3}", "white"
        )
        self.output_line.emit("", "white")
        self.output_line.emit(
            f"YAML files written      : {report.files_written:>3}",
            "green" if report.files_written else "white",
        )
        if report.warnings:
            self.output_line.emit(
                f"Warnings               : {len(report.warnings):>3}", "yellow"
            )
        if report.errors:
            self.output_line.emit(
                f"Errors                 : {len(report.errors):>3}", "red"
            )
        self.output_line.emit("", "white")
        self.output_line.emit(
            f"Output folder           : {report.output_dir}", "white"
        )
        self.output_line.emit(
            "===========================================", "white"
        )

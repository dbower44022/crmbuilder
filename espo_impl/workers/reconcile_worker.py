"""Background worker that detects CRM↔YAML drift off the main thread.

Mirrors :class:`espo_impl.workers.audit_worker.AuditWorker`: builds a client from
the instance profile, runs the (live, potentially slow) detection in ``run`` on a
QThread, streams ``(text, color)`` log lines, and hands the resulting
:class:`espo_impl.core.reconcile.engine.DriftReport` back via ``finished_ok``.

Only detection runs here — applying the accepted subset is fast local file I/O
and is done on the main thread once the user has made their selection.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.models import InstanceProfile


class ReconcileWorker(QThread):
    """Detect drift between the live CRM and the source YAML, off the UI thread.

    :param profile: Source instance connection profile.
    :param program_files: YAML program files to compare against.
    :param include_native_fields: include native-field drift (passed through to
        the engine's field capture).
    :param parent: Parent QObject.
    """

    output_line = Signal(str, str)      # (text, color)
    finished_ok = Signal(object)        # DriftReport
    finished_error = Signal(str)        # error message

    def __init__(
        self,
        profile: InstanceProfile,
        program_files: list[Path],
        *,
        include_native_fields: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.profile = profile
        self.program_files = list(program_files)
        self.include_native_fields = include_native_fields

    def run(self) -> None:
        """Detect drift in a background thread."""
        try:
            from espo_impl.core.reconcile.engine import detect_drift

            self.output_line.emit(
                f"[RECONCILE] Connecting to {self.profile.url} ...", "cyan"
            )
            client = EspoAdminClient(self.profile)
            ok, message = client.test_connection()
            if not ok:
                self.finished_error.emit(f"Connection failed: {message}")
                return
            self.output_line.emit("[RECONCILE] Connection successful.", "green")
            self.output_line.emit(
                f"[RECONCILE] Comparing {len(self.program_files)} program "
                f"file(s) against live configuration ...",
                "white",
            )

            report = detect_drift(
                client,
                self.program_files,
                include_native_fields=self.include_native_fields,
            )
            self._emit_summary(report)
            self.finished_ok.emit(report)
        except Exception as exc:  # surface any failure to the UI, never crash
            self.finished_error.emit(str(exc))

    def _emit_summary(self, report) -> None:
        """Emit a per-(type, category) count summary plus warnings."""
        by = Counter(
            (d.config_type.value, d.category.value) for d in report.differences
        )
        self.output_line.emit(
            f"[RECONCILE] {len(report.differences)} difference(s) detected.",
            "white",
        )
        for (ctype, cat), n in sorted(by.items()):
            self.output_line.emit(f"           {ctype:<13}{cat:<11}{n}", "gray")
        if report.unmapped_entities:
            self.output_line.emit(
                f"[RECONCILE] {len(report.unmapped_entities)} entity(ies) not "
                f"on the live instance: {', '.join(report.unmapped_entities)}",
                "yellow",
            )
        for warn in report.warnings:
            self.output_line.emit(f"[RECONCILE] WARNING: {warn}", "yellow")
        for col in report.collisions:
            self.output_line.emit(
                f"[RECONCILE] COLLISION: {col.entity}.{col.field_name} declared "
                f"in {col.first_file} and {col.duplicate_file}",
                "yellow",
            )

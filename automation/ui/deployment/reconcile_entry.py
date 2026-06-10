"""Reconcile sidebar entry — detect CRM↔YAML drift and write selected changes back.

One-way (CRM → YAML); the live CRM is never written to. Detection runs on a
:class:`espo_impl.workers.reconcile_worker.ReconcileWorker`; the results populate
a tree (entity → config type → change) of checkable rows. "Reconcile Selected"
applies the ticked subset to the source YAML via
:func:`espo_impl.core.reconcile.reconciler.apply_reconciliation`, bumping
``content_version`` and preserving comments/layout.
"""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from automation.ui.deployment.deployment_logic import (
    InstanceRow,
    load_instance_detail,
)
from espo_impl.core.reconcile.models import ConfigType, DiffCategory

_PRIMARY_STYLE = (
    "QPushButton { background-color: #1565C0; color: white; "
    "border-radius: 4px; padding: 6px 14px; font-size: 12px; } "
    "QPushButton:hover { background-color: #0D47A1; }"
)
_SECONDARY_STYLE = (
    "QPushButton { background-color: #FFA726; color: white; "
    "border-radius: 4px; padding: 6px 14px; font-size: 12px; } "
    "QPushButton:hover { background-color: #FB8C00; }"
)

_EMPTY_NO_INSTANCES = (
    "No CRM instances available.\n\n"
    "Go to the Instances entry to create one, or run the Deploy Wizard."
)
_EMPTY_NO_INSTANCE = (
    "Select an instance from the picker above to reconcile against.\n\n"
    "Reconciliation compares the live CRM configuration with the source\n"
    "YAML program files and writes the differences you accept back into YAML."
)
_EMPTY_NO_FOLDER = (
    "No project folder is configured for this client.\n\n"
    "Set a project folder in the Clients tab so the system can find\n"
    "the YAML program files to reconcile."
)

#: log colour -> hex, shared with the audit entry's convention.
_COLOR_MAP = {
    "red": "#F44336", "green": "#4CAF50", "yellow": "#FFC107",
    "cyan": "#00BCD4", "white": "#D4D4D4", "gray": "#9E9E9E",
}
_MAX_VALUE_LEN = 70


def _short(value: object) -> str:
    """Render a diff value compactly for a tree row (layouts can be huge)."""
    text = str(value)
    text = " ".join(text.split())
    return text if len(text) <= _MAX_VALUE_LEN else text[: _MAX_VALUE_LEN - 1] + "…"


def _locator_name(diff) -> str:
    """A human label for the item a difference concerns."""
    loc = diff.locator
    for attr in ("field_name", "rel_name", "layout_type", "role", "team"):
        val = getattr(loc, attr, None)
        if val:
            return val
    return diff.property or "?"


def _diff_label(diff) -> str:
    """One-line description of a difference for its tree row."""
    name = _locator_name(diff)
    if diff.category is DiffCategory.CHANGED:
        return f"{name}.{diff.property}:  {_short(diff.yaml_value)}  →  {_short(diff.crm_value)}"
    if diff.category is DiffCategory.CRM_ONLY:
        return f"{name}  —  add from CRM"
    src = diff.source_file.name if diff.source_file is not None else "?"
    return f"{name}  —  in YAML, absent from CRM — {src} (report-only)"


class ReconcileEntry(QWidget):
    """Reconcile sidebar entry: detect drift, then write accepted changes to YAML."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn: sqlite3.Connection | None = None
        self._instance: InstanceRow | None = None
        self._project_folder: str | None = None
        self._output_entry = None
        self._worker = None
        self._report = None
        self._program_files: list[Path] = []
        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        self._detect_btn = QPushButton("Detect Drift")
        self._detect_btn.setStyleSheet(_PRIMARY_STYLE)
        self._detect_btn.clicked.connect(self._on_detect)
        header.addWidget(self._detect_btn)

        self._apply_btn = QPushButton("Reconcile Selected")
        self._apply_btn.setStyleSheet(_SECONDARY_STYLE)
        self._apply_btn.clicked.connect(self._on_reconcile_selected)
        self._apply_btn.setEnabled(False)
        header.addWidget(self._apply_btn)
        header.addStretch()
        layout.addLayout(header)

        self._empty_label = QLabel()
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("font-size: 14px; color: #757575; padding: 40px;")
        layout.addWidget(self._empty_label)

        self._content = QWidget()
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 8, 0, 0)

        info_group = QGroupBox("Source Instance")
        info_layout = QVBoxLayout(info_group)
        self._instance_label = QLabel()
        self._instance_label.setStyleSheet("font-size: 13px;")
        info_layout.addWidget(self._instance_label)
        content_layout.addWidget(info_group)

        diff_group = QGroupBox("Differences (CRM → YAML)")
        diff_layout = QVBoxLayout(diff_group)
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setMinimumHeight(220)
        diff_layout.addWidget(self._tree)
        self._summary_label = QLabel("Run Detect Drift to compare the live CRM with the YAML.")
        self._summary_label.setStyleSheet("font-size: 12px; color: #757575; padding: 2px;")
        diff_layout.addWidget(self._summary_label)
        content_layout.addWidget(diff_group)

        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        content_layout.addWidget(self._progress_bar)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(
            "QTextEdit { background-color: #1E1E1E; color: #D4D4D4; "
            "font-family: monospace; font-size: 11px; }"
        )
        self._log.setMaximumHeight(160)
        content_layout.addWidget(self._log)

        layout.addWidget(self._content)

    def set_output_entry(self, output_entry) -> None:
        """Set the OutputEntry widget for mirrored log output."""
        self._output_entry = output_entry

    # -------------------------------------------------------------- refresh
    def refresh(
        self,
        conn: sqlite3.Connection,
        instance: InstanceRow | None,
        project_folder: str | None,
        has_instances: bool,
    ) -> None:
        """Reload the entry with current context (mirrors AuditEntry.refresh)."""
        self._conn = conn
        self._instance = instance
        self._project_folder = project_folder

        if not has_instances:
            self._show_empty(_EMPTY_NO_INSTANCES)
            return
        if not instance:
            self._show_empty(_EMPTY_NO_INSTANCE)
            return
        if not project_folder:
            self._show_empty(_EMPTY_NO_FOLDER)
            return

        self._empty_label.setVisible(False)
        self._content.setVisible(True)
        self._instance_label.setText(
            f"{instance.name}  ({instance.code})\n"
            f"URL: {instance.url or 'Not configured'}\n"
            f"Environment: {instance.environment}"
        )

    def _show_empty(self, message: str) -> None:
        self._empty_label.setText(message)
        self._empty_label.setVisible(True)
        self._content.setVisible(False)

    # --------------------------------------------------------------- detect
    def _on_detect(self) -> None:
        """Build the client + program-file list and launch the detect worker."""
        from espo_impl.core.models import InstanceProfile
        from espo_impl.core.reconcile.provenance import discover_program_files
        from espo_impl.workers.reconcile_worker import ReconcileWorker

        if self._conn is None or self._instance is None or not self._project_folder:
            return

        detail = load_instance_detail(self._conn, self._instance.id)
        if not detail or not detail.url or not detail.username or not detail.password:
            QMessageBox.warning(
                self, "Reconcile",
                "The selected instance is missing a URL or credentials.",
            )
            return

        programs_dir = Path(self._project_folder) / "programs"
        if not programs_dir.is_dir():
            QMessageBox.warning(
                self, "Reconcile",
                f"No programs directory found at {programs_dir}.",
            )
            return
        self._program_files = discover_program_files(programs_dir)
        if not self._program_files:
            QMessageBox.warning(
                self, "Reconcile",
                f"No YAML program files found under {programs_dir}.",
            )
            return

        profile = InstanceProfile(
            name=detail.name, url=detail.url, api_key=detail.username,
            auth_method="basic", secret_key=detail.password,
        )

        self._tree.clear()
        self._report = None
        self._apply_btn.setEnabled(False)
        self._detect_btn.setEnabled(False)
        self._progress_bar.setRange(0, 0)  # indeterminate
        self._progress_bar.setVisible(True)
        self._log.clear()

        self._worker = ReconcileWorker(profile, self._program_files, parent=self)
        self._worker.output_line.connect(self._on_output_line)
        self._worker.finished_ok.connect(self._on_finished_ok)
        self._worker.finished_error.connect(self._on_finished_error)
        self._worker.start()

    def _on_output_line(self, text: str, color: str) -> None:
        hex_color = _COLOR_MAP.get(color, "#D4D4D4")
        escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self._log.append(f'<span style="color: {hex_color};">{escaped}</span>')
        if self._output_entry:
            level = {"red": "error", "yellow": "warning", "green": "success"}.get(color, "info")
            self._output_entry.append_line(text, level)

    def _on_finished_ok(self, report) -> None:
        self._report = report
        self._progress_bar.setVisible(False)
        self._detect_btn.setEnabled(True)
        self._populate_tree(report)
        self._apply_btn.setEnabled(bool(report.differences))

    def _on_finished_error(self, error: str) -> None:
        self._progress_bar.setVisible(False)
        self._detect_btn.setEnabled(True)
        self._on_output_line(f"RECONCILE FAILED: {error}", "red")

    # ----------------------------------------------------------- tree build
    def _populate_tree(self, report) -> None:
        """Group differences entity → config type → change; CHANGED checked."""
        self._tree.clear()
        by_entity: dict[str, list[tuple[int, object]]] = {}
        for idx, diff in enumerate(report.differences):
            by_entity.setdefault(diff.entity, []).append((idx, diff))

        changed = 0
        for entity in sorted(by_entity):
            ent_item = QTreeWidgetItem([entity])
            ent_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._tree.addTopLevelItem(ent_item)
            by_type: dict[str, list[tuple[int, object]]] = {}
            for idx, diff in by_entity[entity]:
                by_type.setdefault(diff.config_type.value, []).append((idx, diff))
            for ctype in sorted(by_type):
                type_item = QTreeWidgetItem([ctype])
                type_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                ent_item.addChild(type_item)
                for idx, diff in by_type[ctype]:
                    leaf = QTreeWidgetItem([_diff_label(diff)])
                    leaf.setFlags(leaf.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    is_changed = diff.category is DiffCategory.CHANGED
                    leaf.setCheckState(
                        0,
                        Qt.CheckState.Checked if is_changed else Qt.CheckState.Unchecked,
                    )
                    leaf.setData(0, Qt.ItemDataRole.UserRole, idx)
                    type_item.addChild(leaf)
                    changed += int(is_changed)
            ent_item.setExpanded(True)

        self._summary_label.setText(
            f"{len(report.differences)} difference(s); {changed} changed-in-both "
            f"pre-selected. Tick others to include them."
        )

    def _checked_diffs(self) -> list:
        """Collect the Difference behind every checked leaf row."""
        out = []
        for i in range(self._tree.topLevelItemCount()):
            ent = self._tree.topLevelItem(i)
            for j in range(ent.childCount()):
                type_item = ent.child(j)
                for k in range(type_item.childCount()):
                    leaf = type_item.child(k)
                    if leaf.checkState(0) is Qt.CheckState.Checked:
                        idx = leaf.data(0, Qt.ItemDataRole.UserRole)
                        if idx is not None:
                            out.append(self._report.differences[idx])
        return out

    # ----------------------------------------------------------- apply
    def _on_reconcile_selected(self) -> None:
        """Apply the ticked differences to the source YAML files."""
        from espo_impl.core.reconcile.reconciler import apply_reconciliation

        if self._report is None:
            return
        checked = self._checked_diffs()
        if not checked:
            QMessageBox.information(self, "Reconcile", "No differences are selected.")
            return

        accepted, report_only = [], []
        for diff in checked:
            if diff.source_file is not None:
                accepted.append(diff)
            elif (
                diff.config_type is ConfigType.FIELD
                and diff.category is DiffCategory.CRM_ONLY
            ):
                target = self._ask_target_file(diff)
                if target is None:  # user cancelled this addition
                    continue
                accepted.append(replace(diff, source_file=target))
            else:
                report_only.append(diff)  # CRM-only non-field: no write path in v1

        if report_only:
            self._on_output_line(
                f"[RECONCILE] {len(report_only)} selected CRM-only "
                f"item(s) have no v1 write path; left for manual handling.",
                "yellow",
            )
        if not accepted:
            QMessageBox.information(
                self, "Reconcile",
                "Nothing to write (selected items are report-only in v1).",
            )
            return

        result = apply_reconciliation(accepted, write=True)
        self._report_result(result)
        # Re-detect so the tree reflects the new on-disk state.
        self._on_detect()

    def _ask_target_file(self, diff) -> Path | None:
        """Ask which program file a CRM-only addition should be written to."""
        names = [str(p) for p in self._program_files]
        choice, ok = QInputDialog.getItem(
            self,
            "Choose target file",
            f"Add {diff.entity}.{_locator_name(diff)} to which file?",
            names,
            0,
            False,
        )
        return Path(choice) if ok else None

    def _report_result(self, result) -> None:
        """Log the per-file apply outcome, write a report, and show a summary."""
        self._on_output_line(
            f"[RECONCILE] Applied {result.applied_count} change(s) across "
            f"{len(result.files)} file(s); {result.not_applied_count} not applied.",
            "green",
        )
        for fr in result.files:
            ver = (
                f" (content_version {fr.old_version} → {fr.new_version})"
                if fr.new_version else ""
            )
            self._on_output_line(
                f"           {fr.path.name}: {len(fr.applied)} applied{ver}",
                "white",
            )
            for diff, reason in fr.not_applied:
                self._on_output_line(
                    f"             - skipped {diff.entity}.{_locator_name(diff)}: {reason}",
                    "gray",
                )

        report_paths = self._write_report(result)
        if report_paths:
            for path in report_paths:
                self._on_output_line(f"[RECONCILE] Report: {path}", "cyan")

        extra = f"\n\nReport written to:\n{report_paths[0].parent}" if report_paths else ""
        QMessageBox.information(
            self, "Reconcile",
            f"Applied {result.applied_count} change(s); "
            f"{result.not_applied_count} not applied. See the log for detail."
            f"{extra}",
        )

    def _write_report(self, result) -> tuple[Path, Path] | None:
        """Write the .log/.json reconcile report under the client's reports/."""
        if not self._project_folder:
            return None
        from espo_impl.core.reconcile.report import write_reconcile_report

        try:
            return write_reconcile_report(
                result,
                Path(self._project_folder) / "reports",
                instance_name=self._instance.name if self._instance else None,
                source_url=self._instance.url if self._instance else None,
            )
        except OSError as exc:
            self._on_output_line(f"[RECONCILE] Could not write report: {exc}", "yellow")
            return None

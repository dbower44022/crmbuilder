"""Record editor — edit mode with type-constrained inputs (Section 14.8.3).

Handles edit, save (with pre-commit impact analysis), and delete flows.
"""

from __future__ import annotations

import logging
import sqlite3

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from automation.ui.browser.browser_logic import (
    RecordDetail,
    delete_record,
    save_record,
    write_impact_rows,
)
from automation.ui.browser.fk_selector import FKSelector
from automation.ui.common.toast import show_toast

logger = logging.getLogger(__name__)

_PRIMARY_STYLE = (
    "QPushButton { background-color: #1565C0; color: white; "
    "border-radius: 4px; padding: 6px 12px; font-size: 12px; } "
    "QPushButton:hover { background-color: #0D47A1; }"
)
_CANCEL_STYLE = "QPushButton { padding: 6px 12px; font-size: 12px; }"
_DELETE_STYLE = (
    "QPushButton { background-color: #C62828; color: white; "
    "border-radius: 4px; padding: 6px 12px; font-size: 12px; } "
    "QPushButton:hover { background-color: #B71C1C; }"
)


class RecordEditor(QWidget):
    """Edit mode form for a record (Section 14.8.3).

    :param conn: Database connection.
    :param record: The record to edit.
    :param parent: Parent widget.
    """

    save_completed = Signal()
    delete_completed = Signal()
    cancelled = Signal()

    def __init__(
        self,
        conn: sqlite3.Connection,
        record: RecordDetail,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._conn = conn
        self._record = record
        self._editors: dict[str, QWidget] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 8)

        # Title
        title = QLabel(f"Editing: {record.table_name} #{record.record_id}")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1F3864; padding: 4px;")
        layout.addWidget(title)

        # Scroll area for form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_widget = QWidget()
        self._form = QFormLayout(form_widget)
        self._form.setContentsMargins(0, 0, 0, 0)

        for col_info in record.columns:
            value = record.values.get(col_info.name)
            label = QLabel(col_info.name)
            label.setStyleSheet("font-size: 11px; font-weight: bold; color: #424242;")

            if col_info.is_read_only:
                # Read-only display
                ro_label = QLabel(str(value) if value is not None else "—")
                ro_label.setStyleSheet("font-size: 11px; color: #757575;")
                self._form.addRow(label, ro_label)
            elif col_info.is_fk:
                # FK selector
                selector = FKSelector(conn, col_info.fk_table, value)
                self._editors[col_info.name] = selector
                self._form.addRow(label, selector)
            elif col_info.check_values:
                # Enum dropdown
                combo = QComboBox()
                combo.setStyleSheet("font-size: 11px;")
                combo.addItem("— None —", None)
                for cv in col_info.check_values:
                    combo.addItem(cv, cv)
                if value is not None:
                    idx = combo.findData(str(value))
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                self._editors[col_info.name] = combo
                self._form.addRow(label, combo)
            elif col_info.col_type in ("BOOLEAN",):
                # Boolean checkbox
                checkbox = QCheckBox()
                checkbox.setChecked(bool(value))
                self._editors[col_info.name] = checkbox
                self._form.addRow(label, checkbox)
            elif col_info.col_type in ("INTEGER", "REAL"):
                # Number input
                spin = QSpinBox()
                spin.setRange(-999999, 999999)
                spin.setStyleSheet("font-size: 11px;")
                if value is not None:
                    try:
                        spin.setValue(int(value))
                    except (ValueError, TypeError):
                        pass
                self._editors[col_info.name] = spin
                self._form.addRow(label, spin)
            else:
                # Text input
                line = QLineEdit(str(value) if value is not None else "")
                line.setStyleSheet("font-size: 11px;")
                self._editors[col_info.name] = line
                self._form.addRow(label, line)

        scroll.setWidget(form_widget)
        layout.addWidget(scroll, stretch=1)

        # Buttons
        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(_PRIMARY_STYLE)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(_CANCEL_STYLE)
        cancel_btn.clicked.connect(self.cancelled.emit)
        btn_row.addWidget(cancel_btn)

        btn_row.addStretch()

        delete_btn = QPushButton("Delete")
        delete_btn.setStyleSheet(_DELETE_STYLE)
        delete_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(delete_btn)

        layout.addLayout(btn_row)

    def _collect_changes(self) -> dict[str, object]:
        """Collect changed values from editors."""
        changes: dict[str, object] = {}
        for col_name, editor in self._editors.items():
            original = self._record.values.get(col_name)

            if isinstance(editor, FKSelector):
                new_val = editor.get_selected_id()
            elif isinstance(editor, QComboBox):
                new_val = editor.currentData()
            elif isinstance(editor, QCheckBox):
                new_val = editor.isChecked()
            elif isinstance(editor, QSpinBox):
                new_val = editor.value()
            elif isinstance(editor, QLineEdit):
                text = editor.text().strip()
                new_val = text if text else None
            else:
                continue

            # Compare as strings to detect changes
            if str(new_val) != str(original):
                changes[col_name] = new_val

        return changes

    def _on_save(self) -> None:
        """Handle Save click with pre-commit impact analysis."""
        changes = self._collect_changes()
        if not changes:
            show_toast(self, "No changes to save")
            self.cancelled.emit()
            return

        try:
            from automation.impact.engine import ImpactAnalysisEngine
            engine = ImpactAnalysisEngine(self._conn)
            proposed = engine.analyze_proposed_change(
                table_name=self._record.table_name,
                record_id=self._record.record_id,
                change_type="update",
                new_values=changes,
            )

            if proposed:
                # Show pre-commit confirmation dialog
                from automation.ui.impact.precommit_confirm import (
                    PrecommitConfirmDialog,
                )
                dialog = PrecommitConfirmDialog(proposed, parent=self)
                if not dialog.exec():
                    return  # Cancelled — stay in edit mode
                rationale = dialog.get_rationale()
            else:
                rationale = None

            # Write changes
            save_record(
                self._conn, self._record.table_name,
                self._record.record_id, changes, rationale=rationale,
            )

            # Write ChangeImpact rows if there were proposed impacts
            if proposed:
                # Get the ChangeLog IDs we just created
                cl_rows = self._conn.execute(
                    "SELECT id FROM ChangeLog WHERE table_name = ? AND record_id = ? "
                    "AND change_type = 'update' ORDER BY id DESC LIMIT ?",
                    (self._record.table_name, self._record.record_id, len(changes)),
                ).fetchall()
                cl_ids = [r[0] for r in cl_rows]
                write_impact_rows(self._conn, cl_ids, proposed)

            show_toast(self, "Record saved")
            self.save_completed.emit()

        except Exception as e:
            logger.warning("Save failed: %s", e)
            show_toast(self, f"Save failed: {e}")

    def _on_delete(self) -> None:
        """Handle Delete click with pre-commit impact analysis."""
        try:
            from automation.impact.engine import ImpactAnalysisEngine
            engine = ImpactAnalysisEngine(self._conn)
            proposed = engine.analyze_proposed_change(
                table_name=self._record.table_name,
                record_id=self._record.record_id,
                change_type="delete",
            )

            # Always show confirmation for deletes
            from automation.ui.impact.precommit_confirm import PrecommitConfirmDialog
            dialog = PrecommitConfirmDialog(proposed, parent=self)
            if not dialog.exec():
                return  # Cancelled
            rationale = dialog.get_rationale()

            delete_record(
                self._conn, self._record.table_name,
                self._record.record_id, rationale=rationale,
            )

            # Write ChangeImpact rows
            if proposed:
                cl_rows = self._conn.execute(
                    "SELECT id FROM ChangeLog WHERE table_name = ? AND record_id = ? "
                    "AND change_type = 'delete' ORDER BY id DESC LIMIT 1",
                    (self._record.table_name, self._record.record_id),
                ).fetchall()
                cl_ids = [r[0] for r in cl_rows]
                write_impact_rows(self._conn, cl_ids, proposed)

            show_toast(self, "Record deleted")
            self.delete_completed.emit()

        except Exception as e:
            logger.warning("Delete failed: %s", e)
            show_toast(self, f"Delete failed: {e}")

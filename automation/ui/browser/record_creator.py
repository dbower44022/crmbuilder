"""New record creation flow (Section 14.8.6).

Inserts are exempt from pre-commit impact analysis per Section 12.2.
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
    create_record,
    get_table_columns,
    infer_fk_from_context,
)
from automation.ui.browser.fk_selector import FKSelector
from automation.ui.common.toast import show_toast

logger = logging.getLogger(__name__)

_PRIMARY_STYLE = (
    "QPushButton { background-color: #1565C0; color: white; "
    "border-radius: 4px; padding: 6px 12px; font-size: 12px; } "
    "QPushButton:hover { background-color: #0D47A1; }"
)


class RecordCreator(QWidget):
    """New record creation form (Section 14.8.6).

    :param conn: Database connection.
    :param table_name: Table to create a record in.
    :param context_table: Currently selected table in the tree (for FK inference).
    :param context_id: Currently selected record ID in the tree.
    :param parent: Parent widget.
    """

    create_completed = Signal(str, int)  # table_name, new_record_id
    cancelled = Signal()

    def __init__(
        self,
        conn: sqlite3.Connection,
        table_name: str,
        context_table: str | None = None,
        context_id: int | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._conn = conn
        self._table_name = table_name
        self._editors: dict[str, QWidget] = {}

        # Infer FK values from context
        inferred = infer_fk_from_context(table_name, context_table, context_id)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 8)

        title = QLabel(f"New {table_name}")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1F3864; padding: 4px;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_widget = QWidget()
        self._form = QFormLayout(form_widget)
        self._form.setContentsMargins(0, 0, 0, 0)

        columns = get_table_columns(conn, table_name)
        for col_info in columns:
            if col_info.name == "id":
                continue  # Auto-generated

            label = QLabel(col_info.name)
            label.setStyleSheet("font-size: 11px; font-weight: bold; color: #424242;")

            if col_info.name in ("created_at", "updated_at"):
                ro_label = QLabel("(auto)")
                ro_label.setStyleSheet("font-size: 11px; color: #757575;")
                self._form.addRow(label, ro_label)
            elif col_info.is_fk:
                pre_value = inferred.get(col_info.name)
                selector = FKSelector(conn, col_info.fk_table, pre_value)
                self._editors[col_info.name] = selector
                self._form.addRow(label, selector)
            elif col_info.check_values:
                combo = QComboBox()
                combo.setStyleSheet("font-size: 11px;")
                combo.addItem("— None —", None)
                for cv in col_info.check_values:
                    combo.addItem(cv, cv)
                self._editors[col_info.name] = combo
                self._form.addRow(label, combo)
            elif col_info.col_type in ("BOOLEAN",):
                checkbox = QCheckBox()
                self._editors[col_info.name] = checkbox
                self._form.addRow(label, checkbox)
            elif col_info.col_type in ("INTEGER", "REAL"):
                spin = QSpinBox()
                spin.setRange(-999999, 999999)
                spin.setStyleSheet("font-size: 11px;")
                self._editors[col_info.name] = spin
                self._form.addRow(label, spin)
            else:
                line = QLineEdit()
                line.setStyleSheet("font-size: 11px;")
                self._editors[col_info.name] = line
                self._form.addRow(label, line)

        scroll.setWidget(form_widget)
        layout.addWidget(scroll, stretch=1)

        btn_row = QHBoxLayout()
        create_btn = QPushButton("Create")
        create_btn.setStyleSheet(_PRIMARY_STYLE)
        create_btn.clicked.connect(self._on_create)
        btn_row.addWidget(create_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("QPushButton { padding: 6px 12px; font-size: 12px; }")
        cancel_btn.clicked.connect(self.cancelled.emit)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _on_create(self) -> None:
        """Collect values and create the record."""
        values: dict[str, object] = {}
        for col_name, editor in self._editors.items():
            if isinstance(editor, FKSelector):
                val = editor.get_selected_id()
            elif isinstance(editor, QComboBox):
                val = editor.currentData()
            elif isinstance(editor, QCheckBox):
                val = editor.isChecked()
            elif isinstance(editor, QSpinBox):
                val = editor.value()
            elif isinstance(editor, QLineEdit):
                text = editor.text().strip()
                val = text if text else None
            else:
                continue

            if val is not None:
                values[col_name] = val

        if not values:
            show_toast(self, "No values provided")
            return

        try:
            new_id = create_record(self._conn, self._table_name, values)
            show_toast(self, f"Created {self._table_name} #{new_id}")
            self.create_completed.emit(self._table_name, new_id)
        except Exception as e:
            logger.warning("Create failed: %s", e)
            show_toast(self, f"Create failed: {e}")

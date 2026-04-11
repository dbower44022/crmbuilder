"""Instances sidebar entry — list + detail pane (Section 14.12.3).

Displays all instances for the active client with inline editing.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from automation.ui.deployment.deployment_logic import (
    InstanceRow,
    create_instance,
    load_instance_detail,
    load_instances,
    set_default_instance,
    update_instance,
)

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

_EMPTY_MSG = (
    "No CRM instances have been created for this client yet.\n\n"
    "Click '+ New Instance' above to add the first instance."
)


class InstancesEntry(QWidget):
    """Instances list + detail pane.

    :param parent: Parent widget.
    """

    instance_created = Signal()  # Emitted after creating/updating an instance

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn: sqlite3.Connection | None = None
        self._instances: list[InstanceRow] = []
        self._selected_id: int | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header with + New Instance button
        header = QHBoxLayout()
        self._new_btn = QPushButton("+ New Instance")
        self._new_btn.setStyleSheet(_PRIMARY_STYLE)
        self._new_btn.clicked.connect(self._on_new)
        header.addWidget(self._new_btn)
        header.addStretch()
        layout.addLayout(header)

        # Empty state
        self._empty_label = QLabel(_EMPTY_MSG)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            "font-size: 14px; color: #757575; padding: 40px;"
        )
        layout.addWidget(self._empty_label)

        # Splitter: table on top, detail below
        self._splitter = QSplitter(Qt.Orientation.Vertical)

        # --- Instance table ---
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["Name", "Code", "Environment", "URL", "Default", "Status"]
        )
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._table.currentCellChanged.connect(self._on_row_changed)
        self._splitter.addWidget(self._table)

        # --- Detail pane ---
        self._detail_group = QGroupBox("Instance Details")
        detail_layout = QFormLayout()

        self._detail_name = QLineEdit()
        detail_layout.addRow("Name:", self._detail_name)

        self._detail_code = QLineEdit()
        self._detail_code.setReadOnly(True)
        self._detail_code.setStyleSheet("background-color: #F5F5F5;")
        detail_layout.addRow("Code:", self._detail_code)

        self._detail_env = QLineEdit()
        self._detail_env.setReadOnly(True)
        self._detail_env.setStyleSheet("background-color: #F5F5F5;")
        detail_layout.addRow("Environment:", self._detail_env)

        self._detail_url = QLineEdit()
        detail_layout.addRow("URL:", self._detail_url)

        self._detail_username = QLineEdit()
        detail_layout.addRow("Username:", self._detail_username)

        self._detail_password = QLineEdit()
        self._detail_password.setEchoMode(QLineEdit.EchoMode.Password)
        detail_layout.addRow("Password:", self._detail_password)

        self._detail_desc = QLineEdit()
        detail_layout.addRow("Description:", self._detail_desc)

        self._detail_default = QCheckBox("Default Instance")
        detail_layout.addRow("", self._detail_default)

        # Save button
        btn_row = QHBoxLayout()
        self._save_btn = QPushButton("Save Changes")
        self._save_btn.setStyleSheet(_SECONDARY_STYLE)
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addStretch()
        btn_row.addWidget(self._save_btn)
        detail_layout.addRow("", btn_row)

        self._detail_group.setLayout(detail_layout)
        self._splitter.addWidget(self._detail_group)

        layout.addWidget(self._splitter, stretch=1)

        # --- New-instance form (hidden by default) ---
        self._new_form = QGroupBox("Create New Instance")
        new_layout = QFormLayout()

        self._new_name = QLineEdit()
        new_layout.addRow("Name:", self._new_name)

        self._new_code = QLineEdit()
        self._new_code.setPlaceholderText("2-10 uppercase letters/digits")
        new_layout.addRow("Code:", self._new_code)

        self._new_env = QComboBox()
        self._new_env.addItems(["production", "staging", "test"])
        new_layout.addRow("Environment:", self._new_env)

        self._new_url = QLineEdit()
        new_layout.addRow("URL:", self._new_url)

        self._new_username = QLineEdit()
        new_layout.addRow("Username:", self._new_username)

        self._new_password = QLineEdit()
        self._new_password.setEchoMode(QLineEdit.EchoMode.Password)
        new_layout.addRow("Password:", self._new_password)

        self._new_desc = QLineEdit()
        new_layout.addRow("Description:", self._new_desc)

        self._new_default = QCheckBox("Set as default instance")
        new_layout.addRow("", self._new_default)

        new_btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self._on_cancel_new)
        new_btn_row.addWidget(cancel_btn)
        create_btn = QPushButton("Create")
        create_btn.setStyleSheet(_PRIMARY_STYLE)
        create_btn.clicked.connect(self._on_create)
        new_btn_row.addWidget(create_btn)
        new_layout.addRow("", new_btn_row)

        self._new_form.setLayout(new_layout)
        self._new_form.setVisible(False)
        layout.addWidget(self._new_form)

    def refresh(self, conn: sqlite3.Connection) -> None:
        """Reload instances from the database.

        :param conn: Per-client database connection.
        """
        self._conn = conn
        self._instances = load_instances(conn)
        self._populate_table()
        has_instances = len(self._instances) > 0
        self._empty_label.setVisible(not has_instances)
        self._splitter.setVisible(has_instances)

    def _populate_table(self) -> None:
        self._table.setRowCount(len(self._instances))
        for row, inst in enumerate(self._instances):
            self._table.setItem(row, 0, QTableWidgetItem(inst.name))
            self._table.setItem(row, 1, QTableWidgetItem(inst.code))
            self._table.setItem(row, 2, QTableWidgetItem(inst.environment))
            self._table.setItem(row, 3, QTableWidgetItem(inst.url or ""))
            self._table.setItem(
                row, 4, QTableWidgetItem("Yes" if inst.is_default else "")
            )
            self._table.setItem(row, 5, QTableWidgetItem("—"))

        # Restore selection
        if self._selected_id is not None:
            for row, inst in enumerate(self._instances):
                if inst.id == self._selected_id:
                    self._table.setCurrentCell(row, 0)
                    return
        if self._instances:
            self._table.setCurrentCell(0, 0)

    def _on_row_changed(self, row: int, _col: int, _prev_row: int, _prev_col: int) -> None:
        if not self._conn or row < 0 or row >= len(self._instances):
            self._detail_group.setVisible(False)
            self._selected_id = None
            return

        inst_row = self._instances[row]
        self._selected_id = inst_row.id
        detail = load_instance_detail(self._conn, inst_row.id)
        if detail is None:
            self._detail_group.setVisible(False)
            return

        self._detail_group.setVisible(True)
        self._detail_name.setText(detail.name)
        self._detail_code.setText(detail.code)
        self._detail_env.setText(detail.environment)
        self._detail_url.setText(detail.url or "")
        self._detail_username.setText(detail.username or "")
        self._detail_password.setText(detail.password or "")
        self._detail_desc.setText(detail.description or "")
        self._detail_default.setChecked(detail.is_default)

    def _on_save(self) -> None:
        if not self._conn or self._selected_id is None:
            return

        name = self._detail_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Name is required.")
            return

        update_instance(
            self._conn,
            self._selected_id,
            name=name,
            url=self._detail_url.text().strip() or None,
            username=self._detail_username.text().strip() or None,
            password=self._detail_password.text() or None,
            description=self._detail_desc.text().strip() or None,
        )

        # Handle default flag change
        if self._detail_default.isChecked():
            set_default_instance(self._conn, self._selected_id)

        self.refresh(self._conn)
        self.instance_created.emit()

    def _on_new(self) -> None:
        self._new_form.setVisible(True)
        self._new_name.clear()
        self._new_code.clear()
        self._new_env.setCurrentIndex(0)
        self._new_url.clear()
        self._new_username.clear()
        self._new_password.clear()
        self._new_desc.clear()
        self._new_default.setChecked(not self._instances)

    def _on_cancel_new(self) -> None:
        self._new_form.setVisible(False)

    def _on_create(self) -> None:
        if not self._conn:
            return

        name = self._new_name.text().strip()
        code = self._new_code.text().strip().upper()
        if not name:
            QMessageBox.warning(self, "Validation", "Name is required.")
            return
        if not code or len(code) < 2 or len(code) > 10:
            QMessageBox.warning(
                self, "Validation",
                "Code must be 2-10 uppercase letters/digits, starting with a letter.",
            )
            return

        environment = self._new_env.currentText()
        try:
            new_id = create_instance(
                self._conn,
                name=name,
                code=code,
                environment=environment,
                url=self._new_url.text().strip() or None,
                username=self._new_username.text().strip() or None,
                password=self._new_password.text() or None,
                description=self._new_desc.text().strip() or None,
                is_default=self._new_default.isChecked(),
            )
        except Exception as exc:
            QMessageBox.warning(
                self, "Error", f"Could not create instance: {exc}"
            )
            return

        self._new_form.setVisible(False)
        self._selected_id = new_id
        self.refresh(self._conn)
        self.instance_created.emit()

"""Clients tab — master/detail client management (Section 14.11).

The application's entry point for managing client implementations.
Clients are created, reviewed, edited, and selected here.  Selecting a
client establishes it as the active client for the Requirements and
Deployment tabs.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from automation.core.active_client_state import Client
from automation.core.client_reachability import check_reachability
from automation.core.create_client import (
    CreateClientParams,
    create_client,
)
from automation.core.master_prd_prompt import (
    build_master_prd_prompt,
    save_master_prd_prompt,
)
from automation.ui.active_client_context import ActiveClientContext

# Default master database location
_DEFAULT_MASTER_DB = Path(__file__).resolve().parent.parent / "data" / "master.db"

# List column indices
_COL_NAME = 0
_COL_CODE = 1
_COL_PROJECT_FOLDER = 2
_COL_LAST_OPENED = 3

# Detail pane stack indices
_DETAIL_EMPTY = 0
_DETAIL_VIEW = 1
_DETAIL_CREATE = 2


def load_all_clients(master_db_path: str) -> list[Client]:
    """Load all clients from the master database.

    :param master_db_path: Path to the master database.
    :returns: List of Client objects sorted by last_opened_at DESC NULLS LAST.
    """
    conn = sqlite3.connect(master_db_path)
    try:
        rows = conn.execute(
            "SELECT id, name, code, description, project_folder, "
            "crm_platform, deployment_model, last_opened_at, "
            "created_at, updated_at "
            "FROM Client "
            "ORDER BY "
            "  CASE WHEN last_opened_at IS NULL THEN 1 ELSE 0 END, "
            "  last_opened_at DESC"
        ).fetchall()
        return [
            Client(
                id=r[0], name=r[1], code=r[2], description=r[3],
                project_folder=r[4], crm_platform=r[5],
                deployment_model=r[6], last_opened_at=r[7],
                created_at=r[8], updated_at=r[9],
            )
            for r in rows
        ]
    finally:
        conn.close()


class ClientsTab(QWidget):
    """The Clients tab — master/detail layout for client management.

    :param active_context: The application's active-client context.
    :param master_db_path: Path to the master database.
    :param parent: Parent widget.
    """

    def __init__(
        self,
        active_context: ActiveClientContext,
        master_db_path: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._active_context = active_context
        self._master_db_path = master_db_path or str(_DEFAULT_MASTER_DB)
        self._clients: list[Client] = []
        self._selected_client: Client | None = None
        self._build_ui()
        self._refresh_list()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # --- Left pane: client list ---
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(8, 8, 4, 8)

        # Header with "+ New Client" button
        header_layout = QHBoxLayout()
        header_label = QLabel("Clients")
        header_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_layout.addWidget(header_label)
        header_layout.addStretch()

        self._new_client_btn = QPushButton("+ New Client")
        self._new_client_btn.setStyleSheet(
            "QPushButton { padding: 6px 14px; font-size: 13px; "
            "background-color: #1F3864; color: white; border: none; "
            "border-radius: 4px; } "
            "QPushButton:hover { background-color: #2A4A7F; }"
        )
        self._new_client_btn.clicked.connect(self._show_create_form)
        header_layout.addWidget(self._new_client_btn)
        left_layout.addLayout(header_layout)

        # Client table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(
            ["Name", "Code", "Project Folder", "Last Opened"]
        )
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setVisible(False)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        self._table.currentCellChanged.connect(self._on_row_selected)
        left_layout.addWidget(self._table, stretch=1)

        # Empty state label (shown when no clients exist)
        self._empty_list_label = QLabel(
            "No clients exist yet.\n\n"
            "Click '+ New Client' above or in the detail pane\n"
            "to create your first client implementation."
        )
        self._empty_list_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_list_label.setStyleSheet(
            "font-size: 14px; color: #757575; padding: 40px;"
        )
        self._empty_list_label.setVisible(False)
        left_layout.addWidget(self._empty_list_label, stretch=1)

        splitter.addWidget(left_pane)

        # --- Right pane: detail stack ---
        self._detail_stack = QStackedWidget()

        # Index 0: Empty placeholder
        empty_detail = QWidget()
        empty_layout = QVBoxLayout(empty_detail)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._empty_detail_new_btn = QPushButton("+ New Client")
        self._empty_detail_new_btn.setStyleSheet(
            "QPushButton { padding: 10px 24px; font-size: 14px; "
            "background-color: #1F3864; color: white; border: none; "
            "border-radius: 4px; } "
            "QPushButton:hover { background-color: #2A4A7F; }"
        )
        self._empty_detail_new_btn.clicked.connect(self._show_create_form)

        empty_msg = QLabel("Select a client to view details.")
        empty_msg.setStyleSheet("font-size: 14px; color: #9E9E9E;")
        empty_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_msg)
        empty_layout.addWidget(
            self._empty_detail_new_btn,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        self._detail_stack.addWidget(empty_detail)

        # Index 1: Client detail view
        self._detail_view = self._build_detail_view()
        self._detail_stack.addWidget(self._detail_view)

        # Index 2: Create Client form
        self._create_form = self._build_create_form()
        self._detail_stack.addWidget(self._create_form)

        splitter.addWidget(self._detail_stack)
        splitter.setSizes([400, 500])

    # ------------------------------------------------------------------
    # Detail view
    # ------------------------------------------------------------------

    def _build_detail_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Client Details")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # Name (editable)
        layout.addWidget(QLabel("Name"))
        self._detail_name = QLineEdit()
        self._detail_name.editingFinished.connect(self._save_name)
        layout.addWidget(self._detail_name)

        # Code (read-only)
        layout.addWidget(QLabel("Code"))
        self._detail_code = QLineEdit()
        self._detail_code.setReadOnly(True)
        self._detail_code.setStyleSheet("background-color: #F5F5F5;")
        layout.addWidget(self._detail_code)

        # Description (editable)
        layout.addWidget(QLabel("Description"))
        self._detail_description = QTextEdit()
        self._detail_description.setMaximumHeight(80)
        layout.addWidget(self._detail_description)
        self._detail_desc_save_btn = QPushButton("Save Description")
        self._detail_desc_save_btn.setStyleSheet(
            "QPushButton { padding: 4px 12px; font-size: 12px; "
            "background-color: #FFA726; color: white; border: none; "
            "border-radius: 3px; } "
            "QPushButton:hover { background-color: #FB8C00; }"
        )
        self._detail_desc_save_btn.clicked.connect(self._save_description)
        layout.addWidget(
            self._detail_desc_save_btn,
            alignment=Qt.AlignmentFlag.AlignRight,
        )

        # Project Folder (read-only)
        layout.addWidget(QLabel("Project Folder"))
        self._detail_project_folder = QLineEdit()
        self._detail_project_folder.setReadOnly(True)
        self._detail_project_folder.setStyleSheet("background-color: #F5F5F5;")
        layout.addWidget(self._detail_project_folder)

        # Database File (read-only, reference)
        layout.addWidget(QLabel("Database File"))
        self._detail_db_file = QLineEdit()
        self._detail_db_file.setReadOnly(True)
        self._detail_db_file.setStyleSheet("background-color: #F5F5F5;")
        layout.addWidget(self._detail_db_file)

        # Created / Last Opened row
        ts_row = QHBoxLayout()
        ts_row.addWidget(QLabel("Created:"))
        self._detail_created = QLabel("")
        self._detail_created.setStyleSheet("color: #616161;")
        ts_row.addWidget(self._detail_created)
        ts_row.addStretch()
        ts_row.addWidget(QLabel("Last Opened:"))
        self._detail_last_opened = QLabel("")
        self._detail_last_opened.setStyleSheet("color: #616161;")
        ts_row.addWidget(self._detail_last_opened)
        layout.addLayout(ts_row)

        # CRM Platform / Deployment Model (conditional)
        self._crm_row = QWidget()
        crm_layout = QHBoxLayout(self._crm_row)
        crm_layout.setContentsMargins(0, 4, 0, 0)
        crm_layout.addWidget(QLabel("CRM Platform:"))
        self._detail_crm_platform = QLabel("")
        self._detail_crm_platform.setStyleSheet("color: #616161;")
        crm_layout.addWidget(self._detail_crm_platform)
        crm_layout.addStretch()
        crm_layout.addWidget(QLabel("Deployment Model:"))
        self._detail_deployment_model = QLabel("")
        self._detail_deployment_model.setStyleSheet("color: #616161;")
        crm_layout.addWidget(self._detail_deployment_model)
        layout.addWidget(self._crm_row)

        # Reachability indicator
        self._reachability_widget = QWidget()
        reach_layout = QHBoxLayout(self._reachability_widget)
        reach_layout.setContentsMargins(0, 8, 0, 0)
        self._reach_indicator = QLabel()
        self._reach_indicator.setFixedWidth(14)
        self._reach_indicator.setFixedHeight(14)
        self._reach_indicator.setStyleSheet(
            "border-radius: 7px; background-color: #4CAF50;"
        )
        reach_layout.addWidget(self._reach_indicator)
        self._reach_label = QLabel("Reachable")
        self._reach_label.setStyleSheet("font-size: 13px;")
        reach_layout.addWidget(self._reach_label)
        reach_layout.addStretch()
        layout.addWidget(self._reachability_widget)

        # Start Master PRD Interview button
        self._detail_start_master_prd_btn = QPushButton(
            "Start Master PRD Interview"
        )
        self._detail_start_master_prd_btn.setStyleSheet(
            "QPushButton { padding: 6px 16px; font-size: 12px; "
            "background-color: #FFA726; color: white; border: none; "
            "border-radius: 3px; } "
            "QPushButton:hover { background-color: #FB8C00; }"
        )
        self._detail_start_master_prd_btn.clicked.connect(
            self._on_start_master_prd_clicked
        )
        layout.addWidget(
            self._detail_start_master_prd_btn,
            alignment=Qt.AlignmentFlag.AlignRight,
        )

        layout.addStretch()
        return widget

    def _populate_detail(self, client: Client) -> None:
        self._detail_name.setText(client.name)
        self._detail_code.setText(client.code)
        self._detail_description.setPlainText(client.description or "")
        self._detail_project_folder.setText(client.project_folder)
        self._detail_db_file.setText(client.database_path)
        self._detail_created.setText(client.created_at or "—")
        self._detail_last_opened.setText(client.last_opened_at or "—")

        # CRM Platform / Deployment Model — show only if populated
        has_crm = client.crm_platform or client.deployment_model
        self._crm_row.setVisible(bool(has_crm))
        if has_crm:
            self._detail_crm_platform.setText(client.crm_platform or "—")
            self._detail_deployment_model.setText(client.deployment_model or "—")

        # Reachability
        result = check_reachability(client.project_folder, client.code)
        if result.is_reachable:
            self._reach_indicator.setStyleSheet(
                "border-radius: 7px; background-color: #4CAF50;"
            )
            self._reach_label.setText("Reachable")
            self._reach_label.setStyleSheet("font-size: 13px; color: #2E7D32;")
        else:
            self._reach_indicator.setStyleSheet(
                "border-radius: 7px; background-color: #F44336;"
            )
            self._reach_label.setText(f"Unreachable — {result.error}")
            self._reach_label.setStyleSheet("font-size: 13px; color: #C62828;")

    # ------------------------------------------------------------------
    # Create Client form
    # ------------------------------------------------------------------

    def _build_create_form(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Create New Client")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # Name
        layout.addWidget(QLabel("Name *"))
        self._create_name = QLineEdit()
        self._create_name.setPlaceholderText("e.g. Cleveland Business Mentoring")
        layout.addWidget(self._create_name)
        self._create_name_error = QLabel("")
        self._create_name_error.setStyleSheet("color: #C62828; font-size: 12px;")
        self._create_name_error.setVisible(False)
        layout.addWidget(self._create_name_error)

        # Code
        layout.addWidget(QLabel("Code *"))
        self._create_code = QLineEdit()
        self._create_code.setPlaceholderText("e.g. CBM")
        self._create_code.setMaxLength(10)
        layout.addWidget(self._create_code)
        self._create_code_error = QLabel("")
        self._create_code_error.setStyleSheet("color: #C62828; font-size: 12px;")
        self._create_code_error.setVisible(False)
        layout.addWidget(self._create_code_error)

        # Description
        layout.addWidget(QLabel("Description"))
        self._create_description = QTextEdit()
        self._create_description.setMaximumHeight(60)
        self._create_description.setPlaceholderText("Optional description")
        layout.addWidget(self._create_description)

        # Project Folder
        layout.addWidget(QLabel("Project Folder *"))
        folder_row = QHBoxLayout()
        self._create_folder = QLineEdit()
        self._create_folder.setPlaceholderText("/path/to/project")
        folder_row.addWidget(self._create_folder)
        browse_btn = QPushButton("Browse...")
        browse_btn.setStyleSheet(
            "QPushButton { padding: 4px 10px; font-size: 12px; "
            "background-color: #FFA726; color: white; border: none; "
            "border-radius: 3px; } "
            "QPushButton:hover { background-color: #FB8C00; }"
        )
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(browse_btn)
        layout.addLayout(folder_row)
        self._create_folder_error = QLabel("")
        self._create_folder_error.setStyleSheet("color: #C62828; font-size: 12px;")
        self._create_folder_error.setVisible(False)
        layout.addWidget(self._create_folder_error)

        # General error
        self._create_general_error = QLabel("")
        self._create_general_error.setStyleSheet(
            "color: #C62828; font-size: 13px; padding: 8px; "
            "background-color: #FFEBEE; border-radius: 4px;"
        )
        self._create_general_error.setVisible(False)
        self._create_general_error.setWordWrap(True)
        layout.addWidget(self._create_general_error)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(
            "QPushButton { padding: 6px 16px; font-size: 13px; "
            "background-color: #FFA726; color: white; border: none; "
            "border-radius: 4px; } "
            "QPushButton:hover { background-color: #FB8C00; }"
        )
        cancel_btn.clicked.connect(self._cancel_create)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(
            "QPushButton { padding: 6px 16px; font-size: 13px; "
            "background-color: #1F3864; color: white; border: none; "
            "border-radius: 4px; } "
            "QPushButton:hover { background-color: #2A4A7F; }"
        )
        save_btn.clicked.connect(self._save_create)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)
        layout.addStretch()
        return widget

    # ------------------------------------------------------------------
    # List management
    # ------------------------------------------------------------------

    def _refresh_list(self) -> None:
        """Reload clients from the master database and repopulate the table."""
        try:
            self._clients = load_all_clients(self._master_db_path)
        except Exception:
            self._clients = []

        has_clients = len(self._clients) > 0
        self._table.setVisible(has_clients)
        self._empty_list_label.setVisible(not has_clients)

        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(self._clients))
        for row, client in enumerate(self._clients):
            name_item = QTableWidgetItem(client.name)
            name_item.setData(Qt.ItemDataRole.UserRole, client.id)
            self._table.setItem(row, _COL_NAME, name_item)

            self._table.setItem(
                row, _COL_CODE, QTableWidgetItem(client.code)
            )
            self._table.setItem(
                row, _COL_PROJECT_FOLDER,
                QTableWidgetItem(client.project_folder),
            )
            self._table.setItem(
                row, _COL_LAST_OPENED,
                QTableWidgetItem(client.last_opened_at or "—"),
            )
        self._table.setSortingEnabled(True)

        # If no clients, show empty-state detail
        if not has_clients:
            self._detail_stack.setCurrentIndex(_DETAIL_EMPTY)

    def _find_client_by_id(self, client_id: int) -> Client | None:
        for c in self._clients:
            if c.id == client_id:
                return c
        return None

    # ------------------------------------------------------------------
    # Selection handling
    # ------------------------------------------------------------------

    def _on_row_selected(self, current_row: int, current_col: int,
                         prev_row: int, prev_col: int) -> None:
        if current_row < 0:
            self._selected_client = None
            self._detail_stack.setCurrentIndex(_DETAIL_EMPTY)
            return

        name_item = self._table.item(current_row, _COL_NAME)
        if not name_item:
            return

        client_id = name_item.data(Qt.ItemDataRole.UserRole)
        client = self._find_client_by_id(client_id)
        if not client:
            return

        self._selected_client = client
        self._populate_detail(client)
        self._detail_stack.setCurrentIndex(_DETAIL_VIEW)

        # Attempt activation — row selection and activation are the same gesture
        result = check_reachability(client.project_folder, client.code)
        if result.is_reachable:
            error = self._active_context.set_active_client(client)
            if error:
                from PySide6.QtWidgets import QMessageBox

                QMessageBox.warning(
                    self,
                    "Client Activation Failed",
                    f"Could not activate client {client.name}:\n\n{error}",
                )

    # ------------------------------------------------------------------
    # Inline editing (detail view)
    # ------------------------------------------------------------------

    def _save_name(self) -> None:
        if not self._selected_client:
            return
        new_name = self._detail_name.text().strip()
        if not new_name or new_name == self._selected_client.name:
            return
        try:
            conn = sqlite3.connect(self._master_db_path)
            try:
                conn.execute(
                    "UPDATE Client SET name = ?, updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = ?",
                    (new_name, self._selected_client.id),
                )
                conn.commit()
            finally:
                conn.close()
            self._selected_client.name = new_name
            self._refresh_list()
            self._select_row_by_id(self._selected_client.id)
        except sqlite3.Error:
            pass

    def _save_description(self) -> None:
        if not self._selected_client:
            return
        new_desc = self._detail_description.toPlainText().strip() or None
        try:
            conn = sqlite3.connect(self._master_db_path)
            try:
                conn.execute(
                    "UPDATE Client SET description = ?, "
                    "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (new_desc, self._selected_client.id),
                )
                conn.commit()
            finally:
                conn.close()
            self._selected_client.description = new_desc
        except sqlite3.Error:
            pass

    def _on_start_master_prd_clicked(self) -> None:
        """Generate the Master PRD interview prompt and copy to clipboard.

        Creates a master_prd WorkItem and AISession in the client database
        so the Import Results flow is available on the Requirements tab
        after the interview completes.
        """
        if self._selected_client is None:
            QMessageBox.information(self, "No Client", "Select a client first.")
            return

        client = self._selected_client
        db_path = client.database_path
        if not Path(db_path).exists():
            QMessageBox.information(
                self,
                "Database Not Found",
                f"Client database not found at:\n{db_path}\n\n"
                "The client may not have been fully created.",
            )
            return

        # Ensure WorkItem exists and is in_progress, then create AISession.
        try:
            conn = sqlite3.connect(db_path)
            try:
                row = conn.execute(
                    "SELECT id, status FROM WorkItem "
                    "WHERE item_type = 'master_prd'"
                ).fetchone()

                if row is None:
                    from automation.workflow.graph import create_project
                    wid = create_project(conn)
                    status = "ready"
                else:
                    wid, status = row

                if status == "ready":
                    from automation.workflow.transitions import start
                    start(conn, wid)
                elif status != "in_progress":
                    QMessageBox.information(
                        self,
                        "Work Item Not Available",
                        f"The Master PRD work item is '{status}'.\n\n"
                        "It must be 'ready' or 'in_progress' to "
                        "generate a new prompt.",
                    )
                    return

                prompt_text = build_master_prd_prompt(
                    client, work_item_id=wid,
                )

                conn.execute(
                    "INSERT INTO AISession (work_item_id, session_type, "
                    "generated_prompt, import_status, started_at) "
                    "VALUES (?, 'initial', ?, 'pending', CURRENT_TIMESTAMP)",
                    (wid, prompt_text),
                )
                conn.commit()
            finally:
                conn.close()
        except (sqlite3.Error, FileNotFoundError, ValueError) as exc:
            QMessageBox.warning(
                self,
                "Prompt Generation Failed",
                f"Could not set up the Master PRD session:\n\n{exc}",
            )
            return

        QApplication.clipboard().setText(prompt_text)

        saved_path = None
        if client.project_folder and Path(client.project_folder).is_dir():
            try:
                saved_path = save_master_prd_prompt(
                    prompt_text, client.project_folder, client.code
                )
            except OSError:
                pass  # Non-critical; prompt is already on clipboard

        msg_parts = [
            "Prompt copied to clipboard.",
            f"\nWork Item ID: {wid}",
        ]
        if saved_path:
            msg_parts.append(f"\nSaved to:\n{saved_path}")
        msg_parts.append(
            "\nPaste it into a new Claude.ai conversation to begin "
            "the Master PRD interview.\n\n"
            "When the interview is complete, go to the Requirements "
            "tab, select the Master PRD work item, and click "
            "'Import Results' to paste the JSON output."
        )

        QMessageBox.information(
            self,
            "Master PRD Prompt Ready",
            "\n".join(msg_parts),
        )

    # ------------------------------------------------------------------
    # Create Client
    # ------------------------------------------------------------------

    def _show_create_form(self) -> None:
        self._clear_create_form()
        self._detail_stack.setCurrentIndex(_DETAIL_CREATE)

    def _cancel_create(self) -> None:
        self._clear_create_form()
        if self._selected_client:
            self._populate_detail(self._selected_client)
            self._detail_stack.setCurrentIndex(_DETAIL_VIEW)
        else:
            self._detail_stack.setCurrentIndex(_DETAIL_EMPTY)

    def _clear_create_form(self) -> None:
        self._create_name.clear()
        self._create_code.clear()
        self._create_description.clear()
        self._create_folder.clear()
        self._create_name_error.setVisible(False)
        self._create_code_error.setVisible(False)
        self._create_folder_error.setVisible(False)
        self._create_general_error.setVisible(False)

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Select Project Folder"
        )
        if folder:
            self._create_folder.setText(folder)

    def _save_create(self) -> None:
        # Clear previous errors
        self._create_name_error.setVisible(False)
        self._create_code_error.setVisible(False)
        self._create_folder_error.setVisible(False)
        self._create_general_error.setVisible(False)

        params = CreateClientParams(
            name=self._create_name.text().strip(),
            code=self._create_code.text().strip().upper(),
            description=self._create_description.toPlainText().strip() or None,
            project_folder=self._create_folder.text().strip(),
        )

        result = create_client(params, self._master_db_path)

        if result.validation_errors:
            for ve in result.validation_errors:
                if ve.field == "name":
                    self._create_name_error.setText(ve.message)
                    self._create_name_error.setVisible(True)
                elif ve.field == "code":
                    self._create_code_error.setText(ve.message)
                    self._create_code_error.setVisible(True)
                elif ve.field == "project_folder":
                    self._create_folder_error.setText(ve.message)
                    self._create_folder_error.setVisible(True)
            return

        if not result.success:
            self._create_general_error.setText(result.error or "Unknown error.")
            self._create_general_error.setVisible(True)
            return

        # Success: refresh list, select new client, activate it
        self._refresh_list()
        client = result.client
        self._selected_client = client
        self._select_row_by_id(client.id)
        self._populate_detail(client)
        self._detail_stack.setCurrentIndex(_DETAIL_VIEW)

        # Activate the new client
        error = self._active_context.set_active_client(client)
        if error:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self,
                "Client Activation Failed",
                f"Client was created but could not be activated:\n\n{error}",
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _select_row_by_id(self, client_id: int) -> None:
        """Select the table row for the given client ID."""
        for row in range(self._table.rowCount()):
            item = self._table.item(row, _COL_NAME)
            if item and item.data(Qt.ItemDataRole.UserRole) == client_id:
                self._table.blockSignals(True)
                self._table.setCurrentCell(row, 0)
                self._table.blockSignals(False)
                return

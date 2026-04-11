"""Main application window — three-tab architecture (DEC-055)."""

import json
import logging
import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from automation.config import preferences
from automation.core.active_client_state import Client
from automation.db.migrations import run_master_migrations
from automation.ui.active_client_context import ActiveClientContext
from automation.ui.clients_tab import ClientsTab
from automation.ui.deployment.deployment_window import DeploymentWindow

logger = logging.getLogger(__name__)

# Default master database location
_DEFAULT_MASTER_DB = Path(__file__).resolve().parent.parent.parent / "automation" / "data" / "master.db"

# Tab indices
_TAB_CLIENTS = 0
_TAB_REQUIREMENTS = 1
_TAB_DEPLOYMENT = 2

# Tab name ↔ preference key mapping
_TAB_NAMES = {0: "clients", 1: "requirements", 2: "deployment"}
_TAB_INDICES = {"clients": 0, "requirements": 1, "deployment": 2}


class _RequirementsEmptyState(QWidget):
    """Empty-state placeholder shown when no client is active."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg = QLabel(
            "No client is currently active.\n\n"
            "Switch to the Clients tab to select or create a client\n"
            "before using the Requirements workspace."
        )
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setStyleSheet("font-size: 16px; color: #757575; line-height: 1.6;")
        layout.addWidget(msg)


class MainWindow(QMainWindow):
    """Main application window for CRM Builder.

    Three peer tabs: Clients, Requirements, Deployment (DEC-055).

    :param base_dir: Base directory for data and reports.
    """

    def __init__(self, base_dir: Path) -> None:
        super().__init__()
        self.base_dir = base_dir
        self._master_db_path = str(_DEFAULT_MASTER_DB)

        # Ensure master database exists and run migrations
        Path(self._master_db_path).parent.mkdir(parents=True, exist_ok=True)
        overrides = self._load_migration_overrides()
        try:
            conn = run_master_migrations(
                self._master_db_path,
                project_folder_overrides=overrides,
            )
            conn.close()
        except Exception as exc:
            logger.error(
                "Could not initialize master database at %s: %s",
                self._master_db_path,
                exc,
            )
            self._show_migration_failure(exc)

        # Active client context — shared across all tabs
        self._active_context = ActiveClientContext(
            self._master_db_path, parent=self
        )
        self._active_context.active_client_changed.connect(
            self._on_active_client_changed
        )

        self._build_ui()
        self._restore_state()

    def _load_migration_overrides(self) -> dict[str, str] | None:
        """Load project_folder overrides from migration-overrides.json.

        :returns: Override dict or None if the file is absent or invalid.
        """
        overrides_path = (
            Path(self._master_db_path).parent / "migration-overrides.json"
        )
        if not overrides_path.exists():
            return None
        try:
            with open(overrides_path) as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
            logger.warning("migration-overrides.json is not a JSON object")
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read migration-overrides.json: %s", exc)
        return None

    def _show_migration_failure(self, exc: Exception) -> None:
        """Show a blocking error dialog for master migration failure.

        :param exc: The exception that caused the failure.
        """
        overrides_path = (
            Path(self._master_db_path).parent / "migration-overrides.json"
        )
        QMessageBox.critical(
            None,
            "Database Migration Failed",
            "The master database migration failed and CRM Builder cannot "
            "start correctly.\n\n"
            f"Error: {exc}\n\n"
            "If this error mentions NULL project_folder, you can fix it by "
            "creating or updating the override file at:\n"
            f"  {overrides_path}\n\n"
            "The file should be a JSON object mapping client codes to "
            "project folder paths, e.g.:\n"
            '  {"CBM": "/path/to/project/folder"}\n\n'
            "After fixing, restart the application.",
        )
        import sys
        sys.exit(1)

    def _build_ui(self) -> None:
        """Build the main window layout with three-tab architecture."""
        self.setWindowTitle("CRM Builder")
        self.setMinimumSize(900, 650)

        central = QWidget()
        self.setCentralWidget(central)
        outer_layout = QVBoxLayout(central)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # --- Tab widget ---
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            "QTabBar::tab { padding: 8px 18px; font-size: 13px; } "
            "QTabBar::tab:selected { font-weight: bold; }"
        )
        outer_layout.addWidget(self._tabs)

        # Tab 0: Clients
        self._clients_tab = ClientsTab(
            self._active_context,
            master_db_path=self._master_db_path,
        )
        self._tabs.addTab(self._clients_tab, "Clients")

        # Tab 1: Requirements (empty state wrapper + RequirementsWindow)
        self._req_wrapper = QStackedWidget()

        self._req_empty = _RequirementsEmptyState()
        self._req_wrapper.addWidget(self._req_empty)  # index 0

        from automation.ui.requirements_window import RequirementsWindow
        self._requirements_window = RequirementsWindow(
            master_db_path=self._master_db_path,
            active_context=self._active_context,
            parent=self,
        )
        self._req_wrapper.addWidget(self._requirements_window)  # index 1
        self._req_wrapper.setCurrentIndex(0)  # Start with empty state

        self._tabs.addTab(
            self._req_wrapper, "Requirements (no client selected)"
        )

        # Tab 2: Deployment
        self._deployment_window = DeploymentWindow(
            active_context=self._active_context,
            master_db_path=self._master_db_path,
            parent=self,
        )
        self._tabs.addTab(
            self._deployment_window, "Deployment (no client selected)"
        )

        # Tab change persistence
        self._tabs.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, index: int) -> None:
        """Persist the active tab to preferences."""
        tab_name = _TAB_NAMES.get(index)
        if tab_name:
            preferences.set_last_active_tab(tab_name)

    def _on_active_client_changed(self, client: Client | None) -> None:
        """Update tab labels and empty-state wrappers on client change."""
        if client:
            self._tabs.setTabText(
                _TAB_REQUIREMENTS, f"Requirements \u2014 {client.name}"
            )
            self._tabs.setTabText(
                _TAB_DEPLOYMENT, f"Deployment \u2014 {client.name}"
            )
            self._req_wrapper.setCurrentIndex(1)  # Show RequirementsWindow
        else:
            self._tabs.setTabText(
                _TAB_REQUIREMENTS, "Requirements (no client selected)"
            )
            self._tabs.setTabText(
                _TAB_DEPLOYMENT, "Deployment (no client selected)"
            )
            self._req_wrapper.setCurrentIndex(0)  # Show empty state

    def _restore_state(self) -> None:
        """Restore last active tab and client from preferences (DEC-059)."""
        client_id = preferences.get_last_selected_client_id()
        tab_name = preferences.get_last_active_tab()

        restored_client = False
        if client_id is not None:
            client = self._load_client_by_id(client_id)
            if client:
                error = self._active_context.set_active_client(client)
                if error is None:
                    restored_client = True
                else:
                    logger.error(
                        "Could not restore client %s (id=%d): %s",
                        client.name,
                        client.id,
                        error,
                    )

        if restored_client and tab_name:
            tab_index = _TAB_INDICES.get(tab_name, _TAB_CLIENTS)
            self._tabs.setCurrentIndex(tab_index)
        else:
            self._tabs.setCurrentIndex(_TAB_CLIENTS)

    def _load_client_by_id(self, client_id: int) -> Client | None:
        """Load a single client from the master database by ID."""
        try:
            conn = sqlite3.connect(self._master_db_path)
            try:
                row = conn.execute(
                    "SELECT id, name, code, description, project_folder, "
                    "crm_platform, deployment_model, last_opened_at, "
                    "created_at, updated_at "
                    "FROM Client WHERE id = ?",
                    (client_id,),
                ).fetchone()
            finally:
                conn.close()
            if row:
                return Client(
                    id=row[0], name=row[1], code=row[2], description=row[3],
                    project_folder=row[4], crm_platform=row[5],
                    deployment_model=row[6], last_opened_at=row[7],
                    created_at=row[8], updated_at=row[9],
                )
        except Exception:
            pass
        return None

    def closeEvent(self, event) -> None:
        """Clean up resources on window close."""
        if hasattr(self, "_requirements_window"):
            self._requirements_window.cleanup()
        if hasattr(self, "_deployment_window"):
            self._deployment_window.cleanup()
        if hasattr(self, "_active_context"):
            self._active_context.cleanup()
        super().closeEvent(event)

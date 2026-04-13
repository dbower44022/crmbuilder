"""Deployment tab container — sidebar + header + content (Section 14.12).

Mirrors the Requirements tab's sidebar+content architecture.  Five sidebar
entries: Instances, Deploy, Configure, Verify, Output.  A persistent
header above the content area holds the active-instance picker and
phase status banner.
"""

from __future__ import annotations

import logging
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from automation.ui.deployment.configure_entry import ConfigureEntry
from automation.ui.deployment.deploy_entry import DeployEntry
from automation.ui.deployment.deployment_logic import (
    load_instances,
)
from automation.ui.deployment.instance_picker import InstancePicker
from automation.ui.deployment.instances_entry import InstancesEntry
from automation.ui.deployment.output_entry import OutputEntry
from automation.ui.deployment.phase_banner import PhaseBanner
from automation.ui.deployment.run_history_entry import RunHistoryEntry

logger = logging.getLogger(__name__)

# Sidebar entry names
_ENTRIES = ["Instances", "Deploy", "Configure", "Run History", "Output"]

# Content stack indices
_IDX_INSTANCES = 0
_IDX_DEPLOY = 1
_IDX_CONFIGURE = 2
_IDX_RUN_HISTORY = 3
_IDX_OUTPUT = 4

# Entries that show the phase status banner (§14.12.2)
_BANNER_ENTRIES = {"Deploy", "Configure"}

_NO_CLIENT_MSG = (
    "No client is currently active.\n\n"
    "Switch to the Clients tab to select or create a client\n"
    "before using the Deployment workspace."
)


class DeploymentWindow(QWidget):
    """Deployment tab container — sidebar + picker/banner + content area.

    :param active_context: The ActiveClientContext shared across tabs.
    :param parent: Parent widget.
    """

    def __init__(self, active_context=None, master_db_path: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self._active_context = active_context
        self._master_db_path = master_db_path
        self._conn: sqlite3.Connection | None = None
        self._project_folder: str | None = None
        self._client_id: int | None = None

        self._build_ui()

        if self._active_context is not None:
            self._active_context.active_client_changed.connect(
                self._on_active_client_changed
            )

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # --- No-client empty state ---
        self._no_client_label = QLabel(_NO_CLIENT_MSG)
        self._no_client_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_client_label.setStyleSheet(
            "font-size: 16px; color: #757575; line-height: 1.6;"
        )
        outer.addWidget(self._no_client_label)

        # --- Main content area (hidden when no client) ---
        self._main_area = QWidget()
        main_layout = QVBoxLayout(self._main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Header: picker + banner
        self._picker = InstancePicker()
        self._picker.instance_changed.connect(self._on_instance_changed)
        main_layout.addWidget(self._picker)

        self._banner = PhaseBanner()
        self._banner.status_changed.connect(self._on_banner_status_changed)
        main_layout.addWidget(self._banner)

        # Sidebar + content
        body = QHBoxLayout()

        self._sidebar = QListWidget()
        self._sidebar.setMaximumWidth(160)
        self._sidebar.setStyleSheet(
            "QListWidget { font-size: 13px; } "
            "QListWidget::item { padding: 8px; } "
            "QListWidget::item:selected { "
            "   background-color: #E3F2FD; color: #1565C0; font-weight: bold; }"
        )
        for label in _ENTRIES:
            self._sidebar.addItem(label)
        self._sidebar.setCurrentRow(0)
        self._sidebar.currentRowChanged.connect(self._on_sidebar_changed)
        body.addWidget(self._sidebar)

        # Content stack
        self._stack = QStackedWidget()

        self._instances_entry = InstancesEntry()
        self._instances_entry.instance_created.connect(self._on_instance_created)
        self._instances_entry.navigate_requested.connect(self._on_navigate)
        self._stack.addWidget(self._instances_entry)  # 0

        self._deploy_entry = DeployEntry()
        self._stack.addWidget(self._deploy_entry)  # 1

        self._configure_entry = ConfigureEntry()
        self._stack.addWidget(self._configure_entry)  # 2

        self._run_history_entry = RunHistoryEntry()
        self._stack.addWidget(self._run_history_entry)  # 3

        self._output_entry = OutputEntry()
        self._stack.addWidget(self._output_entry)  # 4

        # Give configure entry a reference to the output entry for log streaming
        self._configure_entry.set_output_entry(self._output_entry)

        body.addWidget(self._stack, stretch=1)
        main_layout.addLayout(body, stretch=1)

        outer.addWidget(self._main_area)

        # Start in no-client state
        self._main_area.setVisible(False)

    # ------------------------------------------------------------------
    # Active client context
    # ------------------------------------------------------------------

    def _on_active_client_changed(self, client_obj) -> None:
        """Handle active client change from the Clients tab."""
        if client_obj is not None:
            self._conn = self._active_context.connection
            self._project_folder = client_obj.project_folder
            self._client_id = client_obj.id
            self._no_client_label.setVisible(False)
            self._main_area.setVisible(True)

            # Pass client context for wizard launch
            if self._master_db_path and self._client_id:
                self._deploy_entry.set_client_context(
                    self._master_db_path, self._client_id,
                )
                self._instances_entry.set_client_context(
                    self._master_db_path, self._client_id,
                )

            # Refresh picker, then the current entry
            if self._conn:
                self._picker.refresh(self._conn)
            self._sidebar.setCurrentRow(0)
            self._refresh_current_entry()
        else:
            self._conn = None
            self._project_folder = None
            self._client_id = None
            self._no_client_label.setVisible(True)
            self._main_area.setVisible(False)

    # ------------------------------------------------------------------
    # Sidebar navigation
    # ------------------------------------------------------------------

    def _on_sidebar_changed(self, index: int) -> None:
        """Handle sidebar entry selection."""
        if index < 0 or index >= len(_ENTRIES):
            return
        self._stack.setCurrentIndex(index)

        entry_name = _ENTRIES[index]
        # Show/hide banner per §14.12.2
        if entry_name in _BANNER_ENTRIES and self._conn:
            self._banner.setVisible(True)
            self._banner.set_entry(entry_name, self._conn)
        else:
            self._banner.setVisible(False)

        self._refresh_current_entry()

    # ------------------------------------------------------------------
    # Instance picker
    # ------------------------------------------------------------------

    def _on_instance_changed(self, instance) -> None:
        """Handle active instance selection change."""
        self._refresh_current_entry()

    def _on_instance_created(self) -> None:
        """Handle instance creation/update from the Instances entry."""
        if self._conn:
            self._picker.refresh(self._conn)

    def _on_navigate(self, sidebar_index: int) -> None:
        """Handle navigation request from an entry (e.g. Instances → Configure)."""
        if 0 <= sidebar_index < len(_ENTRIES):
            self._sidebar.setCurrentRow(sidebar_index)

    # ------------------------------------------------------------------
    # Banner
    # ------------------------------------------------------------------

    def _on_banner_status_changed(self) -> None:
        """Handle phase status change from the banner."""
        # Refresh the current entry in case status affects display
        self._refresh_current_entry()

    # ------------------------------------------------------------------
    # Entry refresh
    # ------------------------------------------------------------------

    def _refresh_current_entry(self) -> None:
        """Refresh the currently visible entry view."""
        if not self._conn:
            return

        index = self._sidebar.currentRow()
        instance = self._picker.selected_instance
        instances = load_instances(self._conn)
        has_instances = len(instances) > 0

        if index == _IDX_INSTANCES:
            self._instances_entry.refresh(self._conn)
        elif index == _IDX_DEPLOY:
            self._deploy_entry.refresh(self._conn, instance, has_instances)
        elif index == _IDX_CONFIGURE:
            self._configure_entry.refresh(
                self._conn, instance, self._project_folder, has_instances
            )
        elif index == _IDX_RUN_HISTORY:
            self._run_history_entry.refresh(
                self._conn, instance, self._project_folder, has_instances
            )
        elif index == _IDX_OUTPUT:
            self._output_entry.refresh(self._conn, instance, has_instances)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Release resources on shutdown."""
        # Connection is owned by ActiveClientContext — do not close here.
        self._conn = None

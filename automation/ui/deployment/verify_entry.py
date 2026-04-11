"""Verify sidebar entry — verification spec + run action (Section 14.12.8).

Thin wrapper over existing verification execution, scoped to the active
instance from the picker.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from automation.ui.deployment.deployment_logic import InstanceRow

_SECONDARY_STYLE = (
    "QPushButton { background-color: #FFA726; color: white; "
    "border-radius: 4px; padding: 6px 14px; font-size: 12px; } "
    "QPushButton:hover { background-color: #FB8C00; }"
)

_EMPTY_NO_INSTANCES = (
    "No CRM instances available.\n\n"
    "Go to the Instances entry to create one, or run the Deploy Wizard."
)

_EMPTY_NO_INSTANCE_SELECTED = (
    "Select an instance from the picker above to run verification."
)


class VerifyEntry(QWidget):
    """Verification spec display and run action.

    :param parent: Parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn: sqlite3.Connection | None = None
        self._instance: InstanceRow | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Run button
        self._run_btn = QPushButton("Run Verification")
        self._run_btn.setStyleSheet(_SECONDARY_STYLE)
        self._run_btn.clicked.connect(self._on_run)
        layout.addWidget(self._run_btn)

        # Empty / status area
        self._status_label = QLabel()
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet(
            "font-size: 14px; color: #757575; padding: 40px;"
        )
        layout.addWidget(self._status_label)

        layout.addStretch()

    def refresh(
        self,
        conn: sqlite3.Connection,
        instance: InstanceRow | None,
        has_instances: bool,
    ) -> None:
        """Reload state for the verify entry.

        :param conn: Per-client database connection.
        :param instance: Active instance from the picker.
        :param has_instances: Whether the client has any instances.
        """
        self._conn = conn
        self._instance = instance

        if not has_instances:
            self._status_label.setText(_EMPTY_NO_INSTANCES)
            self._run_btn.setVisible(False)
            return

        self._run_btn.setVisible(True)

        if instance is None:
            self._status_label.setText(_EMPTY_NO_INSTANCE_SELECTED)
        else:
            self._status_label.setText(
                f"Verification will run against: {instance.name} ({instance.environment})\n\n"
                "Click 'Run Verification' to execute test cases against this instance."
            )

    def _on_run(self) -> None:
        """Handle Run Verification — placeholder for espo_impl integration."""
        # The existing verification execution path will be wired here.
        pass

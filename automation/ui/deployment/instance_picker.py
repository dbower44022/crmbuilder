"""Active-instance picker dropdown (Section 14.12.2).

Populates from the active client's Instance table.  Displays each
instance as ``"name (environment)"`` and defaults to the client's
default instance on first load in a session.

Also shows an EspoCRM version badge for self-hosted instances, fed by
a background ``VersionCheckWorker`` triggered on selection change.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from automation.core.deployment.deploy_config_repo import load_deploy_config
from automation.core.deployment.upgrade_ssh import is_upgrade_available
from automation.ui.deployment.deployment_logic import (
    InstanceRow,
    get_default_instance_id,
    load_instances,
    picker_display_text,
)


class InstancePicker(QWidget):
    """Dropdown for selecting the active instance.

    Emits :attr:`instance_changed` whenever the selection changes.

    :param parent: Parent widget.
    """

    instance_changed = Signal(object)  # InstanceRow | None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._instances: list[InstanceRow] = []
        self._conn: sqlite3.Connection | None = None
        self._version_worker = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        picker_row = QHBoxLayout()
        picker_row.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel("Active Instance:")
        self._label.setStyleSheet("font-weight: bold; font-size: 13px;")
        picker_row.addWidget(self._label)

        self._combo = QComboBox()
        self._combo.setMinimumWidth(250)
        self._combo.currentIndexChanged.connect(self._on_selection_changed)
        picker_row.addWidget(self._combo)

        picker_row.addStretch()

        self._version_badge = QLabel("")
        self._version_badge.setStyleSheet(
            "color: #9E9E9E; font-size: 11px;"
        )
        picker_row.addWidget(self._version_badge)
        outer.addLayout(picker_row)

        # Connect to our own signal so the badge refreshes whenever the
        # selection changes — both refresh() (programmatic) and user
        # selection paths emit instance_changed.
        self.instance_changed.connect(self._refresh_version_badge)

    @property
    def selected_instance(self) -> InstanceRow | None:
        """Return the currently selected instance, or None."""
        idx = self._combo.currentIndex()
        if idx < 0 or idx >= len(self._instances):
            return None
        return self._instances[idx]

    def refresh(self, conn: sqlite3.Connection) -> None:
        """Reload instances from the database.

        Preserves the current selection if possible; otherwise selects the
        default instance.

        :param conn: Per-client database connection.
        """
        self._conn = conn
        prev_id = None
        if self.selected_instance:
            prev_id = self.selected_instance.id

        self._combo.blockSignals(True)
        self._combo.clear()
        self._instances = load_instances(conn)

        for inst in self._instances:
            self._combo.addItem(picker_display_text(inst))

        # Restore previous selection or select default
        selected_idx = -1
        if prev_id is not None:
            for i, inst in enumerate(self._instances):
                if inst.id == prev_id:
                    selected_idx = i
                    break

        if selected_idx < 0:
            # Select the default instance
            default_id = get_default_instance_id(conn)
            if default_id is not None:
                for i, inst in enumerate(self._instances):
                    if inst.id == default_id:
                        selected_idx = i
                        break

        if selected_idx < 0 and self._instances:
            selected_idx = 0

        if selected_idx >= 0:
            self._combo.setCurrentIndex(selected_idx)

        self._combo.blockSignals(False)

        # Emit current selection
        self.instance_changed.emit(self.selected_instance)

    def _on_selection_changed(self, index: int) -> None:
        """Handle combo box selection change."""
        if 0 <= index < len(self._instances):
            self.instance_changed.emit(self._instances[index])
        else:
            self.instance_changed.emit(None)

    def _refresh_version_badge(self, instance: InstanceRow | None) -> None:
        """Update the EspoCRM version badge for the selected instance.

        Reads any cached version state from InstanceDeployConfig
        synchronously, then kicks off a background VersionCheckWorker
        to refresh it.
        """
        if self._conn is None or instance is None:
            self._version_badge.setText("")
            return

        config = load_deploy_config(self._conn, instance.id)
        if config is None or config.scenario != "self_hosted":
            self._version_badge.setText("")
            return

        self._render_badge(
            config.current_espocrm_version,
            config.latest_espocrm_version,
        )
        self._kick_off_version_check(config)

    def _render_badge(
        self, current: str | None, latest: str | None
    ) -> None:
        if not current and not latest:
            self._version_badge.setText("EspoCRM version: unknown")
            self._version_badge.setStyleSheet(
                "color: #9E9E9E; font-size: 11px;"
            )
            return
        if is_upgrade_available(current, latest):
            self._version_badge.setText(
                f"EspoCRM {current} \u2192 {latest} available"
            )
            self._version_badge.setStyleSheet(
                "color: #FFA726; font-weight: bold; font-size: 11px;"
            )
        else:
            self._version_badge.setText(
                f"EspoCRM {current or latest} \u2014 up to date"
            )
            self._version_badge.setStyleSheet(
                "color: #4CAF50; font-size: 11px;"
            )

    def _kick_off_version_check(self, config) -> None:
        if self._version_worker is not None:
            return
        db_path = self._db_path()
        if db_path is None:
            return
        from automation.ui.deployment.upgrade_worker import VersionCheckWorker

        self._version_worker = VersionCheckWorker(config, db_path, self)
        self._version_worker.versions_detected.connect(
            self._on_versions_detected
        )
        self._version_worker.finished.connect(self._on_version_worker_done)
        self._version_worker.start()

    def _on_versions_detected(self, current: str, latest: str) -> None:
        self._render_badge(current or None, latest or None)

    def _on_version_worker_done(self) -> None:
        self._version_worker = None

    def _db_path(self) -> str | None:
        if self._conn is None:
            return None
        try:
            row = self._conn.execute("PRAGMA database_list").fetchone()
            return row[2] if row else None
        except Exception:
            return None

"""Active-instance picker dropdown (Section 14.12.2).

Populates from the active client's Instance table.  Displays each
instance as ``"name (environment)"`` and defaults to the client's
default instance on first load in a session.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget

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

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel("Active Instance:")
        self._label.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(self._label)

        self._combo = QComboBox()
        self._combo.setMinimumWidth(250)
        self._combo.currentIndexChanged.connect(self._on_selection_changed)
        layout.addWidget(self._combo)

        layout.addStretch()

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

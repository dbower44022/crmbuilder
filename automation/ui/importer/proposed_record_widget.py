"""Proposed record widget (Section 14.5.5).

Renders a single proposed record with action badge, field values,
conflict indicators, dependency info, and accept/modify/reject controls.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from automation.importer.proposed import ProposedRecord
from automation.ui.common.action_badges import ActionBadge
from automation.ui.common.severity_indicators import SeverityIndicator
from automation.ui.importer.import_logic import RecordAction


class ProposedRecordWidget(QWidget):
    """Widget for a single proposed record in the review stage.

    :param record: The ProposedRecord.
    :param current_values: For updates, dict of current field values.
    :param parent: Parent widget.
    """

    action_changed = Signal(str, str)  # (source_payload_path, action_value)
    modify_accepted = Signal(str, dict)  # (source_payload_path, modified_values)

    def __init__(
        self,
        record: ProposedRecord,
        current_values: dict[str, Any] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._record = record
        self._current_values = current_values or {}
        self._record_action = RecordAction.ACCEPTED
        self._edit_widgets: dict[str, QLineEdit] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        # Top row: action badge + key fields
        top = QHBoxLayout()

        # Action badge (Create / Update)
        badge = ActionBadge(record.action.title())
        top.addWidget(badge)

        # Modified badge (hidden initially)
        self._modified_badge = ActionBadge("Modified")
        self._modified_badge.setStyleSheet(
            "background-color: #FFF3E0; color: #E65100; "
            "border-radius: 4px; padding: 2px 8px; font-size: 11px;"
        )
        self._modified_badge.setVisible(False)
        top.addWidget(self._modified_badge)

        # Key identifying fields
        name = record.values.get("name", record.values.get("title", ""))
        code = record.values.get("code", record.values.get("identifier", ""))
        key_text = f"{name}"
        if code:
            key_text += f" ({code})"
        key_text += f" — {record.table_name}"
        key_label = QLabel(key_text)
        key_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        top.addWidget(key_label, stretch=1)

        # Dependency indicator
        if record.intra_batch_refs:
            dep_label = QLabel(f"{len(record.intra_batch_refs)} ref(s)")
            dep_label.setStyleSheet("font-size: 10px; color: #757575;")
            top.addWidget(dep_label)

        layout.addLayout(top)

        # Field values
        self._fields_widget = QWidget()
        self._fields_layout = QVBoxLayout(self._fields_widget)
        self._fields_layout.setContentsMargins(16, 2, 0, 2)
        self._build_field_display()
        layout.addWidget(self._fields_widget)

        # Conflict indicators
        for conflict in record.conflicts:
            severity_map = {"error": "high", "warning": "medium", "info": "low"}
            row = QHBoxLayout()
            indicator = SeverityIndicator(severity_map.get(conflict.severity, "low"))
            row.addWidget(indicator)
            msg = QLabel(conflict.message)
            msg.setStyleSheet("font-size: 11px;")
            msg.setWordWrap(True)
            row.addWidget(msg, stretch=1)
            layout.addLayout(row)

        # Action controls
        self._actions_widget = QWidget()
        actions_layout = QHBoxLayout(self._actions_widget)
        actions_layout.setContentsMargins(16, 4, 0, 0)
        actions_layout.setSpacing(8)

        self._accept_btn = QPushButton("Accept")
        self._accept_btn.setStyleSheet(
            "QPushButton { background-color: #E8F5E9; color: #2E7D32; "
            "border-radius: 3px; padding: 4px 12px; font-size: 11px; "
            "font-weight: bold; } "
            "QPushButton:hover { background-color: #C8E6C9; }"
        )
        self._accept_btn.clicked.connect(lambda: self._set_action(RecordAction.ACCEPTED))
        actions_layout.addWidget(self._accept_btn)

        modify_btn = QPushButton("Modify")
        modify_btn.setStyleSheet(
            "QPushButton { background-color: #FFF3E0; color: #E65100; "
            "border-radius: 3px; padding: 4px 12px; font-size: 11px; } "
            "QPushButton:hover { background-color: #FFE0B2; }"
        )
        modify_btn.clicked.connect(self._enter_edit_mode)
        actions_layout.addWidget(modify_btn)

        reject_btn = QPushButton("Reject")
        reject_btn.setStyleSheet(
            "QPushButton { background-color: #FFEBEE; color: #C62828; "
            "border-radius: 3px; padding: 4px 12px; font-size: 11px; } "
            "QPushButton:hover { background-color: #FFCDD2; }"
        )
        reject_btn.clicked.connect(lambda: self._set_action(RecordAction.REJECTED))
        actions_layout.addWidget(reject_btn)

        actions_layout.addStretch()

        # Edit mode buttons (hidden initially)
        self._edit_actions = QWidget()
        edit_layout = QHBoxLayout(self._edit_actions)
        edit_layout.setContentsMargins(16, 4, 0, 0)

        accept_changes_btn = QPushButton("Accept with Changes")
        accept_changes_btn.setStyleSheet(
            "QPushButton { background-color: #E8F5E9; color: #2E7D32; "
            "border-radius: 3px; padding: 4px 12px; font-size: 11px; } "
            "QPushButton:hover { background-color: #C8E6C9; }"
        )
        accept_changes_btn.clicked.connect(self._accept_with_changes)
        edit_layout.addWidget(accept_changes_btn)

        cancel_edit_btn = QPushButton("Cancel Edit")
        cancel_edit_btn.setStyleSheet("font-size: 11px;")
        cancel_edit_btn.clicked.connect(self._cancel_edit)
        edit_layout.addWidget(cancel_edit_btn)
        edit_layout.addStretch()

        self._edit_actions.setVisible(False)
        layout.addWidget(self._actions_widget)
        layout.addWidget(self._edit_actions)

        # Visual state
        self._update_visual_state()

    def _build_field_display(self) -> None:
        """Build the field value display."""
        while self._fields_layout.count():
            child = self._fields_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self._edit_widgets.clear()

        for field_name, value in self._record.values.items():
            row = QHBoxLayout()

            name_label = QLabel(f"{field_name}:")
            name_label.setStyleSheet("font-size: 11px; color: #757575; min-width: 120px;")
            row.addWidget(name_label)

            if self._record.action == "update" and field_name in self._current_values:
                current = self._current_values.get(field_name, "")
                if str(current) != str(value):
                    # Changed field — show current vs proposed
                    current_label = QLabel(str(current))
                    current_label.setStyleSheet(
                        "font-size: 11px; color: #9E9E9E; text-decoration: line-through;"
                    )
                    row.addWidget(current_label)

                    arrow = QLabel(" → ")
                    arrow.setStyleSheet("font-size: 11px; color: #757575;")
                    row.addWidget(arrow)

                    value_label = QLabel(str(value))
                    value_label.setStyleSheet("font-size: 11px; font-weight: bold;")
                    row.addWidget(value_label, stretch=1)
                else:
                    # Unchanged field — subdued
                    value_label = QLabel(str(value))
                    value_label.setStyleSheet("font-size: 11px; color: #9E9E9E;")
                    row.addWidget(value_label, stretch=1)
            else:
                value_label = QLabel(str(value))
                value_label.setStyleSheet("font-size: 11px;")
                row.addWidget(value_label, stretch=1)

            self._fields_layout.addLayout(row)

    def _build_edit_fields(self) -> None:
        """Replace field display with editable inputs."""
        while self._fields_layout.count():
            child = self._fields_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self._edit_widgets.clear()

        for field_name, value in self._record.values.items():
            row = QHBoxLayout()

            name_label = QLabel(f"{field_name}:")
            name_label.setStyleSheet("font-size: 11px; color: #757575; min-width: 120px;")
            row.addWidget(name_label)

            edit = QLineEdit(str(value) if value is not None else "")
            edit.setStyleSheet("font-size: 11px;")
            row.addWidget(edit, stretch=1)
            self._edit_widgets[field_name] = edit

            self._fields_layout.addLayout(row)

    def _set_action(self, action: RecordAction) -> None:
        """Set the record action and update visuals."""
        self._record_action = action
        self._modified_badge.setVisible(action == RecordAction.MODIFIED)
        self._update_visual_state()
        self.action_changed.emit(
            self._record.source_payload_path, action.value
        )

    def _enter_edit_mode(self) -> None:
        """Switch to inline edit mode."""
        self._build_edit_fields()
        self._actions_widget.setVisible(False)
        self._edit_actions.setVisible(True)

    def _accept_with_changes(self) -> None:
        """Accept the record with modified values."""
        modified = {}
        for field_name, edit in self._edit_widgets.items():
            new_val = edit.text()
            original = str(self._record.values.get(field_name, ""))
            if new_val != original:
                modified[field_name] = new_val

        self._record_action = RecordAction.MODIFIED
        self._modified_badge.setVisible(True)
        self._build_field_display()
        self._actions_widget.setVisible(True)
        self._edit_actions.setVisible(False)
        self._update_visual_state()

        self.modify_accepted.emit(self._record.source_payload_path, modified)
        self.action_changed.emit(
            self._record.source_payload_path, RecordAction.MODIFIED.value
        )

    def _cancel_edit(self) -> None:
        """Cancel edit mode and revert to display."""
        self._build_field_display()
        self._actions_widget.setVisible(True)
        self._edit_actions.setVisible(False)

    def _update_visual_state(self) -> None:
        """Update the widget's visual style based on current action."""
        if self._record_action == RecordAction.REJECTED:
            self.setStyleSheet("background-color: #FAFAFA; opacity: 0.6;")
            self._accept_btn.setText("Accept")
        elif self._record_action == RecordAction.MODIFIED:
            self.setStyleSheet("background-color: #FFF8E1;")
            self._accept_btn.setText("Accept (Original)")
        else:
            self.setStyleSheet("")
            self._accept_btn.setText("Accept")

    @property
    def record_action(self) -> RecordAction:
        """Return the current record action."""
        return self._record_action

    @property
    def source_payload_path(self) -> str:
        """Return the record's source_payload_path."""
        return self._record.source_payload_path

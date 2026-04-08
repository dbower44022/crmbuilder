"""Stage 5 — Review (Section 14.5.5).

Proposed records grouped by category with accept/modify/reject controls.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from automation.importer.proposed import ProposedBatch
from automation.ui.common.confirmation import confirm_action
from automation.ui.common.error_display import show_info
from automation.ui.importer.import_logic import (
    CATEGORY_LABELS,
    ImportState,
    RecordAction,
    count_by_action,
    get_cascade_reject_set_from_batch,
    get_records_by_category,
    get_unresolved_errors,
    set_category_action,
    set_record_action,
)
from automation.ui.importer.proposed_record_widget import ProposedRecordWidget


class CategoryGroup(QWidget):
    """A collapsible group of proposed records for one category.

    :param table_name: The category/table name.
    :param records: ProposedRecord objects in this category.
    :param state: The import state.
    :param batch: The full ProposedBatch.
    :param parent: Parent widget.
    """

    state_changed = Signal()

    def __init__(
        self, table_name, records, state, batch, parent=None
    ) -> None:
        super().__init__(parent)
        self._table_name = table_name
        self._state = state
        self._batch = batch

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)

        # Header with count + bulk actions
        header = QHBoxLayout()
        label_text = CATEGORY_LABELS.get(table_name, table_name)
        header_label = QLabel(f"{label_text} ({len(records)})")
        header_label.setStyleSheet(
            "font-size: 13px; font-weight: bold; padding: 4px 8px; "
            "background-color: #E8EAF6; border-radius: 2px;"
        )
        header.addWidget(header_label, stretch=1)

        accept_all_btn = QPushButton("Accept All")
        accept_all_btn.setStyleSheet(
            "QPushButton { background-color: #E8F5E9; color: #2E7D32; "
            "border-radius: 3px; padding: 3px 8px; font-size: 10px; } "
            "QPushButton:hover { background-color: #C8E6C9; }"
        )
        accept_all_btn.clicked.connect(
            lambda: self._bulk_action(RecordAction.ACCEPTED)
        )
        header.addWidget(accept_all_btn)

        reject_all_btn = QPushButton("Reject All")
        reject_all_btn.setStyleSheet(
            "QPushButton { background-color: #FFEBEE; color: #C62828; "
            "border-radius: 3px; padding: 3px 8px; font-size: 10px; } "
            "QPushButton:hover { background-color: #FFCDD2; }"
        )
        reject_all_btn.clicked.connect(
            lambda: self._bulk_action(RecordAction.REJECTED)
        )
        header.addWidget(reject_all_btn)

        layout.addLayout(header)

        # Record widgets
        self._record_widgets: list[ProposedRecordWidget] = []
        # Sort: rejected at bottom
        accepted_records = []
        rejected_records = []
        for rec in records:
            rec_state = state.records.get(rec.source_payload_path)
            if rec_state and rec_state.record_action == RecordAction.REJECTED:
                rejected_records.append(rec)
            else:
                accepted_records.append(rec)

        for rec in accepted_records + rejected_records:
            widget = ProposedRecordWidget(rec)
            widget.action_changed.connect(self._on_record_action)
            widget.modify_accepted.connect(self._on_modify_accepted)
            layout.addWidget(widget)
            self._record_widgets.append(widget)

    def _bulk_action(self, action: RecordAction) -> None:
        """Apply bulk action to all records in this category."""
        if action == RecordAction.REJECTED:
            # Check for cascade
            has_deps = False
            for widget in self._record_widgets:
                deps = get_cascade_reject_set_from_batch(
                    self._batch, widget.source_payload_path
                )
                if deps:
                    has_deps = True
                    break
            if has_deps:
                if not confirm_action(
                    self, "Cascade Reject",
                    "Some records in this category have dependents in other "
                    "categories. Reject all including dependents?"
                ):
                    return

        set_category_action(self._state, self._table_name, action)
        self.state_changed.emit()

    def _on_record_action(self, path: str, action_value: str) -> None:
        """Handle individual record action change."""
        action = RecordAction(action_value)

        if action == RecordAction.REJECTED:
            deps = get_cascade_reject_set_from_batch(self._batch, path)
            if deps:
                if confirm_action(
                    self, "Cascade Reject",
                    f"This record has {len(deps)} dependent record(s). "
                    "Cascade-reject all dependents?"
                ):
                    for dep_path in deps:
                        set_record_action(self._state, dep_path, RecordAction.REJECTED)

        set_record_action(self._state, path, action)
        self.state_changed.emit()

    def _on_modify_accepted(self, path: str, modified_values: dict) -> None:
        """Handle modify-accepted for a record."""
        set_record_action(
            self._state, path, RecordAction.MODIFIED,
            modified_values=modified_values,
        )
        self.state_changed.emit()


class StageReview(QWidget):
    """Stage 5 — Review: proposed record review with commit button.

    :param batch: The ProposedBatch with conflicts.
    :param state: The ImportState.
    :param parent: Parent widget.
    """

    commit_requested = Signal()

    def __init__(
        self, batch: ProposedBatch, state: ImportState, parent=None
    ) -> None:
        super().__init__(parent)
        self._batch = batch
        self._state = state

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Scrollable record groups
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self._groups_layout = QVBoxLayout(content)
        self._groups_layout.setContentsMargins(0, 0, 0, 0)

        # Build category groups
        categories = get_records_by_category(state)
        records_by_path = {r.source_payload_path: r for r in batch.records}

        for table_name, rec_states in categories:
            records = [
                records_by_path[rs.source_payload_path]
                for rs in rec_states
                if rs.source_payload_path in records_by_path
            ]
            if records:
                group = CategoryGroup(table_name, records, state, batch)
                group.state_changed.connect(self._update_summary)
                self._groups_layout.addWidget(group)

        self._groups_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, stretch=1)

        # Fixed summary bar at bottom
        self._summary_bar = QWidget()
        self._summary_bar.setStyleSheet(
            "background-color: #F5F5F5; border-top: 1px solid #E0E0E0;"
        )
        summary_layout = QHBoxLayout(self._summary_bar)
        summary_layout.setContentsMargins(8, 8, 8, 8)

        self._counts_label = QLabel()
        self._counts_label.setStyleSheet("font-size: 12px;")
        summary_layout.addWidget(self._counts_label, stretch=1)

        commit_btn = QPushButton("Commit")
        commit_btn.setStyleSheet(
            "QPushButton { background-color: #1565C0; color: white; "
            "border-radius: 4px; padding: 8px 24px; font-size: 13px; "
            "font-weight: bold; } "
            "QPushButton:hover { background-color: #0D47A1; }"
        )
        commit_btn.clicked.connect(self._on_commit)
        summary_layout.addWidget(commit_btn)

        layout.addWidget(self._summary_bar)
        self._update_summary()

    def _update_summary(self) -> None:
        """Update the summary bar counts."""
        counts = count_by_action(self._state)
        errors = get_unresolved_errors(self._state)
        parts = [
            f"Accepted: {counts['accepted']}",
            f"Modified: {counts['modified']}",
            f"Rejected: {counts['rejected']}",
        ]
        if errors:
            parts.append(f"Unresolved Errors: {len(errors)}")
        self._counts_label.setText("  |  ".join(parts))

    def _on_commit(self) -> None:
        """Handle commit button click."""
        errors = get_unresolved_errors(self._state)
        if errors:
            show_info(
                self, "Unresolved Conflicts",
                f"Cannot commit: {len(errors)} record(s) have error-severity "
                "conflicts that must be resolved (rejected or modified) "
                "before commit."
            )
            return
        self.commit_requested.emit()

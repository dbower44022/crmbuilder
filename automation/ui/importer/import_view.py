"""Import Review container (Section 14.5).

Pushed onto the drill-down stack from header_actions.py.
Manages the 7-stage import pipeline flow.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from automation.ui.common.error_display import show_error
from automation.ui.common.loading import LoadingIndicator
from automation.ui.importer.import_logic import (
    ImportStage,
    ImportState,
    advance_stage,
    compute_accepted_record_ids,
    count_by_action,
    init_records_from_batch,
    set_error,
)
from automation.ui.importer.progress_indicator import ProgressIndicator
from automation.ui.importer.stage_commit import CommitResultDisplay, StageCommit
from automation.ui.importer.stage_receive import StageReceive
from automation.ui.importer.stage_review import StageReview
from automation.ui.importer.stage_trigger import StageTrigger


class ImportView(QWidget):
    """Import Review container — manages the 7-stage pipeline.

    :param work_item_id: The work item ID.
    :param conn: Client database connection.
    :param return_callback: Called when the user returns to the work item.
    :param parent: Parent widget.
    """

    def __init__(
        self,
        work_item_id: int,
        conn: sqlite3.Connection,
        return_callback=None,
        master_db_path: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._work_item_id = work_item_id
        self._conn = conn
        self._return_callback = return_callback
        self._master_db_path = master_db_path
        self._state = ImportState()
        self._batch = None
        self._ai_session_id: int | None = None
        self._commit_result = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Progress indicator
        self._progress = ProgressIndicator()
        layout.addWidget(self._progress)

        # Cancel button
        cancel_bar = QWidget()
        cancel_layout = QHBoxLayout(cancel_bar)
        cancel_layout.setContentsMargins(8, 0, 8, 0)
        cancel_layout.addStretch()
        self._cancel_btn = QPushButton("Cancel Import")
        self._cancel_btn.setStyleSheet(
            "QPushButton { color: #C62828; border: none; "
            "text-decoration: underline; font-size: 11px; } "
            "QPushButton:hover { color: #B71C1C; }"
        )
        self._cancel_btn.clicked.connect(self._on_cancel)
        cancel_layout.addWidget(self._cancel_btn)
        layout.addWidget(cancel_bar)

        # Stage content area
        self._stage_area = QVBoxLayout()
        layout.addLayout(self._stage_area, stretch=1)

        # Check for previous raw_output
        previous_raw = self._get_previous_raw_output()

        # Show Stage 1
        self._show_receive(previous_raw)

    def _get_previous_raw_output(self) -> str | None:
        """Check if the latest pending session already has raw_output."""
        row = self._conn.execute(
            "SELECT raw_output FROM AISession "
            "WHERE work_item_id = ? AND import_status = 'pending' "
            "ORDER BY id DESC LIMIT 1",
            (self._work_item_id,),
        ).fetchone()
        if row and row[0]:
            return row[0]
        return None

    def _open_master_conn(self) -> sqlite3.Connection | None:
        """Open a connection to the master database, or None if unavailable."""
        if self._master_db_path:
            try:
                return sqlite3.connect(self._master_db_path)
            except sqlite3.Error:
                pass
        return None

    def _clear_stage(self) -> None:
        while self._stage_area.count():
            child = self._stage_area.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _update_progress(self) -> None:
        self._progress.update_stage(
            self._state.current_stage, self._state.completed_stages
        )

    # --- Stage 1: Receive ---

    def _show_receive(self, previous_raw: str | None = None) -> None:
        self._clear_stage()
        self._state.current_stage = ImportStage.RECEIVE
        self._update_progress()

        receive = StageReceive(previous_raw)
        receive.parse_requested.connect(self._on_parse_requested)
        self._stage_area.addWidget(receive)

    def _on_parse_requested(self, raw_text: str) -> None:
        """Handle parse request from Stage 1."""
        self._clear_stage()
        self._state = advance_stage(self._state, ImportStage.PARSE)
        self._update_progress()

        loading = LoadingIndicator("Receiving and parsing...")
        self._stage_area.addWidget(loading)

        try:
            from automation.importer.pipeline import ImportProcessor
            master_conn = self._open_master_conn()
            processor = ImportProcessor(self._conn, master_conn=master_conn)

            # Stage 1: Receive
            self._ai_session_id = processor.receive(self._work_item_id, raw_text)
            self._state.ai_session_id = self._ai_session_id

            # Stage 2: Parse
            processor.parse(self._ai_session_id)

            # Auto-advance through Map and Detect
            self._run_map_and_detect(processor)

        except Exception as e:
            self._clear_stage()
            self._state = set_error(self._state, str(e))
            self._show_parse_error(str(e))

    # --- Stage 2: Parse Error ---

    def _show_parse_error(self, error_message: str) -> None:
        self._clear_stage()
        self._update_progress()

        from automation.ui.importer.stage_parse import StageParse
        error_display = StageParse(error_message)
        self._stage_area.addWidget(error_display)

    # --- Stages 3-4: Map and Detect ---

    def _run_map_and_detect(self, processor) -> None:
        self._clear_stage()
        self._state = advance_stage(self._state, ImportStage.MAP)
        self._update_progress()

        loading = LoadingIndicator("Mapping payload to records...")
        self._stage_area.addWidget(loading)

        try:
            # Stage 3: Map
            batch = processor.map(self._ai_session_id)

            loading.set_message("Detecting conflicts...")
            self._state = advance_stage(self._state, ImportStage.DETECT)
            self._update_progress()

            # Stage 4: Detect
            batch = processor.detect_conflicts(batch)
            self._batch = batch

            # Initialize record states
            self._state = init_records_from_batch(self._state, batch)

            # Advance to Review
            self._state = advance_stage(self._state, ImportStage.REVIEW)
            self._show_review()

        except Exception as e:
            self._clear_stage()
            self._state = set_error(self._state, str(e))
            error_label = QLabel(f"Error: {e}")
            error_label.setStyleSheet(
                "font-size: 12px; color: #C62828; padding: 8px; "
                "background-color: #FFEBEE; border-radius: 4px;"
            )
            error_label.setWordWrap(True)
            self._stage_area.addWidget(error_label)

    # --- Stage 5: Review ---

    def _show_review(self) -> None:
        self._clear_stage()
        self._update_progress()

        review = StageReview(self._batch, self._state)
        review.commit_requested.connect(self._on_commit_requested)
        self._stage_area.addWidget(review)

    def _on_commit_requested(self) -> None:
        """Show commit confirmation."""
        counts = count_by_action(self._state)

        # Count creates vs updates among accepted
        create_count = 0
        update_count = 0
        accepted_ids = compute_accepted_record_ids(self._state)
        for rec in self._batch.records:
            if rec.source_payload_path in accepted_ids:
                if rec.action == "create":
                    create_count += 1
                else:
                    update_count += 1

        self._clear_stage()
        self._state = advance_stage(self._state, ImportStage.COMMIT)
        self._update_progress()

        commit_confirm = StageCommit(create_count, update_count, counts["rejected"])
        commit_confirm.confirmed.connect(self._do_commit)
        commit_confirm.cancelled.connect(self._show_review)
        self._stage_area.addWidget(commit_confirm)

    def _do_commit(self) -> None:
        """Execute the commit."""
        self._clear_stage()
        loading = LoadingIndicator("Committing records...")
        self._stage_area.addWidget(loading)

        try:
            from automation.importer.pipeline import ImportProcessor
            master_conn = self._open_master_conn()
            processor = ImportProcessor(self._conn, master_conn=master_conn)

            accepted_ids = compute_accepted_record_ids(self._state)
            self._commit_result = processor.commit(
                self._ai_session_id, self._batch,
                accepted_record_ids=accepted_ids if accepted_ids else None,
            )

            # Show commit results
            self._clear_stage()
            result_display = CommitResultDisplay(
                self._commit_result.created_count,
                self._commit_result.updated_count,
                self._commit_result.rejected_count,
                self._commit_result.import_status,
            )
            self._stage_area.addWidget(result_display)

            # Auto-advance to triggers
            self._run_triggers()

        except Exception as e:
            self._clear_stage()
            show_error(self, "Commit Failed", str(e))
            # Return to review
            self._state.completed_stages.discard(ImportStage.COMMIT)
            self._state.current_stage = ImportStage.REVIEW
            self._show_review()

    # --- Stage 7: Trigger ---

    def _run_triggers(self) -> None:
        self._state = advance_stage(self._state, ImportStage.TRIGGER)
        self._update_progress()
        self._cancel_btn.setVisible(False)  # Can't cancel after commit

        try:
            from automation.importer.pipeline import ImportProcessor
            processor = ImportProcessor(self._conn)

            trigger_result = processor.trigger(self._ai_session_id, self._commit_result)

            self._clear_stage()
            trigger_display = StageTrigger(trigger_result)
            trigger_display.return_requested.connect(self._on_return)
            self._stage_area.addWidget(trigger_display)

            self._state = advance_stage(self._state, ImportStage.DONE)
            self._update_progress()

        except Exception as e:
            self._clear_stage()
            error = QLabel(f"Trigger error: {e}\n\nCommitted data is preserved.")
            error.setStyleSheet(
                "font-size: 12px; color: #E65100; padding: 8px; "
                "background-color: #FFF3E0; border-radius: 4px;"
            )
            error.setWordWrap(True)
            self._stage_area.addWidget(error)

            return_btn = QPushButton("Return to Work Item")
            return_btn.clicked.connect(self._on_return)
            self._stage_area.addWidget(return_btn)

    # --- Navigation ---

    def _on_cancel(self) -> None:
        """Cancel the import and return."""
        if self._return_callback:
            self._return_callback()

    def _on_return(self) -> None:
        """Return to the work item."""
        if self._return_callback:
            self._return_callback()

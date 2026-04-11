"""Session orchestration container (Section 14.4).

Pushed onto the drill-down stack from header_actions.py when
the implementor clicks "Generate Prompt".
"""

from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from automation.ui.common.error_display import show_error
from automation.ui.common.loading import LoadingIndicator
from automation.ui.common.readable_first import format_work_item_name
from automation.ui.session.pre_generation import PreGenerationConfig
from automation.ui.session.prompt_display import PromptDisplay
from automation.ui.session.session_history import SessionHistory
from automation.ui.session.session_logic import analyze_prompt
from automation.ui.work_item.work_item_logic import (
    load_sessions,
    load_work_item,
)


class SessionView(QWidget):
    """Session Orchestration view container.

    :param work_item_id: The work item ID.
    :param session_type: "initial", "revision", or "clarification".
    :param conn: Client database connection.
    :param return_callback: Called when the user clicks "Return to Work Item".
    :param parent: Parent widget.
    """

    def __init__(
        self,
        work_item_id: int,
        session_type: str,
        conn: sqlite3.Connection,
        return_callback=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._work_item_id = work_item_id
        self._session_type = session_type
        self._conn = conn
        self._return_callback = return_callback

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        # Load work item details
        item = load_work_item(conn, work_item_id)
        if not item:
            self._layout.addWidget(QLabel("Work item not found"))
            return

        self._item = item
        self._work_item_name = format_work_item_name(
            item.item_type, item.domain_name, item.entity_name, item.process_name
        )

        # Show pre-generation config
        self._show_pre_generation()

    def _show_pre_generation(self) -> None:
        """Display the pre-generation configuration panel."""
        self._clear_content()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 8, 8, 8)

        # Pre-generation config
        config = PreGenerationConfig(
            self._work_item_id,
            self._session_type,
            self._item.item_type,
            self._item.phase_name,
            self._work_item_name,
        )
        config.generate_requested.connect(self._on_generate)
        content_layout.addWidget(config)

        # Session history (below config)
        sessions = load_sessions(self._conn, self._work_item_id)
        history = SessionHistory(sessions)
        content_layout.addWidget(history)

        content_layout.addStretch()
        scroll.setWidget(content)
        self._layout.addWidget(scroll, stretch=1)

    def _on_generate(
        self, session_type: str, revision_reason: str, clarification_topic: str
    ) -> None:
        """Handle the generate request — call PromptGenerator."""
        self._clear_content()

        # Loading indicator
        loading = LoadingIndicator("Generating prompt...")
        self._layout.addWidget(loading)

        try:
            from automation.prompts.generator import PromptGenerator

            generator = PromptGenerator(self._conn)
            prompt_text = generator.generate(
                self._work_item_id,
                session_type=session_type,
                revision_reason=revision_reason or None,
                clarification_topic=clarification_topic or None,
            )

            # Remove loading and show prompt display
            self._clear_content()
            self._show_prompt_display(prompt_text)

        except Exception as e:
            self._clear_content()
            show_error(self, "Prompt Generation Failed", str(e))
            # Re-show pre-generation config
            self._show_pre_generation()

    def _show_prompt_display(self, prompt_text: str) -> None:
        """Show the generated prompt in sectioned display."""
        analysis = analyze_prompt(prompt_text)

        display = PromptDisplay(analysis, prompt_text)
        display.set_return_callback(self._on_return)
        self._layout.addWidget(display, stretch=1)

        # Session history below the prompt
        sessions = load_sessions(self._conn, self._work_item_id)
        if sessions:
            history = SessionHistory(sessions)
            self._layout.addWidget(history)

    def _on_return(self) -> None:
        """Handle return to work item."""
        if self._return_callback:
            self._return_callback()

    def _clear_content(self) -> None:
        """Remove all widgets from the layout."""
        while self._layout.count():
            child = self._layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

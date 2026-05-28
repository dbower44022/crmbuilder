"""Chat panel — the AI chat tab (PI-052 Slice B/C, WT-055).

A top-level ``QWidget`` registered under the new sidebar entry
``AI ▸ Chat``. Composed of a header (model + mode pickers, usage display,
Stop button), a streaming transcript, and an input area. Owns one
:class:`ChatController`.

API-key bootstrap is lazy — it runs on first activation (``showEvent``),
never at app startup, so a user who never opens the tab is never prompted
and the ``keyring`` backend is never touched.

Slice C wired the full tool surface, prompt caching, persistence, the
active model + mode pickers, the usage display, and the ask-before-write
confirm modal. The multi-conversation sidebar (rename/delete/export) is
Slice D.
"""

from __future__ import annotations

import json
import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.chat import persistence
from crmbuilder_v2.ui.chat.auth import ApiKeyDialog, resolve_api_key
from crmbuilder_v2.ui.chat.controller import ChatController
from crmbuilder_v2.ui.chat.widgets import (
    AssistantMessageItem,
    NoticeItem,
    ToolResultItem,
    ToolUseItem,
    TranscriptView,
    UserMessageItem,
)
from crmbuilder_v2.ui.styling import t
from crmbuilder_v2.ui.widgets.form_helpers import primary_button

_log = logging.getLogger("crmbuilder_v2.ui.panels.chat")

# (label shown in picker, value passed to the API / controller)
_MODELS: tuple[tuple[str, str], ...] = (
    ("Opus 4.7", "claude-opus-4-7"),
    ("Sonnet 4.6", "claude-sonnet-4-6"),
    ("Haiku 4.5", "claude-haiku-4-5-20251001"),
)
_MODES: tuple[tuple[str, str], ...] = (
    ("Full", "full"),
    ("Read-only", "read_only"),
    ("Ask before write", "ask_before_write"),
)


class ChatPanel(QWidget):
    """The AI chat tab widget."""

    def __init__(self, base_url: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("chat_panel")
        self._controller = ChatController(base_url, self)
        self._bootstrapped = False
        self._live_assistant: AssistantMessageItem | None = None

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_empty_state())  # index 0
        self._stack.addWidget(self._build_chat_widget())  # index 1

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._stack)

        self._connect_controller()

        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._controller.shutdown)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_empty_state(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)
        message = QLabel("No Anthropic API key is configured for chat.")
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(message)
        configure_btn = primary_button("Configure API key")
        configure_btn.setObjectName("chat_configure_button")
        configure_btn.clicked.connect(self._on_configure_clicked)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(configure_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)
        return widget

    def _build_chat_widget(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_conversation_sidebar())

        main_column = QWidget()
        col = QVBoxLayout(main_column)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self._build_header())
        self._transcript = TranscriptView()
        col.addWidget(self._transcript, stretch=1)
        col.addWidget(self._build_input_area())
        layout.addWidget(main_column, stretch=1)
        return widget

    def _build_conversation_sidebar(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("chat_conv_sidebar")
        panel.setFixedWidth(240)
        panel.setStyleSheet(
            f"#chat_conv_sidebar {{"
            f"  background: {t('color.neutral.50')};"
            f"  border-right: 1px solid {t('color.neutral.200')};"
            f"}}"
        )
        col = QVBoxLayout(panel)
        col.setContentsMargins(8, 8, 8, 8)
        col.setSpacing(6)

        new_btn = QPushButton("+ New chat")
        new_btn.setObjectName("chat_new_button")
        new_btn.clicked.connect(self._on_new_chat)
        col.addWidget(new_btn)

        self._conv_list = QListWidget()
        self._conv_list.setObjectName("chat_conv_list")
        self._conv_list.setStyleSheet("#chat_conv_list { border: none; }")
        self._conv_list.itemClicked.connect(self._on_conversation_selected)
        col.addWidget(self._conv_list, stretch=1)
        return panel

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("chat_header")
        header.setStyleSheet(
            f"#chat_header {{"
            f"  background: {t('color.neutral.0')};"
            f"  border-bottom: 1px solid {t('color.neutral.200')};"
            f"}}"
        )
        row = QHBoxLayout(header)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(8)

        row.addWidget(QLabel("Model:"))
        self._model_picker = QComboBox()
        self._model_picker.addItems([label for label, _ in _MODELS])
        self._model_picker.currentIndexChanged.connect(self._on_model_changed)
        row.addWidget(self._model_picker)

        row.addWidget(QLabel("Mode:"))
        self._mode_picker = QComboBox()
        self._mode_picker.addItems([label for label, _ in _MODES])
        self._mode_picker.currentIndexChanged.connect(self._on_mode_changed)
        row.addWidget(self._mode_picker)

        row.addStretch(1)

        self._usage_label = QLabel("")
        self._usage_label.setObjectName("chat_usage_label")
        self._usage_label.setStyleSheet(
            f"color: {t('color.neutral.500')};"
            f"font-family: '{t('font.family.mono')}';"
            f"font-size: {t('font.size.caption')};"
        )
        row.addWidget(self._usage_label)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName("chat_stop_button")
        self._stop_btn.setVisible(False)
        self._stop_btn.clicked.connect(self._controller.stop)
        row.addWidget(self._stop_btn)

        return header

    def _build_input_area(self) -> QWidget:
        area = QWidget()
        area.setObjectName("chat_input_area")
        area.setStyleSheet(
            f"#chat_input_area {{"
            f"  background: {t('color.neutral.0')};"
            f"  border-top: 1px solid {t('color.neutral.200')};"
            f"}}"
        )
        row = QHBoxLayout(area)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(8)

        self._input = QPlainTextEdit()
        self._input.setPlaceholderText("Type a message…  (Ctrl+Enter to send)")
        self._input.setFixedHeight(72)
        row.addWidget(self._input, stretch=1)

        self._send_btn = primary_button("Send")
        self._send_btn.setObjectName("chat_send_button")
        self._send_btn.clicked.connect(self._on_send_clicked)
        row.addWidget(self._send_btn, alignment=Qt.AlignmentFlag.AlignBottom)

        send_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self._input)
        send_shortcut.activated.connect(self._on_send_clicked)
        send_shortcut_enter = QShortcut(QKeySequence("Ctrl+Enter"), self._input)
        send_shortcut_enter.activated.connect(self._on_send_clicked)

        return area

    def _connect_controller(self) -> None:
        self._controller.assistant_delta.connect(self._on_assistant_delta)
        self._controller.tool_started.connect(self._on_tool_started)
        self._controller.tool_completed.connect(self._on_tool_completed)
        self._controller.tool_failed.connect(self._on_tool_failed)
        self._controller.turn_state_changed.connect(self._on_turn_state_changed)
        self._controller.turn_finished.connect(self._on_turn_finished)
        self._controller.turn_failed.connect(self._on_turn_failed)
        self._controller.auth_failed.connect(self._on_auth_failed)
        self._controller.confirm_write_requested.connect(self._on_confirm_write)
        self._controller.usage_updated.connect(self._on_usage_updated)

    # ------------------------------------------------------------------
    # Header pickers + usage
    # ------------------------------------------------------------------

    def _on_model_changed(self, index: int) -> None:
        if 0 <= index < len(_MODELS):
            self._controller.set_model(_MODELS[index][1])

    def _on_mode_changed(self, index: int) -> None:
        if 0 <= index < len(_MODES):
            self._controller.set_mode(_MODES[index][1])

    def _on_usage_updated(self, usage: dict) -> None:
        self._usage_label.setText(
            f"↑{usage.get('input_tokens', 0)} "
            f"↓{usage.get('output_tokens', 0)} "
            f"(cache {usage.get('cache_read_input_tokens', 0)})"
        )

    def _on_confirm_write(self, name: str, args_json: str) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("Confirm write")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(f"Claude wants to call the write tool {name}.")
        box.setInformativeText("Allow this write?")
        box.setDetailedText(args_json)
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setDefaultButton(QMessageBox.StandardButton.No)
        allowed = box.exec() == QMessageBox.StandardButton.Yes
        self._controller.resolve_confirm(allowed)

    # ------------------------------------------------------------------
    # Conversation sidebar (DEC-258)
    # ------------------------------------------------------------------

    def _refresh_conversation_list(self) -> None:
        self._conv_list.clear()
        current_id = self._controller.session.chat_id
        for summary in persistence.list_summaries():
            item = QListWidgetItem(summary.title)
            item.setData(Qt.ItemDataRole.UserRole, summary.chat_id)
            item.setToolTip(summary.title)
            self._conv_list.addItem(item)
            if summary.chat_id == current_id:
                self._conv_list.setCurrentItem(item)

    def _on_new_chat(self) -> None:
        self._controller.new_session()
        self._transcript.clear()
        self._close_live_assistant()
        self._usage_label.setText("")
        self._refresh_conversation_list()
        self._input.setFocus()

    def _on_conversation_selected(self, item: QListWidgetItem) -> None:
        chat_id = item.data(Qt.ItemDataRole.UserRole)
        if not chat_id or chat_id == self._controller.session.chat_id:
            return
        session = self._controller.switch_to(chat_id)
        if session is None:
            return
        self._render_session()

    def _render_session(self) -> None:
        """Rebuild the transcript widgets from the active session's history."""
        self._transcript.clear()
        self._close_live_assistant()
        for message in self._controller.session.messages:
            self._render_message(message.get("role"), message.get("content"))

    def _render_message(self, role: str, content) -> None:
        if role == "user":
            if isinstance(content, str):
                self._transcript.add_item(UserMessageItem(content))
                return
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_result":
                        is_err = bool(block.get("is_error"))
                        self._transcript.add_item(
                            ToolResultItem(
                                "tool result",
                                str(block.get("content", "")),
                                is_error=is_err,
                            )
                        )
                    elif block.get("type") == "text":
                        self._transcript.add_item(
                            UserMessageItem(block.get("text", ""))
                        )
            return
        if role == "assistant" and isinstance(content, list):
            for block in content:
                btype = (
                    block.get("type")
                    if isinstance(block, dict)
                    else getattr(block, "type", None)
                )
                if btype == "text":
                    text = (
                        block.get("text", "")
                        if isinstance(block, dict)
                        else getattr(block, "text", "")
                    )
                    bubble = AssistantMessageItem()
                    self._transcript.add_item(bubble)
                    bubble.append_text(text)
                elif btype == "tool_use":
                    name = (
                        block.get("name", "")
                        if isinstance(block, dict)
                        else getattr(block, "name", "")
                    )
                    args = (
                        block.get("input", {})
                        if isinstance(block, dict)
                        else getattr(block, "input", {})
                    )
                    self._transcript.add_item(
                        ToolUseItem(name, json.dumps(args, indent=2))
                    )

    # ------------------------------------------------------------------
    # Lazy auth bootstrap
    # ------------------------------------------------------------------

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 — Qt
        super().showEvent(event)
        if self._bootstrapped:
            return
        self._bootstrapped = True
        key = resolve_api_key()
        if key:
            self._activate_chat(key)
        else:
            self._stack.setCurrentIndex(0)

    def _activate_chat(self, api_key: str) -> None:
        self._controller.set_api_key(api_key)
        self._stack.setCurrentIndex(1)
        self._refresh_conversation_list()
        self._input.setFocus()

    def _on_configure_clicked(self) -> None:
        dialog = ApiKeyDialog(self)
        if dialog.exec() == ApiKeyDialog.DialogCode.Accepted:
            key = dialog.api_key()
            if key:
                self._activate_chat(key)

    def _on_auth_failed(self, _message: str) -> None:
        dialog = ApiKeyDialog(self, invalid=True)
        if dialog.exec() == ApiKeyDialog.DialogCode.Accepted and dialog.api_key():
            self._activate_chat(dialog.api_key())
        else:
            self._stack.setCurrentIndex(0)

    # ------------------------------------------------------------------
    # Send / Stop
    # ------------------------------------------------------------------

    def _on_send_clicked(self) -> None:
        if self._controller.in_turn:
            return
        text = self._input.toPlainText().strip()
        if not text:
            return
        self._transcript.add_item(UserMessageItem(text))
        self._input.clear()
        self._close_live_assistant()
        self._controller.send(text)

    # ------------------------------------------------------------------
    # Controller signal handlers
    # ------------------------------------------------------------------

    def _on_assistant_delta(self, text: str) -> None:
        if self._live_assistant is None:
            self._live_assistant = AssistantMessageItem()
            self._transcript.add_item(self._live_assistant)
        self._live_assistant.append_text(text)

    def _on_tool_started(self, name: str, args_json: str) -> None:
        self._close_live_assistant()
        self._transcript.add_item(ToolUseItem(name, args_json))

    def _on_tool_completed(self, name: str, summary: str, result_json: str) -> None:
        self._transcript.add_item(ToolResultItem(summary, result_json))

    def _on_tool_failed(self, name: str, error: str) -> None:
        self._transcript.add_item(
            ToolResultItem(f"{name} failed", error, is_error=True)
        )

    def _on_turn_state_changed(self, in_turn: bool) -> None:
        self._send_btn.setEnabled(not in_turn)
        self._stop_btn.setVisible(in_turn)

    def _on_turn_finished(self, stop_reason: str) -> None:
        if stop_reason == "cancelled":
            if self._live_assistant is not None and not self._live_assistant.is_empty():
                self._live_assistant.mark_cancelled()
            else:
                self._transcript.add_item(NoticeItem("(cancelled)"))
        self._close_live_assistant()
        # A just-persisted new chat now has a title; refresh the sidebar so
        # it appears (and the current row stays selected).
        self._refresh_conversation_list()

    def _on_turn_failed(self, error: str) -> None:
        self._transcript.add_item(NoticeItem(f"Error: {error}"))
        self._close_live_assistant()

    def _close_live_assistant(self) -> None:
        self._live_assistant = None

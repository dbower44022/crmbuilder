"""Transcript bubble + tool-disclosure widgets (PI-052 Slice B).

Four widget types render the transcript, styled with the v0.6 design
tokens per design doc §9:

* :class:`UserMessageItem` — right-aligned bubble, ``neutral.100`` fill.
* :class:`AssistantMessageItem` — left-aligned bubble, ``neutral.0``
  fill with a ``neutral.300`` hairline border. Grows as text streams in
  via :meth:`AssistantMessageItem.append_text`.
* :class:`ToolUseItem` — collapsed-by-default disclosure showing
  ``🔧 name({…})``; click the header to reveal the pretty-printed args.
* :class:`ToolResultItem` — collapsed-by-default disclosure showing
  ``↩︎ summary``; click to reveal the full JSON result.

Slice B uses a plain ``QScrollArea`` + ``QVBoxLayout`` of these widgets
(see :class:`TranscriptView`) rather than the ``QListWidget`` + item
delegates sketched in design §2.7 — the vertical-box approach is simpler
and the transcript is append-only.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.styling import t

_BUBBLE_MAX_WIDTH = 620


def _bubble_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setMaximumWidth(_BUBBLE_MAX_WIDTH)
    return label


class UserMessageItem(QWidget):
    """Right-aligned user message bubble."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        bubble = _bubble_label(text)
        bubble.setObjectName("chat_user_bubble")
        bubble.setStyleSheet(
            f"#chat_user_bubble {{"
            f"  background: {t('color.accent.subtle')};"
            f"  border: 1px solid {t('color.neutral.200')};"
            f"  border-radius: {t('radius.default')};"
            f"  padding: {t('space.2')} {t('space.3')};"
            f"  color: {t('color.neutral.900')};"
            f"}}"
        )
        row.addStretch(1)
        row.addWidget(bubble)


class AssistantMessageItem(QWidget):
    """Left-aligned assistant bubble that grows as text streams in."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = ""
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self._bubble = _bubble_label("")
        self._bubble.setObjectName("chat_assistant_bubble")
        self._bubble.setStyleSheet(
            f"#chat_assistant_bubble {{"
            f"  background: {t('color.neutral.0')};"
            f"  border: 1px solid {t('color.neutral.300')};"
            f"  border-radius: {t('radius.default')};"
            f"  padding: {t('space.2')} {t('space.3')};"
            f"  color: {t('color.neutral.800')};"
            f"}}"
        )
        row.addWidget(self._bubble)
        row.addStretch(1)

    def append_text(self, text: str) -> None:
        self._text += text
        self._bubble.setText(self._text)

    def mark_cancelled(self) -> None:
        self._text = (self._text + "  (cancelled)").strip()
        self._bubble.setText(self._text)

    def is_empty(self) -> bool:
        return not self._text


class _DisclosureItem(QFrame):
    """Collapsed-by-default header + click-to-expand detail body."""

    def __init__(
        self,
        header_text: str,
        detail_text: str,
        *,
        mono_detail: bool = True,
        danger: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._toggle = QPushButton(self._collapsed_label(header_text))
        self._header_text = header_text
        self._toggle.setCheckable(True)
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.setStyleSheet(
            f"QPushButton {{"
            f"  border: none;"
            f"  background: transparent;"
            f"  text-align: left;"
            f"  padding: {t('space.1')} 0;"
            f"  color: {t('color.danger.text') if danger else t('color.neutral.700')};"
            f"  font-family: '{t('font.family.mono')}';"
            f"  font-size: {t('font.size.small')};"
            f"}}"
        )
        layout.addWidget(self._toggle)

        self._detail = QLabel(detail_text)
        self._detail.setWordWrap(True)
        self._detail.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._detail.setMaximumWidth(_BUBBLE_MAX_WIDTH)
        self._detail.setVisible(False)
        detail_font = "font.family.mono" if mono_detail else "font.family.default"
        self._detail.setStyleSheet(
            f"QLabel {{"
            f"  background: {t('color.neutral.50')};"
            f"  border: 1px solid {t('color.neutral.200')};"
            f"  border-radius: {t('radius.subtle')};"
            f"  padding: {t('space.2')};"
            f"  color: {t('color.neutral.700')};"
            f"  font-family: '{t(detail_font)}';"
            f"  font-size: {t('font.size.caption')};"
            f"}}"
        )
        layout.addWidget(self._detail)

        self._toggle.toggled.connect(self._on_toggled)

    def _collapsed_label(self, header_text: str) -> str:
        return f"▶ {header_text}"

    def _expanded_label(self, header_text: str) -> str:
        return f"▼ {header_text}"

    def _on_toggled(self, checked: bool) -> None:
        self._detail.setVisible(checked)
        self._toggle.setText(
            self._expanded_label(self._header_text)
            if checked
            else self._collapsed_label(self._header_text)
        )


class ToolUseItem(_DisclosureItem):
    """Disclosure for a tool call: ``🔧 name({…})`` → args on expand."""

    def __init__(
        self, name: str, args_json: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(
            f"🔧 {name}({{…}})",
            args_json,
            mono_detail=True,
            parent=parent,
        )


class ToolResultItem(_DisclosureItem):
    """Disclosure for a tool result: ``↩︎ summary`` → full JSON on expand."""

    def __init__(
        self,
        summary: str,
        result_text: str,
        *,
        is_error: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        marker = "⚠" if is_error else "↩︎"
        super().__init__(
            f"{marker} {summary}",
            result_text,
            mono_detail=True,
            danger=is_error,
            parent=parent,
        )


class NoticeItem(QWidget):
    """A small centered notice line (e.g. a standalone cancellation marker)."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        label = QLabel(text)
        label.setStyleSheet(
            f"color: {t('color.neutral.500')};font-size: {t('font.size.caption')};"
        )
        row.addStretch(1)
        row.addWidget(label)
        row.addStretch(1)


class ActionNoticeItem(QWidget):
    """A centered notice line with a single action button (PI-106).

    Used for the context-window-overflow Trim affordance: shows an
    explanatory message and a button that emits :data:`triggered` when
    clicked. The button can be disabled via :meth:`set_active` once the
    action is under way.
    """

    triggered = Signal()

    def __init__(
        self, text: str, button_label: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(
            f"color: {t('color.neutral.500')};font-size: {t('font.size.caption')};"
        )
        self._button = QPushButton(button_label)
        self._button.setObjectName("chat_trim_button")
        self._button.clicked.connect(self.triggered)
        row.addStretch(1)
        row.addWidget(label)
        row.addWidget(self._button)
        row.addStretch(1)

    def set_active(self, active: bool) -> None:
        """Enable or disable the action button."""
        self._button.setEnabled(active)


class TranscriptView(QScrollArea):
    """Scrollable, append-only column of transcript item widgets."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setObjectName("chat_transcript")
        self.setStyleSheet(
            f"#chat_transcript {{ border: none; background: {t('color.neutral.50')}; }}"
        )
        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(10)
        self._layout.addStretch(1)
        self.setWidget(self._container)

    def add_item(self, widget: QWidget) -> None:
        """Insert a transcript item above the trailing stretch."""
        self._layout.insertWidget(self._layout.count() - 1, widget)
        self._scroll_to_bottom()

    def clear(self) -> None:
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _scroll_to_bottom(self) -> None:
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

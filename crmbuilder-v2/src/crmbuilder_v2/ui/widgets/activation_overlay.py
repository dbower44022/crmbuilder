"""Activation-progress overlay shown during the 12-step switch dance.

Binds to an :class:`ActivationWorker`'s ``step_started`` /
``step_completed`` / ``step_failed`` / ``completed`` / ``failed`` signals,
displays the current step's description, and on failure surfaces the
two PRD §5.2-mandated affordances: "Try switching now" (retry) and
"Stay in <previous>" (abort).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.access.engagement_models import Engagement

_OVERLAY_BACKDROP = "rgba(0, 0, 0, 96)"


class ActivationOverlay(QWidget):
    """Modal-style progress overlay for an activation in flight.

    Connect ``worker`` (an :class:`ActivationWorker`) at construction;
    the overlay subscribes to its signals and dismisses on
    ``completed``.

    Emits :pyattr:`retry_requested` when the user clicks "Try switching
    now", and :pyattr:`stay_requested` when the user clicks the stay-
    in-previous button. Parents wire these to retry or abort.
    """

    retry_requested = Signal()
    stay_requested = Signal()

    def __init__(
        self,
        target_engagement: Engagement,
        previous_engagement: Engagement | None,
        worker,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._target = target_engagement
        self._previous = previous_engagement
        self._worker = worker
        self.setObjectName("activation_overlay")
        self.setStyleSheet(
            f"#activation_overlay {{ background-color: {_OVERLAY_BACKDROP}; }}"
        )
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)
        card_row = QHBoxLayout()
        card_row.addStretch(1)
        self._card = self._build_card()
        card_row.addWidget(self._card)
        card_row.addStretch(1)
        outer.addLayout(card_row)
        outer.addStretch(1)

        worker.step_started.connect(self._on_step_started)
        worker.step_completed.connect(self._on_step_completed)
        worker.step_failed.connect(self._on_step_failed)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)

    # ------------------------------------------------------------------
    # Card construction
    # ------------------------------------------------------------------

    def _build_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("activation_card")
        card.setStyleSheet(
            "#activation_card {"
            "  background-color: white;"
            "  border-radius: 8px;"
            "  padding: 16px;"
            "}"
        )
        card.setFixedWidth(420)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        self._title = QLabel(f"Switching to {self._target.engagement_name}…")
        self._title.setObjectName("activation_title")
        title_font = QFont(self._title.font())
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 2)
        self._title.setFont(title_font)
        layout.addWidget(self._title)

        self._step_label = QLabel("Step 0 of 12 — Preparing…")
        self._step_label.setObjectName("activation_step_label")
        layout.addWidget(self._step_label)

        self._error_label = QLabel("")
        self._error_label.setObjectName("activation_error_label")
        self._error_label.setWordWrap(True)
        self._error_label.setStyleSheet("color: #c1272d;")
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        # Action row (hidden until failure).
        self._actions_widget = QWidget()
        actions = QHBoxLayout(self._actions_widget)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        actions.addStretch(1)
        self._retry_btn = QPushButton("Try switching now")
        self._retry_btn.setObjectName("activation_retry_button")
        self._retry_btn.clicked.connect(self._on_retry_clicked)
        actions.addWidget(self._retry_btn)
        previous_label = (
            self._previous.engagement_name
            if self._previous is not None
            else "(no previous engagement)"
        )
        self._stay_btn = QPushButton(f"Stay in {previous_label}")
        self._stay_btn.setObjectName("activation_stay_button")
        self._stay_btn.clicked.connect(self._on_stay_clicked)
        actions.addWidget(self._stay_btn)
        self._actions_widget.setVisible(False)
        layout.addWidget(self._actions_widget)

        return card

    # ------------------------------------------------------------------
    # Worker-signal slots
    # ------------------------------------------------------------------

    def _on_step_started(self, step: int, description: str) -> None:
        self._step_label.setText(f"Step {step} of 12 — {description}")

    def _on_step_completed(self, step: int, _description: str) -> None:
        self._step_label.setText(f"Step {step} of 12 complete")

    def _on_step_failed(
        self, step: int, _description: str, error_message: str
    ) -> None:
        self._title.setText(f"Switching failed at step {step}")
        self._error_label.setText(error_message)
        self._error_label.setVisible(True)
        self._actions_widget.setVisible(True)

    def _on_completed(self, _engagement) -> None:
        self.close()
        self.deleteLater()

    def _on_failed(self, _previous, error_message: str) -> None:
        # Reuse step_failed visual if it hasn't already fired (e.g.,
        # the worker raised before emitting step_failed).
        if not self._error_label.isVisible():
            self._title.setText("Switching failed")
            self._error_label.setText(error_message)
            self._error_label.setVisible(True)
            self._actions_widget.setVisible(True)

    def _on_retry_clicked(self) -> None:
        self.retry_requested.emit()

    def _on_stay_clicked(self) -> None:
        self.stay_requested.emit()

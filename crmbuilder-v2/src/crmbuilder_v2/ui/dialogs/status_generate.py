"""Status generate dialog — PI-433 / REQ-527.

Collects an optional narrative paragraph, shows a read-only preview of
the payload ``POST /status/generate`` would write (fetched through
:meth:`StorageClient.preview_status`), and on Save calls
:meth:`StorageClient.generate_status`. Both calls run through worker
threads. Sibling of :class:`StatusReplaceDialog`, which remains the
hand-edit path.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.elevation import apply_dialog_shadow
from crmbuilder_v2.ui.exceptions import (
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.widgets.form_helpers import primary_button
from crmbuilder_v2.ui.workers import run_in_thread

_log = logging.getLogger("crmbuilder_v2.ui.dialogs.status_generate")

_DIALOG_WIDTH = 800
_DIALOG_HEIGHT = 700


class StatusGenerateDialog(QDialog):
    """Modal: narrative field + generated-payload preview + Save."""

    def __init__(self, client: StorageClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._client = client
        self.setWindowTitle("Generate Status Version")
        self.setModal(True)
        self.resize(_DIALOG_WIDTH, _DIALOG_HEIGHT)
        apply_dialog_shadow(self)
        self._in_flight_workers: list[object] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        header = QLabel("Generate Status Version")
        header_font = QFont(header.font())
        header_font.setBold(True)
        header_font.setPointSize(header_font.pointSize() + 1)
        header.setFont(header_font)
        outer.addWidget(header)

        outer.addWidget(
            QLabel(
                "The facts below come from the record store. Add an optional "
                "narrative paragraph; it is carried in active_work."
            )
        )

        self._narrative = QPlainTextEdit()
        self._narrative.setObjectName("narrative_editor")
        self._narrative.setPlaceholderText("Narrative (optional)")
        self._narrative.setMaximumHeight(120)
        outer.addWidget(self._narrative)

        preview_row = QHBoxLayout()
        preview_row.setContentsMargins(0, 0, 0, 0)
        self._preview_btn = QPushButton("Refresh Preview")
        self._preview_btn.setObjectName("preview_button")
        self._preview_btn.clicked.connect(self._on_preview)
        preview_row.addWidget(self._preview_btn)
        self._preview_status = QLabel("")
        self._preview_status.setObjectName("preview_status")
        preview_row.addWidget(self._preview_status, 1)
        outer.addLayout(preview_row)

        self._preview = QPlainTextEdit()
        self._preview.setObjectName("payload_preview")
        self._preview.setReadOnly(True)
        preview_font = QFont("Monaco")
        preview_font.setStyleHint(QFont.StyleHint.Monospace)
        preview_font.setPointSize(10)
        self._preview.setFont(preview_font)
        outer.addWidget(self._preview, stretch=1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancel_button")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        self._save_btn = primary_button("Save")
        self._save_btn.setObjectName("save_button")
        self._save_btn.setDefault(True)
        self._save_btn.clicked.connect(self._on_save)
        button_row.addWidget(self._save_btn)
        outer.addLayout(button_row)

        self._on_preview()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _narrative_text(self) -> str | None:
        text = self._narrative.toPlainText().strip()
        return text or None

    def _track(self, worker) -> None:
        self._in_flight_workers.append(worker)
        worker.finished.connect(lambda w=worker: self._discard_worker(w))

    def _discard_worker(self, worker: object) -> None:
        try:
            self._in_flight_workers.remove(worker)
        except ValueError:
            pass

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _on_preview(self) -> None:
        self._preview_status.setText("Loading preview…")
        narrative = self._narrative_text()
        self._track(
            run_in_thread(
                lambda n=narrative: self._client.preview_status(n),
                on_success=self._on_preview_success,
                on_error=self._on_error,
                parent=self,
            )
        )

    def _on_preview_success(self, payload: Any) -> None:
        self._preview.setPlainText(json.dumps(payload, indent=2))
        self._preview_status.setText("")

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _on_save(self) -> None:
        self._save_btn.setEnabled(False)
        narrative = self._narrative_text()
        self._track(
            run_in_thread(
                lambda n=narrative: self._client.generate_status(n),
                on_success=self._on_save_success,
                on_error=self._on_save_error,
                parent=self,
            )
        )

    def _on_save_success(self, _result: object) -> None:
        self.accept()

    def _on_save_error(self, exc: BaseException) -> None:
        self._save_btn.setEnabled(True)
        self._on_error(exc)

    def _on_error(self, exc: BaseException) -> None:
        self._preview_status.setText("")
        if isinstance(exc, StorageConnectionError):
            _log.warning("Connection lost during status generate: %s", exc)
            self.reject()
            return
        if isinstance(exc, StorageClientError):
            ErrorDialog(
                "Could not generate status",
                "The server rejected the request.",
                detail=str(exc),
                parent=self,
            ).exec()
            return
        _log.exception("Unexpected error during status generate", exc_info=exc)
        ErrorDialog(
            "Unexpected error",
            "An unexpected error occurred.",
            detail=repr(exc),
            parent=self,
        ).exec()

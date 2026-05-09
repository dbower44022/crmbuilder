"""Status panel — versioned view + replace flow per slice E (v0.2).

Mirror of :class:`CharterPanel`. Adds:

* "New Version" button in the toolbar (opens
  :class:`StatusReplaceDialog`).
* "Make Current" button in the detail pane for non-current versions.
* :class:`ReferencesSection` widget in the detail pane.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.base.versioned_panel import VersionedPanel
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.dialogs.status_replace import StatusReplaceDialog
from crmbuilder_v2.ui.exceptions import (
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection
from crmbuilder_v2.ui.workers import run_in_thread

_log = logging.getLogger("crmbuilder_v2.ui.panels.status")

_REFERENCES_ENTITY_TYPE = "status"
_REFERENCES_ENTITY_ID = "status"


class StatusPanel(VersionedPanel):
    """Status — singleton with full version history and replace flow."""

    def __init__(self, client, parent=None):
        super().__init__(client, parent)
        self._new_version_btn = QPushButton("New Version")
        self._new_version_btn.setObjectName("new_status_version_button")
        self._new_version_btn.clicked.connect(self._on_new_version_clicked)
        self._action_layout.addWidget(self._new_version_btn)

    def entity_title(self) -> str:
        return "Status"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_status_versions()

    # ------------------------------------------------------------------
    # Detail pane
    # ------------------------------------------------------------------

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        return {
            "references": self._client.list_references_touching(
                _REFERENCES_ENTITY_TYPE, _REFERENCES_ENTITY_ID
            ),
        }

    def render_detail(
        self, record: dict[str, Any], extras: dict[str, Any]
    ) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        version = record.get("version")
        is_current = bool(record.get("is_current"))
        outer.addWidget(_version_heading(version, is_current))

        if not is_current and version is not None:
            button_strip = QWidget()
            strip_layout = QHBoxLayout(button_strip)
            strip_layout.setContentsMargins(0, 0, 0, 0)
            strip_layout.setSpacing(6)
            make_current_btn = QPushButton("Make Current")
            make_current_btn.setObjectName("make_current_button")
            make_current_btn.clicked.connect(
                lambda _checked=False, v=version: self._on_make_current(v)
            )
            strip_layout.addWidget(make_current_btn)
            strip_layout.addStretch(1)
            outer.addWidget(button_strip)

        payload_widget = self._build_payload_form(record.get("payload") or {})
        outer.addWidget(payload_widget)

        references_section = ReferencesSection(
            _REFERENCES_ENTITY_TYPE,
            _REFERENCES_ENTITY_ID,
            extras.get("references") or {},
            client=self._client,
        )
        references_section.navigate_requested.connect(self.navigate_requested)
        references_section.references_changed.connect(self.refresh)
        outer.addWidget(references_section)

        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

    # ------------------------------------------------------------------
    # Click handlers
    # ------------------------------------------------------------------

    def _on_new_version_clicked(self) -> None:
        current = self._find_current_record()
        if current is None:
            ErrorDialog(
                "No current status",
                "There is no current status version. Cannot create a new version.",
                parent=self,
            ).exec()
            return
        dialog = StatusReplaceDialog(
            self._client, current.get("payload") or {}, self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_make_current(self, version: int) -> None:
        confirm = QMessageBox(self)
        confirm.setWindowTitle("Make Current")
        confirm.setText(
            f"Make status version {version} the current version?"
        )
        confirm.setInformativeText(
            "The current version will become a non-current historical record."
        )
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        confirm.setDefaultButton(QMessageBox.StandardButton.No)
        if confirm.exec() != QMessageBox.StandardButton.Yes:
            return

        worker = run_in_thread(
            lambda v=version: self._client.make_status_version_current(v),
            on_success=self._on_make_current_success,
            on_error=self._on_make_current_error,
            parent=self,
        )
        self._in_flight_workers.append(worker)
        worker.finished.connect(lambda w=worker: self._discard_worker(w))

    def _on_make_current_success(self, _result: object) -> None:
        self._initial_select_done = False
        self.refresh()

    def _on_make_current_error(self, exc: BaseException) -> None:
        if isinstance(exc, StorageConnectionError):
            _log.warning("Connection lost during make-current: %s", exc)
            self.connection_lost.emit(str(exc))
            return
        if isinstance(exc, StorageClientError):
            _log.warning("Domain error during make-current: %s", exc)
            ErrorDialog(
                "Could not make current",
                "An error occurred while flipping the current version.",
                detail=str(exc),
                parent=self,
            ).exec()
            return
        _log.exception("Unexpected error during make-current", exc_info=exc)
        ErrorDialog(
            "Unexpected error",
            "An unexpected error occurred.",
            detail=repr(exc),
            parent=self,
        ).exec()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_current_record(self) -> dict[str, Any] | None:
        for record in self._records:
            if record.get("is_current"):
                return record
        return None

    def _discard_worker(self, worker: object) -> None:
        try:
            self._in_flight_workers.remove(worker)
        except ValueError:
            pass


def _version_heading(version: Any, is_current: bool) -> QLabel:
    text = f"Version {version}"
    if is_current:
        text += "  (current)"
    label = QLabel(text)
    font = QFont(label.font())
    font.setBold(True)
    font.setPointSize(font.pointSize() + 1)
    label.setFont(font)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label

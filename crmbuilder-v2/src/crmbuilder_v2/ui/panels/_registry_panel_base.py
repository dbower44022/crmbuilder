"""Shared base for the Agent Profile Registry CRUD panels (PI-330 / REQ-367).

Factors out the new/edit/delete plumbing and context menu common to the skills,
governance-rules, and learnings panels (and reused by the richer agent-profiles
panel). Subclasses implement the ``ListDetailPanel`` display hooks
(``entity_title`` / ``fetch_records`` / ``list_columns`` / ``render_detail``)
plus four registry hooks: ``_new_dialog`` / ``_edit_dialog`` / ``_delete_dialog``
/ ``_fetch_one`` and ``_record_label``.

Common detail-rendering helpers (heading, labels, read-only text, separator,
created/updated footer) live here so the panels stay focused on layout.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QLabel,
    QMenu,
    QPlainTextEdit,
)

from crmbuilder_v2.ui.base.list_detail_panel import ListDetailPanel
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.exceptions import (
    NotFoundError,
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.widgets.form_helpers import primary_button

_log = logging.getLogger("crmbuilder_v2.ui.panels.registry")

_LONG_TEXT_MIN_HEIGHT = 80


def heading_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setWordWrap(True)
    font = QFont(label.font())
    font.setBold(True)
    font.setPointSize(font.pointSize() + 2)
    label.setFont(font)
    return label


def field_label(text: str, *, dim: bool = False) -> QLabel:
    label = QLabel(text)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setWordWrap(True)
    if dim:
        label.setStyleSheet("color: #888;")
    return label


def read_only_text(value: str) -> QPlainTextEdit:
    widget = QPlainTextEdit()
    widget.setPlainText(value or "")
    widget.setReadOnly(True)
    widget.setMinimumHeight(_LONG_TEXT_MIN_HEIGHT)
    return widget


def separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


class RegistryCrudPanel(ListDetailPanel):
    """A ``ListDetailPanel`` with registry create/edit/delete wiring.

    Subclasses set ``new_button_label`` and ``entity_noun`` and implement the
    registry hooks below plus the standard ListDetailPanel display hooks.
    """

    new_button_label = "New"
    entity_noun = "record"

    def __init__(self, client, parent=None):
        super().__init__(client, parent)
        self._new_button = primary_button(self.new_button_label)
        self._new_button.setObjectName(
            f"new_{self.entity_noun.replace(' ', '_')}_button"
        )
        self._new_button.clicked.connect(self._on_new_clicked)
        self._action_layout.addWidget(self._new_button)

    # --- registry hooks (subclasses implement) -------------------------

    def _new_dialog(self) -> QDialog:
        raise NotImplementedError

    def _edit_dialog(self, record: dict[str, Any]) -> QDialog:
        raise NotImplementedError

    def _delete_dialog(self, identifier: str, label: str) -> QDialog:
        raise NotImplementedError

    def _fetch_one(self, identifier: str) -> dict[str, Any]:
        raise NotImplementedError

    def _record_label(self, record: dict[str, Any]) -> str:
        return str(record.get("identifier") or "")

    # --- context menu ---------------------------------------------------

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        new_action = menu.addAction(self.new_button_label)
        new_action.triggered.connect(self._on_new_clicked)
        if not index.isValid():
            return menu
        record = self._record_at_index(index)
        if record is None:
            return menu
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(
            lambda _checked=False, r=record: self._on_delete_clicked(r)
        )
        return menu

    # --- click handlers -------------------------------------------------

    def _on_new_clicked(self) -> None:
        dialog = self._new_dialog()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_id = getattr(dialog, "created_identifier", lambda: None)()
            if new_id:
                self.select_record_by_identifier(new_id)
            else:
                self.refresh()

    def _on_edit_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("identifier")
        if not identifier:
            return
        try:
            fresh = self._fetch_one(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            _log.warning("Connection lost loading %s for edit: %s", identifier, exc)
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            _log.warning("Domain error loading %s for edit: %s", identifier, exc)
            ErrorDialog(
                title=f"Could not load {self.entity_noun}",
                message=f"Could not load the latest version of this {self.entity_noun}.",
                detail=str(exc),
                parent=self,
            ).exec()
            return
        dialog = self._edit_dialog(fresh)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("identifier") or ""
        if not identifier:
            return
        dialog = self._delete_dialog(identifier, self._record_label(record))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

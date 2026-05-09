"""Decisions panel — PRD §4.6 list/detail + §4.7-§4.9 write surfaces.

Slice D replaced slice C's smoke-grade panel with the full per-PRD
column set and a structured detail view. Slice G adds the only write
surface in v0.1: a "New Decision" toolbar button plus Edit and Delete
buttons in the detail pane that open the create/edit/delete dialogs.

Columns: identifier, title, decision_date, status, superseded_by_identifier.

Detail pane: identifier, title (heading), decision_date, status,
supersedes (clickable decision link), superseded_by (clickable decision
link), context, decision, rationale, alternatives_considered,
consequences (each as a read-only multi-line text widget), then a
references section showing inbound ``decided_in`` from sessions
(clickable) plus any other touching references.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.dialogs.decision_create import DecisionCreateDialog
from crmbuilder_v2.ui.dialogs.decision_delete import DecisionDeleteDialog
from crmbuilder_v2.ui.dialogs.decision_edit import DecisionEditDialog
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.exceptions import (
    NotFoundError,
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection

_log = logging.getLogger("crmbuilder_v2.ui.panels.decisions")

_LONG_TEXT_MIN_HEIGHT = 80
_LONG_TEXT_FIELDS = (
    ("context", "Context"),
    ("decision", "Decision"),
    ("rationale", "Rationale"),
    ("alternatives_considered", "Alternatives Considered"),
    ("consequences", "Consequences"),
)


def _label(text: str, *, bold: bool = False, dim: bool = False) -> QLabel:
    label = QLabel(text)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setWordWrap(True)
    if bold:
        font = QFont(label.font())
        font.setBold(True)
        label.setFont(font)
    if dim:
        label.setStyleSheet("color: #888;")
    return label


def _heading_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setWordWrap(True)
    font = QFont(label.font())
    font.setBold(True)
    font.setPointSize(font.pointSize() + 2)
    label.setFont(font)
    return label


def _long_text(content: str) -> QPlainTextEdit:
    widget = QPlainTextEdit()
    widget.setReadOnly(True)
    widget.setPlainText(content or "")
    widget.setMinimumHeight(_LONG_TEXT_MIN_HEIGHT)
    return widget


def _separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


class DecisionsPanel(ListDetailPanel):
    """Decisions panel with read + write surfaces."""

    def __init__(self, client, parent=None):
        self._include_deleted = False
        super().__init__(client, parent)
        self._show_deleted_check = QCheckBox("Show deleted")
        self._show_deleted_check.setObjectName("show_deleted_check")
        self._show_deleted_check.toggled.connect(self._on_show_deleted_toggled)
        self._action_layout.addWidget(self._show_deleted_check)
        self._new_button = QPushButton("New Decision")
        self._new_button.setObjectName("new_decision_button")
        self._new_button.clicked.connect(self._on_new_decision_clicked)
        self._action_layout.addWidget(self._new_button)

    def entity_title(self) -> str:
        return "Decisions"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_decisions(include_deleted=self._include_deleted)

    def _strikethrough_for_record(self, record: dict[str, Any]) -> bool:
        return record.get("status") == "Deleted"

    def _on_show_deleted_toggled(self, checked: bool) -> None:
        self._include_deleted = checked
        self.refresh()

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="identifier", title="Identifier", width=120),
            ColumnSpec(field="title", title="Title"),
            ColumnSpec(field="decision_date", title="Decision Date", width=120),
            ColumnSpec(field="status", title="Status", width=100),
            ColumnSpec(
                field="superseded_by_identifier",
                title="Superseded By",
                width=140,
            ),
        ]

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        identifier = record.get("identifier")
        if not identifier:
            return {"references": {"as_source": [], "as_target": []}}
        return {
            "references": self._client.list_references_touching(
                "decision", identifier
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

        # Edit / Delete (or Restore / Edit, for soft-deleted records) at the
        # top of the detail pane.
        button_strip = QWidget()
        button_strip_layout = QHBoxLayout(button_strip)
        button_strip_layout.setContentsMargins(0, 0, 0, 0)
        button_strip_layout.setSpacing(6)
        is_deleted = record.get("status") == "Deleted"
        if is_deleted:
            restore_btn = QPushButton("Restore")
            restore_btn.setObjectName("restore_decision_button")
            restore_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_restore_clicked(r)
            )
            button_strip_layout.addWidget(restore_btn)
        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("edit_decision_button")
        edit_btn.clicked.connect(lambda _checked=False, r=record: self._on_edit_clicked(r))
        button_strip_layout.addWidget(edit_btn)
        if not is_deleted:
            delete_btn = QPushButton("Delete")
            delete_btn.setObjectName("delete_decision_button")
            delete_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_delete_clicked(r)
            )
            button_strip_layout.addWidget(delete_btn)
        button_strip_layout.addStretch(1)
        outer.addWidget(button_strip)

        outer.addWidget(_heading_label(record.get("title") or "(untitled)"))

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form.addRow("Identifier", _label(record.get("identifier") or ""))
        form.addRow("Decision Date", _label(record.get("decision_date") or ""))
        form.addRow("Status", _label(record.get("status") or ""))
        form.addRow(
            "Supersedes",
            self._decision_link_or_dash(record.get("supersedes_identifier")),
        )
        form.addRow(
            "Superseded By",
            self._decision_link_or_dash(record.get("superseded_by_identifier")),
        )
        outer.addLayout(form)

        outer.addWidget(_separator())

        for field, label_text in _LONG_TEXT_FIELDS:
            section_label = _label(label_text, bold=True)
            outer.addWidget(section_label)
            outer.addWidget(_long_text(record.get(field) or ""))

        outer.addWidget(_separator())
        # ReferencesSection renders inbound and outbound references via the
        # shared widget (DEC-031). The Decisions detail pane already shows
        # supersedes/superseded_by as top-level fields; suppress those
        # outbound relationships in the section to avoid redundancy.
        identifier = record.get("identifier") or ""
        references_section = ReferencesSection(
            "decision",
            identifier,
            extras.get("references") or {},
            exclude_relationships={"supersedes"},
        )
        references_section.navigate_requested.connect(
            self.navigate_requested
        )
        outer.addWidget(references_section)

        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

    # ------------------------------------------------------------------
    # Right-click context menu (v0.3 — DEC-036)
    # ------------------------------------------------------------------

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        if not index.isValid():
            new_action = menu.addAction("New decision")
            new_action.triggered.connect(self._on_new_decision_clicked)
            return menu

        record = self._record_at_index(index)
        if record is None:
            return menu

        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )

        if record.get("status") == "Deleted":
            restore_action = menu.addAction("Restore")
            restore_action.triggered.connect(
                lambda _checked=False, r=record: self._on_restore_clicked(r)
            )
        else:
            delete_action = menu.addAction("Delete")
            delete_action.triggered.connect(
                lambda _checked=False, r=record: self._on_delete_clicked(r)
            )

        show_refs_action = menu.addAction("Show references")
        show_refs_action.triggered.connect(
            lambda _checked=False, r=record: self._show_references_for(r)
        )
        return menu

    def _show_references_for(self, record: dict[str, Any]) -> None:
        """Right-click "Show references" handler — selects the row.

        Selecting the row triggers the existing detail-pane load, which
        renders the ``ReferencesSection`` widget at the bottom. No
        explicit scroll is performed in v0.3 slice B; if the section is
        below the fold the user scrolls naturally.
        """
        identifier = record.get("identifier")
        if identifier:
            self.select_record_by_identifier(identifier)

    # ------------------------------------------------------------------
    # Write-surface click handlers (slice G)
    # ------------------------------------------------------------------

    def _on_new_decision_clicked(self) -> None:
        dialog = DecisionCreateDialog(self._client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_id = dialog.created_identifier()
            if new_id:
                # Triggers refresh + select via _pending_select_identifier.
                self.select_record_by_identifier(new_id)
            else:
                self.refresh()

    def _on_edit_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("identifier")
        if not identifier:
            return
        try:
            fresh = self._client.get_decision(identifier)
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
                title="Could not load decision",
                message=(
                    "Could not load the latest version of this decision."
                ),
                detail=str(exc),
                parent=self,
            ).exec()
            return

        dialog = DecisionEditDialog(self._client, fresh, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("identifier") or ""
        title = record.get("title") or ""
        if not identifier:
            return
        dialog = DecisionDeleteDialog(self._client, identifier, title, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_restore_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("identifier") or ""
        title = record.get("title") or ""
        if not identifier:
            return
        confirm = QMessageBox(self)
        confirm.setWindowTitle("Restore decision")
        confirm.setText(
            f"Restore {identifier} — {title or '(untitled)'}?\n\n"
            "Its status will return to Active."
        )
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        confirm.setDefaultButton(QMessageBox.StandardButton.No)
        if confirm.exec() != QMessageBox.StandardButton.Yes:
            return
        try:
            self._client.restore_decision(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            _log.warning("Connection lost restoring %s: %s", identifier, exc)
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            _log.warning("Domain error restoring %s: %s", identifier, exc)
            ErrorDialog(
                title="Could not restore decision",
                message=(
                    "An error occurred while restoring the decision. "
                    "Please try again."
                ),
                detail=str(exc),
                parent=self,
            ).exec()
            return
        self.refresh()

    def _decision_link_or_dash(self, identifier: str | None) -> QLabel:
        if not identifier:
            return _label("—", dim=True)
        return self._link_label(f'<a href="decision:{identifier}">{identifier}</a>')

    def _link_label(self, html: str) -> QLabel:
        label = QLabel()
        label.setText(html)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setOpenExternalLinks(False)
        label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        label.setWordWrap(True)
        label.linkActivated.connect(self._emit_link_navigation)
        return label

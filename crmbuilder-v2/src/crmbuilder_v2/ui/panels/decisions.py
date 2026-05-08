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

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
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
        super().__init__(client, parent)
        self._new_button = QPushButton("New Decision")
        self._new_button.setObjectName("new_decision_button")
        self._new_button.clicked.connect(self._on_new_decision_clicked)
        self._action_layout.addWidget(self._new_button)

    def entity_title(self) -> str:
        return "Decisions"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_decisions()

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

        # Edit / Delete button strip at the top of the detail pane.
        button_strip = QWidget()
        button_strip_layout = QHBoxLayout(button_strip)
        button_strip_layout.setContentsMargins(0, 0, 0, 0)
        button_strip_layout.setSpacing(6)
        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("edit_decision_button")
        edit_btn.clicked.connect(lambda _checked=False, r=record: self._on_edit_clicked(r))
        button_strip_layout.addWidget(edit_btn)
        delete_btn = QPushButton("Delete")
        delete_btn.setObjectName("delete_decision_button")
        delete_btn.clicked.connect(lambda _checked=False, r=record: self._on_delete_clicked(r))
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
        outer.addWidget(_label("References", bold=True))
        refs = extras.get("references") or {}
        as_source = refs.get("as_source") or []
        as_target = refs.get("as_target") or []
        rendered_any = False
        # Inbound `decided_in` from sessions reads naturally; surface them first.
        for ref in as_target:
            if ref.get("relationship") == "decided_in" and ref.get(
                "source_type"
            ) == "session":
                source_id = ref.get("source_id") or ""
                outer.addWidget(self._reference_row(
                    f'Decided in: <a href="session:{source_id}">{source_id}</a>'
                ))
                rendered_any = True
        # Generic rendering for any remaining refs (both directions).
        for ref in as_target:
            if ref.get("relationship") == "decided_in" and ref.get(
                "source_type"
            ) == "session":
                continue  # already rendered
            outer.addWidget(self._reference_row(_format_ref(ref, direction="from")))
            rendered_any = True
        for ref in as_source:
            outer.addWidget(self._reference_row(_format_ref(ref, direction="to")))
            rendered_any = True
        if not rendered_any:
            outer.addWidget(_label("(no references)", dim=True))

        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

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

    def _reference_row(self, html: str) -> QLabel:
        return self._link_label(html)

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


def _format_ref(ref: dict, *, direction: str) -> str:
    """Generic reference renderer: ``{relationship} ({direction}): <link>``."""
    if direction == "from":
        # Inbound: this entity is the target.
        other_type = ref.get("source_type") or ""
        other_id = ref.get("source_id") or ""
    else:
        other_type = ref.get("target_type") or ""
        other_id = ref.get("target_id") or ""
    relationship = ref.get("relationship") or "?"
    href = f"{other_type}:{other_id}"
    label_text = f"{other_type.replace('_', ' ').title()} {other_id}".strip()
    if not label_text:
        label_text = href
    return (
        f"{relationship} ({direction}): "
        f'<a href="{href}">{label_text}</a>'
    )

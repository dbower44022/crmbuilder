"""Candidate Review panel — PI-256 (PRJ-027 / REQ-341).

The human review surface for source-mapping candidates the reconciler surfaces
(PI-255): an unmatched source entity / field / association / value awaiting a
human mapping decision. Slice 1 is the read surface — the candidate list ordered
into confidence buckets (high → medium → low → unranked), with a detail pane
showing the discovered source object and the reconciler's name-match suggestion.
The resolve workflow (accept / reject / revise → create the mapping), staleness
review, and the supersession chain are subsequent slices.

A ``mapping_candidate`` is an integer-PK discovery record (no prefixed
identifier), so this panel keys rows on the synthetic ``id`` and renders the
candidate dict directly.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.dialogs.candidate_resolve import (
    ResolveAssociationCandidateDialog,
    ResolveEntityCandidateDialog,
    ResolveFieldCandidateDialog,
)
from crmbuilder_v2.ui.exceptions import StorageConnectionError
from crmbuilder_v2.ui.widgets.datetime_format import format_timestamp
from crmbuilder_v2.ui.widgets.form_helpers import primary_button

_log = logging.getLogger("crmbuilder_v2.ui.panels.candidate_review")

# Confidence buckets, highest first (REQ-341 "grouped by confidence"). An
# unranked candidate (no suggestion) sorts last. Resolved candidates sort below
# open ones so the reviewer's outstanding work is at the top.
_CONFIDENCE_RANK: dict[str | None, int] = {
    "high": 0,
    "medium": 1,
    "low": 2,
    None: 3,
}

_CANDIDATE_TYPE_LABEL: dict[str, str] = {
    "entity": "Entity",
    "field": "Field",
    "association": "Association",
    "value": "Value",
}


def _heading_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("detail_heading")
    return label


def _source_display(record: dict[str, Any]) -> str:
    """Human label for the discovered source object."""
    entity = record.get("source_entity_name") or ""
    field = record.get("source_field_name")
    value = record.get("source_value")
    if value:
        return f"{entity}.{field or '?'} = {value}"
    if field:
        return f"{entity}.{field}"
    return entity


class CandidateReviewPanel(ListDetailPanel):
    """Read surface for reconciler-surfaced mapping candidates (PI-256 slice 1)."""

    def __init__(self, client, parent=None):
        self._show_resolved = False
        super().__init__(client, parent)
        self._show_resolved_check = QCheckBox("Show resolved")
        self._show_resolved_check.setObjectName("show_resolved_check")
        self._show_resolved_check.toggled.connect(self._on_show_resolved_toggled)
        self._action_layout.addWidget(self._show_resolved_check)

    # ------------------------------------------------------------------
    # ListDetailPanel hooks
    # ------------------------------------------------------------------

    def entity_title(self) -> str:
        return "Candidate Review"

    def fetch_records(self) -> list[dict[str, Any]]:
        resolved_filter = None if self._show_resolved else False
        records = self._client.list_mapping_candidates(resolved=resolved_filter)
        for r in records:
            conf = r.get("suggestion_confidence")
            r["confidence_display"] = (conf or "—").capitalize()
            r["type_display"] = _CANDIDATE_TYPE_LABEL.get(
                r.get("candidate_type"), r.get("candidate_type") or ""
            )
            r["source_display"] = _source_display(r)
            r["resolved_display"] = "Resolved" if r.get("resolved") else "Open"
        # Group by confidence bucket (open first), then type, then source.
        records.sort(
            key=lambda r: (
                bool(r.get("resolved")),
                _CONFIDENCE_RANK.get(r.get("suggestion_confidence"), 3),
                r.get("candidate_type") or "",
                r.get("source_display") or "",
            )
        )
        return records

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="confidence_display", title="Confidence", width=110),
            ColumnSpec(field="type_display", title="Type", width=110),
            ColumnSpec(field="source_display", title="Source object"),
            ColumnSpec(field="resolved_display", title="State", width=90),
        ]

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        # The mappings already decided for this candidate's source instance —
        # context for the upcoming resolve workflow (slice 2).
        instance = record.get("instance_identifier")
        if not instance:
            return {"source_mappings": []}
        return {
            "source_mappings": self._client.list_source_mappings(
                instance_identifier=instance
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

        # Resolve action — an open entity / field / association candidate can be
        # mapped or rejected here (slice 2 + 2b). Value candidates are a later slice.
        is_open = not record.get("resolved")
        if is_open and record.get("candidate_type") in (
            "entity", "field", "association"
        ):
            strip = QWidget()
            strip_layout = QHBoxLayout(strip)
            strip_layout.setContentsMargins(0, 0, 0, 0)
            resolve_btn = primary_button("Resolve…")
            resolve_btn.setObjectName("resolve_candidate_button")
            resolve_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_resolve_clicked(r)
            )
            strip_layout.addWidget(resolve_btn)
            strip_layout.addStretch(1)
            outer.addWidget(strip)

        outer.addWidget(_heading_label(_source_display(record) or "(candidate)"))

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        def _row(label: str, value: Any) -> None:
            v = QLabel(str(value) if value not in (None, "") else "—")
            v.setWordWrap(True)
            form.addRow(QLabel(label), v)

        _row("Candidate type", _CANDIDATE_TYPE_LABEL.get(
            record.get("candidate_type"), record.get("candidate_type")))
        _row("Source instance", record.get("instance_identifier"))
        _row("Source entity", record.get("source_entity_name"))
        _row("Source field", record.get("source_field_name"))
        _row("Source value", record.get("source_value"))
        _row("Suggestion confidence", record.get("confidence_display"))
        _row("Suggestion basis", record.get("suggestion_basis"))
        _row("State", "Resolved" if record.get("resolved") else "Open — awaiting decision")
        if record.get("resolved"):
            _row("Resolved at", format_timestamp(record.get("resolved_at")))
            _row("Resolved to source mapping",
                 record.get("resolved_to_source_mapping_identifier"))
            _row("Resolved to field mapping",
                 record.get("resolved_to_field_mapping_identifier"))

        outer.addLayout(form)

        decided = extras.get("source_mappings") or []
        outer.addWidget(QLabel(
            f"Decisions on this instance so far: {len(decided)} source mapping(s)."
        ))
        outer.addStretch(1)

        scroll.setWidget(container)
        return scroll

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_show_resolved_toggled(self, checked: bool) -> None:
        self._show_resolved = checked
        self.refresh()

    _RESOLVE_DIALOGS = {
        "entity": ResolveEntityCandidateDialog,
        "field": ResolveFieldCandidateDialog,
        "association": ResolveAssociationCandidateDialog,
    }

    def _on_resolve_clicked(self, record: dict[str, Any]) -> None:
        dialog_cls = self._RESOLVE_DIALOGS.get(record.get("candidate_type"))
        if dialog_cls is None:
            return
        try:
            dialog = dialog_cls(self._client, record, self)
        except StorageConnectionError as exc:
            _log.warning("Connection lost opening resolve dialog: %s", exc)
            self.connection_lost.emit(str(exc))
            return
        try:
            accepted = dialog.exec() == QDialog.DialogCode.Accepted
        except StorageConnectionError as exc:
            _log.warning("Connection lost resolving candidate: %s", exc)
            self.connection_lost.emit(str(exc))
            return
        if accepted:
            self.refresh()

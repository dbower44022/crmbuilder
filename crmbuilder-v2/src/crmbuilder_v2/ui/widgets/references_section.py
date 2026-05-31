"""ReferencesSection — references rendered as a sortable/filterable grid.

History: through v0.6 this widget rendered each reference as a rich-text
``<a href>`` QLabel showing only *identifier + entity type*, grouped into
kind-labeled sub-sections. You could not tell *what* ``PI-048`` was, nor see
its status or dates, without navigating away (PRJ-015 usability item).

This rewrite (PRJ-015) replaces the label list with a single
``QTableView`` over all of a record's references, with columns:
Direction, Relationship, Identifier, Type, Title, Status, Created, Updated.
The table is sortable (click a header) and filterable (the filter box
matches across every column). Title/Status/Created/Updated come from the
``other_summary`` block the access layer now attaches to each edge
(``references.list_touching``); edges whose far side has no summary
(version-keyed singletons, catalog rows) show identifier + type only.

Behavior preserved from the prior widget:
- ``navigate_requested(entity_type, identifier)`` — emitted on double-click
  (or the row right-click "Go to" action).
- ``references_changed()`` — emitted after a successful add/delete.
- ``Add reference`` button (only when a ``client`` was supplied) and
  ``set_add_enabled`` to hide it for read-only/audit panels.
- Per-row right-click menu (Delete reference + Go to).
- ``exclude_relationships`` filtering.
- Constructor signature, including the vestigial ``inbound_label`` /
  ``outbound_label`` args kept for back-compat with the v0.4 ``processes``
  panel.

The widget is a pure renderer over a pre-fetched payload (the shape from
``StorageClient.list_references_touching``); fetching still happens on the
panel's ``fetch_detail_extras`` worker thread.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPoint,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.styling import t
from crmbuilder_v2.ui.widgets.form_helpers import text_link_button

# (direction, relationship) → human-readable label. Direction is "inbound"
# (the record is the target) or "outbound" (the record is the source).
# Unmapped kinds fall through to :func:`_default_kind_label`.
_KIND_LABELS: dict[tuple[str, str], str] = {
    ("outbound", "is_about"): "Is about",
    ("inbound", "is_about"): "Cited by",
    ("outbound", "references"): "References",
    ("inbound", "references"): "Referenced by",
    ("inbound", "decided_in"): "Decided in",
    ("outbound", "decided_in"): "Decides",
    ("outbound", "supersedes"): "Supersedes",
    ("inbound", "supersedes"): "Superseded by",
    ("outbound", "affects"): "Affects",
    ("inbound", "affects"): "Affected by",
    ("outbound", "blocked_by"): "Blocked by",
    ("inbound", "blocked_by"): "Blocks",
    ("outbound", "covers"): "Covers",
    ("inbound", "covers"): "Covered by",
    ("outbound", "entity_scopes_to_domain"): "Scopes to",
    ("inbound", "entity_scopes_to_domain"): "Scoped by",
    ("outbound", "process_hands_off_to_process"): "Hands off to",
    ("inbound", "process_hands_off_to_process"): "Receives from",
    ("outbound", "resolves"): "Resolves",
    ("inbound", "resolves"): "Resolved by",
    ("outbound", "addresses"): "Addresses",
    ("inbound", "addresses"): "Addressed by",
}

# Display columns, in order. Each tuple is (header, row-dict key).
_COLUMNS: list[tuple[str, str]] = [
    ("Direction", "direction_label"),
    ("Relationship", "kind_label"),
    ("Identifier", "identifier"),
    ("Type", "type_label"),
    ("Title", "title"),
    ("Status", "status"),
    ("Created", "created"),
    ("Updated", "updated"),
]

_DASH = "—"
_ROW_HEIGHT = 26


def _default_kind_label(direction: str, relationship: str) -> str:
    pretty = relationship.replace("_", " ")
    if direction == "outbound":
        return pretty[:1].upper() + pretty[1:]
    return f"{pretty.title()} (inbound)"


def _pretty_entity_type(entity_type: str) -> str:
    return entity_type.replace("_", " ").title()


def _fmt_dt(value: Any) -> str:
    """Render an ISO timestamp as ``YYYY-MM-DD HH:MM`` for display.

    The access layer serializes timestamps to ISO strings via the API
    envelope; we keep the date + minute and drop seconds/offset. Non-ISO or
    empty values pass through as a dash.
    """
    if not value:
        return _DASH
    text = str(value)
    # ISO: "2026-05-30T22:51:41.677924+00:00" → "2026-05-30 22:51".
    date_part, _, time_part = text.partition("T")
    if not time_part:
        return date_part or _DASH
    return f"{date_part} {time_part[:5]}"


class _RefsModel(QAbstractTableModel):
    """Table model over flattened reference rows.

    Each row dict carries the display fields plus the bookkeeping needed
    for navigation and deletion (``other_type``, ``other_id``, ``ref`` — the
    raw edge). ``DisplayRole`` returns formatted strings; ``UserRole``
    returns sort keys (raw ISO strings sort chronologically; text sorts
    case-insensitively).
    """

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        super().__init__()
        self._rows = rows

    def rowCount(self, _parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self._rows)

    def columnCount(self, _parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(_COLUMNS)

    def row_dict(self, source_row: int) -> dict[str, Any]:
        return self._rows[source_row]

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(_COLUMNS)
        ):
            return _COLUMNS[section][0]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        key = _COLUMNS[index.column()][1]
        value = row.get(key)
        if role == Qt.ItemDataRole.DisplayRole:
            if key in ("created", "updated"):
                return _fmt_dt(value)
            return value if value not in (None, "") else _DASH
        if role == Qt.ItemDataRole.UserRole:
            # Sort key: ISO strings already sort chronologically; text
            # lowercased for case-insensitive ordering; missing sorts last.
            if value in (None, ""):
                return "￿"
            if key in ("created", "updated"):
                return str(value)
            return str(value).lower()
        return None


class ReferencesSection(QWidget):
    """Renders a record's inbound and outbound references as a grid."""

    navigate_requested = Signal(str, str)
    references_changed = Signal()

    def __init__(
        self,
        entity_type: str,
        identifier: str,
        references_payload: dict[str, Any] | None,
        *,
        exclude_relationships: set[str] | None = None,
        client: StorageClient | None = None,
        inbound_label: str = "Inbound",  # noqa: ARG002 — vestigial; back-compat
        outbound_label: str = "Outbound",  # noqa: ARG002 — vestigial; back-compat
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._entity_type = entity_type
        self._identifier = identifier
        self._exclude = set(exclude_relationships or set())
        self._client = client
        self._add_button = None
        self._table = None
        self._build(references_payload or {})

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _flatten(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for direction, bucket_key, other_type_key, other_id_key in (
            ("inbound", "as_target", "source_type", "source_id"),
            ("outbound", "as_source", "target_type", "target_id"),
        ):
            for ref in payload.get(bucket_key) or []:
                rel = ref.get("relationship") or "?"
                if rel in self._exclude:
                    continue
                other_type = ref.get(other_type_key) or ""
                other_id = ref.get(other_id_key) or ""
                summary = ref.get("other_summary") or {}
                rows.append(
                    {
                        "direction": direction,
                        "direction_label": "In" if direction == "inbound" else "Out",
                        "kind_label": _KIND_LABELS.get(
                            (direction, rel), _default_kind_label(direction, rel)
                        ),
                        "identifier": other_id,
                        "type_label": _pretty_entity_type(other_type),
                        "title": summary.get("title"),
                        "status": summary.get("status"),
                        "created": summary.get("created_at"),
                        "updated": summary.get("updated_at"),
                        # bookkeeping
                        "other_type": other_type,
                        "other_id": other_id,
                        "ref": ref,
                    }
                )
        return rows

    def _build(self, payload: dict[str, Any]) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(t("space.2").rstrip("px")))
        layout.addWidget(self._heading("References"))

        rows = self._flatten(payload)
        if not rows:
            layout.addWidget(self._dim_label("(none)"))
            self._add_button_row(layout)
            return

        # Filter box.
        self._filter = QLineEdit()
        self._filter.setObjectName("references_section_filter")
        self._filter.setPlaceholderText("Filter references…")
        self._filter.setClearButtonEnabled(True)
        layout.addWidget(self._filter)

        # Model + proxy (sort + filter across all columns).
        self._model = _RefsModel(rows)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterKeyColumn(-1)  # match against every column
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setSortRole(Qt.ItemDataRole.UserRole)
        self._filter.textChanged.connect(self._on_filter_changed)

        # Table view.
        self._table = QTableView(self)
        self._table.setModel(self._proxy)
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        self._table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(_ROW_HEIGHT)
        self._table.setWordWrap(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        # Title column takes the slack so long titles are readable.
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._table.doubleClicked.connect(self._on_double_clicked)
        self._table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._table)
        self._fit_height()

        self._add_button_row(layout)

    # ------------------------------------------------------------------
    # Height: size the table to its (filtered) content so the detail
    # pane's outer scroll area handles overflow (no nested scrollbar).
    # ------------------------------------------------------------------

    def _fit_height(self) -> None:
        if self._table is None:
            return
        visible = self._proxy.rowCount()
        header_h = self._table.horizontalHeader().height()
        frame = 2 * self._table.frameWidth()
        self._table.setFixedHeight(header_h + _ROW_HEIGHT * max(visible, 1) + frame + 2)

    def _on_filter_changed(self, text: str) -> None:
        self._proxy.setFilterFixedString(text)
        self._fit_height()

    # ------------------------------------------------------------------
    # Add-reference button row
    # ------------------------------------------------------------------

    def _add_button_row(self, layout: QVBoxLayout) -> None:
        if self._client is None:
            return
        layout.addSpacing(int(t("space.3").rstrip("px")))
        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(int(t("space.2").rstrip("px")))
        self._add_button = text_link_button("Add reference", icon_name="plus")
        self._add_button.setObjectName("references_section_add_button")
        self._add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_button.clicked.connect(self._on_add_clicked)
        button_row.addWidget(self._add_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

    def set_add_enabled(self, enabled: bool) -> None:
        if self._add_button is not None:
            self._add_button.setVisible(enabled)

    # ------------------------------------------------------------------
    # Row resolution / interaction
    # ------------------------------------------------------------------

    def _row_at(self, proxy_index: QModelIndex) -> dict[str, Any] | None:
        if not proxy_index.isValid():
            return None
        source_index = self._proxy.mapToSource(proxy_index)
        return self._model.row_dict(source_index.row())

    def _on_double_clicked(self, proxy_index: QModelIndex) -> None:
        row = self._row_at(proxy_index)
        if row and row["other_type"] and row["other_id"]:
            self.navigate_requested.emit(row["other_type"], row["other_id"])

    def _on_context_menu(self, position: QPoint) -> None:
        proxy_index = self._table.indexAt(position)
        row = self._row_at(proxy_index)
        if row is None:
            return
        menu = QMenu(self._table)
        if self._client is not None:
            delete_action = menu.addAction("Delete reference")
            delete_action.triggered.connect(
                lambda _checked=False, r=row["ref"]: self._on_delete_clicked(r)
            )
        go_action = menu.addAction(f"Go to {row['other_id']}")
        go_action.triggered.connect(
            lambda _checked=False, et=row["other_type"], ident=row["other_id"]:
            self.navigate_requested.emit(et, ident)
        )
        menu.exec(self._table.viewport().mapToGlobal(position))

    # ------------------------------------------------------------------
    # Add / Delete handlers
    # ------------------------------------------------------------------

    def _on_add_clicked(self) -> None:
        if self._client is None:
            return
        from crmbuilder_v2.ui.dialogs.reference_create import (
            ReferenceCreateDialog,
        )

        dialog = ReferenceCreateDialog(
            self._client,
            pre_populated_source=(self._entity_type, self._identifier),
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.references_changed.emit()

    def _on_delete_clicked(self, reference: dict[str, Any]) -> None:
        if self._client is None:
            return
        ref_id = reference.get("id")
        if ref_id is None:
            return
        from crmbuilder_v2.ui.dialogs.reference_delete import (
            ReferenceDeleteDialog,
            edge_text,
        )

        dialog = ReferenceDeleteDialog(
            self._client,
            reference_id=int(ref_id),
            edge=edge_text(reference),
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.references_changed.emit()

    # ------------------------------------------------------------------
    # Small label helpers
    # ------------------------------------------------------------------

    def _heading(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("references_section_heading")
        label.setStyleSheet(
            f"font-size: {t('font.size.body_large')};"
            f" font-weight: {t('font.weight.semibold')};"
            f" color: {t('color.neutral.800')};"
        )
        return label

    def _dim_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"color: {t('color.neutral.500')};")
        return label

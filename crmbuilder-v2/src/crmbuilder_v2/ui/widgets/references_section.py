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

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPoint,
    Qt,
    Signal,
)
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QStackedWidget,
    QTableView,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.styling import t
from crmbuilder_v2.ui.widgets.form_helpers import text_link_button
from crmbuilder_v2.ui.widgets.grouping_tree_model import GroupingTreeModel
from crmbuilder_v2.ui.widgets.link_filter_input import LinkFilterInput
from crmbuilder_v2.ui.widgets.multi_sort_header import MultiSortHeaderView
from crmbuilder_v2.ui.widgets.multi_sort_proxy import MultiSortProxyModel

# Longest query echoed verbatim in the no-match empty state before it is
# elided with an ellipsis (so a pasted blob does not blow out the line).
_EMPTY_STATE_QUERY_MAX = 40

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
# Floor for a draggable (Interactive) column (PI-119 / WTK-073) so it cannot be
# hidden by an over-drag — this widget has no header context menu to restore a
# zero-width column — and so ``MultiSortHeaderView``'s right-aligned ``▲1``/``▼2``
# precedence glyph is never clipped against the header label. Cosmetic; tunable.
_MIN_SECTION_WIDTH = 48

# Group-by control (PI-117 / WTK-068). Each option maps its label to a
# row-dict key; the ``_GROUP_NONE`` sentinel restores the flat table. The
# special ``created`` key buckets on the YYYY-MM-DD date prefix rather than
# the raw timestamp — handled in :meth:`ReferencesSection._group_value`.
_GROUP_NONE = "(none)"
_GROUP_OPTIONS: list[tuple[str, str]] = [
    (_GROUP_NONE, ""),
    ("Relationship", "kind_label"),
    ("Type", "type_label"),
    ("Status", "status"),
    ("Direction", "direction_label"),
    ("Created (by day)", "created"),
]


# Work Task grid configuration (PI-120 / WTK-076). The same grid, a second
# contract: five columns (identifier, title, area, status, claim state), no
# date columns, Title as the slack-absorbing Stretch column. Rows are built by
# the panel (joining the membership edges with fetched Work Task records) and
# fed in directly, so there is no ``_flatten`` step for this contract.
_WORK_TASK_COLUMNS: list[tuple[str, str]] = [
    ("Identifier", "identifier"),
    ("Title", "title"),
    ("Area", "area"),
    ("Status", "status"),
    ("Claim state", "claim_state"),
]

_WORK_TASK_GROUP_OPTIONS: list[tuple[str, str]] = [
    (_GROUP_NONE, ""),
    ("Area", "area"),
    ("Status", "status"),
    ("Claim state", "claim_state"),
]


def _references_row_menu(
    section: ReferencesSection, view: QWidget, row: dict[str, Any] | None
) -> QMenu | None:
    """References per-row menu: Delete reference (when writable) + Go to.

    The unchanged default behavior — split out as the References contract's
    ``row_menu`` so a different contract can supply a different menu without
    touching this path (and so ``test_context_menus`` is unaffected).
    """
    if row is None:
        return None
    menu = QMenu(view)
    if section._client is not None:
        delete_action = menu.addAction("Delete reference")
        delete_action.triggered.connect(
            lambda _checked=False, r=row["ref"]: section._on_delete_clicked(r)
        )
    go_action = menu.addAction(f"Go to {row['other_id']}")
    go_action.triggered.connect(
        lambda _checked=False, et=row["other_type"], ident=row["other_id"]:
        section.navigate_requested.emit(et, ident)
    )
    return menu


def _work_task_row_menu(
    section: ReferencesSection, view: QWidget, row: dict[str, Any] | None
) -> QMenu | None:
    """Work Task per-row menu: Go to + Copy identifier (read-only, no Delete)."""
    if row is None:
        return None
    menu = QMenu(view)
    ident = row["other_id"]
    go_action = menu.addAction(f"Go to {ident}")
    go_action.triggered.connect(
        lambda _checked=False, et=row["other_type"], i=ident:
        section.navigate_requested.emit(et, i)
    )
    copy_action = menu.addAction("Copy identifier")
    copy_action.triggered.connect(
        lambda _checked=False, i=ident: _copy_to_clipboard(i)
    )
    return menu


def _copy_to_clipboard(text: str) -> None:
    clipboard = QGuiApplication.clipboard()
    if clipboard is not None:
        clipboard.setText(text)


@dataclass(frozen=True)
class GridContract:
    """Parameterizes the grid for a given record kind (PI-120 / WTK-076).

    Exactly one grid implementation exists; a contract is the small value
    object that names the references-specific seams so the same code can drive
    both references and Work Tasks. The References configuration
    (:data:`_REFERENCES_CONTRACT`) is the built-in default and reproduces the
    pre-WTK-076 behavior byte-for-byte; a non-references contract supplies its
    own columns/group options/row menu without forking the widget.

    :param columns: display columns, in order — ``(header, row-dict key)``.
    :param datetime_keys: row-dict keys rendered via :func:`_fmt_dt` and
        bucketed by-day when grouped (empty for contracts with no timestamps).
    :param group_options: the Group-by combo's ``(label, row-dict key)`` list.
    :param stretch_column: index of the slack-absorbing Stretch column.
    :param heading: section heading text; empty suppresses the heading widget
        (the host panel supplies its own).
    :param empty_text: dim placeholder shown when there are no rows.
    :param preview_subtitle_key: row-dict key feeding the inline preview card's
        subtitle line.
    :param show_add_button: whether to build the Add row (writable contracts
        only); read-only contracts pass ``False``.
    :param row_menu: ``(section, view, row) -> QMenu | None`` per-row menu
        factory.
    """

    columns: list[tuple[str, str]]
    datetime_keys: frozenset[str]
    group_options: list[tuple[str, str]]
    stretch_column: int
    heading: str
    empty_text: str
    preview_subtitle_key: str
    show_add_button: bool
    row_menu: Callable[
        [ReferencesSection, QWidget, dict[str, Any] | None], QMenu | None
    ]


_REFERENCES_CONTRACT = GridContract(
    columns=_COLUMNS,
    datetime_keys=frozenset({"created", "updated"}),
    group_options=_GROUP_OPTIONS,
    stretch_column=4,
    heading="References",
    empty_text="(none)",
    preview_subtitle_key="kind_label",
    show_add_button=True,
    row_menu=_references_row_menu,
)

_WORK_TASK_CONTRACT = GridContract(
    columns=_WORK_TASK_COLUMNS,
    datetime_keys=frozenset(),
    group_options=_WORK_TASK_GROUP_OPTIONS,
    stretch_column=1,
    heading="",
    empty_text="No Work Tasks recorded.",
    preview_subtitle_key="area",
    show_add_button=False,
    row_menu=_work_task_row_menu,
)


def _default_kind_label(direction: str, relationship: str) -> str:
    pretty = relationship.replace("_", " ")
    if direction == "outbound":
        return pretty[:1].upper() + pretty[1:]
    return f"{pretty.title()} (inbound)"


def _pretty_entity_type(entity_type: str) -> str:
    return entity_type.replace("_", " ").title()


def _elide(text: str, limit: int = _EMPTY_STATE_QUERY_MAX) -> str:
    """Truncate an echoed query with an ellipsis so a long paste fits."""
    return text if len(text) <= limit else text[: limit - 1] + "…"


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

    def __init__(
        self,
        rows: list[dict[str, Any]],
        columns: list[tuple[str, str]],
        datetime_keys: frozenset[str],
    ) -> None:
        super().__init__()
        self._rows = rows
        self._columns = columns
        self._datetime_keys = datetime_keys

    def rowCount(self, _parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self._rows)

    def columnCount(self, _parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self._columns)

    def row_dict(self, source_row: int) -> dict[str, Any]:
        return self._rows[source_row]

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(self._columns)
        ):
            return self._columns[section][0]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        key = self._columns[index.column()][1]
        value = row.get(key)
        if role == Qt.ItemDataRole.DisplayRole:
            if key in self._datetime_keys:
                return _fmt_dt(value)
            return value if value not in (None, "") else _DASH
        if role == Qt.ItemDataRole.UserRole:
            # Sort key: ISO strings already sort chronologically; text
            # lowercased for case-insensitive ordering; missing sorts last.
            if value in (None, ""):
                return "￿"
            if key in self._datetime_keys:
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
        contract: GridContract | None = None,
        rows: list[dict[str, Any]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._entity_type = entity_type
        self._identifier = identifier
        self._exclude = set(exclude_relationships or set())
        self._client = client
        # References is the built-in default (no contract argument → today's
        # behavior, unchanged for all existing call sites). A non-references
        # contract (e.g. Work Tasks) supplies its rows directly, bypassing the
        # references ``_flatten`` step.
        self._contract = contract or _REFERENCES_CONTRACT
        self._add_button = None
        self._table = None
        self._empty_state = None
        self._preview = None
        if rows is None:
            rows = self._flatten(references_payload or {})
        self._build(rows)

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

    def _build(self, rows: list[dict[str, Any]]) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(t("space.2").rstrip("px")))
        if self._contract.heading:
            layout.addWidget(self._heading(self._contract.heading))

        if not rows:
            layout.addWidget(self._dim_label(self._contract.empty_text))
            self._add_button_row(layout)
            return

        # Filter + Group-by row (PI-116 filter on the left, PI-117 grouping
        # controls on the right, reading left-to-right). The clear button
        # restores the full list immediately; typing applies after the
        # 250 ms debounce settles. ``filterChanged`` (not ``textChanged``)
        # drives the apply path so the model is re-filtered once per burst.
        self._filter = LinkFilterInput(object_name="references_section_filter")
        self._filter.filterChanged.connect(self._on_filter_changed)
        layout.addWidget(self._control_row())

        # Model + multi-sort proxy (sort + filter across all columns). The
        # PI-117 ``MultiSortProxyModel`` is a drop-in for the stock proxy:
        # same filter contract, plus an ordered sort-key list.
        self._model = _RefsModel(
            rows, self._contract.columns, self._contract.datetime_keys
        )
        self._proxy = MultiSortProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterKeyColumn(-1)  # match against every column
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setSortRole(Qt.ItemDataRole.UserRole)
        # Re-sort within groups whenever the sort keys change while grouped.
        self._proxy.sortKeysChanged.connect(self._on_sort_keys_changed)

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
        # Multi-column header: our own click routing replaces Qt's stock
        # single-column sort, so disable the built-in sorting toggle.
        self._table.setSortingEnabled(False)
        table_header = MultiSortHeaderView(
            Qt.Orientation.Horizontal, self._table
        )
        self._table.setHorizontalHeader(table_header)
        table_header.attach_proxy(self._proxy)
        self._proxy.clear_sort()  # deterministic default: column 0, ascending
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(_ROW_HEIGHT)
        self._table.setWordWrap(False)
        # PI-119 / WTK-073: Interactive sections expose a draggable divider grip
        # and honor ``resizeSection`` — that is what user drag-resize means in
        # Qt. ResizeToContents (the prior mode) auto-sized every column and
        # silently ignored manual resize, so this flip is the whole feature.
        table_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        # Title column absorbs the slack so long titles stay readable and the
        # grid always fills the viewport width (no trailing empty gutter); a
        # Stretch column ignores the content seed and manual resize below.
        table_header.setSectionResizeMode(
            self._contract.stretch_column, QHeaderView.ResizeMode.Stretch
        )
        table_header.setMinimumSectionSize(_MIN_SECTION_WIDTH)
        # One-time content-fit seed: Interactive columns otherwise start at the
        # generic defaultSectionSize. Runs after the model + view are wired so
        # the metrics are real; the Stretch column (4) is unaffected.
        self._table.resizeColumnsToContents()
        self._table.doubleClicked.connect(self._on_double_clicked)
        self._table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self._table.customContextMenuRequested.connect(self._on_context_menu)

        # Grouped tree (PI-117): a sibling presentation shown only while a
        # group key is active. The table and tree are two views of one row
        # set; a QStackedWidget keeps exactly one visible.
        self._tree = QTreeView(self)
        self._tree.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._tree.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tree.setAlternatingRowColors(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setExpandsOnDoubleClick(True)
        self._tree.doubleClicked.connect(self._on_double_clicked)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        self._tree.expanded.connect(self._on_tree_expansion_changed)
        self._tree.collapsed.connect(self._on_tree_expansion_changed)
        self._group_model: GroupingTreeModel | None = None

        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._table)
        self._stack.addWidget(self._tree)
        self._stack.setCurrentWidget(self._table)
        layout.addWidget(self._stack)

        # No-match empty state — hidden until a filter excludes every row.
        # Distinct from the "record has no links at all" case above, which
        # renders "(none)" and never builds the filter box.
        self._empty_state = self._dim_label("")
        self._empty_state.setObjectName("references_section_empty_state")
        self._empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_state.setVisible(False)
        layout.addWidget(self._empty_state)

        self._install_preview()

        self._fit_height()

        self._add_button_row(layout)

    # ------------------------------------------------------------------
    # Inline linked-record preview (PI-118 / WTK-071)
    # ------------------------------------------------------------------

    def _install_preview(self) -> None:
        """Wire the hover/keyboard inline preview over the table and tree.

        Additive over the PI-116/PI-117 rebuild: one ``PreviewController``,
        shared by the flat ``QTableView`` and the grouped ``QTreeView`` (both
        already route through :meth:`_row_at`), fed by a field extractor that
        names the far-side record. Any reorder / regroup / refilter dismisses
        an open card (§3.7). When no ``StorageClient`` is available the read
        path is harmless — the card still renders the always-available row
        fields and reports no extra details.
        """
        # Lazy import avoids a load-time cycle: the preview module imports the
        # grid's ``_fmt_dt`` from this module at top level.
        from crmbuilder_v2.ui.widgets.linked_record_preview import (
            PreviewController,
        )

        self._preview = PreviewController(
            self,
            self._row_at,
            self._client,
            lambda row, _col: (
                row.get("other_type") or "",
                row.get("other_id") or "",
                row.get("title"),
                row.get(self._contract.preview_subtitle_key),
            ),
        )
        self._preview.attach_view(self._table)
        self._preview.attach_view(self._tree)
        # Dismiss on any reorder / regroup / refilter (§3.7).
        self._proxy.sortKeysChanged.connect(self._preview.dismiss)
        self._group_combo.currentIndexChanged.connect(self._preview.dismiss)
        self._filter.filterChanged.connect(self._preview.dismiss)

    def closeEvent(self, event):  # noqa: N802 (Qt naming)
        """Tear down the preview controller's in-flight workers on close."""
        preview = getattr(self, "_preview", None)
        if preview is not None:
            preview.shutdown()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Height: size the table to its (filtered) content so the detail
    # pane's outer scroll area handles overflow (no nested scrollbar).
    # ------------------------------------------------------------------

    def _fit_height(self) -> None:
        """Size the visible presentation (table or grouped tree) to content.

        The table fits its filtered proxy row count; the tree fits its
        currently-expanded node count (group nodes + visible children) so
        the detail pane's outer scroll handles overflow with no nested
        scrollbar. Collapsing a group re-runs this and shrinks the tree.
        """
        if self._table is None:
            return
        if self._is_grouped():
            # sizeHint().height() is layout-state-independent; the live
            # .height() drifts after the first event-loop pass (the custom
            # header hides Qt's sort arrow), which would desync repeated
            # fits. Use the stable hint so the delta on filter/collapse is
            # exactly the row-count change × row height.
            header_h = self._tree.header().sizeHint().height()
            frame = 2 * self._tree.frameWidth()
            visible = self._visible_tree_rows()
            self._tree.setFixedHeight(
                header_h + _ROW_HEIGHT * max(visible, 1) + frame + 2
            )
            return
        visible = self._proxy.rowCount()
        header_h = self._table.horizontalHeader().sizeHint().height()
        frame = 2 * self._table.frameWidth()
        self._table.setFixedHeight(header_h + _ROW_HEIGHT * max(visible, 1) + frame + 2)

    def _visible_tree_rows(self) -> int:
        """Count group nodes plus the children of currently-expanded groups."""
        if self._group_model is None:
            return 0
        total = 0
        for g in range(self._group_model.group_count()):
            total += 1  # the group node itself
            group_index = self._group_model.index(g, 0, QModelIndex())
            if self._tree.isExpanded(group_index):
                total += self._group_model.child_count(g)
        return total

    def _on_filter_changed(self, text: str) -> None:
        self._proxy.setFilterFixedString(text)
        if self._is_grouped():
            self._rebuild_tree()
        self._update_empty_state(text)
        self._fit_height()

    def _update_empty_state(self, text: str) -> None:
        """Show/hide the no-match line for the current filter text.

        The empty state appears only when an active (non-empty) query
        excludes every loaded row; clearing the field (``text == ""``)
        always dismisses it and restores the active presentation. Takes
        precedence over both the flat table and the grouped tree.
        """
        if self._empty_state is None or self._table is None:
            return
        query = text.strip()
        no_match = bool(query) and self._proxy.rowCount() == 0
        if no_match:
            self._empty_state.setText(f'No links match "{_elide(query)}".')
        self._empty_state.setVisible(no_match)
        self._stack.setVisible(not no_match)

    # ------------------------------------------------------------------
    # Sort + Group controls (PI-117 / WTK-068)
    # ------------------------------------------------------------------

    def _control_row(self) -> QWidget:
        """Filter box + Group-by combo + Expand/Collapse-all links."""
        container = QWidget(self)
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(int(t("space.2").rstrip("px")))
        row.addWidget(self._filter, stretch=1)

        row.addWidget(QLabel("Group by:"))
        self._group_combo = QComboBox(container)
        self._group_combo.setObjectName("references_section_group_combo")
        for label, _key in self._contract.group_options:
            self._group_combo.addItem(label)
        self._group_combo.currentIndexChanged.connect(self._on_group_changed)
        row.addWidget(self._group_combo)

        self._expand_all_link = text_link_button("Expand all")
        self._expand_all_link.setObjectName("references_section_expand_all")
        self._expand_all_link.clicked.connect(self._on_expand_all)
        self._collapse_all_link = text_link_button("Collapse all")
        self._collapse_all_link.setObjectName("references_section_collapse_all")
        self._collapse_all_link.clicked.connect(self._on_collapse_all)
        self._expand_all_link.setVisible(False)
        self._collapse_all_link.setVisible(False)
        row.addWidget(self._expand_all_link)
        row.addWidget(self._collapse_all_link)
        return container

    def _is_grouped(self) -> bool:
        combo = getattr(self, "_group_combo", None)
        return combo is not None and combo.currentIndex() > 0

    def _group_field(self) -> str:
        return self._contract.group_options[self._group_combo.currentIndex()][1]

    def _ordered_rows(self) -> list[dict[str, Any]]:
        """Read the proxy's currently visible rows in sorted order."""
        rows: list[dict[str, Any]] = []
        for r in range(self._proxy.rowCount()):
            source = self._proxy.mapToSource(self._proxy.index(r, 0))
            rows.append(self._model.row_dict(source.row()))
        return rows

    def _group_value(self, row: dict[str, Any]) -> str:
        """Group-key value for a row — the display string, by-day for dates."""
        key = self._group_field()
        raw = row.get(key)
        if raw in (None, ""):
            return _GROUP_NONE
        if key in self._contract.datetime_keys:
            # Bucket on the YYYY-MM-DD prefix (reusing _fmt_dt's date part).
            return str(raw).partition("T")[0] or _GROUP_NONE
        return str(raw)

    def _on_group_changed(self, _index: int) -> None:
        # Combo population during _build emits this before the stack/tree
        # exist; ignore until the views are wired.
        if getattr(self, "_stack", None) is None:
            return
        if self._is_grouped():
            self._rebuild_tree()
            self._stack.setCurrentWidget(self._tree)
            self._expand_all_link.setVisible(True)
            self._collapse_all_link.setVisible(True)
        else:
            self._group_model = None
            self._stack.setCurrentWidget(self._table)
            self._expand_all_link.setVisible(False)
            self._collapse_all_link.setVisible(False)
        self._fit_height()

    def _on_sort_keys_changed(self) -> None:
        # While grouped, a sort-key change must re-order rows within groups.
        if self._is_grouped():
            self._rebuild_tree()
            self._fit_height()

    def _cell_display(self, row: dict[str, Any], column: int) -> str:
        """Render a row's cell for ``column`` exactly as the flat grid does.

        Shared with the grouped ``QTreeView`` (via ``GroupingTreeModel``) so
        child rows match the table. Reads the active contract's columns and
        datetime keys; date columns format via :func:`_fmt_dt`, empties show
        the dash sentinel.
        """
        key = self._contract.columns[column][1]
        value = row.get(key)
        if key in self._contract.datetime_keys:
            return _fmt_dt(value)
        return value if value not in (None, "") else _DASH

    def _rebuild_tree(self) -> None:
        rows = self._ordered_rows()
        headers = [col[0] for col in self._contract.columns]
        if self._group_model is None:
            self._group_model = GroupingTreeModel(
                rows, headers, self._group_value, self._cell_display, self
            )
            self._tree.setModel(self._group_model)
        else:
            self._group_model.set_rows(rows)
        self._tree.expandAll()
        self._tree.header().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._tree.header().setSectionResizeMode(
            self._contract.stretch_column, QHeaderView.ResizeMode.Stretch
        )

    def _on_expand_all(self) -> None:
        self._tree.expandAll()
        self._fit_height()

    def _on_collapse_all(self) -> None:
        self._tree.collapseAll()
        self._fit_height()

    def _on_tree_expansion_changed(self, _index: QModelIndex) -> None:
        self._fit_height()

    # ------------------------------------------------------------------
    # Add-reference button row
    # ------------------------------------------------------------------

    def _add_button_row(self, layout: QVBoxLayout) -> None:
        if self._client is None or not self._contract.show_add_button:
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

    def _row_at(self, index: QModelIndex) -> dict[str, Any] | None:
        """Resolve a row dict from an index on whichever view is live.

        Table indices map proxy → source; grouped-tree indices delegate to
        the grouping model (group-node indices return ``None``). Both paths
        land on the same underlying edge dict, so navigation/delete behave
        identically whether the flat table or the grouped tree is showing.
        """
        if not index.isValid():
            return None
        model = index.model()
        if self._group_model is not None and model is self._group_model:
            return self._group_model.row_dict(index)
        source_index = self._proxy.mapToSource(index)
        return self._model.row_dict(source_index.row())

    def _on_double_clicked(self, index: QModelIndex) -> None:
        row = self._row_at(index)
        if row and row["other_type"] and row["other_id"]:
            self.navigate_requested.emit(row["other_type"], row["other_id"])

    def _on_context_menu(self, position: QPoint) -> None:
        self._show_row_menu(self._table, self._table.indexAt(position), position)

    def _on_tree_context_menu(self, position: QPoint) -> None:
        self._show_row_menu(self._tree, self._tree.indexAt(position), position)

    def _show_row_menu(
        self, view: QWidget, index: QModelIndex, position: QPoint
    ) -> None:
        # Opening the row menu dismisses any open preview card (§3.6) so the
        # menu and the preview never overlap.
        if self._preview is not None:
            self._preview.dismiss()
        menu = self._build_row_menu(view, self._row_at(index))
        if menu is None:
            return
        menu.exec(view.viewport().mapToGlobal(position))

    def _build_row_menu(
        self, view: QWidget, row: dict[str, Any] | None
    ) -> QMenu | None:
        """Build the per-row right-click menu, or ``None`` for a group node.

        Delegates to the active contract's ``row_menu`` factory so the menu's
        label set is contract-specific (References: Delete + Go to; Work Tasks:
        Go to + Copy identifier). Split from :meth:`_show_row_menu` so the set
        can be asserted without the blocking ``menu.exec``.
        """
        return self._contract.row_menu(self, view, row)

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


class WorkTaskGridSection(ReferencesSection):
    """Work Task configuration of the grid (PI-120 / WTK-076).

    A thin parameterization of :class:`ReferencesSection` — *not* a fork — that
    drives the same grid (PI-116 filter, PI-117 sort/grouping, PI-118 preview,
    PI-119 drag-resize) with the Work Task column model and a read-only
    (no Delete) row menu. Rows are pre-built by the host panel (joining the
    ``work_task_belongs_to_workstream`` membership edges with fetched Work Task
    records for area + claim state) and passed in directly, so this section
    runs no references ``_flatten`` step and writes no edges.
    """

    def __init__(
        self,
        entity_type: str,
        identifier: str,
        rows: list[dict[str, Any]],
        *,
        client: StorageClient | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            entity_type,
            identifier,
            None,
            client=client,
            contract=_WORK_TASK_CONTRACT,
            rows=rows,
            parent=parent,
        )

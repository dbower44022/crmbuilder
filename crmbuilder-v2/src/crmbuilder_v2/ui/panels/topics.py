"""Topics panel — PRD §4.6 list/detail with QTreeView master + v0.2 §4.4 write surfaces.

Slice D rewrote the v0.1 read-only panel: the master pane switches
from a flat ``QTableView`` (with name-prefix indentation) to a
``QTreeView`` backed by a ``QStandardItemModel``. Roots are top-level
topics; children nest under their parent via ``parent_topic_id``.
Single-row selection emits the standard detail-pane flow. The write
surface — New Topic toolbar button plus Edit/Delete in the detail
pane — opens the create/edit/delete dialogs from
``ui.dialogs.topic_*``. The shared ``ReferencesSection`` widget renders
inbound and outbound references on the detail pane.

v0.3 slice A migrates the panel to the ``_create_master_widget``
factory introduced on ``ListDetailPanel`` (DEC-035). The factory
returns a configured ``QTreeView`` with its ``QStandardItemModel``
pre-installed; the v0.2 ``_build_ui`` override and the
``self._table = self._tree`` workaround are gone. Selection still flows
through the base's ``_on_current_changed`` slot, which Topics
overrides to route to ``_on_tree_current_changed``.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QFont, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.dialogs.topic_create import TopicCreateDialog
from crmbuilder_v2.ui.dialogs.topic_delete import TopicDeleteDialog
from crmbuilder_v2.ui.dialogs.topic_edit import TopicEditDialog
from crmbuilder_v2.ui.exceptions import (
    NotFoundError,
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.panels._governance_helpers import created_updated_section
from crmbuilder_v2.ui.widgets.form_helpers import (
    destructive_button,
    primary_button,
    required_label,
)
from crmbuilder_v2.ui.widgets.master_pane_delegate import MasterPaneTreeDelegate
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection

_log = logging.getLogger("crmbuilder_v2.ui.panels.topics")

_LONG_TEXT_MIN_HEIGHT = 80

_IDENTIFIER_ROLE = Qt.ItemDataRole.UserRole + 1


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


class _LucideChevronTreeView(QTreeView):
    """``QTreeView`` whose branch indicator renders as a Lucide chevron.

    Default ``QTreeView`` draws an OS-themed triangle for the
    expand/collapse indicator; design pass §2.3 (DEC-093) replaces
    this with Lucide ``chevron-right`` (collapsed) and
    ``chevron-down`` (expanded) so the indicator is consistent across
    platforms. The painting is delegated to
    :meth:`MasterPaneTreeDelegate.paint_branch`.
    """

    def drawBranches(self, painter, rect, index):  # noqa: N802 — Qt naming
        if self.model() is None or not index.isValid():
            return
        if not self.model().hasChildren(index):
            return
        MasterPaneTreeDelegate.paint_branch(
            painter, rect, expanded=self.isExpanded(index)
        )


class TopicsPanel(ListDetailPanel):
    """Topics panel — QTreeView master + write surface (v0.2 slice D)."""

    # v0.6 slice B (DEC-093): use the tree-aware master-pane delegate
    # so chevron painting (drawBranches override on the tree view)
    # composes cleanly with the inherited row-state vocabulary.
    master_pane_delegate_cls = MasterPaneTreeDelegate

    def __init__(self, client, parent=None):
        # Initialize the items-by-identifier map before ``super().__init__``
        # runs ``_build_ui`` — which doesn't touch it but guards against
        # any future construction-time selection request.
        self._items_by_identifier: dict[str, QStandardItem] = {}
        super().__init__(client, parent)
        self._new_button = primary_button("New Topic")
        self._new_button.setObjectName("new_topic_button")
        self._new_button.clicked.connect(self._on_new_clicked)
        self._action_layout.addWidget(self._new_button)

    # ------------------------------------------------------------------
    # ListDetailPanel hooks
    # ------------------------------------------------------------------

    def entity_title(self) -> str:
        return "Topics"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_topics()

    def list_columns(self) -> list[ColumnSpec]:
        # Single-column header — the tree shows hierarchy via indentation.
        return [ColumnSpec(field="_display_name", title="Topic")]

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        identifier = record.get("identifier")
        if not identifier:
            return {"references": {"as_source": [], "as_target": []}}
        return {
            "references": self._client.list_references_touching(
                "topic", identifier
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

        button_strip = QWidget()
        button_strip_layout = QHBoxLayout(button_strip)
        button_strip_layout.setContentsMargins(0, 0, 0, 0)
        button_strip_layout.setSpacing(6)
        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("edit_topic_button")
        edit_btn.clicked.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )
        button_strip_layout.addWidget(edit_btn)
        delete_btn = destructive_button("Delete")
        delete_btn.setObjectName("delete_topic_button")
        delete_btn.clicked.connect(
            lambda _checked=False, r=record: self._on_delete_clicked(r)
        )
        button_strip_layout.addWidget(delete_btn)
        button_strip_layout.addStretch(1)
        outer.addWidget(button_strip)

        outer.addWidget(_heading_label(record.get("name") or "(unnamed)"))

        form = QFormLayout()
        # v0.6 slice C: label-above form layout per design pass §2.4.
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form.addRow(
            required_label("Identifier"), _label(record.get("identifier") or "")
        )
        form.addRow(
            "Parent Topic",
            self._parent_link_or_dash(record.get("parent_topic_identifier")),
        )
        outer.addLayout(form)

        outer.addWidget(_separator())
        outer.addWidget(_label("Description", bold=True))
        outer.addWidget(_long_text(record.get("description") or ""))

        # PI-108: created audit timestamp (immutable, no Last Updated).
        # Tree master pane has no list-column flow, so detail-only.
        outer.addWidget(_separator())
        outer.addWidget(created_updated_section(record, "created_at", None))

        outer.addWidget(_separator())
        identifier = record.get("identifier") or ""
        references_section = ReferencesSection(
            "topic",
            identifier,
            extras.get("references") or {},
            client=self._client,
        )
        self._wire_link_section(references_section)
        references_section.references_changed.connect(self.refresh)
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
            new_action = menu.addAction("New topic")
            new_action.triggered.connect(self._on_new_clicked)
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

    def _record_at_index(self, index: QModelIndex) -> dict[str, Any] | None:
        """Map a tree-view index to the record dict via the identifier role.

        Overrides the base's ``record_at(row)`` lookup because the tree
        model is a ``QStandardItemModel``, not a ``_RecordTableModel``.
        """
        if not index.isValid():
            return None
        item = self._tree_model.itemFromIndex(index)
        if item is None:
            return None
        identifier = item.data(_IDENTIFIER_ROLE)
        return self._record_by_identifier(identifier)

    # ------------------------------------------------------------------
    # Master-pane factory override — QTreeView in place of QTableView
    # ------------------------------------------------------------------

    def _create_master_widget(self) -> QAbstractItemView:
        """Return a configured ``_LucideChevronTreeView`` with the topics tree model.

        v0.3 slice A — DEC-035. Pre-installs ``self._tree_model`` so the
        base's default ``_RecordTableModel`` setup is skipped (the base's
        ``_build_ui`` checks ``self._master_view.model() is None``).

        v0.6 slice B — DEC-093. Uses :class:`_LucideChevronTreeView` so
        the default branch indicators render as Lucide chevrons (down
        when expanded, right when collapsed) per design pass §2.3.
        Indentation is set to 16px (``space.4``) per the same section.
        """
        tree = _LucideChevronTreeView(self)
        tree.setHeaderHidden(False)
        tree.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        tree.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tree.setUniformRowHeights(True)
        tree.setIndentation(MasterPaneTreeDelegate.indentation_per_level())
        self._tree_model = QStandardItemModel()
        self._tree_model.setHorizontalHeaderLabels(["Topic"])
        tree.setModel(self._tree_model)
        return tree

    # ------------------------------------------------------------------
    # Refresh — populate the tree from the flat record list
    # ------------------------------------------------------------------

    def _on_fetch_success(self, result: list[dict[str, Any]]) -> None:
        if not self._sender_is_current_refresh():
            return
        # Capture the prior selection so refreshes preserve it when the
        # identifier still exists post-refresh. See the matching
        # ListDetailPanel._on_fetch_success comment for the cross-panel
        # navigation race this guards against.
        prior_selected_id = self._currently_selected_identifier()
        raw = list(result) if isinstance(result, list) else []
        self._records = self._post_process_records(raw)
        self._populate_tree(self._records)
        self._status_label.setText(f"{len(self._records)} topics")
        pending = self._pending_select_identifier
        self._pending_select_identifier = None
        desired = pending if pending is not None else prior_selected_id
        if desired is not None and self._select_by_identifier(desired):
            return
        self._show_empty_detail()

    def _populate_tree(self, topics: list[dict[str, Any]]) -> None:
        self._tree_model.clear()
        self._tree_model.setHorizontalHeaderLabels(["Topic"])
        # Reset the identifier → item map. Used by
        # ``select_record_by_identifier``.
        self._items_by_identifier: dict[str, QStandardItem] = {}

        by_identifier: dict[str, dict[str, Any]] = {}
        for t in topics:
            ident = t.get("identifier")
            if ident:
                by_identifier[ident] = t

        children: dict[str | None, list[dict[str, Any]]] = {}
        orphan_ids: set[str] = set()
        for t in topics:
            parent = t.get("parent_topic_identifier")
            ident = t.get("identifier")
            # Treat references to missing parents as orphans (root-level
            # with a visual indicator).
            if parent is not None and parent not in by_identifier:
                if ident:
                    orphan_ids.add(ident)
                parent = None
            children.setdefault(parent, []).append(t)
        for bucket in children.values():
            bucket.sort(key=lambda r: (r.get("name") or "").lower())

        visited: set[str] = set()

        def insert(parent_item: QStandardItem | None, parent_id: str | None) -> None:
            for topic in children.get(parent_id, []):
                ident = topic.get("identifier") or ""
                if not ident or ident in visited:
                    continue
                visited.add(ident)
                base = f"{ident} — {topic.get('name') or ''}"
                label = base + " (orphan)" if ident in orphan_ids else base
                item = QStandardItem(label)
                item.setEditable(False)
                item.setData(ident, _IDENTIFIER_ROLE)
                if parent_item is None:
                    self._tree_model.appendRow(item)
                else:
                    parent_item.appendRow(item)
                self._items_by_identifier[ident] = item
                insert(item, ident)

        insert(None, None)

        # Topics that are part of an orphan-bucket where the parent_id
        # was rewritten to None above are already inserted via the
        # ``children[None]`` walk. Topics caught in cycles (no path
        # from any root) need a defensive sweep.
        for t in topics:
            ident = t.get("identifier") or ""
            if not ident or ident in visited:
                continue
            visited.add(ident)
            label = f"{ident} — {t.get('name') or ''} (orphan)"
            item = QStandardItem(label)
            item.setEditable(False)
            item.setData(ident, _IDENTIFIER_ROLE)
            self._tree_model.appendRow(item)
            self._items_by_identifier[ident] = item

        self._table.expandAll()

    # ------------------------------------------------------------------
    # Selection routing
    # ------------------------------------------------------------------

    def _on_tree_current_changed(
        self, current: QModelIndex, _previous: QModelIndex
    ) -> None:
        if not current.isValid():
            self._show_empty_detail()
            return
        item = self._tree_model.itemFromIndex(current)
        if item is None:
            self._show_empty_detail()
            return
        identifier = item.data(_IDENTIFIER_ROLE)
        record = self._record_by_identifier(identifier)
        if record is None:
            self._show_empty_detail()
            return
        self._begin_detail_load(record)

    def _on_current_changed(
        self, current: QModelIndex, previous: QModelIndex
    ) -> None:  # pragma: no cover — superseded by ``_on_tree_current_changed``
        # Defensive override: the base wires the QTableView's selection
        # model to this slot. We never connect it on the tree, but if
        # the base path is invoked anyway treat it as a tree event.
        self._on_tree_current_changed(current, previous)

    def _record_by_identifier(self, identifier: str | None) -> dict[str, Any] | None:
        if not identifier:
            return None
        for record in self._records:
            if record.get("identifier") == identifier:
                return record
        return None

    def _select_by_identifier(self, identifier: str) -> bool:
        """Override the base: select the tree item via the identifier→item map.

        With a QTreeView, "row" doesn't address an item uniquely, so the
        base's row-walk fallback in ``ListDetailPanel._select_by_identifier``
        is replaced by a direct map lookup populated in ``_populate_tree``.
        """
        item = self._items_by_identifier.get(identifier)
        if item is None:
            return False
        self._table.setCurrentIndex(item.index())
        self._table.scrollTo(item.index())
        return True

    def _select_row(self, row: int) -> None:  # pragma: no cover — base-class fallback
        # The base's ``_select_by_identifier`` is now the public path; this
        # remains as a defensive fallback in case anything still calls
        # ``_select_row`` directly.
        if 0 <= row < len(self._records):
            ident = self._records[row].get("identifier")
            if ident:
                self._select_by_identifier(ident)

    def _currently_selected_identifier(self) -> str | None:
        """Read the selected item's identifier via the tree's identifier role.

        Overrides the base's row-index lookup because the tree model is
        a ``QStandardItemModel`` whose nested rows don't address records
        uniquely by ``self._records[row]``.
        """
        sel_model = self._master_view.selectionModel()
        if sel_model is None:
            return None
        index = sel_model.currentIndex()
        if not index.isValid():
            return None
        item = self._tree_model.itemFromIndex(index)
        if item is None:
            return None
        ident = item.data(_IDENTIFIER_ROLE)
        return ident if isinstance(ident, str) else None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parent_link_or_dash(self, identifier: str | None) -> QLabel:
        if not identifier:
            return _label("—", dim=True)
        label = QLabel()
        label.setText(f'<a href="topic:{identifier}">{identifier}</a>')
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setOpenExternalLinks(False)
        label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        label.setWordWrap(True)
        label.linkActivated.connect(self._emit_link_navigation)
        return label

    # ------------------------------------------------------------------
    # Write-surface click handlers (v0.2 slice D)
    # ------------------------------------------------------------------

    def _on_new_clicked(self) -> None:
        dialog = TopicCreateDialog(self._client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_id = dialog.created_identifier()
            if new_id:
                self.select_record_by_identifier(new_id)
            else:
                self.refresh()

    def _on_edit_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("identifier")
        if not identifier:
            return
        try:
            fresh = self._client.get_topic(identifier)
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
                title="Could not load topic",
                message="Could not load the latest version of this topic.",
                detail=str(exc),
                parent=self,
            ).exec()
            return

        dialog = TopicEditDialog(self._client, fresh, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("identifier") or ""
        title = record.get("name") or ""
        if not identifier:
            return
        dialog = TopicDeleteDialog(self._client, identifier, title, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

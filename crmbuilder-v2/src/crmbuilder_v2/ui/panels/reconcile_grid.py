"""Redesigned reconciliation surface — native Qt grid + drill — PI-333 (REL-027).

The operator surface rebuilt on Qt Model/View over the extended compare payload
(PI-331): a landing **existence grid** (entities × locations) the operator reads
at a glance, and a drill into a per-entity **detail tree** grouped into Fields /
Layouts / Relationships / Formulas / Settings / Other (REQ-368/370/373/378). This
slice delivers the read-and-navigate surface; the unified apply interaction and
multi-select batch apply layer on top in PI-334, view-only handling in PI-335.

Reads go through the synchronous :class:`StorageClient` (fast local API calls).
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTableView,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.panels.reconcile_models import (
    RECORD_ROLE,
    EntityDetailModel,
    ExistenceGridModel,
)
from crmbuilder_v2.ui.widgets.selectable_text import CopyableMessageBox

_log = logging.getLogger(__name__)

_PRIMARY = (
    "QPushButton { background-color: #1565C0; color: white; border-radius: 4px; "
    "padding: 6px 14px; } QPushButton:hover { background-color: #0D47A1; }"
)
_SECONDARY = (
    "QPushButton { background-color: #FFA726; color: white; border-radius: 4px; "
    "padding: 6px 14px; } QPushButton:hover { background-color: #FB8C00; }"
)


class _ExistenceFilterProxy(QSortFilterProxyModel):
    """Sort/filter proxy over the existence grid (REQ-373 sort + a filter bar).

    With ``needs_attention_only`` set, only entities that are not fully in sync
    pass — those missing/unknown in some location, or whose ``entity_identifier``
    is in the differing set (entities with at least one field-level difference).
    """

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._attention_only = False
        self._differing: set[str] = set()

    def set_attention_only(self, on: bool) -> None:
        self._attention_only = on
        self.invalidateRowsFilter()

    def set_differing(self, ids: set[str]) -> None:
        self._differing = set(ids)
        self.invalidateRowsFilter()

    def filterAcceptsRow(  # noqa: N802
        self, source_row: int, source_parent: QModelIndex
    ) -> bool:
        if not self._attention_only:
            return True
        model = self.sourceModel()
        idx = model.index(source_row, 0, source_parent)
        rec = model.data(idx, RECORD_ROLE) or {}
        if rec.get("entity_identifier") in self._differing:
            return True
        return any(
            rec.get(k) != "present" for k in ("design", "instance_a", "instance_b")
        )


class ReconcileGridPanel(QWidget):
    """Existence-grid landing view with a drill into a per-entity detail tree."""

    def __init__(self, client: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._client = client
        self._instances: list[dict[str, Any]] = []
        self._payload: dict[str, Any] = {}
        self._groups_by_entity: dict[str, dict[str, Any]] = {}
        self._build_ui()
        self._load_instances()

    # ------------------------------------------------------------------ build
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)

        picker = QHBoxLayout()
        picker.addWidget(QLabel("Instance A:"))
        self._combo_a = QComboBox()
        self._combo_a.setMinimumWidth(220)
        picker.addWidget(self._combo_a)
        picker.addWidget(QLabel("Instance B:"))
        self._combo_b = QComboBox()
        self._combo_b.setMinimumWidth(220)
        picker.addWidget(self._combo_b)
        compare_btn = QPushButton("Compare")
        compare_btn.setStyleSheet(_PRIMARY)
        compare_btn.setObjectName("reconcile_compare_button")
        compare_btn.clicked.connect(self._on_compare)
        picker.addWidget(compare_btn)
        self._attention = QCheckBox("Only entities needing attention")
        self._attention.setObjectName("reconcile_attention_filter")
        self._attention.toggled.connect(self._on_attention_toggled)
        picker.addWidget(self._attention)
        picker.addStretch()
        outer.addLayout(picker)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_grid_view())
        self._stack.addWidget(self._build_detail_view())
        outer.addWidget(self._stack)

        self._summary = QLabel("Pick two instances and click Compare.")
        self._summary.setStyleSheet("color: #757575;")
        outer.addWidget(self._summary)

    def _build_grid_view(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        self._grid_model = ExistenceGridModel(parent=self)
        self._grid_proxy = _ExistenceFilterProxy(self)
        self._grid_proxy.setSourceModel(self._grid_model)
        self._grid = QTableView()
        self._grid.setObjectName("reconcile_existence_grid")
        self._grid.setModel(self._grid_proxy)
        self._grid.setSortingEnabled(True)
        self._grid.setAlternatingRowColors(True)
        self._grid.setShowGrid(True)
        self._grid.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._grid.verticalHeader().setVisible(False)
        self._grid.horizontalHeader().setStretchLastSection(True)
        self._grid.doubleClicked.connect(self._on_grid_activated)
        lay.addWidget(self._grid)
        hint = QLabel("Double-click an entity to see its differences.")
        hint.setStyleSheet("color: #9E9E9E;")
        lay.addWidget(hint)
        return page

    def _build_detail_view(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        bar = QHBoxLayout()
        back = QPushButton("← Back to all entities")
        back.setStyleSheet(_SECONDARY)
        back.setObjectName("reconcile_back_button")
        back.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        bar.addWidget(back)
        self._detail_title = QLabel("")
        self._detail_title.setStyleSheet("font-weight: bold;")
        bar.addWidget(self._detail_title)
        bar.addStretch()
        lay.addLayout(bar)

        self._detail_model = EntityDetailModel(parent=self)
        self._detail = QTreeView()
        self._detail.setObjectName("reconcile_detail_tree")
        self._detail.setModel(self._detail_model)
        self._detail.setAlternatingRowColors(True)
        self._detail.setRootIsDecorated(True)
        self._detail.setUniformRowHeights(True)
        self._detail.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        lay.addWidget(self._detail)
        return page

    # ------------------------------------------------------------------ data
    def _load_instances(self) -> None:
        try:
            self._instances = self._client.list_instances()
        except Exception as exc:  # noqa: BLE001
            _log.warning("could not load instances: %s", exc)
            self._instances = []
        for combo in (self._combo_a, self._combo_b):
            combo.clear()
            for inst in self._instances:
                combo.addItem(
                    f"{inst.get('instance_name')} ({inst.get('instance_identifier')})",
                    inst.get("instance_identifier"),
                )
        if self._combo_b.count() > 1:
            self._combo_b.setCurrentIndex(1)
        if not self._instances:
            self._summary.setText(
                "This engagement has no instances yet. Add a source and a target "
                "instance, run an audit, then come back to reconcile."
            )

    def _instance_label(self, identifier: str | None) -> str:
        for inst in self._instances:
            if inst.get("instance_identifier") == identifier:
                return inst.get("instance_name") or identifier or "?"
        return identifier or "?"

    def _on_compare(self) -> None:
        a = self._combo_a.currentData()
        b = self._combo_b.currentData()
        if not a or not b:
            CopyableMessageBox.information(self, "Reconcile", "Select two instances first.")
            return
        if a == b:
            CopyableMessageBox.information(self, "Reconcile", "Pick two different instances.")
            return
        try:
            self._payload = self._client.reconcile_compare(a, b)
        except Exception as exc:  # noqa: BLE001
            CopyableMessageBox.warning(self, "Reconcile", f"Compare failed: {exc}")
            return
        self._populate(a, b)

    def _populate(self, a: str, b: str) -> None:
        a_label, b_label = self._instance_label(a), self._instance_label(b)
        self._groups_by_entity = {
            g["entity_identifier"]: g
            for g in self._payload.get("groups", [])
            if g.get("entity_identifier")
        }
        self._grid_model.set_rows(
            self._payload.get("existence", []),
            instance_a_label=a_label,
            instance_b_label=b_label,
        )
        self._grid_proxy.set_differing(set(self._groups_by_entity))
        self._grid.resizeColumnsToContents()
        self._stack.setCurrentIndex(0)
        entity_count = len(self._payload.get("existence", []))
        diff_count = self._payload.get("row_count", 0)
        self._summary.setText(
            f"{entity_count} entities · {diff_count} difference(s) across "
            f"{len(self._groups_by_entity)} entit(y/ies). Double-click an entity to drill in."
        )

    def _on_attention_toggled(self, on: bool) -> None:
        self._grid_proxy.set_attention_only(on)

    def _on_grid_activated(self, proxy_index: QModelIndex) -> None:
        src = self._grid_proxy.mapToSource(proxy_index)
        rec = self._grid_model.data(
            self._grid_model.index(src.row(), 0), RECORD_ROLE
        ) or {}
        self._drill(rec)

    def _drill(self, existence_row: dict[str, Any]) -> None:
        eid = existence_row.get("entity_identifier")
        name = existence_row.get("entity") or eid or "?"
        a_label = self._instance_label(self._combo_a.currentData())
        b_label = self._instance_label(self._combo_b.currentData())
        group = self._groups_by_entity.get(eid)
        object_groups = group.get("object_groups", []) if group else []
        self._detail_model.set_groups(
            object_groups, instance_a_label=a_label, instance_b_label=b_label
        )
        if object_groups:
            self._detail_title.setText(f"{name} — differences")
        else:
            self._detail_title.setText(f"{name} — no differences found")
        self._detail.expandAll()
        self._stack.setCurrentIndex(1)

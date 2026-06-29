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

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableView,
    QTabWidget,
    QTreeView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.panels.reconcile_models import (
    LOCATION_LABELS,
    RECORD_ROLE,
    EntityDetailModel,
    ExistenceGridModel,
    plan_apply,
)
from crmbuilder_v2.ui.widgets.selectable_text import CopyableMessageBox

_log = logging.getLogger(__name__)

#: Recorded as the transaction actor for desktop-driven reconcile actions.
_ACTOR = "desktop"

def _fill_width(
    header,
    *,
    stretch_col: int,
    content_cols,
    content_mode: QHeaderView.ResizeMode = QHeaderView.ResizeMode.ResizeToContents,
) -> None:
    """Size a view's columns to fill the full width with no manual resize (REQ-391).

    ``stretch_col`` takes all the slack (the critical text column — Entity or
    Difference); ``content_cols`` use ``content_mode``. The last section does
    not auto-stretch, so the stretch column owns the leftover space.

    ``content_mode`` defaults to ``ResizeToContents`` — right for the existence
    grid, whose location cells hold short state labels. The detail grid passes
    ``Stretch`` instead (REQ-429): its value cells can hold a layout data
    structure hundreds of characters long, and sizing them to content blew the
    grid far past the window and forced horizontal scrolling. Stretching the
    value columns shares the viewport so every column stays visible; overlong
    text elides (the view's default elide mode) and the full value is on hover.
    """
    header.setStretchLastSection(False)
    header.setSectionResizeMode(stretch_col, QHeaderView.ResizeMode.Stretch)
    for col in content_cols:
        header.setSectionResizeMode(col, content_mode)


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
        self.invalidate()

    def set_differing(self, ids: set[str]) -> None:
        self._differing = set(ids)
        self.invalidate()

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


class _EntityAuditWorker(QThread):
    """Runs the fast entity-only re-audit off the UI thread (REQ-392).

    Audits one entity on each of ``instance_ids`` in turn (so a row-level action
    can refresh both instances) and emits the combined result. A live network
    read must not block the UI thread or the app freezes.
    """

    done = Signal(list)   # list of {instance, summary} dicts
    failed = Signal(str)

    def __init__(self, client: Any, entity_identifier: str, instance_ids: list[str]) -> None:
        super().__init__()
        self._client = client
        self._entity = entity_identifier
        self._instances = instance_ids

    def run(self) -> None:  # noqa: D102
        try:
            results = [
                {"instance": iid, "result": self._client.audit_entity(iid, self._entity)}
                for iid in self._instances
            ]
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.done.emit(results)


class ReconcileGridPanel(QWidget):
    """Existence-grid landing view with a drill into a per-entity detail tree."""

    def __init__(self, client: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._client = client
        self._instances: list[dict[str, Any]] = []
        self._payload: dict[str, Any] = {}
        self._groups_by_entity: dict[str, dict[str, Any]] = {}
        self._audit_worker: _EntityAuditWorker | None = None
        self._build_ui()
        self._load_instances()

    # ------------------------------------------------------------------ build
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_reconcile_tab(), "Reconcile")
        self._tabs.addTab(self._build_history_tab(), "History")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        outer.addWidget(self._tabs)

    def _build_reconcile_tab(self) -> QWidget:
        tab = QWidget()
        outer = QVBoxLayout(tab)

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
        return tab

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
        # Per-cell re-audit (REQ-392): right-click an entity / location cell.
        self._grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._grid.customContextMenuRequested.connect(self._on_grid_context_menu)
        # Fill the full width with no manual resize (REQ-391): the entity column
        # takes the slack so its names stay readable; the location columns size to
        # their short state labels.
        _fill_width(self._grid.horizontalHeader(), stretch_col=0, content_cols=(1, 2, 3))
        self._grid.doubleClicked.connect(self._on_grid_activated)
        lay.addWidget(self._grid)
        hint = QLabel("Double-click an entity to see its differences.")
        hint.setStyleSheet("color: #9E9E9E;")
        lay.addWidget(hint)

        # Whole-entity promote (REQ-369): copy the selected entity + its supported
        # configuration to instances where it is missing or differs.
        promote = QHBoxLayout()
        promote.addWidget(QLabel("Copy selected entity to:"))
        self._promote_a = QCheckBox("Instance A")
        self._promote_b = QCheckBox("Instance B")
        promote.addWidget(self._promote_a)
        promote.addWidget(self._promote_b)
        copy_btn = QPushButton("Copy entity")
        copy_btn.setStyleSheet(_SECONDARY)
        copy_btn.setObjectName("reconcile_promote_button")
        copy_btn.clicked.connect(self._on_promote_entity)
        promote.addWidget(copy_btn)
        promote.addStretch()
        # Row-level re-audit (REQ-392): refresh the selected entity on both
        # instances. Per-cell refresh is the right-click menu above.
        reaudit_btn = QPushButton("Re-audit this entity")
        reaudit_btn.setStyleSheet(_SECONDARY)
        reaudit_btn.setObjectName("reconcile_reaudit_button")
        reaudit_btn.clicked.connect(self._on_reaudit_selected)
        promote.addWidget(reaudit_btn)
        lay.addLayout(promote)

        self._audit_status = QLabel("")
        self._audit_status.setStyleSheet("color: #757575;")
        self._audit_status.setWordWrap(True)
        lay.addWidget(self._audit_status)
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
        # Elide overlong values rather than widen the column (REQ-429); the full
        # text is exposed on hover via the model's ToolTipRole.
        self._detail.setTextElideMode(Qt.TextElideMode.ElideRight)
        # The difference column takes the slack (REQ-391); the three value columns
        # share the remaining width by stretching (REQ-429) so a long layout data
        # structure cannot push the grid past the window and force scrolling.
        _fill_width(
            self._detail.header(),
            stretch_col=0,
            content_cols=(1, 2, 3),
            content_mode=QHeaderView.ResizeMode.Stretch,
        )
        lay.addWidget(self._detail)

        # Unified apply (REQ-371/372): pick where the correct value lives and where
        # to bring it; applies to every selected, supported difference.
        apply_bar = QHBoxLayout()
        apply_bar.addWidget(QLabel("Correct value is in:"))
        self._source_combo = QComboBox()
        self._source_combo.setObjectName("reconcile_source_combo")
        apply_bar.addWidget(self._source_combo)
        apply_bar.addWidget(QLabel("Bring into line:"))
        self._target_design = QCheckBox("Master design")
        self._target_a = QCheckBox("Instance A")
        self._target_b = QCheckBox("Instance B")
        for chk in (self._target_design, self._target_a, self._target_b):
            apply_bar.addWidget(chk)
        apply_btn = QPushButton("Apply")
        apply_btn.setStyleSheet(_PRIMARY)
        apply_btn.setObjectName("reconcile_apply_button")
        apply_btn.clicked.connect(self._on_apply)
        apply_bar.addWidget(apply_btn)
        apply_bar.addStretch()
        lay.addLayout(apply_bar)

        self._apply_status = QLabel(
            "Select one or more differences, choose the source and targets, then Apply."
        )
        self._apply_status.setStyleSheet("color: #757575;")
        self._apply_status.setWordWrap(True)
        lay.addWidget(self._apply_status)
        return page

    def _build_history_tab(self) -> QWidget:
        """The reconcile transaction log + guarded rollback (carried from REL-024).

        Every capture/publish is logged and reversible; this tab lists the trail
        and offers rollback, gated by the data-loss analysis (REQ-360/361).
        """
        tab = QWidget()
        lay = QVBoxLayout(tab)
        self._log_tree = QTreeWidget()
        self._log_tree.setColumnCount(7)
        self._log_tree.setHeaderLabels(
            ["ID", "Action", "Object", "Setting", "Before → After", "Status", "By"]
        )
        self._log_tree.setObjectName("reconcile_log_tree")
        self._log_tree.setAlternatingRowColors(True)
        lay.addWidget(self._log_tree)
        row = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._load_transactions)
        rollback = QPushButton("Undo selected")
        rollback.setStyleSheet(_SECONDARY)
        rollback.setObjectName("reconcile_rollback")
        rollback.clicked.connect(self._on_rollback)
        row.addWidget(refresh)
        row.addWidget(rollback)
        row.addStretch()
        lay.addLayout(row)
        return tab

    def _on_tab_changed(self, index: int) -> None:
        if self._tabs.tabText(index) == "History":
            self._load_transactions()

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
        # Relabel the apply/promote controls with the chosen instances (REQ-374).
        self._source_combo.clear()
        self._source_combo.addItem(LOCATION_LABELS["design"], "design")
        self._source_combo.addItem(a_label, "instance_a")
        self._source_combo.addItem(b_label, "instance_b")
        self._target_a.setText(a_label)
        self._target_b.setText(b_label)
        self._promote_a.setText(a_label)
        self._promote_b.setText(b_label)
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

    # ------------------------------------------------------------------ apply
    def _loc_instance(self, loc: str) -> str | None:
        """Resolve a location key to a concrete instance identifier (None=design)."""
        if loc == "instance_a":
            return self._combo_a.currentData()
        if loc == "instance_b":
            return self._combo_b.currentData()
        return None

    def _selected_diff_rows(self) -> list[dict[str, Any]]:
        """The difference rows currently selected in the detail tree (leaves only)."""
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()
        for idx in self._detail.selectionModel().selectedIndexes():
            if idx.column() != 0:
                continue
            rec = self._detail_model.data(idx, RECORD_ROLE)
            if isinstance(rec, dict) and rec.get("member_type") and id(rec) not in seen:
                seen.add(id(rec))
                rows.append(rec)
        return rows

    def _on_apply(self) -> None:
        rows = self._selected_diff_rows()
        if not rows:
            CopyableMessageBox.information(
                self, "Reconcile", "Select one or more differences first."
            )
            return
        source_loc = self._source_combo.currentData()
        targets = [
            loc for loc, chk in (
                ("design", self._target_design),
                ("instance_a", self._target_a),
                ("instance_b", self._target_b),
            ) if chk.isChecked()
        ]
        if not targets:
            CopyableMessageBox.information(
                self, "Reconcile", "Choose at least one location to bring into line."
            )
            return

        applied = 0
        skipped: list[str] = []
        errors: list[str] = []
        view_only: list[str] = []
        for row in rows:
            label = row.get("member_name") or row.get("member_identifier") or "?"
            # View-only config (REQ-377): shown and selectable, but the platform
            # has no write path, so acting on it explains rather than no-ops.
            if not row.get("actionable"):
                view_only.append(label)
                continue
            plan = plan_apply(row, source_loc, targets)
            for reason in plan["skipped"]:
                skipped.append(f"{label}: {reason}")
            for op in plan["ops"]:
                try:
                    self._execute_op(row, op)
                    applied += 1
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{label}: {op['kind']} failed — {exc}")

        if view_only:
            CopyableMessageBox.information(
                self, "Configure by hand",
                "These items can be compared but cannot be pushed automatically — "
                "the platform has no way to write them, so they must be set by hand "
                "in the admin console:\n\n• " + "\n• ".join(view_only),
            )
        self._report_apply(applied, skipped, errors)
        if applied:
            # Refresh the comparison so the surface reflects the new state.
            self._on_compare()

    def _execute_op(self, row: dict[str, Any], op: dict[str, str]) -> None:
        """Run one capture/publish operation against the API."""
        member_type = row["member_type"]
        mid = row["member_identifier"]
        attribute = row.get("attribute")
        if op["kind"] == "capture":
            instance = self._loc_instance(op["location"])
            if member_type == "entity":
                self._client.reconcile_capture_setting(
                    instance=instance, entity_identifier=mid,
                    attribute=attribute, actor=_ACTOR,
                )
            else:
                self._client.reconcile_capture(
                    instance=instance, field_identifier=mid,
                    attribute=attribute, actor=_ACTOR,
                )
        else:  # publish
            instance = self._loc_instance(op["location"])
            self._client.reconcile_publish(
                instance=instance, member_type=member_type,
                member_identifier=mid, attribute=attribute, actor=_ACTOR,
            )

    def _report_apply(
        self, applied: int, skipped: list[str], errors: list[str]
    ) -> None:
        parts = [f"Applied {applied} change(s)."]
        if skipped:
            parts.append(f"Skipped {len(skipped)}: " + "; ".join(skipped))
        if errors:
            parts.append(f"{len(errors)} failed: " + "; ".join(errors))
        msg = " ".join(parts)
        self._apply_status.setText(msg)
        if errors:
            CopyableMessageBox.warning(self, "Reconcile", msg)

    # --------------------------------------------------------------- promote
    def _on_promote_entity(self) -> None:
        """Copy the selected entity to the chosen instances (whole-entity promote)."""
        idxs = self._grid.selectionModel().selectedRows() if self._grid.selectionModel() else []
        if not idxs:
            CopyableMessageBox.information(
                self, "Reconcile", "Select an entity row first."
            )
            return
        targets = [
            loc for loc, chk in (
                ("instance_a", self._promote_a), ("instance_b", self._promote_b)
            ) if chk.isChecked()
        ]
        if not targets:
            CopyableMessageBox.information(
                self, "Reconcile", "Choose at least one instance to copy the entity to."
            )
            return

        applied = 0
        errors: list[str] = []
        for proxy_idx in idxs:
            src = self._grid_proxy.mapToSource(proxy_idx)
            rec = self._grid_model.data(
                self._grid_model.index(src.row(), 0), RECORD_ROLE
            ) or {}
            eid = rec.get("entity_identifier")
            name = rec.get("entity") or eid or "?"
            for loc in targets:
                try:
                    self._client.reconcile_publish(
                        instance=self._loc_instance(loc), member_type="entity",
                        member_identifier=eid, actor=_ACTOR,
                    )
                    applied += 1
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{name} → {LOCATION_LABELS.get(loc, loc)}: {exc}")

        msg = f"Copied {applied} entit(y/ies)."
        if errors:
            msg += " Failed: " + "; ".join(errors)
            CopyableMessageBox.warning(self, "Reconcile", msg)
        self._summary.setText(msg)
        if applied:
            self._on_compare()

    # ----------------------------------------------------------- re-audit
    def _existence_at(self, proxy_index: QModelIndex) -> dict[str, Any]:
        src = self._grid_proxy.mapToSource(proxy_index)
        return self._grid_model.data(
            self._grid_model.index(src.row(), 0), RECORD_ROLE
        ) or {}

    def _on_reaudit_selected(self) -> None:
        """Row-level re-audit (REQ-392): refresh the selected entity on both
        instances."""
        sel = self._grid.selectionModel().selectedRows() if self._grid.selectionModel() else []
        if not sel:
            CopyableMessageBox.information(self, "Reconcile", "Select an entity row first.")
            return
        rec = self._existence_at(sel[0])
        both = [i for i in (self._combo_a.currentData(), self._combo_b.currentData()) if i]
        self._start_entity_audit(rec, both)

    def _on_grid_context_menu(self, pos) -> None:
        index = self._grid.indexAt(pos)
        if not index.isValid():
            return
        rec = self._existence_at(index)
        name = rec.get("entity") or rec.get("entity_identifier") or "entity"
        menu = QMenu(self._grid)
        both = [i for i in (self._combo_a.currentData(), self._combo_b.currentData()) if i]
        act_both = menu.addAction(f"Re-audit {name} on both instances")
        # Per-cell: a location column (2 = Instance A, 3 = Instance B) re-audits
        # just that instance; the design column (1) has nothing to audit.
        col = index.column()
        per_cell = None
        if col in (2, 3):
            loc_id = self._combo_a.currentData() if col == 2 else self._combo_b.currentData()
            if loc_id:
                per_cell = (menu.addAction(f"Re-audit {name} on {self._instance_label(loc_id)}"), [loc_id])
        chosen = menu.exec(self._grid.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is act_both:
            self._start_entity_audit(rec, both)
        elif per_cell and chosen is per_cell[0]:
            self._start_entity_audit(rec, per_cell[1])

    def _start_entity_audit(self, rec: dict[str, Any], instance_ids: list[str]) -> None:
        eid = rec.get("entity_identifier")
        name = rec.get("entity") or eid or "entity"
        if not eid:
            CopyableMessageBox.information(self, "Reconcile", "Select an entity row first.")
            return
        if not instance_ids:
            CopyableMessageBox.information(self, "Reconcile", "No instance to audit.")
            return
        if self._audit_worker is not None and self._audit_worker.isRunning():
            CopyableMessageBox.information(self, "Reconcile", "An audit is already running.")
            return
        where = ", ".join(self._instance_label(i) for i in instance_ids)
        self._audit_status.setText(f"Re-auditing {name} on {where}…")
        self.setCursor(Qt.CursorShape.BusyCursor)
        worker = _EntityAuditWorker(self._client, eid, instance_ids)
        worker.done.connect(self._on_audit_done)
        worker.failed.connect(self._on_audit_failed)
        worker.finished.connect(worker.deleteLater)
        self._audit_worker = worker
        worker.start()

    def _on_audit_done(self, results: list) -> None:
        self.unsetCursor()
        self._audit_worker = None
        n = len(results)
        self._audit_status.setText(
            f"Re-audited on {n} instance(s); refreshing comparison…"
        )
        # Refresh the grid so the new state shows, if a comparison is loaded.
        if self._combo_a.currentData() and self._combo_b.currentData():
            self._on_compare()
        self._audit_status.setText(f"Re-audited on {n} instance(s).")

    def _on_audit_failed(self, message: str) -> None:
        self.unsetCursor()
        self._audit_worker = None
        self._audit_status.setText(f"Re-audit failed: {message}")
        CopyableMessageBox.warning(self, "Reconcile", f"Re-audit failed: {message}")

    # --------------------------------------------------------------- history
    def _load_transactions(self) -> None:
        self._log_tree.clear()
        try:
            rows = self._client.reconcile_transactions(limit=200)
        except Exception as exc:  # noqa: BLE001
            _log.warning("could not load transactions: %s", exc)
            rows = []
        for t in rows:
            direction = "Pulled to design" if t.get("direction") == "capture" else "Pushed to instance"
            item = QTreeWidgetItem([
                str(t.get("id")),
                direction,
                t.get("member_identifier", ""),
                _fmt(t.get("attribute")),
                f"{_fmt(t.get('before_value'))} → {_fmt(t.get('after_value'))}",
                t.get("status", ""),
                t.get("actor", ""),
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, t)
            self._log_tree.addTopLevelItem(item)

    def _on_rollback(self) -> None:
        items = self._log_tree.selectedItems()
        if not items:
            CopyableMessageBox.information(self, "Reconcile", "Select a change to undo first.")
            return
        txn = items[0].data(0, Qt.ItemDataRole.UserRole)
        tid = txn.get("id")
        if txn.get("status") == "rolled_back":
            CopyableMessageBox.information(self, "Reconcile", "Already undone.")
            return
        # Data-loss analysis before proceeding (REQ-361).
        try:
            verdict = self._client.reconcile_assess_revert(tid)
        except Exception as exc:  # noqa: BLE001
            verdict = {}
            _log.warning("assess-revert failed: %s", exc)
        if verdict.get("requires_confirmation"):
            reasons = "\n• ".join(verdict.get("reasons", []))
            proceed = CopyableMessageBox.warning(
                self, "Possible data loss",
                f"Undoing this change could cause data loss:\n\n• {reasons}\n\nProceed anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if proceed != QMessageBox.StandardButton.Yes:
                return
        try:
            self._client.reconcile_rollback(tid, actor=_ACTOR)
        except Exception as exc:  # noqa: BLE001
            CopyableMessageBox.warning(self, "Reconcile", f"Undo failed: {exc}")
            return
        self._load_transactions()


def _fmt(value: Any) -> str:
    """Render a transaction-log cell value compactly."""
    if value is None:
        return "—"
    return str(value)

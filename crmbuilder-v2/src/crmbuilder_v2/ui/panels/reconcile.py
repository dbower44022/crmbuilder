"""Three-way reconciliation panel — PI-319 (REL-024).

Pick two instances, compare them against the canonical design, and reconcile each
difference. The "Differences" tab shows one row per differing setting grouped by
entity (design vs instance A vs instance B); a field-attribute row can have its
value captured from either instance into the design. The "Transaction Log" tab
lists every reconcile action and offers rollback — guarded by the data-loss
analysis, which warns before a risky revert proceeds (REQ-352..361).

Reads/writes go through the synchronous :class:`StorageClient`; the calls are
fast local API requests, so no worker thread is needed.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

_log = logging.getLogger(__name__)

#: Recorded as the transaction actor for desktop-driven reconcile actions.
_ACTOR = "desktop"

_PRIMARY = (
    "QPushButton { background-color: #1565C0; color: white; border-radius: 4px; "
    "padding: 6px 14px; } QPushButton:hover { background-color: #0D47A1; }"
)
_SECONDARY = (
    "QPushButton { background-color: #FFA726; color: white; border-radius: 4px; "
    "padding: 6px 14px; } QPushButton:hover { background-color: #FB8C00; }"
)


def _fmt(value: Any) -> str:
    """Render a cell value compactly."""
    if value is None:
        return "—"
    return str(value)


class ReconcilePanel(QWidget):
    """Two-instance + design reconciliation surface."""

    def __init__(self, client: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._client = client
        self._instances: list[dict[str, Any]] = []
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
        picker.addStretch()
        outer.addLayout(picker)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_diff_tab(), "Differences")
        self._tabs.addTab(self._build_log_tab(), "Transaction Log")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        outer.addWidget(self._tabs)

    def _build_diff_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        self._tree = QTreeWidget()
        self._tree.setColumnCount(5)
        self._tree.setHeaderLabels(
            ["Member / Attribute", "Kind", "Design", "Instance A", "Instance B"]
        )
        self._tree.setObjectName("reconcile_diff_tree")
        lay.addWidget(self._tree)

        self._summary = QLabel("Pick two instances and click Compare.")
        self._summary.setStyleSheet("color: #757575;")
        lay.addWidget(self._summary)

        actions = QHBoxLayout()
        cap_a = QPushButton("Capture A → Design")
        cap_a.setStyleSheet(_SECONDARY)
        cap_a.setObjectName("reconcile_capture_a")
        cap_a.clicked.connect(lambda: self._on_capture("instance_a"))
        cap_b = QPushButton("Capture B → Design")
        cap_b.setStyleSheet(_SECONDARY)
        cap_b.setObjectName("reconcile_capture_b")
        cap_b.clicked.connect(lambda: self._on_capture("instance_b"))
        actions.addWidget(cap_a)
        actions.addWidget(cap_b)
        actions.addStretch()
        lay.addLayout(actions)
        return tab

    def _build_log_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        self._log_tree = QTreeWidget()
        self._log_tree.setColumnCount(7)
        self._log_tree.setHeaderLabels(
            ["ID", "Direction", "Member", "Attribute", "Before → After", "Status", "Actor"]
        )
        self._log_tree.setObjectName("reconcile_log_tree")
        lay.addWidget(self._log_tree)
        row = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._load_transactions)
        rollback = QPushButton("Roll Back Selected")
        rollback.setStyleSheet(_SECONDARY)
        rollback.setObjectName("reconcile_rollback")
        rollback.clicked.connect(self._on_rollback)
        row.addWidget(refresh)
        row.addWidget(rollback)
        row.addStretch()
        lay.addLayout(row)
        return tab

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

    def _on_tab_changed(self, index: int) -> None:
        if index == 1:
            self._load_transactions()

    def _on_compare(self) -> None:
        a = self._combo_a.currentData()
        b = self._combo_b.currentData()
        if not a or not b:
            QMessageBox.information(self, "Reconcile", "Select two instances first.")
            return
        if a == b:
            QMessageBox.information(self, "Reconcile", "Pick two different instances.")
            return
        try:
            result = self._client.reconcile_compare(a, b)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Reconcile", f"Compare failed: {exc}")
            return
        self._populate_tree(result)

    def _populate_tree(self, result: dict[str, Any]) -> None:
        self._tree.clear()
        groups = result.get("groups", [])
        for grp in groups:
            top = QTreeWidgetItem([grp.get("entity") or "(entity)", "", "", "", ""])
            top.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._tree.addTopLevelItem(top)
            for r in grp.get("rows", []):
                label = r.get("member_name") or r.get("member_identifier") or "?"
                if r.get("attribute"):
                    label = f"{label} . {r['attribute']}"
                leaf = QTreeWidgetItem([
                    label,
                    r.get("kind", ""),
                    _fmt(r.get("design")),
                    _fmt(r.get("instance_a")),
                    _fmt(r.get("instance_b")),
                ])
                leaf.setData(0, Qt.ItemDataRole.UserRole, r)
                top.addChild(leaf)
            top.setExpanded(True)
        self._summary.setText(
            f"{result.get('row_count', 0)} difference(s) across "
            f"{len(groups)} group(s). Select a field-attribute row, then Capture."
        )

    def _selected_row(self) -> dict[str, Any] | None:
        items = self._tree.selectedItems()
        if not items:
            return None
        return items[0].data(0, Qt.ItemDataRole.UserRole)

    def _on_capture(self, source: str) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.information(self, "Reconcile", "Select a difference row first.")
            return
        if not row.get("actionable"):
            QMessageBox.information(
                self, "Reconcile",
                "This difference is shown for visibility but cannot be reconciled "
                "from here yet (field-attribute differences are actionable).",
            )
            return
        instance = self._combo_a.currentData() if source == "instance_a" else self._combo_b.currentData()
        try:
            self._client.reconcile_capture(
                instance=instance,
                field_identifier=row["member_identifier"],
                attribute=row["attribute"],
                actor=_ACTOR,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Reconcile", f"Capture failed: {exc}")
            return
        QMessageBox.information(
            self, "Reconcile",
            f"Captured {row['attribute']} from {instance} into the design.",
        )
        self._on_compare()  # refresh

    # ------------------------------------------------------------------ log
    def _load_transactions(self) -> None:
        self._log_tree.clear()
        try:
            rows = self._client.reconcile_transactions(limit=200)
        except Exception as exc:  # noqa: BLE001
            _log.warning("could not load transactions: %s", exc)
            rows = []
        for t in rows:
            item = QTreeWidgetItem([
                str(t.get("id")),
                t.get("direction", ""),
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
            QMessageBox.information(self, "Reconcile", "Select a transaction first.")
            return
        txn = items[0].data(0, Qt.ItemDataRole.UserRole)
        tid = txn.get("id")
        if txn.get("status") == "rolled_back":
            QMessageBox.information(self, "Reconcile", "Already rolled back.")
            return
        # Data-loss analysis before proceeding (REQ-361).
        try:
            verdict = self._client.reconcile_assess_revert(tid)
        except Exception as exc:  # noqa: BLE001
            verdict = {}
            _log.warning("assess-revert failed: %s", exc)
        if verdict.get("requires_confirmation"):
            reasons = "\n• ".join(verdict.get("reasons", []))
            proceed = QMessageBox.warning(
                self, "Possible data loss",
                f"This rollback could cause data loss:\n\n• {reasons}\n\nProceed anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if proceed != QMessageBox.StandardButton.Yes:
                return
        try:
            self._client.reconcile_rollback(tid, actor=_ACTOR)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Reconcile", f"Rollback failed: {exc}")
            return
        self._load_transactions()

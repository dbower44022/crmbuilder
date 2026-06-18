"""Resource Locks panel — the file-level check-out backstop monitor (PI-225).

A master/detail browse over the ``/locks`` API (the PI-203 / PRJ-030
named-resource lock substrate, FL-1..6). Each row is a *held* lock — a named
resource (a file path, or a logical resource like ``migration-chain``) checked
out by one holder (a sub-agent). The list is the "who holds what" view; the
detail exposes the two operator escape hatches:

* **Reclaim holder's locks** (FL-6) — release *every* lock the selected
  holder holds. The owner-supervised recovery for a dead sub-agent.
* **Release this lock** — release just the selected resource's lock.

Acquire and verify are the runtime's job (agent-side), so the panel is
read-mostly with those two human actions. Both confirm first, since they
break another agent's check-out. Single-occupancy means resource names are
not release-scoped (§7.1), so one resource appears at most once.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.exceptions import (
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.panels._governance_helpers import (
    heading_label,
    read_only_line,
    separator,
)
from crmbuilder_v2.ui.widgets.datetime_format import format_timestamp
from crmbuilder_v2.ui.widgets.selectable_text import CopyableMessageBox
from crmbuilder_v2.ui.workers import run_in_thread

_log = logging.getLogger("crmbuilder_v2.ui.panels.resource_locks")

_DIM_STYLE = "color: #888;"


class ResourceLocksPanel(ListDetailPanel):
    """Master/detail monitor + reclaim/release actions for held locks (PI-225)."""

    def __init__(self, client, parent=None):
        super().__init__(client, parent)

    # ------------------------------------------------------------------
    # Master list
    # ------------------------------------------------------------------

    def entity_title(self) -> str:
        return "Resource Locks"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_locks()

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="identifier", title="Resource"),
            ColumnSpec(field="holder", title="Holder", width=200),
            ColumnSpec(field="acquired_at_display", title="Acquired", width=160),
        ]

    def _post_process_records(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        for r in records:
            # Synthetic identifier = resource name (unique among held locks),
            # so the base class's selection/search/delegate work unchanged.
            r["identifier"] = r.get("resource_name")
            r["acquired_at_display"] = format_timestamp(r.get("acquired_at"))
        return records

    # ------------------------------------------------------------------
    # Detail
    # ------------------------------------------------------------------

    def render_detail(
        self, record: dict[str, Any], extras: dict[str, Any]
    ) -> QWidget:
        resource = record.get("resource_name") or ""
        holder = record.get("holder") or ""
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        outer.addWidget(heading_label(resource))

        self._action_status = QLabel("")
        self._action_status.setObjectName("lock_action_status")
        self._action_status.setWordWrap(True)
        outer.addWidget(self._action_status)

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form.addRow("Resource", read_only_line(resource))
        form.addRow("Holder", read_only_line(holder))
        form.addRow("Acquired", read_only_line(format_timestamp(record.get("acquired_at"))))
        outer.addLayout(form)

        outer.addWidget(separator())
        note = QLabel(
            "Reclaim releases <i>every</i> lock this holder holds (FL-6 — for a "
            "dead sub-agent). Release frees just this resource. Both break the "
            "holder's check-out, so confirm first."
        )
        note.setStyleSheet(_DIM_STYLE)
        note.setWordWrap(True)
        note.setTextFormat(Qt.TextFormat.RichText)
        outer.addWidget(note)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        reclaim = QPushButton("Reclaim holder's locks")
        reclaim.setObjectName("lock_reclaim_button")
        reclaim.clicked.connect(lambda: self._do_reclaim(holder))
        actions.addWidget(reclaim)
        release = QPushButton("Release this lock")
        release.setObjectName("lock_release_button")
        release.clicked.connect(lambda: self._do_release(holder, resource))
        actions.addWidget(release)
        actions.addStretch(1)
        outer.addLayout(actions)

        outer.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        return scroll

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _do_reclaim(self, holder: str) -> None:
        if not holder:
            self._set_action_status("This lock has no holder to reclaim.")
            return
        if not self._confirm(
            "Reclaim locks",
            f"Release every lock held by {holder!r}? This is the recovery "
            "for a dead sub-agent and frees all of its checked-out resources.",
        ):
            return
        self._run(lambda: self._client.reclaim_locks(holder), label="reclaim")

    def _do_release(self, holder: str, resource: str) -> None:
        if not holder or not resource:
            self._set_action_status("Missing holder or resource.")
            return
        if not self._confirm(
            "Release lock",
            f"Release the lock on {resource!r} held by {holder!r}?",
        ):
            return
        self._run(
            lambda: self._client.release_lock(holder, resource), label="release"
        )

    def _confirm(self, title: str, text: str) -> bool:
        # CopyableMessageBox (not a raw QMessageBox) per PI-124 / WTK-145 —
        # popup text must be selectable/copyable across the v2 UI.
        reply = CopyableMessageBox.question(
            self,
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return reply == QMessageBox.StandardButton.Yes

    # ------------------------------------------------------------------
    # Worker plumbing (mirrors ReleasesPanel)
    # ------------------------------------------------------------------

    def _run(self, fn, *, label: str) -> None:
        self._set_action_status(f"{label.capitalize()}…")

        def _on_done(_result: Any) -> None:
            self._set_action_status(f"{label.capitalize()} done.")
            self.refresh()

        worker = run_in_thread(
            fn, on_success=_on_done, on_error=self._on_action_error, parent=self
        )
        self._in_flight_workers.append(worker)
        worker.finished.connect(lambda w=worker: self._drop_worker(w))

    def _on_action_error(self, exc: Exception) -> None:
        if isinstance(exc, StorageConnectionError):
            _log.warning("Connection lost during lock action: %s", exc)
            self._set_action_status("Connection lost")
            self.connection_lost.emit(str(exc))
            return
        if isinstance(exc, StorageClientError):
            self._set_action_status(f"Rejected: {exc.message}")
            return
        _log.exception("Unexpected error during lock action", exc_info=exc)
        self._set_action_status(f"Error: {exc!s}")

    def _drop_worker(self, worker: Any) -> None:
        try:
            self._in_flight_workers.remove(worker)
        except ValueError:
            pass

    def _set_action_status(self, text: str) -> None:
        status = getattr(self, "_action_status", None)
        if status is None:
            return
        try:
            status.setText(text)
        except RuntimeError:
            # Label's C++ object reclaimed (detail replaced by a refresh).
            pass

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        if not index.isValid():
            return menu
        record = self._record_at_index(index)
        if record is None:
            return menu
        copy_resource = menu.addAction("Copy Resource")
        copy_resource.triggered.connect(
            lambda _c=False, r=record: self._copy(r.get("resource_name") or "")
        )
        copy_holder = menu.addAction("Copy Holder")
        copy_holder.triggered.connect(
            lambda _c=False, r=record: self._copy(r.get("holder") or "")
        )
        return menu

    @staticmethod
    def _copy(text: str) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)

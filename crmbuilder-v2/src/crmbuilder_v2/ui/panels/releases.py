"""Releases hub panel — the multi-agent release-pipeline operability surface (PI-224).

A master/detail browse over the ``/releases`` API plus the lifecycle *writes*
the pipeline needs from the desktop. A ``release`` (``REL-``) is the staged
delivery container (PRJ-031): it walks ``preliminary_planning →
development_planning → reconciliation → architecture_planning → ready →
development → qa → testing → deployment → shipped`` (or ``cancelled`` /
``superseded``) through gated transitions.

The detail pane is a tabbed view:

* **Overview** — status, lifecycle stamps, the derived *freeze band* and
  planning *temperature*, planning-readiness, lane order/holder, and area
  ownership.
* **Composition** — the release-scoped projects → planning-items, and the
  artifact versions the release introduces.
* **Conflicts** — the reconciliation conflicts, each open one carrying a
  governed *Resolve…* action.
* **Reopens** — the in-lane area-reopens, the paused-area set, and each open
  reopen's *Refreeze* action.

The action row drives the lifecycle: **Transition…** (which performs the
*freeze* via ``development_planning → reconciliation``, plus the qa/testing/
deployment moves), **QA Pass**, **Test Pass**, **Set Lane Order…**, **Open
Correction…**, and **Reopen Area…**. Every gate is enforced server-side; a
rejected action surfaces its message inline (buttons are never disabled — the
user clicks and learns why, per the project convention).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.access.vocab import (
    RELEASE_STATUS_TRANSITIONS,
    SYSTEM_AREA_RANKS,
)
from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.exceptions import (
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.panels._governance_helpers import (
    created_updated_section,
    heading_label,
    lifecycle_timestamps_section,
    read_only_line,
    read_only_text,
    separator,
)
from crmbuilder_v2.ui.widgets.datetime_format import format_timestamp
from crmbuilder_v2.ui.widgets.selectable_text import CopyableMessageBox
from crmbuilder_v2.ui.workers import run_in_thread

_log = logging.getLogger("crmbuilder_v2.ui.panels.releases")

# The dependency-spine areas a frozen-area reopen may target (the ranked
# System areas; unranked areas have no downstream cascade — RW2). Ordered by
# rank so the dropdown reads storage → access → api → mcp → ui.
_RANKED_AREAS: list[str] = [
    a
    for a, _r in sorted(
        ((a, r) for a, r in SYSTEM_AREA_RANKS.items() if r is not None),
        key=lambda kv: (kv[1], kv[0]),
    )
]

_LIFECYCLE_TIMESTAMPS = [
    ("Frozen", "release_frozen_at"),
    ("Planned completely", "release_planned_completely_at"),
    ("QA passed", "release_qa_passed_at"),
    ("Tests passed", "release_test_passed_at"),
    ("Shipped", "release_shipped_at"),
    ("Cancelled", "release_cancelled_at"),
    ("Superseded", "release_superseded_at"),
]

# Freeze-band badge styling — neutral/open, amber/amend-window, red/locked.
_BAND_STYLE = {
    "open": "color: #0f5132; background: #d1e7dd; border-radius: 4px; padding: 2px 8px;",
    "amend_window": "color: #664d03; background: #fff3cd; border-radius: 4px; padding: 2px 8px;",
    "locked": "color: #842029; background: #f8d7da; border-radius: 4px; padding: 2px 8px;",
}
_DIM_STYLE = "color: #888;"


class ReleasesPanel(ListDetailPanel):
    """Master/detail + lifecycle-action panel for Releases (PI-224)."""

    def __init__(self, client, parent=None):
        super().__init__(client, parent)
        # Transient modal dialogs are tracked so they can be deleteLater()'d on
        # close — a sub-dialog GC'd while a worker thread is live can crash Qt.
        self._dialogs: list[QDialog] = []
        # PI-226: the panel is the human release-planning workbench. A New
        # Release button lives in the toolbar action slot; the rest of the
        # authoring (scope add/remove, edit) is in the detail pane.
        new_button = QPushButton("New Release")
        new_button.setObjectName("new_release_button")
        new_button.clicked.connect(self._on_new_release)
        self._action_layout.addWidget(new_button)

    # ------------------------------------------------------------------
    # Master list
    # ------------------------------------------------------------------

    def entity_title(self) -> str:
        return "Releases"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_releases()

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="identifier", title="Identifier", width=100),
            ColumnSpec(field="release_title", title="Title"),
            ColumnSpec(field="release_status", title="Status", width=150),
            ColumnSpec(field="lane_order_display", title="Lane", width=60),
            ColumnSpec(field="updated_at_display", title="Updated", width=140),
        ]

    def _post_process_records(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        for r in records:
            # Synthetic ``identifier`` lets the base class's selection,
            # navigation, and identifier-column delegate work unchanged.
            r["identifier"] = r.get("release_identifier")
            order = r.get("release_lane_order")
            r["lane_order_display"] = "—" if order is None else str(order)
            r["updated_at_display"] = format_timestamp(r.get("release_updated_at"))
        return records

    def _strikethrough_for_record(self, record: dict[str, Any]) -> bool:
        return record.get("release_deleted_at") is not None

    # ------------------------------------------------------------------
    # Detail extras (each fetch is independent; one failure must not blank
    # the whole pane — degrade to an inline note per section instead).
    # ------------------------------------------------------------------

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        identifier = record.get("release_identifier")
        extras: dict[str, Any] = {"errors": {}}
        if not identifier:
            return extras

        def _safe(key: str, fn) -> None:
            try:
                extras[key] = fn()
            except StorageConnectionError:
                raise  # promoted to connection_lost by the base class
            except Exception as exc:  # noqa: BLE001 — degrade per-section
                _log.warning("release detail %s failed: %s", key, exc)
                extras["errors"][key] = str(
                    getattr(exc, "message", exc)
                )

        _safe("freeze", lambda: self._client.release_freeze(identifier))
        _safe("temperature", lambda: self._client.release_temperature(identifier))
        _safe(
            "readiness",
            lambda: self._client.release_planning_readiness(identifier),
        )
        _safe("composition", lambda: self._client.release_composition(identifier))
        _safe("versions", lambda: self._client.release_versions(identifier))
        _safe(
            "conflicts",
            lambda: self._client.release_reconciliation_conflicts(identifier),
        )
        _safe("reopens", lambda: self._client.release_area_reopens(identifier))
        _safe(
            "area_ownership",
            lambda: self._client.release_area_ownership(identifier),
        )
        _safe("lane_holder", lambda: self._client.release_lane_holder())
        # PI-226: the edges touching the release, so the Composition tab can map
        # each in-scope project back to its project_belongs_to_release edge id
        # for the Remove action.
        _safe(
            "edges",
            lambda: self._client.list_references_touching("release", identifier),
        )
        return extras

    # ------------------------------------------------------------------
    # Detail render
    # ------------------------------------------------------------------

    def render_detail(
        self, record: dict[str, Any], extras: dict[str, Any]
    ) -> QWidget:
        identifier = record.get("release_identifier") or ""
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        outer.addWidget(heading_label(record.get("release_title") or identifier))

        status = record.get("release_status") or ""
        band = (extras.get("freeze") or {}).get("freeze_band")
        temp = (extras.get("temperature") or {}).get("temperature")
        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)
        badge_row.addWidget(self._badge(f"Status: {status}", None))
        if band:
            badge_row.addWidget(self._badge(f"Freeze: {band}", _BAND_STYLE.get(band)))
        if temp:
            badge_row.addWidget(self._badge(f"Temperature: {temp}", None))
        badge_row.addStretch(1)
        outer.addLayout(badge_row)

        # Inline action status (success / server-rejection messages land here).
        self._action_status = QLabel("")
        self._action_status.setWordWrap(True)
        self._action_status.setObjectName("release_action_status")
        outer.addWidget(self._action_status)

        outer.addWidget(self._action_row(record))
        outer.addWidget(separator())

        tabs = QTabWidget()
        tabs.addTab(self._overview_tab(record, extras), "Overview")
        tabs.addTab(self._composition_tab(identifier, extras), "Composition")
        tabs.addTab(self._conflicts_tab(identifier, extras), "Conflicts")
        tabs.addTab(self._reopens_tab(identifier, extras), "Reopens")
        outer.addWidget(tabs, stretch=1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        return scroll

    # ------------------------------------------------------------------
    # Action row
    # ------------------------------------------------------------------

    def _action_row(self, record: dict[str, Any]) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        ident = record.get("release_identifier") or ""
        status = record.get("release_status") or ""

        def _btn(label: str, handler) -> QPushButton:
            b = QPushButton(label)
            b.clicked.connect(handler)
            row.addWidget(b)
            return b

        _btn("Edit…", lambda: self._do_edit(record))
        _btn("Transition…", lambda: self._do_transition(ident, status))
        _btn("QA Pass", lambda: self._do_simple(self._client.release_qa_pass, ident))
        _btn(
            "Test Pass",
            lambda: self._do_simple(self._client.release_test_pass, ident),
        )
        _btn("Set Lane Order…", lambda: self._do_lane_order(record))
        _btn("Open Correction…", lambda: self._do_correction(ident))
        _btn("Reopen Area…", lambda: self._do_reopen(ident))
        row.addStretch(1)
        return widget

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------

    def _overview_tab(
        self, record: dict[str, Any], extras: dict[str, Any]
    ) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(8)

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form.addRow("Identifier", read_only_line(record.get("release_identifier") or ""))
        form.addRow("Status", read_only_line(record.get("release_status") or ""))
        order = record.get("release_lane_order")
        form.addRow("Lane order", read_only_line("—" if order is None else str(order)))
        holder = extras.get("lane_holder")
        holder_id = (
            holder.get("release_identifier") if isinstance(holder, dict) else None
        )
        form.addRow("Lane holder", self._link_or_dim("release", holder_id or "", "— (lane free)"))
        v.addLayout(form)

        v.addWidget(separator())
        v.addWidget(QLabel("<b>Planning readiness</b>"))
        v.addWidget(self._readiness_widget(extras))

        v.addWidget(separator())
        v.addWidget(QLabel("<b>Area ownership</b>"))
        v.addWidget(self._area_ownership_widget(extras))

        v.addWidget(separator())
        v.addWidget(QLabel("<b>Description</b>"))
        v.addWidget(read_only_text(record.get("release_description") or ""))

        notes = record.get("release_notes")
        if notes:
            v.addWidget(separator())
            v.addWidget(QLabel("<b>Internal notes</b>"))
            v.addWidget(read_only_text(notes))

        ts = lifecycle_timestamps_section(record, _LIFECYCLE_TIMESTAMPS)
        if ts is not None:
            v.addWidget(separator())
            v.addWidget(QLabel("<b>Lifecycle timestamps</b>"))
            v.addWidget(ts)

        v.addWidget(separator())
        v.addWidget(
            created_updated_section(
                record, "release_created_at", "release_updated_at"
            )
        )
        v.addStretch(1)
        return w

    def _readiness_widget(self, extras: dict[str, Any]) -> QWidget:
        err = extras.get("errors", {}).get("readiness")
        if err:
            return self._dim(f"Unavailable: {err}")
        r = extras.get("readiness")
        if not isinstance(r, dict):
            return self._dim("No readiness data.")
        ready = r.get("ready")
        lines = [
            f"Ready: {'yes' if ready else 'no'}",
            f"Frozen: {'yes' if r.get('frozen') else 'no'}",
            f"In-scope planning items: {len(r.get('in_scope_planning_items') or [])}",
            f"Undecomposed: {', '.join(r.get('undecomposed_planning_items') or []) or '—'}",
            f"Designs authored: {r.get('designs_authored', 0)}",
            f"Sequencing ok: {'yes' if r.get('sequencing_ok') else 'no'}",
        ]
        missing = r.get("missing")
        if missing:
            lines.append(f"Missing: {', '.join(missing)}")
        return read_only_text("\n".join(lines))

    def _area_ownership_widget(self, extras: dict[str, Any]) -> QWidget:
        err = extras.get("errors", {}).get("area_ownership")
        if err:
            return self._dim(f"Unavailable: {err}")
        owners = extras.get("area_ownership")
        if not isinstance(owners, dict) or not owners:
            return self._dim("No areas claimed.")
        lines = [f"{area}: {who}" for area, who in sorted(owners.items())]
        return read_only_text("\n".join(lines))

    def _composition_tab(self, identifier: str, extras: dict[str, Any]) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(8)

        # PI-226: scope is editable only while the release is open (pre-freeze).
        # Once frozen, the band is amend_window/locked and scope is closed (FE-3).
        band = (extras.get("freeze") or {}).get("freeze_band")
        open_for_scope = band == "open"

        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Projects &amp; planning items</b>"))
        header.addStretch(1)
        if open_for_scope:
            add_btn = QPushButton("Add project to scope…")
            add_btn.setObjectName("add_project_button")
            add_btn.clicked.connect(
                lambda: self._do_add_project(identifier, extras)
            )
            header.addWidget(add_btn)
        v.addLayout(header)
        if not open_for_scope and band:
            v.addWidget(
                self._dim("Scope is closed (release is frozen) — re-scope by "
                          "opening a correction release.")
            )

        comp_err = extras.get("errors", {}).get("composition")
        if comp_err:
            v.addWidget(self._dim(f"Unavailable: {comp_err}"))
        else:
            comp = extras.get("composition")
            projects = comp.get("projects") if isinstance(comp, dict) else None
            if not projects:
                v.addWidget(self._dim("No projects in scope."))
            else:
                for prj in projects:
                    pid = prj.get("project_identifier") or ""
                    row = QHBoxLayout()
                    row.addWidget(self._link_or_dim("project", pid, pid))
                    row.addStretch(1)
                    if open_for_scope:
                        rm = QPushButton("Remove")
                        rm.clicked.connect(
                            lambda _c=False, p=pid: self._do_remove_project(
                                identifier, p, extras
                            )
                        )
                        row.addWidget(rm)
                    v.addLayout(row)
                    pis = prj.get("planning_items") or []
                    inner = QLabel(
                        "    " + (", ".join(pis) if pis else "— no planning items")
                    )
                    inner.setStyleSheet(_DIM_STYLE)
                    inner.setTextInteractionFlags(
                        Qt.TextInteractionFlag.TextSelectableByMouse
                    )
                    v.addWidget(inner)

        v.addWidget(separator())
        v.addWidget(QLabel("<b>Artifact versions introduced</b>"))
        ver_err = extras.get("errors", {}).get("versions")
        if ver_err:
            v.addWidget(self._dim(f"Unavailable: {ver_err}"))
        else:
            versions = extras.get("versions") or []
            if not versions:
                v.addWidget(self._dim("No versions authored yet."))
            else:
                lines = [
                    f"{ver.get('artifact_type')}:{ver.get('artifact_identifier')} "
                    f"v{ver.get('version_number')}"
                    for ver in versions
                ]
                v.addWidget(read_only_text("\n".join(lines)))
        v.addStretch(1)
        return w

    def _conflicts_tab(self, identifier: str, extras: dict[str, Any]) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)
        err = extras.get("errors", {}).get("conflicts")
        if err:
            v.addWidget(self._dim(f"Unavailable: {err}"))
            v.addStretch(1)
            return w
        conflicts = extras.get("conflicts") or []
        if not conflicts:
            v.addWidget(self._dim("No reconciliation conflicts."))
            v.addStretch(1)
            return w
        for c in conflicts:
            v.addWidget(self._conflict_row(c))
            v.addWidget(separator())
        v.addStretch(1)
        return w

    def _conflict_row(self, c: dict[str, Any]) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        status = c.get("status") or ""
        text = (
            f"{c.get('artifact_type')}:{c.get('artifact_identifier')} "
            f"[{c.get('facet')}] — {c.get('conflict_type')} ({status})"
        )
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(label, stretch=1)
        if status == "open":
            btn = QPushButton("Resolve…")
            btn.clicked.connect(lambda _c=False, conf=c: self._do_resolve(conf))
            row.addWidget(btn)
        elif c.get("resolving_decision_identifier"):
            dim = QLabel(f"by {c.get('resolving_decision_identifier')}")
            dim.setStyleSheet(_DIM_STYLE)
            row.addWidget(dim)
        return w

    def _reopens_tab(self, identifier: str, extras: dict[str, Any]) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)
        err = extras.get("errors", {}).get("reopens")
        if err:
            v.addWidget(self._dim(f"Unavailable: {err}"))
            v.addStretch(1)
            return w
        data = extras.get("reopens")
        if not isinstance(data, dict):
            v.addWidget(self._dim("No reopen data."))
            v.addStretch(1)
            return w
        paused = data.get("paused_areas") or []
        paused_label = QLabel(
            "Paused areas: " + (", ".join(paused) if paused else "none")
        )
        paused_label.setStyleSheet(_DIM_STYLE)
        v.addWidget(paused_label)
        v.addWidget(separator())

        reopens = data.get("reopens") or []
        if not reopens:
            v.addWidget(self._dim("No area reopens."))
            v.addStretch(1)
            return w
        for r in reopens:
            v.addWidget(self._reopen_row(identifier, r))
            v.addWidget(separator())
        v.addStretch(1)
        return w

    def _reopen_row(self, identifier: str, r: dict[str, Any]) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        area = r.get("area") or ""
        status = r.get("status") or ""
        cascade = r.get("cascade_areas") or []
        done = r.get("revalidated_areas") or []
        text = (
            f"{area} — {status} · tier {r.get('approval_tier')} · "
            f"revalidated {len(done)}/{len(cascade)}"
        )
        if r.get("reason"):
            text += f"\n    {r.get('reason')}"
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(label, stretch=1)
        if status == "open":
            btn = QPushButton("Refreeze")
            btn.clicked.connect(
                lambda _c=False, a=area: self._do_refreeze(identifier, a)
            )
            row.addWidget(btn)
        return w

    # ------------------------------------------------------------------
    # Planning-workbench handlers (PI-226)
    # ------------------------------------------------------------------

    def _on_new_release(self) -> None:
        dialog = _ReleaseCreateDialog(parent=self)
        self._dialogs.append(dialog)
        try:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            title, description, order = dialog.values()
            body: dict[str, Any] = {
                "release_title": title,
                "release_description": description,
            }
            if order is not None:
                body["release_lane_order"] = order

            def _on_done(result: Any) -> None:
                new_id = (
                    result.get("release_identifier")
                    if isinstance(result, dict)
                    else None
                )
                self._status_label.setText(f"Created {new_id or 'release'}.")
                if new_id:
                    self._pending_select_identifier = new_id
                self.refresh()

            worker = run_in_thread(
                lambda: self._client.create_release(body),
                on_success=_on_done,
                on_error=self._on_toolbar_error,
                parent=self,
            )
            self._in_flight_workers.append(worker)
            worker.finished.connect(lambda w=worker: self._drop_worker(w))
        finally:
            self._dialogs.remove(dialog)
            dialog.deleteLater()

    def _do_edit(self, record: dict[str, Any]) -> None:
        identifier = record.get("release_identifier") or ""
        dialog = _ReleaseEditDialog(record, parent=self)
        self._exec_dialog(
            dialog,
            lambda: self._run(
                lambda: self._client.patch_release(identifier, dialog.values()),
                label="edit",
            ),
        )

    def _do_add_project(self, identifier: str, extras: dict[str, Any]) -> None:
        in_scope = {
            p.get("project_identifier")
            for p in ((extras.get("composition") or {}).get("projects") or [])
        }
        try:
            projects = [
                p
                for p in self._client.list_projects()
                if p.get("project_identifier") not in in_scope
            ]
        except StorageClientError as exc:
            self._set_action_status(f"Could not load projects: {exc.message}")
            return
        if not projects:
            self._set_action_status("No unassigned projects available to add.")
            return
        dialog = _ProjectPickerDialog(projects, parent=self)
        self._exec_dialog(
            dialog,
            lambda: self._run(
                lambda: self._client.create_reference(
                    {
                        "source_type": "project",
                        "source_id": dialog.chosen_project(),
                        "target_type": "release",
                        "target_id": identifier,
                        "relationship": "project_belongs_to_release",
                    }
                ),
                label="add project",
            ),
        )

    def _do_remove_project(
        self, identifier: str, project_id: str, extras: dict[str, Any]
    ) -> None:
        edge_id = self._scope_edge_id(extras, project_id, identifier)
        if edge_id is None:
            self._set_action_status(
                f"Could not find the scope edge for {project_id} (try Refresh)."
            )
            return
        if not self._confirm(
            "Remove from scope",
            f"Remove {project_id} from {identifier}'s scope?",
        ):
            return
        self._run(
            lambda: self._client.delete_reference(edge_id), label="remove project"
        )

    @staticmethod
    def _scope_edge_id(
        extras: dict[str, Any], project_id: str, release_id: str
    ) -> int | None:
        """The id of the project_belongs_to_release edge (project → release)."""
        edges = extras.get("edges") or {}
        for edge in edges.get("as_target") or []:
            if (
                edge.get("relationship") == "project_belongs_to_release"
                and edge.get("source_id") == project_id
                and edge.get("target_id") == release_id
            ):
                return edge.get("id")
        return None

    def _confirm(self, title: str, text: str) -> bool:
        # CopyableMessageBox (not raw QMessageBox) per the PI-124 guard.
        reply = CopyableMessageBox.question(
            self,
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _on_toolbar_error(self, exc: Exception) -> None:
        if isinstance(exc, StorageConnectionError):
            self._status_label.setText("Connection lost")
            self.connection_lost.emit(str(exc))
            return
        if isinstance(exc, StorageClientError):
            self._status_label.setText(f"Rejected: {exc.message}")
            return
        _log.exception("Unexpected error creating release", exc_info=exc)
        self._status_label.setText(f"Error: {exc!s}")

    # ------------------------------------------------------------------
    # Lifecycle-action handlers
    # ------------------------------------------------------------------

    def _do_simple(self, fn, identifier: str) -> None:
        self._run(lambda: fn(identifier), label="action")

    def _do_transition(self, identifier: str, status: str) -> None:
        next_states = sorted(RELEASE_STATUS_TRANSITIONS.get(status, frozenset()))
        if not next_states:
            self._set_action_status(f"{status!r} is terminal — no transitions.")
            return
        dialog = _TransitionDialog(status, next_states, parent=self)
        self._exec_dialog(
            dialog,
            lambda: self._run(
                lambda: self._client.transition_release(
                    identifier, dialog.chosen_status()
                ),
                label="transition",
            ),
        )

    def _do_lane_order(self, record: dict[str, Any]) -> None:
        identifier = record.get("release_identifier") or ""
        current = record.get("release_lane_order")
        dialog = _LaneOrderDialog(current, parent=self)
        self._exec_dialog(
            dialog,
            lambda: self._run(
                lambda: self._client.set_release_lane_order(
                    identifier, dialog.chosen_order()
                ),
                label="lane order",
            ),
        )

    def _do_correction(self, identifier: str) -> None:
        dialog = _CorrectionDialog(parent=self)
        self._exec_dialog(
            dialog,
            lambda: self._run(
                lambda: self._client.open_release_correction(
                    identifier,
                    title=dialog.values()[0],
                    description=dialog.values()[1],
                    notes=dialog.values()[2] or None,
                ),
                label="open correction",
            ),
        )

    def _do_reopen(self, identifier: str) -> None:
        dialog = _ReopenDialog(identifier, self._client, parent=self)
        self._exec_dialog(
            dialog,
            lambda: self._run(
                lambda: self._client.reopen_release_area(
                    identifier,
                    area=dialog.values()["area"],
                    reason=dialog.values()["reason"],
                    approval_decision_identifier=dialog.values()["decision"] or None,
                    triggering_finding_identifier=dialog.values()["finding"] or None,
                ),
                label="reopen area",
            ),
        )

    def _do_refreeze(self, identifier: str, area: str) -> None:
        self._run(
            lambda: self._client.refreeze_release_area(identifier, area),
            label="refreeze",
        )

    def _do_resolve(self, conflict: dict[str, Any]) -> None:
        dialog = _ResolveConflictDialog(conflict, parent=self)
        self._exec_dialog(
            dialog,
            lambda: self._run(
                lambda: self._client.resolve_reconciliation_conflict(
                    int(conflict.get("id")),
                    decision_identifier=dialog.values()[0],
                    resolved_value=dialog.values()[1],
                ),
                label="resolve conflict",
            ),
        )

    # ------------------------------------------------------------------
    # Worker + dialog plumbing
    # ------------------------------------------------------------------

    def _run(self, fn, *, label: str) -> None:
        self._set_action_status(f"{label.capitalize()}…")

        def _on_done(_result: Any) -> None:
            self._set_action_status(f"{label.capitalize()} done.")
            self.refresh()  # re-selects the same release → re-renders the detail

        worker = run_in_thread(
            fn, on_success=_on_done, on_error=self._on_action_error, parent=self
        )
        self._in_flight_workers.append(worker)
        worker.finished.connect(lambda w=worker: self._drop_worker(w))

    def _on_action_error(self, exc: Exception) -> None:
        if isinstance(exc, StorageConnectionError):
            _log.warning("Connection lost during release action: %s", exc)
            self._set_action_status("Connection lost")
            self.connection_lost.emit(str(exc))
            return
        if isinstance(exc, StorageClientError):
            self._set_action_status(f"Rejected: {exc.message}")
            return
        _log.exception("Unexpected error during release action", exc_info=exc)
        self._set_action_status(f"Error: {exc!s}")

    def _drop_worker(self, worker: Any) -> None:
        try:
            self._in_flight_workers.remove(worker)
        except ValueError:
            pass

    def _exec_dialog(self, dialog: QDialog, on_accept) -> None:
        self._dialogs.append(dialog)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                on_accept()
        finally:
            self._dialogs.remove(dialog)
            dialog.deleteLater()

    def _set_action_status(self, text: str) -> None:
        status = getattr(self, "_action_status", None)
        if status is None:
            return
        try:
            status.setText(text)
        except RuntimeError:
            # The label's C++ object was reclaimed (e.g. the detail pane was
            # replaced by a refresh between the action and its callback).
            pass

    # ------------------------------------------------------------------
    # Small render helpers
    # ------------------------------------------------------------------

    def _badge(self, text: str, style: str | None) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            style
            or "color: #1b1b1b; background: #e9ecef; border-radius: 4px; padding: 2px 8px;"
        )
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    def _dim(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(_DIM_STYLE)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    def _link_or_dim(self, entity_type: str, identifier: str, empty_text: str) -> QLabel:
        if identifier:
            label = QLabel(f'<a href="{entity_type}:{identifier}">{identifier}</a>')
            label.setTextFormat(Qt.TextFormat.RichText)
            label.linkActivated.connect(self._emit_link_navigation)
        else:
            label = QLabel(empty_text or "—")
            label.setStyleSheet(_DIM_STYLE)
            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
        return label

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
        copy_id = menu.addAction("Copy Identifier")
        copy_id.triggered.connect(
            lambda _c=False, r=record: self._copy(r.get("release_identifier") or "")
        )
        return menu

    @staticmethod
    def _copy(text: str) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)


# ---------------------------------------------------------------------------
# Planning dialogs (PI-226)
# ---------------------------------------------------------------------------


class _ReleaseCreateDialog(QDialog):
    """Create a new release — the start of human release planning."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New release")
        layout = QVBoxLayout(self)
        self._title = QLineEdit()
        self._description = QPlainTextEdit()
        self._description.setMinimumHeight(80)
        self._order = QSpinBox()
        self._order.setRange(-1, 9999)
        self._order.setSpecialValueText("— (none)")
        self._order.setValue(-1)
        form = QFormLayout()
        form.addRow("Title", self._title)
        form.addRow("Description", self._description)
        form.addRow("Lane order", self._order)
        layout.addLayout(form)
        self._error = QLabel("")
        self._error.setStyleSheet("color: #842029;")
        layout.addWidget(self._error)
        layout.addWidget(_button_box(self, accept=self._validate))

    def _validate(self) -> None:
        if not self._title.text().strip():
            self._error.setText("A title is required.")
            return
        if not self._description.toPlainText().strip():
            self._error.setText("A description is required.")
            return
        self.accept()

    def values(self) -> tuple[str, str, int | None]:
        order = self._order.value()
        return (
            self._title.text().strip(),
            self._description.toPlainText().strip(),
            None if order < 0 else order,
        )


class _ReleaseEditDialog(QDialog):
    """Edit a release's title / description / notes while it is open."""

    def __init__(self, record: dict[str, Any], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit release")
        layout = QVBoxLayout(self)
        self._title = QLineEdit(record.get("release_title") or "")
        self._description = QPlainTextEdit(record.get("release_description") or "")
        self._description.setMinimumHeight(80)
        self._notes = QPlainTextEdit(record.get("release_notes") or "")
        self._notes.setMinimumHeight(60)
        form = QFormLayout()
        form.addRow("Title", self._title)
        form.addRow("Description", self._description)
        form.addRow("Notes", self._notes)
        layout.addLayout(form)
        layout.addWidget(_button_box(self))

    def values(self) -> dict[str, Any]:
        return {
            "release_title": self._title.text().strip(),
            "release_description": self._description.toPlainText().strip(),
            "release_notes": self._notes.toPlainText().strip() or None,
        }


class _ProjectPickerDialog(QDialog):
    """Pick an unassigned project to add to the release's scope."""

    def __init__(self, projects: list[dict[str, Any]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add project to scope")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Project (only those not yet in a release):"))
        self._combo = QComboBox()
        for p in projects:
            pid = p.get("project_identifier") or ""
            name = p.get("project_name") or ""
            self._combo.addItem(f"{pid} — {name}" if name else pid, pid)
        layout.addWidget(self._combo)
        layout.addWidget(_button_box(self))

    def chosen_project(self) -> str:
        return self._combo.currentData()


# ---------------------------------------------------------------------------
# Action dialogs
# ---------------------------------------------------------------------------


class _TransitionDialog(QDialog):
    """Pick a legal next status (the freeze is the dev_planning→reconciliation move)."""

    def __init__(self, current: str, next_states: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Transition release")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Current status: {current}"))
        self._combo = QComboBox()
        self._combo.addItems(next_states)
        form = QFormLayout()
        form.addRow("To status", self._combo)
        layout.addLayout(form)
        layout.addWidget(_button_box(self))

    def chosen_status(self) -> str:
        return self._combo.currentText()


class _LaneOrderDialog(QDialog):
    """Set (or clear) the integer lane order."""

    def __init__(self, current: int | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set lane order")
        layout = QVBoxLayout(self)
        self._spin = QSpinBox()
        self._spin.setRange(-1, 9999)
        self._spin.setSpecialValueText("— (clear)")
        self._spin.setValue(current if current is not None else -1)
        form = QFormLayout()
        form.addRow("Lane order", self._spin)
        layout.addLayout(form)
        hint = QLabel("Set to “— (clear)” to remove the lane order.")
        hint.setStyleSheet(_DIM_STYLE)
        layout.addWidget(hint)
        layout.addWidget(_button_box(self))

    def chosen_order(self) -> int | None:
        value = self._spin.value()
        return None if value < 0 else value


class _CorrectionDialog(QDialog):
    """Open a correcting release for a frozen prior (RW1 / PI-211)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Open correction release")
        layout = QVBoxLayout(self)
        self._title = QLineEdit()
        self._description = QPlainTextEdit()
        self._description.setMinimumHeight(80)
        self._notes = QPlainTextEdit()
        self._notes.setMinimumHeight(60)
        form = QFormLayout()
        form.addRow("Title", self._title)
        form.addRow("Description", self._description)
        form.addRow("Notes (optional)", self._notes)
        layout.addLayout(form)
        layout.addWidget(_button_box(self))

    def values(self) -> tuple[str, str, str]:
        return (
            self._title.text().strip(),
            self._description.toPlainText().strip(),
            self._notes.toPlainText().strip(),
        )


class _ReopenDialog(QDialog):
    """Reopen a frozen spine area in-lane, previewing the blast-radius tier (RW2/RW5)."""

    def __init__(self, identifier: str, client, parent=None):
        super().__init__(parent)
        self._identifier = identifier
        self._client = client
        self.setWindowTitle("Reopen frozen area")
        layout = QVBoxLayout(self)
        self._area = QComboBox()
        self._area.addItems(_RANKED_AREAS)
        self._area.currentTextChanged.connect(self._refresh_impact)
        self._reason = QPlainTextEdit()
        self._reason.setMinimumHeight(60)
        self._decision = QLineEdit()
        self._decision.setPlaceholderText("DEC-NNN (required above tier lead_auto)")
        self._finding = QLineEdit()
        self._finding.setPlaceholderText("FND-NNN (optional)")
        form = QFormLayout()
        form.addRow("Area", self._area)
        form.addRow("Reason", self._reason)
        form.addRow("Approval decision", self._decision)
        form.addRow("Triggering finding", self._finding)
        layout.addLayout(form)
        self._impact = QLabel("")
        self._impact.setStyleSheet(_DIM_STYLE)
        self._impact.setWordWrap(True)
        layout.addWidget(self._impact)
        layout.addWidget(_button_box(self))
        self._refresh_impact()

    def _refresh_impact(self) -> None:
        area = self._area.currentText()
        try:
            impact = self._client.release_reopen_impact(self._identifier, area)
        except Exception as exc:  # noqa: BLE001 — preview only
            self._impact.setText(f"Impact unavailable: {exc}")
            return
        downstream = impact.get("downstream_areas") or []
        self._impact.setText(
            f"Blast radius: {len(downstream)} downstream "
            f"({', '.join(downstream) or 'none'}) · tier "
            f"{impact.get('tier')}{' · repeat' if impact.get('is_repeat') else ''}"
        )

    def values(self) -> dict[str, str]:
        return {
            "area": self._area.currentText(),
            "reason": self._reason.toPlainText().strip(),
            "decision": self._decision.text().strip(),
            "finding": self._finding.text().strip(),
        }


class _ResolveConflictDialog(QDialog):
    """Resolve a reconciliation conflict by a governed decision (RC-4)."""

    def __init__(self, conflict: dict[str, Any], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resolve reconciliation conflict")
        layout = QVBoxLayout(self)
        summary = QLabel(
            f"{conflict.get('artifact_type')}:{conflict.get('artifact_identifier')} "
            f"[{conflict.get('facet')}] — {conflict.get('conflict_type')}"
        )
        summary.setWordWrap(True)
        layout.addWidget(summary)
        self._decision = QLineEdit()
        self._decision.setPlaceholderText("DEC-NNN")
        self._value = QPlainTextEdit()
        self._value.setMinimumHeight(60)
        self._value.setPlaceholderText(
            'Resolved value as JSON, e.g. {"value": true} or {"remove": true} '
            "(blank = leave merged)"
        )
        form = QFormLayout()
        form.addRow("Decision", self._decision)
        form.addRow("Resolved value", self._value)
        layout.addLayout(form)
        self._error = QLabel("")
        self._error.setStyleSheet("color: #842029;")
        layout.addWidget(self._error)
        layout.addWidget(_button_box(self, accept=self._validate))

    def _validate(self) -> None:
        if not self._decision.text().strip():
            self._error.setText("A decision identifier is required.")
            return
        raw = self._value.toPlainText().strip()
        if raw:
            try:
                json.loads(raw)
            except ValueError as exc:
                self._error.setText(f"Invalid JSON: {exc}")
                return
        self.accept()

    def values(self) -> tuple[str, Any | None]:
        raw = self._value.toPlainText().strip()
        return (
            self._decision.text().strip(),
            json.loads(raw) if raw else None,
        )


def _button_box(dialog: QDialog, accept=None) -> QDialogButtonBox:
    box = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    box.accepted.connect(accept if accept is not None else dialog.accept)
    box.rejected.connect(dialog.reject)
    return box

"""Deploy History panel — PI-419 (REQ-522, DEC-945).

Read-only master/detail over the ``/deploy-runs`` API: every provisioning run
the service has executed or is executing for this engagement, with its status
and current phase, the server and DNS record it created, the verification
results, the error that stopped it, and its log. From here an administrator
reopens a running run's progress window, retries a failed one (it resumes at
the phase that did not finish), and copies the server id of a failed run that
still exists and needs cleaning up. Runs are written only by the deploy
worker, so there is no Create/Edit/Delete.
"""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import QModelIndex
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.access.vocab import DEPLOY_RUN_PHASE_ORDER
from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.dialogs.deploy_progress_dialog import (
    PHASE_LABELS,
    DeployProgressDialog,
    describe_run,
)
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.exceptions import StorageClientError
from crmbuilder_v2.ui.panels._governance_helpers import (
    created_updated_section,
    heading_label,
    read_only_line,
    read_only_text,
    separator,
)
from crmbuilder_v2.ui.widgets.datetime_format import format_timestamp
from crmbuilder_v2.ui.widgets.form_helpers import primary_button

_STATUS_BADGE = {
    "queued": "⏳ queued",
    "running": "▶ running",
    "succeeded": "✓ succeeded",
    "succeeded_with_issues": "⚠ succeeded (issues)",
    "failed": "✗ failed",
    "cancelled": "■ cancelled",
}


def _phase_display(record: dict[str, Any]) -> str:
    phase = record.get("deploy_run_phase")
    return PHASE_LABELS.get(phase, phase or "—")


def _phase_table(state: dict[str, Any]) -> str:
    phases = state.get("phases") or {}
    lines = []
    for name in DEPLOY_RUN_PHASE_ORDER:
        entry = phases.get(name) or {}
        status = entry.get("status") or "—"
        line = f"{PHASE_LABELS.get(name, name):<22} {status}"
        if entry.get("error"):
            line += f"  ({entry['error']})"
        lines.append(line)
    return "\n".join(lines)


def _kept_line(record: dict[str, Any]) -> str | None:
    """For a failed / cancelled run, what still exists and bills."""
    if record.get("deploy_run_status") not in ("failed", "cancelled"):
        return None
    state = record.get("deploy_run_state") or {}
    parts = []
    if state.get("droplet_id"):
        parts.append(
            f"server {state['droplet_id']}"
            + (f" at {state['droplet_ip']}" if state.get("droplet_ip") else "")
        )
    if state.get("dns_record_id"):
        parts.append(f"DNS record {(record.get('deploy_run_spec') or {}).get('domain', '')}")
    if not parts:
        return None
    return (
        "Still exists (not destroyed): " + ", ".join(parts)
        + ". Retry to resume, or remove it in the provider console."
    )


class DeployHistoryPanel(ListDetailPanel):
    """Browse deploy runs; reopen progress, retry, copy the server id."""

    def entity_title(self) -> str:
        return "Deploy History"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_deploy_runs()

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="deploy_run_identifier", title="Identifier", width=100),
            ColumnSpec(field="status_display", title="Status", width=150),
            ColumnSpec(field="phase_display", title="Phase", width=150),
            ColumnSpec(field="domain_display", title="Address", width=200),
            ColumnSpec(field="instance_identifier", title="Instance", width=100),
            ColumnSpec(field="started_display", title="Started", width=150),
        ]

    def _post_process_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for r in records:
            status = r.get("deploy_run_status") or ""
            r["status_display"] = _STATUS_BADGE.get(status, status)
            r["phase_display"] = _phase_display(r)
            r["domain_display"] = (r.get("deploy_run_spec") or {}).get("domain", "")
            r["started_display"] = format_timestamp(r.get("deploy_run_started_at"))
        return records

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        """The list omits the log; fetch the full run for the detail pane."""
        identifier = record.get("deploy_run_identifier")
        if not identifier:
            return {}
        try:
            return {"full": self._client.get_deploy_run(identifier)}
        except StorageClientError:
            return {}

    def render_detail(self, record: dict[str, Any], extras: dict[str, Any]) -> QWidget:
        full = extras.get("full") or record
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        identifier = full.get("deploy_run_identifier") or ""
        status = full.get("deploy_run_status") or ""
        spec = full.get("deploy_run_spec") or {}
        state = full.get("deploy_run_state") or {}

        strip = QWidget()
        strip_layout = QHBoxLayout(strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        if status in ("queued", "running"):
            follow = primary_button("Open progress…")
            follow.setObjectName("deploy_open_progress_button")
            follow.clicked.connect(lambda _c=False, i=identifier: self._open_progress(i))
            strip_layout.addWidget(follow)
        if status in ("failed", "cancelled"):
            retry = primary_button("Retry")
            retry.setObjectName("deploy_retry_button")
            retry.clicked.connect(lambda _c=False, i=identifier: self._retry(i))
            strip_layout.addWidget(retry)
        if state.get("droplet_id"):
            copy_btn = QPushButton("Copy server id")
            copy_btn.setObjectName("deploy_copy_droplet_button")
            copy_btn.clicked.connect(lambda _c=False, d=str(state["droplet_id"]): self._copy(d))
            strip_layout.addWidget(copy_btn)
        strip_layout.addStretch(1)
        outer.addWidget(strip)

        outer.addWidget(heading_label(f"{identifier} — {spec.get('domain', '')}"))
        kept = _kept_line(full)
        if kept:
            warn = QLabel(kept)
            warn.setObjectName("deploy_kept_label")
            warn.setWordWrap(True)
            warn.setStyleSheet("color: #b9770e; font-weight: 600;")
            outer.addWidget(warn)

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.addRow("Status", read_only_line(describe_run(full)))
        form.addRow("Instance", read_only_line(full.get("instance_identifier") or "—"))
        form.addRow("Address", read_only_line(f"https://{spec.get('domain', '')}" if spec.get("domain") else "—"))
        form.addRow("Server", read_only_line(
            f"{spec.get('size', '')} in {spec.get('region', '')} ({spec.get('image', '')})"
        ))
        form.addRow("Server id / IP", read_only_line(
            " / ".join(str(v) for v in (state.get("droplet_id"), state.get("droplet_ip")) if v) or "—"
        ))
        # PI-442 (REQ-544): the history row names its hosting provider.
        form.addRow("Provider", read_only_line(full.get("deploy_run_provider") or "—"))
        form.addRow("Certificate expires", read_only_line(state.get("cert_expiry") or "—"))
        form.addRow("Requested by", read_only_line(full.get("deploy_run_requested_by") or "—"))
        form.addRow("Worker", read_only_line(full.get("deploy_run_worker_id") or "—"))
        form.addRow("Started", read_only_line(format_timestamp(full.get("deploy_run_started_at")) or "—"))
        form.addRow("Finished", read_only_line(format_timestamp(full.get("deploy_run_ended_at")) or "—"))
        outer.addLayout(form)

        if full.get("deploy_run_error"):
            outer.addWidget(separator())
            outer.addWidget(QLabel("<b>Error</b>"))
            outer.addWidget(read_only_text(full["deploy_run_error"]))

        outer.addWidget(separator())
        outer.addWidget(QLabel("<b>Phases</b>"))
        outer.addWidget(read_only_text(_phase_table(state)))

        checks = state.get("verify_checks")
        if checks:
            outer.addWidget(separator())
            outer.addWidget(QLabel("<b>Verification</b>"))
            outer.addWidget(read_only_text("\n".join(
                f"{'✓' if c.get('passed') else '✗'} {c.get('check')}"
                + (f" — {c['detail']}" if c.get("detail") else "")
                for c in checks
            )))

        log = full.get("deploy_run_log") or []
        outer.addWidget(separator())
        outer.addWidget(QLabel(f"<b>Log</b> — {len(log)} line(s)"))
        outer.addWidget(read_only_text("\n".join(
            f"{e[0][11:19] if isinstance(e[0], str) else ''} [{e[1]}] {e[2]}" for e in log[-400:]
        ) or "—"))

        outer.addWidget(separator())
        outer.addWidget(QLabel("<b>Request</b>"))
        outer.addWidget(read_only_text(_pretty(spec)))
        outer.addWidget(separator())
        outer.addWidget(created_updated_section(full, "created_at", "updated_at"))
        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

    # -- actions --------------------------------------------------------------

    def _open_progress(self, identifier: str) -> None:
        dialog = DeployProgressDialog(self._client, identifier, parent=self)
        dialog.connection_lost.connect(self.connection_lost)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()
        self.refresh()

    def _retry(self, identifier: str) -> None:
        try:
            self._client.retry_deploy_run(identifier)
        except StorageClientError as exc:
            ErrorDialog(title="Retry failed", message=str(exc), parent=self).exec()
            return
        self._open_progress(identifier)

    # -- identifier override + context menu ---------------------------------------

    def _select_by_identifier(self, identifier: str) -> bool:
        for row, record in enumerate(self._records):
            if record.get("deploy_run_identifier") == identifier:
                self._select_row(row)
                return True
        return False

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        if not index.isValid():
            return menu
        record = self._record_at_index(index)
        if record is None:
            return menu
        copy_id = menu.addAction("Copy Identifier")
        copy_id.triggered.connect(
            lambda _c=False, r=record: self._copy(r.get("deploy_run_identifier") or "")
        )
        droplet = (record.get("deploy_run_state") or {}).get("droplet_id")
        if droplet:
            copy_srv = menu.addAction("Copy server id")
            copy_srv.triggered.connect(lambda _c=False, d=str(droplet): self._copy(d))
        if record.get("deploy_run_status") in ("failed", "cancelled"):
            retry = menu.addAction("Retry")
            retry.triggered.connect(
                lambda _c=False, r=record: self._retry(r.get("deploy_run_identifier") or "")
            )
        return menu

    @staticmethod
    def _copy(text: str) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)


def _pretty(value: Any) -> str:
    try:
        return json.dumps(value, indent=2, default=str, sort_keys=True)
    except (TypeError, ValueError):
        return str(value)

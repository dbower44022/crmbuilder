"""Instances panel — CRM-connection entity (PI-186 / PRJ-027).

A ``ListDetailPanel`` for the ``instance`` entity, registered under the
Governance sidebar group. An engagement defines one or more instances, each a
connection to a live CRM system; audit (pull) reads structure into the canonical
inventory and publish (push, PRJ-025) writes design to a target instance.

The detail pane never shows a secret value — only whether one is configured
(REQ-157). Editing and secret entry go through the dialogs. Default sort is
identifier-ascending.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.dialogs.audit_progress_dialog import AuditProgressDialog
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.dialogs.instance_crud import (
    InstanceCreateDialog,
    InstanceDeleteDialog,
    InstanceEditDialog,
)
from crmbuilder_v2.ui.dialogs.publish_dialog import PublishDialog
from crmbuilder_v2.ui.exceptions import (
    NotFoundError,
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.panels._governance_helpers import created_updated_section
from crmbuilder_v2.ui.widgets.datetime_format import format_timestamp
from crmbuilder_v2.ui.widgets.form_helpers import (
    CollapsibleSection,
    destructive_button,
    primary_button,
    required_label,
)
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection
from crmbuilder_v2.ui.widgets.selectable_text import CopyableMessageBox

_log = logging.getLogger("crmbuilder_v2.ui.panels.instances")

_LONG_TEXT_MIN_HEIGHT = 80
_READ_ONLY_STYLE = "color: #444; background: #f4f4f4;"


def _heading_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setWordWrap(True)
    font = QFont(label.font())
    font.setBold(True)
    font.setPointSize(font.pointSize() + 2)
    label.setFont(font)
    return label


def _read_only_line(value: str) -> QLineEdit:
    widget = QLineEdit()
    widget.setText(value or "")
    widget.setReadOnly(True)
    widget.setStyleSheet(_READ_ONLY_STYLE)
    return widget


def _read_only_text(value: str) -> QPlainTextEdit:
    widget = QPlainTextEdit()
    widget.setPlainText(value or "")
    widget.setReadOnly(True)
    widget.setStyleSheet(_READ_ONLY_STYLE)
    widget.setMinimumHeight(_LONG_TEXT_MIN_HEIGHT)
    return widget


def _separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


class InstancesPanel(ListDetailPanel):
    """Instances panel with read + write surfaces (PI-186)."""

    def __init__(self, client, parent=None):
        self._include_deleted = False
        super().__init__(client, parent)
        self._show_deleted_check = QCheckBox("Show deleted")
        self._show_deleted_check.setObjectName("show_deleted_check")
        self._show_deleted_check.toggled.connect(self._on_show_deleted_toggled)
        self._action_layout.addWidget(self._show_deleted_check)
        self._new_button = primary_button("New Instance")
        self._new_button.setObjectName("new_instance_button")
        self._new_button.clicked.connect(self._on_new_clicked)
        self._action_layout.addWidget(self._new_button)

    # ------------------------------------------------------------------
    # ListDetailPanel hooks
    # ------------------------------------------------------------------

    def entity_title(self) -> str:
        return "Instances"

    def fetch_records(self) -> list[dict[str, Any]]:
        records = self._client.list_instances(
            include_deleted=self._include_deleted
        )
        for r in records:
            r["created_at_display"] = format_timestamp(
                r.get("instance_created_at")
            )
        return records

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="instance_identifier", title="Identifier", width=110),
            ColumnSpec(field="instance_name", title="Name"),
            ColumnSpec(field="instance_vendor", title="CRM", width=90),
            ColumnSpec(field="instance_role", title="Role", width=80),
            ColumnSpec(field="instance_status", title="Status", width=90),
            ColumnSpec(field="created_at_display", title="Created", width=140),
        ]

    def _strikethrough_for_record(self, record: dict[str, Any]) -> bool:
        return record.get("instance_deleted_at") is not None

    def _on_show_deleted_toggled(self, checked: bool) -> None:
        self._include_deleted = checked
        self.refresh()

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        identifier = record.get("instance_identifier")
        if not identifier:
            return {"references": {"as_source": [], "as_target": []}}
        extras: dict[str, Any] = {
            "references": self._client.list_references_touching(
                "instance", identifier
            ),
        }
        # PI-188 inventory/drift surface: membership counts + publish-plan size.
        # Reads degrade gracefully so a transient error never blanks the detail.
        try:
            extras["membership_summary"] = self._client.get_membership_summary(
                identifier
            )
            extras["publish_plan"] = self._client.get_publish_plan(identifier)
        except StorageClientError as exc:
            _log.warning("inventory read failed for %s: %s", identifier, exc)
            extras["membership_summary"] = {}
            extras["publish_plan"] = {"item_count": 0}
        # PI-201 (REQ-172): the deploy/provisioning config, if the instance has one.
        try:
            extras["deploy_config"] = self._client.get_deploy_config(identifier)
        except StorageClientError as exc:
            _log.warning("deploy-config read failed for %s: %s", identifier, exc)
            extras["deploy_config"] = None
        return extras

    def render_detail(
        self, record: dict[str, Any], extras: dict[str, Any]
    ) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        identifier = record.get("instance_identifier") or ""
        is_deleted = record.get("instance_deleted_at") is not None

        # Action strip.
        button_strip = QWidget()
        strip_layout = QHBoxLayout(button_strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(6)
        if is_deleted:
            restore_btn = QPushButton("Restore")
            restore_btn.setObjectName("restore_instance_button")
            restore_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_restore_clicked(r)
            )
            strip_layout.addWidget(restore_btn)
        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("edit_instance_button")
        edit_btn.clicked.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )
        strip_layout.addWidget(edit_btn)
        # Audit (pull) — offered on any non-deleted instance (REQ-430). The entry
        # point is never hidden by role: a target-only instance gets a clear,
        # actionable refusal from the server on click ("set its role to source or
        # both") rather than no button at all (the no-hidden-buttons rule).
        if not is_deleted:
            audit_btn = QPushButton("Audit now")
            audit_btn.setObjectName("audit_instance_button")
            audit_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_audit_clicked(r)
            )
            strip_layout.addWidget(audit_btn)
        # Publish (push) — available for target/both instances that aren't deleted.
        if not is_deleted and record.get("instance_role") != "source":
            publish_btn = QPushButton("Publish…")
            publish_btn.setObjectName("publish_instance_button")
            publish_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_publish_clicked(r)
            )
            strip_layout.addWidget(publish_btn)
        if not is_deleted:
            delete_btn = destructive_button("Delete")
            delete_btn.setObjectName("delete_instance_button")
            delete_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_delete_clicked(r)
            )
            strip_layout.addWidget(delete_btn)
        strip_layout.addStretch(1)
        outer.addWidget(button_strip)

        outer.addWidget(_heading_label(record.get("instance_name") or "(unnamed)"))

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        identifier_label = QLabel(identifier or "—")
        identifier_label.setObjectName("instance_identifier_value")
        identifier_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        form.addRow("Identifier", identifier_label)

        name_value = _read_only_line(record.get("instance_name") or "")
        name_value.setObjectName("instance_name_value")
        form.addRow(required_label("Name"), name_value)

        url_value = _read_only_line(record.get("instance_url") or "")
        url_value.setObjectName("instance_url_value")
        form.addRow(required_label("URL"), url_value)

        vendor_value = _read_only_line(record.get("instance_vendor") or "")
        vendor_value.setObjectName("instance_vendor_value")
        form.addRow("CRM system", vendor_value)

        role_value = _read_only_line(record.get("instance_role") or "")
        role_value.setObjectName("instance_role_value")
        form.addRow("Role", role_value)

        auth_value = _read_only_line(record.get("instance_auth_method") or "")
        auth_value.setObjectName("instance_auth_method_value")
        form.addRow("Auth method", auth_value)

        # Secret presence only — never the value or the opaque ref (REQ-157).
        has_secret = bool(record.get("instance_secret_ref"))
        secret_value = _read_only_line("configured" if has_secret else "none")
        secret_value.setObjectName("instance_secret_state_value")
        form.addRow("Secret", secret_value)

        status_value = _read_only_line(record.get("instance_status") or "")
        status_value.setObjectName("instance_status_value")
        form.addRow(required_label("Status"), status_value)
        outer.addLayout(form)

        notes_value = _read_only_text(record.get("instance_notes") or "")
        notes_value.setObjectName("instance_notes_value")
        notes_section = CollapsibleSection(
            "Internal notes", notes_value, expanded=False
        )
        notes_section.setObjectName("instance_notes_toggle")
        outer.addWidget(notes_section)

        # PI-188: inventory / drift summary for this instance.
        outer.addWidget(_separator())
        outer.addWidget(self._membership_section(extras))

        # PI-201 (REQ-172): deploy/provisioning config, if present.
        outer.addWidget(_separator())
        outer.addWidget(self._deploy_config_section(extras))

        outer.addWidget(_separator())
        outer.addWidget(
            created_updated_section(
                record, "instance_created_at", "instance_updated_at"
            )
        )

        outer.addWidget(_separator())
        references_section = ReferencesSection(
            "instance",
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

    def _deploy_config_section(self, extras: dict[str, Any]) -> QWidget:
        """Read-only deploy/provisioning config block (PI-201 / REQ-172)."""
        cfg = extras.get("deploy_config")
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(_heading_label("Deploy config"))
        if not cfg:
            lay.addWidget(QLabel(
                "No deploy/provisioning config recorded for this instance."
            ))
            return box
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)

        def _row(label: str, value: Any) -> None:
            v = QLabel(str(value) if value not in (None, "") else "—")
            v.setWordWrap(True)
            form.addRow(QLabel(label), v)

        _row("Scenario", cfg.get("scenario"))
        _row("SSH", "{}@{}:{}".format(
            cfg.get("ssh_username") or "?", cfg.get("ssh_host") or "?",
            cfg.get("ssh_port") or 22))
        _row("SSH auth", cfg.get("ssh_auth_type"))
        _row("Domain", cfg.get("domain"))
        _row("Let's Encrypt email", cfg.get("letsencrypt_email"))
        # Secrets are never shown — only whether one is set.
        _row("DB root password", "set" if cfg.get("db_root_password_ref") else "—")
        _row("Current version", cfg.get("current_espocrm_version"))
        _row("Latest version", cfg.get("latest_espocrm_version"))
        _row("Cert expiry", cfg.get("cert_expiry_date"))
        _row("Backups enabled", cfg.get("backups_enabled"))
        _row("Droplet id", cfg.get("droplet_id"))
        lay.addLayout(form)
        return box

    # ------------------------------------------------------------------
    # Identifier addressing
    # ------------------------------------------------------------------

    def _select_by_identifier(self, identifier: str) -> bool:
        for row, record in enumerate(self._records):
            if record.get("instance_identifier") == identifier:
                self._select_row(row)
                return True
        return False

    def _currently_selected_identifier(self) -> str | None:
        master = getattr(self, "_master_view", None)
        if master is None:
            return None
        sel_model = master.selectionModel()
        if sel_model is None:
            return None
        index = sel_model.currentIndex()
        if not index.isValid():
            return None
        row = index.row()
        if 0 <= row < len(self._records):
            ident = self._records[row].get("instance_identifier")
            if isinstance(ident, str):
                return ident
        return None

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        new_action = menu.addAction("New instance")
        new_action.triggered.connect(self._on_new_clicked)
        if not index.isValid():
            return menu
        record = self._record_at_index(index)
        if record is None:
            return menu
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )
        if record.get("instance_deleted_at") is not None:
            restore_action = menu.addAction("Restore")
            restore_action.triggered.connect(
                lambda _checked=False, r=record: self._on_restore_clicked(r)
            )
        else:
            delete_action = menu.addAction("Delete")
            delete_action.triggered.connect(
                lambda _checked=False, r=record: self._on_delete_clicked(r)
            )
        return menu

    # ------------------------------------------------------------------
    # Write-surface click handlers
    # ------------------------------------------------------------------

    def _on_new_clicked(self) -> None:
        dialog = InstanceCreateDialog(self._client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_id = dialog.created_identifier()
            if new_id:
                self.select_record_by_identifier(new_id)
            else:
                self.refresh()

    def _membership_section(self, extras: dict[str, Any]) -> QWidget:
        """Render the inventory/drift summary + publish-plan size (PI-188)."""
        summary = extras.get("membership_summary") or {}
        plan = extras.get("publish_plan") or {}
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(_heading_label("Inventory & drift"))
        if not summary:
            empty = QLabel(
                'No audit yet — click "Audit now" to reconcile this '
                "instance into the canonical inventory."
            )
            empty.setObjectName("membership_empty")
            empty.setWordWrap(True)
            lay.addWidget(empty)
        else:
            for member_type in sorted(summary):
                counts = summary[member_type]
                lbl = QLabel(
                    f"{member_type}: {counts.get('present', 0)} present, "
                    f"{counts.get('drifted', 0)} drifted, "
                    f"{counts.get('absent', 0)} absent"
                )
                lbl.setObjectName(f"membership_summary_{member_type}")
                lay.addWidget(lbl)
        plan_lbl = QLabel(
            f"Publish plan: {plan.get('item_count', 0)} object(s) to push to "
            "bring a target in line with the canonical design."
        )
        plan_lbl.setObjectName("publish_plan_count")
        plan_lbl.setWordWrap(True)
        lay.addWidget(plan_lbl)
        return box

    def _on_audit_clicked(self, record: dict[str, Any]) -> None:
        if not record.get("instance_identifier"):
            return
        # Live per-area progress (PI-274): the dialog drives the reconcile areas
        # one at a time and streams progress, instead of one blocking request.
        dialog = AuditProgressDialog(self._client, record, parent=self)
        dialog.connection_lost.connect(self.connection_lost)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()
        self.refresh()

    def _on_publish_clicked(self, record: dict[str, Any]) -> None:
        if not record.get("instance_identifier"):
            return
        dialog = PublishDialog(self._client, record, parent=self)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()
        self.refresh()

    def _on_edit_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("instance_identifier")
        if not identifier:
            return
        try:
            fresh = self._client.get_instance(identifier)
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
                title="Could not load instance",
                message="Could not load the latest version of this instance.",
                detail=str(exc),
                parent=self,
            ).exec()
            return

        dialog = InstanceEditDialog(self._client, fresh, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("instance_identifier") or ""
        name = record.get("instance_name") or ""
        if not identifier:
            return
        dialog = InstanceDeleteDialog(self._client, identifier, name, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_restore_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("instance_identifier") or ""
        name = record.get("instance_name") or ""
        if not identifier:
            return
        confirm = CopyableMessageBox(self)
        confirm.setWindowTitle("Restore instance")
        confirm.setText(
            f"Restore {identifier} — {name or '(unnamed)'}?\n\n"
            "It will reappear in the default Instances list."
        )
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        confirm.setDefaultButton(QMessageBox.StandardButton.No)
        if confirm.exec() != QMessageBox.StandardButton.Yes:
            return
        try:
            self._client.restore_instance(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            _log.warning("Connection lost restoring %s: %s", identifier, exc)
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            _log.warning("Domain error restoring %s: %s", identifier, exc)
            ErrorDialog(
                title="Could not restore instance",
                message=(
                    "An error occurred while restoring the instance. "
                    "Please try again."
                ),
                detail=str(exc),
                parent=self,
            ).exec()
            return
        self.refresh()

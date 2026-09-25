"""Deployments panel — PI-580 (PRJ-128; the record is PI-576 / PI-577).

A ``ListDetailPanel`` over ``/deployments``: one row per installation of the
active application for one client. The panel replaces the Instances panel in
the Operate sidebar; the deployment is what people see, and the CRM
connection it holds (the ``instance`` record), its deploy configuration and
the hosting credentials that apply to it are sections of the deployment's
detail. The actions the Instances panel offered on a connection — Audit now,
Publish…, Feature selection…, Check DNS now — act on the held connection.

Words: the screen says "application" and "deployment", never "engagement"
or "instance"; the connection details are titled "CRM connection". No secret
value is shown — only whether one is configured (REQ-157).
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
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

from crmbuilder_v2.segments.operate.ui.dialogs.deploy_progress_dialog import (
    DeployProgressDialog,
)
from crmbuilder_v2.segments.operate.ui.dialogs.deploy_wizard_dialog import (
    DeployWizardDialog,
)
from crmbuilder_v2.segments.operate.ui.dialogs.deployment_register_dialog import (
    HOSTING_PROVIDER_LABELS,
    PURPOSE_LABELS,
    DeploymentRegisterDialog,
)
from crmbuilder_v2.segments.operate.ui.dialogs.handover_dialog import fit_to_screen
from crmbuilder_v2.segments.operate.ui.dialogs.instance_crud import (
    InstanceEditDialog,
)
from crmbuilder_v2.segments.operate.ui.dialogs.provider_credentials_dialog import (
    PROVIDERS,
    ProviderCredentialsDialog,
)
from crmbuilder_v2.segments.operate.ui.handover import open_items_html
from crmbuilder_v2.segments.operate.ui.panels.deploy_history import (
    DeployHistoryPanel,
)
from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.dialogs.audit_progress_dialog import AuditProgressDialog
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.dialogs.feature_selection_dialog import (
    FeatureSelectionDialog,
)
from crmbuilder_v2.ui.dialogs.publish_dialog import PublishDialog
from crmbuilder_v2.ui.exceptions import (
    NotFoundError,
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.panels._governance_helpers import (
    created_updated_section,
    heading_label,
    read_only_line,
    read_only_text,
    separator,
)
from crmbuilder_v2.ui.widgets.datetime_format import format_timestamp
from crmbuilder_v2.ui.widgets.form_helpers import (
    CollapsibleSection,
    destructive_button,
    primary_button,
    required_label,
)
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection
from crmbuilder_v2.ui.widgets.selectable_text import CopyableMessageBox
from crmbuilder_v2.ui.workers import run_in_thread

_log = logging.getLogger("crmbuilder_v2.ui.panels.deployments")

_EMPTY_LIST_TEXT = "No deployments yet"
_EMPTY_DETAIL_TEXT = "Select a record to see its detail."


def _value(value: Any) -> str:
    return str(value) if value not in (None, "") else "—"


class DeploymentsPanel(ListDetailPanel):
    """Deployments of the active application, with what each one holds."""

    def __init__(self, client, active_context=None, parent=None):
        self._active_context = active_context
        self._include_retired = False
        self._dns_checks: list = []
        super().__init__(client, parent)
        self._show_retired_check = QCheckBox("Show retired")
        self._show_retired_check.setObjectName("show_retired_check")
        self._show_retired_check.setToolTip(
            "Also list deployments that are retired or removed."
        )
        self._show_retired_check.toggled.connect(self._on_show_retired_toggled)
        self._action_layout.addWidget(self._show_retired_check)
        # A brand-new CRM: the wizard creates the deployment, then queues the
        # run that builds it (PI-580). Shown to everyone (no hidden buttons).
        self._new_button = primary_button("New deployment…")
        self._new_button.setObjectName("new_deployment_button")
        self._new_button.setToolTip(
            "Rent a server, install the CRM and record it as a deployment."
        )
        self._new_button.clicked.connect(self._on_new_clicked)
        self._action_layout.addWidget(self._new_button)
        # A CRM that already exists: record it as a deployment with its
        # connection details.
        self._register_button = QPushButton("Register existing…")
        self._register_button.setObjectName("register_deployment_button")
        self._register_button.setToolTip(
            "Record a CRM that is already running as a deployment."
        )
        self._register_button.clicked.connect(self._on_register_clicked)
        self._action_layout.addWidget(self._register_button)
        self.records_loaded.connect(self._on_records_loaded)

    # ------------------------------------------------------------------
    # ListDetailPanel hooks
    # ------------------------------------------------------------------

    def entity_title(self) -> str:
        return "Deployments"

    def application_identifier(self) -> str | None:
        """The active application (the engagement record the desktop selected)."""
        identifier = None
        if self._active_context is not None:
            identifier = self._active_context.engagement_identifier()
        return identifier or self._client.active_engagement()

    def fetch_records(self) -> list[dict[str, Any]]:
        records = self._client.list_deployments(
            application=self.application_identifier(),
            include_deleted=self._include_retired,
        )
        names = {
            c.get("client_identifier"): c.get("client_name")
            for c in self._client.list_clients()
        }
        for r in records:
            client = r.get("deployment_client")
            r["client_display"] = names.get(client) or client or ""
            purpose = r.get("deployment_purpose") or ""
            r["purpose_display"] = PURPOSE_LABELS.get(purpose, purpose)
            provider = r.get("deployment_hosting_provider") or ""
            r["hosting_provider_display"] = HOSTING_PROVIDER_LABELS.get(
                provider, provider
            )
            r["created_at_display"] = format_timestamp(r.get("deployment_created_at"))
        if not self._include_retired:
            records = [r for r in records if r.get("deployment_status") != "retired"]
        return records

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="deployment_identifier", title="Identifier", width=100),
            ColumnSpec(field="deployment_name", title="Name"),
            ColumnSpec(field="client_display", title="Client", width=160),
            ColumnSpec(field="deployment_application", title="Application", width=100),
            ColumnSpec(
                field="hosting_provider_display", title="Hosting provider", width=120
            ),
            ColumnSpec(field="purpose_display", title="Purpose", width=100),
            ColumnSpec(field="deployment_status", title="Status", width=80),
            ColumnSpec(field="created_at_display", title="Created", width=140),
        ]

    def _strikethrough_for_record(self, record: dict[str, Any]) -> bool:
        return record.get("deployment_deleted_at") is not None

    def _on_show_retired_toggled(self, checked: bool) -> None:
        self._include_retired = checked
        self.refresh()

    def _on_records_loaded(self, count: int) -> None:
        """An empty list says so in the detail pane instead of asking for a pick."""
        empty = getattr(self, "_empty_detail", None)
        if empty is not None:
            empty.setText(_EMPTY_LIST_TEXT if count == 0 else _EMPTY_DETAIL_TEXT)

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        identifier = record.get("deployment_identifier")
        extras: dict[str, Any] = {
            "deployment": record,
            "references": {"as_source": [], "as_target": []},
        }
        if not identifier:
            return extras
        # Re-read the composed record so a dialog's change shows at once.
        try:
            extras["deployment"] = self._client.get_deployment(identifier)
        except StorageClientError as exc:
            _log.warning("deployment read failed for %s: %s", identifier, exc)
        instance_id = extras["deployment"].get("deployment_instance_identifier")
        if not instance_id:
            return extras
        extras["references"] = self._client.list_references_touching(
            "instance", instance_id
        )
        # PI-188 inventory/drift surface on the held connection; reads degrade
        # gracefully so a transient error never blanks the detail.
        try:
            extras["membership_summary"] = self._client.get_membership_summary(
                instance_id
            )
            extras["publish_plan"] = self._client.get_publish_plan(instance_id)
        except StorageClientError as exc:
            _log.warning("inventory read failed for %s: %s", instance_id, exc)
            extras["membership_summary"] = {}
            extras["publish_plan"] = {"item_count": 0}
        return extras

    def render_detail(self, record: dict[str, Any], extras: dict[str, Any]) -> QWidget:
        deployment = extras.get("deployment") or record
        instance = deployment.get("instance") or None
        is_deleted = deployment.get("deployment_deleted_at") is not None

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        outer.addWidget(self._action_strip(deployment, instance, is_deleted))
        outer.addWidget(heading_label(deployment.get("deployment_name") or "(unnamed)"))
        outer.addLayout(self._deployment_form(deployment, record))

        notes_value = read_only_text(deployment.get("deployment_notes") or "")
        notes_value.setObjectName("deployment_notes_value")
        notes_section = CollapsibleSection(
            "Internal notes", notes_value, expanded=False
        )
        notes_section.setObjectName("deployment_notes_toggle")
        outer.addWidget(notes_section)

        outer.addWidget(separator())
        outer.addWidget(self._connection_section(instance))
        if instance is not None:
            outer.addWidget(separator())
            outer.addWidget(self._membership_section(extras))
        outer.addWidget(separator())
        outer.addWidget(
            self._deploy_config_section(
                deployment.get("deploy_config"),
                deployment.get("deployment_instance_identifier"),
            )
        )
        outer.addWidget(separator())
        outer.addWidget(self._credentials_section(deployment))
        outer.addWidget(separator())
        outer.addWidget(
            created_updated_section(
                deployment, "deployment_created_at", "deployment_updated_at"
            )
        )
        if instance is not None:
            outer.addWidget(separator())
            references_section = ReferencesSection(
                "instance",
                instance.get("instance_identifier") or "",
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
    # Detail sections
    # ------------------------------------------------------------------

    def _action_strip(
        self,
        deployment: dict[str, Any],
        instance: dict[str, Any] | None,
        is_deleted: bool,
    ) -> QWidget:
        strip = QWidget()
        layout = QHBoxLayout(strip)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        if is_deleted:
            restore_btn = QPushButton("Restore")
            restore_btn.setObjectName("restore_deployment_button")
            restore_btn.clicked.connect(
                lambda _checked=False, d=deployment: self._on_restore_clicked(d)
            )
            layout.addWidget(restore_btn)
        if instance is not None and not is_deleted:
            edit_btn = QPushButton("Edit CRM connection…")
            edit_btn.setObjectName("edit_connection_button")
            edit_btn.clicked.connect(
                lambda _checked=False, i=instance: self._on_edit_connection_clicked(i)
            )
            layout.addWidget(edit_btn)
            # Audit (pull) is never hidden by role (REQ-430): a target-only
            # connection gets the server's refusal explained on click.
            audit_btn = QPushButton("Audit now")
            audit_btn.setObjectName("audit_instance_button")
            audit_btn.clicked.connect(
                lambda _checked=False, i=instance: self._on_audit_clicked(i)
            )
            layout.addWidget(audit_btn)
            if instance.get("instance_role") != "source":
                publish_btn = QPushButton("Publish…")
                publish_btn.setObjectName("publish_instance_button")
                publish_btn.clicked.connect(
                    lambda _checked=False, i=instance: self._on_publish_clicked(i)
                )
                layout.addWidget(publish_btn)
                # PI-444 (REQ-546): which design entities a bare publish sends.
                selection_btn = QPushButton("Feature selection…")
                selection_btn.setObjectName("feature_selection_button")
                selection_btn.clicked.connect(
                    lambda _checked=False, i=instance: (
                        self._on_feature_selection_clicked(i)
                    )
                )
                layout.addWidget(selection_btn)
        history_btn = QPushButton("Run history…")
        history_btn.setObjectName("run_history_button")
        history_btn.setToolTip("The deploy runs that built or rebuilt this deployment.")
        history_btn.clicked.connect(
            lambda _checked=False, d=deployment: self._on_run_history_clicked(d)
        )
        layout.addWidget(history_btn)
        if not is_deleted:
            remove_btn = destructive_button("Remove")
            remove_btn.setObjectName("remove_deployment_button")
            remove_btn.setToolTip(
                "Remove this deployment from the list. Nothing on the server "
                "changes; Show retired brings it back for Restore."
            )
            remove_btn.clicked.connect(
                lambda _checked=False, d=deployment: self._on_remove_clicked(d)
            )
            layout.addWidget(remove_btn)
        layout.addStretch(1)
        return strip

    def _deployment_form(
        self, deployment: dict[str, Any], record: dict[str, Any]
    ) -> QFormLayout:
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        identifier_label = QLabel(deployment.get("deployment_identifier") or "—")
        identifier_label.setObjectName("deployment_identifier_value")
        identifier_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        form.addRow("Identifier", identifier_label)

        def _row(label: str | QLabel, value: Any, name: str) -> None:
            widget = read_only_line(_value(value))
            widget.setObjectName(name)
            form.addRow(label, widget)

        _row(
            required_label("Name"),
            deployment.get("deployment_name"),
            "deployment_name_value",
        )
        _row(
            "Client",
            record.get("client_display") or deployment.get("deployment_client"),
            "deployment_client_value",
        )
        _row(
            "Application",
            deployment.get("deployment_application"),
            "deployment_application_value",
        )
        provider = deployment.get("deployment_hosting_provider") or ""
        _row(
            "Hosting provider",
            HOSTING_PROVIDER_LABELS.get(provider, provider),
            "deployment_hosting_provider_value",
        )
        purpose = deployment.get("deployment_purpose") or ""
        _row(
            "Purpose", PURPOSE_LABELS.get(purpose, purpose), "deployment_purpose_value"
        )
        _row("Status", deployment.get("deployment_status"), "deployment_status_value")
        return form

    def _connection_section(self, instance: dict[str, Any] | None) -> QWidget:
        """The CRM connection the deployment holds (the composed ``instance``)."""
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(heading_label("CRM connection"))
        if not instance:
            empty = QLabel(
                "No CRM connection yet. A deploy run records one when the CRM "
                "is installed."
            )
            empty.setObjectName("connection_empty")
            empty.setWordWrap(True)
            lay.addWidget(empty)
            return box
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        def _row(label: str, value: Any, name: str) -> None:
            widget = read_only_line(_value(value))
            widget.setObjectName(name)
            form.addRow(label, widget)

        _row(
            "Identifier",
            instance.get("instance_identifier"),
            "instance_identifier_value",
        )
        _row("Name", instance.get("instance_name"), "instance_name_value")
        _row("URL", instance.get("instance_url"), "instance_url_value")
        _row("CRM system", instance.get("instance_vendor"), "instance_vendor_value")
        _row("Role", instance.get("instance_role"), "instance_role_value")
        _row(
            "Auth method",
            instance.get("instance_auth_method"),
            "instance_auth_method_value",
        )
        # Secret presence only — never the value or the opaque ref (REQ-157).
        _row(
            "Secret",
            "configured" if instance.get("instance_secret_ref") else "none",
            "instance_secret_state_value",
        )
        _row("Status", instance.get("instance_status"), "instance_status_value")
        selection = instance.get("instance_feature_selection") or []
        _row(
            "Feature selection",
            (
                f"{len(selection)} design entit"
                f"{'y' if len(selection) == 1 else 'ies'} selected"
                if selection
                else "full design (no selection)"
            ),
            "instance_feature_selection_value",
        )
        lay.addLayout(form)
        return box

    def _membership_section(self, extras: dict[str, Any]) -> QWidget:
        """The inventory/drift summary + publish-plan size (PI-188)."""
        summary = extras.get("membership_summary") or {}
        plan = extras.get("publish_plan") or {}
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(heading_label("Inventory & drift"))
        if not summary:
            empty = QLabel(
                'No audit yet — click "Audit now" to reconcile this CRM into the '
                "canonical inventory."
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

    def _deploy_config_section(
        self, cfg: dict[str, Any] | None, instance_identifier: str | None
    ) -> QWidget:
        """Read-only deploy configuration block (PI-201 / REQ-172)."""
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(heading_label("Deploy configuration"))
        if not cfg:
            empty = QLabel("No deploy configuration recorded for this deployment.")
            empty.setObjectName("deploy_config_empty")
            empty.setWordWrap(True)
            lay.addWidget(empty)
            return box
        lay.addWidget(self._open_items_block(cfg, instance_identifier))
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)

        def _row(label: str, value: Any) -> None:
            v = QLabel(_value(value))
            v.setWordWrap(True)
            form.addRow(QLabel(label), v)

        def _joined(*keys: str, sep: str = " / ") -> str:
            return sep.join(str(cfg.get(k)) for k in keys if cfg.get(k))

        _row("Scenario", cfg.get("scenario"))
        _row(
            "SSH",
            "{}@{}:{}".format(
                cfg.get("ssh_username") or "?",
                cfg.get("ssh_host") or "?",
                cfg.get("ssh_port") or 22,
            ),
        )
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
        _row("Droplet IP", cfg.get("droplet_ip"))
        _row("Droplet region / size", _joined("droplet_region", "droplet_size"))
        _row("DNS provider", cfg.get("dns_provider"))
        _row("CRM admin username", cfg.get("admin_username"))
        _row("CRM admin password", "set" if cfg.get("admin_password_ref") else "—")
        _row("DB password", "set" if cfg.get("db_password_ref") else "—")
        _row("Last deploy run", cfg.get("last_deploy_run_identifier"))
        # PI-442 (REQ-544): server-management facts.
        _row(
            "Hosting provider",
            _joined("hosting_provider", "hosting_account", sep=" — "),
        )
        _row("Provider console", cfg.get("hosting_console_url"))
        _row("DNS console", cfg.get("dns_console_url"))
        _row("SSH key fingerprint", cfg.get("ssh_key_fingerprint"))
        _row("SSH key name / id", _joined("ssh_key_name", "ssh_key_provider_id"))
        _row("Server image", cfg.get("server_image"))
        _row("Provisioned", cfg.get("provisioned_at"))
        _row("Last verified", cfg.get("last_verified_at"))
        _row(
            "Backup schedule / retention / destination",
            _joined("backup_schedule", "backup_retention", "backup_destination"),
        )
        _row("Monthly cost (USD)", cfg.get("monthly_cost_usd"))
        _row("Billing note", cfg.get("billing_note"))
        _row("Notes", cfg.get("notes"))
        lay.addLayout(form)
        return box

    def _open_items_block(
        self, cfg: dict[str, Any], instance_identifier: str | None
    ) -> QWidget:
        """What is still outstanding after the deploy, and Check DNS now (PI-571)."""
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        items = cfg.get("open_items") or []
        summary = QLabel()
        summary.setObjectName("deployment_open_items")
        summary.setWordWrap(True)
        summary.setTextFormat(Qt.TextFormat.RichText)
        summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        if items:
            summary.setText(
                "<b>Still outstanding from the deploy:</b>" + open_items_html(items)
            )
            summary.setStyleSheet(
                "background: #FBF2E0; border-radius: 6px; padding: 8px;"
            )
        else:
            summary.setText("Nothing outstanding from the deploy.")
        lay.addWidget(summary)
        if cfg.get("domain") and (cfg.get("droplet_ip") or cfg.get("ssh_host")):
            btn = QPushButton("Check DNS now")
            btn.setObjectName("check_dns_button")
            btn.setToolTip(
                "Checks the web address's DNS, reads the certificate job on the "
                "server, starts it if DNS is ready, and updates the items above."
            )
            btn.clicked.connect(
                lambda _checked=False: self._on_check_dns_clicked(
                    instance_identifier, btn
                )
            )
            lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignLeft)
        return box

    def _credentials_section(self, deployment: dict[str, Any]) -> QWidget:
        """The hosting credentials that apply, each with its scope; never a token."""
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(heading_label("Hosting credentials"))
        by_key = {
            c.get("provider"): c for c in deployment.get("provider_credentials") or []
        }
        for key, title, _hint in PROVIDERS:
            rec = by_key.get(key)
            if rec and rec.get("configured"):
                scope = (
                    "this deployment"
                    if rec.get("scope") == "deployment"
                    else "application default"
                )
                text = f"{title}: configured ({scope})"
                if rec.get("label"):
                    text += f" — {rec['label']}"
            else:
                text = f"{title}: not configured"
            label = QLabel(text)
            label.setObjectName(f"credential_{key}")
            label.setWordWrap(True)
            lay.addWidget(label)
        btn = QPushButton("Credentials…")
        btn.setObjectName("deployment_credentials_button")
        btn.setToolTip(
            "Set the hosting tokens this deployment uses. A token set here "
            "overrides the application default."
        )
        identifier = deployment.get("deployment_identifier") or ""
        btn.clicked.connect(
            lambda _checked=False: self._on_credentials_clicked(identifier)
        )
        lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignLeft)
        return box

    # ------------------------------------------------------------------
    # Check DNS now (PI-571 / REQ-651)
    # ------------------------------------------------------------------

    def _on_check_dns_clicked(
        self, identifier: str | None, button: QPushButton
    ) -> None:
        if not identifier:
            return
        button.setEnabled(False)
        button.setText("Checking…")
        self._dns_checks.append(
            run_in_thread(
                lambda: self._client.check_instance_dns(identifier),
                on_success=self._dns_checked,
                on_error=self._dns_check_failed,
                parent=self,
            )
        )

    def _dns_checked(self, result: dict[str, Any]) -> None:
        dns = result.get("dns") or {}
        lines = [f"{dns.get('title', 'DNS checked')}. {dns.get('found', '')}".strip()]
        if dns.get("action") and dns.get("state") != "correct":
            lines.append(f"What to do: {dns['action']}")
        if result.get("certificate_expiry"):
            lines.append(
                f"The certificate is in place; it expires {result['certificate_expiry']}."
            )
        elif result.get("certificate_job_started"):
            lines.append(
                "DNS is correct, so the certificate is being installed now. "
                "Check again in a few minutes."
            )
        if result.get("ssh_error"):
            lines.append(result["ssh_error"])
        box = CopyableMessageBox(self)
        box.setWindowTitle("Check DNS now")
        box.setText("\n\n".join(lines))
        box.exec()
        self.refresh()

    def _dns_check_failed(self, exc: Exception) -> None:
        if isinstance(exc, StorageConnectionError):
            self.connection_lost.emit(str(exc))
        ErrorDialog(title="Check DNS now", message=str(exc), parent=self).exec()
        self.refresh()

    # ------------------------------------------------------------------
    # Identifier addressing — a deployment answers to its own identifier and
    # to the identifier of the connection it holds, so a reference to an
    # ``instance`` opens the deployment holding it.
    # ------------------------------------------------------------------

    def _select_by_identifier(self, identifier: str) -> bool:
        for row, record in enumerate(self._records):
            if identifier in (
                record.get("deployment_identifier"),
                record.get("deployment_instance_identifier"),
            ):
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
            ident = self._records[row].get("deployment_identifier")
            if isinstance(ident, str):
                return ident
        return None

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        menu.addAction("New deployment…").triggered.connect(self._on_new_clicked)
        menu.addAction("Register existing…").triggered.connect(
            self._on_register_clicked
        )
        if not index.isValid():
            return menu
        record = self._record_at_index(index)
        if record is None:
            return menu
        history = menu.addAction("Run history…")
        history.triggered.connect(
            lambda _checked=False, r=record: self._on_run_history_clicked(r)
        )
        if record.get("deployment_deleted_at") is not None:
            restore = menu.addAction("Restore")
            restore.triggered.connect(
                lambda _checked=False, r=record: self._on_restore_clicked(r)
            )
        else:
            remove = menu.addAction("Remove")
            remove.triggered.connect(
                lambda _checked=False, r=record: self._on_remove_clicked(r)
            )
        return menu

    # ------------------------------------------------------------------
    # Click handlers
    # ------------------------------------------------------------------

    def _on_new_clicked(self) -> None:
        """Run the deploy wizard; follow the queued run in the progress window."""
        wizard = DeployWizardDialog(
            self._client, parent=self, active_context=self._active_context
        )
        wizard.connection_lost.connect(self.connection_lost)
        queued: list[str] = []
        created: list[str] = []
        wizard.run_queued.connect(queued.append)
        wizard.deployment_created.connect(created.append)
        try:
            wizard.exec()
            # Kept only for this deploy's handover sheet (PI-571 / REQ-652).
            password = wizard.admin_password.text() or None
        finally:
            wizard.deleteLater()
        if queued:
            self.open_deploy_progress(queued[0], admin_password=password)
        elif created:
            # The deployment exists even when no run was queued: show it.
            self.select_record_by_identifier(created[0])

    def open_deploy_progress(
        self, identifier: str, *, admin_password: str | None = None
    ) -> None:
        """Follow deploy run ``identifier``; select the deployment it builds."""
        dialog = DeployProgressDialog(
            self._client, identifier, parent=self, admin_password=admin_password
        )
        dialog.connection_lost.connect(self.connection_lost)
        created: list[str] = []
        dialog.instance_created.connect(created.append)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()
        self.refresh()
        if created:
            self.select_record_by_identifier(created[0])

    def _on_register_clicked(self) -> None:
        dialog = DeploymentRegisterDialog(self._client, parent=self)
        dialog.connection_lost.connect(self.connection_lost)
        try:
            accepted = dialog.exec() == QDialog.DialogCode.Accepted
            new_id = dialog.created_identifier()
        finally:
            dialog.deleteLater()
        if accepted and new_id:
            self.select_record_by_identifier(new_id)
        else:
            self.refresh()

    def _on_run_history_clicked(self, deployment: dict[str, Any]) -> None:
        """The deploy runs of this deployment, in the history panel."""
        identifier = deployment.get("deployment_identifier") or ""
        if not identifier:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Run history — {identifier}")
        fit_to_screen(dialog, 0.7, (900, 600))
        layout = QVBoxLayout(dialog)
        panel = DeployHistoryPanel(self._client, deployment_identifier=identifier)
        panel.connection_lost.connect(self.connection_lost)
        layout.addWidget(panel, 1)
        close_btn = QPushButton("Close")
        close_btn.setObjectName("run_history_close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
        try:
            dialog.exec()
        finally:
            panel.drain_workers()
            dialog.deleteLater()
        self.refresh()

    def _on_credentials_clicked(self, identifier: str) -> None:
        if not identifier:
            return
        dialog = ProviderCredentialsDialog(
            self._client, parent=self, deployment_identifier=identifier
        )
        dialog.connection_lost.connect(self.connection_lost)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()
        self.refresh()

    def _on_audit_clicked(self, instance: dict[str, Any]) -> None:
        if not instance.get("instance_identifier"):
            return
        # Live per-area progress (PI-274).
        dialog = AuditProgressDialog(self._client, instance, parent=self)
        dialog.connection_lost.connect(self.connection_lost)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()
        self.refresh()

    def _on_publish_clicked(self, instance: dict[str, Any]) -> None:
        if not instance.get("instance_identifier"):
            return
        dialog = PublishDialog(self._client, instance, parent=self)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()
        self.refresh()

    def _on_feature_selection_clicked(self, instance: dict[str, Any]) -> None:
        """Edit the connection's stored feature selection (PI-444 / REQ-546)."""
        if not instance.get("instance_identifier"):
            return
        dialog = FeatureSelectionDialog(self._client, instance, parent=self)
        try:
            accepted = bool(dialog.exec())
        finally:
            dialog.deleteLater()
        if accepted:
            self.refresh()

    def _on_edit_connection_clicked(self, instance: dict[str, Any]) -> None:
        identifier = instance.get("instance_identifier")
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
                title="Could not load the CRM connection",
                message="Could not load the latest version of this CRM connection.",
                detail=str(exc),
                parent=self,
            ).exec()
            return
        dialog = InstanceEditDialog(self._client, fresh, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_remove_clicked(self, deployment: dict[str, Any]) -> None:
        identifier = deployment.get("deployment_identifier") or ""
        name = deployment.get("deployment_name") or ""
        if not identifier:
            return
        confirm = CopyableMessageBox(self)
        confirm.setWindowTitle("Remove deployment")
        confirm.setText(
            f"Remove {identifier} — {name or '(unnamed)'} from the list?\n\n"
            "Nothing on the server changes. Tick Show retired to see it again "
            "and Restore it."
        )
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        confirm.setDefaultButton(QMessageBox.StandardButton.No)
        if confirm.exec() != QMessageBox.StandardButton.Yes:
            return
        self._write(
            lambda: self._client.delete_deployment(identifier),
            identifier,
            title="Could not remove the deployment",
        )

    def _on_restore_clicked(self, deployment: dict[str, Any]) -> None:
        identifier = deployment.get("deployment_identifier") or ""
        if not identifier:
            return
        self._write(
            lambda: self._client.restore_deployment(identifier),
            identifier,
            title="Could not restore the deployment",
        )

    def _write(self, action, identifier: str, *, title: str) -> None:
        """Run a one-shot write; explain a failure; refresh either way."""
        try:
            action()
        except NotFoundError:
            pass
        except StorageConnectionError as exc:
            _log.warning("Connection lost writing %s: %s", identifier, exc)
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            _log.warning("Domain error writing %s: %s", identifier, exc)
            ErrorDialog(
                title=title,
                message="The change was not saved. Please try again.",
                detail=str(exc),
                parent=self,
            ).exec()
            return
        self.refresh()

"""Register an existing CRM as a deployment — PI-580 (PRJ-128).

The deploy wizard creates a deployment and builds its CRM; this dialog is
for a CRM that already runs. It asks who the deployment is for (the client
and the purpose), how it is hosted and what to call it, then the CRM
connection details the Instances create dialog used to take, and posts them
in one ``POST /deployments`` request with a nested ``instance``. The API's
refusals (a client the application may not deploy for, a demo/test
deployment for a client that does not define the application) come back as
a 422 and are shown under the form. Secrets cross once and are never read
back (REQ-157).
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.segments.operate.vocab import (
    INSTANCE_AUTH_METHODS,
    INSTANCE_ROLES,
    INSTANCE_STATUSES,
    INSTANCE_VENDORS,
)
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.exceptions import (
    RequestShapeError,
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.styling import t
from crmbuilder_v2.ui.widgets.form_helpers import primary_button, required_label
from crmbuilder_v2.ui.workers import drain_workers, run_in_thread

_log = logging.getLogger("crmbuilder_v2.ui.dialogs.deployment_register_dialog")

#: API value → what people see (PI-577 / REQ-654).
PURPOSE_LABELS = {"client_own": "Client's own", "demo_test": "Demo/test"}
#: API value → what people see (PI-576 / REQ-653).
HOSTING_PROVIDER_LABELS = {"digitalocean": "DigitalOcean", "other": "Other"}


def _combo(options: dict[str, str], *, default: str | None = None) -> QComboBox:
    """A combo whose text is the label and whose data is the API value."""
    combo = QComboBox()
    for value, label in options.items():
        combo.addItem(label, value)
    if default is not None:
        index = combo.findData(default)
        if index >= 0:
            combo.setCurrentIndex(index)
    return combo


class DeploymentRegisterDialog(QDialog):
    """Record a CRM that already runs as a deployment with its connection."""

    connection_lost = Signal(str)

    def __init__(self, client, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._client = client
        self._in_flight: list = []
        self._created: str | None = None
        self.setWindowTitle("Register an existing CRM")
        self.setMinimumWidth(620)

        outer = QVBoxLayout(self)
        intro = QLabel(
            "Records a CRM that is already running as a deployment of the "
            "active application, with the connection CRMBuilder uses to audit "
            "and publish to it."
        )
        intro.setWordWrap(True)
        outer.addWidget(intro)

        deployment_box = QGroupBox("Deployment")
        form = QFormLayout(deployment_box)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.client_combo = QComboBox()
        self.client_combo.setObjectName("register_client")
        self.client_combo.addItem("Loading clients…", None)
        form.addRow(required_label("Client"), self.client_combo)
        self.purpose = _combo(PURPOSE_LABELS, default="client_own")
        self.purpose.setObjectName("register_purpose")
        form.addRow(required_label("Purpose"), self.purpose)
        purpose_hint = QLabel(
            "A client's own deployment is the CRM that client runs. A demo/test "
            "deployment is run by the client that defines the application."
        )
        purpose_hint.setWordWrap(True)
        purpose_hint.setStyleSheet(f"color: {t('color.neutral.700')};")
        form.addRow("", purpose_hint)
        self.hosting_provider = _combo(HOSTING_PROVIDER_LABELS, default="digitalocean")
        self.hosting_provider.setObjectName("register_hosting_provider")
        form.addRow(required_label("Hosting provider"), self.hosting_provider)
        self.deployment_name = QLineEdit()
        self.deployment_name.setObjectName("register_deployment_name")
        self.deployment_name.setPlaceholderText("Cleveland Business Mentors CRM")
        form.addRow(required_label("Deployment name"), self.deployment_name)
        self.deployment_notes = QPlainTextEdit()
        self.deployment_notes.setObjectName("register_deployment_notes")
        self.deployment_notes.setMaximumHeight(70)
        form.addRow("Internal notes", self.deployment_notes)
        outer.addWidget(deployment_box)

        connection_box = QGroupBox("CRM connection")
        cform = QFormLayout(connection_box)
        cform.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.instance_url = QLineEdit()
        self.instance_url.setObjectName("register_instance_url")
        self.instance_url.setPlaceholderText("https://crm.example.org")
        cform.addRow(required_label("URL"), self.instance_url)
        self.instance_name = QLineEdit()
        self.instance_name.setObjectName("register_instance_name")
        self.instance_name.setPlaceholderText("Same as the deployment name")
        cform.addRow("Connection label", self.instance_name)
        self.instance_vendor = _combo(
            {v: v for v in sorted(INSTANCE_VENDORS)}, default="espocrm"
        )
        self.instance_vendor.setObjectName("register_instance_vendor")
        cform.addRow(required_label("CRM system"), self.instance_vendor)
        self.instance_role = _combo(
            {v: v for v in sorted(INSTANCE_ROLES)}, default="both"
        )
        self.instance_role.setObjectName("register_instance_role")
        cform.addRow(required_label("Role"), self.instance_role)
        self.instance_auth_method = _combo(
            {v: v for v in sorted(INSTANCE_AUTH_METHODS)}, default="api_key"
        )
        self.instance_auth_method.setObjectName("register_instance_auth_method")
        cform.addRow(required_label("Auth method"), self.instance_auth_method)
        self.secret = QLineEdit()
        self.secret.setObjectName("register_secret")
        self.secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.secret.setPlaceholderText(
            "API key (API key & HMAC auth) or username (Basic auth). Stored encrypted"
        )
        cform.addRow("API key / username", self.secret)
        self.secret_key = QLineEdit()
        self.secret_key.setObjectName("register_secret_key")
        self.secret_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.secret_key.setPlaceholderText(
            "Password (Basic auth) or HMAC secret key (HMAC auth); unused for API key auth"
        )
        cform.addRow("Password / HMAC secret", self.secret_key)
        self.instance_status = _combo(
            {v: v for v in sorted(INSTANCE_STATUSES)}, default="active"
        )
        self.instance_status.setObjectName("register_instance_status")
        cform.addRow(required_label("Status"), self.instance_status)
        outer.addWidget(connection_box)

        self._notice = QLabel("")
        self._notice.setObjectName("register_notice")
        self._notice.setWordWrap(True)
        self._notice.setStyleSheet(
            f"color: {t('color.warning.default')}; font-weight: 600;"
        )
        outer.addWidget(self._notice)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("register_cancel")
        cancel_btn.clicked.connect(self.reject)
        self._save_btn = primary_button("Register")
        self._save_btn.setObjectName("register_save")
        self._save_btn.clicked.connect(self._on_save_clicked)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(self._save_btn)
        outer.addLayout(buttons)
        self._load_clients()

    # -- clients ---------------------------------------------------------------

    def _load_clients(self) -> None:
        def fetch() -> tuple[list[dict[str, Any]], str | None]:
            clients = self._client.list_clients()
            defining = None
            application = self._client.active_engagement()
            if application:
                try:
                    defining = self._client.get_engagement(application).get(
                        "engagement_defining_client"
                    )
                except StorageClientError:
                    defining = None
            return clients, defining

        self._in_flight.append(
            run_in_thread(
                fetch,
                on_success=self._clients_loaded,
                on_error=self._on_error,
                parent=self,
            )
        )

    def _clients_loaded(self, result: tuple[list[dict[str, Any]], str | None]) -> None:
        clients, defining = result
        self.client_combo.clear()
        for c in clients:
            self.client_combo.addItem(
                c.get("client_name") or c.get("client_identifier") or "",
                c.get("client_identifier"),
            )
        if defining:
            index = self.client_combo.findData(defining)
            if index >= 0:
                self.client_combo.setCurrentIndex(index)
        if not clients:
            self.client_combo.addItem("No clients recorded yet", None)

    # -- data ------------------------------------------------------------------

    def created_identifier(self) -> str | None:
        """The new deployment's identifier once Register succeeded."""
        return self._created

    def validate(self) -> str | None:
        """What is missing, or ``None`` when the form can be sent."""
        if not self.client_combo.currentData():
            return "Choose the client this deployment is for."
        if not self.deployment_name.text().strip():
            return "Give the deployment a name."
        if not self.instance_url.text().strip():
            return "Enter the CRM's URL."
        return None

    def build_body(self) -> dict[str, Any]:
        """The POST /deployments body: the deployment plus its connection."""
        name = self.deployment_name.text().strip()
        return {
            "deployment_client": self.client_combo.currentData(),
            "deployment_purpose": self.purpose.currentData(),
            "deployment_hosting_provider": self.hosting_provider.currentData(),
            "deployment_name": name,
            "deployment_notes": self.deployment_notes.toPlainText().strip() or None,
            "instance": {
                "instance_name": self.instance_name.text().strip() or name,
                "instance_url": self.instance_url.text().strip(),
                "instance_vendor": self.instance_vendor.currentData(),
                "instance_role": self.instance_role.currentData(),
                "instance_auth_method": self.instance_auth_method.currentData(),
                "secret": self.secret.text() or None,
                "secret_key": self.secret_key.text() or None,
                "instance_status": self.instance_status.currentData(),
            },
        }

    # -- save ------------------------------------------------------------------

    def _on_save_clicked(self) -> None:
        problem = self.validate()
        if problem:
            self._notice.setText(problem)
            return
        self._notice.setText("")
        self._save_btn.setEnabled(False)
        body = self.build_body()
        self._in_flight.append(
            run_in_thread(
                lambda: self._client.create_deployment(body),
                on_success=self._saved,
                on_error=self._save_failed,
                parent=self,
            )
        )

    def _saved(self, record: dict[str, Any]) -> None:
        self._created = record.get("deployment_identifier")
        self.accept()

    def _save_failed(self, exc: Exception) -> None:
        self._save_btn.setEnabled(True)
        if isinstance(exc, RequestShapeError):
            problems = "; ".join(
                f"{e.get('field')}: {e.get('message')}" for e in (exc.errors or [])
            ) or str(exc)
            self._notice.setText(f"Not registered — {problems}")
            return
        self._on_error(exc)

    def _on_error(self, exc: Exception) -> None:
        if isinstance(exc, StorageConnectionError):
            self.connection_lost.emit(str(exc))
        _log.warning("register deployment: %s", exc)
        detail = (
            str(getattr(exc, "errors", ""))
            if isinstance(exc, StorageClientError)
            else None
        )
        ErrorDialog(
            title="Register an existing CRM",
            message=str(exc),
            detail=detail or None,
            parent=self,
        ).exec()

    def done(self, result: int) -> None:  # noqa: D401 - Qt override
        """Finish the in-flight workers before the dialog is torn down."""
        drain_workers(self._in_flight)
        super().done(result)

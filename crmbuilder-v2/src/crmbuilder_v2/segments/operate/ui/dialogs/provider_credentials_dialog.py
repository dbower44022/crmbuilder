"""Hosting credentials dialog — PI-419 (REQ-522, PRJ-111); per deployment
PI-580 (PRJ-128).

Lets an administrator set, replace or remove the DigitalOcean and Cloudflare
API tokens — the *provider credentials* a deploy run uses to create a server
and its DNS record. Opened without a deployment it edits the application's
defaults; opened with ``deployment_identifier`` it edits that deployment's
own tokens, showing for each provider whether the token that applies is the
deployment's own or the application default (PI-576 / REQ-653). The dialog
never sees a stored token: the API reports only whether one is configured
(REQ-157), and a token typed here crosses to the service once and is stored
behind the secret boundary. Every network call runs off the UI thread via
:func:`run_in_thread`.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.exceptions import StorageClientError, StorageConnectionError
from crmbuilder_v2.ui.widgets.form_helpers import destructive_button, primary_button
from crmbuilder_v2.ui.workers import drain_workers, run_in_thread

_log = logging.getLogger("crmbuilder_v2.ui.dialogs.provider_credentials_dialog")

#: (provider key, display name, what the token must be able to do)
PROVIDERS: tuple[tuple[str, str, str], ...] = (
    (
        "digitalocean",
        "DigitalOcean",
        "Personal access token with read and write scope — creates the server.",
    ),
    (
        "cloudflare",
        "Cloudflare",
        "API token with Zone:Read and DNS:Edit on the customer's zone — "
        "creates the DNS-only A record (proxying stays off so certificates "
        "and SSH work).",
    ),
)

_SCOPE_WORDS = {"deployment": "this deployment", "application": "application default"}


class _ProviderRow(QGroupBox):
    """One provider's status line plus token / label inputs and actions."""

    def __init__(self, key: str, title: str, hint: str, parent=None) -> None:
        super().__init__(title, parent)
        self.key = key
        #: The record last shown, so Remove knows whose token it would remove.
        self.record: dict[str, Any] | None = None
        layout = QVBoxLayout(self)
        self.status = QLabel("Checking…")
        self.status.setObjectName(f"provider_status_{key}")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        hint_label = QLabel(hint)
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: #666;")
        layout.addWidget(hint_label)
        form = QFormLayout()
        self.token = QLineEdit()
        self.token.setObjectName(f"provider_token_{key}")
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        self.token.setPlaceholderText("Paste a token to set or replace")
        form.addRow("Token", self.token)
        self.label = QLineEdit()
        self.label.setObjectName(f"provider_label_{key}")
        self.label.setPlaceholderText("Optional label, e.g. CRMBuilder account")
        form.addRow("Label", self.label)
        layout.addLayout(form)
        actions = QHBoxLayout()
        actions.addStretch(1)
        self.remove_btn = destructive_button("Remove")
        self.remove_btn.setObjectName(f"provider_remove_{key}")
        self.save_btn = primary_button("Save token")
        self.save_btn.setObjectName(f"provider_save_{key}")
        actions.addWidget(self.remove_btn)
        actions.addWidget(self.save_btn)
        layout.addLayout(actions)

    def show_status(
        self, record: dict[str, Any] | None, *, show_scope: bool = False
    ) -> None:
        self.record = record
        if record and record.get("configured"):
            label = record.get("label")
            text = "✓ Configured" + (f" — {label}" if label else "")
            if show_scope:
                scope = record.get("scope") or "application"
                text += f" ({_SCOPE_WORDS.get(scope, scope)})"
            self.status.setText(text)
            self.status.setStyleSheet("color: #1e8449;")
            self.label.setText(label or "")
        else:
            self.status.setText("Not set — a deploy run cannot use this provider.")
            self.status.setStyleSheet("color: #b9770e;")


class ProviderCredentialsDialog(QDialog):
    """Set, replace or remove the application's or one deployment's credentials."""

    #: Emitted after any successful save or removal, so a wizard can re-check.
    changed = Signal()
    connection_lost = Signal(str)

    def __init__(
        self, client, parent=None, *, deployment_identifier: str | None = None
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._deployment = deployment_identifier or None
        self._in_flight: list = []
        self._rows: dict[str, _ProviderRow] = {}
        self.setWindowTitle("Hosting credentials")
        self.resize(560, 540)

        layout = QVBoxLayout(self)
        if self._deployment:
            intro_text = (
                f"Tokens for deployment {self._deployment}. A token set here applies "
                "to this deployment only and overrides the application default. "
                "Tokens are stored encrypted by the service and never shown again; "
                "leave a token blank to keep the one already stored."
            )
        else:
            intro_text = (
                "The application's default tokens; a deployment may override them "
                "with its own. Tokens are stored encrypted by the service and never "
                "shown again. Leave a token blank to keep the one already stored."
            )
        intro = QLabel(intro_text)
        intro.setObjectName("provider_credentials_intro")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        for key, title, hint in PROVIDERS:
            row = _ProviderRow(key, title, hint, self)
            row.save_btn.clicked.connect(lambda _=False, k=key: self._save(k))
            row.remove_btn.clicked.connect(lambda _=False, k=key: self._remove(k))
            self._rows[key] = row
            layout.addWidget(row)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.setObjectName("provider_credentials_close")
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)
        self.refresh()

    @property
    def deployment_identifier(self) -> str | None:
        """The deployment whose tokens are edited, or ``None`` for the application."""
        return self._deployment

    # -- reads ------------------------------------------------------------

    def refresh(self) -> None:
        deployment = self._deployment
        self._in_flight.append(
            run_in_thread(
                (
                    (
                        lambda: self._client.list_deployment_provider_credentials(
                            deployment
                        )
                    )
                    if deployment
                    else self._client.list_provider_credentials
                ),
                on_success=self._loaded,
                on_error=self._on_error,
                parent=self,
            )
        )

    def _loaded(self, records: list[dict[str, Any]]) -> None:
        by_key = {r.get("provider"): r for r in records or []}
        for key, row in self._rows.items():
            row.show_status(by_key.get(key), show_scope=bool(self._deployment))

    def status_for(self, provider: str) -> str:
        """The status text currently shown for ``provider`` (for tests)."""
        return self._rows[provider].status.text()

    # -- writes -----------------------------------------------------------

    def _save(self, provider: str) -> None:
        row = self._rows[provider]
        token = row.token.text().strip()
        if not token:
            row.status.setText("Paste a token first — nothing was changed.")
            row.status.setStyleSheet("color: #b9770e;")
            return
        label = row.label.text().strip() or None
        deployment = self._deployment
        if deployment:

            def write() -> dict[str, Any] | None:
                records = self._client.put_deployment_provider_credential(
                    deployment, provider, token, label
                )
                return next((r for r in records if r.get("provider") == provider), None)

        else:

            def write() -> dict[str, Any] | None:
                return self._client.put_provider_credential(provider, token, label)

        self._in_flight.append(
            run_in_thread(
                write,
                on_success=lambda rec, p=provider: self._saved(p, rec),
                on_error=self._on_error,
                parent=self,
            )
        )

    def _saved(self, provider: str, record: dict[str, Any] | None) -> None:
        row = self._rows[provider]
        row.token.clear()
        row.show_status(record, show_scope=bool(self._deployment))
        self.changed.emit()

    def _remove(self, provider: str) -> None:
        row = self._rows[provider]
        deployment = self._deployment
        if deployment and (row.record or {}).get("scope") != "deployment":
            # Only the deployment's own token can be removed here; the
            # application default is removed from the application's dialog.
            row.status.setText(
                "This deployment has no token of its own for this provider; the "
                "application default applies. Remove that from the application's "
                "hosting credentials."
            )
            row.status.setStyleSheet("color: #b9770e;")
            return
        self._in_flight.append(
            run_in_thread(
                (
                    (
                        lambda: self._client.delete_deployment_provider_credential(
                            deployment, provider
                        )
                    )
                    if deployment
                    else (lambda: self._client.delete_provider_credential(provider))
                ),
                on_success=lambda _r, p=provider: self._removed(p),
                on_error=self._on_error,
                parent=self,
            )
        )

    def _removed(self, provider: str) -> None:
        row = self._rows[provider]
        row.token.clear()
        row.label.clear()
        row.show_status(None)
        self.changed.emit()
        if self._deployment:
            # The application default, if any, applies again: show it.
            self.refresh()

    def done(self, result: int) -> None:  # noqa: D401 - Qt override
        """Finish the in-flight workers before the dialog is torn down."""
        drain_workers(self._in_flight)
        super().done(result)

    # -- errors -----------------------------------------------------------

    def _on_error(self, exc: Exception) -> None:
        if isinstance(exc, StorageConnectionError):
            self.connection_lost.emit(str(exc))
            ErrorDialog(title="Connection lost", message=str(exc), parent=self).exec()
            return
        detail = (
            getattr(exc, "errors", None)
            if isinstance(exc, StorageClientError)
            else None
        )
        _log.warning("Hosting credential action failed: %s", exc)
        ErrorDialog(
            title="Hosting credential not saved",
            message=str(exc),
            detail=str(detail) if detail else None,
            parent=self,
        ).exec()

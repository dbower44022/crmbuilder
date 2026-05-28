"""API-key bootstrap for the chat tab (PI-052 Slice B, DEC-254).

Resolution order on first chat-panel activation:

1. ``ANTHROPIC_API_KEY`` environment variable.
2. System keyring entry (service ``crmbuilder-v2-chat``, user
   ``default``).
3. A modal :class:`ApiKeyDialog` — single text field, paste-from-
   clipboard button, save-to-keyring checkbox (default on), Save/Cancel.

``keyring`` is imported lazily inside these functions so a missing or
broken backend (e.g. headless Linux) never blocks app startup — the
import only happens when the chat panel is first activated.
"""

from __future__ import annotations

import logging
import os

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_log = logging.getLogger("crmbuilder_v2.ui.chat.auth")

KEYRING_SERVICE = "crmbuilder-v2-chat"
KEYRING_USER = "default"
ENV_VAR = "ANTHROPIC_API_KEY"


def _keyring_get() -> str | None:
    try:
        import keyring

        return keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
    except Exception:  # noqa: BLE001 — backend may be missing/locked
        _log.debug("keyring.get_password unavailable", exc_info=True)
        return None


def _keyring_set(api_key: str) -> bool:
    try:
        import keyring

        keyring.set_password(KEYRING_SERVICE, KEYRING_USER, api_key)
        return True
    except Exception:  # noqa: BLE001 — backend may be missing/locked
        _log.warning("Could not write API key to keyring", exc_info=True)
        return False


def keyring_available() -> bool:
    """Whether a usable keyring backend is present."""
    try:
        import keyring
        from keyring.backends.fail import Keyring as FailKeyring

        return not isinstance(keyring.get_keyring(), FailKeyring)
    except Exception:  # noqa: BLE001
        return False


def resolve_api_key() -> str | None:
    """Return a key from the environment or keyring, or ``None``."""
    env_key = os.environ.get(ENV_VAR)
    if env_key:
        return env_key
    return _keyring_get()


class ApiKeyDialog(QDialog):
    """Modal dialog to enter (and optionally store) the Anthropic API key."""

    def __init__(self, parent: QWidget | None = None, *, invalid: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configure Anthropic API key")
        self.setModal(True)
        self._api_key: str | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        if invalid:
            warning = QLabel("The previous key was rejected (401). Enter a valid key.")
            warning.setWordWrap(True)
            warning.setObjectName("chat_apikey_warning")
            layout.addWidget(warning)

        layout.addWidget(QLabel("Anthropic API key:"))

        field_row = QHBoxLayout()
        self._field = QLineEdit()
        self._field.setEchoMode(QLineEdit.EchoMode.Password)
        self._field.setPlaceholderText("sk-ant-…")
        field_row.addWidget(self._field, stretch=1)
        paste_btn = QPushButton("Paste")
        paste_btn.clicked.connect(self._on_paste)
        field_row.addWidget(paste_btn)
        layout.addLayout(field_row)

        self._save_checkbox = QCheckBox("Save to system keyring")
        if keyring_available():
            self._save_checkbox.setChecked(True)
        else:
            self._save_checkbox.setChecked(False)
            self._save_checkbox.setEnabled(False)
            self._save_checkbox.setToolTip(
                "No system keyring backend available; the key will be held "
                "in memory for this session only."
            )
        layout.addWidget(self._save_checkbox)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_paste(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            self._field.setText(clipboard.text().strip())

    def _on_accept(self) -> None:
        key = self._field.text().strip()
        if not key:
            return
        self._api_key = key
        if self._save_checkbox.isChecked():
            _keyring_set(key)
        self.accept()

    def api_key(self) -> str | None:
        """The entered key (only valid after the dialog is accepted)."""
        return self._api_key

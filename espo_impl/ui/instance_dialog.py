"""Modal dialog for adding/editing instance profiles."""

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QWidget,
)

from espo_impl.core.models import InstanceProfile

AUTH_METHODS = [
    ("API Key", "api_key"),
    ("HMAC", "hmac"),
    ("Basic (Username/Password)", "basic"),
]


class InstanceDialog(QDialog):
    """Dialog for creating or editing an instance profile.

    :param parent: Parent widget.
    :param profile: Existing profile for edit mode, or None for add mode.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        profile: InstanceProfile | None = None,
    ) -> None:
        super().__init__(parent)
        self._profile = profile
        self._build_ui()
        if profile:
            self.setWindowTitle("Edit Instance")
            self.name_input.setText(profile.name)
            self.url_input.setText(profile.url)
            for i, (_, value) in enumerate(AUTH_METHODS):
                if value == profile.auth_method:
                    self.auth_combo.setCurrentIndex(i)
                    break
            self.key_input.setText(profile.api_key)
            if profile.secret_key:
                self.secret_input.setText(profile.secret_key)
        else:
            self.setWindowTitle("Add Instance")

    def _build_ui(self) -> None:
        """Build the dialog layout."""
        layout = QFormLayout(self)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., CBM Production")
        layout.addRow("Name:", self.name_input)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://your-instance.espocloud.com")
        layout.addRow("URL:", self.url_input)

        self.auth_combo = QComboBox()
        for label, value in AUTH_METHODS:
            self.auth_combo.addItem(label, value)
        self.auth_combo.currentIndexChanged.connect(self._on_auth_changed)
        layout.addRow("Auth Method:", self.auth_combo)

        self.key_label = QLabel("API Key:")
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("API key")
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow(self.key_label, self.key_input)

        self.secret_label = QLabel("Secret Key:")
        self.secret_input = QLineEdit()
        self.secret_input.setPlaceholderText("HMAC secret key")
        self.secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow(self.secret_label, self.secret_input)
        self.secret_label.setVisible(False)
        self.secret_input.setVisible(False)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.setMinimumWidth(400)

    def _on_auth_changed(self, index: int) -> None:
        """Update field labels and visibility based on auth method."""
        auth_method = self.auth_combo.currentData()

        if auth_method == "basic":
            self.key_label.setText("Username:")
            self.key_input.setPlaceholderText("Admin username")
            self.key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.secret_label.setText("Password:")
            self.secret_label.setVisible(True)
            self.secret_input.setPlaceholderText("Password")
            self.secret_input.setVisible(True)
        elif auth_method == "hmac":
            self.key_label.setText("API Key:")
            self.key_input.setPlaceholderText("API key")
            self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.secret_label.setText("Secret Key:")
            self.secret_label.setVisible(True)
            self.secret_input.setPlaceholderText("HMAC secret key")
            self.secret_input.setVisible(True)
        else:
            self.key_label.setText("API Key:")
            self.key_input.setPlaceholderText("API key")
            self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.secret_label.setVisible(False)
            self.secret_input.setVisible(False)

    def _on_save(self) -> None:
        """Validate inputs and accept the dialog."""
        name = self.name_input.text().strip()
        url = self.url_input.text().strip()
        key = self.key_input.text().strip()
        auth_method = self.auth_combo.currentData()

        if not name or not url or not key:
            QMessageBox.warning(
                self, "Validation Error", "All fields are required."
            )
            return

        if auth_method in ("hmac", "basic") and not self.secret_input.text().strip():
            label = "Password" if auth_method == "basic" else "Secret Key"
            QMessageBox.warning(
                self,
                "Validation Error",
                f"{label} is required for {self.auth_combo.currentText()} authentication.",
            )
            return

        self.accept()

    def get_profile(self) -> InstanceProfile:
        """Return the profile from the dialog inputs.

        :returns: InstanceProfile with the entered values.
        """
        auth_method = self.auth_combo.currentData()
        secret_key = (
            self.secret_input.text().strip()
            if auth_method in ("hmac", "basic")
            else None
        )
        return InstanceProfile(
            name=self.name_input.text().strip(),
            url=self.url_input.text().strip(),
            api_key=self.key_input.text().strip(),
            auth_method=auth_method,
            secret_key=secret_key,
        )

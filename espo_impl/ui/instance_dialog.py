"""Modal dialog for adding/editing instance profiles."""

from pathlib import Path

from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QWidget,
)

from espo_impl.core.models import InstanceProfile, InstanceRole

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
            if profile.project_folder:
                self.folder_input.setText(profile.project_folder)
            self._role_buttons[profile.role].setChecked(True)
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

        # Instance role
        role_layout = QHBoxLayout()
        self.role_group = QButtonGroup(self)
        self._role_buttons: dict[InstanceRole, QRadioButton] = {}
        for role, label in [
            (InstanceRole.TARGET, "Target"),
            (InstanceRole.SOURCE, "Source"),
            (InstanceRole.BOTH, "Both"),
        ]:
            btn = QRadioButton(label)
            self.role_group.addButton(btn)
            self._role_buttons[role] = btn
            role_layout.addWidget(btn)
        self._role_buttons[InstanceRole.TARGET].setChecked(True)
        layout.addRow("Role:", role_layout)

        # Project folder
        folder_layout = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText(
            "Select project folder (programs, reports, docs)"
        )
        self.folder_input.setReadOnly(True)
        self.folder_browse_btn = QPushButton("Browse...")
        self.folder_browse_btn.clicked.connect(self._on_browse_folder)
        folder_layout.addWidget(self.folder_input)
        folder_layout.addWidget(self.folder_browse_btn)
        layout.addRow("Project Folder:", folder_layout)

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

    def _on_browse_folder(self) -> None:
        """Open folder picker dialog."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Project Folder",
            self.folder_input.text() or str(Path.home()),
        )
        if folder:
            self.folder_input.setText(folder)

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

        folder = self.folder_input.text().strip()
        if folder and not Path(folder).exists():
            QMessageBox.warning(
                self,
                "Validation Error",
                f"Project folder does not exist:\n{folder}",
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
        role = InstanceRole.TARGET
        for r, btn in self._role_buttons.items():
            if btn.isChecked():
                role = r
                break

        return InstanceProfile(
            name=self.name_input.text().strip(),
            url=self.url_input.text().strip(),
            api_key=self.key_input.text().strip(),
            auth_method=auth_method,
            secret_key=secret_key,
            project_folder=self.folder_input.text().strip() or None,
            role=role,
        )

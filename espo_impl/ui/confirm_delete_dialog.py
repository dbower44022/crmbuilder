"""Modal confirmation dialog for destructive entity operations."""

from enum import Enum

from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from espo_impl.core.models import EntityDefinition

# Entity name mapping: YAML natural name → EspoCRM internal name (C-prefixed)
ENTITY_NAME_MAP: dict[str, str] = {
    "Engagement": "CEngagement",
    "Session": "CSessions",
    "Workshop": "CWorkshops",
    "WorkshopAttendance": "CWorkshopAttendee",
    "NpsSurveyResponse": "CNpsSurveyResponse",
}

# Native entities that do not get the C prefix
NATIVE_ENTITIES: set[str] = {
    "Contact", "Account", "Lead", "Opportunity", "Case",
    "Task", "Meeting", "Call", "Email", "Document",
    "Campaign", "TargetList", "User", "Team",
}


def get_espo_entity_name(yaml_name: str) -> str:
    """Map a YAML entity name to the EspoCRM internal name.

    :param yaml_name: Entity name from the YAML program file.
    :returns: EspoCRM internal name (C-prefixed for custom, unchanged for native).
    """
    if yaml_name in NATIVE_ENTITIES:
        return yaml_name
    if yaml_name in ENTITY_NAME_MAP:
        return ENTITY_NAME_MAP[yaml_name]
    return f"C{yaml_name}"


class DeleteDialogResult(Enum):
    """Outcome of the confirmation dialog."""

    CANCELLED = "cancelled"
    SKIP_DELETES = "skip_deletes"
    FULL_REBUILD = "full_rebuild"


class ConfirmDeleteDialog(QDialog):
    """Modal dialog for destructive entity operations.

    Presents two options: skip deletes (field updates only) or proceed
    with full rebuild (destructive). Returns a DeleteDialogResult.

    :param entities: List of entity definitions that contain delete actions.
    :param program_name: Name of the program file being run.
    :param parent: Parent widget.
    """

    def __init__(
        self,
        entities: list[EntityDefinition],
        program_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._entities = entities
        self._program_name = program_name
        self.result = DeleteDialogResult.CANCELLED
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the confirmation dialog layout."""
        self.setWindowTitle("Delete Operations Detected")
        self.setModal(True)
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)

        # Header
        header = QLabel(
            f'The program "{self._program_name}" contains DELETE operations '
            "for the following entities:"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        # Entity list
        for entity in self._entities:
            espo_name = get_espo_entity_name(entity.name)
            action_label = entity.action.value.replace("_", " ")
            bullet = QLabel(f"  \u2022  {espo_name}  ({action_label})")
            layout.addWidget(bullet)

        layout.addSpacing(10)

        # Radio buttons
        self.btn_group = QButtonGroup(self)

        self.skip_radio = QRadioButton(
            "Skip deletes \u2014 update fields only"
        )
        skip_desc = QLabel("  Safe for live instances with existing data.")
        skip_desc.setStyleSheet("color: gray; font-size: 11px;")
        self.skip_radio.setChecked(True)
        self.btn_group.addButton(self.skip_radio)
        layout.addWidget(self.skip_radio)
        layout.addWidget(skip_desc)

        layout.addSpacing(5)

        self.rebuild_radio = QRadioButton(
            "Proceed with deletes \u2014 full rebuild"
        )
        rebuild_desc = QLabel(
            "  Destroys all data in listed entities. Cannot be undone."
        )
        rebuild_desc.setStyleSheet("color: gray; font-size: 11px;")
        self.btn_group.addButton(self.rebuild_radio)
        layout.addWidget(self.rebuild_radio)
        layout.addWidget(rebuild_desc)

        # DELETE confirmation input (initially hidden)
        self.confirm_label = QLabel("  Type DELETE to confirm:")
        self.confirm_input = QLineEdit()
        self.confirm_input.setPlaceholderText("Type DELETE here")
        self.confirm_input.textChanged.connect(self._on_text_changed)
        self.confirm_label.setVisible(False)
        self.confirm_input.setVisible(False)
        layout.addWidget(self.confirm_label)
        layout.addWidget(self.confirm_input)

        # Wire radio button changes
        self.btn_group.buttonToggled.connect(self._on_option_changed)

        layout.addSpacing(10)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self.cancel_btn)

        self.proceed_btn = QPushButton("Proceed")
        self.proceed_btn.clicked.connect(self._on_proceed)
        btn_layout.addWidget(self.proceed_btn)

        layout.addLayout(btn_layout)

    def _on_option_changed(self) -> None:
        """Update UI when the selected option changes."""
        is_rebuild = self.rebuild_radio.isChecked()
        self.confirm_label.setVisible(is_rebuild)
        self.confirm_input.setVisible(is_rebuild)
        if is_rebuild:
            self.proceed_btn.setEnabled(self.confirm_input.text() == "DELETE")
        else:
            self.proceed_btn.setEnabled(True)
            self.confirm_input.clear()

    def _on_text_changed(self, text: str) -> None:
        """Enable Proceed when DELETE is typed in rebuild mode."""
        if self.rebuild_radio.isChecked():
            self.proceed_btn.setEnabled(text == "DELETE")

    def _on_cancel(self) -> None:
        """Handle Cancel button."""
        self.result = DeleteDialogResult.CANCELLED
        self.reject()

    def _on_proceed(self) -> None:
        """Handle Proceed button."""
        if self.skip_radio.isChecked():
            self.result = DeleteDialogResult.SKIP_DELETES
        else:
            self.result = DeleteDialogResult.FULL_REBUILD
        self.accept()

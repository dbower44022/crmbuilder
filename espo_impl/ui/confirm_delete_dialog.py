"""Modal confirmation dialog for destructive entity operations."""

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
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
NATIVE_ENTITIES: set[str] = {"Contact", "Account", "Lead", "Opportunity", "Case", "Task", "Meeting", "Call", "Email", "Document", "Campaign", "TargetList", "User", "Team"}


def get_espo_entity_name(yaml_name: str) -> str:
    """Map a YAML entity name to the EspoCRM internal name.

    :param yaml_name: Entity name from the YAML program file.
    :returns: EspoCRM internal name (C-prefixed for custom, unchanged for native).
    """
    if yaml_name in NATIVE_ENTITIES:
        return yaml_name
    if yaml_name in ENTITY_NAME_MAP:
        return ENTITY_NAME_MAP[yaml_name]
    # Default: apply C prefix
    return f"C{yaml_name}"


class ConfirmDeleteDialog(QDialog):
    """Modal dialog requiring typed confirmation for destructive operations.

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
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the confirmation dialog layout."""
        self.setWindowTitle("Destructive Operation Detected")
        self.setModal(True)
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        # Warning header
        warning = QLabel(
            f'The program "{self._program_name}" contains DELETE operations.\n'
            "The following entities will be permanently deleted:"
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)

        # Entity list
        for entity in self._entities:
            espo_name = get_espo_entity_name(entity.name)
            action_label = entity.action.value.replace("_", " ")
            bullet = QLabel(f"  \u2022  {espo_name}  ({action_label})")
            layout.addWidget(bullet)

        # Warning text
        cannot_undo = QLabel("\nThis cannot be undone.")
        cannot_undo.setStyleSheet("font-weight: bold;")
        layout.addWidget(cannot_undo)

        # Confirmation input
        prompt = QLabel("Type DELETE to confirm:")
        layout.addWidget(prompt)

        self.confirm_input = QLineEdit()
        self.confirm_input.setPlaceholderText("Type DELETE here")
        self.confirm_input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.confirm_input)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.proceed_btn = QPushButton("Proceed")
        self.proceed_btn.setEnabled(False)
        self.proceed_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.proceed_btn)

        layout.addLayout(btn_layout)

    def _on_text_changed(self, text: str) -> None:
        """Enable Proceed button only when DELETE is typed exactly."""
        self.proceed_btn.setEnabled(text == "DELETE")

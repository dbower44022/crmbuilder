"""Instance profile management panel."""

import json
import logging
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from espo_impl.core.models import InstanceProfile
from espo_impl.ui.instance_dialog import InstanceDialog

logger = logging.getLogger(__name__)


class InstancePanel(QWidget):
    """Panel for managing EspoCRM instance profiles.

    :param instances_dir: Directory containing instance profile JSON files.
    :param parent: Parent widget.
    """

    instance_selected = Signal(object)

    def __init__(
        self, instances_dir: Path, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.instances_dir = instances_dir
        self.instances_dir.mkdir(parents=True, exist_ok=True)
        self._profiles: list[InstanceProfile] = []
        self._build_ui()
        self._load_instances()

    def _build_ui(self) -> None:
        """Build the instance panel layout."""
        group = QGroupBox("Instance")
        group_layout = QVBoxLayout()

        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self._on_selection_changed)
        group_layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("+ Add")
        self.edit_btn = QPushButton("Edit")
        self.delete_btn = QPushButton("Delete")
        self.add_btn.clicked.connect(self._on_add)
        self.edit_btn.clicked.connect(self._on_edit)
        self.delete_btn.clicked.connect(self._on_delete)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.delete_btn)
        group_layout.addLayout(btn_layout)

        group_layout.addWidget(QLabel("URL:"))
        self.url_display = QLineEdit()
        self.url_display.setReadOnly(True)
        group_layout.addWidget(self.url_display)

        group_layout.addWidget(QLabel("API Key:"))
        self.key_display = QLineEdit()
        self.key_display.setReadOnly(True)
        self.key_display.setEchoMode(QLineEdit.EchoMode.Password)
        group_layout.addWidget(self.key_display)

        group_layout.addWidget(QLabel("Project Folder:"))
        self.folder_display = QLineEdit()
        self.folder_display.setReadOnly(True)
        group_layout.addWidget(self.folder_display)

        group.setLayout(group_layout)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(group)

    def _load_instances(self) -> None:
        """Load instance profiles from JSON files."""
        self._profiles.clear()
        self.list_widget.clear()

        for path in sorted(self.instances_dir.glob("*.json")):
            if path.stem.endswith("_deploy"):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                profile = InstanceProfile(
                    name=data["name"],
                    url=data["url"],
                    api_key=data["api_key"],
                    auth_method=data.get("auth_method", "api_key"),
                    secret_key=data.get("secret_key"),
                    project_folder=data.get("project_folder"),
                )
                self._profiles.append(profile)
                self.list_widget.addItem(profile.name)
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning("Failed to load instance %s: %s", path, exc)

    def _save_instance(self, profile: InstanceProfile) -> None:
        """Save an instance profile to a JSON file.

        :param profile: Profile to save.
        """
        path = self.instances_dir / f"{profile.slug}.json"
        data = {
            "name": profile.name,
            "url": profile.url,
            "api_key": profile.api_key,
            "auth_method": profile.auth_method,
        }
        if profile.secret_key:
            data["secret_key"] = profile.secret_key
        if profile.project_folder:
            data["project_folder"] = profile.project_folder
        path.write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )

    def _delete_instance_file(self, profile: InstanceProfile) -> None:
        """Delete an instance profile JSON file.

        :param profile: Profile to delete.
        """
        path = self.instances_dir / f"{profile.slug}.json"
        if path.exists():
            path.unlink()

    def _on_selection_changed(self, row: int) -> None:
        """Handle instance list selection change."""
        if 0 <= row < len(self._profiles):
            profile = self._profiles[row]
            self.url_display.setText(profile.url)
            self.key_display.setText(profile.api_key)
            self.folder_display.setText(profile.project_folder or "")
            self.instance_selected.emit(profile)
        else:
            self.url_display.clear()
            self.key_display.clear()
            self.folder_display.clear()
            self.instance_selected.emit(None)

    @staticmethod
    def _ensure_project_structure(folder: Path) -> None:
        """Create standard project subdirectories if they don't exist.

        :param folder: Project folder root path.
        """
        (folder / "programs").mkdir(parents=True, exist_ok=True)
        (folder / "reports").mkdir(parents=True, exist_ok=True)
        (folder / "Implementation Docs").mkdir(parents=True, exist_ok=True)

    def _on_add(self) -> None:
        """Open dialog to add a new instance."""
        dialog = InstanceDialog(self)
        if dialog.exec() == InstanceDialog.DialogCode.Accepted:
            profile = dialog.get_profile()
            self._save_instance(profile)
            if profile.project_folder:
                self._ensure_project_structure(Path(profile.project_folder))
            self._load_instances()
            # Select the newly added instance
            for i, p in enumerate(self._profiles):
                if p.slug == profile.slug:
                    self.list_widget.setCurrentRow(i)
                    self.instance_selected.emit(p)
                    break

    def _on_edit(self) -> None:
        """Open dialog to edit the selected instance."""
        row = self.list_widget.currentRow()
        if row < 0:
            return
        old_profile = self._profiles[row]
        dialog = InstanceDialog(self, old_profile)
        if dialog.exec() == InstanceDialog.DialogCode.Accepted:
            new_profile = dialog.get_profile()
            # Remove old file if slug changed
            if old_profile.slug != new_profile.slug:
                self._delete_instance_file(old_profile)
            self._save_instance(new_profile)
            if new_profile.project_folder:
                self._ensure_project_structure(Path(new_profile.project_folder))
            self._load_instances()
            for i, p in enumerate(self._profiles):
                if p.slug == new_profile.slug:
                    self.list_widget.setCurrentRow(i)
                    self.instance_selected.emit(p)
                    break

    def _on_delete(self) -> None:
        """Delete the selected instance after confirmation."""
        row = self.list_widget.currentRow()
        if row < 0:
            return
        profile = self._profiles[row]
        reply = QMessageBox.question(
            self,
            "Delete Instance",
            f"Delete instance '{profile.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._delete_instance_file(profile)
            self._load_instances()
            self.instance_selected.emit(None)

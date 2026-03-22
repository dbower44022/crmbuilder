"""Program file management panel."""

import logging
import shutil
from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class ProgramPanel(QWidget):
    """Panel for managing YAML program files.

    :param programs_dir: Directory containing YAML program files.
    :param parent: Parent widget.
    """

    program_selected = Signal(object)

    def __init__(
        self, programs_dir: Path, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.programs_dir = programs_dir
        self.programs_dir.mkdir(parents=True, exist_ok=True)
        self._paths: list[Path] = []
        self._build_ui()
        self._load_programs()

    def _build_ui(self) -> None:
        """Build the program panel layout."""
        group = QGroupBox("Program File")
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

        group.setLayout(group_layout)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(group)

    def _load_programs(self) -> None:
        """Load program file list from the programs directory."""
        self._paths.clear()
        self.list_widget.clear()

        for path in sorted(self.programs_dir.glob("*.yaml")):
            self._paths.append(path)
            self.list_widget.addItem(path.name)

        for path in sorted(self.programs_dir.glob("*.yml")):
            if path not in self._paths:
                self._paths.append(path)
                self.list_widget.addItem(path.name)

    def _on_selection_changed(self, row: int) -> None:
        """Handle program list selection change."""
        if 0 <= row < len(self._paths):
            self.program_selected.emit(self._paths[row])
        else:
            self.program_selected.emit(None)

    def _on_add(self) -> None:
        """Import a YAML file via file picker."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Program File",
            "",
            "YAML Files (*.yaml *.yml);;All Files (*)",
        )
        if path:
            source = Path(path)
            dest = self.programs_dir / source.name
            if dest.exists():
                reply = QMessageBox.question(
                    self,
                    "File Exists",
                    f"'{source.name}' already exists. Overwrite?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
            shutil.copy2(source, dest)
            self._load_programs()
            for i, p in enumerate(self._paths):
                if p.name == source.name:
                    self.list_widget.setCurrentRow(i)
                    break

    def _on_edit(self) -> None:
        """Open the selected program file in the system default editor."""
        row = self.list_widget.currentRow()
        if row < 0:
            return
        path = self._paths[row]
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _on_delete(self) -> None:
        """Delete the selected program file after confirmation."""
        row = self.list_widget.currentRow()
        if row < 0:
            return
        path = self._paths[row]
        reply = QMessageBox.question(
            self,
            "Delete Program",
            f"Delete program file '{path.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            path.unlink()
            self._load_programs()
            self.program_selected.emit(None)

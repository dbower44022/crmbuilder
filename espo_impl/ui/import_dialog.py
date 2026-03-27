"""Four-step import wizard dialog."""

import json
import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.import_manager import (
    ImportAction,
    ImportManager,
    ImportReport,
    RecordPlan,
)
from espo_impl.core.models import InstanceProfile
from espo_impl.workers.import_worker import ImportWorker

logger = logging.getLogger(__name__)

# Known alias table for auto-mapping (Section 4 of spec)
CONTACT_ALIAS_TABLE: dict[str, str] = {
    "Contact Name": "(skip)",
    "Preferred Name": "firstName",
    "Email": "emailAddress",
    "SCORE Email": "emailAddress",
    "Phone": "phoneNumber",
    "Personal Email": "(skip)",
    "Mailing Address": "(skip)",
    "Birth Year": "cBirthYear",
    "Gender": "cGender",
}

# EspoCRM field types that are computed or composite and cannot be set directly
NON_WRITABLE_FIELD_TYPES: set[str] = {
    "personName",
    "address",
    "map",
    "foreign",
    "linkParent",
    "autoincrement",
}

ENTITY_OPTIONS = ["Contact"]

OUTPUT_COLORS: dict[str, str] = {
    "green": "#4CAF50",
    "red": "#F44336",
    "yellow": "#FFC107",
    "gray": "#9E9E9E",
    "white": "#D4D4D4",
}


class CheckWorker(QThread):
    """Background worker for the CHECK step (Step 3).

    :param manager: ImportManager instance.
    :param entity: EspoCRM entity name.
    :param records: Source records.
    :param field_mapping: Field mapping dict.
    :param fixed_values: Fixed value dict.
    """

    output_line = Signal(str, str)
    finished = Signal(list)
    error = Signal(str)

    def __init__(
        self,
        manager: ImportManager,
        entity: str,
        records: list[dict],
        field_mapping: dict[str, str],
        fixed_values: dict[str, str],
        source_file: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.manager = manager
        self.entity = entity
        self.records = records
        self.field_mapping = field_mapping
        self.fixed_values = fixed_values
        self.source_file = source_file

    def run(self) -> None:
        """Run CHECK in background thread."""
        try:
            self.manager.emit_line = self.output_line.emit
            plans = self.manager.check(
                self.entity,
                self.records,
                self.field_mapping,
                self.fixed_values,
                self.source_file,
            )
            self.finished.emit(plans)
        except Exception as exc:
            self.error.emit(str(exc))


class ImportDialog(QDialog):
    """Four-step import wizard dialog.

    :param profile: Instance connection profile.
    :param client: Authenticated API client.
    :param parent: Parent widget.
    """

    def __init__(
        self,
        profile: InstanceProfile,
        client: EspoAdminClient,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.profile = profile
        self.client = client

        # State
        self._records: list[dict] = []
        self._source_file: str = ""
        self._espo_fields: dict[str, dict] = {}
        self._field_mapping: dict[str, str] = {}
        self._fixed_values: dict[str, str] = {}
        self._plans: list[RecordPlan] = []
        self._report: ImportReport | None = None
        self._report_log_path: Path | None = None
        self._check_worker: CheckWorker | None = None
        self._import_worker: ImportWorker | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the wizard UI."""
        self.setWindowTitle("Import Data")
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)

        # Step indicator
        self._step_label = QLabel("Step 1 of 4 — Setup")
        self._step_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self._step_label)

        # Stacked widget for steps
        self._stack = QStackedWidget()
        layout.addWidget(self._stack, stretch=1)

        # Build step widgets
        self._step1 = self._build_step1()
        self._step2 = self._build_step2()
        self._step3 = self._build_step3()
        self._step4 = self._build_step4()
        self._stack.addWidget(self._step1)
        self._stack.addWidget(self._step2)
        self._stack.addWidget(self._step3)
        self._stack.addWidget(self._step4)

        # Navigation buttons
        nav_layout = QHBoxLayout()
        self._back_btn = QPushButton("Back")
        self._back_btn.clicked.connect(self._on_back)
        nav_layout.addWidget(self._back_btn)

        nav_layout.addStretch()

        self._next_btn = QPushButton("Next")
        self._next_btn.clicked.connect(self._on_next)
        nav_layout.addWidget(self._next_btn)

        self._import_btn = QPushButton("Import")
        self._import_btn.clicked.connect(self._on_import)
        nav_layout.addWidget(self._import_btn)

        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.accept)
        nav_layout.addWidget(self._close_btn)

        layout.addLayout(nav_layout)

        # Connect entity combo signal and trigger initial field load
        # after all widgets exist
        self._entity_combo.currentTextChanged.connect(self._on_entity_changed)
        self._on_entity_changed(self._entity_combo.currentText())

        self._update_nav_buttons()

    # ── Step 1: Setup ──────────────────────────────────────────────

    def _build_step1(self) -> QWidget:
        """Build the Setup step widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # File selection
        file_group = QGroupBox("JSON File")
        file_layout = QHBoxLayout(file_group)
        self._file_path_edit = QLineEdit()
        self._file_path_edit.setReadOnly(True)
        self._file_path_edit.setPlaceholderText("Select a JSON file...")
        file_layout.addWidget(self._file_path_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._on_browse_file)
        file_layout.addWidget(browse_btn)
        layout.addWidget(file_group)

        self._file_status_label = QLabel("")
        layout.addWidget(self._file_status_label)

        # Entity type
        entity_group = QGroupBox("Entity Type")
        entity_layout = QHBoxLayout(entity_group)
        self._entity_combo = QComboBox()
        self._entity_combo.addItems(ENTITY_OPTIONS)
        entity_layout.addWidget(self._entity_combo)
        self._entity_status_label = QLabel("")
        entity_layout.addWidget(self._entity_status_label)
        layout.addWidget(entity_group)

        # Fixed-value fields
        fixed_group = QGroupBox("Fixed-Value Fields")
        fixed_layout = QVBoxLayout(fixed_group)

        self._fixed_table = QTableWidget(0, 3)
        self._fixed_table.setHorizontalHeaderLabels(["Field", "Value", ""])
        header = self._fixed_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._fixed_table.verticalHeader().setVisible(False)
        fixed_layout.addWidget(self._fixed_table)

        add_fixed_btn = QPushButton("+ Add Field")
        add_fixed_btn.clicked.connect(self._on_add_fixed_row)
        fixed_layout.addWidget(add_fixed_btn)
        layout.addWidget(fixed_group)

        layout.addStretch()
        return widget

    def _on_browse_file(self) -> None:
        """Open file picker for JSON file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select JSON File", "", "JSON Files (*.json)"
        )
        if not path:
            return

        self._file_path_edit.setText(path)
        self._source_file = Path(path).name

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            self._file_status_label.setText(f"Error: {exc}")
            self._file_status_label.setStyleSheet("color: red;")
            self._records = []
            self._update_nav_buttons()
            return

        # Detect records array
        self._records = self._detect_records(data)
        if self._records:
            self._file_status_label.setText(
                f"{len(self._records)} records found"
            )
            self._file_status_label.setStyleSheet("color: green;")
        else:
            self._file_status_label.setText(
                "No records found — expected a list of objects with 'fields' key"
            )
            self._file_status_label.setStyleSheet("color: red;")

        self._update_nav_buttons()

    def _detect_records(self, data: Any) -> list[dict]:
        """Find the records array in the JSON data.

        :param data: Parsed JSON.
        :returns: List of record dicts, or empty list.
        """
        if not isinstance(data, dict):
            return []
        for _key, value in data.items():
            if (
                isinstance(value, list)
                and value
                and isinstance(value[0], dict)
                and "fields" in value[0]
            ):
                return value
        return []

    def _on_entity_changed(self, entity: str) -> None:
        """Fetch field list when entity type changes."""
        if not entity:
            return

        self._entity_status_label.setText("Loading fields...")
        self._entity_status_label.setStyleSheet("color: gray;")

        status, body = self.client.get_entity_field_list(entity)
        if status == 200 and isinstance(body, dict):
            self._espo_fields = body
            count = len(body)
            self._entity_status_label.setText(f"{count} fields loaded")
            self._entity_status_label.setStyleSheet("color: green;")
            self._refresh_fixed_field_combos()
        else:
            self._espo_fields = {}
            self._entity_status_label.setText(
                f"Failed to load fields (HTTP {status})"
            )
            self._entity_status_label.setStyleSheet("color: red;")

        self._update_nav_buttons()

    def _on_add_fixed_row(self) -> None:
        """Add a new row to the fixed-value fields table."""
        if not self._espo_fields:
            self._entity_status_label.setText(
                "Select an entity type first — fields must be loaded"
            )
            self._entity_status_label.setStyleSheet("color: red;")
            return

        row = self._fixed_table.rowCount()
        self._fixed_table.insertRow(row)

        combo = self._build_espo_field_combo(exclude_fixed=False)
        self._fixed_table.setCellWidget(row, 0, combo)

        value_edit = QLineEdit()
        self._fixed_table.setCellWidget(row, 1, value_edit)

        remove_btn = QPushButton("\u2715")
        remove_btn.setFixedWidth(30)
        remove_btn.clicked.connect(
            lambda _checked, b=remove_btn: self._remove_fixed_row(b)
        )
        self._fixed_table.setCellWidget(row, 2, remove_btn)

    def _remove_fixed_row(self, btn: QPushButton) -> None:
        """Remove the fixed-value row containing the given button."""
        for r in range(self._fixed_table.rowCount()):
            if self._fixed_table.cellWidget(r, 2) is btn:
                self._fixed_table.removeRow(r)
                return

    def _refresh_fixed_field_combos(self) -> None:
        """Refresh field combos in the fixed-value table after fields load."""
        for row in range(self._fixed_table.rowCount()):
            old_combo = self._fixed_table.cellWidget(row, 0)
            old_text = old_combo.currentData() if old_combo else None
            combo = self._build_espo_field_combo(exclude_fixed=False)
            if old_text:
                idx = combo.findData(old_text)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            self._fixed_table.setCellWidget(row, 0, combo)

    @staticmethod
    def _field_display(label: str, name: str) -> str:
        """Build a display string for a field, avoiding redundancy.

        Shows just the label when it matches the internal name.
        Shows "Label (internal_name)" when they differ.

        :param label: Human-readable field label.
        :param name: Internal EspoCRM field name.
        :returns: Display string.
        """
        if label.lower().replace(" ", "") == name.lower():
            return label
        return f"{label} ({name})"

    def _build_espo_field_combo(
        self, exclude_fixed: bool = True
    ) -> QComboBox:
        """Build a searchable QComboBox with EspoCRM fields sorted by label.

        :param exclude_fixed: If True, exclude fields used in fixed-value table.
        :returns: Populated QComboBox with type-to-filter.
        """
        combo = QComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        combo.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        combo.completer().setCompletionMode(
            combo.completer().CompletionMode.PopupCompletion
        )
        used_fields = self._get_fixed_field_names() if exclude_fixed else set()

        items: list[tuple[str, str]] = []
        for name, meta in self._espo_fields.items():
            if name in used_fields:
                continue
            field_type = meta.get("type", "")
            if field_type in NON_WRITABLE_FIELD_TYPES:
                continue
            if meta.get("readOnly") or meta.get("notStorable"):
                continue
            label = meta.get("label", name)
            items.append((self._field_display(label, name), name))

        items.sort(key=lambda x: x[0].lower())
        for display, data in items:
            combo.addItem(display, data)

        return combo

    def _get_fixed_field_names(self) -> set[str]:
        """Get the set of EspoCRM field names used in fixed-value table."""
        names: set[str] = set()
        for row in range(self._fixed_table.rowCount()):
            combo = self._fixed_table.cellWidget(row, 0)
            if combo and isinstance(combo, QComboBox):
                data = combo.currentData()
                if data:
                    names.add(data)
        return names

    def _collect_fixed_values(self) -> dict[str, str]:
        """Collect fixed values from the table."""
        values: dict[str, str] = {}
        for row in range(self._fixed_table.rowCount()):
            combo = self._fixed_table.cellWidget(row, 0)
            value_edit = self._fixed_table.cellWidget(row, 1)
            if (
                combo
                and isinstance(combo, QComboBox)
                and value_edit
                and isinstance(value_edit, QLineEdit)
            ):
                field_name = combo.currentData()
                value = value_edit.text().strip()
                if field_name and value:
                    values[field_name] = value
        return values

    # ── Step 2: Field Mapping ──────────────────────────────────────

    def _build_step2(self) -> QWidget:
        """Build the Field Mapping step widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Mapping table
        mapping_group = QGroupBox("Field Mapping")
        mapping_layout = QVBoxLayout(mapping_group)

        self._mapping_table = QTableWidget(0, 2)
        self._mapping_table.setHorizontalHeaderLabels(
            ["JSON Field", "EspoCRM Field"]
        )
        header = self._mapping_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._mapping_table.verticalHeader().setVisible(False)
        mapping_layout.addWidget(self._mapping_table)
        layout.addWidget(mapping_group, stretch=3)

        # Unmapped fields
        unmapped_group = QGroupBox("Fields with no EspoCRM mapping")
        unmapped_layout = QVBoxLayout(unmapped_group)
        self._unmapped_list = QListWidget()
        unmapped_layout.addWidget(self._unmapped_list)
        layout.addWidget(unmapped_group, stretch=1)

        return widget

    def _populate_mapping_table(self) -> None:
        """Populate the mapping table from JSON keys and EspoCRM fields."""
        self._fixed_values = self._collect_fixed_values()
        fixed_field_names = set(self._fixed_values.keys())

        # Collect all unique JSON field keys
        json_keys: set[str] = set()
        for record in self._records:
            json_keys.update(record.get("fields", {}).keys())
        sorted_keys = sorted(json_keys, key=str.lower)

        self._mapping_table.setRowCount(len(sorted_keys))

        # Build label→name and normalized lookup for auto-mapping
        label_to_name: dict[str, str] = {}
        normalized_to_name: dict[str, str] = {}
        for name, meta in self._espo_fields.items():
            label = meta.get("label", name)
            label_to_name[label.lower()] = name
            normalized = label.lower().replace(" ", "").replace("-", "").replace("_", "")
            normalized_to_name[normalized] = name

        for row, json_key in enumerate(sorted_keys):
            # JSON field column (read-only)
            item = QTableWidgetItem(json_key)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._mapping_table.setItem(row, 0, item)

            # EspoCRM field combo (searchable)
            combo = QComboBox()
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            combo.completer().setFilterMode(Qt.MatchFlag.MatchContains)
            combo.completer().setCompletionMode(
                combo.completer().CompletionMode.PopupCompletion
            )
            combo.addItem("(skip)", "(skip)")

            items: list[tuple[str, str]] = []
            for name, meta in self._espo_fields.items():
                if name in fixed_field_names:
                    continue
                field_type = meta.get("type", "")
                if field_type in NON_WRITABLE_FIELD_TYPES:
                    continue
                if meta.get("readOnly") or meta.get("notStorable"):
                    continue
                label = meta.get("label", name)
                items.append((self._field_display(label, name), name))
            items.sort(key=lambda x: x[0].lower())
            for display, data in items:
                combo.addItem(display, data)

            # Auto-mapping
            auto_mapped = self._auto_map(
                json_key, label_to_name, normalized_to_name
            )
            if auto_mapped and auto_mapped not in fixed_field_names:
                idx = combo.findData(auto_mapped)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

            combo.currentIndexChanged.connect(self._on_mapping_changed)
            self._mapping_table.setCellWidget(row, 1, combo)

        self._update_unmapped_list()

    def _auto_map(
        self,
        json_key: str,
        label_to_name: dict[str, str],
        normalized_to_name: dict[str, str],
    ) -> str | None:
        """Attempt to auto-map a JSON key to an EspoCRM field.

        :param json_key: JSON field key.
        :param label_to_name: Lowercase label → field name lookup.
        :param normalized_to_name: Normalized label → field name lookup.
        :returns: EspoCRM field name or None.
        """
        # 1. Known alias table
        if json_key in CONTACT_ALIAS_TABLE:
            return CONTACT_ALIAS_TABLE[json_key]

        # 2. Exact label match (case-insensitive)
        lower_key = json_key.lower()
        if lower_key in label_to_name:
            return label_to_name[lower_key]

        # 3. Normalized match
        normalized = lower_key.replace(" ", "").replace("-", "").replace("_", "")
        if normalized in normalized_to_name:
            return normalized_to_name[normalized]

        return None

    def _on_mapping_changed(self) -> None:
        """Handle mapping dropdown change."""
        self._update_unmapped_list()
        self._update_nav_buttons()

    def _update_unmapped_list(self) -> None:
        """Update the unmapped fields list."""
        self._unmapped_list.clear()
        for row in range(self._mapping_table.rowCount()):
            combo = self._mapping_table.cellWidget(row, 1)
            if combo and isinstance(combo, QComboBox):
                if combo.currentData() == "(skip)":
                    item = self._mapping_table.item(row, 0)
                    if item:
                        self._unmapped_list.addItem(item.text())

    def _collect_field_mapping(self) -> dict[str, str]:
        """Collect the field mapping from the table."""
        mapping: dict[str, str] = {}
        for row in range(self._mapping_table.rowCount()):
            json_item = self._mapping_table.item(row, 0)
            combo = self._mapping_table.cellWidget(row, 1)
            if json_item and combo and isinstance(combo, QComboBox):
                mapping[json_item.text()] = combo.currentData()
        return mapping

    def _has_any_mapping(self) -> bool:
        """Check if at least one field is mapped (not skip)."""
        for row in range(self._mapping_table.rowCount()):
            combo = self._mapping_table.cellWidget(row, 1)
            if combo and isinstance(combo, QComboBox):
                if combo.currentData() != "(skip)":
                    return True
        return False

    # ── Step 3: Preview (CHECK) ────────────────────────────────────

    def _build_step3(self) -> QWidget:
        """Build the Preview step widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Progress area
        self._check_progress = QProgressBar()
        self._check_progress.setRange(0, 0)
        layout.addWidget(self._check_progress)

        self._check_status_label = QLabel("Preparing check...")
        layout.addWidget(self._check_status_label)

        # Preview scroll area
        self._preview_scroll = QScrollArea()
        self._preview_scroll.setWidgetResizable(True)
        self._preview_content = QWidget()
        self._preview_layout = QVBoxLayout(self._preview_content)
        self._preview_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._preview_scroll.setWidget(self._preview_content)
        layout.addWidget(self._preview_scroll, stretch=1)

        # Summary
        self._preview_summary = QLabel("")
        self._preview_summary.setStyleSheet(
            "font-weight: bold; padding: 8px;"
        )
        layout.addWidget(self._preview_summary)

        return widget

    def _run_check(self) -> None:
        """Start the CHECK operation in a background thread."""
        self._check_progress.setVisible(True)
        self._check_status_label.setText(
            f"Checking {len(self._records)} records..."
        )
        self._plans = []

        # Clear preview
        while self._preview_layout.count():
            child = self._preview_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._preview_summary.setText("")

        self._field_mapping = self._collect_field_mapping()
        self._fixed_values = self._collect_fixed_values()

        manager = ImportManager(self.client)
        self._check_worker = CheckWorker(
            manager,
            self._entity_combo.currentText(),
            self._records,
            self._field_mapping,
            self._fixed_values,
            self._source_file,
            parent=self,
        )
        self._check_worker.output_line.connect(self._on_check_output)
        self._check_worker.finished.connect(self._on_check_finished)
        self._check_worker.error.connect(self._on_check_error)
        self._check_worker.start()

        self._update_nav_buttons()

    def _on_check_output(self, message: str, color: str) -> None:
        """Update check status from worker output."""
        self._check_status_label.setText(message)

    def _on_check_finished(self, plans: list[RecordPlan]) -> None:
        """Handle CHECK completion."""
        self._plans = plans
        self._check_progress.setVisible(False)
        self._check_status_label.setText("Check complete.")
        self._check_worker = None

        # Build preview
        for i, plan in enumerate(plans):
            self._add_preview_row(i, plan)

        # Summary counts
        creates = sum(1 for p in plans if p.action == ImportAction.CREATE)
        updates = sum(1 for p in plans if p.action == ImportAction.UPDATE)
        skips = sum(1 for p in plans if p.action == ImportAction.SKIP)
        errors = sum(1 for p in plans if p.action == ImportAction.ERROR)

        self._preview_summary.setText(
            f"To create: {creates}  |  "
            f"To update: {updates}  |  "
            f"To skip: {skips}  |  "
            f"Errors: {errors}"
        )

        self._update_nav_buttons()

    def _on_check_error(self, error_msg: str) -> None:
        """Handle CHECK failure."""
        self._check_progress.setVisible(False)
        self._check_status_label.setText(f"Check failed: {error_msg}")
        self._check_status_label.setStyleSheet("color: red;")
        self._check_worker = None
        self._update_nav_buttons()

    def _add_preview_row(self, index: int, plan: RecordPlan) -> None:
        """Add a preview row for a single record plan."""
        color_map = {
            ImportAction.CREATE: "#4CAF50",
            ImportAction.UPDATE: "#2196F3",
            ImportAction.SKIP: "#9E9E9E",
            ImportAction.ERROR: "#F44336",
        }
        color = color_map.get(plan.action, "#D4D4D4")

        email_str = f" ({plan.email})" if plan.email else ""
        header = (
            f"<b>Record {index + 1}</b> \u2014 "
            f"{plan.source_name}{email_str}"
        )
        action_text = f"<span style='color:{color}'>"
        action_text += f"<b>{plan.action.value.upper()}</b>"
        action_text += "</span>"

        details_parts: list[str] = []
        if plan.action == ImportAction.ERROR:
            details_parts.append(f"<i>{plan.error_message}</i>")
        else:
            if plan.fields_to_set:
                fields_str = ", ".join(plan.fields_to_set.keys())
                label = "Will set" if plan.action == ImportAction.CREATE else "Will patch"
                details_parts.append(f"{label}: {fields_str}")
            if plan.fields_skipped:
                details_parts.append(
                    f"Will skip (already has value): "
                    f"{', '.join(plan.fields_skipped)}"
                )

        text = f"{header}<br>Action: {action_text}"
        if details_parts:
            text += "<br>" + "<br>".join(details_parts)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setStyleSheet(
            "padding: 6px; border-bottom: 1px solid #444;"
        )
        self._preview_layout.addWidget(label)

    # ── Step 4: Execute (ACT) ──────────────────────────────────────

    def _build_step4(self) -> QWidget:
        """Build the Execute step widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Progress bar
        self._import_progress = QProgressBar()
        self._import_progress.setRange(0, 0)
        layout.addWidget(self._import_progress)

        # Output panel (matches main window style)
        self._output_edit = QTextEdit()
        self._output_edit.setReadOnly(True)
        self._output_edit.setFont(QFont("Monospace", 10))
        self._output_edit.setStyleSheet(
            "QTextEdit { background-color: #1e1e1e; color: #d4d4d4; }"
        )
        layout.addWidget(self._output_edit, stretch=1)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        self._view_report_btn = QPushButton("View Report")
        self._view_report_btn.clicked.connect(self._on_view_report)
        btn_layout.addWidget(self._view_report_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return widget

    def _run_import(self) -> None:
        """Start the ACT operation in a background thread."""
        self._import_progress.setVisible(True)
        self._output_edit.clear()

        actionable = [
            p for p in self._plans
            if p.action in (ImportAction.CREATE, ImportAction.UPDATE)
        ]

        self._append_output(
            f"--- IMPORT started ({len(actionable)} records) ---", "white"
        )

        self._import_worker = ImportWorker(
            self.client,
            self._entity_combo.currentText(),
            self._plans,
            self._source_file,
            parent=self,
        )
        self._import_worker.output_line.connect(self._on_import_output)
        self._import_worker.finished_ok.connect(self._on_import_finished)
        self._import_worker.finished_error.connect(self._on_import_error)
        self._import_worker.start()

        self._update_nav_buttons()

    def _on_import_output(self, message: str, color: str) -> None:
        """Forward worker output to the output panel."""
        self._append_output(message, color)

    def _on_import_finished(self, report: ImportReport) -> None:
        """Handle import completion."""
        self._report = report
        self._import_progress.setVisible(False)
        self._import_worker = None

        # Emit summary
        self._append_output("", "white")
        self._append_output("===========================================", "white")
        self._append_output("IMPORT SUMMARY", "white")
        self._append_output("===========================================", "white")
        self._append_output(
            f"Total records processed : {report.total}", "white"
        )
        self._append_output(
            f"  Created               : {report.created}",
            "green" if report.created else "white",
        )
        self._append_output(
            f"  Updated               : {report.updated}",
            "green" if report.updated else "white",
        )
        self._append_output(
            f"  Skipped               : {report.skipped}",
            "gray",
        )
        self._append_output(
            f"  Errors                : {report.errors}",
            "red" if report.errors else "white",
        )
        self._append_output("===========================================", "white")

        # Write report files
        if self.profile.reports_dir:
            reports_dir = self.profile.reports_dir
        else:
            reports_dir = Path("reports")

        try:
            manager = ImportManager(self.client)
            log_path, json_path = manager.write_report(
                report, reports_dir, self._source_file
            )
            self._report_log_path = log_path
            self._append_output("", "white")
            self._append_output("Reports written to:", "white")
            self._append_output(f"  {log_path}", "white")
            self._append_output(f"  {json_path}", "white")
        except Exception as exc:
            self._append_output(
                f"[ERROR] Failed to write reports: {exc}", "red"
            )

        self._update_nav_buttons()

    def _on_import_error(self, error_msg: str) -> None:
        """Handle import failure."""
        self._import_progress.setVisible(False)
        self._append_output(
            f"[ERROR] Import failed: {error_msg}", "red"
        )
        self._import_worker = None
        self._update_nav_buttons()

    def _on_view_report(self) -> None:
        """Open the import report log file."""
        if not self._report_log_path:
            self._append_output(
                "[INFO] No report yet — run an import first", "yellow"
            )
            return
        if not self._report_log_path.exists():
            self._append_output(
                f"[INFO] Report file not found: {self._report_log_path}",
                "yellow",
            )
            return
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self._report_log_path))
        )

    def _append_output(self, message: str, color: str = "white") -> None:
        """Append a color-coded line to the output panel.

        :param message: Text to display.
        :param color: Color key.
        """
        cursor = self._output_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        hex_color = OUTPUT_COLORS.get(color, OUTPUT_COLORS["white"])
        fmt.setForeground(QColor(hex_color))
        fmt.setFont(QFont("Monospace", 10))

        if not self._output_edit.document().isEmpty():
            cursor.insertText("\n", fmt)
        cursor.insertText(message, fmt)

        self._output_edit.setTextCursor(cursor)
        self._output_edit.ensureCursorVisible()

    # ── Navigation ─────────────────────────────────────────────────

    def _current_step(self) -> int:
        """Return the current step index (0-based)."""
        return self._stack.currentIndex()

    def _on_back(self) -> None:
        """Navigate to the previous step."""
        if self._is_operation_active():
            return
        step = self._current_step()
        if step > 0:
            self._stack.setCurrentIndex(step - 1)
            self._update_step_label()
            self._update_nav_buttons()

    def _on_next(self) -> None:
        """Navigate to the next step."""
        if self._is_operation_active():
            return

        step = self._current_step()

        if step == 0:
            if not self._records:
                self._file_status_label.setText(
                    "Select a JSON file first"
                )
                self._file_status_label.setStyleSheet("color: red;")
                return
            if not self._espo_fields:
                self._entity_status_label.setText(
                    "Entity fields must be loaded — check your connection"
                )
                self._entity_status_label.setStyleSheet("color: red;")
                return
            self._stack.setCurrentIndex(1)
            self._populate_mapping_table()
        elif step == 1:
            if not self._has_any_mapping():
                return
            self._stack.setCurrentIndex(2)
            self._run_check()
        else:
            self._stack.setCurrentIndex(step + 1)

        self._update_step_label()
        self._update_nav_buttons()

    def _on_import(self) -> None:
        """Start the import (transition to Step 4)."""
        if self._is_operation_active():
            return
        has_actionable = any(
            p.action in (ImportAction.CREATE, ImportAction.UPDATE)
            for p in self._plans
        )
        if not has_actionable:
            return
        self._stack.setCurrentIndex(3)
        self._update_step_label()
        self._update_nav_buttons()
        self._run_import()

    def _update_step_label(self) -> None:
        """Update the step indicator label."""
        labels = [
            "Step 1 of 4 \u2014 Setup",
            "Step 2 of 4 \u2014 Field Mapping",
            "Step 3 of 4 \u2014 Preview",
            "Step 4 of 4 \u2014 Import",
        ]
        step = self._current_step()
        self._step_label.setText(labels[step])

    def _is_operation_active(self) -> bool:
        """Check if a background operation is running."""
        return (
            (self._check_worker is not None and self._check_worker.isRunning())
            or (self._import_worker is not None and self._import_worker.isRunning())
        )

    def _update_nav_buttons(self) -> None:
        """Update navigation button visibility."""
        if not hasattr(self, "_back_btn"):
            return
        step = self._current_step()

        # Back: visible on steps 1-2
        self._back_btn.setVisible(step > 0 and step < 3)

        # Next: visible on steps 0-1
        self._next_btn.setVisible(step < 2)

        # Import: visible on step 2, update label with count
        self._import_btn.setVisible(step == 2)
        if step == 2 and self._plans:
            count = sum(
                1 for p in self._plans
                if p.action in (ImportAction.CREATE, ImportAction.UPDATE)
            )
            if count:
                self._import_btn.setText(f"Import ({count} records)")
            else:
                self._import_btn.setText("Import")

        # Close: visible on step 3
        self._close_btn.setVisible(step == 3)

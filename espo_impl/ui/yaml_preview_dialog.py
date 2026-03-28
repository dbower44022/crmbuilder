"""Sortable grid preview of a selected YAML program file."""

import logging
from pathlib import Path

from PySide6.QtCore import QSortFilterProxyModel, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTabWidget,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from espo_impl.core.config_loader import ConfigLoader
from espo_impl.core.models import ProgramFile

logger = logging.getLogger(__name__)


class MultiColumnSortProxy(QSortFilterProxyModel):
    """Proxy model supporting multi-column sort.

    Click a column header to sort by that column. Hold Shift and click
    another header to add a secondary (then tertiary, etc.) sort key.
    Clicking without Shift resets to single-column sort.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sort_keys: list[tuple[int, Qt.SortOrder]] = []

    def add_sort_column(
        self, column: int, order: Qt.SortOrder, multi: bool
    ) -> None:
        """Add or replace a sort column.

        :param column: Column index.
        :param order: Sort order.
        :param multi: If True, append to existing sort keys (Shift-click).
        """
        if not multi:
            self._sort_keys = [(column, order)]
        else:
            # Remove this column if already present, then append
            self._sort_keys = [
                (c, o) for c, o in self._sort_keys if c != column
            ]
            self._sort_keys.append((column, order))
        self.invalidate()

    def lessThan(self, left, right):
        """Compare two rows using all sort keys."""
        if not self._sort_keys:
            return super().lessThan(left, right)

        source = self.sourceModel()
        left_row = left.row()
        right_row = right.row()

        for col, order in self._sort_keys:
            left_val = source.item(left_row, col)
            right_val = source.item(right_row, col)
            left_text = left_val.text() if left_val else ""
            right_text = right_val.text() if right_val else ""

            if left_text != right_text:
                result = left_text.lower() < right_text.lower()
                # If this key's order is descending, invert the comparison
                # (the proxy applies the top-level order, so we compensate
                # for secondary keys that differ from the primary order)
                if len(self._sort_keys) > 1 and col != self._sort_keys[0][0]:
                    primary_order = self._sort_keys[0][1]
                    if order != primary_order:
                        result = not result
                return result

        return False

    @property
    def sort_description(self) -> str:
        """Human-readable description of current sort keys."""
        if not self._sort_keys:
            return ""
        parts = []
        for col, order in self._sort_keys:
            source = self.sourceModel()
            name = source.headerData(
                col, Qt.Orientation.Horizontal
            ) if source else str(col)
            arrow = "\u25b2" if order == Qt.SortOrder.AscendingOrder else "\u25bc"
            parts.append(f"{name} {arrow}")
        return "Sort: " + ", then ".join(parts)


class SortableTreeView(QTreeView):
    """QTreeView that tracks Shift-click for multi-column sorting."""

    def __init__(
        self,
        proxy: MultiColumnSortProxy,
        sort_label: QLabel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._proxy = proxy
        self._sort_label = sort_label
        self._last_clicked_col: int | None = None
        self._last_order = Qt.SortOrder.AscendingOrder

        self.header().setSectionsClickable(True)
        self.header().sectionClicked.connect(self._on_header_clicked)

    def _on_header_clicked(self, logical_index: int) -> None:
        """Handle header click with Shift detection."""
        from PySide6.QtWidgets import QApplication

        modifiers = QApplication.keyboardModifiers()
        multi = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)

        # Toggle order if clicking the same column
        if logical_index == self._last_clicked_col and not multi:
            if self._last_order == Qt.SortOrder.AscendingOrder:
                order = Qt.SortOrder.DescendingOrder
            else:
                order = Qt.SortOrder.AscendingOrder
        else:
            order = Qt.SortOrder.AscendingOrder

        self._last_clicked_col = logical_index
        self._last_order = order

        self._proxy.add_sort_column(logical_index, order, multi)
        self._proxy.sort(
            self._proxy._sort_keys[0][0],
            self._proxy._sort_keys[0][1],
        )
        self._sort_label.setText(self._proxy.sort_description)


class YamlPreviewDialog(QDialog):
    """Dialog showing a YAML program file's contents in sortable tables.

    :param programs_dir: Directory containing YAML program files.
    :param parent: Parent widget.
    """

    def __init__(
        self,
        programs_dir: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.programs_dir = programs_dir
        self._loader = ConfigLoader()
        self._current_program: ProgramFile | None = None
        self._yaml_files: list[Path] = sorted(programs_dir.glob("*.yaml"))

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the dialog UI."""
        self.setWindowTitle("YAML Preview")
        self.setMinimumSize(1000, 600)

        layout = QVBoxLayout(self)

        # File selector
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("File:"))
        self._file_combo = QComboBox()
        for path in self._yaml_files:
            self._file_combo.addItem(path.name, str(path))
        self._file_combo.currentIndexChanged.connect(self._on_file_selected)
        selector_layout.addWidget(self._file_combo, stretch=1)

        self._tooltip_check = QCheckBox("Add Description to Tool Tips")
        self._tooltip_check.setChecked(False)
        self._tooltip_check.toggled.connect(self._on_tooltip_toggled)
        selector_layout.addWidget(self._tooltip_check)

        layout.addLayout(selector_layout)

        # Track models for tooltip updates
        self._models: list[QStandardItemModel] = []

        # Summary line
        self._summary_label = QLabel("")
        self._summary_label.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(self._summary_label)

        # Error label (hidden unless parse fails)
        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: red; padding: 4px;")
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        # Tabs container
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs, stretch=1)

        # Hint
        hint = QLabel("Click column header to sort. Shift-click to add secondary sort.")
        hint.setStyleSheet("color: gray; font-size: 11px; padding: 2px;")
        layout.addWidget(hint)

        # Load the first file
        if self._yaml_files:
            self._load_file(self._yaml_files[0])

    def _on_file_selected(self, index: int) -> None:
        """Handle file combo selection change."""
        if index < 0 or index >= len(self._yaml_files):
            return
        self._load_file(self._yaml_files[index])

    def _load_file(self, path: Path) -> None:
        """Load and display a YAML file."""
        self._error_label.setVisible(False)

        try:
            program = self._loader.load_program(path)
        except ValueError as exc:
            self._error_label.setText(f"Error loading {path.name}: {exc}")
            self._error_label.setVisible(True)
            self._summary_label.setText("")
            self._tabs.clear()
            self._current_program = None
            return

        self._current_program = program
        self._rebuild_tabs(path.name, program)

    def _on_tooltip_toggled(self, checked: bool) -> None:
        """Toggle description tooltips on all field table models."""
        for model in self._models:
            for row in range(model.rowCount()):
                for col in range(model.columnCount()):
                    item = model.item(row, col)
                    if item is None:
                        continue
                    desc = item.data(Qt.ItemDataRole.UserRole)
                    if checked and desc:
                        item.setToolTip(desc)
                    else:
                        item.setToolTip("")

    def _rebuild_tabs(self, filename: str, program: ProgramFile) -> None:
        """Rebuild the tab widget for a loaded program."""
        self._tabs.clear()
        self._models.clear()

        total_entities = len(program.entities)
        total_fields = sum(len(e.fields) for e in program.entities)
        total_rels = len(program.relationships)

        self._summary_label.setText(
            f"{filename}  \u2014  "
            f"{total_entities} entities, "
            f"{total_fields} fields, "
            f"{total_rels} relationships"
        )

        # Fields tab
        fields_table = self._build_fields_table(program)
        self._tabs.addTab(fields_table, f"Fields ({total_fields})")

        # Entities tab
        entities_table = self._build_entities_table(program)
        self._tabs.addTab(entities_table, f"Entities ({total_entities})")

        # Relationships tab
        if total_rels:
            rels_table = self._build_relationships_table(program)
            self._tabs.addTab(rels_table, f"Relationships ({total_rels})")

    def _build_fields_table(self, program: ProgramFile) -> QWidget:
        """Build the fields table for a program."""
        columns = [
            "Entity", "Field", "Type", "Label",
            "Required", "Default", "Category",
            "Options", "Option Descriptions",
            "Tooltip", "Description",
        ]

        rows: list[list[str]] = []
        tooltips: list[str] = []
        for entity in program.entities:
            for field in entity.fields:
                options_str = ""
                if field.options:
                    options_str = ", ".join(field.options)
                opt_desc_str = ""
                if field.optionDescriptions:
                    opt_desc_str = "; ".join(
                        f"{k}: {v}" for k, v in field.optionDescriptions.items()
                    )
                rows.append([
                    entity.name,
                    field.name,
                    field.type,
                    field.label,
                    "Yes" if field.required else "",
                    field.default or "",
                    field.category or "",
                    options_str,
                    opt_desc_str[:150],
                    (field.tooltip or "")[:120],
                    (field.description or "").strip().replace("\n", " ")[:120],
                ])
                tooltips.append(
                    (field.description or "").strip()
                )

        return self._build_sortable_table(columns, rows, tooltips)

    def _build_entities_table(self, program: ProgramFile) -> QWidget:
        """Build the entities table for a program."""
        columns = [
            "Entity", "Action", "Type",
            "Label (Singular)", "Label (Plural)",
            "Fields", "Layouts", "Stream", "Description",
        ]

        rows: list[list[str]] = []
        for entity in program.entities:
            rows.append([
                entity.name,
                entity.action.value,
                entity.type or "",
                entity.labelSingular or "",
                entity.labelPlural or "",
                str(len(entity.fields)),
                str(len(entity.layouts)),
                "Yes" if entity.stream else "",
                (entity.description or "").strip().replace("\n", " ")[:120],
            ])

        return self._build_sortable_table(columns, rows)

    def _build_relationships_table(self, program: ProgramFile) -> QWidget:
        """Build the relationships table for a program."""
        columns = [
            "Name", "Entity", "Foreign Entity",
            "Link Type", "Link", "Link Foreign",
            "Label", "Label Foreign", "Description",
        ]

        rows: list[list[str]] = []
        for rel in program.relationships:
            rows.append([
                rel.name,
                rel.entity,
                rel.entity_foreign,
                rel.link_type,
                rel.link,
                rel.link_foreign,
                rel.label,
                rel.label_foreign,
                (rel.description or "").strip().replace("\n", " ")[:120],
            ])

        return self._build_sortable_table(columns, rows)

    def _build_sortable_table(
        self,
        columns: list[str],
        rows: list[list[str]],
        tooltips: list[str] | None = None,
    ) -> QWidget:
        """Build a multi-column sortable table with resizable columns.

        :param columns: Column headers.
        :param rows: Row data (list of lists).
        :param tooltips: Optional per-row tooltip text (stored for checkbox toggle).
        :returns: Widget containing the table.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Model
        model = QStandardItemModel(len(rows), len(columns))
        model.setHorizontalHeaderLabels(columns)

        for row_idx, row_data in enumerate(rows):
            for col_idx, value in enumerate(row_data):
                item = QStandardItem(value)
                item.setEditable(False)
                # Store full tooltip text in UserRole for later toggle
                if tooltips and row_idx < len(tooltips) and tooltips[row_idx]:
                    item.setData(tooltips[row_idx], Qt.ItemDataRole.UserRole)
                model.setItem(row_idx, col_idx, item)

        self._models.append(model)

        # Proxy for multi-column sorting
        proxy = MultiColumnSortProxy(widget)
        proxy.setSourceModel(model)

        # Sort label
        sort_label = QLabel("")
        sort_label.setStyleSheet("color: gray; font-size: 11px; padding: 2px;")

        # View
        view = SortableTreeView(proxy, sort_label, widget)
        view.setModel(proxy)
        view.setRootIsDecorated(False)
        view.setAlternatingRowColors(True)
        view.setUniformRowHeights(True)

        # Resizable columns — fit to content initially, then user can drag
        header = view.header()
        header.setStretchLastSection(True)
        for col in range(len(columns)):
            header.setSectionResizeMode(
                col, QHeaderView.ResizeMode.Interactive
            )
        view.resizeColumnToContents(0)
        for col in range(len(columns)):
            view.resizeColumnToContents(col)

        layout.addWidget(view)

        # Bottom bar
        bottom = QHBoxLayout()
        count_label = QLabel(f"{len(rows)} rows")
        count_label.setStyleSheet("color: gray; padding: 2px;")
        bottom.addWidget(count_label)
        bottom.addStretch()
        bottom.addWidget(sort_label)
        layout.addLayout(bottom)

        return widget

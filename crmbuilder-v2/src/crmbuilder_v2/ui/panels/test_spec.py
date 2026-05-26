"""Test Specs panel — PI-004 cohort closer methodology entity (v0.5+).

A ``ListDetailPanel`` for the ``test_spec`` entity, registered under
the Methodology sidebar group between Requirements and CRM Candidates
per ``test_spec.md`` §3.6.1's proposed ordering. Mirrors the
manual_config panel pattern with test_spec-specific adjustments per
``test_spec.md`` v1.0:

* **Five-column master pane** per spec §3.6.2 + AC-12 (Identifier /
  Name / Status / Last Run / Updated). The Last Run column renders
  with a color cue per spec §3.6.2's UI deviation — passing green,
  failing red, not_run gray, skipped amber. Label text always shown;
  color is additive. Implementation: a small ``QStyledItemDelegate``
  subclass installed via ``setItemDelegateForColumn`` on the Last Run
  column only — leaves the shared ``MasterPaneDelegate`` driving the
  rest of the row. Authority: ``test_spec.md`` §3.6.2.
* **Three-section detail pane** per spec §3.6.3: identity-and-
  methodology block, Test body block, Last run block, plus a
  collapsible Internal notes section and the shared
  ``ReferencesSection``.
* **Record Run button** in the action strip (next to Edit / Delete)
  per spec §3.8.1's convenience-endpoint affordance.
* **Three outbound reference kinds** plus the inbound
  ``requirement_verified_by_test_spec`` kind surface through the
  shared ``ReferencesSection`` widget.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.dialogs._test_spec_schema import (
    run_outcome_choices,
    status_choices,
)
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.dialogs.test_spec_crud import (
    TestSpecCreateDialog,
    TestSpecDeleteDialog,
    TestSpecEditDialog,
    TestSpecRecordRunDialog,
)
from crmbuilder_v2.ui.exceptions import (
    NotFoundError,
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.styling import t as _T
from crmbuilder_v2.ui.widgets.form_helpers import (
    CollapsibleSection,
    destructive_button,
    primary_button,
    required_label,
)
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection

_log = logging.getLogger("crmbuilder_v2.ui.panels.test_spec")

_LONG_TEXT_MIN_HEIGHT = 80
_BODY_TEXT_MIN_HEIGHT = 100
_READ_ONLY_STYLE = "color: #444; background: #f4f4f4;"

# Color cue tokens for the Last Run column per spec §3.6.2 deviation.
# Tokens resolved via ``crmbuilder_v2.ui.styling.t(...)``; fallback hex
# kept inline so an unknown token name doesn't fail-loud.
_OUTCOME_COLOR_FALLBACK = {
    "passing": "#1b7e1b",
    "failing": "#b41a1a",
    "not_run": "#888888",
    "skipped": "#c0830d",
}
_OUTCOME_COLOR_TOKEN = {
    "passing": "color.success.default",
    "failing": "color.danger.default",
    "not_run": "color.neutral.500",
    "skipped": "color.warning.default",
}


def _resolve_outcome_color(outcome: str | None) -> QColor:
    """Resolve an outcome value to a QColor for the master-pane delegate.

    Tries the styling token first; falls back to a hardcoded hex per
    the table above. Unknown outcomes fall back to neutral-500.
    """
    key = outcome if outcome in _OUTCOME_COLOR_FALLBACK else "not_run"
    token = _OUTCOME_COLOR_TOKEN[key]
    try:
        raw = _T(token)
    except Exception:  # noqa: BLE001
        raw = None
    if raw:
        color = QColor(raw)
        if color.isValid():
            return color
    return QColor(_OUTCOME_COLOR_FALLBACK[key])


class _LastRunColorDelegate(QStyledItemDelegate):
    """Render the Last Run column with a per-outcome color cue.

    Spec §3.6.2 deviation: passing green, failing red, not_run gray,
    skipped amber. Label text always shown (color additive). The
    delegate paints the text in the resolved color; everything else
    (background, hover, divider, focus) defers to the standard
    ``QStyledItemDelegate.paint`` path so this column visually merges
    with the rest of the row.
    """

    def __init__(self, panel: TestSpecsPanel) -> None:
        super().__init__(panel)
        self._panel = panel

    def paint(self, painter, option, index) -> None:  # noqa: D401
        record = self._panel._record_at_index(index)
        outcome = (
            record.get("test_spec_last_run_outcome") if record else None
        )
        color = _resolve_outcome_color(outcome)

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        # Paint text in the outcome color regardless of selection /
        # hover state. Setting both Text and HighlightedText keeps the
        # color consistent across selection.
        opt.palette.setColor(opt.palette.ColorRole.Text, color)
        opt.palette.setColor(opt.palette.ColorRole.HighlightedText, color)
        # Optional: bold weight for failing rows so red doesn't shout
        # at the operator and instead reads as "needs attention".
        if outcome == "failing":
            font = QFont(opt.font)
            font.setWeight(QFont.Weight.DemiBold)
            opt.font = font

        style = opt.widget.style() if opt.widget else None
        if style is None:
            super().paint(painter, opt, index)
        else:
            style.drawControl(
                QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget
            )


def _heading_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setWordWrap(True)
    font = QFont(label.font())
    font.setBold(True)
    font.setPointSize(font.pointSize() + 2)
    label.setFont(font)
    return label


def _subsection_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    font = QFont(label.font())
    font.setBold(True)
    label.setFont(font)
    return label


def _read_only_line(value: str, *, placeholder: str = "") -> QLineEdit:
    widget = QLineEdit()
    widget.setText(value or "")
    widget.setReadOnly(True)
    widget.setStyleSheet(_READ_ONLY_STYLE)
    if placeholder:
        widget.setPlaceholderText(placeholder)
    return widget


def _read_only_text(
    value: str, *, placeholder: str = "", min_height: int = _LONG_TEXT_MIN_HEIGHT
) -> QPlainTextEdit:
    widget = QPlainTextEdit()
    widget.setPlainText(value or "")
    widget.setReadOnly(True)
    widget.setStyleSheet(_READ_ONLY_STYLE)
    widget.setMinimumHeight(min_height)
    if placeholder:
        widget.setPlaceholderText(placeholder)
    return widget


def _separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


class TestSpecsPanel(ListDetailPanel):
    """Test Specs panel with read + write surfaces (PI-004 cohort closer)."""

    # Tell pytest not to try collecting this Qt widget as a test class —
    # the class name starts with ``Test`` which trips pytest's default
    # collection rule (see PytestCollectionWarning if absent).
    __test__ = False

    def __init__(self, client, parent=None):
        self._include_deleted = False
        super().__init__(client, parent)
        self._show_deleted_check = QCheckBox("Show deleted")
        self._show_deleted_check.setObjectName("show_deleted_check")
        self._show_deleted_check.toggled.connect(self._on_show_deleted_toggled)
        self._action_layout.addWidget(self._show_deleted_check)
        self._new_button = primary_button("New Test Spec")
        self._new_button.setObjectName("new_test_spec_button")
        self._new_button.clicked.connect(self._on_new_test_spec_clicked)
        self._action_layout.addWidget(self._new_button)

        # Install the color-cued Last Run delegate on its column. The
        # rest of the row keeps the shared MasterPaneDelegate semantics.
        # See class docstring + spec §3.6.2 for the rationale.
        self._last_run_delegate = _LastRunColorDelegate(self)
        last_run_col = self._last_run_column_index()
        if last_run_col is not None and self._master_view is not None:
            self._master_view.setItemDelegateForColumn(
                last_run_col, self._last_run_delegate
            )

    def _last_run_column_index(self) -> int | None:
        for idx, spec in enumerate(self.list_columns()):
            if spec.field == "test_spec_last_run_outcome":
                return idx
        return None

    # ------------------------------------------------------------------
    # ListDetailPanel hooks
    # ------------------------------------------------------------------

    def entity_title(self) -> str:
        return "Test Specs"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_test_specs(
            include_deleted=self._include_deleted
        )

    def list_columns(self) -> list[ColumnSpec]:
        # Five-column master pane per spec §3.6.2 + AC-12. The Last
        # Run column is the spec's UI deviation — color-cued via the
        # _LastRunColorDelegate installed in __init__.
        return [
            ColumnSpec(
                field="test_spec_identifier",
                title="Identifier",
                width=120,
            ),
            ColumnSpec(field="test_spec_name", title="Name"),
            ColumnSpec(
                field="test_spec_status", title="Status", width=110
            ),
            ColumnSpec(
                field="test_spec_last_run_outcome",
                title="Last Run",
                width=110,
            ),
            ColumnSpec(
                field="test_spec_updated_at",
                title="Updated",
                width=180,
            ),
        ]

    def _strikethrough_for_record(self, record: dict[str, Any]) -> bool:
        return record.get("test_spec_deleted_at") is not None

    def _on_show_deleted_toggled(self, checked: bool) -> None:
        self._include_deleted = checked
        self.refresh()

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        identifier = record.get("test_spec_identifier")
        if not identifier:
            return {"references": {"as_source": [], "as_target": []}}
        return {
            "references": self._client.list_references_touching(
                "test_spec", identifier
            ),
        }

    def render_detail(
        self, record: dict[str, Any], extras: dict[str, Any]
    ) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        identifier = record.get("test_spec_identifier") or ""
        is_deleted = record.get("test_spec_deleted_at") is not None
        current_status = record.get("test_spec_status") or "candidate"
        current_outcome = record.get("test_spec_last_run_outcome") or "not_run"

        # Edit / Delete / Record Run action strip.
        button_strip = QWidget()
        strip_layout = QHBoxLayout(button_strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(6)
        if is_deleted:
            restore_btn = QPushButton("Restore")
            restore_btn.setObjectName("restore_test_spec_button")
            restore_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_restore_clicked(r)
            )
            strip_layout.addWidget(restore_btn)
        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("edit_test_spec_button")
        edit_btn.clicked.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )
        strip_layout.addWidget(edit_btn)
        if not is_deleted:
            record_run_btn = QPushButton("Record Run")
            record_run_btn.setObjectName("record_run_test_spec_button")
            record_run_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_record_run_clicked(r)
            )
            strip_layout.addWidget(record_run_btn)
            delete_btn = destructive_button("Delete")
            delete_btn.setObjectName("delete_test_spec_button")
            delete_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_delete_clicked(r)
            )
            strip_layout.addWidget(delete_btn)
        strip_layout.addStretch(1)
        outer.addWidget(button_strip)

        outer.addWidget(
            _heading_label(record.get("test_spec_name") or "(unnamed)")
        )

        # Identity-and-methodology block per spec §3.6.3.
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        identifier_label = QLabel(identifier or "—")
        identifier_label.setObjectName("test_spec_identifier_value")
        identifier_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        form.addRow("Identifier", identifier_label)

        name_value = _read_only_line(record.get("test_spec_name") or "")
        name_value.setObjectName("test_spec_name_value")
        form.addRow(required_label("Name"), name_value)

        description_value = _read_only_text(
            record.get("test_spec_description") or "",
            placeholder="What does this test verify?",
        )
        description_value.setObjectName("test_spec_description_value")
        form.addRow(required_label("Description"), description_value)

        # Methodology status (combo disabled — editing goes through the
        # dialog or PATCH). Hint caption shows the valid successors.
        status_combo = QComboBox()
        status_combo.setObjectName("test_spec_status_value")
        status_combo.addItems(status_choices(current_status))
        idx = status_combo.findText(current_status)
        if idx >= 0:
            status_combo.setCurrentIndex(idx)
        status_combo.setEnabled(False)
        successors = sorted(
            set(status_choices(current_status)) - {current_status}
        )
        status_container = QWidget()
        status_layout = QVBoxLayout(status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(int(_T("space.1").rstrip("px")))
        status_layout.addWidget(status_combo)
        status_hint = QLabel(
            f"Valid transitions: {', '.join(successors)}"
            if successors
            else "Terminal status (no further transitions)"
        )
        status_hint.setObjectName("statusHintCaption")
        status_layout.addWidget(status_hint)
        form.addRow(required_label("Status"), status_container)
        outer.addLayout(form)

        # Test body block per spec §3.6.3.
        outer.addWidget(_separator())
        outer.addWidget(_subsection_label("Test body"))
        body_form = QFormLayout()
        body_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        body_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        setup_value = _read_only_text(
            record.get("test_spec_setup") or "",
            placeholder=(
                "Preconditions — what must be true before the test runs?"
            ),
        )
        setup_value.setObjectName("test_spec_setup_value")
        body_form.addRow("Setup", setup_value)

        steps_value = _read_only_text(
            record.get("test_spec_steps") or "",
            placeholder="Numbered steps to execute the test",
            min_height=_BODY_TEXT_MIN_HEIGHT,
        )
        steps_value.setObjectName("test_spec_steps_value")
        body_form.addRow(required_label("Steps"), steps_value)

        expected_value = _read_only_text(
            record.get("test_spec_expected") or "",
            placeholder=(
                "Expected results — what must be true after the steps "
                "execute?"
            ),
        )
        expected_value.setObjectName("test_spec_expected_value")
        body_form.addRow(required_label("Expected results"), expected_value)
        outer.addLayout(body_form)

        # Last run block per spec §3.6.3.
        outer.addWidget(_separator())
        outer.addWidget(_subsection_label("Last run"))
        last_form = QFormLayout()
        last_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        last_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        outcome_combo = QComboBox()
        outcome_combo.setObjectName("test_spec_last_run_outcome_value")
        outcome_combo.addItems(run_outcome_choices(current_outcome))
        oidx = outcome_combo.findText(current_outcome)
        if oidx >= 0:
            outcome_combo.setCurrentIndex(oidx)
        outcome_combo.setEnabled(False)
        # Small color swatch beside the outcome combo per §3.6.3
        # ("optionally render a small color swatch beside the outcome
        # combo to echo the master-pane cue").
        outcome_color = _resolve_outcome_color(current_outcome)
        outcome_swatch = QLabel(" ")
        outcome_swatch.setFixedSize(14, 14)
        outcome_swatch.setStyleSheet(
            f"background-color: {outcome_color.name()};"
            " border: 1px solid #444;"
        )
        outcome_row = QWidget()
        outcome_layout = QHBoxLayout(outcome_row)
        outcome_layout.setContentsMargins(0, 0, 0, 0)
        outcome_layout.setSpacing(6)
        outcome_layout.addWidget(outcome_combo, 1)
        outcome_layout.addWidget(outcome_swatch)
        last_form.addRow(required_label("Outcome"), outcome_row)

        last_at_raw = record.get("test_spec_last_run_at") or ""
        last_at_str = (
            last_at_raw if isinstance(last_at_raw, str) else str(last_at_raw)
        ) or "—"
        last_at_value = _read_only_line(last_at_str)
        last_at_value.setObjectName("test_spec_last_run_at_value")
        last_form.addRow("Run at", last_at_value)

        last_notes_value = _read_only_text(
            record.get("test_spec_last_run_notes") or "",
            placeholder=(
                "Notes from the most recent run (auto-cleared on "
                "transition to not_run)"
            ),
        )
        last_notes_value.setObjectName("test_spec_last_run_notes_value")
        last_form.addRow("Run notes", last_notes_value)
        outer.addLayout(last_form)

        # Internal notes collapsible section per spec §3.6.3.
        notes_value = _read_only_text(
            record.get("test_spec_notes") or ""
        )
        notes_value.setObjectName("test_spec_notes_value")
        notes_section = CollapsibleSection(
            "Internal notes", notes_value, expanded=False
        )
        notes_section.setObjectName("test_spec_notes_toggle")
        outer.addWidget(notes_section)

        outer.addWidget(_separator())

        # References section. Renders the three outbound kinds plus the
        # inbound ``requirement_verified_by_test_spec`` references the
        # widget treats inbound and outbound symmetrically.
        references_section = ReferencesSection(
            "test_spec",
            identifier,
            extras.get("references") or {},
            client=self._client,
        )
        references_section.navigate_requested.connect(self.navigate_requested)
        references_section.references_changed.connect(self.refresh)
        outer.addWidget(references_section)

        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

    # ------------------------------------------------------------------
    # Identifier addressing (test_spec uses ``test_spec_identifier``)
    # ------------------------------------------------------------------

    def _select_by_identifier(self, identifier: str) -> bool:
        for row, record in enumerate(self._records):
            if record.get("test_spec_identifier") == identifier:
                self._select_row(row)
                return True
        return False

    def _currently_selected_identifier(self) -> str | None:
        master = getattr(self, "_master_view", None)
        if master is None:
            return None
        sel_model = master.selectionModel()
        if sel_model is None:
            return None
        index = sel_model.currentIndex()
        if not index.isValid():
            return None
        row = index.row()
        if 0 <= row < len(self._records):
            ident = self._records[row].get("test_spec_identifier")
            if isinstance(ident, str):
                return ident
        return None

    # ------------------------------------------------------------------
    # Right-click context menu (New / Edit / Delete / Restore / Record Run)
    # ------------------------------------------------------------------

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        if not index.isValid():
            new_action = menu.addAction("New test spec")
            new_action.triggered.connect(self._on_new_test_spec_clicked)
            return menu

        record = self._record_at_index(index)
        if record is None:
            return menu

        new_action = menu.addAction("New test spec")
        new_action.triggered.connect(self._on_new_test_spec_clicked)
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )
        if record.get("test_spec_deleted_at") is not None:
            restore_action = menu.addAction("Restore")
            restore_action.triggered.connect(
                lambda _checked=False, r=record: self._on_restore_clicked(r)
            )
        else:
            record_run_action = menu.addAction("Record Run…")
            record_run_action.triggered.connect(
                lambda _checked=False, r=record: self._on_record_run_clicked(r)
            )
            delete_action = menu.addAction("Delete")
            delete_action.triggered.connect(
                lambda _checked=False, r=record: self._on_delete_clicked(r)
            )
        return menu

    # ------------------------------------------------------------------
    # Write-surface click handlers
    # ------------------------------------------------------------------

    def _on_new_test_spec_clicked(self) -> None:
        dialog = TestSpecCreateDialog(self._client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_id = dialog.created_identifier()
            if new_id:
                self.select_record_by_identifier(new_id)
            else:
                self.refresh()

    def _on_edit_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("test_spec_identifier")
        if not identifier:
            return
        try:
            fresh = self._client.get_test_spec(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            _log.warning(
                "Connection lost loading %s for edit: %s", identifier, exc
            )
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            _log.warning(
                "Test spec error loading %s for edit: %s", identifier, exc
            )
            ErrorDialog(
                title="Could not load test spec",
                message=(
                    "Could not load the latest version of this test spec."
                ),
                detail=str(exc),
                parent=self,
            ).exec()
            return

        dialog = TestSpecEditDialog(self._client, fresh, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("test_spec_identifier") or ""
        name = record.get("test_spec_name") or ""
        if not identifier:
            return
        dialog = TestSpecDeleteDialog(
            self._client, identifier, name, self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_record_run_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("test_spec_identifier") or ""
        if not identifier:
            return
        current_outcome = (
            record.get("test_spec_last_run_outcome") or "not_run"
        )
        dialog = TestSpecRecordRunDialog(
            self._client, identifier, current_outcome=current_outcome, parent=self
        )
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.refresh()
        finally:
            # Per project memory project_qt_worker_widget_gc_hazard.md
            # — transient modal sub-dialogs opened from the panel need
            # deleteLater() to avoid worker-thread GC crashes.
            dialog.deleteLater()

    def _on_restore_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("test_spec_identifier") or ""
        name = record.get("test_spec_name") or ""
        if not identifier:
            return
        confirm = QMessageBox(self)
        confirm.setWindowTitle("Restore test spec")
        confirm.setText(
            f"Restore {identifier} — {name or '(unnamed)'}?\n\n"
            "It will reappear in the default Test Specs list."
        )
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        confirm.setDefaultButton(QMessageBox.StandardButton.No)
        if confirm.exec() != QMessageBox.StandardButton.Yes:
            return
        try:
            self._client.restore_test_spec(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            _log.warning("Connection lost restoring %s: %s", identifier, exc)
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            _log.warning("Test spec error restoring %s: %s", identifier, exc)
            ErrorDialog(
                title="Could not restore test spec",
                message=(
                    "An error occurred while restoring the test spec. "
                    "Please try again."
                ),
                detail=str(exc),
                parent=self,
            ).exec()
            return
        self.refresh()

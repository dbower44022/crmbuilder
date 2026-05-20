"""Engagement create / edit dialogs (UI v0.5 slice C).

Thin subclasses of the shared ``EntityCrudDialog`` base, mirroring the
v0.4 methodology-entity dialog pattern. The declarative field schema
lives in ``_engagement_schema.py``.

* ``EngagementCreateDialog`` — create mode. Fields per
  ``engagement.md`` §3.6.3 / PRD §5.1: code (writeable, regex hint
  visible, with format validation), name, purpose, status (default
  ``active``), optional export dir (with directory-browser button).

  Slice C creates the meta DB row only — the per-engagement DB file is
  NOT created and activation is NOT initiated. Both land in slice D's
  ``NewEngagementDialog`` extension. Users who attempt to switch to such
  a partially-created engagement in slice D will get a reachability-
  check failure; that is acceptable interim behavior.

* ``EngagementEditDialog`` — edit mode. ``engagement_identifier`` and
  ``engagement_code`` are read-only (the code field carries a tooltip
  reading "Engagement code cannot be changed after creation."); all
  other fields editable. PATCH-only on submit — the base computes a
  partial diff against the pre-fill values.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QWidget,
)

from crmbuilder_v2.ui.base.crud_dialog import EntityCrudDialog
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._engagement_schema import (
    engagement_fields_create,
    engagement_fields_edit,
)
from crmbuilder_v2.ui.styling import t

_EXPORT_DIR_FIELD = "engagement_export_dir"

_IDENTIFIER_FIELD = "engagement_identifier"
_EXPORT_DIR_TOOLTIP = (
    "Where this engagement's JSON snapshots will be written. "
    "Recommend a path inside the client repo so exports travel with "
    "the engagement documents."
)


def _attach_directory_browser(dialog: EntityCrudDialog) -> None:
    """Replace the export-dir line widget with a line+browse-button pair.

    The line edit keeps its schema-driven validation behavior; the
    button opens ``QFileDialog.getExistingDirectory`` and writes the
    chosen path back into the line edit on selection.
    """
    line_widget = dialog._field_widgets.get("engagement_export_dir")
    if not isinstance(line_widget, QLineEdit):
        return
    line_widget.setToolTip(_EXPORT_DIR_TOOLTIP)

    # Wrap the line edit in a horizontal layout with a Browse button.
    parent = line_widget.parentWidget()
    if parent is None:
        return
    container = QWidget(parent)
    row = QHBoxLayout(container)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(4)
    parent_layout = parent.layout()
    # Replace the line_widget in its parent's layout with the container.
    if parent_layout is not None:
        idx = parent_layout.indexOf(line_widget)
        if idx >= 0:
            parent_layout.removeWidget(line_widget)
            line_widget.setParent(container)
            row.addWidget(line_widget, stretch=1)
            browse = QPushButton("Browse…", container)
            browse.setObjectName("engagement_export_dir_browse")

            def _on_browse():
                start = line_widget.text() or ""
                chosen = QFileDialog.getExistingDirectory(
                    dialog, "Choose export directory", start
                )
                if chosen:
                    line_widget.setText(chosen)

            browse.clicked.connect(_on_browse)
            row.addWidget(browse)
            parent_layout.insertWidget(idx, container)


class EngagementCreateDialog(EntityCrudDialog):
    """Modal create-engagement dialog (slice C — meta DB row only).

    Per ``engagement.md`` §3.6.3. Creates the meta DB row only — does
    NOT create the per-engagement DB file at ``engagements/{code}.db``
    and does NOT initiate activation. Both land in slice D's
    ``NewEngagementDialog`` single-gesture flow.
    """

    def __init__(
        self,
        client: StorageClient,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client,
            engagement_fields_create(),
            mode="create",
            title="New engagement",
            create_method=client.create_engagement,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )
        _attach_directory_browser(self)

    def created_identifier(self) -> str | None:
        """Identifier of the newly created engagement, or None if not accepted."""
        return self.saved_identifier()


class EngagementEditDialog(EntityCrudDialog):
    """Modal edit-engagement dialog. ``code`` read-only with explanatory tooltip."""

    def __init__(
        self,
        client: StorageClient,
        record: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        identifier = str(record.get(_IDENTIFIER_FIELD) or "")
        title = f"Edit {identifier}" if identifier else "Edit engagement"
        super().__init__(
            client,
            engagement_fields_edit(),
            mode="edit",
            title=title,
            update_method=client.patch_engagement,
            record=record,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )
        # The code field is locked because rename requires a per-engagement
        # DB file move; that work is v0.6+.
        code_widget = self._field_widgets.get("engagement_code")
        if isinstance(code_widget, QLineEdit):
            code_widget.setToolTip(
                "Engagement code cannot be changed after creation."
            )
        _attach_directory_browser(self)

        # Multi-tenancy routing fix slice B (B6): emphasise the export-dir
        # field while it is empty, since an unconfigured export directory
        # disables writes for the active engagement. The emphasis clears as
        # soon as the operator types or browses to a path.
        export_widget = self._field_widgets.get(_EXPORT_DIR_FIELD)
        if isinstance(export_widget, QLineEdit):
            export_widget.textChanged.connect(
                lambda _t=None: self._refresh_export_dir_emphasis()
            )
            self._refresh_export_dir_emphasis()

    # ------------------------------------------------------------------
    # Export-dir affordances (slice B — B6)
    # ------------------------------------------------------------------

    def focus_export_dir_field(self) -> None:
        """Move keyboard focus to the export-dir field.

        Called by the Engagements panel's warning-band action button when
        the active engagement has no export directory configured, so the
        operator lands directly on the field to set.
        """
        widget = self._field_widgets.get(_EXPORT_DIR_FIELD)
        if isinstance(widget, QLineEdit):
            widget.setFocus()

    def _refresh_export_dir_emphasis(self) -> None:
        widget = self._field_widgets.get(_EXPORT_DIR_FIELD)
        if not isinstance(widget, QLineEdit):
            return
        if widget.text().strip():
            widget.setStyleSheet("")
        else:
            widget.setStyleSheet(
                f"QLineEdit {{ border: 1px solid {t('color.warning.default')}; }}"
            )

    def _on_save_clicked(self) -> None:
        """Confirm a non-existent export_dir before the standard save flow.

        If the export-dir field holds a non-empty path that does not exist
        on disk, prompt the operator to confirm. On confirm, proceed (the
        access layer now accepts a not-yet-created absolute path; the
        write-time gate fails loud if it is still absent at export). On
        cancel, return focus to the field without closing the dialog.
        """
        widget = self._field_widgets.get(_EXPORT_DIR_FIELD)
        value = widget.text().strip() if isinstance(widget, QLineEdit) else ""
        if value and not Path(value).is_dir():
            if not self._confirm_nonexistent_export_dir(value):
                if isinstance(widget, QLineEdit):
                    widget.setFocus()
                return
        super()._on_save_clicked()

    def _confirm_nonexistent_export_dir(self, value: str) -> bool:
        """Prompt to save a path that does not exist. Return True to proceed."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Export directory does not exist")
        box.setText(
            f"The path '{value}' does not exist. Save anyway? You can "
            "create the directory later."
        )
        save_btn = box.addButton(
            "Save anyway", QMessageBox.ButtonRole.AcceptRole
        )
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save_btn)
        box.exec()
        return box.clickedButton() is save_btn

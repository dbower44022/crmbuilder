"""Test spec create / edit / delete / record-run dialogs (PI-004 closer, v0.5+).

Thin subclasses of the shared ``EntityCrudDialog`` /
``EntityCrudDeleteDialog`` bases plus a dedicated ``QDialog`` for the
``POST /test-specs/{id}/record-run`` convenience endpoint (§3.8.1).
Following the v0.3 governance-entity pattern and mirroring
``manual_config_crud.py``. The declarative field schema lives in
``_test_spec_schema.py``.

* ``TestSpecCreateDialog`` — create mode; ``test_spec_identifier``
  is not shown (server-assigned). Status defaults to ``candidate``;
  outcome defaults to ``not_run``. Per spec §3.6.4's create-then-
  attach flow the dialog creates the test_spec record only — there
  are no reference multi-selects; the user attaches references via
  the detail pane's "Add reference" affordance after the record
  exists.
* ``TestSpecEditDialog`` — edit mode; ``test_spec_identifier``
  read-only. Saves via PATCH; the status combo is restricted to valid
  successors by the schema's ``compute_options`` (propose-verify
  gate). The outcome combo offers the full four-value vocabulary
  unconditionally (transitions unrestricted per §3.4.2). The server
  enforces the §3.4.4 cross-field invariant on ``last_run_at``.
* ``TestSpecDeleteDialog`` — edge-text confirmation per spec §3.6.6:
  the Delete button stays disabled until the operator types the
  ``TST-NNN`` identifier exactly. Confirmation soft-deletes; outbound
  references persist per spec §3.4.6.
* ``TestSpecRecordRunDialog`` — modal sub-dialog opened from the
  detail pane's Record Run button (§3.8.1). Fields: outcome (combo,
  defaults to current outcome), notes (multi-line), at (free-form
  line with ISO-8601 placeholder; leave blank for server-default to
  now). On accept POSTs ``/test-specs/{id}/record-run`` and signals
  the panel to refresh.

  Per project memory ``project_qt_worker_widget_gc_hazard.md`` this is
  a transient modal sub-dialog opened from ``TestSpecsPanel``, so the
  panel calls ``deleteLater()`` on the dialog after exec returns.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.access.vocab import TEST_SPEC_RUN_OUTCOMES
from crmbuilder_v2.ui.base.crud_dialog import (
    EntityCrudDeleteDialog,
    EntityCrudDialog,
)
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._test_spec_schema import test_spec_fields

_log = logging.getLogger("crmbuilder_v2.ui.dialogs.test_spec_crud")

_IDENTIFIER_FIELD = "test_spec_identifier"


class TestSpecCreateDialog(EntityCrudDialog):
    """Modal create-test_spec dialog. Per ``test_spec.md`` §3.6.4."""

    __test__ = False  # Not a pytest test class — Qt dialog subclass.

    def __init__(
        self,
        client: StorageClient,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client,
            test_spec_fields(include_identifier=False),
            mode="create",
            title="New test spec",
            create_method=client.create_test_spec,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )

    def created_identifier(self) -> str | None:
        """Identifier of the newly created test_spec, or None."""
        return self.saved_identifier()


class TestSpecEditDialog(EntityCrudDialog):
    """Modal edit-test_spec dialog. Per ``test_spec.md`` §3.6.5."""

    __test__ = False  # Not a pytest test class — Qt dialog subclass.

    def __init__(
        self,
        client: StorageClient,
        record: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        identifier = str(record.get(_IDENTIFIER_FIELD) or "")
        title = f"Edit {identifier}" if identifier else "Edit test spec"
        super().__init__(
            client,
            test_spec_fields(include_identifier=True),
            mode="edit",
            title=title,
            update_method=client.patch_test_spec,
            record=record,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )


class TestSpecDeleteDialog(EntityCrudDeleteDialog):
    """Confirmation dialog for deleting a test_spec. Per spec §3.6.6.

    Extends ``EntityCrudDeleteDialog`` with edge-text confirmation: the
    Delete button is disabled until the operator types the test_spec's
    ``TST-NNN`` identifier exactly into the confirmation field.
    """

    __test__ = False  # Not a pytest test class — Qt dialog subclass.

    def __init__(
        self,
        client: StorageClient,
        identifier: str,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client,
            identifier,
            title,
            client.delete_test_spec,
            entity_label="test_spec",
            parent=parent,
        )
        self._body_label.setText(
            f"Delete {identifier} — {title or '(untitled)'}?\n\n"
            "Type the identifier below to confirm. This soft-deletes "
            "the test spec; it can be restored from the Show-deleted "
            "view. All outbound references are kept."
        )
        self._confirm_edit = QLineEdit()
        self._confirm_edit.setObjectName("delete_confirm_edit")
        self._confirm_edit.setPlaceholderText(identifier)
        self._confirm_edit.textChanged.connect(self._on_confirm_text_changed)
        layout = self.layout()
        if isinstance(layout, QVBoxLayout):
            layout.insertWidget(layout.count() - 1, self._confirm_edit)
        self._delete_btn.setEnabled(False)

    def _on_confirm_text_changed(self, text: str) -> None:
        self._delete_btn.setEnabled(text.strip() == self._identifier)


class TestSpecRecordRunDialog(QDialog):
    """Record-run convenience dialog (§3.8.1).

    Captures outcome + optional notes + optional at. POSTs to
    ``/test-specs/{identifier}/record-run`` on accept. Transient modal
    sub-dialog opened from ``TestSpecsPanel``; per the Qt worker/widget
    GC hazard the panel calls ``deleteLater()`` after exec returns.
    """

    __test__ = False  # Not a pytest test class — Qt dialog subclass.

    def __init__(
        self,
        client: StorageClient,
        identifier: str,
        current_outcome: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._identifier = identifier
        self._error: str | None = None

        self.setWindowTitle(f"Record run — {identifier}")
        self.setModal(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        intro = QLabel(
            f"Record the most recent verification run for {identifier}.\n"
            "Outcome=not_run clears both Run At and Run Notes."
        )
        intro.setWordWrap(True)
        outer.addWidget(intro)

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        self._outcome_combo = QComboBox()
        self._outcome_combo.setObjectName("record_run_outcome_combo")
        outcomes = sorted(TEST_SPEC_RUN_OUTCOMES)
        self._outcome_combo.addItems(outcomes)
        if current_outcome and current_outcome in outcomes:
            idx = self._outcome_combo.findText(current_outcome)
            if idx >= 0:
                self._outcome_combo.setCurrentIndex(idx)
        form.addRow("Outcome", self._outcome_combo)

        self._at_edit = QLineEdit()
        self._at_edit.setObjectName("record_run_at_edit")
        self._at_edit.setPlaceholderText(
            "ISO 8601 UTC; leave blank to use now"
        )
        form.addRow("Run at", self._at_edit)

        self._notes_edit = QPlainTextEdit()
        self._notes_edit.setObjectName("record_run_notes_edit")
        self._notes_edit.setMinimumHeight(80)
        self._notes_edit.setPlaceholderText(
            "Notes from this run (cleared if outcome is not_run)"
        )
        form.addRow("Run notes", self._notes_edit)

        outer.addLayout(form)

        self._error_label = QLabel("")
        self._error_label.setObjectName("record_run_error_label")
        self._error_label.setStyleSheet("color: #b41a1a;")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        outer.addWidget(self._error_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Record")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _on_accept(self) -> None:
        body: dict[str, Any] = {"outcome": self._outcome_combo.currentText()}
        at_text = self._at_edit.text().strip()
        if at_text:
            body["at"] = at_text
        notes_text = self._notes_edit.toPlainText().strip()
        if notes_text:
            body["notes"] = notes_text
        try:
            self._client.record_test_spec_run(self._identifier, body)
        except Exception as exc:  # noqa: BLE001 — surface any failure inline
            _log.warning(
                "record_test_spec_run failed for %s: %s",
                self._identifier,
                exc,
            )
            self._error = str(exc)
            self._error_label.setText(str(exc))
            self._error_label.setVisible(True)
            return
        self.accept()

    def error_text(self) -> str | None:
        """Return the last error string if the dialog failed, else None."""
        return self._error

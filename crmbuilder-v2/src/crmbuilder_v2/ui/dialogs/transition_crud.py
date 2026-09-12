"""Add and edit one allowed status move on a process (PI-471, REQ-585).

Opened from the Transitions section of a process's detail view. The process is
already known, so the form never asks for it. It asks what a transition says,
in the order the approved Mentor Application table reads:

1. **The status field** — the choice fields on the entities this process
   touches, by name. Changing it reloads the value lists below.
2. **From** — either the creation of the record, or one or more of the status
   field's values, each with a tick box.
3. **To** — one of the status field's values.
4. **Who** — the system, or one of the personas that perform this process.
   A short occasion in words tells two moves by the same persona apart, or
   names which system acts.
5. **Before the move** — the fields that must hold a value, ticked from the
   fields on the entities this process touches, plus any further condition in
   words.
6. **After the move** — the records that follow automatically, ticked from the
   automations, message templates, views, transitions and processes the store
   holds; words for an automatic action that has no record yet; and, kept
   apart, what a person does by hand.

Nothing in the form is typed by hand except the words: every identifier and
every status value is chosen from a list drawn from the store, which is what
REQ-585 asks for. The store's checks still apply on save, and a refusal is
shown with the name of the check that failed rather than swallowed.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.elevation import apply_dialog_shadow
from crmbuilder_v2.ui.exceptions import (
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.widgets.form_helpers import primary_button, required_label

_log = logging.getLogger("crmbuilder_v2.ui.dialogs.transition_crud")

#: The field type a status field must have — the store refuses any other.
CHOICE_FIELD_TYPE = "enum"

#: What the From list calls the move that brings the record into being.
RECORD_CREATION_LABEL = "the creation of the record"

_CONSEQUENCE_PREFIX_LABELS = {
    "AUT": "routine",
    "MSG": "message",
    "VEW": "view",
    "TRN": "move",
    "PROC": "process hand-off",
}


def _ticked(widget: QListWidget) -> list[str]:
    """Return the data of every ticked row, in list order."""
    out = []
    for row in range(widget.count()):
        item = widget.item(row)
        if item.checkState() == Qt.CheckState.Checked:
            out.append(item.data(Qt.ItemDataRole.UserRole))
    return out


def _add_tickable(widget: QListWidget, label: str, value: str, *, ticked: bool) -> None:
    item = QListWidgetItem(label)
    item.setData(Qt.ItemDataRole.UserRole, value)
    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
    item.setCheckState(
        Qt.CheckState.Checked if ticked else Qt.CheckState.Unchecked
    )
    widget.addItem(item)


class TransitionDialog(QDialog):
    """Add or edit one transition on a known process."""

    def __init__(
        self,
        client: StorageClient,
        *,
        process_identifier: str,
        record: dict[str, Any] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._process = process_identifier
        self._record = record or {}
        self._editing = bool(self._record)
        self.saved_record: dict[str, Any] | None = None

        self.setWindowTitle(
            "Edit status move" if self._editing else "Add status move"
        )
        self.setModal(True)
        apply_dialog_shadow(self)

        self._touched_entities: list[str] = []
        self._fields_by_entity: dict[str, list[dict[str, Any]]] = {}
        self._status_fields: list[dict[str, Any]] = []
        self._personas: list[dict[str, Any]] = []
        self._consequence_choices: list[tuple[str, str]] = []

        self._build()
        self._load_choices()
        self._populate_from_record()

    # -- construction ------------------------------------------------------

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)

        self.status_field_combo = QComboBox()
        self.status_field_combo.setObjectName("transition_field_combo")
        self.status_field_combo.currentIndexChanged.connect(
            self._on_status_field_changed
        )
        form.addRow(required_label("Status field"), self.status_field_combo)

        self.from_creation_check = QCheckBox(
            f"Moves from {RECORD_CREATION_LABEL}"
        )
        self.from_creation_check.setObjectName("transition_from_creation")
        self.from_creation_check.toggled.connect(self._on_from_kind_toggled)
        form.addRow("", self.from_creation_check)

        self.from_values_list = QListWidget()
        self.from_values_list.setObjectName("transition_from_values")
        self.from_values_list.setMaximumHeight(140)
        form.addRow("From", self.from_values_list)

        self.to_value_combo = QComboBox()
        self.to_value_combo.setObjectName("transition_to_value")
        form.addRow(required_label("To"), self.to_value_combo)

        self.actor_combo = QComboBox()
        self.actor_combo.setObjectName("transition_actor")
        form.addRow(required_label("Who makes the move"), self.actor_combo)

        self.occasion_edit = QLineEdit()
        self.occasion_edit.setObjectName("transition_actor_occasion")
        self.occasion_edit.setPlaceholderText(
            "first vote — or which system acts"
        )
        form.addRow("On what occasion", self.occasion_edit)

        self.required_fields_list = QListWidget()
        self.required_fields_list.setObjectName("transition_required_fields")
        self.required_fields_list.setMaximumHeight(140)
        form.addRow("Must hold a value first", self.required_fields_list)

        self.precondition_edit = QPlainTextEdit()
        self.precondition_edit.setObjectName("transition_precondition")
        self.precondition_edit.setPlaceholderText(
            "Any further condition, in words"
        )
        self.precondition_edit.setMaximumHeight(70)
        form.addRow("And this must be true", self.precondition_edit)

        self.consequences_list = QListWidget()
        self.consequences_list.setObjectName("transition_consequences")
        self.consequences_list.setMaximumHeight(140)
        form.addRow("Happens automatically", self.consequences_list)

        self.consequence_notes_edit = QPlainTextEdit()
        self.consequence_notes_edit.setObjectName(
            "transition_consequence_notes"
        )
        self.consequence_notes_edit.setPlaceholderText(
            "An automatic action with no record yet — this move will be "
            "reported as incomplete until one exists"
        )
        self.consequence_notes_edit.setMaximumHeight(70)
        form.addRow("Still owed a record", self.consequence_notes_edit)

        self.manual_edit = QPlainTextEdit()
        self.manual_edit.setObjectName("transition_manual_follow_up")
        self.manual_edit.setPlaceholderText(
            "What a person does by hand afterwards — never counted as "
            "incomplete"
        )
        self.manual_edit.setMaximumHeight(70)
        form.addRow("Done by hand afterwards", self.manual_edit)

        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setObjectName("transition_notes")
        self.notes_edit.setMaximumHeight(70)
        form.addRow("Internal notes", self.notes_edit)

        outer.addLayout(form)

        self.message = QLabel("")
        self.message.setObjectName("transition_dialog_message")
        self.message.setWordWrap(True)
        self.message.setVisible(False)
        outer.addWidget(self.message)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("transition_cancel")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.save_button = primary_button("Save")
        self.save_button.setObjectName("transition_save")
        self.save_button.clicked.connect(self._on_save)
        buttons.addWidget(self.save_button)
        outer.addLayout(buttons)

    # -- choices -----------------------------------------------------------

    def _load_choices(self) -> None:
        """Read from the store every list the form offers."""
        try:
            touching = self._client.list_references_touching(
                "process", self._process
            )
        except (StorageClientError, StorageConnectionError):
            touching = {"as_source": [], "as_target": []}
        self._touched_entities = [
            edge["target_id"]
            for edge in touching.get("as_source", [])
            if edge.get("relationship") == "process_touches_entity"
        ]
        performer_ids = {
            edge["target_id"]
            for edge in touching.get("as_source", [])
            if edge.get("relationship") == "process_performed_by_persona"
        }

        status_fields: list[dict[str, Any]] = []
        for entity_identifier in self._touched_entities:
            try:
                rows = self._client.list_fields(
                    entity_identifier=entity_identifier
                )
            except (StorageClientError, StorageConnectionError):
                rows = []
            self._fields_by_entity[entity_identifier] = rows
            status_fields.extend(
                row
                for row in rows
                if row.get("field_type") == CHOICE_FIELD_TYPE
            )
        self._status_fields = status_fields
        self.status_field_combo.clear()
        for row in status_fields:
            self.status_field_combo.addItem(
                f"{row['field_name']} ({row['field_identifier']})",
                row["field_identifier"],
            )

        try:
            personas = self._client.list_personas()
        except (StorageClientError, StorageConnectionError):
            personas = []
        self._personas = [
            p for p in personas if p["persona_identifier"] in performer_ids
        ] or personas
        self.actor_combo.clear()
        self.actor_combo.addItem("The system", "system")
        for row in self._personas:
            self.actor_combo.addItem(
                f"{row['persona_name']} ({row['persona_identifier']})",
                row["persona_identifier"],
            )

        self._load_consequence_choices()
        self._reload_value_lists()
        self._reload_required_field_list()

    def _load_consequence_choices(self) -> None:
        choices: list[tuple[str, str]] = []

        def _collect(rows, id_key, name_key, prefix) -> None:
            for row in rows:
                identifier = row.get(id_key)
                if not identifier:
                    continue
                label = (
                    f"{row.get(name_key) or identifier} "
                    f"({_CONSEQUENCE_PREFIX_LABELS[prefix]}, {identifier})"
                )
                choices.append((label, identifier))

        try:
            _collect(
                self._client.list_automations(),
                "automation_identifier",
                "automation_name",
                "AUT",
            )
            _collect(
                self._client.list_message_templates(),
                "message_template_identifier",
                "message_template_name",
                "MSG",
            )
            _collect(
                self._client.list_views(), "view_identifier", "view_name", "VEW"
            )
            _collect(
                self._client.list_processes(),
                "process_identifier",
                "process_name",
                "PROC",
            )
            for row in self._client.list_transitions(
                process_identifier=self._process
            ):
                identifier = row["transition_identifier"]
                if identifier == self._record.get("transition_identifier"):
                    continue
                choices.append(
                    (
                        f"the move to {row['transition_to_value']} "
                        f"(move, {identifier})",
                        identifier,
                    )
                )
        except (StorageClientError, StorageConnectionError):
            pass
        self._consequence_choices = choices

        chosen = set(self._record.get("transition_consequences") or [])
        self.consequences_list.clear()
        for label, identifier in choices:
            _add_tickable(
                self.consequences_list,
                label,
                identifier,
                ticked=identifier in chosen,
            )

    def _current_status_field(self) -> dict[str, Any] | None:
        identifier = self.status_field_combo.currentData()
        for row in self._status_fields:
            if row["field_identifier"] == identifier:
                return row
        return None

    def _option_values(self) -> list[str]:
        row = self._current_status_field()
        if row is None:
            return []
        options = row.get("field_options") or []
        if not options:
            try:
                options = (
                    self._client.get_field(row["field_identifier"]).get(
                        "field_options"
                    )
                    or []
                )
            except (StorageClientError, StorageConnectionError):
                options = []
            row["field_options"] = options
        return [option["option_value"] for option in options]

    def _reload_value_lists(self) -> None:
        values = self._option_values()
        chosen_from = set(self._record.get("transition_from_values") or [])
        self.from_values_list.clear()
        for value in values:
            _add_tickable(
                self.from_values_list, value, value, ticked=value in chosen_from
            )
        current_to = self._record.get("transition_to_value")
        self.to_value_combo.clear()
        for value in values:
            self.to_value_combo.addItem(value, value)
        if current_to in values:
            self.to_value_combo.setCurrentIndex(values.index(current_to))

    def _reload_required_field_list(self) -> None:
        chosen = set(self._record.get("transition_required_fields") or [])
        self.required_fields_list.clear()
        for entity_identifier in self._touched_entities:
            for row in self._fields_by_entity.get(entity_identifier, []):
                identifier = row["field_identifier"]
                _add_tickable(
                    self.required_fields_list,
                    f"{row['field_name']} ({identifier})",
                    identifier,
                    ticked=identifier in chosen,
                )

    # -- state -------------------------------------------------------------

    def _on_status_field_changed(self, _index: int) -> None:
        self._reload_value_lists()

    def _on_from_kind_toggled(self, checked: bool) -> None:
        self.from_values_list.setEnabled(not checked)

    def _populate_from_record(self) -> None:
        if not self._record:
            return
        field_identifier = self._record.get("transition_field")
        index = self.status_field_combo.findData(field_identifier)
        if index >= 0:
            self.status_field_combo.setCurrentIndex(index)
        self._reload_value_lists()
        self.from_creation_check.setChecked(
            self._record.get("transition_from_kind") == "record_creation"
        )
        actor = (
            "system"
            if self._record.get("transition_actor_kind") == "system"
            else self._record.get("transition_actor_persona")
        )
        actor_index = self.actor_combo.findData(actor)
        if actor_index >= 0:
            self.actor_combo.setCurrentIndex(actor_index)
        self.occasion_edit.setText(
            self._record.get("transition_actor_occasion") or ""
        )
        self.precondition_edit.setPlainText(
            self._record.get("transition_precondition") or ""
        )
        self.consequence_notes_edit.setPlainText(
            self._record.get("transition_consequence_notes") or ""
        )
        self.manual_edit.setPlainText(
            self._record.get("transition_manual_follow_up") or ""
        )
        self.notes_edit.setPlainText(
            self._record.get("transition_notes") or ""
        )

    # -- save --------------------------------------------------------------

    def body(self) -> dict[str, Any]:
        """The request body the form describes."""
        from_creation = self.from_creation_check.isChecked()
        actor = self.actor_combo.currentData()
        occasion = self.occasion_edit.text().strip()
        precondition = self.precondition_edit.toPlainText().strip()
        words = self.consequence_notes_edit.toPlainText().strip()
        by_hand = self.manual_edit.toPlainText().strip()
        notes = self.notes_edit.toPlainText().strip()
        return {
            "transition_process": self._process,
            "transition_field": self.status_field_combo.currentData(),
            "transition_from_kind": (
                "record_creation" if from_creation else "values"
            ),
            "transition_from_values": (
                [] if from_creation else _ticked(self.from_values_list)
            ),
            "transition_to_value": self.to_value_combo.currentData(),
            "transition_actor_kind": (
                "system" if actor == "system" else "persona"
            ),
            "transition_actor_persona": (
                None if actor == "system" else actor
            ),
            "transition_actor_occasion": occasion or None,
            "transition_required_fields": _ticked(self.required_fields_list),
            "transition_precondition": precondition or None,
            "transition_consequences": _ticked(self.consequences_list),
            "transition_consequence_notes": words or None,
            "transition_manual_follow_up": by_hand or None,
            "transition_notes": notes or None,
        }

    def _show_message(self, text: str) -> None:
        self.message.setText(text)
        self.message.setVisible(True)

    def _on_save(self) -> None:
        body = self.body()
        if not body["transition_field"]:
            self._show_message(
                "Choose the status field this move changes. If the list is "
                "empty, the process touches no entity that has a choice field."
            )
            return
        if not body["transition_to_value"]:
            self._show_message("Choose the value this move goes to.")
            return
        try:
            if self._editing:
                identifier = self._record["transition_identifier"]
                self.saved_record = self._client.update_transition(
                    identifier, body
                )
            else:
                self.saved_record = self._client.create_transition(body)
        except StorageConnectionError as exc:
            ErrorDialog.show_error(
                self,
                title="Could not reach the store",
                message="The status move was not saved.",
                detail=str(exc),
            )
            return
        except StorageClientError as exc:
            # A refused check names itself; show that rather than a generic
            # failure, so the user can see which rule the move broke.
            self._show_message(str(exc))
            _log.info("transition save refused: %s", exc)
            return
        self.accept()

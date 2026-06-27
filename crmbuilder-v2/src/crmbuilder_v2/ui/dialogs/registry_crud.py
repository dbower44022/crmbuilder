"""Agent Profile Registry CRUD + binding + promotion dialogs (PI-330 / REQ-367).

Thin subclasses of the shared ``EntityCrudDialog`` / ``EntityCrudDeleteDialog``
for the four registry entities, plus three registry-specific dialogs:

* ``JsonFieldDialog`` — edit one JSON column (capability_description / io_contract
  / predicate) with parse validation, patching via a supplied callback.
* ``BindingPickerDialog`` — pick a skill or governance_rule to bind to a profile.
* ``PromoteToSkillDialog`` / ``PromoteToRuleDialog`` — promote a learning.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.access.vocab import RULE_ENFORCEMENT_MODES, SKILL_KINDS
from crmbuilder_v2.ui.base.crud_dialog import (
    EntityCrudDeleteDialog,
    EntityCrudDialog,
)
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._registry_schemas import (
    agent_profile_fields,
    governance_rule_fields,
    learning_fields,
    skill_fields,
)
from crmbuilder_v2.ui.exceptions import StorageClientError, StorageConnectionError

_IDENTIFIER_FIELD = "identifier"


# ---------------------------------------------------------------------------
# Agent profiles
# ---------------------------------------------------------------------------


class AgentProfileCreateDialog(EntityCrudDialog):
    def __init__(self, client: StorageClient, parent: QWidget | None = None) -> None:
        super().__init__(
            client,
            agent_profile_fields(client, include_identifier=False),
            mode="create",
            title="New agent profile",
            create_method=client.create_agent_profile,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )

    def created_identifier(self) -> str | None:
        return self.saved_identifier()


class AgentProfileEditDialog(EntityCrudDialog):
    def __init__(
        self, client: StorageClient, record: dict[str, Any], parent: QWidget | None = None
    ) -> None:
        identifier = str(record.get(_IDENTIFIER_FIELD) or "")
        super().__init__(
            client,
            agent_profile_fields(client, include_identifier=True),
            mode="edit",
            title=f"Edit {identifier}" if identifier else "Edit agent profile",
            update_method=client.patch_agent_profile,
            record=record,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )


class AgentProfileDeleteDialog(EntityCrudDeleteDialog):
    def __init__(
        self, client: StorageClient, identifier: str, title: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(
            client, identifier, title, client.delete_agent_profile,
            entity_label="agent profile", parent=parent,
        )


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------


class SkillCreateDialog(EntityCrudDialog):
    def __init__(self, client: StorageClient, parent: QWidget | None = None) -> None:
        super().__init__(
            client,
            skill_fields(client, include_identifier=False),
            mode="create",
            title="New skill",
            create_method=client.create_skill,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )

    def created_identifier(self) -> str | None:
        return self.saved_identifier()


class SkillEditDialog(EntityCrudDialog):
    def __init__(
        self, client: StorageClient, record: dict[str, Any], parent: QWidget | None = None
    ) -> None:
        identifier = str(record.get(_IDENTIFIER_FIELD) or "")
        super().__init__(
            client,
            skill_fields(client, include_identifier=True),
            mode="edit",
            title=f"Edit {identifier}" if identifier else "Edit skill",
            update_method=client.patch_skill,
            record=record,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )


class SkillDeleteDialog(EntityCrudDeleteDialog):
    def __init__(
        self, client: StorageClient, identifier: str, title: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(
            client, identifier, title, client.delete_skill,
            entity_label="skill", parent=parent,
        )


# ---------------------------------------------------------------------------
# Governance rules
# ---------------------------------------------------------------------------


class GovernanceRuleCreateDialog(EntityCrudDialog):
    def __init__(self, client: StorageClient, parent: QWidget | None = None) -> None:
        super().__init__(
            client,
            governance_rule_fields(client, include_identifier=False),
            mode="create",
            title="New governance rule",
            create_method=client.create_governance_rule,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )

    def created_identifier(self) -> str | None:
        return self.saved_identifier()


class GovernanceRuleEditDialog(EntityCrudDialog):
    def __init__(
        self, client: StorageClient, record: dict[str, Any], parent: QWidget | None = None
    ) -> None:
        identifier = str(record.get(_IDENTIFIER_FIELD) or "")
        super().__init__(
            client,
            governance_rule_fields(client, include_identifier=True),
            mode="edit",
            title=f"Edit {identifier}" if identifier else "Edit governance rule",
            update_method=client.patch_governance_rule,
            record=record,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )


class GovernanceRuleDeleteDialog(EntityCrudDeleteDialog):
    def __init__(
        self, client: StorageClient, identifier: str, title: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(
            client, identifier, title, client.delete_governance_rule,
            entity_label="governance rule", parent=parent,
        )


# ---------------------------------------------------------------------------
# Learnings
# ---------------------------------------------------------------------------


class LearningCreateDialog(EntityCrudDialog):
    def __init__(self, client: StorageClient, parent: QWidget | None = None) -> None:
        super().__init__(
            client,
            learning_fields(client, include_identifier=False),
            mode="create",
            title="New learning",
            create_method=client.create_learning,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )

    def created_identifier(self) -> str | None:
        return self.saved_identifier()


class LearningEditDialog(EntityCrudDialog):
    def __init__(
        self, client: StorageClient, record: dict[str, Any], parent: QWidget | None = None
    ) -> None:
        identifier = str(record.get(_IDENTIFIER_FIELD) or "")
        super().__init__(
            client,
            learning_fields(client, include_identifier=True),
            mode="edit",
            title=f"Edit {identifier}" if identifier else "Edit learning",
            update_method=client.patch_learning,
            record=record,
            identifier_field=_IDENTIFIER_FIELD,
            parent=parent,
        )


class LearningDeleteDialog(EntityCrudDeleteDialog):
    def __init__(
        self, client: StorageClient, identifier: str, title: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(
            client, identifier, title, client.delete_learning,
            entity_label="learning", parent=parent,
        )


# ---------------------------------------------------------------------------
# JSON-column editor (capability_description / io_contract / predicate)
# ---------------------------------------------------------------------------


class JsonFieldDialog(QDialog):
    """Edit a single JSON column, validate it, and patch the record.

    ``patch`` is ``client.patch_<entity>``; it is called as
    ``patch(identifier, {field_key: parsed_or_None})``. An empty editor clears
    the column (patches it to ``null``).
    """

    def __init__(
        self,
        patch: Callable[[str, dict[str, Any]], dict[str, Any]],
        identifier: str,
        field_key: str,
        field_label: str,
        current_value: Any,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._patch = patch
        self._identifier = identifier
        self._field_key = field_key
        self.setWindowTitle(f"Edit {field_label} — {identifier}")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"{field_label} (JSON; leave empty to clear):"))
        self._editor = QPlainTextEdit()
        if current_value not in (None, ""):
            self._editor.setPlainText(json.dumps(current_value, indent=2))
        self._editor.setMinimumHeight(220)
        layout.addWidget(self._editor)

        self._error = QLabel("")
        self._error.setStyleSheet("color: #C62828;")
        self._error.setWordWrap(True)
        self._error.setVisible(False)
        layout.addWidget(self._error)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_save(self) -> None:
        raw = self._editor.toPlainText().strip()
        if raw == "":
            parsed: Any = None
        else:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                self._error.setText(f"Invalid JSON: {exc}")
                self._error.setVisible(True)
                return
        try:
            self._patch(self._identifier, {self._field_key: parsed})
        except (StorageClientError, StorageConnectionError) as exc:
            self._error.setText(str(exc))
            self._error.setVisible(True)
            return
        self.accept()


# ---------------------------------------------------------------------------
# Binding picker (bind a skill or governance rule to an agent profile)
# ---------------------------------------------------------------------------


class BindingPickerDialog(QDialog):
    """Pick one candidate record's identifier to bind to a profile.

    ``candidates`` is a list of ``(identifier, label)`` pairs already filtered
    to the not-yet-bound records. The selected identifier is read via
    ``selected_identifier()`` after an accepted exec.
    """

    def __init__(
        self,
        title: str,
        candidates: list[tuple[str, str]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(480)
        self._selected: str | None = None

        layout = QVBoxLayout(self)
        if candidates:
            layout.addWidget(QLabel("Select one to bind:"))
            self._list = QListWidget()
            for identifier, label in candidates:
                item = QListWidgetItem(f"{identifier} — {label}")
                item.setData(256, identifier)  # Qt.UserRole
                self._list.addItem(item)
            self._list.setCurrentRow(0)
            self._list.itemDoubleClicked.connect(lambda _i: self._on_ok())
            layout.addWidget(self._list)
        else:
            self._list = None
            layout.addWidget(QLabel("Nothing available to bind (all are already bound)."))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_ok(self) -> None:
        if self._list is not None and self._list.currentItem() is not None:
            self._selected = self._list.currentItem().data(256)
        self.accept()

    def selected_identifier(self) -> str | None:
        return self._selected


# ---------------------------------------------------------------------------
# Learning promotion
# ---------------------------------------------------------------------------


class PromoteToSkillDialog(QDialog):
    """Promote a learning to a skill (name + kind + optional description)."""

    def __init__(self, learning: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Promote {learning.get('identifier', '')} to skill")
        self.setMinimumWidth(460)
        self._body: dict[str, Any] | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._name = QLineEdit()
        form.addRow("Name", self._name)
        self._kind = QComboBox()
        for k in sorted(SKILL_KINDS):
            self._kind.addItem(k)
        form.addRow("Kind", self._kind)
        self._description = QPlainTextEdit()
        self._description.setPlainText(learning.get("content") or "")
        self._description.setMinimumHeight(120)
        form.addRow("Description", self._description)
        layout.addLayout(form)

        self._error = QLabel("")
        self._error.setStyleSheet("color: #C62828;")
        self._error.setVisible(False)
        layout.addWidget(self._error)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_ok(self) -> None:
        name = self._name.text().strip()
        if not name:
            self._error.setText("Name is required.")
            self._error.setVisible(True)
            return
        self._body = {
            "name": name,
            "kind": self._kind.currentText(),
            "description": self._description.toPlainText().strip() or None,
        }
        self.accept()

    def body(self) -> dict[str, Any] | None:
        return self._body


class PromoteToRuleDialog(QDialog):
    """Promote a learning to a governance rule.

    Enforced rules require an explicit human-approval acknowledgement (the
    Needs-Attention hard line): the OK button stays gated until the operator
    checks the approval box when enforcement is not advisory.
    """

    def __init__(self, learning: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Promote {learning.get('identifier', '')} to rule")
        self.setMinimumWidth(460)
        self._body: dict[str, Any] | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._enforcement = QComboBox()
        for mode in sorted(RULE_ENFORCEMENT_MODES):
            self._enforcement.addItem(mode)
        form.addRow("Enforcement", self._enforcement)
        self._body_edit = QPlainTextEdit()
        self._body_edit.setPlainText(learning.get("content") or "")
        self._body_edit.setMinimumHeight(120)
        form.addRow("Rule body", self._body_edit)
        self._rule_type = QLineEdit()
        form.addRow("Rule type", self._rule_type)
        self._severity = QLineEdit()
        form.addRow("Severity", self._severity)
        layout.addLayout(form)

        self._approve = QCheckBox(
            "I have reviewed and approve promoting this to an enforced rule."
        )
        layout.addWidget(self._approve)

        self._error = QLabel("")
        self._error.setStyleSheet("color: #C62828;")
        self._error.setVisible(False)
        layout.addWidget(self._error)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_ok(self) -> None:
        enforcement = self._enforcement.currentText()
        approved = self._approve.isChecked()
        if enforcement != "advisory" and not approved:
            self._error.setText(
                "Enforced rules require the human-approval acknowledgement above."
            )
            self._error.setVisible(True)
            return
        self._body = {
            "enforcement": enforcement,
            "body": self._body_edit.toPlainText().strip() or None,
            "rule_type": self._rule_type.text().strip() or None,
            "severity": self._severity.text().strip() or None,
            "human_approved": approved,
        }
        self.accept()

    def body(self) -> dict[str, Any] | None:
        return self._body


# ---------------------------------------------------------------------------
# Learning evidence + confidence (PI-336 / DEC-762)
# ---------------------------------------------------------------------------

# Evidence targets accepted by POST /learnings/{id}/evidence
# (access/repositories/learnings.py _DERIVED_TARGETS). Contradicting evidence
# must be a work_task.
_EVIDENCE_TARGETS = ("work_task", "decision", "test_spec")


class AddEvidenceDialog(QDialog):
    """Link supporting or contradicting evidence to a learning.

    Supporting evidence (a work_task / decision / test_spec) raises the
    learning's confidence; contradicting evidence must be a work_task and lowers
    it. The dialog returns the evidence payload via ``body()``.
    """

    def __init__(self, learning: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Add evidence — {learning.get('identifier', '')}")
        self.setMinimumWidth(460)
        self._body: dict[str, Any] | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Supporting evidence raises confidence; contradicting evidence "
                "(work_task only) lowers it."
            )
        )
        form = QFormLayout()
        self._target_type = QComboBox()
        for t in _EVIDENCE_TARGETS:
            self._target_type.addItem(t)
        form.addRow("Evidence type", self._target_type)
        self._target_id = QLineEdit()
        self._target_id.setPlaceholderText("Identifier, e.g. WTK-012 / DEC-415 / TST-003")
        form.addRow("Evidence identifier", self._target_id)
        layout.addLayout(form)

        self._contradicts = QCheckBox("This evidence contradicts the learning (work_task only)")
        self._contradicts.toggled.connect(self._on_contradicts_toggled)
        layout.addWidget(self._contradicts)

        self._error = QLabel("")
        self._error.setStyleSheet("color: #C62828;")
        self._error.setWordWrap(True)
        self._error.setVisible(False)
        layout.addWidget(self._error)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_contradicts_toggled(self, checked: bool) -> None:
        # Contradicting evidence must be a work_task; pin + lock the combo.
        if checked:
            idx = self._target_type.findText("work_task")
            if idx >= 0:
                self._target_type.setCurrentIndex(idx)
            self._target_type.setEnabled(False)
        else:
            self._target_type.setEnabled(True)

    def _on_ok(self) -> None:
        target_id = self._target_id.text().strip()
        if not target_id:
            self._error.setText("An evidence identifier is required.")
            self._error.setVisible(True)
            return
        self._body = {
            "target_type": self._target_type.currentText(),
            "target_id": target_id,
            "contradicts": self._contradicts.isChecked(),
        }
        self.accept()

    def body(self) -> dict[str, Any] | None:
        return self._body


class SetConfidenceDialog(QDialog):
    """Set a learning's confidence directly.

    Confidence is normally evidence-derived, but a direct override is useful for
    a manually-authored learning that needs to reach an agent's effective
    contract (the resolver gates active_learnings on confidence >= 1).
    """

    def __init__(self, current: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Set confidence")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel("Confidence (0 = unevidenced hunch; >= 1 reaches matching agents):")
        )
        self._spin = QSpinBox()
        self._spin.setRange(0, 1000)
        self._spin.setValue(max(0, int(current or 0)))
        layout.addWidget(self._spin)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self) -> int:
        return self._spin.value()

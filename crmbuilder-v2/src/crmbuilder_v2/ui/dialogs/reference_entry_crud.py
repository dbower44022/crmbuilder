"""Reference Entry CRUD dialogs (REL-016 / PI-067, REQ-402).

Bespoke create/edit dialogs for the ``reference_entry`` registry entity. Unlike
the other registry entities, a reference entry carries a **required per-kind JSON
``content``** payload and a ``trigger_keywords`` list, which the generic
``EntityCrudDialog`` (string-valued widgets, no JSON) cannot author — so these
dialogs edit the JSON directly (a per-kind template guides the operator) and
parse it on save, mirroring ``JsonFieldDialog``'s synchronous validate-then-call
pattern. Delete reuses the shared ``EntityCrudDeleteDialog``.
"""

from __future__ import annotations

import json
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

from crmbuilder_v2.access.vocab import REFERENCE_ENTRY_KINDS, REGISTRY_STATUSES
from crmbuilder_v2.ui.base.crud_dialog import EntityCrudDeleteDialog
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.exceptions import StorageClientError, StorageConnectionError

_SYSTEM_SCOPE = "system"

# Per-kind starter content, inserted to guide the operator (DEC-887 shapes).
_CONTENT_TEMPLATES: dict[str, dict] = {
    "domain_knowledge": {"body": ""},
    "organization_structure": {"typical_entities": [], "typical_relationships": []},
    "inventory_items": {"entities": [], "personas": [], "processes": []},
}
_KIND_ORDER = ("domain_knowledge", "organization_structure", "inventory_items")


def _scope_values(client: StorageClient) -> list[str]:
    values = [_SYSTEM_SCOPE]
    try:
        for eng in client.list_engagements():
            ident = eng.get("engagement_identifier") or eng.get("identifier")
            if ident and ident not in values:
                values.append(str(ident))
    except Exception:  # noqa: BLE001 — scope still works with system-only.
        pass
    return values


class _ReferenceEntryDialog(QDialog):
    """Shared form for create + edit."""

    def __init__(
        self,
        client: StorageClient,
        *,
        title: str,
        record: dict[str, Any] | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._record = record or {}
        self._saved_identifier: str | None = None
        self.setWindowTitle(title)
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)

        self._name = QLineEdit(self._record.get("name") or "")
        self._name.setObjectName("reference_entry_name")
        form.addRow("Name", self._name)

        self._kind = QComboBox()
        self._kind.setObjectName("reference_entry_kind")
        self._kind.addItems([k for k in _KIND_ORDER if k in REFERENCE_ENTRY_KINDS])
        current_kind = self._record.get("kind") or "domain_knowledge"
        idx = self._kind.findText(current_kind)
        if idx >= 0:
            self._kind.setCurrentIndex(idx)
        self._kind.currentTextChanged.connect(self._on_kind_changed)
        form.addRow("Kind", self._kind)

        self._applies_to = QLineEdit(self._record.get("applies_to") or "")
        self._applies_to.setObjectName("reference_entry_applies_to")
        self._applies_to.setPlaceholderText("Org type / domain, e.g. nonprofit mentoring")
        form.addRow("Applies to", self._applies_to)

        kws = self._record.get("trigger_keywords") or []
        self._keywords = QLineEdit(", ".join(kws) if isinstance(kws, list) else "")
        self._keywords.setObjectName("reference_entry_keywords")
        self._keywords.setPlaceholderText("Comma-separated match terms for the loader")
        form.addRow("Trigger keywords", self._keywords)

        self._status = QComboBox()
        self._status.addItems(sorted(REGISTRY_STATUSES))
        st = self._record.get("status") or "active"
        j = self._status.findText(st)
        if j >= 0:
            self._status.setCurrentIndex(j)
        form.addRow("Status", self._status)

        self._scope = QComboBox()
        self._scope.setObjectName("reference_entry_scope")
        self._scope.addItems(_scope_values(client))
        sc = self._record.get("scope") or _SYSTEM_SCOPE
        k = self._scope.findText(sc)
        if k >= 0:
            self._scope.setCurrentIndex(k)
        form.addRow("Scope", self._scope)

        layout.addLayout(form)

        layout.addWidget(QLabel("Content (JSON):"))
        self._content = QPlainTextEdit()
        self._content.setObjectName("reference_entry_content")
        self._content.setMinimumHeight(180)
        existing = self._record.get("content")
        if existing:
            self._content.setPlainText(json.dumps(existing, indent=2))
        else:
            self._content.setPlainText(
                json.dumps(_CONTENT_TEMPLATES[current_kind], indent=2)
            )
        layout.addWidget(self._content)

        self._error = QLabel("")
        self._error.setStyleSheet("color: #C62828;")
        self._error.setWordWrap(True)
        self._error.setVisible(False)
        layout.addWidget(self._error)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_kind_changed(self, kind: str) -> None:
        """Swap the content template when the editor still holds a template."""
        current = self._content.toPlainText().strip()
        template_texts = {
            json.dumps(t, indent=2) for t in _CONTENT_TEMPLATES.values()
        }
        if current in template_texts or current == "":
            self._content.setPlainText(
                json.dumps(_CONTENT_TEMPLATES.get(kind, {}), indent=2)
            )

    def _fail(self, message: str) -> None:
        self._error.setText(message)
        self._error.setVisible(True)

    def _build_body(self) -> dict[str, Any] | None:
        name = self._name.text().strip()
        if not name:
            self._fail("Name is required.")
            return None
        raw = self._content.toPlainText().strip()
        try:
            content = json.loads(raw) if raw else None
        except json.JSONDecodeError as exc:
            self._fail(f"Invalid content JSON: {exc}")
            return None
        keywords = [
            k.strip() for k in self._keywords.text().split(",") if k.strip()
        ]
        return {
            "name": name,
            "kind": self._kind.currentText(),
            "applies_to": self._applies_to.text().strip() or None,
            "trigger_keywords": keywords or None,
            "content": content,
            "status": self._status.currentText(),
            "scope": self._scope.currentText(),
        }

    def _persist(self, body: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def _on_save(self) -> None:
        body = self._build_body()
        if body is None:
            return
        try:
            saved = self._persist(body)
        except (StorageClientError, StorageConnectionError) as exc:
            self._fail(str(exc))
            return
        self._saved_identifier = saved.get("identifier")
        self.accept()

    def created_identifier(self) -> str | None:
        return self._saved_identifier


class ReferenceEntryCreateDialog(_ReferenceEntryDialog):
    def __init__(self, client: StorageClient, parent: QWidget | None = None) -> None:
        super().__init__(
            client, title="New reference entry", record=None, parent=parent
        )

    def _persist(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._client.create_reference_entry(body)


class ReferenceEntryEditDialog(_ReferenceEntryDialog):
    def __init__(
        self,
        client: StorageClient,
        record: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        identifier = str(record.get("identifier") or "")
        super().__init__(
            client,
            title=f"Edit {identifier}" if identifier else "Edit reference entry",
            record=record,
            parent=parent,
        )
        self._identifier = identifier

    def _persist(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._client.patch_reference_entry(self._identifier, body)


class ReferenceEntryDeleteDialog(EntityCrudDeleteDialog):
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
            client.delete_reference_entry,
            entity_label="reference entry",
            parent=parent,
        )

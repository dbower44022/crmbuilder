"""Per-instance feature-selection dialog (PI-444 / REQ-546).

Edits the instance's stored feature selection — which design entities are
active for this chapter's instance (DEC-976/977). The selection is stored on
the instance record (``instance_feature_selection``, a list of ``ENT-NNN``
design-entity identifiers) and drives the publish scope automatically; no
selection means the full design is published.

The dialog lists every live design entity with a checkbox, pre-checked from
the stored selection (everything checked reads as "about to store an explicit
full list" — distinct from *no* selection, which follows the design as it
grows). Stored identifiers that no longer resolve to a design entity are shown
flagged so saving consciously keeps or drops them. "Save selection" PATCHes
the checked identifiers; "Clear selection" stores NULL (publish the full
design).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.exceptions import StorageClientError
from crmbuilder_v2.ui.widgets.form_helpers import primary_button
from crmbuilder_v2.ui.widgets.selectable_text import CopyableMessageBox

_IDENTIFIER_ROLE = Qt.ItemDataRole.UserRole


class FeatureSelectionDialog(QDialog):
    """Check the design entities that a bare publish sends to this instance."""

    def __init__(
        self,
        client: StorageClient,
        record: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._record = record
        self._identifier = str(record.get("instance_identifier") or "")
        self._saved_record: dict[str, Any] | None = None
        name = record.get("instance_name") or self._identifier

        self.setWindowTitle(f"Feature selection — {name}")
        self.resize(520, 480)

        layout = QVBoxLayout(self)
        intro = QLabel(
            "Design entities checked here are what a publish sends to this "
            "instance when no per-run scope is chosen. No stored selection "
            "means the full design is always published (including entities "
            "added later)."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._list = QListWidget()
        self._list.setObjectName("feature_selection_list")
        layout.addWidget(self._list, 1)

        row = QHBoxLayout()
        self._clear_btn = QPushButton("Clear selection (full design)")
        self._clear_btn.setObjectName("clear_feature_selection_button")
        self._clear_btn.clicked.connect(self._on_clear_clicked)
        self._save_btn = primary_button("Save selection")
        self._save_btn.setObjectName("save_feature_selection_button")
        self._save_btn.clicked.connect(self._on_save_clicked)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        row.addWidget(self._clear_btn)
        row.addStretch(1)
        row.addWidget(self._save_btn)
        row.addWidget(cancel_btn)
        layout.addLayout(row)

        self._populate()

    # -- population ------------------------------------------------------

    def _populate(self) -> None:
        stored = list(self._record.get("instance_feature_selection") or [])
        try:
            entities = self._client.list_entities()
        except StorageClientError as exc:
            self._status.setText(f"Could not load the design entities: {exc}")
            self._save_btn.setEnabled(False)
            self._clear_btn.setEnabled(False)
            return

        known: set[str] = set()
        for ent in entities:
            eid = ent.get("entity_identifier") or ""
            if not eid:
                continue
            known.add(eid)
            label = f"{eid} — {ent.get('entity_name') or '(unnamed)'}"
            self._add_item(eid, label, checked=eid in stored)

        # Stored identifiers that no longer resolve to a design entity stay
        # visible and flagged: saving with them checked keeps them; unchecking
        # drops them (they contribute nothing to a publish either way).
        for eid in stored:
            if eid not in known:
                self._add_item(
                    eid, f"{eid} — (no longer in the design)", checked=True
                )

        if stored:
            self._status.setText(
                f"Stored selection: {len(stored)} entit"
                f"{'y' if len(stored) == 1 else 'ies'}."
            )
        else:
            self._status.setText(
                "No stored selection — publishes the full design."
            )

    def _add_item(self, identifier: str, label: str, *, checked: bool) -> None:
        item = QListWidgetItem(label)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(
            Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        )
        item.setData(_IDENTIFIER_ROLE, identifier)
        self._list.addItem(item)

    # -- reads -----------------------------------------------------------

    def _checked_identifiers(self) -> list[str]:
        return [
            self._list.item(i).data(_IDENTIFIER_ROLE)
            for i in range(self._list.count())
            if self._list.item(i).checkState() == Qt.CheckState.Checked
        ]

    def saved_record(self) -> dict[str, Any] | None:
        """The updated instance record after an accepted save, else ``None``."""
        return self._saved_record

    # -- actions ---------------------------------------------------------

    def _on_save_clicked(self) -> None:
        checked = self._checked_identifiers()
        if not checked:
            CopyableMessageBox.information(
                self,
                "Nothing selected",
                "No entities are checked. To publish the full design, use "
                "Clear selection; otherwise check at least one entity.",
            )
            return
        self._patch(checked)

    def _on_clear_clicked(self) -> None:
        self._patch(None)

    def _patch(self, selection: list[str] | None) -> None:
        try:
            self._saved_record = self._client.patch_instance(
                self._identifier,
                {"instance_feature_selection": selection},
            )
        except StorageClientError as exc:
            CopyableMessageBox.warning(
                self, "Save failed", f"Could not save the selection: {exc}"
            )
            return
        self.accept()

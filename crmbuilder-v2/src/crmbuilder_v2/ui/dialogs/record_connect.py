"""Record-side connection form — REQ-563 / PI-464 (DEC-1042, DEC-1043).

Opened from a record's own detail view (the ReferencesSection "Add
reference" affordance) in place of the generic cascading
:class:`~crmbuilder_v2.ui.dialogs.reference_create.ReferenceCreateDialog`.
The starting record is already known, so the form never shows a source
type or source identifier. It asks one question — "connected to what,
and how?" — in three steps:

1. **Relationship** — only the kinds the vocabulary allows from this
   record's type (``kinds_for_source``).
2. **Target type** — derived from the chosen kind
   (``target_types_for``); auto-selected when only one applies.
3. **Target records** — every live record of that type, by identifier
   and name, each with a tick box. Records already connected by the same
   kind are pre-ticked and locked so the unique-tuple index cannot be
   tripped. A filter box narrows long lists.

Saving creates one reference per newly ticked record, in order, on a
worker thread. A partial failure reports what was created and what
failed and leaves the dialog open with the created rows now locked, so
a retry cannot double-create.

The generic dialog remains the References pane's form (REQ-562): that
pane starts with nothing chosen and must ask for both ends.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.access.vocab import kinds_for_source, target_types_for
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.dialogs.reference_create import list_records_for_type
from crmbuilder_v2.ui.elevation import apply_dialog_shadow
from crmbuilder_v2.ui.exceptions import StorageConnectionError
from crmbuilder_v2.ui.styling import t
from crmbuilder_v2.ui.widgets.form_helpers import primary_button, required_label
from crmbuilder_v2.ui.widgets.modal_backdrop import attach as _backdrop_attach
from crmbuilder_v2.ui.widgets.modal_backdrop import detach as _backdrop_detach

_log = logging.getLogger("crmbuilder_v2.ui.dialogs.record_connect")

LinkKey = tuple[str, str, str]
"""``(relationship, target_type, target_id)`` — an outbound reference
already held by the source record."""


class RecordConnectDialog(QDialog):
    """Multi-select connection form for one known source record."""

    def __init__(
        self,
        client: StorageClient,
        *,
        source_type: str,
        source_id: str,
        existing: set[LinkKey] | frozenset[LinkKey] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._source_type = source_type
        self._source_id = source_id
        self._existing: set[LinkKey] = set(existing or ())
        self._records_cache: dict[str, list[tuple[str, str]]] = {}
        self._created: list[dict[str, Any]] = []
        self._worker = None

        self.setWindowTitle(f"Add references from {source_id}")
        self.setModal(True)
        self.setMinimumWidth(520)
        self.setMinimumHeight(480)
        apply_dialog_shadow(self)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(int(t("space.2").rstrip("px")))

        outer.addWidget(required_label("Relationship"))
        self._kind_combo = QComboBox()
        self._kind_combo.setObjectName("record_connect_kind")
        self._kind_combo.addItems(sorted(kinds_for_source(source_type)))
        self._kind_combo.setCurrentIndex(-1)
        self._kind_combo.currentTextChanged.connect(self._on_kind_changed)
        outer.addWidget(self._kind_combo)

        outer.addWidget(required_label("Target type"))
        self._target_type_combo = QComboBox()
        self._target_type_combo.setObjectName("record_connect_target_type")
        self._target_type_combo.currentTextChanged.connect(self._on_target_type_changed)
        outer.addWidget(self._target_type_combo)

        outer.addWidget(required_label("Target records"))
        self._filter = QLineEdit()
        self._filter.setObjectName("record_connect_filter")
        self._filter.setPlaceholderText("Filter by identifier or name")
        self._filter.setClearButtonEnabled(True)
        self._filter.textChanged.connect(self._apply_filter)
        outer.addWidget(self._filter)

        self._list = QListWidget()
        self._list.setObjectName("record_connect_targets")
        self._list.itemChanged.connect(self._on_item_changed)
        outer.addWidget(self._list, stretch=1)

        self._summary = QLabel("")
        self._summary.setObjectName("record_connect_summary")
        self._summary.setProperty("role", "help")
        outer.addWidget(self._summary)

        button_row = QHBoxLayout()
        button_row.setSpacing(int(t("space.2").rstrip("px")))
        button_row.addStretch(1)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(self._cancel_btn)
        self._save_btn = primary_button("Save")
        self._save_btn.setObjectName("record_connect_save")
        self._save_btn.setDefault(True)
        self._save_btn.clicked.connect(self._on_save_clicked)
        button_row.addWidget(self._save_btn)
        outer.addLayout(button_row)

        self._refresh_summary()

    # ------------------------------------------------------------------
    # Modal backdrop hooks
    # ------------------------------------------------------------------

    def showEvent(self, event):  # noqa: N802 — Qt naming
        super().showEvent(event)
        _backdrop_attach(self)

    def hideEvent(self, event):  # noqa: N802 — Qt naming
        _backdrop_detach(self)
        super().hideEvent(event)

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def relationship(self) -> str:
        return self._kind_combo.currentText().strip()

    def target_type(self) -> str:
        return self._target_type_combo.currentText().strip()

    def ticked_identifiers(self) -> list[str]:
        """Identifiers ticked by the operator this visit (locked rows —
        already connected — are excluded)."""
        out: list[str] = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            if (
                item.checkState() == Qt.CheckState.Checked
                and item.flags() & Qt.ItemFlag.ItemIsEnabled
            ):
                out.append(str(item.data(Qt.ItemDataRole.UserRole)))
        return out

    def created_references(self) -> list[dict[str, Any]]:
        return list(self._created)

    # ------------------------------------------------------------------
    # Cascade
    # ------------------------------------------------------------------

    def _on_kind_changed(self, kind: str) -> None:
        kind = kind.strip()
        self._target_type_combo.blockSignals(True)
        self._target_type_combo.clear()
        if kind:
            types = sorted(target_types_for(self._source_type, kind))
            self._target_type_combo.addItems(types)
            # Auto-select when the kind determines the type (the common
            # case: process_touches_entity -> entity). Otherwise leave it
            # unselected so the operator chooses.
            self._target_type_combo.setCurrentIndex(0 if len(types) == 1 else -1)
        self._target_type_combo.blockSignals(False)
        self._on_target_type_changed(self._target_type_combo.currentText())

    def _on_target_type_changed(self, target_type: str) -> None:
        target_type = target_type.strip()
        kind = self.relationship()
        self._list.blockSignals(True)
        self._list.clear()
        if target_type and kind:
            for identifier, title in self._records(target_type):
                display = f"{identifier} — {title}" if title else identifier
                item = QListWidgetItem(display)
                item.setData(Qt.ItemDataRole.UserRole, identifier)
                item.setFlags(
                    item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsEnabled
                )
                if (kind, target_type, identifier) in self._existing:
                    item.setCheckState(Qt.CheckState.Checked)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                    item.setText(f"{display}  (already connected)")
                else:
                    item.setCheckState(Qt.CheckState.Unchecked)
                self._list.addItem(item)
        self._list.blockSignals(False)
        self._apply_filter(self._filter.text())
        self._refresh_summary()

    def _records(self, entity_type: str) -> list[tuple[str, str]]:
        cached = self._records_cache.get(entity_type)
        if cached is None:
            cached = list_records_for_type(self._client, entity_type)
            self._records_cache[entity_type] = cached
        return cached

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self._list.count()):
            item = self._list.item(i)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def _on_item_changed(self, _item: QListWidgetItem) -> None:
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        n = len(self.ticked_identifiers())
        kind = self.relationship()
        if not kind:
            self._summary.setText("Choose a relationship.")
        elif n == 0:
            self._summary.setText("Tick the records to connect.")
        else:
            noun = "reference" if n == 1 else "references"
            self._summary.setText(
                f"Save will create {n} {noun}: {self._source_id} "
                f"{kind} → each ticked record."
            )

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _on_save_clicked(self) -> None:
        from crmbuilder_v2.ui.workers import run_in_thread

        kind = self.relationship()
        target_type = self.target_type()
        targets = self.ticked_identifiers()
        if not kind or not target_type or not targets:
            self._refresh_summary()
            return
        self._save_btn.setEnabled(False)
        bodies = [
            {
                "source_type": self._source_type,
                "source_id": self._source_id,
                "target_type": target_type,
                "target_id": target_id,
                "relationship": kind,
            }
            for target_id in targets
        ]
        self._worker = run_in_thread(
            lambda: _create_all(self._client, bodies),
            on_success=self._on_save_result,
            on_error=self._on_save_error,
            parent=self,
        )

    def _on_save_result(self, result: dict[str, Any]) -> None:
        created: list[dict[str, Any]] = result.get("created") or []
        failed: list[tuple[dict[str, Any], str]] = result.get("failed") or []
        self._created.extend(created)
        for body in created:
            self._existing.add(
                (body["relationship"], body["target_type"], body["target_id"])
            )
        if not failed:
            self.accept()
            return
        # Lock what landed, keep the dialog open for a retry of the rest.
        self._on_target_type_changed(self.target_type())
        self._save_btn.setEnabled(True)
        lines = [f"{body['target_id']}: {msg}" for body, msg in failed]
        ErrorDialog(
            "Some references were not created",
            f"Created {len(created)} of {len(created) + len(failed)}. "
            "The rows below failed; the created rows are now locked.",
            detail="\n".join(lines),
            parent=self,
        ).exec()

    def _on_save_error(self, exc: Exception) -> None:
        self._save_btn.setEnabled(True)
        if isinstance(exc, StorageConnectionError):
            _log.warning("Connection lost while creating references: %s", exc)
            self.reject()
            return
        ErrorDialog("Could not create references", str(exc), parent=self).exec()


def _create_all(client: StorageClient, bodies: list[dict[str, Any]]) -> dict[str, Any]:
    """Create each reference in turn; never let one failure abort the rest."""
    created: list[dict[str, Any]] = []
    failed: list[tuple[dict[str, Any], str]] = []
    for body in bodies:
        try:
            client.create_reference(body)
        except StorageConnectionError:
            raise
        except Exception as exc:  # noqa: BLE001 — surfaced per row
            failed.append((body, str(exc)))
        else:
            created.append(body)
    return {"created": created, "failed": failed}

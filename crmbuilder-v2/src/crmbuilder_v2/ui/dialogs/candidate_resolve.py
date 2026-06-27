"""Resolve-candidate dialog — PI-256 (PRJ-027 / REQ-341) slice 2.

The human decision that turns a reconciler-surfaced **entity** candidate into a
real ``source_mapping`` (DEC-649: candidates gate promotion; only this human act
creates the mapping). The reviewer either **maps** the source entity to a design
entity (direct or referential) or **rejects** it as a lasting exclusion. On
accept the dialog creates the mapping, points it at the chosen design entity
(for a map), drives it to ``resolved``, and resolves the candidate so it leaves
the open queue — all through the StorageClient, errors surfaced inline.

Field and association candidate resolution (which need a parent mapping / a
canonical association) are the next slice.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.exceptions import StorageClientError, StorageConnectionError

# Decision label -> (source_mapping decision_type, is_map). "decomposition"
# (one source entity to several design entities) is a later slice.
_DECISIONS: tuple[tuple[str, str, bool], ...] = (
    ("Map — direct (same intent)", "direct", True),
    ("Map — referential (different surface, same intent)", "referential", True),
    ("Reject (exclude from the design)", "rejected", False),
)


class ResolveEntityCandidateDialog(QDialog):
    """Resolve an entity ``mapping_candidate`` into a ``source_mapping``."""

    def __init__(
        self,
        client: StorageClient,
        candidate: dict[str, Any],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._client = client
        self._candidate = candidate
        self.setWindowTitle("Resolve entity candidate")
        self.setObjectName("resolve_entity_candidate_dialog")

        self._entities = self._load_entities()

        layout = QVBoxLayout(self)
        source_name = candidate.get("source_entity_name") or "(unknown)"
        layout.addWidget(QLabel(
            f"Source entity <b>{source_name}</b> discovered on "
            f"{candidate.get('instance_identifier') or 'the source instance'}."
        ))

        form = QFormLayout()
        self._decision_combo = QComboBox()
        self._decision_combo.setObjectName("decision_combo")
        for label, _dt, _is_map in _DECISIONS:
            self._decision_combo.addItem(label)
        self._decision_combo.currentIndexChanged.connect(self._sync_target_enabled)
        form.addRow(QLabel("Decision"), self._decision_combo)

        self._target_combo = QComboBox()
        self._target_combo.setObjectName("target_entity_combo")
        for ent in self._entities:
            self._target_combo.addItem(
                ent.get("entity_name") or ent.get("entity_identifier"),
                ent.get("entity_identifier"),
            )
        form.addRow(QLabel("Design entity"), self._target_combo)
        layout.addLayout(form)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self._on_ok)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self._sync_target_enabled()

    # ------------------------------------------------------------------

    def _load_entities(self) -> list[dict[str, Any]]:
        try:
            ents = self._client.list_entities()
        except StorageClientError:
            return []
        return sorted(ents, key=lambda e: (e.get("entity_name") or "").lower())

    def _current_decision(self) -> tuple[str, bool]:
        _label, decision_type, is_map = _DECISIONS[
            self._decision_combo.currentIndex()
        ]
        return decision_type, is_map

    def _sync_target_enabled(self) -> None:
        _dt, is_map = self._current_decision()
        self._target_combo.setEnabled(is_map)

    # ------------------------------------------------------------------

    def _on_ok(self) -> None:
        decision_type, is_map = self._current_decision()
        target_id = self._target_combo.currentData() if is_map else None
        if is_map and not target_id:
            ErrorDialog(
                title="No design entity",
                message="Select a design entity to map this source entity to, "
                        "or choose Reject.",
                detail="",
                parent=self,
            ).exec()
            return

        instance = self._candidate.get("instance_identifier")
        source_name = self._candidate.get("source_entity_name")
        try:
            created = self._client.create_source_mapping({
                "source_mapping_instance_identifier": instance,
                "source_mapping_source_entity_name": source_name,
                "source_mapping_decision_type": decision_type,
            })
            mid = created["source_mapping_identifier"]
            if is_map:
                self._client.add_source_mapping_target(
                    source_mapping_identifier=mid, entity_identifier=target_id
                )
            self._client.update_source_mapping(mid, {
                "source_mapping_source_entity_name": source_name,
                "source_mapping_decision_type": decision_type,
                "source_mapping_status": "resolved",
            })
            self._client.resolve_mapping_candidate(
                int(self._candidate["id"]),
                resolved_to_source_mapping_identifier=mid,
            )
        except StorageConnectionError:
            raise
        except StorageClientError as exc:
            ErrorDialog(
                title="Could not resolve candidate",
                message="The candidate could not be resolved into a mapping.",
                detail=str(exc),
                parent=self,
            ).exec()
            return
        self.accept()

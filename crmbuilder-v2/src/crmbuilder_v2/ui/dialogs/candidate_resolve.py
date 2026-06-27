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


# Field-level decision labels. "referential_interpreted" (needs per-value
# translation) is a later slice.
_FIELD_DECISIONS: tuple[tuple[str, str, bool], ...] = (
    ("Map — direct (same field)", "direct", True),
    ("Map — referential (same intent, different name)", "referential_exact", True),
    ("Reject (exclude from the design)", "rejected", False),
)

# Association-level decision labels (DEC-654: no decomposition).
_ASSOC_DECISIONS: tuple[tuple[str, str, bool], ...] = (
    ("Map — direct (same relationship)", "direct", True),
    ("Map — referential (same intent, different surface)", "referential", True),
    ("Reject (exclude from the design)", "rejected", False),
)


def _resolved_source_mapping_for(
    client: StorageClient, instance: str, source_entity_name: str
) -> dict[str, Any] | None:
    """The resolved, non-rejected entity mapping a field candidate hangs off."""
    for m in client.list_source_mappings(
        instance_identifier=instance, status="resolved"
    ):
        if (
            m.get("source_entity_name") == source_entity_name
            and m.get("decision_type") != "rejected"
        ):
            return m
    return None


class ResolveFieldCandidateDialog(QDialog):
    """Resolve a field ``mapping_candidate`` into a ``field_mapping``.

    A field candidate surfaces only once its parent entity is mapped (DEC-651),
    so it resolves *under* that entity's ``source_mapping``: the reviewer maps the
    source field to a design field on one of the mapping's target entities, or
    rejects it.
    """

    def __init__(
        self,
        client: StorageClient,
        candidate: dict[str, Any],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._client = client
        self._candidate = candidate
        self.setWindowTitle("Resolve field candidate")
        self.setObjectName("resolve_field_candidate_dialog")

        instance = candidate.get("instance_identifier")
        self._parent_mapping = _resolved_source_mapping_for(
            client, instance, candidate.get("source_entity_name")
        )
        self._fields = self._load_target_fields()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"Source field <b>{candidate.get('source_entity_name')}."
            f"{candidate.get('source_field_name')}</b>."
        ))
        if self._parent_mapping is None:
            layout.addWidget(QLabel(
                "Its parent entity has no resolved mapping — resolve the entity "
                "candidate first."
            ))

        form = QFormLayout()
        self._decision_combo = QComboBox()
        self._decision_combo.setObjectName("decision_combo")
        for label, _dt, _is_map in _FIELD_DECISIONS:
            self._decision_combo.addItem(label)
        self._decision_combo.currentIndexChanged.connect(self._sync_target_enabled)
        form.addRow(QLabel("Decision"), self._decision_combo)

        self._target_combo = QComboBox()
        self._target_combo.setObjectName("target_field_combo")
        # Combo data is the field identifier (a string — QComboBox.findData does
        # not deep-compare tuples); the owning entity is looked up alongside.
        self._field_to_entity: dict[str, str] = {}
        for fld in self._fields:
            fid = fld.get("field_identifier")
            self._field_to_entity[fid] = fld.get("entity_identifier")
            self._target_combo.addItem(
                fld.get("field_name") or fid, fid
            )
        form.addRow(QLabel("Design field"), self._target_combo)
        layout.addLayout(form)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self._on_ok)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)
        self._sync_target_enabled()

    def _load_target_fields(self) -> list[dict[str, Any]]:
        if self._parent_mapping is None:
            return []
        mid = self._parent_mapping["source_mapping_identifier"]
        fields: list[dict[str, Any]] = []
        try:
            for tgt in self._client.list_source_mapping_targets(mid):
                eid = tgt.get("entity_identifier")
                for f in self._client.list_fields(entity_identifier=eid):
                    f = dict(f)
                    f["entity_identifier"] = eid
                    fields.append(f)
        except StorageClientError:
            return []
        return fields

    def _current_decision(self) -> tuple[str, bool]:
        _label, dt, is_map = _FIELD_DECISIONS[self._decision_combo.currentIndex()]
        return dt, is_map

    def _sync_target_enabled(self) -> None:
        _dt, is_map = self._current_decision()
        self._target_combo.setEnabled(is_map and bool(self._fields))

    def _on_ok(self) -> None:
        if self._parent_mapping is None:
            ErrorDialog(
                title="Parent entity not mapped",
                message="Resolve this field's parent entity candidate first.",
                detail="", parent=self,
            ).exec()
            return
        decision_type, is_map = self._current_decision()
        target_field = self._target_combo.currentData() if is_map else None
        target_entity = (
            self._field_to_entity.get(target_field) if is_map else None
        )
        if is_map and not target_field:
            ErrorDialog(
                title="No design field",
                message="Select a design field to map to, or choose Reject.",
                detail="", parent=self,
            ).exec()
            return
        source_field = self._candidate.get("source_field_name")
        mid = self._parent_mapping["source_mapping_identifier"]
        try:
            created = self._client.create_field_mapping({
                "field_mapping_source_mapping_identifier": mid,
                "field_mapping_source_field_name": source_field,
                "field_mapping_decision_type": decision_type,
                "field_mapping_target_entity_identifier": target_entity,
                "field_mapping_target_field_identifier": target_field,
            })
            fmid = created["field_mapping_identifier"]
            self._client.update_field_mapping(fmid, {
                "field_mapping_source_field_name": source_field,
                "field_mapping_decision_type": decision_type,
                "field_mapping_status": "resolved",
                "field_mapping_target_entity_identifier": target_entity,
                "field_mapping_target_field_identifier": target_field,
            })
            self._client.resolve_mapping_candidate(
                int(self._candidate["id"]),
                resolved_to_field_mapping_identifier=fmid,
            )
        except StorageConnectionError:
            raise
        except StorageClientError as exc:
            ErrorDialog(
                title="Could not resolve candidate",
                message="The field candidate could not be resolved.",
                detail=str(exc), parent=self,
            ).exec()
            return
        self.accept()


class ResolveAssociationCandidateDialog(QDialog):
    """Resolve an association ``mapping_candidate`` into an ``association_mapping``.

    The reviewer maps the discovered source relationship to a canonical design
    association (direct / referential) or rejects it. The resolve-candidate model
    has no association back-link yet, so the candidate is marked resolved without
    a ``resolved_to_*`` pointer (the association_mapping is the durable record).
    """

    def __init__(
        self,
        client: StorageClient,
        candidate: dict[str, Any],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._client = client
        self._candidate = candidate
        self.setWindowTitle("Resolve relationship candidate")
        self.setObjectName("resolve_association_candidate_dialog")

        self._associations = self._load_associations()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"Source relationship <b>{candidate.get('source_field_name')}</b> on "
            f"{candidate.get('source_entity_name')}."
        ))

        form = QFormLayout()
        self._decision_combo = QComboBox()
        self._decision_combo.setObjectName("decision_combo")
        for label, _dt, _is_map in _ASSOC_DECISIONS:
            self._decision_combo.addItem(label)
        self._decision_combo.currentIndexChanged.connect(self._sync_target_enabled)
        form.addRow(QLabel("Decision"), self._decision_combo)

        self._target_combo = QComboBox()
        self._target_combo.setObjectName("target_association_combo")
        for a in self._associations:
            self._target_combo.addItem(
                a.get("association_name") or a.get("association_identifier"),
                a.get("association_identifier"),
            )
        form.addRow(QLabel("Design relationship"), self._target_combo)
        layout.addLayout(form)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self._on_ok)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)
        self._sync_target_enabled()

    def _load_associations(self) -> list[dict[str, Any]]:
        try:
            assocs = self._client.list_associations()
        except StorageClientError:
            return []
        return sorted(
            assocs, key=lambda a: (a.get("association_name") or "").lower()
        )

    def _current_decision(self) -> tuple[str, bool]:
        _label, dt, is_map = _ASSOC_DECISIONS[self._decision_combo.currentIndex()]
        return dt, is_map

    def _sync_target_enabled(self) -> None:
        _dt, is_map = self._current_decision()
        self._target_combo.setEnabled(is_map and bool(self._associations))

    def _on_ok(self) -> None:
        decision_type, is_map = self._current_decision()
        target_id = self._target_combo.currentData() if is_map else None
        if is_map and not target_id:
            ErrorDialog(
                title="No design relationship",
                message="Select a design relationship to map to, or Reject.",
                detail="", parent=self,
            ).exec()
            return
        # The reconciler stores the source link name in source_field_name.
        source_name = self._candidate.get("source_field_name")
        instance = self._candidate.get("instance_identifier")
        try:
            created = self._client.create_association_mapping({
                "association_mapping_instance_identifier": instance,
                "association_mapping_source_association_name": source_name,
                "association_mapping_decision_type": decision_type,
                "association_mapping_target_association_identifier": target_id,
            })
            amid = created["association_mapping_identifier"]
            self._client.update_association_mapping(amid, {
                "association_mapping_source_association_name": source_name,
                "association_mapping_decision_type": decision_type,
                "association_mapping_status": "resolved",
                "association_mapping_target_association_identifier": target_id,
            })
            self._client.resolve_mapping_candidate(int(self._candidate["id"]))
        except StorageConnectionError:
            raise
        except StorageClientError as exc:
            ErrorDialog(
                title="Could not resolve candidate",
                message="The relationship candidate could not be resolved.",
                detail=str(exc), parent=self,
            ).exec()
            return
        self.accept()

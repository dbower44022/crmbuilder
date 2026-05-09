"""Planning item delete confirmation dialog. Per ui-PRD-v0.2.md §4.3.

Thin subclass of ``EntityCrudDeleteDialog``. Planning items are
physically deleted via ``DELETE /planning-items/{identifier}``; the
base's ConflictError branch handles the case where a planning item is
referenced by another record (defensive ErrorDialog fallback).
NotFoundError is treated as already-deleted and the dialog accepts so
the panel refreshes.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from crmbuilder_v2.ui.base.crud_dialog import EntityCrudDeleteDialog
from crmbuilder_v2.ui.client import StorageClient


class PlanningItemDeleteDialog(EntityCrudDeleteDialog):
    """Confirmation dialog for deleting a planning item."""

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
            client.delete_planning_item,
            entity_label="planning item",
            parent=parent,
        )

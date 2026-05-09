"""Risk delete confirmation dialog. Per ui-PRD-v0.2.md §4.2.

Thin subclass of ``EntityCrudDeleteDialog``. Risks are physically
deleted via ``DELETE /risks/{identifier}``; the base's ConflictError
branch handles the case where a risk is referenced by another record
(defensive ErrorDialog fallback). NotFoundError is treated as
already-deleted and the dialog accepts so the panel refreshes.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from crmbuilder_v2.ui.base.crud_dialog import EntityCrudDeleteDialog
from crmbuilder_v2.ui.client import StorageClient


class RiskDeleteDialog(EntityCrudDeleteDialog):
    """Confirmation dialog for deleting a risk."""

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
            client.delete_risk,
            entity_label="risk",
            parent=parent,
        )

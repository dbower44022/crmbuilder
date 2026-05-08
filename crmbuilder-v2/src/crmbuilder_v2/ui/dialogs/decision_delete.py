"""Decision delete confirmation dialog.

v0.2 migration: thin subclass of ``EntityCrudDeleteDialog``. The base
class implements the v0.1 slice H pattern verbatim — soft-delete
through the API, ConflictError as defensive ErrorDialog fallback,
NotFoundError treated as already-deleted. Per PRD §4.9.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from crmbuilder_v2.ui.base.crud_dialog import EntityCrudDeleteDialog
from crmbuilder_v2.ui.client import StorageClient


class DecisionDeleteDialog(EntityCrudDeleteDialog):
    """Confirmation dialog for deleting a decision. Per PRD §4.9."""

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
            client.delete_decision,
            entity_label="decision",
            parent=parent,
        )

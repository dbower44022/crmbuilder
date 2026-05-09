"""Topic delete confirmation dialog. Per ui-PRD-v0.2.md §4.4.

Thin subclass of ``EntityCrudDeleteDialog``. Topics are physically
deleted via ``DELETE /topics/{identifier}``. If the topic has children
or is referenced by other records, the access layer surfaces a
``ConflictError``; the base's ConflictError branch routes that to the
generic ``ErrorDialog`` and the user must re-parent or remove
dependents before retrying. ``NotFoundError`` is treated as
already-deleted and the dialog accepts so the panel refreshes.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from crmbuilder_v2.ui.base.crud_dialog import EntityCrudDeleteDialog
from crmbuilder_v2.ui.client import StorageClient


class TopicDeleteDialog(EntityCrudDeleteDialog):
    """Confirmation dialog for deleting a topic."""

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
            client.delete_topic,
            entity_label="topic",
            parent=parent,
        )

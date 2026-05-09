"""Topic create dialog. Per ui-PRD-v0.2.md §4.4.

Thin subclass of ``EntityCrudDialog`` driven by the topic field schema
in ``_topic_schema.py``. The base class handles widget construction
(including the tree-picker for the parent_topic field), inline error
labels, save flow, and error envelope routing.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from crmbuilder_v2.ui.base.crud_dialog import EntityCrudDialog
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._topic_schema import topic_fields_create


class TopicCreateDialog(EntityCrudDialog):
    """Modal create-topic dialog."""

    def __init__(
        self,
        client: StorageClient,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client,
            topic_fields_create(),
            mode="create",
            title="New Topic",
            create_method=client.create_topic,
            parent=parent,
        )

    def created_identifier(self) -> str | None:
        """Identifier of the newly created record, or None if not accepted."""
        return self.saved_identifier()

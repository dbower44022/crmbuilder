"""Planning item create dialog. Per ui-PRD-v0.2.md §4.3.

Thin subclass of ``EntityCrudDialog`` driven by the planning-item field
schema in ``_planning_item_schema.py``. The base class handles widget
construction, inline error labels, save flow, and error envelope routing.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from crmbuilder_v2.ui.base.crud_dialog import EntityCrudDialog
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._planning_item_schema import planning_item_fields


class PlanningItemCreateDialog(EntityCrudDialog):
    """Modal create-planning-item dialog."""

    def __init__(
        self,
        client: StorageClient,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client,
            planning_item_fields(),
            mode="create",
            title="New Planning Item",
            create_method=client.create_planning_item,
            parent=parent,
        )

    def created_identifier(self) -> str | None:
        """Identifier of the newly created record, or None if not accepted."""
        return self.saved_identifier()

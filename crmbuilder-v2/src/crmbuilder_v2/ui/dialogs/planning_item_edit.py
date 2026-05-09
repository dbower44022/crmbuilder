"""Planning item edit dialog. Per ui-PRD-v0.2.md §4.3.

Thin subclass of ``EntityCrudDialog``. The base class handles widget
pre-population from the record, the read-only identifier treatment,
partial PATCH diff computation, and error envelope routing.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget

from crmbuilder_v2.ui.base.crud_dialog import EntityCrudDialog
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._planning_item_schema import planning_item_fields


class PlanningItemEditDialog(EntityCrudDialog):
    """Modal edit-planning-item dialog."""

    def __init__(
        self,
        client: StorageClient,
        record: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        identifier = str(record.get("identifier") or "")
        title = f"Edit {identifier}" if identifier else "Edit planning item"
        super().__init__(
            client,
            planning_item_fields(),
            mode="edit",
            title=title,
            update_method=client.update_planning_item,
            record=record,
            parent=parent,
        )

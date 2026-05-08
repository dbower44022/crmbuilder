"""Decision edit dialog.

v0.2 migration: thin subclass of ``EntityCrudDialog``. The base class
handles widget pre-population from the record, the read-only identifier
treatment, partial PATCH diff computation, and error envelope routing.
Per PRD §4.8.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget

from crmbuilder_v2.ui.base.crud_dialog import EntityCrudDialog
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._decision_schema import decision_fields


class DecisionEditDialog(EntityCrudDialog):
    """Modal edit-decision dialog. Per PRD §4.8."""

    def __init__(
        self,
        client: StorageClient,
        record: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        identifier = str(record.get("identifier") or "")
        title = f"Edit {identifier}" if identifier else "Edit decision"
        super().__init__(
            client,
            decision_fields(),
            mode="edit",
            title=title,
            update_method=client.update_decision,
            record=record,
            parent=parent,
        )

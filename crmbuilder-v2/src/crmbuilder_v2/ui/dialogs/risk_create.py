"""Risk create dialog. Per ui-PRD-v0.2.md §4.2.

Thin subclass of ``EntityCrudDialog`` driven by the risk field schema
in ``_risk_schema.py``. The base class handles widget construction,
inline error labels, save flow, and error envelope routing.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from crmbuilder_v2.ui.base.crud_dialog import EntityCrudDialog
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._risk_schema import risk_fields


class RiskCreateDialog(EntityCrudDialog):
    """Modal create-risk dialog."""

    def __init__(
        self,
        client: StorageClient,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client,
            risk_fields(),
            mode="create",
            title="New risk",
            create_method=client.create_risk,
            parent=parent,
        )

    def created_identifier(self) -> str | None:
        """Identifier of the newly created record, or None if not accepted."""
        return self.saved_identifier()

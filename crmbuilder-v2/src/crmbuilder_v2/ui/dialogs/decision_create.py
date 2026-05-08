"""Decision create dialog.

v0.2 migration: thin subclass of ``EntityCrudDialog``. The eleven-field
schema lives in ``_decision_schema.py``; the base class handles widget
construction, inline error labels, save flow, and error envelope
routing. Per PRD §4.7 the visible behavior is unchanged from v0.1
except that Decision Date is now a calendar widget (DEC-026).
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from crmbuilder_v2.ui.base.crud_dialog import EntityCrudDialog
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._decision_schema import decision_fields


class DecisionCreateDialog(EntityCrudDialog):
    """Modal create-decision dialog. Per PRD §4.7."""

    def __init__(
        self,
        client: StorageClient,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client,
            decision_fields(),
            mode="create",
            title="New decision",
            create_method=client.create_decision,
            parent=parent,
        )

    def created_identifier(self) -> str | None:
        """Identifier of the newly created record, or None if not accepted."""
        return self.saved_identifier()

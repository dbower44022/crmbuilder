"""Status replace dialog.

Mirror of :class:`CharterReplaceDialog`; supplies the status-specific
save callback. Per ui-PRD-v0.2.md §4.5.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget

from crmbuilder_v2.ui.base.versioned_replace_dialog import (
    VersionedReplaceDialog,
)
from crmbuilder_v2.ui.client import StorageClient


class StatusReplaceDialog(VersionedReplaceDialog):
    """Open a JSON editor pre-populated with the current status payload.

    Save calls :meth:`StorageClient.replace_status`, which creates a new
    status version (the prior current version is flipped to not-current
    automatically).
    """

    def __init__(
        self,
        client: StorageClient,
        current_payload: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            current_payload,
            client.replace_status,
            title="New Status Version",
            parent=parent,
        )

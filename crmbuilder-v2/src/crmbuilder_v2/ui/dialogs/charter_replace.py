"""Charter replace dialog.

Thin wrapper around :class:`VersionedReplaceDialog` that supplies the
charter-specific save callback. Per ui-PRD-v0.2.md §4.5.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget

from crmbuilder_v2.ui.base.versioned_replace_dialog import (
    VersionedReplaceDialog,
)
from crmbuilder_v2.ui.client import StorageClient


class CharterReplaceDialog(VersionedReplaceDialog):
    """Open a JSON editor pre-populated with the current charter payload.

    Save calls :meth:`StorageClient.replace_charter`, which creates a
    new charter version (the prior current version is flipped to
    not-current automatically).
    """

    def __init__(
        self,
        client: StorageClient,
        current_payload: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            current_payload,
            client.replace_charter,
            title="New Charter Version",
            parent=parent,
        )

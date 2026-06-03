"""Create-and-select engagement dialog (PI-β).

Extends :class:`EngagementCreateDialog`. Where the base dialog only POSTs
``/engagements`` to create the registry row, this variant additionally
**selects** the freshly-created engagement as the desktop's active one on
success — a client-side context change (the active-engagement context
mirrors onto the ``StorageClient``'s ``X-Engagement`` header), with no
per-engagement database file and no subprocess swap.

(PI-β collapsed the former three-step create → per-engagement-DB →
activation-worker flow: the unified DB needs no per-engagement file, and
switching engagements is a header change, so "create + activate" is now
just "create + select".)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from crmbuilder_v2.access.engagement_models import (
    Engagement,
    EngagementStatus,
)
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.engagement_crud import EngagementCreateDialog

_log = logging.getLogger("crmbuilder_v2.ui.dialogs.new_engagement_dialog")


class NewEngagementDialog(EngagementCreateDialog):
    """Create an engagement and select it as the active one.

    Constructor parameters beyond :class:`EngagementCreateDialog`:

    * ``active_context`` — the desktop's :class:`ActiveEngagementContext`.
    """

    activation_completed = Signal(object)  # Engagement

    def __init__(
        self,
        client: StorageClient,
        active_context,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(client, parent)
        self._active_context = active_context
        self.setWindowTitle("New engagement (create + select)")

    def _on_save_success(self, result: Any) -> None:
        # The base dialog records the created identifier and accepts; we
        # additionally select the new engagement before letting that proceed.
        if isinstance(result, dict):
            created = _engagement_from_dict(result)
            if created is not None and self._active_context is not None:
                self._client.set_active_engagement(created.engagement_identifier)
                self._active_context.set_engagement(created)
                self.activation_completed.emit(created)
        super()._on_save_success(result)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _engagement_from_dict(payload: dict[str, Any]) -> Engagement | None:
    """Build an :class:`Engagement` from a REST envelope payload."""
    try:
        status_raw = payload.get("engagement_status") or "active"
        status = (
            status_raw
            if isinstance(status_raw, EngagementStatus)
            else EngagementStatus(status_raw)
        )
        return Engagement(
            engagement_identifier=payload["engagement_identifier"],
            engagement_code=payload["engagement_code"],
            engagement_name=payload.get("engagement_name") or "",
            engagement_purpose=payload.get("engagement_purpose") or "",
            engagement_status=status,
            engagement_last_opened_at=None,
            engagement_export_dir=payload.get("engagement_export_dir"),
            engagement_created_at=_parse_dt(payload.get("engagement_created_at")),
            engagement_updated_at=_parse_dt(payload.get("engagement_updated_at")),
            engagement_deleted_at=None,
        )
    except Exception:  # noqa: BLE001 — defensive
        return None


def _parse_dt(value):
    if value is None:
        return datetime.now(UTC)
    if isinstance(value, datetime):
        return value
    try:
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        return datetime.now(UTC)

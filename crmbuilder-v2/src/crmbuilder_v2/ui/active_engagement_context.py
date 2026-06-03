"""ActiveEngagementContext — the desktop's in-memory active engagement.

PI-β removed the cross-restart ``current_engagement.json`` marker: the
active engagement is now purely client-side desktop state. Panels
subscribe to ``active_engagement_changed`` for both initial selection and
runtime switching; the desktop also mirrors the active engagement onto the
``StorageClient`` so it is sent as the ``X-Engagement`` header on every
request. Switching engagements is a context change (set the engagement,
refresh the panels) — no API restart, no marker file.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

from crmbuilder_v2.access.engagement_models import Engagement

_log = logging.getLogger("crmbuilder_v2.ui.active_engagement_context")


class ActiveEngagementContext(QObject):
    """Holds and emits the currently-active ``Engagement`` (or ``None``).

    Signals:

    * ``active_engagement_changed(object)`` — emits the new ``Engagement``
      or ``None`` whenever the active state changes.
    """

    active_engagement_changed = Signal(object)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._engagement: Engagement | None = None

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def engagement(self) -> Engagement | None:
        return self._engagement

    def engagement_identifier(self) -> str | None:
        return self._engagement.engagement_identifier if self._engagement else None

    def engagement_code(self) -> str | None:
        return self._engagement.engagement_code if self._engagement else None

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------

    def set_engagement(self, engagement: Engagement | None) -> None:
        """Update the active engagement; emit the signal."""
        self._engagement = engagement
        self.active_engagement_changed.emit(engagement)

    def clear(self) -> None:
        """Clear the active engagement; emits ``None``."""
        self.set_engagement(None)

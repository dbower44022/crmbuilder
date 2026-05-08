"""Status panel — read-only versioned view per slice E.

Same pattern as :class:`CharterPanel`: lists every status version
newest-first, marks the current version, and renders the selected
version's payload as a structured form.
"""

from __future__ import annotations

from typing import Any

from crmbuilder_v2.ui.base.versioned_panel import VersionedPanel


class StatusPanel(VersionedPanel):
    """Status — singleton with full version history."""

    def entity_title(self) -> str:
        return "Status"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_status_versions()

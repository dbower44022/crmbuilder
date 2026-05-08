"""Charter panel — read-only versioned view per slice E.

Lists every charter version newest-first, marks the current version
with a check, and renders the selected version's payload as a
structured form via the inherited ``VersionedPanel`` machinery.
"""

from __future__ import annotations

from typing import Any

from crmbuilder_v2.ui.base.versioned_panel import VersionedPanel


class CharterPanel(VersionedPanel):
    """Charter — singleton with full version history."""

    def entity_title(self) -> str:
        return "Charter"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_charter_versions()

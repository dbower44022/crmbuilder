"""ActiveEngagementContext — in-memory + cross-restart active state.

Mirrors v1's ``automation/ui/active_client_context.py`` pattern.
``crmbuilder-v2/data/current_engagement.json`` holds the
cross-restart state; the in-memory ``Engagement`` is the live runtime
state. Panels subscribe to ``active_engagement_changed`` for both
initial load and runtime switching (slice D).

Per ``multi-engagement-architecture.md`` §3.3.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from crmbuilder_v2.access.engagement_models import (
    Engagement,
    EngagementStatus,
)
from crmbuilder_v2.config import get_settings

_log = logging.getLogger("crmbuilder_v2.ui.active_engagement_context")


def current_engagement_path() -> Path:
    """Return the absolute path to ``current_engagement.json``."""
    return get_settings().db_path.parent / "current_engagement.json"


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

    # ------------------------------------------------------------------
    # Cross-restart persistence
    # ------------------------------------------------------------------

    def load_from_disk(
        self, resolver=None
    ) -> Engagement | None:
        """Populate ``_engagement`` from ``current_engagement.json``.

        ``resolver`` is an optional callable that, given the
        engagement_identifier from the file, returns a hydrated
        ``Engagement`` from the meta DB (or ``None`` if the engagement
        does not exist / is soft-deleted / its DB file is missing).
        Slice D wires the resolver to a real engagement lookup; slice
        A's smoke uses a stub that returns ``None``.

        If the file is missing or malformed, or the resolver returns
        ``None``, state is cleared and ``None`` is emitted. Returns the
        loaded engagement (or ``None``).
        """
        path = current_engagement_path()
        if not path.exists():
            self.set_engagement(None)
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _log.warning("current_engagement.json malformed; clearing state")
            self.set_engagement(None)
            return None
        identifier = payload.get("engagement_identifier")
        code = payload.get("engagement_code")
        if not identifier or not code:
            _log.warning(
                "current_engagement.json missing required keys; clearing state"
            )
            self.set_engagement(None)
            return None
        engagement: Engagement | None
        if resolver is not None:
            engagement = resolver(identifier)
        else:
            # Best-effort stub for slice A: synthesise a minimal
            # Engagement so callers can read identifier/code immediately
            # without slice B's repository. Slice D replaces with a
            # real resolver against the meta DB.
            now = datetime.now(UTC)
            engagement = Engagement(
                engagement_identifier=identifier,
                engagement_code=code,
                engagement_name=code,
                engagement_purpose="",
                engagement_status=EngagementStatus.ACTIVE,
                engagement_last_opened_at=None,
                engagement_export_dir=None,
                engagement_created_at=now,
                engagement_updated_at=now,
                engagement_deleted_at=None,
            )
        self.set_engagement(engagement)
        return engagement

    def persist_to_disk(self) -> None:
        """Atomically write ``current_engagement.json`` from current state.

        Writes nothing if the engagement is ``None`` — slice D's
        deactivation flow uses an explicit ``clear_disk()`` to remove
        the file.
        """
        if self._engagement is None:
            return
        path = current_engagement_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "engagement_identifier": self._engagement.engagement_identifier,
            "engagement_code": self._engagement.engagement_code,
            "set_at": datetime.now(UTC).isoformat(),
        }
        fd, tmp = tempfile.mkstemp(
            suffix=".tmp", prefix=path.name, dir=str(path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, sort_keys=True)
                fh.write("\n")
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
            raise

    def clear_disk(self) -> None:
        """Remove ``current_engagement.json`` if present."""
        path = current_engagement_path()
        try:
            path.unlink()
        except FileNotFoundError:
            pass

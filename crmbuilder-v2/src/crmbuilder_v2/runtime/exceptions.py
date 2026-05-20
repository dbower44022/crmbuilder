"""Engagement-routing runtime exceptions (multi-tenancy routing fix, slice A).

Message text is fixed by the SES-044 architectural decisions:

* :class:`UnknownEngagementError` — DEC-111.
* :class:`EngagementExportDirNotConfigured` — DEC-109.
* :class:`EngagementExportDirMissing` — DEC-114.

The CLI may render its own marker-source variant of the unknown-code
message (DEC-108); these classes carry the structured attributes so the
caller can choose the wording.
"""

from __future__ import annotations

from pathlib import Path


class EngagementError(Exception):
    """Base class for engagement-related runtime errors."""


class UnknownEngagementError(EngagementError):
    """Raised when an engagement code is not present in the meta DB.

    Carries ``code`` and ``available_codes`` so callers can enumerate the
    valid choices in their error message.
    """

    def __init__(self, code: str, available_codes: list[str] | None = None) -> None:
        self.code = code
        self.available_codes = list(available_codes) if available_codes else []
        super().__init__(self.__str__())

    def __str__(self) -> str:
        available = ", ".join(self.available_codes) if self.available_codes else "(none)"
        return f"Unknown engagement '{self.code}'. Available: {available}."


class EngagementExportDirError(EngagementError):
    """Umbrella base for ``engagement_export_dir`` problems at write time.

    Lets ``session_scope`` / ``force_export`` / the catalog exporter catch
    both subclasses with a single ``except`` if they need to.
    """


class EngagementExportDirNotConfigured(EngagementExportDirError):
    """Raised when ``engagement_export_dir`` is null in the meta DB (DEC-109).

    Surfaces as the ``__UNCONFIGURED__`` sentinel in
    ``CRMBUILDER_V2_EXPORT_DIR`` at write time.
    """

    def __init__(self, code: str | None = None) -> None:
        self.code = code
        super().__init__(self.__str__())

    def __str__(self) -> str:
        who = f"Engagement '{self.code}'" if self.code else "The active engagement"
        return (
            f"{who} has no engagement_export_dir configured. Set "
            "engagement_export_dir for the active engagement via the desktop "
            "UI's Edit Engagement dialog, or activate a different engagement."
        )


class EngagementExportDirMissing(EngagementExportDirError):
    """Raised when ``engagement_export_dir`` is set but absent on disk (DEC-114)."""

    def __init__(self, path: Path | str, code: str | None = None) -> None:
        self.path = path
        self.code = code
        super().__init__(self.__str__())

    def __str__(self) -> str:
        return (
            f"Configured engagement_export_dir does not exist on disk: {self.path}. "
            "Either create the directory or update the engagement via Edit Engagement."
        )

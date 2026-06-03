"""Engagement-related runtime exceptions.

PI-β slice 4 removed the JSON-snapshot export machinery, so the
``EngagementExportDir*`` write-gate exceptions are gone. ``UnknownEngagementError``
is retained for callers that resolve an engagement by code.
"""

from __future__ import annotations


class EngagementError(Exception):
    """Base class for engagement-related runtime errors."""


class UnknownEngagementError(EngagementError):
    """Raised when an engagement code is not present in the registry.

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

"""Source-format parsers — turn external files into Path B envelope JSON."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ParseWarning:
    """A soft issue encountered during parsing — does not abort parsing."""

    severity: Literal["info", "warning"]
    category: str  # e.g. "missing_description", "orphan_prose", "bad_tier"
    location: str  # e.g. "Persona MST-PER-007", "Process MN-INTAKE"
    message: str


@dataclass
class ParseReport:
    """Soft-issue report returned alongside the parsed envelope."""

    warnings: list[ParseWarning] = field(default_factory=list)
    parsed_counts: dict[str, int] = field(default_factory=dict)

    def warn(self, category: str, location: str, message: str) -> None:
        """Append a warning-severity entry."""
        self.warnings.append(
            ParseWarning(
                severity="warning",
                category=category,
                location=location,
                message=message,
            )
        )


class MasterPrdParseError(Exception):
    """Raised when CBM-Master-PRD.docx is structurally unparseable."""

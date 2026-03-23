"""Internal document model for the documentation generator."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocTable:
    """A table in the document."""

    headers: list[str]
    rows: list[list[str]]
    caption: str | None = None


@dataclass
class DocParagraph:
    """A paragraph in the document."""

    text: str
    style: str = "normal"  # "normal", "note", "code", "status"


@dataclass
class DocSection:
    """A section with a heading and content."""

    title: str
    level: int  # 1=H1, 2=H2, 3=H3, 4=H4
    content: list[Any] = field(default_factory=list)


@dataclass
class DocDocument:
    """A complete document."""

    title: str
    subtitle: str
    version: str
    timestamp: str
    sections: list[DocSection] = field(default_factory=list)

"""Content-vs-software classification for Planning Items (PI-202 / REQ-185).

A Planning Item is **content** (authoring/methodology work) iff it carries at
least one area and **every** area it carries is a ``methodology-*`` system area;
otherwise it is **software**. Content PIs run the same four-step Process (Plan +
Design / Develop / Test) but with content meanings (DEC-444) and are verified
through the review machinery rather than verify-by-commit + the pytest gate
(DEC-763); crucially they are **never** phased Design-only — Develop and Test are
conditional-but-real, active by default (REQ-170).

A pure function of the PI's areas so it is testable without the runtime; the
decomposition (REQ-186) and the scheduler's verify branch (REQ-187) consume it.
A mixed content+software PI (areas spanning both) classifies as **software** for
now — splitting it is deferred (PI-202 design §6). Engagement-defined areas are
never methodology areas, so any of them likewise yields **software**.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from crmbuilder_v2.access.vocab import SYSTEM_AREA_RANKS

#: The methodology/authoring system areas — the classification signal (REQ-185).
METHODOLOGY_AREAS: frozenset[str] = frozenset(
    a for a in SYSTEM_AREA_RANKS if a.startswith("methodology-")
)

CONTENT = "content"
SOFTWARE = "software"


def classify_areas(areas: Iterable[str] | None) -> str:
    """Classify a set of areas as ``"content"`` or ``"software"`` (REQ-185).

    Content iff there is at least one area and **every** area is a
    ``methodology-*`` area. Empty / ``None`` → software (the default runtime
    path). Any non-methodology area — including a mixed content+software set or
    an engagement-defined area — → software.

    :param areas: the PI's areas (e.g. its ``area`` list), or ``None``.
    :returns: ``classification.CONTENT`` or ``classification.SOFTWARE``.
    """
    area_set = {a for a in (areas or []) if a}
    if area_set and area_set <= METHODOLOGY_AREAS:
        return CONTENT
    return SOFTWARE


def classify_planning_item(pi: Mapping[str, Any]) -> str:
    """Classify a planning-item mapping by its ``area`` list (REQ-185)."""
    return classify_areas(pi.get("area"))


def is_content_planning_item(pi: Mapping[str, Any]) -> bool:
    """Whether ``pi`` is a content/authoring Planning Item (REQ-185)."""
    return classify_planning_item(pi) == CONTENT

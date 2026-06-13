"""Requirement readability gate (requirements-provenance Phase 5).

Readability is load-bearing: if a statement is too hard to read, a human
approves it anyway, and a rubber stamp is worse than no gate. So a requirement
cannot be *activated* (approved for delivery) unless its statement reads as one
clear, self-contained idea with an acceptance criterion. The check runs at
activation — the moment of approval — so an unreadable statement can never
become authoritative.

The rules are deliberately mechanical and conservative (they catch the egregious
cases without false-positiving on legitimately terse statements); an AI-assisted
"one idea?" judgement can augment them later. The canonical failure they exist to
stop is a statement that packs live capability and retired build history into one
90-word paragraph.
"""

from __future__ import annotations

import re

from crmbuilder_v2.access.exceptions import FieldError, UnprocessableError

# Governance identifiers do not belong in a requirement statement — they are
# build-trail, not specification. Their presence signals history leaking in.
_IDENTIFIER_RE = re.compile(
    r"\b(PI|DEC|WTK|WT|SES|CNV|CONV|TOP|RSK|RISK|AGP|SKL|GVR|LRN|REF|WS|WSK|PRJ|"
    r"FND|REL|MIG|FLD|ENG)-\d+\b",
    re.IGNORECASE,
)
# Words that describe superseded/retired approaches — history, not requirement.
_HISTORY_RE = re.compile(
    r"\b(superseded|deprecated|shelved|retired|formerly|dead-?ended|obsolete|"
    r"previously|used to be|no longer)\b",
    re.IGNORECASE,
)

_MAX_WORDS = 75
_MAX_SENTENCES = 4
_MIN_ACCEPTANCE_CHARS = 10


def _sentence_count(text: str) -> int:
    return len([s for s in re.split(r"[.!?]+(?:\s|$)", text.strip()) if s.strip()])


def validate_requirement_readability(
    name: str, description: str, acceptance_summary: str
) -> None:
    """Raise :class:`UnprocessableError` if the statement is not review-ready."""
    issues: list[FieldError] = []
    statement = f"{name or ''} {description or ''}"

    if _IDENTIFIER_RE.search(statement):
        issues.append(
            FieldError(
                "requirement_description",
                "readability_identifier_in_statement",
                "a requirement statement must not embed governance identifiers "
                "(PI-/DEC-/WTK- and the like) — build history belongs in the "
                "trail, not in the statement",
            )
        )
    if _HISTORY_RE.search(statement):
        issues.append(
            FieldError(
                "requirement_description",
                "readability_history_in_statement",
                "a requirement statement must describe what the system must do, "
                "not the superseded/retired approaches that led here — keep "
                "history out of the statement",
            )
        )
    word_count = len((description or "").split())
    if word_count > _MAX_WORDS:
        issues.append(
            FieldError(
                "requirement_description",
                "readability_too_long",
                f"the statement is {word_count} words; keep it to one idea "
                f"(<= {_MAX_WORDS}) and push detail into child requirements",
            )
        )
    if _sentence_count(description or "") > _MAX_SENTENCES:
        issues.append(
            FieldError(
                "requirement_description",
                "readability_multiple_ideas",
                "the statement reads as several ideas; one declarative idea per "
                "requirement — split the rest into children",
            )
        )
    if len((acceptance_summary or "").strip()) < _MIN_ACCEPTANCE_CHARS:
        issues.append(
            FieldError(
                "requirement_acceptance_summary",
                "readability_no_acceptance",
                "a requirement needs a substantive acceptance criterion so it "
                "can be verified",
            )
        )

    if issues:
        raise UnprocessableError(issues)

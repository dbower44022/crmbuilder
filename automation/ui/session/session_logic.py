"""Session orchestration logic — pure Python, no Qt.

Token counting, prompt section splitting, reduction strategy extraction,
and context window percentage calculation. All functions operate on
plain strings and return plain data.
"""

from __future__ import annotations

import dataclasses
import re

# Token estimation constant — matches automation/prompts/context_size.py
WORDS_TO_TOKENS = 1.3

# Default context window for Claude 4.6 Opus
DEFAULT_CONTEXT_WINDOW = 200_000

# Prompt section names in order (Section 10.2)
SECTION_NAMES = [
    "Session Header",
    "Session Instructions",
    "Context",
    "Locked Decisions",
    "Open Issues",
    "Structured Output Specification",
]


@dataclasses.dataclass
class PromptSection:
    """A single section of the assembled prompt."""

    name: str
    text: str
    estimated_tokens: int


@dataclasses.dataclass
class PromptAnalysis:
    """Analysis of a complete prompt."""

    sections: list[PromptSection]
    total_tokens: int
    context_percentage: float
    reduction_strategies: list[str]
    over_capacity: bool


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """Estimate the token count of a text string.

    Uses word count * 1.3 as a proxy, matching context_size.py.

    :param text: The text to estimate.
    :returns: Estimated token count.
    """
    if not text:
        return 0
    return int(len(text.split()) * WORDS_TO_TOKENS)


# ---------------------------------------------------------------------------
# Prompt section splitting
# ---------------------------------------------------------------------------

def split_prompt_sections(prompt_text: str) -> list[PromptSection]:
    """Split an assembled prompt into its 6 sections.

    The prompt is assembled by structure.py with '---' separators between
    sections. The format is:

        header
        ---
        # Session Instructions
        instructions
        ---
        # Context
        context
        ---
        # Locked Decisions
        decisions
        ---
        # Open Issues
        issues
        ---
        output_spec

    :param prompt_text: The complete prompt text.
    :returns: List of 6 PromptSection objects.
    """
    # Strip any trailing reduction comment before splitting
    clean_text, _ = _strip_reduction_comment(prompt_text)

    # Split on '---' lines (with optional surrounding whitespace)
    parts = re.split(r'\n\s*---\s*\n', clean_text)

    # Ensure we have exactly 6 parts; pad if the prompt is malformed
    while len(parts) < 6:
        parts.append("")

    # Map parts to named sections
    sections = []
    for i, name in enumerate(SECTION_NAMES):
        text = parts[i].strip() if i < len(parts) else ""
        sections.append(PromptSection(
            name=name,
            text=text,
            estimated_tokens=estimate_tokens(text),
        ))

    return sections


# ---------------------------------------------------------------------------
# Reduction strategy extraction
# ---------------------------------------------------------------------------

def extract_reduction_strategies(prompt_text: str) -> list[str]:
    """Extract reduction strategy descriptions from the prompt.

    The PromptGenerator appends an HTML comment at the end:
    <!-- Context reduction applied: strategy1; strategy2 -->

    :param prompt_text: The complete prompt text.
    :returns: List of strategy description strings.
    """
    _, strategies = _strip_reduction_comment(prompt_text)
    return strategies


def _strip_reduction_comment(prompt_text: str) -> tuple[str, list[str]]:
    """Strip the reduction comment and return (clean_text, strategies)."""
    pattern = r'\n\n<!-- Context reduction applied: (.+?) -->\s*$'
    match = re.search(pattern, prompt_text)
    if not match:
        return prompt_text, []

    strategies_text = match.group(1)
    strategies = [s.strip() for s in strategies_text.split(";") if s.strip()]
    clean_text = prompt_text[:match.start()]
    return clean_text, strategies


# ---------------------------------------------------------------------------
# Context window calculation
# ---------------------------------------------------------------------------

def compute_context_percentage(
    total_tokens: int,
    context_window: int = DEFAULT_CONTEXT_WINDOW,
) -> float:
    """Compute what percentage of the context window is consumed.

    :param total_tokens: Total estimated tokens.
    :param context_window: Context window size in tokens.
    :returns: Percentage as a float (e.g., 45.2 for 45.2%).
    """
    if context_window <= 0:
        return 0.0
    return (total_tokens / context_window) * 100


# ---------------------------------------------------------------------------
# Full analysis
# ---------------------------------------------------------------------------

def analyze_prompt(prompt_text: str) -> PromptAnalysis:
    """Perform full analysis of a generated prompt.

    :param prompt_text: The complete prompt text.
    :returns: PromptAnalysis with sections, totals, and strategies.
    """
    sections = split_prompt_sections(prompt_text)
    strategies = extract_reduction_strategies(prompt_text)
    total_tokens = sum(s.estimated_tokens for s in sections)
    percentage = compute_context_percentage(total_tokens)
    over_capacity = percentage > 100.0

    return PromptAnalysis(
        sections=sections,
        total_tokens=total_tokens,
        context_percentage=percentage,
        reduction_strategies=strategies,
        over_capacity=over_capacity,
    )

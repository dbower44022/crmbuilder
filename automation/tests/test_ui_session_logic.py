"""Tests for automation.ui.session.session_logic — pure Python session logic."""

import pytest

from automation.ui.session.session_logic import (
    SECTION_NAMES,
    analyze_prompt,
    compute_context_percentage,
    estimate_tokens,
    extract_reduction_strategies,
    split_prompt_sections,
)

# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------

class TestEstimateTokens:

    def test_empty(self):
        assert estimate_tokens("") == 0

    def test_single_word(self):
        assert estimate_tokens("hello") == 1  # int(1 * 1.3) = 1

    def test_multiple_words(self):
        # 10 words * 1.3 = 13
        assert estimate_tokens("one two three four five six seven eight nine ten") == 13

    def test_whitespace_only(self):
        assert estimate_tokens("   ") == 0

    def test_real_text(self):
        text = "This is a sample prompt text with some content"
        result = estimate_tokens(text)
        word_count = len(text.split())
        assert result == int(word_count * 1.3)


# ---------------------------------------------------------------------------
# Prompt section splitting
# ---------------------------------------------------------------------------

def _build_prompt(sections=None, strategies=None):
    """Build a test prompt with 6 sections separated by ---."""
    if sections is None:
        sections = [
            "# Session Header\nWork Item: Test",
            "# Session Instructions\n\nFollow these instructions.",
            "# Context\n\n## Entity Data\nSome entity data",
            "# Locked Decisions — do not reopen\n\n**DEC-001: Test**\nDecision text",
            "# Open Issues — attempt to resolve or note impact\n\nNo open issues in scope.",
            "# Structured Output Specification\nOutput JSON here",
        ]
    prompt = "\n\n---\n\n".join(sections)
    if strategies:
        comment = "; ".join(strategies)
        prompt += f"\n\n<!-- Context reduction applied: {comment} -->"
    return prompt


class TestSplitPromptSections:

    def test_splits_into_six(self):
        prompt = _build_prompt()
        sections = split_prompt_sections(prompt)
        assert len(sections) == 6

    def test_section_names(self):
        prompt = _build_prompt()
        sections = split_prompt_sections(prompt)
        for i, section in enumerate(sections):
            assert section.name == SECTION_NAMES[i]

    def test_section_content(self):
        prompt = _build_prompt()
        sections = split_prompt_sections(prompt)
        assert "Work Item: Test" in sections[0].text
        assert "Follow these instructions" in sections[1].text
        assert "Entity Data" in sections[2].text
        assert "DEC-001" in sections[3].text
        assert "open issues" in sections[4].text.lower()
        assert "Output JSON" in sections[5].text

    def test_token_counts(self):
        prompt = _build_prompt()
        sections = split_prompt_sections(prompt)
        for section in sections:
            assert section.estimated_tokens >= 0
            if section.text:
                assert section.estimated_tokens > 0

    def test_strips_reduction_comment(self):
        prompt = _build_prompt(strategies=["Priority 4 omitted"])
        sections = split_prompt_sections(prompt)
        # The reduction comment should not appear in the last section
        assert "<!-- Context reduction" not in sections[5].text

    def test_malformed_fewer_separators(self):
        # Only 2 separators = 3 parts, should pad to 6
        prompt = "Part1\n\n---\n\nPart2\n\n---\n\nPart3"
        sections = split_prompt_sections(prompt)
        assert len(sections) == 6
        assert sections[0].text == "Part1"
        assert sections[1].text == "Part2"
        assert sections[2].text == "Part3"
        assert sections[3].text == ""


# ---------------------------------------------------------------------------
# Reduction strategy extraction
# ---------------------------------------------------------------------------

class TestExtractReductionStrategies:

    def test_no_strategies(self):
        prompt = _build_prompt()
        strategies = extract_reduction_strategies(prompt)
        assert strategies == []

    def test_single_strategy(self):
        prompt = _build_prompt(strategies=["Priority 4 content omitted"])
        strategies = extract_reduction_strategies(prompt)
        assert len(strategies) == 1
        assert "Priority 4" in strategies[0]

    def test_multiple_strategies(self):
        prompt = _build_prompt(strategies=[
            "Priority 4 content omitted",
            "Priority 3 summarized",
        ])
        strategies = extract_reduction_strategies(prompt)
        assert len(strategies) == 2


# ---------------------------------------------------------------------------
# Context window calculation
# ---------------------------------------------------------------------------

class TestComputeContextPercentage:

    def test_zero_tokens(self):
        assert compute_context_percentage(0) == 0.0

    def test_half(self):
        result = compute_context_percentage(100_000, 200_000)
        assert result == pytest.approx(50.0)

    def test_full(self):
        result = compute_context_percentage(200_000, 200_000)
        assert result == pytest.approx(100.0)

    def test_over_capacity(self):
        result = compute_context_percentage(250_000, 200_000)
        assert result == pytest.approx(125.0)

    def test_zero_window(self):
        assert compute_context_percentage(100, 0) == 0.0


# ---------------------------------------------------------------------------
# Full analysis
# ---------------------------------------------------------------------------

class TestAnalyzePrompt:

    def test_basic(self):
        prompt = _build_prompt()
        analysis = analyze_prompt(prompt)
        assert len(analysis.sections) == 6
        assert analysis.total_tokens > 0
        assert analysis.context_percentage > 0
        assert analysis.over_capacity is False
        assert analysis.reduction_strategies == []

    def test_with_strategies(self):
        prompt = _build_prompt(strategies=["Priority 4 omitted"])
        analysis = analyze_prompt(prompt)
        assert len(analysis.reduction_strategies) == 1

    def test_total_is_sum(self):
        prompt = _build_prompt()
        analysis = analyze_prompt(prompt)
        expected = sum(s.estimated_tokens for s in analysis.sections)
        assert analysis.total_tokens == expected

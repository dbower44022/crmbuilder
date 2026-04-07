"""Tests for automation.prompts.structure — prompt assembly."""

from automation.prompts.structure import assemble_prompt


class TestAssemblePrompt:
    def test_contains_all_six_sections(self):
        prompt = assemble_prompt(
            header="# Session Header\nTest header",
            instructions="Follow these instructions.",
            context={"subsections": [
                {"label": "Test Data", "content": "Some data"},
            ]},
            decisions=[{"identifier": "DEC-001", "title": "Use EspoCRM", "description": "We chose it"}],
            open_issues=[{"identifier": "OI-001", "title": "TBD", "description": "Pending", "priority": "high"}],
            output_spec="# Structured Output Specification\nJSON here",
        )
        assert "Session Header" in prompt
        assert "Session Instructions" in prompt
        assert "Context" in prompt
        assert "Locked Decisions" in prompt
        assert "Open Issues" in prompt
        assert "Structured Output Specification" in prompt

    def test_sections_in_correct_order(self):
        prompt = assemble_prompt(
            header="HEADER_MARKER",
            instructions="INSTRUCTIONS_MARKER",
            context={"subsections": [{"label": "CTX", "content": "CONTEXT_MARKER"}]},
            decisions=[],
            open_issues=[],
            output_spec="OUTPUT_MARKER",
        )
        h_pos = prompt.index("HEADER_MARKER")
        i_pos = prompt.index("INSTRUCTIONS_MARKER")
        c_pos = prompt.index("CONTEXT_MARKER")
        d_pos = prompt.index("Locked Decisions")
        o_pos = prompt.index("Open Issues")
        s_pos = prompt.index("OUTPUT_MARKER")
        assert h_pos < i_pos < c_pos < d_pos < o_pos < s_pos

    def test_empty_decisions(self):
        prompt = assemble_prompt(
            header="H", instructions="I",
            context={"subsections": []},
            decisions=[],
            open_issues=[],
            output_spec="O",
        )
        assert "No locked decisions in scope" in prompt

    def test_empty_open_issues(self):
        prompt = assemble_prompt(
            header="H", instructions="I",
            context={"subsections": []},
            decisions=[],
            open_issues=[],
            output_spec="O",
        )
        assert "No open issues in scope" in prompt

    def test_decision_content_included(self):
        prompt = assemble_prompt(
            header="H", instructions="I",
            context={"subsections": []},
            decisions=[{"identifier": "DEC-042", "title": "My Decision", "description": "Details here"}],
            open_issues=[],
            output_spec="O",
        )
        assert "DEC-042" in prompt
        assert "My Decision" in prompt
        assert "Details here" in prompt

    def test_context_subsections_formatted(self):
        prompt = assemble_prompt(
            header="H", instructions="I",
            context={"subsections": [
                {"label": "Domains", "content": [
                    {"name": "Mentoring", "code": "MN"},
                ]},
                {"label": "Overview", "content": "Narrative text here"},
            ]},
            decisions=[], open_issues=[],
            output_spec="O",
        )
        assert "## Domains" in prompt
        assert "Mentoring" in prompt
        assert "## Overview" in prompt
        assert "Narrative text here" in prompt

    def test_separators_present(self):
        prompt = assemble_prompt(
            header="H", instructions="I",
            context={"subsections": []},
            decisions=[], open_issues=[],
            output_spec="O",
        )
        assert "---" in prompt

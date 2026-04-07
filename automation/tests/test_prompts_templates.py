"""Tests for automation.prompts.templates — template rendering."""

from automation.prompts.templates import (
    filter_session_blocks,
    load_template,
    render_template,
)


class TestLoadTemplate:
    def test_loads_existing_file(self, tmp_path):
        tmpl_file = tmp_path / "template-master_prd.md"
        tmpl_file.write_text("Custom template {{TOKEN}}", encoding="utf-8")
        text, is_custom = load_template("master_prd", base_dir=tmp_path)
        assert is_custom is True
        assert "Custom template" in text

    def test_returns_default_when_missing(self, tmp_path):
        text, is_custom = load_template("master_prd", base_dir=tmp_path)
        assert is_custom is False
        assert "{{SESSION_HEADER}}" in text
        assert "{{CONTEXT}}" in text
        assert "{{OUTPUT_SPEC}}" in text

    def test_default_has_all_six_sections(self, tmp_path):
        text, _ = load_template("master_prd", base_dir=tmp_path)
        assert "{{SESSION_HEADER}}" in text
        assert "{{SESSION_INSTRUCTIONS}}" in text
        assert "{{CONTEXT}}" in text
        assert "{{DECISIONS}}" in text
        assert "{{OPEN_ISSUES}}" in text
        assert "{{OUTPUT_SPEC}}" in text


class TestFilterSessionBlocks:
    def test_keeps_matching_block(self):
        template = (
            "Before\n"
            "<!-- IF session_type:initial -->\n"
            "Initial content\n"
            "<!-- ENDIF -->\n"
            "After"
        )
        result = filter_session_blocks(template, "initial")
        assert "Initial content" in result
        assert "<!-- IF" not in result
        assert "Before" in result
        assert "After" in result

    def test_removes_non_matching_block(self):
        template = (
            "Before\n"
            "<!-- IF session_type:revision -->\n"
            "Revision only\n"
            "<!-- ENDIF -->\n"
            "After"
        )
        result = filter_session_blocks(template, "initial")
        assert "Revision only" not in result
        assert "Before" in result
        assert "After" in result

    def test_multiple_blocks(self):
        template = (
            "<!-- IF session_type:initial -->\n"
            "Initial\n"
            "<!-- ENDIF -->\n"
            "<!-- IF session_type:revision -->\n"
            "Revision\n"
            "<!-- ENDIF -->\n"
            "<!-- IF session_type:clarification -->\n"
            "Clarification\n"
            "<!-- ENDIF -->"
        )
        result = filter_session_blocks(template, "revision")
        assert "Initial" not in result
        assert "Revision" in result
        assert "Clarification" not in result


class TestRenderTemplate:
    def test_replaces_tokens(self):
        template = "Hello {{NAME}}, welcome to {{PLACE}}."
        result = render_template(template, {"NAME": "Doug", "PLACE": "CRM"})
        assert result == "Hello Doug, welcome to CRM."

    def test_preserves_unreplaced_tokens(self):
        template = "{{KNOWN}} and {{UNKNOWN}}"
        result = render_template(template, {"KNOWN": "value"})
        assert result == "value and {{UNKNOWN}}"

    def test_combined_tokens_and_blocks(self):
        template = (
            "{{HEADER}}\n"
            "<!-- IF session_type:initial -->\n"
            "This is initial: {{DATA}}\n"
            "<!-- ENDIF -->\n"
            "<!-- IF session_type:revision -->\n"
            "This is revision\n"
            "<!-- ENDIF -->\n"
            "{{FOOTER}}"
        )
        result = render_template(
            template,
            {"HEADER": "Top", "DATA": "content", "FOOTER": "Bottom"},
            session_type="initial",
        )
        assert "Top" in result
        assert "This is initial: content" in result
        assert "This is revision" not in result
        assert "Bottom" in result

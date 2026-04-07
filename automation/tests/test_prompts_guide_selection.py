"""Tests for automation.prompts.guide_selection — interview guide selection."""

import pytest

from automation.prompts.guide_selection import (
    GUIDE_FILENAMES,
    get_guide_content,
    get_guide_path,
    is_guide_available,
)


class TestGetGuidePath:
    def test_known_types_return_path(self, tmp_path):
        for item_type, filename in GUIDE_FILENAMES.items():
            path = get_guide_path(item_type, base_dir=tmp_path)
            assert path.name == filename

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="No interview guide mapping"):
            get_guide_path("bogus")


class TestGetGuideContent:
    def test_returns_file_content_when_exists(self, tmp_path):
        guide_file = tmp_path / "prompt-master-prd.md"
        guide_file.write_text("# Master PRD Guide\nDo the thing.", encoding="utf-8")
        content = get_guide_content("master_prd", base_dir=tmp_path)
        assert "Master PRD Guide" in content
        assert "Do the thing." in content

    def test_returns_placeholder_when_missing(self, tmp_path):
        content = get_guide_content("master_prd", base_dir=tmp_path)
        assert "Guide not yet authored" in content

    def test_all_nine_types_return_content(self, tmp_path):
        for item_type in GUIDE_FILENAMES:
            content = get_guide_content(item_type, base_dir=tmp_path)
            assert len(content) > 0

    def test_unknown_type_raises(self, tmp_path):
        with pytest.raises(ValueError, match="No interview guide mapping"):
            get_guide_content("bogus", base_dir=tmp_path)


class TestIsGuideAvailable:
    def test_true_when_exists(self, tmp_path):
        (tmp_path / "prompt-master-prd.md").write_text("content")
        assert is_guide_available("master_prd", base_dir=tmp_path) is True

    def test_false_when_missing(self, tmp_path):
        assert is_guide_available("master_prd", base_dir=tmp_path) is False

    def test_false_for_unknown_type(self, tmp_path):
        assert is_guide_available("bogus", base_dir=tmp_path) is False

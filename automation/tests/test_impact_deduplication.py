"""Tests for automation.impact.deduplication — batch deduplication."""

from automation.impact.changeimpact import CandidateImpact
from automation.impact.deduplication import deduplicate


class TestDeduplicate:

    def test_no_duplicates_unchanged(self):
        candidates = [
            CandidateImpact(1, "Field", 10, "desc1", True),
            CandidateImpact(2, "Process", 20, "desc2", True),
        ]
        result = deduplicate(candidates)
        assert len(result) == 2

    def test_duplicates_merged(self):
        candidates = [
            CandidateImpact(1, "ProcessField", 10, "field A changed", True),
            CandidateImpact(2, "ProcessField", 10, "field B changed", True),
        ]
        result = deduplicate(candidates)
        assert len(result) == 1
        merged = result[0]
        assert merged.change_log_id == 1  # first
        assert merged.affected_table == "ProcessField"
        assert merged.affected_record_id == 10
        assert "field A changed" in merged.impact_description
        assert "field B changed" in merged.impact_description

    def test_first_changelog_id_kept(self):
        candidates = [
            CandidateImpact(5, "Field", 1, "a", True),
            CandidateImpact(3, "Field", 1, "b", True),
            CandidateImpact(7, "Field", 1, "c", True),
        ]
        result = deduplicate(candidates)
        assert result[0].change_log_id == 5  # first in list, not smallest

    def test_requires_review_or_logic(self):
        candidates = [
            CandidateImpact(1, "Field", 1, "a", False),
            CandidateImpact(2, "Field", 1, "b", True),
        ]
        result = deduplicate(candidates)
        assert result[0].requires_review is True

    def test_all_informational_stays_false(self):
        candidates = [
            CandidateImpact(1, "Decision", 1, "a", False),
            CandidateImpact(2, "Decision", 1, "b", False),
        ]
        result = deduplicate(candidates)
        assert result[0].requires_review is False

    def test_empty_input(self):
        assert deduplicate([]) == []

    def test_identical_descriptions_not_duplicated(self):
        candidates = [
            CandidateImpact(1, "Field", 1, "same desc", True),
            CandidateImpact(2, "Field", 1, "same desc", True),
        ]
        result = deduplicate(candidates)
        # Description should appear only once
        assert result[0].impact_description == "same desc"

    def test_different_records_not_merged(self):
        candidates = [
            CandidateImpact(1, "Field", 1, "a", True),
            CandidateImpact(1, "Field", 2, "b", True),
        ]
        result = deduplicate(candidates)
        assert len(result) == 2

    def test_different_tables_not_merged(self):
        candidates = [
            CandidateImpact(1, "Field", 1, "a", True),
            CandidateImpact(1, "Process", 1, "b", True),
        ]
        result = deduplicate(candidates)
        assert len(result) == 2

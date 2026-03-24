"""Tests for InstanceProfile project folder properties."""

from pathlib import Path

from espo_impl.core.models import InstanceProfile


class TestInstanceProfileProjectFolder:
    """Tests for the project folder directory properties."""

    def test_programs_dir_returns_path_when_set(self):
        profile = InstanceProfile(
            name="Test", url="https://example.com", api_key="key",
            project_folder="/tmp/my_project",
        )
        assert profile.programs_dir == Path("/tmp/my_project/programs")

    def test_programs_dir_returns_none_when_not_set(self):
        profile = InstanceProfile(
            name="Test", url="https://example.com", api_key="key",
        )
        assert profile.programs_dir is None

    def test_reports_dir_returns_correct_path(self):
        profile = InstanceProfile(
            name="Test", url="https://example.com", api_key="key",
            project_folder="/tmp/my_project",
        )
        assert profile.reports_dir == Path("/tmp/my_project/reports")

    def test_reports_dir_returns_none_when_not_set(self):
        profile = InstanceProfile(
            name="Test", url="https://example.com", api_key="key",
        )
        assert profile.reports_dir is None

    def test_docs_dir_returns_correct_path(self):
        profile = InstanceProfile(
            name="Test", url="https://example.com", api_key="key",
            project_folder="/tmp/my_project",
        )
        assert profile.docs_dir == Path("/tmp/my_project/Implementation Docs")

    def test_docs_dir_returns_none_when_not_set(self):
        profile = InstanceProfile(
            name="Test", url="https://example.com", api_key="key",
        )
        assert profile.docs_dir is None

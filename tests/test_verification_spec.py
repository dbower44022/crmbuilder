"""Tests for verification spec builder."""

from textwrap import dedent

import pytest

from espo_impl.core.config_loader import ConfigLoader
from tools.docgen.builders.verification_spec_builder import (
    build_external_dependencies_section,
)


@pytest.fixture
def loader():
    return ConfigLoader()


def _write_yaml(tmp_path, filename, content):
    """Write YAML content to a file and return the path."""
    path = tmp_path / filename
    path.write_text(dedent(content))
    return path


def _load(loader, path):
    """Load a single YAML file and return the ProgramFile."""
    return loader.load_program(path)


class TestExternalDependenciesBuilder:
    """Tests for build_external_dependencies_section."""

    def test_identifies_externally_populated_fields(self, loader, tmp_path):
        """Builder picks up fields with externallyPopulated: true."""
        path = _write_yaml(tmp_path, "prog.yaml", """\
            version: "1.1"
            description: "Test"
            entities:
              Contact:
                fields:
                  - name: lmsScore
                    type: int
                    label: "LMS Score"
                    externallyPopulated: true
                    description: "Score from LMS integration"
                  - name: firstName
                    type: varchar
                    label: "First Name"
        """)
        program = _load(loader, path)
        content = build_external_dependencies_section([program])

        assert "## External Integration Dependencies" in content
        assert "`lmsScore`" in content
        assert "LMS Score" in content
        assert "int" in content
        assert "Score from LMS integration" in content
        assert "firstName" not in content

    def test_groups_by_entity(self, loader, tmp_path):
        """Fields are grouped under their entity heading."""
        path = _write_yaml(tmp_path, "prog.yaml", """\
            version: "1.1"
            description: "Test"
            entities:
              Contact:
                fields:
                  - name: lmsScore
                    type: int
                    label: "LMS Score"
                    externallyPopulated: true
              Account:
                fields:
                  - name: erpId
                    type: varchar
                    label: "ERP ID"
                    externallyPopulated: true
                    description: "Synced from ERP"
        """)
        program = _load(loader, path)
        content = build_external_dependencies_section([program])

        assert "### Account" in content
        assert "### Contact" in content
        assert "`erpId`" in content
        assert "`lmsScore`" in content

    def test_correct_field_details(self, loader, tmp_path):
        """Each field entry includes name, label, type, and description."""
        path = _write_yaml(tmp_path, "prog.yaml", """\
            version: "1.1"
            description: "Test"
            entities:
              Contact:
                fields:
                  - name: externalId
                    type: varchar
                    label: "External ID"
                    externallyPopulated: true
                    description: "ID from external system"
        """)
        program = _load(loader, path)
        content = build_external_dependencies_section([program])

        # Check the table row contains all expected values
        assert "| `externalId` | External ID | varchar | ID from external system |" in content

    def test_zero_externally_populated_fields(self, loader, tmp_path):
        """When no fields are externally populated, output says so."""
        path = _write_yaml(tmp_path, "prog.yaml", """\
            version: "1.1"
            description: "Test"
            entities:
              Contact:
                fields:
                  - name: firstName
                    type: varchar
                    label: "First Name"
                  - name: lastName
                    type: varchar
                    label: "Last Name"
        """)
        program = _load(loader, path)
        content = build_external_dependencies_section([program])

        assert "No fields are marked as externally populated" in content
        assert "### " not in content

    def test_mixed_entities_some_with_some_without(self, loader, tmp_path):
        """Only entities with externally populated fields appear."""
        path = _write_yaml(tmp_path, "prog.yaml", """\
            version: "1.1"
            description: "Test"
            entities:
              Contact:
                fields:
                  - name: firstName
                    type: varchar
                    label: "First Name"
              Account:
                fields:
                  - name: syncStatus
                    type: enum
                    label: "Sync Status"
                    externallyPopulated: true
                    options:
                      - Pending
                      - Synced
                    translatedOptions:
                      Pending: "Pending"
                      Synced: "Synced"
        """)
        program = _load(loader, path)
        content = build_external_dependencies_section([program])

        assert "### Account" in content
        assert "`syncStatus`" in content
        # Contact has no externally populated fields — should not appear
        assert "### Contact" not in content

    def test_multiple_programs(self, loader, tmp_path):
        """Builder merges fields from multiple program files."""
        path1 = _write_yaml(tmp_path, "prog1.yaml", """\
            version: "1.1"
            description: "Program 1"
            entities:
              Contact:
                fields:
                  - name: lmsScore
                    type: int
                    label: "LMS Score"
                    externallyPopulated: true
        """)
        path2 = _write_yaml(tmp_path, "prog2.yaml", """\
            version: "1.1"
            description: "Program 2"
            entities:
              Account:
                fields:
                  - name: erpId
                    type: varchar
                    label: "ERP ID"
                    externallyPopulated: true
        """)
        prog1 = _load(loader, path1)
        prog2 = _load(loader, path2)
        content = build_external_dependencies_section([prog1, prog2])

        assert "### Account" in content
        assert "### Contact" in content

    def test_field_without_description_shows_dash(self, loader, tmp_path):
        """Fields without a description show an em-dash."""
        path = _write_yaml(tmp_path, "prog.yaml", """\
            version: "1.1"
            description: "Test"
            entities:
              Contact:
                fields:
                  - name: externalFlag
                    type: bool
                    label: "External Flag"
                    externallyPopulated: true
        """)
        program = _load(loader, path)
        content = build_external_dependencies_section([program])

        assert "\u2014" in content

    def test_end_to_end_from_yaml_to_content(self, loader, tmp_path):
        """End-to-end: load YAML, build section, verify structure."""
        path = _write_yaml(tmp_path, "prog.yaml", """\
            version: "1.1"
            description: "Full test"
            entities:
              Contact:
                fields:
                  - name: score
                    type: int
                    label: "Score"
                    externallyPopulated: true
                    description: "Test score"
                  - name: name
                    type: varchar
                    label: "Name"
              Account:
                fields:
                  - name: revenue
                    type: currency
                    label: "Revenue"
                    externallyPopulated: true
                    description: "Annual revenue from ERP"
                  - name: industry
                    type: enum
                    label: "Industry"
                    options:
                      - Tech
                      - Finance
                    translatedOptions:
                      Tech: "Technology"
                      Finance: "Finance"
        """)
        program = _load(loader, path)
        content = build_external_dependencies_section([program])

        # Structure checks
        assert content.startswith("## External Integration Dependencies")
        assert "### Account" in content
        assert "### Contact" in content
        # Table header present
        assert "| Field | Label | Type | Description |" in content
        # Correct field data
        assert "`score`" in content
        assert "`revenue`" in content
        # Non-externally-populated fields absent
        assert "`name`" not in content
        assert "`industry`" not in content

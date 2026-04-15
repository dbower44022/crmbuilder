"""Tests for requiredWhen: parsing, validation, and deploy translation."""

from textwrap import dedent

import pytest

from espo_impl.core.condition_expression import AllNode, LeafClause, render_condition
from espo_impl.core.config_loader import ConfigLoader


@pytest.fixture
def loader():
    return ConfigLoader()


# ─── Parsing Tests ───────────────────────────────────────────────


def test_parse_required_when_shorthand(loader, tmp_path):
    """Shorthand requiredWhen (flat list) parses via parse_condition."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: email
                type: varchar
                label: "Email"
                requiredWhen:
                  - { field: status, op: equals, value: "Active" }
              - name: status
                type: enum
                label: "Status"
                options: ["Active", "Inactive"]
    """)
    path = tmp_path / "shorthand.yaml"
    path.write_text(content)
    program = loader.load_program(path)

    field = program.entities[0].fields[0]
    assert field.required_when is not None
    assert isinstance(field.required_when, AllNode)
    assert field.required_when_raw is not None


def test_parse_required_when_structured(loader, tmp_path):
    """Structured requiredWhen (all/any) parses via parse_condition."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: email
                type: varchar
                label: "Email"
                requiredWhen:
                  all:
                    - { field: status, op: equals, value: "Active" }
                    - { field: role, op: equals, value: "Admin" }
              - name: status
                type: enum
                label: "Status"
                options: ["Active"]
              - name: role
                type: enum
                label: "Role"
                options: ["Admin"]
    """)
    path = tmp_path / "structured.yaml"
    path.write_text(content)
    program = loader.load_program(path)

    field = program.entities[0].fields[0]
    assert field.required_when is not None
    assert isinstance(field.required_when, AllNode)


def test_parse_required_when_absent(loader, tmp_path):
    """Absent requiredWhen leaves the typed field as None."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: email
                type: varchar
                label: "Email"
    """)
    path = tmp_path / "absent.yaml"
    path.write_text(content)
    program = loader.load_program(path)

    field = program.entities[0].fields[0]
    assert field.required_when is None
    assert field.required_when_raw is None


# ─── Validation Tests ────────────────────────────────────────────


def test_validate_mutual_exclusion_required_and_required_when(loader, tmp_path):
    """required: true with requiredWhen produces validation error."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: email
                type: varchar
                label: "Email"
                required: true
                requiredWhen:
                  - { field: status, op: equals, value: "Active" }
              - name: status
                type: enum
                label: "Status"
                options: ["Active"]
    """)
    path = tmp_path / "mutual_exclusion.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any(
        "required: true" in e and "requiredWhen" in e
        for e in errors
    )


def test_validate_unknown_field_in_required_when(loader, tmp_path):
    """Unknown field in requiredWhen produces validation error."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: email
                type: varchar
                label: "Email"
                requiredWhen:
                  - { field: ghostField, op: equals, value: "x" }
    """)
    path = tmp_path / "unknown_field.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("ghostField" in e and "requiredWhen" in e for e in errors)


def test_validate_valid_required_when(loader, tmp_path):
    """Valid requiredWhen produces no errors."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: email
                type: varchar
                label: "Email"
                requiredWhen:
                  - { field: status, op: equals, value: "Active" }
              - name: status
                type: enum
                label: "Status"
                options: ["Active"]
    """)
    path = tmp_path / "valid.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    rw_errors = [e for e in errors if "requiredWhen" in e]
    assert rw_errors == []


# ─── Deploy Translation Tests ────────────────────────────────────


def test_render_required_when_for_api():
    """Parsed requiredWhen renders to CRM-API-ready dict."""
    condition = AllNode(children=[
        LeafClause(field="status", op="equals", value="Active"),
    ])
    rendered = render_condition(condition)
    assert isinstance(rendered, dict)
    assert "all" in rendered
    assert rendered["all"][0]["field"] == "status"
    assert rendered["all"][0]["op"] == "equals"
    assert rendered["all"][0]["value"] == "Active"

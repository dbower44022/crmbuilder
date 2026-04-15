"""Tests for visibleWhen: parsing, validation, and deploy translation."""

from textwrap import dedent

import pytest

from espo_impl.core.condition_expression import AllNode, LeafClause, render_condition
from espo_impl.core.config_loader import ConfigLoader


@pytest.fixture
def loader():
    return ConfigLoader()


# ─── Field-Level Parsing ─────────────────────────────────────────


def test_parse_field_visible_when_shorthand(loader, tmp_path):
    """Shorthand visibleWhen on field parses via parse_condition."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: email
                type: varchar
                label: "Email"
                visibleWhen:
                  - { field: status, op: equals, value: "Active" }
              - name: status
                type: enum
                label: "Status"
                options: ["Active", "Inactive"]
    """)
    path = tmp_path / "field_shorthand.yaml"
    path.write_text(content)
    program = loader.load_program(path)

    field = program.entities[0].fields[0]
    assert field.visible_when is not None
    assert isinstance(field.visible_when, AllNode)


def test_parse_field_visible_when_structured(loader, tmp_path):
    """Structured visibleWhen (all/any) on field parses."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: email
                type: varchar
                label: "Email"
                visibleWhen:
                  any:
                    - { field: status, op: equals, value: "Active" }
                    - { field: status, op: equals, value: "Pending" }
              - name: status
                type: enum
                label: "Status"
                options: ["Active", "Pending"]
    """)
    path = tmp_path / "field_structured.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    assert program.entities[0].fields[0].visible_when is not None


def test_parse_field_visible_when_absent(loader, tmp_path):
    """Absent visibleWhen on field leaves typed field as None."""
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
    path = tmp_path / "field_absent.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    assert program.entities[0].fields[0].visible_when is None


# ─── Panel-Level Parsing ─────────────────────────────────────────


def test_parse_panel_visible_when_shorthand(loader, tmp_path):
    """Shorthand visibleWhen on panel parses via parse_condition."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: status
                type: enum
                label: "Status"
                options: ["Active"]
            layout:
              detail:
                panels:
                  - label: "Main"
                    visibleWhen:
                      - { field: status, op: equals, value: "Active" }
                    rows:
                      - [status]
    """)
    path = tmp_path / "panel_shorthand.yaml"
    path.write_text(content)
    program = loader.load_program(path)

    panel = program.entities[0].layouts["detail"].panels[0]
    assert panel.visible_when is not None
    assert isinstance(panel.visible_when, AllNode)


def test_parse_panel_visible_when_absent(loader, tmp_path):
    """Absent visibleWhen on panel leaves typed field as None."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: email
                type: varchar
                label: "Email"
            layout:
              detail:
                panels:
                  - label: "Main"
                    rows:
                      - [email]
    """)
    path = tmp_path / "panel_absent.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    panel = program.entities[0].layouts["detail"].panels[0]
    assert panel.visible_when is None


# ─── Field-Level Validation ──────────────────────────────────────


def test_validate_mutual_exclusion_required_and_visible_when(loader, tmp_path):
    """required: true with visibleWhen produces validation error."""
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
                visibleWhen:
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
        "required: true" in e and "visibleWhen" in e
        for e in errors
    )


def test_validate_unknown_field_in_visible_when(loader, tmp_path):
    """Unknown field in field-level visibleWhen produces validation error."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: email
                type: varchar
                label: "Email"
                visibleWhen:
                  - { field: ghostField, op: equals, value: "x" }
    """)
    path = tmp_path / "unknown_field.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("ghostField" in e and "visibleWhen" in e for e in errors)


# ─── Panel-Level Validation ──────────────────────────────────────


def test_validate_panel_mutual_exclusion(loader, tmp_path):
    """visibleWhen and dynamicLogicVisible on same panel produces error."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: status
                type: enum
                label: "Status"
                options: ["Active"]
            layout:
              detail:
                panels:
                  - label: "Main"
                    visibleWhen:
                      - { field: status, op: equals, value: "Active" }
                    dynamicLogicVisible:
                      attribute: status
                      value: "Active"
                    rows:
                      - [status]
    """)
    path = tmp_path / "panel_conflict.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any(
        "visibleWhen" in e and "dynamicLogicVisible" in e
        for e in errors
    )


def test_validate_panel_visible_when_only_is_ok(loader, tmp_path):
    """Panel with only visibleWhen (no dynamicLogicVisible) is valid."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: status
                type: enum
                label: "Status"
                options: ["Active"]
            layout:
              detail:
                panels:
                  - label: "Main"
                    visibleWhen:
                      - { field: status, op: equals, value: "Active" }
                    rows:
                      - [status]
    """)
    path = tmp_path / "panel_vw_only.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    panel_errors = [
        e for e in errors
        if "visibleWhen" in e and "dynamicLogicVisible" in e
    ]
    assert panel_errors == []


def test_validate_panel_unknown_field_in_visible_when(loader, tmp_path):
    """Unknown field in panel visibleWhen produces validation error."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: status
                type: enum
                label: "Status"
                options: ["Active"]
            layout:
              detail:
                panels:
                  - label: "Main"
                    visibleWhen:
                      - { field: ghostField, op: equals, value: "x" }
                    rows:
                      - [status]
    """)
    path = tmp_path / "panel_bad_field.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("ghostField" in e for e in errors)


# ─── Deploy Translation ──────────────────────────────────────────


def test_render_visible_when_for_api():
    """Parsed visibleWhen renders to CRM-API-ready dict."""
    condition = AllNode(children=[
        LeafClause(field="status", op="equals", value="Active"),
    ])
    rendered = render_condition(condition)
    assert isinstance(rendered, dict)
    assert "all" in rendered


def test_valid_field_and_panel_visible_when(loader, tmp_path):
    """Valid visibleWhen on both field and panel produces no errors."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: email
                type: varchar
                label: "Email"
                visibleWhen:
                  - { field: status, op: equals, value: "Active" }
              - name: status
                type: enum
                label: "Status"
                options: ["Active", "Inactive"]
            layout:
              detail:
                panels:
                  - label: "Main"
                    visibleWhen:
                      - { field: status, op: equals, value: "Active" }
                    rows:
                      - [email, status]
    """)
    path = tmp_path / "valid_both.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    vw_errors = [e for e in errors if "visibleWhen" in e]
    assert vw_errors == []

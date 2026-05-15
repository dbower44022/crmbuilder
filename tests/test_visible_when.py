"""Tests for visibleWhen: parsing, validation, and deploy translation."""

from textwrap import dedent

import pytest

from espo_impl.core.condition_expression import AllNode, LeafClause, render_condition
from espo_impl.core.config_loader import ConfigLoader
from espo_impl.core.models import ProgramContext


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
    """Unknown field in field-level visibleWhen is deferred, not an error.

    The validator drops the parsed condition from the field def so the
    deploy payload omits dynamicLogicVisible, and records a soft
    warning on ``program.condition_warnings``. The author can re-run
    the YAML after the referenced field has been created.
    """
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
    assert not any("ghostField" in e for e in errors), errors
    assert any(
        "ghostField" in w and "visibleWhen" in w and "deferred" in w
        for w in program.condition_warnings
    )
    email_field = program.entities[0].fields[0]
    assert email_field.visible_when is None


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
    """Unknown field in panel visibleWhen is deferred, not an error.

    Same contract as the field-level case: the parsed condition is
    cleared from the panel so the layout still deploys (without
    dynamic logic), and a soft warning lands on
    ``program.condition_warnings``.
    """
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
    assert not any("ghostField" in e for e in errors), errors
    assert any(
        "ghostField" in w and "visibleWhen" in w and "deferred" in w
        for w in program.condition_warnings
    )
    panel = program.entities[0].layouts["detail"].panels[0]
    assert panel.visible_when is None


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


# ─── Deferred-condition behavior ────────────────────────────────


def test_structural_error_in_visible_when_is_not_deferred(loader, tmp_path):
    """A bad operator in visibleWhen is still a hard error.

    Structural problems (unknown operator, missing value, wrong value
    shape) are distinct from "field not in batch yet" and must keep
    failing validation. Deferral applies only to reference-only
    failures.
    """
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
                  - { field: status, op: bogusOp, value: "Active" }
              - name: status
                type: enum
                label: "Status"
                options: ["Active"]
    """)
    path = tmp_path / "bad_op.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any(
        "bogusOp" in e and "visibleWhen" in e for e in errors
    )
    assert program.condition_warnings == []


def test_visible_when_resolved_via_cross_batch_context(loader, tmp_path):
    """Field declared in a sibling YAML resolves the reference cleanly.

    The cross-batch ProgramContext unions field names across files, so
    a YAML that references a sibling's field is fully valid — no
    deferral, no warning, parsed condition preserved on the field.
    """
    content_a = dedent("""\
        version: "1.1"
        description: "A"
        entities:
          Contact:
            fields:
              - name: email
                type: varchar
                label: "Email"
                visibleWhen:
                  - { field: status, op: equals, value: "Active" }
    """)
    content_b = dedent("""\
        version: "1.1"
        description: "B"
        entities:
          Contact:
            fields:
              - name: status
                type: enum
                label: "Status"
                options: ["Active"]
    """)
    path_a = tmp_path / "a.yaml"
    path_a.write_text(content_a)
    path_b = tmp_path / "b.yaml"
    path_b.write_text(content_b)
    program_a = loader.load_program(path_a)
    program_b = loader.load_program(path_b)
    context = ProgramContext.from_programs([program_a, program_b])

    errors = loader.validate_program_with_context(program_a, context)
    assert errors == []
    assert program_a.condition_warnings == []
    email_field = program_a.entities[0].fields[0]
    assert email_field.visible_when is not None


def test_rerun_after_referenced_field_exists_applies_condition(loader, tmp_path):
    """Once the referenced field is added to the batch, the condition applies.

    Simulates the operator's re-run after creating the previously-
    missing field. First pass: deferral + warning. Second pass with
    the field present: clean validation, condition preserved.
    """
    initial = dedent("""\
        version: "1.1"
        description: "Initial"
        entities:
          Contact:
            fields:
              - name: email
                type: varchar
                label: "Email"
                visibleWhen:
                  - { field: status, op: equals, value: "Active" }
    """)
    path = tmp_path / "v1.yaml"
    path.write_text(initial)
    program = loader.load_program(path)
    loader.validate_program(program)
    assert program.entities[0].fields[0].visible_when is None
    assert len(program.condition_warnings) == 1

    # Author adds the referenced field to the same YAML and re-runs.
    updated = dedent("""\
        version: "1.1"
        description: "Updated"
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
                options: ["Active"]
    """)
    path.write_text(updated)
    program2 = loader.load_program(path)
    errors2 = loader.validate_program(program2)
    assert errors2 == []
    assert program2.condition_warnings == []
    assert program2.entities[0].fields[0].visible_when is not None


def test_panel_visible_when_structural_error_still_errors(loader, tmp_path):
    """Panel visibleWhen with a structural error is a hard reject."""
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
                      - { field: status, op: bogusOp, value: "Active" }
                    rows:
                      - [status]
    """)
    path = tmp_path / "panel_bad_op.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("bogusOp" in e for e in errors)
    assert program.condition_warnings == []

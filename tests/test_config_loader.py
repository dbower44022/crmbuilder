"""Tests for YAML config loading and validation."""

from pathlib import Path
from textwrap import dedent

import pytest

from espo_impl.core.config_loader import ConfigLoader
from espo_impl.core.models import EntityAction


@pytest.fixture
def loader():
    return ConfigLoader()


@pytest.fixture
def valid_yaml(tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test program"

        entities:
          Contact:
            fields:
              - name: contactType
                type: enum
                label: "Contact Type"
                options:
                  - Mentor
                  - Client
                translatedOptions:
                  Mentor: "Mentor"
                  Client: "Client"
              - name: isMentor
                type: bool
                label: "Is Mentor"
    """)
    path = tmp_path / "test_program.yaml"
    path.write_text(content)
    return path


def test_load_valid_program(loader, valid_yaml):
    program = loader.load_program(valid_yaml)
    assert program.version == "1.0"
    assert program.description == "Test program"
    assert len(program.entities) == 1
    assert program.entities[0].name == "Contact"
    assert program.entities[0].action == EntityAction.NONE
    assert len(program.entities[0].fields) == 2
    assert program.entities[0].fields[0].name == "contactType"
    assert program.entities[0].fields[0].options == ["Mentor", "Client"]
    assert program.entities[0].fields[1].type == "bool"


def test_validate_valid_program(loader, valid_yaml):
    program = loader.load_program(valid_yaml)
    errors = loader.validate_program(program)
    assert errors == []


def test_validate_missing_version(loader, tmp_path):
    content = dedent("""\
        description: "Test"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
    """)
    path = tmp_path / "no_version.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("version" in e for e in errors)


def test_validate_missing_description(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
    """)
    path = tmp_path / "no_desc.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("description" in e for e in errors)


def test_validate_empty_entities(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
    """)
    path = tmp_path / "empty_entities.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("entities" in e for e in errors)


def test_validate_missing_field_name(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - type: varchar
                label: "No Name"
    """)
    path = tmp_path / "no_name.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("name" in e for e in errors)


def test_validate_unsupported_type(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: foo
                type: unsupported
                label: "Foo"
    """)
    path = tmp_path / "bad_type.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("unsupported" in e for e in errors)


def test_validate_field_link_type_emits_specific_message(loader, tmp_path):
    """A field with ``type: link`` is rejected with a message that
    points the operator to the top-level relationships block."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          FUContribution:
            fields:
              - name: contributor
                type: link
                label: "Contributor"
    """)
    path = tmp_path / "link_field.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    matches = [
        e for e in errors
        if "'link' is not a valid field type" in e
        and "declared in the top-level 'relationships:' block" in e
    ]
    assert matches, f"Expected link-specific message, got: {errors!r}"


def test_validate_field_name_must_start_lowercase(loader, tmp_path):
    """A field whose name starts with an uppercase letter is rejected
    with a message that points the operator at the camelCase requirement.

    EspoCRM's /Admin/fieldManager endpoint returns HTTP 500 with no body
    when the name leads with an uppercase letter, so the validator
    catches this before the request goes out.
    """
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Mentor:
            fields:
              - name: MentorStatus
                type: enum
                label: "Mentor Status"
                options:
                  - "Candidate"
                  - "Approved"
    """)
    path = tmp_path / "uppercase_field.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any(
        "'MentorStatus'" in e and "camelCase" in e and "lowercase" in e
        for e in errors
    ), f"Expected camelCase rejection, got: {errors!r}"


def test_validate_field_name_lowercase_passes(loader, tmp_path):
    """A field whose name starts with a lowercase letter passes the
    name-format check (the engine c-prefixes it server-side)."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Mentor:
            fields:
              - name: mentorStatus
                type: enum
                label: "Mentor Status"
                options:
                  - "Candidate"
                  - "Approved"
    """)
    path = tmp_path / "lowercase_field.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert not any(
        "camelCase" in e and "mentorStatus" in e
        for e in errors
    )


def test_validate_field_other_unsupported_type_emits_generic_message(
    loader, tmp_path,
):
    """Non-link unsupported field types continue to emit the generic
    ``unsupported field type 'X'`` message."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: bar
                type: frobnicate
                label: "Bar"
    """)
    path = tmp_path / "bad_other_type.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("unsupported field type 'frobnicate'" in e for e in errors)
    assert not any(
        "declared in the top-level 'relationships:' block" in e
        for e in errors
    )


def test_validate_enum_without_options(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: status
                type: enum
                label: "Status"
    """)
    path = tmp_path / "enum_no_opts.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("options" in e for e in errors)


def test_validate_program_accepts_empty_options_when_options_deferred_true(
    loader, tmp_path,
):
    """An enum field with options:[] and optionsDeferred:true validates cleanly."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Account:
            fields:
              - name: industrySubsector
                type: enum
                label: "Industry Subsector"
                optionsDeferred: true
                options: []
    """)
    path = tmp_path / "deferred_ok.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert not any("options" in e for e in errors), (
        f"Expected no options-related errors, got: {errors!r}"
    )


def test_validate_program_still_rejects_empty_options_when_flag_absent(
    loader, tmp_path,
):
    """An enum field with options:[] and no optionsDeferred is still rejected."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: status
                type: enum
                label: "Status"
                options: []
    """)
    path = tmp_path / "deferred_absent.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any(
        "non-empty 'options'" in e for e in errors
    ), f"Expected the standard non-empty options error, got: {errors!r}"


def test_validate_program_still_rejects_empty_options_when_flag_false(
    loader, tmp_path,
):
    """Explicit optionsDeferred:false does not bypass the empty-options check."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: status
                type: enum
                label: "Status"
                optionsDeferred: false
                options: []
    """)
    path = tmp_path / "deferred_false.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any(
        "non-empty 'options'" in e for e in errors
    ), f"Expected the standard non-empty options error, got: {errors!r}"


def test_validate_program_options_deferred_must_be_boolean(loader, tmp_path):
    """Non-boolean optionsDeferred values are rejected with a type-check error."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: status
                type: enum
                label: "Status"
                optionsDeferred: "yes"
                options: []
    """)
    path = tmp_path / "deferred_non_bool.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any(
        "'optionsDeferred' must be a boolean" in e for e in errors
    ), f"Expected boolean type error, got: {errors!r}"


def test_validate_program_options_deferred_only_on_enum_types(loader, tmp_path):
    """optionsDeferred:true on a non-enum type is flagged as inappropriate."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: notes
                type: varchar
                label: "Notes"
                optionsDeferred: true
    """)
    path = tmp_path / "deferred_non_enum.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any(
        "'optionsDeferred' is only valid on enum/multiEnum fields" in e
        for e in errors
    ), f"Expected enum-only error, got: {errors!r}"


def test_validate_program_non_empty_options_with_options_deferred_validates(
    loader, tmp_path,
):
    """Non-empty options with optionsDeferred:true validates fine — the flag has
    no effect when options are explicitly listed."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: status
                type: enum
                label: "Status"
                optionsDeferred: true
                options:
                  - A
                  - B
    """)
    path = tmp_path / "deferred_with_opts.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert errors == [], f"Expected clean validation, got: {errors!r}"


def test_validate_duplicate_field_names(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
              - name: foo
                type: varchar
                label: "Foo Again"
    """)
    path = tmp_path / "dupes.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("duplicate" in e for e in errors)


def test_load_invalid_yaml(loader, tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("{{invalid yaml::")
    with pytest.raises(ValueError, match="Failed to parse YAML"):
        loader.load_program(path)


def test_validate_missing_label(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
    """)
    path = tmp_path / "no_label.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("label" in e for e in errors)


# --- Entity action tests ---


def test_load_entity_create(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Engagement:
            action: create
            type: Base
            labelSingular: "Engagement"
            labelPlural: "Engagements"
            stream: true
            fields:
              - name: status
                type: enum
                label: "Status"
                options:
                  - Active
                  - Closed
    """)
    path = tmp_path / "create.yaml"
    path.write_text(content)
    program = loader.load_program(path)

    assert program.entities[0].action == EntityAction.CREATE
    assert program.entities[0].type == "Base"
    assert program.entities[0].labelSingular == "Engagement"
    assert program.entities[0].labelPlural == "Engagements"
    assert program.entities[0].stream is True
    assert len(program.entities[0].fields) == 1
    assert not program.has_delete_operations


def test_load_entity_delete(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Engagement:
            action: delete
    """)
    path = tmp_path / "delete.yaml"
    path.write_text(content)
    program = loader.load_program(path)

    assert program.entities[0].action == EntityAction.DELETE
    assert program.entities[0].fields == []
    assert program.has_delete_operations


def test_load_entity_delete_and_create(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Engagement:
            action: delete_and_create
            type: Base
            labelSingular: "Engagement"
            labelPlural: "Engagements"
            fields:
              - name: status
                type: varchar
                label: "Status"
    """)
    path = tmp_path / "rebuild.yaml"
    path.write_text(content)
    program = loader.load_program(path)

    assert program.entities[0].action == EntityAction.DELETE_AND_CREATE
    assert program.has_delete_operations
    assert len(program.entities[0].fields) == 1


def test_load_entity_no_action(loader, valid_yaml):
    """Entities without action default to NONE (fields-only)."""
    program = loader.load_program(valid_yaml)
    assert program.entities[0].action == EntityAction.NONE
    assert not program.has_delete_operations


def test_validate_create_missing_type(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Engagement:
            action: create
            labelSingular: "Engagement"
            labelPlural: "Engagements"
    """)
    path = tmp_path / "no_type.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("type" in e and "required" in e for e in errors)


def test_validate_create_missing_labels(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Engagement:
            action: create
            type: Base
    """)
    path = tmp_path / "no_labels.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("labelSingular" in e for e in errors)
    assert any("labelPlural" in e for e in errors)


def test_validate_create_invalid_entity_type(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Engagement:
            action: create
            type: InvalidType
            labelSingular: "Engagement"
            labelPlural: "Engagements"
    """)
    path = tmp_path / "bad_entity_type.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("unsupported entity type" in e for e in errors)


def test_validate_delete_with_fields_is_error(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Engagement:
            action: delete
            fields:
              - name: foo
                type: varchar
                label: "Foo"
    """)
    path = tmp_path / "delete_with_fields.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("delete" in e and "fields" in e for e in errors)


def test_validate_delete_and_create_requires_type(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Engagement:
            action: delete_and_create
            labelSingular: "Engagement"
            labelPlural: "Engagements"
    """)
    path = tmp_path / "rebuild_no_type.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("type" in e and "required" in e for e in errors)


def test_load_field_with_min_max(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Session:
            fields:
              - name: npsScore
                type: int
                label: "NPS Score"
                min: 0
                max: 10
    """)
    path = tmp_path / "min_max.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert errors == []
    field = program.entities[0].fields[0]
    assert field.min == 0
    assert field.max == 10


def test_load_field_with_max_length(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Account:
            fields:
              - name: einNumber
                type: varchar
                label: "EIN Number"
                maxLength: 20
    """)
    path = tmp_path / "max_length.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert errors == []
    field = program.entities[0].fields[0]
    assert field.maxLength == 20


# --- Layout tests ---


def test_load_field_with_category(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: isMentor
                type: bool
                label: "Is Mentor"
                category: mentor
    """)
    path = tmp_path / "category.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    assert program.entities[0].fields[0].category == "mentor"


def test_load_layout_detail_with_panels(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: isMentor
                type: bool
                label: "Is Mentor"
                category: mentor
            layout:
              detail:
                panels:
                  - label: "Mentor Info"
                    tabBreak: true
                    tabLabel: "Mentor"
                    tabs:
                      - label: "Mentor Details"
                        category: mentor
    """)
    path = tmp_path / "layout_detail.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    entity = program.entities[0]
    assert "detail" in entity.layouts
    layout = entity.layouts["detail"]
    assert layout.layout_type == "detail"
    assert len(layout.panels) == 1
    assert layout.panels[0].label == "Mentor Info"
    assert layout.panels[0].tabBreak is True
    assert layout.panels[0].tabLabel == "Mentor"
    assert len(layout.panels[0].tabs) == 1
    assert layout.panels[0].tabs[0].category == "mentor"


def test_load_layout_list_with_columns(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: isMentor
                type: bool
                label: "Is Mentor"
            layout:
              list:
                columns:
                  - field: name
                    width: 30
                  - field: isMentor
    """)
    path = tmp_path / "layout_list.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    entity = program.entities[0]
    assert "list" in entity.layouts
    layout = entity.layouts["list"]
    assert layout.layout_type == "list"
    assert len(layout.columns) == 2
    assert layout.columns[0].field == "name"
    assert layout.columns[0].width == 30
    assert layout.columns[1].field == "isMentor"
    assert layout.columns[1].width is None


def test_validate_panel_rows_and_tabs_error(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
                category: general
            layout:
              detail:
                panels:
                  - label: "Bad Panel"
                    rows:
                      - [foo]
                    tabs:
                      - label: "Tab"
                        category: general
    """)
    path = tmp_path / "both.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("both" in e and "rows" in e and "tabs" in e for e in errors)


def test_validate_tab_category_not_found(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
            layout:
              detail:
                panels:
                  - label: "Panel"
                    tabs:
                      - label: "Tab"
                        category: nonexistent
    """)
    path = tmp_path / "bad_cat.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("nonexistent" in e and "not found" in e for e in errors)


def test_validate_tab_break_without_label(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
            layout:
              detail:
                panels:
                  - label: "Panel"
                    tabBreak: true
                    rows:
                      - [foo]
    """)
    path = tmp_path / "no_tab_label.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("tabLabel" in e and "required" in e for e in errors)


def test_validate_list_layout_must_have_columns(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
            layout:
              list:
                panels:
                  - label: "Bad"
    """)
    path = tmp_path / "list_no_cols.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("columns" in e for e in errors)


def test_validate_valid_layout_no_errors(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: isMentor
                type: bool
                label: "Is Mentor"
                category: mentor
              - name: mentorStatus
                type: enum
                label: "Status"
                category: mentor
                options:
                  - Active
                  - Inactive
            layout:
              detail:
                panels:
                  - label: "Mentor Info"
                    tabBreak: true
                    tabLabel: "Mentor"
                    tabs:
                      - label: "Details"
                        category: mentor
              list:
                columns:
                  - field: name
                  - field: isMentor
    """)
    path = tmp_path / "valid_layout.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert errors == []


# --- Description property tests ---


def test_panel_rows_parsed(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
              - name: bar
                type: varchar
                label: "Bar"
            layout:
              detail:
                panels:
                  - label: "General"
                    rows:
                      - [foo, bar]
                      - [foo]
    """)
    path = tmp_path / "panel_rows.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    panel = program.entities[0].layouts["detail"].panels[0]
    assert panel.rows is not None
    assert len(panel.rows) == 2
    assert panel.rows[0] == ["foo", "bar"]
    assert panel.rows[1] == ["foo"]


def test_panel_dynamic_logic_visible_parsed(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
            layout:
              detail:
                panels:
                  - label: "Conditional"
                    dynamicLogicVisible:
                      conditionGroup:
                        - type: equals
                          attribute: contactType
                          value: Mentor
                    rows:
                      - [foo]
    """)
    path = tmp_path / "dynamic_logic.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    panel = program.entities[0].layouts["detail"].panels[0]
    assert panel.dynamicLogicVisible is not None
    assert "conditionGroup" in panel.dynamicLogicVisible
    assert panel.dynamicLogicVisible["conditionGroup"][0]["attribute"] == "contactType"


def test_entity_description_parsed(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            description: >
              Represents individuals in the CRM system.
              Includes both mentors and clients.
            fields:
              - name: foo
                type: varchar
                label: "Foo"
    """)
    path = tmp_path / "entity_desc.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    assert program.entities[0].description is not None
    assert "individuals" in program.entities[0].description


def test_field_description_parsed(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: contactType
                type: enum
                label: "Contact Type"
                description: "Classifies contact as Mentor or Client"
                options:
                  - Mentor
                  - Client
    """)
    path = tmp_path / "field_desc.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    assert program.entities[0].fields[0].description == "Classifies contact as Mentor or Client"


def test_field_copy_to_clipboard_parsed(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: einNumber
                type: varchar
                label: "EIN Number"
                copyToClipboard: true
              - name: firstName
                type: varchar
                label: "First Name"
    """)
    path = tmp_path / "clipboard.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    assert program.entities[0].fields[0].copyToClipboard is True
    assert program.entities[0].fields[1].copyToClipboard is None


def test_field_tooltip_parsed(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: mentorStatus
                type: enum
                label: "Mentor Status"
                tooltip: "Current stage of the mentor in the CBM program lifecycle."
                description: "Developer-facing PRD reference."
                options:
                  - Active
                  - Inactive
              - name: firstName
                type: varchar
                label: "First Name"
    """)
    path = tmp_path / "tooltip.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    # tooltip and description coexist independently
    field0 = program.entities[0].fields[0]
    assert field0.tooltip == "Current stage of the mentor in the CBM program lifecycle."
    assert field0.description == "Developer-facing PRD reference."
    # field without tooltip
    assert program.entities[0].fields[1].tooltip is None


def test_option_descriptions_parsed(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: mentorStatus
                type: enum
                label: "Mentor Status"
                options:
                  - Active
                  - Inactive
                optionDescriptions:
                  Active: "Fully qualified mentor."
                  Inactive: "No longer mentoring."
              - name: firstName
                type: varchar
                label: "First Name"
    """)
    path = tmp_path / "opt_desc.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    field0 = program.entities[0].fields[0]
    assert field0.optionDescriptions == {
        "Active": "Fully qualified mentor.",
        "Inactive": "No longer mentoring.",
    }
    assert program.entities[0].fields[1].optionDescriptions is None


def test_option_descriptions_valid_keys(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: status
                type: enum
                label: "Status"
                options:
                  - Active
                  - Inactive
                optionDescriptions:
                  Active: "Active description"
    """)
    path = tmp_path / "opt_desc_valid.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert not errors


def test_option_descriptions_invalid_key(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: status
                type: enum
                label: "Status"
                options:
                  - Active
                  - Inactive
                optionDescriptions:
                  Active: "Active description"
                  Bogus: "Not a real option"
    """)
    path = tmp_path / "opt_desc_bad_key.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("Bogus" in e and "does not match" in e for e in errors)


def test_option_descriptions_on_non_enum_field(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: firstName
                type: varchar
                label: "First Name"
                optionDescriptions:
                  Foo: "Bar"
    """)
    path = tmp_path / "opt_desc_non_enum.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("only valid on enum" in e for e in errors)


def test_option_descriptions_without_options_warns(loader, tmp_path, caplog):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: status
                type: enum
                label: "Status"
                optionDescriptions:
                  Active: "Active description"
    """)
    path = tmp_path / "opt_desc_no_opts.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    # Validation should produce an error for missing options (enum requires options)
    # but optionDescriptions itself should only warn, not error
    errors = loader.validate_program(program)
    # The enum-requires-options error fires
    assert any("non-empty 'options'" in e for e in errors)
    # But no error specifically about optionDescriptions — it logs a warning
    assert not any("optionDescriptions" in e for e in errors)


def test_panel_description_parsed(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
            layout:
              detail:
                panels:
                  - label: "General Info"
                    description: "Core contact information"
                    rows:
                      - [foo]
    """)
    path = tmp_path / "panel_desc.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    panel = program.entities[0].layouts["detail"].panels[0]
    assert panel.description == "Core contact information"


def test_entity_without_description_validates(loader, tmp_path):
    """Entity without description should pass validation (backward compatible)."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
    """)
    path = tmp_path / "no_entity_desc.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert errors == []
    assert program.entities[0].description is None


def test_field_without_description_validates(loader, tmp_path):
    """Field without description should pass validation (no warning)."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
    """)
    path = tmp_path / "no_field_desc.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert errors == []
    assert program.entities[0].fields[0].description is None


# --- Relationship tests ---


def test_load_relationships(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        relationships:
          - name: testRel
            entity: Session
            entityForeign: Engagement
            linkType: manyToOne
            link: sessionEngagement
            linkForeign: engagementSessions
            label: "Engagement"
            labelForeign: "Sessions"
            audited: false
    """)
    path = tmp_path / "rels.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    assert len(program.relationships) == 1
    rel = program.relationships[0]
    assert rel.name == "testRel"
    assert rel.entity == "Session"
    assert rel.entity_foreign == "Engagement"
    assert rel.link_type == "manyToOne"
    assert rel.action is None


def test_load_relationship_action_skip(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        relationships:
          - name: existingRel
            entity: Engagement
            entityForeign: Account
            linkType: manyToOne
            link: assignedEngagement
            linkForeign: cCompanyRequestionHelp
            label: "Company"
            labelForeign: "Engagements"
            action: skip
    """)
    path = tmp_path / "skip.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    assert program.relationships[0].action == "skip"
    errors = loader.validate_program(program)
    assert errors == []


def test_validate_relationship_invalid_link_type(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        relationships:
          - name: badRel
            entity: A
            entityForeign: B
            linkType: invalidType
            link: a
            linkForeign: b
            label: "A"
            labelForeign: "B"
    """)
    path = tmp_path / "bad_link.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("linkType" in e for e in errors)


def test_validate_relationship_many_to_many_needs_relation_name(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        relationships:
          - name: m2m
            entity: A
            entityForeign: B
            linkType: manyToMany
            link: bs
            linkForeign: as
            label: "Bs"
            labelForeign: "As"
    """)
    path = tmp_path / "m2m.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("relationName" in e for e in errors)


def test_validate_relationship_missing_required_fields(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        relationships:
          - name: ""
            entity: ""
            entityForeign: B
            linkType: oneToMany
            link: bs
            linkForeign: ""
            label: "Bs"
            labelForeign: "As"
    """)
    path = tmp_path / "missing.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("name" in e for e in errors)
    assert any("entity" in e and "missing" in e for e in errors)
    assert any("linkForeign" in e for e in errors)


def test_relationships_only_file_validates(loader, tmp_path):
    """A YAML file with only relationships (no entities) should validate."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        relationships:
          - name: testRel
            entity: A
            entityForeign: B
            linkType: oneToMany
            link: bs
            linkForeign: a
            label: "Bs"
            labelForeign: "A"
    """)
    path = tmp_path / "rels_only.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert errors == []


# --- Content version tests ---


def test_content_version_parsed(loader, tmp_path):
    """content_version is parsed correctly when present."""
    content = dedent("""\
        version: "1.0"
        content_version: "2.3.1"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
    """)
    path = tmp_path / "versioned.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    assert program.content_version == "2.3.1"


def test_content_version_defaults_when_absent(loader, tmp_path):
    """Default '1.0.0' is used when content_version is absent."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
    """)
    path = tmp_path / "no_cv.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    assert program.content_version == "1.0.0"


# --- v1.1 entity-level pass-through tests ---


def test_v11_entity_level_keys_stash_raw(loader, tmp_path):
    """v1.1 entity-level keys are stashed as raw values without validation."""
    content = dedent("""\
        version: "1.1"
        description: "Test v1.1"
        entities:
          Contact:
            settings:
              labelSingular: "Contact"
              labelPlural: "Contacts"
              stream: true
            duplicateChecks:
              - fields: [email]
                scope: Contact
            savedViews:
              - name: "Active Mentors"
                filter:
                  - { field: mentorStatus, op: equals, value: Active }
            emailTemplates:
              - name: "Welcome"
                subject: "Welcome!"
            workflows:
              - name: "Auto-assign"
                trigger: create
            fields:
              - name: foo
                type: varchar
                label: "Foo"
    """)
    path = tmp_path / "v11_entity.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    entity = program.entities[0]
    assert entity.settings_raw == {
        "labelSingular": "Contact",
        "labelPlural": "Contacts",
        "stream": True,
    }
    assert isinstance(entity.duplicate_checks_raw, list)
    assert len(entity.duplicate_checks_raw) == 1
    assert isinstance(entity.saved_views_raw, list)
    assert len(entity.saved_views_raw) == 1
    assert isinstance(entity.email_templates_raw, list)
    assert isinstance(entity.workflows_raw, list)


def test_v11_entity_level_keys_default_none(loader, valid_yaml):
    """v1.0 files without v1.1 keys default to None."""
    program = loader.load_program(valid_yaml)
    entity = program.entities[0]
    assert entity.settings_raw is None
    assert entity.duplicate_checks_raw is None
    assert entity.saved_views_raw is None
    assert entity.email_templates_raw is None
    assert entity.workflows_raw is None


# --- v1.1 field-level pass-through tests ---


def test_v11_field_level_keys_stash_raw(loader, tmp_path):
    """v1.1 field-level keys are stashed as raw values."""
    content = dedent("""\
        version: "1.1"
        description: "Test v1.1"
        entities:
          Contact:
            fields:
              - name: mentorStatus
                type: enum
                label: "Mentor Status"
                options:
                  - Active
                  - Inactive
                requiredWhen:
                  - { field: contactType, op: contains, value: Mentor }
                visibleWhen:
                  all:
                    - { field: contactType, op: contains, value: Mentor }
              - name: score
                type: int
                label: "Score"
                formula:
                  type: count
                  relatedEntity: Session
                externallyPopulated: true
    """)
    path = tmp_path / "v11_fields.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    f0 = program.entities[0].fields[0]
    assert isinstance(f0.required_when_raw, list)
    assert isinstance(f0.visible_when_raw, dict)
    f1 = program.entities[0].fields[1]
    assert isinstance(f1.formula_raw, dict)
    assert f1.externally_populated is True


def test_v11_field_level_keys_default(loader, valid_yaml):
    """Fields without v1.1 keys have safe defaults."""
    program = loader.load_program(valid_yaml)
    f = program.entities[0].fields[0]
    assert f.required_when_raw is None
    assert f.visible_when_raw is None
    assert f.formula_raw is None
    assert f.externally_populated is False


# --- Deprecation warning tests ---


def test_deprecated_entity_top_level_keys_warn(loader, tmp_path):
    """v1.0 top-level labelSingular/labelPlural/stream/disabled emit warnings."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Engagement:
            action: create
            type: Base
            labelSingular: "Engagement"
            labelPlural: "Engagements"
            stream: true
            disabled: false
            fields:
              - name: foo
                type: varchar
                label: "Foo"
    """)
    path = tmp_path / "deprecated_keys.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    # All four deprecated keys should produce warnings
    assert len(program.deprecation_warnings) == 4
    for key in ("labelSingular", "labelPlural", "stream", "disabled"):
        assert any(key in w for w in program.deprecation_warnings), (
            f"No deprecation warning for '{key}'"
        )
    # Values still populated for backward compatibility
    entity = program.entities[0]
    assert entity.labelSingular == "Engagement"
    assert entity.labelPlural == "Engagements"
    assert entity.stream is True
    assert entity.disabled is False


def test_v10_file_no_deprecation_warnings(loader, valid_yaml):
    """v1.0 files without the deprecated keys produce no warnings."""
    program = loader.load_program(valid_yaml)
    assert program.deprecation_warnings == []


def test_deprecated_dynamic_logic_visible_warns(loader, tmp_path):
    """Panel-level dynamicLogicVisible emits a deprecation warning."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
            layout:
              detail:
                panels:
                  - label: "Conditional"
                    dynamicLogicVisible:
                      conditionGroup:
                        - type: equals
                          attribute: contactType
                          value: Mentor
                    rows:
                      - [foo]
    """)
    path = tmp_path / "deprecated_dlv.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    assert any("dynamicLogicVisible" in w for w in program.deprecation_warnings)
    # Value still populated for backward compat
    panel = program.entities[0].layouts["detail"].panels[0]
    assert panel.dynamicLogicVisible is not None


def test_panel_visible_when_stashed(loader, tmp_path):
    """Panel-level visibleWhen is stashed on PanelSpec."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
            layout:
              detail:
                panels:
                  - label: "Mentor Info"
                    visibleWhen:
                      - { field: contactType, op: contains, value: Mentor }
                    rows:
                      - [foo]
    """)
    path = tmp_path / "panel_vw.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    panel = program.entities[0].layouts["detail"].panels[0]
    assert isinstance(panel.visible_when_raw, list)
    assert len(panel.visible_when_raw) == 1


def test_wysiwyg_field_type_supported(loader, tmp_path):
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: notes
                type: wysiwyg
                label: "Notes"
    """)
    path = tmp_path / "wysiwyg.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert errors == []


# --- ProgramContext / cross-file validation tests ---


def _write(tmp_path, name: str, body: str) -> Path:
    path: Path = tmp_path / name
    path.write_text(dedent(body))
    return path


def test_program_context_unions_fields_across_programs(loader, tmp_path):
    """ProgramContext.from_programs unions field names by entity."""
    from espo_impl.core.models import ProgramContext

    cr = _write(tmp_path, "CR-Account.yaml", """\
        version: "1.1"
        description: "CR domain — Account"
        entities:
          Account:
            fields:
              - name: accountType
                type: enum
                label: "Account Type"
                options:
                  - Client
                  - Prospect
    """)
    mn = _write(tmp_path, "MN-Account.yaml", """\
        version: "1.1"
        description: "MN domain — Account"
        entities:
          Account:
            fields:
              - name: organizationType
                type: enum
                label: "Organization Type"
                options:
                  - Nonprofit
                  - Forprofit
    """)
    p_cr = loader.load_program(cr)
    p_mn = loader.load_program(mn)
    context = ProgramContext.from_programs([p_cr, p_mn])
    names = context.field_names_for("Account")
    assert "accountType" in names
    assert "organizationType" in names
    # Unrelated entity is not present
    assert context.field_names_for("Contact") == frozenset()


def test_validate_program_with_context_resolves_cross_file_field_refs(
    loader, tmp_path,
):
    """A program can reference a field declared by a sibling YAML."""
    from espo_impl.core.models import ProgramContext

    cr = _write(tmp_path, "CR-Account.yaml", """\
        version: "1.1"
        description: "CR domain — Account"
        entities:
          Account:
            fields:
              - name: accountType
                type: enum
                label: "Account Type"
                options:
                  - Client
                  - Prospect
    """)
    mn = _write(tmp_path, "MN-Account.yaml", """\
        version: "1.1"
        description: "MN domain — Account"
        entities:
          Account:
            fields:
              - name: organizationType
                type: enum
                label: "Organization Type"
                options:
                  - Nonprofit
                  - Forprofit
                visibleWhen:
                  - { field: accountType, op: equals, value: Client }
    """)
    p_cr = loader.load_program(cr)
    p_mn = loader.load_program(mn)
    context = ProgramContext.from_programs([p_cr, p_mn])
    errors = loader.validate_program_with_context(p_mn, context)
    assert not any("accountType" in e for e in errors), (
        f"Unexpected accountType error in: {errors}"
    )


def test_validate_program_without_context_uses_single_file_fallback(
    loader, tmp_path,
):
    """validate_program(program) builds a single-program context."""
    path = _write(tmp_path, "self_consistent.yaml", """\
        version: "1.1"
        description: "Self-consistent"
        entities:
          Contact:
            fields:
              - name: contactType
                type: enum
                label: "Contact Type"
                options:
                  - Mentor
                  - Client
              - name: mentorStatus
                type: enum
                label: "Mentor Status"
                options:
                  - Active
                  - Inactive
                visibleWhen:
                  - { field: contactType, op: equals, value: Mentor }
    """)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert errors == [], f"Expected no errors but got: {errors}"


def test_validate_program_without_context_surfaces_typo_as_warning(
    loader, tmp_path,
):
    """Unresolved field references — including typos — surface as
    deferred-condition warnings rather than hard errors. This is the
    explicit tradeoff for letting circular references resolve over
    multiple runs: an unresolved name might be a typo, or it might be
    a forward reference to a field the author plans to add. The
    operator reviews the warning log to catch typos.
    """
    path = _write(tmp_path, "typo.yaml", """\
        version: "1.1"
        description: "Has a typo"
        entities:
          Contact:
            fields:
              - name: contactType
                type: enum
                label: "Contact Type"
                options:
                  - Mentor
                  - Client
              - name: mentorStatus
                type: enum
                label: "Mentor Status"
                options:
                  - Active
                  - Inactive
                visibleWhen:
                  - { field: contctType, op: equals, value: Mentor }
    """)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert errors == [], f"Expected no errors but got: {errors}"
    assert any(
        "contctType" in w and "deferred" in w
        for w in program.condition_warnings
    ), f"Expected deferral warning but got: {program.condition_warnings}"


def test_validate_program_with_context_surfaces_typo_as_warning(
    loader, tmp_path,
):
    """Same as the single-file case but with a multi-file batch:
    unresolved references in a sibling YAML surface as warnings, not
    errors.
    """
    from espo_impl.core.models import ProgramContext

    cr = _write(tmp_path, "CR-Account.yaml", """\
        version: "1.1"
        description: "CR — Account"
        entities:
          Account:
            fields:
              - name: accountType
                type: enum
                label: "Account Type"
                options:
                  - Client
                  - Prospect
    """)
    mn = _write(tmp_path, "MN-Account.yaml", """\
        version: "1.1"
        description: "MN — Account"
        entities:
          Account:
            fields:
              - name: organizationType
                type: enum
                label: "Organization Type"
                options:
                  - Nonprofit
                  - Forprofit
                visibleWhen:
                  - { field: acountType, op: equals, value: Client }
    """)
    p_cr = loader.load_program(cr)
    p_mn = loader.load_program(mn)
    context = ProgramContext.from_programs([p_cr, p_mn])
    errors = loader.validate_program_with_context(p_mn, context)
    assert errors == [], f"Expected no errors but got: {errors}"
    assert any(
        "acountType" in w and "deferred" in w
        for w in p_mn.condition_warnings
    ), f"Expected deferral warning but got: {p_mn.condition_warnings}"


# --- Native-field resolution tests (validator awareness of EspoCRM
# system fields and base-type natives) ---


def test_validate_program_resolves_native_system_fields(loader, tmp_path):
    """A savedView referencing createdAt and modifiedAt validates
    cleanly — those are universal system fields on every entity.
    """
    path = _write(tmp_path, "engagement_system_fields.yaml", """\
        version: "1.1"
        description: "Engagement with system-field references"
        entities:
          Engagement:
            type: Base
            action: create
            labelSingular: "Engagement"
            labelPlural: "Engagements"
            fields:
              - name: status
                type: enum
                label: "Status"
                options:
                  - Active
                  - Closed
            savedViews:
              - id: engagement-recent
                name: "Recent Engagements"
                filter:
                  - { field: status, op: equals, value: Active }
                columns: [name, createdAt, modifiedAt]
                orderBy:
                  field: modifiedAt
                  direction: desc
    """)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert not any("createdAt" in e for e in errors), (
        f"Unexpected createdAt error in: {errors}"
    )
    assert not any("modifiedAt" in e for e in errors), (
        f"Unexpected modifiedAt error in: {errors}"
    )


def test_validate_program_resolves_native_base_fields(loader, tmp_path):
    """A savedView on a Base-type custom entity referencing the
    native 'name' and 'description' fields validates cleanly.
    """
    path = _write(tmp_path, "engagement_base_natives.yaml", """\
        version: "1.1"
        description: "Engagement with Base native references"
        entities:
          Engagement:
            type: Base
            action: create
            labelSingular: "Engagement"
            labelPlural: "Engagements"
            fields:
              - name: status
                type: enum
                label: "Status"
                options:
                  - Active
                  - Closed
            savedViews:
              - id: engagement-active
                name: "Active Engagements"
                filter:
                  - { field: status, op: equals, value: Active }
                columns: [name, description]
    """)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert not any(
        "field 'name' not found" in e or "field 'description' not found" in e
        for e in errors
    ), f"Unexpected name/description error in: {errors}"


def test_validate_program_resolves_native_company_fields_for_account(
    loader, tmp_path,
):
    """A duplicateCheck on the native Account entity referencing the
    native 'website' field validates cleanly.
    """
    path = _write(tmp_path, "account_website.yaml", """\
        version: "1.1"
        description: "Account duplicate check on website"
        entities:
          Account:
            duplicateChecks:
              - id: account-website
                fields: [website]
                onMatch: warn
    """)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert not any("website" in e for e in errors), (
        f"Unexpected website error in: {errors}"
    )


def test_validate_program_resolves_native_person_fields_for_contact(
    loader, tmp_path,
):
    """A savedView on the native Contact entity referencing the native
    'firstName' and 'emailAddress' fields validates cleanly.
    """
    path = _write(tmp_path, "contact_person_natives.yaml", """\
        version: "1.1"
        description: "Contact saved view on person natives"
        entities:
          Contact:
            fields:
              - name: contactType
                type: enum
                label: "Contact Type"
                options:
                  - Mentor
                  - Client
            savedViews:
              - id: contact-mentors
                name: "Mentors"
                filter:
                  - { field: contactType, op: equals, value: Mentor }
                columns: [firstName, lastName, emailAddress]
    """)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert not any("firstName" in e for e in errors), (
        f"Unexpected firstName error in: {errors}"
    )
    assert not any("lastName" in e for e in errors), (
        f"Unexpected lastName error in: {errors}"
    )
    assert not any("emailAddress" in e for e in errors), (
        f"Unexpected emailAddress error in: {errors}"
    )


def test_validate_program_still_catches_typo_on_native_field(
    loader, tmp_path,
):
    """Misspelled native references are still flagged — adding the
    native-field catalog does not weaken typo detection.
    """
    path = _write(tmp_path, "engagement_typo.yaml", """\
        version: "1.1"
        description: "Engagement with native-field typo"
        entities:
          Engagement:
            type: Base
            action: create
            labelSingular: "Engagement"
            labelPlural: "Engagements"
            fields:
              - name: status
                type: enum
                label: "Status"
                options:
                  - Active
                  - Closed
            savedViews:
              - id: engagement-recent
                name: "Recent Engagements"
                filter:
                  - { field: status, op: equals, value: Active }
                columns: [name, creatdAt]
    """)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("creatdAt" in e for e in errors), (
        f"Expected typo error but got: {errors}"
    )


def test_validate_foreign_field_accepts_link_and_field(loader, tmp_path):
    """A `type: foreign` field with both `link` and `field` validates clean."""
    path = _write(tmp_path, "foreign_ok.yaml", """\
        version: "1.0"
        description: "Foreign field smoke test"
        entities:
          Account:
            fields:
              - name: partnerName
                type: foreign
                label: "Partner"
                link: partner
                field: name
    """)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    foreign_errors = [
        e for e in errors
        if "Account.partnerName" in e and ("foreign" in e or "'link'" in e
            or "'field'" in e)
    ]
    assert foreign_errors == [], (
        f"Expected no foreign-specific errors, got: {foreign_errors!r}"
    )
    # Field is parsed onto the typed model
    field_def = program.entities[0].fields[0]
    assert field_def.type == "foreign"
    assert field_def.link == "partner"
    assert field_def.foreign_field == "name"


def test_validate_foreign_field_requires_link(loader, tmp_path):
    path = _write(tmp_path, "foreign_no_link.yaml", """\
        version: "1.0"
        description: "Foreign missing link"
        entities:
          Account:
            fields:
              - name: partnerName
                type: foreign
                label: "Partner"
                field: name
    """)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any(
        "Account.partnerName" in e and "foreign fields require 'link'" in e
        for e in errors
    ), f"Expected missing-link error, got: {errors!r}"


def test_validate_foreign_field_requires_field(loader, tmp_path):
    path = _write(tmp_path, "foreign_no_field.yaml", """\
        version: "1.0"
        description: "Foreign missing field"
        entities:
          Account:
            fields:
              - name: partnerName
                type: foreign
                label: "Partner"
                link: partner
    """)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any(
        "Account.partnerName" in e and "foreign fields require 'field'" in e
        for e in errors
    ), f"Expected missing-field error, got: {errors!r}"


def test_validate_foreign_field_rejects_required_true(loader, tmp_path):
    path = _write(tmp_path, "foreign_required.yaml", """\
        version: "1.0"
        description: "Foreign with required:true is rejected"
        entities:
          Account:
            fields:
              - name: partnerName
                type: foreign
                label: "Partner"
                link: partner
                field: name
                required: true
    """)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any(
        "Account.partnerName" in e and "read-only mirrors" in e
        for e in errors
    ), f"Expected read-only-mirror error, got: {errors!r}"


def test_validate_link_field_only_on_foreign_type(loader, tmp_path):
    """`link:`/`field:` on a non-foreign field is rejected."""
    path = _write(tmp_path, "link_on_varchar.yaml", """\
        version: "1.0"
        description: "link on a varchar field"
        entities:
          Account:
            fields:
              - name: notes
                type: varchar
                label: "Notes"
                link: partner
                field: name
    """)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any(
        "Account.notes" in e
        and "'link' and 'field' are only valid on 'type: foreign'" in e
        for e in errors
    ), f"Expected link-on-non-foreign error, got: {errors!r}"

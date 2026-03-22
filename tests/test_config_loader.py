"""Tests for YAML config loading and validation."""

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

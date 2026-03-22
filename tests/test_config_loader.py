"""Tests for YAML config loading and validation."""

from textwrap import dedent

import pytest

from espo_impl.core.config_loader import ConfigLoader


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

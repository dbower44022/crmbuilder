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

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


def test_validate_tab_category_resolves_same_file(loader, tmp_path):
    """Layout category reference resolves to a field category declared
    in the same YAML file (legacy single-file case). PI-019.
    """
    content = dedent("""\
        version: "1.1"
        description: "Same-file category"
        entities:
          Contact:
            fields:
              - name: sponsorName
                type: varchar
                label: "Sponsor Name"
                category: "Sponsor Profile"
            layout:
              detail:
                panels:
                  - label: "Panel"
                    tabs:
                      - label: "Sponsor"
                        category: "Sponsor Profile"
    """)
    path = tmp_path / "same_file_cat.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert not any("Sponsor Profile" in e for e in errors), (
        f"Unexpected category error in: {errors}"
    )


def test_validate_tab_category_resolves_cross_file(loader, tmp_path):
    """Layout category reference in YAML A resolves to a field category
    declared in YAML B when both are in the same deploy batch via
    ProgramContext. PI-019.
    """
    from espo_impl.core.models import ProgramContext

    a = _write(tmp_path, "MN-Sponsor.yaml", """\
        version: "1.1"
        description: "MN domain — sponsor fields"
        entities:
          Account:
            fields:
              - name: sponsorTier
                type: enum
                label: "Sponsor Tier"
                category: "Sponsor Profile"
                options:
                  - Gold
                  - Silver
              - name: sponsorContact
                type: varchar
                label: "Sponsor Contact"
                category: "Sponsor Profile"
    """)
    b = _write(tmp_path, "MN-Account.yaml", """\
        version: "1.1"
        description: "MN domain — Account layout"
        entities:
          Account:
            fields:
              - name: accountSegment
                type: varchar
                label: "Account Segment"
            layout:
              detail:
                panels:
                  - label: "Sponsorship"
                    tabs:
                      - label: "Sponsor"
                        category: "Sponsor Profile"
    """)
    p_a = loader.load_program(a)
    p_b = loader.load_program(b)
    context = ProgramContext.from_programs([p_a, p_b])
    errors = loader.validate_program_with_context(p_b, context)
    assert not any("Sponsor Profile" in e for e in errors), (
        f"Unexpected cross-file category error in: {errors}"
    )


def test_validate_tab_category_unknown_in_batch_still_errors(
    loader, tmp_path,
):
    """Layout category reference still fails with the existing
    'not found' error when no YAML in the deploy batch declares
    that category on the entity. PI-019.
    """
    from espo_impl.core.models import ProgramContext

    a = _write(tmp_path, "MN-Sponsor.yaml", """\
        version: "1.1"
        description: "MN domain — sponsor fields"
        entities:
          Account:
            fields:
              - name: sponsorTier
                type: enum
                label: "Sponsor Tier"
                category: "Sponsor Profile"
                options:
                  - Gold
                  - Silver
    """)
    b = _write(tmp_path, "MN-Account.yaml", """\
        version: "1.1"
        description: "MN domain — Account layout"
        entities:
          Account:
            fields:
              - name: accountSegment
                type: varchar
                label: "Account Segment"
            layout:
              detail:
                panels:
                  - label: "Donor"
                    tabs:
                      - label: "Donor"
                        category: "Donor Profile"
    """)
    p_a = loader.load_program(a)
    p_b = loader.load_program(b)
    context = ProgramContext.from_programs([p_a, p_b])
    errors = loader.validate_program_with_context(p_b, context)
    assert any(
        "Donor Profile" in e and "not found" in e for e in errors
    ), f"Expected category not-found error in: {errors}"


def test_program_context_categories_for_entity(loader, tmp_path):
    """ProgramContext.field_categories_for unions categories across
    sibling YAMLs by entity. PI-019.
    """
    from espo_impl.core.models import ProgramContext

    a = _write(tmp_path, "A.yaml", """\
        version: "1.1"
        description: "A"
        entities:
          Account:
            fields:
              - name: sponsorTier
                type: varchar
                label: "Sponsor Tier"
                category: "Sponsor Profile"
    """)
    b = _write(tmp_path, "B.yaml", """\
        version: "1.1"
        description: "B"
        entities:
          Account:
            fields:
              - name: donorTier
                type: varchar
                label: "Donor Tier"
                category: "Donor Profile"
    """)
    p_a = loader.load_program(a)
    p_b = loader.load_program(b)
    context = ProgramContext.from_programs([p_a, p_b])
    cats = context.field_categories_for("Account")
    assert "Sponsor Profile" in cats
    assert "Donor Profile" in cats
    assert context.field_categories_for("Contact") == frozenset()


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


def test_validate_relationship_one_to_one_accepted(loader, tmp_path):
    """A well-formed oneToOne relationship validates without errors.

    PI-018: oneToOne joined the set of valid linkTypes alongside
    oneToMany, manyToOne, and manyToMany. EspoCRM's createLink API
    accepts it natively; the engine no longer needs the workaround
    of declaring such relationships as manyToOne plus an operator-
    discipline uniqueness rule.
    """
    content = dedent("""\
        version: "1.0"
        description: "Test"
        relationships:
          - name: accountPartnerProfile
            entity: Account
            entityForeign: PartnerProfile
            linkType: oneToOne
            link: partnerProfile
            linkForeign: account
            label: "Partner Profile"
            labelForeign: "Account"
    """)
    path = tmp_path / "one_to_one.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert errors == []


def test_validate_relationship_one_to_one_missing_link_foreign(
    loader, tmp_path
):
    """oneToOne without linkForeign is a hard-reject error."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        relationships:
          - name: badOneToOne
            entity: Account
            entityForeign: PartnerProfile
            linkType: oneToOne
            link: partnerProfile
            linkForeign: ""
            label: "Partner Profile"
            labelForeign: "Account"
    """)
    path = tmp_path / "bad_one_to_one.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("linkForeign" in e for e in errors)
    # The oneToOne-specific diagnostic surfaces the relationship type
    # explicitly so the operator does not just see the generic missing-
    # required-property message.
    assert any(
        "linkForeign" in e and "oneToOne" in e for e in errors
    )


def test_validate_relationship_one_to_one_with_relation_name_warns(
    loader, tmp_path
):
    """oneToOne + relationName is a soft warning, not a hard error.

    ``relationName`` is a manyToMany affordance (junction-table name)
    with no meaning for a 1:1 link. The file still validates; the
    warning surfaces through ``program.condition_warnings`` so the
    operator sees the diagnostic without losing the deployment.
    """
    content = dedent("""\
        version: "1.0"
        description: "Test"
        relationships:
          - name: oddOneToOne
            entity: Account
            entityForeign: PartnerProfile
            linkType: oneToOne
            link: partnerProfile
            linkForeign: account
            label: "Partner Profile"
            labelForeign: "Account"
            relationName: accountPartner
    """)
    path = tmp_path / "warn_one_to_one.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert errors == []
    assert any(
        "relationName" in w and "oneToOne" in w
        for w in program.condition_warnings
    )


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


# ----------------------------------------------------------------------
# audit-v1.2 Prompt A — top-level roles: and teams: loader recognition
# ----------------------------------------------------------------------


def test_load_roles_block_basic(loader, tmp_path):
    """A valid roles: block populates ProgramFile.roles."""
    path = _write(tmp_path, "roles_basic.yaml", """\
        version: "1.0"
        description: "Roles only"
        roles:
          - name: Mentor
            description: "Volunteer who delivers sessions to mentees."
            persona: MST-PER-005
          - name: StaffMember
    """)
    program = loader.load_program(path)
    assert len(program.roles) == 2
    mentor, staff = program.roles
    assert mentor.name == "Mentor"
    assert mentor.description == (
        "Volunteer who delivers sessions to mentees."
    )
    assert mentor.persona == "MST-PER-005"
    assert mentor.scope_access_raw is None
    assert mentor.system_permissions_raw is None
    assert staff.name == "StaffMember"
    assert staff.description is None
    assert staff.persona is None
    assert staff.scope_access_raw is None
    assert staff.system_permissions_raw is None


def test_load_teams_block_basic(loader, tmp_path):
    """A valid teams: block populates ProgramFile.teams."""
    path = _write(tmp_path, "teams_basic.yaml", """\
        version: "1.0"
        description: "Teams only"
        teams:
          - name: NortheastOhio
            description: "Geographic team for the NEO region."
          - name: Operations
    """)
    program = loader.load_program(path)
    assert len(program.teams) == 2
    neo, ops = program.teams
    assert neo.name == "NortheastOhio"
    assert neo.description == "Geographic team for the NEO region."
    assert ops.name == "Operations"
    assert ops.description is None


def test_load_roles_teams_with_entities(loader, tmp_path):
    """roles: and teams: alongside entities: parse independently."""
    path = _write(tmp_path, "all_three.yaml", """\
        version: "1.0"
        description: "Roles + teams + entities"
        entities:
          Contact:
            fields:
              - name: nickname
                type: varchar
                label: "Nickname"
        roles:
          - name: Admin
        teams:
          - name: HQ
    """)
    program = loader.load_program(path)
    assert len(program.entities) == 1
    assert program.entities[0].name == "Contact"
    assert program.entities[0].fields[0].name == "nickname"
    assert len(program.roles) == 1
    assert program.roles[0].name == "Admin"
    assert len(program.teams) == 1
    assert program.teams[0].name == "HQ"


def test_load_program_without_roles_or_teams(loader, valid_yaml):
    """Programs without roles:/teams: still load cleanly with empty lists."""
    program = loader.load_program(valid_yaml)
    assert program.roles == []
    assert program.teams == []


def test_load_role_with_raw_scope_and_permissions(loader, tmp_path):
    """scope_access and system_permissions are stashed as raw dicts
    alongside the structured fields populated by Prompt B."""
    path = _write(tmp_path, "role_with_raw.yaml", """\
        version: "1.0"
        description: "Role with raw blocks"
        roles:
          - name: Mentor
            scope_access:
              Engagement:
                read: own
              Contact:
                read: team
                edit: own
            system_permissions:
              mass_update: no
              export: yes
    """)
    program = loader.load_program(path)
    assert len(program.roles) == 1
    mentor = program.roles[0]
    assert mentor.scope_access_raw == {
        "Engagement": {"read": "own"},
        "Contact": {"read": "team", "edit": "own"},
    }
    assert mentor.system_permissions_raw == {
        "mass_update": False,
        "export": True,
    }


def test_roles_teams_load_from_security_subdir(loader, tmp_path):
    """A YAML under security/ loads identically to one at the root.

    Locks in the DEC-182 convention that security YAMLs live in
    a ``security/`` subdirectory of the program directory. The
    recursive scan in deployment_logic picks them up unchanged;
    this test guards equivalence at the loader level.
    """
    body = """\
        version: "1.0"
        description: "Shared security content"
        roles:
          - name: Mentor
            persona: MST-PER-005
          - name: Admin
        teams:
          - name: HQ
          - name: Field
    """
    root_path = _write(tmp_path, "security.yaml", body)
    security_dir = tmp_path / "security"
    security_dir.mkdir()
    subdir_path = security_dir / "security.yaml"
    subdir_path.write_text(dedent(body))

    root_program = loader.load_program(root_path)
    subdir_program = loader.load_program(subdir_path)

    assert [r.name for r in root_program.roles] == [
        r.name for r in subdir_program.roles
    ]
    assert [r.persona for r in root_program.roles] == [
        r.persona for r in subdir_program.roles
    ]
    assert [t.name for t in root_program.teams] == [
        t.name for t in subdir_program.teams
    ]
    assert root_program.version == subdir_program.version
    assert root_program.description == subdir_program.description


# ---- Rejection cases: roles ----


def test_roles_top_level_must_be_list(loader, tmp_path):
    path = _write(tmp_path, "roles_not_list.yaml", """\
        version: "1.0"
        description: "Bad roles"
        roles:
          Mentor:
            description: "A mapping at the top, not a list"
    """)
    with pytest.raises(ValueError, match="'roles' must be a list"):
        loader.load_program(path)


def test_role_entry_must_be_mapping(loader, tmp_path):
    path = _write(tmp_path, "role_entry_scalar.yaml", """\
        version: "1.0"
        description: "Role entry scalar"
        roles:
          - Mentor
    """)
    with pytest.raises(ValueError, match=r"roles\[0\] must be a mapping"):
        loader.load_program(path)


def test_role_missing_name(loader, tmp_path):
    path = _write(tmp_path, "role_no_name.yaml", """\
        version: "1.0"
        description: "Role missing name"
        roles:
          - description: "No name here"
    """)
    with pytest.raises(
        ValueError,
        match=r"roles\[0\] is missing a non-empty string 'name'",
    ):
        loader.load_program(path)


def test_role_name_empty_string(loader, tmp_path):
    path = _write(tmp_path, "role_empty_name.yaml", """\
        version: "1.0"
        description: "Role empty name"
        roles:
          - name: ""
    """)
    with pytest.raises(
        ValueError,
        match=r"roles\[0\] is missing a non-empty string 'name'",
    ):
        loader.load_program(path)


def test_role_name_non_string(loader, tmp_path):
    path = _write(tmp_path, "role_int_name.yaml", """\
        version: "1.0"
        description: "Role int name"
        roles:
          - name: 42
    """)
    with pytest.raises(
        ValueError,
        match=r"roles\[0\] is missing a non-empty string 'name'",
    ):
        loader.load_program(path)


def test_role_description_non_string(loader, tmp_path):
    path = _write(tmp_path, "role_bad_desc.yaml", """\
        version: "1.0"
        description: "Role bad description"
        roles:
          - name: Mentor
            description: 99
    """)
    with pytest.raises(
        ValueError,
        match=r"roles\[0\] \('Mentor'\): 'description' must be a string",
    ):
        loader.load_program(path)


def test_role_persona_non_string(loader, tmp_path):
    path = _write(tmp_path, "role_bad_persona.yaml", """\
        version: "1.0"
        description: "Role bad persona"
        roles:
          - name: Mentor
            persona: 7
    """)
    with pytest.raises(
        ValueError,
        match=r"roles\[0\] \('Mentor'\): 'persona' must be a string",
    ):
        loader.load_program(path)


def test_role_scope_access_must_be_mapping(loader, tmp_path):
    path = _write(tmp_path, "role_bad_scope.yaml", """\
        version: "1.0"
        description: "Role bad scope_access"
        roles:
          - name: Mentor
            scope_access:
              - Engagement
              - Contact
    """)
    with pytest.raises(
        ValueError,
        match=r"roles\[0\] \('Mentor'\): 'scope_access' must be a mapping",
    ):
        loader.load_program(path)


def test_role_system_permissions_must_be_mapping(loader, tmp_path):
    path = _write(tmp_path, "role_bad_sysperm.yaml", """\
        version: "1.0"
        description: "Role bad system_permissions"
        roles:
          - name: Mentor
            system_permissions: "all"
    """)
    with pytest.raises(
        ValueError,
        match=(
            r"roles\[0\] \('Mentor'\): 'system_permissions' must be a "
            r"mapping"
        ),
    ):
        loader.load_program(path)


# ---- Rejection cases: teams ----


def test_teams_top_level_must_be_list(loader, tmp_path):
    path = _write(tmp_path, "teams_not_list.yaml", """\
        version: "1.0"
        description: "Bad teams"
        teams:
          HQ:
            description: "A mapping at the top, not a list"
    """)
    with pytest.raises(ValueError, match="'teams' must be a list"):
        loader.load_program(path)


def test_team_entry_must_be_mapping(loader, tmp_path):
    path = _write(tmp_path, "team_entry_scalar.yaml", """\
        version: "1.0"
        description: "Team entry scalar"
        teams:
          - HQ
    """)
    with pytest.raises(ValueError, match=r"teams\[0\] must be a mapping"):
        loader.load_program(path)


def test_team_missing_name(loader, tmp_path):
    path = _write(tmp_path, "team_no_name.yaml", """\
        version: "1.0"
        description: "Team missing name"
        teams:
          - description: "No name here"
    """)
    with pytest.raises(
        ValueError,
        match=r"teams\[0\] is missing a non-empty string 'name'",
    ):
        loader.load_program(path)


def test_team_name_empty_string(loader, tmp_path):
    path = _write(tmp_path, "team_empty_name.yaml", """\
        version: "1.0"
        description: "Team empty name"
        teams:
          - name: ""
    """)
    with pytest.raises(
        ValueError,
        match=r"teams\[0\] is missing a non-empty string 'name'",
    ):
        loader.load_program(path)


def test_team_description_non_string(loader, tmp_path):
    path = _write(tmp_path, "team_bad_desc.yaml", """\
        version: "1.0"
        description: "Team bad description"
        teams:
          - name: HQ
            description: 123
    """)
    with pytest.raises(
        ValueError,
        match=r"teams\[0\] \('HQ'\): 'description' must be a string",
    ):
        loader.load_program(path)


# ----------------------------------------------------------------------
# audit-v1.2 Prompt B — structured scope_access / system_permissions
# parsing, validation, entity-name resolution, cross-batch uniqueness
# ----------------------------------------------------------------------


# ---- Structured scope_access parsing ----


def test_scope_access_structured_two_entities(loader, tmp_path):
    """scope_access populates a structured dict alongside the raw pass."""
    path = _write(tmp_path, "scope_two.yaml", """\
        version: "1.0"
        description: "Two-entity scope"
        entities:
          Engagement:
            fields:
              - name: status
                type: varchar
                label: "Status"
        roles:
          - name: Mentor
            scope_access:
              Engagement:
                create: yes
                read:   own
                edit:   own
                delete: no
                stream: own
              Contact:
                read:   team
                edit:   no
    """)
    program = loader.load_program(path)
    mentor = program.roles[0]
    assert set(mentor.scope_access.keys()) == {"Engagement", "Contact"}

    eng = mentor.scope_access["Engagement"]
    assert eng.create is True
    assert eng.read == "own"
    assert eng.edit == "own"
    assert eng.delete == "no"
    assert eng.stream == "own"

    contact = mentor.scope_access["Contact"]
    assert contact.create is False
    assert contact.read == "team"
    assert contact.edit == "no"
    assert contact.delete == "no"
    assert contact.stream == "no"

    # Raw passthrough must remain populated (Prompt A regression).
    assert mentor.scope_access_raw == {
        "Engagement": {
            "create": True,
            "read": "own",
            "edit": "own",
            "delete": False,
            "stream": "own",
        },
        "Contact": {"read": "team", "edit": False},
    }


def test_scope_access_partial_actions_default_denied(loader, tmp_path):
    """Omitted actions take dataclass defaults (denied)."""
    path = _write(tmp_path, "scope_partial.yaml", """\
        version: "1.0"
        description: "Partial scope"
        roles:
          - name: Mentor
            scope_access:
              Contact:
                read: own
                edit: own
    """)
    program = loader.load_program(path)
    contact = program.roles[0].scope_access["Contact"]
    assert contact.create is False
    assert contact.read == "own"
    assert contact.edit == "own"
    assert contact.delete == "no"
    assert contact.stream == "no"


def test_scope_access_empty_block_yields_empty_dict(loader, tmp_path):
    path = _write(tmp_path, "scope_empty.yaml", """\
        version: "1.0"
        description: "Empty scope"
        roles:
          - name: Mentor
            scope_access: {}
    """)
    program = loader.load_program(path)
    assert program.roles[0].scope_access == {}


def test_scope_access_absent_yields_empty_dict(loader, tmp_path):
    path = _write(tmp_path, "scope_absent.yaml", """\
        version: "1.0"
        description: "Absent scope"
        roles:
          - name: Mentor
    """)
    program = loader.load_program(path)
    assert program.roles[0].scope_access == {}


# ---- YAML 1.1 boolean coercion ----


def test_create_bare_yes_no(loader, tmp_path):
    path = _write(tmp_path, "create_bare.yaml", """\
        version: "1.0"
        description: "Bare yes/no for create"
        roles:
          - name: Mentor
            scope_access:
              Contact:
                create: yes
              Account:
                create: no
    """)
    program = loader.load_program(path)
    mentor = program.roles[0]
    assert mentor.scope_access["Contact"].create is True
    assert mentor.scope_access["Account"].create is False


def test_create_quoted_yes_no(loader, tmp_path):
    path = _write(tmp_path, "create_quoted.yaml", """\
        version: "1.0"
        description: "Quoted yes/no for create"
        roles:
          - name: Mentor
            scope_access:
              Contact:
                create: "yes"
              Account:
                create: "no"
    """)
    program = loader.load_program(path)
    mentor = program.roles[0]
    assert mentor.scope_access["Contact"].create is True
    assert mentor.scope_access["Account"].create is False


def test_read_bare_no_normalizes_to_string_no(loader, tmp_path):
    """Bare ``no`` (YAML False) normalizes to scope 'no'."""
    path = _write(tmp_path, "read_bare_no.yaml", """\
        version: "1.0"
        description: "Bare no for read"
        roles:
          - name: Mentor
            scope_access:
              Contact:
                read: no
    """)
    program = loader.load_program(path)
    assert program.roles[0].scope_access["Contact"].read == "no"


def test_read_quoted_no_normalizes_to_string_no(loader, tmp_path):
    path = _write(tmp_path, "read_quoted_no.yaml", """\
        version: "1.0"
        description: "Quoted no for read"
        roles:
          - name: Mentor
            scope_access:
              Contact:
                read: "no"
    """)
    program = loader.load_program(path)
    assert program.roles[0].scope_access["Contact"].read == "no"


@pytest.mark.parametrize(
    "action",
    ["read", "edit", "delete", "stream"],
)
def test_scope_actions_bare_vs_quoted_equivalence(
    loader, tmp_path, action,
):
    """Bare and quoted scope values produce identical results."""
    bare_path = _write(tmp_path, f"{action}_bare.yaml", f"""\
        version: "1.0"
        description: "Bare {action}"
        roles:
          - name: Mentor
            scope_access:
              Contact:
                {action}: no
    """)
    quoted_path = _write(tmp_path, f"{action}_quoted.yaml", f"""\
        version: "1.0"
        description: "Quoted {action}"
        roles:
          - name: Mentor
            scope_access:
              Contact:
                {action}: "no"
    """)
    bare_program = loader.load_program(bare_path)
    quoted_program = loader.load_program(quoted_path)
    assert (
        getattr(bare_program.roles[0].scope_access["Contact"], action)
        == getattr(
            quoted_program.roles[0].scope_access["Contact"],
            action,
        )
        == "no"
    )


# ---- scope_access rejection ----


def test_create_invalid_value_rejected(loader, tmp_path):
    path = _write(tmp_path, "create_bad.yaml", """\
        version: "1.0"
        description: "Bad create value"
        roles:
          - name: Mentor
            scope_access:
              Contact:
                create: maybe
    """)
    with pytest.raises(
        ValueError,
        match=(
            r"roles \('Mentor'\)\.scope_access\.Contact\.create: must "
            r"be 'yes' or 'no'"
        ),
    ):
        loader.load_program(path)


def test_read_yes_rejected_not_in_scope_vocabulary(loader, tmp_path):
    """``yes`` is not in the scope vocabulary."""
    path = _write(tmp_path, "read_yes.yaml", """\
        version: "1.0"
        description: "yes is not a scope value"
        roles:
          - name: Mentor
            scope_access:
              Contact:
                read: yes
    """)
    with pytest.raises(
        ValueError,
        match=(
            r"roles \('Mentor'\)\.scope_access\.Contact\.read: must "
            r"be one of 'all', 'team', 'own', 'no'"
        ),
    ):
        loader.load_program(path)


def test_read_unknown_string_rejected(loader, tmp_path):
    path = _write(tmp_path, "read_bad.yaml", """\
        version: "1.0"
        description: "Unknown scope"
        roles:
          - name: Mentor
            scope_access:
              Contact:
                read: somewhere
    """)
    with pytest.raises(
        ValueError,
        match=(
            r"roles \('Mentor'\)\.scope_access\.Contact\.read: must "
            r"be one of"
        ),
    ):
        loader.load_program(path)


def test_unknown_action_key_rejected(loader, tmp_path):
    path = _write(tmp_path, "unknown_action.yaml", """\
        version: "1.0"
        description: "Unknown action key"
        roles:
          - name: Mentor
            scope_access:
              Contact:
                archive: yes
    """)
    with pytest.raises(
        ValueError,
        match=(
            r"roles \('Mentor'\)\.scope_access\.Contact: unknown "
            r"action\(s\) \['archive'\]"
        ),
    ):
        loader.load_program(path)


def test_per_entity_block_not_mapping_rejected(loader, tmp_path):
    path = _write(tmp_path, "entity_block_scalar.yaml", """\
        version: "1.0"
        description: "Per-entity not a mapping"
        roles:
          - name: Mentor
            scope_access:
              Contact: own
    """)
    with pytest.raises(
        ValueError,
        match=(
            r"roles \('Mentor'\)\.scope_access\.Contact: must be a "
            r"mapping"
        ),
    ):
        loader.load_program(path)


# ---- system_permissions parsing ----


def test_system_permissions_full_block(loader, tmp_path):
    path = _write(tmp_path, "sysperm_full.yaml", """\
        version: "1.0"
        description: "Full system permissions"
        roles:
          - name: Admin
            system_permissions:
              assignment_permission: all
              user_permission: all
              export: yes
              mass_update: yes
              portal: no
    """)
    program = loader.load_program(path)
    perms = program.roles[0].system_permissions
    assert perms is not None
    assert perms.assignment_permission == "all"
    assert perms.user_permission == "all"
    assert perms.export is True
    assert perms.mass_update is True
    assert perms.portal is False


def test_system_permissions_partial_block(loader, tmp_path):
    path = _write(tmp_path, "sysperm_partial.yaml", """\
        version: "1.0"
        description: "Partial system permissions"
        roles:
          - name: Operator
            system_permissions:
              export: yes
    """)
    program = loader.load_program(path)
    perms = program.roles[0].system_permissions
    assert perms is not None
    assert perms.export is True
    assert perms.mass_update is False
    assert perms.portal is False
    assert perms.assignment_permission == "no"
    assert perms.user_permission == "no"


def test_system_permissions_absent_yields_none(loader, tmp_path):
    path = _write(tmp_path, "sysperm_absent.yaml", """\
        version: "1.0"
        description: "Absent system permissions"
        roles:
          - name: Plain
    """)
    program = loader.load_program(path)
    assert program.roles[0].system_permissions is None


def test_system_permissions_empty_block_yields_defaults(loader, tmp_path):
    path = _write(tmp_path, "sysperm_empty.yaml", """\
        version: "1.0"
        description: "Empty system permissions"
        roles:
          - name: Plain
            system_permissions: {}
    """)
    program = loader.load_program(path)
    perms = program.roles[0].system_permissions
    assert perms is not None
    assert perms.assignment_permission == "no"
    assert perms.user_permission == "no"
    assert perms.export is False
    assert perms.mass_update is False
    assert perms.portal is False


# ---- system_permissions rejection ----


def test_system_permissions_unknown_key_rejected(loader, tmp_path):
    path = _write(tmp_path, "sysperm_unknown.yaml", """\
        version: "1.0"
        description: "Unknown sysperm key"
        roles:
          - name: Mentor
            system_permissions:
              foobar: yes
    """)
    with pytest.raises(
        ValueError,
        match=(
            r"roles \('Mentor'\)\.system_permissions: unknown key\(s\) "
            r"\['foobar'\]"
        ),
    ):
        loader.load_program(path)


def test_system_permissions_audit_log_rejected(loader, tmp_path):
    """DEC-1 (audit-v1.2-D): audit_log dropped from §12.4. Loader
    must reject it as unknown rather than parsing it silently.
    """
    path = _write(tmp_path, "sysperm_audit_log.yaml", """\
        version: "1.0"
        description: "audit_log removed in DEC-1"
        roles:
          - name: Mentor
            system_permissions:
              audit_log: yes
    """)
    with pytest.raises(
        ValueError,
        match=(
            r"roles \('Mentor'\)\.system_permissions: unknown key\(s\) "
            r"\['audit_log'\]"
        ),
    ):
        loader.load_program(path)


def test_system_permissions_scope_key_with_bool_rejected(loader, tmp_path):
    path = _write(tmp_path, "sysperm_scope_bool.yaml", """\
        version: "1.0"
        description: "Scope key with bool"
        roles:
          - name: Mentor
            system_permissions:
              assignment_permission: yes
    """)
    with pytest.raises(
        ValueError,
        match=(
            r"roles \('Mentor'\)\.system_permissions\.assignment_permission: "
            r"must be one of"
        ),
    ):
        loader.load_program(path)


def test_system_permissions_flag_key_with_scope_rejected(loader, tmp_path):
    path = _write(tmp_path, "sysperm_flag_scope.yaml", """\
        version: "1.0"
        description: "Flag key with scope value"
        roles:
          - name: Mentor
            system_permissions:
              export: team
    """)
    with pytest.raises(
        ValueError,
        match=(
            r"roles \('Mentor'\)\.system_permissions\.export: must "
            r"be 'yes' or 'no'"
        ),
    ):
        loader.load_program(path)


# ---- _validate_roles ----


def test_within_file_role_uniqueness_violation(loader, tmp_path):
    path = _write(tmp_path, "dupe_roles.yaml", """\
        version: "1.0"
        description: "Duplicate role"
        roles:
          - name: Mentor
          - name: Mentor
    """)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any(
        "duplicate role name within this file" in e
        and "Mentor" in e
        for e in errors
    ), f"Expected within-file duplicate role error, got: {errors!r}"


def test_cross_batch_role_uniqueness_violation(loader, tmp_path):
    """Two files each declaring the same role produce a cross-batch error."""
    from espo_impl.core.models import ProgramContext

    path_a = _write(tmp_path, "a.yaml", """\
        version: "1.0"
        description: "A"
        roles:
          - name: Mentor
    """)
    path_b = _write(tmp_path, "b.yaml", """\
        version: "1.0"
        description: "B"
        roles:
          - name: Mentor
    """)
    program_a = loader.load_program(path_a)
    program_b = loader.load_program(path_b)
    context = ProgramContext.from_programs([program_a, program_b])
    errors_a = loader.validate_program_with_context(program_a, context)
    errors_b = loader.validate_program_with_context(program_b, context)
    assert any("declared in 2 files" in e for e in errors_a), errors_a
    assert any("declared in 2 files" in e for e in errors_b), errors_b


def test_scope_access_entity_resolves_native(loader, tmp_path):
    """Native entity in scope_access validates cleanly."""
    path = _write(tmp_path, "native_scope.yaml", """\
        version: "1.0"
        description: "Native entity in scope_access"
        roles:
          - name: Mentor
            scope_access:
              Contact:
                read: team
    """)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert errors == [], f"Unexpected errors: {errors!r}"


def test_scope_access_entity_resolves_custom_in_batch(loader, tmp_path):
    """Custom entity declared elsewhere in batch validates cleanly."""
    from espo_impl.core.models import ProgramContext

    entity_file = _write(tmp_path, "ent.yaml", """\
        version: "1.0"
        description: "Engagement entity"
        entities:
          Engagement:
            fields:
              - name: status
                type: varchar
                label: "Status"
    """)
    role_file = _write(tmp_path, "role.yaml", """\
        version: "1.0"
        description: "Role referencing Engagement"
        roles:
          - name: Mentor
            scope_access:
              Engagement:
                read: own
    """)
    program_entity = loader.load_program(entity_file)
    program_role = loader.load_program(role_file)
    context = ProgramContext.from_programs(
        [program_entity, program_role],
    )
    errors = loader.validate_program_with_context(program_role, context)
    assert errors == [], f"Unexpected errors: {errors!r}"


def test_scope_access_entity_unresolved_rejected(loader, tmp_path):
    path = _write(tmp_path, "unknown_entity.yaml", """\
        version: "1.0"
        description: "Unknown entity in scope_access"
        roles:
          - name: Mentor
            scope_access:
              NonexistentEntity:
                read: own
    """)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any(
        "NonexistentEntity" in e
        and "not declared in this batch" in e
        for e in errors
    ), f"Expected unresolved-entity error, got: {errors!r}"


# ---- _validate_teams ----


def test_within_file_team_uniqueness_violation(loader, tmp_path):
    path = _write(tmp_path, "dupe_teams.yaml", """\
        version: "1.0"
        description: "Duplicate team"
        teams:
          - name: HQ
          - name: HQ
    """)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any(
        "duplicate team name within this file" in e
        and "HQ" in e
        for e in errors
    ), f"Expected within-file duplicate team error, got: {errors!r}"


def test_cross_batch_team_uniqueness_violation(loader, tmp_path):
    from espo_impl.core.models import ProgramContext

    path_a = _write(tmp_path, "a.yaml", """\
        version: "1.0"
        description: "A"
        teams:
          - name: HQ
    """)
    path_b = _write(tmp_path, "b.yaml", """\
        version: "1.0"
        description: "B"
        teams:
          - name: HQ
    """)
    program_a = loader.load_program(path_a)
    program_b = loader.load_program(path_b)
    context = ProgramContext.from_programs([program_a, program_b])
    errors_a = loader.validate_program_with_context(program_a, context)
    errors_b = loader.validate_program_with_context(program_b, context)
    assert any("declared in 2 files" in e for e in errors_a), errors_a
    assert any("declared in 2 files" in e for e in errors_b), errors_b


# ---- ProgramContext extensions ----


def test_program_context_tracks_entity_role_team_names(loader, tmp_path):
    from espo_impl.core.models import ProgramContext

    path = _write(tmp_path, "all.yaml", """\
        version: "1.0"
        description: "All three"
        entities:
          Engagement:
            fields:
              - name: status
                type: varchar
                label: "Status"
        roles:
          - name: Mentor
        teams:
          - name: HQ
    """)
    program = loader.load_program(path)
    context = ProgramContext.from_programs([program])
    assert context.entity_names == frozenset({"Engagement"})
    assert context.role_names == frozenset({"Mentor"})
    assert context.team_names == frozenset({"HQ"})
    assert context.role_count_by_name == {"Mentor": 1}
    assert context.team_count_by_name == {"HQ": 1}


def test_program_context_role_team_counts_accumulate(loader, tmp_path):
    from espo_impl.core.models import ProgramContext

    a = _write(tmp_path, "a.yaml", """\
        version: "1.0"
        description: "A"
        roles:
          - name: Mentor
        teams:
          - name: HQ
    """)
    b = _write(tmp_path, "b.yaml", """\
        version: "1.0"
        description: "B"
        roles:
          - name: Mentor
        teams:
          - name: HQ
    """)
    pa = loader.load_program(a)
    pb = loader.load_program(b)
    context = ProgramContext.from_programs([pa, pb])
    assert context.role_count_by_name == {"Mentor": 2}
    assert context.team_count_by_name == {"HQ": 2}


# ---------------------------------------------------------------------------
# Section 12.5 — Role-aware visibility (Prompt G)
# ---------------------------------------------------------------------------


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(dedent(content))
    return path


def test_parse_layout_variants_detail(loader, tmp_path):
    """detail layout with two variants parses to LayoutSpec with variants."""
    path = _write(tmp_path, "p.yaml", """\
        version: "1.0"
        description: "Variant detail"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
            layout:
              detail:
                - forRoles: ["Mentor"]
                  panels:
                    - label: "Mentor panel"
                      rows: [[foo]]
                - forRoles: ["Admin"]
                  panels:
                    - label: "Admin panel"
                      rows: [[foo]]
        roles:
          - name: Mentor
          - name: Admin
    """)
    program = loader.load_program(path)
    detail = program.entities[0].layouts["detail"]
    assert detail.has_variants() is True
    assert detail.panels in (None, [])
    assert len(detail.variants) == 2
    assert detail.variants[0].for_roles == ["Mentor"]
    assert detail.variants[1].for_roles == ["Admin"]


def test_parse_layout_variants_list_accepted(loader, tmp_path):
    """list layout with variants parses (deploy NOT_SUPPORTED downstream)."""
    path = _write(tmp_path, "p.yaml", """\
        version: "1.0"
        description: "Variant list"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
            layout:
              list:
                - forRoles: ["Mentor"]
                  columns:
                    - field: foo
                - forRoles: ["Admin"]
                  columns:
                    - field: foo
        roles:
          - name: Mentor
          - name: Admin
    """)
    program = loader.load_program(path)
    list_layout = program.entities[0].layouts["list"]
    assert list_layout.has_variants() is True
    assert len(list_layout.variants) == 2
    assert list_layout.variants[0].columns[0].field == "foo"


def test_parse_layout_variants_missing_forRoles(loader, tmp_path):
    """Variant without forRoles is rejected at parse time."""
    path = _write(tmp_path, "p.yaml", """\
        version: "1.0"
        description: "Bad variant"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
            layout:
              detail:
                - panels:
                    - label: "P"
                      rows: [[foo]]
    """)
    with pytest.raises(ValueError, match="forRoles"):
        loader.load_program(path)


def test_parse_layout_variants_empty_forRoles(loader, tmp_path):
    """Empty forRoles list is rejected."""
    path = _write(tmp_path, "p.yaml", """\
        version: "1.0"
        description: "Bad variant"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
            layout:
              detail:
                - forRoles: []
                  panels:
                    - label: "P"
                      rows: [[foo]]
    """)
    with pytest.raises(ValueError, match="forRoles"):
        loader.load_program(path)


def test_parse_layout_single_block_still_works(loader, tmp_path):
    """Regression: existing single-block detail layout parses unchanged."""
    path = _write(tmp_path, "p.yaml", """\
        version: "1.0"
        description: "Single block"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
            layout:
              detail:
                panels:
                  - label: "P"
                    rows: [[foo]]
    """)
    program = loader.load_program(path)
    detail = program.entities[0].layouts["detail"]
    assert detail.has_variants() is False
    assert detail.panels is not None
    assert detail.panels[0].label == "P"


def test_layout_coverage_unmatched_role(loader, tmp_path):
    """Coverage rule rejects a role not claimed by any variant."""
    path = _write(tmp_path, "p.yaml", """\
        version: "1.0"
        description: "Unmatched"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
            layout:
              detail:
                - forRoles: ["Mentor"]
                  panels:
                    - label: "P"
                      rows: [[foo]]
        roles:
          - name: Mentor
          - name: Admin
    """)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    matching = [e for e in errors if "Admin" in e and "does not appear" in e]
    assert matching, f"expected coverage error, got: {errors}"


def test_layout_coverage_doubly_matched_role(loader, tmp_path):
    """Coverage rule rejects a role appearing in two variants."""
    path = _write(tmp_path, "p.yaml", """\
        version: "1.0"
        description: "Doubly matched"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
            layout:
              detail:
                - forRoles: ["Mentor"]
                  panels:
                    - label: "P1"
                      rows: [[foo]]
                - forRoles: ["Mentor"]
                  panels:
                    - label: "P2"
                      rows: [[foo]]
        roles:
          - name: Mentor
    """)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    matching = [e for e in errors if "Mentor" in e and "more than one" in e]
    assert matching, f"expected double-match error, got: {errors}"


def test_layout_coverage_full_match_clean(loader, tmp_path):
    """Every role covered by exactly one variant → no coverage errors."""
    path = _write(tmp_path, "p.yaml", """\
        version: "1.0"
        description: "Full coverage"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
            layout:
              detail:
                - forRoles: ["Mentor"]
                  panels:
                    - label: "P1"
                      rows: [[foo]]
                - forRoles: ["Admin"]
                  panels:
                    - label: "P2"
                      rows: [[foo]]
        roles:
          - name: Mentor
          - name: Admin
    """)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    coverage_errors = [
        e for e in errors
        if "does not appear" in e or "more than one" in e
    ]
    assert coverage_errors == [], f"unexpected coverage errors: {errors}"


def test_layout_variant_references_unknown_role(loader, tmp_path):
    """A variant referencing a role not declared anywhere is flagged."""
    path = _write(tmp_path, "p.yaml", """\
        version: "1.0"
        description: "Unknown role"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
            layout:
              detail:
                - forRoles: ["GhostRole"]
                  panels:
                    - label: "P"
                      rows: [[foo]]
        roles:
          - name: Mentor
    """)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    matching = [
        e for e in errors
        if "GhostRole" in e and "not declared" in e
    ]
    assert matching, f"expected unknown-role error, got: {errors}"


def test_field_visibleWhen_role_clause_accepted_at_loader(loader, tmp_path):
    """visibleWhen with role clause parses + validates clean at loader."""
    path = _write(tmp_path, "p.yaml", """\
        version: "1.0"
        description: "Role visible"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
                visibleWhen:
                  - { role: equals, value: "Mentor" }
        roles:
          - name: Mentor
    """)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert errors == []


def test_field_requiredWhen_role_clause_rejected(loader, tmp_path):
    """requiredWhen with role clause is rejected (defaults from Prompt F)."""
    path = _write(tmp_path, "p.yaml", """\
        version: "1.0"
        description: "Bad required"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
                requiredWhen:
                  - { role: equals, value: "Mentor" }
        roles:
          - name: Mentor
    """)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    matching = [e for e in errors if "not permitted in this context" in e]
    assert matching, f"expected context-rejection error, got: {errors}"


def test_saved_view_filter_role_clause_rejected(loader, tmp_path):
    """savedView.filter with role clause is rejected."""
    path = _write(tmp_path, "p.yaml", """\
        version: "1.0"
        description: "Bad filter"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
            savedViews:
              - id: sv1
                name: "Test"
                columns: [foo]
                filter:
                  - { role: equals, value: "Mentor" }
        roles:
          - name: Mentor
    """)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    matching = [e for e in errors if "not permitted in this context" in e]
    assert matching, f"expected context-rejection error, got: {errors}"


def test_panel_visibleWhen_role_clause_accepted(loader, tmp_path):
    """Panel-level visibleWhen with role clause parses + validates clean."""
    path = _write(tmp_path, "p.yaml", """\
        version: "1.0"
        description: "Panel role visible"
        entities:
          Contact:
            fields:
              - name: foo
                type: varchar
                label: "Foo"
            layout:
              detail:
                panels:
                  - label: "Mentor only"
                    rows: [[foo]]
                    visibleWhen:
                      - { role: equals, value: "Mentor" }
        roles:
          - name: Mentor
    """)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert errors == []

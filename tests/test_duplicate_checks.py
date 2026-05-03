"""Tests for duplicate-check parsing, validation, and short-circuit manager."""

from textwrap import dedent
from unittest.mock import MagicMock

import pytest

from espo_impl.core.config_loader import ConfigLoader
from espo_impl.core.duplicate_check_manager import DuplicateCheckManager
from espo_impl.core.models import (
    DuplicateCheck,
    DuplicateCheckStatus,
    EntityAction,
    EntityDefinition,
    FieldDefinition,
    ProgramFile,
)


@pytest.fixture
def loader():
    return ConfigLoader()


# ─── Parsing Tests ───────────────────────────────────────────────


def test_parse_no_duplicate_checks(loader, tmp_path):
    """Entity without duplicateChecks: has empty list."""
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
    path = tmp_path / "no_dup.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    assert program.entities[0].duplicate_checks == []


def test_parse_single_rule(loader, tmp_path):
    """Single duplicate-check rule parses correctly."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: personalEmail
                type: email
                label: "Personal Email"
            duplicateChecks:
              - id: contact-email
                fields: [personalEmail]
                normalize:
                  personalEmail: lowercase-trim
                onMatch: block
                message: "A Contact with this email already exists."
    """)
    path = tmp_path / "single_rule.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    checks = program.entities[0].duplicate_checks
    assert len(checks) == 1
    assert checks[0].id == "contact-email"
    assert checks[0].fields == ["personalEmail"]
    assert checks[0].normalize == {"personalEmail": "lowercase-trim"}
    assert checks[0].onMatch == "block"
    assert "already exists" in checks[0].message


def test_parse_multiple_rules(loader, tmp_path):
    """Multiple rules per entity parse correctly."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: personalEmail
                type: email
                label: "Email"
              - name: name
                type: varchar
                label: "Name"
              - name: billingCity
                type: varchar
                label: "City"
            duplicateChecks:
              - id: email-check
                fields: [personalEmail]
                onMatch: block
                message: "Duplicate email."
              - id: name-city-check
                fields: [name, billingCity]
                normalize:
                  name: case-fold-trim
                  billingCity: case-fold-trim
                onMatch: warn
    """)
    path = tmp_path / "multi_rules.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    checks = program.entities[0].duplicate_checks
    assert len(checks) == 2
    assert checks[0].id == "email-check"
    assert checks[1].id == "name-city-check"
    assert checks[1].onMatch == "warn"


def test_parse_rule_with_alert_fields(loader, tmp_path):
    """Rule with alertTemplate and alertTo parses correctly."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: personalEmail
                type: email
                label: "Email"
            duplicateChecks:
              - id: email-alert
                fields: [personalEmail]
                onMatch: block
                message: "Duplicate."
                alertTemplate: dup-email-alert
                alertTo: role:admin
    """)
    path = tmp_path / "alert_rule.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    check = program.entities[0].duplicate_checks[0]
    assert check.alertTemplate == "dup-email-alert"
    assert check.alertTo == "role:admin"


def test_parse_rule_without_normalize(loader, tmp_path):
    """Rule without normalize: has normalize=None."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: name
                type: varchar
                label: "Name"
            duplicateChecks:
              - id: name-check
                fields: [name]
                onMatch: warn
    """)
    path = tmp_path / "no_normalize.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    check = program.entities[0].duplicate_checks[0]
    assert check.normalize is None


# ─── Validation Tests ────────────────────────────────────────────


def test_validate_duplicate_id_within_entity(loader, tmp_path):
    """Duplicate id within an entity is an error."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: email
                type: email
                label: "Email"
            duplicateChecks:
              - id: dup-check
                fields: [email]
                onMatch: block
                message: "Dup."
              - id: dup-check
                fields: [email]
                onMatch: warn
    """)
    path = tmp_path / "dup_id.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("duplicate id 'dup-check'" in e for e in errors)


def test_validate_unknown_field_in_fields(loader, tmp_path):
    """Field in duplicateChecks.fields not on entity is an error."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: email
                type: email
                label: "Email"
            duplicateChecks:
              - id: check
                fields: [email, nonExistentField]
                onMatch: warn
    """)
    path = tmp_path / "unknown_field.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("nonExistentField" in e and "not found" in e for e in errors)


def test_validate_unknown_field_in_normalize(loader, tmp_path):
    """Normalize key not in fields: list is an error."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: email
                type: email
                label: "Email"
            duplicateChecks:
              - id: check
                fields: [email]
                normalize:
                  otherField: lowercase-trim
                onMatch: warn
    """)
    path = tmp_path / "normalize_unknown_field.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("otherField" in e and "not listed in 'fields'" in e for e in errors)


def test_validate_invalid_normalize_value(loader, tmp_path):
    """Invalid normalization value is an error."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: email
                type: email
                label: "Email"
            duplicateChecks:
              - id: check
                fields: [email]
                normalize:
                  email: uppercase-all
                onMatch: warn
    """)
    path = tmp_path / "bad_normalize.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("uppercase-all" in e and "invalid value" in e for e in errors)


def test_validate_invalid_on_match(loader, tmp_path):
    """Invalid onMatch value is an error."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: email
                type: email
                label: "Email"
            duplicateChecks:
              - id: check
                fields: [email]
                onMatch: reject
    """)
    path = tmp_path / "bad_on_match.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("invalid onMatch" in e for e in errors)


def test_validate_block_without_message(loader, tmp_path):
    """onMatch: block without message is an error."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: email
                type: email
                label: "Email"
            duplicateChecks:
              - id: check
                fields: [email]
                onMatch: block
    """)
    path = tmp_path / "block_no_msg.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("'message' is required" in e for e in errors)


def test_validate_alert_to_role_format(loader, tmp_path):
    """alertTo: role:admin is valid."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: email
                type: email
                label: "Email"
            duplicateChecks:
              - id: check
                fields: [email]
                onMatch: block
                message: "Dup."
                alertTo: "role:admin"
    """)
    path = tmp_path / "alert_role.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    alert_errors = [e for e in errors if "alertTo" in e]
    assert alert_errors == []


def test_validate_alert_to_email_format(loader, tmp_path):
    """alertTo with literal email is valid."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: email
                type: email
                label: "Email"
            duplicateChecks:
              - id: check
                fields: [email]
                onMatch: block
                message: "Dup."
                alertTo: "admin@example.com"
    """)
    path = tmp_path / "alert_email.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    alert_errors = [e for e in errors if "alertTo" in e]
    assert alert_errors == []


def test_validate_alert_to_field_name(loader, tmp_path):
    """alertTo with a valid field name is valid."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: email
                type: email
                label: "Email"
              - name: assignedUser
                type: varchar
                label: "Assigned User"
            duplicateChecks:
              - id: check
                fields: [email]
                onMatch: block
                message: "Dup."
                alertTo: assignedUser
    """)
    path = tmp_path / "alert_field.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    alert_errors = [e for e in errors if "alertTo" in e]
    assert alert_errors == []


def test_validate_alert_to_invalid(loader, tmp_path):
    """alertTo with invalid value is an error."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: email
                type: email
                label: "Email"
            duplicateChecks:
              - id: check
                fields: [email]
                onMatch: block
                message: "Dup."
                alertTo: notAFieldOrEmail
    """)
    path = tmp_path / "alert_invalid.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("alertTo" in e and "notAFieldOrEmail" in e for e in errors)


def test_validate_empty_fields_list(loader, tmp_path):
    """Empty fields: list is an error."""
    content = dedent("""\
        version: "1.0"
        description: "Test"
        entities:
          Contact:
            fields:
              - name: email
                type: email
                label: "Email"
            duplicateChecks:
              - id: check
                fields: []
                onMatch: warn
    """)
    path = tmp_path / "empty_fields.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("at least one field" in e for e in errors)


# ─── Manager NOT_SUPPORTED Short-Circuit Tests (Prompt D) ──────


def _make_dup_manager():
    """Create a duplicate check manager with mocked client and output."""
    client = MagicMock()
    client.profile.name = "Test"
    client.profile.url = "https://test.example.com"
    log = []

    def output_fn(msg, color):
        log.append((msg, color))

    mgr = DuplicateCheckManager(client, output_fn)
    return mgr, client, log


def _make_program_with_checks(checks):
    """Build a minimal ProgramFile with duplicate checks on Contact."""
    entity = EntityDefinition(
        name="Contact",
        fields=[
            FieldDefinition(name="email", type="email", label="Email"),
            FieldDefinition(name="name", type="varchar", label="Name"),
        ],
        duplicate_checks=checks,
    )
    return ProgramFile(
        version="1.0", description="Test", entities=[entity]
    )


def test_manager_short_circuits_without_api_calls():
    """process_duplicate_checks must not call any API method."""
    mgr, client, log = _make_dup_manager()

    checks = [
        DuplicateCheck(
            id="email-check", fields=["email"], onMatch="block",
            message="Dup email.",
        ),
        DuplicateCheck(
            id="name-check", fields=["name"], onMatch="warn",
        ),
    ]
    program = _make_program_with_checks(checks)
    results = mgr.process_duplicate_checks(program)

    assert len(results) == 2
    assert all(
        r.status == DuplicateCheckStatus.NOT_SUPPORTED for r in results
    )
    client.put_metadata.assert_not_called()
    client.get_client_defs.assert_not_called()


def test_manager_emits_not_supported_lines():
    """Each duplicate check emits a yellow [NOT SUPPORTED] line."""
    mgr, client, log = _make_dup_manager()

    checks = [DuplicateCheck(
        id="email-check", fields=["email"], onMatch="block",
        message="Dup email.",
    )]
    program = _make_program_with_checks(checks)
    mgr.process_duplicate_checks(program)

    messages = [msg for msg, _ in log]
    assert any(
        "[NOT SUPPORTED]" in msg
        and "Contact.duplicateChecks[email-check]" in msg
        and "manual config required" in msg
        and "—" in msg
        for msg in messages
    )
    assert all(color == "yellow" for _, color in log)


def test_manager_skips_delete_entities():
    """Entities with action=DELETE produce no results."""
    mgr, client, log = _make_dup_manager()

    entity = EntityDefinition(
        name="Old",
        fields=[],
        action=EntityAction.DELETE,
        duplicate_checks=[DuplicateCheck(
            id="x", fields=["email"], onMatch="warn"
        )],
    )
    program = ProgramFile(
        version="1.0", description="Test", entities=[entity]
    )
    results = mgr.process_duplicate_checks(program)
    assert results == []
    client.put_metadata.assert_not_called()


def test_manager_no_checks_returns_empty():
    """An entity with no duplicate checks produces no results."""
    mgr, client, log = _make_dup_manager()

    entity = EntityDefinition(
        name="Contact",
        fields=[FieldDefinition(name="email", type="email", label="Email")],
    )
    program = ProgramFile(
        version="1.0", description="Test", entities=[entity]
    )
    results = mgr.process_duplicate_checks(program)
    assert results == []
    client.put_metadata.assert_not_called()

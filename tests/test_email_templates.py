"""Tests for email-template parsing, validation, and CHECK->ACT manager."""

from textwrap import dedent
from unittest.mock import MagicMock

import pytest

from espo_impl.core.config_loader import ConfigLoader
from espo_impl.core.models import EmailTemplateStatus


@pytest.fixture
def loader():
    return ConfigLoader()


def _write_body(tmp_path, filename, content):
    """Write an HTML body file for testing."""
    tpl_dir = tmp_path / "templates"
    tpl_dir.mkdir(exist_ok=True)
    body_path = tpl_dir / filename
    body_path.write_text(content)
    return body_path


# ─── Parsing Tests ───────────────────────────────────────────────


def test_parse_email_template_full(loader, tmp_path):
    """Fully-populated email template parses correctly."""
    _write_body(
        tmp_path, "confirm.html",
        "<p>Hello {{name}}, your email is {{email}}.</p>"
    )
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            emailTemplates:
              - id: confirm
                name: "Confirmation"
                description: "Sent on creation"
                entity: Contact
                audience: "role:admin"
                subject: "Welcome {{name}}"
                bodyFile: "templates/confirm.html"
                mergeFields:
                  - name
                  - email
            fields:
              - name: name
                type: varchar
                label: "Name"
              - name: email
                type: varchar
                label: "Email"
    """)
    path = tmp_path / "full.yaml"
    path.write_text(content)
    program = loader.load_program(path)

    templates = program.entities[0].email_templates
    assert len(templates) == 1
    tmpl = templates[0]
    assert tmpl.id == "confirm"
    assert tmpl.name == "Confirmation"
    assert tmpl.entity == "Contact"
    assert tmpl.subject == "Welcome {{name}}"
    assert tmpl.body_file == "templates/confirm.html"
    assert tmpl.merge_fields == ["name", "email"]
    assert tmpl.description is not None
    assert "Sent on creation" in tmpl.description
    assert tmpl.audience == "role:admin"
    assert tmpl.body_content is not None
    assert tmpl.body_hash is not None


def test_parse_multiple_templates(loader, tmp_path):
    """Multiple templates per entity parse correctly."""
    _write_body(tmp_path, "a.html", "<p>{{name}}</p>")
    _write_body(tmp_path, "b.html", "<p>{{email}}</p>")
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            emailTemplates:
              - id: tmpl-a
                name: "Template A"
                entity: Contact
                subject: "A {{name}}"
                bodyFile: "templates/a.html"
                mergeFields: [name]
              - id: tmpl-b
                name: "Template B"
                entity: Contact
                subject: "B {{email}}"
                bodyFile: "templates/b.html"
                mergeFields: [email]
            fields:
              - name: name
                type: varchar
                label: "Name"
              - name: email
                type: varchar
                label: "Email"
    """)
    path = tmp_path / "multi.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    assert len(program.entities[0].email_templates) == 2


# ─── Validation Tests ────────────────────────────────────────────


def test_validate_duplicate_id(loader, tmp_path):
    """Duplicate template id within entity produces error."""
    _write_body(tmp_path, "a.html", "<p>{{name}}</p>")
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            emailTemplates:
              - id: dup
                name: "Template 1"
                entity: Contact
                subject: "A {{name}}"
                bodyFile: "templates/a.html"
                mergeFields: [name]
              - id: dup
                name: "Template 2"
                entity: Contact
                subject: "B {{name}}"
                bodyFile: "templates/a.html"
                mergeFields: [name]
            fields:
              - name: name
                type: varchar
                label: "Name"
    """)
    path = tmp_path / "dup.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("duplicate id 'dup'" in e for e in errors)


def test_validate_entity_mismatch(loader, tmp_path):
    """entity: value that doesn't match parent produces error."""
    _write_body(tmp_path, "a.html", "<p>{{name}}</p>")
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            emailTemplates:
              - id: tmpl
                name: "Template"
                entity: WrongEntity
                subject: "Hi {{name}}"
                bodyFile: "templates/a.html"
                mergeFields: [name]
            fields:
              - name: name
                type: varchar
                label: "Name"
    """)
    path = tmp_path / "mismatch.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("WrongEntity" in e and "entity" in e for e in errors)


def test_validate_missing_body_file(loader, tmp_path):
    """bodyFile that doesn't resolve produces error."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            emailTemplates:
              - id: tmpl
                name: "Template"
                entity: Contact
                subject: "Hi {{name}}"
                bodyFile: "templates/nonexistent.html"
                mergeFields: [name]
            fields:
              - name: name
                type: varchar
                label: "Name"
    """)
    path = tmp_path / "no_body.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("not found" in e and "bodyFile" in e for e in errors)


def test_validate_merge_field_not_on_entity(loader, tmp_path):
    """mergeField not a real field on entity produces error."""
    _write_body(tmp_path, "a.html", "<p>{{ghostField}}</p>")
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            emailTemplates:
              - id: tmpl
                name: "Template"
                entity: Contact
                subject: "Hi"
                bodyFile: "templates/a.html"
                mergeFields: [ghostField]
            fields:
              - name: name
                type: varchar
                label: "Name"
    """)
    path = tmp_path / "bad_merge.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("ghostField" in e and "mergeFields" in e for e in errors)


def test_validate_placeholder_not_in_merge_fields(loader, tmp_path):
    """{{placeholder}} in subject not in mergeFields produces error."""
    _write_body(tmp_path, "a.html", "<p>Hello</p>")
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            emailTemplates:
              - id: tmpl
                name: "Template"
                entity: Contact
                subject: "Hi {{unknownField}}"
                bodyFile: "templates/a.html"
                mergeFields: [name]
            fields:
              - name: name
                type: varchar
                label: "Name"
    """)
    path = tmp_path / "bad_ph.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("unknownField" in e and "subject" in e for e in errors)


def test_validate_placeholder_in_body_not_in_merge_fields(loader, tmp_path):
    """{{placeholder}} in body file not in mergeFields produces error."""
    _write_body(tmp_path, "a.html", "<p>{{badField}}</p>")
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            emailTemplates:
              - id: tmpl
                name: "Template"
                entity: Contact
                subject: "Hi {{name}}"
                bodyFile: "templates/a.html"
                mergeFields: [name]
            fields:
              - name: name
                type: varchar
                label: "Name"
    """)
    path = tmp_path / "body_ph.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("badField" in e and "bodyFile" in e for e in errors)


def test_validate_unused_merge_field(loader, tmp_path):
    """mergeField listed but never used produces error."""
    _write_body(tmp_path, "a.html", "<p>Hello</p>")
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            emailTemplates:
              - id: tmpl
                name: "Template"
                entity: Contact
                subject: "Hi"
                bodyFile: "templates/a.html"
                mergeFields: [name]
            fields:
              - name: name
                type: varchar
                label: "Name"
    """)
    path = tmp_path / "unused.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("never used" in e and "name" in e for e in errors)


def test_validate_valid_email_template(loader, tmp_path):
    """Valid email template produces no errors."""
    _write_body(
        tmp_path, "a.html",
        "<p>Hello {{name}}, your email is {{email}}.</p>"
    )
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            emailTemplates:
              - id: tmpl
                name: "Template"
                entity: Contact
                subject: "Hi {{name}}"
                bodyFile: "templates/a.html"
                mergeFields: [name, email]
            fields:
              - name: name
                type: varchar
                label: "Name"
              - name: email
                type: varchar
                label: "Email"
    """)
    path = tmp_path / "valid.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    et_errors = [e for e in errors if "emailTemplates" in e]
    assert et_errors == []


# ─── Cross-Block alertTemplate Tests ─────────────────────────────


def test_validate_alert_template_valid_ref(loader, tmp_path):
    """alertTemplate matching email template id passes."""
    _write_body(tmp_path, "alert.html", "<p>{{email}}</p>")
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            emailTemplates:
              - id: alert-tmpl
                name: "Alert"
                entity: Contact
                subject: "Alert {{email}}"
                bodyFile: "templates/alert.html"
                mergeFields: [email]
            duplicateChecks:
              - id: dup-email
                fields: [email]
                onMatch: warn
                alertTemplate: alert-tmpl
            fields:
              - name: email
                type: varchar
                label: "Email"
    """)
    path = tmp_path / "valid_ref.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    alert_errors = [e for e in errors if "alertTemplate" in e]
    assert alert_errors == []


def test_validate_alert_template_invalid_ref(loader, tmp_path):
    """alertTemplate not matching any template id produces error."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            duplicateChecks:
              - id: dup-email
                fields: [email]
                onMatch: warn
                alertTemplate: nonexistent-tmpl
            fields:
              - name: email
                type: varchar
                label: "Email"
    """)
    path = tmp_path / "invalid_ref.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    assert any("nonexistent-tmpl" in e and "alertTemplate" in e for e in errors)


def test_validate_alert_template_absent_no_error(loader, tmp_path):
    """Absent alertTemplate produces no error."""
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Contact:
            duplicateChecks:
              - id: dup-email
                fields: [email]
                onMatch: warn
            fields:
              - name: email
                type: varchar
                label: "Email"
    """)
    path = tmp_path / "no_ref.yaml"
    path.write_text(content)
    program = loader.load_program(path)
    errors = loader.validate_program(program)
    alert_errors = [e for e in errors if "alertTemplate" in e]
    assert alert_errors == []


# ─── Manager CHECK->ACT Tests ───────────────────────────────────


def _make_program(templates_data, tmp_path=None):
    """Build a minimal ProgramFile with email templates for manager testing."""
    from espo_impl.core.models import (
        EmailTemplate,
        EntityDefinition,
        FieldDefinition,
        ProgramFile,
    )

    templates = []
    for td in templates_data:
        templates.append(EmailTemplate(
            id=td["id"],
            name=td["name"],
            entity="Contact",
            subject=td.get("subject", "Test"),
            body_file=td.get("bodyFile", "templates/test.html"),
            merge_fields=td.get("mergeFields", []),
            body_content=td.get("body_content", "<p>Test</p>"),
            body_hash=td.get("body_hash", "abc123"),
        ))

    entity = EntityDefinition(
        name="Contact",
        fields=[
            FieldDefinition(name="email", type="varchar", label="Email"),
        ],
        email_templates=templates,
    )
    return ProgramFile(
        version="1.1",
        description="Test",
        entities=[entity],
    )


def _mock_client(existing_templates=None):
    """Create a mock API client for email template testing."""
    client = MagicMock()
    if existing_templates is None:
        existing_templates = []

    def mock_request(method, url, **kwargs):
        if "EmailTemplate" in url and method == "GET":
            return (200, {"list": existing_templates})
        return (200, {})

    client._request = MagicMock(side_effect=mock_request)
    client.profile.api_url = "https://test.example.com/api/v1"
    client.create_record.return_value = (200, {"id": "new-id"})
    client.patch_record.return_value = (200, {})
    return client


def test_manager_create_new_template():
    """Template absent on CRM is created."""
    from espo_impl.core.email_template_manager import EmailTemplateManager

    program = _make_program([{
        "id": "tmpl-1",
        "name": "Template One",
    }])
    client = _mock_client()
    output = []
    mgr = EmailTemplateManager(client, lambda msg, color: output.append(msg))
    results = mgr.process_email_templates(program)

    assert len(results) == 1
    assert results[0].status == EmailTemplateStatus.CREATED


def test_manager_skip_matching_template():
    """Template matching CRM state is skipped."""
    from espo_impl.core.email_template_manager import EmailTemplateManager

    existing = [{
        "id": "crm-id-1",
        "name": "Template One",
        "subject": "Test",
        "body": "<p>Test</p>",
    }]
    program = _make_program([{
        "id": "tmpl-1",
        "name": "Template One",
        "subject": "Test",
        "body_content": "<p>Test</p>",
    }])
    client = _mock_client(existing)
    output = []
    mgr = EmailTemplateManager(client, lambda msg, color: output.append(msg))
    results = mgr.process_email_templates(program)

    assert len(results) == 1
    assert results[0].status == EmailTemplateStatus.SKIPPED


def test_manager_update_differing_template():
    """Template differing from CRM is updated."""
    from espo_impl.core.email_template_manager import EmailTemplateManager

    existing = [{
        "id": "crm-id-1",
        "name": "Template One",
        "subject": "Old Subject",
        "body": "<p>Old</p>",
    }]
    program = _make_program([{
        "id": "tmpl-1",
        "name": "Template One",
        "subject": "New Subject",
        "body_content": "<p>New</p>",
    }])
    client = _mock_client(existing)
    output = []
    mgr = EmailTemplateManager(client, lambda msg, color: output.append(msg))
    results = mgr.process_email_templates(program)

    assert len(results) == 1
    assert results[0].status == EmailTemplateStatus.UPDATED


def test_manager_drift_detection():
    """Templates on CRM not in YAML are flagged as drift."""
    from espo_impl.core.email_template_manager import EmailTemplateManager

    existing = [
        {"id": "crm-1", "name": "Known", "subject": "Test", "body": "<p>Test</p>"},
        {"id": "crm-2", "name": "Orphan", "subject": "X", "body": "<p>X</p>"},
    ]
    program = _make_program([{
        "id": "tmpl-1",
        "name": "Known",
        "subject": "Test",
        "body_content": "<p>Test</p>",
    }])
    client = _mock_client(existing)
    output = []
    mgr = EmailTemplateManager(client, lambda msg, color: output.append(msg))
    results = mgr.process_email_templates(program)

    statuses = {r.template_id: r.status for r in results}
    assert statuses.get("Orphan") == EmailTemplateStatus.DRIFT

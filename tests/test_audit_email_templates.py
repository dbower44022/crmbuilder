"""Tests for email-template audit capture (REQ-124 / PI-168).

Covers reverse-discovery of EmailTemplate records, merge-field
derivation from ``{{fieldName}}`` placeholders, sidecar HTML body
writing, ``emailTemplates:`` YAML emission, and a full round-trip:
the audited YAML + body file must load and pass the deploy-side
validator, proving the captured templates are re-deployable.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from espo_impl.core.audit_manager import (
    AuditManager,
    AuditOptions,
    AuditReport,
    EmailTemplateAuditResult,
    EntityAuditResult,
)
from espo_impl.core.audit_utils import EntityClass
from espo_impl.core.config_loader import ConfigLoader

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(**method_returns: Any) -> MagicMock:
    client = MagicMock()
    profile = MagicMock()
    profile.url = "https://example.test"
    profile.name = "audit-test"
    client.profile = profile
    for name, value in method_returns.items():
        getattr(client, name).return_value = value
    return client


def _make_manager(
    client: MagicMock | None = None,
    options: AuditOptions | None = None,
) -> tuple[AuditManager, list[tuple[str, str]]]:
    if client is None:
        client = _make_client()
    log: list[tuple[str, str]] = []
    manager = AuditManager(
        client=client,
        options=options or AuditOptions(),
        callback=lambda msg, color: log.append((msg, color)),
    )
    return manager, log


def _empty_report() -> AuditReport:
    return AuditReport(
        source_url="https://example.test",
        source_name="audit-test",
        timestamp="2026-06-13T00:00:00Z",
        output_dir="",
    )


def _entity(yaml_name: str = "Contact", espo: str = "Contact") -> EntityAuditResult:
    return EntityAuditResult(
        yaml_name=yaml_name,
        espo_name=espo,
        entity_class=EntityClass.NATIVE,
    )


def _tmpl_record(name: str, subject: str, body: str) -> dict[str, Any]:
    return {"id": "x" + name, "name": name, "subject": subject, "body": body}


# ---------------------------------------------------------------------------
# merge-field derivation + id slugging
# ---------------------------------------------------------------------------


def test_extract_merge_fields_dedupes_sorts_and_ignores_dotted():
    fields = AuditManager._extract_merge_fields(
        "Hello {{firstName}}",
        "<p>{{firstName}} of {{accountName}}; ignore {{Account.name}}</p>",
    )
    assert fields == ["accountName", "firstName"]


def test_extract_merge_fields_empty_when_no_placeholders():
    assert AuditManager._extract_merge_fields("Static subject", "<p>hi</p>") == []


def test_unique_template_id_slugifies_and_disambiguates():
    manager, _ = _make_manager()
    seen: set[str] = set()
    first = manager._unique_template_id("Mentor Application Confirmation!", seen)
    seen.add(first)
    second = manager._unique_template_id("Mentor Application Confirmation", seen)
    assert first == "mentor-application-confirmation"
    assert second == "mentor-application-confirmation-2"


# ---------------------------------------------------------------------------
# _discover_email_templates
# ---------------------------------------------------------------------------


def test_discover_populates_templates_with_derived_merge_fields():
    client = _make_client(get_email_templates=(200, {"total": 1, "list": [
        _tmpl_record(
            "Welcome", "Hi {{firstName}}", "<p>Hi {{firstName}}</p>"
        ),
    ]}))
    manager, _ = _make_manager(client)
    entity = _entity()
    report = _empty_report()

    manager._discover_email_templates([entity], report)

    assert len(entity.email_templates) == 1
    tmpl = entity.email_templates[0]
    assert tmpl.name == "Welcome"
    assert tmpl.id == "welcome"
    assert tmpl.subject == "Hi {{firstName}}"
    assert tmpl.merge_fields == ["firstName"]
    assert report.warnings == []
    client.get_email_templates.assert_called_once_with("Contact")


def test_discover_404_skips_without_warning():
    client = _make_client(get_email_templates=(404, None))
    manager, log = _make_manager(client)
    entity = _entity()
    report = _empty_report()

    manager._discover_email_templates([entity], report)

    assert entity.email_templates == []
    assert report.warnings == []
    assert any("EmailTemplate unavailable" in msg for msg, _ in log)


def test_discover_non_200_records_warning():
    client = _make_client(get_email_templates=(500, None))
    manager, _ = _make_manager(client)
    entity = _entity()
    report = _empty_report()

    manager._discover_email_templates([entity], report)

    assert entity.email_templates == []
    assert len(report.warnings) == 1
    assert "HTTP 500" in report.warnings[0]


def test_discover_skips_unnamed_records():
    client = _make_client(get_email_templates=(200, {"list": [
        {"id": "a", "name": "", "subject": "s", "body": "b"},
        _tmpl_record("Real", "s {{firstName}}", "b"),
    ]}))
    manager, _ = _make_manager(client)
    entity = _entity()

    manager._discover_email_templates([entity], _empty_report())

    assert [t.name for t in entity.email_templates] == ["Real"]


# ---------------------------------------------------------------------------
# YAML emission + body writing
# ---------------------------------------------------------------------------


def test_build_entity_yaml_emits_email_templates_block():
    manager, _ = _make_manager()
    entity = _entity()
    entity.email_templates.append(EmailTemplateAuditResult(
        id="welcome", name="Welcome", subject="Hi {{firstName}}",
        body="<p>Hi {{firstName}}</p>", merge_fields=["firstName"],
    ))

    yaml_dict = manager._build_entity_yaml(entity)
    block = yaml_dict["entities"]["Contact"]["emailTemplates"]

    assert block == [{
        "id": "welcome",
        "name": "Welcome",
        "entity": "Contact",
        "subject": "Hi {{firstName}}",
        "bodyFile": "templates/Contact/welcome.html",
        "mergeFields": ["firstName"],
    }]


def test_write_email_template_bodies_creates_sidecar_files(tmp_path: Path):
    manager, _ = _make_manager()
    entity = _entity()
    entity.email_templates.append(EmailTemplateAuditResult(
        id="welcome", name="Welcome", subject="Hi",
        body="<p>Hi {{firstName}}</p>", merge_fields=["firstName"],
    ))
    report = _empty_report()

    manager._write_email_template_bodies(entity, tmp_path, report)

    body_path = tmp_path / "templates" / "Contact" / "welcome.html"
    assert body_path.read_text(encoding="utf-8") == "<p>Hi {{firstName}}</p>"
    assert report.errors == []


def test_entity_with_only_templates_is_written(tmp_path: Path):
    manager, _ = _make_manager()
    entity = _entity()
    entity.email_templates.append(EmailTemplateAuditResult(
        id="welcome", name="Welcome", subject="Hi {{firstName}}",
        body="<p>Hi</p>", merge_fields=["firstName"],
    ))
    report = _empty_report()

    count = manager._write_yaml_files([entity], [], tmp_path, report)

    assert count == 1
    assert (tmp_path / "Contact.yaml").is_file()
    assert (tmp_path / "templates" / "Contact" / "welcome.html").is_file()


# ---------------------------------------------------------------------------
# Round-trip: audited YAML must pass the deploy-side validator
# ---------------------------------------------------------------------------


def test_audited_email_template_yaml_validates(tmp_path: Path):
    """Emit, then load+validate through the real config loader.

    Proves the captured ``emailTemplates:`` block is re-deployable:
    the bodyFile resolves, mergeFields reference real (native) fields,
    and every placeholder is declared.
    """
    manager, _ = _make_manager()
    entity = _entity()  # Contact (native Person) — firstName is native
    entity.email_templates.append(EmailTemplateAuditResult(
        id="welcome",
        name="Welcome Mentor",
        subject="Welcome {{firstName}}",
        body="<p>Hello {{firstName}}, welcome aboard.</p>",
        merge_fields=["firstName"],
    ))
    report = _empty_report()

    manager._write_yaml_files([entity], [], tmp_path, report)
    assert report.errors == []

    loader = ConfigLoader()
    program = loader.load_program(tmp_path / "Contact.yaml")
    errors = loader.validate_program(program)

    template_errors = [e for e in errors if "emailTemplates" in e]
    assert template_errors == [], template_errors
    # The body file resolved (content loaded) at parse time.
    tmpl = program.entities[0].email_templates[0]
    assert tmpl.body_content == "<p>Hello {{firstName}}, welcome aboard.</p>"

"""Tests for the headless publish service (PRJ-042, PI-243).

Covers the V2-instance -> InstanceProfile mapping, in-memory generate-result
parsing, the schema + live-target validation gate (REQ-288), and the
publish() orchestration: validate-only, the no-deploy-on-validation-failure
gate, and the deploy path. The live target is faked throughout — only the
pure generate/parse/validate logic runs for real.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.adapters.base import GenerationResult, ProgramArtifact
from crmbuilder_v2.publish import service

from espo_impl.core.deploy_pipeline import DeployOutcome
from espo_impl.core.models import InstanceRole

# A clean one-entity program.
_CLEAN_YAML = """\
version: "1.1"
description: "clean"
entities:
  Contact:
    fields:
      - name: nickName
        type: varchar
        label: Nickname
"""

# A program whose savedView column references accountType — declared by no
# YAML in the batch. Hard-fails batch-only; resolves clean once the live
# target reports accountType as an existing field (REQ-288).
_SERVER_FIELD_YAML = """\
version: "1.1"
description: "references a deployed-only field"
entities:
  Account:
    fields:
      - name: fundraisingStage
        type: enum
        label: "Fundraising Stage"
        options:
          - Prospect
          - Active
    savedViews:
      - id: by-type
        name: "By Account Type"
        filter:
          - { field: fundraisingStage, op: equals, value: Active }
        columns: [name, accountType]
"""


def _result(*programs: tuple[str, str], companions=None) -> GenerationResult:
    return GenerationResult(
        engine="espocrm",
        rendered_at="2026-06-21T00:00:00",
        programs=[ProgramArtifact(filename=f, content=c) for f, c in programs],
        companions=list(companions or []),
    )


# -- build_target_profile ----------------------------------------------------


def test_build_target_profile_maps_fields():
    record = {
        "instance_identifier": "INST-001",
        "instance_name": "CBM prod",
        "instance_url": "https://crm.example.org",
        "instance_auth_method": "hmac",
    }
    profile = service.build_target_profile(record, api_key="K", secret_key="S")
    assert profile.name == "CBM prod"
    assert profile.url == "https://crm.example.org"
    assert profile.api_key == "K"
    assert profile.secret_key == "S"
    assert profile.auth_method == "hmac"
    assert profile.role == InstanceRole.TARGET


def test_build_target_profile_defaults():
    record = {
        "instance_identifier": "INST-002",
        "instance_url": "https://x.example.org",
    }
    profile = service.build_target_profile(record, api_key="K")
    # name falls back to the identifier; auth_method defaults to api_key.
    assert profile.name == "INST-002"
    assert profile.auth_method == "api_key"
    assert profile.secret_key is None


# -- parse_programs ----------------------------------------------------------


def test_parse_programs_in_memory():
    parsed = service.parse_programs(_result(("Contact.yaml", _CLEAN_YAML)))
    assert [f for f, _ in parsed] == ["Contact.yaml"]
    program = parsed[0][1]
    assert program.entities[0].name == "Contact"
    assert program.entities[0].fields[0].name == "nickName"
    # String input leaves no source path.
    assert program.source_path is None


# -- validate_programs (REQ-288) ---------------------------------------------


def test_validate_programs_clean():
    parsed = service.parse_programs(_result(("Contact.yaml", _CLEAN_YAML)))
    assert service.validate_programs(parsed) == {}


def test_validate_programs_fails_without_server_field():
    parsed = service.parse_programs(_result(("Account.yaml", _SERVER_FIELD_YAML)))
    failures = service.validate_programs(parsed)
    assert "Account.yaml" in failures
    assert any("accountType" in e for e in failures["Account.yaml"])


def test_validate_programs_resolves_with_server_field():
    parsed = service.parse_programs(_result(("Account.yaml", _SERVER_FIELD_YAML)))
    failures = service.validate_programs(
        parsed, {"Account": frozenset({"accountType"})}
    )
    assert failures == {}


# -- publish() orchestration -------------------------------------------------


class _FakeDesignClient:
    """A design client whose nine list_* methods return empty design lists;
    generation is stubbed, so the contents don't matter."""

    def __getattr__(self, _name):
        return lambda: []


@pytest.fixture
def _stub_live(monkeypatch):
    """Stub the live-target touchpoints: client construction and field
    discovery. Returns a setter for the server-field map."""
    monkeypatch.setattr(service, "EspoAdminClient", lambda profile: object())
    state = {"server_fields": {}}

    def _gather(_client, _names):
        return state["server_fields"], []

    monkeypatch.setattr(service, "gather_server_fields", _gather)
    return state


def _stub_generate(monkeypatch, result: GenerationResult):
    monkeypatch.setattr(
        service, "generate_design_yaml",
        lambda design_client, *, rendered_at, engagement=None: result,
    )


def test_publish_validate_only_skips_deploy(monkeypatch, _stub_live):
    _stub_generate(monkeypatch, _result(("Contact.yaml", _CLEAN_YAML)))
    deployed_calls = []
    monkeypatch.setattr(
        service, "deploy_pipeline",
        lambda *a, **k: deployed_calls.append(1),
    )

    res = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _FakeDesignClient(),
        api_key="K",
        rendered_at="2026-06-21T00:00:00",
        validate_only=True,
    )
    assert res.validate_only is True
    assert res.validation_failed is False
    assert deployed_calls == []
    assert all(not p.deployed for p in res.programs)


def test_publish_blocks_deploy_on_validation_failure(monkeypatch, _stub_live):
    # accountType unresolved (server fields empty) -> validation fails.
    _stub_generate(monkeypatch, _result(("Account.yaml", _SERVER_FIELD_YAML)))
    deployed_calls = []
    monkeypatch.setattr(
        service, "deploy_pipeline",
        lambda *a, **k: deployed_calls.append(1),
    )

    res = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _FakeDesignClient(),
        api_key="K",
        rendered_at="2026-06-21T00:00:00",
    )
    assert res.validation_failed is True
    assert deployed_calls == []
    account = next(p for p in res.programs if p.filename == "Account.yaml")
    assert not account.deployed
    assert any("accountType" in e for e in account.validation_errors)


def test_publish_deploys_when_valid(monkeypatch, _stub_live):
    _stub_generate(monkeypatch, _result(("Contact.yaml", _CLEAN_YAML)))
    sentinel_report = object()
    calls = []

    def _fake_deploy(program, client, field_mgr, output_fn, **k):
        calls.append(program)
        output_fn("deploying", "white")
        return DeployOutcome(report=sentinel_report)

    monkeypatch.setattr(service, "deploy_pipeline", _fake_deploy)

    res = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _FakeDesignClient(),
        api_key="K",
        rendered_at="2026-06-21T00:00:00",
    )
    assert res.validation_failed is False
    assert len(calls) == 1
    contact = res.programs[0]
    assert contact.deployed is True
    assert contact.report is sentinel_report
    assert ("deploying", "white") in contact.log


# -- verify_publish (REQ-291) ------------------------------------------------


def _contact_programs():
    return service.parse_programs(_result(("Contact.yaml", _CLEAN_YAML)))


def test_verify_publish_all_present():
    res = service.verify_publish(
        _contact_programs(),
        {"Contact": frozenset({"nickName", "name"})},
        [],
    )
    assert res.ran is True
    assert res.conclusive is True
    assert res.all_present is True
    ent = res.entities[0]
    assert ent.entity == "Contact"
    assert ent.present is True
    assert ent.status == "matching"
    assert ent.fields_present == ["nickName"]
    assert ent.fields_missing == []


def test_verify_publish_partial_missing_field():
    res = service.verify_publish(
        _contact_programs(),
        {"Contact": frozenset({"name"})},  # nickName did not land
        [],
    )
    assert res.all_present is False
    ent = res.entities[0]
    assert ent.present is True
    assert ent.status == "partial"
    assert ent.fields_missing == ["nickName"]


def test_verify_publish_missing_entity():
    res = service.verify_publish(
        _contact_programs(),
        {},  # entity not present on target
        ["Contact: not present on the live instance — ..."],
    )
    assert res.conclusive is True
    assert res.all_present is False
    ent = res.entities[0]
    assert ent.present is False
    assert ent.status == "missing"
    assert ent.fields_missing == ["nickName"]


def test_verify_publish_inconclusive_when_scopes_unreadable():
    res = service.verify_publish(
        _contact_programs(),
        {},
        ["Could not read live instance scopes (HTTP 500); ..."],
    )
    assert res.conclusive is False
    assert res.all_present is False
    ent = res.entities[0]
    assert ent.present is None
    assert ent.status == "unverified"


def test_publish_verifies_after_real_publish(monkeypatch, _stub_live):
    _stub_generate(monkeypatch, _result(("Contact.yaml", _CLEAN_YAML)))
    _stub_live["server_fields"] = {"Contact": frozenset({"nickName"})}
    monkeypatch.setattr(
        service, "deploy_pipeline",
        lambda *a, **k: DeployOutcome(report=object()),
    )

    res = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _FakeDesignClient(),
        api_key="K",
        rendered_at="2026-06-21T00:00:00",
    )
    assert res.verification is not None
    assert res.verification.ran is True
    assert res.verification.all_present is True


def test_publish_no_verification_on_preview(monkeypatch, _stub_live):
    _stub_generate(monkeypatch, _result(("Contact.yaml", _CLEAN_YAML)))
    monkeypatch.setattr(
        service, "deploy_pipeline",
        lambda *a, **k: DeployOutcome(report=object()),
    )
    res = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _FakeDesignClient(),
        api_key="K",
        rendered_at="2026-06-21T00:00:00",
        preview=True,
    )
    assert res.preview is True
    assert res.verification is None


def test_publish_no_verification_on_validate_only(monkeypatch, _stub_live):
    _stub_generate(monkeypatch, _result(("Contact.yaml", _CLEAN_YAML)))
    monkeypatch.setattr(service, "deploy_pipeline", lambda *a, **k: None)
    res = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _FakeDesignClient(),
        api_key="K",
        rendered_at="2026-06-21T00:00:00",
        validate_only=True,
    )
    assert res.verification is None


# -- scoped publish (REQ-290) ------------------------------------------------


def _two_program_result():
    return _result(
        ("Contact.yaml", _CLEAN_YAML),
        ("Account.yaml", _CLEAN_YAML.replace("Contact", "Account")),
    )


def test_publish_scope_deploys_only_selected(monkeypatch, _stub_live):
    _stub_generate(monkeypatch, _two_program_result())
    deployed = []
    monkeypatch.setattr(
        service, "deploy_pipeline",
        lambda program, *a, **k: deployed.append(program.entities[0].name)
        or DeployOutcome(report=object()),
    )
    res = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _FakeDesignClient(),
        api_key="K",
        rendered_at="2026-06-21T00:00:00",
        scope={"Account.yaml"},
    )
    assert deployed == ["Account"]
    assert [p.filename for p in res.programs] == ["Account.yaml"]


def test_publish_scope_none_deploys_everything(monkeypatch, _stub_live):
    _stub_generate(monkeypatch, _two_program_result())
    deployed = []
    monkeypatch.setattr(
        service, "deploy_pipeline",
        lambda program, *a, **k: deployed.append(program.entities[0].name)
        or DeployOutcome(report=object()),
    )
    res = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _FakeDesignClient(),
        api_key="K",
        rendered_at="2026-06-21T00:00:00",
        scope=None,
    )
    assert sorted(deployed) == ["Account", "Contact"]
    assert {p.filename for p in res.programs} == {"Contact.yaml", "Account.yaml"}


def test_publish_preview_dry_runs(monkeypatch, _stub_live):
    from espo_impl.core.deploy_pipeline import DeployOutcome

    _stub_generate(monkeypatch, _result(("Contact.yaml", _CLEAN_YAML)))
    captured = {}

    def fake_deploy(program, client, field_mgr, output_fn, *, dry_run=False, **k):
        captured["dry_run"] = dry_run
        return DeployOutcome(report=object())

    monkeypatch.setattr(service, "deploy_pipeline", fake_deploy)

    res = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _FakeDesignClient(),
        api_key="K",
        rendered_at="2026-06-21T00:00:00",
        preview=True,
    )
    # Preview runs the deploy engine in dry-run, and marks nothing deployed.
    assert captured["dry_run"] is True
    assert res.preview is True
    assert all(not p.deployed for p in res.programs)

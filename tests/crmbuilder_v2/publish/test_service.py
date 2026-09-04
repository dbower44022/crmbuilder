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
    """A design client whose list_* methods return empty design lists;
    generation is stubbed, so the contents don't matter. The lambda takes
    any arguments so per-instance reads (list_system_setting_values) work."""

    def __getattr__(self, _name):
        return lambda *args, **kwargs: []


@pytest.fixture
def _stub_live(monkeypatch):
    """Stub the live-target touchpoints: client construction, field discovery,
    and the pre-publish backup capture. Returns a setter for the server-field
    map (``server_fields``) and the backup behaviour (``backup``)."""
    state = {"server_fields": {}, "backup": {"entities": {}}, "entity_defs": {}}

    class _StubTarget:
        """The live-target client: entity defs served from the state dict
        (absent by default, so every plan reads as additive)."""

        def get_entity_field_list(self, entity):
            defs = state["entity_defs"].get(entity)
            return (200, defs) if defs is not None else (404, None)

    monkeypatch.setattr(service, "EspoAdminClient", lambda profile: _StubTarget())

    def _gather(_client, _names):
        return state["server_fields"], []

    def _capture(_client, _names):
        backup = state["backup"]
        if isinstance(backup, Exception):
            raise backup
        return backup

    monkeypatch.setattr(service, "gather_server_fields", _gather)
    monkeypatch.setattr(service, "capture_target_backup", _capture)
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


def test_publish_captures_backup_before_deploy(monkeypatch, _stub_live):
    _stub_generate(monkeypatch, _result(("Contact.yaml", _CLEAN_YAML)))
    _stub_live["backup"] = {"entities": {"Contact": {"fields": {}}}}
    monkeypatch.setattr(
        service, "deploy_pipeline", lambda *a, **k: DeployOutcome(report=object())
    )
    res = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _FakeDesignClient(),
        api_key="K",
        rendered_at="2026-06-21T00:00:00",
    )
    assert res.aborted is False
    assert res.backup == {"entities": {"Contact": {"fields": {}}}}
    assert res.programs[0].deployed is True


def test_publish_aborts_when_backup_fails(monkeypatch, _stub_live):
    _stub_generate(monkeypatch, _result(("Contact.yaml", _CLEAN_YAML)))
    _stub_live["backup"] = service.BackupCaptureError("no scopes")
    deployed = []
    monkeypatch.setattr(
        service, "deploy_pipeline",
        lambda *a, **k: deployed.append(1) or DeployOutcome(report=object()),
    )
    res = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _FakeDesignClient(),
        api_key="K",
        rendered_at="2026-06-21T00:00:00",
    )
    assert res.aborted is True
    assert "no scopes" in res.abort_reason
    assert res.backup is None
    assert deployed == []  # never wrote to the target
    assert all(not p.deployed for p in res.programs)
    assert res.verification is None  # no verify on an aborted publish


def test_publish_allow_no_backup_overrides_gate(monkeypatch, _stub_live):
    _stub_generate(monkeypatch, _result(("Contact.yaml", _CLEAN_YAML)))
    _stub_live["backup"] = service.BackupCaptureError("no scopes")
    monkeypatch.setattr(
        service, "deploy_pipeline", lambda *a, **k: DeployOutcome(report=object())
    )
    res = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _FakeDesignClient(),
        api_key="K",
        rendered_at="2026-06-21T00:00:00",
        allow_no_backup=True,
    )
    assert res.aborted is False
    assert res.backup is None
    assert res.programs[0].deployed is True


def test_publish_no_backup_on_preview(monkeypatch, _stub_live):
    _stub_generate(monkeypatch, _result(("Contact.yaml", _CLEAN_YAML)))
    captured = []
    monkeypatch.setattr(
        service, "capture_target_backup",
        lambda *a, **k: captured.append(1) or {},
    )
    monkeypatch.setattr(
        service, "deploy_pipeline", lambda *a, **k: DeployOutcome(report=object())
    )
    res = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _FakeDesignClient(),
        api_key="K",
        rendered_at="2026-06-21T00:00:00",
        preview=True,
    )
    assert captured == []  # preview never backs up
    assert res.backup is None


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


# -- governed per-instance settings (PI-406 / REQ-485) ------------------------


class _SettingsDesignClient(_FakeDesignClient):
    """Empty design except one confirmed governed setting with a declared
    value for INST-001 and a value row for some other instance."""

    def list_system_settings(self):
        return [
            {
                "system_setting_identifier": "SET-001",
                "system_setting_key": "orgName",
                "system_setting_status": "confirmed",
            },
            {
                "system_setting_identifier": "SET-002",
                "system_setting_key": "oldKey",
                "system_setting_status": "candidate",
            },
        ]

    def list_system_setting_values(self, instance_identifier):
        assert instance_identifier == "INST-001"
        return [
            {"system_setting_identifier": "SET-001", "value": "Cleveland"},
            # A value row for a non-confirmed setting must not be applied.
            {"system_setting_identifier": "SET-002", "value": "X"},
        ]


def test_declared_setting_values_maps_confirmed_keys_only():
    declared = service.declared_setting_values(
        _SettingsDesignClient(), "INST-001"
    )
    assert declared == {"orgName": "Cleveland"}


def test_publish_applies_declared_settings_and_reports(monkeypatch, _stub_live):
    from espo_impl.core.models import SettingsResult, SettingsStatus

    _stub_generate(monkeypatch, _result(("Contact.yaml", _CLEAN_YAML)))
    monkeypatch.setattr(
        service, "deploy_pipeline",
        lambda *a, **k: DeployOutcome(report=object()),
    )
    seen = {}

    class _FakeManager:
        def __init__(self, client, output_fn):
            self._ofn = output_fn

        def apply_values(self, declared, dry_run=False):
            seen["declared"] = declared
            seen["dry_run"] = dry_run
            self._ofn("[UPDATE]  applied", "green")
            return SettingsResult(
                entity="CNetworkStandard",
                status=SettingsStatus.UPDATED,
                changes=sorted(declared),
            )

    monkeypatch.setattr(service, "SystemSettingsManager", _FakeManager)
    res = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _SettingsDesignClient(),
        api_key="K",
        rendered_at="2026-08-31T00:00:00",
    )
    assert seen["declared"] == {"orgName": "Cleveland"}
    assert seen["dry_run"] is False
    assert res.settings is not None
    assert res.settings.status is SettingsStatus.UPDATED
    assert res.settings.changes == ["orgName"]
    assert res.settings_log == [("[UPDATE]  applied", "green")]


def test_publish_preview_dry_runs_the_settings_apply(monkeypatch, _stub_live):
    from espo_impl.core.models import SettingsResult, SettingsStatus

    _stub_generate(monkeypatch, _result(("Contact.yaml", _CLEAN_YAML)))
    monkeypatch.setattr(
        service, "deploy_pipeline",
        lambda *a, **k: DeployOutcome(report=object()),
    )
    seen = {}

    class _FakeManager:
        def __init__(self, client, output_fn):
            pass

        def apply_values(self, declared, dry_run=False):
            seen["dry_run"] = dry_run
            return SettingsResult(
                entity="CNetworkStandard", status=SettingsStatus.UPDATED
            )

    monkeypatch.setattr(service, "SystemSettingsManager", _FakeManager)
    service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _SettingsDesignClient(),
        api_key="K",
        rendered_at="2026-08-31T00:00:00",
        preview=True,
    )
    assert seen["dry_run"] is True


def test_publish_with_nothing_declared_reports_no_settings(monkeypatch, _stub_live):
    _stub_generate(monkeypatch, _result(("Contact.yaml", _CLEAN_YAML)))
    monkeypatch.setattr(
        service, "deploy_pipeline",
        lambda *a, **k: DeployOutcome(report=object()),
    )
    res = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _FakeDesignClient(),
        api_key="K",
        rendered_at="2026-08-31T00:00:00",
    )
    assert res.settings is None
    assert res.settings_log == []


# -- plan identity (PI-411 / REQ-496) -----------------------------------------


def _fp(artifacts, *, target="INST-001", values=None):
    return service.plan_fingerprint_for(
        artifacts, target_identifier=target, setting_values=values or {}
    )


def test_plan_fingerprint_ignores_the_provenance_header():
    """Two derivations of the same design at different moments are the same
    plan; the rendered-at header must not move the fingerprint."""
    body = "entities:\n  Contact:\n    fields: []\n"
    fp1 = _fp([("Contact.yaml", "# header\n# Rendered at T1.\n" + body)])
    fp2 = _fp([("Contact.yaml", "# header\n# Rendered at T2.\n" + body)])
    assert fp1 == fp2
    fp3 = _fp([("Contact.yaml", "# header\n" + body + "  extra: 1\n")])
    assert fp3 != fp1


def test_a_changed_setting_value_moves_the_plan():
    """The run writes declared setting values too (PI-406), so a governed
    value changed between showing and applying is a moved plan (REQ-496) —
    without this, an apply writes a value the operator was never shown."""
    art = [("Contact.yaml", "entities: {}\n")]
    shown = _fp(art, values={"applicationName": "Lakeside"})
    changed = _fp(art, values={"applicationName": "Riverside"})
    assert shown != changed
    assert shown == _fp(art, values={"applicationName": "Lakeside"})


def test_the_target_instance_is_part_of_the_plan():
    """A fingerprint approved for one instance approves nothing on another."""
    art = [("Contact.yaml", "entities: {}\n")]
    assert _fp(art, target="INST-001") != _fp(art, target="INST-003")


def test_preview_hands_the_operator_a_plan_fingerprint(monkeypatch, _stub_live):
    _stub_generate(monkeypatch, _result(("Contact.yaml", _CLEAN_YAML)))
    monkeypatch.setattr(
        service, "deploy_pipeline",
        lambda *a, **k: DeployOutcome(report=object()),
    )
    res = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _FakeDesignClient(),
        api_key="K",
        rendered_at="2026-08-31T00:00:00",
        preview=True,
    )
    assert res.plan_fingerprint
    assert res.plan_moved is False


def test_a_moved_plan_refuses_and_reports_the_new_plan(monkeypatch, _stub_live):
    _stub_generate(monkeypatch, _result(("Contact.yaml", _CLEAN_YAML)))
    deployed = []
    monkeypatch.setattr(
        service, "deploy_pipeline",
        lambda *a, **k: deployed.append(1) or DeployOutcome(report=object()),
    )
    res = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _FakeDesignClient(),
        api_key="K",
        rendered_at="2026-08-31T00:00:00",
        expected_plan_fingerprint="stale-fingerprint",
    )
    assert res.aborted is True
    assert res.plan_moved is True
    assert res.plan_fingerprint in res.abort_reason
    assert deployed == []
    assert res.backup is None
    assert all(not p.deployed for p in res.programs)


def test_a_matching_plan_fingerprint_lets_the_apply_proceed(
    monkeypatch, _stub_live
):
    _stub_generate(monkeypatch, _result(("Contact.yaml", _CLEAN_YAML)))
    monkeypatch.setattr(
        service, "deploy_pipeline",
        lambda *a, **k: DeployOutcome(report=object()),
    )
    preview = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _FakeDesignClient(),
        api_key="K",
        rendered_at="2026-08-31T00:00:00",
        preview=True,
    )
    res = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _FakeDesignClient(),
        api_key="K",
        rendered_at="2026-08-31T01:00:00",
        expected_plan_fingerprint=preview.plan_fingerprint,
    )
    assert res.aborted is False
    assert res.plan_moved is False
    assert all(p.deployed for p in res.programs)


# -- design-version stamp (PI-411 / REQ-495, DEC-980, DEC-981) ----------------


def _stamp_capturing_manager(monkeypatch, *, fail_settings=False):
    """Replace the manager class; returns the dict recording stamp writes."""
    from espo_impl.core.models import SettingsResult, SettingsStatus

    seen = {}

    class _FakeManager:
        def __init__(self, client, output_fn):
            self._ofn = output_fn

        def apply_values(self, declared, dry_run=False):
            return SettingsResult(
                entity="CNetworkStandard",
                status=(
                    SettingsStatus.ERROR if fail_settings
                    else SettingsStatus.UPDATED
                ),
                error="HTTP 500" if fail_settings else None,
            )

        def write_stamp(self, *, standard_version, plan_fingerprint,
                        dry_run=False):
            seen["standard_version"] = standard_version
            seen["plan_fingerprint"] = plan_fingerprint
            self._ofn("[UPDATE]  stamp ... OK", "green")
            return SettingsResult(
                entity="CNetworkStandard",
                status=SettingsStatus.UPDATED,
                changes=["planFingerprint", "standardVersion"],
            )

    monkeypatch.setattr(service, "SystemSettingsManager", _FakeManager)
    return seen


def _publish_under_release(
    monkeypatch, _stub_live, *, design_client=None, verified=True, **kwargs
):
    _stub_generate(monkeypatch, _result(("Contact.yaml", _CLEAN_YAML)))
    monkeypatch.setattr(
        service, "deploy_pipeline",
        lambda *a, **k: DeployOutcome(report=object()),
    )
    if verified:
        monkeypatch.setattr(
            service, "verify_publish",
            lambda *a, **k: service.VerificationResult(
                ran=True, conclusive=True, all_present=True
            ),
        )
    return service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        design_client or _FakeDesignClient(),
        api_key="K",
        rendered_at="2026-08-31T00:00:00",
        release_identifier="REL-045",
        **kwargs,
    )


def test_a_fully_successful_release_publish_writes_the_stamp(
    monkeypatch, _stub_live
):
    seen = _stamp_capturing_manager(monkeypatch)
    res = _publish_under_release(monkeypatch, _stub_live)
    assert seen["standard_version"] == "REL-045"
    assert seen["plan_fingerprint"] == res.plan_fingerprint
    assert res.stamp is not None
    assert res.stamp_log


def test_a_publish_outside_a_release_never_writes_the_stamp(
    monkeypatch, _stub_live
):
    seen = _stamp_capturing_manager(monkeypatch)
    _stub_generate(monkeypatch, _result(("Contact.yaml", _CLEAN_YAML)))
    monkeypatch.setattr(
        service, "deploy_pipeline",
        lambda *a, **k: DeployOutcome(report=object()),
    )
    res = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _FakeDesignClient(),
        api_key="K",
        rendered_at="2026-08-31T00:00:00",
    )
    assert "standard_version" not in seen
    assert res.stamp is None


def test_a_preview_never_writes_the_stamp(monkeypatch, _stub_live):
    seen = _stamp_capturing_manager(monkeypatch)
    res = _publish_under_release(monkeypatch, _stub_live, preview=True)
    assert "standard_version" not in seen
    assert res.stamp is None


def test_an_unverified_result_leaves_the_previous_stamp(
    monkeypatch, _stub_live
):
    """DEC-981: succeeded_with_issues must not advance the stamp — the
    verification explicitly could not confirm the result."""
    seen = _stamp_capturing_manager(monkeypatch)
    # verified=False leaves the real verify running against an empty target,
    # which is exactly the could-not-confirm outcome DEC-981 names.
    res = _publish_under_release(monkeypatch, _stub_live, verified=False)
    assert service.publish_run_status(res) == "succeeded_with_issues"
    assert "standard_version" not in seen
    assert res.stamp is None


def test_a_failed_settings_apply_leaves_the_previous_stamp(
    monkeypatch, _stub_live
):
    seen = _stamp_capturing_manager(monkeypatch, fail_settings=True)
    res = _publish_under_release(
        monkeypatch, _stub_live, design_client=_SettingsDesignClient()
    )
    assert service.publish_run_status(res) == "failed"
    assert "standard_version" not in seen
    assert res.stamp is None


# -- additive-only automatic apply (PI-411 / REQ-497, DEC-982) ----------------

_NARROWING_YAML = """\
version: "1.1"
description: "drops an option the live field permits"
entities:
  Contact:
    fields:
      - name: stage
        type: enum
        label: Stage
        options:
          - open
"""


def _live_contact_defs(_stub_live, defs):
    _stub_live["entity_defs"]["Contact"] = defs


def test_an_automatic_apply_refuses_a_narrowing_by_name(
    monkeypatch, _stub_live
):
    """DEC-982: a publish without an approved plan fingerprint is automatic,
    and dropping a value the live field permits is a narrowing."""
    _stub_generate(monkeypatch, _result(("Contact.yaml", _NARROWING_YAML)))
    deployed = []
    monkeypatch.setattr(
        service, "deploy_pipeline",
        lambda *a, **k: deployed.append(1) or DeployOutcome(report=object()),
    )
    _live_contact_defs(_stub_live, {
        "cStage": {"type": "enum", "options": ["open", "closed"]},
    })
    res = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _FakeDesignClient(),
        api_key="K",
        rendered_at="2026-08-31T00:00:00",
    )
    assert res.aborted is True
    assert deployed == []
    assert len(res.declined_changes) == 1
    declined = res.declined_changes[0]
    assert declined["kind"] == "narrowing"
    assert "Contact.stage" in declined["construct"]
    assert declined["construct"] in res.abort_reason
    assert "REQ-497" in res.abort_reason


def test_the_approved_plan_fingerprint_is_the_reviewed_run(
    monkeypatch, _stub_live
):
    """The same narrowing plan proceeds when the operator was shown it — the
    preview-then-approve flow is the separately triggered reviewed run."""
    _stub_generate(monkeypatch, _result(("Contact.yaml", _NARROWING_YAML)))
    monkeypatch.setattr(
        service, "deploy_pipeline",
        lambda *a, **k: DeployOutcome(report=object()),
    )
    _live_contact_defs(_stub_live, {
        "cStage": {"type": "enum", "options": ["open", "closed"]},
    })
    common = {"api_key": "K", "rendered_at": "2026-08-31T00:00:00"}
    preview = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _FakeDesignClient(), preview=True, **common,
    )
    res = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _FakeDesignClient(),
        expected_plan_fingerprint=preview.plan_fingerprint,
        **common,
    )
    assert res.aborted is False
    assert res.declined_changes == []
    assert all(p.deployed for p in res.programs)


def test_an_automatic_apply_refuses_a_type_change(monkeypatch, _stub_live):
    _stub_generate(monkeypatch, _result(("Contact.yaml", _CLEAN_YAML)))
    monkeypatch.setattr(
        service, "deploy_pipeline",
        lambda *a, **k: DeployOutcome(report=object()),
    )
    _live_contact_defs(_stub_live, {"cNickName": {"type": "enum"}})
    res = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _FakeDesignClient(),
        api_key="K",
        rendered_at="2026-08-31T00:00:00",
    )
    assert res.aborted is True
    assert [d["kind"] for d in res.declined_changes] == ["type_change"]


def test_an_automatic_apply_refuses_an_entity_deletion(
    monkeypatch, _stub_live
):
    yaml = """\
version: "1.1"
description: "deletes"
entities:
  Widget:
    action: delete
"""
    _stub_generate(monkeypatch, _result(("Widget.yaml", yaml)))
    monkeypatch.setattr(
        service, "deploy_pipeline",
        lambda *a, **k: DeployOutcome(report=object()),
    )
    res = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _FakeDesignClient(),
        api_key="K",
        rendered_at="2026-08-31T00:00:00",
    )
    assert res.aborted is True
    assert [d["kind"] for d in res.declined_changes] == ["removal"]


def test_a_purely_additive_automatic_apply_proceeds(monkeypatch, _stub_live):
    """A brand-new field on a live entity, and widened options, both pass."""
    _stub_generate(monkeypatch, _result(("Contact.yaml", _CLEAN_YAML)))
    monkeypatch.setattr(
        service, "deploy_pipeline",
        lambda *a, **k: DeployOutcome(report=object()),
    )
    _live_contact_defs(_stub_live, {"other": {"type": "varchar"}})
    res = service.publish(
        {"instance_identifier": "INST-001", "instance_url": "https://x"},
        _FakeDesignClient(),
        api_key="K",
        rendered_at="2026-08-31T00:00:00",
    )
    assert res.aborted is False
    assert all(p.deployed for p in res.programs)


# --- generate_design_yaml reads every list the adapter's run() reads ---------

class _RecordingDesignClient:
    """Every ``list_*`` returns what it was seeded with, or nothing — and
    records which readers the service actually asked, which is the point."""

    def __init__(self, **lists):
        self._lists = lists
        self.asked: list[str] = []

    def __getattr__(self, name):
        if not name.startswith("list_"):
            raise AttributeError(name)

        def _reader(*args, **kwargs):
            self.asked.append(name)
            return list(self._lists.get(name[len("list_"):], []))

        return _reader


def test_generate_design_yaml_reads_the_same_lists_as_the_adapter_run():
    """PI-417: the publish path read nine design lists while the adapter's own
    ``run`` read eleven, so a publish silently omitted the field-permission,
    field-visibility and security blocks. The two must stay in step — this
    pins the set, not a count, so a new reader shows up by name."""
    from crmbuilder_v2.adapters.espocrm.client import DesignClient

    client = _RecordingDesignClient()
    service.generate_design_yaml(client, rendered_at="2026-09-03T00:00:00Z")

    protocol = {
        m for m in dir(DesignClient)
        if m.startswith("list_") and m != "list_system_settings"
        and m != "list_system_setting_values"
    }
    assert set(client.asked) == protocol


def test_generate_design_yaml_renders_a_confirmed_layout_on_its_entity():
    """PI-427 (REQ-519), the LSN-071 rule: a new emitted block needs a test
    that starts at the publish path's generation and finds the block in the
    artifact — the unit on ``build_program_model`` and the validation gate
    can both be green while the publish renders nothing."""
    import yaml as pyyaml

    from tests.crmbuilder_v2.adapters.test_espocrm_model import _entity, _field

    client = _RecordingDesignClient(
        entities=[_entity()],
        fields=[_field()],
        layouts=[{
            "layout_identifier": "LAY-001",
            "layout_entity_identifier": "ENT-001",
            "layout_type": "detail",
            "layout_content": [
                {"label": "Overview", "rows": [[{"name": "name"}, {"name": "mentorStatus"}]]}
            ],
            "layout_status": "confirmed",
            "layout_notes": None,
        }],
    )
    result = service.generate_design_yaml(client, rendered_at="2026-09-03T00:00:00Z")
    program = next(p for p in result.programs if p.filename != "security.yaml")
    # Read with the deploy engine's dialect, never the writer's (LSN-070).
    loaded = pyyaml.safe_load(program.content)
    block = loaded["entities"]["Mentor Application"]["layout"]
    assert block == {
        "detail": {"panels": [{"label": "Overview", "rows": [["name", "mentorStatus"]]}]}
    }
    assert "list_layouts" in client.asked


def test_generate_design_yaml_renders_the_security_program_and_filtered_tabs():
    """The consequence stated as an outcome: a confirmed role reaches
    ``security.yaml`` and a confirmed filtered tab reaches its entity's block
    through the very path a publish uses."""
    from tests.crmbuilder_v2.adapters.test_espocrm_model import _entity, _field

    client = _RecordingDesignClient(
        entities=[_entity()],
        fields=[_field()],
        roles=[{"role_identifier": "ROL-001", "role_name": "Mentor",
                "role_status": "confirmed"}],
        filtered_tabs=[{
            "filtered_tab_identifier": "FTB-001",
            "filtered_tab_entity_identifier": "ENT-001",
            "filtered_tab_label": "Approved",
            "filtered_tab_filter": {"field": "FLD-001", "op": "eq", "value": "a"},
            "filtered_tab_status": "confirmed",
        }],
    )
    result = service.generate_design_yaml(client, rendered_at="2026-09-03T00:00:00Z")
    by_name = {a.filename: a.content for a in result.programs}
    assert "security.yaml" in by_name
    assert "- name: Mentor" in by_name["security.yaml"]
    assert "filteredTabs:" in by_name["Mentor-Application.yaml"]
    assert "scope: Approved" in by_name["Mentor-Application.yaml"]

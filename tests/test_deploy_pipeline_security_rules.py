"""PI-051 — field-level security rules in the deploy pipeline (Section 12.7).

Proves the Step-11 security sub-phase wiring: field permissions run, their
results reach the report, a NOT_SUPPORTED visibility rule surfaces in the
MANUAL CONFIGURATION REQUIRED block without failing the step, and a rule
ERROR downgrades the security step to FAILED.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.comparator import FieldComparator
from espo_impl.core.deploy_pipeline import DeployManagers, deploy_pipeline
from espo_impl.core.field_manager import FieldManager
from espo_impl.core.models import (
    FieldPermissionSpec,
    FieldVisibilitySpec,
    InstanceProfile,
    ProgramFile,
    SecurityRuleResult,
    SecurityRuleStatus,
    StepStatus,
)


def _mock_client() -> MagicMock:
    client = MagicMock(spec=EspoAdminClient)
    client.profile = MagicMock(spec=InstanceProfile)
    client.profile.name = "Target"
    client.profile.url = "https://t.example.org"
    client.profile.api_url = "https://t.example.org/api/v1"
    return client


class _FakeSecurityRuleManager:
    """Records its call and returns canned per-rule results."""

    def __init__(self, client, output_fn):
        self.output_fn = output_fn

    def process_security_rules(
        self, field_permissions, field_visibility, dry_run=False
    ):
        results: list[SecurityRuleResult] = []
        for v in field_visibility:
            results.append(SecurityRuleResult(
                role=v.role, entity=v.entity, field=v.field,
                status=SecurityRuleStatus.NOT_SUPPORTED,
            ))
        for p in field_permissions:
            results.append(SecurityRuleResult(
                role=p.role, entity=p.entity, field=p.field,
                status=SecurityRuleStatus.CREATED,
            ))
        return results


class _ErroringSecurityRuleManager(_FakeSecurityRuleManager):
    def process_security_rules(
        self, field_permissions, field_visibility, dry_run=False
    ):
        return [
            SecurityRuleResult(
                role=p.role, entity=p.entity, field=p.field,
                status=SecurityRuleStatus.ERROR, error="boom",
            )
            for p in field_permissions
        ]


def _program() -> ProgramFile:
    return ProgramFile(
        version="1.0",
        description="security rules",
        entities=[],
        field_permissions=[
            FieldPermissionSpec("Mentor Role", "CMentorProfile",
                                "mentorStatus", "read_only"),
        ],
        field_visibility=[
            FieldVisibilitySpec("Mentor Role", "CMentorProfile",
                                "internalNote", visible=False),
        ],
    )


def _run(program, manager_cls):
    client = _mock_client()
    log: list[tuple[str, str]] = []
    out = lambda m, c: log.append((m, c))  # noqa: E731
    field_mgr = FieldManager(client, FieldComparator(), out)
    managers = DeployManagers(security_rule=manager_cls)
    outcome = deploy_pipeline(program, client, field_mgr, out, managers=managers)
    return outcome, log


def test_field_permissions_run_and_reach_report():
    outcome, log = _run(_program(), _FakeSecurityRuleManager)

    by_name = {sr.step_name: sr.status for sr in outcome.report.step_results}
    assert by_name["security"] == StepStatus.OK

    # Results reach both the report and the outcome.
    statuses = [r.status for r in outcome.report.security_rule_results]
    assert SecurityRuleStatus.CREATED in statuses
    assert SecurityRuleStatus.NOT_SUPPORTED in statuses
    assert outcome.security_rule_results == outcome.report.security_rule_results


def test_not_supported_visibility_surfaces_in_manual_config():
    _outcome, log = _run(_program(), _FakeSecurityRuleManager)
    text = "\n".join(m for m, _ in log)
    assert "MANUAL CONFIGURATION REQUIRED" in text
    assert "Section 12.7 field-level visibility" in text
    assert "CMentorProfile.internalNote" in text


def test_rule_error_fails_security_step():
    outcome, _log = _run(_program(), _ErroringSecurityRuleManager)
    by_name = {sr.step_name: sr.status for sr in outcome.report.step_results}
    assert by_name["security"] == StepStatus.FAILED
    sr = next(s for s in outcome.report.step_results if s.step_name == "security")
    assert "field-permission error(s)" in (sr.error or "")

"""The unattended conformance entry point — PI-410 (REQ-492/493/494/500).

Drives ``run_check`` against a stubbed API: exit statuses map to verdicts, the
machine-readable result reaches stdout on every outcome including failures,
live mode reads the instance first, and an override lets one deploy through
without touching the verdict.
"""

from __future__ import annotations

import io
import json

import pytest
from crmbuilder_v2 import conformance_check
from crmbuilder_v2.publish.check import CheckError


class _StubApi:
    def __init__(self, verdict="conformant", audit_fails=False,
                 override=None):
        self.verdict = verdict
        self.audit_fails = audit_fails
        self.override = override
        self.calls: list[str] = []

    def post(self, path):
        self.calls.append(("POST", path))
        if path.endswith("/audit"):
            if self.audit_fails:
                raise CheckError("introspection failed: no credentials")
            return {"completion": {"status": "complete"}}
        if path.endswith("/conformance-overrides/consume"):
            if self.override is None:
                raise CheckError("HTTP 404")
            return self.override
        raise AssertionError(path)

    def get(self, path):
        self.calls.append(("GET", path))
        assert path.endswith("/conformance")
        return {
            "instance": "INST-001",
            "status": self.verdict,
            "counts": {"match": 1, "drift": 0, "unknown": 0,
                       "unwritable_drift": 0},
            "entries": [],
        }


@pytest.fixture
def _wire(monkeypatch):
    def wire(api):
        monkeypatch.setattr(
            conformance_check, "_settings",
            lambda base_url, env_file: ("http://x", None),
        )
        monkeypatch.setattr(
            conformance_check, "_Api", lambda url, token, engagement: api
        )
        return api
    return wire


def _run(api, **kwargs):
    out, err = io.StringIO(), io.StringIO()
    code = conformance_check.run_check(
        instance="INST-001", engagement="ENG-002", base_url=None,
        env_file="/nonexistent", out=out, err=err, **kwargs,
    )
    return code, json.loads(out.getvalue()), err.getvalue()


def test_a_conformant_instance_exits_zero_after_a_live_read(_wire):
    api = _wire(_StubApi(verdict="conformant"))
    code, result, _ = _run(api)
    assert code == 0
    assert result["status"] == "conformant"
    assert result["run_mode"] == "live"
    # REQ-500: the live run read the instance (the audit) before evaluating.
    assert ("POST", "/instances/INST-001/audit") in api.calls


def test_each_blocking_status_has_its_own_exit(_wire):
    for verdict, expected in (
        ("drifted", 1),
        ("unable_to_be_checked", 2),
        ("named_but_unwritable", 3),
    ):
        api = _wire(_StubApi(verdict=verdict))
        code, result, _ = _run(api)
        assert (code, result["status"]) == (expected, verdict)


def test_stored_mode_skips_the_live_read_and_says_so(_wire):
    api = _wire(_StubApi())
    code, result, _ = _run(api, stored=True)
    assert code == 0
    assert result["run_mode"] == "stored"
    assert ("POST", "/instances/INST-001/audit") not in api.calls


def test_an_unreadable_instance_still_emits_a_result(_wire):
    """REQ-493: every run emits a machine-readable result, failures included."""
    api = _wire(_StubApi(audit_fails=True))
    code, result, _ = _run(api)
    assert code == 2
    assert result["status"] == "unable_to_be_checked"
    assert "could not be read" in result["reason"]


def test_an_override_lets_one_deploy_through_without_touching_the_verdict(
    _wire,
):
    api = _wire(_StubApi(
        verdict="drifted",
        override={"authorized_by": "Doug", "reason": "hotfix",
                  "consumed_at": "2026-09-01T00:00:00+00:00"},
    ))
    code, result, err = _run(api, use_override=True)
    assert code == 0  # the gate proceeds
    assert result["status"] == "drifted"  # the verdict is untouched (REQ-494)
    assert result["override"]["authorized_by"] == "Doug"
    assert "overridden" in err


def test_without_an_unspent_override_the_verdict_stands(_wire):
    api = _wire(_StubApi(verdict="drifted", override=None))
    code, result, _ = _run(api, use_override=True)
    assert code == 1
    assert "override" not in result


def test_overrides_are_never_consumed_unless_asked(_wire):
    api = _wire(_StubApi(
        verdict="drifted",
        override={"authorized_by": "Doug", "reason": "hotfix"},
    ))
    code, _, _ = _run(api)
    assert code == 1
    assert not any(
        path.endswith("/consume") for _m, path in api.calls
    )

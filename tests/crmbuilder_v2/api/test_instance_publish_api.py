"""Publish REST endpoint tests — PRJ-042 / PI-250 (REQ-287 + REQ-288).

Exercises the wiring of ``POST /instances/{id}/publish`` and
``/publish-validate``: target + keyring-credential resolution, the
source-only rejection, the validate_only flag propagation, and result
serialization. The publish *service* is stubbed here (it is unit-tested
separately) so these tests never touch a live target.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2 import secrets
from crmbuilder_v2.publish import service as publish_service
from crmbuilder_v2.publish.service import ProgramOutcome, PublishResult


@pytest.fixture(autouse=True)
def _keyring_in_memory(monkeypatch):
    monkeypatch.setenv(secrets.DISABLE_ENV_VAR, "1")
    secrets._reset_in_memory_store_for_tests()
    yield
    secrets._reset_in_memory_store_for_tests()


def _make_instance(client, *, role="target", secret="api-key"):
    body = {
        "instance_name": "Target",
        "instance_url": "https://t.example.org",
        "instance_role": role,
    }
    if secret is not None:
        body["secret"] = secret
    r = client.post("/instances", json=body)
    assert r.status_code == 201, r.text
    return r.json()["data"]["instance_identifier"]


def _fake_result(validate_only, *, backup=None, aborted=False):
    return PublishResult(
        engine="espocrm",
        target_instance="INST-001",
        validate_only=validate_only,
        validation_failed=False,
        programs=[]
        if aborted
        else [
            ProgramOutcome(
                filename="Contact.yaml", deployed=not validate_only
            )
        ],
        deferrals=[],
        manual_config=None,
        backup=backup,
        aborted=aborted,
        abort_reason="no scopes" if aborted else None,
    )


def test_publish_validate_only(client, monkeypatch):
    iid = _make_instance(client)
    captured = {}

    def fake_publish(rec, design_client, *, validate_only=False, **kw):
        captured["validate_only"] = validate_only
        captured["api_key"] = kw.get("api_key")
        return _fake_result(validate_only)

    monkeypatch.setattr(publish_service, "publish", fake_publish)
    r = client.post(f"/instances/{iid}/publish-validate")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["validate_only"] is True
    assert data["validation_failed"] is False
    assert data["programs"][0]["filename"] == "Contact.yaml"
    assert captured["validate_only"] is True
    # The keyring secret stored at create time was resolved and passed through.
    assert captured["api_key"] == "api-key"


def test_publish_deploys(client, monkeypatch):
    iid = _make_instance(client)
    captured = {}

    def fake_publish(rec, design_client, *, validate_only=False, **kw):
        captured["validate_only"] = validate_only
        return _fake_result(validate_only)

    monkeypatch.setattr(publish_service, "publish", fake_publish)
    r = client.post(f"/instances/{iid}/publish")
    assert r.status_code == 200, r.text
    assert captured["validate_only"] is False
    assert r.json()["data"]["programs"][0]["deployed"] is True


def test_publish_unknown_instance_404(client):
    r = client.post("/instances/INST-999/publish")
    assert r.status_code == 404


def test_publish_missing_credentials_422(client, monkeypatch):
    iid = _make_instance(client, secret=None)
    monkeypatch.setattr(
        publish_service, "publish",
        lambda *a, **k: pytest.fail("publish must not run without credentials"),
    )
    r = client.post(f"/instances/{iid}/publish")
    assert r.status_code == 422, r.text
    assert r.json()["errors"][0]["code"] == "missing_credentials"


def test_publish_source_only_rejected_422(client, monkeypatch):
    iid = _make_instance(client, role="source")
    monkeypatch.setattr(
        publish_service, "publish",
        lambda *a, **k: pytest.fail("publish must not run on a source-only target"),
    )
    r = client.post(f"/instances/{iid}/publish")
    assert r.status_code == 422, r.text
    assert r.json()["errors"][0]["code"] == "not_publishable"


def test_publish_preview(client, monkeypatch):
    iid = _make_instance(client)
    captured = {}

    def fake_publish(rec, design_client, *, preview=False, validate_only=False, **kw):
        captured["preview"] = preview
        result = _fake_result(validate_only=False)
        result.preview = preview
        return result

    monkeypatch.setattr(publish_service, "publish", fake_publish)
    r = client.post(f"/instances/{iid}/publish-preview")
    assert r.status_code == 200, r.text
    assert captured["preview"] is True
    assert r.json()["data"]["preview"] is True


def test_publish_scope_body_threaded(client, monkeypatch):
    iid = _make_instance(client)
    captured = {}

    def fake_publish(rec, design_client, *, scope=None, **kw):
        captured["scope"] = scope
        return _fake_result(validate_only=False)

    monkeypatch.setattr(publish_service, "publish", fake_publish)
    # An explicit subset is passed through as a set.
    r = client.post(
        f"/instances/{iid}/publish", json={"scope": ["Contact.yaml"]}
    )
    assert r.status_code == 200, r.text
    assert captured["scope"] == {"Contact.yaml"}


def test_publish_no_body_means_full_scope(client, monkeypatch):
    iid = _make_instance(client)
    captured = {}

    def fake_publish(rec, design_client, *, scope=None, **kw):
        captured["scope"] = scope
        return _fake_result(validate_only=False)

    monkeypatch.setattr(publish_service, "publish", fake_publish)
    r = client.post(f"/instances/{iid}/publish")
    assert r.status_code == 200, r.text
    assert captured["scope"] is None


# -- publish_run recording + backup gate (REQ-292 / REQ-293) -----------------


def test_publish_records_run(client, monkeypatch):
    iid = _make_instance(client)
    monkeypatch.setattr(
        publish_service, "publish",
        lambda *a, **k: _fake_result(
            validate_only=False, backup={"entities": {}}
        ),
    )
    r = client.post(f"/instances/{iid}/publish")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    # A real publish records a PUB-NNN run and reports the backup state.
    assert data["publish_run"] == "PUB-001"
    assert data["backup_captured"] is True
    assert data["aborted"] is False


def test_publish_aborted_records_run(client, monkeypatch):
    iid = _make_instance(client)
    monkeypatch.setattr(
        publish_service, "publish",
        lambda *a, **k: _fake_result(validate_only=False, aborted=True),
    )
    r = client.post(f"/instances/{iid}/publish")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["aborted"] is True
    assert data["backup_captured"] is False
    # The aborted attempt is still recorded in history.
    assert data["publish_run"] == "PUB-001"


def test_publish_allow_no_backup_threaded(client, monkeypatch):
    iid = _make_instance(client)
    captured = {}

    def fake_publish(rec, design_client, *, allow_no_backup=False, **kw):
        captured["allow_no_backup"] = allow_no_backup
        return _fake_result(validate_only=False)

    monkeypatch.setattr(publish_service, "publish", fake_publish)
    r = client.post(
        f"/instances/{iid}/publish", json={"allow_no_backup": True}
    )
    assert r.status_code == 200, r.text
    assert captured["allow_no_backup"] is True


def test_validate_does_not_record_run(client, monkeypatch):
    iid = _make_instance(client)
    monkeypatch.setattr(
        publish_service, "publish",
        lambda *a, **k: _fake_result(validate_only=True),
    )
    r = client.post(f"/instances/{iid}/publish-validate")
    assert r.status_code == 200, r.text
    assert "publish_run" not in r.json()["data"]


# --- REQ-481 / PI-402: a broken secret backend is a 422, never a 500 ----------


def test_publish_reports_422_when_no_secret_backend_is_reachable(client, monkeypatch):
    """The reported production failure: the droplet has no keyring backend, so
    resolving the target's credentials raised NoKeyringError uncaught and the
    publish returned an opaque 500. It must be the actionable 422 instead — and
    the message must name the real cause, not "no stored credentials"."""
    iid = _make_instance(client)

    def _boom(ref):
        raise secrets.SecretBackendError(
            "Cannot resolve the secret: this host has no OS keyring backend and "
            "CRMBUILDER_V2_SECRET_KEY is not set."
        )

    monkeypatch.setattr(secrets, "get_secret", _boom)
    r = client.post(f"/instances/{iid}/publish", json={})
    assert r.status_code == 422, r.text
    err = r.json()["errors"][0]
    assert err["code"] == "secret_backend_unavailable"
    assert "CRMBUILDER_V2_SECRET_KEY" in err["message"]


def test_publish_still_reports_missing_credentials_when_simply_unset(client, monkeypatch):
    """A reference that resolves nowhere is a missing credential, which must stay
    distinguishable from a host that cannot read secrets at all."""
    iid = _make_instance(client)

    def _miss(ref):
        raise KeyError(ref)

    monkeypatch.setattr(secrets, "get_secret", _miss)
    r = client.post(f"/instances/{iid}/publish", json={})
    assert r.status_code == 422, r.text
    assert r.json()["errors"][0]["code"] == "missing_credentials"


def test_creating_an_instance_reports_422_when_nothing_can_store_the_secret(
    client, monkeypatch
):
    """The write half of the same defect: put_secret raised at save time on a
    host with no keyring, surfacing as a 500 rather than a usable message."""
    def _boom(value, *, ref=None):
        raise secrets.SecretBackendError(
            "Cannot store the secret: this host has no OS keyring backend and "
            "CRMBUILDER_V2_SECRET_KEY is not set."
        )

    monkeypatch.setattr(secrets, "put_secret", _boom)
    r = client.post(
        "/instances",
        json={
            "instance_name": "Target",
            "instance_url": "https://t.example.org",
            "instance_role": "target",
            "secret": "api-key",
        },
    )
    assert r.status_code == 422, r.text
    assert r.json()["errors"][0]["code"] == "secret_backend_unavailable"


# -- the access fence on the whole-design route (REQ-521 / PI-466) -----------


def _access_section(*, removes=True, known=True):
    removal = {
        "attribute": "role_scope_access", "scope": "Contact",
        "action": "delete", "before": "all", "after": "no",
        "removes_access": True, "member_name": "Mentor",
        "description": "Mentor: Contact.delete all → no",
    }
    return {
        "target": "INST-001", "assessed": True, "known": known,
        "reason": None if known else "could not read the target's roles (HTTP 500)",
        "roles": [], "teams": [],
        "changes": [removal] if removes else [],
        "removals": [removal] if removes else [],
        "removes_access": removes, "requires_confirmation": True,
        "summary": "Publishing the security program to INST-001 changes 1 "
        "access setting(s) across 1 role(s), 1 of which take access away.",
    }


def _fake_publish_with_fence(captured):
    """A service double that behaves as the real fence does on the flags it
    is handed, so the route's wiring of them is what gets exercised."""

    def fake_publish(rec, design_client, *, preview=False, validate_only=False,
                     expected_plan_fingerprint=None,
                     confirm_access_removal=False, **kw):
        captured.update(
            preview=preview,
            expected_plan_fingerprint=expected_plan_fingerprint,
            confirm_access_removal=confirm_access_removal,
        )
        result = _fake_result(validate_only=False)
        result.preview = preview
        result.plan_fingerprint = "fp-1"
        result.access = _access_section()
        if preview:
            return result
        if expected_plan_fingerprint is None and not confirm_access_removal:
            result.aborted = True
            result.programs = []
            result.declined_changes = [{
                "construct": "role Mentor (security.yaml)", "kind": "removal",
                "reason": "takes away access the instance currently grants: "
                "Mentor: Contact.delete all → no",
            }]
            result.abort_reason = "declined 1 change(s): role Mentor"
        elif not confirm_access_removal:
            result.aborted = True
            result.programs = []
            result.access_removal_unconfirmed = True
            result.abort_reason = (
                "This publish removes access the instance currently grants "
                "and is never applied automatically; confirm the removal "
                "separately (confirm_access_removal): "
                "Mentor: Contact.delete all → no"
            )
        return result

    return fake_publish


def test_the_preview_response_carries_the_access_section(client, monkeypatch):
    iid = _make_instance(client)
    monkeypatch.setattr(publish_service, "publish", _fake_publish_with_fence({}))
    r = client.post(f"/instances/{iid}/publish-preview")
    assert r.status_code == 200, r.text
    access = r.json()["data"]["access"]
    assert access["removes_access"] is True
    assert access["removals"][0]["description"] == "Mentor: Contact.delete all → no"


def test_an_automatic_publish_that_lowers_access_is_declined_by_name(
    client, monkeypatch
):
    iid = _make_instance(client)
    monkeypatch.setattr(publish_service, "publish", _fake_publish_with_fence({}))
    r = client.post(f"/instances/{iid}/publish")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["aborted"] is True
    assert data["declined_changes"][0]["kind"] == "removal"
    assert "Contact.delete all → no" in data["declined_changes"][0]["reason"]
    assert data["access"]["removes_access"] is True


def test_a_reviewed_publish_with_a_removal_is_409_without_the_word(
    client, monkeypatch
):
    iid = _make_instance(client)
    captured = {}
    monkeypatch.setattr(
        publish_service, "publish", _fake_publish_with_fence(captured)
    )
    r = client.post(f"/instances/{iid}/publish", json={
        "expected_plan_fingerprint": "fp-1",
    })
    assert r.status_code == 409, r.text
    assert r.json()["errors"][0]["code"] == "conflict"
    assert "removes access" in r.text
    assert "Mentor: Contact.delete all → no" in r.text
    # the refusal is a gate, not an outcome: no run is recorded
    assert client.get("/publish-runs").json()["data"] == []


def test_confirming_the_change_is_not_confirming_the_removal(client, monkeypatch):
    iid = _make_instance(client)
    monkeypatch.setattr(publish_service, "publish", _fake_publish_with_fence({}))
    r = client.post(f"/instances/{iid}/publish", json={
        "expected_plan_fingerprint": "fp-1", "confirm_access_change": True,
    })
    assert r.status_code == 409, r.text
    assert "confirm_access_removal" in r.text


def test_a_reviewed_publish_with_the_word_proceeds(client, monkeypatch):
    iid = _make_instance(client)
    captured = {}
    monkeypatch.setattr(
        publish_service, "publish", _fake_publish_with_fence(captured)
    )
    r = client.post(f"/instances/{iid}/publish", json={
        "expected_plan_fingerprint": "fp-1", "confirm_access_removal": True,
    })
    assert r.status_code == 200, r.text
    assert captured == {
        "preview": False,
        "expected_plan_fingerprint": "fp-1",
        "confirm_access_removal": True,
    }
    data = r.json()["data"]
    assert data["aborted"] is False
    assert data["access"]["removes_access"] is True
    assert data["publish_run"] is not None


def test_the_removal_word_without_a_reviewed_run_is_422(client, monkeypatch):
    """DEC-924: the word is not an incident-time switch that lets an
    automatic run revoke access — it needs the reviewed run's fingerprint."""
    iid = _make_instance(client)
    called = []
    monkeypatch.setattr(
        publish_service, "publish", lambda *a, **k: called.append(1)
    )
    r = client.post(f"/instances/{iid}/publish", json={
        "confirm_access_removal": True,
    })
    assert r.status_code == 422, r.text
    assert r.json()["errors"][0]["code"] == "removal_needs_reviewed_run"
    assert called == []

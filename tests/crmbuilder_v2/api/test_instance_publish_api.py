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


def _fake_result(validate_only):
    return PublishResult(
        engine="espocrm",
        target_instance="INST-001",
        validate_only=validate_only,
        validation_failed=False,
        programs=[
            ProgramOutcome(
                filename="Contact.yaml", deployed=not validate_only
            )
        ],
        deferrals=[],
        manual_config=None,
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

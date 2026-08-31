"""Per-instance stored feature selection — PI-444 (REQ-546 / DEC-976/977).

Covers the instance-record side (store, validate, patch, clear) and the
publish side: a bare publish resolves the stored selection to program
filenames automatically, an explicit per-run scope wins for that run only, a
validate-only run stays full-design but reports the resolution, and a
selection that matches nothing is refused rather than widened into a full
publish. The publish *service* is stubbed (unit-tested separately).
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


def _make_instance(client, **over):
    body = {
        "instance_name": "Chapter target",
        "instance_url": "https://t.example.org",
        "instance_role": "target",
        "secret": "api-key",
    }
    body.update(over)
    r = client.post("/instances", json=body)
    assert r.status_code == 201, r.text
    return r.json()["data"]


def _make_entity(client, name):
    r = client.post(
        "/entities",
        json={"entity_name": name, "entity_description": f"{name} record"},
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["entity_identifier"]


def _fake_result(validate_only=False):
    return PublishResult(
        engine="espocrm",
        target_instance="INST-001",
        validate_only=validate_only,
        validation_failed=False,
        programs=[
            ProgramOutcome(filename="Contact.yaml", deployed=not validate_only)
        ],
        deferrals=[],
        manual_config=None,
    )


# --- record side ------------------------------------------------------------


def test_create_with_selection_stores_it(client):
    data = _make_instance(
        client, instance_feature_selection=["ENT-001", "ENT-002"]
    )
    assert data["instance_feature_selection"] == ["ENT-001", "ENT-002"]


def test_create_without_selection_is_null(client):
    data = _make_instance(client)
    assert data["instance_feature_selection"] is None


def test_patch_sets_and_clears_selection(client):
    iid = _make_instance(client)["instance_identifier"]
    r = client.patch(
        f"/instances/{iid}",
        json={"instance_feature_selection": ["ENT-003", "ENT-003", "ENT-001"]},
    )
    assert r.status_code == 200, r.text
    # Duplicates dropped, order preserved.
    assert r.json()["data"]["instance_feature_selection"] == [
        "ENT-003",
        "ENT-001",
    ]
    r = client.patch(
        f"/instances/{iid}", json={"instance_feature_selection": None}
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["instance_feature_selection"] is None


def test_patch_empty_list_clears_selection(client):
    iid = _make_instance(
        client, instance_feature_selection=["ENT-001"]
    )["instance_identifier"]
    r = client.patch(
        f"/instances/{iid}", json={"instance_feature_selection": []}
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["instance_feature_selection"] is None


def test_bad_identifier_rejected(client):
    r = client.post(
        "/instances",
        json={
            "instance_name": "T",
            "instance_url": "https://t.example.org",
            "instance_feature_selection": ["Contact.yaml"],
        },
    )
    assert r.status_code == 422
    assert "invalid_entity_identifier" in r.text


def test_put_preserves_selection_round_trip(client):
    iid = _make_instance(
        client, instance_feature_selection=["ENT-001"]
    )["instance_identifier"]
    r = client.put(
        f"/instances/{iid}",
        json={
            "instance_name": "Renamed",
            "instance_url": "https://t.example.org",
            "instance_role": "target",
            "instance_feature_selection": ["ENT-002"],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["instance_feature_selection"] == ["ENT-002"]


# --- publish side (REQ-546) -------------------------------------------------


def test_bare_publish_resolves_stored_selection(client, monkeypatch):
    contact = _make_entity(client, "Contact")
    _make_entity(client, "Account")
    iid = _make_instance(
        client, instance_feature_selection=[contact]
    )["instance_identifier"]
    captured = {}

    def fake_publish(rec, design_client, *, scope=None, **kw):
        captured["scope"] = scope
        return _fake_result()

    monkeypatch.setattr(publish_service, "publish", fake_publish)
    r = client.post(f"/instances/{iid}/publish")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    # The stored selection resolved to the entity's generated filename.
    assert captured["scope"] == {"Contact.yaml"}
    assert data["scope_source"] == "stored_selection"
    assert data["feature_selection"]["filenames"] == ["Contact.yaml"]
    assert data["feature_selection"]["unresolved"] == []


def test_explicit_scope_overrides_stored_selection(client, monkeypatch):
    contact = _make_entity(client, "Contact")
    _make_entity(client, "Account")
    iid = _make_instance(
        client, instance_feature_selection=[contact]
    )["instance_identifier"]
    captured = {}

    def fake_publish(rec, design_client, *, scope=None, **kw):
        captured["scope"] = scope
        return _fake_result()

    monkeypatch.setattr(publish_service, "publish", fake_publish)
    r = client.post(
        f"/instances/{iid}/publish", json={"scope": ["Account.yaml"]}
    )
    assert r.status_code == 200, r.text
    # The per-run scope wins for this run only (REQ-546 acceptance).
    assert captured["scope"] == {"Account.yaml"}
    assert r.json()["data"]["scope_source"] == "explicit_scope"


def test_no_selection_publishes_full_design(client, monkeypatch):
    iid = _make_instance(client)["instance_identifier"]
    captured = {}

    def fake_publish(rec, design_client, *, scope=None, **kw):
        captured["scope"] = scope
        return _fake_result()

    monkeypatch.setattr(publish_service, "publish", fake_publish)
    r = client.post(f"/instances/{iid}/publish")
    assert r.status_code == 200, r.text
    assert captured["scope"] is None
    assert r.json()["data"]["scope_source"] == "full_design"


def test_validate_stays_full_design_but_reports_selection(
    client, monkeypatch
):
    contact = _make_entity(client, "Contact")
    iid = _make_instance(
        client, instance_feature_selection=[contact]
    )["instance_identifier"]
    captured = {}

    def fake_publish(rec, design_client, *, scope=None, **kw):
        captured["scope"] = scope
        return _fake_result(validate_only=True)

    monkeypatch.setattr(publish_service, "publish", fake_publish)
    r = client.post(f"/instances/{iid}/publish-validate")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    # Validation runs full-scope (the dialog's discovery surface)…
    assert captured["scope"] is None
    # …but the resolution is reported so the UI can pre-check its scope list.
    assert data["feature_selection"]["filenames"] == ["Contact.yaml"]


def test_selection_matching_nothing_refused(client, monkeypatch):
    # ENT-099 names no design entity: publishing must not silently widen to
    # the full design.
    iid = _make_instance(
        client, instance_feature_selection=["ENT-099"]
    )["instance_identifier"]
    monkeypatch.setattr(
        publish_service, "publish", lambda *a, **k: _fake_result()
    )
    r = client.post(f"/instances/{iid}/publish")
    assert r.status_code == 422
    assert "selection_matches_nothing" in r.text


def test_publish_run_records_selection_provenance(client, monkeypatch):
    contact = _make_entity(client, "Contact")
    iid = _make_instance(
        client, instance_feature_selection=[contact]
    )["instance_identifier"]
    monkeypatch.setattr(
        publish_service, "publish", lambda *a, **k: _fake_result()
    )
    r = client.post(f"/instances/{iid}/publish")
    assert r.status_code == 200, r.text
    run_id = r.json()["data"]["publish_run"]
    run = client.get(f"/publish-runs/{run_id}").json()["data"]
    assert run["publish_run_scope"] == ["Contact.yaml"]
    assert run["publish_run_summary"]["scope_source"] == "stored_selection"
    assert run["publish_run_summary"]["feature_selection"] == [contact]

"""End-to-end check for the publish path — REQ-483 / PI-404.

Publish broke in three independent places in August 2026, each invisible until
the one above it was fixed, and each found by a person reaching for the feature
rather than by a run:

1. **Credentials.** Instance secrets lived in an OS keyring the hosted service
   has no backend for; ``get_secret`` raised ``NoKeyringError`` uncaught and it
   surfaced as an opaque 500 (REQ-481 / DEC-913).
2. **Self-authentication.** The publish handlers built a ``RestDesignClient``
   against the service's own ``api_base_url`` and called its own endpoints. That
   client sends no ``Authorization`` header and the droplet runs
   ``PRINCIPAL_AUTH_ENABLED=true`` — 401, wrapped in a 500 (REQ-482 / DEC-914).
3. **Silent data loss.** ``RestDesignClient.list_fields`` filtered reference rows
   on ``relationship_kind`` while the API serializes that key as
   ``relationship``. The parent map was always empty, so every field came back
   with no parent entity. *Nothing raised.* The run was green and the YAML was
   hollow (LSN-052).

This module drives the real request handler — credential resolution, the
in-process design read, generation, parsing, validation — over a seeded design
against a faked target CRM, and asserts on **what was generated**, not on the
absence of an exception. A check that only asserted "publish returned 200" would
have missed the third defect entirely.

What this does **not** cover, stated rather than implied: the real write path.
``deploy_pipeline`` against a real EspoCRM, pre-publish backup capture and
post-publish verification are exercised only against the fake here. Closing that
needs a full publish to a disposable instance, deferred by DEC-915.
"""

from __future__ import annotations

import os
from urllib import request as urllib_request

import pytest
from crmbuilder_v2 import secrets
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import association, entity, field
from crmbuilder_v2.adapters.espocrm.client import RestDesignClient
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.publish import service as publish_service
from fastapi.testclient import TestClient

from tests.crmbuilder_v2.conftest import DEFAULT_ENGAGEMENT_ID


@pytest.fixture
def client(v2_env):
    """A TestClient on a fresh store. Declared here rather than borrowed from
    the api package's conftest — this check is meant to stand on its own."""
    test_client = TestClient(create_app())
    test_client.headers.update({"X-Engagement": DEFAULT_ENGAGEMENT_ID})
    return test_client

# The design the publish is generated from. Two confirmed entities carrying
# confirmed fields, an association between them, and one candidate field that
# the generator's scope filter must drop. Every expectation below is derived
# from this map rather than written out again — the same discipline the live
# check follows, because the real design moves.
SEEDED: dict[str, list[str]] = {
    "Mentor Application": ["application_status", "approver_name", "contact_email"],
    "Sponsor Organization": ["sponsor_tier"],
}

#: Field names the design declares but must never reach a program.
UNCONFIRMED = ["draft_note"]


def _seed_design() -> None:
    with session_scope() as s:
        org = entity.create_entity(
            s, name="Sponsor Organization", description="a sponsoring organization",
            kind="organization", status="confirmed",
        )["entity_identifier"]
        app = entity.create_entity(
            s, name="Mentor Application", description="a mentor application",
            kind="person", status="confirmed",
        )["entity_identifier"]

        field.create_field(
            s, field_belongs_to_entity_identifier=app, name="application_status",
            description="where the application is", type="enum", status="confirmed",
            options=[
                {"option_value": "submitted", "option_order": 1},
                {"option_value": "approved", "option_order": 2},
            ],
        )
        field.create_field(
            s, field_belongs_to_entity_identifier=app, name="approver_name",
            description="who approved it", type="text", status="confirmed",
        )
        field.create_field(
            s, field_belongs_to_entity_identifier=app, name="contact_email",
            description="primary email", type="text", status="confirmed",
            format="email", max_length=120,
        )
        field.create_field(
            s, field_belongs_to_entity_identifier=org, name="sponsor_tier",
            description="sponsorship level", type="text", status="confirmed",
        )
        # Candidate — unfinished design, never published.
        field.create_field(
            s, field_belongs_to_entity_identifier=org, name="draft_note",
            description="scratch", type="text", status="candidate",
        )
        association.create_association(
            s, name="Sponsor funds applications", source_entity=org,
            target_entity=app, cardinality="one_to_many", status="confirmed",
        )


class FakeTargetCrm:
    """The live target, faked at the boundary the publish service talks to.

    Deliberately small. The publish service reaches a target through exactly
    three reads — ``get_all_scopes``, ``get_entity_field_list``, ``get_all_links``
    — plus whatever the deploy pipeline drives, and the fake stops at the reads.
    It reports every seeded entity as already present with its declared fields,
    which is the state that lets validation resolve cross-program references.

    It does not emulate EspoCRM. Asserting against a rich fiction would be worse
    than asserting against a thin one: the value here is proving what the
    *pipeline* did, and the real target's behaviour is the disposable-instance
    layer's job (DEC-915).
    """

    def __init__(self, present: dict[str, list[str]] | None = None) -> None:
        self.present = SEEDED if present is None else present
        self.scope_status = 200

    def _espo(self, name: str) -> str:
        return name.replace(" ", "")

    def get_all_scopes(self):
        if self.scope_status != 200:
            return self.scope_status, None
        return 200, {
            f"C{self._espo(n)}": {"type": "Base", "custom": True}
            for n in self.present
        }

    def get_entity_field_list(self, espo_name: str):
        for natural, fields in self.present.items():
            if f"C{self._espo(natural)}" == espo_name:
                meta = {"name": {"type": "varchar"}}
                for f in fields:
                    meta[f"c{f[0].upper()}{f[1:]}"] = {"type": "varchar"}
                return 200, meta
        return 404, None

    def get_all_links(self, espo_name: str):
        return 200, {}


@pytest.fixture
def no_http_egress(monkeypatch):
    """Fail the test if anything tries to make an HTTP call out of the process.

    This is defect #2 as an assertion. The service reading its own design over
    HTTP is not merely slow — on a host with authentication enabled and no
    credential of its own it is a hard failure, and one that reproduces nowhere
    except that host. Rather than trying to recreate the host, forbid the shape:
    when the service is serving the request, no request may leave.
    """

    def _forbidden(*args, **kwargs):
        raise AssertionError(
            "the publish path made an outbound HTTP call while serving a "
            "request — it must read the design in-process via "
            "AccessDesignClient, never by calling its own API (REQ-482)"
        )

    monkeypatch.setattr(urllib_request, "urlopen", _forbidden)
    monkeypatch.setattr(RestDesignClient, "_get", _forbidden)


@pytest.fixture
def target(client, monkeypatch):
    """A publishable instance with stored credentials, pointed at a fake CRM.

    Returns ``(instance_identifier, FakeTargetCrm)``.
    """
    monkeypatch.setenv(secrets.DISABLE_ENV_VAR, "1")
    secrets._reset_in_memory_store_for_tests()
    crm = FakeTargetCrm()
    monkeypatch.setattr(publish_service, "EspoAdminClient", lambda profile: crm)
    resp = client.post(
        "/instances",
        json={
            "instance_name": "Fake target",
            "instance_url": "https://target.example.org",
            "instance_role": "target",
            "secret": "api-key-value",
        },
    )
    assert resp.status_code == 201, resp.text
    yield resp.json()["data"]["instance_identifier"], crm
    secrets._reset_in_memory_store_for_tests()


def _programs(client, identifier: str, path: str = "publish-validate") -> list[dict]:
    resp = client.post(f"/instances/{identifier}/{path}")
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["aborted"] is False, body["abort_reason"]
    assert body["validation_failed"] is False, [
        p["validation_errors"] for p in body["programs"]
    ]
    return body["programs"]


# -- the acceptance bar: all three defects -----------------------------------


def test_publish_validate_generates_every_seeded_field(
    v2_env, client, target, no_http_egress
):
    """Defect #3. Every confirmed field reaches the program for its entity.

    This is the assertion a status-only check cannot make. The number of
    programs follows the count of confirmed entities and is independent of
    fields, so a run that lost every field-to-entity edge produces the same
    programs, passes the same validation, and returns the same 200. Only the
    census distinguishes them: under the defect this is 4 fields expected and 0
    delivered.
    """
    _seed_design()
    identifier, _crm = target
    programs = _programs(client, identifier)

    by_entity = {
        ent: p for p in programs for ent in p["entities"]
    }
    assert set(by_entity) == set(SEEDED), (
        f"generated programs cover {sorted(by_entity)}, design has {sorted(SEEDED)}"
    )

    for ent, expected in SEEDED.items():
        got = by_entity[ent]["field_names"]
        assert by_entity[ent]["field_count"] == len(got)
        missing = [f for f in expected if _camel(f) not in got]
        assert not missing, (
            f"{ent} generated {got} — lost {missing}; a field that reaches no "
            "program is published as though it were never designed"
        )

    total = sum(p["field_count"] for p in programs)
    assert total == sum(len(v) for v in SEEDED.values())
    for name in UNCONFIRMED:
        assert not any(_camel(name) in p["field_names"] for p in programs), (
            f"{name} is candidate design and must not be published"
        )


def test_publish_validate_makes_no_outbound_http_call(
    v2_env, client, target, no_http_egress
):
    """Defect #2. The service reads its own design in-process.

    ``no_http_egress`` is the whole test: it turns any outbound call into a
    failure, so a handler that reverts to ``RestDesignClient`` against its own
    base URL fails here instead of on the droplet with a 401 inside a 500.
    """
    _seed_design()
    identifier, _crm = target
    assert _programs(client, identifier)


def test_publish_reports_a_backend_failure_as_unprocessable(
    v2_env, client, target, monkeypatch
):
    """Defect #1, the handling class. A host that cannot read secrets says so.

    The live check proves the droplet's key is configured; only the real
    deployment can. What is provable here is the shape of the failure: a backend
    that cannot answer must surface as an unprocessable entity naming the cause,
    never as the opaque 500 a bare ``NoKeyringError`` produced.
    """
    _seed_design()
    identifier, _crm = target

    def _no_backend(_ref):
        raise secrets.SecretBackendError("this host has no keyring and no key")

    monkeypatch.setattr(secrets, "get_secret", _no_backend)
    resp = client.post(f"/instances/{identifier}/publish-validate")
    assert resp.status_code == 422, resp.status_code
    codes = [e["code"] for e in resp.json()["errors"]]
    assert "secret_backend_unavailable" in codes, codes


@pytest.mark.skipif(
    not os.environ.get("CRMBUILDER_V2_TEST_PG_URL"),
    reason=(
        "the encrypted store cannot be exercised through the API on SQLite: "
        "both the save path (_store inside writable_session) and the read path "
        "(_resolve_secret_or_none inside readonly_session) open a second "
        "session for the secret, and SQLite's single writer deadlocks on the "
        "nested BEGIN IMMEDIATE. Postgres tolerates it, which is why the "
        "droplet works. Set CRMBUILDER_V2_TEST_PG_URL to run this. Reported "
        "against REQ-483 as a finding, not fixed here"
    ),
)
def test_publish_resolves_credentials_from_the_encrypted_store(
    v2_env, client, monkeypatch, no_http_egress
):
    """Defect #1, the store path. Credentials resolve with no keyring at all.

    The keyring is made to fail outright and a Fernet key is configured — the
    droplet's shape. The publish must resolve the credential from the encrypted
    store and proceed. Before REQ-481 this host could resolve nothing, and the
    ``NoKeyringError`` escaped as a 500.

    The instance is seeded through the access layer rather than ``POST
    /instances`` because the save path nests sessions the same way the read path
    does; the subject here is resolution, not saving.
    """
    from crmbuilder_v2.access.repositories import instances as instances_repo
    from crmbuilder_v2.config import reset_settings_cache
    from cryptography.fernet import Fernet

    monkeypatch.delenv(secrets.DISABLE_ENV_VAR, raising=False)
    monkeypatch.setenv("CRMBUILDER_V2_SECRET_KEY", Fernet.generate_key().decode())
    # The cache holds the key setting; it must be dropped again on the way out
    # or the next test inherits an encryption key it never asked for.
    reset_settings_cache()
    try:
        monkeypatch.setattr(
            secrets.keyring, "get_password",
            lambda *a: pytest.fail("resolved via the keyring, not the store"),
        )
        monkeypatch.setattr(
            secrets.keyring, "set_password",
            lambda *a: pytest.fail("stored in the keyring, not the store"),
        )
        assert secrets.store_available(), "the encrypted store should be configured"

        ref = secrets.put_secret("api-key-value")
        crm = FakeTargetCrm()
        monkeypatch.setattr(publish_service, "EspoAdminClient", lambda profile: crm)
        with session_scope() as s:
            identifier = instances_repo.create_instance(
                s, name="Keyringless target", url="https://target.example.org",
                vendor="espocrm", role="target", auth_method="api_key",
                secret_ref=ref,
            )["instance_identifier"]

        _seed_design()
        assert _programs(client, identifier)
    finally:
        monkeypatch.undo()
        reset_settings_cache()


# -- validate_only writes nothing --------------------------------------------


def test_validate_only_touches_nothing_on_the_target(
    v2_env, client, target, no_http_egress, monkeypatch
):
    """A validate run is safe to point at a live instance — that is why the live
    layer uses it. Nothing deploys, no backup is captured, no verification runs,
    and no publish_run is recorded."""
    _seed_design()
    identifier, _crm = target
    monkeypatch.setattr(
        publish_service, "deploy_pipeline",
        lambda *a, **k: pytest.fail("validate_only reached the deploy pipeline"),
    )
    monkeypatch.setattr(
        publish_service, "capture_target_backup",
        lambda *a, **k: pytest.fail("validate_only captured a backup"),
    )

    resp = client.post(f"/instances/{identifier}/publish-validate")
    body = resp.json()["data"]
    assert body["validate_only"] is True
    assert all(not p["deployed"] for p in body["programs"])
    assert body["backup_captured"] is False
    assert body["verification"] is None
    assert "publish_run" not in body
    assert client.get("/publish-runs").json()["data"] == []


# -- the census survives every path ------------------------------------------


def test_a_validation_failure_still_reports_what_was_generated(
    v2_env, client, target, no_http_egress, monkeypatch
):
    """The census is not a success-path decoration.

    A run that fails validation is exactly when a reader needs to know what was
    generated, so the counts must be present on that path too — otherwise a
    hollow design and a broken one are indistinguishable in the response.
    """
    _seed_design()
    identifier, _crm = target
    monkeypatch.setattr(
        publish_service, "validate_programs",
        lambda programs, server_fields=None: {
            f: ["forced failure"] for f, _ in programs
        },
    )
    resp = client.post(f"/instances/{identifier}/publish-validate")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["validation_failed"] is True
    assert sum(p["field_count"] for p in body["programs"]) == sum(
        len(v) for v in SEEDED.values()
    )


def test_a_real_publish_reports_the_same_census_and_records_a_run(
    v2_env, client, target, no_http_egress, monkeypatch
):
    """The deploy path carries the census too, and records the run.

    The pipeline itself is stubbed: what the deploy actually does to a real
    EspoCRM is the disposable-instance layer's question (DEC-915). What is
    checked here is that the handler composes — backup gate, deploy, post-publish
    verification, publish_run row — over a design that generated real content.
    """
    from espo_impl.core.deploy_pipeline import DeployOutcome

    _seed_design()
    identifier, _crm = target
    deployed: list[str] = []

    def _fake_deploy(program, client_, field_mgr, output_fn, **kw):
        deployed.extend(e.name for e in program.entities)
        return DeployOutcome(report=None)

    monkeypatch.setattr(publish_service, "deploy_pipeline", _fake_deploy)

    resp = client.post(f"/instances/{identifier}/publish")
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert set(deployed) == set(SEEDED)
    assert body["backup_captured"] is True
    assert body["verification"] is not None and body["verification"]["ran"] is True
    assert body["publish_run"], "a real publish must record a publish_run"
    assert sum(p["field_count"] for p in body["programs"]) == sum(
        len(v) for v in SEEDED.values()
    )


def _camel(name: str) -> str:
    """The design's snake_case business name as the adapter emits it."""
    head, *rest = name.split("_")
    return head + "".join(w[:1].upper() + w[1:] for w in rest)

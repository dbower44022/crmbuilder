"""Deployment repository tests — PI-576 (REQ-653, DEC-1155, DEC-1185).

A deployment names one client, one application and one hosting provider and
holds an instance, its deploy configuration and the client's provider
credentials by composition. The refusals fire before any row is written; the
identifier is unique across applications; a private application accepts a
deployment only from its defining client; a deployment's own credential wins
over the application's fallback.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.engagement_scope import active_engagement
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.segments.client_management.repositories import (
    client as client_repo,
)
from crmbuilder_v2.segments.client_management.repositories import (
    engagement as engagement_repo,
)
from crmbuilder_v2.segments.operate.repositories import deployments as repo
from crmbuilder_v2.segments.operate.repositories import instances as instance_repo
from crmbuilder_v2.segments.operate.repositories import (
    provider_credentials as credential_repo,
)
from sqlalchemy import inspect

INSTANCE = {
    "name": "Chapter CRM",
    "url": "https://crm.example.org",
    "auth_method": "basic",
    "secret_ref": "crmbuilder:user",
    "secret_key_ref": "crmbuilder:pass",
}


@pytest.fixture
def db(v2_env):
    """ENG-001 (active) defined by CLI-001 Cleveland, private; ENG-002 defined
    by CLI-002 CRMBuilder, public; CLI-003 Rochester defines nothing."""
    with session_scope() as s:
        client_repo.create_client(s, name="Cleveland Business Mentors")
        client_repo.create_client(s, name="CRMBuilder")
        client_repo.create_client(s, name="Rochester Business Mentors")
        client_repo.set_engagement_clients(
            s, "ENG-001", clients=["CLI-001"], primary="CLI-001"
        )
        engagement_repo.create_engagement(
            s,
            engagement_code="PUBAPP",
            engagement_name="Public application",
            engagement_purpose="p",
            engagement_identifier="ENG-002",
            engagement_defining_client="CLI-002",
            engagement_visibility="public",
        )
    return v2_env


def _codes(excinfo) -> list[str]:
    return [e.code for e in excinfo.value.errors]


def test_table_shape(db):
    cols = {c["name"] for c in inspect(get_engine()).get_columns("deployments")}
    assert cols == {
        "deployment_identifier",
        "deployment_application",
        "deployment_client",
        "deployment_hosting_provider",
        "deployment_name",
        "deployment_status",
        "deployment_purpose",
        "deployment_instance_identifier",
        "deployment_notes",
        "deployment_created_at",
        "deployment_updated_at",
        "deployment_deleted_at",
    }


def test_create_with_a_new_instance_composes_what_it_holds(db):
    with session_scope() as s:
        d = repo.create_deployment(
            s,
            purpose="client_own",
            client="CLI-001",
            application="ENG-001",
            name="Cleveland production",
            instance=INSTANCE,
            deploy_config={"domain": "crm.example.org", "droplet_id": "42"},
        )
    assert d["deployment_identifier"] == "DPL-001"
    assert d["deployment_application"] == "ENG-001"
    assert d["deployment_client"] == "CLI-001"
    assert d["deployment_hosting_provider"] == "digitalocean"
    assert d["deployment_status"] == "active"
    assert d["deployment_instance_identifier"] == "INST-001"
    assert d["instance"]["instance_name"] == "Chapter CRM"
    assert d["instance"]["instance_url"] == "https://crm.example.org"
    assert d["instance"]["instance_secret_ref"] == "crmbuilder:user"
    assert d["deploy_config"]["domain"] == "crm.example.org"
    assert d["deploy_config"]["droplet_id"] == "42"
    assert d["provider_credentials"] == []
    with session_scope() as s:
        # The instance was created under the application, INST-001 there.
        inst = instance_repo.get_instance(s, "INST-001")
        assert inst is not None and inst["instance_name"] == "Chapter CRM"
        assert repo.deployment_for_instance(s, "ENG-001", "INST-001")[
            "deployment_identifier"
        ] == "DPL-001"


def test_create_holding_an_existing_instance_and_refusing_a_second_holder(db):
    with session_scope() as s:
        instance_repo.create_instance(s, name="Existing", url="https://x.example.org")
        d = repo.create_deployment(
            s,
            purpose="client_own",
            client="CLI-001",
            application="ENG-001",
            name="Existing",
            instance_identifier="INST-001",
        )
        assert d["instance"]["instance_name"] == "Existing"
        with pytest.raises(UnprocessableError) as excinfo:
            repo.create_deployment(
                s,
                purpose="client_own",
                client="CLI-001",
                application="ENG-001",
                name="Second holder",
                instance_identifier="INST-001",
            )
        assert _codes(excinfo) == ["instance_already_deployed"]
        with pytest.raises(UnprocessableError) as excinfo:
            repo.create_deployment(
                s,
                purpose="client_own",
                client="CLI-001",
                application="ENG-001",
                name="Ghost",
                instance_identifier="INST-999",
            )
        assert _codes(excinfo) == ["instance_not_found"]
        with pytest.raises(UnprocessableError) as excinfo:
            repo.create_deployment(
                s,
                purpose="client_own",
                client="CLI-001",
                application="ENG-001",
                name="Both",
                instance_identifier="INST-001",
                instance=INSTANCE,
            )
        assert _codes(excinfo) == ["ambiguous_instance"]


def test_refusals_fire_before_any_row_is_written(db):
    with session_scope() as s:
        with pytest.raises(UnprocessableError) as excinfo:
            repo.create_deployment(s, purpose="client_own", client="CLI-999", application="ENG-001", name="x", instance=INSTANCE
            )
        assert _codes(excinfo) == ["client_not_found"]
        with pytest.raises(UnprocessableError) as excinfo:
            repo.create_deployment(s, purpose="client_own", client="CLI-001", application="ENG-999", name="x", instance=INSTANCE
            )
        assert _codes(excinfo) == ["application_not_found"]
        # A private application refuses another client.
        with pytest.raises(UnprocessableError) as excinfo:
            repo.create_deployment(s, purpose="client_own", client="CLI-003", application="ENG-001", name="x", instance=INSTANCE
            )
        assert _codes(excinfo) == ["application_private"]
        with pytest.raises(UnprocessableError) as excinfo:
            repo.create_deployment(s, purpose="client_own", client="CLI-001", application="ENG-001", name="x", hosting_provider="aws"
            )
        assert _codes(excinfo) == ["invalid_value"] or "hosting" in str(excinfo.value)
    with session_scope() as s:
        assert repo.list_deployments(s) == []
        assert instance_repo.list_instances(s) == []


def test_an_engagement_without_a_defining_client_is_not_an_application(db):
    with session_scope() as s:
        engagement_repo.create_engagement(
            s,
            engagement_code="NOCLI",
            engagement_name="No client",
            engagement_purpose="p",
            engagement_identifier="ENG-003",
        )
        with pytest.raises(UnprocessableError) as excinfo:
            repo.create_deployment(s, purpose="client_own", client="CLI-001", application="ENG-003", name="x")
        assert _codes(excinfo) == ["no_defining_client"]


def test_public_application_accepts_any_client_and_identifiers_span_applications(db):
    with session_scope() as s:
        first = repo.create_deployment(s, purpose="client_own", client="CLI-001", application="ENG-001", name="Cleveland", instance=INSTANCE
        )
        second = repo.create_deployment(s, purpose="client_own", client="CLI-003", application="ENG-002", name="Rochester on public"
        )
        third = repo.create_deployment(s, purpose="client_own", client="CLI-001", application="ENG-002", name="Cleveland on public"
        )
    assert [d["deployment_identifier"] for d in (first, second, third)] == [
        "DPL-001",
        "DPL-002",
        "DPL-003",
    ]
    with session_scope() as s:
        assert repo.next_deployment_identifier(s) == "DPL-004"
        assert [
            d["deployment_identifier"]
            for d in repo.list_deployments(s, application="ENG-002")
        ] == ["DPL-002", "DPL-003"]
        assert [
            d["deployment_identifier"] for d in repo.list_deployments(s, client="CLI-001")
        ] == ["DPL-001", "DPL-003"]


def test_read_composes_under_the_application_scope_from_another_engagement(db):
    with session_scope() as s:
        repo.create_deployment(s, purpose="client_own", client="CLI-001", application="ENG-001", name="Cleveland", instance=INSTANCE
        )
    with active_engagement("ENG-002"), session_scope() as s:
        d = repo.get_deployment(s, "DPL-001")
        assert d["instance"]["instance_url"] == "https://crm.example.org"
        assert d["deployment_application"] == "ENG-001"


def test_deployment_credentials_override_the_application_fallback(db):
    with session_scope() as s:
        repo.create_deployment(s, purpose="client_own", client="CLI-001", application="ENG-001", name="A")
        repo.create_deployment(s, purpose="client_own", client="CLI-001", application="ENG-001", name="B")
        credential_repo.upsert_provider_credential(
            s, "digitalocean", token_ref="crmbuilder:app-do", label="application"
        )
        credential_repo.upsert_provider_credential(
            s, "cloudflare", token_ref="crmbuilder:app-cf"
        )
        credential_repo.upsert_provider_credential(
            s,
            "digitalocean",
            token_ref="crmbuilder:dpl1-do",
            label="Rochester's own",
            deployment_identifier="DPL-001",
        )
    with session_scope() as s:
        # Resolution: the deployment's own row, else the application's.
        assert credential_repo.resolve_provider_credential(
            s, "digitalocean", deployment_identifier="DPL-001"
        )["token_ref"] == "crmbuilder:dpl1-do"
        assert credential_repo.resolve_provider_credential(
            s, "cloudflare", deployment_identifier="DPL-001"
        )["token_ref"] == "crmbuilder:app-cf"
        assert credential_repo.resolve_provider_credential(
            s, "digitalocean", deployment_identifier="DPL-002"
        )["token_ref"] == "crmbuilder:app-do"
        assert credential_repo.resolve_provider_credential(s, "digitalocean")[
            "token_ref"
        ] == "crmbuilder:app-do"
        # The application-level list never shows deployment rows and vice versa.
        assert [r["provider"] for r in credential_repo.list_provider_credentials(s)] == [
            "cloudflare",
            "digitalocean",
        ]
        assert [
            r["token_ref"]
            for r in credential_repo.list_provider_credentials(
                s, deployment_identifier="DPL-001"
            )
        ] == ["crmbuilder:dpl1-do"]
        # The composed read marks each credential's scope.
        one = repo.get_deployment(s, "DPL-001")
        assert [(c["provider"], c["scope"], c["configured"]) for c in one["provider_credentials"]] == [
            ("cloudflare", "application", True),
            ("digitalocean", "deployment", True),
        ]
        two = repo.get_deployment(s, "DPL-002")
        assert [(c["provider"], c["scope"]) for c in two["provider_credentials"]] == [
            ("cloudflare", "application"),
            ("digitalocean", "application"),
        ]
        # Deleting the deployment's row restores the fallback.
        assert credential_repo.delete_provider_credential(
            s, "digitalocean", deployment_identifier="DPL-001"
        ) == "crmbuilder:dpl1-do"
        assert credential_repo.resolve_provider_credential(
            s, "digitalocean", deployment_identifier="DPL-001"
        )["token_ref"] == "crmbuilder:app-do"


def test_attach_patch_delete_restore(db):
    with session_scope() as s:
        repo.create_deployment(s, purpose="client_own", client="CLI-001", application="ENG-001", name="Pending")
        instance_repo.create_instance(s, name="Built later", url="https://later.example.org")
        d = repo.attach_instance(s, "DPL-001", "INST-001")
        assert d["deployment_instance_identifier"] == "INST-001"
        assert d["instance"]["instance_name"] == "Built later"
        # Attaching the same instance again is a no-op; another instance is a conflict.
        assert repo.attach_instance(s, "DPL-001", "INST-001")["deployment_instance_identifier"] == "INST-001"
        instance_repo.create_instance(s, name="Other", url="https://other.example.org")
        with pytest.raises(ConflictError):
            repo.attach_instance(s, "DPL-001", "INST-002")
        p = repo.patch_deployment(
            s, "DPL-001", name="Cleveland test", status="retired", notes="kept", hosting_provider="other"
        )
        assert (p["deployment_name"], p["deployment_status"], p["deployment_notes"], p["deployment_hosting_provider"]) == (
            "Cleveland test", "retired", "kept", "other",
        )
        # A client change obeys the private-application rule.
        with pytest.raises(UnprocessableError) as excinfo:
            repo.patch_deployment(s, "DPL-001", client="CLI-003")
        assert _codes(excinfo) == ["application_private"]
        with pytest.raises(UnprocessableError) as excinfo:
            repo.patch_deployment(s, "DPL-001", colour="red")
        assert _codes(excinfo) == ["unknown_field"]
        gone = repo.delete_deployment(s, "DPL-001")
        assert gone["deployment_deleted_at"] is not None
        assert repo.get_deployment(s, "DPL-001") is None
        assert repo.get_deployment(s, "DPL-001", include_deleted=True) is not None
        assert repo.list_deployments(s) == []
        back = repo.restore_deployment(s, "DPL-001")
        assert back["deployment_deleted_at"] is None
        with pytest.raises(NotFoundError):
            repo.patch_deployment(s, "DPL-404", name="x")

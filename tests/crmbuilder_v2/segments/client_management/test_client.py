"""Client repository tests (PI-512 / REQ-589, DEC-1092): the organisation
above the engagement, and the one link table to engagements."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.segments.client_management.repositories import client as repo
from crmbuilder_v2.segments.client_management.repositories.engagement import (
    create_engagement,
)


@pytest.fixture
def db(v2_env):
    """The unified store with ``ENG-001`` seeded plus two more engagements."""
    with session_scope() as s:
        create_engagement(
            s,
            engagement_code="ALPHA",
            engagement_name="Alpha",
            engagement_purpose="p",
            engagement_identifier="ENG-002",
        )
        create_engagement(
            s,
            engagement_code="BETA",
            engagement_name="Beta",
            engagement_purpose="p",
            engagement_identifier="ENG-003",
        )
    return v2_env


def test_create_assigns_cli_identifier_and_lists_with_engagements(db):
    with session_scope() as s:
        first = repo.create_client(s, name="Cleveland Business Mentors")
        second = repo.create_client(s, name="CRMBuilder", notes="dogfood")
    assert first["client_identifier"] == "CLI-001"
    assert second["client_identifier"] == "CLI-002"
    assert first["client_status"] == "active"
    assert first["engagements"] == []
    with session_scope() as s:
        assert [c["client_identifier"] for c in repo.list_clients(s)] == [
            "CLI-001",
            "CLI-002",
        ]
        assert repo.next_client_identifier(s) == "CLI-003"


def test_explicit_identifier_must_match_format_and_be_free(db):
    with session_scope() as s:
        with pytest.raises(UnprocessableError):
            repo.create_client(s, name="Bad", identifier="CLIENT-1")
        repo.create_client(s, name="Given", identifier="CLI-010")
        with pytest.raises(ConflictError):
            repo.create_client(s, name="Again", identifier="CLI-010")


def test_name_is_unique_ignoring_case(db):
    with session_scope() as s:
        repo.create_client(s, name="Acme")
        with pytest.raises(UnprocessableError):
            repo.create_client(s, name="acme")


def test_status_toggles_and_unknown_value_refused(db):
    with session_scope() as s:
        record = repo.create_client(s, name="Acme")
        ident = record["client_identifier"]
        assert repo.patch_client(s, ident, status="inactive")["client_status"] == "inactive"
        assert repo.patch_client(s, ident, status="active")["client_status"] == "active"
        with pytest.raises(UnprocessableError):
            repo.patch_client(s, ident, status="archived")
        with pytest.raises(UnprocessableError):
            repo.patch_client(s, ident, colour="blue")


def test_transition_check_refuses_unlisted_move(monkeypatch, db):
    monkeypatch.setitem(repo.CLIENT_STATUS_TRANSITIONS, "active", frozenset())
    with session_scope() as s:
        record = repo.create_client(s, name="Acme")
        with pytest.raises(StatusTransitionError):
            repo.patch_client(s, record["client_identifier"], status="inactive")


def test_update_replaces_and_checks_path(db):
    with session_scope() as s:
        record = repo.create_client(s, name="Acme", notes="n")
        ident = record["client_identifier"]
        with pytest.raises(UnprocessableError):
            repo.update_client(s, ident, client_identifier="CLI-999", name="X", status="active")
        after = repo.update_client(s, ident, name="Acme Ltd", notes=None, status="active")
        assert after["client_name"] == "Acme Ltd" and after["client_notes"] is None
        with pytest.raises(NotFoundError):
            repo.update_client(s, "CLI-404", name="X", status="active")


def test_set_engagement_clients_one_primary_and_chapter(db):
    with session_scope() as s:
        a = repo.create_client(s, name="A")["client_identifier"]
        b = repo.create_client(s, name="B")["client_identifier"]
        # An ordinary engagement: one client, primary.
        answer = repo.set_engagement_clients(s, "ENG-002", clients=[a])
        assert answer["primary"] == a
        assert [c["client_identifier"] for c in answer["clients"]] == [a]
        # A chapter engagement: two clients, one primary (the first by default).
        answer = repo.set_engagement_clients(s, "ENG-003", clients=[b, a])
        assert answer["primary"] == b
        assert [c["client_identifier"] for c in answer["clients"]] == [b, a]
        assert answer["clients"][0]["is_primary"] and not answer["clients"][1]["is_primary"]
        # The primary can be chosen explicitly.
        answer = repo.set_engagement_clients(s, "ENG-003", clients=[b, a], primary=a)
        assert answer["primary"] == a
        assert repo.primary_client_for_engagement(s, "ENG-003")["client_identifier"] == a
        # Each client lists what it holds; a client's engagements carry is_primary.
        assert repo.get_client(s, a)["engagements"] == ["ENG-002", "ENG-003"]
        held = repo.list_client_engagements(s, b)
        assert [(e["engagement_identifier"], e["is_primary"]) for e in held] == [
            ("ENG-003", False)
        ]
        # An empty set means no client.
        answer = repo.set_engagement_clients(s, "ENG-002", clients=[])
        assert answer["clients"] == [] and answer["primary"] is None
        assert repo.primary_client_for_engagement(s, "ENG-002") is None


def test_set_engagement_clients_validates(db):
    with session_scope() as s:
        a = repo.create_client(s, name="A")["client_identifier"]
        with pytest.raises(NotFoundError):
            repo.set_engagement_clients(s, "ENG-404", clients=[a])
        with pytest.raises(UnprocessableError):
            repo.set_engagement_clients(s, "ENG-002", clients=["CLI-404"])
        with pytest.raises(UnprocessableError):
            repo.set_engagement_clients(s, "ENG-002", clients=[a], primary="CLI-404")
        with pytest.raises(UnprocessableError):
            repo.set_engagement_clients(s, "ENG-002", clients=[], primary=a)


def test_delete_refused_while_holding_engagements_then_allowed(db):
    with session_scope() as s:
        a = repo.create_client(s, name="A")["client_identifier"]
        repo.set_engagement_clients(s, "ENG-002", clients=[a])
        with pytest.raises(UnprocessableError) as excinfo:
            repo.delete_client(s, a)
        assert "ENG-002" in str(excinfo.value.errors[0].message)
        repo.set_engagement_clients(s, "ENG-002", clients=[])
        deleted = repo.delete_client(s, a)
        assert deleted["client_deleted_at"] is not None
        assert repo.get_client(s, a) is None
        assert repo.get_client(s, a, include_deleted=True) is not None
        assert repo.list_clients(s) == []
        restored = repo.restore_client(s, a)
        assert restored["client_deleted_at"] is None
        with pytest.raises(UnprocessableError):
            repo.restore_client(s, a)
        # A deleted client cannot be linked.
        repo.delete_client(s, a)
        with pytest.raises(UnprocessableError):
            repo.set_engagement_clients(s, "ENG-002", clients=[a])

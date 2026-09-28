"""Deployment grant repository tests — PI-588 (REQ-664, DEC-1194, DEC-1196).

A deployment grant is a client's recorded permission to deploy a private
application it did not define: a holding row without the primary mark. The
grant functions change one row at a time, refuse before any row changes, and
never move the defining client.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import NotFoundError, UnprocessableError
from crmbuilder_v2.segments.client_management.repositories import client as repo
from crmbuilder_v2.segments.client_management.repositories.engagement import (
    create_engagement,
)


@pytest.fixture
def db(v2_env):
    """ENG-001 defined by CLI-001 Cleveland; ENG-002 held by no client;
    CLI-002 Rochester and CLI-003 Boston define nothing."""
    with session_scope() as s:
        repo.create_client(s, name="Cleveland Business Mentors")
        repo.create_client(s, name="Rochester Business Mentors")
        repo.create_client(s, name="Boston Business Mentors")
        repo.set_engagement_clients(s, "ENG-001", clients=["CLI-001"], primary="CLI-001")
        create_engagement(
            s,
            engagement_code="ALPHA",
            engagement_name="Alpha",
            engagement_purpose="p",
            engagement_identifier="ENG-002",
        )
    return v2_env


def _codes(excinfo) -> list[str]:
    return [e.code for e in excinfo.value.errors]


def test_add_list_and_remove_never_move_the_defining_client(db):
    with session_scope() as s:
        assert repo.list_deployment_grants(s, "ENG-001") == {
            "engagement": "ENG-001",
            "defining_client": "CLI-001",
            "deployment_grants": [],
        }
        repo.add_deployment_grant(s, "ENG-001", "CLI-002")
        answer = repo.add_deployment_grant(s, "ENG-001", "CLI-003")
        assert answer["defining_client"] == "CLI-001"
        assert [g["client_identifier"] for g in answer["deployment_grants"]] == [
            "CLI-002",
            "CLI-003",
        ]
        assert repo.holds_deployment_grant(s, "ENG-001", "CLI-002")
        assert not repo.holds_deployment_grant(s, "ENG-001", "CLI-001")
        # Adding a grant already held changes nothing.
        again = repo.add_deployment_grant(s, "ENG-001", "CLI-002")
        assert len(again["deployment_grants"]) == 2
        answer = repo.remove_deployment_grant(s, "ENG-001", "CLI-002")
        assert [g["client_identifier"] for g in answer["deployment_grants"]] == ["CLI-003"]
        assert repo.primary_client_for_engagement(s, "ENG-001")["client_identifier"] == "CLI-001"


def test_refusals_change_no_row(db):
    with session_scope() as s:
        with pytest.raises(UnprocessableError) as excinfo:
            repo.add_deployment_grant(s, "ENG-001", "CLI-001")
        assert _codes(excinfo) == ["is_defining_client"]
        with pytest.raises(UnprocessableError) as excinfo:
            repo.add_deployment_grant(s, "ENG-001", "CLI-404")
        assert _codes(excinfo) == ["client_not_found"]
        with pytest.raises(UnprocessableError) as excinfo:
            repo.add_deployment_grant(s, "ENG-002", "CLI-002")
        assert _codes(excinfo) == ["no_defining_client"]
        with pytest.raises(UnprocessableError) as excinfo:
            repo.remove_deployment_grant(s, "ENG-001", "CLI-001")
        assert _codes(excinfo) == ["is_defining_client"]
        with pytest.raises(NotFoundError):
            repo.remove_deployment_grant(s, "ENG-001", "CLI-002")
        with pytest.raises(NotFoundError):
            repo.add_deployment_grant(s, "ENG-404", "CLI-002")
        holding = repo.get_engagement_clients(s, "ENG-001")
        assert [(c["client_identifier"], c["is_primary"]) for c in holding["clients"]] == [
            ("CLI-001", True)
        ]
        assert repo.get_engagement_clients(s, "ENG-002")["clients"] == []


def test_a_deleted_client_cannot_be_granted(db):
    with session_scope() as s:
        repo.delete_client(s, "CLI-003")
        with pytest.raises(UnprocessableError) as excinfo:
            repo.add_deployment_grant(s, "ENG-001", "CLI-003")
        assert _codes(excinfo) == ["client_not_found"]

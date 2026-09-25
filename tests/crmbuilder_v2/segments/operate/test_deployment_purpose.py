"""Deployment purpose tests — PI-577 (REQ-654, DEC-1156).

A deployment cannot be saved without a purpose; a demo/test deployment
names the application's defining client and is refused for any other
client; a client sees its own deployments plus the demo/test deployment of
every application it may deploy; the purpose is in every listing.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import UnprocessableError
from crmbuilder_v2.segments.client_management.repositories import (
    client as client_repo,
)
from crmbuilder_v2.segments.client_management.repositories import (
    engagement as engagement_repo,
)
from crmbuilder_v2.segments.operate.repositories import deployments as repo


@pytest.fixture
def db(v2_env):
    """ENG-001 private, defined by CLI-001 Cleveland; ENG-002 public, defined
    by CLI-002 CRMBuilder; CLI-003 Rochester and CLI-004 Boston define
    nothing."""
    with session_scope() as s:
        client_repo.create_client(s, name="Cleveland Business Mentors")
        client_repo.create_client(s, name="CRMBuilder")
        client_repo.create_client(s, name="Rochester Business Mentors")
        client_repo.create_client(s, name="Boston Business Mentors")
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


def test_purpose_is_required_and_constrained(db):
    with session_scope() as s:
        with pytest.raises(UnprocessableError) as excinfo:
            repo.create_deployment(s, client="CLI-001", application="ENG-001", name="x")
        assert _codes(excinfo) == ["required"]
        with pytest.raises(UnprocessableError) as excinfo:
            repo.create_deployment(
                s, client="CLI-001", application="ENG-001", name="x", purpose="staging"
            )
        assert _codes(excinfo) == ["invalid_value"]
        assert repo.list_deployments(s) == []
        d = repo.create_deployment(
            s, client="CLI-001", application="ENG-001", name="own", purpose="client_own"
        )
        assert d["deployment_purpose"] == "client_own"


def test_demo_test_is_only_for_the_defining_client(db):
    with session_scope() as s:
        # Rochester may deploy the public application, but not run its demo/test.
        with pytest.raises(UnprocessableError) as excinfo:
            repo.create_deployment(
                s, client="CLI-003", application="ENG-002", name="x", purpose="demo_test"
            )
        assert _codes(excinfo) == ["demo_test_requires_defining_client"]
        assert repo.list_deployments(s) == []
        demo = repo.create_deployment(
            s, client="CLI-002", application="ENG-002", name="Try it", purpose="demo_test"
        )
        assert demo["deployment_purpose"] == "demo_test"
        assert repo.demo_test_deployment(s, "ENG-002")["deployment_identifier"] == (
            demo["deployment_identifier"]
        )
        assert repo.demo_test_deployment(s, "ENG-001") is None
        # The rule holds on a change of purpose or client too.
        own = repo.create_deployment(
            s, client="CLI-003", application="ENG-002", name="Rochester", purpose="client_own"
        )
        with pytest.raises(UnprocessableError) as excinfo:
            repo.patch_deployment(s, own["deployment_identifier"], purpose="demo_test")
        assert _codes(excinfo) == ["demo_test_requires_defining_client"]
        with pytest.raises(UnprocessableError) as excinfo:
            repo.patch_deployment(s, demo["deployment_identifier"], client="CLI-003")
        assert _codes(excinfo) == ["demo_test_requires_defining_client"]
        back = repo.patch_deployment(s, own["deployment_identifier"], purpose="client_own")
        assert back["deployment_purpose"] == "client_own"


def test_a_client_sees_its_own_and_the_demo_test_of_what_it_may_deploy(db):
    with session_scope() as s:
        repo.create_deployment(
            s, client="CLI-001", application="ENG-001", name="Cleveland prod", purpose="client_own"
        )  # DPL-001, private application
        repo.create_deployment(
            s, client="CLI-001", application="ENG-001", name="Cleveland try", purpose="demo_test"
        )  # DPL-002, demo/test of the private application
        repo.create_deployment(
            s, client="CLI-002", application="ENG-002", name="Public try", purpose="demo_test"
        )  # DPL-003, demo/test of the public application
        repo.create_deployment(
            s, client="CLI-003", application="ENG-002", name="Rochester", purpose="client_own"
        )  # DPL-004
    with session_scope() as s:
        def ids(client):
            return [
                (d["deployment_identifier"], d["deployment_purpose"])
                for d in repo.list_deployments_for_client(s, client)
            ]
        # Rochester: its own, plus the public application's demo/test; never
        # Cleveland's private demo/test or Cleveland's own.
        assert ids("CLI-003") == [("DPL-003", "demo_test"), ("DPL-004", "client_own")]
        # Boston deploys nothing yet but may try the public application.
        assert ids("CLI-004") == [("DPL-003", "demo_test")]
        # Cleveland: both of its own (one is its demo/test) plus the public demo/test.
        assert ids("CLI-001") == [
            ("DPL-001", "client_own"),
            ("DPL-002", "demo_test"),
            ("DPL-003", "demo_test"),
        ]
        # CRMBuilder: its own demo/test only; it does not deploy Cleveland's.
        assert ids("CLI-002") == [("DPL-003", "demo_test")]
        # Every listing carries the purpose.
        assert all("deployment_purpose" in d for d in repo.list_deployments(s))

"""PI-575 / REQ-653 (DEC-1183) — the application reading of the engagement
row: the visibility attribute and the defining client resolved from the
primary holding, the ``client_not_found`` refusal before any row is written,
the default visibility of private, and the refusal of an application reading
for an engagement no client holds."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import NotFoundError, UnprocessableError
from crmbuilder_v2.segments.client_management.models import (
    EngagementClientRow,
    EngagementRow,
)
from crmbuilder_v2.segments.client_management.repositories import client as client_repo
from crmbuilder_v2.segments.client_management.repositories import (
    engagement as repo,
)


@pytest.fixture
def db(v2_env):
    """The unified store with ``ENG-001`` seeded (no client) and two live
    clients, ``CLI-001`` and ``CLI-002``."""
    with session_scope() as s:
        client_repo.create_client(s, name="Cleveland Business Mentors")
        client_repo.create_client(s, name="CRMBuilder")
    return v2_env

def _error_codes(excinfo) -> list[str]:
    return [e.code for e in excinfo.value.errors]

def test_create_with_defining_client_round_trips_and_defaults_private(db):
    with session_scope() as s:
        app = repo.create_engagement(
            s,
            engagement_code="ALPHA",
            engagement_name="Alpha",
            engagement_purpose="p",
            engagement_defining_client="CLI-001",
        )
        assert app.engagement_visibility == "private"
        assert app.engagement_defining_client == "CLI-001"
        assert app.engagement_defining_client_name == "Cleveland Business Mentors"
        record = app.to_dict()
        assert record["engagement_visibility"] == "private"
        assert record["engagement_defining_client"] == "CLI-001"
        assert record["engagement_defining_client_name"] == "Cleveland Business Mentors"
        # The holding row is the storage: one primary row, nothing else.
        assert client_repo.get_engagement_clients(s, app.engagement_identifier)[
            "primary"
        ] == "CLI-001"
        # A read resolves the same two attributes.
        again = repo.get_engagement(s, app.engagement_identifier)
        assert (again.engagement_defining_client, again.engagement_visibility) == (
            "CLI-001",
            "private",
        )

def test_create_public_and_change_visibility_by_replace_and_patch(db):
    with session_scope() as s:
        app = repo.create_engagement(
            s,
            engagement_code="ALPHA",
            engagement_name="Alpha",
            engagement_purpose="p",
            engagement_defining_client="CLI-001",
            engagement_visibility="public",
        )
        assert app.engagement_visibility == "public"
        replaced = repo.update_engagement(
            s,
            app.engagement_identifier,
            engagement_name="Alpha",
            engagement_purpose="p",
            engagement_status="active",
            engagement_visibility="private",
        )
        assert replaced.engagement_visibility == "private"
        assert replaced.engagement_defining_client == "CLI-001"  # untouched
        patched = repo.patch_engagement(
            s, app.engagement_identifier, engagement_visibility="public"
        )
        assert patched.engagement_visibility == "public"
        with pytest.raises(UnprocessableError) as excinfo:
            repo.patch_engagement(
                s, app.engagement_identifier, engagement_visibility="secret"
            )
        assert _error_codes(excinfo) == ["invalid_enum_value"]
        with pytest.raises(UnprocessableError):
            repo.create_engagement(
                s,
                engagement_code="BETA",
                engagement_name="Beta",
                engagement_purpose="p",
                engagement_visibility="secret",
            )

def test_missing_or_deleted_client_is_refused_before_any_row_is_written(db):
    with session_scope() as s:
        before = s.query(EngagementRow).count()
        with pytest.raises(UnprocessableError) as excinfo:
            repo.create_engagement(
                s,
                engagement_code="ALPHA",
                engagement_name="Alpha",
                engagement_purpose="p",
                engagement_defining_client="CLI-404",
            )
        assert _error_codes(excinfo) == ["client_not_found"]
        assert excinfo.value.errors[0].field == "engagement_defining_client"
        assert s.query(EngagementRow).count() == before
        assert s.query(EngagementClientRow).count() == 0

        client_repo.delete_client(s, "CLI-002")
        with pytest.raises(UnprocessableError) as excinfo:
            repo.create_application(
                s,
                engagement_code="ALPHA",
                engagement_name="Alpha",
                engagement_purpose="p",
                engagement_defining_client="CLI-002",
            )
        assert _error_codes(excinfo) == ["client_not_found"]
        assert s.query(EngagementRow).count() == before

        # The same refusal on replace and on patch, and nothing changes.
        app = repo.create_application(
            s,
            engagement_code="ALPHA",
            engagement_name="Alpha",
            engagement_purpose="p",
            engagement_defining_client="CLI-001",
        )
        with pytest.raises(UnprocessableError) as excinfo:
            repo.update_engagement(
                s,
                app.engagement_identifier,
                engagement_name="Renamed",
                engagement_purpose="p",
                engagement_status="active",
                engagement_defining_client="CLI-002",
            )
        assert _error_codes(excinfo) == ["client_not_found"]
        with pytest.raises(UnprocessableError) as excinfo:
            repo.patch_engagement(
                s, app.engagement_identifier, engagement_defining_client="CLI-404"
            )
        assert _error_codes(excinfo) == ["client_not_found"]
        unchanged = repo.get_engagement(s, app.engagement_identifier)
        assert unchanged.engagement_name == "Alpha"
        assert unchanged.engagement_defining_client == "CLI-001"

def test_create_application_requires_the_client(db):
    with session_scope() as s:
        with pytest.raises(UnprocessableError) as excinfo:
            repo.create_application(
                s,
                engagement_code="ALPHA",
                engagement_name="Alpha",
                engagement_purpose="p",
                engagement_defining_client="",
            )
        assert _error_codes(excinfo) == ["missing_or_empty"]
        with pytest.raises(UnprocessableError) as excinfo:
            repo.patch_engagement(s, "ENG-001", engagement_defining_client=None)
        assert _error_codes(excinfo) == ["missing_or_empty"]

def test_engagement_without_client_lists_as_engagement_not_application(db):
    with session_scope() as s:
        app = repo.create_application(
            s,
            engagement_code="ALPHA",
            engagement_name="Alpha",
            engagement_purpose="p",
            engagement_defining_client="CLI-001",
        )
        # ENG-001 (seeded, no client) is an engagement and not an application.
        listed = repo.list_engagements(s)
        assert {e.engagement_identifier for e in listed} == {
            "ENG-001",
            app.engagement_identifier,
        }
        seeded = repo.get_engagement(s, "ENG-001")
        assert seeded.engagement_defining_client is None
        assert seeded.engagement_visibility == "private"
        assert [a.engagement_identifier for a in repo.list_applications(s)] == [
            app.engagement_identifier
        ]
        with pytest.raises(UnprocessableError) as excinfo:
            repo.get_application(s, "ENG-001")
        assert _error_codes(excinfo) == ["no_defining_client"]
        assert repo.get_application(s, "ENG-404") is None
        assert (
            repo.get_application(s, app.engagement_identifier).engagement_identifier
            == app.engagement_identifier
        )

def test_applications_of_a_client(db):
    with session_scope() as s:
        a = repo.create_application(
            s,
            engagement_code="ALPHA",
            engagement_name="Alpha",
            engagement_purpose="p",
            engagement_defining_client="CLI-001",
        )
        b = repo.create_application(
            s,
            engagement_code="BETA",
            engagement_name="Beta",
            engagement_purpose="p",
            engagement_defining_client="CLI-002",
        )
        # A non-primary holder does not define the application.
        client_repo.set_engagement_clients(
            s, b.engagement_identifier, clients=["CLI-002", "CLI-001"], primary="CLI-002"
        )
        assert [
            e.engagement_identifier for e in repo.list_applications_of_client(s, "CLI-001")
        ] == [a.engagement_identifier]
        assert [
            e.engagement_identifier for e in repo.list_applications_of_client(s, "CLI-002")
        ] == [b.engagement_identifier]
        with pytest.raises(NotFoundError):
            repo.list_applications_of_client(s, "CLI-404")

def test_changing_the_defining_client_keeps_other_holders(db):
    with session_scope() as s:
        app = repo.create_application(
            s,
            engagement_code="ALPHA",
            engagement_name="Alpha",
            engagement_purpose="p",
            engagement_defining_client="CLI-001",
        )
        ident = app.engagement_identifier
        # Same client again: a no-op.
        assert (
            repo.patch_engagement(s, ident, engagement_defining_client="CLI-001")
            .engagement_defining_client
            == "CLI-001"
        )
        # A client that does not hold the engagement replaces the primary row.
        patched = repo.patch_engagement(s, ident, engagement_defining_client="CLI-002")
        assert patched.engagement_defining_client == "CLI-002"
        assert patched.engagement_defining_client_name == "CRMBuilder"
        holding = client_repo.get_engagement_clients(s, ident)
        assert [c["client_identifier"] for c in holding["clients"]] == ["CLI-002"]
        # A chapter shape: a second holder promoted to primary demotes the old
        # primary to a plain holder instead of removing it.
        client_repo.set_engagement_clients(
            s, ident, clients=["CLI-002", "CLI-001"], primary="CLI-002"
        )
        replaced = repo.update_engagement(
            s,
            ident,
            engagement_name="Alpha",
            engagement_purpose="p",
            engagement_status="active",
            engagement_defining_client="CLI-001",
        )
        assert replaced.engagement_defining_client == "CLI-001"
        holding = client_repo.get_engagement_clients(s, ident)
        assert holding["primary"] == "CLI-001"
        assert sorted(c["client_identifier"] for c in holding["clients"]) == [
            "CLI-001",
            "CLI-002",
        ]

"""Tests for the write half of the EspoCRM client (REQ-605 / PI-518).

The same recorder approach as ``tests/crmbuilder_v2/introspect/test_espo_client.py``:
no HTTP mocking library is installed, so ``requests.Session.request`` is
replaced by a recorder that captures the outgoing call and replays a canned
response.

What these tests hold in place is the shape of each write — its method, its
address and its body — because the managers absorbed next are written against
exactly these, and a wrong address fails against a live instance only.
"""

from __future__ import annotations

import json as json_mod
from typing import Any

import pytest
import requests
from crmbuilder_v2.publish.espo_write_client import EspoWriteClient

BASE = "https://crm.example.org"
API = "https://crm.example.org/api/v1"


class FakeResponse:
    """Minimal stand-in for ``requests.Response``."""

    def __init__(self, status_code: int = 200, body: Any = None) -> None:
        self.status_code = status_code
        self.headers = {"Content-Type": "application/json"}
        if body is None:
            self.content = b""
            self._body = None
        else:
            self._body = body
            self.content = json_mod.dumps(body).encode("utf-8")

    def json(self) -> Any:
        return self._body


class Recorder:
    """Captures each ``Session.request`` call and replays a queued response."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.response: FakeResponse | Exception = FakeResponse(200, {})

    def __call__(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, "kwargs": kwargs})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    @property
    def last(self) -> dict[str, Any]:
        return self.calls[-1]


@pytest.fixture
def client_and_recorder(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[EspoWriteClient, Recorder]:
    recorder = Recorder()
    monkeypatch.setattr(requests.Session, "request", recorder)
    client = EspoWriteClient(base_url=BASE, api_key="KEY123")
    return client, recorder


def test_the_write_client_can_still_read(client_and_recorder) -> None:
    """Applying a declaration is check-then-write, so one client does both."""
    client, recorder = client_and_recorder
    recorder.response = FakeResponse(200, {"Account": {}})
    status, _ = client.get_all_scopes()
    assert status == 200
    assert recorder.last["method"] == "GET"


# --- fields -----------------------------------------------------------------


def test_create_field_addresses_the_field_manager_and_marks_the_field_custom(
    client_and_recorder,
) -> None:
    client, recorder = client_and_recorder
    client.create_field("Account", {"name": "cRegion", "type": "varchar"})
    assert recorder.last["method"] == "POST"
    assert recorder.last["url"] == f"{API}/Admin/fieldManager/Account"
    assert recorder.last["kwargs"]["json"] == {
        "name": "cRegion",
        "type": "varchar",
        "isCustom": True,
    }


def test_create_field_does_not_mutate_the_payload_it_was_given(
    client_and_recorder,
) -> None:
    """A caller that reuses its payload must not find ``isCustom`` in it."""
    client, _ = client_and_recorder
    payload = {"name": "cRegion", "type": "varchar"}
    client.create_field("Account", payload)
    assert payload == {"name": "cRegion", "type": "varchar"}


def test_update_field_addresses_the_named_field(client_and_recorder) -> None:
    client, recorder = client_and_recorder
    client.update_field("Account", "cRegion", {"required": True})
    assert recorder.last["method"] == "PUT"
    assert recorder.last["url"] == f"{API}/Admin/fieldManager/Account/cRegion"
    assert recorder.last["kwargs"]["json"] == {"required": True}


def test_get_field_reads_one_field(client_and_recorder) -> None:
    client, recorder = client_and_recorder
    recorder.response = FakeResponse(200, {"type": "varchar"})
    status, body = client.get_field("Account", "cRegion")
    assert (status, body) == (200, {"type": "varchar"})
    assert recorder.last["method"] == "GET"
    assert recorder.last["url"] == f"{API}/Admin/fieldManager/Account/cRegion"


# --- entity types -----------------------------------------------------------


def test_create_entity_posts_to_the_entity_manager(client_and_recorder) -> None:
    client, recorder = client_and_recorder
    client.create_entity({"name": "CEngagement", "type": "Base"})
    assert recorder.last["method"] == "POST"
    assert recorder.last["url"] == f"{API}/EntityManager/action/createEntity"
    assert recorder.last["kwargs"]["json"] == {
        "name": "CEngagement",
        "type": "Base",
    }


def test_update_entity_posts_to_the_entity_manager(client_and_recorder) -> None:
    client, recorder = client_and_recorder
    client.update_entity({"name": "CEngagement", "stream": True})
    assert recorder.last["url"] == f"{API}/EntityManager/action/updateEntity"


def test_remove_entity_names_the_entity_in_the_body(client_and_recorder) -> None:
    client, recorder = client_and_recorder
    client.remove_entity("CEngagement")
    assert recorder.last["url"] == f"{API}/EntityManager/action/removeEntity"
    assert recorder.last["kwargs"]["json"] == {"name": "CEngagement"}


def test_check_entity_exists_is_true_for_a_populated_scope(
    client_and_recorder,
) -> None:
    client, recorder = client_and_recorder
    recorder.response = FakeResponse(200, {"entity": True})
    assert client.check_entity_exists("CEngagement") == (200, True)


def test_check_entity_exists_is_false_for_an_empty_scope(
    client_and_recorder,
) -> None:
    client, recorder = client_and_recorder
    recorder.response = FakeResponse(200, {})
    assert client.check_entity_exists("CNope") == (200, False)


def test_check_entity_exists_answers_false_when_the_request_fails(
    client_and_recorder,
) -> None:
    """A transport failure is not evidence of absence — the status says so."""
    client, recorder = client_and_recorder
    recorder.response = requests.exceptions.ConnectionError("down")
    status, exists = client.check_entity_exists("CEngagement")
    assert (status, exists) == (-1, False)


def test_rebuild_posts_to_the_administration_endpoint(client_and_recorder) -> None:
    client, recorder = client_and_recorder
    client.rebuild()
    assert recorder.last["method"] == "POST"
    assert recorder.last["url"] == f"{API}/Admin/rebuild"


def test_create_link_posts_the_whole_definition(client_and_recorder) -> None:
    client, recorder = client_and_recorder
    payload = {"entityForeign": "Account", "linkType": "manyToOne"}
    client.create_link(payload)
    assert recorder.last["url"] == f"{API}/EntityManager/action/createLink"
    assert recorder.last["kwargs"]["json"] == payload


# --- layouts, records, teams, roles, filters ---------------------------------


def test_save_layout_puts_the_body_at_the_layout_address(
    client_and_recorder,
) -> None:
    client, recorder = client_and_recorder
    body = [{"label": "Overview", "rows": []}]
    client.save_layout("CEngagement", "detail", body)
    assert recorder.last["method"] == "PUT"
    assert recorder.last["url"] == f"{API}/CEngagement/layout/detail"
    assert recorder.last["kwargs"]["json"] == body


def test_create_record_posts_to_the_entity_collection(client_and_recorder) -> None:
    client, recorder = client_and_recorder
    client.create_record("Contact", {"lastName": "Bower"})
    assert recorder.last["method"] == "POST"
    assert recorder.last["url"] == f"{API}/Contact"


def test_patch_record_changes_only_what_it_is_given(client_and_recorder) -> None:
    client, recorder = client_and_recorder
    client.patch_record("Contact", "abc123", {"title": "Mentor"})
    assert recorder.last["method"] == "PATCH"
    assert recorder.last["url"] == f"{API}/Contact/abc123"
    assert recorder.last["kwargs"]["json"] == {"title": "Mentor"}


def test_create_team_carries_a_description_only_when_given(
    client_and_recorder,
) -> None:
    client, recorder = client_and_recorder
    client.create_team("Mentors")
    assert recorder.last["kwargs"]["json"] == {"name": "Mentors"}
    client.create_team("Mentors", "The mentor cohort")
    assert recorder.last["kwargs"]["json"] == {
        "name": "Mentors",
        "description": "The mentor cohort",
    }


def test_update_team_cannot_rename_a_team(client_and_recorder) -> None:
    """A declaration identifies a team by name; a rename would detach it."""
    client, recorder = client_and_recorder
    client.update_team("team-1", "Now with a description")
    assert recorder.last["method"] == "PATCH"
    assert recorder.last["url"] == f"{API}/Team/team-1"
    assert recorder.last["kwargs"]["json"] == {
        "description": "Now with a description"
    }
    assert "name" not in recorder.last["kwargs"]["json"]


def test_create_and_update_role_go_through_the_record_endpoints(
    client_and_recorder,
) -> None:
    client, recorder = client_and_recorder
    client.create_role({"name": "Mentor", "data": {}})
    assert recorder.last["url"] == f"{API}/Role"
    client.update_role("role-1", {"data": {"Account": {"read": "all"}}})
    assert recorder.last["method"] == "PATCH"
    assert recorder.last["url"] == f"{API}/Role/role-1"


def test_report_filter_create_and_delete(client_and_recorder) -> None:
    client, recorder = client_and_recorder
    client.create_report_filter({"name": "Mine", "entityType": "CEngagement"})
    assert recorder.last["method"] == "POST"
    assert recorder.last["url"] == f"{API}/ReportFilter"
    client.delete_report_filter("filter-1")
    assert recorder.last["method"] == "DELETE"
    assert recorder.last["url"] == f"{API}/ReportFilter/filter-1"


def test_a_missing_report_filter_endpoint_is_reported_not_raised(
    client_and_recorder,
) -> None:
    """The filter endpoint belongs to a paid extension; its absence is a
    404 the caller reads as "not installed", not a failed publish."""
    client, recorder = client_and_recorder
    recorder.response = FakeResponse(404, {"message": "Not Found"})
    status, _ = client.create_report_filter({"name": "Mine"})
    assert status == 404


# --- failure shape ----------------------------------------------------------


def test_a_dropped_connection_returns_a_diagnosable_body_not_an_exception(
    client_and_recorder,
) -> None:
    client, recorder = client_and_recorder
    recorder.response = requests.exceptions.ConnectionError("connection refused")
    status, body = client.create_field("Account", {"name": "cRegion"})
    assert status == -1
    assert body["_request_failed"] is True
    assert "connection refused" in body["_error"]


def test_a_timeout_returns_a_diagnosable_body(client_and_recorder) -> None:
    client, recorder = client_and_recorder
    recorder.response = requests.exceptions.Timeout("took too long")
    status, body = client.save_layout("CEngagement", "detail", [])
    assert status == -1
    assert body["_exception_type"] == "Timeout"

"""Tests for the storage HTTP client and exception mapping."""

from __future__ import annotations

import json

import httpx
import pytest
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.exceptions import (
    ConflictError,
    NotFoundError,
    RequestShapeError,
    ServerError,
    StorageConnectionError,
    ValidationError,
)


def _client(handler, base_url: str = "http://test.invalid") -> StorageClient:
    transport = httpx.MockTransport(handler)
    httpx_client = httpx.Client(base_url=base_url, transport=transport)
    return StorageClient(base_url=base_url, client=httpx_client)


def test_get_decisions_returns_data():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "GET"
        assert req.url.path == "/decisions"
        return httpx.Response(
            200,
            json={
                "data": [{"identifier": "DEC-001", "title": "Hello"}],
                "meta": {},
                "errors": None,
            },
        )

    client = _client(handler)
    result = client.list_decisions()
    assert result == [{"identifier": "DEC-001", "title": "Hello"}]


def test_validation_error_with_field_errors_helper():
    body = {
        "data": None,
        "meta": {},
        "errors": [
            {"code": "validation_error", "field": "title", "message": "required"},
            {"code": "validation_error", "field": "status", "message": "bad value"},
        ],
    }

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json=body)

    client = _client(handler)
    with pytest.raises(ValidationError) as excinfo:
        client.list_decisions()
    exc = excinfo.value
    assert exc.field_errors() == {"title": "required", "status": "bad value"}


def test_validation_error_first_message_per_field():
    body = {
        "data": None,
        "meta": {},
        "errors": [
            {"code": "validation_error", "field": "title", "message": "first"},
            {"code": "validation_error", "field": "title", "message": "second"},
        ],
    }

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json=body)

    client = _client(handler)
    with pytest.raises(ValidationError) as excinfo:
        client.list_decisions()
    assert excinfo.value.field_errors() == {"title": "first"}


def test_not_found_error():
    body = {
        "data": None,
        "meta": {},
        "errors": [{"code": "not_found", "message": "Decision 'DEC-999' not found"}],
    }

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json=body)

    client = _client(handler)
    with pytest.raises(NotFoundError) as excinfo:
        client.get_decision("DEC-999")
    assert "DEC-999" in str(excinfo.value)


def test_conflict_error():
    body = {
        "data": None,
        "meta": {},
        "errors": [
            {"code": "conflict", "message": "Decision 'DEC-001' already exists"}
        ],
    }

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json=body)

    client = _client(handler)
    with pytest.raises(ConflictError) as excinfo:
        client.list_decisions()
    assert "already exists" in str(excinfo.value)


def test_request_shape_error_422():
    body = {
        "data": None,
        "meta": {},
        "errors": [
            {
                "code": "request_validation_error",
                "field": "body.title",
                "message": "Field required",
            }
        ],
    }

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json=body)

    client = _client(handler)
    with pytest.raises(RequestShapeError):
        client.list_decisions()


def test_500_raises_server_error():
    body = {
        "data": None,
        "meta": {},
        "errors": [{"code": "internal_error", "message": "boom"}],
    }

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json=body)

    client = _client(handler)
    with pytest.raises(ServerError) as excinfo:
        client.list_decisions()
    assert excinfo.value.status_code == 500


def test_502_raises_server_error():
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(502, json={"data": None, "meta": {}, "errors": []})

    client = _client(handler)
    with pytest.raises(ServerError) as excinfo:
        client.list_decisions()
    assert excinfo.value.status_code == 502


def test_unparseable_non_2xx_falls_back_to_server_error():
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"<html>oops</html>")

    client = _client(handler)
    with pytest.raises(ServerError) as excinfo:
        client.list_decisions()
    assert excinfo.value.status_code == 500
    assert excinfo.value.errors == []


def test_connection_error_raises_storage_connection_error():
    def handler(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("could not connect")

    client = _client(handler)
    with pytest.raises(StorageConnectionError) as excinfo:
        client.list_decisions()
    assert isinstance(excinfo.value.original, httpx.ConnectError)


def test_read_timeout_raises_storage_connection_error():
    def handler(_req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("read timed out")

    client = _client(handler)
    with pytest.raises(StorageConnectionError):
        client.list_decisions()


def test_get_decision_returns_dict():
    record = {"identifier": "DEC-019", "title": "REST as the consumed interface"}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/decisions/DEC-019"
        return httpx.Response(
            200, json={"data": record, "meta": {}, "errors": None}
        )

    client = _client(handler)
    assert client.get_decision("DEC-019") == record


def test_get_decision_missing_raises_not_found():
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "data": None,
                "meta": {},
                "errors": [{"code": "not_found", "message": "missing"}],
            },
        )

    client = _client(handler)
    with pytest.raises(NotFoundError):
        client.get_decision("DEC-999")


def test_close_owned_client_is_idempotent():
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [], "meta": {}, "errors": None})

    client = StorageClient(base_url="http://test.invalid")
    client.close()
    # No assertion: just confirms no exception on second close.
    client._client._transport = httpx.MockTransport(handler)  # noqa: SLF001


def test_unowned_client_not_closed_by_storage_client_close():
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json={"data": [], "meta": {}, "errors": None})
    )
    httpx_client = httpx.Client(base_url="http://test.invalid", transport=transport)
    client = StorageClient(base_url="http://test.invalid", client=httpx_client)
    client.close()
    # Caller still owns the underlying client and can use it.
    assert httpx_client.is_closed is False
    httpx_client.close()


def test_context_manager_closes_owned_client():
    with StorageClient(base_url="http://test.invalid") as client:
        assert client._client.is_closed is False  # noqa: SLF001
    assert client._client.is_closed is True  # noqa: SLF001


def test_list_sessions_returns_data():
    record = {"identifier": "SES-004", "title": "Storage v0.1"}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "GET"
        assert req.url.path == "/sessions"
        return httpx.Response(
            200, json={"data": [record], "meta": {}, "errors": None}
        )

    client = _client(handler)
    assert client.list_sessions() == [record]


def test_get_session_returns_dict():
    record = {"identifier": "SES-004", "title": "Storage v0.1"}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/sessions/SES-004"
        return httpx.Response(
            200, json={"data": record, "meta": {}, "errors": None}
        )

    client = _client(handler)
    assert client.get_session("SES-004") == record


def test_get_session_missing_raises_not_found():
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "data": None,
                "meta": {},
                "errors": [{"code": "not_found", "message": "missing"}],
            },
        )

    client = _client(handler)
    with pytest.raises(NotFoundError):
        client.get_session("SES-999")


def test_list_risks_returns_data():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "GET"
        assert req.url.path == "/risks"
        return httpx.Response(
            200, json={"data": [], "meta": {}, "errors": None}
        )

    client = _client(handler)
    assert client.list_risks() == []


def test_get_risk_returns_dict():
    record = {"identifier": "RSK-001", "title": "Test risk"}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/risks/RSK-001"
        return httpx.Response(
            200, json={"data": record, "meta": {}, "errors": None}
        )

    client = _client(handler)
    assert client.get_risk("RSK-001") == record


def test_get_risk_missing_raises_not_found():
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "data": None,
                "meta": {},
                "errors": [{"code": "not_found", "message": "missing"}],
            },
        )

    client = _client(handler)
    with pytest.raises(NotFoundError):
        client.get_risk("RSK-999")


def test_list_charter_versions_returns_list():
    versions = [
        {"version": 2, "is_current": True, "payload": {"scope": "two"}},
        {"version": 1, "is_current": False, "payload": {"scope": "one"}},
    ]

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "GET"
        assert req.url.path == "/charter/versions"
        return httpx.Response(
            200, json={"data": versions, "meta": {}, "errors": None}
        )

    client = _client(handler)
    assert client.list_charter_versions() == versions


def test_get_charter_version_returns_dict():
    record = {"version": 2, "is_current": True, "payload": {"scope": "two"}}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/charter/versions/2"
        return httpx.Response(
            200, json={"data": record, "meta": {}, "errors": None}
        )

    client = _client(handler)
    assert client.get_charter_version(2) == record


def test_get_charter_version_missing_raises_not_found():
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "data": None,
                "meta": {},
                "errors": [{"code": "not_found", "message": "version 99"}],
            },
        )

    client = _client(handler)
    with pytest.raises(NotFoundError):
        client.get_charter_version(99)


def test_list_status_versions_returns_list():
    versions = [
        {"version": 5, "is_current": True, "payload": {"phase": "ui"}},
        {"version": 4, "is_current": False, "payload": {"phase": "storage"}},
    ]

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/status/versions"
        return httpx.Response(
            200, json={"data": versions, "meta": {}, "errors": None}
        )

    client = _client(handler)
    assert client.list_status_versions() == versions


def test_get_status_version_returns_dict():
    record = {"version": 5, "is_current": True, "payload": {"phase": "ui"}}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/status/versions/5"
        return httpx.Response(
            200, json={"data": record, "meta": {}, "errors": None}
        )

    client = _client(handler)
    assert client.get_status_version(5) == record


def test_get_status_version_missing_raises_not_found():
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "data": None,
                "meta": {},
                "errors": [{"code": "not_found", "message": "version 99"}],
            },
        )

    client = _client(handler)
    with pytest.raises(NotFoundError):
        client.get_status_version(99)


def test_replace_charter_returns_record():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "PUT"
        assert req.url.path == "/charter"
        body = json.loads(req.content)
        assert body == {"payload": {"scope": "v3"}}
        return httpx.Response(
            200,
            json={
                "data": {"version": 3, "is_current": True, "payload": {"scope": "v3"}},
                "meta": {},
                "errors": None,
            },
        )

    client = _client(handler)
    record = client.replace_charter({"scope": "v3"})
    assert record["version"] == 3


def test_make_charter_version_current_returns_record():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "PATCH"
        assert req.url.path == "/charter/versions/2/make-current"
        return httpx.Response(
            200,
            json={
                "data": {"version": 2, "is_current": True, "payload": {}},
                "meta": {},
                "errors": None,
            },
        )

    client = _client(handler)
    record = client.make_charter_version_current(2)
    assert record["version"] == 2


def test_make_charter_version_current_not_found():
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "data": None,
                "meta": {},
                "errors": [{"code": "not_found", "message": "missing"}],
            },
        )

    client = _client(handler)
    with pytest.raises(NotFoundError):
        client.make_charter_version_current(99)


def test_replace_status_returns_record():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "PUT"
        assert req.url.path == "/status"
        return httpx.Response(
            200,
            json={
                "data": {
                    "version": 4,
                    "is_current": True,
                    "payload": {"phase": "v0.2"},
                },
                "meta": {},
                "errors": None,
            },
        )

    client = _client(handler)
    record = client.replace_status({"phase": "v0.2"})
    assert record["payload"]["phase"] == "v0.2"


def test_make_status_version_current_returns_record():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "PATCH"
        assert req.url.path == "/status/versions/3/make-current"
        return httpx.Response(
            200,
            json={
                "data": {"version": 3, "is_current": True, "payload": {}},
                "meta": {},
                "errors": None,
            },
        )

    client = _client(handler)
    assert client.make_status_version_current(3)["version"] == 3


def test_list_topics_returns_list():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/topics"
        return httpx.Response(
            200, json={"data": [], "meta": {}, "errors": None}
        )

    client = _client(handler)
    assert client.list_topics() == []


def test_get_topic_missing_raises_not_found():
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "data": None,
                "meta": {},
                "errors": [{"code": "not_found", "message": "missing"}],
            },
        )

    client = _client(handler)
    with pytest.raises(NotFoundError):
        client.get_topic("TOP-X")


def test_list_planning_items_returns_list():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/planning-items"
        return httpx.Response(
            200, json={"data": [], "meta": {}, "errors": None}
        )

    client = _client(handler)
    assert client.list_planning_items() == []


def test_list_references_returns_list():
    refs = [
        {
            "source_type": "session",
            "source_id": "SES-004",
            "target_type": "decision",
            "target_id": "DEC-018",
            "relationship": "decided_in",
        },
        {
            "source_type": "decision",
            "source_id": "DEC-018",
            "target_type": "decision",
            "target_id": "DEC-001",
            "relationship": "supersedes",
        },
    ]

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "GET"
        assert req.url.path == "/references"
        return httpx.Response(
            200, json={"data": refs, "meta": {}, "errors": None}
        )

    client = _client(handler)
    assert client.list_references() == refs


def test_list_references_touching_returns_split_dict():
    payload = {
        "as_source": [
            {
                "source_type": "decision",
                "source_id": "DEC-018",
                "target_type": "decision",
                "target_id": "DEC-001",
                "relationship": "supersedes",
            }
        ],
        "as_target": [
            {
                "source_type": "session",
                "source_id": "SES-004",
                "target_type": "decision",
                "target_id": "DEC-018",
                "relationship": "decided_in",
            }
        ],
    }

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "GET"
        assert req.url.path == "/references/touching/decision/DEC-018"
        return httpx.Response(
            200, json={"data": payload, "meta": {}, "errors": None}
        )

    client = _client(handler)
    result = client.list_references_touching("decision", "DEC-018")
    assert result == payload


def test_list_references_touching_defensive_on_missing_keys():
    """Server returns an unexpected shape; client returns empty lists."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"data": {}, "meta": {}, "errors": None}
        )

    client = _client(handler)
    result = client.list_references_touching("decision", "DEC-018")
    assert result == {"as_source": [], "as_target": []}


# ---------------------------------------------------------------------------
# Slice G: decision write methods
# ---------------------------------------------------------------------------


def test_create_decision_returns_created_dict():
    record = {
        "identifier": "DEC-100",
        "title": "Slice G works",
        "decision_date": "05-08-26",
        "status": "Active",
    }

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "POST"
        assert req.url.path == "/decisions"
        return httpx.Response(
            201, json={"data": record, "meta": {}, "errors": None}
        )

    client = _client(handler)
    result = client.create_decision(
        {
            "identifier": "DEC-100",
            "title": "Slice G works",
            "decision_date": "05-08-26",
            "status": "Active",
        }
    )
    assert result == record


def test_create_decision_duplicate_raises_conflict():
    body = {
        "data": None,
        "meta": {},
        "errors": [
            {"code": "conflict", "message": "decision 'DEC-001' already exists"}
        ],
    }

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json=body)

    client = _client(handler)
    with pytest.raises(ConflictError):
        client.create_decision(
            {
                "identifier": "DEC-001",
                "title": "dup",
                "decision_date": "05-08-26",
                "status": "Active",
            }
        )


def test_create_decision_invalid_status_raises_validation():
    body = {
        "data": None,
        "meta": {},
        "errors": [
            {
                "code": "validation_error",
                "field": "status",
                "message": "must be one of Active, Superseded, Withdrawn",
            }
        ],
    }

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json=body)

    client = _client(handler)
    with pytest.raises(ValidationError) as excinfo:
        client.create_decision(
            {
                "identifier": "DEC-100",
                "title": "x",
                "decision_date": "05-08-26",
                "status": "Bogus",
            }
        )
    assert excinfo.value.field_errors() == {
        "status": "must be one of Active, Superseded, Withdrawn"
    }


def test_update_decision_returns_updated_dict():
    record = {
        "identifier": "DEC-001",
        "title": "new title",
        "decision_date": "05-08-26",
        "status": "Active",
    }

    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "PATCH"
        assert req.url.path == "/decisions/DEC-001"
        captured["body"] = req.read()
        return httpx.Response(
            200, json={"data": record, "meta": {}, "errors": None}
        )

    client = _client(handler)
    result = client.update_decision("DEC-001", {"title": "new title"})
    assert result == record
    assert b'"title"' in captured["body"]
    assert b'"new title"' in captured["body"]


def test_update_decision_missing_raises_not_found():
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "data": None,
                "meta": {},
                "errors": [{"code": "not_found", "message": "missing"}],
            },
        )

    client = _client(handler)
    with pytest.raises(NotFoundError):
        client.update_decision("DEC-999", {"title": "x"})


def test_delete_decision_returns_response_data():
    deleted = {"identifier": "DEC-001", "title": "gone"}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "DELETE"
        assert req.url.path == "/decisions/DEC-001"
        return httpx.Response(
            200, json={"data": deleted, "meta": {}, "errors": None}
        )

    client = _client(handler)
    assert client.delete_decision("DEC-001") == deleted


def test_delete_decision_referenced_raises_conflict():
    body = {
        "data": None,
        "meta": {},
        "errors": [
            {
                "code": "conflict",
                "message": "decision 'DEC-018' is referenced by SES-004",
            }
        ],
    }

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json=body)

    client = _client(handler)
    with pytest.raises(ConflictError) as excinfo:
        client.delete_decision("DEC-018")
    assert "referenced" in str(excinfo.value)


# ---------------------------------------------------------------------------
# v0.2 slice B: risk write methods
# ---------------------------------------------------------------------------


def test_create_risk_returns_created_dict():
    record = {
        "identifier": "RSK-001",
        "title": "Schema drift",
        "description": "",
        "probability": "Low",
        "impact": "Medium",
        "response_plan": "",
        "status": "Open",
    }

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "POST"
        assert req.url.path == "/risks"
        return httpx.Response(
            201, json={"data": record, "meta": {}, "errors": None}
        )

    client = _client(handler)
    result = client.create_risk(
        {
            "identifier": "RSK-001",
            "title": "Schema drift",
            "probability": "Low",
            "impact": "Medium",
            "status": "Open",
        }
    )
    assert result == record


def test_create_risk_duplicate_raises_conflict():
    body = {
        "data": None,
        "meta": {},
        "errors": [
            {"code": "conflict", "message": "risk 'RSK-001' already exists"}
        ],
    }

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json=body)

    client = _client(handler)
    with pytest.raises(ConflictError):
        client.create_risk(
            {
                "identifier": "RSK-001",
                "title": "dup",
                "probability": "Low",
                "impact": "Low",
                "status": "Open",
            }
        )


def test_create_risk_invalid_probability_raises_validation():
    body = {
        "data": None,
        "meta": {},
        "errors": [
            {
                "code": "validation_error",
                "field": "probability",
                "message": "must be one of Low, Medium, High",
            }
        ],
    }

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json=body)

    client = _client(handler)
    with pytest.raises(ValidationError) as excinfo:
        client.create_risk(
            {
                "identifier": "RSK-001",
                "title": "x",
                "probability": "Bogus",
                "impact": "Low",
                "status": "Open",
            }
        )
    assert excinfo.value.field_errors() == {
        "probability": "must be one of Low, Medium, High"
    }


def test_update_risk_returns_updated_dict():
    record = {
        "identifier": "RSK-001",
        "title": "new title",
        "probability": "Low",
        "impact": "Medium",
        "status": "Open",
    }

    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "PATCH"
        assert req.url.path == "/risks/RSK-001"
        captured["body"] = req.read()
        return httpx.Response(
            200, json={"data": record, "meta": {}, "errors": None}
        )

    client = _client(handler)
    result = client.update_risk("RSK-001", {"title": "new title"})
    assert result == record
    assert b'"title"' in captured["body"]
    assert b'"new title"' in captured["body"]


def test_update_risk_missing_raises_not_found():
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "data": None,
                "meta": {},
                "errors": [{"code": "not_found", "message": "missing"}],
            },
        )

    client = _client(handler)
    with pytest.raises(NotFoundError):
        client.update_risk("RSK-999", {"title": "x"})


def test_delete_risk_returns_response_data():
    deleted = {"identifier": "RSK-001", "title": "gone"}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "DELETE"
        assert req.url.path == "/risks/RSK-001"
        return httpx.Response(
            200, json={"data": deleted, "meta": {}, "errors": None}
        )

    client = _client(handler)
    assert client.delete_risk("RSK-001") == deleted


# ---------------------------------------------------------------------------
# v0.2 slice C: planning-item write methods
# ---------------------------------------------------------------------------


def test_create_planning_item_returns_created_dict():
    record = {
        "identifier": "PI-001",
        "title": "Pacing dimension",
        "item_type": "planning_dimension",
        "description": "",
        "status": "Open",
        "resolution_reference": None,
    }

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "POST"
        assert req.url.path == "/planning-items"
        return httpx.Response(
            201, json={"data": record, "meta": {}, "errors": None}
        )

    client = _client(handler)
    result = client.create_planning_item(
        {
            "identifier": "PI-001",
            "title": "Pacing dimension",
            "item_type": "planning_dimension",
            "status": "Open",
        }
    )
    assert result == record


def test_create_planning_item_duplicate_raises_conflict():
    body = {
        "data": None,
        "meta": {},
        "errors": [
            {"code": "conflict", "message": "planning_item 'PI-001' already exists"}
        ],
    }

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json=body)

    client = _client(handler)
    with pytest.raises(ConflictError):
        client.create_planning_item(
            {
                "identifier": "PI-001",
                "title": "dup",
                "item_type": "planning_dimension",
                "status": "Open",
            }
        )


def test_create_planning_item_invalid_type_raises_validation():
    body = {
        "data": None,
        "meta": {},
        "errors": [
            {
                "code": "validation_error",
                "field": "item_type",
                "message": "must be one of planning_dimension, open_question, pending_work",
            }
        ],
    }

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json=body)

    client = _client(handler)
    with pytest.raises(ValidationError) as excinfo:
        client.create_planning_item(
            {
                "identifier": "PI-001",
                "title": "x",
                "item_type": "Bogus",
                "status": "Open",
            }
        )
    assert excinfo.value.field_errors() == {
        "item_type": "must be one of planning_dimension, open_question, pending_work"
    }


def test_update_planning_item_returns_updated_dict():
    record = {
        "identifier": "PI-001",
        "title": "new title",
        "item_type": "planning_dimension",
        "status": "Open",
    }

    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "PATCH"
        assert req.url.path == "/planning-items/PI-001"
        captured["body"] = req.read()
        return httpx.Response(
            200, json={"data": record, "meta": {}, "errors": None}
        )

    client = _client(handler)
    result = client.update_planning_item("PI-001", {"title": "new title"})
    assert result == record
    assert b'"title"' in captured["body"]
    assert b'"new title"' in captured["body"]


def test_update_planning_item_missing_raises_not_found():
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "data": None,
                "meta": {},
                "errors": [{"code": "not_found", "message": "missing"}],
            },
        )

    client = _client(handler)
    with pytest.raises(NotFoundError):
        client.update_planning_item("PI-999", {"title": "x"})


def test_delete_planning_item_returns_response_data():
    deleted = {"identifier": "PI-001", "title": "gone"}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "DELETE"
        assert req.url.path == "/planning-items/PI-001"
        return httpx.Response(
            200, json={"data": deleted, "meta": {}, "errors": None}
        )

    client = _client(handler)
    assert client.delete_planning_item("PI-001") == deleted


# ---------------------------------------------------------------------------
# v0.2 slice F: show-deleted toggle support and restore convenience method
# ---------------------------------------------------------------------------


def test_list_decisions_default_does_not_send_include_deleted():
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["query"] = dict(req.url.params)
        return httpx.Response(
            200, json={"data": [], "meta": {}, "errors": None}
        )

    client = _client(handler)
    client.list_decisions()
    assert "include_deleted" not in captured["query"]


def test_list_decisions_include_deleted_sends_query_param():
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["query"] = dict(req.url.params)
        return httpx.Response(
            200, json={"data": [], "meta": {}, "errors": None}
        )

    client = _client(handler)
    client.list_decisions(include_deleted=True)
    assert captured["query"].get("include_deleted") == "true"


def test_restore_decision_patches_status_active():
    record = {
        "identifier": "DEC-001",
        "title": "restored",
        "decision_date": "05-08-26",
        "status": "Active",
    }

    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "PATCH"
        assert req.url.path == "/decisions/DEC-001"
        captured["body"] = json.loads(req.read())
        return httpx.Response(
            200, json={"data": record, "meta": {}, "errors": None}
        )

    client = _client(handler)
    result = client.restore_decision("DEC-001")
    assert captured["body"] == {"status": "Active"}
    assert result == record


# ---------------------------------------------------------------------------
# Reference create / delete (v0.3 slice C — DEC-033)
# ---------------------------------------------------------------------------


def test_create_reference_posts_body_and_returns_dict():
    captured: dict[str, Any] = {}
    response_record = {
        "id": 7,
        "source_type": "session",
        "source_id": "SES-008",
        "target_type": "decision",
        "target_id": "DEC-032",
        "relationship": "decided_in",
    }

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "POST"
        assert req.url.path == "/references"
        captured["body"] = json.loads(req.read())
        return httpx.Response(
            201,
            json={"data": response_record, "meta": {}, "errors": None},
        )

    client = _client(handler)
    body = {
        "source_type": "session",
        "source_id": "SES-008",
        "target_type": "decision",
        "target_id": "DEC-032",
        "relationship": "decided_in",
    }
    result = client.create_reference(body)
    assert captured["body"] == body
    assert result == response_record


def test_create_reference_propagates_validation_error():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "data": None,
                "meta": {},
                "errors": [
                    {
                        "code": "validation",
                        "message": "Invalid relationship",
                        "field": "relationship",
                    }
                ],
            },
        )

    client = _client(handler)
    body = {
        "source_type": "session",
        "source_id": "SES-008",
        "target_type": "decision",
        "target_id": "DEC-032",
        "relationship": "totally_made_up",
    }
    from crmbuilder_v2.ui.exceptions import ValidationError

    with pytest.raises(ValidationError):
        client.create_reference(body)


def test_delete_reference_sends_delete_to_id_url():
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["method"] = req.method
        captured["path"] = req.url.path
        return httpx.Response(
            200, json={"data": {"id": 7}, "meta": {}, "errors": None}
        )

    client = _client(handler)
    client.delete_reference(7)
    assert captured["method"] == "DELETE"
    assert captured["path"] == "/references/7"


def test_delete_reference_propagates_not_found():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "data": None,
                "meta": {},
                "errors": [{"code": "not_found", "message": "missing"}],
            },
        )

    client = _client(handler)
    from crmbuilder_v2.ui.exceptions import NotFoundError

    with pytest.raises(NotFoundError):
        client.delete_reference(999)

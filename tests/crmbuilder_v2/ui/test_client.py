"""Tests for the storage HTTP client and exception mapping."""

from __future__ import annotations

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

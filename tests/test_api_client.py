"""Tests for the EspoCRM Admin API client."""

import base64
import hashlib
import hmac as hmac_mod
import json
from unittest.mock import MagicMock

import requests as req

from espo_impl.core.api_client import EspoAdminClient, _format_error_detail
from espo_impl.core.models import InstanceProfile


def make_client(auth_method="api_key") -> EspoAdminClient:
    secret = None
    if auth_method == "hmac":
        secret = "test-secret"
    elif auth_method == "basic":
        secret = "test-password"
    profile = InstanceProfile(
        name="Test Instance",
        url="https://test.espocloud.com",
        api_key="test-api-key",
        auth_method=auth_method,
        secret_key=secret,
    )
    return EspoAdminClient(profile)


def mock_response(status_code=200, content=b"{}",
                  json_return=None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    resp.json.return_value = json_return if json_return is not None else {}
    return resp


def test_api_key_session_headers():
    client = make_client("api_key")
    assert client.session.headers["X-Api-Key"] == "test-api-key"
    assert client.session.headers["Content-Type"] == "application/json"


def test_hmac_no_api_key_header():
    client = make_client("hmac")
    assert "X-Api-Key" not in client.session.headers


def test_base_url():
    client = make_client()
    assert client._base_url == "https://test.espocloud.com/api/v1/Admin/fieldManager"


def test_get_field_uses_metadata_api():
    client = make_client()
    client.session.request = MagicMock(
        return_value=mock_response(json_return={"type": "varchar"})
    )

    status, body = client.get_field("Contact", "firstName")

    call_args = client.session.request.call_args
    assert call_args[0][0] == "GET"
    assert call_args[0][1] == (
        "https://test.espocloud.com/api/v1/Metadata"
        "?key=entityDefs.Contact.fields.firstName"
    )
    assert status == 200
    assert body == {"type": "varchar"}


def test_get_field_404():
    client = make_client()
    client.session.request = MagicMock(
        return_value=mock_response(status_code=404, content=b"")
    )

    status, body = client.get_field("Contact", "nonexistent")
    assert status == 404


def test_create_field_injects_is_custom():
    client = make_client()
    client.session.request = MagicMock(return_value=mock_response())

    payload = {"name": "testField", "type": "varchar", "label": "Test"}
    client.create_field("Contact", payload)

    call_args = client.session.request.call_args
    sent_payload = call_args[1]["json"]
    assert sent_payload["isCustom"] is True
    assert sent_payload["name"] == "testField"


def test_create_field_does_not_mutate_original_payload():
    client = make_client()
    client.session.request = MagicMock(return_value=mock_response())

    original = {"name": "testField", "type": "varchar"}
    client.create_field("Contact", original)
    assert "isCustom" not in original


def test_update_field_url_and_method():
    client = make_client()
    client.session.request = MagicMock(return_value=mock_response())

    payload = {"label": "Updated Label"}
    client.update_field("Contact", "firstName", payload)

    call_args = client.session.request.call_args
    assert call_args[0][0] == "PUT"
    assert call_args[0][1] == (
        "https://test.espocloud.com/api/v1/Admin/fieldManager/Contact/firstName"
    )
    assert call_args[1]["json"] == payload


def test_connection_error_returns_negative_status():
    client = make_client()
    client.session.request = MagicMock(
        side_effect=req.exceptions.ConnectionError("fail")
    )

    status, body = client.get_field("Contact", "test")
    assert status == -1
    assert isinstance(body, dict)
    assert body["_request_failed"] is True
    assert body["_exception_type"] == "ConnectionError"
    assert "fail" in body["_error"]


def test_timeout_returns_negative_status():
    client = make_client()
    client.session.request = MagicMock(
        side_effect=req.exceptions.Timeout("timeout")
    )

    status, body = client.create_field("Contact", {"name": "test"})
    assert status == -1
    assert isinstance(body, dict)
    assert body["_request_failed"] is True
    assert body["_exception_type"] == "Timeout"


def test_ssl_error_returns_request_failed_sentinel():
    """SSLError (subclass of RequestException) is caught by the broad fallback."""
    client = make_client()
    client.session.request = MagicMock(
        side_effect=req.exceptions.SSLError("certificate verify failed")
    )

    status, body = client.get_field("Contact", "test")
    assert status == -1
    assert isinstance(body, dict)
    assert body["_request_failed"] is True
    assert body["_exception_type"] == "SSLError"
    assert "certificate" in body["_error"]


def test_non_json_response_returns_parse_failed_sentinel():
    """A 500 response with an HTML body is caught by JSONDecodeError handling."""
    client = make_client()
    resp = MagicMock()
    resp.status_code = 500
    resp.content = b"<html><body>Internal Server Error</body></html>"
    resp.json.side_effect = json.JSONDecodeError("Expecting value", "doc", 0)
    client.session.request = MagicMock(return_value=resp)

    # Use a low-level _request call directly so we exercise it without
    # the get_field fallback dance.
    status, body = client._request(
        "GET",
        "https://test.espocloud.com/api/v1/Metadata?key=foo",
    )
    assert status == 500
    assert isinstance(body, dict)
    assert body["_parse_failed"] is True
    assert body["_status_code"] == 500
    assert "Internal Server Error" in body["_raw_text"]


def test_request_returns_normal_dict_for_valid_json():
    """Regression: a normal 200 JSON response still returns the dict body."""
    client = make_client()
    client.session.request = MagicMock(
        return_value=mock_response(json_return={"key": "value"})
    )
    status, body = client._request(
        "GET",
        "https://test.espocloud.com/api/v1/Metadata?key=foo",
    )
    assert status == 200
    assert body == {"key": "value"}


def test_request_returns_none_for_empty_content():
    """Regression: an empty response body is preserved as None."""
    client = make_client()
    resp = MagicMock()
    resp.status_code = 204
    resp.content = b""
    client.session.request = MagicMock(return_value=resp)
    status, body = client._request(
        "DELETE",
        "https://test.espocloud.com/api/v1/Foo/abc",
    )
    assert status == 204
    assert body is None


def test_request_preserves_list_response():
    """Regression: list-shaped JSON responses (layout endpoints) pass through."""
    client = make_client()
    client.session.request = MagicMock(
        return_value=mock_response(json_return=[{"name": "panel"}])
    )
    status, body = client._request(
        "GET",
        "https://test.espocloud.com/api/v1/Layout/action/getOriginal",
    )
    assert status == 200
    assert body == [{"name": "panel"}]


def test_request_handles_chunked_encoding_error():
    """ChunkedEncodingError (RequestException subclass) is captured."""
    client = make_client()
    client.session.request = MagicMock(
        side_effect=req.exceptions.ChunkedEncodingError("truncated")
    )
    status, body = client._request("GET", "https://test/api/v1/x")
    assert status == -1
    assert body["_request_failed"] is True
    assert body["_exception_type"] == "ChunkedEncodingError"


def test_format_error_detail_none():
    assert _format_error_detail(None) == "(no response body)"


def test_format_error_detail_request_failed():
    body = {
        "_request_failed": True,
        "_error": "boom",
        "_exception_type": "SSLError",
    }
    msg = _format_error_detail(body)
    assert "request failed" in msg
    assert "SSLError" in msg
    assert "boom" in msg


def test_format_error_detail_parse_failed():
    body = {
        "_parse_failed": True,
        "_raw_text": "<html>oops</html>",
        "_status_code": 500,
    }
    msg = _format_error_detail(body)
    assert "non-JSON response" in msg
    assert "<html>oops</html>" in msg


def test_format_error_detail_message_field():
    assert _format_error_detail({"message": "bad request"}) == "bad request"
    # messageTranslation takes precedence
    assert (
        _format_error_detail({
            "message": "bad request",
            "messageTranslation": "translated",
        })
        == "translated"
    )


def test_format_error_detail_fallback_repr():
    body = {"unrecognized": True, "x": 1}
    msg = _format_error_detail(body)
    assert "unrecognized" in msg
    # truncated to 200 chars
    assert len(msg) <= 200


def test_format_error_detail_non_dict_body():
    """A list/scalar body (e.g., from layout endpoints) is rendered via repr."""
    msg = _format_error_detail([1, 2, 3])
    assert "[1, 2, 3]" in msg


def test_test_connection_success():
    client = make_client()
    client.session.request = MagicMock(
        return_value=mock_response(status_code=200)
    )

    ok, msg = client.test_connection()
    assert ok is True
    assert "successful" in msg


def test_test_connection_401():
    client = make_client()
    client.session.request = MagicMock(
        return_value=mock_response(status_code=401)
    )

    ok, msg = client.test_connection()
    assert ok is False
    assert "Authentication" in msg


def test_hmac_header_construction():
    client = make_client("hmac")

    url = "https://test.espocloud.com/api/v1/Admin/fieldManager/Contact/test"
    headers = client._hmac_header("GET", url)

    assert "X-Hmac-Authorization" in headers
    decoded = base64.b64decode(headers["X-Hmac-Authorization"]).decode("utf-8")
    api_key, hex_digest = decoded.split(":", 1)
    assert api_key == "test-api-key"

    # Verify the HMAC was computed correctly (URI is after /api/v1/)
    string_to_sign = "GET /Admin/fieldManager/Contact/test"
    expected = hmac_mod.new(
        b"test-secret", string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    assert hex_digest == expected


def test_hmac_header_sent_with_request():
    client = make_client("hmac")
    client.session.request = MagicMock(return_value=mock_response())

    client.get_field("Contact", "firstName")

    call_args = client.session.request.call_args
    sent_headers = call_args[1]["headers"]
    assert "X-Hmac-Authorization" in sent_headers


def test_api_key_mode_no_hmac_header():
    client = make_client("api_key")
    client.session.request = MagicMock(return_value=mock_response())

    client.get_field("Contact", "firstName")

    call_args = client.session.request.call_args
    sent_headers = call_args[1]["headers"]
    assert "X-Hmac-Authorization" not in sent_headers


def test_basic_auth_session_headers():
    client = make_client("basic")
    expected = base64.b64encode(b"test-api-key:test-password").decode("utf-8")
    assert client.session.headers["Authorization"] == f"Basic {expected}"
    assert client.session.headers["Espo-Authorization"] == expected
    assert "X-Api-Key" not in client.session.headers

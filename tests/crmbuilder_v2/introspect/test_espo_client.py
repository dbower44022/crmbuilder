"""Unit tests for ``crmbuilder_v2.introspect.espo_client`` (PI-187).

No HTTP mocking library is installed (``responses`` / ``requests-mock``
are both absent), so these tests monkeypatch ``requests.Session.request``
with a recorder that captures the outgoing call and returns a canned
response object.
"""

from __future__ import annotations

import base64
import json as json_mod
from typing import Any

import pytest
import requests
from crmbuilder_v2.introspect.espo_client import (
    EspoConnectionConfig,
    EspoIntrospectionClient,
    format_error_detail,
)

BASE = "https://crm.example.org"
API = "https://crm.example.org/api/v1"


class FakeResponse:
    """Minimal stand-in for ``requests.Response``."""

    def __init__(
        self,
        status_code: int = 200,
        body: Any = None,
        *,
        non_json: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "application/json"}
        if non_json is not None:
            self.content = non_json.encode("utf-8")
            self._raw = non_json
            self._json_ok = False
        elif body is None:
            self.content = b""
            self._json_ok = True
            self._body = None
        else:
            self._body = body
            self.content = json_mod.dumps(body).encode("utf-8")
            self._json_ok = True

    def json(self) -> Any:
        if not self._json_ok:
            raise json_mod.JSONDecodeError("no", self._raw, 0)
        return self._body


class Recorder:
    """Captures the most recent ``Session.request`` call and replays a
    queued response.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.response: FakeResponse | Exception = FakeResponse(200, {})

    def __call__(
        self, method: str, url: str, **kwargs: Any
    ) -> FakeResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": kwargs.get("headers", {}),
                "kwargs": kwargs,
            }
        )
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    @property
    def last(self) -> dict[str, Any]:
        return self.calls[-1]


@pytest.fixture
def client_and_recorder(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[EspoIntrospectionClient, Recorder]:
    recorder = Recorder()
    monkeypatch.setattr(requests.Session, "request", recorder)
    client = EspoIntrospectionClient(base_url=BASE, api_key="KEY123")
    return client, recorder


# --- config / construction --------------------------------------------------


def test_api_url_appends_suffix() -> None:
    cfg = EspoConnectionConfig(base_url=BASE, api_key="k")
    assert cfg.api_url == API


def test_api_url_idempotent_when_suffix_present() -> None:
    cfg = EspoConnectionConfig(base_url=API, api_key="k")
    assert cfg.api_url == API


def test_api_url_strips_trailing_slash() -> None:
    cfg = EspoConnectionConfig(base_url=BASE + "/", api_key="k")
    assert cfg.api_url == API


def test_api_key_auth_sets_header() -> None:
    client = EspoIntrospectionClient(base_url=BASE, api_key="KEY123")
    assert client.session.headers["X-Api-Key"] == "KEY123"


def test_basic_auth_sets_headers() -> None:
    client = EspoIntrospectionClient(
        base_url=BASE,
        api_key="user",
        secret_key="pass",
        auth_method="basic",
    )
    expected = base64.b64encode(b"user:pass").decode()
    assert client.session.headers["Authorization"] == f"Basic {expected}"
    assert client.session.headers["Espo-Authorization"] == expected


def test_invalid_auth_method_raises() -> None:
    with pytest.raises(ValueError):
        EspoIntrospectionClient(
            base_url=BASE, api_key="k", auth_method="nonsense"
        )


def test_missing_required_params_raises() -> None:
    with pytest.raises(ValueError):
        EspoIntrospectionClient()


def test_from_config_constructs() -> None:
    cfg = EspoConnectionConfig(base_url=BASE, api_key="k")
    client = EspoIntrospectionClient.from_config(cfg)
    assert client.api_url == API


def test_hmac_header_present_for_hmac_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = Recorder()
    recorder.response = FakeResponse(200, {})
    monkeypatch.setattr(requests.Session, "request", recorder)
    client = EspoIntrospectionClient(
        base_url=BASE,
        api_key="apikey",
        secret_key="secret",
        auth_method="hmac",
    )
    client.get_all_scopes()
    assert "X-Hmac-Authorization" in recorder.last["headers"]


# --- discovery endpoints: right URL + parse ---------------------------------


def test_get_all_scopes(
    client_and_recorder: tuple[EspoIntrospectionClient, Recorder],
) -> None:
    client, rec = client_and_recorder
    rec.response = FakeResponse(200, {"Contact": {"entity": True}})
    status, body = client.get_all_scopes()
    assert status == 200
    assert body == {"Contact": {"entity": True}}
    assert rec.last["method"] == "GET"
    assert rec.last["url"] == f"{API}/Metadata?key=scopes"


def test_get_entity_field_list(
    client_and_recorder: tuple[EspoIntrospectionClient, Recorder],
) -> None:
    client, rec = client_and_recorder
    rec.response = FakeResponse(200, {"name": {"type": "varchar"}})
    status, body = client.get_entity_field_list("Contact")
    assert status == 200
    assert body == {"name": {"type": "varchar"}}
    assert rec.last["url"] == f"{API}/Metadata?key=entityDefs.Contact.fields"


def test_get_collection(
    client_and_recorder: tuple[EspoIntrospectionClient, Recorder],
) -> None:
    client, rec = client_and_recorder
    rec.response = FakeResponse(200, {"orderBy": "createdAt", "order": "desc"})
    status, body = client.get_collection("Contact")
    assert status == 200
    assert body == {"orderBy": "createdAt", "order": "desc"}
    assert rec.last["url"] == f"{API}/Metadata?key=entityDefs.Contact.collection"


def test_get_all_links(
    client_and_recorder: tuple[EspoIntrospectionClient, Recorder],
) -> None:
    client, rec = client_and_recorder
    rec.response = FakeResponse(200, {"account": {"type": "belongsTo"}})
    status, body = client.get_all_links("Contact")
    assert status == 200
    assert rec.last["url"] == f"{API}/Metadata?key=entityDefs.Contact.links"


def test_get_layout(
    client_and_recorder: tuple[EspoIntrospectionClient, Recorder],
) -> None:
    client, rec = client_and_recorder
    rec.response = FakeResponse(200, [{"rows": []}])
    status, body = client.get_layout("CEngagement", "detail")
    assert status == 200
    assert body == [{"rows": []}]
    assert rec.last["url"] == (
        f"{API}/Layout/action/getOriginal?scope=CEngagement&name=detail"
    )


def test_get_i18n_ok(
    client_and_recorder: tuple[EspoIntrospectionClient, Recorder],
) -> None:
    client, rec = client_and_recorder
    rec.response = FakeResponse(200, {"Global": {"scopeNames": {}}})
    status, body = client.get_i18n()
    assert status == 200
    assert body == {"Global": {"scopeNames": {}}}
    assert rec.last["url"] == f"{API}/I18n?language=en_US"


def test_get_i18n_non_200_returns_empty_dict(
    client_and_recorder: tuple[EspoIntrospectionClient, Recorder],
) -> None:
    client, rec = client_and_recorder
    rec.response = FakeResponse(500, None)
    status, body = client.get_i18n("fr_FR")
    assert status == 500
    assert body == {}
    assert rec.last["url"] == f"{API}/I18n?language=fr_FR"


def test_get_i18n_unexpected_shape_returns_empty_dict(
    client_and_recorder: tuple[EspoIntrospectionClient, Recorder],
) -> None:
    client, rec = client_and_recorder
    rec.response = FakeResponse(200, ["not", "a", "dict"])
    status, body = client.get_i18n()
    assert status == 200
    assert body == {}


def test_get_client_defs(
    client_and_recorder: tuple[EspoIntrospectionClient, Recorder],
) -> None:
    client, rec = client_and_recorder
    rec.response = FakeResponse(200, {"duplicateCheck": {}})
    status, body = client.get_client_defs("Contact")
    assert status == 200
    assert rec.last["url"] == f"{API}/Metadata?key=clientDefs.Contact"


def test_list_report_filters(
    client_and_recorder: tuple[EspoIntrospectionClient, Recorder],
) -> None:
    client, rec = client_and_recorder
    rec.response = FakeResponse(200, {"total": 0, "list": []})
    status, body = client.list_report_filters("CEngagement")
    assert status == 200
    assert rec.last["url"] == (
        f"{API}/ReportFilter?where[0][type]=equals"
        f"&where[0][attribute]=entityType&where[0][value]=CEngagement"
    )


def test_list_report_filters_404_propagates(
    client_and_recorder: tuple[EspoIntrospectionClient, Recorder],
) -> None:
    client, rec = client_and_recorder
    rec.response = FakeResponse(404, {"message": "Not Found"})
    status, _ = client.list_report_filters("Account")
    assert status == 404


def test_get_teams(
    client_and_recorder: tuple[EspoIntrospectionClient, Recorder],
) -> None:
    client, rec = client_and_recorder
    rec.response = FakeResponse(200, {"total": 1, "list": [{"name": "T"}]})
    status, body = client.get_teams()
    assert status == 200
    assert body["list"][0]["name"] == "T"
    assert rec.last["url"] == f"{API}/Team?maxSize=200"


def test_get_roles(
    client_and_recorder: tuple[EspoIntrospectionClient, Recorder],
) -> None:
    client, rec = client_and_recorder
    rec.response = FakeResponse(200, {"total": 0, "list": []})
    status, _ = client.get_roles()
    assert status == 200
    assert rec.last["url"] == f"{API}/Role?maxSize=200"


# --- test_connection branches -----------------------------------------------


@pytest.mark.parametrize(
    ("code", "ok"),
    [(200, True), (401, False), (403, False), (500, False)],
)
def test_test_connection_status_branches(
    client_and_recorder: tuple[EspoIntrospectionClient, Recorder],
    code: int,
    ok: bool,
) -> None:
    client, rec = client_and_recorder
    rec.response = FakeResponse(code, {} if code == 200 else {"m": "x"})
    success, message = client.test_connection()
    assert success is ok
    assert isinstance(message, str)
    assert rec.last["url"] == f"{API}/Metadata?key=app.adminPanel"


def test_test_connection_transport_failure(
    client_and_recorder: tuple[EspoIntrospectionClient, Recorder],
) -> None:
    client, rec = client_and_recorder
    rec.response = requests.exceptions.ConnectionError("boom")
    success, message = client.test_connection()
    assert success is False
    assert "Connection failed" in message


# --- _request error handling ------------------------------------------------


def test_request_transport_error_returns_sentinel(
    client_and_recorder: tuple[EspoIntrospectionClient, Recorder],
) -> None:
    client, rec = client_and_recorder
    rec.response = requests.exceptions.Timeout("slow")
    status, body = client.get_all_scopes()
    assert status == -1
    assert body["_request_failed"] is True
    assert body["_exception_type"] == "Timeout"


def test_request_non_json_returns_parse_sentinel(
    client_and_recorder: tuple[EspoIntrospectionClient, Recorder],
) -> None:
    client, rec = client_and_recorder
    rec.response = FakeResponse(200, non_json="<html>nope</html>")
    status, body = client.get_all_scopes()
    assert status == 200
    assert body["_parse_failed"] is True
    assert "nope" in body["_raw_text"]


def test_request_empty_body_returns_none(
    client_and_recorder: tuple[EspoIntrospectionClient, Recorder],
) -> None:
    client, rec = client_and_recorder
    rec.response = FakeResponse(204, None)
    status, body = client.get_teams()
    assert status == 204
    assert body is None


def test_request_captures_response_headers(
    client_and_recorder: tuple[EspoIntrospectionClient, Recorder],
) -> None:
    client, rec = client_and_recorder
    rec.response = FakeResponse(429, {"m": "rate"}, headers={"Retry-After": "5"})
    client.get_roles()
    assert client.last_response_headers.get("Retry-After") == "5"


# --- format_error_detail ----------------------------------------------------


def test_format_error_detail_variants() -> None:
    assert format_error_detail(None) == "(no response body)"
    assert "request failed" in format_error_detail(
        {"_request_failed": True, "_exception_type": "Timeout", "_error": "x"}
    )
    assert "non-JSON" in format_error_detail(
        {"_parse_failed": True, "_raw_text": "<html>"}
    )
    assert format_error_detail({"message": "bad thing"}) == "bad thing"
    assert format_error_detail({"messageTranslation": "translated"}) == (
        "translated"
    )
    assert "list" in format_error_detail(["a", "b"]) or format_error_detail(
        ["a", "b"]
    ).startswith("[")

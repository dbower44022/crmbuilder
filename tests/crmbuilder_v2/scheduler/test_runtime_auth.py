"""Orchestrator self-authentication for the ADO scheduler (REQ-382 / PI-341).

When ``principal_auth_enabled`` is on, the scheduler's REST calls must carry the
configured orchestrator bearer token; when no token is set (the default), they
are unchanged. Covers the shared ``auth_headers`` helper and that a real
dispatcher call attaches the header.
"""

from __future__ import annotations

import json

from crmbuilder_v2.config import get_settings
from crmbuilder_v2.scheduler import dispatcher
from crmbuilder_v2.scheduler.runtime_auth import auth_headers


def _set_token(monkeypatch, token: str) -> None:
    # Set only the token on the cached settings singleton; reverted after the test.
    monkeypatch.setattr(get_settings(), "orchestrator_token", token)


# --- auth_headers ---------------------------------------------------------


def test_auth_headers_no_token_is_engagement_only():
    assert auth_headers("ENG-001") == {"X-Engagement": "ENG-001"}


def test_auth_headers_content_type():
    h = auth_headers("ENG-001", content_type=True)
    assert h["Content-Type"] == "application/json"
    assert "Authorization" not in h


def test_auth_headers_includes_bearer_when_token_set(monkeypatch):
    _set_token(monkeypatch, "crmbv2_orchestrator")
    h = auth_headers("ENG-001", content_type=True)
    assert h["Authorization"] == "Bearer crmbv2_orchestrator"
    assert h["X-Engagement"] == "ENG-001"


def test_auth_headers_empty_token_sends_no_header(monkeypatch):
    _set_token(monkeypatch, "")
    assert "Authorization" not in auth_headers("ENG-001")


# --- the dispatcher actually attaches the header --------------------------


class _FakeResp:
    def __init__(self, body):
        self._body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


def test_dispatcher_get_attaches_bearer(monkeypatch):
    _set_token(monkeypatch, "crmbv2_orchestrator")
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["req"] = req
        return _FakeResp({"data": {"ok": True}, "errors": None})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    dispatcher._get("http://x", "/work-tasks/WTK-001", "ENG-001")
    assert captured["req"].get_header("Authorization") == "Bearer crmbv2_orchestrator"
    assert captured["req"].get_header("X-engagement") == "ENG-001"


def test_dispatcher_patch_attaches_bearer_and_content_type(monkeypatch):
    _set_token(monkeypatch, "crmbv2_orchestrator")
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["req"] = req
        return _FakeResp({"data": {"ok": True}, "errors": None})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    dispatcher._patch("http://x", "/work-tasks/WTK-001", "ENG-001", {"work_task_status": "Complete"})
    assert captured["req"].get_header("Authorization") == "Bearer crmbv2_orchestrator"
    assert captured["req"].get_header("Content-type") == "application/json"


def test_dispatcher_get_no_token_sends_no_auth(monkeypatch):
    _set_token(monkeypatch, "")
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["req"] = req
        return _FakeResp({"data": {"ok": True}, "errors": None})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    dispatcher._get("http://x", "/work-tasks/WTK-001", "ENG-001")
    assert captured["req"].get_header("Authorization") is None

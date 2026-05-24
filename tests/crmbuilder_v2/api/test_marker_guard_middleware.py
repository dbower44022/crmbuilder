"""Tests for EngagementMarkerGuardMiddleware (DEC-205)."""

from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from crmbuilder_v2.api.marker_guard import (
    EngagementMarkerGuardMiddleware,
    set_marker_at_start,
)


async def _ok(request):
    return JSONResponse({"ok": True})


@pytest.fixture
def app():
    routes = [
        Route("/ping", _ok),
        Route("/health", _ok),
        Route("/openapi.json", _ok),
    ]
    application = Starlette(routes=routes)
    application.add_middleware(EngagementMarkerGuardMiddleware)
    return application


def test_matching_marker_dispatches_normally(app, monkeypatch):
    set_marker_at_start("CBM")
    monkeypatch.setattr(
        "crmbuilder_v2.api.marker_guard.resolve_active_engagement",
        lambda: "CBM",
    )
    client = TestClient(app)
    response = client.get("/ping")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_mismatched_marker_returns_409(app, monkeypatch):
    set_marker_at_start("CBM")
    monkeypatch.setattr(
        "crmbuilder_v2.api.marker_guard.resolve_active_engagement",
        lambda: "CRMBUILDER",
    )
    client = TestClient(app)
    response = client.get("/ping")
    assert response.status_code == 409
    body = response.json()
    assert body["error"] == "engagement_marker_changed"
    assert body["marker_at_start"] == "CBM"
    assert body["marker_now"] == "CRMBUILDER"
    assert "action" in body


def test_missing_marker_returns_409_with_null_now(app, monkeypatch):
    set_marker_at_start("CBM")
    monkeypatch.setattr(
        "crmbuilder_v2.api.marker_guard.resolve_active_engagement",
        lambda: None,
    )
    client = TestClient(app)
    response = client.get("/ping")
    assert response.status_code == 409
    assert response.json()["marker_now"] is None


def test_health_bypasses_guard_on_drift(app, monkeypatch):
    set_marker_at_start("CBM")
    monkeypatch.setattr(
        "crmbuilder_v2.api.marker_guard.resolve_active_engagement",
        lambda: "CRMBUILDER",
    )
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/openapi.json").status_code == 200

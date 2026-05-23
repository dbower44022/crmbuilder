# PI-045 slice C — engagement-marker fail-loud guard

**Last Updated:** 05-23-26 23:45
**Workstream:** PI-045 V2 remote-access deployment
**Operating mode:** DETAIL
**Predecessor:** PI-045 slice B (shared-secret middleware)
**Successor:** none (last code-changes slice; operational and smoke-test conversations follow)

---

## Purpose

Implement DEC-205 — fail-loud on engagement-marker drift. Capture the marker value at API process start, and reject every subsequent request whose live marker reading differs from the captured value with HTTP 409. The API process must be restarted (manual `pkill + relaunch` in v1) to bind to the new engagement.

Without this guard, the marker-driven single-deployment model named in DEC-203 silently routes claude.ai's writes to whichever engagement is currently active when each request lands. A mid-conversation marker flip would split a decision flow across two databases with no signal to either caller.

### Net effect block

- New module `crmbuilder-v2/src/crmbuilder_v2/api/marker_guard.py` holding the module-level `_MARKER_AT_START` constant and the FastAPI middleware class.
- `api/main.py` (`create_app()`) registers the middleware before all route dispatch.
- `cli.py` `run_api()` sets `_MARKER_AT_START` after `resolve_active_engagement()` returns and before `uvicorn.run(...)`.
- Exempt paths bypass the guard: `/health`, `/openapi.json`, `/docs`, `/redoc`, and any other liveness or schema endpoint already in the app.
- On drift: HTTP 409 with structured body and a WARNING log line that names both marker values.
- Tests covering the four cases: match → 200, mismatch → 409, missing marker file → 409 with `marker_now: null`, exempt path → bypass even on drift.

---

## Pre-flight

1. Working directory clean and on `main` with latest pulled.
2. Confirm slices A and B have landed (the `--transport` flag, HTTP binding, and shared-secret middleware are in `main`).
3. Read `crmbuilder-v2/src/crmbuilder_v2/cli.py` `run_api()` and `crmbuilder-v2/src/crmbuilder_v2/api/main.py` `create_app()` to confirm:
   - `resolve_active_engagement()` is called once in `run_api()` before `uvicorn.run`. This is the value to capture.
   - `create_app()` is where to register the middleware. The existing middleware/exception-handler registrations (if any) show the conventional spot.
4. Confirm `crmbuilder-v2/src/crmbuilder_v2/runtime/engagement_routing.py` exposes `resolve_active_engagement()` as a public function with the signature `() -> str | None` returning the marker code or `None` for missing/corrupt. This is used by the middleware to read the live value on each request.

---

## Code changes

### 1. `crmbuilder-v2/src/crmbuilder_v2/api/marker_guard.py` — new file

```python
"""Engagement-marker fail-loud guard (DEC-205).

The API binds to one engagement's database for the lifetime of the
process. The active engagement is read from current_engagement.json
once at process start. If Doug switches engagements via the desktop
UI mid-process, this middleware fails every subsequent request with
HTTP 409 rather than silently rerouting writes to the wrong database.

The marker is read on every non-exempt request via
runtime.engagement_routing.resolve_active_engagement(); the cost is a
file stat plus a small JSON read, both warm in the OS page cache after
the first request, so the per-request overhead is on the order of
single-digit microseconds.

Restart mechanism (manual `pkill + relaunch` in v1) is out of scope for
this guard. A desktop-UI "Restart API" button is a follow-up if friction
surfaces in actual use.
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from crmbuilder_v2.runtime.engagement_routing import resolve_active_engagement

_log = logging.getLogger("crmbuilder_v2.api.marker_guard")

# Set by cli.run_api() after resolve_active_engagement() returns and
# before uvicorn boots. None means "no active engagement at start" —
# treated as a valid starting state; the guard still trips if a marker
# appears later (string != None).
_MARKER_AT_START: str | None = None

# Paths exempt from the marker guard. These must remain available even
# when the API process is bound to a stale engagement so operators can
# probe liveness and inspect schema without restarting first.
EXEMPT_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/openapi.json",
        "/docs",
        "/redoc",
    }
)


def set_marker_at_start(value: str | None) -> None:
    """Set the captured marker. Called by cli.run_api() at startup."""
    global _MARKER_AT_START
    _MARKER_AT_START = value
    _log.info("marker_guard: captured engagement at start = %r", value)


def get_marker_at_start() -> str | None:
    """Return the captured marker. Used by tests."""
    return _MARKER_AT_START


class EngagementMarkerGuardMiddleware(BaseHTTPMiddleware):
    """Reject requests when the live marker differs from the start marker."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        live_marker = resolve_active_engagement()
        if live_marker != _MARKER_AT_START:
            _log.warning(
                "marker_guard: request %s %s rejected — "
                "marker_at_start=%r marker_now=%r",
                request.method,
                request.url.path,
                _MARKER_AT_START,
                live_marker,
            )
            return JSONResponse(
                {
                    "error": "engagement_marker_changed",
                    "marker_at_start": _MARKER_AT_START,
                    "marker_now": live_marker,
                    "action": "restart API to bind to new engagement",
                },
                status_code=409,
            )
        return await call_next(request)
```

### 2. `crmbuilder-v2/src/crmbuilder_v2/api/main.py` — register the middleware

In `create_app()`, register `EngagementMarkerGuardMiddleware` before any other middleware so it runs first and exempt paths short-circuit cleanly. Confirm via reading the existing `create_app` body whether middleware is registered via `app.add_middleware(...)` or via the `middleware=` constructor arg; follow the existing convention.

If there are multiple middleware in `create_app` today, place `EngagementMarkerGuardMiddleware` first in registration order (Starlette runs the *last* registered middleware *first* on the request side — verify the actual ordering in the codebase before placing).

### 3. `crmbuilder-v2/src/crmbuilder_v2/cli.py` — capture at startup

In `run_api()`, after the existing `route_settings_to_engagement(active_code)` block succeeds and before `uvicorn.run(...)`, add:

```python
from crmbuilder_v2.api.marker_guard import set_marker_at_start

# DEC-205: capture the marker now so the middleware can detect mid-
# process drift. set_marker_at_start writes to a module-level constant
# read by EngagementMarkerGuardMiddleware on every non-exempt request.
set_marker_at_start(active_code)
```

`active_code` is the value already resolved earlier in `run_api()` from the `--engagement` flag (if passed) or from `resolve_active_engagement()` (the marker file). Capturing this value — rather than re-reading the marker — means a process started with `--engagement CRMBUILDER` ignoring a CBM marker stays bound to CRMBUILDER even if the marker file later names CBM. That is the correct semantic: the binding is "what this process was launched against," not "what the marker currently says."

### 4. Tests

Add `crmbuilder-v2/tests/api/test_marker_guard_middleware.py`:

```python
"""Tests for EngagementMarkerGuardMiddleware (DEC-205)."""

import pytest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
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
```

If the existing API test layout differs, follow that convention.

---

## Verification

After tests pass:

1. **End-to-end happy path.** With `current_engagement.json` set to CRMBUILDER, start the API: `crmbuilder-v2-api`. From another shell, hit any endpoint (e.g., `curl http://127.0.0.1:8765/sessions`). Response is normal — the snapshot returns CRMBUILDER sessions.
2. **End-to-end drift path.** Leave the API running. In the desktop UI's Engagements panel, click Activate on CBM. Hit the same endpoint again. Response is **HTTP 409** with body containing `engagement_marker_changed`, `marker_at_start: "CRMBUILDER"`, `marker_now: "CBM"`. Inspect the API log (stderr or wherever launchd routes it) — confirm the WARNING line names both markers.
3. **Health endpoint bypasses.** With the drift state still in place, `curl http://127.0.0.1:8765/health` returns 200. (If `/health` does not exist in the current app, skip — but flag it so we know the exempt list needs adjusting.)
4. **Restart fixes it.** `pkill -f crmbuilder-v2-api`, relaunch `crmbuilder-v2-api`. The new process captures CBM as `_MARKER_AT_START`; the same `curl` returns the CBM database's content.
5. **`pytest crmbuilder-v2/tests/` passes end-to-end.**

---

## Commit + push

Single commit with subject:

```
v2: PI-045 slice C — engagement-marker fail-loud guard (DEC-205)
```

Body:

```
Implements DEC-205. Captures the engagement marker at API process start
(api/marker_guard._MARKER_AT_START, set from cli.run_api() after the
existing marker resolution). Registers EngagementMarkerGuardMiddleware
in api.main.create_app() to compare the live marker against the captured
value on every non-exempt request; on drift, returns HTTP 409 with body
{"error":"engagement_marker_changed","marker_at_start":...,"marker_now":...,
"action":"restart API to bind to new engagement"} and logs a WARNING.

Exempt paths bypass the guard: /health, /openapi.json, /docs, /redoc.

Restart mechanism (manual pkill + relaunch in v1) is out of scope here;
a desktop-UI "Restart API" button is a follow-up if friction surfaces.
Slice C of three (PI-045) — code-changes scope complete. Operational
and smoke-test conversations follow.

Refs: PI-045, DEC-203, DEC-205.
```

Doug pushes after review.

---

## Done block

Reply with:

- HEAD before / HEAD after.
- Test count before / after; run result.
- Verification steps 1, 2, and 4 results (the happy/drift/restart triad).
- Pointer that PI-045's code-changes scope is now complete; next is the operational conversation for the Cloudflare nameserver migration, cloudflared install, named tunnel + Access policy, and claude.ai MCP URL registration. The kickoff names the path under `PRDs/product/crmbuilder-v2/` where the operational conversation's kickoff prompt should land.

# PI-045 slice B — shared-secret header middleware

**Last Updated:** 05-23-26 23:45
**Workstream:** PI-045 V2 remote-access deployment
**Operating mode:** DETAIL
**Predecessor:** PI-045 slice A (transport flag and HTTP binding)
**Successor:** PI-045 slice C (engagement-marker fail-loud guard)

---

## Purpose

Add a shared-secret header middleware to the FastMCP HTTP transport. After this slice lands, `crmbuilder-v2-mcp --transport streamable-http`:

- Refuses to start if `CRMBUILDER_V2_MCP_SHARED_SECRET` is not set (fail-loud at startup, before any request can be served unauthenticated).
- 401s every HTTP request that does not present the `X-CRMBuilder-Secret` header set to the configured value.
- Continues to dispatch normally for matching requests.

Stdio transport is unaffected — no middleware registered, no secret required (stdio is local-process IPC, not network-reachable).

This is the second of two layers of auth (Cloudflare Access identity gating at the edge is the first; see DEC-204). Belt-and-braces: a misconfiguration at either layer alone does not expose the write surface to the internet.

### Net effect block

- New env-var-driven setting: `CRMBUILDER_V2_MCP_SHARED_SECRET` (no default — must be set for HTTP transport).
- Startup hard-fail when streamable-http transport is selected and the secret is unset.
- New middleware registered on the FastMCP HTTP app that 401s missing/wrong `X-CRMBuilder-Secret` headers before route dispatch.
- Constant-time comparison via `hmac.compare_digest`.
- New tests covering known-good, known-bad, and missing-header cases.

---

## Pre-flight

1. Working directory clean and on `main` with latest pulled.
2. Confirm PI-045 slice A has landed: `crmbuilder-v2-mcp --transport streamable-http` binds 127.0.0.1:8810 unauthenticated. The `Settings.mcp_http_port` exists; `mcp_server.server.main()` is parameterized on transport.
3. Confirm where FastMCP exposes its underlying ASGI app for middleware registration. `python -c "from mcp.server.fastmcp import FastMCP; s = FastMCP('x'); print([attr for attr in dir(s) if 'app' in attr.lower() or 'middleware' in attr.lower()])"`. The MCP SDK's FastMCP wraps a Starlette app; the registration mechanism may be a method (`s.add_middleware(...)`), a property (`s.app.add_middleware(...)`), or via a Starlette `Middleware` constructor passed to `FastMCP.run`. Read the installed source if unclear: `python -c "import mcp.server.fastmcp; print(mcp.server.fastmcp.__file__)"` and inspect.

---

## Code changes

### 1. `crmbuilder-v2/src/crmbuilder_v2/config.py` — new setting

Add to `Settings`:

```python
mcp_shared_secret: str | None = None
```

with env-var `CRMBUILDER_V2_MCP_SHARED_SECRET`. Default `None` — unset is a valid state for stdio. The startup check in `server.main()` enforces presence for HTTP.

### 2. `crmbuilder-v2/src/crmbuilder_v2/mcp_server/middleware.py` — new file

Starlette middleware class:

```python
"""Shared-secret header middleware for the FastMCP HTTP transport.

Validates the X-CRMBuilder-Secret header against the configured value
on every request. Missing or mismatched → 401 before route dispatch.
Constant-time comparison prevents timing oracles.

Registered only when the transport is streamable-http (see
mcp_server.server.main); stdio bypasses the middleware entirely.
"""

from __future__ import annotations

import hmac
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

_log = logging.getLogger("crmbuilder_v2.mcp_server.middleware")

SECRET_HEADER = "X-CRMBuilder-Secret"


class SharedSecretMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, expected_secret: str) -> None:
        super().__init__(app)
        if not expected_secret:
            raise ValueError(
                "SharedSecretMiddleware requires a non-empty expected_secret"
            )
        self._expected = expected_secret

    async def dispatch(self, request: Request, call_next):
        provided = request.headers.get(SECRET_HEADER, "")
        if not hmac.compare_digest(provided, self._expected):
            _log.warning(
                "rejected request %s %s — missing or wrong %s header",
                request.method,
                request.url.path,
                SECRET_HEADER,
            )
            return JSONResponse(
                {"error": "unauthorized"},
                status_code=401,
            )
        return await call_next(request)
```

### 3. `crmbuilder-v2/src/crmbuilder_v2/mcp_server/server.py` — wire the middleware

Slice A established the pattern: `build_server()` constructs the `FastMCP` instance with `host` and `port` threaded into the constructor (FastMCP's installed SDK signature accepts `host=` and `port=` on the constructor; `run("streamable-http")` is called bare from `main()`). Slice B extends the same pattern: middleware registration belongs inside `build_server()` since that is where the `FastMCP` handle exists.

**Extend `build_server()` with a `shared_secret` kwarg.** When non-None, register `SharedSecretMiddleware`. When `None` (the stdio default code path), skip middleware entirely.

```python
def build_server(
    http: httpx.AsyncClient | None = None,
    *,
    host: str = "127.0.0.1",
    port: int | None = None,
    shared_secret: str | None = None,
) -> FastMCP:
    ...
    server = FastMCP(
        "crmbuilder-v2",
        instructions=(...),
        host=host,
        port=resolved_port,
    )
    if shared_secret:
        # Register SharedSecretMiddleware on FastMCP's underlying ASGI app.
        # Exact mechanism depends on the installed FastMCP version. The
        # FastMCP class is built on Starlette; investigate:
        #   - FastMCP(..., middleware=[Middleware(SharedSecretMiddleware, ...)])
        #     if the constructor accepts a middleware kwarg (Starlette convention)
        #   - server.app.add_middleware(SharedSecretMiddleware, ...)
        #     if the FastMCP exposes its Starlette app
        # Confirm via the signature check in pre-flight step 3, then use
        # the cleanest path. Do not skip silently — if no path exists,
        # stop and report; that is a blocker for the tunnel.
        ...  # register here
    client = http or httpx.AsyncClient(base_url=settings.api_base_url, timeout=30.0)
    register_tools(server, client)
    return server
```

**Update `main()` to enforce the secret and pass it through.** When `transport == "streamable-http"`:

```python
elif transport == "streamable-http":
    settings = get_settings()
    if not settings.mcp_shared_secret:
        raise RuntimeError(
            "CRMBUILDER_V2_MCP_SHARED_SECRET must be set when "
            "transport is streamable-http (DEC-204 second-layer auth)"
        )
    server = build_server(
        host=host,
        port=port,
        shared_secret=settings.mcp_shared_secret,
    )
    server.run("streamable-http")
```

The stdio code path is unchanged — `build_server()` is called with default `shared_secret=None` so no middleware is registered, matching Slice A's stdio dispatch byte-for-byte.

If the installed FastMCP version exposes neither a constructor `middleware=` kwarg nor an `app` attribute for middleware registration, fall back to wrapping the ASGI app at the `run()` boundary or to subclassing `FastMCP`. Report what the installed version supports and use the cleanest path. Do not skip the middleware registration silently — if no path exists, stop and report; that is a blocker for the tunnel and needs to be discussed before proceeding.

### 4. Tests

Add `tests/crmbuilder_v2/mcp_server/test_shared_secret_middleware.py` (Slice A established the `tests/crmbuilder_v2/<area>/` layout; the `mcp_server/` subdirectory was created by Slice A's dispatch tests and is where MCP-server tests live):

Use Starlette's `TestClient` against a minimal Starlette app with the middleware applied:

- `test_correct_secret_passes` — `TestClient` with `SharedSecretMiddleware(expected_secret="abc")` wrapping a trivial 200-OK route; GET with `X-CRMBuilder-Secret: abc` → 200.
- `test_missing_header_returns_401` — same setup; GET with no header → 401 with body `{"error":"unauthorized"}`.
- `test_wrong_secret_returns_401` — `X-CRMBuilder-Secret: nope` → 401.
- `test_empty_secret_constructor_raises` — `SharedSecretMiddleware(app, expected_secret="")` → `ValueError`.

Extend `tests/crmbuilder_v2/mcp_server/test_transport_dispatch.py` (the dispatch tests Slice A created):

- `test_streamable_http_without_secret_raises_at_startup` — monkeypatch `get_settings` to return `mcp_shared_secret=None`; `pytest.raises(RuntimeError, match="CRMBUILDER_V2_MCP_SHARED_SECRET")` on `main(transport="streamable-http")`.
- `test_streamable_http_with_secret_proceeds_to_run` — monkeypatch settings with a secret set and `FastMCP.run` to record; assert `run` called and the middleware registration call happened (record on a stub).

---

## Verification

After tests pass:

1. **Startup hard-fails without the secret.** Unset the env var, run `crmbuilder-v2-mcp --transport streamable-http`. Process exits non-zero with the named error. `echo $?` confirms.
2. **Startup succeeds with the secret.** `export CRMBUILDER_V2_MCP_SHARED_SECRET=$(openssl rand -hex 32)`; run `crmbuilder-v2-mcp --transport streamable-http`. Process stays up and binds 127.0.0.1:8810 (same proof as Slice A's HTTP 406 response from a non-MCP GET).
3. **Missing header → 401.** From another shell: `curl -v http://127.0.0.1:8810/` (no header). Response is 401, body `{"error":"unauthorized"}`.
4. **Wrong header → 401.** `curl -v -H "X-CRMBuilder-Secret: wrong" http://127.0.0.1:8810/`. 401.
5. **Correct header passes the middleware.** `curl -v -H "X-CRMBuilder-Secret: $CRMBUILDER_V2_MCP_SHARED_SECRET" http://127.0.0.1:8810/`. Response is something other than 401 (the MCP protocol may complain about the bare GET — that is expected; the proof point is that auth did not block it).
6. **Stdio unaffected.** `crmbuilder-v2-mcp` (no `--transport`) starts and waits on stdin with no secret env var set. Ctrl-C to exit.
7. **`pytest crmbuilder-v2/tests/` passes end-to-end.**

---

## Commit + push

Single commit with subject:

```
v2: PI-045 slice B — shared-secret header middleware on MCP HTTP transport
```

Body:

```
Adds CRMBUILDER_V2_MCP_SHARED_SECRET to Settings, a Starlette
SharedSecretMiddleware that validates X-CRMBuilder-Secret via
hmac.compare_digest, and a startup hard-fail when the HTTP transport
is selected with no secret configured. Missing or wrong header → 401
before route dispatch. Stdio bypasses the middleware entirely.

Second of two auth layers per DEC-204 (Cloudflare Access at the edge is
the first; this is the belt-and-braces second layer). Slice B of three
(PI-045).

Refs: PI-045, DEC-204.
```

Doug pushes after review.

---

## Done block

Reply with:

- HEAD before / HEAD after.
- Test count before / after; run result.
- Verification steps 1, 3, 4, 5 results (the four auth-path proofs).
- Next-step pointer: `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-045-C-marker-handling.md`.

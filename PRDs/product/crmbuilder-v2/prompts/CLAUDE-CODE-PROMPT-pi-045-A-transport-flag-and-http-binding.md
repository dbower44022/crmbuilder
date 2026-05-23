# PI-045 slice A — `--transport` flag and FastMCP HTTP binding

**Last Updated:** 05-23-26 23:45
**Workstream:** PI-045 V2 remote-access deployment
**Operating mode:** DETAIL
**Predecessor:** none (first slice of the code-changes implementation)
**Successor:** PI-045 slice B (shared-secret middleware)

---

## Purpose

Add a `--transport {stdio,streamable-http}` flag to the `crmbuilder-v2-mcp` CLI entry point and parameterize the MCP server's transport. The stdio default preserves the existing desktop-piped behavior (`server.run("stdio")` at `mcp_server/server.py:44` today); the new `streamable-http` mode binds FastMCP's HTTP transport to `127.0.0.1` with a configurable port.

This slice does **not** add authentication. After A lands, the HTTP transport accepts any unauthenticated request — useful for a local end-to-end smoke test against a curl client on the laptop, but not safe for tunneled exposure. Slice B adds the shared-secret middleware before the tunnel comes up.

### Net effect block

- New env-var-driven setting: `CRMBUILDER_V2_MCP_HTTP_PORT` (default `8810`).
- New CLI args on `crmbuilder-v2-mcp`: `--transport {stdio,streamable-http}` (default `stdio`), `--port <int>` (overrides the env var for the running process).
- `server.main()` parameterized to dispatch on transport; the stdio path is byte-for-byte the same as today.
- New tests covering CLI argparse choices and the build-and-dispatch path.
- No behavior change for any existing caller that runs `crmbuilder-v2-mcp` bare.

---

## Pre-flight

1. Working directory clean and on `main` with latest pulled (`git status; git pull --rebase`).
2. Confirm `git log -1 --format='%h %s'` shows the SES-065 / PI-045 planning conversation's close-out as the latest commit on `main` (or a later commit if other work has landed since).
3. Read `crmbuilder-v2/src/crmbuilder_v2/mcp_server/server.py`, `crmbuilder-v2/src/crmbuilder_v2/cli.py` (the `run_mcp` and `run_api` functions for pattern reference), and `crmbuilder-v2/src/crmbuilder_v2/config.py` (the `Settings` class — confirm the existing env-var pattern for `api_host` / `api_port` before adding the new setting).
4. Confirm the installed `mcp` SDK exposes a streamable-http transport on `FastMCP.run`. Inspect the installed package: `python -c "import inspect; from mcp.server.fastmcp import FastMCP; print(inspect.signature(FastMCP.run))"`. If the signature does not show transport-mode support for `streamable-http`, stop and report — the SDK version may need a bump.

---

## Code changes

### 1. `crmbuilder-v2/src/crmbuilder_v2/config.py` — new setting

Add to the `Settings` class (or wherever the existing `api_host` / `api_port` are defined):

```python
mcp_http_port: int = 8810
```

with the env-var name `CRMBUILDER_V2_MCP_HTTP_PORT` per the existing pattern. Host stays implicit — the HTTP transport is hardcoded to `127.0.0.1` since DEC-202 commits to MCP-only public exposure dialed by cloudflared from the same machine; exposing the host as a setting invites a future foot-gun where it gets set to `0.0.0.0`.

### 2. `crmbuilder-v2/src/crmbuilder_v2/mcp_server/server.py` — parameterize `main()`

Replace the current `main()`:

```python
def main() -> None:
    server = build_server()
    server.run("stdio")
```

with a parameterized version that defaults to stdio for backward compatibility:

```python
def main(
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int | None = None,
) -> None:
    """Run the MCP server on the chosen transport.

    transport: "stdio" (default — Claude Desktop pipes here) or
    "streamable-http" (FastMCP HTTP transport bound to host:port for
    cloudflared / Cloudflare Tunnel ingress; see PI-045).
    """
    server = build_server()
    if transport == "stdio":
        server.run("stdio")
    elif transport == "streamable-http":
        if port is None:
            from crmbuilder_v2.config import get_settings
            port = get_settings().mcp_http_port
        # The exact kwarg names depend on the installed FastMCP version;
        # confirm via the signature check in pre-flight step 4 and adjust
        # if necessary. The intent is bind to host:port and serve HTTP.
        server.run("streamable-http", host=host, port=port)
    else:
        raise ValueError(f"unknown MCP transport: {transport!r}")
```

Update the module docstring's local-usage example to mention both transports:

```
crmbuilder-v2-mcp                            # stdio (Claude Desktop pipes here)
crmbuilder-v2-mcp --transport streamable-http  # HTTP for cloudflared ingress
```

### 3. `crmbuilder-v2/src/crmbuilder_v2/cli.py` — argparse in `run_mcp()`

Replace the current thin wrapper:

```python
def run_mcp() -> None:
    from crmbuilder_v2.mcp_server.server import main as mcp_main
    mcp_main()
```

with a CLI that mirrors `run_api`'s pattern:

```python
def run_mcp() -> None:
    import argparse

    from crmbuilder_v2.config import get_settings
    from crmbuilder_v2.mcp_server.server import main as mcp_main

    parser = argparse.ArgumentParser(
        prog="crmbuilder-v2-mcp",
        description=(
            "Start the crmbuilder_v2 MCP server. Default transport is "
            "stdio (Claude Desktop pipes here). Use --transport "
            "streamable-http to bind the FastMCP HTTP transport for "
            "cloudflared / Cloudflare Tunnel ingress."
        ),
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="MCP transport (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        metavar="PORT",
        help=(
            "Override CRMBUILDER_V2_MCP_HTTP_PORT for the running process. "
            "Only meaningful when --transport=streamable-http."
        ),
    )
    args = parser.parse_args()

    port = args.port if args.port is not None else get_settings().mcp_http_port
    mcp_main(transport=args.transport, port=port)
```

### 4. Tests

Add `crmbuilder-v2/tests/mcp_server/test_transport_dispatch.py`:

- `test_main_stdio_calls_server_run_stdio` — monkeypatch `FastMCP.run` to record args; call `main(transport="stdio")`; assert called with `"stdio"` and no host/port kwargs.
- `test_main_streamable_http_uses_settings_port` — monkeypatch `get_settings` to return a stub with `mcp_http_port=8810` and `FastMCP.run` to record args; call `main(transport="streamable-http")`; assert called with `"streamable-http"` and `host="127.0.0.1"` and `port=8810`.
- `test_main_streamable_http_explicit_port_overrides_settings` — same monkeypatching; call `main(transport="streamable-http", port=9999)`; assert `port=9999`.
- `test_main_rejects_unknown_transport` — `pytest.raises(ValueError)` on `main(transport="websocket")`.

Add `crmbuilder-v2/tests/cli/test_run_mcp_argparse.py`:

- `test_run_mcp_default_invokes_stdio` — monkeypatch `mcp_server.server.main`; run `cli.run_mcp()` with `sys.argv = ["crmbuilder-v2-mcp"]`; assert `main` called with `transport="stdio"`.
- `test_run_mcp_streamable_http_invokes_http` — `sys.argv = ["crmbuilder-v2-mcp", "--transport", "streamable-http"]`; assert `main` called with `transport="streamable-http"` and the env-var-default port.
- `test_run_mcp_port_override` — `sys.argv = ["crmbuilder-v2-mcp", "--transport", "streamable-http", "--port", "9999"]`; assert `port=9999`.
- `test_run_mcp_rejects_unknown_transport` — `sys.argv = ["crmbuilder-v2-mcp", "--transport", "sse"]`; assert `argparse` `SystemExit` with non-zero code.

If the existing test layout uses a different organization (e.g., one file per module rather than per topic), follow that convention.

---

## Verification

After the changes land and tests pass locally:

1. **Stdio behavior unchanged.** Run `crmbuilder-v2-mcp` with no args from a shell that pipes stdin/stdout to a test MCP client (or just confirm the process starts and waits on stdin without error — Ctrl-C to exit).
2. **Streamable-http binds locally.** Start the REST API in one shell (`crmbuilder-v2-api`), then in another: `crmbuilder-v2-mcp --transport streamable-http`. Confirm the process starts, binds `127.0.0.1:8810`, and stays running. From a third shell, `curl -v http://127.0.0.1:8810/` should reach the server (some response, even if it is an MCP protocol error from a non-MCP request — proves the HTTP transport is live). Ctrl-C the MCP process when done.
3. **Port override works.** Repeat with `--port 9999`; confirm it binds on 9999 instead.
4. **`pytest crmbuilder-v2/tests/` passes end-to-end** (not just the new tests).

---

## Commit + push

Single commit with subject:

```
v2: PI-045 slice A — add --transport flag and FastMCP HTTP binding
```

Body:

```
Adds CRMBUILDER_V2_MCP_HTTP_PORT (default 8810) to Settings, parameterizes
mcp_server.server.main() on transport / host / port, and adds argparse to
cli.run_mcp() so `crmbuilder-v2-mcp --transport streamable-http` binds the
FastMCP HTTP transport to 127.0.0.1:8810. Stdio default preserves the
existing Claude Desktop pipe behavior unchanged.

Slice A of three (PI-045). No auth yet — slice B adds the shared-secret
middleware before the tunnel goes up.

Refs: PI-045, DEC-201, DEC-202.
```

Doug pushes after review (Claude Code convention — Claude commits, Doug pushes).

---

## Done block

Reply with:

- HEAD before / HEAD after.
- Test summary: how many tests passed (`pytest --collect-only -q` count before and after, plus the run result).
- Confirmation that `crmbuilder-v2-mcp --transport streamable-http` binds locally (the verification step 2 result).
- Next-step pointer: `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-045-B-shared-secret-middleware.md`.

"""MCP server transport-dispatch tests.

Cover the parameterized ``main()`` entry point in
:mod:`crmbuilder_v2.mcp_server.server` — the stdio default preserves
Claude Desktop behavior; the ``streamable-http`` mode wires host/port
into the FastMCP constructor and dispatches ``server.run("streamable-http")``
for cloudflared / Cloudflare Tunnel ingress.

Also confirms ``build_server`` passes ``streamable_http_path="/"`` to
FastMCP — required so Cloudflare Managed OAuth's PRM ``resource`` field
(bare hostname, no path) matches the URL claude.ai users enter.
"""

from __future__ import annotations

from typing import Any

import pytest
from crmbuilder_v2.mcp_server import server as server_mod


class _Recorder:
    """Stand-in for the built FastMCP instance.

    Records the host/port the constructor would have bound and the
    transport mode passed to ``run``.
    """

    def __init__(self, host: str, port: int | None) -> None:
        self.host = host
        self.port = port
        self.run_args: tuple[Any, ...] | None = None

    def run(self, *args: Any, **kwargs: Any) -> None:
        self.run_args = args
        self.run_kwargs = kwargs


@pytest.fixture
def patched_build_server(monkeypatch: pytest.MonkeyPatch):
    """Replace ``build_server`` with a stub that records constructor args.

    Avoids the real FastMCP setup, the httpx client construction, and the
    tool registration — none of which is under test in this slice.
    """

    captured: dict[str, Any] = {}

    def fake_build(
        http: Any = None,
        *,
        host: str = "127.0.0.1",
        port: int | None = None,
    ) -> _Recorder:
        rec = _Recorder(host=host, port=port)
        captured["instance"] = rec
        captured["host"] = host
        captured["port"] = port
        return rec

    monkeypatch.setattr(server_mod, "build_server", fake_build)
    return captured


def test_main_stdio_calls_server_run_stdio(patched_build_server):
    server_mod.main(transport="stdio")
    rec = patched_build_server["instance"]
    assert rec.run_args == ("stdio",)
    assert rec.run_kwargs == {}


def test_main_streamable_http_uses_settings_port(patched_build_server):
    # build_server picks the settings default when port is None;
    # main() passes None through, so build_server resolves it.
    server_mod.main(transport="streamable-http")
    assert patched_build_server["host"] == "127.0.0.1"
    assert patched_build_server["port"] is None
    rec = patched_build_server["instance"]
    assert rec.run_args == ("streamable-http",)


def test_main_streamable_http_explicit_port_overrides(patched_build_server):
    server_mod.main(transport="streamable-http", port=9999)
    assert patched_build_server["port"] == 9999
    rec = patched_build_server["instance"]
    assert rec.run_args == ("streamable-http",)


def test_main_rejects_unknown_transport(patched_build_server):
    with pytest.raises(ValueError, match="websocket"):
        server_mod.main(transport="websocket")


def test_build_server_resolves_port_from_settings(monkeypatch: pytest.MonkeyPatch):
    """When build_server is called with port=None, it falls back to
    ``Settings.mcp_http_port``. Verified by monkeypatching FastMCP to
    record its constructor kwargs."""

    captured: dict[str, Any] = {}

    class _FakeFastMCP:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            captured.update(kwargs)

        def run(self, *_a: Any, **_kw: Any) -> None:  # pragma: no cover
            pass

    monkeypatch.setattr(server_mod, "FastMCP", _FakeFastMCP)
    monkeypatch.setattr(server_mod, "register_tools", lambda *_a, **_kw: None)
    server_mod.build_server(port=None)
    assert captured["host"] == "127.0.0.1"
    # Default from Settings is 8810 per config.py.
    assert captured["port"] == 8810


def test_build_server_explicit_port_wins(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, Any] = {}

    class _FakeFastMCP:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            captured.update(kwargs)

        def run(self, *_a: Any, **_kw: Any) -> None:  # pragma: no cover
            pass

    monkeypatch.setattr(server_mod, "FastMCP", _FakeFastMCP)
    monkeypatch.setattr(server_mod, "register_tools", lambda *_a, **_kw: None)
    server_mod.build_server(port=12345)
    assert captured["port"] == 12345


def test_build_server_mounts_streamable_http_at_root(
    monkeypatch: pytest.MonkeyPatch,
):
    """``build_server`` passes ``streamable_http_path="/"`` to FastMCP.

    Required so the URL claude.ai users enter (``https://mcp.crmbuilder.ai``,
    matching Cloudflare Managed OAuth's PRM ``resource`` field — bare
    hostname, no path) routes to the MCP transport endpoint.
    """
    captured: dict[str, Any] = {}

    class _FakeFastMCP:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            captured.update(kwargs)

        def run(self, *_a: Any, **_kw: Any) -> None:  # pragma: no cover
            pass

    monkeypatch.setattr(server_mod, "FastMCP", _FakeFastMCP)
    monkeypatch.setattr(server_mod, "register_tools", lambda *_a, **_kw: None)
    server_mod.build_server()
    assert captured["streamable_http_path"] == "/"

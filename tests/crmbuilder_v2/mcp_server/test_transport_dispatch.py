"""PI-045 slices A & B — MCP server transport-dispatch tests.

Slice A: cover the parameterized ``main()`` entry point in
:mod:`crmbuilder_v2.mcp_server.server` — the stdio default preserves
existing Claude Desktop behavior; the new ``streamable-http`` mode
wires host/port into the FastMCP constructor and dispatches
``server.run("streamable-http")`` for cloudflared / Cloudflare Tunnel
ingress.

Slice B: cover the startup-time secret-enforcement gate — when the
HTTP transport is selected, ``CRMBUILDER_V2_MCP_SHARED_SECRET`` must
be set or ``main()`` raises ``RuntimeError`` before any server is
built; when it is set, ``build_server`` receives the secret via the
new ``shared_secret`` kwarg.
"""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass
class _FakeSettings:
    """Minimal stand-in for ``Settings`` covering the fields ``main`` reads."""

    mcp_shared_secret: str | None


def _install_fake_settings(
    monkeypatch: pytest.MonkeyPatch, *, secret: str | None
) -> None:
    """Monkeypatch ``server.get_settings`` to a fixed ``Settings`` stub.

    ``server.main()`` now calls ``get_settings()`` to read the shared
    secret. Tests stub it rather than touch the real env-var-backed
    pydantic settings.
    """

    monkeypatch.setattr(
        server_mod,
        "get_settings",
        lambda: _FakeSettings(mcp_shared_secret=secret),
    )


@pytest.fixture
def patched_build_server(monkeypatch: pytest.MonkeyPatch):
    """Replace ``build_server`` with a stub that records constructor args.

    Avoids the real FastMCP setup, the httpx client construction, and the
    tool registration — none of which is under test in this slice. Also
    installs a stub ``get_settings`` returning a non-empty shared secret
    so existing slice-A streamable-http tests keep dispatching past the
    new slice-B startup gate.
    """

    captured: dict[str, Any] = {}

    def fake_build(
        http: Any = None,
        *,
        host: str = "127.0.0.1",
        port: int | None = None,
        shared_secret: str | None = None,
    ) -> _Recorder:
        rec = _Recorder(host=host, port=port)
        captured["instance"] = rec
        captured["host"] = host
        captured["port"] = port
        captured["shared_secret"] = shared_secret
        return rec

    monkeypatch.setattr(server_mod, "build_server", fake_build)
    _install_fake_settings(monkeypatch, secret="test-secret")
    return captured


def test_main_stdio_calls_server_run_stdio(patched_build_server):
    server_mod.main(transport="stdio")
    rec = patched_build_server["instance"]
    assert rec.run_args == ("stdio",)
    assert rec.run_kwargs == {}


def test_main_streamable_http_uses_settings_port(
    patched_build_server, monkeypatch: pytest.MonkeyPatch
):
    # build_server picks the settings default when port is None;
    # main() passes None through, so build_server resolves it.
    server_mod.main(transport="streamable-http")
    assert patched_build_server["host"] == "127.0.0.1"
    # build_server is stubbed so it never consults Settings — verify
    # main passed None through (the resolve-from-settings behavior is
    # covered in build_server's own contract, exercised below).
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
    monkeypatch.setattr(
        server_mod, "register_tools", lambda *_a, **_kw: None
    )
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
    monkeypatch.setattr(
        server_mod, "register_tools", lambda *_a, **_kw: None
    )
    server_mod.build_server(port=12345)
    assert captured["port"] == 12345


# ---- Slice B: shared-secret startup gate ----------------------------------


def test_streamable_http_without_secret_raises_at_startup(
    monkeypatch: pytest.MonkeyPatch,
):
    """``main(transport="streamable-http")`` hard-fails before any server
    is built when ``CRMBUILDER_V2_MCP_SHARED_SECRET`` is unset."""

    _install_fake_settings(monkeypatch, secret=None)

    # Belt-and-braces: if main were to fall through to build_server, the
    # stub here would record the call. We assert below that it doesn't.
    called: dict[str, bool] = {"built": False}

    def fake_build(*_a: Any, **_kw: Any) -> Any:  # pragma: no cover
        called["built"] = True
        raise AssertionError("build_server must not be called when secret is unset")

    monkeypatch.setattr(server_mod, "build_server", fake_build)

    with pytest.raises(RuntimeError, match="CRMBUILDER_V2_MCP_SHARED_SECRET"):
        server_mod.main(transport="streamable-http")
    assert called["built"] is False


def test_streamable_http_with_secret_proceeds_to_run(patched_build_server):
    """With the secret set, ``main`` passes it to ``build_server`` and
    dispatches ``run("streamable-http")``."""

    server_mod.main(transport="streamable-http")
    assert patched_build_server["shared_secret"] == "test-secret"
    rec = patched_build_server["instance"]
    assert rec.run_args == ("streamable-http",)


def test_build_server_installs_middleware_when_secret_set(
    monkeypatch: pytest.MonkeyPatch,
):
    """``build_server(shared_secret=...)`` wraps ``streamable_http_app``
    so the returned Starlette app gets ``SharedSecretMiddleware``
    registered before uvicorn serves it. Verified by capturing the
    ``add_middleware`` call on the Starlette stand-in."""

    add_middleware_calls: list[tuple[Any, dict[str, Any]]] = []

    class _FakeStarletteApp:
        def add_middleware(self, cls: Any, **kwargs: Any) -> None:
            add_middleware_calls.append((cls, kwargs))

    fake_app = _FakeStarletteApp()

    class _FakeFastMCP:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def streamable_http_app(self) -> Any:
            return fake_app

        def run(self, *_a: Any, **_kw: Any) -> None:  # pragma: no cover
            pass

    monkeypatch.setattr(server_mod, "FastMCP", _FakeFastMCP)
    monkeypatch.setattr(server_mod, "register_tools", lambda *_a, **_kw: None)

    server = server_mod.build_server(shared_secret="my-secret")
    # Calling the wrapped factory triggers the add_middleware call.
    returned = server.streamable_http_app()
    assert returned is fake_app
    assert len(add_middleware_calls) == 1
    cls, kwargs = add_middleware_calls[0]
    assert cls is server_mod.SharedSecretMiddleware
    assert kwargs == {"expected_secret": "my-secret"}


def test_build_server_skips_middleware_when_no_secret(
    monkeypatch: pytest.MonkeyPatch,
):
    """No ``shared_secret`` → ``streamable_http_app`` is left untouched
    (stdio dispatch must match Slice A byte-for-byte)."""

    add_middleware_calls: list[Any] = []

    class _FakeStarletteApp:
        def add_middleware(self, *_a: Any, **_kw: Any) -> None:  # pragma: no cover
            add_middleware_calls.append(_a)

    fake_app = _FakeStarletteApp()
    original_factory_id: dict[str, Any] = {}

    class _FakeFastMCP:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            original_factory_id["before"] = id(self.streamable_http_app)

        def streamable_http_app(self) -> Any:
            return fake_app

        def run(self, *_a: Any, **_kw: Any) -> None:  # pragma: no cover
            pass

    monkeypatch.setattr(server_mod, "FastMCP", _FakeFastMCP)
    monkeypatch.setattr(server_mod, "register_tools", lambda *_a, **_kw: None)

    server = server_mod.build_server()  # no shared_secret kwarg
    server.streamable_http_app()
    assert add_middleware_calls == []

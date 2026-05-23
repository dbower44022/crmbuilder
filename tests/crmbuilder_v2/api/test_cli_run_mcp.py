"""PI-045 slice A — ``run_mcp`` CLI argparse tests.

Exercise the argparse layer in :func:`crmbuilder_v2.cli.run_mcp`: the
``--transport`` choices, the ``--port`` override, and the dispatch into
:func:`crmbuilder_v2.mcp_server.server.main`.
"""

from __future__ import annotations

from typing import Any

import pytest
from crmbuilder_v2 import cli


@pytest.fixture
def captured_main(monkeypatch: pytest.MonkeyPatch):
    """Replace ``mcp_server.server.main`` with a recorder.

    ``run_mcp`` looks up ``main`` via a lazy import inside the function,
    so patching the source module is sufficient — the import resolves
    against the patched module.
    """

    calls: list[dict[str, Any]] = []

    from crmbuilder_v2.mcp_server import server as server_mod

    def fake_main(**kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(server_mod, "main", fake_main)
    return calls


def test_run_mcp_default_invokes_stdio(
    captured_main, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr("sys.argv", ["crmbuilder-v2-mcp"])
    cli.run_mcp()
    assert len(captured_main) == 1
    assert captured_main[0]["transport"] == "stdio"


def test_run_mcp_streamable_http_invokes_http(
    captured_main, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "sys.argv", ["crmbuilder-v2-mcp", "--transport", "streamable-http"]
    )
    cli.run_mcp()
    assert len(captured_main) == 1
    assert captured_main[0]["transport"] == "streamable-http"
    # No --port → falls back to the Settings default (8810).
    assert captured_main[0]["port"] == 8810


def test_run_mcp_port_override(
    captured_main, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "sys.argv",
        ["crmbuilder-v2-mcp", "--transport", "streamable-http", "--port", "9999"],
    )
    cli.run_mcp()
    assert len(captured_main) == 1
    assert captured_main[0]["port"] == 9999


def test_run_mcp_rejects_unknown_transport(
    captured_main, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "sys.argv", ["crmbuilder-v2-mcp", "--transport", "sse"]
    )
    with pytest.raises(SystemExit) as exc:
        cli.run_mcp()
    assert exc.value.code != 0
    assert captured_main == []

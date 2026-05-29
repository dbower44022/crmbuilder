"""Unit tests for the chat tool dispatcher + schema generation (Slice D).

Covers ``_schema_from_signature``, ``ChatToolDispatcher`` (tools block,
read-only partition, dispatch), and ``summarize_result``. Tool dispatch
runs against an ``httpx.MockTransport`` so no live API is needed.
"""

from __future__ import annotations

import httpx
import pytest
from crmbuilder_v2.ui.chat import tools as chat_tools
from crmbuilder_v2.ui.chat.tools import ChatToolDispatcher, _schema_from_signature

pytestmark = pytest.mark.v2


def _envelope(handler):
    return httpx.AsyncClient(
        base_url="http://test.invalid", transport=httpx.MockTransport(handler)
    )


def test_schema_from_signature_required_and_optional():
    async def fn(identifier: str, limit: int = 3, flag: bool = True) -> object:
        return None

    schema = _schema_from_signature(fn)
    assert schema["type"] == "object"
    assert schema["properties"]["identifier"] == {"type": "string"}
    assert schema["properties"]["limit"] == {"type": "integer"}
    assert schema["properties"]["flag"] == {"type": "boolean"}
    # Only the no-default param is required.
    assert schema["required"] == ["identifier"]


def test_schema_from_signature_optional_union_and_generics():
    async def fn(
        a: str | None = None, items: list | None = None, meta: dict = None
    ) -> object:
        return None

    schema = _schema_from_signature(fn)
    assert schema["properties"]["a"] == {"type": "string"}
    assert schema["properties"]["items"] == {"type": "array"}
    assert schema["properties"]["meta"] == {"type": "object"}
    assert schema["required"] == []


def test_dispatcher_tools_block_and_partition():
    dispatcher = ChatToolDispatcher(_envelope(lambda r: httpx.Response(200)))
    full = dispatcher.tools_block()
    read_only = dispatcher.tools_block(read_only=True)

    # Every block entry has the Anthropic-required shape.
    for entry in full:
        assert set(entry) == {"name", "description", "input_schema"}

    names = {e["name"] for e in full}
    ro_names = {e["name"] for e in read_only}
    # Full surface includes writes; read-only excludes them.
    assert "create_decision" in names
    assert "create_decision" not in ro_names
    assert "list_decisions" in ro_names
    assert dispatcher.is_write("create_decision") is True
    assert dispatcher.is_write("list_decisions") is False
    assert ro_names == dispatcher.read_names
    assert dispatcher.write_names.isdisjoint(ro_names)


async def test_dispatcher_invoke_dispatches_to_endpoint():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        return httpx.Response(
            200, json={"data": {"identifier": "DEC-001"}, "meta": {}, "errors": None}
        )

    dispatcher = ChatToolDispatcher(_envelope(handler))
    result = await dispatcher.invoke("get_decision", {"identifier": "DEC-001"})
    assert seen["path"] == "/decisions/DEC-001"
    assert result == {"identifier": "DEC-001"}


async def test_dispatcher_invoke_unknown_tool_raises():
    dispatcher = ChatToolDispatcher(_envelope(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="unknown tool"):
        await dispatcher.invoke("not_a_tool", {})


async def test_dispatcher_invoke_surfaces_error_envelope():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": None, "meta": {}, "errors": [{"message": "boom"}]},
        )

    dispatcher = ChatToolDispatcher(_envelope(handler))
    with pytest.raises(RuntimeError):
        await dispatcher.invoke("list_decisions", {})


def test_summarize_result_variants():
    assert "DEC-001" in chat_tools.summarize_result(
        "get_decision", {"identifier": "DEC-001"}
    )
    assert "version=3" in chat_tools.summarize_result(
        "get_current_status", {"version": 3}
    )
    assert "5 items" in chat_tools.summarize_result("list_decisions", [1, 2, 3, 4, 5])
    assert "ok" in chat_tools.summarize_result("delete_topic", None)

"""Tests for ChatWorker: streaming loop, tools, modes, error recovery.

The worker is a real ``QThread`` driving a private asyncio loop; the SDK
client and the tool dispatcher are faked at the module level so the
tests need neither an API key nor the network. A ``QEventLoop`` pumps Qt
signals across the worker/main thread boundary until the turn settles.
"""

from __future__ import annotations

import time

import anthropic
import httpx
import pytest
from crmbuilder_v2.ui.chat import worker as worker_mod
from crmbuilder_v2.ui.chat.worker import (
    ChatWorker,
    _cache_messages,
    _cache_tools,
    _system_blocks,
)
from PySide6.QtCore import QEventLoop, QTimer

pytestmark = pytest.mark.v2


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------


class _Text:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _ToolUse:
    type = "tool_use"

    def __init__(self, name: str, tid: str = "t1", inp=None) -> None:
        self.name = name
        self.id = tid
        self.input = inp or {}


class _Usage:
    def __init__(self, i=0, o=0, cc=0, cr=0) -> None:
        self.input_tokens = i
        self.output_tokens = o
        self.cache_creation_input_tokens = cc
        self.cache_read_input_tokens = cr


class _FinalMessage:
    def __init__(self, content, stop_reason, usage=None) -> None:
        self.content = content
        self.stop_reason = stop_reason
        self.usage = usage


class _FakeStream:
    def __init__(self, step) -> None:
        self._chunks, self._final = step

    @property
    def text_stream(self):
        async def gen():
            for chunk in self._chunks:
                yield chunk

        return gen()

    async def get_final_message(self):
        return self._final

    async def close(self):
        pass


class _FakeStreamCM:
    def __init__(self, step) -> None:
        self._step = step

    async def __aenter__(self):
        if isinstance(self._step, BaseException):
            raise self._step
        return _FakeStream(self._step)

    async def __aexit__(self, *exc):
        return False


class _FakeMessages:
    def __init__(self, steps, captured_tools) -> None:
        self._it = iter(steps)
        self._captured = captured_tools

    def stream(self, **kwargs):
        self._captured.append([t["name"] for t in kwargs.get("tools", [])])
        return _FakeStreamCM(next(self._it))


def _anthropic_factory(steps, captured_tools):
    class _FakeAnthropic:
        def __init__(self, *args, **kwargs) -> None:
            self.messages = _FakeMessages(steps, captured_tools)

    return _FakeAnthropic


def _dispatcher_factory(calls):
    class _FakeDispatcher:
        def __init__(self, http) -> None:
            pass

        def tools_block(self, read_only: bool = False):
            names = ["list_decisions"]
            if not read_only:
                names.append("create_decision")
            return [
                {
                    "name": n,
                    "description": "d",
                    "input_schema": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                }
                for n in names
            ]

        def is_write(self, name: str) -> bool:
            return name.startswith(
                ("create_", "update_", "delete_", "add_", "replace_")
            )

        async def invoke(self, name, args):
            calls.append((name, args))
            return {"identifier": "DEC-999"}

    return _FakeDispatcher


def _err(cls, status):
    req = httpx.Request("POST", "http://test.invalid")
    return cls("boom", response=httpx.Response(status, request=req), body=None)


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------


def _drive(qapp, monkeypatch, steps, *, mode="full", confirm=None, fast=True):
    captured_tools: list[list[str]] = []
    invoke_calls: list[tuple] = []
    monkeypatch.setattr(
        worker_mod, "AsyncAnthropic", _anthropic_factory(steps, captured_tools)
    )
    monkeypatch.setattr(
        worker_mod, "ChatToolDispatcher", _dispatcher_factory(invoke_calls)
    )
    if fast:
        monkeypatch.setattr(worker_mod, "_RATE_LIMIT_BACKOFFS", (0.01, 0.01, 0.01))
        monkeypatch.setattr(worker_mod, "_SERVER_RETRY_DELAY", 0.01)

    collected = {
        "deltas": [],
        "tools": [],
        "completed": [],
        "failed": [],
        "retry": [],
        "usage": [],
    }
    worker = ChatWorker("fake-key", "http://test.invalid")
    worker.assistant_delta.connect(lambda t: collected["deltas"].append(t))
    worker.tool_started.connect(lambda n, a: collected["tools"].append(n))
    worker.tool_completed.connect(lambda n, s, r: collected["completed"].append(n))
    worker.tool_failed.connect(lambda n, e: collected["failed"].append((n, e)))
    worker.retry_notice.connect(lambda m: collected["retry"].append(m))
    worker.usage_updated.connect(lambda u: collected["usage"].append(u))
    if confirm is not None:
        worker.confirm_requested.connect(lambda n, a: worker.resolve_confirm(confirm))

    result: dict = {}
    loop = QEventLoop()
    worker.turn_finished.connect(
        lambda r, m: (result.update(reason=r, messages=m), loop.quit())
    )
    worker.turn_failed.connect(
        lambda e, m: (result.update(error=e, messages=m), loop.quit())
    )

    worker.start()
    deadline = time.time() + 3
    while not worker._loop_ready.is_set() and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.01)

    worker.start_turn([{"role": "user", "content": "hi"}], "claude-opus-4-7", mode)
    QTimer.singleShot(8000, loop.quit)
    loop.exec()
    worker.shutdown()
    worker.wait(3000)
    return collected, result, captured_tools, invoke_calls


# --------------------------------------------------------------------------
# Caching helpers (pure)
# --------------------------------------------------------------------------


def test_system_block_cached():
    blocks = _system_blocks()
    assert blocks[0]["type"] == "text"
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}


def test_cache_tools_breakpoint_on_last_only():
    out = _cache_tools([{"name": "a"}, {"name": "b"}])
    assert "cache_control" not in out[0]
    assert out[1]["cache_control"] == {"type": "ephemeral"}


def test_cache_messages_does_not_mutate_original():
    original = [{"role": "user", "content": [{"type": "tool_result", "content": "x"}]}]
    out = _cache_messages(original)
    assert out[0]["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in original[0]["content"][0]


def test_cache_messages_wraps_string_content():
    out = _cache_messages([{"role": "user", "content": "hello"}])
    block = out[0]["content"][0]
    assert block == {
        "type": "text",
        "text": "hello",
        "cache_control": {"type": "ephemeral"},
    }


# --------------------------------------------------------------------------
# Turn loop
# --------------------------------------------------------------------------


def test_streaming_and_tool_round_trip(qapp, monkeypatch):
    steps = [
        (
            ["Let me check. "],
            _FinalMessage(
                [_Text("Let me check. "), _ToolUse("list_decisions")],
                "tool_use",
                _Usage(10, 2),
            ),
        ),
        (
            ["Found them."],
            _FinalMessage([_Text("Found them.")], "end_turn", _Usage(5, 1)),
        ),
    ]
    collected, result, _tools, invoke_calls = _drive(qapp, monkeypatch, steps)
    assert "".join(collected["deltas"]) == "Let me check. Found them."
    assert collected["tools"] == ["list_decisions"]
    assert collected["completed"] == ["list_decisions"]
    assert result["reason"] == "end_turn"
    assert invoke_calls == [("list_decisions", {})]
    # user / assistant(tool_use) / user(tool_result) / assistant(final)
    assert [m["role"] for m in result["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    tool_result_msg = result["messages"][2]["content"]
    assert tool_result_msg[0]["type"] == "tool_result"


def test_usage_accumulates_across_streams(qapp, monkeypatch):
    steps = [
        (
            [""],
            _FinalMessage(
                [_ToolUse("list_decisions")], "tool_use", _Usage(10, 2, 0, 100)
            ),
        ),
        (["done"], _FinalMessage([_Text("done")], "end_turn", _Usage(5, 3, 0, 50))),
    ]
    collected, result, *_ = _drive(qapp, monkeypatch, steps)
    assert result["reason"] == "end_turn"
    assert len(collected["usage"]) == 2
    assert collected["usage"][-1]["cache_read_input_tokens"] == 50


def test_read_only_mode_excludes_write_tools(qapp, monkeypatch):
    steps = [(["hi"], _FinalMessage([_Text("hi")], "end_turn", _Usage()))]
    _collected, result, captured_tools, _calls = _drive(
        qapp, monkeypatch, steps, mode="read_only"
    )
    assert result["reason"] == "end_turn"
    assert captured_tools[0] == ["list_decisions"]  # create_decision excluded


def test_full_mode_includes_write_tools(qapp, monkeypatch):
    steps = [(["hi"], _FinalMessage([_Text("hi")], "end_turn", _Usage()))]
    _c, _r, captured_tools, _calls = _drive(qapp, monkeypatch, steps, mode="full")
    assert "create_decision" in captured_tools[0]


def test_ask_before_write_deny_blocks_invoke(qapp, monkeypatch):
    steps = [
        ([""], _FinalMessage([_ToolUse("create_decision")], "tool_use", _Usage())),
        (["ok"], _FinalMessage([_Text("ok")], "end_turn", _Usage())),
    ]
    collected, result, _t, invoke_calls = _drive(
        qapp, monkeypatch, steps, mode="ask_before_write", confirm=False
    )
    assert result["reason"] == "end_turn"
    assert invoke_calls == []  # denied → never dispatched
    assert collected["failed"] and "denied" in collected["failed"][0][1]


def test_ask_before_write_allow_dispatches(qapp, monkeypatch):
    steps = [
        ([""], _FinalMessage([_ToolUse("create_decision")], "tool_use", _Usage())),
        (["created"], _FinalMessage([_Text("created")], "end_turn", _Usage())),
    ]
    collected, result, _t, invoke_calls = _drive(
        qapp, monkeypatch, steps, mode="ask_before_write", confirm=True
    )
    assert result["reason"] == "end_turn"
    assert invoke_calls == [("create_decision", {})]
    assert collected["completed"] == ["create_decision"]


# --------------------------------------------------------------------------
# Error recovery (design §12)
# --------------------------------------------------------------------------


def test_rate_limit_retries_then_succeeds(qapp, monkeypatch):
    steps = [
        _err(anthropic.RateLimitError, 429),
        (["ok"], _FinalMessage([_Text("ok")], "end_turn", _Usage())),
    ]
    collected, result, *_ = _drive(qapp, monkeypatch, steps)
    assert result["reason"] == "end_turn"
    assert collected["retry"] and "Rate limited" in collected["retry"][0]


def test_server_error_retries_once_then_succeeds(qapp, monkeypatch):
    steps = [
        _err(anthropic.InternalServerError, 500),
        (["ok"], _FinalMessage([_Text("ok")], "end_turn", _Usage())),
    ]
    collected, result, *_ = _drive(qapp, monkeypatch, steps)
    assert result["reason"] == "end_turn"
    assert collected["retry"] and "Connection problem" in collected["retry"][0]


def test_rate_limit_exhausted_fails(qapp, monkeypatch):
    steps = [_err(anthropic.RateLimitError, 429)] * 5
    _collected, result, *_ = _drive(qapp, monkeypatch, steps)
    assert "error" in result


def test_payment_required_message(qapp, monkeypatch):
    steps = [_err(anthropic.APIStatusError, 402)]
    _collected, result, *_ = _drive(qapp, monkeypatch, steps)
    assert "Payment required" in result["error"]


def test_context_window_message(qapp, monkeypatch):
    req = httpx.Request("POST", "http://test.invalid")
    err = anthropic.BadRequestError(
        "prompt is too long: maximum context length exceeded",
        response=httpx.Response(400, request=req),
        body=None,
    )
    _collected, result, *_ = _drive(qapp, monkeypatch, [err])
    assert "context window" in result["error"]

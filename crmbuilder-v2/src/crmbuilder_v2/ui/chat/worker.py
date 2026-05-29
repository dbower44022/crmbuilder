"""Inference worker thread (PI-052 Slice B/C, DEC-257).

``ChatWorker`` is a ``QThread`` that owns a private asyncio event loop
(no ``qasync`` dependency). The loop hosts the ``AsyncAnthropic`` client,
the ``httpx.AsyncClient`` used for tool dispatch, and the
``ChatToolDispatcher`` built from the full governance tool surface. The
Qt main thread talks to it only through thread-safe entry points
(:meth:`start_turn`, :meth:`stop`, :meth:`shutdown`,
:meth:`resolve_confirm`), each of which marshals onto the worker's loop
via ``loop.call_soon_threadsafe``. Results flow back to the main thread
as Qt signals (queued automatically across the thread boundary).

Slice C additions over Slice B:

* Full tool surface via :class:`ChatToolDispatcher` (was one hardcoded
  tool).
* Three-tier prompt caching (design §8): the system block, the tools
  block (cache breakpoint on the last tool), and a rolling breakpoint on
  the most recent message.
* The substantive system prompt (design §13).
* Mode handling: ``full`` exposes all tools, ``read_only`` exposes only
  read tools, ``ask_before_write`` exposes all but confirms each write
  call with the operator before dispatching.
* Per-turn token/usage emission for the header usage display.

The worker never mutates the controller's live session — it works on a
snapshot copy and emits the authoritative post-turn list on
:data:`turn_finished`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any

import anthropic
import httpx
from anthropic import AsyncAnthropic
from PySide6.QtCore import QThread, Signal

from crmbuilder_v2.ui.chat.tools import ChatToolDispatcher, summarize_result

_log = logging.getLogger("crmbuilder_v2.ui.chat.worker")

# Substantive system prompt (design §13). Three sections: role + scope,
# tool-surface semantics, output preferences. Slice C records this as a
# DEC at close-out per the design doc.
SYSTEM_PROMPT = """\
You are an assistant embedded in the CRMBuilder v2 desktop application. \
You have read and write access to Doug's v2 governance database through \
the provided tools. Doug is the sole operator and trusts you to read \
freely and to write when asked; you do not need to ask permission before \
routine reads.

The governance database tracks a software project's decision record. The \
entity types and their identifier conventions:

- charter (singleton, versioned) — the project's mission and principles.
- status (singleton, versioned) — current project state.
- decision (DEC-NNN) — an architectural or process decision, with \
context, rationale, alternatives, consequences, and supersedes / \
superseded_by edges.
- session (SES-NNN) — a medium-agnostic communication container (one \
chat / email / call / meeting), with a six-status lifecycle.
- conversation (CNV-NNN) — a topical sub-unit within a session.
- risk (RISK-NNN), planning_item (PI-NNN), topic (TOP-NNN).
- references — typed cross-entity edges (is_about, supersedes, \
decided_in, affects, covers, blocks, references).
- the base entity catalog — a reference library of CRM entities and \
attributes across surveyed systems, searchable via the catalog_* tools.

Tool conventions: get_* / list_* read; create_* / update_* / delete_* / \
add_* / replace_* write. update_* tools take only the fields to change. \
When you need related records, chain reads (e.g. list_references_from \
then get_decision).

Output preferences: default to terse, direct answers. Cite identifiers \
(DEC-NNN, SES-NNN, etc.) when you reference records. When you call \
multiple tools, batch them in one assistant turn rather than \
serializing. On consequential writes, a brief "Going to create DEC-NNN \
with X, Y, Z — sound right?" is welcome, but you do not need to wait for \
permission unless the operator has set ask-before-write mode."""

_MAX_TOKENS = 8192

# Sentinel pushed onto the turn queue to unblock the loop for shutdown.
_SHUTDOWN = object()

_CACHE_CONTROL = {"type": "ephemeral"}

# Error-recovery tuning (design §12). Rate limits back off 2/4/8s then
# give up; transient server/network errors get one retry after 2s.
_RATE_LIMIT_BACKOFFS = (2, 4, 8)
_SERVER_RETRY_DELAY = 2


def _system_blocks() -> list[dict[str, Any]]:
    """Tier 1: the system prompt as a single cached text block."""
    return [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": _CACHE_CONTROL}]


def _cache_tools(block: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tier 2: copy the tools block with a cache breakpoint on the last tool."""
    if not block:
        return block
    out = [dict(t) for t in block]
    out[-1] = {**out[-1], "cache_control": _CACHE_CONTROL}
    return out


def _cache_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tier 3: copy the message list with a rolling breakpoint on the last
    message's final content block.

    The stored history is never mutated — caching markers live only on the
    per-call copy, so breakpoints don't accumulate across turns.
    """
    if not messages:
        return messages
    out = list(messages)
    last = dict(out[-1])
    content = last.get("content")
    if isinstance(content, str):
        last["content"] = [
            {"type": "text", "text": content, "cache_control": _CACHE_CONTROL}
        ]
        out[-1] = last
    elif isinstance(content, list) and content:
        new_content = list(content)
        last_block = new_content[-1]
        if isinstance(last_block, dict):
            new_content[-1] = {**last_block, "cache_control": _CACHE_CONTROL}
            last["content"] = new_content
            out[-1] = last
    return out


class ChatWorker(QThread):
    """Runs the streaming chat loop on a private asyncio event loop.

    Signals (all delivered to main-thread slots via queued connections):

    * ``assistant_delta(str)`` — a streamed text chunk.
    * ``tool_started(str, str)`` — ``(tool_name, args_json)``.
    * ``tool_completed(str, str, str)`` — ``(name, summary, result_json)``.
    * ``tool_failed(str, str)`` — ``(name, error)``.
    * ``confirm_requested(str, str)`` — ``(name, args_json)`` when a write
      needs operator confirmation (ask-before-write mode). The controller
      replies via :meth:`resolve_confirm`.
    * ``usage_updated(object)`` — token usage dict after each stream.
    * ``turn_finished(str, object)`` — ``(stop_reason, messages)``.
    * ``turn_failed(str, object)`` — ``(error, messages)``.
    * ``auth_failed(str)`` — a 401 from Anthropic.
    """

    assistant_delta = Signal(str)
    tool_started = Signal(str, str)
    tool_completed = Signal(str, str, str)
    tool_failed = Signal(str, str)
    confirm_requested = Signal(str, str)
    usage_updated = Signal(object)
    retry_notice = Signal(str)
    turn_finished = Signal(str, object)
    turn_failed = Signal(str, object)
    auth_failed = Signal(str)

    def __init__(self, api_key: str, base_url: str, parent=None) -> None:
        super().__init__(parent)
        self._api_key = api_key
        self._base_url = base_url
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue | None = None
        self._cancel: asyncio.Event | None = None
        self._confirm_event: asyncio.Event | None = None
        self._confirm_allowed = False
        self._anthropic: AsyncAnthropic | None = None
        self._http: httpx.AsyncClient | None = None
        self._dispatcher: ChatToolDispatcher | None = None
        # Set once the loop + deps exist so the thread-safe entry points
        # (notably shutdown via aboutToQuit) don't race a still-starting
        # loop and leave the thread blocked on an empty queue.
        self._loop_ready = threading.Event()

    # ------------------------------------------------------------------
    # QThread body
    # ------------------------------------------------------------------

    def run(self) -> None:  # noqa: D401 — Qt method
        try:
            asyncio.run(self._main())
        except Exception:  # noqa: BLE001 — last-resort guard
            _log.exception("ChatWorker event loop crashed")

    async def _main(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue()
        self._cancel = asyncio.Event()
        self._confirm_event = asyncio.Event()
        self._anthropic = AsyncAnthropic(api_key=self._api_key)
        self._http = httpx.AsyncClient(base_url=self._base_url, timeout=30.0)
        self._dispatcher = ChatToolDispatcher(self._http)
        self._loop_ready.set()
        try:
            while True:
                item = await self._queue.get()
                if item is _SHUTDOWN:
                    break
                messages, model, mode = item
                self._cancel.clear()
                await self._run_turn(messages, model, mode)
        finally:
            await self._http.aclose()

    # ------------------------------------------------------------------
    # Thread-safe entry points (called from the Qt main thread)
    # ------------------------------------------------------------------

    def start_turn(self, messages: list[dict[str, Any]], model: str, mode: str) -> None:
        """Queue a turn. ``messages`` is a snapshot the worker may own."""
        loop, queue = self._loop, self._queue
        if loop is None or queue is None:
            _log.warning("start_turn before worker loop ready; dropping turn")
            return
        loop.call_soon_threadsafe(queue.put_nowait, (messages, model, mode))

    def stop(self) -> None:
        """Request cancellation of the in-flight turn at the next ``await``."""
        loop, cancel = self._loop, self._cancel
        if loop is None or cancel is None:
            return
        loop.call_soon_threadsafe(cancel.set)

    def resolve_confirm(self, allowed: bool) -> None:
        """Answer a pending ask-before-write confirmation."""
        loop = self._loop
        if loop is None:
            return
        loop.call_soon_threadsafe(self._set_confirm, allowed)

    def shutdown(self) -> None:
        """Unblock the loop and let :meth:`run` return so the thread exits.

        Waits briefly for the loop to finish starting so a shutdown
        requested immediately after :meth:`start` (e.g. via
        ``aboutToQuit``) still reaches a running loop.
        """
        if not self.isRunning():
            return
        if not self._loop_ready.wait(timeout=2.0):
            _log.warning("ChatWorker loop not ready at shutdown; skipping signal")
            return
        loop, queue, cancel = self._loop, self._queue, self._cancel
        if loop is None or queue is None:
            return
        if cancel is not None:
            loop.call_soon_threadsafe(cancel.set)
        loop.call_soon_threadsafe(queue.put_nowait, _SHUTDOWN)

    def _set_confirm(self, allowed: bool) -> None:
        self._confirm_allowed = allowed
        if self._confirm_event is not None:
            self._confirm_event.set()

    # ------------------------------------------------------------------
    # Turn execution
    # ------------------------------------------------------------------

    async def _run_turn(
        self, messages: list[dict[str, Any]], model: str, mode: str
    ) -> None:
        snapshot = list(messages)
        working = list(messages)
        read_only = mode == "read_only"
        try:
            while True:
                if self._cancel is not None and self._cancel.is_set():
                    self.turn_finished.emit("cancelled", working)
                    return
                final = await self._stream_with_retry(working, model, read_only)
                working.append({"role": "assistant", "content": final.content})

                if final.stop_reason != "tool_use":
                    self.turn_finished.emit(final.stop_reason or "end_turn", working)
                    return

                tool_results = await self._execute_tool_calls(final, mode)
                working.append({"role": "user", "content": tool_results})
        except _Cancelled:
            self.turn_finished.emit("cancelled", working)
        except anthropic.AuthenticationError as exc:
            _log.warning("Anthropic auth error during turn: %s", exc)
            self.auth_failed.emit(str(exc))
            self.turn_failed.emit("authentication failed", snapshot)
        except anthropic.BadRequestError as exc:
            self.turn_failed.emit(self._classify_bad_request(exc), snapshot)
        except anthropic.APIStatusError as exc:
            self.turn_failed.emit(self._classify_status_error(exc), snapshot)
        except anthropic.APIConnectionError:
            _log.warning("Network error reaching Anthropic after retry")
            self.turn_failed.emit(
                "Could not reach the Anthropic API. Check your connection "
                "and try again.",
                snapshot,
            )
        except Exception as exc:  # noqa: BLE001 — surface to the UI
            _log.exception("Chat turn failed")
            self.turn_failed.emit(str(exc), snapshot)

    @staticmethod
    def _classify_bad_request(exc: anthropic.BadRequestError) -> str:
        text = str(exc).lower()
        if any(k in text for k in ("context", "too long", "max_tokens", "tokens")):
            return (
                "This conversation exceeded the model's context window. "
                "Start a new chat (+ New) or switch to a model with a larger "
                "context."
            )
        return f"Request rejected: {exc}"

    @staticmethod
    def _classify_status_error(exc: anthropic.APIStatusError) -> str:
        status = getattr(exc, "status_code", None)
        if status == 402:
            return (
                "Payment required (402). Check your Anthropic Console "
                "billing, then try again."
            )
        return f"API error {status}: {exc}"

    async def _stream_with_retry(
        self, messages: list[dict[str, Any]], model: str, read_only: bool
    ):
        """Call the stream with bounded retries (design §12).

        Rate limits back off 2/4/8s; transient server / network errors get
        a single 2s retry. Cancellation interrupts any backoff sleep.
        """
        rate_attempts = 0
        server_retried = False
        while True:
            self._raise_if_cancelled()
            try:
                return await self._stream_once(messages, model, read_only)
            except anthropic.RateLimitError:
                if rate_attempts >= len(_RATE_LIMIT_BACKOFFS):
                    raise
                delay = _RATE_LIMIT_BACKOFFS[rate_attempts]
                rate_attempts += 1
                self.retry_notice.emit(f"Rate limited — retrying in {delay}s…")
                await self._cancellable_sleep(delay)
            except (anthropic.APIConnectionError, anthropic.InternalServerError):
                if server_retried:
                    raise
                server_retried = True
                self.retry_notice.emit(
                    f"Connection problem — retrying in {_SERVER_RETRY_DELAY}s…"
                )
                await self._cancellable_sleep(_SERVER_RETRY_DELAY)

    def _raise_if_cancelled(self) -> None:
        if self._cancel is not None and self._cancel.is_set():
            raise _Cancelled

    async def _cancellable_sleep(self, seconds: float) -> None:
        steps = max(1, int(seconds / 0.1))
        for _ in range(steps):
            self._raise_if_cancelled()
            await asyncio.sleep(0.1)

    async def _stream_once(
        self, messages: list[dict[str, Any]], model: str, read_only: bool
    ):
        assert self._anthropic is not None and self._dispatcher is not None
        tools_block = _cache_tools(self._dispatcher.tools_block(read_only=read_only))
        async with self._anthropic.messages.stream(
            model=model,
            system=_system_blocks(),
            tools=tools_block,
            messages=_cache_messages(messages),
            max_tokens=_MAX_TOKENS,
        ) as stream:
            async for text in stream.text_stream:
                if self._cancel is not None and self._cancel.is_set():
                    await stream.close()
                    raise _Cancelled
                self.assistant_delta.emit(text)
            final = await stream.get_final_message()
        self._emit_usage(final)
        return final

    async def _execute_tool_calls(self, final, mode: str) -> list[dict[str, Any]]:
        assert self._dispatcher is not None
        results: list[dict[str, Any]] = []
        for block in final.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            args = dict(block.input)
            args_json = json.dumps(args, indent=2)
            self.tool_started.emit(block.name, args_json)

            if (
                mode == "ask_before_write"
                and self._dispatcher.is_write(block.name)
                and not await self._confirm_write(block.name, args_json)
            ):
                self.tool_failed.emit(block.name, "denied by operator")
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "error: operator denied this write",
                        "is_error": True,
                    }
                )
                continue

            try:
                result = await self._dispatcher.invoke(block.name, args)
            except Exception as exc:  # noqa: BLE001 — feed back to Claude
                _log.warning("Tool %s failed: %s", block.name, exc)
                self.tool_failed.emit(block.name, str(exc))
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"error: {exc}",
                        "is_error": True,
                    }
                )
                continue
            summary = summarize_result(block.name, result)
            result_json = json.dumps(result, indent=2, default=str)
            self.tool_completed.emit(block.name, summary, result_json)
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, default=str),
                }
            )
        return results

    async def _confirm_write(self, name: str, args_json: str) -> bool:
        """Ask the operator to allow a write call; block until answered."""
        assert self._confirm_event is not None and self._cancel is not None
        self._confirm_allowed = False
        self._confirm_event.clear()
        self.confirm_requested.emit(name, args_json)
        while not self._confirm_event.is_set():
            if self._cancel.is_set():
                raise _Cancelled
            await asyncio.sleep(0.05)
        return self._confirm_allowed

    def _emit_usage(self, final) -> None:
        usage = getattr(final, "usage", None)
        if usage is None:
            return
        self.usage_updated.emit(
            {
                "input_tokens": getattr(usage, "input_tokens", 0) or 0,
                "output_tokens": getattr(usage, "output_tokens", 0) or 0,
                "cache_creation_input_tokens": getattr(
                    usage, "cache_creation_input_tokens", 0
                )
                or 0,
                "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0)
                or 0,
            }
        )


class _Cancelled(Exception):
    """Internal marker raised when the cancel event trips mid-stream."""

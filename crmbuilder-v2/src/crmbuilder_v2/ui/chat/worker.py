"""Inference worker thread (PI-052 Slice B, DEC-257).

``ChatWorker`` is a ``QThread`` that owns a private asyncio event loop
(no ``qasync`` dependency). The loop hosts the ``AsyncAnthropic`` client
and the ``httpx.AsyncClient`` used for tool dispatch, and runs the
streaming chat loop. The Qt main thread talks to it only through three
thread-safe entry points — :meth:`start_turn`, :meth:`stop`,
:meth:`shutdown` — each of which marshals onto the worker's loop via
``loop.call_soon_threadsafe``. Results flow back to the main thread as
Qt signals (queued automatically across the thread boundary).

Slice B runs a single turn at a time. The controller gates Send so a new
turn can't start while one is in flight.

The worker never mutates the controller's live session. It receives a
snapshot of the messages list, works on a local copy, and emits the full
post-turn list on :data:`turn_finished` so the controller can install it
without cross-thread list mutation.
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

from crmbuilder_v2.ui.chat import tools

_log = logging.getLogger("crmbuilder_v2.ui.chat.worker")

# Slice B placeholder system prompt. The substantive prompt-engineering
# work (design §13) is a Slice C deliverable issued as a DEC at that time.
SYSTEM_PROMPT = (
    "You are an assistant embedded in the CRMBuilder v2 desktop "
    "application. You have read access to Doug's v2 governance database "
    "via the provided tools. Doug is the sole operator. Default to terse "
    "responses and cite identifiers (DEC-NNN, SES-NNN, etc.) when "
    "answering. Call get_current_status when asked about current project "
    "state."
)

_MAX_TOKENS = 8192

# Sentinel pushed onto the turn queue to unblock the loop for shutdown.
_SHUTDOWN = object()


class ChatWorker(QThread):
    """Runs the streaming chat loop on a private asyncio event loop.

    Signals (all delivered to main-thread slots via queued connections):

    * ``assistant_delta(str)`` — a streamed text chunk for the live
      assistant bubble.
    * ``tool_started(str, str)`` — ``(tool_name, args_json)`` just before
      a tool is dispatched.
    * ``tool_completed(str, str, str)`` — ``(tool_name, summary,
      result_json)`` after a successful tool call.
    * ``tool_failed(str, str)`` — ``(tool_name, error)`` on tool error.
    * ``turn_finished(str, object)`` — ``(stop_reason, messages)`` when a
      turn settles (``stop_reason`` is ``"end_turn"`` / ``"cancelled"`` /
      whatever the API returned). ``messages`` is the authoritative
      post-turn list for the controller to install.
    * ``turn_failed(str, object)`` — ``(error, messages)`` on an
      unrecoverable error; ``messages`` is the pre-turn snapshot.
    * ``auth_failed(str)`` — a 401 from Anthropic; the panel re-prompts
      for the API key (error matrix §12).
    """

    assistant_delta = Signal(str)
    tool_started = Signal(str, str)
    tool_completed = Signal(str, str, str)
    tool_failed = Signal(str, str)
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
        self._anthropic: AsyncAnthropic | None = None
        self._http: httpx.AsyncClient | None = None
        # Set once the loop + queue exist, so the thread-safe entry points
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
        self._anthropic = AsyncAnthropic(api_key=self._api_key)
        self._http = httpx.AsyncClient(base_url=self._base_url, timeout=30.0)
        self._loop_ready.set()
        try:
            while True:
                item = await self._queue.get()
                if item is _SHUTDOWN:
                    break
                messages, model = item
                self._cancel.clear()
                await self._run_turn(messages, model)
        finally:
            await self._http.aclose()

    # ------------------------------------------------------------------
    # Thread-safe entry points (called from the Qt main thread)
    # ------------------------------------------------------------------

    def start_turn(self, messages: list[dict[str, Any]], model: str) -> None:
        """Queue a turn. ``messages`` is a snapshot the worker may own."""
        loop, queue = self._loop, self._queue
        if loop is None or queue is None:
            _log.warning("start_turn before worker loop ready; dropping turn")
            return
        loop.call_soon_threadsafe(queue.put_nowait, (messages, model))

    def stop(self) -> None:
        """Request cancellation of the in-flight turn at the next ``await``."""
        loop, cancel = self._loop, self._cancel
        if loop is None or cancel is None:
            return
        loop.call_soon_threadsafe(cancel.set)

    def shutdown(self) -> None:
        """Unblock the loop and let :meth:`run` return so the thread exits.

        Waits briefly for the loop to finish starting so a shutdown
        requested immediately after :meth:`start` (e.g. via
        ``aboutToQuit``) still reaches a running loop — otherwise the
        sentinel would never be queued and the thread would block until
        the caller's ``wait()`` timed out.
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

    # ------------------------------------------------------------------
    # Turn execution
    # ------------------------------------------------------------------

    async def _run_turn(self, messages: list[dict[str, Any]], model: str) -> None:
        snapshot = list(messages)
        working = list(messages)
        try:
            while True:
                if self._cancel is not None and self._cancel.is_set():
                    self.turn_finished.emit("cancelled", working)
                    return
                final = await self._stream_once(working, model)
                working.append({"role": "assistant", "content": final.content})

                if final.stop_reason != "tool_use":
                    self.turn_finished.emit(final.stop_reason or "end_turn", working)
                    return

                tool_results = await self._execute_tool_calls(final)
                working.append({"role": "user", "content": tool_results})
        except _Cancelled:
            self.turn_finished.emit("cancelled", working)
        except anthropic.AuthenticationError as exc:
            _log.warning("Anthropic auth error during turn: %s", exc)
            self.auth_failed.emit(str(exc))
            self.turn_failed.emit("authentication failed", snapshot)
        except Exception as exc:  # noqa: BLE001 — surface to the UI
            _log.exception("Chat turn failed")
            self.turn_failed.emit(str(exc), snapshot)

    async def _stream_once(self, messages: list[dict[str, Any]], model: str):
        assert self._anthropic is not None
        async with self._anthropic.messages.stream(
            model=model,
            system=SYSTEM_PROMPT,
            tools=tools.TOOL_DEFINITIONS,
            messages=messages,
            max_tokens=_MAX_TOKENS,
        ) as stream:
            async for text in stream.text_stream:
                if self._cancel is not None and self._cancel.is_set():
                    await stream.close()
                    raise _Cancelled
                self.assistant_delta.emit(text)
            return await stream.get_final_message()

    async def _execute_tool_calls(self, final) -> list[dict[str, Any]]:
        assert self._http is not None
        results: list[dict[str, Any]] = []
        for block in final.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            args = dict(block.input)
            self.tool_started.emit(block.name, json.dumps(args, indent=2))
            try:
                result = await tools.invoke(block.name, args, self._http)
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
            summary = tools.summarize_result(block.name, result)
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


class _Cancelled(Exception):
    """Internal marker raised when the cancel event trips mid-stream."""

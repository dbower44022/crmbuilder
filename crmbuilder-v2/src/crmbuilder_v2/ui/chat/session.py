"""In-memory chat session model (PI-052 Slice B).

``ChatSession`` holds the running transcript in Anthropic Messages API
format. Slice B keeps it entirely in memory — no JSON-file persistence,
no usage rollup, no multi-conversation list. The dataclass mirrors the
shape the design doc §2.5 specifies so Slice C can layer persistence on
top without reshaping the message store.

The message list is the single source of truth fed to
``messages.stream(messages=...)``. Three append helpers keep the list in
the exact shape the SDK expects:

* :meth:`append_user` — a plain user text turn.
* :meth:`append_assistant` — the assistant content blocks returned by
  ``stream.get_final_message()`` (text + tool_use blocks).
* :meth:`append_tool_results` — a user turn carrying ``tool_result``
  content blocks for the tool calls the prior assistant turn requested.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_MODE = "full"


@dataclass
class ChatSession:
    """A single in-memory chat conversation.

    Slice B always uses the implicit singleton session held by the
    controller; ``chat_id`` / ``title`` exist for forward compatibility
    with Slice C's multi-conversation sidebar but are otherwise unused.
    """

    chat_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    title: str = "New chat"
    model: str = DEFAULT_MODEL
    mode: str = DEFAULT_MODE
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    messages: list[dict[str, Any]] = field(default_factory=list)

    def messages_for_api(self) -> list[dict[str, Any]]:
        """Return the message list in the format the SDK expects."""
        return self.messages

    def append_user(self, text: str) -> None:
        """Append a plain user text turn."""
        self.messages.append({"role": "user", "content": text})
        self._touch()
        if self.title == "New chat" and text.strip():
            self.title = text.strip()[:60]

    def append_assistant(self, content_blocks: Any) -> None:
        """Append the assistant content blocks from the final message.

        ``content_blocks`` is the ``content`` list returned by
        ``stream.get_final_message()`` — a list of SDK content-block
        models. The SDK accepts its own models directly in a subsequent
        ``messages=`` argument, so they are stored as-is.
        """
        self.messages.append({"role": "assistant", "content": content_blocks})
        self._touch()

    def append_tool_results(self, tool_results: list[dict[str, Any]]) -> None:
        """Append a user turn carrying ``tool_result`` content blocks."""
        self.messages.append({"role": "user", "content": tool_results})
        self._touch()

    def replace_messages(self, messages: list[dict[str, Any]]) -> None:
        """Replace the message list with the authoritative post-turn list.

        The worker runs a turn against a snapshot copy and emits the
        full updated list when the turn settles; the controller installs
        it here so cross-thread mutation of the live list never happens.
        """
        self.messages = messages
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)

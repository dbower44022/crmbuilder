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
SCHEMA_VERSION = 1


def _empty_usage() -> dict[str, int]:
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.now(UTC)


def _block_to_jsonable(block: Any) -> Any:
    """Convert one message content block to a JSON-serializable dict.

    Assistant turns store the SDK's content-block models (TextBlock,
    ToolUseBlock); ``model_dump(mode="json", exclude_none=True)`` yields
    a dict the Messages API accepts back verbatim. User-text strings and
    already-dict tool_result blocks pass through unchanged.
    """
    if isinstance(block, dict) or isinstance(block, str):
        return block
    dump = getattr(block, "model_dump", None)
    if callable(dump):
        return dump(mode="json", exclude_none=True)
    return block


def _content_to_jsonable(content: Any) -> Any:
    if isinstance(content, list):
        return [_block_to_jsonable(b) for b in content]
    return content


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
    usage: dict[str, int] = field(default_factory=_empty_usage)

    def messages_for_api(self) -> list[dict[str, Any]]:
        """Return the message list in the format the SDK expects."""
        return self.messages

    # ------------------------------------------------------------------
    # Serialization (Slice C persistence)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the on-disk JSON shape (design §6 file format)."""
        return {
            "chat_id": self.chat_id,
            "schema_version": SCHEMA_VERSION,
            "title": self.title,
            "model": self.model,
            "mode": self.mode,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "messages": [
                {"role": m["role"], "content": _content_to_jsonable(m["content"])}
                for m in self.messages
            ],
            "usage": dict(self.usage),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChatSession:
        """Rebuild a session from its on-disk JSON shape."""
        usage = _empty_usage()
        usage.update(data.get("usage") or {})
        return cls(
            chat_id=data["chat_id"],
            title=data.get("title", "New chat"),
            model=data.get("model", DEFAULT_MODEL),
            mode=data.get("mode", DEFAULT_MODE),
            created_at=_parse_dt(data.get("created_at")),
            updated_at=_parse_dt(data.get("updated_at")),
            messages=data.get("messages", []),
            usage=usage,
        )

    def is_persistable(self) -> bool:
        """A session is worth writing to disk once it has any messages."""
        return bool(self.messages)

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

"""Chat session persistence (PI-052 Slice C, DEC-256).

Chat sessions are JSON files under ``~/.crmbuilder-v2/chats/`` — one file
per chat, named ``<chat_id>.json``. They are NOT governance entities
(DEC-256): a chat is an ad-hoc Q&A surface, not an audit-chain record.

Writes are atomic (tmp file + ``os.replace``) so a crash mid-write can't
corrupt an existing chat. The conversation sidebar reads
:func:`list_summaries` on panel open; switching chats calls
:func:`load`.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from crmbuilder_v2.ui.chat.session import ChatSession

_log = logging.getLogger("crmbuilder_v2.ui.chat.persistence")

_CHATS_DIR = Path("~/.crmbuilder-v2/chats").expanduser()


def chats_dir() -> Path:
    """Return the chats directory, creating it if needed."""
    _CHATS_DIR.mkdir(parents=True, exist_ok=True)
    return _CHATS_DIR


@dataclass(frozen=True)
class ChatSummary:
    """Lightweight sidebar entry — avoids loading full transcripts."""

    chat_id: str
    title: str
    updated_at: datetime


def save(session: ChatSession) -> None:
    """Atomically write ``session`` to ``<chat_id>.json``.

    No-op for an empty session (nothing worth persisting yet).
    """
    if not session.is_persistable():
        return
    directory = chats_dir()
    target = directory / f"{session.chat_id}.json"
    tmp = directory / f".{session.chat_id}.json.tmp"
    try:
        tmp.write_text(
            json.dumps(session.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp, target)
    except OSError:
        _log.exception("Failed to persist chat %s", session.chat_id)
        tmp.unlink(missing_ok=True)


def load(chat_id: str) -> ChatSession | None:
    """Load one chat by id, or ``None`` if missing/unreadable."""
    path = chats_dir() / f"{chat_id}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _log.warning("Could not read chat %s", chat_id, exc_info=True)
        return None
    return ChatSession.from_dict(data)


def list_summaries() -> list[ChatSummary]:
    """Return chat summaries, most-recently-updated first."""
    summaries: list[ChatSummary] = []
    for path in chats_dir().glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _log.warning("Skipping unreadable chat file %s", path, exc_info=True)
            continue
        try:
            updated = datetime.fromisoformat(data.get("updated_at", ""))
        except ValueError:
            updated = datetime.fromtimestamp(path.stat().st_mtime)
        summaries.append(
            ChatSummary(
                chat_id=data.get("chat_id", path.stem),
                title=data.get("title", "Untitled chat"),
                updated_at=updated,
            )
        )
    summaries.sort(key=lambda s: s.updated_at, reverse=True)
    return summaries


def delete(chat_id: str) -> None:
    """Delete a chat's JSON file (no-op if it's already gone)."""
    (chats_dir() / f"{chat_id}.json").unlink(missing_ok=True)


def rename(chat_id: str, title: str) -> ChatSession | None:
    """Set a chat's title and re-save. Returns the updated session."""
    session = load(chat_id)
    if session is None:
        return None
    session.title = title
    save(session)
    return session


def to_markdown(session: ChatSession) -> str:
    """Render a chat as a Markdown document: front-matter + linear transcript."""
    lines = [
        "---",
        f"title: {session.title}",
        f"chat_id: {session.chat_id}",
        f"model: {session.model}",
        f"created_at: {session.created_at.isoformat()}",
        f"updated_at: {session.updated_at.isoformat()}",
        "---",
        "",
        f"# {session.title}",
        "",
    ]
    for message in session.messages:
        lines.extend(_message_markdown(message.get("role"), message.get("content")))
    return "\n".join(lines).rstrip() + "\n"


def _message_markdown(role: str, content) -> list[str]:
    out: list[str] = []
    if role == "user":
        if isinstance(content, str):
            out.append(f"**User:** {content}")
            out.append("")
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_result":
                    out.append(f"↩︎ `{block.get('content', '')}`")
                    out.append("")
                elif block.get("type") == "text":
                    out.append(f"**User:** {block.get('text', '')}")
                    out.append("")
        return out
    if role == "assistant" and isinstance(content, list):
        for block in content:
            btype = (
                block.get("type")
                if isinstance(block, dict)
                else getattr(block, "type", None)
            )
            if btype == "text":
                text = (
                    block.get("text", "")
                    if isinstance(block, dict)
                    else getattr(block, "text", "")
                )
                out.append(f"**Assistant:** {text}")
                out.append("")
            elif btype == "tool_use":
                name = (
                    block.get("name", "")
                    if isinstance(block, dict)
                    else getattr(block, "name", "")
                )
                args = (
                    block.get("input", {})
                    if isinstance(block, dict)
                    else getattr(block, "input", {})
                )
                out.append(f"🔧 `{name}({json.dumps(args)})`")
                out.append("")
    return out

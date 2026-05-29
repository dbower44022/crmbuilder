"""Tests for ChatSession serialization and JSON persistence (Slice D).

The chats directory is redirected to a tmp path via monkeypatch so the
suite never touches ``~/.crmbuilder-v2/chats``.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.ui.chat import persistence
from crmbuilder_v2.ui.chat.session import ChatSession

pytestmark = pytest.mark.v2


@pytest.fixture
def chats_dir(tmp_path, monkeypatch):
    target = tmp_path / "chats"
    monkeypatch.setattr(persistence, "_CHATS_DIR", target)
    return target


class _TextBlock:
    """Stand-in for an SDK content-block model (has model_dump)."""

    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text

    def model_dump(self, mode=None, exclude_none=False):
        return {"type": "text", "text": self.text}


def _sample_session() -> ChatSession:
    session = ChatSession()
    session.append_user("What decisions exist?")
    session.append_assistant([_TextBlock("Let me check.")])
    session.append_tool_results(
        [{"type": "tool_result", "tool_use_id": "t1", "content": "[...]"}]
    )
    session.append_assistant([_TextBlock("There are 313 decisions.")])
    session.usage["input_tokens"] = 500
    session.usage["cache_read_input_tokens"] = 1200
    return session


def test_title_set_from_first_user_turn():
    session = ChatSession()
    session.append_user("Audit the DEC-245 chain")
    assert session.title == "Audit the DEC-245 chain"


def test_to_dict_serializes_sdk_blocks_to_dicts():
    session = _sample_session()
    data = session.to_dict()
    assert data["schema_version"] == 1
    assistant = data["messages"][1]
    assert assistant["role"] == "assistant"
    assert all(isinstance(b, dict) for b in assistant["content"])
    assert assistant["content"][0] == {"type": "text", "text": "Let me check."}


def test_round_trip_preserves_history_and_usage():
    session = _sample_session()
    restored = ChatSession.from_dict(session.to_dict())
    assert restored.chat_id == session.chat_id
    assert restored.title == session.title
    assert [m["role"] for m in restored.messages] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert restored.usage["input_tokens"] == 500
    assert restored.usage["cache_read_input_tokens"] == 1200


def test_save_skips_empty_session(chats_dir):
    persistence.save(ChatSession())
    assert not list(chats_dir.glob("*.json"))


def test_save_load_round_trip(chats_dir):
    session = _sample_session()
    persistence.save(session)
    loaded = persistence.load(session.chat_id)
    assert loaded is not None
    assert loaded.title == session.title
    assert len(loaded.messages) == 4


def test_load_missing_returns_none(chats_dir):
    assert persistence.load("does-not-exist") is None


def test_list_summaries_orders_by_updated_desc(chats_dir):
    import time

    older = ChatSession()
    older.append_user("older chat")
    persistence.save(older)
    time.sleep(0.01)
    newer = ChatSession()
    newer.append_user("newer chat")
    persistence.save(newer)

    summaries = persistence.list_summaries()
    assert [s.chat_id for s in summaries][:2] == [newer.chat_id, older.chat_id]


def test_rename(chats_dir):
    session = _sample_session()
    persistence.save(session)
    persistence.rename(session.chat_id, "Renamed")
    assert persistence.load(session.chat_id).title == "Renamed"


def test_delete(chats_dir):
    session = _sample_session()
    persistence.save(session)
    persistence.delete(session.chat_id)
    assert persistence.load(session.chat_id) is None
    persistence.delete(session.chat_id)  # idempotent


def test_to_markdown(chats_dir):
    session = _sample_session()
    md = persistence.to_markdown(session)
    assert f"chat_id: {session.chat_id}" in md
    assert "**User:** What decisions exist?" in md
    assert "**Assistant:** There are 313 decisions." in md

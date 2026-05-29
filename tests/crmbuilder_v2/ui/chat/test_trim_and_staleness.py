"""Pure-logic tests for the PI-106 follow-ups.

Covers the two riskiest pieces of new logic, both Qt-free:

* :func:`trim_oldest_turns` must always leave the message list in a shape
  the Messages API accepts — it must begin on a fresh user turn and must
  never orphan a ``tool_result`` from its ``tool_use``.
* :func:`entity_type_for_tool` must disambiguate names that contain more
  than one entity token (e.g. ``list_decisions_for_session`` is a
  ``decision`` read, not a ``session`` read).
"""

from __future__ import annotations

from crmbuilder_v2.ui.chat.session import (
    trim_oldest_turns,
    turn_start_indices,
)
from crmbuilder_v2.ui.chat.tools import entity_type_for_tool


def _tool_round(text: str) -> list[dict]:
    """A user text turn + an assistant tool_use + the user tool_result."""
    return [
        {"role": "user", "content": text},
        {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": "t1", "name": "x", "input": {}}],
        },
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}],
        },
        {"role": "assistant", "content": [{"type": "text", "text": "done"}]},
    ]


# --------------------------------------------------------------------------
# trim_oldest_turns
# --------------------------------------------------------------------------


def test_trim_noop_when_single_turn():
    msgs = [{"role": "user", "content": "only one"}]
    out = trim_oldest_turns(msgs)
    assert len(out) == len(msgs)
    assert out == msgs


def test_trim_noop_on_empty():
    assert trim_oldest_turns([]) == []


def test_trim_keeps_most_recent_turn_and_shrinks():
    msgs = _tool_round("first") + _tool_round("second")
    # turn starts: index 0 (first) and index 4 (second). One gets dropped.
    assert turn_start_indices(msgs) == [0, 4]
    out = trim_oldest_turns(msgs)
    assert len(out) < len(msgs)
    # Result begins on a fresh user turn (plain text), not a tool_result.
    assert out[0]["role"] == "user"
    assert out[0]["content"] == "second"


def test_trim_never_orphans_tool_result():
    msgs = _tool_round("a") + _tool_round("b") + _tool_round("c")
    out = trim_oldest_turns(msgs)
    # The first message must be a fresh user turn; a list-content first
    # message must not be a tool_result carrier.
    first = out[0]
    assert first["role"] == "user"
    if isinstance(first["content"], list):
        assert all(b.get("type") != "tool_result" for b in first["content"])
    # Every tool_result in the trimmed list is preceded by its tool_use.
    seen_tool_use_ids: set[str] = set()
    for msg in out:
        content = msg["content"]
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") == "tool_use":
                seen_tool_use_ids.add(block["id"])
            elif block.get("type") == "tool_result":
                assert block["tool_use_id"] in seen_tool_use_ids


# --------------------------------------------------------------------------
# entity_type_for_tool
# --------------------------------------------------------------------------


def test_entity_type_simple_reads():
    assert entity_type_for_tool("list_decisions") == "decision"
    assert entity_type_for_tool("get_session") == "session"
    assert entity_type_for_tool("get_current_charter") == "charter"
    assert entity_type_for_tool("list_planning_items") == "planning_item"
    assert entity_type_for_tool("list_references_to") == "reference"


def test_entity_type_disambiguates_decisions_for_session():
    # Contains both "decision" and "session"; the data read is decisions.
    assert entity_type_for_tool("list_decisions_for_session") == "decision"


def test_entity_type_none_for_catalog_and_writes():
    assert entity_type_for_tool("catalog_search") is None
    assert entity_type_for_tool("catalog_get_entity") is None

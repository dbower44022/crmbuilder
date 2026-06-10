"""Write-back primitive: appending a CRM-only field to a fields: sequence.

Asserts the new block is correctly indented, the rest of the file is byte-for-byte
unchanged, and the result re-parses with the new field present.
"""
from __future__ import annotations

from ruamel.yaml import YAML

from espo_impl.core.reconcile.document import YamlDocument
from espo_impl.core.reconcile.patcher import insert_field

FIXTURE = '''\
version: "1.0"
content_version: "1.0.0"
entities:
  Session:
    fields:

      - name: sessionType
        type: enum
        label: "Session Type"   # kept

      - name: meetingLocationType
        type: enum
        label: "Meeting Location Type"
    layout:
      detail:
        panels:
          - label: "A"
'''


def _reparse(text):
    return YAML().load(text)


def test_insert_appends_field_and_leaves_rest_intact():
    doc = YamlDocument(FIXTURE)
    insert_field(doc, "Session", {"name": "linkedinUrl", "type": "url", "label": "LinkedIn URL"})
    out = doc.render()

    # Everything up to and including the last original field line is unchanged;
    # the new content is purely additive (no original line altered or removed).
    assert FIXTURE.splitlines()[:13] == out.splitlines()[:13]
    assert "      - name: linkedinUrl" in out
    assert "        type: url" in out
    assert "        label: LinkedIn URL" in out

    # The trailing 'layout:' sibling block survived after the inserted field.
    assert "    layout:" in out
    assert out.index("- name: linkedinUrl") < out.index("    layout:")


def test_inserted_field_is_parseable_and_correct():
    doc = YamlDocument(FIXTURE)
    insert_field(doc, "Session", {"name": "topic", "type": "varchar", "label": "Topic"})
    data = _reparse(doc.render())

    names = [f["name"] for f in data["entities"]["Session"]["fields"]]
    assert names == ["sessionType", "meetingLocationType", "topic"]
    topic = data["entities"]["Session"]["fields"][-1]
    assert topic["type"] == "varchar" and topic["label"] == "Topic"


def test_insert_preserves_comments_on_existing_fields():
    doc = YamlDocument(FIXTURE)
    insert_field(doc, "Session", {"name": "topic", "type": "varchar", "label": "Topic"})
    out = doc.render()
    assert 'label: "Session Type"   # kept' in out


def test_insert_blank_line_separator_matches_style():
    doc = YamlDocument(FIXTURE)
    insert_field(doc, "Session", {"name": "topic", "type": "varchar", "label": "Topic"})
    out = doc.render().splitlines()
    i = out.index("      - name: topic")
    assert out[i - 1] == ""  # blank line before the new item, like the others


def test_insert_nested_options_list():
    doc = YamlDocument(FIXTURE)
    insert_field(doc, "Session", {
        "name": "mode", "type": "enum", "label": "Mode", "options": ["Remote", "In-Person"],
    })
    data = _reparse(doc.render())
    mode = data["entities"]["Session"]["fields"][-1]
    assert mode["options"] == ["Remote", "In-Person"]


def test_insert_duplicate_field_rejected():
    doc = YamlDocument(FIXTURE)
    try:
        insert_field(doc, "Session", {"name": "sessionType", "type": "enum", "label": "x"})
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for duplicate field")

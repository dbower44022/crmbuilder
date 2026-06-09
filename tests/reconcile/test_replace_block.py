"""Write-back primitive: replacing a block body (per-layout-type reconciliation)."""
from __future__ import annotations

from ruamel.yaml import YAML

from espo_impl.core.reconcile.document import YamlDocument

FIXTURE = '''\
entities:
  Session:
    layout:
      list:
        columns:
          - field: name
            width: 30
          - field: status
            width: 16
      detail:
        panels:
          - label: "Overview"   # kept
    settings:
      autoPlaceName: true
'''


def _reparse(text):
    return YAML().load(text)


def test_replace_list_body_leaves_siblings_intact():
    doc = YamlDocument(FIXTURE)
    layout = doc.data["entities"]["Session"]["layout"]
    new = {"columns": [{"field": "name", "width": 40}, {"field": "dateStart"}]}
    doc.replace_block_body(layout, "list", new)
    out = doc.render()

    data = _reparse(out)
    cols = data["entities"]["Session"]["layout"]["list"]["columns"]
    assert cols == [{"field": "name", "width": 40}, {"field": "dateStart"}]

    # The detail sibling (and its comment) and the settings block are untouched.
    assert 'label: "Overview"   # kept' in out
    assert "    settings:" in out
    assert "      autoPlaceName: true" in out
    # list: key line itself preserved.
    assert "      list:" in out


def test_replaced_body_indentation_is_correct():
    doc = YamlDocument(FIXTURE)
    layout = doc.data["entities"]["Session"]["layout"]
    doc.replace_block_body(layout, "detail", {"panels": [{"label": "New"}]})
    out = doc.render().splitlines()

    # detail: at col 6 -> body 'panels:' at col 8.
    i = out.index("      detail:")
    assert out[i + 1] == "        panels:"


def test_inline_value_rejected():
    doc = YamlDocument("entities:\n  Session:\n    type: Base\n")
    session = doc.data["entities"]["Session"]
    try:
        doc.replace_block_body(session, "type", {"x": 1})
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for inline scalar value")

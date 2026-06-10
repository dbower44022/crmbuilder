"""Regression: CHANGED field diffs on multi-line block values (options/style).

set_field_property must route a block-authored property through replace_block_body
(set_scalar only handles single-line tokens). This gap was found applying real
CBM drift — contactType.options/style and engagementStatus.options are block lists
/maps and previously errored out.
"""
from __future__ import annotations

from ruamel.yaml import YAML

from espo_impl.core.reconcile.document import YamlDocument
from espo_impl.core.reconcile.patcher import set_field_property

FIXTURE = '''\
entities:
  Contact:
    fields:

      - name: contactType
        type: enum
        label: "Contact Type"
        options:
          - Client
          - Mentor
        style:
          Client: primary
          Mentor: success

      - name: status
        type: enum
        label: "Status"   # untouched
'''


def _reparse(text):
    return YAML().load(text)


def test_block_options_list_replaced():
    doc = YamlDocument(FIXTURE)
    set_field_property(doc, "Contact", "contactType", "options", ["", "Client", "Mentor", "Partner"])
    out = doc.render()

    data = _reparse(out)
    ct = data["entities"]["Contact"]["fields"][0]
    assert ct["options"] == ["", "Client", "Mentor", "Partner"]
    # sibling field + its comment, and the field's other keys, intact.
    assert 'label: "Status"   # untouched' in out
    assert "        label: \"Contact Type\"" in out


def test_block_style_mapping_replaced():
    doc = YamlDocument(FIXTURE)
    set_field_property(doc, "Contact", "contactType", "style",
                       {"Client": "primary", "Mentor": "success", "Partner": "info"})
    out = doc.render()

    ct = _reparse(out)["entities"]["Contact"]["fields"][0]
    assert ct["style"] == {"Client": "primary", "Mentor": "success", "Partner": "info"}
    assert ct["options"] == ["Client", "Mentor"]  # options block untouched


def test_inline_empty_list_still_uses_scalar_path():
    doc = YamlDocument(
        "entities:\n  A:\n    fields:\n      - name: f\n        type: enum\n        options: []\n"
    )
    set_field_property(doc, "A", "f", "options", ["x", "y"])
    out = doc.render()
    assert _reparse(out)["entities"]["A"]["fields"][0]["options"] == ["x", "y"]


def test_scalar_property_unaffected():
    doc = YamlDocument(FIXTURE)
    set_field_property(doc, "Contact", "contactType", "label", "Type")
    out = doc.render()
    assert _reparse(out)["entities"]["Contact"]["fields"][0]["label"] == "Type"
    # block siblings untouched
    assert _reparse(out)["entities"]["Contact"]["fields"][0]["options"] == ["Client", "Mentor"]

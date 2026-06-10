"""Layout reverse-mapping (payload -> YAML body) + write-back integration.

Verified end-to-end live against CBM (Account.detail round-trips losslessly:
apply the reverse-mapped body, re-detect, no residual drift). These lock the
shape/name-reversal offline and the reconciler's apply-with-body path.
"""
from __future__ import annotations

import json
from pathlib import Path

from ruamel.yaml import YAML

from espo_impl.core.reconcile.document import YamlDocument
from espo_impl.core.reconcile.layout_reverse import reverse_layout_payload
from espo_impl.core.reconcile.locators import LayoutLocator
from espo_impl.core.reconcile.models import ConfigType, DiffCategory, Difference
from espo_impl.core.reconcile.reconciler import apply_reconciliation

_FIX = Path(__file__).resolve().parents[1] / "fixtures" / "layouts"


def test_list_payload_to_columns_body_with_name_reversal():
    payload = [
        {"name": "name", "link": True},
        {"name": "cAccountType", "width": 25},  # custom -> reversed
        {"name": "emailAddress"},               # native -> unchanged
    ]
    body = reverse_layout_payload("list", payload, {"cAccountType"})
    assert body == {
        "columns": [
            {"field": "name", "link": True},
            {"field": "accountType", "width": 25},
            {"field": "emailAddress"},
        ]
    }


def test_detail_payload_to_panels_body():
    payload = [{"label": "Main", "rows": [[{"name": "name"}, {"name": "cFoo"}]]}]
    body = reverse_layout_payload("detail", payload, {"cFoo"})
    assert body["panels"][0]["label"] == "Main"
    assert body["panels"][0]["rows"] == [["name", "foo"]]  # plain cells, name reversed


def test_real_detail_fixture_produces_panels_with_no_cprefix():
    payload = json.loads((_FIX / "Contact.detail.json").read_text())
    body = reverse_layout_payload("detail", payload, {"cPreferredName", "cLinkedInProfile"})
    assert "panels" in body
    flat = json.dumps(body)
    assert "cPreferredName" not in flat and "preferredName" in flat


def test_field_list_and_panel_map_shapes():
    assert reverse_layout_payload("filters", ["cFoo", "name"], {"cFoo"}) == ["foo", "name"]
    pm = {"activities": {"disabled": True}}
    assert reverse_layout_payload("sidePanelsDetail", pm, set()) == pm


def test_reconciler_applies_layout_with_reverse_mapped_body(tmp_path):
    body = (
        'content_version: "1.0.0"\n'
        "entities:\n  Contact:\n    layout:\n      list:\n        columns:\n"
        "          - field: name\n"
    )
    f = tmp_path / "MN-Contact.yaml"
    f.write_text(body)
    diff = Difference(
        config_type=ConfigType.LAYOUT, category=DiffCategory.CHANGED, entity="Contact",
        locator=LayoutLocator("Contact", "list"), property="list",
        crm_value=[{"name": "name"}],  # raw payload (must NOT be written)
        full_crm_block={"columns": [{"field": "name"}, {"field": "account", "width": 25}]},
        source_file=f,
    )

    result = apply_reconciliation([diff])
    fr = result.files[0]
    assert len(fr.applied) == 1
    data = YAML().load(f.read_text())
    cols = data["entities"]["Contact"]["layout"]["list"]["columns"]
    assert cols == [{"field": "name"}, {"field": "account", "width": 25}]
    assert data["content_version"] == "1.1.0"

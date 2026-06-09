"""End-to-end (offline) proof that the reconcile pieces compose.

provenance (desired) + simulated live drift -> diff engine -> write-back. The
only thing stubbed is the live CRM read (a dict standing in for LiveStateCapture
output); everything else is the real code path.
"""
from __future__ import annotations

from espo_impl.core.reconcile.diff_engine import diff_fields
from espo_impl.core.reconcile.document import YamlDocument
from espo_impl.core.reconcile.models import DiffCategory
from espo_impl.core.reconcile.patcher import set_field_property
from espo_impl.core.reconcile.provenance import build_field_provenance

_BODY = """\
version: "1.0"
content_version: "1.0.0"
entities:
  Session:
    fields:

      - name: sessionType
        type: enum
        label: "Session Type"   # operator-facing
        required: false
"""


def test_label_drift_flows_from_crm_back_into_yaml(tmp_path):
    f = tmp_path / "MN-Session.yaml"
    f.write_text(_BODY)

    # Desired side: real load + provenance.
    desired, collisions = build_field_provenance([f])
    assert collisions == []

    # Live side: the CRM label was changed via the UI.
    live = {"Session": {"sessionType": {"type": "enum", "label": "Type of Session"}}}

    # Diff -> exactly one CHANGED difference carrying old/new + the owning file.
    diffs = diff_fields(desired, live)
    assert len(diffs) == 1
    d = diffs[0]
    assert d.category is DiffCategory.CHANGED
    assert d.property == "label"
    assert d.yaml_value == "Session Type"
    assert d.crm_value == "Type of Session"
    assert d.source_file == f

    # Accept it: write the CRM value back into the owning file, surgically.
    doc = YamlDocument(f.read_text())
    set_field_property(doc, d.entity, d.locator.field_name, d.property, d.crm_value)
    out = doc.render()

    assert 'label: "Type of Session"   # operator-facing' in out
    assert "      - name: sessionType" in out          # structure intact
    assert out.count("\n") == _BODY.count("\n")        # no lines added/removed

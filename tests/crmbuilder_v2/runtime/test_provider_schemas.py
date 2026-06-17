"""Agent-provider structured-output schema validity — regression for the live-run
findings (PI-219/221/223 hardening).

A live LLM run surfaced that the agents' structured-output schemas were invalid /
unconstrained: ``value`` typed as bare ``object`` (Anthropic rejects a typeless
schema), and ``op`` / ``artifact_type`` / ``phase_type`` / ``area`` unconstrained so
the model emitted invalid values (``op="ensure"``, ``area="Data Model"``). These
tests pin both: every provider schema must transform cleanly for Anthropic
structured output, and the enum fields must be constrained.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.runtime import release_gate
from crmbuilder_v2.runtime import release_runtime as rr

# anthropic's structured-output schema transform — what messages.parse runs.
transform_schema = pytest.importorskip(
    "anthropic.lib._parse._transform"
).transform_schema

_SCHEMAS = [
    rr._Demand, rr._DemandSet, rr._WorkTask, rr._Workstream, rr._Decomposition,
    release_gate._Finding, release_gate._Verdict,
]


@pytest.mark.parametrize("model", _SCHEMAS, ids=lambda m: m.__name__)
def test_schema_is_valid_for_anthropic_structured_output(model):
    # Raises ValueError ("Schema must have a 'type'…") on a bad schema — the bug.
    transform_schema(model.model_json_schema())


def test_enum_fields_are_constrained():
    demand = rr._Demand.model_json_schema()["properties"]
    assert set(demand["op"]["enum"]) == {"set", "add", "remove"}
    assert set(demand["artifact_type"]["enum"]) == {
        "entity", "field", "persona", "process", "association"}
    # value is a typed union (anyOf), never a bare/typeless schema
    assert "anyOf" in demand["value"]

    ws = rr._Workstream.model_json_schema()["properties"]
    assert set(ws["phase_type"]["enum"]) == {"Design", "Develop", "Test"}

    # area is constrained to the System areas (resolved $ref or inline enum)
    wt = rr._WorkTask.model_json_schema()
    area = wt["properties"]["area"]
    if "$ref" in area:
        ref = area["$ref"].split("/")[-1]
        area = wt["$defs"][ref]
    assert "storage" in area["enum"] and "Data Model" not in area["enum"]

"""The two DesignClient implementations must agree — REQ-482 / PI-403.

``AccessDesignClient`` (in-process) and ``RestDesignClient`` (out-of-process)
feed the same generator, so a divergence between them silently changes what gets
published. Two real defects sat in exactly that gap:

* ``RestDesignClient.list_fields`` re-filtered the already-narrowed reference
  query on ``relationship_kind``, but the serialized row names that key
  ``relationship`` — so the parent map was always empty and *every* field came
  back with no parent entity (0 of 254 on CBM).
* the access-layer client the test suite carried walked entities and collected
  their fields, which would drop any field lacking a parent edge rather than
  keeping it with a ``None`` parent as the REST path does.

These pin the contract rather than either implementation.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import entity, field
from crmbuilder_v2.adapters.espocrm.client import (
    AccessDesignClient,
    DesignClient,
    RestDesignClient,
)

#: Every method the generator drives; both clients must implement all of them.
METHODS = [m for m in dir(DesignClient) if m.startswith("list_")]


def test_both_clients_implement_the_whole_protocol():
    for m in METHODS:
        assert callable(getattr(AccessDesignClient, m, None)), m
        assert callable(getattr(RestDesignClient, m, None)), m
    assert len(METHODS) == 12


def test_rest_list_fields_reads_the_serialized_edge_key(monkeypatch):
    """Regression: the reference row calls the edge kind ``relationship``.
    Filtering on ``relationship_kind`` matched nothing and emptied the parent map."""
    client = RestDesignClient(base_url="http://x", engagement="ENG-001")
    payloads = {
        "/fields": [{"field_identifier": "FLD-1", "field_name": "phone"}],
        "/references?source_type=field&relationship_kind=field_belongs_to_entity": [
            # exactly what the API serializes — note: no `relationship_kind` key
            {"source_id": "FLD-1", "target_id": "ENT-1",
             "relationship": "field_belongs_to_entity"}
        ],
    }
    monkeypatch.setattr(client, "_get", lambda path: payloads[path])
    rows = client.list_fields()
    assert rows[0]["parent_entity_identifier"] == "ENT-1"


def test_access_list_fields_keeps_a_parentless_field(v2_env):
    """A field with no parent edge is kept with a ``None`` parent, matching REST —
    walking entities instead would drop it entirely."""
    with session_scope() as s:
        eid = entity.create_entity(s, name="Account", description="x")["entity_identifier"]
        field.create_field(
            s, field_belongs_to_entity_identifier=eid, name="phone",
            description="x", type="text", required=False,
        )
    rows = AccessDesignClient().list_fields()
    assert len(rows) == 1
    assert rows[0]["parent_entity_identifier"] == eid


def test_access_client_stamps_every_field_with_its_parent(v2_env):
    with session_scope() as s:
        e1 = entity.create_entity(s, name="Account", description="x")["entity_identifier"]
        e2 = entity.create_entity(s, name="Contact", description="x")["entity_identifier"]
        for eid, name in ((e1, "phone"), (e2, "email"), (e2, "mobile")):
            field.create_field(
                s, field_belongs_to_entity_identifier=eid, name=name,
                description="x", type="text", required=False,
            )
    rows = AccessDesignClient().list_fields()
    assert len(rows) == 3
    assert all(r["parent_entity_identifier"] for r in rows)
    by_name = {r["field_name"]: r["parent_entity_identifier"] for r in rows}
    assert by_name == {"phone": e1, "email": e2, "mobile": e2}


@pytest.mark.parametrize("method", [m for m in METHODS if m != "list_fields"])
def test_access_client_returns_a_list_for_every_method(v2_env, method):
    """Each method resolves against a real store rather than raising —
    the promoted class is production code now, not a test fake."""
    assert isinstance(getattr(AccessDesignClient(), method)(), list)

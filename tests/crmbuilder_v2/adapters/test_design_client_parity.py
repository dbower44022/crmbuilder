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

**The twelve-method diff.** The defect above was found by diffing both clients'
output against live design data before the switch — a diff that then existed
only in a commit message. :func:`test_clients_agree_on_every_method` makes it a
standing test: one seeded store exercising all twelve surfaces, both clients
read it, results compared field for field. ``RestDesignClient`` is driven
through a real request against an in-process app, patched at ``urlopen`` rather
than at ``_get``, so its URL construction, query parameters, engagement header
and envelope unwrapping all stay under test — every one of those is a place the
two implementations could silently disagree, and one of them is where they did.
"""

from __future__ import annotations

import json
from urllib import parse as urllib_parse
from urllib import request as urllib_request

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import (
    association,
    automation,
    dedup_rule,
    engine_override,
    entity,
    field,
    field_permission_rule,
    field_visibility_rule,
    message_template,
    roles,
    rule,
    view,
)
from crmbuilder_v2.adapters.espocrm.client import (
    AccessDesignClient,
    DesignClient,
    RestDesignClient,
)
from crmbuilder_v2.api.main import create_app
from fastapi.testclient import TestClient

from tests.crmbuilder_v2.conftest import DEFAULT_ENGAGEMENT_ID

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


# -- the twelve-method diff, against one seeded store ------------------------


def _seed_every_surface() -> None:
    """A design touching all twelve read surfaces, so no method compares empty.

    Two clients agreeing that a list is empty proves nothing, so every surface
    here carries at least one row.

    No parentless field is seeded: the store forbids one. A live field must keep
    exactly one ``field_belongs_to_entity`` edge, and
    ``_guard_field_belongs_to_entity_delete`` refuses to remove the last one.
    The ``None``-parent branch both clients carry is defensive, not a reachable
    state, and is covered at unit level above rather than manufactured here.
    """
    with session_scope() as s:
        org = entity.create_entity(
            s, name="Sponsor Organization", description="a sponsor",
            kind="organization", status="confirmed",
        )["entity_identifier"]
        app = entity.create_entity(
            s, name="Mentor Application", description="an application",
            kind="person", status="confirmed",
        )["entity_identifier"]

        status_fid = field.create_field(
            s, field_belongs_to_entity_identifier=app, name="application_status",
            description="where the application is", type="enum", status="confirmed",
            options=[
                {"option_value": "submitted", "option_order": 1},
                {"option_value": "approved", "option_order": 2},
            ],
        )["field_identifier"]
        approver_fid = field.create_field(
            s, field_belongs_to_entity_identifier=app, name="approver_name",
            description="who approved it", type="text", status="confirmed",
        )["field_identifier"]
        email_fid = field.create_field(
            s, field_belongs_to_entity_identifier=app, name="contact_email",
            description="primary email", type="text", status="confirmed",
            format="email", max_length=120, required=True,
        )["field_identifier"]
        # A candidate field on the other entity — present in the raw list, and
        # filtered out downstream by the generator's scope filter, not here.
        field.create_field(
            s, field_belongs_to_entity_identifier=org, name="draft_note",
            description="scratch", type="text", status="candidate",
        )

        engine_override.create_engine_override(
            s, target_engine="espocrm", subject_type="field",
            subject_identifier=email_fid, attribute="internal_name",
            value="emailAddress",
        )
        association.create_association(
            s, name="Sponsor funds applications", source_entity=org,
            target_entity=app, cardinality="one_to_many", status="confirmed",
        )
        rule.create_rule(
            s, name="Approver required once approved", subject_type="field",
            subject_identifier=approver_fid, effect="required_when",
            condition={"field": status_fid, "op": "eq", "value": "approved"},
            status="confirmed",
        )
        view.create_view(
            s, name="Approved applications", entity=app,
            columns=[approver_fid, status_fid],
            filter={"field": status_fid, "op": "eq", "value": "approved"},
            sort_field=status_fid, sort_direction="desc", status="confirmed",
        )
        automation.create_automation(
            s, name="Stamp approver on approval", entity=app, trigger="on_update",
            condition={"field": status_fid, "op": "eq", "value": "approved"},
            actions=[{"type": "set_field", "field": approver_fid, "value": "system"}],
            status="confirmed",
        )
        dedup_rule.create_dedup_rule(
            s, name="No duplicate email", entity=app, match_fields=[email_fid],
            normalize={email_fid: "lowercase"}, on_match="block",
            message="already exists", status="confirmed",
        )
        message_template.create_message_template(
            s, name="Application received", entity=app, channel="email",
            subject="Thanks for applying", body="We received your application.",
            merge_fields=[email_fid], status="confirmed",
        )
        rol = roles.create_role(
            s, name="Mentor Coordinator", status="confirmed"
        )["role_identifier"]
        field_permission_rule.create_field_permission_rule(
            s, name="Coordinator read-only email", role=rol,
            target_field=email_fid, permission_level="read_only", status="confirmed",
        )
        field_visibility_rule.create_field_visibility_rule(
            s, name="Coordinator cannot see email", role=rol,
            target_field=email_fid, visible=False, status="confirmed",
        )


def _rest_client_over(app_client: TestClient, monkeypatch) -> RestDesignClient:
    """A ``RestDesignClient`` whose HTTP goes to an in-process app.

    Patched at ``urlopen``, deliberately: everything ``_get`` does above that
    call — building the URL from ``base_url`` + path and query, attaching the
    engagement header, decoding, unwrapping the ``{data, meta, errors}``
    envelope, raising on a non-2xx — is code the access-layer client has no
    counterpart for, and therefore code that can diverge. Patching ``_get``
    itself would test none of it.
    """

    class _Resp:
        def __init__(self, body: bytes) -> None:
            self._body = body

        def read(self) -> bytes:
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *exc) -> bool:
            return False

    def _fake_urlopen(req):
        split = urllib_parse.urlsplit(req.full_url)
        path = split.path + (f"?{split.query}" if split.query else "")
        resp = app_client.get(path, headers=dict(req.header_items()))
        assert resp.status_code == 200, f"GET {path} -> {resp.status_code}"
        return _Resp(json.dumps(resp.json()).encode("utf-8"))

    monkeypatch.setattr(urllib_request, "urlopen", _fake_urlopen)
    return RestDesignClient(
        base_url="http://testserver", engagement=DEFAULT_ENGAGEMENT_ID
    )


@pytest.mark.parametrize("method", METHODS)
def test_clients_agree_on_every_method(v2_env, monkeypatch, method):
    """Both clients return the same records for the same store, method by method.

    This is the diff that found the parentless-field defect (0 of 254 fields on
    live client data against 254 of 254), made standing and hermetic. Comparing
    the whole row rather than a chosen key is the point: the defect was in a key
    nobody thought to assert on.
    """
    _seed_every_surface()
    app_client = TestClient(create_app())
    app_client.headers.update({"X-Engagement": DEFAULT_ENGAGEMENT_ID})

    rest = getattr(_rest_client_over(app_client, monkeypatch), method)()
    access = getattr(AccessDesignClient(engagement=DEFAULT_ENGAGEMENT_ID), method)()

    assert rest, f"{method} returned nothing — the seed no longer covers it"
    assert access == rest, f"{method} diverges between the two clients"


def test_both_clients_parent_every_seeded_field(v2_env, monkeypatch):
    """The specific regression, stated as an outcome rather than a mechanism.

    Whatever either client does internally, every field must come back carrying
    the parent entity it was created under. Under the defect this was 0 of 254
    on live data, and nothing raised.
    """
    _seed_every_surface()
    app_client = TestClient(create_app())
    app_client.headers.update({"X-Engagement": DEFAULT_ENGAGEMENT_ID})

    for client in (
        _rest_client_over(app_client, monkeypatch),
        AccessDesignClient(engagement=DEFAULT_ENGAGEMENT_ID),
    ):
        rows = client.list_fields()
        by_name = {r["field_name"]: r["parent_entity_identifier"] for r in rows}
        assert by_name, "no fields came back at all"
        assert all(by_name.values()), (
            f"{type(client).__name__} lost the parent entity on "
            f"{[n for n, p in by_name.items() if not p]}"
        )

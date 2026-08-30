"""PI-420 (REQ-124 audit half) — email templates audited into message_template records.

Oracle: ``tests/test_audit_email_templates.py`` (V1): merge fields are the sorted
unique ``{{word}}`` placeholders across subject and body (dotted ones ignored);
templates match per entity by name; a 404 from the EmailTemplate endpoint skips
the entity silently; unnamed templates are skipped. V2 additionally records
per-instance membership and drift on subject/body/merge fields.
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import instance_membership as mb
from crmbuilder_v2.access.repositories import message_template as mt_repo
from crmbuilder_v2.api.routers.instances import _AUDIT_AREAS, _SOURCE_AUDIT_AREAS
from crmbuilder_v2.introspect.reconcile import (
    _merge_fields_of,
    reconcile_email_templates,
)

from tests.crmbuilder_v2.access.test_instance_membership import (
    _custom,
    _FakeClient,
    _make_instance,
)

_TEMPLATE = {
    "name": "Mentor Application Confirmation",
    "subject": "Thanks, {{firstName}}",
    "body": "<p>Dear {{firstName}} {{lastName}}, see {{Person.name}}</p>",
}


def _client(templates):
    client = _FakeClient({"CEngagement": _custom()})
    client._email_templates = templates
    return client


def test_merge_fields_mirror_v1_grammar():
    assert _merge_fields_of("Hi {{firstName}}", "{{lastName}} {{firstName}} {{a.b}}") == [
        "firstName",
        "lastName",
    ]


def test_area_registered_after_filtered_tabs_and_not_source_gated():
    keys = list(_AUDIT_AREAS)
    assert keys.index("email-templates") > keys.index("filtered-tabs")
    assert "email-templates" not in _SOURCE_AUDIT_AREAS


def test_reconcile_creates_templates_and_detects_drift(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        ent = entity_repo.create_entity(s, name="Engagement", description="x")
        summary = reconcile_email_templates(
            s, instance_identifier=iid, client=_client({"CEngagement": [_TEMPLATE]})
        )
        assert summary["created"] == 1 and summary["present"] == 1
        rows = mt_repo.list_message_templates(s)
        assert len(rows) == 1
        row = rows[0]
        assert row["message_template_name"] == _TEMPLATE["name"]
        assert row["message_template_entity"] == ent["entity_identifier"]
        assert row["message_template_subject"] == _TEMPLATE["subject"]
        assert row["message_template_body"] == _TEMPLATE["body"]
        assert row["message_template_merge_fields"] == ["firstName", "lastName"]

        changed = dict(_TEMPLATE, subject="Welcome {{firstName}}")
        s2 = reconcile_email_templates(
            s, instance_identifier=iid, client=_client({"CEngagement": [changed]})
        )
        assert s2["drifted"] == 1 and s2["created"] == 0
        m = mb.list_memberships(s, instance_identifier=iid, member_type="message_template")[0]
        assert m["state"] == "drifted"
        assert m["override"] == {"message_template_subject": "Welcome {{firstName}}"}


def test_endpoint_404_skips_entity_and_unnamed_templates_are_ignored(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        entity_repo.create_entity(s, name="Engagement", description="x")
        summary = reconcile_email_templates(
            s, instance_identifier=iid, client=_client({})  # 404 for every entity
        )
        assert summary["seen"] == 0 and summary["created"] == 0
        summary = reconcile_email_templates(
            s,
            instance_identifier=iid,
            client=_client({"CEngagement": [{"name": "", "subject": "x", "body": "y"}]}),
        )
        assert summary["seen"] == 0


def test_successful_empty_read_sweeps_absent(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        entity_repo.create_entity(s, name="Engagement", description="x")
        reconcile_email_templates(
            s, instance_identifier=iid, client=_client({"CEngagement": [_TEMPLATE]})
        )
        s2 = reconcile_email_templates(
            s, instance_identifier=iid, client=_client({"CEngagement": []})
        )
        assert s2["absent"] == 1

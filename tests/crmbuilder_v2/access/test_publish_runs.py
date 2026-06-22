"""Publish-run repository tests — PI-262 (PRJ-042).

Covers the table shape, ``PUB-NNN`` auto-assignment, the status enum, and the
create / get / list round-trip with the JSON backup + summary payloads.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import UnprocessableError
from crmbuilder_v2.access.repositories import publish_runs
from sqlalchemy import inspect

_EXPECTED_COLUMNS = {
    "id",
    "publish_run_identifier",
    "instance_identifier",
    "publish_run_status",
    "publish_run_scope",
    "publish_run_backup",
    "publish_run_summary",
    "publish_run_started_at",
    "publish_run_ended_at",
    "created_at",
    "updated_at",
    "engagement_id",
}


def test_table_shape(v2_env):
    cols = {c["name"] for c in inspect(get_engine()).get_columns("publish_runs")}
    assert cols == _EXPECTED_COLUMNS


def test_create_assigns_identifier_and_round_trips(v2_env):
    with session_scope() as s:
        row = publish_runs.create_publish_run(
            s,
            instance_identifier="INST-001",
            status="succeeded",
            scope=["Contact.yaml"],
            backup={"entities": {"Contact": {"fields": {}}}},
            summary={"deployed": ["Contact.yaml"]},
        )
        assert row["publish_run_identifier"] == "PUB-001"
        assert row["publish_run_status"] == "succeeded"
        assert row["publish_run_scope"] == ["Contact.yaml"]
        assert row["publish_run_backup"]["entities"]["Contact"] == {"fields": {}}

    with session_scope() as s:
        fetched = publish_runs.get_publish_run(s, "PUB-001")
        assert fetched is not None
        assert fetched["instance_identifier"] == "INST-001"


def test_identifier_increments(v2_env):
    with session_scope() as s:
        a = publish_runs.create_publish_run(
            s, instance_identifier="INST-001", status="succeeded"
        )
        b = publish_runs.create_publish_run(
            s, instance_identifier="INST-001", status="failed"
        )
    assert a["publish_run_identifier"] == "PUB-001"
    assert b["publish_run_identifier"] == "PUB-002"


def test_list_newest_first_and_filtered(v2_env):
    with session_scope() as s:
        publish_runs.create_publish_run(
            s, instance_identifier="INST-001", status="succeeded"
        )
        publish_runs.create_publish_run(
            s, instance_identifier="INST-002", status="succeeded"
        )
        publish_runs.create_publish_run(
            s, instance_identifier="INST-001", status="aborted"
        )

    with session_scope() as s:
        all_runs = publish_runs.list_publish_runs(s)
        assert [r["publish_run_identifier"] for r in all_runs] == [
            "PUB-003",
            "PUB-002",
            "PUB-001",
        ]
        only_1 = publish_runs.list_publish_runs(
            s, instance_identifier="INST-001"
        )
        assert {r["instance_identifier"] for r in only_1} == {"INST-001"}
        assert len(only_1) == 2


def test_invalid_status_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        publish_runs.create_publish_run(
            s, instance_identifier="INST-001", status="bogus"
        )

"""instance_deploy_config repo + backfill tests — PI-201 (REQ-172, PRJ-027)."""

from __future__ import annotations

import json

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import UnprocessableError
from crmbuilder_v2.access.repositories import instance_deploy_config as idc
from crmbuilder_v2.access.repositories import instances as inst_repo


def _instance(s) -> str:
    return inst_repo.create_instance(
        s, name="prod", url="https://crm.example.org", role="target"
    )["instance_identifier"]


def test_upsert_then_partial_update(v2_env):
    with session_scope() as s:
        iid = _instance(s)
        cfg = idc.upsert_deploy_config(
            s, iid, ssh_host="1.2.3.4", domain="d",
            current_espocrm_version="9.3.4")
        assert cfg["ssh_host"] == "1.2.3.4" and cfg["scenario"] == "self_hosted"
        # Partial update preserves untouched fields.
        cfg2 = idc.upsert_deploy_config(s, iid, current_espocrm_version="9.3.6")
        assert cfg2["current_espocrm_version"] == "9.3.6"
        assert cfg2["ssh_host"] == "1.2.3.4"
        assert idc.get_deploy_config(s, iid)["domain"] == "d"


def test_unknown_field_and_bad_enum_rejected(v2_env):
    with session_scope() as s:
        iid = _instance(s)
        with pytest.raises(UnprocessableError):
            idc.upsert_deploy_config(s, iid, bogus="x")
        with pytest.raises(UnprocessableError):
            idc.upsert_deploy_config(s, iid, ssh_auth_type="telnet")


def test_delete(v2_env):
    with session_scope() as s:
        iid = _instance(s)
        idc.upsert_deploy_config(s, iid, domain="d")
        idc.delete_deploy_config(s, iid)
        assert idc.get_deploy_config(s, iid) is None


def test_backfill_from_notes(v2_env):
    with session_scope() as s:
        iid = _instance(s)
        notes = json.dumps({
            "label": "keep me",
            "deploy_config": {
                "ssh_host": "147.182.135.50", "domain": "crm.example.org",
                "scenario": "self_hosted", "current_espocrm_version": "9.3.4",
            },
        })
        cfg, remaining = idc.backfill_from_notes(s, iid, notes)
        assert cfg["ssh_host"] == "147.182.135.50"
        assert json.loads(remaining) == {"label": "keep me"}
        assert idc.get_deploy_config(s, iid)["domain"] == "crm.example.org"


def test_backfill_noop_when_not_json_or_no_config(v2_env):
    with session_scope() as s:
        iid = _instance(s)
        assert idc.backfill_from_notes(s, iid, "just text") == (None, "just text")
        no_dc = json.dumps({"label": "x"})
        assert idc.backfill_from_notes(s, iid, no_dc) == (None, no_dc)
        assert idc.get_deploy_config(s, iid) is None


def test_deploy_run_written_fields_round_trip(v2_env):
    """PI-419 (REQ-522): the columns a deploy run writes are upsertable."""
    with session_scope() as s:
        cfg = idc.upsert_deploy_config(
            s, _instance(s),
            admin_username="admin", admin_password_ref="crmbuilder:p",
            db_password_ref="crmbuilder:d", droplet_ip="203.0.113.7",
            droplet_region="nyc3", droplet_size="s-2vcpu-4gb",
            dns_record_id="abc123", last_deploy_run_identifier="DEP-001",
        )
    assert cfg["admin_username"] == "admin"
    assert cfg["admin_password_ref"] == "crmbuilder:p"
    assert cfg["droplet_ip"] == "203.0.113.7"
    assert cfg["last_deploy_run_identifier"] == "DEP-001"

"""The PRJ-128 migration run — PI-579 (DEC-1175, DEC-1176..DEC-1182).

A miniature of the production store the mapping describes is built in the
test database: Cleveland's application with two instances and a credential,
Rochester's engagement with a copied design that matches Cleveland's by
name apart from the accepted type differences and three built-in fields,
Boston's engagement with an instance and three runs. The run creates the
clients and deployments, re-homes the Rochester and Boston records under
Cleveland's application with fresh identifiers, translates Rochester's
memberships, archives the copy, and archives the four engagements. A copy
that differs stops the run before anything moves, and a fresh store passes
through untouched.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.engagement_scope import active_engagement
from crmbuilder_v2.access.repositories import (
    entity as entity_repo,
)
from crmbuilder_v2.access.repositories import (
    field as field_repo,
)
from crmbuilder_v2.access.repositories import instance_membership as membership_repo
from crmbuilder_v2.segments.client_management.repositories import (
    client as client_repo,
)
from crmbuilder_v2.segments.client_management.repositories import (
    engagement as engagement_repo,
)
from crmbuilder_v2.segments.operate import prj128_migration as mig
from crmbuilder_v2.segments.operate.repositories import (
    deploy_runs,
    instance_deploy_config,
    instances,
    provider_credentials,
)
from sqlalchemy import text

# (entity, field, type) in Cleveland's design; the copy repeats them with the
# engine's spellings and types where DEC-1181 accepts a difference.
_CLEVELAND = {
    "Account": [("name", "text"), ("annualPledgeAmountConverted", "text")],
    "Event": [("name", "text"), ("Format", "enum"), ("eventGraphic", "text")],
    "Contact": [("name", "text"), ("Birthday", "date")],
}
_ROCHESTER = {
    "Account": [("name", "text"), ("annualPledgeAmountConverted", "money"), ("isLocked", "boolean", True)],
    "Event": [("name", "text"), ("format", "enum"), ("eventGraphic", "file")],
    "Contact": [("name", "text"), ("birthday", "date")],
}


def _design(s, eng: str, spec: dict) -> dict[str, dict[str, str]]:
    """Create entities and fields under ``eng``; return {entity: {field: FLD}}."""
    out: dict[str, dict[str, str]] = {}
    with active_engagement(eng):
        for entity_name, fields in spec.items():
            ent = entity_repo.create_entity(s, name=entity_name, description="d")
            out[entity_name] = {}
            for spec_row in fields:
                fname, ftype = spec_row[0], spec_row[1]
                built_in = bool(len(spec_row) > 2 and spec_row[2])
                fld = field_repo.create_field(
                    s,
                    field_belongs_to_entity_identifier=ent["entity_identifier"],
                    name=fname,
                    description="d",
                    type=ftype,
                    built_in=built_in,
                )
                out[entity_name][fname] = fld["field_identifier"]
    return out


def _seed_production_like(v2_env):
    now = datetime.now(UTC)
    with session_scope() as s:
        client_repo.create_client(s, name="Cleveland Business Mentors")  # CLI-001
        client_repo.create_client(s, name="CRMBuilder")  # CLI-002
        client_repo.set_engagement_clients(s, "ENG-001", clients=["CLI-002"], primary="CLI-002")
        for ident, code, name, client in (
            ("ENG-002", "CBM", "Cleveland Business Mentoring", "CLI-001"),
            ("ENG-003", "ADOTEST", "ADO E2E Sandbox", None),
            ("ENG-004", "CBMMENTOR", "CBM Mentoring Custom App", "CLI-001"),
            ("ENG-005", "CRMB3", "V3 Requirements", "CLI-002"),
            ("ENG-006", "ROCHNY", "Rochester NY Test Instance", None),
            ("ENG-007", "BOSTON", "Boston Business Mentors", None),
        ):
            engagement_repo.create_engagement(
                s, engagement_code=code, engagement_name=name, engagement_purpose="p",
                engagement_identifier=ident, engagement_defining_client=client,
            )
    with session_scope() as s:
        clev = _design(s, "ENG-002", _CLEVELAND)
        roch = _design(s, "ENG-006", _ROCHESTER)
        with active_engagement("ENG-002"):
            instances.create_instance(s, name="CBMTEST", url="https://crm-test.example.org")
            instances.create_instance(s, name="CBM Production", url="https://crm.example.org")
            instance_deploy_config.upsert_deploy_config(s, "INST-001", domain="crm-test.example.org")
            provider_credentials.upsert_provider_credential(s, "digitalocean", token_ref="crmbuilder:cbm-do", label="cbm team")
        with active_engagement("ENG-006"):
            instances.create_instance(s, name="Lakeside rehearsal", url="https://crm-lakeside.example.org", notes="Provisioned by deploy run DEP-001.")
            instance_deploy_config.upsert_deploy_config(s, "INST-001", domain="crm-lakeside.example.org", last_deploy_run_identifier="DEP-001")
            provider_credentials.upsert_provider_credential(s, "digitalocean", token_ref="crmbuilder:doug-do", label="dougs account")
            provider_credentials.upsert_provider_credential(s, "cloudflare", token_ref="crmbuilder:lakeside-cf", label="Lakeside Cloudflare Token")
            run = deploy_runs.create_deploy_run(s, spec={"domain": "crm-lakeside.example.org"}, instance_identifier="INST-001")
            deploy_runs.set_phase(s, run["deploy_run_identifier"], "create_instance", state={"instance_identifier": "INST-001", "droplet_id": "1"})
            for entity_name, fields in roch.items():
                membership_repo.upsert_membership(s, instance_identifier="INST-001", member_type="entity", member_identifier=_entity_id(s, "ENG-006", entity_name), state="present")
                for fld in fields.values():
                    membership_repo.upsert_membership(s, instance_identifier="INST-001", member_type="field", member_identifier=fld, state="present")
        with active_engagement("ENG-007"):
            instances.create_instance(s, name="Boston Business Mentors CRM", url="https://crm.bbmentors.org", notes="Provisioned by deploy run DEP-003.")
            instance_deploy_config.upsert_deploy_config(s, "INST-001", domain="crm.bbmentors.org", last_deploy_run_identifier="DEP-003")
            provider_credentials.upsert_provider_credential(s, "digitalocean", token_ref="crmbuilder:boston-do", label="boston-DO")
            for i in range(3):
                r = deploy_runs.create_deploy_run(s, spec={"domain": "crm.bbmentors.org"})
                if i == 2:
                    deploy_runs.set_phase(s, r["deploy_run_identifier"], "create_instance", state={"instance_identifier": "INST-001"})
                    deploy_runs.finish(s, r["deploy_run_identifier"], status="needs_action", instance_identifier="INST-001")
                else:
                    deploy_runs.finish(s, r["deploy_run_identifier"], status="failed")
    return clev, roch, now


def _entity_id(s, eng: str, name: str) -> str:
    return s.execute(text("SELECT entity_identifier FROM entities WHERE engagement_id = :e AND entity_name = :n"), {"e": eng, "n": name}).scalar()


def _q(sql: str, **p):
    with get_engine().begin() as c:
        return [dict(r._mapping) for r in c.execute(text(sql), p)]


def test_mapping_matches_the_document():
    doc = mig.read_mapping_decisions()
    assert doc == {k: v["decision"] for k, v in mig.MAPPING.items()}


def test_fresh_store_passes_through(v2_env):
    with get_engine().begin() as conn:
        assert mig.run(conn, log=lambda m: None) == {"applied": False, "reason": "the seven mapped engagements are not present (fresh or other store)"}


def test_comparison_passes_on_the_verified_shape_and_the_run_moves_everything(v2_env):
    _seed_production_like(v2_env)
    lines: list[str] = []
    with get_engine().begin() as conn:
        report = mig.compare_rochester(conn)
        assert report["passes"], report["stops"]
        assert report["entities"]["matched"] == 3
        assert report["fields"]["excluded_built_in"] == ["Account.isLocked"]
        assert report["fields"]["unmatched"] == []
        assert sorted(report["fields"]["type_differences_accepted"]) == [
            ("Account", "annualPledgeAmountConverted", "money", "text"),
            ("Event", "eventGraphic", "file", "text"),
        ]
        result = mig.run(conn, log=lines.append)
    assert result["applied"] is True
    assert result["clients"] == {"rochester": "CLI-003", "boston": "CLI-004"}
    assert result["instances"] == {"rochester": "INST-003", "boston": "INST-004"}
    assert result["deployments"] == {
        "cleveland_test": "DPL-001", "cleveland_production": "DPL-002",
        "rochester": "DPL-003", "boston": "DPL-004",
    }
    # Deployments: application, client, instance, purpose.
    dpls = _q("SELECT deployment_identifier, deployment_application, deployment_client, deployment_instance_identifier, deployment_purpose FROM deployments ORDER BY 1")
    assert [tuple(d.values()) for d in dpls] == [
        ("DPL-001", "ENG-002", "CLI-001", "INST-001", "client_own"),
        ("DPL-002", "ENG-002", "CLI-001", "INST-002", "client_own"),
        ("DPL-003", "ENG-002", "CLI-003", "INST-003", "client_own"),
        ("DPL-004", "ENG-002", "CLI-004", "INST-004", "client_own"),
    ]
    # Instances and configurations re-homed; nothing left under ENG-006/007.
    assert _q("SELECT engagement_id, instance_identifier, instance_name FROM instances WHERE instance_deleted_at IS NULL ORDER BY 1, 2") == [
        {"engagement_id": "ENG-002", "instance_identifier": "INST-001", "instance_name": "CBMTEST"},
        {"engagement_id": "ENG-002", "instance_identifier": "INST-002", "instance_name": "CBM Production"},
        {"engagement_id": "ENG-002", "instance_identifier": "INST-003", "instance_name": "Lakeside rehearsal"},
        {"engagement_id": "ENG-002", "instance_identifier": "INST-004", "instance_name": "Boston Business Mentors CRM"},
    ]
    cfgs = _q("SELECT engagement_id, instance_identifier, last_deploy_run_identifier FROM instance_deploy_configs ORDER BY 2")
    assert [(c["engagement_id"], c["instance_identifier"]) for c in cfgs] == [("ENG-002", "INST-001"), ("ENG-002", "INST-003"), ("ENG-002", "INST-004")]
    # Deploy runs renumbered under ENG-002 and pointed at their deployments;
    # the run state and the configuration follow the new identifiers.
    runs = _q("SELECT engagement_id, deploy_run_identifier, instance_identifier, deployment_identifier, deploy_run_state FROM deploy_runs ORDER BY id")
    assert [(r["engagement_id"], r["deploy_run_identifier"], r["instance_identifier"], r["deployment_identifier"]) for r in runs] == [
        ("ENG-002", "DEP-001", "INST-003", "DPL-003"),
        ("ENG-002", "DEP-002", None, "DPL-004"),
        ("ENG-002", "DEP-003", None, "DPL-004"),
        ("ENG-002", "DEP-004", "INST-004", "DPL-004"),
    ]
    def _state(r):
        st = r["deploy_run_state"]
        return json.loads(st) if isinstance(st, str) else st
    assert _state(runs[0])["instance_identifier"] == "INST-003"
    assert _state(runs[3])["instance_identifier"] == "INST-004"
    assert {c["instance_identifier"]: c["last_deploy_run_identifier"] for c in cfgs} == {"INST-001": None, "INST-003": "DEP-001", "INST-004": "DEP-004"}
    assert _q("SELECT instance_notes FROM instances WHERE instance_identifier = 'INST-004'")[0]["instance_notes"] == "Provisioned by deploy run DEP-004."
    # Credentials: Cleveland's stays the application's; Rochester's and Boston's are their deployments' own.
    creds = _q("SELECT engagement_id, provider, label, deployment_identifier FROM provider_credentials ORDER BY provider, label")
    assert [(c["engagement_id"], c["provider"], c["deployment_identifier"]) for c in creds] == [
        ("ENG-002", "cloudflare", "DPL-003"),
        ("ENG-002", "digitalocean", "DPL-004"),
        ("ENG-002", "digitalocean", None),
        ("ENG-002", "digitalocean", "DPL-003"),
    ]
    # Memberships: Rochester's translated onto Cleveland's identifiers, the
    # built-in one left with the archived copy.
    moved = _q("SELECT member_type, member_identifier FROM instance_memberships WHERE engagement_id = 'ENG-002' AND instance_identifier = 'INST-003' ORDER BY 1, 2")
    assert len(moved) == 3 + 7  # 3 entities + 7 matched fields
    assert all(m["member_identifier"] in {r["i"] for r in _q("SELECT entity_identifier AS i FROM entities WHERE engagement_id='ENG-002' UNION SELECT field_identifier FROM fields WHERE engagement_id='ENG-002'")} for m in moved)
    left = _q("SELECT member_type, member_identifier FROM instance_memberships WHERE engagement_id = 'ENG-006'")
    assert len(left) == 1 and left[0]["member_type"] == "field"
    # The old instance rows are retained soft-deleted under the archived engagements.
    ghosts = _q("SELECT engagement_id, instance_identifier, instance_notes FROM instances WHERE instance_deleted_at IS NOT NULL ORDER BY 1")
    assert [(g["engagement_id"], g["instance_identifier"]) for g in ghosts] == [("ENG-006", "INST-001"), ("ENG-007", "INST-001")]
    assert "Moved to ENG-002/INST-003" in ghosts[0]["instance_notes"]
    assert result["moves"]["rochester"]["instance_memberships_left_with_the_copy"] == 1
    # The copy is archived, retained: soft-deleted with a note, rows intact.
    archived = _q("SELECT COUNT(*) AS n FROM fields WHERE engagement_id = 'ENG-006' AND field_deleted_at IS NOT NULL AND field_notes LIKE '%PI-579%'")[0]["n"]
    assert archived == 8
    assert _q("SELECT COUNT(*) AS n FROM entities WHERE engagement_id = 'ENG-006' AND entity_deleted_at IS NOT NULL")[0]["n"] == 3
    # Engagement rows: three archived plus ENG-005; ENG-003 now held by CRMBuilder.
    assert {r["engagement_identifier"]: r["engagement_status"] for r in _q("SELECT engagement_identifier, engagement_status FROM engagements")} == {
        "ENG-001": "active", "ENG-002": "active", "ENG-003": "archived", "ENG-004": "active",
        "ENG-005": "archived", "ENG-006": "archived", "ENG-007": "archived",
    }
    assert _q("SELECT client_id FROM engagement_clients WHERE engagement_id = 'ENG-003' AND is_primary")[0]["client_id"] == "CLI-002"
    # The change log carries the two moves.
    assert _q("SELECT COUNT(*) AS n FROM change_log WHERE actor = 'migration' AND entity_type = 'instance'")[0]["n"] == 2
    # Running again is a no-op.
    with get_engine().begin() as conn:
        assert mig.run(conn, log=lambda m: None)["applied"] is False
    # The composed deployment reads the moved instance under the application.
    from crmbuilder_v2.segments.operate.repositories import deployments as repo
    with session_scope() as s:
        d = repo.get_deployment(s, "DPL-003")
        assert d["instance"]["instance_name"] == "Lakeside rehearsal"
        assert d["deploy_config"]["domain"] == "crm-lakeside.example.org"
        assert [(c["provider"], c["scope"]) for c in d["provider_credentials"]] == [("cloudflare", "deployment"), ("digitalocean", "deployment")]
        assert [(c["provider"], c["scope"]) for c in repo.get_deployment(s, "DPL-002")["provider_credentials"]] == [("digitalocean", "application")]


def test_a_copy_that_differs_stops_the_run_before_anything_moves(v2_env):
    _seed_production_like(v2_env)
    # A copied field Cleveland's design does not have, not built in.
    with session_scope() as s, active_engagement("ENG-006"):
        ent = _entity_id(s, "ENG-006", "Contact")
        field_repo.create_field(
            s, field_belongs_to_entity_identifier=ent, name="favouriteColour",
            description="d", type="text",
        )
    with get_engine().begin() as conn:
        with pytest.raises(mig.MigrationStop) as excinfo:
            mig.run(conn, log=lambda m: None)
    assert "Contact.favouriteColour" in str(excinfo.value)
    assert _q("SELECT COUNT(*) AS n FROM deployments")[0]["n"] == 0
    assert _q("SELECT COUNT(*) AS n FROM clients")[0]["n"] == 2
    assert _q("SELECT engagement_status FROM engagements WHERE engagement_identifier = 'ENG-006'")[0]["engagement_status"] == "active"


def test_a_role_on_a_moving_engagement_stops_the_run(v2_env):
    _seed_production_like(v2_env)
    with get_engine().begin() as conn:
        conn.execute(text("INSERT INTO principals (principal_id, kind, display_name, identity, status, created_at, updated_at) VALUES ('PRN-009', 'human', 'R', 'r@example.org', 'active', :now, :now)"), {"now": datetime.now(UTC)})
        conn.execute(text("INSERT INTO role_assignments (principal_id, engagement_id, role, created_at) VALUES ('PRN-009', 'ENG-006', 'editor', :now)"), {"now": datetime.now(UTC)})
    with get_engine().begin() as conn:
        with pytest.raises(mig.MigrationStop) as excinfo:
            mig.run(conn, log=lambda m: None)
    assert "role assignments exist" in str(excinfo.value)

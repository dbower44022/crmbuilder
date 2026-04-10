"""Tests for automation.importer.mappers.master_prd."""

import pytest

from automation.db.migrations import run_client_migrations, run_master_migrations
from automation.importer.mappers.master_prd import map_payload


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


@pytest.fixture()
def master_conn(tmp_path):
    db_path = tmp_path / "master.db"
    c = run_master_migrations(str(db_path))
    c.execute(
        "INSERT INTO Client (name, code, description, database_path) "
        "VALUES ('Test', 'TST', 'Test org', '/tmp/test.db')"
    )
    c.commit()
    yield c
    c.close()


def _work_item(wi_id=1):
    return {"id": wi_id, "item_type": "master_prd", "status": "in_progress",
            "domain_id": None, "entity_id": None, "process_id": None}


def _payload():
    return {
        "organization_overview": "Test org overview",
        "personas": [
            {"name": "Mentor", "identifier": "MNT", "description": "A mentor"},
            {"name": "Admin", "identifier": "ADM", "description": "An admin"},
        ],
        "domains": [
            {
                "name": "Mentoring", "code": "MN", "description": "Mentoring domain",
                "sort_order": 1,
                "sub_domains": [
                    {"name": "Youth", "code": "YTH", "description": "Youth sub",
                     "sort_order": 1, "is_service": False},
                ],
            },
        ],
        "processes": [
            {"name": "Intake", "code": "MN-INTAKE", "description": "Intake process",
             "sort_order": 1, "tier": "core", "domain_code": "MN"},
        ],
    }


class TestMasterPrdMapper:
    def test_produces_correct_record_types(self, conn, master_conn):
        batch = map_payload(
            conn, _work_item(), _payload(), "initial", 1,
            master_conn=master_conn,
        )
        tables = {r.table_name for r in batch.records}
        assert "Client" in tables
        assert "Persona" in tables
        assert "Domain" in tables
        assert "Process" in tables

    def test_client_update(self, conn, master_conn):
        batch = map_payload(
            conn, _work_item(), _payload(), "initial", 1,
            master_conn=master_conn,
        )
        client_recs = [r for r in batch.records if r.table_name == "Client"]
        assert len(client_recs) == 1
        assert client_recs[0].action == "update"
        assert client_recs[0].values["organization_overview"] == "Test org overview"

    def test_personas_created(self, conn, master_conn):
        batch = map_payload(
            conn, _work_item(), _payload(), "initial", 1,
            master_conn=master_conn,
        )
        persona_recs = [r for r in batch.records if r.table_name == "Persona"]
        assert len(persona_recs) == 2
        assert all(r.action == "create" for r in persona_recs)
        codes = {r.values["code"] for r in persona_recs}
        assert codes == {"MNT", "ADM"}

    def test_domains_with_subdomains(self, conn, master_conn):
        batch = map_payload(
            conn, _work_item(), _payload(), "initial", 1,
            master_conn=master_conn,
        )
        domain_recs = [r for r in batch.records if r.table_name == "Domain"]
        assert len(domain_recs) == 2  # MN + YTH
        # Sub-domain has intra-batch ref to parent
        yth = [r for r in domain_recs if r.values["code"] == "YTH"][0]
        assert "parent_domain_id" in yth.intra_batch_refs
        assert yth.intra_batch_refs["parent_domain_id"] == "batch:domain:MN"

    def test_processes_with_domain_ref(self, conn, master_conn):
        batch = map_payload(
            conn, _work_item(), _payload(), "initial", 1,
            master_conn=master_conn,
        )
        proc_recs = [r for r in batch.records if r.table_name == "Process"]
        assert len(proc_recs) == 1
        assert proc_recs[0].values["code"] == "MN-INTAKE"
        # Domain doesn't exist yet, so it should be an intra-batch ref
        assert "domain_id" in proc_recs[0].intra_batch_refs

    def test_batch_metadata(self, conn, master_conn):
        batch = map_payload(
            conn, _work_item(), _payload(), "initial", 1,
            master_conn=master_conn,
        )
        assert batch.ai_session_id == 1
        assert batch.work_item_id == 1
        assert batch.session_type == "initial"

    def test_decisions_from_envelope(self, conn, master_conn):
        envelope = {
            "decisions": [
                {"identifier": "DEC-001", "title": "Test", "description": "A decision",
                 "scope": {}},
            ],
            "open_issues": [],
        }
        batch = map_payload(
            conn, _work_item(), _payload(), "initial", 1,
            master_conn=master_conn, envelope=envelope,
        )
        dec_recs = [r for r in batch.records if r.table_name == "Decision"]
        assert len(dec_recs) == 1
        assert dec_recs[0].values["identifier"] == "DEC-001"

    def test_no_master_conn_skips_client_update(self, conn):
        batch = map_payload(
            conn, _work_item(), _payload(), "initial", 1,
            master_conn=None,
        )
        client_recs = [r for r in batch.records if r.table_name == "Client"]
        assert len(client_recs) == 0

    def test_top_level_service_domain(self, conn, master_conn):
        """Top-level Domain records honor payload is_service flag (DEC-020).

        Cross-Domain Services are top-level Domain records with
        is_service=True and never have sub-domains.
        """
        payload = {
            "organization_overview": "Test",
            "personas": [],
            "domains": [
                {"name": "Mentoring", "code": "MN", "description": "",
                 "sort_order": 1},
                {"name": "Notes", "code": "NOTES", "description": "Notes service",
                 "sort_order": 90, "is_service": True},
            ],
            "processes": [],
        }
        batch = map_payload(
            conn, _work_item(), payload, "initial", 1, master_conn=master_conn,
        )
        domain_recs = [r for r in batch.records if r.table_name == "Domain"]
        by_code = {r.values["code"]: r for r in domain_recs}
        assert by_code["MN"].values["is_service"] is False
        assert by_code["NOTES"].values["is_service"] is True

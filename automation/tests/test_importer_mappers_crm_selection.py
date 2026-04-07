"""Tests for automation.importer.mappers.crm_selection."""

import pytest

from automation.db.migrations import run_client_migrations, run_master_migrations
from automation.importer.mappers.crm_selection import map_payload


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


def _work_item():
    return {"id": 1, "item_type": "crm_selection", "status": "in_progress",
            "domain_id": None, "entity_id": None, "process_id": None}


class TestCrmSelectionMapper:
    def test_client_update(self, conn, master_conn):
        payload = {
            "recommended_platforms": [
                {"name": "EspoCRM", "summary": "Best fit"},
            ],
            "requirements_coverage": [],
            "platform_risks": [],
        }
        batch = map_payload(
            conn, _work_item(), payload, "initial", 1,
            master_conn=master_conn,
        )
        client_recs = [r for r in batch.records if r.table_name == "Client"]
        assert len(client_recs) == 1
        assert client_recs[0].values["crm_platform"] == "EspoCRM"

    def test_platform_decisions(self, conn, master_conn):
        payload = {
            "recommended_platforms": [
                {"name": "EspoCRM", "summary": "Best fit"},
                {"name": "SuiteCRM", "summary": "Alternative"},
            ],
            "requirements_coverage": [],
            "platform_risks": [],
        }
        batch = map_payload(
            conn, _work_item(), payload, "initial", 1,
            master_conn=master_conn,
        )
        dec_recs = [r for r in batch.records if r.table_name == "Decision"]
        assert len(dec_recs) == 2
        # First platform decision should be locked
        assert dec_recs[0].values["status"] == "locked"
        assert dec_recs[1].values["status"] == "proposed"

    def test_platform_risks(self, conn, master_conn):
        payload = {
            "recommended_platforms": [],
            "requirements_coverage": [],
            "platform_risks": [
                {"risk_description": "Limited API", "severity": "high"},
            ],
        }
        batch = map_payload(
            conn, _work_item(), payload, "initial", 1,
            master_conn=master_conn,
        )
        issue_recs = [r for r in batch.records if r.table_name == "OpenIssue"]
        assert len(issue_recs) == 1
        assert issue_recs[0].values["priority"] == "high"

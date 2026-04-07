"""Tests for automation.importer.mappers.crm_deployment."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.importer.mappers.crm_deployment import map_payload


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


def _work_item():
    return {"id": 1, "item_type": "crm_deployment", "status": "in_progress",
            "domain_id": None, "entity_id": None, "process_id": None}


class TestCrmDeploymentMapper:
    def test_infrastructure_decisions(self, conn):
        payload = {
            "deployment_plan": {},
            "infrastructure_decisions": [
                {"decision": "Use DigitalOcean", "rationale": "Cost-effective"},
            ],
            "platform_specific_notes": [],
            "open_items": [],
        }
        batch = map_payload(conn, _work_item(), payload, "initial", 1)
        dec_recs = [r for r in batch.records if r.table_name == "Decision"]
        assert len(dec_recs) == 1
        assert "DigitalOcean" in dec_recs[0].values["description"]
        assert dec_recs[0].values["status"] == "locked"

    def test_open_items_as_strings(self, conn):
        payload = {
            "deployment_plan": {},
            "infrastructure_decisions": [],
            "platform_specific_notes": [],
            "open_items": ["Configure DNS", "Set up SSL"],
        }
        batch = map_payload(conn, _work_item(), payload, "initial", 1)
        issue_recs = [r for r in batch.records if r.table_name == "OpenIssue"]
        assert len(issue_recs) == 2
        descs = {r.values["description"] for r in issue_recs}
        assert "Configure DNS" in descs
        assert "Set up SSL" in descs

    def test_empty_payload(self, conn):
        payload = {
            "deployment_plan": {},
            "infrastructure_decisions": [],
            "platform_specific_notes": [],
            "open_items": [],
        }
        batch = map_payload(conn, _work_item(), payload, "initial", 1)
        assert len(batch.records) == 0

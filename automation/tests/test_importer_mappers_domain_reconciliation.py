"""Tests for automation.importer.mappers.domain_reconciliation."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.importer.mappers.domain_reconciliation import map_payload


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    c.execute("INSERT INTO WorkItem (item_type, status) VALUES ('master_prd', 'complete')")
    c.execute(
        "INSERT INTO AISession (work_item_id, session_type, generated_prompt, "
        "import_status, started_at) VALUES (1, 'initial', 'p', 'imported', CURRENT_TIMESTAMP)"
    )
    c.execute("INSERT INTO Domain (name, code, sort_order) VALUES ('Mentoring', 'MN', 1)")
    c.execute(
        "INSERT INTO Persona (name, code, description) VALUES ('Mentor', 'MNT', 'Old desc')"
    )
    c.commit()
    yield c
    c.close()


def _work_item():
    return {"id": 1, "item_type": "domain_reconciliation", "status": "in_progress",
            "domain_id": 1, "entity_id": None, "process_id": None}


class TestDomainReconciliationMapper:
    def test_domain_reconciliation_text(self, conn):
        payload = {
            "domain_overview_narrative": "Reconciled narrative",
            "personas": [],
            "conflict_resolutions": [],
            "consolidated_data_reference": [],
            "cross_process_gaps": [],
        }
        batch = map_payload(conn, _work_item(), payload, "initial", 1)
        domain_recs = [r for r in batch.records if r.table_name == "Domain"]
        assert len(domain_recs) == 1
        assert domain_recs[0].values["domain_reconciliation_text"] == "Reconciled narrative"

    def test_persona_update(self, conn):
        payload = {
            "domain_overview_narrative": "Narrative",
            "personas": [
                {"identifier": "MNT", "consolidated_role": "Updated role"},
            ],
            "conflict_resolutions": [],
            "consolidated_data_reference": [],
            "cross_process_gaps": [],
        }
        batch = map_payload(conn, _work_item(), payload, "initial", 1)
        persona_recs = [r for r in batch.records if r.table_name == "Persona"]
        assert len(persona_recs) == 1
        assert persona_recs[0].action == "update"
        assert persona_recs[0].values["description"] == "Updated role"

    def test_conflict_resolutions_create_decisions(self, conn):
        payload = {
            "domain_overview_narrative": "Narrative",
            "personas": [],
            "conflict_resolutions": [
                {"resolution_description": "Resolved field conflict",
                 "identifier": "MN-DEC-001"},
            ],
            "consolidated_data_reference": [],
            "cross_process_gaps": [],
        }
        batch = map_payload(conn, _work_item(), payload, "initial", 1)
        dec_recs = [r for r in batch.records if r.table_name == "Decision"]
        assert len(dec_recs) >= 1
        assert dec_recs[0].values["status"] == "locked"
        assert dec_recs[0].values.get("domain_id") == 1

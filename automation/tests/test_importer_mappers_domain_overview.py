"""Tests for automation.importer.mappers.domain_overview."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.importer.mappers.domain_overview import map_payload


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
        "INSERT INTO Entity (name, code, entity_type, is_native, primary_domain_id) "
        "VALUES ('Contact', 'CON', 'Person', 1, 1)"
    )
    c.execute(
        "INSERT INTO Field (entity_id, name, label, field_type) "
        "VALUES (1, 'contactType', 'Contact Type', 'enum')"
    )
    c.execute(
        "INSERT INTO Process (domain_id, name, code, sort_order) "
        "VALUES (1, 'Intake', 'MN-INTAKE', 1)"
    )
    c.execute(
        "INSERT INTO Persona (name, code, description) VALUES ('Mentor', 'MNT', 'A mentor')"
    )
    c.commit()
    yield c
    c.close()


def _work_item():
    return {"id": 1, "item_type": "domain_overview", "status": "in_progress",
            "domain_id": 1, "entity_id": None, "process_id": None}


class TestDomainOverviewMapper:
    def test_domain_update(self, conn):
        payload = {
            "domain_purpose": "Expanded domain purpose",
            "personas": [],
            "business_process_inventory": [],
            "data_reference": [],
        }
        batch = map_payload(conn, _work_item(), payload, "initial", 1)
        domain_recs = [r for r in batch.records if r.table_name == "Domain"]
        assert len(domain_recs) == 1
        assert domain_recs[0].action == "update"
        assert domain_recs[0].values["domain_overview_text"] == "Expanded domain purpose"

    def test_persona_process_roles(self, conn):
        payload = {
            "domain_purpose": "Purpose",
            "personas": [
                {"identifier": "MNT", "domain_specific_role": "Guides mentees"},
            ],
            "business_process_inventory": [],
            "data_reference": [],
        }
        batch = map_payload(conn, _work_item(), payload, "initial", 1)
        pp_recs = [r for r in batch.records if r.table_name == "ProcessPersona"]
        assert len(pp_recs) >= 1
        assert pp_recs[0].values["persona_id"] == 1

    def test_data_reference_entities(self, conn):
        payload = {
            "domain_purpose": "Purpose",
            "personas": [],
            "business_process_inventory": [],
            "data_reference": [
                {"entity_identifier": "Contact",
                 "referenced_fields": ["contactType"],
                 "usage_notes": "Primary data source"},
            ],
        }
        batch = map_payload(conn, _work_item(), payload, "initial", 1)
        pe_recs = [r for r in batch.records if r.table_name == "ProcessEntity"]
        assert len(pe_recs) >= 1
        assert pe_recs[0].values["entity_id"] == 1

    def test_data_reference_fields(self, conn):
        payload = {
            "domain_purpose": "Purpose",
            "personas": [],
            "business_process_inventory": [],
            "data_reference": [
                {"entity_identifier": "Contact",
                 "referenced_fields": ["contactType"],
                 "usage_notes": "Primary"},
            ],
        }
        batch = map_payload(conn, _work_item(), payload, "initial", 1)
        pf_recs = [r for r in batch.records if r.table_name == "ProcessField"]
        assert len(pf_recs) >= 1
        assert pf_recs[0].values["field_id"] == 1

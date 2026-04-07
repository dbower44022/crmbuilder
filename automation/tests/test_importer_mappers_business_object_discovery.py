"""Tests for automation.importer.mappers.business_object_discovery."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.importer.mappers.business_object_discovery import map_payload


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    # Seed domain and process for resolution
    c.execute("INSERT INTO WorkItem (item_type, status) VALUES ('master_prd', 'complete')")
    c.execute(
        "INSERT INTO AISession (work_item_id, session_type, generated_prompt, "
        "import_status, started_at) VALUES (1, 'initial', 'p', 'imported', CURRENT_TIMESTAMP)"
    )
    c.execute("INSERT INTO Domain (name, code, sort_order) VALUES ('Mentoring', 'MN', 1)")
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
    return {"id": 1, "item_type": "business_object_discovery", "status": "in_progress",
            "domain_id": None, "entity_id": None, "process_id": None}


def _payload():
    return {
        "business_objects": [
            {
                "name": "Contact",
                "description": "A person record",
                "classification": "entity",
                "entity_name": "Contact",
                "entity_code": "CON",
                "entity_type": "Person",
                "is_native": True,
                "source_domains": ["MN"],
                "fields": [
                    {"name": "contactType", "label": "Contact Type",
                     "field_type": "enum", "is_required": True,
                     "options": [
                         {"value": "mentor", "label": "Mentor"},
                         {"value": "mentee", "label": "Mentee"},
                     ]},
                ],
            },
            {
                "name": "Intake Process",
                "description": "The intake process",
                "classification": "process",
                "process_code": "MN-INTAKE",
            },
        ],
        "entity_participation": [],
        "dependency_order": ["Contact"],
    }


class TestBODMapper:
    def test_entity_classified_bo(self, conn):
        batch = map_payload(conn, _work_item(), _payload(), "initial", 1)
        entity_recs = [r for r in batch.records if r.table_name == "Entity"]
        assert len(entity_recs) == 1
        assert entity_recs[0].values["name"] == "Contact"
        assert entity_recs[0].values["code"] == "CON"
        assert entity_recs[0].values["entity_type"] == "Person"

    def test_entity_has_primary_domain(self, conn):
        batch = map_payload(conn, _work_item(), _payload(), "initial", 1)
        entity_recs = [r for r in batch.records if r.table_name == "Entity"]
        assert entity_recs[0].values.get("primary_domain_id") == 1

    def test_fields_created_for_entity(self, conn):
        batch = map_payload(conn, _work_item(), _payload(), "initial", 1)
        field_recs = [r for r in batch.records if r.table_name == "Field"]
        assert len(field_recs) == 1
        assert field_recs[0].values["name"] == "contactType"
        assert "entity_id" in field_recs[0].intra_batch_refs

    def test_field_options_for_enum(self, conn):
        batch = map_payload(conn, _work_item(), _payload(), "initial", 1)
        opt_recs = [r for r in batch.records if r.table_name == "FieldOption"]
        assert len(opt_recs) == 2
        values = {r.values["value"] for r in opt_recs}
        assert values == {"mentor", "mentee"}

    def test_process_classified_bo(self, conn):
        batch = map_payload(conn, _work_item(), _payload(), "initial", 1)
        bo_recs = [r for r in batch.records if r.table_name == "BusinessObject"]
        process_bo = [r for r in bo_recs if r.values["name"] == "Intake Process"]
        assert len(process_bo) == 1
        assert process_bo[0].values.get("resolved_to_process_id") == 1

    def test_bo_record_created(self, conn):
        batch = map_payload(conn, _work_item(), _payload(), "initial", 1)
        bo_recs = [r for r in batch.records if r.table_name == "BusinessObject"]
        assert len(bo_recs) == 2
        assert all(r.action == "create" for r in bo_recs)

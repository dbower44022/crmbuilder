"""Tests for automation.importer.mappers.entity_prd."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.importer.mappers.entity_prd import map_payload


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
    c.commit()
    yield c
    c.close()


def _work_item():
    return {"id": 1, "item_type": "entity_prd", "status": "in_progress",
            "domain_id": 1, "entity_id": 1, "process_id": None}


def _payload():
    return {
        "entity_metadata": {
            "entity_type": "Person",
            "is_native": True,
            "singular_label": "Contact",
            "plural_label": "Contacts",
            "description": "Refined description",
        },
        "native_fields": [
            {"field_name": "firstName", "label": "First Name",
             "field_type": "varchar", "is_required": True},
        ],
        "custom_fields": [
            {"field_name": "contactType", "label": "Contact Type",
             "field_type": "enum", "is_required": True,
             "options": [{"value": "mentor", "label": "Mentor"}]},
            {"field_name": "status", "label": "Status",
             "field_type": "varchar"},
        ],
        "relationships": [
            {"name": "contactAccount", "description": "Contact to Account",
             "entity_foreign": "Account", "link_type": "manyToOne",
             "link": "account", "link_foreign": "contacts",
             "label": "Account", "label_foreign": "Contacts"},
        ],
    }


class TestEntityPrdMapper:
    def test_entity_update(self, conn):
        batch = map_payload(conn, _work_item(), _payload(), "initial", 1)
        entity_recs = [r for r in batch.records if r.table_name == "Entity"]
        assert len(entity_recs) == 1
        assert entity_recs[0].action == "update"
        assert entity_recs[0].target_id == 1
        assert entity_recs[0].values["description"] == "Refined description"

    def test_native_field_created(self, conn):
        batch = map_payload(conn, _work_item(), _payload(), "initial", 1)
        field_recs = [r for r in batch.records if r.table_name == "Field"]
        native = [r for r in field_recs if r.values.get("is_native") is True]
        assert len(native) == 1
        assert native[0].values["name"] == "firstName"
        assert native[0].action == "create"

    def test_existing_field_updated(self, conn):
        batch = map_payload(conn, _work_item(), _payload(), "initial", 1)
        field_recs = [r for r in batch.records if r.table_name == "Field"]
        ct = [r for r in field_recs if r.values.get("name") == "contactType"]
        assert len(ct) == 1
        assert ct[0].action == "update"
        assert ct[0].target_id == 1  # existing field id

    def test_new_custom_field_created(self, conn):
        batch = map_payload(conn, _work_item(), _payload(), "initial", 1)
        field_recs = [r for r in batch.records if r.table_name == "Field"]
        status = [r for r in field_recs if r.values.get("name") == "status"]
        assert len(status) == 1
        assert status[0].action == "create"

    def test_field_options(self, conn):
        batch = map_payload(conn, _work_item(), _payload(), "initial", 1)
        opt_recs = [r for r in batch.records if r.table_name == "FieldOption"]
        assert len(opt_recs) == 1
        assert opt_recs[0].values["value"] == "mentor"

    def test_relationship_created(self, conn):
        batch = map_payload(conn, _work_item(), _payload(), "initial", 1)
        rel_recs = [r for r in batch.records if r.table_name == "Relationship"]
        assert len(rel_recs) == 1
        assert rel_recs[0].action == "create"
        assert rel_recs[0].values["name"] == "contactAccount"
        assert rel_recs[0].values["entity_id"] == 1

    def test_revision_updates_existing(self, conn):
        # Add a requirement
        conn.execute(
            "INSERT INTO Requirement (identifier, process_id, description, status) "
            "VALUES ('MN-INTAKE-REQ-001', 1, 'Old desc', 'proposed')"
        )
        conn.commit()

        payload = {
            "entity_metadata": {},
            "native_fields": [],
            "custom_fields": [],
            "relationships": [],
            "requirements": [
                {"identifier": "MN-INTAKE-REQ-001", "description": "Updated desc",
                 "priority": "must", "process_code": "MN-INTAKE"},
            ],
        }
        batch = map_payload(conn, _work_item(), payload, "revision", 1)
        req_recs = [r for r in batch.records if r.table_name == "Requirement"]
        assert len(req_recs) == 1
        assert req_recs[0].action == "update"
        assert req_recs[0].target_id == 1

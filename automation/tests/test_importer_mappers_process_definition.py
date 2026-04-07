"""Tests for automation.importer.mappers.process_definition."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.importer.mappers.process_definition import map_payload


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
    return {"id": 1, "item_type": "process_definition", "status": "in_progress",
            "domain_id": 1, "entity_id": None, "process_id": 1}


def _payload():
    return {
        "process_purpose": "Intake new mentors",
        "triggers": {"preconditions": ["Application submitted"]},
        "personas": [
            {"identifier": "MNT", "role": "performer", "description": "Performs intake"},
        ],
        "workflow": [
            {"step_name": "Review Application", "step_type": "action",
             "description": "Review the submitted application",
             "performer_persona": "MNT"},
        ],
        "completion": {"end_states": ["Approved", "Rejected"]},
        "system_requirements": [
            {"identifier": "MN-INTAKE-REQ-001", "description": "Must capture consent",
             "priority": "must"},
        ],
        "process_data": [
            {"entity_name": "Contact",
             "field_references": ["contactType"]},
        ],
        "data_collected": [],
    }


class TestProcessDefinitionMapper:
    def test_process_update(self, conn):
        batch = map_payload(conn, _work_item(), _payload(), "initial", 1)
        proc_recs = [r for r in batch.records if r.table_name == "Process"]
        assert len(proc_recs) == 1
        assert proc_recs[0].action == "update"
        assert proc_recs[0].target_id == 1
        assert proc_recs[0].values["description"] == "Intake new mentors"

    def test_process_persona_created(self, conn):
        batch = map_payload(conn, _work_item(), _payload(), "initial", 1)
        pp_recs = [r for r in batch.records if r.table_name == "ProcessPersona"]
        assert len(pp_recs) >= 1
        assert pp_recs[0].values["persona_id"] == 1
        assert pp_recs[0].values["role"] == "performer"

    def test_existing_process_persona_updated(self, conn):
        # Create existing ProcessPersona
        conn.execute(
            "INSERT INTO ProcessPersona (process_id, persona_id, role, description) "
            "VALUES (1, 1, 'initiator', 'Old role')"
        )
        conn.commit()
        batch = map_payload(conn, _work_item(), _payload(), "initial", 1)
        pp_recs = [r for r in batch.records if r.table_name == "ProcessPersona"]
        assert len(pp_recs) >= 1
        assert pp_recs[0].action == "update"

    def test_workflow_steps(self, conn):
        batch = map_payload(conn, _work_item(), _payload(), "initial", 1)
        step_recs = [r for r in batch.records if r.table_name == "ProcessStep"]
        assert len(step_recs) == 1
        assert step_recs[0].values["name"] == "Review Application"
        assert step_recs[0].values["performer_persona_id"] == 1

    def test_requirements(self, conn):
        batch = map_payload(conn, _work_item(), _payload(), "initial", 1)
        req_recs = [r for r in batch.records if r.table_name == "Requirement"]
        assert len(req_recs) == 1
        assert req_recs[0].values["identifier"] == "MN-INTAKE-REQ-001"
        assert req_recs[0].values["process_id"] == 1

    def test_process_entity(self, conn):
        batch = map_payload(conn, _work_item(), _payload(), "initial", 1)
        pe_recs = [r for r in batch.records if r.table_name == "ProcessEntity"]
        assert len(pe_recs) >= 1
        assert pe_recs[0].values["entity_id"] == 1

    def test_process_field(self, conn):
        batch = map_payload(conn, _work_item(), _payload(), "initial", 1)
        pf_recs = [r for r in batch.records if r.table_name == "ProcessField"]
        assert len(pf_recs) >= 1
        assert pf_recs[0].values["field_id"] == 1

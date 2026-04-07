"""Tests for automation.importer.mappers.yaml_generation."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.importer.mappers.yaml_generation import map_payload


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
        "INSERT INTO FieldOption (field_id, value, label) "
        "VALUES (1, 'mentor', 'Mentor')"
    )
    c.execute(
        "INSERT INTO Relationship (name, description, entity_id, entity_foreign_id, "
        "link_type, link, link_foreign, label, label_foreign) "
        "VALUES ('contactAccount', 'Contact to Account', 1, 1, 'manyToOne', "
        "'account', 'contacts', 'Account', 'Contacts')"
    )
    c.commit()
    yield c
    c.close()


def _work_item():
    return {"id": 1, "item_type": "yaml_generation", "status": "in_progress",
            "domain_id": 1, "entity_id": None, "process_id": None}


class TestYamlGenerationMapper:
    def test_field_updates(self, conn):
        payload = {
            "entity_configurations": [
                {"entity_name": "Contact", "fields": [
                    {"field_name": "contactType", "tooltip": "Select type",
                     "sort_order": 5, "category": "General"},
                ]},
            ],
            "relationship_configurations": [],
            "layout_definitions": [],
            "resolved_exceptions": [],
            "unresolved_exceptions": [],
        }
        batch = map_payload(conn, _work_item(), payload, "initial", 1)
        field_recs = [r for r in batch.records if r.table_name == "Field"]
        assert len(field_recs) == 1
        assert field_recs[0].action == "update"
        assert field_recs[0].values["tooltip"] == "Select type"

    def test_field_option_style(self, conn):
        payload = {
            "entity_configurations": [
                {"entity_name": "Contact", "fields": [
                    {"field_name": "contactType",
                     "options": [{"value": "mentor", "style": "success"}]},
                ]},
            ],
            "relationship_configurations": [],
            "layout_definitions": [],
            "resolved_exceptions": [],
            "unresolved_exceptions": [],
        }
        batch = map_payload(conn, _work_item(), payload, "initial", 1)
        opt_recs = [r for r in batch.records if r.table_name == "FieldOption"]
        assert len(opt_recs) == 1
        assert opt_recs[0].action == "update"
        assert opt_recs[0].values["style"] == "success"

    def test_relationship_update(self, conn):
        payload = {
            "entity_configurations": [],
            "relationship_configurations": [
                {"name": "contactAccount", "audited": True},
            ],
            "layout_definitions": [],
            "resolved_exceptions": [],
            "unresolved_exceptions": [],
        }
        batch = map_payload(conn, _work_item(), payload, "initial", 1)
        rel_recs = [r for r in batch.records if r.table_name == "Relationship"]
        assert len(rel_recs) == 1
        assert rel_recs[0].action == "update"
        assert rel_recs[0].values["audited"] is True

    def test_layout_panel_and_rows(self, conn):
        payload = {
            "entity_configurations": [],
            "relationship_configurations": [],
            "layout_definitions": [
                {"entity_name": "Contact", "panels": [
                    {"label": "General", "layout_mode": "rows", "sort_order": 1,
                     "rows": [
                         {"cell_1_field": "contactType", "sort_order": 1},
                     ]},
                ], "list_columns": []},
            ],
            "resolved_exceptions": [],
            "unresolved_exceptions": [],
        }
        batch = map_payload(conn, _work_item(), payload, "initial", 1)
        panel_recs = [r for r in batch.records if r.table_name == "LayoutPanel"]
        assert len(panel_recs) == 1
        assert panel_recs[0].values["label"] == "General"
        row_recs = [r for r in batch.records if r.table_name == "LayoutRow"]
        assert len(row_recs) == 1
        assert "panel_id" in row_recs[0].intra_batch_refs

    def test_resolved_exceptions(self, conn):
        payload = {
            "entity_configurations": [],
            "relationship_configurations": [],
            "layout_definitions": [],
            "resolved_exceptions": [
                {"description": "Field naming conflict", "resolution": "Used standard name"},
            ],
            "unresolved_exceptions": [],
        }
        batch = map_payload(conn, _work_item(), payload, "initial", 1)
        dec_recs = [r for r in batch.records if r.table_name == "Decision"]
        assert len(dec_recs) >= 1

    def test_unresolved_exceptions(self, conn):
        payload = {
            "entity_configurations": [],
            "relationship_configurations": [],
            "layout_definitions": [],
            "resolved_exceptions": [],
            "unresolved_exceptions": [
                {"description": "Missing data", "impact": "Needs review"},
            ],
        }
        batch = map_payload(conn, _work_item(), payload, "initial", 1)
        issue_recs = [r for r in batch.records if r.table_name == "OpenIssue"]
        assert len(issue_recs) >= 1

"""Tests for the User Process Guide document type.

Covers:
  - paths.resolve_output_path for USER_PROCESS_GUIDE (top-level + sub-domain)
  - queries.user_process_guide.query (DB only, DB+YAML, missing programs/)
  - templates.user_process_guide_template.generate writes a .docx file
  - end-to-end pipeline.run_pipeline produces the expected file
  - workflow.graph creates and backfills user_process_guide work items
  - migrations.run_client_migrations applies _client_v8 cleanly
"""

from __future__ import annotations

import sqlite3

import pytest

from automation.db.migrations import run_client_migrations, run_master_migrations
from automation.docgen import DocumentType
from automation.docgen.paths import resolve_output_path
from automation.docgen.queries import user_process_guide as q_user_process_guide
from automation.docgen.templates import user_process_guide_template
from automation.workflow.graph import (
    after_business_object_discovery_import,
    backfill_user_process_guides,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path) -> sqlite3.Connection:
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


@pytest.fixture()
def master_conn(tmp_path) -> sqlite3.Connection:
    db_path = tmp_path / "master.db"
    c = run_master_migrations(str(db_path))
    c.execute(
        "INSERT INTO Client (name, code, database_path, project_folder) "
        "VALUES ('Test Org', 'TO', '/tmp/test.db', ?)",
        (str(tmp_path),),
    )
    c.commit()
    yield c
    c.close()


def _seed_process_with_data(conn: sqlite3.Connection) -> int:
    """Seed a Process with steps, persona, requirements, entity, and field.

    Returns the user_process_guide WorkItem.id.
    """
    conn.execute(
        "INSERT INTO Domain (id, name, code, sort_order) "
        "VALUES (1, 'Mentoring', 'MN', 1)"
    )
    conn.execute(
        "INSERT INTO Entity (id, name, code, entity_type, is_native, primary_domain_id) "
        "VALUES (1, 'Engagement', 'ENG', 'Base', 0, 1)"
    )
    conn.execute(
        "INSERT INTO Field (id, entity_id, name, label, field_type, is_required) "
        "VALUES (1, 1, 'engagementStatus', 'Engagement Status', 'enum', 1)"
    )
    conn.execute(
        "INSERT INTO Persona (id, name, code, description) "
        "VALUES (1, 'Program Coordinator', 'MST-PER-001', 'Runs intake')"
    )
    conn.execute(
        "INSERT INTO Process (id, domain_id, name, code, description, "
        "triggers, completion_criteria, sort_order) VALUES "
        "(1, 1, 'Client Intake', 'MN-INTAKE', "
        "'Onboard a new client into the program.', "
        "'A new client application has been received.', "
        "'Client engagement is created and matched to a mentor.', 1)"
    )
    conn.execute(
        "INSERT INTO ProcessPersona (process_id, persona_id, role) "
        "VALUES (1, 1, 'initiator')"
    )
    conn.execute(
        "INSERT INTO ProcessStep (id, process_id, name, description, "
        "step_type, sort_order, performer_persona_id) VALUES "
        "(1, 1, 'Open Engagement', "
        "'Open the Engagement record and set Engagement Status to Active.', "
        "'action', 1, 1)"
    )
    conn.execute(
        "INSERT INTO ProcessEntity (id, process_id, entity_id, role) "
        "VALUES (1, 1, 1, 'primary')"
    )
    conn.execute(
        "INSERT INTO ProcessField (id, process_id, field_id, usage, description) "
        "VALUES (1, 1, 1, 'collected', 'Set when intake completes.')"
    )
    conn.execute(
        "INSERT INTO Requirement (process_id, identifier, description, "
        "priority, status) VALUES "
        "(1, 'MN-INTAKE-REQ-001', 'The system must capture engagement status.', "
        "'must', 'approved')"
    )
    conn.execute(
        "INSERT INTO OpenIssue (process_id, identifier, title, description, "
        "status) VALUES "
        "(1, 'MN-INTAKE-ISS-001', 'Confirm decline reason values', "
        "'Need full enum list from coordinator.', 'open')"
    )
    # Process-definition work item must exist so backfill creates the guide WI
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, status, domain_id, process_id, "
        "completed_at) VALUES "
        "(100, 'process_definition', 'complete', 1, 1, '2026-04-01 12:00:00')"
    )
    conn.commit()

    backfill_user_process_guides(conn)
    row = conn.execute(
        "SELECT id FROM WorkItem "
        "WHERE item_type = 'user_process_guide' AND process_id = 1"
    ).fetchone()
    assert row is not None, "Backfill did not create user_process_guide WI"
    # Mark it complete so 'final' generation is permitted in pipeline tests.
    conn.execute(
        "UPDATE WorkItem SET status = 'complete', "
        "completed_at = '2026-04-02 12:00:00' WHERE id = ?",
        (row[0],),
    )
    conn.commit()
    return row[0]


def _write_yaml_programs(programs_dir) -> None:
    """Write a minimal YAML program file matching the seeded Engagement entity."""
    programs_dir.mkdir(parents=True, exist_ok=True)
    yaml_text = """\
version: "1.1"
entities:
  Engagement:
    description: A mentoring engagement between a mentor and a client.
    labels:
      singular: Engagement
      plural: Engagements
    fields:
      - name: engagementStatus
        label: Engagement Status
        type: enum
        required: true
        description: Current lifecycle state of the engagement.
        options:
          - Pending
          - Active
          - Closed
        translatedOptions:
          Pending: Pending Match
          Active: Active Engagement
          Closed: Closed
    layout:
      detail:
        - label: Engagement Detail
          tabLabel: Detail
          rows:
            - [engagementStatus]
    relationships:
      - name: mentorContact
        type: belongsTo
        targetEntity: Contact
"""
    (programs_dir / "engagement.yaml").write_text(yaml_text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


class TestUserProcessGuidePath:

    def test_top_level_domain(self, conn, master_conn, tmp_path):
        wi_id = _seed_process_with_data(conn)
        path = resolve_output_path(
            DocumentType.USER_PROCESS_GUIDE, conn, wi_id, tmp_path, master_conn,
        )
        assert path.name == "MN-INTAKE-user-guide.docx"
        assert "PRDs" in str(path)
        assert path.parent.name == "MN"

    def test_subdomain_nesting(self, conn, master_conn, tmp_path):
        _seed_process_with_data(conn)
        conn.execute(
            "INSERT INTO Domain (id, name, code, sort_order, parent_domain_id) "
            "VALUES (2, 'Partner', 'CR-PARTNER', 1, 1)"
        )
        conn.execute(
            "INSERT INTO Process (id, domain_id, name, code, sort_order) "
            "VALUES (2, 2, 'Manage Partner', 'CR-PARTNER-MANAGE', 1)"
        )
        conn.execute(
            "INSERT INTO WorkItem (id, item_type, status, domain_id, process_id) "
            "VALUES (200, 'process_definition', 'complete', 2, 2)"
        )
        conn.commit()
        backfill_user_process_guides(conn)
        row = conn.execute(
            "SELECT id FROM WorkItem "
            "WHERE item_type = 'user_process_guide' AND process_id = 2"
        ).fetchone()
        path = resolve_output_path(
            DocumentType.USER_PROCESS_GUIDE, conn, row[0], tmp_path, master_conn,
        )
        assert path.name == "CR-PARTNER-MANAGE-user-guide.docx"
        # Path should be PRDs/MN/CR-PARTNER/CR-PARTNER-MANAGE-user-guide.docx
        assert "MN" in str(path)
        assert "CR-PARTNER" in str(path)


# ---------------------------------------------------------------------------
# Query module
# ---------------------------------------------------------------------------


class TestUserProcessGuideQuery:

    def test_db_only_no_yaml_block(self, conn, master_conn):
        wi_id = _seed_process_with_data(conn)
        data = q_user_process_guide.query(conn, wi_id, master_conn)

        assert data["process"]["code"] == "MN-INTAKE"
        assert data["domain"]["code"] == "MN"
        assert len(data["personas"]) == 1
        assert data["personas"][0]["role"] == "initiator"
        assert len(data["steps"]) == 1
        assert data["steps"][0]["performer_name"] == "Program Coordinator"
        assert len(data["requirements"]) == 1
        assert len(data["data_reference"]) == 1
        assert data["data_reference"][0]["entity_name"] == "Engagement"
        assert len(data["open_issues"]) == 1
        assert data["yaml_by_entity"] == {}
        # No project folder passed -> no errors expected
        assert data["yaml_load_errors"] == []

    def test_with_yaml(self, conn, master_conn, tmp_path):
        wi_id = _seed_process_with_data(conn)
        _write_yaml_programs(tmp_path / "programs")

        data = q_user_process_guide.query(
            conn, wi_id, master_conn, project_folder=tmp_path,
        )

        assert "Engagement" in data["yaml_by_entity"]
        engagement = data["yaml_by_entity"]["Engagement"]
        assert engagement["label_singular"] == "Engagement"
        assert engagement["label_plural"] == "Engagements"
        assert any(f["name"] == "engagementStatus" for f in engagement["fields"])
        # Status field gets surfaced separately
        assert any(
            sf["name"] == "engagementStatus"
            for sf in engagement["status_fields"]
        )
        assert engagement["panels"]
        assert engagement["relationships"]
        assert data["yaml_load_errors"] == []

    def test_missing_programs_dir_warns_but_returns(self, conn, master_conn, tmp_path):
        wi_id = _seed_process_with_data(conn)
        # No programs/ dir under tmp_path
        data = q_user_process_guide.query(
            conn, wi_id, master_conn, project_folder=tmp_path,
        )
        assert data["yaml_by_entity"] == {}
        assert any("programs" in err for err in data["yaml_load_errors"])


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------


class TestUserProcessGuideTemplate:

    def test_generate_writes_docx(self, conn, master_conn, tmp_path):
        wi_id = _seed_process_with_data(conn)
        _write_yaml_programs(tmp_path / "programs")
        data = q_user_process_guide.query(
            conn, wi_id, master_conn, project_folder=tmp_path,
        )
        out = tmp_path / "out" / "MN-INTAKE-user-guide.docx"
        user_process_guide_template.generate(data, out, is_draft=False)
        assert out.exists()
        # Verify the file is non-trivial — a python-docx output is typically
        # several KB minimum.
        assert out.stat().st_size > 4000


# ---------------------------------------------------------------------------
# End-to-end pipeline
# ---------------------------------------------------------------------------


class TestUserProcessGuidePipeline:

    def test_run_pipeline_final(self, conn, master_conn, tmp_path):
        from automation.docgen.pipeline import run_pipeline

        wi_id = _seed_process_with_data(conn)
        _write_yaml_programs(tmp_path / "programs")

        # The pipeline writes to PRDs/{domain}/...; ensure parent is tmp_path.
        result = run_pipeline(
            conn, wi_id, mode="final",
            project_folder=tmp_path, master_conn=master_conn,
        )

        # Git commit will fail since tmp_path isn't a repo — that's surfaced
        # via result.error in the pipeline. The file should still be written.
        expected = tmp_path / "PRDs" / "MN" / "MN-INTAKE-user-guide.docx"
        assert expected.exists(), (
            f"Expected output at {expected}; pipeline error: {result.error}"
        )


# ---------------------------------------------------------------------------
# Workflow graph integration
# ---------------------------------------------------------------------------


class TestWorkflowGraphCreatesGuide:

    def test_after_bod_creates_guide_per_process(self, conn):
        # Seed Domain, Entity, Process, plus prerequisite work items
        conn.execute(
            "INSERT INTO Domain (id, name, code, sort_order) "
            "VALUES (1, 'Mentoring', 'MN', 1)"
        )
        conn.execute(
            "INSERT INTO Entity (id, name, code, entity_type, is_native, "
            "primary_domain_id) VALUES "
            "(1, 'Engagement', 'ENG', 'Base', 0, 1)"
        )
        conn.execute(
            "INSERT INTO Process (id, domain_id, name, code, sort_order) "
            "VALUES (1, 1, 'Client Intake', 'MN-INTAKE', 1)"
        )
        conn.execute(
            "INSERT INTO WorkItem (item_type, status) "
            "VALUES ('master_prd', 'complete')"
        )
        conn.execute(
            "INSERT INTO WorkItem (item_type, status) "
            "VALUES ('business_object_discovery', 'complete')"
        )
        conn.commit()

        after_business_object_discovery_import(conn)

        rows = conn.execute(
            "SELECT item_type FROM WorkItem WHERE process_id = 1 "
            "ORDER BY item_type"
        ).fetchall()
        types = [r[0] for r in rows]
        assert "process_definition" in types
        assert "user_process_guide" in types

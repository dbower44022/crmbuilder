"""Tests for automation.impact.queries — cross-reference query engine."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.impact.queries import (
    batch_trace_changes,
    trace_change,
    trace_decision_change,
    trace_domain_change,
    trace_entity_change,
    trace_field_change,
    trace_field_option_change,
    trace_open_issue_change,
    trace_persona_change,
    trace_process_change,
    trace_process_step_change,
    trace_relationship_change,
    trace_requirement_change,
)


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


def _seed(conn):
    """Seed a populated test database with cross-references."""
    # WorkItem (needed first for AISession FK)
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, status) VALUES (1, 'master_prd', 'complete')"
    )

    # AISession (needed for created_by_session_id FKs)
    conn.execute(
        "INSERT INTO AISession (id, work_item_id, session_type, generated_prompt, "
        "import_status, started_at) VALUES (1, 1, 'initial', 'p', 'imported', '2025-01-01')"
    )
    conn.commit()

    # Domain
    conn.execute(
        "INSERT INTO Domain (id, name, code, sort_order) VALUES (1, 'Mentoring', 'MN', 1)"
    )
    # Entity
    conn.execute(
        "INSERT INTO Entity (id, name, code, entity_type, is_native, primary_domain_id) "
        "VALUES (1, 'Contact', 'CONTACT', 'Person', 0, 1)"
    )
    conn.execute(
        "INSERT INTO Entity (id, name, code, entity_type, is_native, primary_domain_id) "
        "VALUES (2, 'Account', 'ACCOUNT', 'Company', 1, 1)"
    )
    # Field
    conn.execute(
        "INSERT INTO Field (id, entity_id, name, label, field_type) "
        "VALUES (1, 1, 'contactType', 'Contact Type', 'enum')"
    )
    conn.execute(
        "INSERT INTO Field (id, entity_id, name, label, field_type) "
        "VALUES (2, 1, 'mentorStatus', 'Mentor Status', 'enum')"
    )
    conn.execute(
        "INSERT INTO Field (id, entity_id, name, label, field_type, default_value) "
        "VALUES (3, 1, 'intakeDate', 'Intake Date', 'date', NULL)"
    )
    # FieldOption
    conn.execute(
        "INSERT INTO FieldOption (id, field_id, value, label) VALUES (1, 1, 'Mentor', 'Mentor')"
    )
    conn.execute(
        "INSERT INTO FieldOption (id, field_id, value, label) VALUES (2, 1, 'Mentee', 'Mentee')"
    )
    # Persona
    conn.execute(
        "INSERT INTO Persona (id, name, code, persona_entity_id, persona_field_id, "
        "persona_field_value) VALUES (1, 'Volunteer Mentor', 'MENTOR', 1, 1, 'Mentor')"
    )
    # Process
    conn.execute(
        "INSERT INTO Process (id, domain_id, name, code, sort_order) "
        "VALUES (1, 1, 'Mentor Onboarding', 'MN-ONBOARD', 1)"
    )
    # ProcessStep
    conn.execute(
        "INSERT INTO ProcessStep (id, process_id, name, step_type, sort_order, "
        "performer_persona_id) VALUES (1, 1, 'Verify Training', 'action', 1, 1)"
    )
    # Requirement
    conn.execute(
        "INSERT INTO Requirement (id, identifier, process_id, description, status) "
        "VALUES (1, 'MN-ONBOARD-REQ-001', 1, 'Must verify training', 'approved')"
    )
    # Cross-references
    conn.execute(
        "INSERT INTO ProcessEntity (id, process_id, entity_id, process_step_id, role) "
        "VALUES (1, 1, 1, 1, 'primary')"
    )
    conn.execute(
        "INSERT INTO ProcessField (id, process_id, field_id, process_step_id, usage) "
        "VALUES (1, 1, 1, 1, 'evaluated')"
    )
    conn.execute(
        "INSERT INTO ProcessField (id, process_id, field_id, usage) "
        "VALUES (2, 1, 2, 'displayed')"
    )
    conn.execute(
        "INSERT INTO ProcessPersona (id, process_id, persona_id, role) "
        "VALUES (1, 1, 1, 'performer')"
    )
    # Relationship
    conn.execute(
        "INSERT INTO Relationship (id, name, description, entity_id, entity_foreign_id, "
        "link_type, link, link_foreign, label, label_foreign) "
        "VALUES (1, 'Contact-Account', 'Contact belongs to Account', 1, 2, "
        "'manyToOne', 'account', 'contacts', 'Account', 'Contacts')"
    )
    # Layout
    conn.execute(
        "INSERT INTO LayoutPanel (id, entity_id, label, sort_order, layout_mode, "
        "dynamic_logic_attribute, dynamic_logic_value) "
        "VALUES (1, 1, 'Mentor Details', 1, 'rows', 'contactType', 'Mentor')"
    )
    conn.execute(
        "INSERT INTO LayoutRow (id, panel_id, sort_order, cell_1_field_id, cell_2_field_id) "
        "VALUES (1, 1, 1, 1, 2)"
    )
    conn.execute(
        "INSERT INTO LayoutTab (id, panel_id, label, category, sort_order) "
        "VALUES (1, 1, 'Activities', 'activities', 1)"
    )
    conn.execute(
        "INSERT INTO ListColumn (id, entity_id, field_id, sort_order) "
        "VALUES (1, 1, 1, 1)"
    )
    conn.execute(
        "INSERT INTO ListColumn (id, entity_id, field_id, sort_order) "
        "VALUES (2, 1, 2, 2)"
    )
    # Decision & OpenIssue
    conn.execute(
        "INSERT INTO Decision (id, identifier, title, description, status, "
        "field_id, entity_id, process_id, domain_id, requirement_id) "
        "VALUES (1, 'MN-DEC-001', 'Use enum', 'Use enum for type', 'proposed', "
        "1, 1, 1, 1, 1)"
    )
    conn.execute(
        "INSERT INTO OpenIssue (id, identifier, title, description, status, "
        "field_id, entity_id, process_id, domain_id, requirement_id) "
        "VALUES (1, 'MN-ISS-001', 'Clarify type', 'Clarify contact type', 'open', "
        "1, 1, 1, 1, 1)"
    )
    # WorkItems for entity and process
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, entity_id, status) "
        "VALUES (2, 'entity_prd', 1, 'complete')"
    )
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, process_id, status) "
        "VALUES (3, 'process_definition', 1, 'in_progress')"
    )
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, domain_id, status) "
        "VALUES (4, 'domain_overview', 1, 'complete')"
    )

    # Sub-domain
    conn.execute(
        "INSERT INTO Domain (id, name, code, sort_order, parent_domain_id) "
        "VALUES (2, 'Mentor Management', 'MM', 2, 1)"
    )

    conn.commit()


class TestFieldChange:
    """12.3.1 — Field change traces."""

    def test_update_returns_correct_targets(self, conn):
        _seed(conn)
        results = trace_field_change(conn, 1, "update")
        tables = {r.table_name for r in results}
        assert "ProcessField" in tables
        assert "LayoutRow" in tables
        assert "ListColumn" in tables
        assert "Persona" in tables
        assert "Decision" in tables
        assert "OpenIssue" in tables

    def test_decision_and_issue_not_require_review(self, conn):
        _seed(conn)
        results = trace_field_change(conn, 1, "update")
        for r in results:
            if r.table_name in ("Decision", "OpenIssue"):
                assert r.requires_review is False
            else:
                assert r.requires_review is True

    def test_delete_descriptions(self, conn):
        _seed(conn)
        results = trace_field_change(conn, 1, "delete")
        pf = [r for r in results if r.table_name == "ProcessField"]
        assert len(pf) == 1
        assert "deletion" in pf[0].impact_description
        assert "orphan" in pf[0].impact_description

    def test_step_level_granularity(self, conn):
        _seed(conn)
        results = trace_field_change(conn, 1, "update")
        pf = [r for r in results if r.table_name == "ProcessField"][0]
        assert "step 'Verify Training'" in pf.impact_description
        assert "evaluated" in pf.impact_description

    def test_process_level_when_no_step(self, conn):
        _seed(conn)
        # field 2 (mentorStatus) has ProcessField without step
        results = trace_field_change(conn, 2, "update")
        pf = [r for r in results if r.table_name == "ProcessField"][0]
        assert "step" not in pf.impact_description
        assert "displayed" in pf.impact_description

    def test_insert_returns_empty(self, conn):
        _seed(conn)
        assert trace_field_change(conn, 1, "insert") == []


class TestEntityChange:
    """12.3.2 — Entity change traces."""

    def test_update_returns_direct_refs(self, conn):
        _seed(conn)
        results = trace_entity_change(conn, 1, "update")
        tables = {r.table_name for r in results}
        assert "ProcessEntity" in tables
        assert "Field" in tables
        assert "Relationship" in tables
        assert "LayoutPanel" in tables
        assert "Persona" in tables
        assert "WorkItem" in tables

    def test_delete_transitive_field_tracing(self, conn):
        _seed(conn)
        results = trace_entity_change(conn, 1, "delete")
        tables = [r.table_name for r in results]
        # Field is surfaced AND its downstream ProcessField, LayoutRow, etc.
        assert "Field" in tables
        assert "ProcessField" in tables  # transitive via field
        assert "LayoutRow" in tables  # transitive via field AND via panel

    def test_delete_transitive_panel_children(self, conn):
        _seed(conn)
        results = trace_entity_change(conn, 1, "delete")
        tables = [r.table_name for r in results]
        assert "LayoutPanel" in tables
        assert "LayoutRow" in tables
        assert "LayoutTab" in tables

    def test_update_no_transitive_tracing(self, conn):
        _seed(conn)
        results = trace_entity_change(conn, 1, "update")
        # Fields are surfaced but their downstream ProcessField is NOT
        # (one-level only for updates)
        field_results = [r for r in results if r.table_name == "Field"]
        assert len(field_results) > 0
        # ProcessField should NOT appear for entity update at field level
        # (ProcessField from direct ProcessEntity IS there though)
        pf_from_entity = [
            r for r in results
            if r.table_name == "ProcessField"
        ]
        # ProcessField should not appear because entity update doesn't trace through fields
        assert len(pf_from_entity) == 0


class TestFieldOptionChange:
    """12.3.3 — FieldOption change traces."""

    def test_persona_match(self, conn):
        _seed(conn)
        results = trace_field_option_change(conn, 1, "update")  # 'Mentor' option
        persona = [r for r in results if r.table_name == "Persona"]
        assert len(persona) == 1
        assert "Volunteer Mentor" in persona[0].impact_description

    def test_layout_panel_dynamic_logic(self, conn):
        _seed(conn)
        results = trace_field_option_change(conn, 1, "update")
        panels = [r for r in results if r.table_name == "LayoutPanel"]
        assert len(panels) == 1
        assert "visibility" in panels[0].impact_description

    def test_field_default_value(self, conn):
        _seed(conn)
        # Set field 1's default_value to 'Mentor'
        conn.execute("UPDATE Field SET default_value = 'Mentor' WHERE id = 1")
        conn.commit()
        results = trace_field_option_change(conn, 1, "delete")
        fields = [r for r in results if r.table_name == "Field"]
        assert len(fields) == 1
        assert "default value" in fields[0].impact_description

    def test_no_match_different_option(self, conn):
        _seed(conn)
        # Option 2 is 'Mentee' — persona is discriminated by 'Mentor'
        results = trace_field_option_change(conn, 2, "update")
        persona = [r for r in results if r.table_name == "Persona"]
        assert len(persona) == 0


class TestProcessChange:
    """12.3.4 — Process change traces."""

    def test_update_direct_refs(self, conn):
        _seed(conn)
        results = trace_process_change(conn, 1, "update")
        tables = {r.table_name for r in results}
        assert "ProcessStep" in tables
        assert "ProcessEntity" in tables
        assert "ProcessField" in tables
        assert "ProcessPersona" in tables
        assert "Requirement" in tables
        assert "Decision" in tables
        assert "OpenIssue" in tables
        assert "WorkItem" in tables

    def test_delete_transitive_step_tracing(self, conn):
        _seed(conn)
        results = trace_process_change(conn, 1, "delete")
        tables = [r.table_name for r in results]
        # ProcessStep is surfaced AND its downstream ProcessEntity, ProcessField
        assert "ProcessStep" in tables
        # Transitive: step → ProcessEntity at step level
        step_pe = [
            r for r in results
            if r.table_name == "ProcessEntity"
            and "step 'Verify Training'" in r.impact_description
        ]
        assert len(step_pe) >= 1

    def test_delete_transitive_requirement_tracing(self, conn):
        _seed(conn)
        results = trace_process_change(conn, 1, "delete")
        tables = [r.table_name for r in results]
        assert "Requirement" in tables
        # Transitive: requirement → Decision, OpenIssue
        # These may appear from both process-level and requirement-level queries


class TestPersonaChange:
    """12.3.5 — Persona change traces."""

    def test_update_returns_refs(self, conn):
        _seed(conn)
        results = trace_persona_change(conn, 1, "update")
        tables = {r.table_name for r in results}
        assert "ProcessPersona" in tables
        assert "ProcessStep" in tables

    def test_process_step_performer(self, conn):
        _seed(conn)
        results = trace_persona_change(conn, 1, "update")
        steps = [r for r in results if r.table_name == "ProcessStep"]
        assert len(steps) == 1
        assert "performer" in steps[0].impact_description


class TestRelationshipChange:
    """12.3.6 — Relationship change traces."""

    def test_returns_panels_and_entities(self, conn):
        _seed(conn)
        results = trace_relationship_change(conn, 1, "update")
        tables = {r.table_name for r in results}
        assert "LayoutPanel" in tables
        assert "Entity" in tables

    def test_entity_impacts_informational(self, conn):
        _seed(conn)
        results = trace_relationship_change(conn, 1, "update")
        entities = [r for r in results if r.table_name == "Entity"]
        assert len(entities) == 2  # both sides
        for e in entities:
            assert e.requires_review is False


class TestDomainChange:
    """12.3.7 — Domain change traces."""

    def test_update_returns_refs(self, conn):
        _seed(conn)
        results = trace_domain_change(conn, 1, "update")
        tables = {r.table_name for r in results}
        assert "Process" in tables
        assert "Domain" in tables  # sub-domain
        assert "Entity" in tables
        assert "WorkItem" in tables

    def test_delete_transitive_process(self, conn):
        _seed(conn)
        results = trace_domain_change(conn, 1, "delete")
        tables = [r.table_name for r in results]
        assert "Process" in tables
        # Transitive: process → steps, cross-refs, requirements
        assert "ProcessStep" in tables


class TestRequirementChange:
    """12.3.8 — Requirement change traces."""

    def test_returns_decision_and_issue(self, conn):
        _seed(conn)
        results = trace_requirement_change(conn, 1, "update")
        tables = {r.table_name for r in results}
        assert "Decision" in tables
        assert "OpenIssue" in tables
        for r in results:
            assert r.requires_review is False


class TestProcessStepChange:
    """12.3.9 — ProcessStep change traces."""

    def test_returns_step_level_refs(self, conn):
        _seed(conn)
        results = trace_process_step_change(conn, 1, "update")
        tables = {r.table_name for r in results}
        assert "ProcessEntity" in tables
        assert "ProcessField" in tables

    def test_no_process_persona_step_level(self, conn):
        """ProcessPersona has no process_step_id in schema."""
        _seed(conn)
        results = trace_process_step_change(conn, 1, "update")
        tables = {r.table_name for r in results}
        assert "ProcessPersona" not in tables


class TestLeafNodes:
    """12.3.10 — Decision and OpenIssue are leaf nodes."""

    def test_decision_returns_empty(self, conn):
        _seed(conn)
        assert trace_decision_change(conn, 1, "update") == []
        assert trace_decision_change(conn, 1, "delete") == []

    def test_open_issue_returns_empty(self, conn):
        _seed(conn)
        assert trace_open_issue_change(conn, 1, "update") == []
        assert trace_open_issue_change(conn, 1, "delete") == []


class TestDispatcher:
    """trace_change() dispatcher."""

    def test_dispatches_field(self, conn):
        _seed(conn)
        results = trace_change(conn, "Field", 1, "update")
        assert len(results) > 0

    def test_unknown_table_returns_empty(self, conn):
        assert trace_change(conn, "NonExistent", 1, "update") == []

    def test_insert_returns_empty(self, conn):
        _seed(conn)
        assert trace_change(conn, "Field", 1, "insert") == []


class TestBatchConsolidation:
    """batch_trace_changes() — query consolidation."""

    def test_returns_same_results_as_individual(self, conn):
        _seed(conn)
        changes = [
            ("Field", 1, "update"),
            ("Field", 2, "update"),
        ]
        batch_results = batch_trace_changes(conn, changes)
        individual_1 = trace_change(conn, "Field", 1, "update")
        individual_2 = trace_change(conn, "Field", 2, "update")

        # Same affected records, possibly in different order
        batch_1 = batch_results.get(("Field", 1), [])
        batch_2 = batch_results.get(("Field", 2), [])

        assert len(batch_1) == len(individual_1)
        assert len(batch_2) == len(individual_2)

    def test_fewer_queries_with_batch(self, conn):
        """Verify batch consolidation uses fewer SQL queries."""
        _seed(conn)
        # Add more fields for a realistic batch
        for i in range(4, 9):
            conn.execute(
                "INSERT INTO Field (id, entity_id, name, label, field_type) "
                f"VALUES ({i}, 1, 'field{i}', 'Field {i}', 'varchar')"
            )
            conn.execute(
                "INSERT INTO ProcessField (process_id, field_id, usage) "
                f"VALUES (1, {i}, 'collected')"
            )
        conn.commit()

        field_ids = list(range(1, 9))
        changes = [("Field", fid, "update") for fid in field_ids]

        # Count queries using trace callback
        query_count = {"n": 0}

        def counter(sql):
            if sql.startswith("SELECT"):
                query_count["n"] += 1

        conn.set_trace_callback(counter)
        batch_trace_changes(conn, changes)
        batch_n = query_count["n"]
        conn.set_trace_callback(None)

        # Reset counter for individual
        query_count["n"] = 0
        conn.set_trace_callback(counter)
        for fid in field_ids:
            trace_change(conn, "Field", fid, "update")
        individual_n = query_count["n"]
        conn.set_trace_callback(None)

        # Batch should use fewer queries
        assert batch_n < individual_n, (
            f"Batch used {batch_n} queries, individual used {individual_n}"
        )

    def test_non_field_falls_back(self, conn):
        _seed(conn)
        changes = [("Persona", 1, "update")]
        results = batch_trace_changes(conn, changes)
        individual = trace_change(conn, "Persona", 1, "update")
        assert len(results[("Persona", 1)]) == len(individual)

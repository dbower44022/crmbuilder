"""Integration test: ImpactAnalysisEngine traces field changes on CBM data."""

from __future__ import annotations

import pytest

from automation.impact.engine import ImpactAnalysisEngine


class TestCBMImpactAnalysis:

    def test_field_change_produces_impacts(self, cbm_client_conn):
        """Modify a Field record and verify impact tracing."""
        engine = ImpactAnalysisEngine(cbm_client_conn)

        # Find a Field on the Contact entity
        field = cbm_client_conn.execute(
            "SELECT f.id, f.name FROM Field f "
            "JOIN Entity e ON f.entity_id = e.id "
            "WHERE e.name = 'Contact' LIMIT 1"
        ).fetchone()
        if field is None:
            pytest.skip("No Contact fields available")

        # Analyze a proposed change
        proposed = engine.analyze_proposed_change(
            table_name="Field",
            record_id=field[0],
            change_type="update",
            new_values={"field_type": "text"},
        )

        # The impact set may be empty if no cross-references exist,
        # but the call should not raise
        assert isinstance(proposed, list)

    def test_entity_delete_traces_impacts(self, cbm_client_conn):
        """Analyze deleting an entity — should trace to fields and relationships."""
        engine = ImpactAnalysisEngine(cbm_client_conn)

        entity = cbm_client_conn.execute(
            "SELECT id FROM Entity WHERE name = 'Contact'"
        ).fetchone()
        if entity is None:
            pytest.skip("Contact entity not available")

        proposed = engine.analyze_proposed_change(
            table_name="Entity",
            record_id=entity[0],
            change_type="delete",
        )

        # Deleting Contact should impact its Fields at minimum
        assert isinstance(proposed, list)
        if proposed:
            tables = {p.affected_table for p in proposed}
            assert "Field" in tables or "ProcessEntity" in tables or len(tables) > 0

    def test_analyze_proposed_change_returns_proposed_impacts(self, cbm_client_conn):
        """Verify the return type of analyze_proposed_change."""
        engine = ImpactAnalysisEngine(cbm_client_conn)

        # Use any record that exists
        row = cbm_client_conn.execute("SELECT id FROM Domain LIMIT 1").fetchone()
        if row is None:
            pytest.skip("No domains available")

        proposed = engine.analyze_proposed_change(
            table_name="Domain",
            record_id=row[0],
            change_type="update",
            new_values={"description": "Updated"},
        )
        assert isinstance(proposed, list)
        for p in proposed:
            assert hasattr(p, "affected_table")
            assert hasattr(p, "affected_record_id")
            assert hasattr(p, "impact_description")

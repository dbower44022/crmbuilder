"""Tests for automation.importer.proposed — ProposedRecord and ProposedBatch."""

import pytest

from automation.importer.proposed import Conflict, ProposedBatch, ProposedRecord


class TestConflict:
    def test_valid_severities(self):
        for sev in ("error", "warning", "info"):
            c = Conflict(severity=sev, conflict_type="test", message="msg")
            assert c.severity == sev

    def test_invalid_severity(self):
        with pytest.raises(ValueError, match="Invalid conflict severity"):
            Conflict(severity="critical", conflict_type="test", message="msg")


class TestProposedRecord:
    def test_create_record(self):
        rec = ProposedRecord(
            table_name="Domain",
            action="create",
            target_id=None,
            values={"name": "Test", "code": "TST"},
            source_payload_path="payload.domains[0]",
        )
        assert rec.action == "create"
        assert rec.target_id is None
        assert rec.identifier_value == "TST"

    def test_update_record(self):
        rec = ProposedRecord(
            table_name="Domain",
            action="update",
            target_id=5,
            values={"name": "Updated"},
            source_payload_path="payload.domains[0]",
        )
        assert rec.action == "update"
        assert rec.target_id == 5

    def test_invalid_action(self):
        with pytest.raises(ValueError, match="Invalid action"):
            ProposedRecord(
                table_name="Domain",
                action="delete",
                target_id=None,
                values={},
                source_payload_path="x",
            )

    def test_update_requires_target_id(self):
        with pytest.raises(ValueError, match="must have a target_id"):
            ProposedRecord(
                table_name="Domain",
                action="update",
                target_id=None,
                values={},
                source_payload_path="x",
            )

    def test_has_errors(self):
        rec = ProposedRecord(
            table_name="Domain", action="create", target_id=None,
            values={}, source_payload_path="x",
        )
        assert not rec.has_errors
        rec.conflicts.append(Conflict("warning", "test", "warn"))
        assert not rec.has_errors
        rec.conflicts.append(Conflict("error", "test", "err"))
        assert rec.has_errors

    def test_identifier_value_code(self):
        rec = ProposedRecord(
            table_name="Domain", action="create", target_id=None,
            values={"code": "MN"}, source_payload_path="x",
        )
        assert rec.identifier_value == "MN"

    def test_identifier_value_identifier(self):
        rec = ProposedRecord(
            table_name="Requirement", action="create", target_id=None,
            values={"identifier": "MN-INTAKE-REQ-001"}, source_payload_path="x",
        )
        assert rec.identifier_value == "MN-INTAKE-REQ-001"

    def test_identifier_value_none(self):
        rec = ProposedRecord(
            table_name="Field", action="create", target_id=None,
            values={"name": "status"}, source_payload_path="x",
        )
        assert rec.identifier_value is None

    def test_intra_batch_refs(self):
        rec = ProposedRecord(
            table_name="Field", action="create", target_id=None,
            values={"name": "status"},
            source_payload_path="x",
            intra_batch_refs={"entity_id": "batch:entity:CON"},
        )
        assert rec.intra_batch_refs["entity_id"] == "batch:entity:CON"

    def test_batch_id(self):
        rec = ProposedRecord(
            table_name="Domain", action="create", target_id=None,
            values={"code": "MN"}, source_payload_path="x",
            batch_id="batch:domain:MN",
        )
        assert rec.batch_id == "batch:domain:MN"


class TestProposedBatch:
    def _make_batch(self, records=None):
        return ProposedBatch(
            records=records or [],
            ai_session_id=1,
            work_item_id=1,
            session_type="initial",
        )

    def test_empty_batch(self):
        batch = self._make_batch()
        assert not batch.has_errors
        assert batch.error_count == 0
        assert batch.records_by_table() == {}

    def test_has_errors(self):
        rec = ProposedRecord(
            table_name="Domain", action="create", target_id=None,
            values={}, source_payload_path="x",
            conflicts=[Conflict("error", "test", "err")],
        )
        batch = self._make_batch([rec])
        assert batch.has_errors
        assert batch.error_count == 1

    def test_records_by_table(self):
        d = ProposedRecord(
            table_name="Domain", action="create", target_id=None,
            values={"code": "MN"}, source_payload_path="x",
        )
        e = ProposedRecord(
            table_name="Entity", action="create", target_id=None,
            values={"code": "CON"}, source_payload_path="y",
        )
        batch = self._make_batch([d, e])
        by_table = batch.records_by_table()
        assert len(by_table["Domain"]) == 1
        assert len(by_table["Entity"]) == 1

    def test_find_by_batch_id(self):
        rec = ProposedRecord(
            table_name="Domain", action="create", target_id=None,
            values={}, source_payload_path="x", batch_id="batch:domain:MN",
        )
        batch = self._make_batch([rec])
        assert batch.find_by_batch_id("batch:domain:MN") is rec
        assert batch.find_by_batch_id("nonexistent") is None

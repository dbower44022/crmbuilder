"""Tests for automation.ui.importer.import_logic — pure Python import state machine."""


from automation.importer.proposed import ProposedBatch, ProposedRecord
from automation.ui.importer.import_logic import (
    ImportStage,
    ImportState,
    RecordAction,
    advance_stage,
    compute_accepted_record_ids,
    count_by_action,
    get_cascade_reject_set_from_batch,
    get_records_by_category,
    get_unresolved_errors,
    init_records_from_batch,
    set_category_action,
    set_error,
    set_record_action,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_batch(records=None):
    """Create a ProposedBatch with test records."""
    if records is None:
        records = [
            ProposedRecord(
                table_name="Entity", action="create", target_id=None,
                values={"name": "Contact", "code": "ENT-01"},
                source_payload_path="payload.entities[0]",
            ),
            ProposedRecord(
                table_name="Field", action="create", target_id=None,
                values={"name": "email", "field_type": "varchar"},
                source_payload_path="payload.fields[0]",
            ),
        ]
    return ProposedBatch(
        records=records, ai_session_id=1, work_item_id=1, session_type="initial",
    )


# ---------------------------------------------------------------------------
# State machine transitions
# ---------------------------------------------------------------------------

class TestStateMachine:

    def test_initial_state(self):
        state = ImportState()
        assert state.current_stage == ImportStage.RECEIVE
        assert len(state.completed_stages) == 0

    def test_advance(self):
        state = ImportState()
        state = advance_stage(state, ImportStage.PARSE)
        assert state.current_stage == ImportStage.PARSE
        assert ImportStage.RECEIVE in state.completed_stages

    def test_advance_clears_error(self):
        state = ImportState()
        state = set_error(state, "oops")
        state = advance_stage(state, ImportStage.PARSE)
        assert state.error_message is None

    def test_set_error(self):
        state = ImportState()
        state = set_error(state, "Parse failed")
        assert state.error_message == "Parse failed"
        assert state.current_stage == ImportStage.RECEIVE  # doesn't advance

    def test_full_pipeline(self):
        state = ImportState()
        for stage in [
            ImportStage.PARSE, ImportStage.MAP, ImportStage.DETECT,
            ImportStage.REVIEW, ImportStage.COMMIT, ImportStage.TRIGGER,
            ImportStage.DONE,
        ]:
            state = advance_stage(state, stage)
        assert state.current_stage == ImportStage.DONE
        assert len(state.completed_stages) == 7


# ---------------------------------------------------------------------------
# Record state management
# ---------------------------------------------------------------------------

class TestRecordManagement:

    def test_init_from_batch(self):
        batch = _make_batch()
        state = ImportState()
        state = init_records_from_batch(state, batch)
        assert len(state.records) == 2
        assert "payload.entities[0]" in state.records
        assert "payload.fields[0]" in state.records

    def test_default_action_is_accepted(self):
        batch = _make_batch()
        state = ImportState()
        state = init_records_from_batch(state, batch)
        for rec in state.records.values():
            assert rec.record_action == RecordAction.ACCEPTED

    def test_set_record_rejected(self):
        batch = _make_batch()
        state = ImportState()
        state = init_records_from_batch(state, batch)
        state = set_record_action(state, "payload.entities[0]", RecordAction.REJECTED)
        assert state.records["payload.entities[0]"].record_action == RecordAction.REJECTED

    def test_set_record_modified(self):
        batch = _make_batch()
        state = ImportState()
        state = init_records_from_batch(state, batch)
        state = set_record_action(
            state, "payload.entities[0]", RecordAction.MODIFIED,
            modified_values={"name": "Updated Contact"},
        )
        rec = state.records["payload.entities[0]"]
        assert rec.record_action == RecordAction.MODIFIED
        assert rec.modified_values == {"name": "Updated Contact"}

    def test_set_category_action(self):
        batch = _make_batch()
        state = ImportState()
        state = init_records_from_batch(state, batch)
        state = set_category_action(state, "Entity", RecordAction.REJECTED)
        assert state.records["payload.entities[0]"].record_action == RecordAction.REJECTED
        # Field record should be unchanged
        assert state.records["payload.fields[0]"].record_action == RecordAction.ACCEPTED

    def test_dependency_count(self):
        records = [
            ProposedRecord(
                table_name="Entity", action="create", target_id=None,
                values={"name": "Contact"},
                source_payload_path="payload.entities[0]",
                batch_id="entity-contact",
            ),
            ProposedRecord(
                table_name="Field", action="create", target_id=None,
                values={"name": "email"},
                source_payload_path="payload.fields[0]",
                intra_batch_refs={"entity_id": "payload.entities[0]"},
            ),
        ]
        batch = _make_batch(records)
        state = ImportState()
        state = init_records_from_batch(state, batch)
        # Entity has 1 dependent (Field references it)
        assert state.records["payload.entities[0]"].dependency_count == 1
        assert state.records["payload.fields[0]"].dependency_count == 0


# ---------------------------------------------------------------------------
# Computed properties
# ---------------------------------------------------------------------------

class TestComputedProperties:

    def test_accepted_ids_all_accepted(self):
        batch = _make_batch()
        state = ImportState()
        state = init_records_from_batch(state, batch)
        ids = compute_accepted_record_ids(state)
        assert len(ids) == 2

    def test_accepted_ids_one_rejected(self):
        batch = _make_batch()
        state = ImportState()
        state = init_records_from_batch(state, batch)
        state = set_record_action(state, "payload.entities[0]", RecordAction.REJECTED)
        ids = compute_accepted_record_ids(state)
        assert ids == {"payload.fields[0]"}

    def test_accepted_ids_modified_included(self):
        batch = _make_batch()
        state = ImportState()
        state = init_records_from_batch(state, batch)
        state = set_record_action(
            state, "payload.entities[0]", RecordAction.MODIFIED,
            modified_values={"name": "Updated"},
        )
        ids = compute_accepted_record_ids(state)
        assert len(ids) == 2  # Modified records are accepted

    def test_count_by_action(self):
        batch = _make_batch()
        state = ImportState()
        state = init_records_from_batch(state, batch)
        state = set_record_action(state, "payload.entities[0]", RecordAction.REJECTED)
        counts = count_by_action(state)
        assert counts["accepted"] == 1
        assert counts["rejected"] == 1
        assert counts["modified"] == 0


class TestUnresolvedErrors:

    def test_no_errors(self):
        batch = _make_batch()
        state = ImportState()
        state = init_records_from_batch(state, batch)
        assert get_unresolved_errors(state) == []

    def test_error_accepted_is_unresolved(self):
        records = [
            ProposedRecord(
                table_name="Entity", action="create", target_id=None,
                values={"name": "Contact"},
                source_payload_path="payload.entities[0]",
                conflicts=[],
            ),
        ]
        batch = _make_batch(records)
        state = ImportState()
        state = init_records_from_batch(state, batch)
        # Manually set has_errors
        state.records["payload.entities[0]"].has_errors = True
        errors = get_unresolved_errors(state)
        assert errors == ["payload.entities[0]"]

    def test_error_rejected_is_resolved(self):
        batch = _make_batch()
        state = ImportState()
        state = init_records_from_batch(state, batch)
        state.records["payload.entities[0]"].has_errors = True
        state = set_record_action(state, "payload.entities[0]", RecordAction.REJECTED)
        assert get_unresolved_errors(state) == []


class TestCascadeReject:

    def test_finds_dependents(self):
        records = [
            ProposedRecord(
                table_name="Entity", action="create", target_id=None,
                values={"name": "Contact"},
                source_payload_path="payload.entities[0]",
                batch_id="entity-contact",
            ),
            ProposedRecord(
                table_name="Field", action="create", target_id=None,
                values={"name": "email"},
                source_payload_path="payload.fields[0]",
                intra_batch_refs={"entity_id": "payload.entities[0]"},
            ),
            ProposedRecord(
                table_name="Field", action="create", target_id=None,
                values={"name": "phone"},
                source_payload_path="payload.fields[1]",
                intra_batch_refs={"entity_id": "payload.entities[0]"},
            ),
        ]
        batch = _make_batch(records)
        deps = get_cascade_reject_set_from_batch(batch, "payload.entities[0]")
        assert set(deps) == {"payload.fields[0]", "payload.fields[1]"}

    def test_no_dependents(self):
        batch = _make_batch()
        deps = get_cascade_reject_set_from_batch(batch, "payload.entities[0]")
        assert deps == []


class TestCategoryGrouping:

    def test_ordered_by_category(self):
        records = [
            ProposedRecord(
                table_name="Field", action="create", target_id=None,
                values={"name": "email"},
                source_payload_path="payload.fields[0]",
            ),
            ProposedRecord(
                table_name="Entity", action="create", target_id=None,
                values={"name": "Contact"},
                source_payload_path="payload.entities[0]",
            ),
            ProposedRecord(
                table_name="Decision", action="create", target_id=None,
                values={"title": "DEC-001"},
                source_payload_path="payload.decisions[0]",
            ),
        ]
        batch = _make_batch(records)
        state = ImportState()
        state = init_records_from_batch(state, batch)
        groups = get_records_by_category(state)
        table_names = [g[0] for g in groups]
        # Entity should come before Field, Field before Decision
        assert table_names.index("Entity") < table_names.index("Field")
        assert table_names.index("Field") < table_names.index("Decision")

    def test_omits_empty_categories(self):
        batch = _make_batch()
        state = ImportState()
        state = init_records_from_batch(state, batch)
        groups = get_records_by_category(state)
        table_names = [g[0] for g in groups]
        assert "Domain" not in table_names  # No Domain records in batch

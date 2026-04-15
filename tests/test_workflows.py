"""Tests for workflow parsing, validation, and manager CHECK->ACT."""

from textwrap import dedent
from unittest.mock import MagicMock

import pytest

from espo_impl.core.config_loader import ConfigLoader
from espo_impl.core.models import (
    EntityDefinition,
    FieldDefinition,
    ProgramFile,
    Workflow,
    WorkflowAction,
    WorkflowStatus,
    WorkflowTrigger,
)
from espo_impl.core.workflow_manager import (
    WorkflowManager,
    WorkflowManagerError,
)


@pytest.fixture
def loader():
    return ConfigLoader()


# ---------------------------------------------------------------------------
# Helper: write YAML with a workflows block under Contact entity
# ---------------------------------------------------------------------------

_YAML_PREFIX = """\
version: "1.1"
description: "Workflow test"

entities:
  Contact:
    fields:
      - name: status
        type: enum
        label: "Status"
        options:
          - Active
          - Inactive
          - Pending
      - name: email
        type: email
        label: "Email"
      - name: lastContactedAt
        type: datetime
        label: "Last Contacted At"
"""


def _write_yaml(tmp_path, workflows_yaml: str):
    """Write a complete YAML file with the given workflows block.

    The workflows_yaml argument should be a dedented string starting at
    column 0; this helper indents it under the Contact entity.
    """
    # Indent each line by 4 spaces (entity child level)
    indented = "\n".join(
        "    " + line if line.strip() else ""
        for line in workflows_yaml.splitlines()
    )
    content = _YAML_PREFIX + indented + "\n"
    path = tmp_path / "test.yaml"
    path.write_text(content)
    return path


# ===================================================================
# Parsing tests -- trigger events
# ===================================================================

class TestWorkflowTriggerParsing:
    """Verify all 5 trigger events parse correctly."""

    def test_on_create_trigger(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-create
                name: "On Create"
                trigger:
                  event: onCreate
                actions:
                  - type: setField
                    field: status
                    value: Active
        """))
        program = loader.load_program(path)
        wf = program.entities[0].workflows[0]
        assert wf.trigger.event == "onCreate"
        assert wf.trigger.field is None

    def test_on_update_trigger(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-update
                name: "On Update"
                trigger:
                  event: onUpdate
                actions:
                  - type: setField
                    field: lastContactedAt
                    value: now
        """))
        program = loader.load_program(path)
        wf = program.entities[0].workflows[0]
        assert wf.trigger.event == "onUpdate"

    def test_on_field_change_trigger(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-fc
                name: "On Field Change"
                trigger:
                  event: onFieldChange
                  field: status
                  to: Active
                actions:
                  - type: setField
                    field: lastContactedAt
                    value: now
        """))
        program = loader.load_program(path)
        wf = program.entities[0].workflows[0]
        assert wf.trigger.event == "onFieldChange"
        assert wf.trigger.field == "status"
        assert wf.trigger.to_values == "Active"

    def test_on_field_transition_trigger(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-ft
                name: "On Field Transition"
                trigger:
                  event: onFieldTransition
                  field: status
                  from: Pending
                  to:
                    - Active
                    - Inactive
                actions:
                  - type: clearField
                    field: lastContactedAt
        """))
        program = loader.load_program(path)
        wf = program.entities[0].workflows[0]
        assert wf.trigger.event == "onFieldTransition"
        assert wf.trigger.field == "status"
        assert wf.trigger.from_values == "Pending"
        assert wf.trigger.to_values == ["Active", "Inactive"]

    def test_on_delete_trigger(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-del
                name: "On Delete"
                trigger:
                  event: onDelete
                actions:
                  - type: clearField
                    field: status
        """))
        program = loader.load_program(path)
        wf = program.entities[0].workflows[0]
        assert wf.trigger.event == "onDelete"


# ===================================================================
# Parsing tests -- action types
# ===================================================================

class TestWorkflowActionParsing:
    """Verify all 4 action types parse correctly."""

    def test_set_field_action(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-sf
                name: "Set Field"
                trigger:
                  event: onCreate
                actions:
                  - type: setField
                    field: status
                    value: Active
        """))
        program = loader.load_program(path)
        action = program.entities[0].workflows[0].actions[0]
        assert action.type == "setField"
        assert action.field == "status"
        assert action.value == "Active"

    def test_clear_field_action(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-cf
                name: "Clear Field"
                trigger:
                  event: onCreate
                actions:
                  - type: clearField
                    field: lastContactedAt
        """))
        program = loader.load_program(path)
        action = program.entities[0].workflows[0].actions[0]
        assert action.type == "clearField"
        assert action.field == "lastContactedAt"

    def test_send_email_action(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-se
                name: "Send Email"
                trigger:
                  event: onCreate
                actions:
                  - type: sendEmail
                    template: tmpl-welcome
                    to: email
        """))
        program = loader.load_program(path)
        action = program.entities[0].workflows[0].actions[0]
        assert action.type == "sendEmail"
        assert action.template == "tmpl-welcome"
        assert action.to == "email"

    def test_send_internal_notification_action(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-sin
                name: "Send Notification"
                trigger:
                  event: onCreate
                actions:
                  - type: sendInternalNotification
                    template: tmpl-notify
                    to: "role:admin"
        """))
        program = loader.load_program(path)
        action = program.entities[0].workflows[0].actions[0]
        assert action.type == "sendInternalNotification"
        assert action.template == "tmpl-notify"
        assert action.to == "role:admin"


# ===================================================================
# Parsing tests -- where clause
# ===================================================================

class TestWorkflowWhereParsing:
    """Verify where clause parses through condition_expression."""

    def test_where_clause_parsed(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-where
                name: "With Where"
                trigger:
                  event: onCreate
                where:
                  field: status
                  op: "="
                  value: Active
                actions:
                  - type: setField
                    field: lastContactedAt
                    value: now
        """))
        program = loader.load_program(path)
        wf = program.entities[0].workflows[0]
        assert wf.where is not None
        assert wf.where_raw is not None


# ===================================================================
# Validation error tests
# ===================================================================

class TestWorkflowValidation:
    """Test validation error detection."""

    def test_missing_id(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - name: "No ID"
                trigger:
                  event: onCreate
                actions:
                  - type: setField
                    field: status
                    value: Active
        """))
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("missing required property 'id'" in e for e in errors)

    def test_duplicate_id(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-dup
                name: "First"
                trigger:
                  event: onCreate
                actions:
                  - type: setField
                    field: status
                    value: Active
              - id: wf-dup
                name: "Second"
                trigger:
                  event: onUpdate
                actions:
                  - type: setField
                    field: status
                    value: Active
        """))
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("duplicate id" in e for e in errors)

    def test_missing_name(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-noname
                trigger:
                  event: onCreate
                actions:
                  - type: setField
                    field: status
                    value: Active
        """))
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("missing required property 'name'" in e for e in errors)

    def test_missing_trigger(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-notrig
                name: "No Trigger"
                actions:
                  - type: setField
                    field: status
                    value: Active
        """))
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("missing required property 'trigger'" in e for e in errors)

    def test_empty_actions(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-noact
                name: "No Actions"
                trigger:
                  event: onCreate
                actions: []
        """))
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("non-empty list" in e for e in errors)

    def test_invalid_trigger_event(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-bad
                name: "Bad Event"
                trigger:
                  event: onFoo
                actions:
                  - type: setField
                    field: status
                    value: Active
        """))
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("invalid event" in e for e in errors)

    def test_on_field_change_missing_field(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-fc-nf
                name: "FC No Field"
                trigger:
                  event: onFieldChange
                actions:
                  - type: setField
                    field: status
                    value: Active
        """))
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any(
            "'field' is required for onFieldChange" in e for e in errors
        )

    def test_on_field_change_bad_field(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-fc-bf
                name: "FC Bad Field"
                trigger:
                  event: onFieldChange
                  field: nonExistent
                actions:
                  - type: setField
                    field: status
                    value: Active
        """))
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("not found on entity" in e for e in errors)

    def test_on_field_transition_no_from_to(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-ft-nft
                name: "FT No From/To"
                trigger:
                  event: onFieldTransition
                  field: status
                actions:
                  - type: setField
                    field: status
                    value: Active
        """))
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("requires 'from' and/or 'to'" in e for e in errors)

    def test_invalid_action_type(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-badact
                name: "Bad Action"
                trigger:
                  event: onCreate
                actions:
                  - type: doSomething
        """))
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("invalid action type" in e for e in errors)

    def test_set_field_missing_field(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-sf-nf
                name: "SF No Field"
                trigger:
                  event: onCreate
                actions:
                  - type: setField
                    value: Active
        """))
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any(
            "'field' is required for setField" in e for e in errors
        )

    def test_set_field_bad_field(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-sf-bf
                name: "SF Bad Field"
                trigger:
                  event: onCreate
                actions:
                  - type: setField
                    field: nonExistent
                    value: Active
        """))
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("not found on entity" in e for e in errors)

    def test_set_field_missing_value(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-sf-nv
                name: "SF No Value"
                trigger:
                  event: onCreate
                actions:
                  - type: setField
                    field: status
        """))
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any(
            "'value' is required for setField" in e for e in errors
        )

    def test_send_email_missing_template(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-se-nt
                name: "SE No Template"
                trigger:
                  event: onCreate
                actions:
                  - type: sendEmail
                    to: email
        """))
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any(
            "'template' is required for sendEmail" in e for e in errors
        )

    def test_send_email_missing_to(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-se-nto
                name: "SE No To"
                trigger:
                  event: onCreate
                actions:
                  - type: sendEmail
                    template: tmpl-x
        """))
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any(
            "'to' is required for sendEmail" in e for e in errors
        )

    def test_send_email_to_literal_email(self, loader, tmp_path):
        """Literal email in 'to' should pass validation."""
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-se-lit
                name: "SE Literal Email"
                trigger:
                  event: onCreate
                actions:
                  - type: sendEmail
                    template: tmpl-x
                    to: "admin@example.com"
        """))
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        # No error about 'to' (template cross-block check may fire)
        assert not any("'to' value" in e for e in errors)

    def test_send_email_to_bad_field(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-se-bf
                name: "SE Bad To"
                trigger:
                  event: onCreate
                actions:
                  - type: sendEmail
                    template: tmpl-x
                    to: nonExistent
        """))
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any("neither an email address nor a field" in e for e in errors)

    def test_send_internal_notification_bad_to(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-sin-bt
                name: "SIN Bad To"
                trigger:
                  event: onCreate
                actions:
                  - type: sendInternalNotification
                    template: tmpl-x
                    to: badValue
        """))
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any(
            "must be an email, 'role:<id>', or 'user:<id>'" in e
            for e in errors
        )

    def test_send_internal_notification_role_ok(self, loader, tmp_path):
        """role:admin should pass validation."""
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-sin-role
                name: "SIN Role"
                trigger:
                  event: onCreate
                actions:
                  - type: sendInternalNotification
                    template: tmpl-x
                    to: "role:admin"
        """))
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert not any("'to' value" in e for e in errors)

    def test_send_internal_notification_user_ok(self, loader, tmp_path):
        """user:1234 should pass validation."""
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-sin-user
                name: "SIN User"
                trigger:
                  event: onCreate
                actions:
                  - type: sendInternalNotification
                    template: tmpl-x
                    to: "user:1234"
        """))
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert not any("'to' value" in e for e in errors)


# ===================================================================
# Cross-block template check
# ===================================================================

class TestWorkflowTemplateCrossBlock:
    """Test cross-block sendEmail.template reference validation."""

    def test_missing_template_ref(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-xref
                name: "Cross Ref"
                trigger:
                  event: onCreate
                actions:
                  - type: sendEmail
                    template: tmpl-nonexistent
                    to: email
        """))
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert any(
            "sendEmail template 'tmpl-nonexistent' does not match"
            in e for e in errors
        )


# ===================================================================
# Valid workflow -- no errors
# ===================================================================

class TestWorkflowValidProgram:
    """Verify a fully valid workflow produces no validation errors."""

    def test_valid_workflow(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-valid
                name: "Valid Workflow"
                trigger:
                  event: onCreate
                actions:
                  - type: setField
                    field: status
                    value: Active
                  - type: setField
                    field: lastContactedAt
                    value: now
        """))
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert errors == []

    def test_set_field_with_now_value(self, loader, tmp_path):
        path = _write_yaml(tmp_path, dedent("""\
            workflows:
              - id: wf-now
                name: "Set Now"
                trigger:
                  event: onUpdate
                actions:
                  - type: setField
                    field: lastContactedAt
                    value: now
        """))
        program = loader.load_program(path)
        errors = loader.validate_program(program)
        assert errors == []


# ===================================================================
# Manager CHECK->ACT tests
# ===================================================================

class TestWorkflowManager:
    """Test WorkflowManager CHECK->ACT operations."""

    def _make_program(self, workflows):
        """Build a ProgramFile with Contact entity and workflows."""
        entity = EntityDefinition(
            name="Contact",
            fields=[
                FieldDefinition(name="status", type="enum", label="Status"),
                FieldDefinition(name="email", type="email", label="Email"),
            ],
            workflows=workflows,
        )
        return ProgramFile(
            version="1.1",
            description="Test",
            entities=[entity],
        )

    def test_create_new_workflow(self):
        """New workflow should be created when not on CRM."""
        wf = Workflow(
            id="wf-1",
            name="Test Workflow",
            trigger=WorkflowTrigger(event="onCreate"),
            actions=[
                WorkflowAction(type="setField", field="status", value="Active"),
            ],
        )
        program = self._make_program([wf])

        client = MagicMock()
        client.get_client_defs.return_value = (200, {})
        client.put_metadata.return_value = (200, {})

        output = []
        mgr = WorkflowManager(client, lambda msg, color: output.append(msg))
        results = mgr.process_workflows(program)

        assert len(results) == 1
        assert results[0].status == WorkflowStatus.CREATED
        client.put_metadata.assert_called_once()

    def test_skip_matching_workflow(self):
        """Matching workflow should be skipped."""
        wf = Workflow(
            id="wf-1",
            name="Test Workflow",
            trigger=WorkflowTrigger(event="onCreate"),
            actions=[
                WorkflowAction(type="setField", field="status", value="Active"),
            ],
        )
        program = self._make_program([wf])

        existing = {
            "workflows": [
                {
                    "id": "wf-1",
                    "name": "Test Workflow",
                    "trigger": {"event": "onCreate"},
                    "actions": [
                        {"type": "setField", "field": "status", "value": "Active"},
                    ],
                }
            ]
        }

        client = MagicMock()
        client.get_client_defs.return_value = (200, existing)

        output = []
        mgr = WorkflowManager(client, lambda msg, color: output.append(msg))
        results = mgr.process_workflows(program)

        assert len(results) == 1
        assert results[0].status == WorkflowStatus.SKIPPED
        client.put_metadata.assert_not_called()

    def test_update_differing_workflow(self):
        """Differing workflow should be updated."""
        wf = Workflow(
            id="wf-1",
            name="Updated Workflow",
            trigger=WorkflowTrigger(event="onCreate"),
            actions=[
                WorkflowAction(type="setField", field="status", value="Active"),
            ],
        )
        program = self._make_program([wf])

        existing = {
            "workflows": [
                {
                    "id": "wf-1",
                    "name": "Old Workflow",
                    "trigger": {"event": "onCreate"},
                    "actions": [
                        {"type": "setField", "field": "status", "value": "Pending"},
                    ],
                }
            ]
        }

        client = MagicMock()
        client.get_client_defs.return_value = (200, existing)
        client.put_metadata.return_value = (200, {})

        output = []
        mgr = WorkflowManager(client, lambda msg, color: output.append(msg))
        results = mgr.process_workflows(program)

        assert len(results) == 1
        assert results[0].status == WorkflowStatus.UPDATED
        client.put_metadata.assert_called_once()

    def test_drift_detection(self):
        """CRM-side workflow not in YAML should be reported as drift."""
        wf = Workflow(
            id="wf-1",
            name="Test",
            trigger=WorkflowTrigger(event="onCreate"),
            actions=[
                WorkflowAction(type="setField", field="status", value="Active"),
            ],
        )
        program = self._make_program([wf])

        existing = {
            "workflows": [
                {
                    "id": "wf-1",
                    "name": "Test",
                    "trigger": {"event": "onCreate"},
                    "actions": [
                        {"type": "setField", "field": "status", "value": "Active"},
                    ],
                },
                {
                    "id": "wf-orphan",
                    "name": "Orphan",
                    "trigger": {"event": "onDelete"},
                    "actions": [],
                },
            ]
        }

        client = MagicMock()
        client.get_client_defs.return_value = (200, existing)

        output = []
        mgr = WorkflowManager(client, lambda msg, color: output.append(msg))
        results = mgr.process_workflows(program)

        assert len(results) == 2
        drift_results = [r for r in results if r.status == WorkflowStatus.DRIFT]
        assert len(drift_results) == 1
        assert drift_results[0].workflow_id == "wf-orphan"

    def test_auth_failure_raises(self):
        """HTTP 401 should raise WorkflowManagerError."""
        wf = Workflow(
            id="wf-1",
            name="Test",
            trigger=WorkflowTrigger(event="onCreate"),
            actions=[
                WorkflowAction(type="setField", field="status", value="Active"),
            ],
        )
        program = self._make_program([wf])

        client = MagicMock()
        client.get_client_defs.return_value = (401, None)

        output = []
        mgr = WorkflowManager(client, lambda msg, color: output.append(msg))

        with pytest.raises(WorkflowManagerError):
            mgr.process_workflows(program)

    def test_connection_error(self):
        """Negative status code should produce ERROR results."""
        wf = Workflow(
            id="wf-1",
            name="Test",
            trigger=WorkflowTrigger(event="onCreate"),
            actions=[
                WorkflowAction(type="setField", field="status", value="Active"),
            ],
        )
        program = self._make_program([wf])

        client = MagicMock()
        client.get_client_defs.return_value = (-1, None)

        output = []
        mgr = WorkflowManager(client, lambda msg, color: output.append(msg))
        results = mgr.process_workflows(program)

        assert len(results) == 1
        assert results[0].status == WorkflowStatus.ERROR
        assert results[0].error == "Connection error"

    def test_write_failure_marks_error(self):
        """Failed metadata write should mark created/updated as error."""
        wf = Workflow(
            id="wf-1",
            name="Test",
            trigger=WorkflowTrigger(event="onCreate"),
            actions=[
                WorkflowAction(type="setField", field="status", value="Active"),
            ],
        )
        program = self._make_program([wf])

        client = MagicMock()
        client.get_client_defs.return_value = (200, {})
        client.put_metadata.return_value = (500, None)

        output = []
        mgr = WorkflowManager(client, lambda msg, color: output.append(msg))
        results = mgr.process_workflows(program)

        assert len(results) == 1
        assert results[0].status == WorkflowStatus.ERROR
        assert results[0].error == "Failed to write metadata"

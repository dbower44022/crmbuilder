"""Tests for run worker orchestration with skip_deletes behavior.

These test the _run_full logic directly by mocking the API client,
without requiring a Qt event loop.
"""

from unittest.mock import MagicMock

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.comparator import FieldComparator
from espo_impl.core.field_manager import FieldManager
from espo_impl.core.models import (
    EntityAction,
    EntityDefinition,
    FieldDefinition,
    InstanceProfile,
    ProgramFile,
)
from espo_impl.workers.run_worker import RunWorker


def make_program(entities=None) -> ProgramFile:
    if entities is None:
        entities = []
    return ProgramFile(
        version="1.0",
        description="Test",
        entities=entities,
    )


def make_entity(
    name="TestEntity",
    action=EntityAction.DELETE_AND_CREATE,
    fields=None,
    **kwargs,
) -> EntityDefinition:
    defaults = {
        "type": "Base",
        "labelSingular": name,
        "labelPlural": f"{name}s",
    }
    defaults.update(kwargs)
    if fields is None:
        fields = [FieldDefinition(name="testField", type="varchar", label="Test")]
    return EntityDefinition(name=name, action=action, fields=fields, **defaults)


def run_worker_sync(program, skip_deletes=False, client=None):
    """Run the worker's _run_full synchronously with a mock client.

    :returns: Tuple of (client, output_log, report_or_none, error_or_none).
    """
    if client is None:
        client = MagicMock(spec=EspoAdminClient)
        client.profile = MagicMock(spec=InstanceProfile)
        client.profile.name = "Test"
        client.profile.url = "https://test.com"
        client.profile.api_url = "https://test.com/api/v1"
        client.check_entity_exists.return_value = (200, True)
        client.remove_entity.return_value = (200, {})
        client.create_entity.return_value = (200, {})
        client.rebuild.return_value = (200, {})
        client.get_field.return_value = (200, {"type": "varchar", "label": "Test"})

    output_log: list[tuple[str, str]] = []

    comparator = FieldComparator()
    field_mgr = FieldManager(
        client, comparator, lambda m, c: output_log.append((m, c))
    )

    worker = RunWorker.__new__(RunWorker)
    worker.profile = client.profile
    worker.program = program
    worker.operation = "run"
    worker.skip_deletes = skip_deletes
    worker.output_line = MagicMock()
    worker.output_line.emit = lambda m, c: output_log.append((m, c))
    worker.finished_ok = MagicMock()
    worker.finished_error = MagicMock()

    worker._run_full(client, field_mgr)

    report = None
    error = None
    if worker.finished_ok.emit.called:
        report = worker.finished_ok.emit.call_args[0][0]
    if worker.finished_error.emit.called:
        error = worker.finished_error.emit.call_args[0][0]

    return client, output_log, report, error


def test_full_rebuild_deletes_and_creates():
    """Full rebuild mode: deletes entities, rebuilds, creates, rebuilds."""
    client = MagicMock(spec=EspoAdminClient)
    client.profile = MagicMock(spec=InstanceProfile)
    client.profile.name = "Test"
    client.profile.url = "https://test.com"
    client.profile.api_url = "https://test.com/api/v1"
    # Delete check: exists. Create check: doesn't exist (just deleted).
    client.check_entity_exists.side_effect = [
        (200, True),   # delete check
        (200, False),  # create check
    ]
    client.remove_entity.return_value = (200, {})
    client.create_entity.return_value = (200, {})
    client.rebuild.return_value = (200, {})
    client.get_field.return_value = (200, {"type": "varchar", "label": "Test"})

    program = make_program([
        make_entity("Engagement", EntityAction.DELETE_AND_CREATE),
    ])

    client, output_log, report, error = run_worker_sync(
        program, skip_deletes=False, client=client
    )

    assert error is None
    client.remove_entity.assert_called_once()
    client.create_entity.assert_called_once()
    assert client.rebuild.call_count == 2
    messages = [m for m, _ in output_log]
    assert any("ENTITY DELETIONS" in m for m in messages)
    assert any("ENTITY CREATION" in m for m in messages)


def test_skip_deletes_no_delete_calls():
    """Skip deletes mode: no delete API calls, entities created if not exist."""
    client = MagicMock(spec=EspoAdminClient)
    client.profile = MagicMock(spec=InstanceProfile)
    client.profile.name = "Test"
    client.profile.url = "https://test.com"
    client.profile.api_url = "https://test.com/api/v1"
    # In skip mode, only create check happens — entity doesn't exist
    client.check_entity_exists.return_value = (200, False)
    client.create_entity.return_value = (200, {})
    client.rebuild.return_value = (200, {})
    client.get_field.return_value = (200, {"type": "varchar", "label": "Test"})

    program = make_program([
        make_entity("Engagement", EntityAction.DELETE_AND_CREATE),
    ])

    client, output_log, report, error = run_worker_sync(
        program, skip_deletes=True, client=client
    )

    assert error is None
    client.remove_entity.assert_not_called()
    client.create_entity.assert_called_once()
    assert client.rebuild.call_count == 1
    messages = [m for m, _ in output_log]
    assert any("field-update mode" in m for m in messages)
    assert not any("ENTITY DELETIONS" in m for m in messages)


def test_skip_deletes_with_pure_delete_entity():
    """Skip deletes mode: action=delete entities are fully skipped."""
    client = MagicMock(spec=EspoAdminClient)
    client.profile = MagicMock(spec=InstanceProfile)
    client.profile.name = "Test"
    client.profile.url = "https://test.com"
    client.profile.api_url = "https://test.com/api/v1"
    client.check_entity_exists.return_value = (200, False)
    client.create_entity.return_value = (200, {})
    client.rebuild.return_value = (200, {})
    client.get_field.return_value = (200, {"type": "varchar", "label": "Test"})

    program = make_program([
        make_entity("OldEntity", EntityAction.DELETE, fields=[]),
        make_entity("Engagement", EntityAction.DELETE_AND_CREATE),
    ])

    client, output_log, report, error = run_worker_sync(
        program, skip_deletes=True, client=client
    )

    assert error is None
    client.remove_entity.assert_not_called()
    # Only delete_and_create entity gets created, not the pure delete one
    client.create_entity.assert_called_once()


def test_skip_deletes_existing_entity_skips_create():
    """Skip deletes: if entity already exists, create is skipped."""
    program = make_program([
        make_entity("Engagement", EntityAction.DELETE_AND_CREATE),
    ])

    # Default mock: check_entity_exists returns (200, True)
    client, output_log, report, error = run_worker_sync(
        program, skip_deletes=True
    )

    assert error is None
    messages = [m for m, _ in output_log]
    assert any("ALREADY EXISTS" in m for m in messages)


def test_full_rebuild_field_operations_proceed():
    """Full rebuild: field operations run after entity operations."""
    client = MagicMock(spec=EspoAdminClient)
    client.profile = MagicMock(spec=InstanceProfile)
    client.profile.name = "Test"
    client.profile.url = "https://test.com"
    client.profile.api_url = "https://test.com/api/v1"
    client.check_entity_exists.side_effect = [
        (200, True),   # delete check
        (200, False),  # create check
    ]
    client.remove_entity.return_value = (200, {})
    client.create_entity.return_value = (200, {})
    client.rebuild.return_value = (200, {})
    client.get_field.return_value = (200, {"type": "varchar", "label": "Test"})

    program = make_program([
        make_entity("Engagement", EntityAction.DELETE_AND_CREATE),
    ])

    client, output_log, report, error = run_worker_sync(
        program, skip_deletes=False, client=client
    )

    assert error is None
    assert report is not None
    messages = [m for m, _ in output_log]
    assert any("FIELD OPERATIONS" in m for m in messages)

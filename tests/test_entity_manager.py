"""Tests for the entity manager orchestration logic."""

from unittest.mock import MagicMock

import pytest

from espo_impl.core.entity_manager import EntityManager, EntityManagerError
from espo_impl.core.models import EntityAction, EntityDefinition


def make_entity(
    name="TestEntity",
    action=EntityAction.CREATE,
    **kwargs,
) -> EntityDefinition:
    defaults = {
        "fields": [],
        "type": "Base",
        "labelSingular": name,
        "labelPlural": f"{name}s",
    }
    defaults.update(kwargs)
    return EntityDefinition(name=name, action=action, **defaults)


def make_manager(client=None) -> tuple[EntityManager, list]:
    if client is None:
        client = MagicMock()
    output_log: list[tuple[str, str]] = []

    def output_fn(msg, color):
        output_log.append((msg, color))

    manager = EntityManager(client, output_fn)
    return manager, output_log


def test_create_entity_success():
    client = MagicMock()
    client.check_entity_exists.return_value = (200, False)
    client.create_entity.return_value = (200, {})

    manager, output_log = make_manager(client)
    entity = make_entity("Engagement", EntityAction.CREATE)
    result = manager.process_entity(entity)

    assert result is True
    client.create_entity.assert_called_once()
    payload = client.create_entity.call_args[0][0]
    assert payload["name"] == "Engagement"
    assert payload["type"] == "Base"


def test_create_entity_already_exists_skips():
    client = MagicMock()
    client.check_entity_exists.return_value = (200, True)

    manager, output_log = make_manager(client)
    entity = make_entity("Engagement", EntityAction.CREATE)
    result = manager.process_entity(entity)

    assert result is True
    client.create_entity.assert_not_called()
    messages = [msg for msg, _ in output_log]
    assert any("ALREADY EXISTS" in msg for msg in messages)


def test_create_entity_api_error():
    client = MagicMock()
    client.check_entity_exists.return_value = (200, False)
    client.create_entity.return_value = (500, {"message": "Internal error"})

    manager, output_log = make_manager(client)
    entity = make_entity("Engagement", EntityAction.CREATE)
    result = manager.process_entity(entity)

    assert result is False
    messages = [msg for msg, _ in output_log]
    assert any("ERROR" in msg for msg in messages)


def test_delete_entity_success():
    client = MagicMock()
    client.check_entity_exists.return_value = (200, True)
    client.remove_entity.return_value = (200, {})

    manager, output_log = make_manager(client)
    entity = make_entity("Engagement", EntityAction.DELETE)
    result = manager.process_entity(entity)

    assert result is True
    client.remove_entity.assert_called_once_with("CEngagement")


def test_delete_entity_not_found_skips():
    client = MagicMock()
    client.check_entity_exists.return_value = (200, False)

    manager, output_log = make_manager(client)
    entity = make_entity("Engagement", EntityAction.DELETE)
    result = manager.process_entity(entity)

    assert result is True
    client.remove_entity.assert_not_called()
    messages = [msg for msg, _ in output_log]
    assert any("NOT FOUND" in msg for msg in messages)


def test_delete_entity_api_error():
    client = MagicMock()
    client.check_entity_exists.return_value = (200, True)
    client.remove_entity.return_value = (500, {"message": "Server error"})

    manager, output_log = make_manager(client)
    entity = make_entity("Engagement", EntityAction.DELETE)
    result = manager.process_entity(entity)

    assert result is False


def test_delete_and_create():
    client = MagicMock()
    # Delete phase: entity exists, delete succeeds
    # Create phase: entity doesn't exist (just deleted), create succeeds
    client.check_entity_exists.side_effect = [
        (200, True),   # delete check
        (200, False),  # create check
    ]
    client.remove_entity.return_value = (200, {})
    client.create_entity.return_value = (200, {})

    manager, output_log = make_manager(client)
    entity = make_entity("Engagement", EntityAction.DELETE_AND_CREATE)
    result = manager.process_entity(entity)

    assert result is True
    client.remove_entity.assert_called_once_with("CEngagement")
    client.create_entity.assert_called_once()


def test_delete_and_create_delete_fails_aborts():
    client = MagicMock()
    client.check_entity_exists.return_value = (200, True)
    client.remove_entity.return_value = (500, {"message": "Error"})

    manager, output_log = make_manager(client)
    entity = make_entity("Engagement", EntityAction.DELETE_AND_CREATE)
    result = manager.process_entity(entity)

    assert result is False
    client.create_entity.assert_not_called()


def test_401_raises_error_on_check():
    client = MagicMock()
    client.check_entity_exists.return_value = (401, False)

    manager, output_log = make_manager(client)
    entity = make_entity("Engagement", EntityAction.CREATE)

    with pytest.raises(EntityManagerError):
        manager.process_entity(entity)


def test_401_raises_error_on_create():
    client = MagicMock()
    client.check_entity_exists.return_value = (200, False)
    client.create_entity.return_value = (401, None)

    manager, output_log = make_manager(client)
    entity = make_entity("Engagement", EntityAction.CREATE)

    with pytest.raises(EntityManagerError):
        manager.process_entity(entity)


def test_rebuild_cache_success():
    client = MagicMock()
    client.rebuild.return_value = (200, {})

    manager, output_log = make_manager(client)
    result = manager.rebuild_cache()

    assert result is True
    messages = [msg for msg, _ in output_log]
    assert any("rebuild complete" in msg for msg in messages)


def test_rebuild_cache_failure():
    client = MagicMock()
    client.rebuild.return_value = (500, {"message": "Error"})

    manager, output_log = make_manager(client)
    result = manager.rebuild_cache()

    assert result is False


def test_native_entity_name_passthrough():
    """Native entities like Contact use the name as-is for check."""
    client = MagicMock()
    client.check_entity_exists.return_value = (200, True)
    client.remove_entity.return_value = (200, {})

    manager, output_log = make_manager(client)
    entity = make_entity("Contact", EntityAction.DELETE)
    manager.process_entity(entity)

    # Contact is a native entity — should check with "Contact" not "CContact"
    client.check_entity_exists.assert_called_once_with("Contact")


def test_entity_name_mapping():
    """Custom entities use the C-prefixed name from the mapping."""
    client = MagicMock()
    client.check_entity_exists.return_value = (200, True)
    client.remove_entity.return_value = (200, {})

    manager, output_log = make_manager(client)
    entity = make_entity("Session", EntityAction.DELETE)
    manager.process_entity(entity)

    # Session maps to CSessions per the mapping table
    client.check_entity_exists.assert_called_once_with("CSessions")
    client.remove_entity.assert_called_once_with("CSessions")

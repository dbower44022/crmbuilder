"""Tests for the tooltip manager orchestration logic."""

from unittest.mock import MagicMock

import pytest

from espo_impl.core.models import (
    EntityDefinition,
    FieldDefinition,
    TooltipStatus,
)
from espo_impl.core.tooltip_manager import TooltipManager, TooltipManagerError


def make_entity(fields=None) -> EntityDefinition:
    if fields is None:
        fields = [
            FieldDefinition(
                name="mentorStatus", type="enum", label="Mentor Status",
                tooltip="Current lifecycle stage.",
                options=["Active", "Inactive"],
            ),
        ]
    return EntityDefinition(name="Contact", fields=fields)


def make_manager(client=None) -> tuple[TooltipManager, list]:
    if client is None:
        client = MagicMock()
    output_log: list[tuple[str, str]] = []
    manager = TooltipManager(client, lambda msg, color: output_log.append((msg, color)))
    return manager, output_log


def test_field_with_no_tooltip_skipped():
    manager, log = make_manager()
    entity = make_entity([
        FieldDefinition(name="firstName", type="varchar", label="First Name"),
    ])
    results = manager.process_tooltips(entity)
    assert len(results) == 1
    assert results[0].status == TooltipStatus.SKIPPED


def test_current_tooltip_matches_no_change():
    client = MagicMock()
    client.get_field.return_value = (200, {"tooltip": "Current lifecycle stage."})
    manager, log = make_manager(client)
    results = manager.process_tooltips(make_entity())
    assert results[0].status == TooltipStatus.NO_CHANGE


def test_current_tooltip_differs_updated():
    client = MagicMock()
    client.get_field.return_value = (200, {"tooltip": "Old text"})
    client.update_field.return_value = (200, {})
    manager, log = make_manager(client)
    results = manager.process_tooltips(make_entity())
    assert results[0].status == TooltipStatus.UPDATED
    # Verify update_field was called with only tooltip key
    call_args = client.update_field.call_args
    payload = call_args[0][2]
    assert payload == {"tooltip": "Current lifecycle stage."}
    assert "label" not in payload
    assert "type" not in payload


def test_current_tooltip_null_updated():
    client = MagicMock()
    client.get_field.return_value = (200, {"tooltip": None})
    client.update_field.return_value = (200, {})
    manager, log = make_manager(client)
    results = manager.process_tooltips(make_entity())
    assert results[0].status == TooltipStatus.UPDATED


def test_http_401_raises_error():
    client = MagicMock()
    client.get_field.return_value = (401, None)
    manager, log = make_manager(client)
    with pytest.raises(TooltipManagerError):
        manager.process_tooltips(make_entity())


def test_http_403_continues():
    client = MagicMock()
    client.get_field.return_value = (403, None)
    manager, log = make_manager(client)
    results = manager.process_tooltips(make_entity())
    assert results[0].status == TooltipStatus.ERROR
    assert "403" in results[0].error


def test_c_prefix_for_custom_field():
    client = MagicMock()
    # c-prefix lookup succeeds
    client.get_field.return_value = (200, {"tooltip": ""})
    client.update_field.return_value = (200, {})
    manager, log = make_manager(client)
    manager.process_tooltips(make_entity())
    # First get_field call uses c-prefixed name
    first_call = client.get_field.call_args_list[0]
    assert first_call[0][1] == "cMentorStatus"


def test_native_field_fallback():
    client = MagicMock()
    # c-prefix fails, raw name succeeds
    client.get_field.side_effect = [
        (404, None),
        (200, {"tooltip": ""}),
    ]
    client.update_field.return_value = (200, {})
    manager, log = make_manager(client)
    entity = make_entity([
        FieldDefinition(
            name="description", type="text", label="Description",
            tooltip="Enter a description.",
        ),
    ])
    results = manager.process_tooltips(entity)
    assert results[0].status == TooltipStatus.UPDATED
    # update_field uses the raw name (native field)
    update_call = client.update_field.call_args
    assert update_call[0][1] == "description"


def test_payload_contains_only_tooltip():
    client = MagicMock()
    client.get_field.return_value = (200, {"tooltip": "old"})
    client.update_field.return_value = (200, {})
    manager, log = make_manager(client)
    entity = make_entity([
        FieldDefinition(
            name="mentorStatus", type="enum", label="Mentor Status",
            tooltip="New tooltip", required=True, audited=True,
            options=["Active"],
        ),
    ])
    manager.process_tooltips(entity)
    payload = client.update_field.call_args[0][2]
    assert list(payload.keys()) == ["tooltip"]
    assert payload["tooltip"] == "New tooltip"


def test_update_field_non_json_failure_surfaces_raw_text():
    """Parse-failed sentinel from update_field surfaces raw text in result error."""
    client = MagicMock()
    client.get_field.return_value = (200, {"tooltip": "old"})
    client.update_field.return_value = (
        500,
        {
            "_parse_failed": True,
            "_raw_text": "<html>nginx 502</html>",
            "_status_code": 500,
        },
    )
    manager, log = make_manager(client)
    results = manager.process_tooltips(make_entity())
    assert results[0].status == TooltipStatus.ERROR
    assert "non-JSON response" in results[0].error
    assert "nginx 502" in results[0].error

"""Tests for the governed system settings CHECK->ACT manager (PI-406 / REQ-485)."""

from unittest.mock import MagicMock

import pytest

from espo_impl.core.models import SettingsStatus
from espo_impl.core.system_settings_manager import (
    SETTINGS_ENTITY,
    SETTINGS_FIELD,
    SystemSettingsManager,
    SystemSettingsManagerError,
)


def _manager(client):
    return SystemSettingsManager(client, lambda _m, _c: None)


def _client(list_status=200, list_body=None):
    client = MagicMock()
    client.list_records.return_value = (
        list_status,
        list_body if list_body is not None else {"total": 0, "list": []},
    )
    client.create_record.return_value = (200, {"id": "rec1"})
    client.patch_record.return_value = (200, {"id": "rec1"})
    return client


def test_nothing_declared_is_skipped_and_writes_nothing():
    """A governed setting with no declared value for this instance is not
    captured — the applier must not invent one (REQ-485)."""
    client = _client()
    result = _manager(client).apply_values({})
    assert result.status is SettingsStatus.SKIPPED
    client.list_records.assert_not_called()
    client.create_record.assert_not_called()
    client.patch_record.assert_not_called()


def test_absent_carrier_is_manual_config_not_error():
    client = _client(list_status=404, list_body=None)
    result = _manager(client).apply_values({"orgName": "Cleveland"})
    assert result.status is SettingsStatus.NOT_SUPPORTED
    client.create_record.assert_not_called()


def test_auth_failure_raises():
    client = _client(list_status=401, list_body=None)
    with pytest.raises(SystemSettingsManagerError):
        _manager(client).apply_values({"orgName": "Cleveland"})


def test_no_carrier_record_creates_one_with_the_declared_values():
    client = _client()
    result = _manager(client).apply_values({"orgName": "Cleveland"})
    assert result.status is SettingsStatus.UPDATED
    assert result.changes == ["orgName"]
    client.create_record.assert_called_once_with(
        SETTINGS_ENTITY, {SETTINGS_FIELD: {"orgName": "Cleveland"}}
    )


def test_declared_values_merge_over_the_carrier_never_replace_it():
    """Per-key upsert: keys the design has not declared survive untouched."""
    client = _client(
        list_body={
            "total": 1,
            "list": [
                {
                    "id": "rec1",
                    SETTINGS_FIELD: {"orgName": "Old", "handSet": "kept"},
                }
            ],
        }
    )
    result = _manager(client).apply_values({"orgName": "Cleveland"})
    assert result.status is SettingsStatus.UPDATED
    assert result.changes == ["orgName"]
    client.patch_record.assert_called_once_with(
        SETTINGS_ENTITY,
        "rec1",
        {SETTINGS_FIELD: {"orgName": "Cleveland", "handSet": "kept"}},
    )


def test_matching_values_are_skipped_without_a_write():
    client = _client(
        list_body={
            "total": 1,
            "list": [{"id": "rec1", SETTINGS_FIELD: {"orgName": "Cleveland"}}],
        }
    )
    result = _manager(client).apply_values({"orgName": "Cleveland"})
    assert result.status is SettingsStatus.SKIPPED
    client.patch_record.assert_not_called()
    client.create_record.assert_not_called()


def test_dry_run_reports_the_change_and_writes_nothing():
    client = _client()
    result = _manager(client).apply_values(
        {"orgName": "Cleveland"}, dry_run=True
    )
    assert result.status is SettingsStatus.UPDATED
    assert result.changes == ["orgName"]
    client.create_record.assert_not_called()
    client.patch_record.assert_not_called()


def test_write_failure_is_an_error_result():
    client = _client()
    client.create_record.return_value = (500, {"message": "boom"})
    result = _manager(client).apply_values({"orgName": "Cleveland"})
    assert result.status is SettingsStatus.ERROR
    assert result.error == "HTTP 500"


def test_uninterpretable_carrier_field_is_treated_as_empty_for_the_merge():
    """A carrier holding a non-mapping is unreadable to the reader; the writer
    replaces it with the declared mapping rather than crashing."""
    client = _client(
        list_body={
            "total": 1,
            "list": [{"id": "rec1", SETTINGS_FIELD: "not-a-mapping"}],
        }
    )
    result = _manager(client).apply_values({"orgName": "Cleveland"})
    assert result.status is SettingsStatus.UPDATED
    client.patch_record.assert_called_once_with(
        SETTINGS_ENTITY, "rec1", {SETTINGS_FIELD: {"orgName": "Cleveland"}}
    )

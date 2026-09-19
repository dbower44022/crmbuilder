"""Tests for the governed per-instance values and the design-version stamp
(REQ-615 / PI-529).
"""

from __future__ import annotations

from typing import Any

import pytest
from crmbuilder_v2.publish import governed_settings as gs
from crmbuilder_v2.publish.entities import AuthenticationRejected
from crmbuilder_v2.publish.governed_settings import (
    apply_values,
    silently_dropped,
    write_stamp,
)


class FakeClient:
    """A carrier record that can be made to behave like a real instance —
    including accepting a write and keeping none of it."""

    def __init__(self, record: dict[str, Any] | None = None) -> None:
        self.record = record
        self.list_status = 200
        self.calls: list[tuple[str, Any]] = []
        #: What the instance answers with; by default, what it was sent.
        self.keeps: dict[str, Any] | None = None
        self.write_status = 200

    def list_records(self, record_type: str, max_size: int = 1) -> tuple[int, Any]:
        self.calls.append(("list", record_type))
        rows = [self.record] if self.record else []
        return self.list_status, {"list": rows}

    def create_record(self, record_type: str, payload: dict) -> tuple[int, Any]:
        self.calls.append(("create", payload))
        return self.write_status, self.keeps if self.keeps is not None else payload

    def patch_record(self, record_type: str, record_id: str, payload: dict):
        self.calls.append(("patch", (record_id, payload)))
        return self.write_status, self.keeps if self.keeps is not None else payload

    @property
    def kinds(self) -> list[str]:
        return [kind for kind, _ in self.calls]


# --- the values -------------------------------------------------------------


def test_declaring_nothing_writes_nothing() -> None:
    client = FakeClient()
    outcome = apply_values(client, {})
    assert outcome.status == gs.SKIPPED
    assert client.calls == []


def test_values_already_held_are_not_rewritten() -> None:
    client = FakeClient({"id": "1", "settings": {"maxMentees": 5}})
    outcome = apply_values(client, {"maxMentees": 5})
    assert outcome.status == gs.SKIPPED
    assert "patch" not in client.kinds


def test_only_what_differs_is_reported_and_the_rest_survives() -> None:
    """A value somebody set that the design says nothing about is not this
    system's to remove."""
    client = FakeClient({"id": "1", "settings": {"maxMentees": 5, "theirs": "x"}})
    outcome = apply_values(client, {"maxMentees": 8})
    assert outcome.status == gs.UPDATED
    assert outcome.changed == ["maxMentees"]
    _, (record_id, payload) = next(c for c in client.calls if c[0] == "patch")
    assert record_id == "1"
    assert payload["settings"] == {"maxMentees": 8, "theirs": "x"}


def test_a_missing_carrier_record_is_created() -> None:
    client = FakeClient(None)
    outcome = apply_values(client, {"maxMentees": 5})
    assert outcome.status == gs.UPDATED
    assert "create" in client.kinds


def test_an_instance_without_the_carrier_says_what_to_do() -> None:
    client = FakeClient()
    client.list_status = 404
    outcome = apply_values(client, {"maxMentees": 5})
    assert outcome.status == gs.UNAVAILABLE
    assert outcome.manual_config
    assert "grant the account" in outcome.detail


def test_a_write_the_instance_accepted_but_did_not_keep_is_a_failure() -> None:
    """The platform answers success and discards a read-only field."""
    client = FakeClient({"id": "1", "settings": {}})
    client.keeps = {"settings": {}}
    outcome = apply_values(client, {"maxMentees": 5})
    assert outcome.failed
    assert "did not keep" in outcome.detail
    assert "read-only" in outcome.detail


def test_an_answer_with_nothing_to_check_against_is_not_called_a_failure() -> None:
    client = FakeClient({"id": "1", "settings": {}})
    client.keeps = None
    outcome = apply_values(client, {"maxMentees": 5})
    assert outcome.status == gs.UPDATED


def test_a_refused_write_is_reported_with_what_the_instance_said() -> None:
    client = FakeClient({"id": "1", "settings": {}})
    client.write_status = 403
    outcome = apply_values(client, {"maxMentees": 5})
    assert outcome.failed
    assert "403" in outcome.detail


def test_a_rejected_credential_stops_the_run() -> None:
    client = FakeClient()
    client.list_status = 401
    with pytest.raises(AuthenticationRejected):
        apply_values(client, {"maxMentees": 5})


def test_preview_writes_nothing() -> None:
    client = FakeClient({"id": "1", "settings": {"maxMentees": 5}})
    outcome = apply_values(client, {"maxMentees": 8}, preview=True)
    assert outcome.status == gs.PREVIEWED
    assert "maxMentees" in outcome.detail
    assert "patch" not in client.kinds


def test_what_the_instance_did_not_keep_is_named() -> None:
    assert silently_dropped({"a": 1, "b": 2}, {"a": 1}) == ["b"]
    assert silently_dropped({"a": 1}, {"a": 1}) == []
    assert silently_dropped({"a": 1}, None) == []


# --- the stamp --------------------------------------------------------------


def test_the_stamp_records_the_design_version_and_the_plan() -> None:
    client = FakeClient({"id": "1"})
    outcome = write_stamp(client, design_version="2.1.0", plan="abc123")
    assert outcome.status == gs.UPDATED
    _, (_, payload) = next(c for c in client.calls if c[0] == "patch")
    assert payload == {"standardVersion": "2.1.0", "planFingerprint": "abc123"}


def test_an_instance_already_at_that_version_is_not_restamped() -> None:
    client = FakeClient(
        {"id": "1", "standardVersion": "2.1.0", "planFingerprint": "abc123"}
    )
    outcome = write_stamp(client, design_version="2.1.0", plan="abc123")
    assert outcome.status == gs.SKIPPED
    assert "patch" not in client.kinds


def test_the_same_version_from_a_different_plan_is_stamped_again() -> None:
    client = FakeClient(
        {"id": "1", "standardVersion": "2.1.0", "planFingerprint": "old"}
    )
    outcome = write_stamp(client, design_version="2.1.0", plan="new")
    assert outcome.status == gs.UPDATED


def test_a_stamp_the_instance_did_not_keep_says_why_it_matters() -> None:
    client = FakeClient({"id": "1"})
    client.keeps = {"standardVersion": "2.1.0"}
    outcome = write_stamp(client, design_version="2.1.0", plan="abc123")
    assert outcome.failed
    assert "cannot be identified" in outcome.detail


def test_preview_does_not_stamp() -> None:
    client = FakeClient({"id": "1"})
    outcome = write_stamp(client, design_version="2.1.0", plan="abc", preview=True)
    assert outcome.status == gs.PREVIEWED
    assert "patch" not in client.kinds


def test_an_instance_without_the_carrier_cannot_be_stamped() -> None:
    client = FakeClient()
    client.list_status = 404
    outcome = write_stamp(client, design_version="2.1.0", plan="abc")
    assert outcome.status == gs.UNAVAILABLE

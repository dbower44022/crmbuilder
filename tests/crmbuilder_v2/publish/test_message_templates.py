"""Tests for applying declared message templates (REQ-613 / PI-527)."""

from __future__ import annotations

from typing import Any

import pytest
from crmbuilder_v2.publish import message_templates as mt
from crmbuilder_v2.publish.entities import AuthenticationRejected
from crmbuilder_v2.publish.message_templates import TemplateIntent, apply_templates


class FakeClient:
    def __init__(self, live: list[dict[str, Any]] | None = None) -> None:
        self.live = live or []
        self.list_status = 200
        self.calls: list[tuple[str, Any]] = []
        self.create_answers: list[tuple[int, Any]] = [(200, {})]
        self.patch_answers: list[tuple[int, Any]] = [(200, {})]

    @staticmethod
    def _next(queue: list) -> Any:
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def list_email_templates(self, entity: str) -> tuple[int, Any]:
        self.calls.append(("list", entity))
        return self.list_status, {"list": list(self.live)}

    def create_record(self, record_type: str, payload: dict) -> tuple[int, Any]:
        self.calls.append(("create", payload))
        return self._next(self.create_answers)

    def patch_record(
        self, record_type: str, record_id: str, payload: dict
    ) -> tuple[int, Any]:
        self.calls.append(("patch", (record_id, payload)))
        return self._next(self.patch_answers)

    @property
    def kinds(self) -> list[str]:
        return [kind for kind, _ in self.calls]


def _intent(**overrides: Any) -> TemplateIntent:
    base = {
        "name": "welcome",
        "entity": "Contact",
        "subject": "Welcome",
        "body": "Hello {name}",
    }
    base.update(overrides)
    return TemplateIntent(**base)


def test_a_missing_template_is_created_with_its_object_type() -> None:
    client = FakeClient()
    [outcome] = apply_templates(client, "Contact", [_intent()])
    assert outcome.status == mt.CREATED
    sent = next(payload for kind, payload in client.calls if kind == "create")
    assert sent["entityType"] == "Contact"
    assert sent["name"] == "welcome"


def test_a_template_already_as_declared_is_left_alone() -> None:
    client = FakeClient(
        live=[
            {
                "id": "1",
                "name": "welcome",
                "subject": "Welcome",
                "body": "Hello {name}",
            }
        ]
    )
    [outcome] = apply_templates(client, "Contact", [_intent()])
    assert outcome.status == mt.SKIPPED
    assert "patch" not in client.kinds


def test_only_the_parts_that_differ_are_sent() -> None:
    client = FakeClient(
        live=[{"id": "1", "name": "welcome", "subject": "Old", "body": "Hello {name}"}]
    )
    [outcome] = apply_templates(client, "Contact", [_intent()])
    assert outcome.status == mt.UPDATED
    _, (record_id, payload) = next(
        call for call in client.calls if call[0] == "patch"
    )
    assert record_id == "1"
    assert payload == {"subject": "Welcome"}


def test_an_empty_part_and_a_missing_one_are_the_same_thing() -> None:
    client = FakeClient(live=[{"id": "1", "name": "welcome", "subject": "Welcome"}])
    [outcome] = apply_templates(
        client, "Contact", [_intent(body="")]
    )
    assert outcome.status == mt.SKIPPED


def test_a_template_the_instance_reports_without_an_identifier_cannot_be_updated() -> None:
    client = FakeClient(live=[{"name": "welcome", "subject": "Old"}])
    [outcome] = apply_templates(client, "Contact", [_intent()])
    assert outcome.failed
    assert "identifier" in outcome.detail


def test_a_template_on_the_instance_that_the_design_does_not_mention_is_reported() -> None:
    """Never removed: a person may have written it."""
    client = FakeClient(
        live=[{"id": "9", "name": "somebody else's", "subject": "Hi", "body": ""}]
    )
    outcomes = apply_templates(client, "Contact", [])
    assert [o.name for o in outcomes] == ["somebody else's"]
    assert outcomes[0].status == mt.SKIPPED
    assert "not in the design" in outcomes[0].detail
    assert "create" not in client.kinds and "patch" not in client.kinds


def test_undeclared_templates_can_be_left_unreported() -> None:
    client = FakeClient(live=[{"id": "9", "name": "other", "subject": "Hi"}])
    outcomes = apply_templates(client, "Contact", [], report_undeclared=False)
    assert outcomes == []


def test_an_instance_that_will_not_list_its_templates_fails_every_one() -> None:
    client = FakeClient()
    client.list_status = 500
    outcomes = apply_templates(client, "Contact", [_intent(), _intent(name="two")])
    assert [o.status for o in outcomes] == [mt.FAILED, mt.FAILED]


def test_a_rejected_credential_stops_the_run() -> None:
    client = FakeClient()
    client.list_status = 401
    with pytest.raises(AuthenticationRejected):
        apply_templates(client, "Contact", [_intent()])


def test_preview_writes_nothing() -> None:
    client = FakeClient(live=[{"id": "1", "name": "welcome", "subject": "Old"}])
    outcomes = apply_templates(
        client, "Contact", [_intent(), _intent(name="new one")], preview=True
    )
    assert [o.status for o in outcomes] == [mt.PREVIEWED, mt.PREVIEWED]
    assert "would be updated" in outcomes[0].detail
    assert outcomes[1].detail == "would be created"
    assert client.kinds == ["list"]

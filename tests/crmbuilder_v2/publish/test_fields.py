"""Tests for applying declared fields (REQ-608 / PI-521).

A fake client stands in for the instance. The interesting cases are all
about the platform's own behaviour: where it stores a custom field, what it
says when a creation collides with one, and what it will not do at all.
"""

from __future__ import annotations

from typing import Any

import pytest
from crmbuilder_v2.publish import fields as fld
from crmbuilder_v2.publish.entities import AuthenticationRejected
from crmbuilder_v2.publish.fields import (
    FieldIntent,
    apply_field,
    apply_fields,
    mentions_a_role,
    prefixed_name,
)


class FakeClient:
    """Answers field reads from a store keyed by the name asked for."""

    def __init__(self, stored: dict[str, dict[str, Any]] | None = None) -> None:
        self.stored = stored or {}
        self.calls: list[tuple[str, str, Any]] = []
        self.create_answers: list[tuple[int, Any]] = [(200, {})]
        self.update_answers: list[tuple[int, Any]] = [(200, {})]
        self.get_status_override: int | None = None

    @staticmethod
    def _next(queue: list) -> Any:
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def get_field(self, entity: str, name: str) -> tuple[int, Any]:
        self.calls.append(("get", name, None))
        if self.get_status_override is not None:
            return self.get_status_override, None
        if name in self.stored:
            return 200, self.stored[name]
        return 404, None

    def create_field(self, entity: str, payload: dict) -> tuple[int, Any]:
        self.calls.append(("create", entity, payload))
        return self._next(self.create_answers)

    def update_field(
        self, entity: str, name: str, payload: dict
    ) -> tuple[int, Any]:
        self.calls.append(("update", name, payload))
        return self._next(self.update_answers)

    @property
    def kinds(self) -> list[str]:
        return [kind for kind, _, _ in self.calls]


def _intent(name: str = "contactType", **payload: Any) -> FieldIntent:
    body = {"type": "varchar", "label": "Contact type"}
    body.update(payload)
    return FieldIntent(name=name, payload=body)


# --- the platform's naming --------------------------------------------------


def test_the_platform_prefixes_a_custom_field_and_capitalises_it() -> None:
    assert prefixed_name("contactType") == "cContactType"


def test_the_prefixed_name_is_tried_first() -> None:
    """That is where a custom field lives; looking under the design's name
    first would find nothing and create a duplicate."""
    client = FakeClient()
    apply_field(client, "Contact", _intent())
    assert client.calls[0][1] == "cContactType"


def test_a_built_in_field_is_found_under_its_own_name() -> None:
    client = FakeClient(
        stored={"description": {"type": "text", "label": "Description"}}
    )
    outcome = apply_field(
        client,
        "Contact",
        FieldIntent("description", {"type": "text", "label": "Description"}),
    )
    assert outcome.wire_name == "description"
    assert outcome.status == fld.SKIPPED


# --- create, update, leave alone --------------------------------------------


def test_a_missing_field_is_created() -> None:
    client = FakeClient()
    outcome = apply_field(client, "Contact", _intent())
    assert outcome.status == fld.CREATED
    assert "create" in client.kinds


def test_a_field_already_as_declared_is_left_alone() -> None:
    client = FakeClient(
        stored={"cContactType": {"type": "varchar", "label": "Contact type"}}
    )
    outcome = apply_field(client, "Contact", _intent())
    assert outcome.status == fld.SKIPPED
    assert outcome.detail == "already as declared"
    assert "update" not in client.kinds


def test_a_field_that_differs_is_updated_under_the_name_it_is_stored_as() -> None:
    client = FakeClient(
        stored={"cContactType": {"type": "varchar", "label": "Old label"}}
    )
    outcome = apply_field(client, "Contact", _intent())
    assert outcome.status == fld.UPDATED
    assert outcome.differences == ["label"]
    assert ("update", "cContactType", outcome_payload(client)) in client.calls


def outcome_payload(client: FakeClient) -> dict:
    return next(payload for kind, _, payload in client.calls if kind == "update")


def test_a_field_of_a_different_kind_is_left_alone_and_reported() -> None:
    client = FakeClient(
        stored={"cContactType": {"type": "enum", "label": "Contact type"}}
    )
    outcome = apply_field(client, "Contact", _intent())
    assert outcome.status == fld.KIND_CONFLICT
    assert "update" not in client.kinds
    assert "discards its data" in outcome.detail


# --- the collision the platform reports -------------------------------------


def test_a_creation_that_collides_becomes_an_update() -> None:
    """The platform answers a collision by naming the field it already has."""
    client = FakeClient()
    client.create_answers = [
        (409, {"messageTranslation": {"data": {"field": "cContactType"}}})
    ]
    outcome = apply_field(client, "Contact", _intent())
    assert outcome.status == fld.UPDATED
    assert outcome.wire_name == "cContactType"
    assert "updated instead of created" in outcome.detail


def test_a_collision_whose_answer_names_nothing_stays_a_failure() -> None:
    client = FakeClient()
    client.create_answers = [(409, {"message": "Conflict"})]
    outcome = apply_field(client, "Contact", _intent())
    assert outcome.failed
    assert "409" in outcome.detail


def test_a_collision_whose_update_is_refused_reports_both_facts() -> None:
    client = FakeClient()
    client.create_answers = [
        (409, {"messageTranslation": {"data": {"field": "cContactType"}}})
    ]
    client.update_answers = [(400, {"message": "bad"})]
    outcome = apply_field(client, "Contact", _intent())
    assert outcome.failed
    assert "already present as cContactType" in outcome.detail
    assert "400" in outcome.detail


# --- what the platform will not do ------------------------------------------


def test_a_visibility_rule_that_tests_a_role_is_not_sent() -> None:
    client = FakeClient()
    intent = _intent(
        dynamicLogicVisible={"all": [{"field": "role", "op": "equals", "value": "Mentor"}]}
    )
    outcome = apply_field(client, "Contact", intent)
    sent = next(p for kind, _, p in client.calls if kind == "create")
    assert "dynamicLogicVisible" not in sent
    assert outcome.status == fld.CREATED


def test_a_rule_the_platform_cannot_express_is_reported_for_manual_setup() -> None:
    client = FakeClient()
    intent = _intent(
        dynamicLogicVisible={"any": [{"field": "roles", "op": "contains", "value": "Staff"}]}
    )
    outcome = apply_field(client, "Contact", intent)
    assert outcome.manual_config
    assert "viewer's role" in outcome.manual_config[0]


def test_a_visibility_rule_without_a_role_is_sent_untouched() -> None:
    client = FakeClient()
    rule = {"all": [{"field": "stage", "op": "equals", "value": "Active"}]}
    apply_field(client, "Contact", _intent(dynamicLogicVisible=rule))
    sent = next(p for kind, _, p in client.calls if kind == "create")
    assert sent["dynamicLogicVisible"] == rule


def test_a_role_is_found_however_deep_it_sits() -> None:
    nested = {"all": [{"any": [{"field": "userRole", "op": "equals", "value": "X"}]}]}
    assert mentions_a_role(nested)
    assert not mentions_a_role({"all": [{"field": "stage", "op": "equals"}]})


def test_the_caller_s_payload_is_never_mutated() -> None:
    client = FakeClient()
    payload = {
        "type": "varchar",
        "label": "Contact type",
        "dynamicLogicVisible": {"all": [{"field": "role", "op": "equals"}]},
    }
    apply_field(client, "Contact", FieldIntent("contactType", payload))
    assert "dynamicLogicVisible" in payload


# --- failures ---------------------------------------------------------------


def test_an_unreachable_instance_is_reported_not_raised() -> None:
    client = FakeClient()
    client.get_status_override = -1
    outcome = apply_field(client, "Contact", _intent())
    assert outcome.failed
    assert "could not be reached" in outcome.detail


def test_a_forbidden_read_stops_that_field_rather_than_writing_blind() -> None:
    client = FakeClient()
    client.get_status_override = 403
    outcome = apply_field(client, "Contact", _intent())
    assert outcome.failed
    assert "403" in outcome.detail
    assert "create" not in client.kinds


def test_a_rejected_credential_stops_the_run() -> None:
    client = FakeClient()
    client.get_status_override = 401
    with pytest.raises(AuthenticationRejected):
        apply_field(client, "Contact", _intent())


def test_a_refused_creation_is_reported_with_what_the_instance_said() -> None:
    client = FakeClient()
    client.create_answers = [(400, {"message": "maxLength must be a number"})]
    outcome = apply_field(client, "Contact", _intent())
    assert outcome.failed
    assert "400" in outcome.detail


# --- preview and batches ----------------------------------------------------


def test_preview_writes_nothing() -> None:
    client = FakeClient(
        stored={"cContactType": {"type": "varchar", "label": "Old"}}
    )
    outcome = apply_field(client, "Contact", _intent(), preview=True)
    assert outcome.status == fld.PREVIEWED
    assert "would be updated" in outcome.detail
    assert "update" not in client.kinds


def test_preview_says_what_would_be_created() -> None:
    client = FakeClient()
    outcome = apply_field(client, "Contact", _intent(), preview=True)
    assert outcome.status == fld.PREVIEWED
    assert outcome.detail == "would be created"
    assert "create" not in client.kinds


def test_one_field_s_failure_does_not_stop_the_others() -> None:
    client = FakeClient()
    client.create_answers = [(400, {"message": "no"}), (200, {})]
    outcomes = apply_fields(
        client, "Contact", [_intent("one"), _intent("two")]
    )
    assert [o.status for o in outcomes] == [fld.FAILED, fld.CREATED]

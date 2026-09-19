"""Tests for applying an object type's own settings (REQ-613 / PI-527)."""

from __future__ import annotations

from typing import Any

import pytest
from crmbuilder_v2.publish import entity_settings as es
from crmbuilder_v2.publish.entities import AuthenticationRejected
from crmbuilder_v2.publish.entity_settings import (
    SettingsIntent,
    activity_parent_registration,
    apply_settings,
    changed_settings,
    multiple_assigned_users_live,
    update_payload,
)


class FakeClient:
    def __init__(
        self,
        entity_defs: Any = None,
        client_defs: Any = None,
        defs_status: int = 200,
    ) -> None:
        self.entity_defs = entity_defs if entity_defs is not None else {}
        self.client_defs = client_defs if client_defs is not None else {}
        self.defs_status = defs_status
        self.calls: list[tuple[str, Any]] = []
        self.update_answers: list[tuple[int, Any]] = [(200, {})]

    def get_entity_defs(self, entity: str) -> tuple[int, Any]:
        self.calls.append(("defs", entity))
        return self.defs_status, self.entity_defs

    def get_client_defs(self, entity: str) -> tuple[int, Any]:
        self.calls.append(("client_defs", entity))
        return 200, self.client_defs

    def update_entity(self, payload: dict) -> tuple[int, Any]:
        self.calls.append(("update", payload))
        return (
            self.update_answers.pop(0)
            if len(self.update_answers) > 1
            else self.update_answers[0]
        )

    @property
    def kinds(self) -> list[str]:
        return [kind for kind, _ in self.calls]


# --- where the platform keeps each setting ----------------------------------


def test_a_setting_kept_on_the_object_type_is_compared_there() -> None:
    intent = SettingsIntent("Engagement", {"labelSingular": "Engagement"})
    assert changed_settings(intent, {"labelSingular": "Engagement"}) == []
    assert changed_settings(intent, {"labelSingular": "Mentoring"}) == [
        "labelSingular"
    ]


def test_a_setting_kept_in_the_collection_block_is_compared_there() -> None:
    intent = SettingsIntent("Engagement", {"orderBy": "createdAt"})
    assert changed_settings(intent, {"collection": {"orderBy": "createdAt"}}) == []
    assert changed_settings(intent, {"collection": {"orderBy": "name"}}) == [
        "orderBy"
    ]


def test_a_presentation_setting_is_compared_against_the_other_surface() -> None:
    intent = SettingsIntent("Engagement", {"iconClass": "fas fa-handshake"})
    assert changed_settings(intent, {}, {"iconClass": "fas fa-handshake"}) == []
    assert changed_settings(intent, {}, {}) == ["iconClass"]


def test_an_unreported_switch_means_off_not_missing() -> None:
    """Declaring false against a setting the platform omits is not a change."""
    intent = SettingsIntent("Engagement", {"stream": False})
    assert changed_settings(intent, {}) == []
    assert changed_settings(SettingsIntent("Engagement", {"stream": True}), {}) == [
        "stream"
    ]


def test_a_setting_the_design_does_not_declare_is_not_touched() -> None:
    intent = SettingsIntent("Engagement", {})
    assert changed_settings(intent, {"labelSingular": "Anything"}, {"color": "#fff"}) == []


# --- what is sent -----------------------------------------------------------


def test_only_what_differs_is_sent() -> None:
    intent = SettingsIntent(
        "Engagement", {"labelSingular": "Engagement", "stream": True}
    )
    payload = update_payload(intent, ["stream"])
    assert payload == {"name": "CEngagement", "stream": True}


def test_the_sort_settings_are_sent_under_the_platform_s_names() -> None:
    intent = SettingsIntent("Engagement", {"orderBy": "createdAt", "order": "desc"})
    payload = update_payload(intent, ["orderBy", "order"])
    assert payload["sortBy"] == "createdAt"
    assert payload["sortDirection"] == "desc"
    assert "orderBy" not in payload


# --- applying ---------------------------------------------------------------


def test_settings_already_as_declared_are_not_written() -> None:
    client = FakeClient(entity_defs={"labelSingular": "Engagement"})
    outcome = apply_settings(
        client, SettingsIntent("Engagement", {"labelSingular": "Engagement"})
    )
    assert outcome.status == es.SKIPPED
    assert "update" not in client.kinds


def test_settings_that_differ_are_written_and_named() -> None:
    client = FakeClient(entity_defs={"labelSingular": "Old"})
    outcome = apply_settings(
        client, SettingsIntent("Engagement", {"labelSingular": "Engagement"})
    )
    assert outcome.status == es.UPDATED
    assert outcome.changed == ["labelSingular"]
    assert "labelSingular" in outcome.detail


def test_an_object_type_the_instance_will_not_describe_is_a_failure() -> None:
    client = FakeClient(defs_status=404)
    outcome = apply_settings(client, SettingsIntent("Engagement", {"stream": True}))
    assert outcome.failed
    assert "404" in outcome.detail


def test_a_refused_update_is_reported_with_what_the_instance_said() -> None:
    client = FakeClient(entity_defs={"labelSingular": "Old"})
    client.update_answers = [(400, {"message": "bad name"})]
    outcome = apply_settings(
        client, SettingsIntent("Engagement", {"labelSingular": "New"})
    )
    assert outcome.failed
    assert "400" in outcome.detail


def test_a_rejected_credential_stops_the_run() -> None:
    client = FakeClient(defs_status=401)
    with pytest.raises(AuthenticationRejected):
        apply_settings(client, SettingsIntent("Engagement", {"stream": True}))


def test_preview_writes_nothing_and_names_what_would_change() -> None:
    client = FakeClient(entity_defs={"labelSingular": "Old"})
    outcome = apply_settings(
        client,
        SettingsIntent("Engagement", {"labelSingular": "New"}),
        preview=True,
    )
    assert outcome.status == es.PREVIEWED
    assert "labelSingular" in outcome.detail
    assert "update" not in client.kinds


# --- what the platform will not accept --------------------------------------


def test_several_assignees_shows_in_the_shape_of_the_object_type() -> None:
    """The platform reports no setting for it — only its consequences."""
    assert multiple_assigned_users_live({"fields": {"assignedUsers": {}}})
    assert multiple_assigned_users_live({"links": {"collaborators": {}}})
    assert not multiple_assigned_users_live({"fields": {"assignedUser": {}}})


def test_a_difference_in_several_assignees_is_reported_for_manual_setup() -> None:
    client = FakeClient(entity_defs={"fields": {"assignedUser": {}}})
    outcome = apply_settings(
        client,
        SettingsIntent("Engagement", {}, multiple_assigned_users=True),
    )
    assert outcome.manual_config
    assert "several people" in outcome.manual_config[0]


def test_several_assignees_already_as_declared_says_nothing() -> None:
    client = FakeClient(entity_defs={"fields": {"assignedUsers": {}}})
    outcome = apply_settings(
        client,
        SettingsIntent("Engagement", {}, multiple_assigned_users=True),
    )
    assert outcome.manual_config == []


def test_an_unregistered_object_type_is_reported_for_manual_setup() -> None:
    client = FakeClient(entity_defs={"fields": {"parent": {"entityList": ["Account"]}}})
    steps = activity_parent_registration(client, "Engagement")
    assert steps and "definition files" in steps[0]


def test_a_registered_object_type_needs_nothing() -> None:
    client = FakeClient(
        entity_defs={"fields": {"parent": {"entityList": ["CEngagement"]}}}
    )
    assert activity_parent_registration(client, "Engagement") == []


def test_an_unreadable_registration_says_so_rather_than_guessing() -> None:
    client = FakeClient(defs_status=500)
    steps = activity_parent_registration(client, "Engagement")
    assert steps and "could not tell" in steps[0]

"""Tests for applying declared object types (REQ-607 / PI-520).

A fake client stands in for the instance: each method records its call and
returns the next queued answer. That keeps the tests about the decisions the
module makes — when it writes, when it skips, when it gives up, what it says
afterwards — rather than about HTTP.
"""

from __future__ import annotations

from typing import Any

import pytest
from crmbuilder_v2.publish import entities as ent
from crmbuilder_v2.publish.entities import (
    AuthenticationRejected,
    EntityIntent,
    apply_entities,
    apply_entity,
    rebuild_cache,
    wait_until_usable,
)


class FakeClient:
    """Records calls and replays queued answers.

    Each queue holds ``(status, body)`` pairs. An exhausted queue repeats its
    last answer, so a test only queues what it cares about.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.exists_answers: list[tuple[int, bool]] = [(200, False)]
        self.create_answers: list[tuple[int, Any]] = [(200, {})]
        self.remove_answers: list[tuple[int, Any]] = [(200, {})]
        self.rebuild_answers: list[tuple[int, Any]] = [(200, {})]
        self.defs_answers: list[tuple[int, Any]] = [(200, {"fields": {}})]

    @staticmethod
    def _next(queue: list) -> Any:
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def check_entity_exists(self, name: str) -> tuple[int, bool]:
        self.calls.append(("check", name))
        return self._next(self.exists_answers)

    def create_entity(self, payload: dict) -> tuple[int, Any]:
        self.calls.append(("create", payload))
        return self._next(self.create_answers)

    def remove_entity(self, name: str) -> tuple[int, Any]:
        self.calls.append(("remove", name))
        return self._next(self.remove_answers)

    def rebuild(self) -> tuple[int, Any]:
        self.calls.append(("rebuild", None))
        return self._next(self.rebuild_answers)

    def get_entity_defs(self, name: str) -> tuple[int, Any]:
        self.calls.append(("defs", name))
        return self._next(self.defs_answers)

    @property
    def kinds(self) -> list[str]:
        return [kind for kind, _ in self.calls]


# --- naming -----------------------------------------------------------------


def test_a_custom_object_type_carries_the_platform_prefix() -> None:
    assert EntityIntent("Engagement").wire_name == "CEngagement"


def test_a_native_object_type_keeps_its_own_name() -> None:
    assert EntityIntent("Account").wire_name == "Account"


def test_the_creation_payload_sends_the_design_name_not_the_prefixed_one() -> None:
    """The platform applies its own prefix; sending a prefixed name would
    produce a doubly-prefixed object type."""
    payload = EntityIntent("Engagement").creation_payload()
    assert payload["name"] == "Engagement"


def test_the_creation_payload_defaults_the_labels() -> None:
    payload = EntityIntent("Engagement").creation_payload()
    assert payload["labelSingular"] == "Engagement"
    assert payload["labelPlural"] == "Engagements"


def test_declared_labels_win_over_the_defaults() -> None:
    payload = EntityIntent(
        "Engagement", label_singular="Mentoring engagement", label_plural="Engagements"
    ).creation_payload()
    assert payload["labelSingular"] == "Mentoring engagement"


# --- creating ---------------------------------------------------------------


def test_a_missing_object_type_is_created() -> None:
    client = FakeClient()
    [outcome] = apply_entity(client, EntityIntent("Engagement"))
    assert outcome.status == ent.CREATED
    assert client.kinds == ["check", "create"]


def test_an_object_type_already_present_is_left_alone() -> None:
    client = FakeClient()
    client.exists_answers = [(200, True)]
    [outcome] = apply_entity(client, EntityIntent("Engagement"))
    assert outcome.status == ent.SKIPPED
    assert "already present" in outcome.detail
    assert "create" not in client.kinds


def test_a_refused_creation_is_reported_with_what_the_instance_said() -> None:
    client = FakeClient()
    client.create_answers = [(400, {"message": "labelSingular is required"})]
    [outcome] = apply_entity(client, EntityIntent("Engagement"))
    assert outcome.failed
    assert "400" in outcome.detail


def test_a_refused_creation_does_not_try_to_clear_the_name() -> None:
    """A refusal the instance decided created nothing, so there is nothing
    stranded to clear."""
    client = FakeClient()
    client.create_answers = [(400, {"message": "no"})]
    apply_entity(client, EntityIntent("Engagement"))
    assert "remove" not in client.kinds


# --- the stranded name ------------------------------------------------------


def test_a_server_error_clears_the_name_it_may_have_stranded() -> None:
    client = FakeClient()
    client.create_answers = [(500, {"message": "boom"})]
    [outcome] = apply_entity(client, EntityIntent("Engagement"))
    assert outcome.failed
    assert outcome.recovered is True
    assert "free to try again" in outcome.detail
    assert client.kinds == ["check", "create", "remove", "rebuild"]


def test_a_name_that_cannot_be_cleared_tells_the_operator_what_to_do() -> None:
    client = FakeClient()
    client.create_answers = [(500, {"message": "boom"})]
    client.remove_answers = [(403, {"message": "no scope"})]
    [outcome] = apply_entity(client, EntityIntent("Engagement"))
    assert outcome.recovered is False
    assert "CEngagement" in outcome.detail
    assert "rebuild" in outcome.detail


# --- removing ---------------------------------------------------------------


def test_a_declared_removal_is_applied() -> None:
    client = FakeClient()
    client.exists_answers = [(200, True)]
    [outcome] = apply_entity(client, EntityIntent("Engagement", action=ent.REMOVE))
    assert outcome.status == ent.REMOVED
    assert client.kinds == ["check", "remove"]


def test_removing_something_already_absent_is_not_a_failure() -> None:
    client = FakeClient()
    client.exists_answers = [(200, False)]
    [outcome] = apply_entity(client, EntityIntent("Engagement", action=ent.REMOVE))
    assert outcome.status == ent.SKIPPED
    assert "remove" not in client.kinds


def test_remove_and_create_does_both_in_order() -> None:
    client = FakeClient()
    client.exists_answers = [(200, True), (200, False)]
    outcomes = apply_entity(
        client, EntityIntent("Engagement", action=ent.REMOVE_AND_CREATE)
    )
    assert [o.status for o in outcomes] == [ent.REMOVED, ent.CREATED]


def test_a_failed_removal_stops_the_recreation() -> None:
    """Creating over a half-removed object type is worse than not creating."""
    client = FakeClient()
    client.exists_answers = [(200, True)]
    client.remove_answers = [(500, {"message": "boom"})]
    outcomes = apply_entity(
        client, EntityIntent("Engagement", action=ent.REMOVE_AND_CREATE)
    )
    assert len(outcomes) == 1
    assert outcomes[0].failed
    assert "create" not in client.kinds


def test_an_unknown_action_is_a_programming_error() -> None:
    client = FakeClient()
    with pytest.raises(ValueError, match="unknown action"):
        apply_entity(client, EntityIntent("Engagement", action="rename"))


# --- several, and authentication --------------------------------------------


def test_one_object_types_failure_does_not_stop_the_others() -> None:
    client = FakeClient()
    client.create_answers = [(400, {"message": "no"}), (200, {})]
    outcomes = apply_entities(
        client, [EntityIntent("Engagement"), EntityIntent("Session")]
    )
    assert [o.status for o in outcomes] == [ent.FAILED, ent.CREATED]


def test_a_rejected_credential_stops_the_run() -> None:
    client = FakeClient()
    client.exists_answers = [(401, False)]
    with pytest.raises(AuthenticationRejected):
        apply_entity(client, EntityIntent("Engagement"))


def test_a_rejected_credential_on_the_write_also_stops_the_run() -> None:
    client = FakeClient()
    client.create_answers = [(401, None)]
    with pytest.raises(AuthenticationRejected):
        apply_entity(client, EntityIntent("Engagement"))


# --- preview ----------------------------------------------------------------


def test_preview_writes_nothing_and_says_what_it_would_do() -> None:
    client = FakeClient()
    # The one to create is absent; the one to remove is present.
    client.exists_answers = [(200, False), (200, True)]
    outcomes = apply_entities(
        client,
        [
            EntityIntent("Engagement"),
            EntityIntent("Session", action=ent.REMOVE),
        ],
        preview=True,
    )
    assert [o.status for o in outcomes] == [ent.PREVIEWED, ent.PREVIEWED]
    assert client.kinds == ["check", "check"]


def test_preview_still_reports_what_is_already_as_declared() -> None:
    client = FakeClient()
    client.exists_answers = [(200, True)]
    [outcome] = apply_entity(client, EntityIntent("Engagement"), preview=True)
    assert outcome.status == ent.SKIPPED


# --- the cache and the wait -------------------------------------------------


def test_a_successful_rebuild_is_reported() -> None:
    client = FakeClient()
    assert rebuild_cache(client).status == ent.CREATED


def test_a_refused_rebuild_is_reported_not_raised() -> None:
    client = FakeClient()
    client.rebuild_answers = [(503, {"message": "busy"})]
    outcome = rebuild_cache(client)
    assert outcome.failed
    assert "503" in outcome.detail


def test_waiting_for_nothing_returns_at_once() -> None:
    client = FakeClient()
    result = wait_until_usable(client, [])
    assert result.ready == [] and not result.timed_out
    assert client.calls == []


def test_the_wait_ends_when_the_definition_appears() -> None:
    client = FakeClient()
    client.defs_answers = [(200, {}), (200, {"fields": {}})]
    slept: list[float] = []
    result = wait_until_usable(
        client, ["Engagement"], sleep=slept.append, now=_fake_clock()
    )
    assert result.ready == ["Engagement"]
    assert not result.timed_out
    assert slept == [0.5, 0.5]


def test_the_wait_polls_the_platform_name_not_the_design_name() -> None:
    client = FakeClient()
    wait_until_usable(client, ["Engagement"], sleep=lambda _: None, now=_fake_clock())
    assert ("defs", "CEngagement") in client.calls


def test_a_wait_that_times_out_names_what_is_still_pending() -> None:
    client = FakeClient()
    client.defs_answers = [(200, {})]
    result = wait_until_usable(
        client,
        ["Engagement", "Session"],
        timeout_seconds=3.0,
        sleep=lambda _: None,
        now=_fake_clock(step=1.0),
    )
    assert result.timed_out
    assert result.pending == ["Engagement", "Session"]


def test_a_partial_wait_reports_both_sides() -> None:
    client = FakeClient()

    def defs(name: str) -> tuple[int, Any]:
        client.calls.append(("defs", name))
        return (200, {"fields": {}}) if name == "CEngagement" else (200, {})

    client.get_entity_defs = defs  # type: ignore[assignment]
    result = wait_until_usable(
        client,
        ["Engagement", "Session"],
        timeout_seconds=3.0,
        sleep=lambda _: None,
        now=_fake_clock(step=1.0),
    )
    assert result.ready == ["Engagement"]
    assert result.pending == ["Session"]


def _fake_clock(step: float = 0.0):
    """A monotonic clock that advances by ``step`` on each reading."""
    state = {"t": 0.0}

    def clock() -> float:
        value = state["t"]
        state["t"] += step
        return value

    return clock

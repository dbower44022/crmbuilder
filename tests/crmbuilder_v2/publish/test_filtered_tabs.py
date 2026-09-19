"""Tests for applying declared navigation tabs and their filters
(REQ-614 / PI-528), including dates written as words.
"""

from __future__ import annotations

import datetime
from typing import Any

import pytest
from crmbuilder_v2.publish import filtered_tabs as ft
from crmbuilder_v2.publish.entities import AuthenticationRejected
from crmbuilder_v2.publish.filtered_tabs import (
    TabIntent,
    apply_tabs,
    is_relative_date,
    resolve_dates,
    resolve_relative_date,
)

MARCH_15 = datetime.date(2026, 3, 15)


class FakeClient:
    def __init__(self, filters: list[dict[str, Any]] | None = None) -> None:
        self.filters = filters or []
        self.list_status = 200
        self.create_answers: list[tuple[int, Any]] = [(200, {"id": "1"})]
        self.calls: list[tuple[str, Any]] = []

    def list_report_filters(self, entity: str) -> tuple[int, Any]:
        self.calls.append(("list", entity))
        return self.list_status, {"list": list(self.filters)}

    def create_report_filter(self, payload: dict) -> tuple[int, Any]:
        self.calls.append(("create", payload))
        return (
            self.create_answers.pop(0)
            if len(self.create_answers) > 1
            else self.create_answers[0]
        )

    @property
    def kinds(self) -> list[str]:
        return [kind for kind, _ in self.calls]


# --- dates written as words -------------------------------------------------


def test_the_words_this_system_knows() -> None:
    for word in ("today", "yesterday", "thisMonth", "lastMonth"):
        assert is_relative_date(word)
    assert is_relative_date("lastNDays:30")
    assert is_relative_date("nextNDays:7")
    assert not is_relative_date("2026-03-15")
    assert not is_relative_date(30)


def test_each_word_resolves_to_the_day_it_means() -> None:
    assert resolve_relative_date("today", MARCH_15) == MARCH_15
    assert resolve_relative_date("yesterday", MARCH_15) == datetime.date(2026, 3, 14)
    assert resolve_relative_date("thisMonth", MARCH_15) == datetime.date(2026, 3, 1)
    assert resolve_relative_date("lastMonth", MARCH_15) == datetime.date(2026, 2, 1)


def test_last_month_from_the_first_of_a_month_is_the_month_before() -> None:
    assert resolve_relative_date("lastMonth", datetime.date(2026, 1, 1)) == (
        datetime.date(2025, 12, 1)
    )


def test_a_count_of_days_resolves_in_both_directions() -> None:
    assert resolve_relative_date("lastNDays:30", MARCH_15) == datetime.date(
        2026, 2, 13
    )
    assert resolve_relative_date("nextNDays:7", MARCH_15) == datetime.date(
        2026, 3, 22
    )


def test_a_word_this_system_does_not_know_says_what_it_knows() -> None:
    with pytest.raises(ValueError, match="lastNDays"):
        resolve_relative_date("lastFortnight")


def test_dates_are_resolved_wherever_they_sit_in_a_filter() -> None:
    where = [
        {"type": "after", "attribute": "createdAt", "value": "lastNDays:30"},
        {"type": "or", "value": [{"type": "on", "value": "today"}]},
    ]
    resolved = resolve_dates(where, MARCH_15)
    assert resolved[0]["value"] == "2026-02-13"
    assert resolved[1]["value"][0]["value"] == "2026-03-15"


def test_anything_that_is_not_a_date_is_left_alone() -> None:
    where = [{"type": "equals", "attribute": "stage", "value": "Active"}]
    assert resolve_dates(where, MARCH_15) == where


# --- applying ---------------------------------------------------------------


def _intent(**overrides: Any) -> TabIntent:
    base = {
        "label": "My engagements",
        "entity": "CEngagement",
        "where": [{"type": "equals", "attribute": "stage", "value": "Active"}],
    }
    base.update(overrides)
    return TabIntent(**base)


def test_a_missing_filter_is_created() -> None:
    client = FakeClient()
    [outcome] = apply_tabs(client, [_intent()])
    assert outcome.status == ft.CREATED
    sent = next(payload for kind, payload in client.calls if kind == "create")
    assert sent["name"] == "My engagements"
    assert sent["entityType"] == "CEngagement"


def test_the_filter_is_written_with_its_dates_already_resolved() -> None:
    client = FakeClient()
    apply_tabs(
        client,
        [_intent(where=[{"type": "after", "value": "lastNDays:30"}])],
        today=MARCH_15,
    )
    sent = next(payload for kind, payload in client.calls if kind == "create")
    assert sent["data"]["where"][0]["value"] == "2026-02-13"


def test_a_filter_that_already_exists_is_left_alone() -> None:
    client = FakeClient(filters=[{"id": "1", "name": "My engagements"}])
    [outcome] = apply_tabs(client, [_intent()])
    assert outcome.status == ft.SKIPPED
    assert "create" not in client.kinds


def test_every_tab_carries_the_step_the_interface_cannot_do() -> None:
    """The filter is writable; putting the tab in the navigation is not."""
    client = FakeClient()
    [outcome] = apply_tabs(client, [_intent()])
    assert outcome.manual_config
    assert "definition files" in outcome.manual_config[0]


def test_an_instance_without_the_extension_says_so_rather_than_failing() -> None:
    client = FakeClient()
    client.list_status = 404
    [outcome] = apply_tabs(client, [_intent()])
    assert outcome.status == ft.UNAVAILABLE
    assert "not installed" in outcome.detail


def test_the_missing_extension_is_asked_about_once() -> None:
    client = FakeClient()
    client.list_status = 404
    outcomes = apply_tabs(
        client, [_intent(), _intent(label="Another"), _intent(label="A third")]
    )
    assert [o.status for o in outcomes] == [ft.UNAVAILABLE] * 3
    assert client.kinds.count("list") == 1


def test_an_extension_that_disappears_at_the_write_is_handled_too() -> None:
    client = FakeClient()
    client.create_answers = [(404, {"message": "Not Found"})]
    [outcome] = apply_tabs(client, [_intent()])
    assert outcome.status == ft.UNAVAILABLE


def test_a_refused_filter_is_reported_with_what_the_instance_said() -> None:
    client = FakeClient()
    client.create_answers = [(400, {"message": "bad where"})]
    [outcome] = apply_tabs(client, [_intent()])
    assert outcome.failed
    assert "400" in outcome.detail


def test_an_instance_that_will_not_list_its_filters_fails_that_tab() -> None:
    client = FakeClient()
    client.list_status = 500
    [outcome] = apply_tabs(client, [_intent()])
    assert outcome.failed
    assert "create" not in client.kinds


def test_a_rejected_credential_stops_the_run() -> None:
    client = FakeClient()
    client.list_status = 401
    with pytest.raises(AuthenticationRejected):
        apply_tabs(client, [_intent()])


def test_preview_writes_nothing() -> None:
    client = FakeClient()
    [outcome] = apply_tabs(client, [_intent()], preview=True)
    assert outcome.status == ft.PREVIEWED
    assert "create" not in client.kinds


def test_one_object_type_is_listed_once_for_several_tabs() -> None:
    client = FakeClient()
    outcomes = apply_tabs(client, [_intent(), _intent(label="Another")])
    assert [o.status for o in outcomes] == [ft.CREATED, ft.CREATED]
    assert client.kinds.count("list") == 1

"""Tests for applying declared links between object types (REQ-612 / PI-526)."""

from __future__ import annotations

from typing import Any

import pytest
from crmbuilder_v2.publish import links as lnk
from crmbuilder_v2.publish.entities import AuthenticationRejected
from crmbuilder_v2.publish.links import (
    LinkIntent,
    apply_link,
    apply_links,
    link_matches,
    strip_platform_prefix,
)


class FakeClient:
    """Answers link reads from a store, and records what was sent."""

    def __init__(self, links: dict[str, dict[str, Any]] | None = None) -> None:
        self.links = links or {}
        self.calls: list[tuple[str, Any]] = []
        self.create_answers: list[tuple[int, Any]] = [(200, {})]
        self.get_status = 200
        #: When set, the link appears only after a creation — which is what a
        #: real instance does.
        self.appears_after_create: dict[str, dict[str, Any]] | None = None

    def get_all_links(self, entity: str) -> tuple[int, Any]:
        self.calls.append(("links", entity))
        return self.get_status, dict(self.links)

    def create_link(self, payload: dict) -> tuple[int, Any]:
        self.calls.append(("create", payload))
        answer = (
            self.create_answers.pop(0)
            if len(self.create_answers) > 1
            else self.create_answers[0]
        )
        if answer[0] == 200 and self.appears_after_create is not None:
            self.links.update(self.appears_after_create)
        return answer

    @property
    def kinds(self) -> list[str]:
        return [kind for kind, _ in self.calls]


def _intent(**overrides: Any) -> LinkIntent:
    base = {
        "entity": "Engagement",
        "entity_foreign": "Account",
        "link": "account",
        "link_foreign": "engagements",
        "kind": "manyToOne",
    }
    base.update(overrides)
    return LinkIntent(**base)


# --- the platform's prefix --------------------------------------------------


def test_one_prefix_is_removed() -> None:
    assert strip_platform_prefix("cEngagements") == "engagements"


def test_a_name_that_merely_begins_with_the_letter_is_untouched() -> None:
    assert strip_platform_prefix("contacts") == "contacts"


def test_only_one_prefix_is_removed_per_call() -> None:
    """A doubly-prefixed name loses one layer, not both. The letter after the
    prefix goes back to lower case, because prefixing capitalises it."""
    assert strip_platform_prefix("cCEngagements") == "cEngagements"


def test_the_far_side_is_sent_unprefixed_for_a_native_target() -> None:
    """The platform applies the prefix itself; sending a prefixed name makes
    a doubly-prefixed link that never round-trips."""
    payload = _intent(link_foreign="cEngagements").creation_payload()
    assert payload["linkForeign"] == "engagements"


def test_the_far_side_is_sent_as_declared_for_a_custom_target() -> None:
    payload = _intent(
        entity_foreign="Session", link_foreign="cThings"
    ).creation_payload()
    assert payload["linkForeign"] == "cThings"


def test_both_object_types_are_named_the_platform_s_way() -> None:
    payload = _intent(entity="Engagement", entity_foreign="Account").creation_payload()
    assert payload["entity"] == "CEngagement"
    assert payload["entityForeign"] == "Account"


# --- comparison -------------------------------------------------------------


def test_a_link_of_the_declared_shape_matches() -> None:
    live = {"type": "belongsTo", "entity": "Account", "foreign": "engagements"}
    assert link_matches(live, _intent())


def test_a_link_of_another_shape_does_not_match() -> None:
    live = {"type": "hasMany", "entity": "Account", "foreign": "engagements"}
    assert not link_matches(live, _intent())


def test_either_side_of_a_one_to_one_link_matches() -> None:
    """Which side a design is written from is the platform's decision."""
    intent = _intent(kind="oneToOne")
    for reading in ("hasOne", "belongsTo"):
        live = {"type": reading, "entity": "Account", "foreign": "engagements"}
        assert link_matches(live, intent)


def test_a_link_to_another_object_type_does_not_match() -> None:
    live = {"type": "belongsTo", "entity": "Contact", "foreign": "engagements"}
    assert not link_matches(live, _intent())


def test_the_platform_s_prefix_on_the_far_side_still_matches() -> None:
    live = {"type": "belongsTo", "entity": "Account", "foreign": "cEngagements"}
    assert link_matches(live, _intent())


def test_a_link_that_does_not_report_its_far_side_is_judged_on_the_rest() -> None:
    live = {"type": "belongsTo", "entity": "Account"}
    assert link_matches(live, _intent())


# --- applying ---------------------------------------------------------------


def test_a_missing_link_is_created_and_read_back() -> None:
    client = FakeClient()
    client.appears_after_create = {
        "account": {"type": "belongsTo", "entity": "Account", "foreign": "engagements"}
    }
    outcome = apply_link(client, _intent())
    assert outcome.status == lnk.CREATED
    assert outcome.verified
    assert client.kinds == ["links", "create", "links"]


def test_a_link_the_instance_accepted_but_does_not_report_is_a_failure() -> None:
    """Everything built on top of a link assumes the link is there."""
    client = FakeClient()
    outcome = apply_link(client, _intent())
    assert outcome.failed
    assert "does not report it" in outcome.detail


def test_a_matching_link_is_left_alone() -> None:
    client = FakeClient(
        links={
            "account": {
                "type": "belongsTo",
                "entity": "Account",
                "foreign": "engagements",
            }
        }
    )
    outcome = apply_link(client, _intent())
    assert outcome.status == lnk.SKIPPED
    assert "create" not in client.kinds


def test_a_differing_link_is_reported_not_rewritten() -> None:
    """Changing a link's shape means dropping it, which takes its data."""
    client = FakeClient(
        links={"account": {"type": "hasMany", "entity": "Account"}}
    )
    outcome = apply_link(client, _intent())
    assert outcome.status == lnk.DIFFERS
    assert "takes its data" in outcome.detail
    assert "create" not in client.kinds


def test_a_refused_creation_is_reported_with_what_the_instance_said() -> None:
    client = FakeClient()
    client.create_answers = [(500, {"message": "no such entity"})]
    outcome = apply_link(client, _intent())
    assert outcome.failed
    assert "500" in outcome.detail


def test_a_rejected_credential_stops_the_run() -> None:
    client = FakeClient()
    client.get_status = 401
    with pytest.raises(AuthenticationRejected):
        apply_link(client, _intent())


def test_an_unreadable_link_list_is_treated_as_the_link_being_absent() -> None:
    client = FakeClient()
    client.get_status = 404
    client.create_answers = [(500, {"message": "boom"})]
    outcome = apply_link(client, _intent())
    assert outcome.failed
    assert "create" in client.kinds


# --- preview and batches ----------------------------------------------------


def test_preview_writes_nothing() -> None:
    client = FakeClient()
    outcome = apply_link(client, _intent(), preview=True)
    assert outcome.status == lnk.PREVIEWED
    assert "create" not in client.kinds


def test_preview_still_reports_a_link_already_as_declared() -> None:
    client = FakeClient(
        links={
            "account": {
                "type": "belongsTo",
                "entity": "Account",
                "foreign": "engagements",
            }
        }
    )
    outcome = apply_link(client, _intent(), preview=True)
    assert outcome.status == lnk.SKIPPED


def test_one_link_s_failure_does_not_stop_the_others() -> None:
    client = FakeClient()
    client.appears_after_create = {
        "account": {"type": "belongsTo", "entity": "Account", "foreign": "engagements"}
    }
    client.create_answers = [(400, {"message": "no"}), (200, {})]
    outcomes = apply_links(
        client, [_intent(link="missing"), _intent()]
    )
    assert [o.status for o in outcomes] == [lnk.FAILED, lnk.CREATED]

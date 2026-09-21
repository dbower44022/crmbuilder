"""An object type that tracks activities is told when it cannot receive them.

REQ-636 / PI-551. The design's two activity properties are both handled: one
becomes the record stream, the other builds the object type on the base kind
that carries activities. That base kind is necessary and not sufficient — the
platform also lists which object types a meeting may be filed against, in its
own definition files, which its interface does not expose.

The shapes below are what the client's test instance actually reported on
2026-09-21: five object types on that base kind, three listed as permitted
parents and two not. Nobody could file a meeting against a contribution, and
no publish had ever mentioned it, because the check that would have said so
was written, documented, tested — and called by nothing.
"""

from __future__ import annotations

from typing import Any

from crmbuilder_v2.publish import entity_settings as settings
from crmbuilder_v2.publish.declaration import parse
from crmbuilder_v2.publish.from_declaration import plan_for
from crmbuilder_v2.publish.run import apply_plan, describe

#: CBMTEST on 2026-09-21: Engagement may receive a meeting, Contribution
#: may not, and both are built on the same base kind.
LIVE_PARENTS = ["Account", "Contact", "CEngagement", "CIntakeSubmission"]

DECLARATION = """
version: "1.0.0"
content_version: "1.0.0"
entities:
  Engagement:
    action: create
    type: BasePlus
  Contribution:
    action: create
    type: BasePlus
  Resource:
    action: create
    type: Base
"""


class Instance:
    """Answers as CBMTEST did, and records what was asked."""

    def __init__(self, parents: list[str] | None = None, status: int = 200) -> None:
        self.parents = LIVE_PARENTS if parents is None else parents
        self.status = status
        self.asked: list[str] = []

    def get_entity_defs(self, name: str) -> tuple[int, Any]:
        self.asked.append(name)
        if self.status != 200:
            return self.status, None
        return 200, {"fields": {"parent": {"entityList": list(self.parents)}}}

    def __getattr__(self, name: str):
        def call(*_args, **_kwargs):
            if name == "check_entity_exists":
                return 200, True
            if name in ("get_all_scopes", "get_all_links", "get_metadata"):
                return 200, {}
            if name == "get_layout":
                return 200, []
            if name in ("create_entity", "rebuild", "update_entity"):
                return 200, {}
            return 404, None

        return call


# --- the check itself -------------------------------------------------------


def test_an_object_type_already_permitted_needs_nothing() -> None:
    outcomes = settings.check_activity_registration(Instance(), ["Engagement"])
    assert [o.status for o in outcomes] == [settings.SKIPPED]
    assert outcomes[0].manual_config == []


def test_an_object_type_not_permitted_is_named_with_what_to_do() -> None:
    """The case that was live and silent: built on the right base kind, and
    still unable to receive a meeting."""
    outcomes = settings.check_activity_registration(Instance(), ["Contribution"])
    assert [o.status for o in outcomes] == [settings.UNAVAILABLE]
    assert "Contribution" in outcomes[0].manual_config[0]
    assert "rebuild" in outcomes[0].manual_config[0]


def test_a_check_that_could_not_be_made_says_so() -> None:
    """Not readable is a third answer. Reporting it as permitted would hide
    the gap; reporting it as missing would send somebody to change a server
    that may need nothing."""
    outcomes = settings.check_activity_registration(
        Instance(status=503), ["Engagement"]
    )
    assert outcomes[0].status == settings.UNAVAILABLE
    assert "could not tell" in outcomes[0].manual_config[0]


def test_a_change_only_a_person_can_make_is_not_a_failed_run() -> None:
    outcomes = settings.check_activity_registration(Instance(), ["Contribution"])
    assert not any(outcome.failed for outcome in outcomes)


# --- what the run does with it ----------------------------------------------


def test_only_the_object_types_that_carry_activities_are_checked() -> None:
    """Resource is on the plain base kind, so asking about it would be a
    question about something the design never claimed."""
    plan = plan_for([parse(DECLARATION, "design.yaml")])
    carrying = [entity.name for entity in plan.entities if entity.tracks_activities]
    assert carrying == ["Engagement", "Contribution"]


def test_the_run_names_the_one_that_cannot_receive_a_meeting() -> None:
    instance = Instance()
    report = apply_plan(instance, plan_for([parse(DECLARATION, "design.yaml")]))
    assert any("Contribution" in item for item in report.manual_config)
    assert not any("Engagement:" in item for item in report.manual_config)


def test_the_reason_reaches_the_report_beside_the_object_type() -> None:
    """A count would say how many and never which."""
    report = apply_plan(Instance(), plan_for([parse(DECLARATION, "design.yaml")]))
    reasons = [
        line
        for line in describe(report)
        if line.startswith("  ") and not line.startswith("  - ")
    ]
    assert any("Contribution" in line for line in reasons)

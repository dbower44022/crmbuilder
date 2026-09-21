"""A declared duplicate-detection rule is reported, never dropped — REQ-635.

Version 2 parsed the block and then did nothing with it: no write, no refusal,
no word. A design saying "treat two contacts with the same electronic-mail
address as one" reached the instance and vanished. Version 1 at least said so,
once per rule, and that is what these hold.

Nothing here asks an instance anything, because there is nothing to ask: the
platform serves its definition metadata for reading only, so the rule cannot
be written, and reading one back is a separate piece of work that waits for a
design to carry a rule at all.
"""

from __future__ import annotations

from crmbuilder_v2.publish import duplicate_checks as dedup
from crmbuilder_v2.publish.declaration import parse
from crmbuilder_v2.publish.from_declaration import plan_for
from crmbuilder_v2.publish.run import apply_plan, describe, summary

DECLARATION = """
version: "1.0.0"
content_version: "1.0.0"
entities:
  Contact:
    duplicateChecks:
      - id: sameEmail
        fields: [emailAddress]
"""


class SilentInstance:
    """Answers every read as an empty instance and records nothing, because
    reporting a rule must not touch the instance at all."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __getattr__(self, name: str):
        def call(*_args, **_kwargs):
            self.calls.append(name)
            if name == "check_entity_exists":
                return 200, True
            if name in ("get_all_scopes", "get_all_links", "get_metadata"):
                return 200, {}
            if name == "get_layout":
                return 200, []
            return 404, None

        return call


# --- reading the declaration ------------------------------------------------


def test_a_declared_rule_becomes_something_to_report() -> None:
    plan = plan_for([parse(DECLARATION, "Contact.yaml")])
    rules = plan.entities[0].duplicate_checks
    assert [rule.description for rule in rules] == [
        "Contact.sameEmail (matching on emailAddress)"
    ]


def test_a_rule_written_as_a_bare_name_is_still_reported() -> None:
    """The point is to report it, not to validate it. An unfamiliar shape
    reported under its object type beats one dropped for being unfamiliar —
    dropping it quietly is the defect this ends."""
    rules = dedup.intents_for("Contact", {"duplicateChecks": ["sameEmail"]})
    assert [rule.description for rule in rules] == ["Contact.sameEmail"]


def test_a_rule_with_neither_name_nor_fields_is_reported_by_its_object_type() -> None:
    rules = dedup.intents_for("Contact", {"duplicateChecks": [{}]})
    assert [rule.description for rule in rules] == ["Contact"]


def test_an_object_type_declaring_none_reports_none() -> None:
    assert dedup.intents_for("Contact", {"fields": []}) == []


# --- what the run does with them --------------------------------------------


def test_every_rule_comes_back_as_one_a_person_must_configure() -> None:
    outcomes = dedup.report_duplicate_checks(
        dedup.intents_for("Contact", {"duplicateChecks": ["sameEmail"]})
    )
    assert [outcome.status for outcome in outcomes] == [dedup.UNAVAILABLE]
    assert outcomes[0].manual_config == [
        "Contact.sameEmail: " + dedup._NO_WRITE_PATH
    ]


def test_a_platform_limit_is_not_a_failure_of_the_run() -> None:
    """A run that reported failure because the platform cannot do something
    would teach an operator to ignore the word."""
    outcomes = dedup.report_duplicate_checks(
        dedup.intents_for("Contact", {"duplicateChecks": ["sameEmail"]})
    )
    assert not any(outcome.failed for outcome in outcomes)


def test_the_run_reaches_the_operator_by_the_hand_configuration_list() -> None:
    report = apply_plan(
        SilentInstance(), plan_for([parse(DECLARATION, "Contact.yaml")])
    )
    assert any("sameEmail" in item for item in report.manual_config)
    assert any(
        line.startswith("duplicate checks:") for line in describe(report)
    )


def test_reporting_a_rule_touches_the_instance_for_nothing() -> None:
    """There is nothing to write and nothing this yet knows how to read, so a
    read here would be a request made to look busy."""
    instance = SilentInstance()
    apply_plan(instance, plan_for([parse(DECLARATION, "Contact.yaml")]))
    assert "create_field" not in instance.calls


def test_each_rule_gets_its_own_line_carrying_the_reason() -> None:
    """A count would say how many and never which. Every outcome that did not
    succeed carries its own sentence (REQ-629), and a rule nobody can write is
    exactly such an outcome."""
    report = apply_plan(
        SilentInstance(), plan_for([parse(DECLARATION, "Contact.yaml")])
    )
    reasons = [
        line
        for line in describe(report)
        if line.startswith("  ") and not line.startswith("  - ")
    ]
    assert any("sameEmail" in line and "reading only" in line for line in reasons)


def test_the_run_does_not_report_a_failure_for_a_platform_limit() -> None:
    report = apply_plan(
        SilentInstance(), plan_for([parse(DECLARATION, "Contact.yaml")])
    )
    assert summary(report)["errors"] == 0

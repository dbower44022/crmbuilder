"""Tests for saying what a publish would do (REQ-610 / PI-523)."""

from __future__ import annotations

from crmbuilder_v2.publish import preview as pv
from crmbuilder_v2.publish.entities import EntityIntent
from crmbuilder_v2.publish.fields import FieldIntent
from crmbuilder_v2.publish.layouts import LayoutIntent
from crmbuilder_v2.publish.run import ApplyPlan, EntityPlan

from tests.crmbuilder_v2.publish.test_run import FakeInstance


def _plan() -> ApplyPlan:
    return ApplyPlan(
        entities=[
            EntityPlan(
                name="Engagement",
                entity=EntityIntent("Engagement"),
                fields=[FieldIntent("stage", {"type": "enum", "label": "Stage"})],
                layouts=[
                    LayoutIntent("detail", [{"label": "Overview", "rows": []}]),
                    LayoutIntent("detailPortal", []),
                ],
            )
        ]
    )


def test_a_preview_touches_nothing() -> None:
    instance = FakeInstance()
    pv.preview(instance, _plan())
    assert not {"create_entity", "create_field", "save_layout"} & set(instance.calls)


def test_every_thing_the_publish_would_touch_appears_once() -> None:
    changes = pv.preview(FakeInstance(), _plan())
    targets = [change.target for change in changes]
    assert "Engagement" in targets
    assert "CEngagement.stage" in targets
    assert any(target.endswith("detail") for target in targets)


def test_what_would_be_created_says_so() -> None:
    changes = pv.preview(FakeInstance(), _plan())
    entity_change = next(c for c in changes if c.target == "Engagement")
    assert entity_change.action == pv.CREATE


def test_what_the_platform_would_refuse_says_so_with_the_reason() -> None:
    changes = pv.preview(FakeInstance(), _plan())
    refused = [c for c in changes if c.action == pv.REFUSE]
    assert refused
    assert "portal" in refused[0].reason


def test_what_is_already_as_declared_is_left_alone() -> None:
    instance = FakeInstance()
    instance.existing_entities.add("CEngagement")
    changes = pv.preview(instance, _plan())
    assert any(change.action == pv.LEAVE for change in changes)


def test_the_counts_add_up_to_the_changes() -> None:
    changes = pv.preview(FakeInstance(), _plan())
    assert sum(pv.summarise(changes).values()) == len(changes)


def test_the_description_leads_with_what_would_change() -> None:
    """A person is being asked to authorise the changes, not the no-ops."""
    instance = FakeInstance()
    instance.existing_entities.add("CEngagement")
    lines = pv.describe(pv.preview(instance, _plan()))
    assert lines
    assert lines[0].startswith(pv.CREATE) or lines[0].startswith(pv.UPDATE)
    assert lines[-1].startswith(pv.LEAVE)


def test_an_empty_design_previews_as_nothing() -> None:
    assert pv.preview(FakeInstance(), ApplyPlan()) == []

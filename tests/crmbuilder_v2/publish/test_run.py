"""Tests for applying a whole design and reporting it (REQ-616 / PI-530).

One fake instance stands behind every applier, so these exercise the real
order of the run rather than mocked steps: what must exist before what, what
a failure stops, and what the report says afterwards.
"""

from __future__ import annotations

from typing import Any

from crmbuilder_v2.publish import run as runner
from crmbuilder_v2.publish.entities import EntityIntent
from crmbuilder_v2.publish.fields import FieldIntent
from crmbuilder_v2.publish.filtered_tabs import TabIntent
from crmbuilder_v2.publish.layouts import LayoutIntent
from crmbuilder_v2.publish.links import LinkIntent
from crmbuilder_v2.publish.message_templates import TemplateIntent
from crmbuilder_v2.publish.run import ApplyPlan, EntityPlan, apply_plan, describe
from crmbuilder_v2.publish.security import RoleIntent, TeamIntent


class FakeInstance:
    """An instance that accepts everything and remembers the order of it."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.existing_entities: set[str] = set()
        self.fields: dict[str, dict[str, Any]] = {}
        self.links: dict[str, dict[str, Any]] = {}
        self.scopes: dict[str, Any] = {"Account": {}}
        self.field_create_status = 200
        self.entity_create_status = 200

    # object types
    def check_entity_exists(self, name: str) -> tuple[int, bool]:
        self.calls.append("check_entity")
        return 200, name in self.existing_entities

    def create_entity(self, payload: dict) -> tuple[int, Any]:
        self.calls.append("create_entity")
        if self.entity_create_status == 200:
            self.existing_entities.add(f"C{payload['name']}")
            self.scopes[f"C{payload['name']}"] = {}
        return self.entity_create_status, {}

    def remove_entity(self, name: str) -> tuple[int, Any]:
        self.calls.append("remove_entity")
        return 200, {}

    def rebuild(self) -> tuple[int, Any]:
        self.calls.append("rebuild")
        return 200, {}

    def get_entity_defs(self, entity: str) -> tuple[int, Any]:
        self.calls.append("entity_defs")
        return 200, {"fields": {}, "collection": {}}

    def get_client_defs(self, entity: str) -> tuple[int, Any]:
        self.calls.append("client_defs")
        return 200, {}

    def update_entity(self, payload: dict) -> tuple[int, Any]:
        self.calls.append("update_entity")
        return 200, {}

    # fields
    def get_field(self, entity: str, name: str) -> tuple[int, Any]:
        self.calls.append("get_field")
        return (200, self.fields[name]) if name in self.fields else (404, None)

    def create_field(self, entity: str, payload: dict) -> tuple[int, Any]:
        self.calls.append("create_field")
        return self.field_create_status, {}

    def update_field(self, entity: str, name: str, payload: dict) -> tuple[int, Any]:
        self.calls.append("update_field")
        return 200, {}

    # layouts
    def get_layout(self, entity: str, layout_type: str) -> tuple[int, Any]:
        self.calls.append("get_layout")
        return 200, []

    def save_layout(self, entity: str, layout_type: str, body: Any):
        self.calls.append("save_layout")
        return 200, {}

    # links
    def get_all_links(self, entity: str) -> tuple[int, Any]:
        self.calls.append("get_links")
        return 200, dict(self.links)

    def create_link(self, payload: dict) -> tuple[int, Any]:
        self.calls.append("create_link")
        self.links[payload["link"]] = {
            "type": "belongsTo",
            "entity": payload["entityForeign"],
            "foreign": payload["linkForeign"],
        }
        return 200, {}

    # templates, teams, roles, tabs
    def list_email_templates(self, entity: str) -> tuple[int, Any]:
        self.calls.append("list_templates")
        return 200, {"list": []}

    def create_record(self, record_type: str, payload: dict) -> tuple[int, Any]:
        self.calls.append("create_record")
        return 200, {"id": "1"}

    def patch_record(self, record_type: str, record_id: str, payload: dict):
        self.calls.append("patch_record")
        return 200, {}

    def get_teams(self) -> tuple[int, Any]:
        self.calls.append("get_teams")
        return 200, {"list": []}

    def create_team(self, name: str, description: str | None = None):
        self.calls.append("create_team")
        return 200, {"id": "t1"}

    def get_roles(self) -> tuple[int, Any]:
        self.calls.append("get_roles")
        return 200, {"list": []}

    def create_role(self, payload: dict) -> tuple[int, Any]:
        self.calls.append("create_role")
        return 200, {"id": "r1"}

    def get_all_scopes(self) -> tuple[int, Any]:
        self.calls.append("get_scopes")
        return 200, dict(self.scopes)

    def list_report_filters(self, entity: str) -> tuple[int, Any]:
        self.calls.append("list_filters")
        return 200, {"list": []}

    def create_report_filter(self, payload: dict) -> tuple[int, Any]:
        self.calls.append("create_filter")
        return 200, {"id": "f1"}


def _full_plan() -> ApplyPlan:
    return ApplyPlan(
        entities=[
            EntityPlan(
                name="Engagement",
                entity=EntityIntent("Engagement"),
                templates=[TemplateIntent("welcome", "CEngagement", "Hi", "Hello")],
                fields=[FieldIntent("stage", {"type": "enum", "label": "Stage"})],
                layouts=[LayoutIntent("detail", [{"label": "Overview", "rows": []}])],
            )
        ],
        links=[LinkIntent("Engagement", "Account", "account", "engagements", "manyToOne")],
        teams=[TeamIntent("Mentors")],
        roles=[RoleIntent("Mentor", {"Account": {"read": "all"}})],
        tabs=[TabIntent("Mine", "CEngagement")],
    )


# --- order ------------------------------------------------------------------


def test_every_declared_step_runs() -> None:
    report = apply_plan(FakeInstance(), _full_plan())
    names = [step.name for step in report.steps]
    assert names == [
        "object types",
        "definition cache",
        "waiting for new object types",
        "object settings",
        "message templates",
        # Reported before the fields, so a rule about which records count as
        # the same is named beside the object type it guards (REQ-635).
        "duplicate checks",
        "fields",
        "layouts",
        "links",
        "teams",
        "roles",
        "navigation tabs",
    ]
    assert report.succeeded


def test_an_object_type_is_created_before_its_fields() -> None:
    instance = FakeInstance()
    apply_plan(instance, _full_plan())
    assert instance.calls.index("create_entity") < instance.calls.index("create_field")


def test_the_cache_is_rebuilt_and_believed_before_the_fields_follow() -> None:
    """The platform answers a rebuild before it has finished one."""
    instance = FakeInstance()
    apply_plan(instance, _full_plan())
    assert instance.calls.index("rebuild") < instance.calls.index("create_field")
    assert "entity_defs" in instance.calls


def test_fields_come_before_the_layouts_that_place_them() -> None:
    instance = FakeInstance()
    apply_plan(instance, _full_plan())
    assert instance.calls.index("create_field") < instance.calls.index("save_layout")


def test_roles_come_after_the_object_types_they_grant_access_to() -> None:
    instance = FakeInstance()
    apply_plan(instance, _full_plan())
    assert instance.calls.index("create_entity") < instance.calls.index("create_role")


def test_nothing_is_created_so_nothing_is_waited_for() -> None:
    instance = FakeInstance()
    instance.existing_entities.add("CEngagement")
    report = apply_plan(instance, _full_plan())
    assert "definition cache" not in [step.name for step in report.steps]


# --- the three kinds of quiet -----------------------------------------------


def test_a_step_the_design_asks_nothing_of_says_so() -> None:
    report = apply_plan(FakeInstance(), ApplyPlan())
    assert {step.status for step in report.steps} == {runner.NOTHING_DECLARED}
    assert report.succeeded


def test_nothing_declared_is_not_a_failure() -> None:
    report = apply_plan(FakeInstance(), ApplyPlan())
    assert report.failed_steps == []
    assert report.summary()[runner.NOTHING_DECLARED] == len(report.steps)


def test_work_the_platform_cannot_do_is_not_a_failure_either() -> None:
    plan = ApplyPlan(
        entities=[
            EntityPlan(
                name="Engagement",
                layouts=[LayoutIntent("detailPortal", [])],
            )
        ]
    )
    report = apply_plan(FakeInstance(), plan)
    assert report.succeeded
    assert report.manual_config
    assert report.refusals


# --- failure -----------------------------------------------------------------


def test_one_step_s_failure_does_not_stop_the_others() -> None:
    instance = FakeInstance()
    instance.field_create_status = 400
    report = apply_plan(instance, _full_plan())
    failed = [step.name for step in report.failed_steps]
    assert failed == ["fields"]
    assert "create_link" in instance.calls
    assert not report.succeeded


def test_an_unexpected_error_in_a_step_is_contained_and_named() -> None:
    instance = FakeInstance()

    def explode(entity: str) -> tuple[int, Any]:
        raise RuntimeError("the instance hung up")

    instance.get_all_links = explode  # type: ignore[assignment]
    report = apply_plan(instance, _full_plan())
    links_step = next(step for step in report.steps if step.name == "links")
    assert links_step.failed
    assert "the instance hung up" in links_step.error
    # The steps after it still ran.
    assert "create_role" in instance.calls


def test_a_rejected_credential_stops_the_run_and_says_why() -> None:
    instance = FakeInstance()

    def rejected(name: str) -> tuple[int, bool]:
        return 401, False

    instance.check_entity_exists = rejected  # type: ignore[assignment]
    report = apply_plan(instance, _full_plan())
    assert report.stopped_early
    assert not report.succeeded
    assert "create_field" not in instance.calls


# --- preview and the written report -----------------------------------------


def test_preview_writes_nothing_anywhere() -> None:
    instance = FakeInstance()
    report = apply_plan(instance, _full_plan(), preview=True)
    assert report.preview
    written = {
        "create_entity",
        "create_field",
        "save_layout",
        "create_link",
        "create_role",
        "create_team",
        "create_filter",
        "create_record",
        "update_entity",
    }
    assert not written & set(instance.calls)


def test_preview_does_not_wait_for_object_types_it_did_not_create() -> None:
    report = apply_plan(FakeInstance(), _full_plan(), preview=True)
    assert "definition cache" not in [step.name for step in report.steps]


def test_the_report_reads_as_sentences() -> None:
    instance = FakeInstance()
    instance.field_create_status = 400
    report = apply_plan(instance, _full_plan())
    lines = describe(report)
    assert any(line.startswith("fields:") for line in lines)
    assert any("failed" in line for line in lines)


def _reason_lines(lines: list[str]) -> list[str]:
    """The per-outcome lines, which are indented under their step. The
    hand-configuration list is indented too and is a different thing, so it is
    kept out by its bullet."""
    return [
        line
        for line in lines
        if line.startswith("  ") and not line.startswith("  - ")
    ]


def test_a_failure_carries_its_reason_and_names_the_construct() -> None:
    """REQ-629. The count answers how many; the operator asks which and why,
    and the applier has already written the answer. Discarding it cost a
    direct read of a live instance to diagnose one refused link on CBMTEST."""
    instance = FakeInstance()
    instance.field_create_status = 400
    lines = describe(apply_plan(instance, _full_plan()))
    reasons = _reason_lines(lines)
    assert reasons, "a failed outcome contributed no line of its own"
    assert any("400" in line for line in reasons), reasons


def test_the_outcomes_that_succeeded_are_counted_not_listed() -> None:
    """A line per success would bury the one line that matters."""
    lines = describe(apply_plan(FakeInstance(), _full_plan()))
    assert not _reason_lines(lines)


def test_the_manual_configuration_list_is_gathered_from_every_step() -> None:
    plan = ApplyPlan(
        entities=[
            EntityPlan(
                name="Engagement",
                fields=[
                    FieldIntent(
                        "secret",
                        {
                            "type": "varchar",
                            "label": "Secret",
                            "dynamicLogicVisible": {
                                "all": [{"field": "role", "op": "equals", "value": "X"}]
                            },
                        },
                    )
                ],
            )
        ],
        tabs=[TabIntent("Mine", "CEngagement")],
    )
    report = apply_plan(FakeInstance(), plan)
    assert len(report.manual_config) >= 2
    assert any("role" in item for item in report.manual_config)
    assert any("definition files" in item for item in report.manual_config)


def test_a_timed_out_wait_is_not_a_failure() -> None:
    instance = FakeInstance()

    def never_ready(entity: str) -> tuple[int, Any]:
        instance.calls.append("entity_defs")
        return 200, {}

    instance.get_entity_defs = never_ready  # type: ignore[assignment]
    report = apply_plan(
        instance,
        ApplyPlan(entities=[EntityPlan("Engagement", entity=EntityIntent("Engagement"))]),
        wait_timeout_seconds=0.2,
    )
    wait_step = next(
        step for step in report.steps if step.name == "waiting for new object types"
    )
    assert not wait_step.failed
    assert report.succeeded


# --- the counts a screen reads ----------------------------------------------


def test_the_counts_name_what_the_screen_shows() -> None:
    """The publish screen turns these into "3 create, 1 update, 2 unchanged".
    A run that stopped naming them would show "no changes" for a publish that
    changed plenty."""
    report = apply_plan(FakeInstance(), _full_plan())
    counts = runner.summary(report)
    assert counts["created"] == 1  # the one declared field
    assert counts["layouts_updated"] == 1
    assert counts["relationships_created"] == 1
    assert counts["errors"] == 0


def test_what_was_already_as_declared_counts_as_unchanged() -> None:
    instance = FakeInstance()
    instance.existing_entities.add("CEngagement")
    instance.fields["cStage"] = {"type": "enum", "label": "Stage"}
    counts = runner.summary(apply_plan(instance, _full_plan()))
    assert counts["skipped"] >= 1


def test_a_failure_is_counted_as_an_error() -> None:
    instance = FakeInstance()
    instance.field_create_status = 400
    counts = runner.summary(apply_plan(instance, _full_plan()))
    assert counts["errors"] == 1


def test_a_preview_counts_what_it_would_do() -> None:
    """That is the question a preview answers."""
    counts = runner.summary(apply_plan(FakeInstance(), _full_plan(), preview=True))
    assert counts["created"] >= 1


def test_a_refusal_is_counted_apart_from_a_match() -> None:
    """Both leave the instance alone; one means "already as declared" and the
    other means "the design and the instance disagree". Counting them together
    told an operator four fields were unchanged when one conflicted."""
    instance = FakeInstance()
    instance.existing_entities.add("CEngagement")
    # The field exists with a different type: a conflict, not a match.
    instance.fields["cStage"] = {"type": "varchar", "label": "Stage"}
    counts = runner.summary(apply_plan(instance, _full_plan()))
    assert counts["refused"] == 1
    assert counts["skipped"] == 0


def test_a_refused_layout_is_counted_as_refused() -> None:
    plan = ApplyPlan(
        entities=[EntityPlan(name="Engagement", layouts=[LayoutIntent("detailPortal", [])])]
    )
    counts = runner.summary(apply_plan(FakeInstance(), plan))
    assert counts["layouts_refused"] == 1

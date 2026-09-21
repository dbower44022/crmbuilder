"""Applying a whole design, and saying truthfully what happened
(REQ-616 / PI-530).

The appliers each know one kind of thing. This is what runs them in an order
that works, contains a failure so the rest of the run still happens, and
produces a report a person can act on.

**Order is not arbitrary.** An object type must exist before a field can go
on it, the platform's cache must be rebuilt and believed before anything
else touches a new object type, and a role cannot grant access to an object
type that is not there yet. The order here is version 1's, which was
established by deploying against real instances.

**A failing step is contained, not fatal.** A declaration describes many
things; an operator is better served by one run that reports every outcome
than by one that stops at the first refusal. The single exception is a
rejected credential, which is not an outcome about one object — it means
nothing further can be applied, so it stops the run.

**The summary distinguishes three kinds of quiet.** A step that failed, a
step the design asked nothing of, and a step somebody chose to skip look
identical in a naive report and mean entirely different things. So does the
fourth kind: work the platform cannot do, which is not a failure of the
publish but a list of things a person must now do by hand.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any

from crmbuilder_v2.introspect.utilization import wire_entity_name
from crmbuilder_v2.publish import duplicate_checks as dedup_applier
from crmbuilder_v2.publish import entities as entities_applier
from crmbuilder_v2.publish import entity_settings as settings_applier
from crmbuilder_v2.publish import fields as fields_applier
from crmbuilder_v2.publish import filtered_tabs as tabs_applier
from crmbuilder_v2.publish import layouts as layouts_applier
from crmbuilder_v2.publish import links as links_applier
from crmbuilder_v2.publish import message_templates as templates_applier
from crmbuilder_v2.publish import security as security_applier
from crmbuilder_v2.publish.entities import AuthenticationRejected
from crmbuilder_v2.publish.espo_write_client import EspoWriteClient

#: How a step came out.
OK = "ok"
FAILED = "failed"
NOTHING_DECLARED = "nothing_declared"
SKIPPED = "skipped"

#: The statuses an applier reports that mean something was refused by the
#: platform rather than done or left alone.
_REFUSAL_STATUSES = frozenset(
    {
        layouts_applier.REFUSED,
        security_applier.REFUSED,
        tabs_applier.UNAVAILABLE,
        fields_applier.KIND_CONFLICT,
        links_applier.DIFFERS,
    }
)


@dataclass
class EntityPlan:
    """Everything one object type's design asks for.

    :ivar entity: The object type as declared, or ``None`` when the design
        only adds to an object type the instance already has.
    :ivar settings: Its own settings, when the design declares any.
    :ivar templates: Its message templates.
    :ivar fields: Its fields.
    :ivar layouts: Its screen layouts.
    :ivar duplicate_checks: Its duplicate-detection rules, which no publish
        can write — reported so they are not dropped in silence (REQ-635).
    """

    name: str
    entity: entities_applier.EntityIntent | None = None
    settings: settings_applier.SettingsIntent | None = None
    templates: Sequence[templates_applier.TemplateIntent] = ()
    fields: Sequence[fields_applier.FieldIntent] = ()
    layouts: Sequence[layouts_applier.LayoutIntent] = ()
    duplicate_checks: Sequence[dedup_applier.DuplicateCheckIntent] = ()
    #: Whether the design builds this object type on the base kind that
    #: carries activities. Necessary for a meeting to be filed against it,
    #: and not sufficient — the server must list it too (REQ-636).
    tracks_activities: bool = False


@dataclass
class ApplyPlan:
    """A whole design, ready to apply.

    :ivar entities: Per object type, everything it asks for.
    :ivar links: The links between object types.
    :ivar teams: The teams.
    :ivar roles: The roles, with their field permissions.
    :ivar tabs: The navigation tabs.
    """

    entities: Sequence[EntityPlan] = ()
    links: Sequence[links_applier.LinkIntent] = ()
    teams: Sequence[security_applier.TeamIntent] = ()
    roles: Sequence[security_applier.RoleIntent] = ()
    tabs: Sequence[tabs_applier.TabIntent] = ()


@dataclass
class Step:
    """One step of the run.

    :ivar name: What the step did, in words.
    :ivar status: One of :data:`OK`, :data:`FAILED`,
        :data:`NOTHING_DECLARED`, :data:`SKIPPED`.
    :ivar outcomes: What each applier reported, unchanged.
    :ivar error: Why the step failed, when something unexpected did.
    """

    name: str
    status: str = OK
    outcomes: list[Any] = dataclass_field(default_factory=list)
    error: str = ""

    @property
    def failed(self) -> bool:
        return self.status == FAILED


@dataclass
class RunReport:
    """What a run did, in a shape a screen or a store can hold.

    :ivar steps: Each step, in the order it ran.
    :ivar manual_config: Everything the platform will not do, gathered from
        every step, in the order it was found.
    :ivar preview: Whether this run wrote anything.
    :ivar stopped_early: Set when the run could not continue at all — a
        rejected credential is the only cause.
    """

    steps: list[Step] = dataclass_field(default_factory=list)
    manual_config: list[str] = dataclass_field(default_factory=list)
    preview: bool = False
    stopped_early: str = ""

    @property
    def failed_steps(self) -> list[Step]:
        return [step for step in self.steps if step.failed]

    @property
    def succeeded(self) -> bool:
        """Whether every step that did anything did it without failing.

        A step the design asked nothing of is not a failure, and neither is
        work the platform cannot do — that is what the manual-configuration
        list is for.
        """
        return not self.failed_steps and not self.stopped_early

    @property
    def refusals(self) -> list[Any]:
        """Everything the platform would not accept, across every step."""
        return [
            outcome
            for step in self.steps
            for outcome in step.outcomes
            if getattr(outcome, "status", None) in _REFUSAL_STATUSES
        ]

    def summary(self) -> dict[str, int]:
        """How many steps came out each way."""
        counts: dict[str, int] = {}
        for step in self.steps:
            counts[step.status] = counts.get(step.status, 0) + 1
        return counts


def _gather_manual(outcomes: Sequence[Any]) -> list[str]:
    gathered: list[str] = []
    for outcome in outcomes:
        gathered.extend(getattr(outcome, "manual_config", ()) or ())
    return gathered


def _run_step(
    report: RunReport,
    name: str,
    work: Callable[[], Sequence[Any]],
    *,
    declared: bool = True,
) -> Step:
    """Run one step, containing anything it throws except a rejected credential.

    A step that raises something unexpected is a failure of that step and of
    the run, but not a reason to abandon the work that follows: the next
    object type may be fine, and the operator learns more from a run that
    finishes.
    """
    if not declared:
        step = Step(name, NOTHING_DECLARED)
        report.steps.append(step)
        return step

    try:
        outcomes = list(work())
    except AuthenticationRejected:
        raise
    except Exception as exc:  # noqa: BLE001 — a step must not sink the run
        step = Step(name, FAILED, error=f"{type(exc).__name__}: {exc}")
        report.steps.append(step)
        return step

    failed = any(getattr(outcome, "failed", False) for outcome in outcomes)
    step = Step(name, FAILED if failed else OK, outcomes=outcomes)
    report.manual_config.extend(_gather_manual(outcomes))
    report.steps.append(step)
    return step


def apply_plan(
    client: EspoWriteClient,
    plan: ApplyPlan,
    *,
    preview: bool = False,
    wait_for_new_object_types: bool = True,
    wait_timeout_seconds: float = 30.0,
) -> RunReport:
    """Apply a whole design to a live CRM system.

    :param client: A write-capable client for the target instance.
    :param plan: The design, as intents the appliers understand.
    :param preview: When true, nothing is written and every step reports
        what it would have done.
    :param wait_for_new_object_types: Whether to rebuild the platform's
        cache and wait after creating object types. Turned off only where
        the caller knows nothing was created — the wait is what stops the
        fields that follow failing against an object type the platform does
        not yet know.
    :param wait_timeout_seconds: How long that wait may take in total. A
        slow instance may need longer; a caller that knows the instance is
        fast may want to stop waiting sooner.
    :returns: What happened, step by step.
    """
    report = RunReport(preview=preview)
    try:
        _apply(
            client,
            plan,
            report,
            preview,
            wait_for_new_object_types,
            wait_timeout_seconds,
        )
    except AuthenticationRejected as rejected:
        report.stopped_early = str(rejected)
    return report


def _apply(
    client: EspoWriteClient,
    plan: ApplyPlan,
    report: RunReport,
    preview: bool,
    wait: bool,
    wait_timeout_seconds: float,
) -> None:
    # Object types first: nothing else can be applied to one that is absent.
    entity_intents = [
        entity.entity for entity in plan.entities if entity.entity is not None
    ]
    step = _run_step(
        report,
        "object types",
        lambda: entities_applier.apply_entities(
            client, entity_intents, preview=preview
        ),
        declared=bool(entity_intents),
    )

    created = [
        outcome.name
        for outcome in step.outcomes
        if getattr(outcome, "status", None) == entities_applier.CREATED
    ]
    if created and wait and not preview:
        _run_step(
            report,
            "definition cache",
            lambda: [entities_applier.rebuild_cache(client)],
        )
        _run_step(
            report,
            "waiting for new object types",
            lambda: _wait_outcomes(client, created, wait_timeout_seconds),
        )

    # An object type's own settings and templates before its fields, so a
    # field that depends on a setting — a status field, a sort order — finds
    # the object type already shaped as the design says.
    settings_intents = [
        entity.settings for entity in plan.entities if entity.settings is not None
    ]
    _run_step(
        report,
        "object settings",
        lambda: [
            settings_applier.apply_settings(client, intent, preview=preview)
            for intent in settings_intents
        ],
        declared=bool(settings_intents),
    )

    template_work = [
        entity for entity in plan.entities if entity.templates
    ]
    _run_step(
        report,
        "message templates",
        lambda: [
            outcome
            for entity in template_work
            for outcome in templates_applier.apply_templates(
                client,
                wire_entity_name(entity.name),
                entity.templates,
                preview=preview,
            )
        ],
        declared=bool(template_work),
    )

    # Reported rather than applied, and deliberately before the fields: a
    # duplicate-detection rule is about which records count as the same, so
    # an operator wants it named beside the object type it guards rather than
    # at the end of a long run (REQ-635).
    dedup_work = [entity for entity in plan.entities if entity.duplicate_checks]
    _run_step(
        report,
        "duplicate checks",
        lambda: [
            outcome
            for entity in dedup_work
            for outcome in dedup_applier.report_duplicate_checks(
                entity.duplicate_checks
            )
        ],
        declared=bool(dedup_work),
    )

    # Reported, never applied: listing an object type as somewhere a meeting
    # may be filed is a change to the platform's own definition files, which
    # its interface does not expose (REQ-636).
    activity_work = [
        entity.name for entity in plan.entities if entity.tracks_activities
    ]
    _run_step(
        report,
        "activity registration",
        lambda: settings_applier.check_activity_registration(
            client, activity_work
        ),
        declared=bool(activity_work),
    )

    field_work = [entity for entity in plan.entities if entity.fields]
    _run_step(
        report,
        "fields",
        lambda: [
            outcome
            for entity in field_work
            for outcome in fields_applier.apply_fields(
                client,
                wire_entity_name(entity.name),
                entity.fields,
                preview=preview,
            )
        ],
        declared=bool(field_work),
    )

    # Layouts after fields: a layout places fields, and a layout naming a
    # field that does not exist yet shows an empty cell.
    layout_work = [entity for entity in plan.entities if entity.layouts]
    _run_step(
        report,
        "layouts",
        lambda: [
            outcome
            for entity in layout_work
            for outcome in layouts_applier.apply_layouts(
                client,
                wire_entity_name(entity.name),
                entity.layouts,
                preview=preview,
            )
        ],
        declared=bool(layout_work),
    )

    _run_step(
        report,
        "links",
        lambda: links_applier.apply_links(client, plan.links, preview=preview),
        declared=bool(plan.links),
    )

    # Access last: a role grants access to object types, so they must exist.
    _run_step(
        report,
        "teams",
        lambda: security_applier.apply_teams(client, plan.teams, preview=preview),
        declared=bool(plan.teams),
    )
    _run_step(
        report,
        "roles",
        lambda: security_applier.apply_roles(client, plan.roles, preview=preview),
        declared=bool(plan.roles),
    )
    _run_step(
        report,
        "navigation tabs",
        lambda: tabs_applier.apply_tabs(client, plan.tabs, preview=preview),
        declared=bool(plan.tabs),
    )


def _wait_outcomes(
    client: EspoWriteClient, created: Sequence[str], timeout_seconds: float
) -> list[Any]:
    """The wait, as an outcome a step can report.

    A timeout is deliberately not a failure. The platform is often merely
    slow, and the work that follows says plainly whether the object type is
    really missing — failing here would abandon a run that would have
    succeeded.
    """
    waited = entities_applier.wait_until_usable(
        client, list(created), timeout_seconds=timeout_seconds
    )
    detail = (
        "all ready"
        if not waited.timed_out
        else "still not ready when the wait ran out: "
        + ", ".join(waited.pending)
        + ". Continuing; the work that follows will say if they are missing."
    )
    return [
        entities_applier.EntityOutcome(
            ", ".join(created),
            "",
            "wait",
            entities_applier.SKIPPED if waited.timed_out else entities_applier.CREATED,
            detail,
        )
    ]


#: The counts the publish screen reads off a run, and what each one counts.
#: Kept because a screen depends on these names: it shows "3 create, 1 update,
#: 2 unchanged" from them, and a run that stopped naming them would silently
#: show "no changes" for a publish that changed plenty.
_COUNTED: dict[str, tuple[str, tuple[str, ...]]] = {
    "fields": ("", ("created", "updated", "skipped", "refused")),
    "layouts": ("layouts_", ("updated", "skipped", "refused", "failed")),
    "links": ("relationships_", ("created", "skipped", "refused", "failed")),
}

#: What each applier calls the outcome the screen counts under that name.
#:
#: A refusal is counted apart from a match, and the distinction is the point:
#: both leave the instance alone, but one means "already as declared" and the
#: other means "the design and the instance disagree and this will not be
#: written". Folding the second into the first told an operator that four
#: fields were unchanged when one of them conflicted.
_COUNTS_AS: dict[str, str] = {
    "created": "created",
    "updated": "updated",
    "skipped": "skipped",
    "kind_conflict": "refused",
    "differs": "refused",
    "refused": "refused",
    "unavailable": "refused",
    "previewed": "created",
    "failed": "failed",
}


def summary(report: RunReport) -> dict[str, int]:
    """The run as the counts a screen reads.

    A preview counts what it would do, because that is the question a preview
    answers; an applied run counts what it did.
    """
    counts: dict[str, int] = {
        "total": 0,
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "refused": 0,
        "errors": 0,
        "layouts_updated": 0,
        "layouts_skipped": 0,
        "layouts_refused": 0,
        "layouts_failed": 0,
        "relationships_created": 0,
        "relationships_skipped": 0,
        "relationships_refused": 0,
        "relationships_failed": 0,
    }
    for step in report.steps:
        prefix, wanted = _COUNTED.get(step.name, (None, ()))
        for outcome in step.outcomes:
            status = getattr(outcome, "status", "")
            counted = _COUNTS_AS.get(status)
            if prefix is None:
                if counted == "failed":
                    counts["errors"] += 1
                continue
            counts["total"] += 1
            if counted == "failed":
                counts["errors" if not prefix else f"{prefix}failed"] += 1
            elif counted in wanted:
                counts[f"{prefix}{counted}"] += 1
    return counts


#: Where an outcome keeps the name of the thing it concerns, most specific
#: first. Each applier names its own construct, so there is no one attribute.
_NAMES = ("name", "link", "label", "layout_type", "entity")

#: The outcomes whose own words are worth a line of their own (REQ-629). A
#: success is counted; anything else raises the question "which one, and why",
#: and the answer is already sitting on the outcome.
_WORTH_A_LINE = frozenset(
    {"failed", "refused", "differs", "kind_conflict", "unavailable"}
)


def _construct_of(outcome: Any) -> str:
    """What the outcome is about, qualified by its object type where it has one."""
    for attribute in _NAMES:
        name = getattr(outcome, attribute, None)
        if name:
            entity = getattr(outcome, "entity", None)
            if entity and attribute != "entity":
                return f"{entity}.{name}"
            return str(name)
    return "?"


def describe(report: RunReport) -> list[str]:
    """The run as lines a person can read.

    Each step, then what the platform could not do. Nothing here decides
    anything; it is the report put into words.

    An outcome that did not succeed gets its own line carrying the sentence
    the applier wrote for it (REQ-629). Counting alone answers how many and
    never which or why, and a failure raises no other question: ``links: 1
    failed`` cost a direct read of a live instance to turn into an answer.
    """
    lines: list[str] = []
    for step in report.steps:
        if step.status == NOTHING_DECLARED:
            lines.append(f"{step.name}: nothing declared")
            continue
        if step.status == SKIPPED:
            lines.append(f"{step.name}: skipped")
            continue
        counted: dict[str, int] = {}
        for outcome in step.outcomes:
            status = getattr(outcome, "status", "?")
            counted[status] = counted.get(status, 0) + 1
        summary = ", ".join(f"{count} {status}" for status, count in counted.items())
        lines.append(
            f"{step.name}: {summary or 'nothing to do'}"
            + (f" — {step.error}" if step.error else "")
        )
        for outcome in step.outcomes:
            if getattr(outcome, "status", "") not in _WORTH_A_LINE:
                continue
            detail = getattr(outcome, "detail", "") or "no reason given"
            lines.append(
                f"  {_construct_of(outcome)}: "
                f"{getattr(outcome, 'status', '?')} — {detail}"
            )
    if report.manual_config:
        lines.append("")
        lines.append("To be configured by hand:")
        lines.extend(f"  - {item}" for item in report.manual_config)
    if report.stopped_early:
        lines.append("")
        lines.append(f"The run stopped: {report.stopped_early}")
    return lines

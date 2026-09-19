"""What a publish would do, before it does anything (REQ-610 / PI-523).

A person authorising a change to a live system should see the change first,
per object, with the reason — not a count, and not a promise. Every applier
already answers that question when asked not to write; this gathers their
answers into one flat list in one vocabulary, so a screen can show it and a
person can read it without knowing which applier said what.

The vocabulary is deliberately small — create, update, leave alone, refuse,
cannot tell — because a preview a person must decode is not a preview.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from crmbuilder_v2.publish import entities as entities_applier
from crmbuilder_v2.publish import fields as fields_applier
from crmbuilder_v2.publish import filtered_tabs as tabs_applier
from crmbuilder_v2.publish import layouts as layouts_applier
from crmbuilder_v2.publish import links as links_applier
from crmbuilder_v2.publish import message_templates as templates_applier
from crmbuilder_v2.publish import security as security_applier
from crmbuilder_v2.publish.espo_write_client import EspoWriteClient
from crmbuilder_v2.publish.run import ApplyPlan, RunReport, apply_plan

#: What a publish would do to one thing.
CREATE = "create"
UPDATE = "update"
LEAVE = "leave alone"
REFUSE = "refuse"
UNKNOWN = "cannot tell"

#: Every applier's own words for what it would do, in this vocabulary.
_MEANING: dict[str, str] = {
    entities_applier.CREATED: CREATE,
    entities_applier.REMOVED: UPDATE,
    fields_applier.CREATED: CREATE,
    fields_applier.UPDATED: UPDATE,
    layouts_applier.UPDATED: UPDATE,
    links_applier.CREATED: CREATE,
    templates_applier.CREATED: CREATE,
    templates_applier.UPDATED: UPDATE,
    security_applier.CREATED: CREATE,
    security_applier.UPDATED: UPDATE,
    tabs_applier.CREATED: CREATE,
    "skipped": LEAVE,
    "refused": REFUSE,
    "unavailable": REFUSE,
    "kind_conflict": REFUSE,
    "differs": REFUSE,
    "failed": UNKNOWN,
}


@dataclass(frozen=True)
class PlannedChange:
    """One thing a publish would do.

    :ivar step: Which part of the run would do it.
    :ivar target: What it would be done to, as a person would name it.
    :ivar action: One of :data:`CREATE`, :data:`UPDATE`, :data:`LEAVE`,
        :data:`REFUSE`, :data:`UNKNOWN`.
    :ivar reason: Why, in the applier's own words. Empty when the action
        says everything.
    """

    step: str
    target: str
    action: str
    reason: str = ""


def _target_of(outcome: Any) -> str:
    """What an outcome is about, as a person would name it.

    Each applier names its own subject differently — a layout by its kind, a
    field by its name, a link by both its ends — so the compound cases are
    spelled out rather than guessed at from whichever attribute comes first.
    """
    entity = getattr(outcome, "entity", None)
    layout_type = getattr(outcome, "layout_type", None)
    if layout_type:
        return f"{entity}.{layout_type}" if entity else str(layout_type)
    link = getattr(outcome, "link", None)
    if link:
        return str(link)
    name = getattr(outcome, "name", None) or getattr(outcome, "label", None)
    if name:
        return f"{entity}.{name}" if entity else str(name)
    return str(entity) if entity else "?"


def _action_of(outcome: Any) -> str:
    status = getattr(outcome, "status", "")
    if status == "previewed":
        # The applier says what it would do in words, because a preview is
        # the one run where "previewed" is not an answer.
        detail = (getattr(outcome, "detail", "") or "").lower()
        if "creat" in detail:
            return CREATE
        if "chang" in detail or "updat" in detail or "written" in detail:
            return UPDATE
        return UPDATE
    return _MEANING.get(status, UNKNOWN)


def changes_in(report: RunReport) -> list[PlannedChange]:
    """Every change a preview run found, flattened into one vocabulary."""
    return [
        PlannedChange(
            step.name,
            _target_of(outcome),
            _action_of(outcome),
            getattr(outcome, "detail", "") or "",
        )
        for step in report.steps
        for outcome in step.outcomes
    ]


def preview(client: EspoWriteClient, plan: ApplyPlan) -> list[PlannedChange]:
    """Say what applying this design would do, without touching the instance.

    :param client: A client for the target instance. It is only read from.
    :param plan: The design, as intents the appliers understand.
    :returns: One entry per thing the publish would touch.
    """
    return changes_in(apply_plan(client, plan, preview=True))


def summarise(changes: Sequence[PlannedChange]) -> dict[str, int]:
    """How many things fall under each action."""
    counts: dict[str, int] = {}
    for change in changes:
        counts[change.action] = counts.get(change.action, 0) + 1
    return counts


def describe(changes: Sequence[PlannedChange]) -> list[str]:
    """The planned changes as lines a person can read.

    What would change comes first, because that is what a person is being
    asked to authorise. What would be left alone comes last, counted rather
    than listed: on a settled design it is most of them.
    """
    lines: list[str] = []
    for action in (CREATE, UPDATE, REFUSE, UNKNOWN):
        wanted = [change for change in changes if change.action == action]
        if not wanted:
            continue
        lines.append(f"{action} ({len(wanted)}):")
        for change in wanted:
            lines.append(
                f"  {change.target}"
                + (f" — {change.reason}" if change.reason else "")
            )
    left = sum(1 for change in changes if change.action == LEAVE)
    if left:
        lines.append(f"{LEAVE}: {left} already as declared")
    return lines

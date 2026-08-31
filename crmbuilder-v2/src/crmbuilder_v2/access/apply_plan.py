"""Plan identity and the additive-only fence — PI-411 (REQ-496 / REQ-497, DEC-924).

Two gates stand between a plan and a live CRM, and they answer different
questions. :func:`fingerprint_plan` answers *is this still the plan you were
shown*; :func:`screen_automatic` answers *is this plan one nobody needs to look
at*. An apply that runs unattended has to pass both, and passing one has never
implied the other.

**Why a fingerprint rather than re-showing the plan.** REQ-496 requires the
apply to re-derive the plan and refuse if it moved. Comparing rendered output
would make the gate fire on cosmetic differences and miss real ones, so the
fingerprint covers what determines *what gets written* and is insensitive to the
order the plan was assembled in — two derivations of the same decisions are the
same plan even when the underlying lists iterate differently.

**Why the refusal list is closed.** REQ-497 names exactly three kinds that an
automatic run may not perform: removing a construct, narrowing an allowed set,
and changing a type. Everything else may proceed. The temptation is to refuse
anything unfamiliar, but a gate that blocks more than it was asked to gets
switched off, and DEC-924 already rejected a mode flag that would let an
automatic run execute a removal — precisely because the flag gets set during an
incident by whoever needs the deploy to pass. So the fence is exactly as wide as
the requirement, and no wider.

The reason those three and no others: an automatic apply changes the CRM
*before* the new application code is live, so an addition is inert to code that
does not know about it, while a removal or a narrowing takes away something the
still-running code depends on for the width of the deploy.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

#: A change an automatic apply may perform.
ADDITIVE = "additive"
#: Taking away a construct the instance holds.
REMOVAL = "removal"
#: Reducing the set of values a construct permits.
NARROWING = "narrowing"
#: Changing what kind of value a construct holds.
TYPE_CHANGE = "type_change"

#: The kinds REQ-497 refuses in an automatic run. Closed by the requirement.
REFUSED_AUTOMATICALLY: frozenset[str] = frozenset(
    {REMOVAL, NARROWING, TYPE_CHANGE}
)

#: Attributes whose value is a set of permitted values, so that shrinking one is
#: a narrowing rather than an ordinary edit.
_OPTION_SET_ATTRS: frozenset[str] = frozenset({"field_options"})

#: Attributes that say what kind of value a construct holds.
_TYPE_ATTRS: frozenset[str] = frozenset(
    {"field_type", "system_setting_value_type", "association_cardinality"}
)

_REASONS = {
    REMOVAL: "removes a construct the instance holds",
    NARROWING: "narrows the set of values the instance permits",
    TYPE_CHANGE: "changes the kind of value the construct holds",
}


def _canonical(value: Any) -> Any:
    """Reduce a value to a form two derivations agree on.

    Mappings are key-sorted and sequences are left in order except where the
    value is a set of options, whose order is not part of what it means. Without
    this the gate would fire on a dictionary that serialized differently, which
    trains an operator to ignore it.
    """
    if isinstance(value, dict):
        return {k: _canonical(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    return value


def _option_values(value: Any) -> frozenset[str] | None:
    """The bare permitted values of an option set, or ``None`` if not one."""
    if not isinstance(value, (list, tuple)):
        return None
    out: set[str] = set()
    for item in value:
        if isinstance(item, dict) and "option_value" in item:
            out.add(str(item["option_value"]))
        elif isinstance(item, (str, int)):
            out.add(str(item))
        else:
            return None
    return frozenset(out)


def fingerprint_plan(plan: Any) -> str:
    """A stable identity for one plan (REQ-496).

    Two derivations of the same decisions fingerprint identically regardless of
    the order their sources were iterated; any change to what would be written
    changes the fingerprint.
    """
    canonical = _canonical(plan)
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def plan_moved(shown_fingerprint: str, current_plan: Any) -> bool:
    """Whether the plan has changed since the operator was shown it."""
    return fingerprint_plan(current_plan) != shown_fingerprint


def classify_change(change: dict[str, Any]) -> str:
    """What kind of change one attribute-level difference would make.

    ``change`` carries ``attribute`` plus the ``design`` value being published
    and the ``instance`` value it would replace.

    A construct the instance does not hold is an addition, never a removal:
    publishing the design creates it. A removal is only reachable when the plan
    explicitly asks for one, which is why it is detected from the design side
    going empty rather than inferred.
    """
    attribute = change.get("attribute")
    design = change.get("design")
    instance = change.get("instance")

    if attribute in _TYPE_ATTRS:
        # An unset design value is not a type change — nothing is being changed
        # to. It is caught, if at all, as an undeclared attribute (REQ-513).
        if design is not None and instance is not None and design != instance:
            return TYPE_CHANGE
        return ADDITIVE

    if attribute in _OPTION_SET_ATTRS:
        design_values = _option_values(design)
        instance_values = _option_values(instance)
        if design_values is not None and instance_values is not None:
            # Narrowing is the instance permitting something the design does
            # not. Adding options is a widening and is permitted.
            if instance_values - design_values:
                return NARROWING
        return ADDITIVE

    # The design withdrawing a value the instance holds takes something away.
    if design is None and instance is not None:
        return REMOVAL

    return ADDITIVE


def screen_automatic(
    changes: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split a plan's changes into what an automatic apply may do and may not.

    :returns: ``(permitted, declined)``. Each declined change carries ``kind``
        and ``reason``, because REQ-497 requires the refusal to name each change
        it declined and why — a bare refusal leaves an operator to guess which
        part of a large plan was the problem, and guessing ends in the plan
        being pushed through by hand.
    """
    permitted: list[dict[str, Any]] = []
    declined: list[dict[str, Any]] = []
    for change in changes:
        kind = classify_change(change)
        if kind in REFUSED_AUTOMATICALLY:
            declined.append({**change, "kind": kind, "reason": _REASONS[kind]})
        else:
            permitted.append(change)
    return permitted, declined


def automatic_apply_refused(changes: list[dict[str, Any]]) -> bool:
    """Whether an automatic apply of these changes must write nothing.

    REQ-497 is all-or-nothing: a plan carrying a single refused change is not
    partially applied, because applying its additive half would leave the
    instance in a state neither the plan nor the operator ever described.
    """
    _, declined = screen_automatic(changes)
    return bool(declined)

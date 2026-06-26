"""Revert/apply impact + data-loss analysis — PI-318 (REL-024 / REQ-361).

Before a change is pushed to a live instance — in particular a *revert* that
re-pushes a prior value — the system analyzes the change's impact and flags
whether it could cause data loss or cannot be cleanly applied, so the operator is
warned and must confirm before it proceeds (DEC-723). Pure functions, no session.

The verdict's ``requires_confirmation`` is the gate: ``False`` for a clean,
safe change; ``True`` when at least one risk reason is present. ``severity`` is
``safe`` / ``data_loss`` for quick UI styling.
"""

from __future__ import annotations

from typing import Any


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def assess_field_change(
    attribute: str | None,
    from_value: Any,
    to_value: Any,
    *,
    removes_member: bool = False,
) -> dict[str, Any]:
    """Assess one proposed change to a live field for data-loss risk.

    :param attribute: the field attribute changing (``None`` for a whole-member
        presence change).
    :param from_value: the value currently on the live instance.
    :param to_value: the value the change would set.
    :param removes_member: True when the change removes the field from the
        instance (its stored data would be lost).
    """
    reasons: list[str] = []

    if removes_member:
        reasons.append(
            "removes a field that exists on the target; its stored data would be lost"
        )

    if attribute == "field_max_length" and _is_int(from_value) and _is_int(to_value):
        if to_value < from_value:
            reasons.append(
                f"narrows max length {from_value} -> {to_value}; values longer "
                f"than {to_value} would be truncated"
            )

    if attribute == "field_type" and from_value != to_value and from_value is not None:
        reasons.append(
            f"changes field type {from_value} -> {to_value}; existing values may "
            f"not convert cleanly"
        )

    return {
        "attribute": attribute,
        "from_value": from_value,
        "to_value": to_value,
        "severity": "data_loss" if reasons else "safe",
        "requires_confirmation": bool(reasons),
        "reasons": reasons,
    }


def assess_revert(transaction: dict[str, Any]) -> dict[str, Any]:
    """Assess reverting a logged transaction (re-applying its ``before_value``).

    A revert pushes the change back from ``after_value`` to ``before_value`` on
    the transaction's target, so the impact is assessed as a change *from* the
    current (``after_value``) *to* the restored (``before_value``). A revert that
    restores a member to absent removes it (data loss).
    """
    removes = transaction.get("attribute") is None and transaction.get(
        "before_value"
    ) in (None, "absent")
    verdict = assess_field_change(
        transaction.get("attribute"),
        transaction.get("after_value"),
        transaction.get("before_value"),
        removes_member=removes,
    )
    verdict["transaction_id"] = transaction.get("id")
    verdict["target_ref"] = transaction.get("target_ref")
    return verdict

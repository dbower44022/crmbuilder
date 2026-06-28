"""Pre-launch budget gate (REQ-318, PI-283).

An autonomous run does not begin until an operator has reviewed its projected
cost against a budget and explicitly approved it. This module records those
decisions (``record_decision``) and answers the launch gate
(``run_is_approved``): a run is launch-approved only when its **latest** recorded
decision is ``approved`` and the projection that decision approved was within its
budget. A later decline (or a fresh, higher projection that was declined)
overrides an earlier approval, since the latest decision is the operative one.

Decisions are kept append-only (one row per decision) so the budget/projection an
approval was made against is auditable. Engagement scoping is transparent.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import to_dict
from crmbuilder_v2.access.exceptions import FieldError, UnprocessableError
from crmbuilder_v2.access.models import _BUDGET_DECISIONS, BudgetApproval


def evaluate(projected_usd: float, budget_usd: float) -> dict:
    """Compare a projection against a budget (pure)."""
    over = round(max(0.0, projected_usd - budget_usd), 6)
    return {
        "projected_usd": round(projected_usd, 6),
        "budget_usd": round(budget_usd, 6),
        "within_budget": projected_usd <= budget_usd,
        "overage_usd": over,
    }


def record_decision(
    session: Session,
    *,
    release_identifier: str,
    budget_usd: float,
    projected_usd: float,
    decision: str,
    operator: str,
) -> dict:
    """Record an operator's pre-launch budget decision for a run (REQ-318)."""
    if decision not in _BUDGET_DECISIONS:
        raise UnprocessableError(
            [FieldError("budget_decision", "invalid",
                        f"{decision!r} is not one of {sorted(_BUDGET_DECISIONS)}")]
        )
    if not release_identifier:
        raise UnprocessableError(
            [FieldError("budget_release_identifier", "required",
                        "a run (release) identifier is required")]
        )
    if not operator:
        raise UnprocessableError(
            [FieldError("budget_operator", "required", "operator is required")]
        )
    row = BudgetApproval(
        budget_release_identifier=release_identifier,
        budget_usd=float(budget_usd),
        budget_projected_usd=float(projected_usd),
        budget_decision=decision,
        budget_operator=operator,
    )
    session.add(row)
    session.flush()
    return to_dict(row)


def latest_decision(session: Session, release_identifier: str) -> dict | None:
    """The most recent budget decision for a run, or ``None`` if none."""
    row = session.scalars(
        select(BudgetApproval)
        .where(BudgetApproval.budget_release_identifier == release_identifier)
        .order_by(BudgetApproval.budget_created_at.desc(), BudgetApproval.id.desc())
    ).first()
    return to_dict(row) if row is not None else None


def run_is_approved(session: Session, release_identifier: str) -> bool:
    """Whether a run may launch: latest decision ``approved`` AND its approved
    projection was within its budget (REQ-318). No decision → not approved."""
    latest = latest_decision(session, release_identifier)
    if latest is None or latest["budget_decision"] != "approved":
        return False
    return latest["budget_projected_usd"] <= latest["budget_usd"]


def gate_state(session: Session, release_identifier: str) -> dict:
    """The launch-gate view for a run: whether it may launch and the latest
    decision behind that (the surface a launcher reads before starting)."""
    latest = latest_decision(session, release_identifier)
    return {
        "release_identifier": release_identifier,
        "launch_approved": run_is_approved(session, release_identifier),
        "latest_decision": latest,
    }

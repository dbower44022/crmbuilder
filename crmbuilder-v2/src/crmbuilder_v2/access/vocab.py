"""Controlled vocabularies enforced by the access layer.

Both the SQLAlchemy CHECK constraints (database boundary, belt-and-braces)
and the access-layer validators consume the values defined here. New
allowed values are added by editing this module — that deliberate gate is
the point, per DEC-006.
"""

from __future__ import annotations

DECISION_STATUSES: frozenset[str] = frozenset(
    {"Active", "Superseded", "Withdrawn", "Deleted"}
)

SESSION_STATUSES: frozenset[str] = frozenset({"Complete", "In Progress"})

RISK_PROBABILITIES: frozenset[str] = frozenset({"Low", "Medium", "High"})
RISK_IMPACTS: frozenset[str] = frozenset({"Low", "Medium", "High"})
RISK_STATUSES: frozenset[str] = frozenset({"Open", "Mitigated", "Accepted", "Closed"})

PLANNING_ITEM_TYPES: frozenset[str] = frozenset(
    {"planning_dimension", "open_question", "pending_work"}
)
PLANNING_ITEM_STATUSES: frozenset[str] = frozenset({"Open", "Resolved", "Deferred"})

REFERENCE_RELATIONSHIPS: frozenset[str] = frozenset(
    {
        "is_about",
        "supersedes",
        "decided_in",
        "affects",
        "covers",
        "blocks",
        "references",
    }
)

# Entity types that can appear as source_type or target_type in references.
# The set grows as methodology entities are added in Step 0 follow-on.
ENTITY_TYPES: frozenset[str] = frozenset(
    {
        "charter",
        "status",
        "decision",
        "session",
        "risk",
        "planning_item",
        "topic",
    }
)

CHANGE_LOG_OPERATIONS: frozenset[str] = frozenset({"insert", "update", "delete"})

CHANGE_LOG_ACTORS: frozenset[str] = frozenset(
    {"claude_session", "migration", "manual"}
)


def _check_in(name: str, allowed: frozenset[str]) -> str:
    """Build a SQLite CHECK constraint expression for an enumerated column."""
    quoted = ", ".join(f"'{v}'" for v in sorted(allowed))
    return f"{name} IN ({quoted})"

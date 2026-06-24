"""Task-transition repository — the append-only lifecycle log (PI-304, DEC-692).

Phase 6a of the Agent System Redesign. One :class:`TaskTransitionRow` is created
on **every** status change of a parent task (the scheduler stamp in
``work_tasks._apply_status`` is the sole writer today). The record is
**born-terminal append-only**, mirroring ``deposit_event``: the only write verb
is :func:`record`; there is no update, patch, delete, or restore (the structural
guarantee behind REQ-264 — cleanup never destroys the record).

Schema spec: ``governance-schema-specs/task-transition.md`` (WTK-213). Stamping
contract: ``pi-304-scheduler-task-transition-stamping-design.md`` (WTK-214).

The repository owns the conditional rules a DB CHECK cannot express portably:

* ``reason`` non-empty (spec §3.6);
* per-task ordering — ``task_transition_sequence`` is assigned ``MAX + 1`` per
  parent under SAVEPOINT-retry, so concurrent appends to the *same* task get
  distinct consecutive ordinals (the UNIQUE constraint is the backstop);
* chain consistency — ``from_status`` is NULL **iff** the row is the inaugural
  (sequence 1) row for the task, else it must equal the prior row's
  ``to_status``;
* the terminal agent report (spec §3.2.4 / §3.6) — see :func:`record`.

**Terminal vs report (the access-layer reconciliation).** "Terminal" here means
*run-ending*, the set ``_TERMINAL_STATUSES = {Complete, Failed, Blocked}`` (the
agent-outcome / halt-point set per the stamping design §2 edge case), **not** the
graph sinks. A *non-terminal* transition must carry no report (a report on a
non-terminal row → 422). A *terminal* transition **with** a report must carry a
complete one (``outcome`` valid + non-empty ``reasoning_summary``; ``escalation``
required for the needs-human-equivalent halt ``Blocked``). A terminal transition
**without** a report is permitted — the internal-stamp path the stamping design
§7 sanctions ("no report unless a caller passes one"), since the api layer that
surfaces ``agent_report`` on the request bodies is out of scope here. Enforcing a
hard report-required rule at this primitive would break every existing
``update``/``patch`` that drives a task to ``Complete``; the strict
POST-requires-report contract (spec §3.7 criterion 4) belongs to the api layer.
"""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import next_prefixed_identifier, to_dict
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import FieldError, UnprocessableError
from crmbuilder_v2.access.models import TaskTransitionRow
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.repositories import references as references_repo
from crmbuilder_v2.access.vocab import (
    TASK_TRANSITION_OUTCOMES,
    TASK_TRANSITION_STATUSES,
    TASK_TRANSITION_TASK_TYPES,
)

_ENTITY_TYPE = "task_transition"
_IDENTIFIER_PREFIX = "TXN"
_IDENTIFIER_RE = re.compile(r"^TXN-\d{3}$")
_RECORDS_KIND = "task_transition_records_task"
_MAX_AUTOASSIGN_ATTEMPTS = 50

# Run-ending statuses (NOT graph sinks) — the agent reports at every run-ending
# outcome, including the recoverable halts. Mirrors ``_TERMINAL_STATUSES`` in
# ``work_tasks`` per the stamping design §2 edge case.
_TERMINAL_STATUSES = frozenset({"Complete", "Failed", "Blocked"})
# The needs-human-equivalent halt: a human must decide before the task can move
# on, so a captured report must carry an escalation (spec §3.6).
_ESCALATION_REQUIRED_STATUSES = frozenset({"Blocked"})
# The succeeded-equivalent terminal: no escalation is meaningful (spec §3.2.4
# "NULL on succeeded").
_ESCALATION_FORBIDDEN_STATUSES = frozenset({"Complete"})


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_for_task(
    session: Session,
    task_identifier: str,
    task_type: str = "work_task",
) -> list[dict]:
    """Return the complete, ordered transition history for one task.

    The primitive the other reads compose — the literal "complete transition
    history per task is reconstructable" criterion (spec §3.7.3) made queryable.
    Ordered oldest → newest by ``task_transition_sequence`` (``task_transition_at``
    is the secondary tie-break).
    """
    stmt = (
        select(TaskTransitionRow)
        .where(
            TaskTransitionRow.task_transition_task_type == task_type,
            TaskTransitionRow.task_transition_task_identifier == task_identifier,
        )
        .order_by(
            TaskTransitionRow.task_transition_sequence,
            TaskTransitionRow.task_transition_at,
        )
    )
    return [to_dict(r) for r in session.scalars(stmt).all()]


def terminal_report(
    session: Session,
    task_identifier: str,
    task_type: str = "work_task",
) -> dict | None:
    """Return the agent report at the task's terminal transition, or ``None``.

    Convenience over :func:`list_for_task`: the report ``(outcome,
    reasoning_summary, escalation)`` attached at the latest transition whose
    ``to_status`` is run-ending, or ``None`` if the task has not reached one (or
    reached one without a captured report).
    """
    for row in reversed(list_for_task(session, task_identifier, task_type)):
        if row["task_transition_to_status"] in _TERMINAL_STATUSES:
            if row["task_transition_outcome"] is None:
                return None
            return {
                "outcome": row["task_transition_outcome"],
                "reasoning_summary": row["task_transition_reasoning_summary"],
                "escalation": row["task_transition_escalation"],
            }
    return None


# ---------------------------------------------------------------------------
# Write (record-only — born-terminal append-only)
# ---------------------------------------------------------------------------


def _last_row(
    session: Session, task_type: str, task_identifier: str
) -> TaskTransitionRow | None:
    stmt = (
        select(TaskTransitionRow)
        .where(
            TaskTransitionRow.task_transition_task_type == task_type,
            TaskTransitionRow.task_transition_task_identifier == task_identifier,
        )
        .order_by(TaskTransitionRow.task_transition_sequence.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def _next_sequence(session: Session, task_type: str, task_identifier: str) -> int:
    current = session.scalar(
        select(func.max(TaskTransitionRow.task_transition_sequence)).where(
            TaskTransitionRow.task_transition_task_type == task_type,
            TaskTransitionRow.task_transition_task_identifier == task_identifier,
        )
    )
    return (current or 0) + 1


def _validate_report(
    to_status: str, agent_report: dict | None
) -> tuple[str | None, str | None, dict | None]:
    """Validate the terminal-report shape against ``to_status`` (spec §3.6).

    Returns the ``(outcome, reasoning_summary, escalation)`` triple to persist.

    * non-terminal ``to_status`` → a supplied report is rejected; the triple is
      all-NULL;
    * terminal ``to_status`` with no report → all-NULL (the internal-stamp path);
    * terminal ``to_status`` with a report → ``outcome`` (valid) and a non-empty
      ``reasoning_summary`` are required; ``escalation`` is required for the
      needs-human-equivalent halt (``Blocked``) and forbidden on the
      succeeded-equivalent terminal (``Complete``).
    """
    terminal = to_status in _TERMINAL_STATUSES

    if not terminal:
        if agent_report is not None:
            raise UnprocessableError(
                [
                    FieldError(
                        "agent_report",
                        "report_on_non_terminal_transition",
                        "a non-terminal transition carries no agent report",
                    )
                ]
            )
        return None, None, None

    if agent_report is None:
        return None, None, None

    if not isinstance(agent_report, dict):
        raise UnprocessableError(
            [
                FieldError(
                    "agent_report",
                    "invalid_value",
                    "agent_report must be a JSON object",
                )
            ]
        )

    outcome = gov.require_in(
        agent_report.get("outcome"),
        TASK_TRANSITION_OUTCOMES,
        field="task_transition_outcome",
    )
    reasoning_summary = gov.require_nonempty(
        agent_report.get("reasoning_summary"),
        field="task_transition_reasoning_summary",
    )
    escalation = agent_report.get("escalation")

    if escalation is not None and not isinstance(escalation, dict):
        raise UnprocessableError(
            [
                FieldError(
                    "task_transition_escalation",
                    "invalid_value",
                    "escalation must be a JSON object",
                )
            ]
        )
    if to_status in _ESCALATION_REQUIRED_STATUSES and escalation is None:
        raise UnprocessableError(
            [
                FieldError(
                    "task_transition_escalation",
                    "escalation_required",
                    f"a transition into {to_status!r} (a human-decision halt) "
                    "requires an escalation payload",
                )
            ]
        )
    if to_status in _ESCALATION_FORBIDDEN_STATUSES and escalation is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "task_transition_escalation",
                    "escalation_forbidden",
                    f"a transition into {to_status!r} carries no escalation",
                )
            ]
        )
    return outcome, reasoning_summary, escalation


def record(
    session: Session,
    *,
    task_type: str = "work_task",
    task_identifier: str,
    from_status: str | None,
    to_status: str,
    reason: str,
    agent_report: dict | None = None,
    at: datetime | None = None,
) -> dict:
    """Append one transition row for a parent task (record-only, append-only).

    Assigns the next ``task_transition_sequence`` (``MAX + 1`` per parent) and a
    server-assigned ``TXN-NNN`` identifier under SAVEPOINT-retry, inserts the
    row, and creates the ``task_transition_records_task`` edge to the parent — all
    in the caller's transaction, so the stamp shares the status update's atomicity
    (spec §3 / stamping design §3).

    :param task_type: parent task entity type (``work_task`` | ``workstream``).
    :param task_identifier: parent task's prefixed identifier.
    :param from_status: source status; ``None`` only for the inaugural row, else
        must equal the prior row's ``to_status``.
    :param to_status: destination status (a member of the union task vocabulary).
    :param reason: non-empty human-readable reason for the move.
    :param agent_report: at a *run-ending* ``to_status``, the optional terminal
        report ``{outcome, reasoning_summary, escalation}``; must be ``None`` on a
        non-terminal transition.
    :param at: optional semantic transition time (defaults to now).
    :raises UnprocessableError: any §3.6 repository rule is violated.
    """
    task_type = gov.require_in(
        task_type, TASK_TRANSITION_TASK_TYPES, field="task_transition_task_type"
    )
    task_identifier = gov.require_nonempty(
        task_identifier, field="task_transition_task_identifier"
    )
    to_status = gov.require_in(
        to_status, TASK_TRANSITION_STATUSES, field="task_transition_to_status"
    )
    if from_status is not None:
        from_status = gov.require_in(
            from_status,
            TASK_TRANSITION_STATUSES,
            field="task_transition_from_status",
        )
    reason = gov.require_nonempty(reason, field="task_transition_reason")

    # Chain consistency (spec §3.4). A NULL ``from_status`` is exclusively an
    # *inaugural* property — it may never appear mid-stream — and every
    # non-inaugural row must chain (its from_status == the prior row's
    # to_status). The spec's "NULL iff inaugural" is relaxed to "NULL only on
    # inaugural": the inaugural row MAY carry a real from_status, because the real
    # work_task lifecycle (PI-304 defect #1) has no ``not_started`` creation-into
    # state — a task is created *with* a status (``Planned``), so its first
    # stamped *change* legitimately carries a real from_status. A POST that models
    # true creation can still pass ``from_status=None`` for the inaugural row.
    prior = _last_row(session, task_type, task_identifier)
    if from_status is None:
        if prior is not None:
            raise UnprocessableError(
                [
                    FieldError(
                        "task_transition_from_status",
                        "null_from_status_only_on_inaugural",
                        "only the inaugural transition may have a null "
                        "from_status",
                    )
                ]
            )
    elif prior is not None and from_status != prior.task_transition_to_status:
        raise UnprocessableError(
            [
                FieldError(
                    "task_transition_from_status",
                    "from_status_chain_break",
                    f"from_status {from_status!r} must equal the prior "
                    f"transition's to_status "
                    f"{prior.task_transition_to_status!r}",
                )
            ]
        )

    outcome, reasoning_summary, escalation = _validate_report(to_status, agent_report)

    sequence = _next_sequence(session, task_type, task_identifier)
    identifiers = session.scalars(
        select(TaskTransitionRow.task_transition_identifier)
    ).all()
    candidate = next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)

    row: TaskTransitionRow | None = None
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = TaskTransitionRow(
            task_transition_identifier=candidate,
            task_transition_task_type=task_type,
            task_transition_task_identifier=task_identifier,
            task_transition_from_status=from_status,
            task_transition_to_status=to_status,
            task_transition_reason=reason,
            task_transition_sequence=sequence,
            task_transition_outcome=outcome,
            task_transition_reasoning_summary=reasoning_summary,
            task_transition_escalation=escalation,
        )
        if at is not None:
            row.task_transition_at = at
        session.add(row)
        try:
            session.flush()
        except IntegrityError as exc:
            last_error = exc
            savepoint.rollback()
            # Either the identifier collided or a concurrent append claimed this
            # task's sequence ordinal — recompute both and retry.
            sequence = _next_sequence(session, task_type, task_identifier)
            identifiers = session.scalars(
                select(TaskTransitionRow.task_transition_identifier)
            ).all()
            candidate = next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)
            continue
        savepoint.commit()
        break
    else:
        raise UnprocessableError(
            [
                FieldError(
                    "task_transition_identifier",
                    "autoassign_exhausted",
                    "could not assign a unique task_transition identifier / "
                    f"sequence after {_MAX_AUTOASSIGN_ATTEMPTS} attempts",
                )
            ]
        ) from last_error

    txn_identifier = row.task_transition_identifier

    # Graph-form parent edge (spec §3.3.1). The denormalized (type, identifier)
    # columns are the fast path; this edge is the queryable form.
    references_repo.upsert(
        session,
        source_type=_ENTITY_TYPE,
        source_id=txn_identifier,
        target_type=task_type,
        target_id=task_identifier,
        relationship=_RECORDS_KIND,
    )

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=txn_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after

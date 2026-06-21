"""The uniform task contract (Agent System Redesign, Phase 0b / REQ-284 / PI-236).

Every scheduling step reports its run-outcome with **one** vocabulary —
``TaskStatus`` — so the scheduler can drive and gate any step the same way,
replacing the per-step dialects (``VerifyOutcome``, ``StepResult``, ``TaskOutcome``,
``MergeStatus``, …). The finer "why" each dialect used to carry lives on
``TaskResult.detail``; produced artifacts live on ``TaskResult.outputs``.

This is the scheduler's *run-status* layer. It is deliberately **distinct** from
the entity lifecycle state machines (Work Task ``Ready/Complete``, the Release
pipeline stages, the Planning Item lifecycle, …): those track *where a record is
on its journey* and are unchanged. ``TaskStatus`` tracks *how a task-run went*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(str, Enum):
    """How a single task-run went — the one vocabulary the scheduler gates on."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    NEEDS_HUMAN = "needs_human"  # blocked on a human decision/review (e.g. a merge conflict)
    FAILED = "failed"  # errored / did not meet its spec — eligible for retry


@dataclass(frozen=True)
class TaskResult:
    """The uniform return shape of a task-run: a ``status`` the scheduler gates
    on, a free-text ``detail`` (the finer reason the old dialects encoded), and
    the ``outputs`` the task persisted/produced."""

    status: TaskStatus
    detail: str = ""
    outputs: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """True iff the run succeeded — the common gate predicate."""
        return self.status is TaskStatus.SUCCEEDED

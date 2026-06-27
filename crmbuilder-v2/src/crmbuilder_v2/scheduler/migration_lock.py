"""Exclusive migration lock — PI-133, built on the Layer 2 pool (DEC-399).

A schema migration rebuilds tables / constraints and locks out or times out any
*concurrent* writer (the collision seen migrating the four-step constraint). So
a migration must not run while agents are writing — it must run **alone**. This
module makes that an exclusive, runtime-owned operation layered over the Layer 2
pool (:mod:`.parallel_scheduler`) without any new locking machinery: it reuses the
pool's own active-agent bookkeeping plus its main-thread serialization (already
used for merges) as the exclusion primitive.

The window has three phases (DEC-399):

1. **PAUSE** — the moment a migration is requested, the runtime stops filling
   slots, so no *new* agent starts.
2. **DRAIN then RUN** — the migration may begin only once the in-flight agent
   set has emptied to **zero** (a full drain). It then runs **alone** on the
   runtime's main thread, so there is provably no concurrent writer.
3. **RESUME** — when the migration finishes, the window closes and slot-filling
   resumes, dispatching any work that was held during the pause.

The two decisions that define the safety property — *may we dispatch right now?*
and *may the exclusive window begin right now?* — are pure predicates
(:func:`dispatch_allowed`, :func:`can_enter_exclusive`), split from all I/O so
the lock / drain / resume behaviour is unit-tested without a server, a worktree,
or a spawned agent. The :class:`ExclusiveMigrationLock` coordinator is the thin
thread-safe state holder the pool loop consults each tick.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum


class MigrationPhase(StrEnum):
    """Where the migration lock is in its three-phase window."""

    OPEN = "open"  # normal operation — dispatch flows freely
    PENDING = "pending"  # a migration is requested; new dispatch is paused while
    # the pool drains its in-flight agents to zero
    EXCLUSIVE = "exclusive"  # the migration is running alone (active set == 0)


# --------------------------------------------------------------------------
# Pure decisions (no I/O — unit-tested directly)
# --------------------------------------------------------------------------


def dispatch_allowed(phase: MigrationPhase) -> bool:
    """Whether the pool may start new agents right now (REQ — exclusive lock).

    Only in :data:`MigrationPhase.OPEN`. Once a migration is ``PENDING`` the
    runtime stops dispatching so the pool can drain; while it is ``EXCLUSIVE``
    the migration owns the runtime alone. Both non-open phases hold the gate
    closed so the migration never overlaps an agent's writes.
    """
    return phase is MigrationPhase.OPEN


def can_enter_exclusive(phase: MigrationPhase, active_count: int) -> bool:
    """Whether the exclusive migration window may begin right now.

    Only when a migration is ``PENDING`` *and* the in-flight agent set has fully
    drained (``active_count == 0``). Requiring a complete drain — not merely a
    paused dispatch — is what guarantees no concurrent writer when the migration
    runs: every agent that was mid-flight has finished and been integrated.
    """
    return phase is MigrationPhase.PENDING and active_count == 0


# --------------------------------------------------------------------------
# The coordinator the pool loop consults each tick
# --------------------------------------------------------------------------


@dataclass
class MigrationRecord:
    """A human- and test-readable record of one exclusive migration window."""

    label: str
    requested_at: float | None = None
    drained_at: float | None = None  # when active hit 0 and the window opened
    finished_at: float | None = None
    active_at_run: int | None = None  # the live agent count when it ran (proves 0)
    error: str | None = None


@dataclass
class ExclusiveMigrationLock:
    """Thread-safe holder of the migration window's phase + the pending callable.

    Lifecycle, all driven from the pool's main loop:

    * a migration is **requested** (``request``) — from the operator/PM side, or
      another thread — moving the phase ``OPEN -> PENDING``; the pool sees
      :meth:`dispatch_allowed` go False and stops starting agents;
    * each tick the pool calls :meth:`maybe_run` with the current in-flight
      count; while the pool is still draining this is a no-op; once the count is
      zero it transitions ``PENDING -> EXCLUSIVE``, runs the migration callable
      **alone**, then transitions ``EXCLUSIVE -> OPEN`` so dispatch resumes.

    The migration callable runs on the calling (main) thread — the same thread
    that integrates merges — so it is serialized against every other main-thread
    mutation, and because the active set is zero, against every worker too.
    """

    log: Callable[[str], None] = print
    _phase: MigrationPhase = MigrationPhase.OPEN
    _migration_fn: Callable[[], None] | None = None
    _record: MigrationRecord | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)
    records: list[MigrationRecord] = field(default_factory=list)
    _clock: Callable[[], float] = time.time

    @property
    def phase(self) -> MigrationPhase:
        with self._lock:
            return self._phase

    def request(self, migration_fn: Callable[[], None], *, label: str = "migration") -> None:
        """Request an exclusive migration (``OPEN -> PENDING``).

        Pauses new dispatch immediately. Idempotent-ish: a second request while
        one is already pending/running is rejected (one exclusive op at a time).
        """
        with self._lock:
            if self._phase is not MigrationPhase.OPEN:
                raise RuntimeError(
                    f"a migration is already {self._phase.value}; "
                    "only one exclusive window at a time"
                )
            self._phase = MigrationPhase.PENDING
            self._migration_fn = migration_fn
            self._record = MigrationRecord(label=label, requested_at=self._clock())
        self.log(f"  (migration) requested '{label}' — pausing new dispatch, draining")

    def dispatch_allowed(self) -> bool:
        """Whether the pool may start new agents now (delegates to the predicate)."""
        with self._lock:
            return dispatch_allowed(self._phase)

    def pending_or_running(self) -> bool:
        """True while a migration is waiting to drain or actively running."""
        with self._lock:
            return self._phase is not MigrationPhase.OPEN

    def maybe_run(self, active_count: int) -> bool:
        """If the pool has drained, run the pending migration exclusively.

        Returns ``True`` iff a migration ran this call. Safe to call every tick:
        a no-op until the pool drains, and a no-op when nothing is pending. The
        run records the live agent count it saw (which is ``0`` — the proof of
        exclusion) and always resumes dispatch, even if the migration raised.
        """
        with self._lock:
            if not can_enter_exclusive(self._phase, active_count):
                return False
            self._phase = MigrationPhase.EXCLUSIVE
            fn = self._migration_fn
            record = self._record
        assert fn is not None and record is not None
        record.drained_at = self._clock()
        record.active_at_run = active_count  # == 0 by can_enter_exclusive
        self.log(
            f"  (migration) pool drained (in-flight={active_count}) — "
            f"running '{record.label}' EXCLUSIVELY"
        )
        try:
            fn()
        except Exception as exc:  # surface, then still resume — never wedge the pool
            record.error = f"{type(exc).__name__}: {exc}"
            self.log(f"  (migration) '{record.label}' FAILED: {record.error}")
        finally:
            record.finished_at = self._clock()
            with self._lock:
                self._phase = MigrationPhase.OPEN
                self._migration_fn = None
                self.records.append(record)
                self._record = None
        self.log(f"  (migration) '{record.label}' done — resuming dispatch")
        return True

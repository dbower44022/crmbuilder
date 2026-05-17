"""Activation worker — kill-relaunch dance for engagement switching.

Implements the 12-step activation sequence per
``multi-engagement-architecture.md`` §4, with the PRD §3 / question-6
amendment: step 7's ``engagement_last_opened_at`` PATCH is deferred to
after the new API subprocess is up (renumbered to step 10).

Subprocess interactions go through injected manager callables so tests
can simulate kill/launch without spawning real processes. Production
wiring passes a small adapter built on top of :class:`ServerLifecycle`
plus an optional MCP-server hook.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx
from PySide6.QtCore import QObject, QThread, Signal, Slot

from crmbuilder_v2.access.engagement_models import Engagement
from crmbuilder_v2.migration.lazy_migration import (
    MigrationError,
    engagement_db_path,
    run_engagement_migrations,
)

_log = logging.getLogger("crmbuilder_v2.ui.activation_worker")

# Health-check polling for new API launch (step 8). Initial 100 ms,
# doubling each retry, capped at 5 s, total budget 30 s.
_API_HEALTH_INITIAL_DELAY = 0.1
_API_HEALTH_MAX_DELAY = 5.0
_API_HEALTH_TOTAL_TIMEOUT = 30.0


STEP_DESCRIPTIONS: tuple[str, ...] = (
    "Preparing…",
    "Verifying engagement is reachable…",
    "Upgrading engagement database…",
    "Stopping API server…",
    "Stopping MCP server…",
    "Saving active engagement state…",
    "Updating engagement context…",
    "Starting API server…",
    "Starting MCP server…",
    "Recording last-opened timestamp…",
    "Notifying panels…",
    "Finalizing…",
)


@dataclass
class SubprocessManagers:
    """Callable bundle passed into :class:`ActivationWorker`.

    Each callable is a no-op-friendly hook to make the worker fully
    testable. Production wiring injects real implementations (built on
    top of :class:`ServerLifecycle` for the API, a parallel adapter for
    the MCP server). Tests can pass stubs returning success/failure.
    """

    # Stops the currently-running API subprocess. Raises ``RuntimeError``
    # if the API does not release its port within an internal deadline.
    kill_api: Callable[[], None]
    # Same for the MCP subprocess. May be a no-op when no MCP is wired.
    kill_mcp: Callable[[], None]
    # Spawns a fresh API subprocess against ``engagement_db_path``.
    # Returns once the new API is up (``GET /health`` returns 200).
    launch_api: Callable[[Path], None]
    # Spawns a fresh MCP subprocess. May be a no-op when no MCP is wired.
    launch_mcp: Callable[[Path], None]


def default_api_health_probe(base_url: str) -> bool:
    """Default ``GET /health`` probe used by :func:`build_default_managers`."""
    try:
        resp = httpx.get(f"{base_url.rstrip('/')}/health", timeout=1.0)
    except httpx.HTTPError:
        return False
    return resp.status_code == 200


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------


class ActivationWorker(QObject):
    """Drive the 12-step activation sequence on a Qt worker thread.

    Signals (all carry primitives so they marshal across threads
    without trouble):

    * ``step_started(int step_number, str description)``
    * ``step_completed(int step_number, str description)``
    * ``step_failed(int step_number, str description, str error_message)``
    * ``completed(object engagement)`` — the activated Engagement on success
    * ``failed(object previous_engagement, str error_message)``
    """

    step_started = Signal(int, str)
    step_completed = Signal(int, str)
    step_failed = Signal(int, str, str)
    completed = Signal(object)
    failed = Signal(object, str)

    def __init__(
        self,
        target_engagement: Engagement,
        previous_engagement: Engagement | None,
        client,
        active_context,
        managers: SubprocessManagers,
        *,
        api_health_probe: Callable[[], bool] | None = None,
        write_current_engagement: Callable[[Engagement], None] | None = None,
        rollback_current_engagement: Callable[[Engagement | None], None] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._target = target_engagement
        self._previous = previous_engagement
        self._client = client
        self._active_context = active_context
        self._managers = managers
        self._api_health_probe = api_health_probe
        self._write_current_engagement = write_current_engagement
        self._rollback_current_engagement = rollback_current_engagement
        self._context_updated = False
        self._current_file_written = False

    @Slot()
    def run(self) -> None:
        """Execute the 12-step sequence sequentially."""
        try:
            # Step 1: Preparing.
            self._begin(1)
            self._end(1)
            # Step 2: Reachability check.
            self._begin(2)
            self._reachability_check()
            self._end(2)
            # Step 3: Pre-flight Alembic.
            self._begin(3)
            self._preflight_alembic()
            self._end(3)
            # Step 4: Kill API subprocess.
            self._begin(4)
            self._managers.kill_api()
            self._end(4)
            # Step 5: Kill MCP subprocess.
            self._begin(5)
            self._managers.kill_mcp()
            self._end(5)
            # Step 6: Write current_engagement.json atomically.
            self._begin(6)
            self._write_current_file()
            self._end(6)
            # Step 7: Update in-memory ActiveEngagementContext.
            self._begin(7)
            self._update_in_memory_context()
            self._end(7)
            # Step 8: Launch new API subprocess.
            self._begin(8)
            db_path = engagement_db_path(self._target.engagement_code)
            self._managers.launch_api(db_path)
            self._end(8)
            # Step 9: Launch new MCP subprocess.
            self._begin(9)
            self._managers.launch_mcp(db_path)
            self._end(9)
            # Step 10: PATCH engagement_last_opened_at via new API. Per
            # the q6 amendment this is the deferred former-step-7. Logged
            # but does NOT abort activation on failure (idempotent; next
            # switch retries).
            self._begin(10)
            try:
                now = datetime.now(UTC).isoformat()
                self._client.patch_engagement(
                    self._target.engagement_identifier,
                    {"engagement_last_opened_at": now},
                )
            except Exception as exc:  # noqa: BLE001 — best-effort
                _log.warning(
                    "PATCH engagement_last_opened_at failed: %s "
                    "(non-fatal, will retry on next activation)",
                    exc,
                )
            self._end(10)
            # Step 11: Re-emit signal for clean post-activation refresh.
            self._begin(11)
            if self._active_context is not None and hasattr(
                self._active_context, "set_engagement"
            ):
                self._active_context.set_engagement(self._target)
            self._end(11)
            # Step 12: UI restore.
            self._begin(12)
            self._end(12)
            self.completed.emit(self._target)
        except _StepFailure as failure:
            self._rollback()
            self.step_failed.emit(
                failure.step, STEP_DESCRIPTIONS[failure.step - 1], failure.message
            )
            self.failed.emit(self._previous, failure.message)
        except Exception as exc:  # noqa: BLE001 — defensive
            _log.exception("ActivationWorker hit unexpected exception")
            self._rollback()
            self.failed.emit(self._previous, f"Unexpected error: {exc}")

    # ------------------------------------------------------------------
    # Per-step helpers
    # ------------------------------------------------------------------

    def _begin(self, step: int) -> None:
        self.step_started.emit(step, STEP_DESCRIPTIONS[step - 1])

    def _end(self, step: int) -> None:
        self.step_completed.emit(step, STEP_DESCRIPTIONS[step - 1])

    def _reachability_check(self) -> None:
        identifier = self._target.engagement_identifier
        if self._target.engagement_deleted_at is not None:
            raise _StepFailure(
                2,
                f"Engagement {identifier} is soft-deleted; cannot activate.",
            )
        db_path = engagement_db_path(self._target.engagement_code)
        if not db_path.exists() or not os.access(db_path, os.R_OK):
            raise _StepFailure(
                2,
                "Engagement record references file at "
                f"{db_path} that does not exist or is not readable",
            )

    def _preflight_alembic(self) -> None:
        try:
            run_engagement_migrations(self._target.engagement_code)
        except MigrationError as exc:
            raise _StepFailure(3, f"Migration failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 — defensive
            raise _StepFailure(3, f"Migration failed: {exc}") from exc

    def _write_current_file(self) -> None:
        if self._write_current_engagement is None:
            # Default: route through ActiveEngagementContext so the
            # write semantics stay consistent.
            if self._active_context is None:
                raise _StepFailure(
                    6,
                    "no active_context and no write_current_engagement hook",
                )
            previous = self._active_context.engagement()
            try:
                self._active_context.set_engagement(self._target)
                self._active_context.persist_to_disk()
                self._current_file_written = True
            except Exception as exc:  # noqa: BLE001 — capture for rollback
                # Restore previous in-memory state so rollback doesn't
                # leave the context pointing at a half-activated target.
                self._active_context.set_engagement(previous)
                raise _StepFailure(
                    6, f"Failed to write current_engagement.json: {exc}"
                ) from exc
            return
        try:
            self._write_current_engagement(self._target)
            self._current_file_written = True
        except Exception as exc:  # noqa: BLE001 — capture for rollback
            raise _StepFailure(
                6, f"Failed to write current_engagement.json: {exc}"
            ) from exc

    def _update_in_memory_context(self) -> None:
        # When _write_current_file routed through the default
        # active_context.persist_to_disk path it already called
        # set_engagement; flag for the rollback path.
        if self._active_context is None:
            return
        if self._active_context.engagement() != self._target:
            self._active_context.set_engagement(self._target)
        self._context_updated = True

    def _rollback(self) -> None:
        """Restore in-memory and persisted state to the previous engagement."""
        if self._active_context is None:
            return
        try:
            if self._context_updated or self._current_file_written:
                self._active_context.set_engagement(self._previous)
            if self._rollback_current_engagement is not None:
                self._rollback_current_engagement(self._previous)
            elif self._current_file_written:
                if self._previous is not None:
                    self._active_context.persist_to_disk()
                else:
                    self._active_context.clear_disk()
        except Exception:  # noqa: BLE001 — best-effort rollback
            _log.exception("Rollback of in-memory context failed")


class _StepFailure(Exception):
    """Internal helper carrying step+message for typed control flow."""

    def __init__(self, step: int, message: str) -> None:
        super().__init__(message)
        self.step = step
        self.message = message


# ---------------------------------------------------------------------------
# Thread wrapper
# ---------------------------------------------------------------------------


def run_activation_in_thread(
    worker: ActivationWorker,
    *,
    parent: QObject | None = None,
) -> QThread:
    """Move ``worker`` to a fresh QThread and start it.

    Returns the QThread; caller must keep a reference until ``finished``
    fires (or the worker's ``completed`` / ``failed`` signal handles
    teardown). The thread auto-quits when the worker emits its terminal
    signal.
    """
    thread = QThread(parent)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.completed.connect(thread.quit)
    worker.failed.connect(thread.quit)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return thread


# ---------------------------------------------------------------------------
# Default subprocess manager built on ServerLifecycle
# ---------------------------------------------------------------------------


def build_lifecycle_managers(lifecycle) -> SubprocessManagers:
    """Build a :class:`SubprocessManagers` bundle from a ``ServerLifecycle``.

    The MCP hooks are no-ops in v0.5 because the v2 MCP server is stdio-
    based and not yet under desktop-side process control. Slice D's
    architecture leaves the placeholder explicit so a future MCP
    lifecycle (post-PI-017) can swap in without touching the worker.
    """

    def _kill_api() -> None:
        lifecycle.terminate()

    def _kill_mcp() -> None:
        # No MCP process under desktop control in v0.5; the user runs
        # the MCP server out-of-process when needed.
        return None

    def _launch_api(db_path: Path) -> None:
        # Set the env var the new spawn reads so the new API binds to
        # the activated engagement's DB.
        os.environ["CRMBUILDER_V2_DB_PATH"] = str(db_path)
        lifecycle.start()
        _poll_api_health(lifecycle, deadline_seconds=_API_HEALTH_TOTAL_TIMEOUT)

    def _launch_mcp(_db_path: Path) -> None:
        return None

    return SubprocessManagers(
        kill_api=_kill_api,
        kill_mcp=_kill_mcp,
        launch_api=_launch_api,
        launch_mcp=_launch_mcp,
    )


def _poll_api_health(
    lifecycle, *, deadline_seconds: float
) -> None:
    """Poll lifecycle until ready or until ``deadline_seconds`` elapses.

    The lifecycle's own readiness polling is QTimer-driven, so we just
    spin briefly while it runs. In practice the lifecycle's QTimer ticks
    fire as soon as we yield, and the deadline mostly serves as a
    failsafe. Raises ``RuntimeError`` on timeout.
    """
    deadline = time.monotonic() + deadline_seconds
    delay = _API_HEALTH_INITIAL_DELAY
    base_url = getattr(lifecycle, "_base_url", None) or "http://127.0.0.1:8765"
    while time.monotonic() < deadline:
        if default_api_health_probe(base_url):
            return
        time.sleep(min(delay, _API_HEALTH_MAX_DELAY))
        delay = min(delay * 2, _API_HEALTH_MAX_DELAY)
    raise RuntimeError(
        f"API health-check did not respond within {deadline_seconds:.0f}s"
    )

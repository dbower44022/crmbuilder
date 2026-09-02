"""The audit-run worker — PI-448 (REQ-551 / DEC-994).

Claims queued (or stale-heartbeat) audit runs and executes the area's
reconciler off any request thread, in the :class:`DeployWorker` shape: the
API's lifespan starts :meth:`AuditRunWorker.start` as a daemon thread when
``Settings.audit_run_worker_inprocess`` is on. A client disconnect therefore
cannot stop a run or sever its completion-time deposit event — the failure
mode that left a stray empty deposit event when the utilization area ran
inside one long HTTP request.

Claims are cross-engagement (enforcement off, no active engagement); the run
executes inside its own engagement scope. A heartbeat thread keeps the claim
fresh through the long record scan; a worker that dies mid-run leaves a stale
heartbeat and the next worker reclaims the run, which restarts profiling —
safe, because evidence lands only at completion.
"""

from __future__ import annotations

import logging
import threading
import time

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.engagement_scope import active_engagement, enforcement
from crmbuilder_v2.access.exceptions import ConflictError
from crmbuilder_v2.access.repositories import audit_runs
from crmbuilder_v2.config import get_settings
from crmbuilder_v2.deploy.worker import default_worker_id

_log = logging.getLogger("crmbuilder_v2.introspect.audit_run_worker")


def run_audit_run(identifier: str, *, engagement_id: str, worker_id: str) -> str:
    """Execute one claimed audit run to a terminal status; return it.

    The instance credentials resolve through the same gate the audit
    endpoints use (imported lazily — the API layer imports introspect, so a
    module-level import here would be a cycle). Progress lines and counters
    are written through their own short sessions, the deploy-heartbeat
    precedent; the reconciler keeps one session for its work-list read and
    its completion-time writes, exactly as the synchronous endpoint did.
    """
    from crmbuilder_v2.api.routers.instances import _audit_introspection_client
    from crmbuilder_v2.introspect.utilization import reconcile_utilization

    with active_engagement(engagement_id):
        with session_scope() as s:
            run = audit_runs.get_audit_run(s, identifier)
        if run is None:  # pragma: no cover - claim just returned it
            return "failed"
        instance_identifier = run["instance_identifier"]

        def note(message: str, level: str = "info") -> None:
            with session_scope() as s:
                audit_runs.append_log(s, identifier, [[level, message]])

        def counts(done: int, total: int) -> None:
            with session_scope() as s:
                audit_runs.set_progress(
                    s, identifier, {"entities_done": done, "entities_total": total}
                )

        try:
            client = _audit_introspection_client(instance_identifier)
        except Exception as exc:
            with session_scope() as s:
                audit_runs.finish(s, identifier, status="failed", error=str(exc))
            return "failed"

        try:
            with session_scope() as s:
                summary = reconcile_utilization(
                    s,
                    instance_identifier=instance_identifier,
                    client=client,
                    progress=note,
                    counters=counts,
                )
        except Exception as exc:
            _log.exception("audit run %s failed", identifier)
            with session_scope() as s:
                audit_runs.finish(s, identifier, status="failed", error=str(exc))
            return "failed"

        # A full abort before any entity completed is a failed run (the
        # deposit event already says outcome=failure); a partial abort is a
        # succeeded run whose summary carries the aborted flag (DEC-994).
        failed = bool(summary.get("aborted")) and not summary.get("entities")
        status = "failed" if failed else "succeeded"
        with session_scope() as s:
            audit_runs.finish(
                s,
                identifier,
                status=status,
                summary=summary,
                error="profiling aborted before any entity completed"
                if failed
                else None,
            )
        return status


class AuditRunWorker:
    """Poll → claim → run loop; :meth:`run_once` is the unit tests drive."""

    def __init__(
        self,
        *,
        worker_id: str | None = None,
        poll_seconds: int | None = None,
        heartbeat_seconds: int | None = None,
        stale_seconds: int | None = None,
    ) -> None:
        settings = get_settings()
        self.worker_id = worker_id or default_worker_id("audit")
        self.poll_seconds = poll_seconds or settings.audit_run_worker_poll_seconds
        self.heartbeat_seconds = (
            heartbeat_seconds or settings.audit_run_worker_heartbeat_seconds
        )
        self.stale_seconds = stale_seconds or settings.audit_run_worker_stale_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_poll_at: float | None = None
        self.current_run: str | None = None

    # -- lifecycle --------------------------------------------------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name=f"audit-run-worker[{self.worker_id}]", daemon=True
        )
        self._thread.start()
        _log.info("audit-run worker %s started", self.worker_id)

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)
        _log.info("audit-run worker %s stopped", self.worker_id)

    @property
    def alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                ran = self.run_once()
            except Exception:  # keep the loop alive; the run itself is recorded
                _log.exception("audit-run worker %s: poll failed", self.worker_id)
                ran = False
            if not ran:
                self._stop.wait(self.poll_seconds)

    # -- one claim --------------------------------------------------------

    def run_once(self) -> bool:
        """Claim and execute at most one run; return whether one ran."""
        self.last_poll_at = time.time()
        with enforcement(False), active_engagement(None), session_scope() as s:
            claimed = audit_runs.claim_next_run(
                s, worker_id=self.worker_id, stale_after_seconds=self.stale_seconds
            )
        if claimed is None:
            return False
        identifier = claimed["audit_run_identifier"]
        engagement_id = claimed["engagement_id"]
        self.current_run = identifier
        _log.info(
            "audit-run worker %s: running %s (%s)",
            self.worker_id, identifier, engagement_id,
        )
        stop_hb = threading.Event()
        hb = threading.Thread(
            target=self._heartbeat_loop,
            args=(identifier, engagement_id, stop_hb),
            name=f"audit-run-heartbeat[{identifier}]",
            daemon=True,
        )
        hb.start()
        try:
            status = run_audit_run(
                identifier, engagement_id=engagement_id, worker_id=self.worker_id
            )
            _log.info(
                "audit-run worker %s: %s finished %s",
                self.worker_id, identifier, status,
            )
        finally:
            stop_hb.set()
            hb.join(2.0)
            self.current_run = None
        return True

    def _heartbeat_loop(
        self, identifier: str, engagement_id: str, stop: threading.Event
    ) -> None:
        while not stop.wait(self.heartbeat_seconds):
            try:
                with active_engagement(engagement_id), session_scope() as s:
                    audit_runs.heartbeat(s, identifier, worker_id=self.worker_id)
            except ConflictError as exc:
                _log.warning(
                    "audit-run worker %s lost %s: %s", self.worker_id, identifier, exc
                )
                return
            except Exception:  # pragma: no cover - transient DB trouble
                _log.exception("heartbeat for %s failed", identifier)

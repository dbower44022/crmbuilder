"""The deploy worker — PI-419 (REQ-522, DEC-945).

Claims queued (or stale-heartbeat) deploy runs and executes them through
:func:`crmbuilder_v2.deploy.runner.run_deploy`. One class, two homes:

* **in-process** — the API's lifespan starts :meth:`DeployWorker.start` as a
  daemon thread when ``Settings.deploy_worker_inprocess`` is on (the default:
  nothing new to operate on the droplet);
* **standalone** — ``crmbuilder-v2-deploy-worker`` runs :func:`main`, the same
  loop in its own process, for when phases outgrow the API's restart cadence.

Claims are cross-engagement (enforcement off, no active engagement), then the
run executes inside its own engagement scope. A heartbeat thread keeps the
claim fresh through long, quiet SSH phases; a worker that dies mid-run leaves
a stale heartbeat and the next worker reclaims and resumes.
"""

from __future__ import annotations

import logging
import os
import socket
import threading
import time

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.engagement_scope import active_engagement, enforcement
from crmbuilder_v2.access.exceptions import ConflictError
from crmbuilder_v2.access.repositories import deploy_runs
from crmbuilder_v2.config import get_settings
from crmbuilder_v2.deploy.runner import RunnerDeps, run_deploy

_log = logging.getLogger("crmbuilder_v2.deploy.worker")


def default_worker_id(kind: str = "api") -> str:
    return f"{kind}:{socket.gethostname()}:{os.getpid()}"


class DeployWorker:
    """Poll → claim → run loop; :meth:`run_once` is the unit tests drive."""

    def __init__(
        self,
        *,
        worker_id: str | None = None,
        poll_seconds: int | None = None,
        heartbeat_seconds: int | None = None,
        stale_seconds: int | None = None,
        deps: RunnerDeps | None = None,
    ) -> None:
        settings = get_settings()
        self.worker_id = worker_id or default_worker_id()
        self.poll_seconds = poll_seconds or settings.deploy_worker_poll_seconds
        self.heartbeat_seconds = heartbeat_seconds or settings.deploy_worker_heartbeat_seconds
        self.stale_seconds = stale_seconds or settings.deploy_worker_stale_seconds
        self._deps = deps
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
            target=self._loop, name=f"deploy-worker[{self.worker_id}]", daemon=True
        )
        self._thread.start()
        _log.info("deploy worker %s started", self.worker_id)

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)
        _log.info("deploy worker %s stopped", self.worker_id)

    @property
    def alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                ran = self.run_once()
            except Exception:  # keep the loop alive; the run itself is recorded
                _log.exception("deploy worker %s: poll failed", self.worker_id)
                ran = False
            if not ran:
                self._stop.wait(self.poll_seconds)

    # -- one claim ----------------------------------------------------------

    def run_once(self) -> bool:
        """Claim and execute at most one run; return whether one ran."""
        self.last_poll_at = time.time()
        with enforcement(False), active_engagement(None), session_scope() as s:
            claimed = deploy_runs.claim_next_run(
                s, worker_id=self.worker_id, stale_after_seconds=self.stale_seconds
            )
        if claimed is None:
            return False
        identifier = claimed["deploy_run_identifier"]
        engagement_id = claimed["engagement_id"]
        self.current_run = identifier
        _log.info("deploy worker %s: running %s (%s)", self.worker_id, identifier, engagement_id)
        stop_hb = threading.Event()
        hb = threading.Thread(
            target=self._heartbeat_loop,
            args=(identifier, engagement_id, stop_hb),
            name=f"deploy-heartbeat[{identifier}]",
            daemon=True,
        )
        hb.start()
        try:
            status = run_deploy(
                identifier,
                engagement_id=engagement_id,
                worker_id=self.worker_id,
                deps=self._deps,
            )
            _log.info("deploy worker %s: %s finished %s", self.worker_id, identifier, status)
        finally:
            stop_hb.set()
            hb.join(2.0)
            self.current_run = None
        return True

    def _heartbeat_loop(self, identifier: str, engagement_id: str, stop: threading.Event) -> None:
        while not stop.wait(self.heartbeat_seconds):
            try:
                with active_engagement(engagement_id), session_scope() as s:
                    deploy_runs.heartbeat(s, identifier, worker_id=self.worker_id)
            except ConflictError as exc:
                _log.warning("deploy worker %s lost %s: %s", self.worker_id, identifier, exc)
                return
            except Exception:  # pragma: no cover - transient DB trouble
                _log.exception("heartbeat for %s failed", identifier)


def main() -> None:
    """``crmbuilder-v2-deploy-worker`` — run the loop standalone until interrupted."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="crmbuilder-v2-deploy-worker",
        description=(
            "Execute queued deploy runs. Set CRMBUILDER_V2_DEPLOY_WORKER_INPROCESS="
            "false on the API when running this so two workers do not compete."
        ),
    )
    parser.add_argument("--once", action="store_true", help="Run at most one claim and exit.")
    parser.add_argument("--worker-id", default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    worker = DeployWorker(worker_id=args.worker_id or default_worker_id("cli"))
    if args.once:
        ran = worker.run_once()
        print("ran one deploy run" if ran else "nothing queued")
        return
    worker.start()
    try:
        while worker.alive:
            time.sleep(1)
    except KeyboardInterrupt:
        worker.stop()

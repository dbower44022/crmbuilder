"""Release Scheduler monitor — scan frozen releases and drive each, single-occupancy.

PI-259 / PRJ-041 / REQ-298 (target-model §3). The single-release scheduler
(``release_scheduler.ReleaseScheduler``) is pointed at *one* release; this monitor
scans for **frozen** releases (past the freeze gate, not terminal) and drives each
end-to-end, honoring the single development lane:

* Front-half releases (``reconciliation`` / ``architecture_planning``) are driven
  *without* the dev lane, so they advance to their next human-review pause and park
  at ``ready`` — they never contend for the lane.
* At most one release occupies the lane (``development`` → ``deployment``) at a time.
  The monitor only ever enables the dev lane for that single driver per pass, so it
  complements the existing single-occupancy *gate*
  (``releases._check_single_occupancy`` + ``uq_releases_one_in_lane``) and never
  double-dispatches.

When several ``ready`` releases compete for a free lane, the monitor admits the one
with the strictly-lowest ``release_lane_order`` and raises ``needs_human`` (rather than
guess) on a tie, or when a competing candidate has no order at all.

Layering: this lives in the scheduler and may import the scheduler + access; the access
layer must not import it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.vocab import RELEASE_LANE_STATUSES

# A release is "frozen" once it is past the freeze gate (reconciliation onward) and
# not in a terminal state.
_PRE_FREEZE = frozenset({"preliminary_planning", "development_planning"})
_TERMINAL = frozenset({"shipped", "cancelled", "superseded"})
_FRONT_HALF = frozenset({"reconciliation", "architecture_planning"})


def arbitrate_lane(ready: list[dict]) -> tuple[str | None, str | None]:
    """Which ``ready`` release should enter a free lane — strictly by lane order.

    ``ready`` items are ``{"identifier", "lane_order"}`` dicts. Returns
    ``(driver_identifier, None)`` when the choice is unambiguous, else
    ``(None, reason)`` when the monitor must defer to a human rather than guess: a tie
    at the lowest order, or a competing candidate with no order. A single uncontested
    candidate is admitted even without an order (there is nothing to disambiguate).
    """
    if not ready:
        return (None, None)
    if len(ready) == 1:
        return (ready[0]["identifier"], None)
    if any(r["lane_order"] is None for r in ready):
        return (
            None,
            "a competing ready release has no lane_order — set lane orders to "
            "disambiguate which enters the lane first",
        )
    ordered = sorted(ready, key=lambda r: r["lane_order"])
    if ordered[0]["lane_order"] == ordered[1]["lane_order"]:
        return (
            None,
            f"two or more ready releases tie at the lowest lane_order "
            f"({ordered[0]['lane_order']}) — break the tie to disambiguate",
        )
    return (ordered[0]["identifier"], None)


@dataclass
class MonitorReport:
    """The outcome of one monitor pass."""

    driven: list[dict] = field(default_factory=list)
    lane_driver: str | None = None
    waiting: list[str] = field(default_factory=list)
    needs_human: str | None = None
    errors: list[dict] = field(default_factory=list)


def _scan(session) -> dict:
    """Partition the live, frozen, non-terminal releases the monitor acts on."""
    from crmbuilder_v2.access.repositories import releases

    rows = releases.list_releases(session)
    frozen = [
        r
        for r in rows
        if r["release_status"] not in _PRE_FREEZE
        and r["release_status"] not in _TERMINAL
    ]
    return {
        "lane": [r for r in frozen if r["release_status"] in RELEASE_LANE_STATUSES],
        "front": [r for r in frozen if r["release_status"] in _FRONT_HALF],
        "ready": [
            {
                "identifier": r["release_identifier"],
                "lane_order": r["release_lane_order"],
            }
            for r in frozen
            if r["release_status"] == "ready"
        ],
    }


def monitor_once(
    drive: Callable[[str, bool], object],
    *,
    log: Callable[[str], None] = print,
) -> MonitorReport:
    """Run one monitor pass.

    ``drive(release_identifier, dev_lane)`` runs one release through the scheduler:
    ``dev_lane=True`` drives the development lane (the single occupant), ``False`` stops
    at ``ready`` (front-half advancement). It should return a ``ReleaseRunReport``-like
    object exposing ``final_status`` / ``stopped_reason``. A driver that raises (e.g. a
    single-occupancy / ``blocked_by`` gate conflict) is recorded, not propagated, so one
    release cannot crash the whole pass.
    """
    report = MonitorReport()
    with session_scope() as s:
        scan = _scan(s)

    # 1. Pick the single lane driver: the current occupant if any, else arbitrate the
    #    ready candidates for the free lane.
    if scan["lane"]:
        report.lane_driver = scan["lane"][0]["release_identifier"]
    else:
        report.lane_driver, report.needs_human = arbitrate_lane(scan["ready"])
        if report.needs_human:
            log(f"[monitor] lane arbitration needs a human: {report.needs_human}")

    report.waiting = [
        r["identifier"] for r in scan["ready"] if r["identifier"] != report.lane_driver
    ]

    # 2. Drive front-half releases (no dev lane) + the single lane driver (dev lane).
    to_drive: list[tuple[str, bool]] = [
        (r["release_identifier"], False) for r in scan["front"]
    ]
    if report.lane_driver:
        to_drive.append((report.lane_driver, True))

    for rid, dev_lane in to_drive:
        try:
            rep = drive(rid, dev_lane)
            report.driven.append(
                {
                    "release": rid,
                    "dev_lane": dev_lane,
                    "final_status": getattr(rep, "final_status", None),
                    "stopped_reason": getattr(rep, "stopped_reason", None),
                }
            )
        except Exception as exc:  # noqa: BLE001 — a gate conflict must not crash the pass
            log(f"[monitor] driving {rid} stopped: {exc}")
            report.errors.append({"release": rid, "error": str(exc)})

    return report


def _real_drive(args) -> Callable[[str, bool], object]:
    """The live driver seam: build a real ReleaseScheduler run per release."""
    from crmbuilder_v2.scheduler.release_scheduler import (
        ReleaseScheduler,
        ReleaseSchedulerConfig,
        ado_pi_runner,
        anthropic_providers,
    )

    demands_provider, decomposition_provider = anthropic_providers()

    def drive(release_identifier: str, dev_lane: bool):
        pi_runner = (
            ado_pi_runner(
                repo_root=args.repo_root,
                base_branch=args.base_branch,
                max_concurrent=args.max_concurrent,
                engagement=args.engagement,
            )
            if dev_lane
            else None
        )
        gate_runner = None
        if dev_lane and not args.manual_gates:
            from crmbuilder_v2.scheduler.release_gate import anthropic_gate_runner

            gate_runner = anthropic_gate_runner()
        return ReleaseScheduler(
            ReleaseSchedulerConfig(
                release_identifier=release_identifier,
                demands_provider=demands_provider,
                decomposition_provider=decomposition_provider,
                authored_by=args.authored_by,
                max_steps=args.max_steps,
                pi_runner=pi_runner,
                gate_runner=gate_runner,
            )
        ).run()

    return drive


def main(argv: list[str] | None = None) -> int:
    """CLI: one monitor pass over the frozen releases. Drives front-half releases to
    their next human-review pause and the single arbitrated release through the lane.
    """
    import argparse
    import json

    parser = argparse.ArgumentParser(
        prog="crmbuilder-v2-release-monitor",
        description="Scan frozen releases and drive each, honoring single-occupancy.",
    )
    parser.add_argument("--authored-by", default="AGP-release-planning")
    parser.add_argument("--max-steps", type=int, default=24)
    parser.add_argument(
        "--manual-gates",
        action="store_true",
        help="pause at the release QA/test gates for a human instead of the LLM judge",
    )
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--base-branch", default="main")
    parser.add_argument("--max-concurrent", type=int, default=2)
    parser.add_argument("--engagement", default="CRMBUILDER")
    args = parser.parse_args(argv)

    report = monitor_once(_real_drive(args))
    print(
        json.dumps(
            {
                "lane_driver": report.lane_driver,
                "driven": report.driven,
                "waiting": report.waiting,
                "needs_human": report.needs_human,
                "errors": report.errors,
            },
            indent=2,
        )
    )
    return 0

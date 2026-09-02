"""Unattended read-only conformance check — PI-410 (REQ-492/493/494/500).

A single non-interactive entry point answering whether an instance matches the
design, precisely enough to gate a deploy. Driven by arguments and environment,
reading only the instance being checked and writing nothing to it. Reuses the
proven unattended plumbing of ``crmbuilder-v2-publish-check``: the same env
resolution, the same headless credential story (the service resolves instance
secrets; no keyring, display, or operator workstation is ever needed).

**What a run does (live mode, the default).** It refreshes the audit —
``POST /instances/{id}/audit`` reads the live instance and records what it
holds; read-only toward the target — then evaluates the declared compared set
over those fresh readings (``GET /instances/{id}/conformance``). REQ-500's
rule is structural here: an unattended check reads the instance rather than
reusing a stored verdict. ``--stored`` evaluates the store as it stands
(surfaces and tests); the result names its ``run_mode`` either way.

**The result is the JSON on stdout** — instance identity, design version,
run mode, counts by outcome, one entry per compared attribute with construct,
attribute, outcome and reason, and when each reading was taken. Human
narration goes to stderr. Exit statuses a gate can consume without prose
(REQ-493 / DEC-923):

* 0 — conformant (or a blocking result explicitly overridden, see below)
* 1 — drifted
* 2 — unable to be checked, or the check could not run at all
* 3 — named-but-unwritable (the only differences have no write path)

**Override (REQ-494).** ``--use-override`` lets one recorded operator
authorization allow one deploy past a blocking result: the run consumes the
oldest unspent override for the instance, reports WHO authorized it, when and
why inside the result, and exits 0 — while ``status`` keeps the true verdict,
which is never altered. The authorization is spent by that run; the next run
reports the same outcome as if none had been granted.

Usage::

    crmbuilder-v2-conformance-check --instance INST-001 --engagement ENG-002
    crmbuilder-v2-conformance-check --instance INST-001 --stored
    crmbuilder-v2-conformance-check --instance INST-001 --use-override
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from crmbuilder_v2.publish.check import CheckError, _Api, _settings

EXIT_CONFORMANT = 0
EXIT_DRIFTED = 1
EXIT_UNCHECKABLE = 2
EXIT_UNWRITABLE = 3

_STATUS_EXIT = {
    "conformant": EXIT_CONFORMANT,
    "drifted": EXIT_DRIFTED,
    "unable_to_be_checked": EXIT_UNCHECKABLE,
    "named_but_unwritable": EXIT_UNWRITABLE,
}


def run_check(
    *,
    instance: str,
    engagement: str,
    base_url: str | None,
    env_file: str,
    stored: bool = False,
    use_override: bool = False,
    out=sys.stdout,
    err=sys.stderr,
) -> int:
    """Run the conformance check. Returns the gate's exit code."""
    try:
        url, token = _settings(base_url, env_file)
        api = _Api(url, token, engagement)
        print(
            f"conformance check: {instance} ({engagement}) via {url}",
            file=err,
        )

        if not stored:
            # REQ-500: read the instance, never a stored verdict. The audit
            # reads the live target (read-only toward it) and records what it
            # holds; a failed read is "unable to be checked", not a crash.
            try:
                api.post(f"/instances/{instance}/audit")
            except CheckError as exc:
                result = {
                    "instance": instance,
                    "run_mode": "live",
                    "status": "unable_to_be_checked",
                    "reason": f"the instance could not be read: {exc}",
                    "counts": None,
                    "entries": [],
                }
                print(json.dumps(result, indent=2), file=out)
                return EXIT_UNCHECKABLE

        result = api.get(f"/instances/{instance}/conformance")
        assert isinstance(result, dict)
        result["run_mode"] = "stored" if stored else "live"
    except CheckError as exc:
        result = {
            "instance": instance,
            "run_mode": "stored" if stored else "live",
            "status": "unable_to_be_checked",
            "reason": f"the check could not run: {exc}",
            "counts": None,
            "entries": [],
        }
        print(json.dumps(result, indent=2), file=out)
        print(f"CANNOT RUN: {exc}", file=err)
        return EXIT_UNCHECKABLE

    status = result.get("status")
    exit_code = _STATUS_EXIT.get(status, EXIT_UNCHECKABLE)
    print(
        f"  status: {status}; counts: {result.get('counts')}", file=err
    )

    if exit_code != EXIT_CONFORMANT and use_override:
        # REQ-494: one recorded authorization lets one deploy proceed. The
        # verdict above is never altered — only the exit the gate consumes.
        try:
            override = api.post(
                f"/instances/{instance}/conformance-overrides/consume"
            )
            result["override"] = override
            print(
                "  blocking result overridden for this deploy by "
                f"{override.get('authorized_by')!r}: {override.get('reason')}",
                file=err,
            )
            exit_code = EXIT_CONFORMANT
        except CheckError:
            print("  no unspent override recorded; verdict stands", file=err)

    print(json.dumps(result, indent=2), file=out)
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crmbuilder-v2-conformance-check",
        description=(
            "Unattended read-only conformance check: does this instance match "
            "the declared design? Writes nothing to the target; emits a "
            "machine-readable result and a gate-consumable exit status."
        ),
    )
    parser.add_argument("--instance", required=True)
    parser.add_argument("--engagement", default="ENG-002")
    parser.add_argument("--base-url", default=None)
    parser.add_argument(
        "--env-file",
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)
            ))),
            "data",
            "crmbuilder.env",
        ),
    )
    parser.add_argument(
        "--stored",
        action="store_true",
        help=(
            "evaluate the store's existing readings without re-reading the "
            "instance (the unattended default reads live, per REQ-500)"
        ),
    )
    parser.add_argument(
        "--use-override",
        action="store_true",
        help=(
            "allow one recorded operator authorization to let this deploy "
            "proceed past a blocking result (REQ-494); the verdict itself "
            "is never altered"
        ),
    )
    args = parser.parse_args(argv)
    return run_check(
        instance=args.instance,
        engagement=args.engagement,
        base_url=args.base_url,
        env_file=args.env_file,
        stored=args.stored,
        use_override=args.use_override,
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

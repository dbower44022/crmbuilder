"""Live publish check — REQ-483 / PI-404.

The hermetic layer (``tests/crmbuilder_v2/publish/test_publish_e2e_check.py``)
proves the publish path composes correctly. It cannot prove that *this
deployment* can publish, and the two defects that cost the most in August 2026
were properties of the deployment rather than of the code:

* the hosted service had no keyring backend, so an instance's credentials could
  not be resolved there at all (REQ-481);
* that same host runs with authentication enabled and holds no credential of its
  own, so the service calling its own API was rejected (REQ-482).

Neither reproduces anywhere else. This check runs against the real service and
exercises the path end to end **without writing to the target**: a validate-only
publish generates the design, resolves the target's credentials, reads the live
target, and validates — everything up to the write.

**It asserts what was generated, not that the run finished.** The third defect
produced a green run with hollow output: every field lost its parent entity, so
the programs carried no fields, and the response was indistinguishable from a
healthy one because the number of programs follows the count of confirmed
entities regardless. So the check reads the design in the same run and requires
the generated programs to account for it, field by field.

Every expectation is derived at run time. The design is filtered to ``confirmed``
records and moves as the engagement progresses — hard-coding a count would make
this a tripwire for ordinary design work rather than for regressions.

Usage::

    crmbuilder-v2-publish-check                      # INST-001 under ENG-002
    crmbuilder-v2-publish-check --instance INST-003 --engagement ENG-004
    crmbuilder-v2-publish-check --base-url http://127.0.0.1:8765

Exits 0 when the publish path is healthy, 1 when it is not, 2 when the check
could not run (no credentials, service unreachable).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib import error as urllib_error
from urllib import request as urllib_request

#: The engagement whose design is published, and the instance it goes to.
DEFAULT_ENGAGEMENT = "ENG-002"
DEFAULT_INSTANCE = "INST-001"

#: Instances this check must never touch. Validate-only writes nothing, but a
#: flag flipped by accident on a production target is not a risk worth carrying
#: for a check whose whole purpose is to run unattended. Refusing by name is a
#: guard the operator cannot forget (DEC-915).
FORBIDDEN_INSTANCES = frozenset({"INST-002"})

EXIT_OK, EXIT_FAILED, EXIT_CANNOT_RUN = 0, 1, 2


class CheckError(RuntimeError):
    """The check could not run — distinct from the check finding a problem.

    The distinction is the point. A check that shouts "failed" when it merely
    could not reach the service teaches the operator to ignore it, and an
    ignored check is worth less than none.
    """


def assert_census_available(result: dict) -> None:
    """Refuse to judge a response that predates the per-program census.

    A service running code from before this requirement returns programs with no
    ``entities`` or ``field_names`` keys. Read naively that is zero fields
    generated — precisely the signature of the defect this check exists to
    catch — so an un-deployed service would report the catastrophe on every run
    and the check would be disbelieved within a day. It is a *cannot run*.
    """
    programs = result.get("programs", [])
    if programs and not any("field_names" in p for p in programs):
        raise CheckError(
            "this service predates the per-program census (REQ-483): its "
            "publish response carries no field_names, so the check cannot tell "
            "a healthy run from one that generated nothing. Deploy the current "
            "code and re-run."
        )


def _load_env_file(path: str) -> dict[str, str]:
    """Read ``KEY=value`` lines from the service environment file, if present."""
    values: dict[str, str] = {}
    if not os.path.exists(path):
        return values
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip("'\"")
    return values


def _settings(base_url: str | None, env_file: str) -> tuple[str, str | None]:
    """Resolve the API base URL and token: real environment first, file second."""
    from_file = _load_env_file(env_file)
    url = (
        base_url
        or os.environ.get("CRMBUILDER_V2_API_BASE_URL")
        or from_file.get("CRMBUILDER_V2_API_BASE_URL")
    )
    token = os.environ.get("CRMBUILDER_V2_API_TOKEN") or from_file.get(
        "CRMBUILDER_V2_API_TOKEN"
    )
    if not url:
        raise CheckError(
            "no API base URL: pass --base-url, or set "
            f"CRMBUILDER_V2_API_BASE_URL in the environment or {env_file}"
        )
    return url.rstrip("/"), token


class _Api:
    """Minimal authenticated client for the checks below."""

    def __init__(self, base_url: str, token: str | None, engagement: str) -> None:
        self.base_url = base_url
        self.token = token
        self.engagement = engagement

    def _call(self, path: str, *, method: str = "GET") -> dict:
        req = urllib_request.Request(f"{self.base_url}{path}", method=method)
        req.add_header("X-Engagement", self.engagement)
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        if method == "POST":
            req.add_header("Content-Type", "application/json")
            req.data = b"{}"
        try:
            with urllib_request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise CheckError(f"{method} {path} -> HTTP {exc.code}: {body}") from exc
        except urllib_error.URLError as exc:
            raise CheckError(f"{method} {path} -> unreachable: {exc.reason}") from exc

    def get(self, path: str) -> list | dict:
        payload = self._call(path)
        if payload.get("errors"):
            raise CheckError(f"GET {path} -> {payload['errors']}")
        return payload["data"]

    def post(self, path: str) -> dict:
        payload = self._call(path, method="POST")
        if payload.get("errors"):
            raise CheckError(f"POST {path} -> {payload['errors']}")
        return payload["data"]


def read_expected_design(api: _Api) -> dict:
    """What the design says the publish should produce, read live.

    Only ``confirmed`` records are generated, and a field reaches a program only
    if its parent entity is confirmed too — so the expectation is the join, not
    either list alone.

    :returns: ``{entities: {name: [field names]}, association_count: int}``.
    """
    # LSN-011: list endpoints ignore offset; ask for one large page.
    entities = api.get("/entities?limit=5000")
    fields = api.get("/fields?limit=5000")
    refs = api.get(
        "/references?source_type=field"
        "&relationship_kind=field_belongs_to_entity&limit=20000"
    )
    associations = api.get("/associations?limit=5000")

    confirmed_entities = {
        e["entity_identifier"]: e["entity_name"]
        for e in entities
        if e.get("entity_status") == "confirmed"
    }
    parent_of = {r["source_id"]: r["target_id"] for r in refs}

    expected: dict[str, list[str]] = {name: [] for name in confirmed_entities.values()}
    for row in fields:
        if row.get("field_status") != "confirmed":
            continue
        parent = parent_of.get(row["field_identifier"])
        if parent in confirmed_entities:
            expected[confirmed_entities[parent]].append(row["field_name"])

    return {
        "entities": expected,
        "association_count": sum(
            1 for a in associations if a.get("association_status") == "confirmed"
        ),
    }


#: Deferral kinds that mean a whole field was not emitted. The other
#: ``field_*`` kinds (``field_attribute``, ``field_rule``, ``field_permission``,
#: ``field_visibility``) defer an *attribute* of a field that was emitted, and
#: must not be counted against the census.
_UNEMITTED_FIELD_KINDS = frozenset(
    {"reference_field", "derived_field", "unmapped_field", "foreign_field"}
)


def _unemitted_field_count(result: dict) -> int:
    """Fields the adapter deliberately did not emit, from the run's deferrals.

    A shortfall the adapter announced is design working as intended; only an
    unannounced one is a regression.
    """
    return len(
        {
            d.get("identifier")
            for d in result.get("deferrals", [])
            if d.get("kind") in _UNEMITTED_FIELD_KINDS
            and str(d.get("identifier", "")).startswith("FLD-")
        }
    )


def evaluate(
    result: dict, expected: dict, runs_before: int, runs_after: int
) -> list[str]:
    """Compare a publish-validate result against the design. Returns failures.

    Compares **counts**, not names: the design holds business names
    (``application_status``) while a program holds what the adapter emitted
    (``applicationStatus``, or an override-pinned internal name). Mapping one to
    the other here would duplicate the adapter's naming rules and turn this into
    a test of that duplicate. The census answers the question that matters — did
    the fields arrive at all — and a legitimate shortfall is one the run
    announced as a deferral.

    Pure: no I/O, so the judgement is testable without a live service.
    """
    failures: list[str] = []

    if result.get("aborted"):
        failures.append(f"publish aborted: {result.get('abort_reason')}")
    if result.get("validation_failed"):
        for program in result.get("programs", []):
            for error in program.get("validation_errors", []):
                failures.append(f"{program['filename']}: {error}")

    # Nothing may have been written. This is what makes the check safe to point
    # at a live instance, so it is asserted rather than assumed.
    if not result.get("validate_only"):
        failures.append("run was not validate-only — it may have written")
    for program in result.get("programs", []):
        if program.get("deployed"):
            failures.append(f"{program['filename']} was deployed by a validate run")
    if result.get("backup_captured"):
        failures.append("a validate run captured a backup")
    if result.get("verification") is not None:
        failures.append("a validate run ran post-publish verification")
    if runs_after != runs_before:
        failures.append(
            f"publish_runs changed {runs_before} -> {runs_after}; "
            "a validate run must record nothing"
        )

    # The census. A design whose field-to-entity edges went missing still
    # generates one program per confirmed entity and still validates clean —
    # this is the only assertion that separates that from a healthy run.
    # Accumulate rather than assign: one entity may be declared by more than one
    # program (a native entity extended by several domain files is the v1
    # pattern), and overwriting would undercount it into a false failure.
    generated: dict[str, list[str]] = {}
    for program in result.get("programs", []):
        for name in program.get("entities", []):
            generated.setdefault(name, []).extend(program.get("field_names", []))

    want_entities = set(expected["entities"])
    missing_entities = want_entities - set(generated)
    if missing_entities:
        failures.append(
            f"confirmed entities generated no program: {sorted(missing_entities)}"
        )

    want_total = sum(len(v) for v in expected["entities"].values())
    got_total = sum(len(v) for v in generated.values())
    deferred = _unemitted_field_count(result)

    if want_total and not got_total:
        failures.append(
            f"the design has {want_total} confirmed fields and the publish "
            "generated none — this is what losing every field's parent entity "
            "looks like, and the run is otherwise green (REQ-483)"
        )
    elif got_total + deferred < want_total:
        short = {
            name: len(fields) - len(generated.get(name, []))
            for name, fields in expected["entities"].items()
            if len(generated.get(name, [])) < len(fields)
        }
        failures.append(
            f"generated {got_total} fields and deferred {deferred}, but the "
            f"design has {want_total} confirmed — {want_total - got_total - deferred} "
            f"went missing without being announced; short by entity: {short}"
        )

    return failures


def run_check(
    *,
    instance: str,
    engagement: str,
    base_url: str | None,
    env_file: str,
    out=sys.stdout,
) -> int:
    """Run the live publish check. Returns the process exit code."""
    if instance in FORBIDDEN_INSTANCES:
        print(
            f"refusing to check {instance}: it is a production target and this "
            "check is never pointed at one (DEC-915)",
            file=sys.stderr,
        )
        return EXIT_CANNOT_RUN

    try:
        url, token = _settings(base_url, env_file)
        api = _Api(url, token, engagement)

        print(f"publish check: {instance} ({engagement}) via {url}", file=out)
        expected = read_expected_design(api)
        want_total = sum(len(v) for v in expected["entities"].values())
        print(
            f"  design: {len(expected['entities'])} confirmed entities, "
            f"{want_total} confirmed fields, "
            f"{expected['association_count']} confirmed associations",
            file=out,
        )

        runs_before = len(api.get("/publish-runs?limit=5000"))
        result = api.post(f"/instances/{instance}/publish-validate")
        runs_after = len(api.get("/publish-runs?limit=5000"))
        assert_census_available(result)
    except CheckError as exc:
        print(f"CANNOT RUN: {exc}", file=sys.stderr)
        return EXIT_CANNOT_RUN

    got_total = sum(len(p.get("field_names", [])) for p in result.get("programs", []))
    print(
        f"  generated: {len(result.get('programs', []))} programs, "
        f"{got_total} fields, "
        f"{sum(p.get('relationship_count', 0) for p in result.get('programs', []))} "
        "relationships",
        file=out,
    )

    failures = evaluate(result, expected, runs_before, runs_after)
    if failures:
        print(f"\nFAILED ({len(failures)}):", file=out)
        for failure in failures:
            print(f"  - {failure}", file=out)
        return EXIT_FAILED

    print("  nothing written to the target; publish path healthy", file=out)
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crmbuilder-v2-publish-check",
        description=(
            "Validate-only publish against a live instance, asserting what was "
            "generated. Writes nothing to the target."
        ),
    )
    parser.add_argument("--instance", default=DEFAULT_INSTANCE)
    parser.add_argument("--engagement", default=DEFAULT_ENGAGEMENT)
    parser.add_argument(
        "--base-url",
        default=None,
        help="override the API base URL (default: the service environment)",
    )
    parser.add_argument(
        "--env-file",
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            ))),
            "data",
            "crmbuilder.env",
        ),
        help="environment file to read the base URL and token from",
    )
    args = parser.parse_args(argv)
    return run_check(
        instance=args.instance,
        engagement=args.engagement,
        base_url=args.base_url,
        env_file=args.env_file,
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

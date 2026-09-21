"""The catalogue of kinds of work, version 0.1 (PI-488 / REQ-569, DEC-1060).

The nine kinds of work from the phase-specific governance plan's Part 6, in
the shape Gate 2 ruled: each is a process record belonging to the lifecycle
domain where a request of that kind enters, its steps field carrying the
ordered phase segments (each naming a lifecycle domain and a phase profile —
by identifier where the profile exists, by planned area and marked *pending*
where it does not) and its triggers field carrying the recognition phrases.

Run as a module to write or refresh the catalogue in a store over the API::

    python -m crmbuilder_v2.kind_of_work_catalogue --base-url URL --token TOKEN

Idempotent by entry name: an existing entry has its steps and triggers
refreshed; a missing one is created. Stdlib-only so it runs anywhere the hooks
run. The domain identifiers below are the lifecycle domains DOM-004..DOM-010
and the cross-cutting DOM-012; the profile identifiers are the two phase
profiles Step 2 created (AGP-039 Requirements Interviewer, AGP-040 Release
Operator). Solution Designer, Application Developer and Maintainer do not
exist yet (plan Steps 5 and 6), so their segments are pending.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

from crmbuilder_v2.access.repositories.session_opening import catalogue_steps_block

DOM = {
    "project_definition": "DOM-004",
    "requirements_capture": "DOM-005",
    "specification_and_approval": "DOM-006",
    "solution_analysis": "DOM-007",
    "development_and_sandbox": "DOM-008",
    "release_to_production": "DOM-009",
    "feedback_and_upgrades": "DOM-010",
    "governance_recording": "DOM-012",
}
REQUIREMENTS_INTERVIEWER = "AGP-039"
RELEASE_OPERATOR = "AGP-040"


def _seg(domain: str, *, profile: str | None, area: str, label: str) -> dict:
    return {
        "domain": DOM[domain],
        "profile": profile,
        "area": area,
        "label": label,
        "status": "active" if profile else "pending",
    }


def interviewer(domain: str = "requirements_capture") -> dict:
    return _seg(domain, profile=REQUIREMENTS_INTERVIEWER, area="requirements-capture",
                label="Requirements Interviewer")


def designer() -> dict:
    return _seg("specification_and_approval", profile=None, area="solution-design",
                label="Solution Designer")


def developer() -> dict:
    return _seg("development_and_sandbox", profile=None, area="application-development",
                label="Application Developer")


def operator() -> dict:
    return _seg("release_to_production", profile=RELEASE_OPERATOR, area="release-to-production",
                label="Release Operator")


def maintainer() -> dict:
    return _seg("feedback_and_upgrades", profile=None, area="maintenance", label="Maintainer")


def _numbered(segments: list[dict]) -> list[dict]:
    return [{"position": i, **s} for i, s in enumerate(segments, start=1)]


#: (name, entry domain, purpose, segments, trigger phrases, notes)
CATALOGUE: list[dict] = [
    {
        "name": "Start working with a new organisation",
        "domain": "project_definition",
        "purpose": "Establish who a new client organisation is and what it wants from the engagement, before any process is captured (plan Phase 0 and Phase 1).",
        "segments": [interviewer("project_definition")],
        "phrases": ["start working with a new organisation", "start working with a new organization",
                 "new organisation", "new organization", "new client", "onboard a new client",
                 "set up a new engagement", "kick off an engagement", "project definition"],
        "notes": "Requirements Interviewer only; Project Definition stays inside that profile in the first version (plan Part 10).",
    },
    {
        "name": "Define new business processes",
        "domain": "requirements_capture",
        "purpose": "Capture one or more business processes an organisation runs, one conversation each, and carry the confirmed inventory into a design.",
        "segments": [interviewer(), designer()],
        "phrases": ["define new business processes", "define a business process", "define business processes",
                 "new business process", "capture requirements", "requirements interview",
                 "interview a stakeholder", "describe how we do", "document our process"],
        "notes": "Requirements Interviewer, then Solution Designer (pending until Step 6).",
    },
    {
        "name": "Describe a system you already use",
        "domain": "requirements_capture",
        "purpose": "Baseline a system the organisation already runs so its data, screens and processes are known before anything new is designed (plan Phase 1.5).",
        "segments": [interviewer()],
        "phrases": ["describe a system you already use", "describe our current system", "system we already use",
                 "existing system", "baseline the current crm", "what we use today", "audit the current system",
                 "document the existing system"],
        "notes": "Requirements Interviewer only.",
    },
    {
        "name": "Add or change a field or screen in an existing application",
        "domain": "feedback_and_upgrades",
        "purpose": "Take a change request against a running application from intake through a short requirements step, a design change, a build, a sandbox check and a release.",
        "segments": [maintainer(), interviewer(), designer(), developer(), operator()],
        "phrases": ["add or change a field or screen", "add a field", "change a field", "add a screen",
                 "change a screen", "add a field to", "new field on", "change the layout", "modify the form",
                 "add a column", "existing application", "intake screen"],
        "notes": "Maintainer intake first (pending until Step 5), then a short Requirements Interviewer segment where the purpose of the change is captured as a requirement, then Solution Designer, Application Developer (both pending) and Release Operator.",
    },
    {
        "name": "Build a new application or module from approved requirements",
        "domain": "specification_and_approval",
        "purpose": "Design, build and release a new application or module whose requirements are already confirmed.",
        "segments": [designer(), developer(), operator()],
        "phrases": ["build a new application", "build a new module", "build from approved requirements",
                 "new application from requirements", "implement the approved design", "build the app",
                 "develop the module", "start the build"],
        "notes": "Solution Designer and Application Developer are pending until Steps 5 and 6; Release Operator exists.",
    },
    {
        "name": "Upgrade the platform to the latest version",
        "domain": "release_to_production",
        "purpose": "Take a running CRM instance to a newer platform version through the in-place upgrader, with backup and verification.",
        "segments": [operator()],
        "phrases": ["upgrade the platform", "upgrade to the latest version", "upgrade espocrm", "platform upgrade",
                 "upgrade the crm", "update to the latest release", "apply the upgrade"],
        "notes": "Release Operator only.",
    },
    {
        "name": "Fix something that is not working",
        "domain": "feedback_and_upgrades",
        "purpose": "Take a defect report through intake and impact check, then a fix in the build or in the release, depending on what the intake finds.",
        "segments": [maintainer(), developer(), operator()],
        "phrases": ["fix something that is not working", "something is not working", "fix a bug", "is broken",
                 "not working", "fix the", "error when", "stopped working", "defect"],
        "notes": "Maintainer intake first (pending until Step 5); the intake decides whether the fix is a build (Application Developer, pending) or a release step (Release Operator). Both segments are listed; the intake may skip one.",
    },
    {
        "name": "Review what has been delivered",
        "domain": "specification_and_approval",
        "purpose": "Review a design or a running system against what was agreed, recording acceptance or the changes needed.",
        "segments": [designer()],
        "phrases": ["review what has been delivered", "review the delivery", "review the design", "stakeholder review",
                 "acceptance review", "check what was delivered", "walk through what was built", "review the release"],
        "notes": "Solution Designer (stakeholder review segment, pending until Step 6) when the thing reviewed is a design; a review of a running system enters through the Maintainer in a later catalogue version.",
    },
    {
        "name": "Ask a question about the system or its records",
        "domain": "governance_recording",
        "purpose": "Answer a question about CRMBuilder, an engagement, or the records in the store, without entering any phase.",
        "segments": [],
        "phrases": ["ask a question", "question about the system", "question about the records", "what is",
                 "what does", "how does", "look up", "show me", "explain", "where is", "tell me about"],
        "notes": "No phase profile; the cross-cutting rules only.",
    },
]


def entries_as_process_bodies() -> list[dict]:
    """The nine catalogue entries as POST /processes bodies (steps and
    triggers rendered), in plan order."""
    bodies = []
    for e in CATALOGUE:
        bodies.append(
            {
                "process_name": e["name"],
                "process_domain_identifier": DOM[e["domain"]],
                "process_purpose": e["purpose"],
                "process_classification": "supporting",
                "process_notes": (
                    "Kind of work (catalogue of kinds of work, version 0.1; PI-488 / REQ-569, DEC-1060). "
                    + e["notes"]
                ),
                "process_steps": catalogue_steps_block(_numbered(e["segments"])),
                "process_triggers": json.dumps(e["phrases"], indent=2),
            }
        )
    return bodies


# --- writing to a store over the API ------------------------------------------


def _call(base: str, token: str, engagement: str, method: str, path: str, body=None):
    req = urllib.request.Request(
        base.rstrip("/") + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {token}" if token else "",
            "X-Engagement": engagement,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            envelope = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"{method} {path}: HTTP {exc.code} {exc.read().decode()[:300]}") from exc
    if envelope.get("errors"):
        raise RuntimeError(f"{method} {path}: {envelope['errors']}")
    return envelope.get("data")


def write_catalogue(base: str, token: str, engagement: str = "ENG-001") -> list[tuple[str, str, str]]:
    """Create or refresh the nine entries. Returns ``(action, identifier, name)`` rows."""
    existing = {p["process_name"]: p for p in _call(base, token, engagement, "GET", "/processes")}
    rows = []
    for body in entries_as_process_bodies():
        name = body["process_name"]
        if name in existing:
            pid = existing[name]["process_identifier"]
            patch = {k: body[k] for k in ("process_purpose", "process_notes", "process_steps", "process_triggers")}
            _call(base, token, engagement, "PATCH", f"/processes/{pid}", patch)
            rows.append(("refreshed", pid, name))
        else:
            created = _call(base, token, engagement, "POST", "/processes", body)
            rows.append(("created", created["process_identifier"], name))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the catalogue of kinds of work to a store.")
    parser.add_argument("--base-url", default=os.environ.get("CRMBUILDER_V2_API_BASE_URL", ""))
    parser.add_argument("--token", default=os.environ.get("CRMBUILDER_V2_API_TOKEN", ""))
    parser.add_argument("--engagement", default="ENG-001")
    args = parser.parse_args(argv)
    if not args.base_url:
        parser.error("--base-url (or CRMBUILDER_V2_API_BASE_URL) is required")
    for action, pid, name in write_catalogue(args.base_url, args.token, args.engagement):
        print(f"{action:9} {pid}  {name}")
    opening = _call(args.base_url, args.token, args.engagement, "GET", "/sessions/opening")
    print(f"catalogue now lists {len(opening['catalogue'])} kinds of work")
    return 0


if __name__ == "__main__":
    sys.exit(main())

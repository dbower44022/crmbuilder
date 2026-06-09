#!/usr/bin/env python3
"""Stand up an isolated sandbox for ADO end-to-end testing.

End-to-end runs spawn **real** Claude agents that make real commits and mutate the
governance DB, so everything is isolated:

* a throwaway **test engagement** (default code ``ADOTEST``) — identifiers are
  per-engagement, so the test PI/Workstreams/Work Tasks never touch CRMBUILDER's
  real backlog;
* a throwaway **git repo** (default ``/tmp/ado-e2e``) — the agents' commits and the
  runtime's merges land there, never in the crmbuilder repo.

Each run creates a **fresh** project + one small ``storage`` Planning Item (storage
is the only area with seeded registry contracts — AGP-001/002 — so it exercises the
real resolver path, not the minimal fallback), decomposes it, and scopes the Design
phase with one trivial, safe, verifiable Work Task. The engagement and repo are
reused across runs. Then it prints a runbook tailored to the ids it created.

Usage::

    uv run python crmbuilder-v2/scripts/seed_ado_e2e.py
    uv run python crmbuilder-v2/scripts/seed_ado_e2e.py --repo /tmp/ado-e2e --start-design

``--start-design`` also starts the Design phase so its Work Task is ``Ready`` — use it
for the smallest rung (one real agent on one Work Task via the Layer-1 runtime). For
the full-driver rung, omit it (the driver starts the phase itself).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_API = "http://127.0.0.1:8765"
ENG_CODE = "ADOTEST"
AREA = "storage"  # the area with seeded registry contracts (AGP-001/002)


def api(method: str, base: str, path: str, *, engagement: str | None = None, body: dict | None = None):
    """Call the V2 API and unwrap the {data, meta, errors} envelope."""
    headers = {"Content-Type": "application/json"}
    if engagement:
        headers["X-Engagement"] = engagement
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base.rstrip("/") + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode()
        raise SystemExit(f"API {method} {path} failed ({e.code}): {detail}") from e
    if payload.get("errors"):
        raise SystemExit(f"API {method} {path} returned errors: {payload['errors']}")
    return payload.get("data")


# --------------------------------------------------------------------------
# engagement + repo (reused across runs)
# --------------------------------------------------------------------------


def ensure_engagement(base: str) -> str:
    existing = api("GET", base, "/engagements") or []
    for e in existing:
        if (e.get("engagement_code") or "").upper() == ENG_CODE:
            print(f"• engagement {ENG_CODE} exists ({e.get('engagement_identifier')})")
            return ENG_CODE
    api("POST", base, "/engagements", body={
        "engagement_code": ENG_CODE,
        "engagement_name": "ADO E2E Sandbox",
        "engagement_purpose": "Isolated sandbox for ADO orchestration end-to-end testing.",
        "engagement_status": "active",
    })
    print(f"• created engagement {ENG_CODE}")
    return ENG_CODE


def ensure_repo(repo: Path) -> None:
    if (repo / ".git").is_dir():
        print(f"• repo {repo} exists")
        return
    repo.mkdir(parents=True, exist_ok=True)

    def git(*args):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)

    git("init", "-q")
    git("symbolic-ref", "HEAD", "refs/heads/main")
    (repo / "README.md").write_text("# ADO end-to-end sandbox\n\nThrowaway repo. Agents commit here.\n")
    git("add", "-A")
    git("-c", "user.email=ado@e2e.local", "-c", "user.name=ADO E2E", "commit", "-q", "-m", "seed: initial commit")
    print(f"• created throwaway git repo {repo} (branch main, 1 commit)")


# --------------------------------------------------------------------------
# fresh project + PI each run
# --------------------------------------------------------------------------


def make_project(base: str, eng: str) -> str:
    # Project names are unique per engagement — number each fresh run's project.
    existing = api("GET", base, "/projects", engagement=eng) or []
    n = 1 + sum(1 for p in existing if (p.get("project_name") or "").startswith("ADO E2E Test Project"))
    return api("POST", base, "/projects", engagement=eng, body={
        "project_name": f"ADO E2E Test Project {n}",
        "project_purpose": "Exercise the ADO orchestration driver end to end.",
        "project_description": "A throwaway project holding small storage PIs for end-to-end testing.",
        "project_status": "in_flight",
    })["project_identifier"]


def make_pi(base: str, eng: str, prj: str, marker: str, *,
            start_design: bool = False, blocked_by: list[str] | None = None) -> dict:
    """Create one trivial storage PI (decomposed, Design scoped) in ``prj``.

    Its single Work Task creates ``marker`` — distinct per PI so parallel PIs
    merge cleanly. ``blocked_by`` adds dependency edges so the PM holds it until
    those PIs are Resolved.
    """
    pi = api("POST", base, "/planning-items", engagement=eng, body={
        "title": f"Add the marker file {marker}",
        "item_type": "pending_work",
        "status": "Draft",
        "description": (
            f"Create a single small marker file `{marker}` in the repo root containing "
            f"one line, then commit it. No other changes. Proves one PI runs end to end."
        ),
        "executive_summary": (
            f"A deliberately trivial storage Planning Item that exercises the ADO orchestration "
            f"driver end to end with real agents. Its only deliverable is the marker file "
            f"`{marker}` created and committed in the throwaway sandbox repo, so the run is fast, "
            f"safe, and easy to verify by eye. It validates the scope -> reconcile -> build -> "
            f"review loop and helps tune the real-agent prompts; it carries no product value and "
            f"lives in the isolated ADOTEST engagement so it never touches the CRMBUILDER backlog."
        ),
    })["identifier"]

    api("POST", base, "/references", engagement=eng, body={
        "source_type": "planning_item", "source_id": pi,
        "target_type": "project", "target_id": prj,
        "relationship": "planning_item_belongs_to_project",
    })
    for blocker in blocked_by or []:
        api("POST", base, "/references", engagement=eng, body={
            "source_type": "planning_item", "source_id": pi,
            "target_type": "planning_item", "target_id": blocker,
            "relationship": "blocked_by",
        })

    api("POST", base, f"/planning-items/{pi}/decompose", engagement=eng)
    overview = api("GET", base, f"/planning-items/{pi}/phase-overview", engagement=eng)
    phases = {p["phase_type"]: p["workstream"]["workstream_identifier"] for p in overview["phases"]}
    design = phases["Design"]

    scoped = api("POST", base, f"/workstreams/{design}/scope", engagement=eng, body={
        "work_tasks": [{
            "title": f"Create the marker file {marker}",
            "area": AREA,
            "description": (
                f"In the repository root, create a file named `{marker}` whose entire "
                f"contents are the single line: `ADO end-to-end proof`. That is the whole "
                f"task. Commit it. Do not touch anything else."
            ),
        }],
    })
    wtk = scoped["work_tasks"][0]["work_task_identifier"]

    if start_design:
        api("POST", base, f"/workstreams/{design}/start-execution", engagement=eng)

    return {"project": prj, "pi": pi, "phases": phases, "work_task": wtk, "marker": marker}


def seed_single(base: str, eng: str, start_design: bool) -> dict:
    prj = make_project(base, eng)
    return make_pi(base, eng, prj, "ado-e2e-proof.txt", start_design=start_design)


def seed_fanout(base: str, eng: str) -> dict:
    """One project, two independent PIs + one dependent (blocked_by both)."""
    prj = make_project(base, eng)
    a = make_pi(base, eng, prj, "ado-e2e-proof-A.txt")
    b = make_pi(base, eng, prj, "ado-e2e-proof-B.txt")
    c = make_pi(base, eng, prj, "ado-e2e-proof-C.txt", blocked_by=[a["pi"], b["pi"]])
    return {"project": prj, "pis": [a, b, c]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api-base", default=DEFAULT_API)
    ap.add_argument("--repo", default="/tmp/ado-e2e", help="throwaway git repo path")
    ap.add_argument("--start-design", action="store_true",
                    help="start the Design phase so its Work Task is Ready (for the Layer-1 single-agent rung)")
    ap.add_argument("--fanout", action="store_true",
                    help="seed a project with 2 independent PIs + 1 dependent (for the PM fan-out rung)")
    args = ap.parse_args()
    base, repo = args.api_base, Path(args.repo)

    print("Standing up the ADO end-to-end sandbox …")
    eng = ensure_engagement(base)
    ensure_repo(repo)
    h = f'-H "X-Engagement: {eng}"'

    if args.fanout:
        f = seed_fanout(base, eng)
        a, b, c = f["pis"]
        print(f"\n  engagement : {eng}")
        print(f"  repo       : {repo}")
        print(f"  project    : {f['project']}")
        print(f"  independent: {a['pi']} ({a['marker']}), {b['pi']} ({b['marker']})")
        print(f"  dependent  : {c['pi']} ({c['marker']}, blocked_by {a['pi']} + {b['pi']})")
        print("\n── Runbook ──\n")
        print("Rung 5 — PM fan-out: two PIs built in parallel, reviewed + resolved,")
        print("then the dependent unblocks and runs:")
        print(f"  uv run crmbuilder-v2-ado-pm {f['project']} --engagement {eng} \\")
        print(f"      --repo-root {repo} --base-branch main --max-parallel-pis 2 --review-on-complete\n")
        print("Watch / verify:")
        print(f"  curl -s {h} {base}/projects/{f['project']}/backlog | python3 -m json.tool")
        print(f"  git -C {repo} log --oneline --graph --all")
        return 0

    s = seed_single(base, eng, args.start_design)
    print(f"\n  engagement : {eng}")
    print(f"  repo       : {repo}")
    print(f"  project    : {s['project']}")
    print(f"  planning   : {s['pi']}  (Design={s['phases']['Design']}, "
          f"Develop={s['phases']['Develop']}, Test={s['phases']['Test']})")
    print(f"  work task  : {s['work_task']}  (area=storage, {'Ready' if args.start_design else 'Planned'})")

    print("\n── Runbook (each command sends the test engagement header / repo) ──\n")
    if args.start_design:
        print("Rung 2 — one real agent on one Work Task (Layer 1), smallest test:")
        print(f"  uv run crmbuilder-v2-runtime --work-task {s['work_task']} --engagement {eng} \\")
        print(f"      --repo-root {repo} --base-branch main --tier developer\n")
    else:
        print("Rung 4 — full driver: one PI scoped→reconciled→built→In Review:")
        print(f"  uv run crmbuilder-v2-ado {s['pi']} --engagement {eng} --repo-root {repo} --base-branch main\n")
        print("  (re-run with --start-design for Rung 2, or --fanout for the Rung-5 PM fan-out)\n")
    print("Watch / verify:")
    print(f"  curl -s {h} {base}/planning-items/{s['pi']}/phase-overview | python3 -m json.tool")
    print(f"  curl -s {h} {base}/findings        # did reconcile raise any?")
    print(f"  git -C {repo} log --oneline --graph --all")
    print("\nNote: every spawned agent is a real `claude -p` session with bypassPermissions,")
    print("scoped to the throwaway worktree. The engagement + repo keep it isolated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

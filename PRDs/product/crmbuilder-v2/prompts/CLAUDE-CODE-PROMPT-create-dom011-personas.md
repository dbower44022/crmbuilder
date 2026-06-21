# Create DOM-011 Software Delivery Personas
**Operating mode:** DETAIL — pure execution, no design decisions.
**Engagement:** CRMBUILDER
**Repo:** dbower44022/crmbuilder

---

## Purpose

Create seven Persona records in the CRMBUILDER engagement database representing the agent roles that participate in the Release Pipeline process (PROC-009) under the Software Delivery domain (DOM-011). These personas formalize the agent system as a methodology artifact, consistent with how CBM personas are defined.

**Net effect:** 7 new PER-NNN records posted via the V2 API.

---

## Pre-flight

1. Confirm API is running and routed to CRMBUILDER:
```bash
curl -s http://127.0.0.1:8765/admin/connection | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['engagement_code'])"
```
Expected: `CRMBUILDER`. If not, switch engagement via the desktop UI before proceeding.

2. Confirm DOM-011 exists:
```bash
curl -s http://127.0.0.1:8765/domains -H "X-Engagement: CRMBUILDER" | python3 -c "import sys,json; doms=[d for d in json.load(sys.stdin)['data'] if d['domain_identifier']=='DOM-011']; print(doms[0]['domain_name'] if doms else 'NOT FOUND')"
```
Expected: `Software Delivery`. Do not proceed if not found.

3. Confirm PROC-009 exists:
```bash
curl -s http://127.0.0.1:8765/processes -H "X-Engagement: CRMBUILDER" | python3 -c "import sys,json; procs=[p for p in json.load(sys.stdin)['data'] if p['process_identifier']=='PROC-009']; print(procs[0]['process_name'] if procs else 'NOT FOUND')"
```
Expected: `Release Pipeline`. Do not proceed if not found.

4. Capture the current persona identifier head:
```bash
curl -s http://127.0.0.1:8765/personas -H "X-Engagement: CRMBUILDER" | python3 -c "import sys,json; pers=json.load(sys.stdin)['data']; print('Current head:', sorted([p['persona_identifier'] for p in pers])[-1] if pers else 'none')"
```
Record this — verify advancement after apply.

---

## Apply

Run this script in full. It POSTs all seven personas in order and prints each identifier as it lands. Do not run partially.

```python
import urllib.request
import json

BASE = "http://127.0.0.1:8765"
HEADERS = {
    "Content-Type": "application/json",
    "X-Engagement": "CRMBUILDER"
}

def post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

personas = [
    {
        "persona_name": "Scheduler",
        "persona_role_summary": (
            "The program that drives the release pipeline — starts agents at the right moment, "
            "checks their results, runs the gates, and halts for human input when something needs "
            "attention. Not an agent itself; the infrastructure that spawns and manages agents."
        ),
        "persona_responsibilities": (
            "Walks a frozen release through its pipeline states (reconciliation → architecture "
            "planning → ready → development → QA → test → deployment → shipped) one step at a "
            "time. Spawns the right agent at the right moment. Verifies agent results before "
            "advancing. Runs QA and test gates. Sets needs_attention and halts when a problem "
            "requires human resolution. Merges agent branches into main after verification."
        ),
        "persona_notes": (
            "The Scheduler is not an agent — it carries no 'Agent' suffix and is never spawned "
            "itself. It is the deterministic substrate that manages agents. Implemented across "
            "release_runtime.py, ado_runtime.py, parallel_runtime.py, and coordinating_runtime.py."
        ),
        "persona_status": "confirmed"
    },
    {
        "persona_name": "Reconciliation Agent",
        "persona_role_summary": (
            "The first AI agent in the pipeline. Reads the release's confirmed requirements and "
            "produces a precise, tidy demand-set — the exact data changes needed to satisfy them."
        ),
        "persona_responsibilities": (
            "Receives the full list of confirmed requirements for a release. Produces a structured "
            "demand-set of exact changes (add this field, rename that entity, remove this "
            "relationship). Flags contradictions between requirements rather than quietly resolving "
            "them. Does not persist demands, run conflict detection, or resolve conflicts — those "
            "are the Scheduler's responsibilities."
        ),
        "persona_notes": (
            "Stored in the Agent Profile Registry as AGP-003. Current job card is loose and "
            "advisory — a hardening priority under REQ-278. The job card must accurately describe "
            "only what this agent actually does, not steps performed by the Scheduler."
        ),
        "persona_status": "confirmed"
    },
    {
        "persona_name": "Architect Agent",
        "persona_role_summary": (
            "The second AI agent in the pipeline. Takes the reconciled demand-set and produces the "
            "build plan — decomposing each planning item into Design, Develop, and Test phases with "
            "area-labeled work tasks in dependency order."
        ),
        "persona_responsibilities": (
            "Receives the delta set for each planning item. Produces the complete build plan: three "
            "phases per planning item (Design, Develop, Test), work tasks inside each phase labeled "
            "by area and technology, dependency ordering across tasks, and an acceptance criterion "
            "per task. This is the last judgment step before building starts — the Scheduler and "
            "worker agents execute the plan but do not re-plan."
        ),
        "persona_notes": (
            "Stored in the Agent Profile Registry as AGP-004. The batch unit decision (REQ-283) "
            "means the Architect Agent emits area-phase batches across the whole release, not one "
            "task per planning item. Must emit explicit acceptance criteria per task per REQ-278 "
            "— currently does not."
        ),
        "persona_status": "confirmed"
    },
    {
        "persona_name": "Project Manager Agent",
        "persona_role_summary": (
            "The top-tier agent in the development organization. Looks across all planning items "
            "in a project, identifies the next eligible one, and dispatches it to the PI Lead Agent."
        ),
        "persona_responsibilities": (
            "Monitors planning item statuses within a project. Identifies which planning items are "
            "ready to start (prerequisites met, no blockers). Dispatches the next eligible planning "
            "item to the PI Lead Agent. Does not build anything — purely a coordination and "
            "sequencing role."
        ),
        "persona_notes": (
            "Currently implemented as deterministic substrate (pm.py), not an LLM agent. The ADO "
            "design intends this to eventually be an agent; today it is code. Tier 1 of the "
            "four-tier ADO hierarchy."
        ),
        "persona_status": "confirmed"
    },
    {
        "persona_name": "PI Lead Agent",
        "persona_role_summary": (
            "The team-leader agent for one planning item. Walks it through its phases in order — "
            "Design, then Develop, then Test — gating each phase transition and rolling up problems "
            "for human attention."
        ),
        "persona_responsibilities": (
            "Opens each phase when its predecessor is complete. Declares a phase complete when all "
            "its work tasks are done. Runs the cross-area coherence check between Design and Develop "
            "(currently an implementation gap — the check is confirmed by REQ-027 but not yet "
            "wired). Rolls up needs_attention flags. Advances the planning item to In Review when "
            "all phases are complete."
        ),
        "persona_notes": (
            "Currently implemented as deterministic substrate (lead.py), not an LLM agent. Tier 2 "
            "of the four-tier ADO hierarchy. The coherence check wiring is a confirmed but unbuilt "
            "requirement — a known implementation gap recorded in DEC-556."
        ),
        "persona_status": "confirmed"
    },
    {
        "persona_name": "Developer Agent",
        "persona_role_summary": (
            "The area specialist agent that builds one area's work for a phase across the whole "
            "release. Receives a batch of work tasks for its area, implements them in one session, "
            "commits, and reports."
        ),
        "persona_responsibilities": (
            "Validates inputs before starting — confirms the batch is well-formed, correctly scoped, "
            "and not already built. Implements the assigned work tasks using only the allowed "
            "technology and conventions for its area. Commits before verifying so an interruption "
            "never loses work. Verifies within a time budget. Emits a structured report on exit "
            "(outcome class, files touched, done-condition checked, verification result, commit SHA). "
            "Sets needs_attention and halts if the batch is mis-scoped, duplicate, or missing a "
            "done-condition."
        ),
        "persona_notes": (
            "The current system has only one worker profile (AGP-002, storage/developer) used as a "
            "fallback for all areas — a critical profile gap. Each area and technology variant "
            "requires its own Developer Agent profile with hard technical constraints (REQ-280) and "
            "a technology-specific contract (REQ-281). Tier 4 of the four-tier ADO hierarchy."
        ),
        "persona_status": "confirmed"
    },
    {
        "persona_name": "Tester Agent",
        "persona_role_summary": (
            "The independent verification agent for one area's work. Verifies the Developer Agent's "
            "output against the acceptance criteria without having been involved in writing it, "
            "ensuring an honest check."
        ),
        "persona_responsibilities": (
            "Receives the completed work and the acceptance criteria for each task in the batch. "
            "Verifies each task independently against its done-condition. Reports pass/fail per task "
            "with evidence. Does not modify code — verification only. Sets needs_attention if the "
            "work fails verification or if acceptance criteria are absent or untestable."
        ),
        "persona_notes": (
            "This persona does not yet exist in the built system — it is the target model direction "
            "per Agent-System-Target-Model.md. Currently verification is handled by the Scheduler's "
            "post-agent test run. Creating this record establishes it as a governed design intent "
            "before it is built. No AGP record exists yet."
        ),
        "persona_status": "candidate"
    }
]

print("Creating DOM-011 Software Delivery personas...\n")
created = []
for p in personas:
    result = post("/personas", p)
    identifier = result["data"]["persona_identifier"]
    print(f"  ✓ {identifier} — {p['persona_name']}")
    created.append(identifier)

print(f"\nDone. {len(created)} personas created: {created[0]} through {created[-1]}")
```

Save the script as `/tmp/create_personas.py` and run:
```bash
python3 /tmp/create_personas.py
```

---

## Post-apply verification

1. Confirm all seven landed:
```bash
curl -s http://127.0.0.1:8765/personas -H "X-Engagement: CRMBUILDER" | python3 -c "
import sys, json
pers = json.load(sys.stdin)['data']
dom011 = [p for p in pers if 'Agent' in p['persona_name'] or p['persona_name'] == 'Scheduler']
for p in sorted(dom011, key=lambda x: x['persona_identifier']):
    print(p['persona_identifier'], '|', p['persona_name'], '|', p['persona_status'])
"
```

2. Confirm identifier head advanced by 7 from the pre-flight capture.

3. Spot-check one record in full:
```bash
curl -s http://127.0.0.1:8765/personas/PER-NNN -H "X-Engagement: CRMBUILDER" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin)['data'], indent=2))"
```
Replace PER-NNN with the Tester Agent's identifier. Confirm persona_status is `candidate` (the only one that differs from `confirmed`).

---

## Done

Reply with:
- The identifier range landed (e.g. PER-010 through PER-016)
- Any errors encountered
- Confirmation that the Tester Agent is `candidate` status and all others are `confirmed`

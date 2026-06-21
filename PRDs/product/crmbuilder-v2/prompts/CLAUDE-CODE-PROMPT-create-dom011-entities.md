# Create DOM-011 Software Delivery Entities
**Operating mode:** DETAIL — pure execution, no design decisions.
**Engagement:** CRMBUILDER
**Repo:** dbower44022/crmbuilder

---

## Purpose

Create six Entity records in the CRMBUILDER engagement database representing the data entities used by the Release Pipeline process (PROC-009) under the Software Delivery domain (DOM-011). These records formalize the agent pipeline's data model as a methodology artifact.

**Net effect:** 6 new ENT-NNN records posted via the V2 API.

---

## Pre-flight

1. Confirm API is running and routed to CRMBUILDER:
```bash
curl -s http://127.0.0.1:8765/admin/connection | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['engagement_code'])"
```
Expected: `CRMBUILDER`. Do not proceed if not.

2. Confirm DOM-011 exists:
```bash
curl -s http://127.0.0.1:8765/domains -H "X-Engagement: CRMBUILDER" | python3 -c "import sys,json; doms=[d for d in json.load(sys.stdin)['data'] if d['domain_identifier']=='DOM-011']; print(doms[0]['domain_name'] if doms else 'NOT FOUND')"
```
Expected: `Software Delivery`. Do not proceed if not found.

3. Capture the current entity identifier head:
```bash
curl -s http://127.0.0.1:8765/entities -H "X-Engagement: CRMBUILDER" | python3 -c "import sys,json; ents=json.load(sys.stdin)['data']; print('Current head:', sorted([e['entity_identifier'] for e in ents])[-1] if ents else 'none')"
```
Record this — verify advancement by 6 after apply.

---

## Apply

Run this script in full. It POSTs all six entities in order and prints each identifier as it lands. Do not run partially.

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

entities = [
    {
        "entity_name": "Release",
        "entity_kind": "other",
        "entity_status": "confirmed",
        "entity_description": (
            "A bundle of Planning Items that ship together as one delivery. Carries a pipeline "
            "status (one of 12 states from preliminary_planning through shipped) that the Scheduler "
            "advances. Only one Release may occupy the development lane at a time. The top-level "
            "container for all work in a delivery cycle."
        ),
        "entity_notes": (
            "Identifier prefix REL. Pipeline position stored in a single release_status field — "
            "the Scheduler reads this each tick and drives transitions through a guarded "
            "allowed-transitions map. Releases are never edited after shipping; a correction "
            "becomes a new Release."
        ),
        "entity_track_activity": True
    },
    {
        "entity_name": "Planning Item",
        "entity_kind": "other",
        "entity_status": "confirmed",
        "entity_description": (
            "One unit of work inside a Release — roughly one feature or one requirement's worth "
            "of work to build. Each Planning Item passes through three phases (Design, Develop, "
            "Test) managed by the PI Lead Agent. The primary thing the agent organization builds."
        ),
        "entity_notes": (
            "Identifier prefix PI. Planning Items belong to Projects, which are scoped to "
            "Releases. A Planning Item's lifecycle runs from open through in_review to delivered. "
            "Multiple Planning Items execute in parallel within a Release's development lane."
        ),
        "entity_track_activity": True
    },
    {
        "entity_name": "Workstream",
        "entity_kind": "other",
        "entity_status": "confirmed",
        "entity_description": (
            "The record representing one phase (Design, Develop, or Test) of a Planning Item. "
            "When a Planning Item is decomposed, three Workstream records are created in dependency "
            "order. Work Tasks live inside Workstreams. The PI Lead Agent opens and closes each "
            "Workstream as the Planning Item advances."
        ),
        "entity_notes": (
            "Identifier prefix WSK. Note: the word Workstream was previously used to mean what is "
            "now called a Project — it was recycled. In the current system Workstream always means "
            "a phase container. The phase boundary between Design and Develop is where the "
            "cross-area coherence check runs (REQ-027, currently an implementation gap)."
        ),
        "entity_track_activity": False
    },
    {
        "entity_name": "Work Task",
        "entity_kind": "other",
        "entity_status": "confirmed",
        "entity_description": (
            "The smallest unit of work in the pipeline — one specific piece of work in one area, "
            "sized for a single Developer Agent session. Always belongs to exactly one Workstream "
            "and is labeled with exactly one area. Carries an acceptance criterion written by the "
            "Architect Agent at decomposition time. The Developer Agent claims, implements, and "
            "completes it."
        ),
        "entity_notes": (
            "Identifier prefix WTK. Area label determines which Developer Agent profile handles "
            "the task — if no profile exists for the area/technology combination the task is "
            "refused rather than misrouted (REQ-273). In the target batch model (REQ-283) a "
            "Developer Agent handles all Work Tasks for its area within a phase across the whole "
            "Release in one session."
        ),
        "entity_track_activity": True
    },
    {
        "entity_name": "Finding",
        "entity_kind": "other",
        "entity_status": "confirmed",
        "entity_description": (
            "A record of a discovered problem — typically a clash between two area designs or a "
            "gap in coverage. Findings are the currency of the reconciliation gate between Design "
            "and Develop: the gate checks that no blocking Finding is open before allowing Develop "
            "to start. A blocking Finding halts the pipeline until a human resolves it; an "
            "advisory Finding is a heads-up only."
        ),
        "entity_notes": (
            "Identifier prefix FND. Two severity levels: blocking (halts phase advancement) and "
            "advisory (logged but does not halt). The infrastructure for Findings is built; the "
            "deeper automatic cross-area coherence check that would generate them is largely "
            "aspirational as of the current system state."
        ),
        "entity_track_activity": False
    },
    {
        "entity_name": "Agent Profile",
        "entity_kind": "other",
        "entity_status": "confirmed",
        "entity_description": (
            "A record in the Agent Profile Registry defining one agent type — its job description, "
            "allowed tools and skills, hard governance rules, and accumulated learnings. When the "
            "Scheduler spawns an agent it assembles a contract from the matching Agent Profile. "
            "Each profile covers one area/technology/tier combination. If no matching profile "
            "exists for a Work Task the task is refused rather than misrouted."
        ),
        "entity_notes": (
            "Identifier prefix AGP. Currently only 5 profiles exist (AGP-001 through AGP-005) "
            "covering storage and planning roles — a critical gap. The full target registry needs "
            "one profile per area per technology per tier. Profiles are the methodology home for "
            "REQ-278 (strict documented contracts) and REQ-280 (hard technical constraints per area)."
        ),
        "entity_track_activity": False
    }
]

print("Creating DOM-011 Software Delivery entities...\n")
created = []
for e in entities:
    result = post("/entities", e)
    identifier = result["data"]["entity_identifier"]
    print(f"  \u2713 {identifier} \u2014 {e['entity_name']}")
    created.append(identifier)

print(f"\nDone. {len(created)} entities created: {created[0]} through {created[-1]}")
```

Save as `/tmp/create_entities.py` and run:
```bash
python3 /tmp/create_entities.py
```

---

## Post-apply verification

1. Confirm all six landed:
```bash
curl -s http://127.0.0.1:8765/entities -H "X-Engagement: CRMBUILDER" | python3 -c "
import sys, json
ents = json.load(sys.stdin)['data']
names = {'Release', 'Planning Item', 'Workstream', 'Work Task', 'Finding', 'Agent Profile'}
dom011 = [e for e in ents if e['entity_name'] in names]
for e in sorted(dom011, key=lambda x: x['entity_identifier']):
    print(e['entity_identifier'], '|', e['entity_name'], '|', e['entity_status'], '|', e['entity_kind'])
"
```

2. Confirm identifier head advanced by 6 from the pre-flight capture.

3. Spot-check one record in full:
```bash
curl -s http://127.0.0.1:8765/entities/ENT-NNN -H "X-Engagement: CRMBUILDER" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin)['data'], indent=2))"
```
Replace ENT-NNN with the Agent Profile identifier. Confirm entity_kind is `other` and entity_status is `confirmed`.

---

## Done

Reply with:
- The identifier range landed (e.g. ENT-010 through ENT-015)
- Any errors encountered
- Confirmation that all six show entity_kind `other` and entity_status `confirmed`

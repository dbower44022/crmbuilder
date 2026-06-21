# Link Software Delivery Requirements to DOM-011 and PROC-009
**Operating mode:** DETAIL — pure execution, no design decisions.
**Engagement:** CRMBUILDER
**Repo:** dbower44022/crmbuilder

---

## Purpose

Create `requirement_belongs_to_domain` and `requirement_belongs_to_process` reference links for all requirements under TOP-005 and TOP-099, anchoring them to the Software Delivery domain (DOM-011) and the Release Pipeline process (PROC-009).

**Net effect:** 34 new REF-NNN records posted via the V2 API.
- 17 × `requirement_belongs_to_domain` (REQ → DOM-011)
- 17 × `requirement_belongs_to_process` (REQ → PROC-009)

**Requirements in scope:**
- TOP-005: REQ-014, REQ-252, REQ-258
- TOP-099: REQ-265, REQ-266, REQ-267, REQ-268, REQ-269, REQ-270, REQ-271, REQ-272, REQ-273, REQ-274, REQ-275, REQ-276, REQ-278, REQ-279, REQ-280, REQ-281, REQ-283

Note: REQ-282 is excluded — it was rejected/withdrawn this session.

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

3. Confirm PROC-009 exists:
```bash
curl -s http://127.0.0.1:8765/processes -H "X-Engagement: CRMBUILDER" | python3 -c "import sys,json; procs=[p for p in json.load(sys.stdin)['data'] if p['process_identifier']=='PROC-009']; print(procs[0]['process_name'] if procs else 'NOT FOUND')"
```
Expected: `Release Pipeline`. Do not proceed if not found.

4. Confirm all 17 requirements exist:
```bash
curl -s http://127.0.0.1:8765/requirements -H "X-Engagement: CRMBUILDER" | python3 -c "
import sys, json
reqs = json.load(sys.stdin)['data']
expected = {'REQ-014','REQ-252','REQ-258','REQ-265','REQ-266','REQ-267','REQ-268','REQ-269','REQ-270','REQ-271','REQ-272','REQ-273','REQ-274','REQ-275','REQ-276','REQ-278','REQ-279','REQ-280','REQ-281','REQ-283'}
found = {r['requirement_identifier'] for r in reqs if r['requirement_identifier'] in expected}
missing = expected - found
print('Found:', len(found), '| Missing:', missing if missing else 'none')
"
```
Expected: Found: 17 | Missing: none. Do not proceed if any are missing.

5. Capture current reference head:
```bash
curl -s http://127.0.0.1:8765/references -H "X-Engagement: CRMBUILDER" | python3 -c "import sys,json; refs=json.load(sys.stdin)['data']; print('Current head:', sorted([r['reference_identifier'] for r in refs])[-1] if refs else 'none')"
```
Record this — verify advancement by 34 after apply.

---

## Apply

Run this script in full. It POSTs all 34 references in order and prints each as it lands. Do not run partially.

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

REQUIREMENTS = [
    # TOP-005
    "REQ-014", "REQ-252", "REQ-258",
    # TOP-099
    "REQ-265", "REQ-266", "REQ-267", "REQ-268", "REQ-269", "REQ-270",
    "REQ-271", "REQ-272", "REQ-273", "REQ-274", "REQ-275", "REQ-276",
    "REQ-278", "REQ-279", "REQ-280", "REQ-281", "REQ-283"
]

print("Creating requirement \u2192 domain links...\n")
domain_refs = []
for req in REQUIREMENTS:
    result = post("/references", {
        "source_type": "requirement",
        "source_id": req,
        "target_type": "domain",
        "target_id": "DOM-011",
        "relationship": "requirement_belongs_to_domain"
    })
    ref_id = result["data"]["reference_identifier"]
    print(f"  \u2713 {ref_id} \u2014 {req} \u2192 DOM-011")
    domain_refs.append(ref_id)

print(f"\nCreating requirement \u2192 process links...\n")
process_refs = []
for req in REQUIREMENTS:
    result = post("/references", {
        "source_type": "requirement",
        "source_id": req,
        "target_type": "process",
        "target_id": "PROC-009",
        "relationship": "requirement_belongs_to_process"
    })
    ref_id = result["data"]["reference_identifier"]
    print(f"  \u2713 {ref_id} \u2014 {req} \u2192 PROC-009")
    process_refs.append(ref_id)

print(f"\nDone. {len(domain_refs)} domain links + {len(process_refs)} process links = {len(domain_refs)+len(process_refs)} total references created.")
print(f"Domain refs: {domain_refs[0]} through {domain_refs[-1]}")
print(f"Process refs: {process_refs[0]} through {process_refs[-1]}")
```

Save as `/tmp/link_requirements.py` and run:
```bash
python3 /tmp/link_requirements.py
```

---

## Post-apply verification

1. Confirm domain links landed for all 17 requirements:
```bash
curl -s http://127.0.0.1:8765/references -H "X-Engagement: CRMBUILDER" | python3 -c "
import sys, json
refs = json.load(sys.stdin)['data']
domain_links = [r for r in refs if r['relationship'] == 'requirement_belongs_to_domain' and r['target_id'] == 'DOM-011']
print(f'Domain links to DOM-011: {len(domain_links)} (expected 17)')
for r in sorted(domain_links, key=lambda x: x['source_id']):
    print(' ', r['reference_identifier'], '|', r['source_id'], '\u2192 DOM-011')
"
```

2. Confirm process links landed for all 17 requirements:
```bash
curl -s http://127.0.0.1:8765/references -H "X-Engagement: CRMBUILDER" | python3 -c "
import sys, json
refs = json.load(sys.stdin)['data']
proc_links = [r for r in refs if r['relationship'] == 'requirement_belongs_to_process' and r['target_id'] == 'PROC-009']
print(f'Process links to PROC-009: {len(proc_links)} (expected 17)')
for r in sorted(proc_links, key=lambda x: x['source_id']):
    print(' ', r['reference_identifier'], '|', r['source_id'], '\u2192 PROC-009')
"
```

3. Confirm reference head advanced by 34 from pre-flight capture.

---

## Done

Reply with:
- Total references created (expected 34)
- Domain ref range (first \u2192 last)
- Process ref range (first \u2192 last)
- Any errors encountered

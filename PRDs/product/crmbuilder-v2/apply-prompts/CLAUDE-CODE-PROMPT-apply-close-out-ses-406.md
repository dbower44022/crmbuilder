# CLAUDE-CODE-PROMPT: Apply Close-Out SES-406

Operating mode: DETAIL. Read `CLAUDE.md` at the repository root before doing anything else.

## Purpose

Apply the SES-406 governance close-out to the CRMBUILDER engagement database. SES-406 is the claude.ai session of 09-05-26 that reviewed how governance rules and skills are selected, ruled that they are selected by the work in front of the session, and drafted the phase-specific governance plan.

**Net Effect:**
- 1 session record: SES-406 (phase-specific governance: rules and skills selected by the work in front of the session)
- 1 conversation record: CNV-380
- 3 decision records: DEC-1057 (the session names an agent profile and the system names it from the user's plain-language opening answer), DEC-1058 (the opening answer maps to a kind of work composed of phase segments; five phase profiles hold the rules), DEC-1059 (the seven lifecycle domain records are the phase vocabulary)
- 9 planning item records: PI-486 through PI-492 (the plan's Steps 2 through 7, with Step 2 split into cleanup and build), PI-493 (the four-digit decision identifier defect), PI-494 (approve the plan's four new glossary terms)
- 14 reference records: 3 decided-in (to CNV-380), 9 planning-item-belongs-to-project (PRJ-023), 1 conversation-belongs-to-session, 1 session-belongs-to-project (the last two are hoisted inline by the apply script)
- 1 document committed: `PRDs/product/crmbuilder-v2/phase-governance-plan.md` version 0.1 (already in the repository from the sandbox commit; nothing to do here but confirm it is present)

The identifiers were chosen against the cloud store on 2026-09-05 at 05:15 UTC (heads then: SES-405, CNV-379, DEC-1056, PI-485 — verified by reading each and confirming the next one is absent). If any head has moved by apply time, re-key the payload before applying; the pre-flight below shows the current heads.

**Known defect this prompt works around (PI-493 in this payload).** The decisions repository rejects an explicit identifier unless it has exactly three digits, while the payload validator requires one. Step 1 will therefore report the three decisions and their three decided-in references as failed. Step 2 posts the decisions without identifiers, confirms the server assigned DEC-1057 through DEC-1059, and writes the three references. Do not edit the payload to remove the identifiers — the validator would then refuse it.

---

## Pre-flight

```bash
# 1. Working directory
cd ~/Dropbox/Projects/CRMBuilder
pwd

# 2. Clean status
git status

# 3. Git identity
git config user.name
git config user.email

# 4. Pull rebase
git pull --rebase origin main

# 5. Payload, plan and next-step prompt exist
ls PRDs/product/crmbuilder-v2/close-out-payloads/ses_406.json
ls PRDs/product/crmbuilder-v2/phase-governance-plan.md
ls PRDs/product/crmbuilder-v2/CLAUDE-CODE-PROMPT-pi-486-487-phase-profiles-step-2.md

# 6. API health
curl -s http://127.0.0.1:8765/health -H "X-Engagement: CRMBUILDER"

# 7. Pre-apply identifier heads — every one must be exactly the value shown, or re-key first
for e in sessions conversations decisions planning-items; do
  curl -s "http://127.0.0.1:8765/$e/next-identifier" -H "X-Engagement: CRMBUILDER"; echo
done
# Expected: SES-406, CNV-380, DEC-1057, PI-486
# If the sessions head is not SES-406 the local API is not serving the cloud store — stop and report; do not apply.
```

---

## Apply — step 1, the close-out payload

```bash
uv run python crmbuilder-v2/scripts/apply_close_out.py \
  PRDs/product/crmbuilder-v2/close-out-payloads/ses_406.json \
  --engagement CRMBUILDER
```

**Expected OK record counts:** 1 conversation, 1 session, 9 planning items, 9 references (the project-membership edges), plus the two membership edges written inline with their records.

**Expected failures, by design:** 3 decisions (HTTP 422, identifier must match DEC- and three digits) and 3 decided-in references (their source does not exist yet). Anything else failing is a real problem — stop and report.

## Apply — step 2, the decisions and their references

```bash
uv run python - <<'EOF'
import json, urllib.request
BASE = "http://127.0.0.1:8765"
H = {"Content-Type": "application/json", "X-Engagement": "CRMBUILDER"}
def call(method, path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers=H, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")
payload = json.load(open("PRDs/product/crmbuilder-v2/close-out-payloads/ses_406.json"))
assigned = {}
for dec in payload["decisions"]:
    wanted = dec.pop("identifier")
    status, resp = call("POST", "/decisions", dec)
    got = (resp.get("data") or {}).get("identifier")
    print(f"POST decision wanted {wanted}: HTTP {status} -> {got}")
    if status not in (200, 201):
        print(resp.get("errors") or resp); raise SystemExit(1)
    if got != wanted:
        print(f"ASSIGNED {got}, PAYLOAD SAYS {wanted} — stop; the references below must be re-keyed to {got}")
        raise SystemExit(1)
    assigned[wanted] = got
for ref in payload["references"]:
    if ref["relationship"] != "decided_in":
        continue
    ref["source_id"] = assigned[ref["source_id"]]
    status, resp = call("POST", "/references", ref)
    print(f"POST decided_in {ref['source_id']} -> {ref['target_id']}: HTTP {status}")
    if status not in (200, 201, 409):
        print(resp.get("errors") or resp); raise SystemExit(1)
EOF
```

**Expected:** three `HTTP 201` decision lines each reporting the wanted identifier, then three `HTTP 201` reference lines.

---

## Post-apply verification

```bash
# Heads advanced
for e in sessions conversations decisions planning-items; do
  curl -s "http://127.0.0.1:8765/$e/next-identifier" -H "X-Engagement: CRMBUILDER"; echo
done
# Expected: SES-407, CNV-381, DEC-1060, PI-495

# Spot-check the session and one decision
curl -s "http://127.0.0.1:8765/sessions/SES-406" -H "X-Engagement: CRMBUILDER" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['session_title'])"
curl -s "http://127.0.0.1:8765/decisions/DEC-1058" -H "X-Engagement: CRMBUILDER" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['title'])"

# Decided-in references resolve to the conversation
curl -s "http://127.0.0.1:8765/references?target_type=conversation&target_id=CNV-380" -H "X-Engagement: CRMBUILDER" | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted((r['source_id'], r['relationship']) for r in d))"
# Expected: DEC-1057, DEC-1058, DEC-1059 decided_in

# Reference count delta for the session's project edges
curl -s "http://127.0.0.1:8765/references?target_type=project&target_id=PRJ-023&source_type=planning_item" -H "X-Engagement: CRMBUILDER" | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['source_id'] for r in d if r['source_id'] >= 'PI-486'))"
# Expected: PI-486 .. PI-494
```

---

## Commit snapshots

```bash
git add PRDs/methodology-records/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "v2: governance apply — SES-406 (DEC-1057..1059, PI-486..494, phase-specific governance plan v0.1)

Governed-By: PI-486
Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01VfBU5r5yxJAP6CYrAhRnF5" -- PRDs/methodology-records/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/
git push origin main
```

If the commit gate refuses the Governed-By trailer because PI-486 is not yet visible to it, re-run after the snapshot regeneration completes; the item exists in the store after step 1.

---

## Done

Reply with, and nothing else:
- Heads before and after (SES, CNV, DEC, PI)
- Record counts applied in step 1, and the three decision identifiers confirmed in step 2
- Snapshot commit SHA
- Next conversation kickoff: run `PRDs/product/crmbuilder-v2/CLAUDE-CODE-PROMPT-pi-486-487-phase-profiles-step-2.md` (Step 2 of the phase-specific governance plan: corpus cleanup and the first two phase profiles).

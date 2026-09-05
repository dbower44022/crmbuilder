# CLAUDE-CODE-PROMPT: Apply Close-Out SES-405

## Purpose

Apply the SES-405 governance close-out to the CRMBUILDER engagement database, then create four governance rules and amend two, so the writing standards live in the system.

**Net Effect:**
- 1 session record: SES-405 (application generation test: the Mentor Application against the prototype; writing standards move into the system)
- 1 conversation record: CNV-379
- 3 decision records: DEC-1053 (an AI agent builds the application from the definition), DEC-1054 (the per-process gap register method), DEC-1055 (writing standards become system-scope governance rules)
- 15 planning item records: PI-471 through PI-485 (one per gap in the register, plus the bootstrap tool and the prose check kind)
- 21 reference records: 3 decided-in, 15 planning-item-belongs-to-project (PRJ-023), 1 conversation-belongs-to-session, 1 session-belongs-to-project (hoisted inline by the apply script)
- 4 new governance rules (system scope, audience all, always): plain language for the reader; executive register; terminology precision; reply format
- 2 amended governance rules: GVR-232 (terminology governance) and GVR-237 (approval requests) now say "the product owner" instead of a person's name

The identifiers were chosen against the database on 2026-09-05 at 04:30 UTC (heads then: SES-404, CNV-378, DEC-1052, PI-470). If any head has moved by apply time, re-key the payload before applying; the pre-flight step below shows the current heads.

---

## Pre-flight

```bash
# 1. Working directory check
cd ~/Dropbox/Projects/CRMBuilder
pwd

# 2. Clean status check
git status

# 3. Git identity
git config user.name
git config user.email

# 4. Pull rebase
git pull --rebase origin main

# 5. Payload and rule file exist
ls PRDs/product/crmbuilder-v2/close-out-payloads/ses_405.json
ls PRDs/product/crmbuilder-v2/close-out-payloads/governance_rules_ses_405.json

# 6. API health check
curl -s http://127.0.0.1:8765/health -H "X-Engagement: CRMBUILDER"

# 7. Pre-apply identifier heads — every one must be exactly the value shown, or re-key first
for e in sessions conversations decisions planning-items; do
  curl -s "http://127.0.0.1:8765/$e/next-identifier" -H "X-Engagement: CRMBUILDER"; echo
done
# Expected: SES-405, CNV-379, DEC-1053, PI-471
curl -s "http://127.0.0.1:8765/governance-rules/next-identifier" -H "X-Engagement: CRMBUILDER"; echo
# Expected: GVR-242 (informational; rule identifiers are server-assigned)
```

---

## Apply — step 1, the close-out payload

```bash
uv run python crmbuilder-v2/scripts/apply_close_out.py \
  PRDs/product/crmbuilder-v2/close-out-payloads/ses_405.json \
  --engagement CRMBUILDER
```

**Expected OK record counts:** 1 conversation, 1 session, 15 planning items, 3 decisions, 18 references (the two membership edges are written inline with their records).

## Apply — step 2, the governance rules

The apply script does not handle governance rules. Run this after step 1 succeeds; it needs DEC-1055 to exist because every rule names the decision that ruled it.

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
spec = json.load(open("PRDs/product/crmbuilder-v2/close-out-payloads/governance_rules_ses_405.json"))
for rule in spec["create"]:
    status, resp = call("POST", "/governance-rules", rule)
    ident = (resp.get("data") or {}).get("identifier")
    print(f"POST {rule['rule_type']}: HTTP {status} -> {ident}")
    if status not in (200, 201, 409):
        print(resp.get("errors") or resp)
for amend in spec["amend"]:
    ident = amend.pop("identifier")
    status, resp = call("PATCH", f"/governance-rules/{ident}", amend)
    print(f"PATCH {ident}: HTTP {status}")
    if status not in (200, 201):
        print(resp.get("errors") or resp)
EOF
```

**Expected:** four `HTTP 201` lines with new GVR identifiers, two `HTTP 200` lines. A 409 on a POST means the rule text already exists at that scope (the lifecycle rule allows one rule per text per scope) — report it, do not retry with altered text.

---

## Post-apply verification

```bash
# Heads advanced
for e in sessions conversations decisions planning-items; do
  curl -s "http://127.0.0.1:8765/$e/next-identifier" -H "X-Engagement: CRMBUILDER"; echo
done
# Expected: SES-406, CNV-380, DEC-1056, PI-486

# Spot-check the session and one decision
curl -s "http://127.0.0.1:8765/sessions/SES-405" -H "X-Engagement: CRMBUILDER" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['session_title'])"
curl -s "http://127.0.0.1:8765/decisions/DEC-1053" -H "X-Engagement: CRMBUILDER" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['title'])"

# Decided-in references resolve
curl -s "http://127.0.0.1:8765/references?target_type=session&target_id=SES-405" -H "X-Engagement: CRMBUILDER" | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted((r['source_id'], r['relationship']) for r in d))"
# Expected: CNV-379 conversation_belongs_to_session, DEC-1053..1055 decided_in

# The four writing rules are in the effective ruleset for every audience
curl -s "http://127.0.0.1:8765/governance-rules?resolution=effective&applies_to=all" -H "X-Engagement: CRMBUILDER" | python3 -c "
import sys,json
rows=json.load(sys.stdin)['data']
print([r['rule_type'] for r in rows if str(r.get('rule_type','')).startswith('writing_')])"
# Expected: the four writing_* rule types

# The amended rules no longer name a person
curl -s "http://127.0.0.1:8765/governance-rules/GVR-232" -H "X-Engagement: CRMBUILDER" | python3 -c "import sys,json; b=json.load(sys.stdin)['data']['body']; print('Doug' in b, b[:80])"
curl -s "http://127.0.0.1:8765/governance-rules/GVR-237" -H "X-Engagement: CRMBUILDER" | python3 -c "import sys,json; b=json.load(sys.stdin)['data']['body']; print('Doug' in b, b[:80])"
# Expected: False on both

# A fresh Claude Code session loads the rules at start: confirm the session-start context includes them
uv run python crmbuilder-v2/src/crmbuilder_v2/session_context.py | grep -c "writing_"
# Expected: 4 (or more, if the context prints each rule more than once)
```

---

## Commit snapshots

The API write hook regenerates the db-export snapshots. Commit them with the deposit-event log:

```bash
git add PRDs/methodology-records/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "v2: governance snapshot — SES-405 apply (DEC-1053..1055, PI-471..485, four writing rules, GVR-232/237 amended)

Governed-By: PI-479
Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015Zpq98tPbuZ8CUUpmZoKEw"
git push origin main
```

If the commit gate refuses the Governed-By trailer because PI-479 is not yet visible to it, re-run after the snapshot regeneration completes; the item exists in the store after step 1.

---

## Done

Reply with:
- Heads before and after (SES, CNV, DEC, PI, GVR)
- Record counts applied in step 1, and the four new GVR identifiers from step 2
- Snapshot commit SHA
- Next conversation kickoff: in the Cleveland Business Mentors engagement, rule whether a person or the application moves a mentor candidate to Provisional (the definition says a person, after email and training are set up; the prototype does it once the mailbox exists), then write the Mentor Application transition table (PI-471) and field roles (PI-472). The register is at specifications/application-generation/gap-register-mentor-application.md.

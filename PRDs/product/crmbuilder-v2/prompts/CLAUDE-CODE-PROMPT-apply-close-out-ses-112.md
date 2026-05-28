# Apply close-out — SES-112 / CNV-014 (v2 AI Surface Integration / WS-010)

## 1. Purpose

Apply the close-out payload at
`PRDs/product/crmbuilder-v2/close-out-payloads/ses_112.json` to the CRMBUILDER
engagement's v2 governance database, recording the remote-MCP-access /
own-OAuth-server work.

**Net effect (records that will land):**

| Section | Count | Identifiers |
|---|---|---|
| session | 1 | SES-112 |
| conversation | 1 | CNV-014 |
| work_tickets | 0 | — |
| planning_items | 1 | PI-104 (new, Open) |
| commits | 1 | 5b098bc |
| decisions | 3 | DEC-326, DEC-327, DEC-328 (all Active) |
| references | 6 | 3× decided_in (DEC-326/327/328 → CNV-014); DEC-327 supersedes DEC-226; DEC-326 is_about DEC-244; DEC-328 is_about DEC-244 |
| resolves_planning_items | 1 | PI-049 → Resolved (atomic flip) |
| addresses_planning_items | 2 | PI-045, PI-104 |
| deposit_event | 1 | DEP-NNN (auto), → COP-112 |

**Post-apply manual step:** the apply only POSTs the `supersedes` edge; flip
DEC-226 to `Superseded` with a PATCH (step 5).

## 2. Pre-flight

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
pwd                                   # expect repo root
git status --short                    # note any unrelated parallel-orchestrator churn
git rev-parse --abbrev-ref HEAD       # expect main
curl -s -m5 http://127.0.0.1:8765/health   # expect 200
test -f PRDs/product/crmbuilder-v2/close-out-payloads/ses_112.json && echo "payload present"
# Identifier-head re-capture (PARALLEL ORCHESTRATOR ACTIVE — re-key if any collide):
for ep in sessions conversations decisions planning-items; do
  echo -n "$ep head: "
  curl -s -m5 "http://127.0.0.1:8765/$ep?limit=3000" | python3 -c "import sys,json,re;rows=json.load(sys.stdin).get('data') or [];b={}
for r in rows:
 i=r.get('session_identifier') or r.get('conversation_identifier') or r.get('identifier') or r.get('work_ticket_identifier') or ''
 m=re.match(r'([A-Z]+)-(\d+)',i or '')
 if m:b[m.group(1)]=max(b.get(m.group(1),0),int(m.group(2)))
print(b)"
done
```

Expected free at draft time: SES-112, CNV-014, DEC-326/327/328, PI-104.
**If any are now taken, re-key the payload (and this prompt) to the next free
slots before applying** — a collision would be silently skipped as HTTP 409
(the known apply 409-skip behavior), not loudly failed.

## 3. Apply

```bash
cd /home/doug/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_112.json
```

Expect ✓ on: 1 conversation, 1 session, 1 planning_item, 1 commit, 3 decisions,
6 references, 1 resolves edge, 2 addresses edges, and a deposit_event POST.
Exit code 0.

## 4. Post-apply verification

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
curl -s -m5 http://127.0.0.1:8765/sessions/SES-112 | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('SES-112',d['session_status'],'| WS edge ok')"
curl -s -m5 http://127.0.0.1:8765/decisions/DEC-327 | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('DEC-327',d['status'])"
curl -s -m5 http://127.0.0.1:8765/planning-items/PI-049 | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('PI-049',d['status'],'(expect Resolved)')"
curl -s -m5 http://127.0.0.1:8765/planning-items/PI-104 | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print('PI-104',d['status'],'(expect Open)')"
# decided_in resolves:
curl -s -m5 "http://127.0.0.1:8765/references?source_id=DEC-326" | python3 -c "import sys,json;print('DEC-326 edges:',[(r['relationship'],r['target_id']) for r in json.load(sys.stdin)['data']])"
```

## 5. Flip DEC-226 to Superseded (manual PATCH — apply only wrote the edge)

```bash
curl -s -m5 -X PATCH http://127.0.0.1:8765/decisions/DEC-226 \
  -H "Content-Type: application/json" \
  -d '{"status":"Superseded","superseded_by":"DEC-327"}' \
  | python3 -c "import sys,json;d=json.load(sys.stdin).get('data') or {};print('DEC-226 now',d.get('status'),'superseded_by',d.get('superseded_by'))"
```

## 6. Commit snapshot regeneration

The apply transactionally regenerated `db-export/*.json` and wrote
`deposit-event-logs/dep_NNN.log`. Commit them with the payload, the apply
prompt, and the OAuth-server systemd/config note:

```bash
cd /home/doug/Dropbox/Projects/crmbuilder
git add PRDs/product/crmbuilder-v2/db-export/ \
        PRDs/product/crmbuilder-v2/deposit-event-logs/ \
        PRDs/product/crmbuilder-v2/close-out-payloads/ses_112.json \
        PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-112.md
git commit -m "v2: SES-112 close-out applied — DEC-326/327/328 (own OAuth 2.1 server for remote MCP) + PI-049 resolved + PI-104 filed"
```

## 7. Done block

Reply with: heads before/after, record counts from the apply, the DEC-226
PATCH result, the deposit-event identifier + log path, and the snapshot-commit
SHA. Note that commit `5b098bc` (the OAuth server code) and this close-out
commit both still need `git push`.

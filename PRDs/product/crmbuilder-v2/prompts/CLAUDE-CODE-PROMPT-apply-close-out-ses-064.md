# CLAUDE-CODE-PROMPT — Apply SES-064 close-out payload

**Last Updated:** 05-23-26 21:30
**Purpose:** Apply the SES-064 close-out payload — the V2 remote-access deployment architectural decision conversation that settles four decisions (DEC-201 through DEC-204) and authors planning item PI-045 scoping the implementation workstream.
**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_064.json`
**Predecessor sessions in apply order:** SES-058 → SES-059 → SES-060 → SES-061 → SES-062 → SES-063, all of which must already be applied before this one. SES-062 is the PI-025 prior-conversations backfill planning payload (parallel sandbox A, DEC-191..197) and SES-063 is the PI-029 commit entity schema spec payload (parallel sandbox B, DEC-198..200); both were pushed before this conversation's payload reached origin. This conversation rebased twice (SES-062 → SES-063 → SES-064) and is unrelated to either predecessor's workstream content but must apply after both. Each predecessor has its own apply prompt under `PRDs/product/crmbuilder-v2/prompts/`. If `curl -sf http://127.0.0.1:8765/sessions/SES-063` returns 404, apply the predecessor chain first and then return here.

---

## Net Effect

After this apply lands, the CRMBUILDER engagement database will hold the four governance decisions that scope the V2 remote-access deployment workstream and the planning item PI-045 that will be opened by the deployment kickoff prompt drafted in the follow-on conversation. No code changes, no new entity types, no new relationship_kinds, no methodology documents are produced by this conversation — the deliverables are purely the four decisions and the one planning item.

After this apply, the next action is to open a separate Claude.ai conversation to draft the deployment kickoff prompt for PI-045 (the in-flight follow-on named in the session record's `in_flight_at_end` field). The deployment kickoff conversation will read DEC-201 through DEC-204 as inputs and produce the kickoff document under `PRDs/product/crmbuilder-v2/`.

---

## Scope

Apply `close-out-payloads/ses_064.json` using `crmbuilder-v2/scripts/apply_close_out.py`. The payload contains:

- 1 session record (SES-064)
- 4 decisions (DEC-201 V2 remote-access architecture Option A; DEC-202 MCP-only exposure; DEC-203 marker-driven engagement routing; DEC-204 Cloudflare Tunnel on mcp.crmbuilder.com)
- 1 planning item (PI-045 V2 remote-access deployment)
- 5 references (4 `decided_in` linking each decision to SES-064; 1 `is_about` linking SES-064 to PI-045)

The payload is idempotent on re-run; HTTP 409 SKIPs are treated as already-present.

---

## Pre-flight

```bash
# Working directory
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2 || cd ~/crmbuilder/crmbuilder-v2

# Clean status check
cd .. && git status --porcelain
# Expect clean. If anything is staged or modified, halt and resolve before continuing.
cd crmbuilder-v2

# Git identity
git config user.email
git config user.name
# Expect doug@dougbower.com and Doug Bower

# Pull latest commits from origin/main (SES-064 payload was pushed from the architectural decision sandbox)
cd .. && git pull --rebase origin main && cd crmbuilder-v2

# API health
curl -sf http://127.0.0.1:8765/health
# If this fails, start the API:
#   uv run crmbuilder-v2-api &

# Verify the payload file exists
ls -la ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_064.json

# Verify the API is routed to the CRMBUILDER engagement (the dogfood DB, not CBM)
# Look for the latest session to be SES-063 (the PI-029 commit entity schema spec, applied immediately before this)
curl -s http://127.0.0.1:8765/sessions \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d), 'sessions - latest:', sorted(r['identifier'] for r in d)[-1] if d else 'none')"

# Verify SES-063 has been applied (the immediate predecessor in apply order — PI-029 commit entity schema spec from parallel sandbox B)
curl -sf http://127.0.0.1:8765/sessions/SES-063 | head -5
# If this returns 404, the predecessor chain has not been fully applied. Apply in order via:
#   PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-058.md
#   PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-059.md
#   PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-060.md
#   PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-061.md
#   PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-062.md (PI-025 backfill planning, sandbox A)
#   PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-063.md (PI-029 commit entity schema spec, sandbox B)
# Return to this prompt after SES-063 lands.

# Capture pre-apply identifier heads for post-apply verification
echo "=== Pre-apply heads ==="
echo "Sessions:"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Decisions:"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Planning items:"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "References (count):"
curl -s 'http://127.0.0.1:8765/references?limit=1000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"
```

Expected pre-apply heads: SES-063, DEC-200, PI-044. Reference count will vary; capture for delta verification.

---

## Apply

Run the apply script against the payload:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_064.json
```

Expected output structure:

- 1 session OK (SES-064)
- 4 decisions OK (DEC-201, DEC-202, DEC-203, DEC-204)
- 1 planning item OK (PI-045)
- 5 references OK
- 1 deposit_event written at apply close

If any record returns 409 SKIP on first run, halt and investigate — first run should have zero SKIPs. On re-run, every record should SKIP idempotently.

---

## Post-apply verification

```bash
# Head advancement
echo "=== Post-apply heads ==="
echo "Sessions (expect SES-064):"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Decisions (expect DEC-204):"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Planning items (expect PI-045):"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"

# Reference count delta — expect +5
echo "References after apply:"
curl -s 'http://127.0.0.1:8765/references?limit=1000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"

# Spot check SES-064
curl -s http://127.0.0.1:8765/sessions/SES-064 | python3 -m json.tool | head -25

# Spot check DEC-201 (the architectural decision — Option A)
curl -s http://127.0.0.1:8765/decisions/DEC-201 | python3 -m json.tool | head -20

# Spot check DEC-204 (the tunnel host decision)
curl -s http://127.0.0.1:8765/decisions/DEC-204 | python3 -m json.tool | head -20

# Spot check PI-045
curl -s http://127.0.0.1:8765/planning-items/PI-045 | python3 -m json.tool | head -15

# Spot check the decided_in resolution for DEC-201
curl -s 'http://127.0.0.1:8765/references?source_type=decision&source_id=DEC-201' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(r['source_id'], '->', r['target_id'], '[', r['relationship'], ']') for r in d]"
# Expect at minimum:
#   DEC-201 -> SES-064 [ decided_in ]

# Spot check the is_about edge linking SES-064 to PI-045
curl -s 'http://127.0.0.1:8765/references?source_type=session&source_id=SES-064' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(r['source_id'], '->', r['target_id'], '[', r['relationship'], ']') for r in d]"
# Expect at minimum:
#   SES-064 -> PI-045 [ is_about ]

# Confirm decision count
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('total decisions:', len(d))"
# Expect 204 (was 200 before this apply).

# Confirm planning item count
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('total planning items:', len(d))"
# Expect 45 (was 44 before this apply).
```

---

## Commit snapshot regeneration

The apply script transactionally regenerates the engagement's db-export JSON snapshots on every API write via the `_refresh_snapshot` hook in `crmbuilder-v2/src/crmbuilder_v2/access/engagement.py`. The `change_log.json` file also gets one audit row per write with before/after payloads. After a successful apply, commit the regenerated snapshots together with the deposit-event log:

```bash
cd ~/Dropbox/Projects/crmbuilder

# Inspect what changed (should be sessions, decisions, planning_items, references, deposit_events, change_log, plus deposit-event log)
git status PRDs/product/crmbuilder-v2/db-export/
git status PRDs/product/crmbuilder-v2/deposit-event-logs/

# Commit the snapshot regeneration in a single commit
git add PRDs/product/crmbuilder-v2/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "Apply SES-064 close-out: V2 remote-access deployment architecture

Records landed via apply_close_out.py against CRMBUILDER engagement:
- 1 session (SES-064)
- 4 decisions (DEC-201 V2 remote-access architecture Option A,
  local-canonical SQLite with public MCP via tunnel; DEC-202 MCP-only
  exposure, REST API stays on localhost; DEC-203 marker-driven single
  remote MCP versus per-engagement deploys; DEC-204 Cloudflare Tunnel
  on mcp.crmbuilder.com with Access + shared-secret auth)
- 1 planning item (PI-045 V2 remote-access deployment workstream)
- 5 references (4 decided_in, 1 is_about to PI-045)
- 1 deposit_event

Next action: open a separate Claude.ai conversation to draft the
deployment kickoff prompt for PI-045 per the four decisions above."

git pull --rebase origin main
git push
```

---

## Done

Reply with:

- **Pre-apply heads:** SES-063, DEC-200, PI-044, references = N (captured)
- **Post-apply heads:** SES-064, DEC-204, PI-045, references = N + 5
- **Record counts:** expect 1 session OK, 4 decisions OK, 1 planning item OK, 5 references OK, 0 SKIPs on first run
- **Snapshot commit SHA** from the commit-snapshot-regeneration step
- **Next-conversation kickoff path:** No kickoff document yet — open a new Claude.ai conversation with the seed prompt "Draft the V2 remote-access deployment kickoff prompt for PI-045 per the four decisions in SES-064 (DEC-201 through DEC-204)." That conversation produces the kickoff document under `PRDs/product/crmbuilder-v2/`.

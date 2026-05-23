# CLAUDE-CODE-PROMPT — Apply SES-065 close-out payload

**Last Updated:** 05-23-26 23:55
**Purpose:** Apply the SES-065 close-out payload — the PI-045 V2 remote-access deployment planning conversation that settles DEC-205 (engagement-marker fail-loud on drift), records the five decide-and-announce implementation choices inline in the session narrative, and authors the three Claude Code prompts for the PI-045 code-changes implementation conversation.
**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_065.json`
**Predecessor sessions in apply order:** SES-064 must already be applied. The SES-064 close-out (V2 remote-access deployment architectural decisions DEC-201..DEC-204 and PI-045 authoring) was pushed before this conversation opened and the snapshots at HEAD show it as applied locally. If `curl -sf http://127.0.0.1:8765/sessions/SES-064` returns 404, apply `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-064.md` first and then return here.

---

## Net Effect

After this apply lands, the CRMBUILDER engagement database will hold the one governance decision settled by this planning conversation (DEC-205 fail-loud on engagement-marker drift) and three reference edges (DEC-205 → SES-065 decided_in; SES-065 → PI-045 is_about; DEC-205 → DEC-203 references — the trace edge linking the implementing decision to the original footgun-naming decision). No new planning items are authored — PI-045 already exists from SES-064 and this conversation operates against it.

After this apply, the next action is the PI-045 code-changes Claude Code conversation that runs slices A, B, C in series. The three slice prompts land at the same push as the close-out payload and apply prompt:

- `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-045-A-transport-flag-and-http-binding.md`
- `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-045-B-shared-secret-middleware.md`
- `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-045-C-marker-handling.md`

---

## Scope

Apply `close-out-payloads/ses_065.json` using `crmbuilder-v2/scripts/apply_close_out.py`. The payload contains:

- 1 session record (SES-065)
- 1 decision (DEC-205 engagement-marker fail-loud guard on the remote v2 API)
- 0 planning items (PI-045 already exists from SES-064)
- 3 references (DEC-205 decided_in SES-065; SES-065 is_about PI-045; DEC-205 references DEC-203)

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

# Pull latest commits from origin/main (SES-065 payload was pushed from the planning sandbox)
cd .. && git pull --rebase origin main && cd crmbuilder-v2

# API health
curl -sf http://127.0.0.1:8765/health
# If this fails, start the API:
#   uv run crmbuilder-v2-api &

# Verify the payload file exists
ls -la ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_065.json

# Verify the API is routed to the CRMBUILDER engagement (the dogfood DB, not CBM)
# Look for the latest session to be SES-064 (the architectural decision conversation, applied before this)
curl -s http://127.0.0.1:8765/sessions \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d), 'sessions - latest:', sorted(r['identifier'] for r in d)[-1] if d else 'none')"

# Verify SES-064 has been applied (the immediate predecessor in apply order)
curl -sf http://127.0.0.1:8765/sessions/SES-064 | head -5
# If this returns 404, apply the predecessor:
#   PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-064.md
# Return to this prompt after SES-064 lands.

# Verify DEC-203 has been applied (the target of the trace-edge reference DEC-205 -> DEC-203)
curl -sf http://127.0.0.1:8765/decisions/DEC-203 | head -5
# If this returns 404, the predecessor chain is incomplete; apply ses-064 first.

# Verify PI-045 has been applied (the target of the is_about edge SES-065 -> PI-045)
curl -sf http://127.0.0.1:8765/planning-items/PI-045 | head -5
# If this returns 404, the predecessor chain is incomplete; apply ses-064 first.

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

Expected pre-apply heads: SES-064, DEC-204, PI-045. Reference count will vary; capture for delta verification.

---

## Apply

Run the apply script against the payload:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_065.json
```

Expected output structure:

- 1 session OK (SES-065)
- 1 decision OK (DEC-205)
- 0 planning items (no planning_items in this payload)
- 3 references OK
- 1 deposit_event written at apply close

If any record returns 409 SKIP on first run, halt and investigate — first run should have zero SKIPs. On re-run, every record should SKIP idempotently.

---

## Post-apply verification

```bash
# Head advancement
echo "=== Post-apply heads ==="
echo "Sessions (expect SES-065):"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Decisions (expect DEC-205):"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Planning items (expect PI-045 — unchanged from pre-apply):"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"

# Reference count delta — expect +3
echo "References after apply:"
curl -s 'http://127.0.0.1:8765/references?limit=1000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"

# Spot check SES-065
curl -s http://127.0.0.1:8765/sessions/SES-065 | python3 -m json.tool | head -25

# Spot check DEC-205 (the fail-loud marker-guard decision)
curl -s http://127.0.0.1:8765/decisions/DEC-205 | python3 -m json.tool | head -30

# Spot check the decided_in resolution for DEC-205
curl -s 'http://127.0.0.1:8765/references?source_type=decision&source_id=DEC-205' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(r['source_id'], '->', r['target_id'], '[', r['relationship'], ']') for r in d]"
# Expect at minimum:
#   DEC-205 -> SES-065 [ decided_in ]
#   DEC-205 -> DEC-203 [ references ]

# Spot check the is_about edge linking SES-065 to PI-045
curl -s 'http://127.0.0.1:8765/references?source_type=session&source_id=SES-065' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(r['source_id'], '->', r['target_id'], '[', r['relationship'], ']') for r in d]"
# Expect at minimum:
#   SES-065 -> PI-045 [ is_about ]

# Confirm decision count
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('total decisions:', len(d))"
# Expect 205 (was 204 before this apply).

# Confirm session count
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('total sessions:', len(d))"
# Expect 65 (was 64 before this apply).

# Confirm planning item count UNCHANGED (this payload authors no new planning items)
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('total planning items:', len(d))"
# Expect 45 (same as before — PI-045 already existed).
```

---

## Commit snapshot regeneration

The apply script transactionally regenerates the engagement's db-export JSON snapshots on every API write via the `_refresh_snapshot` hook in `crmbuilder-v2/src/crmbuilder_v2/access/engagement.py`. The `change_log.json` file also gets one audit row per write with before/after payloads. After a successful apply, commit the regenerated snapshots together with the deposit-event log:

```bash
cd ~/Dropbox/Projects/crmbuilder

# Inspect what changed (should be sessions, decisions, references, deposit_events, change_log, plus deposit-event log)
git status PRDs/product/crmbuilder-v2/db-export/
git status PRDs/product/crmbuilder-v2/deposit-event-logs/

# Commit the snapshot regeneration in a single commit
git add PRDs/product/crmbuilder-v2/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "Apply SES-065 close-out: PI-045 V2 remote-access deployment planning

Records landed via apply_close_out.py against CRMBUILDER engagement:
- 1 session (SES-065)
- 1 decision (DEC-205 engagement-marker fail-loud guard: capture
  active_code at API process start in api/marker_guard._MARKER_AT_START,
  middleware in api.main.create_app() returns HTTP 409 on drift with
  structured body and a WARNING log line; exempt paths /health,
  /openapi.json, /docs, /redoc bypass; manual restart in v1)
- 3 references (DEC-205 decided_in SES-065; SES-065 is_about PI-045;
  DEC-205 references DEC-203 — trace edge to the original footgun-
  naming decision)
- 1 deposit_event

Next action: open a Claude Code session at the laptop and run the
PI-045 code-changes implementation conversation through slices A, B,
and C in series. Prompts at:
  PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-045-A-transport-flag-and-http-binding.md
  PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-045-B-shared-secret-middleware.md
  PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-045-C-marker-handling.md"

git pull --rebase origin main
git push
```

---

## Done

Reply with:

- **Pre-apply heads:** SES-064, DEC-204, PI-045, references = N (captured)
- **Post-apply heads:** SES-065, DEC-205, PI-045 (unchanged), references = N + 3
- **Record counts:** expect 1 session OK, 1 decision OK, 0 planning items, 3 references OK, 0 SKIPs on first run
- **Snapshot commit SHA** from the commit-snapshot-regeneration step
- **Next-conversation kickoff path:** Open a Claude Code session at the laptop and start with `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-045-A-transport-flag-and-http-binding.md` (slice A); slices B and C follow in sequence per the predecessor/successor pointers in each prompt's header.

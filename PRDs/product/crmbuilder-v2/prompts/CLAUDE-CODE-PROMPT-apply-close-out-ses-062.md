# CLAUDE-CODE-PROMPT — Apply SES-062 close-out payload

**Last Updated:** 05-23-26 22:30
**Purpose:** Apply the SES-062 close-out payload — the ARCHITECTURE-mode planning conversation that scoped the PI-025 prior-conversations backfill, settled seven governing decisions (DEC-191 scope with WS-008 audit-v1.2 fold-in, DEC-192 WS-006 cross-engagement Option IV defer, DEC-193 born-complete single-POST pattern, DEC-194 unambiguous succeeds-chain policy, DEC-195 source-document field defaults, DEC-196 work_ticket backfill scope, DEC-197 sixteen orphan sessions deferred), and authored the Claude Code prompt that will land WS-008 and the 37 conversation+work_ticket pairs out-of-band.
**Payload file:** `PRDs/product/crmbuilder-v2/close-out-payloads/ses_062.json`
**Predecessor sessions:** SES-060 (audit-v1.2 planning resolved) and SES-061 (Code Change Lifecycle methodology drafted). Both close-out payloads must be applied before this one. If `curl -sf http://127.0.0.1:8765/sessions/SES-061` returns 404, apply SES-060's and SES-061's close-outs first via their respective apply prompts and return here.
**Successor prompt:** After this apply lands, run the PI-025 backfill prompt at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-025-prior-conversations-backfill.md` to land the 1 workstream (WS-008), 37 work_tickets, 37 conversation records, and ~140 reference edges. The backfill prompt depends on DEC-191..197 (landed by this apply) being present for its commit messages to reference; running it before this apply does not break correctness, but the dependency is more legible when applied in order.

---

## Scope

Apply `close-out-payloads/ses_062.json` using the existing `crmbuilder-v2/scripts/apply_close_out.py` script. The payload contains:

- 1 session record (SES-062)
- 7 decisions (DEC-191 through DEC-197)
- 0 planning items
- 7 references (7 `decided_in` linking each decision to SES-062)

The payload is idempotent on re-run; HTTP 409 SKIPs are treated as already-present.

This payload does NOT author the WS-008 workstream record, the 37 work_ticket records, the 37 conversation records, or any of the supporting references (workstream-membership, session-record, work_ticket, succeeds-chain). Those land via the backfill prompt named above, which installs `crmbuilder-v2/scripts/backfill_pi_025_prior_conversations.py` and runs it. The close-out payload's session record's `artifacts_produced` and `in_flight_at_end` fields note this explicitly.

---

## Pre-flight

```bash
# Working directory
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2 || cd ~/crmbuilder/crmbuilder-v2

# Confirm clean working tree
git status

# API health
curl -sf http://127.0.0.1:8765/health
# If this fails, start the API:
#   uv run crmbuilder-v2-api &

# Pull latest commits from origin/main (SES-062 payload and the PI-025
# backfill prompt were pushed from the planning sandbox)
cd .. && git pull --rebase origin main && cd crmbuilder-v2

# Verify the payload file exists
ls -la ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_062.json

# Verify the backfill prompt also exists (same sandbox push)
ls -la ../PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-025-prior-conversations-backfill.md

# Verify the API is routed to the CRMBUILDER engagement (the dogfood DB, not CBM)
curl -s http://127.0.0.1:8765/sessions \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d), 'sessions - latest:', sorted(r['identifier'] for r in d)[-1] if d else 'none')"
# Expect 61 sessions, latest SES-061. After this apply, expect 62 sessions, latest SES-062.

# Verify SES-061 has been applied (the immediate predecessor)
curl -sf http://127.0.0.1:8765/sessions/SES-061 | head -5
# If this returns 404, SES-061 (and possibly SES-060) have not been applied.
# Apply SES-060's close-out first, then SES-061's, then return to this prompt.

# Capture pre-apply identifier heads for post-apply verification
echo "=== Pre-apply heads ==="
echo "Sessions:"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Decisions:"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "Planning items:"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1] if d else 'none')"
echo "References (count):"
curl -s 'http://127.0.0.1:8765/references?limit=4000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"
echo "Workstreams (expect WS-007, unchanged by this apply):"
curl -s http://127.0.0.1:8765/workstreams | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['workstream_identifier'] for r in d)[-1] if d else 'none')"
echo "Conversations (expect CONV-008, unchanged by this apply):"
curl -s http://127.0.0.1:8765/conversations | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['conversation_identifier'] for r in d)[-1] if d else 'none')"
```

Expected pre-apply heads: SES-061, DEC-190, PI-044, WS-007, CONV-008. Reference count varies; capture for delta verification.

---

## Apply

Run the apply script against the payload:

```bash
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python scripts/apply_close_out.py \
  ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_062.json
```

Expected output structure:

- 1 session OK (SES-062)
- 7 decisions OK (DEC-191 through DEC-197)
- 0 planning items
- 7 references OK
- 1 deposit_event written at apply close

If any record returns 409 SKIP on first run, halt and investigate — first run should have zero SKIPs. On re-run, every record should SKIP idempotently.

---

## Post-apply verification

```bash
# Head advancement
echo "=== Post-apply heads ==="
echo "Sessions (expect SES-062):"
curl -s http://127.0.0.1:8765/sessions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Decisions (expect DEC-197):"
curl -s http://127.0.0.1:8765/decisions | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Planning items (expect PI-044 — unchanged):"
curl -s http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['identifier'] for r in d)[-1])"
echo "Workstreams (expect WS-007 — unchanged; WS-008 lands via backfill prompt):"
curl -s http://127.0.0.1:8765/workstreams | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(sorted(r['workstream_identifier'] for r in d)[-1])"

# Spot check SES-062
curl -s http://127.0.0.1:8765/sessions/SES-062 | python3 -m json.tool | head -20

# Spot check DEC-191 (scope decision) — confirm WS-008 fold-in language
curl -s http://127.0.0.1:8765/decisions/DEC-191 | python3 -m json.tool | head -20

# Spot check DEC-192 (WS-006 Option IV defer)
curl -s http://127.0.0.1:8765/decisions/DEC-192 | python3 -m json.tool | head -20

# Spot check a decided_in reference: find DEC-191 → SES-062 reference and confirm it resolves
curl -s 'http://127.0.0.1:8765/references?source_type=decision&source_id=DEC-191' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; [print(r['source_id'], '->', r['target_id'], '[', r['relationship_kind'], ']') for r in d]"
# Expect at minimum: DEC-191 -> SES-062 [ decided_in ]

# Confirm reference total delta is +12 from pre-apply
# (7 payload refs + 4 wrote_record edges from the apply script's deposit_event POST + 1 applies_close_out_payload edge to the lazy-created COP-062)
echo "Reference total after apply:"
curl -s 'http://127.0.0.1:8765/references?limit=4000' | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(len(d))"
```

Expected: sessions head SES-062, decisions head DEC-197, planning_items head PI-044 (unchanged), workstreams head WS-007 (unchanged), reference total +12 from pre-apply (7 payload `decided_in` refs + 4 `wrote_record` edges from the deposit_event POST + 1 `applies_close_out_payload` edge to the lazy-created COP-062).

---

## Commit snapshot regeneration

The apply script transactionally regenerates the engagement's db-export JSON snapshots on every API write via the `_refresh_snapshot` hook in `crmbuilder-v2/src/crmbuilder_v2/access/engagement.py`. The `change_log.json` file also gets one audit row per write with before/after payloads. After a successful apply, commit the regenerated snapshots together with the deposit-event log:

```bash
cd ~/Dropbox/Projects/crmbuilder

# Inspect what changed (should be sessions.json, decisions.json, references.json,
# change_log.json, plus the deposit-event log)
git status PRDs/product/crmbuilder-v2/db-export/
git status PRDs/product/crmbuilder-v2/deposit-event-logs/

# Commit the snapshot regeneration in a single commit
git add PRDs/product/crmbuilder-v2/db-export/ PRDs/product/crmbuilder-v2/deposit-event-logs/
git commit -m "Apply SES-062 close-out: PI-025 prior-conversations backfill planned

Records landed via apply_close_out.py against CRMBUILDER engagement:
- 1 session (SES-062)
- 7 decisions (DEC-191 scope with WS-008 audit-v1.2 fold-in;
  DEC-192 WS-006 cross-engagement Option IV defer;
  DEC-193 born-complete single-POST pattern;
  DEC-194 unambiguous succeeds-chain policy;
  DEC-195 source-document field defaults;
  DEC-196 work_ticket backfill scope (37 work_tickets);
  DEC-197 sixteen orphan sessions deferred)
- 0 planning items
- 7 references (7 decided_in)
- 1 deposit_event

WS-008 audit-v1.2 workstream, 37 work_ticket records, 37 conversation
records, and ~140 supporting reference edges land out-of-band via the
backfill prompt at PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-
PROMPT-pi-025-prior-conversations-backfill.md, applied next."

git pull --rebase origin main
git push
```

---

## Done

Reply with:

- Pre-apply heads: SES-061, DEC-190, PI-044, WS-007, CONV-008, references = N (captured)
- Post-apply heads: SES-062, DEC-197, PI-044 (unchanged), WS-007 (unchanged), CONV-008 (unchanged), references = N + 12 (7 payload refs + 4 wrote_record edges + 1 applies_close_out_payload edge)
- Record counts (expect 1 session OK, 7 decisions OK, 0 planning items, 7 references OK, 0 SKIPs on first run)
- Snapshot commit SHA from the commit-snapshot-regeneration step
- Next prompt to run: `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-025-prior-conversations-backfill.md` — installs and runs the backfill script that lands the WS-008 workstream record, the 37 work_ticket records, the 37 conversation records, and the ~140 supporting reference edges
